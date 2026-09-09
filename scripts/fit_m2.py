#!/usr/bin/env python3
"""
fit_m2.py — compute and write the M2 error quantiles
=====================================================

Implements PREREG_M2_ERROR.md (sha 16b729e1...), frozen before any quantile was
computed. Writes `forecast_p10..p90` into `weather_forecasts`, in CELSIUS: the
table is unit-agnostic and `forecast_tmax` is Celsius. Conversion into the
market's contractual unit happens at feature time (B-7), where the band lives.

Emits `M2_ERROR_QUANTILES.json` (the fitted strata) and `M2_REPORT.md`.

Usage:
    python3 scripts/fit_m2.py --db data/pmw.duckdb --out ~/pmw-e2
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from weather_agent import database as db  # noqa: E402
from weather_agent import error_model as em  # noqa: E402

DATASET_VERSION = "backfill_2b_v1"
PREREG_SHA = "16b729e1d28f3cbab8a102ab7ebd67a451471a961a299726714e987d8223e55d"


def load_pairs(con):
    """(pairs, issue_by_key): the pairs, plus the run each (station, date, lead)
    actually used, so quantiles land on the row they were fitted for."""
    rows = db.query(
        con,
        """
        SELECT f.station, f.target_date, f.issue_time, f.forecast_tmax,
               o.tmax_observed
        FROM weather_forecasts f
        JOIN (SELECT station, CAST(observation_time AS DATE) AS d,
                     max(tmax_observed) AS tmax_observed
              FROM weather_observations
              WHERE dataset_version = ? GROUP BY 1, 2) o
          ON f.station = o.station AND f.target_date = o.d
        WHERE f.dataset_version = ? AND f.forecast_tmax IS NOT NULL
        """,
        [DATASET_VERSION, DATASET_VERSION],
    )
    # The lead is NOT stored on the row: the backfill keys on
    # (station, model, issue_time, target_date), and two leads can select the same
    # run. Recovering it by "hours from issue to endDate" was wrong — it collapsed
    # every pair onto lead 24 and silently pooled the two leads that the
    # preregistration (§4) says are never mixed. Instead, reproduce the selection
    # itself: for each station-day compute T at each lead, ask which run was
    # available then, and match the row to it. Deterministic, and it fails loudly
    # if a row matches no lead rather than being filed under a plausible one.
    from datetime import datetime, timezone
    from weather_agent import weather

    def pick_run(t, model, issue_hours=(0, 6, 12, 18), max_age_h=36):
        cursor = t.replace(minute=0, second=0, microsecond=0)
        limit = t - timedelta(hours=max_age_h)
        while cursor >= limit:
            if cursor.hour in issue_hours and weather.is_available_at(cursor, model, t):
                return cursor
            cursor -= timedelta(hours=1)
        return None

    out: list[em.Pair] = []
    issue_by_key: dict[tuple, object] = {}
    unmatched = 0
    for r in rows:
        td = r["target_date"]
        td = td.date() if hasattr(td, "date") else td
        issue = r["issue_time"]
        if issue.tzinfo is None:
            issue = issue.replace(tzinfo=timezone.utc)
        end = datetime(td.year, td.month, td.day, 12, tzinfo=timezone.utc)
        lead = None
        for candidate in (9, 24):
            run = pick_run(end - timedelta(hours=candidate), "icon_seamless")
            if run is not None and run == issue:
                lead = candidate
                break
        if lead is None:
            unmatched += 1
            continue
        issue_by_key[(r["station"], td, lead)] = r["issue_time"]
        out.append(
            em.Pair(
                station=r["station"],
                target_date=td,
                lead_h=lead,
                forecast_c=float(r["forecast_tmax"]),
                observed_c=float(r["tmax_observed"]),
            )
        )
    if unmatched:
        print(f"  AVISO: {unmatched} filas no corresponden a ningún lead preregistrado", flush=True)
    return out, issue_by_key


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/pmw.duckdb")
    ap.add_argument("--out", default=os.path.expanduser("~/pmw-e2"))
    args = ap.parse_args()

    con = db.init_db(db.connect(args.db))
    # clear any previously written quantiles: an earlier run fitted them with a
    # broken lead derivation, and a stale value is worse than a missing one.
    con.execute("""UPDATE weather_forecasts SET forecast_p10=NULL, forecast_p25=NULL,
                   forecast_p50=NULL, forecast_p75=NULL, forecast_p90=NULL
                   WHERE dataset_version = ?""", [DATASET_VERSION])
    pairs, issue_by_key = load_pairs(con)
    print(f"pares de entrenamiento: {len(pairs)}", flush=True)
    if not pairs:
        print("sin pares; nada que ajustar")
        return 1

    by_lead = Counter(p.lead_h for p in pairs)
    print(f"  por lead: {dict(by_lead)}", flush=True)

    # every (station, target_date, lead) that needs quantiles = every forecast row
    targets = sorted({(p.station, p.target_date, p.lead_h) for p in pairs})
    fitted: dict[str, dict] = {}
    scopes: Counter = Counter()
    written = 0

    for station, target, lead in targets:
        q = em.quantiles_for(pairs, station, target, lead)
        scopes[q.scope] += 1
        key = f"{station}|{target.isoformat()}|{lead}"
        fitted[key] = {"scope": q.scope, "n": q.n, "quantiles": q.values}
        if not q.values:
            continue  # §5/§8: no quantiles, no probability. build_feature returns None.
        # ONLY the row this stratum was fitted for. Writing lead-24 quantiles onto
        # the lead-9 row would silently mis-state the uncertainty of a different
        # horizon — the error grows with the lead, which is why §4 separates them.
        issue = issue_by_key.get((station, target, lead))
        if issue is None:
            continue
        rows = db.query(
            con,
            """SELECT issue_time, forecast_tmax FROM weather_forecasts
               WHERE station = ? AND target_date = ? AND issue_time = ?
                 AND dataset_version = ?""",
            [station, target.isoformat(), issue, DATASET_VERSION],
        )
        for r in rows:
            fq = em.forecast_quantiles_c(float(r["forecast_tmax"]), q)
            con.execute(
                """UPDATE weather_forecasts
                   SET forecast_p10 = ?, forecast_p25 = ?, forecast_p50 = ?,
                       forecast_p75 = ?, forecast_p90 = ?
                   WHERE station = ? AND target_date = ? AND issue_time = ?
                     AND dataset_version = ?""",
                [fq[10], fq[25], fq[50], fq[75], fq[90], station,
                 target.isoformat(), r["issue_time"], DATASET_VERSION],
            )
            written += 1

    print(f"estratos: {dict(scopes)}", flush=True)
    print(f"filas con cuantiles escritos: {written}", flush=True)

    os.makedirs(args.out, exist_ok=True)
    art = os.path.join(args.out, "M2_ERROR_QUANTILES.json")
    with open(art, "w") as fh:
        json.dump(
            {"prereg_sha256": PREREG_SHA, "n_pairs": len(pairs),
             "scopes": dict(scopes), "strata": fitted},
            fh, indent=1, default=str,
        )
    print(f"artefacto: {art}", flush=True)

    cov = db.query(
        con,
        """SELECT count(*) AS total,
                  sum(CASE WHEN forecast_p50 IS NOT NULL THEN 1 ELSE 0 END) AS con_q
           FROM weather_forecasts WHERE dataset_version = ?""",
        [DATASET_VERSION],
    )[0]
    print(
        f"weather_forecasts: {cov['con_q']}/{cov['total']} filas con cuantiles",
        flush=True,
    )
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
