# -*- coding: utf-8 -*-
"""
tests/test_checkpoint_resume.py — Phase 2C, Blocker 1 (persistent checkpoint/resume)
====================================================================================
REAL cross-process evidence (not an in-memory simulation):
  - a REAL subprocess runs discover() against a deterministic 2-event source
    (NYC then ANKARA, from gamma_fixtures);
  - the child signals EVENT_1_COMMITTED on stdout and BLOCKS (no sleep, no race);
  - the PARENT (this test) issues SIGKILL; the child dies by -SIGKILL;
  - a SECOND independent subprocess reopens the SAME DuckDB file and resumes from
    the PERSISTED discovery_checkpoint.

Two scenarios:
  before_event2  — kill AFTER event 1 COMMIT, BEFORE event 2 ingestion begins.
  during_event2  — kill INSIDE event 2's txn (rows written, pre-COMMIT): DuckDB WAL
                   recovery must roll it back (atomicity variant).

STATUS: IMPLEMENTED, executed on Hetzner/Actions (no Python in the authoring env).
Requires POSIX SIGKILL (skipped elsewhere).
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys

import pytest

from weather_agent import database as db

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
_RUNNER = os.path.join(_HERE, "support", "checkpoint_runner.py")
SENTINEL = "EVENT_1_COMMITTED"

NYC_ID = "128661"      # event 1 (processed first)
ANKARA_ID = "869074"   # event 2 (processed second)
DSV = "ds_ckpt"

pytestmark = pytest.mark.skipif(
    not hasattr(signal, "SIGKILL"), reason="requires POSIX SIGKILL")

_FACT_TABLES = ("markets", "outcomes", "market_fee_schedule", "data_quality")


# --------------------------------------------------------------------------- utils
def _child_env():
    env = dict(os.environ)
    # ensure src/ + tests/ importable in the child regardless of CWD
    env["PYTHONPATH"] = os.pathsep.join(
        [os.path.join(_ROOT, "src"), _HERE, env.get("PYTHONPATH", "")])
    return env


def _run_blocking(mode, db_path, dsv=DSV, kill_point=None):
    """clean / resume: run to normal completion; assert returncode 0."""
    cmd = [sys.executable, _RUNNER, "--db", db_path, "--dsv", dsv, "--mode", mode]
    if kill_point:
        cmd += ["--kill-point", kill_point]
    r = subprocess.run(cmd, capture_output=True, text=True, env=_child_env(), timeout=180)
    assert r.returncode == 0, f"{mode} failed rc={r.returncode}\nSTDOUT:{r.stdout}\nSTDERR:{r.stderr}"
    return r


def _run_interrupt(db_path, kill_point, dsv=DSV):
    """interrupt: read SENTINEL on the child's stdout (deterministic rendezvous — the
    child emits it exactly after event 1 COMMIT), then the PARENT sends SIGKILL and
    asserts the child died by -SIGKILL. No sleep / no timing is used to synchronise;
    the blocking readline IS the synchronisation."""
    proc = subprocess.Popen(
        [sys.executable, _RUNNER, "--db", db_path, "--dsv", dsv,
         "--mode", "interrupt", "--kill-point", kill_point],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env=_child_env())
    try:
        saw = False
        for line in proc.stdout:                 # blocks until the child writes a line
            if line.strip() == SENTINEL:
                saw = True
                break
        assert saw, "child never signalled EVENT_1_COMMITTED"
        proc.kill()                              # PARENT issues the real SIGKILL
        rc = proc.wait(timeout=60)               # safety net, not the sync mechanism
    finally:
        for s in (proc.stdin, proc.stdout, proc.stderr):
            try:
                s.close()
            except Exception:
                pass
    assert rc == -signal.SIGKILL, f"expected -SIGKILL, got rc={rc}"


def _q1(con, sql, params):
    return con.execute(sql, params).fetchone()[0]


def _event_markets(con, event_id, dsv=DSV):
    return _q1(con, "SELECT COUNT(*) FROM markets WHERE event_id=? AND dataset_version=?",
               [event_id, dsv])


def _ckpt_has(con, event_id, dsv=DSV):
    return _q1(con, "SELECT COUNT(*) FROM discovery_checkpoint WHERE dataset_version=? AND event_id=?",
               [dsv, event_id]) == 1


def _ckpt_committed_at(con, event_id, dsv=DSV):
    return _q1(con, "SELECT committed_at FROM discovery_checkpoint WHERE dataset_version=? AND event_id=?",
               [dsv, event_id])


def _counts(con, dsv=DSV):
    return {t: _q1(con, f"SELECT COUNT(*) FROM {t} WHERE dataset_version=?", [dsv])
            for t in _FACT_TABLES}


def _dupes(con, dsv=DSV):
    d = {}
    d["markets"] = _q1(con, "SELECT COUNT(*) FROM (SELECT 1 FROM markets WHERE dataset_version=? "
                            "GROUP BY market_id, dataset_version, record_version HAVING COUNT(*)>1)", [dsv])
    d["outcomes"] = _q1(con, "SELECT COUNT(*) FROM (SELECT 1 FROM outcomes WHERE dataset_version=? "
                             "GROUP BY token_id, dataset_version, record_version HAVING COUNT(*)>1)", [dsv])
    d["market_fee_schedule"] = _q1(con, "SELECT COUNT(*) FROM (SELECT 1 FROM market_fee_schedule "
                                        "WHERE dataset_version=? GROUP BY fee_regime, dataset_version, "
                                        "record_version HAVING COUNT(*)>1)", [dsv])
    d["data_quality"] = _q1(con, "SELECT COUNT(*) FROM (SELECT 1 FROM data_quality WHERE dataset_version=? "
                                 "GROUP BY ref, dataset_version HAVING COUNT(*)>1)", [dsv])
    d["discovery_checkpoint"] = _q1(con, "SELECT COUNT(*) FROM (SELECT 1 FROM discovery_checkpoint "
                                         "WHERE dataset_version=? GROUP BY dataset_version, event_id "
                                         "HAVING COUNT(*)>1)", [dsv])
    return d


def _identity(con, dsv=DSV):
    """STRONG equivalence fingerprint — NOT just totals. Captures the actual identity
    sets (PK tuples per table + processed event_ids + final checkpoint event_ids +
    per-table counts), so two DIFFERENT results with equal counts cannot be mistaken
    for equivalent. (Non-PK volatile columns like ingestion_timestamp are excluded on
    purpose: they legitimately differ between the clean and the resumed wall-clock.)"""
    def rows(sql):
        return con.execute(sql, [dsv]).fetchall()
    return {
        "markets_pk": sorted(rows("SELECT market_id, record_version FROM markets WHERE dataset_version=?")),
        "outcomes_pk": sorted(rows("SELECT token_id, record_version FROM outcomes WHERE dataset_version=?")),
        "fees_pk": sorted(rows("SELECT fee_regime, record_version FROM market_fee_schedule WHERE dataset_version=?")),
        "data_quality_pk": sorted(rows("SELECT ref FROM data_quality WHERE dataset_version=?")),
        "market_event_ids": sorted({r[0] for r in rows("SELECT DISTINCT event_id FROM markets WHERE dataset_version=?")}),
        "checkpoint_event_ids": sorted(r[0] for r in rows("SELECT event_id FROM discovery_checkpoint WHERE dataset_version=?")),
        "counts": {t: rows(f"SELECT COUNT(*) FROM {t} WHERE dataset_version=?")[0][0] for t in _FACT_TABLES},
    }


def _open(path):
    return db.init_db(db_path=path)   # reopen (triggers DuckDB WAL recovery)


# --------------------------------------------------------------- unit: atomic rollback
def test_rollback_leaves_no_rows_and_no_checkpoint(con, monkeypatch):
    """If any write in the event fails, the whole event rolls back AND the checkpoint
    mark (the last write before COMMIT) is never persisted."""
    import gamma_fixtures
    from weather_agent.polymarket import discovery
    real_upsert = db.upsert

    def boom(con_, table, row, keys):
        if table == "data_quality":
            raise RuntimeError("injected failure")
        return real_upsert(con_, table, row, keys)

    monkeypatch.setattr(db, "upsert", boom)
    dsv = "ds_rollback"
    with pytest.raises(RuntimeError):
        discovery.ingest_event(con, gamma_fixtures.NYC_EVENT, dsv, run_id="r")
    assert db.checkpoint_load(con, dsv) == set()
    assert _q1(con, "SELECT COUNT(*) FROM markets WHERE dataset_version=?", [dsv]) == 0


# --------------------------------------------------------- scenario: before_event2
def test_before_event2_kill_and_resume(tmp_path):
    db_clean = str(tmp_path / "clean.duckdb")
    db_test = str(tmp_path / "test.duckdb")

    _run_blocking("clean", db_clean)                       # reference run
    _run_interrupt(db_test, "before_event2")               # parent SIGKILLs child

    # after the kill: event 1 committed, event 2 not ingested at all
    con = _open(db_test)
    try:
        assert _event_markets(con, NYC_ID) > 0             # event 1 exists
        assert _ckpt_has(con, NYC_ID)                      # event 1 checkpoint exists
        assert _event_markets(con, ANKARA_ID) == 0         # event 2 does NOT exist
        assert not _ckpt_has(con, ANKARA_ID)               # event 2 checkpoint absent
        nyc_committed_at = _ckpt_committed_at(con, NYC_ID)
    finally:
        con.close()

    _run_blocking("resume", db_test)                       # second independent process

    con = _open(db_test)
    try:
        assert _ckpt_committed_at(con, NYC_ID) == nyc_committed_at   # event 1 NOT reprocessed
        assert _event_markets(con, ANKARA_ID) > 0          # event 2 processed
        assert _ckpt_has(con, ANKARA_ID)                   # event 2 checkpoint present
        identity_resumed, dupes = _identity(con), _dupes(con)
    finally:
        con.close()

    con = _open(db_clean)
    try:
        identity_clean = _identity(con)
    finally:
        con.close()

    # STRONG equivalence: identical PK/event-id identity sets per table + identical
    # final checkpoints + identical counts (not totals alone) + zero duplicates.
    assert identity_resumed == identity_clean, "resume != clean run (identity mismatch)"
    assert all(v == 0 for v in dupes.values())             # zero duplicates


# --------------------------------------------------------- scenario: during_event2
def test_during_event2_wal_rollback_and_resume(tmp_path):
    db_clean = str(tmp_path / "clean2.duckdb")
    db_test = str(tmp_path / "test2.duckdb")

    _run_blocking("clean", db_clean)
    _run_interrupt(db_test, "during_event2")               # kill mid event-2 txn

    con = _open(db_test)                                    # WAL recovery on open
    try:
        assert _event_markets(con, NYC_ID) > 0             # event 1 survived
        assert _ckpt_has(con, NYC_ID)                      # event 1 checkpoint survived
        assert _event_markets(con, ANKARA_ID) == 0         # event 2 rolled back
        assert not _ckpt_has(con, ANKARA_ID)               # event 2 checkpoint rolled back
    finally:
        con.close()

    _run_blocking("resume", db_test)

    con = _open(db_test)
    try:
        assert _event_markets(con, ANKARA_ID) > 0          # event 2 processed on resume
        assert _ckpt_has(con, ANKARA_ID)
        identity_resumed, dupes = _identity(con), _dupes(con)
    finally:
        con.close()

    con = _open(db_clean)
    try:
        identity_clean = _identity(con)
    finally:
        con.close()

    assert identity_resumed == identity_clean, "resume != clean run (identity mismatch)"
    assert all(v == 0 for v in dupes.values())
