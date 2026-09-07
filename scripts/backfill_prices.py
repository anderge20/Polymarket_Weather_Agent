#!/usr/bin/env python3
"""
backfill_prices.py — historical indicative prices for resolved weather markets
==============================================================================

Fills `price_history` with the CLOB indicative series around each market's
decision window, so the backtest can read "the price at the lead" as-of.

WINDOW: [endDate - WINDOW_HOURS, endDate]. `endDate` is the 2E/D1 anchor
(target_date 12:00:00Z); the leads under study (9 h, 24 h) both fall inside a
48 h window, so one stitched request per market suffices.

RESUMABLE: the market list is walked in a stable order and every market already
present in `price_history` for this dataset_version is skipped. Re-running
continues where it stopped. Failures are recorded and skipped, never retried
forever, and never silently turned into empty series.

Usage:
    python3 scripts/backfill_prices.py --limit 200 --db data/pmw.duckdb
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


def markets(catalog_path: str, limit: int | None, city: str | None):
    con = duckdb.connect(catalog_path, read_only=True)
    where = "WHERE clobTokenIds IS NOT NULL AND endDate IS NOT NULL"
    if city:
        where += f" AND city = '{city}'"
    sql = f"""
        SELECT market_id, condition_id, city, station_identifier, endDate,
               clobTokenIds, winning_outcome
        FROM mk {where}
        ORDER BY endDate DESC, market_id
    """
    if limit:
        sql += f" LIMIT {limit}"
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
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--city", default=None)
    ap.add_argument("--db", default="data/pmw.duckdb")
    ap.add_argument("--catalog", default=CATALOG)
    ap.add_argument("--sleep", type=float, default=0.25)
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.db) or ".", exist_ok=True)
    con = db.init_db(db.connect(args.db))

    done = {
        r["token_id"]
        for r in db.query(
            con,
            "SELECT DISTINCT token_id FROM price_history WHERE dataset_version = ?",
            [DATASET_VERSION],
        )
    }
    rows = markets(args.catalog, args.limit, args.city)
    print(f"mercados candidatos: {len(rows)} · ya ingeridos: {len(done)}", flush=True)

    ok = skipped = failed = 0
    total_points = 0
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
        try:
            n = prices.ingest(
                con, tok, str(m["market_id"]), start, end, DATASET_VERSION
            )
            ok += 1
            total_points += n
            if i % 10 == 0 or n == 0:
                print(
                    f"  [{i}/{len(rows)}] {m['city']} {m['station_identifier']} "
                    f"{end.date()} → {n} puntos (acum {total_points})",
                    flush=True,
                )
        except Exception as e:  # noqa: BLE001 - recorded, not swallowed
            failed += 1
            print(f"  [{i}] {m['market_id']} FALLO: {type(e).__name__}: {e}", flush=True)
        time.sleep(args.sleep)

    print(
        f"LISTO_BACKFILL ok={ok} saltados={skipped} fallos={failed} puntos={total_points}",
        flush=True,
    )
    n_rows = db.query(con, "SELECT count(*) AS n FROM price_history")[0]["n"]
    n_tok = db.query(con, "SELECT count(DISTINCT token_id) AS n FROM price_history")[0]["n"]
    print(f"price_history: {n_rows} filas · {n_tok} tokens", flush=True)
    con.close()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
