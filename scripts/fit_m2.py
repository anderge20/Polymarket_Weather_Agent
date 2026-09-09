#!/usr/bin/env python3
"""
fit_m2.py — compute and write the M2 error quantiles  (v2)
===========================================================

Implements `PREREG_M2_ERROR_v2.md` (sha b2b168d4...), which replaces v1 after
A-32's hostile refutation found two defects I verified myself:

  D-1  the pairing used `CAST(observation_time AS DATE)` on a TIMESTAMPTZ, so the
       sample size depended on the DuckDB session TimeZone: 2 599 (UTC) vs 1 881
       (Asia/Shanghai). Now the pair key is the station's LOCAL day.
  D-2  training filtered on `target_date < D`, which leaks: the label of the
       previous day is not yet available at a 24 h-lead decision. Verified over
       8 stations: leaks in 8/8 at both leads, by -9 h to -43 h. Now the filter is
       the availability condition itself, pair by pair.

Writes `forecast_p10..p90` in CELSIUS; the move to the market's contractual unit
happens at feature time (B-7).

Usage:
    python3 scripts/fit_m2.py --db data/pmw.duckdb --out ~/pmw-e2
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from weather_agent import database as db  # noqa: E402
from weather_agent import error_model as em  # noqa: E402
from weather_agent import stations, weather  # noqa: E402

# The pairing and lead rules now live in `weather_agent.m2`: R17, R19 and the
# paper cycle need them too, and a second implementation in a script is how
# two prices.py nearly shipped.
from weather_agent.m2 import (  # noqa: E402
    DATASET_VERSION, LEADS, PREREG_SHA_V2 as PREREG_SHA, load_pairs,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/pmw.duckdb")
    ap.add_argument("--out", default=os.path.expanduser("~/pmw-e2"))
    args = ap.parse_args()

    con = db.init_db(db.connect(args.db))
    con.execute(
        """UPDATE weather_forecasts SET forecast_p10=NULL, forecast_p25=NULL,
           forecast_p50=NULL, forecast_p75=NULL, forecast_p90=NULL
           WHERE dataset_version = ? AND model = ?""",
        [DATASET_VERSION, weather.M1_MODEL],
    )
    pairs, issue_by_key, stats = load_pairs(con)
    print(f"pares (día local): {len(pairs)} · {stats}", flush=True)
    print(f"  por lead: {dict(Counter(p.lead_h for p in pairs))}", flush=True)
    if not pairs:
        return 1

    targets = sorted({(p.station, p.target_date, p.lead_h) for p in pairs})
    fitted: dict[str, dict] = {}
    scopes: Counter = Counter()
    written = 0

    for station, target, lead in targets:
        end = datetime(target.year, target.month, target.day, 12, tzinfo=timezone.utc)
        t = end - timedelta(hours=lead)
        q = em.quantiles_for(pairs, t, lead)   # v2 §3/§4: availability filter, pooled
        scopes[q.scope] += 1
        fitted[f"{station}|{target.isoformat()}|{lead}"] = {
            "scope": q.scope, "n": q.n, "quantiles": q.values
        }
        if not q.values:
            continue
        issue = issue_by_key.get((station, target, lead))
        if issue is None:
            continue
        rows = db.query(
            con,
            # model and record_version are BOTH part of this table's primary key
            # and neither was named. With one of each they coincide; with two, the
            # SELECT returns every version and each unscoped UPDATE writes to ALL
            # of them, so the last forecast_tmax processed fixes the quantiles of
            # every version. Same class as the price read returning another
            # token's price — caught by session A before it could fire.
            """SELECT issue_time, forecast_tmax, model, record_version
               FROM weather_forecasts
               WHERE station = ? AND target_date = ? AND issue_time = ?
                 AND model = ? AND dataset_version = ?""",
            [station, target.isoformat(), issue, weather.M1_MODEL, DATASET_VERSION],
        )
        for r in rows:
            fq = em.forecast_quantiles_c(float(r["forecast_tmax"]), q)
            con.execute(
                """UPDATE weather_forecasts
                   SET forecast_p10=?, forecast_p25=?, forecast_p50=?,
                       forecast_p75=?, forecast_p90=?
                   WHERE station=? AND target_date=? AND issue_time=?
                     AND model=? AND record_version=? AND dataset_version=?""",
                [fq[10], fq[25], fq[50], fq[75], fq[90], station,
                 target.isoformat(), r["issue_time"], r["model"],
                 r["record_version"], DATASET_VERSION],
            )
            written += 1

    print(f"estratos: {dict(scopes)} · filas escritas: {written}", flush=True)

    # ---- v2 §5: falsifiable acceptance, thresholds fixed before seeing results
    verdict: dict = {"criterios": {}}
    for lead in LEADS:
        sub = [p for p in pairs if p.lead_h == lead]
        if len(sub) < em.MIN_N:
            continue
        # holdout: the final third by target date, never used to fit itself
        sub.sort(key=lambda p: p.target_date)
        cut = int(len(sub) * 2 / 3)
        train, hold = sub[:cut], sub[cut:]
        q = em.fit((p.error_c for p in train), em.SCOPE_POOLED)
        cal = em.calibration(hold, q)
        mae = sum(abs(p.error_c) for p in sub) / len(sub)
        verdict["criterios"][f"lead_{lead}"] = {
            "calibracion": cal, "mae": mae, "n": len(sub),
            "anchura": (q.spread if q.values else None),
        }
    c9 = verdict["criterios"].get("lead_9", {})
    c24 = verdict["criterios"].get("lead_24", {})
    cal_ok = all(
        v.get("calibracion", {}).get("passes") for v in verdict["criterios"].values()
    )
    mono_ok = (c24.get("mae", 0) >= c9.get("mae", 0)) if c9 and c24 else False
    spread_ok = all(
        v.get("anchura") is not None and 0 < v["anchura"] <= em.MAX_SPREAD_C
        for v in verdict["criterios"].values()
    )
    verdict["calibracion_ok"] = cal_ok
    verdict["monotonia_horizonte_ok"] = mono_ok
    verdict["no_degenerado_ok"] = spread_ok
    verdict["VEREDICTO"] = "VALIDO" if (cal_ok and mono_ok and spread_ok) else "NO_VALIDO"
    print(json.dumps(verdict, indent=1, default=str), flush=True)

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "M2_ERROR_QUANTILES.json"), "w") as fh:
        json.dump(
            {"prereg_version": "v2", "prereg_sha256": PREREG_SHA,
             "n_pairs": len(pairs), "pairing_stats": stats,
             "scopes": dict(scopes), "acceptance": verdict, "strata": fitted},
            fh, indent=1, default=str,
        )
    if verdict["VEREDICTO"] != "VALIDO":
        print("M2 NO VALIDO por §5: los cuantiles quedan escritos pero NO deben usarse "
              "hasta resolver el criterio que falla.", flush=True)
    con.close()
    return 0 if verdict["VEREDICTO"] == "VALIDO" else 2


if __name__ == "__main__":
    raise SystemExit(main())
