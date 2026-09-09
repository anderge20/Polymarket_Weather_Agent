#!/usr/bin/env python3
"""
backfill_observations.py — realized daily highs for every forecast station-day
==============================================================================

Fills `weather_observations` with the IEM/METAR daily high (`Y_final`, D17) for
each (station, target_date) that already has a forecast, so M2 can measure the
empirical forecast error and the backtest has a label to settle against.

Walks the OLDEST station-days first. Forecasts come from a rolling archive that
loses its far edge every day (B-1); observations do not expire, but pairing them
oldest-first keeps the two sides aligned as the forecast edge moves.

Fails per station-day, never in bulk: a station with no METAR coverage for a day
is counted and skipped, not silently written as a lower maximum.

Usage:
    python3 scripts/backfill_observations.py --db data/pmw.duckdb
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from weather_agent import database as db  # noqa: E402
from weather_agent import observations as obs  # noqa: E402
from weather_agent import stations  # noqa: E402

DATASET_VERSION = "backfill_2b_v1"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/pmw.duckdb")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--sleep", type=float, default=0.3)
    args = ap.parse_args()

    con = db.init_db(db.connect(args.db))

    pairs = db.query(
        con,
        """SELECT DISTINCT station, target_date FROM weather_forecasts
           WHERE dataset_version = ? ORDER BY target_date, station""",
        [DATASET_VERSION],
    )
    if args.limit:
        pairs = pairs[: args.limit]
    print(f"pares (estación, fecha) con pronóstico: {len(pairs)}", flush=True)

    ok = skipped = no_tz = missing = failed = 0
    for i, p in enumerate(pairs, 1):
        icao = p["station"]
        target = p["target_date"]
        if hasattr(target, "date"):
            target = target.date()
        try:
            tz = stations.timezone_of(icao)
        except stations.UnknownStation:
            no_tz += 1
            continue
        try:
            existing = obs.observed_tmax(con, icao, target, tz, DATASET_VERSION)
        except obs.NoObservation:
            existing = None
        if existing is not None:
            skipped += 1
            continue
        try:
            dh = obs.ingest_daily_high(con, icao, target, tz, DATASET_VERSION)
            ok += 1
            if ok % 50 == 0:
                print(
                    f"  [{i}/{len(pairs)}] {icao} {target} → {dh.tmax_c:.1f} °C "
                    f"({dh.n_obs} obs, {ok} escritas)",
                    flush=True,
                )
        except obs.NoObservation as e:
            missing += 1
            if missing <= 8:
                print(f"  [{i}] {icao} {target}: {str(e)[:90]}", flush=True)
        except obs.ObservationError as e:
            failed += 1
            if failed <= 8:
                print(f"  [{i}] {icao} {target}: {str(e)[:90]}", flush=True)
        time.sleep(args.sleep)

    print(
        f"LISTO_OBS escritas={ok} saltadas={skipped} sin_tz={no_tz} "
        f"sin_cobertura={missing} fallos={failed}",
        flush=True,
    )
    s = db.query(
        con,
        """SELECT count(*) AS filas, count(DISTINCT station) AS est,
                  count(DISTINCT CAST(observation_time AS DATE)) AS dias
           FROM weather_observations""",
    )[0]
    print(
        f"weather_observations: {s['filas']} filas · {s['est']} estaciones · "
        f"{s['dias']} días",
        flush=True,
    )
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
