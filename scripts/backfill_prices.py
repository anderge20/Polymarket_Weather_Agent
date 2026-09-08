#!/usr/bin/env python3
"""
backfill_prices.py — historical indicative prices for resolved weather markets
==============================================================================

Fills `price_history` with the CLOB indicative series around each market's
decision window, so the backtest can read "the price at the lead" as-of.

WINDOW: [endDate - WINDOW_HOURS, endDate]. `endDate` is the 2E/D1 anchor
(target_date 12:00:00Z); the leads under study (9 h, 24 h) both fall inside a
48 h window.

SAMPLING — stratified by target date AND station (neither alone is enough)
--------------------------------------------------------------------------
Two sampling defects were found and fixed here, both by looking at what the data
actually contained rather than at what the query was meant to do:

1. `ORDER BY endDate DESC LIMIT n` returned n markets all sharing the most recent
   date. The first run pulled 1.14 M price points spanning ONE target date — no
   temporal variation, useless for a backtest.
2. Stratifying by date alone then put 471 of 600 markets in London, because
   `PARTITION BY date ORDER BY market_id` lands on the same city every time.
   MODELSEL V5 found the ICON/ECMWF contrast reverses sign by region, so a
   London-dominated sample cannot support any claim about the universe.

Sampling is therefore over (date, station) pairs. `--stride` keeps every n-th
date, trading temporal density for full station coverage inside a bounded
request budget.

RATE LIMITS: a 429 stops the walk immediately and the script exits non-zero.
It is never retried and never worked around (gate D0). Re-running resumes.

RESUMABLE: markets already present for this dataset_version are skipped, and
every market is written atomically, so a stopped run leaves no partial history.

Usage:
    python3 scripts/backfill_prices.py --per-pair 1 --since 2026-04-08 --stride 5
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import duckdb  # noqa: E402

from weather_agent import database as db  # noqa: E402
from weather_agent.polymarket import prices  # noqa: E402

CATALOG = os.path.expanduser("~/pmw-catalog-v2/CATALOG_V2.duckdb")
WINDOW_HOURS = 48
DATASET_VERSION = "backfill_2b_v1"


def markets(
    catalog_path: str,
    per_pair: int,
    max_total: int | None,
    city: str | None,
    since: str | None = None,
    stride: int = 1,
):
    """Up to `per_pair` markets from every (target date, STATION) pair.

    Stratifying by date alone is not enough — and getting that wrong is not
    hypothetical. `PARTITION BY date ORDER BY market_id` put 471 of 600 sampled
    markets in London, because within a date the ordering is stable and always
    lands on the same city. MODELSEL V5 found the ICON/ECMWF contrast reverses
    sign by region (ASIA_SUR and HEM_SUR favour ECMWF, LATAM_NORTE favours ICON),
    so a London-dominated sample cannot support a claim about the universe.

    `stride` keeps every n-th date, to trade temporal density for coverage of all
    stations within a bounded request budget.
    """
    con = duckdb.connect(catalog_path, read_only=True)
    where = [
        "clobTokenIds IS NOT NULL",
        "endDate IS NOT NULL",
        "station_identifier IS NOT NULL",
    ]
    if city:
        where.append(f"city = '{city}'")
    if since:
        where.append(f"CAST(endDate AS DATE) >= DATE '{since}'")
    sql = f"""
        WITH base AS (
            SELECT market_id, condition_id, city, station_identifier, endDate,
                   clobTokenIds, winning_outcome, CAST(endDate AS DATE) AS d
            FROM mk WHERE {' AND '.join(where)}
        ),
        dated AS (
            SELECT *, dense_rank() OVER (ORDER BY d) AS date_rank FROM base
        ),
        ranked AS (
            SELECT *, row_number() OVER (
                PARTITION BY d, station_identifier ORDER BY market_id
            ) AS rn
            FROM dated WHERE (date_rank - 1) % {max(1, stride)} = 0
        )
        SELECT * FROM ranked WHERE rn <= {per_pair} ORDER BY d, station_identifier
    """
    if max_total:
        sql += f" LIMIT {max_total}"
    rows = con.execute(sql).fetchdf().to_dict("records")
    con.close()
    return rows


def yes_token(clob_token_ids: str) -> str:
    """The YES token is the first of the pair, matching outcomes ["Yes","No"]."""
    ids = json.loads(clob_token_ids)
    if not ids:
        raise ValueError("empty clobTokenIds")
    return ids[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-pair", type=int, default=1,
                    help="markets per (target date, station) pair")
    ap.add_argument("--since", default=None, help="earliest target date (YYYY-MM-DD)")
    ap.add_argument("--stride", type=int, default=1, help="keep every n-th date")
    ap.add_argument("--max-total", type=int, default=None)
    ap.add_argument("--city", default=None)
    ap.add_argument("--db", default="data/pmw.duckdb")
    ap.add_argument("--catalog", default=CATALOG)
    ap.add_argument("--sleep", type=float, default=0.25)
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.db) or ".", exist_ok=True)
    con = db.init_db(db.connect(args.db))
    session = prices.default_session()

    done = {
        r["token_id"]
        for r in db.query(
            con,
            "SELECT DISTINCT token_id FROM price_history WHERE dataset_version = ?",
            [DATASET_VERSION],
        )
    }
    rows = markets(args.catalog, args.per_pair, args.max_total, args.city,
                   since=args.since, stride=args.stride)
    dates = {str(m["d"]) for m in rows}
    ests = {str(m["station_identifier"]) for m in rows}
    print(
        f"candidatos: {len(rows)} mercados · {len(dates)} fechas "
        f"({min(dates)} → {max(dates)}) · {len(ests)} estaciones · "
        f"ya ingeridos: {len(done)}",
        flush=True,
    )

    ok = skipped = failed = 0
    total_points = 0
    by_status: dict[str, int] = {}
    for i, m in enumerate(rows, 1):
        try:
            tok = yes_token(m["clobTokenIds"])
        except Exception as e:
            print(f"  [{i}] {m['market_id']}: clobTokenIds ilegible ({e})", flush=True)
            failed += 1
            continue
        if tok in done:
            skipped += 1
            continue
        end = datetime.fromisoformat(str(m["endDate"]).replace("Z", "+00:00"))
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        start = end - timedelta(hours=WINDOW_HOURS)

        summary = prices.ingest(
            con, session, tok, str(m["market_id"]), start, end, DATASET_VERSION
        )
        st = summary["status"]
        by_status[st] = by_status.get(st, 0) + 1

        if st in prices.STOP_STATUSES:
            print(
                f"  [{i}] {st} en {m['market_id']} — se detiene la pasada. "
                "Relanzar el mismo comando continúa donde quedó.",
                flush=True,
            )
            break
        if st in prices.ERROR_STATUSES:
            failed += 1
            print(f"  [{i}] {m['market_id']} {st}", flush=True)
        else:
            ok += 1
            total_points += summary["points_written"]
            if i % 25 == 0:
                print(
                    f"  [{i}/{len(rows)}] {m['d']} {m['city']} → "
                    f"{summary['points_written']} puntos (acum {total_points})",
                    flush=True,
                )
        time.sleep(args.sleep)

    print(
        f"LISTO_BACKFILL ok={ok} saltados={skipped} fallos={failed} "
        f"puntos={total_points} estados={by_status}",
        flush=True,
    )
    stats = db.query(
        con,
        """SELECT count(*) AS filas, count(DISTINCT token_id) AS tokens,
                  count(DISTINCT CAST(observation_time AS DATE)) AS dias
           FROM price_history""",
    )[0]
    print(
        f"price_history: {stats['filas']} filas · {stats['tokens']} tokens · "
        f"{stats['dias']} días distintos",
        flush=True,
    )
    con.close()
    return 1 if (failed or prices.S_RATE_LIMITED in by_status) else 0


if __name__ == "__main__":
    raise SystemExit(main())
