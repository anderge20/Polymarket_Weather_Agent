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

DATASET_VERSION = "backfill_2b_v1"
PREREG_SHA = "b2b168d4cddb65c469cbd00bd20cce30c54e5afd194526527714e23cf0d5b34c"
LEADS = (9, 24)


def _local_day(ts, tz_name: str):
    """v2 §1: the station's LOCAL day. `observation_time::date` is forbidden."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(ZoneInfo(tz_name)).date()


def _label_available_at(target_day, tz_name: str) -> datetime:
    """v2 §3: end of the local day, plus the assumed 24 h publication lag."""
    zone = ZoneInfo(tz_name)
    end_local = datetime(
        target_day.year, target_day.month, target_day.day, tzinfo=zone
    ) + timedelta(days=1)
    return end_local.astimezone(timezone.utc) + em.ASSUMED_LABEL_LAG


def _pick_run(t: datetime, model: str, issue_hours=(0, 6, 12, 18), max_age_h=36):
    cursor = t.replace(minute=0, second=0, microsecond=0)
    limit = t - timedelta(hours=max_age_h)
    while cursor >= limit:
        if cursor.hour in issue_hours and weather.is_available_at(cursor, model, t):
            return cursor
        cursor -= timedelta(hours=1)
    return None


def load_pairs(con):
    """(pairs, issue_by_key, stats). Pairing by LOCAL day, in Python — the SQL
    join on `CAST(observation_time AS DATE)` is what made the sample depend on a
    session variable."""
    obs = db.query(
        con,
        """SELECT station, observation_time, tmax_observed FROM weather_observations
           WHERE dataset_version = ?""",
        [DATASET_VERSION],
    )
    by_local_day: dict[tuple, float] = {}
    no_tz = 0
    for r in obs:
        try:
            tz = stations.timezone_of(r["station"])
        except stations.UnknownStation:
            no_tz += 1
            continue
        key = (r["station"], _local_day(r["observation_time"], tz))
        v = float(r["tmax_observed"])
        by_local_day[key] = max(by_local_day.get(key, v), v)

    fc = db.query(
        con,
        """SELECT station, target_date, issue_time, forecast_tmax
           FROM weather_forecasts
           WHERE dataset_version = ? AND forecast_tmax IS NOT NULL""",
        [DATASET_VERSION],
    )
    pairs: list[em.Pair] = []
    issue_by_key: dict[tuple, object] = {}
    unmatched_lead = unmatched_obs = 0
    for r in fc:
        td = r["target_date"]
        td = td.date() if hasattr(td, "date") else td
        try:
            tz = stations.timezone_of(r["station"])
        except stations.UnknownStation:
            continue
        y = by_local_day.get((r["station"], td))
        if y is None:
            unmatched_obs += 1
            continue
        issue = r["issue_time"]
        if issue.tzinfo is None:
            issue = issue.replace(tzinfo=timezone.utc)
        end = datetime(td.year, td.month, td.day, 12, tzinfo=timezone.utc)
        lead = None
        for cand in LEADS:
            run = _pick_run(end - timedelta(hours=cand), weather.M1_MODEL)
            if run is not None and run == issue:
                lead = cand
                break
        if lead is None:
            unmatched_lead += 1  # v2 §2: counted, never assigned to a plausible lead
            continue
        issue_by_key[(r["station"], td, lead)] = r["issue_time"]
        pairs.append(
            em.Pair(
                station=r["station"],
                target_date=td,
                lead_h=lead,
                forecast_c=float(r["forecast_tmax"]),
                observed_c=y,
                label_available_at=_label_available_at(td, tz),
            )
        )
    stats = {
        "obs_sin_huso": no_tz,
        "pronosticos_sin_observacion": unmatched_obs,
        "filas_sin_lead_preregistrado": unmatched_lead,
    }
    return pairs, issue_by_key, stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/pmw.duckdb")
    ap.add_argument("--out", default=os.path.expanduser("~/pmw-e2"))
    args = ap.parse_args()

    con = db.init_db(db.connect(args.db))
    con.execute(
        """UPDATE weather_forecasts SET forecast_p10=NULL, forecast_p25=NULL,
           forecast_p50=NULL, forecast_p75=NULL, forecast_p90=NULL
           WHERE dataset_version = ?""",
        [DATASET_VERSION],
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
            """SELECT issue_time, forecast_tmax FROM weather_forecasts
               WHERE station = ? AND target_date = ? AND issue_time = ?
                 AND dataset_version = ?""",
            [station, target.isoformat(), issue, DATASET_VERSION],
        )
        for r in rows:
            fq = em.forecast_quantiles_c(float(r["forecast_tmax"]), q)
            con.execute(
                """UPDATE weather_forecasts
                   SET forecast_p10=?, forecast_p25=?, forecast_p50=?,
                       forecast_p75=?, forecast_p90=?
                   WHERE station=? AND target_date=? AND issue_time=? AND dataset_version=?""",
                [fq[10], fq[25], fq[50], fq[75], fq[90], station,
                 target.isoformat(), r["issue_time"], DATASET_VERSION],
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
