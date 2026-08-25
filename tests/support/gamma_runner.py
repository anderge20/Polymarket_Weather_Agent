#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/support/gamma_runner.py — run discovery.discover() against the REAL Gamma API
in an INDEPENDENT OS process, on a given DuckDB file.

validate_2c.py spawns this TWICE (two separate processes sharing the SAME DuckDB) to
prove the real-Gamma two-process resume: process 2 opens the same file, LOADS the
checkpoint that process 1 persisted, and does NOT reprocess the already-committed
events. Each invocation is a genuine separate process (its pid is reported).

Prints exactly one machine-readable line:
    GAMMA_RESULT <json>
with: pid, status, events_ingested (committed by THIS process), checkpoint_before,
checkpoint_after. Exit 0 on completion — a Gamma rate-limit/empty is reported in
`status` (NOT a pass, NOT an exception). Exit non-zero only on an unexpected error.
"""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from weather_agent import database as db            # noqa: E402
from weather_agent.polymarket import discovery      # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dsv", required=True)
    ap.add_argument("--max-pages", type=int, default=1)
    ap.add_argument("--page-limit", type=int, default=5)
    a = ap.parse_args()
    try:
        con = db.init_db(db_path=a.db)
        before = sorted(db.checkpoint_load(con, a.dsv))
        summary = discovery.discover(con, a.dsv, session=None,
                                     max_pages=a.max_pages, page_limit=a.page_limit)
        after = sorted(db.checkpoint_load(con, a.dsv))
        con.close()
        print("GAMMA_RESULT " + json.dumps({
            "pid": os.getpid(),
            "status": summary.get("status"),
            "events_ingested": summary.get("events"),   # events THIS process committed
            "checkpoint_before": before,
            "checkpoint_after": after,
        }))
        sys.exit(0)
    except Exception as e:  # unexpected only; Gamma errors are surfaced via `status`
        print("GAMMA_ERROR " + repr(e), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
