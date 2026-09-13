#!/usr/bin/env python3
"""
backfill_prices.py — historical indicative prices for WHOLE catalogue events
============================================================================

Fills `price_history` with the CLOB indicative series of the YES token of every
market of every selected event, over [endDate - WINDOW_HOURS, endDate]. `endDate`
is the 2E/D1 anchor (target_date 12:00:00Z); the leads under study (9 h, 24 h) both
fall inside a 48 h window.

WHOLE EVENTS, OR NOTHING (B-136)
--------------------------------
Every sampling this script ever did chose MARKETS, and each left a different
universe behind: `ORDER BY endDate DESC LIMIT n` kept one target date;
`PARTITION BY date ORDER BY market_id` kept the three lowest ids of each date — the
three lowest bands of one London event, 471 of 597 markets — and stored 1 028 of the
1 464 events truncated, because `backfill_markets` then read only what had prices.
The selection now lives in `weather_agent.backfill_universe`, shared with
`backfill_markets`: the unit is the event, filters and the cap apply to events, and
the cap order is declared.

NO LAUNCH WITHOUT FILTERS
-------------------------
A run with no filter would price the whole catalogue — about 80 000 requests. That
has to be an act written on the command line, not the absence of a flag, so a
launch without `--stations`, `--since`, `--until`, `--require-forecast` or
`--max-events` exits with an error. `--dry-run` needs no filter: it spends nothing,
and it is how a budget is sized.

WHAT WAS ASKED FOR IS RECORDED
------------------------------
Each fetch writes its status to `price_fetch_attempts`. "Pending" is every YES token
of the selection without a FINAL attempt (OK or EMPTY) in this dataset_version, so
the dry run's request count is exact, and a token that came back EMPTY is not asked
for again. One request per market: the YES side. The NO side is a separate decision
with its own budget.

RATE LIMITS: a 429 stops the walk immediately and the script exits non-zero. It is
never retried and never worked around (gate D0). The token stays pending; re-running
resumes.

Usage:
    python3 scripts/backfill_prices.py --dataset-version backfill_2b_v2 --dry-run
    python3 scripts/backfill_prices.py --dataset-version backfill_2b_v2 --stations EGLC --since 2026-04-08
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from weather_agent import backfill_universe as bu  # noqa: E402
from weather_agent import database as db  # noqa: E402
from weather_agent.polymarket import prices  # noqa: E402

CATALOG = os.path.expanduser("~/pmw-catalog-v2/CATALOG_V2.duckdb")
WINDOW_HOURS = 48
#: The statuses after which a token is not asked for again in the same dataset_version.
FINAL_STATUSES = (prices.S_OK, prices.S_EMPTY)
ATTEMPT_SOURCE = "clob /prices-history"

FILTER_FLAGS = "--stations, --since, --until, --require-forecast, --max-events"


def yes_token(clob_token_ids) -> str:
    """The YES token is the first of the pair, matching outcomes ["Yes","No"]."""
    ids = json.loads(clob_token_ids)
    if not ids:
        raise ValueError("empty clobTokenIds")
    return ids[0]


def _forecast_pairs(con, dataset_version: str) -> set[tuple[str, str]]:
    def d10(x):
        x = x.date() if hasattr(x, "date") else x
        return str(x)[:10]

    return {
        (r["station"], d10(r["target_date"]))
        for r in db.query(con, "SELECT DISTINCT station, target_date FROM weather_forecasts "
                               "WHERE dataset_version = ?", [dataset_version])
    }


def _final_tokens(con, dataset_version: str) -> set[str]:
    return {
        r["token_id"]
        for r in db.query(
            con,
            f"SELECT token_id FROM price_fetch_attempts WHERE dataset_version = ? "
            f"AND status IN ({', '.join('?' * len(FINAL_STATUSES))})",
            [dataset_version, *FINAL_STATUSES],
        )
    }


def _record_attempt(con, market_id: str, token_id: str, dataset_version: str, summary: dict) -> None:
    now = datetime.now(timezone.utc).isoformat()
    db.upsert(
        con,
        "price_fetch_attempts",
        {
            "token_id": token_id, "market_id": market_id, "dataset_version": dataset_version,
            "status": summary["status"], "points_written": summary.get("points_written", 0),
            "attempted_at": now, "source": ATTEMPT_SOURCE, "source_timestamp": now,
            "ingestion_timestamp": now, "record_version": 1,
        },
        conflict_cols=("token_id", "dataset_version"),
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/pmw.duckdb")
    ap.add_argument("--catalog", default=CATALOG)
    ap.add_argument("--dataset-version", required=True,
                    help="REQUIRED, no default: nothing lands in an existing version by accident")
    ap.add_argument("--stations", nargs="+", default=None)
    ap.add_argument("--since", default=None, help="earliest target date (YYYY-MM-DD), inclusive")
    ap.add_argument("--until", default=None, help="latest target date (YYYY-MM-DD), inclusive")
    ap.add_argument("--require-forecast", action="store_true",
                    help="only events whose (station, target date) has a forecast")
    ap.add_argument("--forecast-dataset-version", default="backfill_2b_v1")
    ap.add_argument("--max-events", type=int, default=None,
                    help=f"cap by EVENTS, in the order {bu.ORDER}")
    ap.add_argument("--sleep", type=float, default=0.25)
    ap.add_argument("--dry-run", action="store_true",
                    help="print the selection and the exact number of requests pending; request nothing")
    args = ap.parse_args(argv)

    filtered = any([args.stations, args.since, args.until, args.require_forecast,
                    args.max_events is not None])
    if not filtered and not args.dry_run:
        print(
            "REFUSED: no filter given, which would price the whole catalogue (~80 000 "
            "requests). Launching the full universe has to be written on the command "
            f"line, not left to a missing flag. Accepted filters: {FILTER_FLAGS}. "
            "--dry-run needs none.",
            file=sys.stderr, flush=True,
        )
        return 2

    db_exists = os.path.exists(args.db)
    con = db.init_db(db.connect(args.db)) if (db_exists or not args.dry_run) else None

    forecast_pairs = None
    if args.require_forecast:
        if con is None:
            print("REFUSED: --require-forecast needs an existing database to read forecasts from",
                  file=sys.stderr, flush=True)
            return 2
        forecast_pairs = _forecast_pairs(con, args.forecast_dataset_version)

    rows = bu.load_catalog_rows(args.catalog)
    selection = bu.select_events(rows, stations=args.stations, since=args.since, until=args.until,
                                 forecast_pairs=forecast_pairs, max_events=args.max_events)
    final = _final_tokens(con, args.dataset_version) if con is not None else set()

    pending, unpriceable = [], 0
    for m in selection.rows:
        try:
            tok = yes_token(m["clobTokenIds"])
        except (TypeError, ValueError):
            unpriceable += 1
            continue
        if tok not in final:
            pending.append((m, tok))

    summary = bu.summarize(selection)
    summary.update({
        "dataset_version": args.dataset_version,
        "markets_unpriceable": unpriceable,
        "tokens_already_final": len(selection.rows) - unpriceable - len(pending),
        "requests_pending": len(pending),
    })
    print(json.dumps(summary, indent=1, default=str), flush=True)
    if args.dry_run:
        return 0

    session = prices.default_session()
    ok = failed = 0
    by_status: dict[str, int] = {}
    for i, (m, tok) in enumerate(pending, 1):
        end = datetime.fromisoformat(str(m["endDate"]).replace("Z", "+00:00"))
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        start = end - timedelta(hours=WINDOW_HOURS)
        result = prices.ingest(con, session, tok, str(m["market_id"]), start, end, args.dataset_version)
        _record_attempt(con, str(m["market_id"]), tok, args.dataset_version, result)
        st = result["status"]
        by_status[st] = by_status.get(st, 0) + 1
        if st in prices.STOP_STATUSES:
            print(f"  [{i}] {st} on {m['market_id']}: stopping. Re-running resumes.", flush=True)
            break
        if st in prices.ERROR_STATUSES:
            failed += 1
        else:
            ok += 1
        time.sleep(args.sleep)

    print(f"DONE ok={ok} failed={failed} statuses={by_status}", flush=True)
    con.close()
    return 1 if (failed or prices.S_RATE_LIMITED in by_status) else 0


if __name__ == "__main__":
    raise SystemExit(main())
