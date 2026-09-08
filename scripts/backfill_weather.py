#!/usr/bin/env python3
"""
backfill_weather.py — forecasts for every (station, target_date) we price
=========================================================================

Fills `weather_forecasts` with the M1 model (`icon_seamless`, adopted in D12) for
each station/target-date that already has price coverage, at each decision time
the study uses.

WHICH RUN, AND WHY IT MATTERS
------------------------------
For a decision at T we may only use a run whose `available_at` (issue + L_MAX)
is <= T. This script therefore does not "fetch today's forecast": it walks the
candidate issue times backwards and takes the freshest one that was actually
published by T. Picking the run by `issue_time <= T` instead would silently pull
a forecast that did not exist yet — the exact leak `test_no_future_information`
exists to prevent.

Leads come from the preregistration: 9 h and 24 h before `endDate`, which is the
2E/D1 anchor (target_date 12:00:00Z).

QUOTA: Open-Meteo's daily limit is shared across single-runs and
historical-forecast. A 429 stops the walk immediately and exits non-zero; it is
never retried and never worked around (gate D0). Re-running resumes: every
(station, model, issue_time, target_date) already present is skipped.

Usage:
    python3 scripts/backfill_weather.py --db data/pmw.duckdb --limit 200
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import duckdb  # noqa: E402

from weather_agent import database as db  # noqa: E402
from weather_agent import stations, weather  # noqa: E402

CATALOG = os.path.expanduser("~/pmw-catalog-v2/CATALOG_V2.duckdb")
DATASET_VERSION = "backfill_2b_v1"

#: Leads under study (hours before endDate). Preregistered in V2 §4.
LEADS_H = (9, 24)

#: Candidate ICON issue hours (UTC). The seamless product publishes on this grid.
ISSUE_HOURS = (0, 6, 12, 18)

#: How far back to look for a published run before giving up on a decision time.
MAX_RUN_AGE_H = 36

#: Earliest run the Single Runs archive still holds, measured 2026-09-08 by
#: bisection against the live API: 2026-04-01 is rejected ("The requested model
#: run is not available"), 2026-04-08 succeeds. This is a ROLLING window of about
#: five months — a run that falls out of it is gone for good, so anything the
#: backtest may ever need must be captured while it is still there. Re-measure
#: before assuming this constant still holds.
ARCHIVE_START = date(2026, 4, 8)


def pick_run(t: datetime, model: str) -> datetime | None:
    """The freshest issue time whose forecast was AVAILABLE at `t`.

    Walks backwards over the issue grid and returns the first run that satisfies
    `available_at(run) <= t`. Returns None if nothing was published in time.
    """
    cursor = t.replace(minute=0, second=0, microsecond=0)
    limit = t - timedelta(hours=MAX_RUN_AGE_H)
    while cursor >= limit:
        if cursor.hour in ISSUE_HOURS and weather.is_available_at(cursor, model, t):
            return cursor
        cursor -= timedelta(hours=1)
    return None


def targets(catalog_path: str, con, limit: int | None):
    """(station, target_date, tz) for every market we already hold prices for."""
    priced = {
        r["market_id"]
        for r in db.query(con, "SELECT DISTINCT market_id FROM price_history")
    }
    if not priced:
        return []
    cat = duckdb.connect(catalog_path, read_only=True)
    rows = cat.execute(
        """
        SELECT DISTINCT station_identifier AS icao, CAST(endDate AS DATE) AS target_date,
               market_id
        FROM mk
        WHERE station_identifier IS NOT NULL AND endDate IS NOT NULL
        ORDER BY target_date, icao
        """
    ).fetchdf().to_dict("records")
    cat.close()
    seen: dict[tuple[str, date], None] = {}
    out = []
    for r in rows:
        if str(r["market_id"]) not in priced:
            continue
        # DuckDB hands dates back as pandas Timestamps; normalise to date so the
        # archive-window comparison is not a type error waiting to happen.
        td = r["target_date"]
        r["target_date"] = td.date() if hasattr(td, "date") else td
        key = (r["icao"], r["target_date"])
        if key in seen:
            continue
        seen[key] = None
        out.append(r)
        if limit and len(out) >= limit:
            break
    return out


def station_tz(icao: str) -> str | None:
    """Timezone for the station, from the canonical snapshot's city where known."""
    try:
        st = stations.get(icao)
    except stations.UnknownStation:
        return None
    return getattr(st, "tz", None) or _TZ_BY_ICAO.get(icao)


#: Minimal ICAO->tz map for the stations in the priced universe. The canonical
#: snapshot carries coordinates, not timezones; the target day is a LOCAL day, so
#: an unknown timezone is a refusal, never a guess of UTC.
_TZ_BY_ICAO = {
    "KLGA": "America/New_York", "KATL": "America/New_York", "KMIA": "America/New_York",
    "KORD": "America/Chicago", "KDAL": "America/Chicago", "KHOU": "America/Chicago",
    "KAUS": "America/Chicago", "KDEN": "America/Denver", "KBKF": "America/Denver",
    "KLAX": "America/Los_Angeles", "KSFO": "America/Los_Angeles",
    "KSEA": "America/Los_Angeles", "KPHX": "America/Phoenix",
    "EGLC": "Europe/London", "LFPG": "Europe/Paris", "LFPB": "Europe/Paris",
    "EDDM": "Europe/Berlin", "EHAM": "Europe/Amsterdam", "LEMD": "Europe/Madrid",
    "LIMC": "Europe/Rome", "EPWA": "Europe/Warsaw", "EFHK": "Europe/Helsinki",
    "UUWW": "Europe/Moscow", "LTFM": "Europe/Istanbul", "LTAC": "Europe/Istanbul",
    "LLBG": "Asia/Jerusalem", "OEJN": "Asia/Riyadh", "OPKC": "Asia/Karachi",
    "VILK": "Asia/Kolkata", "VHHH": "Asia/Hong_Kong", "RCTP": "Asia/Taipei",
    "RCSS": "Asia/Taipei", "RJTT": "Asia/Tokyo", "RKSI": "Asia/Seoul",
    "RKPK": "Asia/Seoul", "ZBAA": "Asia/Shanghai", "ZSPD": "Asia/Shanghai",
    "ZSQD": "Asia/Shanghai", "ZSJN": "Asia/Shanghai", "ZGGG": "Asia/Shanghai",
    "ZGSZ": "Asia/Shanghai", "ZHHH": "Asia/Shanghai", "ZHCC": "Asia/Shanghai",
    "ZUUU": "Asia/Shanghai", "ZUCK": "Asia/Shanghai",
    "WSSS": "Asia/Singapore", "WMKK": "Asia/Kuala_Lumpur", "WIHH": "Asia/Jakarta",
    "RPLL": "Asia/Manila", "VTBS": "Asia/Bangkok",
    "SBGR": "America/Sao_Paulo", "SAEZ": "America/Argentina/Buenos_Aires",
    "MMMX": "America/Mexico_City", "MPMG": "America/Panama",
    "CYYZ": "America/Toronto", "NZWN": "Pacific/Auckland",
    "FACT": "Africa/Johannesburg", "DNMM": "Africa/Lagos",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/pmw.duckdb")
    ap.add_argument("--catalog", default=CATALOG)
    ap.add_argument("--limit", type=int, default=None, help="max station/date pairs")
    ap.add_argument(
        "--since",
        default=ARCHIVE_START.isoformat(),
        help="earliest target date; defaults to the Single Runs archive start",
    )
    ap.add_argument("--sleep", type=float, default=0.2)
    args = ap.parse_args()

    since = date.fromisoformat(args.since)
    con = db.init_db(db.connect(args.db))
    pairs = [p for p in targets(args.catalog, con, None) if p["target_date"] >= since]
    if args.limit:
        pairs = pairs[: args.limit]
    print(
        f"pares (estación, fecha) con precios desde {since}: {len(pairs)}",
        flush=True,
    )

    have = {
        (r["station"], str(r["target_date"]), str(r["issue_time"]))
        for r in db.query(
            con,
            "SELECT station, target_date, issue_time FROM weather_forecasts "
            "WHERE dataset_version = ?",
            [DATASET_VERSION],
        )
    }

    ok = skipped = no_tz = no_run = failed = 0
    quota_hit = False
    for i, p in enumerate(pairs, 1):
        icao, target = p["icao"], p["target_date"]
        tz = station_tz(icao)
        if tz is None:
            no_tz += 1
            continue
        end = datetime(target.year, target.month, target.day, 12, tzinfo=timezone.utc)
        for lead in LEADS_H:
            t = end - timedelta(hours=lead)
            run = pick_run(t, weather.M1_MODEL)
            if run is None:
                no_run += 1
                continue
            if (icao, str(target), run.isoformat()) in have:
                skipped += 1
                continue
            try:
                fc = weather.ingest_run(
                    con, icao, target, tz, run, DATASET_VERSION, model=weather.M1_MODEL
                )
                ok += 1
                have.add((icao, str(target), run.isoformat()))
                if ok % 25 == 0:
                    print(
                        f"  [{i}/{len(pairs)}] {icao} {target} lead{lead}h "
                        f"run {run:%m-%d %Hz} → tmax {fc.tmax:.1f} ({ok} escritos)",
                        flush=True,
                    )
            except weather.WeatherIngestError as e:
                msg = str(e)
                if "429" in msg or "quota" in msg.lower():
                    print(f"  CUOTA AGOTADA en {icao} {target}: {e}", flush=True)
                    quota_hit = True
                    break
                failed += 1
                if failed <= 10:
                    print(f"  [{i}] {icao} {target} lead{lead}h: {e}", flush=True)
            time.sleep(args.sleep)
        if quota_hit:
            break

    print(
        f"LISTO_WEATHER escritos={ok} saltados={skipped} sin_tz={no_tz} "
        f"sin_run={no_run} fallos={failed} cuota_agotada={quota_hit}",
        flush=True,
    )
    stats = db.query(
        con,
        """SELECT count(*) AS filas, count(DISTINCT station) AS est,
                  count(DISTINCT target_date) AS fechas FROM weather_forecasts""",
    )[0]
    print(
        f"weather_forecasts: {stats['filas']} filas · {stats['est']} estaciones · "
        f"{stats['fechas']} fechas",
        flush=True,
    )
    con.close()
    return 1 if (quota_hit or failed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
