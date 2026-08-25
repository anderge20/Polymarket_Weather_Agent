#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/support/checkpoint_runner.py
==========================================================================
Standalone entry point run as a REAL OS subprocess to prove persistent
checkpoint/resume for Phase 2C — Blocker 1. NOT a pytest module (it is spawned
via subprocess so the SIGKILL is a genuine process death, not an in-process
simulation).

Deterministic source: the two REAL gamma events from tests/gamma_fixtures.py
(NYC_EVENT, ANKARA_EVENT), served by an in-process stub session (no network,
fully deterministic). They have distinct event ids and DIFFERENT fee regimes
(NYC fees_disabled, Ankara weather_fees) so there is no fee-schedule conflict.

Modes:
  clean     : run discover() once on a fresh DB  -> both events committed.
  interrupt : run discover() but send SIGKILL to THIS process DURING the 2nd
              event's transaction (rows written, BEFORE its mark + COMMIT). DuckDB
              WAL recovery must roll that event back on the next open. Never
              returns 0 (parent observes returncode == -SIGKILL).
  resume    : run discover() again on an existing DB -> loads the PERSISTED
              checkpoint from DuckDB and processes only the remaining event.

The persisted `discovery_checkpoint` table is the source of truth: a brand-new
process (this one) resumes exactly where the last one committed.
"""
import argparse
import os
import signal
import sys

# Make src/ and tests/ importable without an install (mirrors conftest's shim).
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
sys.path.insert(0, os.path.join(_ROOT, "src"))
sys.path.insert(0, os.path.join(_ROOT, "tests"))

import gamma_fixtures  # noqa: E402
from weather_agent import database as db  # noqa: E402
from weather_agent.polymarket import discovery  # noqa: E402

EVENTS = [gamma_fixtures.NYC_EVENT, gamma_fixtures.ANKARA_EVENT]


class _Resp:
    def __init__(self, payload):
        self.status_code = 200
        self.headers = {}
        self._payload = payload

    def json(self):
        return self._payload


class _StubSession:
    """Serves the 2 canned events on the first page (offset==0), empty afterwards.
    Matches the interface discovery.fetch_events_page uses: .get(url, params, timeout)
    -> object with .status_code / .headers / .json()."""
    def __init__(self):
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        offset = (params or {}).get("offset", 0)
        return _Resp(EVENTS if offset == 0 else [])


SENTINEL = "EVENT_1_COMMITTED"


def _barrier():
    """Deterministic parent<->child rendezvous (NO sleep, NO race, NO exception).
    Called by the test hook at the sync point. The child:
      1) writes SENTINEL to stdout and flushes  -> tells the PARENT event 1 is
         committed and event 2 has not started;
      2) BLOCKS on a stdin read that never completes (the parent keeps the child's
         stdin open and never writes to it) -> the child halts here, so event 2's
         ingestion cannot begin, until the PARENT sends SIGKILL.
    The kill is issued by the PARENT (proc.kill()); the child dies by -SIGKILL while
    blocked. If stdin ever returns EOF (parent misbehaved), we exit non-zero rather
    than continue — never a silent normal exit."""
    sys.stdout.write(SENTINEL + "\n")
    sys.stdout.flush()
    data = sys.stdin.readline()   # blocks; parent never writes -> waits for SIGKILL
    # Only reached if the parent closed stdin (EOF) instead of killing us:
    sys.stderr.write("ERROR: barrier released without SIGKILL (stdin=%r)\n" % data)
    os._exit(4)


def _install_barrier_hook(kill_point: str, on_event: int):
    """Install a deterministic call-count barrier by WRAPPING a real function and
    delegating to it — PRODUCTION SEMANTICS ARE UNCHANGED (the wrapper only adds the
    rendezvous in the test child). discover() processes events strictly sequentially
    in one thread, and the Nth event's ingest_event/checkpoint_mark runs only AFTER
    the (N-1)th event's ingest_event fully returned (incl. its COMMIT, discovery.py
    :344). So `on_event == 2` provably means event 1 is committed — no timing race."""
    state = {"n": 0}

    if kill_point == "before_event2":
        # Barrier at the START of the 2nd event's ingest_event, BEFORE delegating to
        # the real one -> AFTER event 1's COMMIT and BEFORE event 2's BEGIN. No open
        # transaction exists at the barrier. (Satisfies "signal before event 2.")
        real = discovery.ingest_event

        def wrapped(*a, **k):
            state["n"] += 1
            if state["n"] == on_event:
                _barrier()          # (never returns; parent SIGKILLs here)
            return real(*a, **k)

        discovery.ingest_event = wrapped

    elif kill_point == "during_event2":
        # Barrier INSIDE the 2nd event's transaction (rows written, before mark+COMMIT)
        # -> the parent's SIGKILL leaves an uncommitted txn that DuckDB WAL recovery
        # must roll back. (Atomicity variant — kept as a separate scenario.)
        real = db.checkpoint_mark

        def killing_mark(con_, dataset_version, event_id, run_id=None):
            state["n"] += 1
            if state["n"] == on_event:
                _barrier()
            return real(con_, dataset_version, event_id, run_id)

        db.checkpoint_mark = killing_mark
    else:
        raise SystemExit("unknown --kill-point %r" % kill_point)


def _run(db_path: str, dsv: str, kill_point: str | None = None, on_event: int = 2):
    con = db.init_db(db_path=db_path)
    if kill_point is not None:
        _install_barrier_hook(kill_point, on_event)
    summary = discovery.discover(con, dsv, session=_StubSession(), page_limit=100)
    con.close()
    print("SUMMARY events=%s markets=%s status=%s"
          % (summary.get("events"), summary.get("markets"), summary.get("status")))
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dsv", required=True)
    ap.add_argument("--mode", choices=["clean", "interrupt", "resume"], required=True)
    ap.add_argument("--kill-point", choices=["before_event2", "during_event2"],
                    default="before_event2",
                    help="interrupt mode: deterministic barrier point (parent SIGKILLs)")
    ap.add_argument("--on-event", type=int, default=2,
                    help="1-based event index at which the barrier fires (default 2)")
    a = ap.parse_args()

    if a.mode == "interrupt":
        # discover() will block at the barrier inside the 2nd event; the PARENT reads
        # SENTINEL on stdout and issues SIGKILL. This call therefore never returns
        # normally in interrupt mode.
        _run(a.db, a.dsv, kill_point=a.kill_point, on_event=a.on_event)
        print("ERROR: interrupt returned without SIGKILL", file=sys.stderr)
        sys.exit(3)
    else:
        _run(a.db, a.dsv)
        sys.exit(0)


if __name__ == "__main__":
    main()
