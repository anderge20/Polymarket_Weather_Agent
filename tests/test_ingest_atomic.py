"""
test_ingest_atomic.py — Phase 2B: per-event atomicity of ingest_event (#1–#5)
=============================================================================
STATUS: IMPLEMENTED, NOT EXECUTED here. Runnable on Hetzner (needs DuckDB).

ingest_event writes a whole gamma event inside ONE DuckDB transaction
(market -> outcomes -> fee schedule -> provenance/evidence -> COMMIT). If ANY
step fails — including a FeeScheduleConflict (#3) — the ENTIRE event is ROLLED
BACK, so an event can never be persisted partially, and the caller's checkpoint
advances ONLY after a successful COMMIT (so a failed event is retried on resume).
"""
from __future__ import annotations

import json

import pytest

from weather_agent import database
from weather_agent.polymarket import discovery


# --------------------------------------------------------------------------- helpers
def _mkt(mid, cond, tokens, prices, *, gband="20°C or below",
         fee_type=None, fees_enabled=False, schedule=None):
    m = {
        "id": mid, "conditionId": cond, "slug": f"s{mid}", "question": f"q {gband}",
        "groupItemTitle": gband, "outcomes": json.dumps(["Yes", "No"]),
        "outcomePrices": json.dumps(prices), "clobTokenIds": json.dumps(tokens),
        "umaEndDate": "2026-08-20T21:00:00Z", "createdAt": "2026-08-18T00:00:00Z",
        "startDate": "2026-08-18T00:00:00Z", "closedTime": "2026-08-20T21:00:00Z",
        "orderPriceMinTickSize": 0.001, "orderMinSize": 5, "feesEnabled": fees_enabled,
    }
    if fee_type is not None:
        m["feeType"] = fee_type
    if schedule is not None:
        m["feeSchedule"] = schedule
    return m


def _ev(eid, markets):
    return {"id": eid, "title": "Highest temperature in Testville on August 20?",
            "tags": [{"id": "104596"}], "markets": markets}


def _count(con, table, dsv, **where):
    sql = f"SELECT COUNT(*) c FROM {table} WHERE dataset_version = ?"
    params = [dsv]
    for k, v in where.items():
        sql += f" AND {k} = ?"
        params.append(v)
    return database.query(con, sql, params)[0]["c"]


_WF = {"rate": 0.05, "rebateRate": 0.25}
_WF2 = {"rate": 0.10, "rebateRate": 0.25}


class _Resp:
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload
        self.headers = {}

    def json(self):
        return self._p


class _StubSession:
    def __init__(self, resp):
        self._resp = resp
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        return self._resp


# --------------------------------------------------------------------------- tests
def test_ingest_event_atomic_success(con):
    """A clean event commits ALL entities exactly once."""
    ev = _ev("ev1", [
        _mkt("m1", "0x1", ["t1", "t2"], ["1", "0"],
             fee_type="weather_fees", fees_enabled=True, schedule=_WF),
        _mkt("m2", "0x2", ["t3", "t4"], ["0", "1"], gband="21°C",
             fee_type="weather_fees", fees_enabled=True, schedule=_WF),
    ])
    counts = discovery.ingest_event(con, ev, "ds_ok")
    assert counts["markets"] == 2
    assert counts["outcomes"] == 4
    assert _count(con, "markets", "ds_ok") == 2
    assert _count(con, "outcomes", "ds_ok") == 4
    assert _count(con, "market_fee_schedule", "ds_ok") == 1   # one shared regime
    assert _count(con, "data_quality", "ds_ok") == 2


def test_ingest_event_atomic_rollback(con, monkeypatch):
    """A failure at the LAST write (data_quality) rolls the WHOLE event back —
    the market/outcomes/fee rows written earlier in the same transaction vanish."""
    ev = _ev("ev2", [_mkt("m1", "0x1", ["t1", "t2"], ["1", "0"],
                          fee_type="weather_fees", fees_enabled=True, schedule=_WF)])
    real_upsert = database.upsert

    def boom(c, table, row, cols):
        if table == "data_quality":
            raise RuntimeError("injected write failure")
        return real_upsert(c, table, row, cols)

    monkeypatch.setattr(database, "upsert", boom)
    with pytest.raises(RuntimeError):
        discovery.ingest_event(con, ev, "ds_rb")
    monkeypatch.undo()
    assert _count(con, "markets", "ds_rb") == 0
    assert _count(con, "outcomes", "ds_rb") == 0
    assert _count(con, "market_fee_schedule", "ds_rb") == 0
    assert _count(con, "data_quality", "ds_rb") == 0


def test_fee_conflict_rolls_back_entire_event(con):
    """market OK + outcomes OK, then a fee conflict on the 2nd market -> the whole
    event (including the already-written 1st market) is rolled back."""
    ev = _ev("ev3", [
        _mkt("m1", "0x1", ["t1", "t2"], ["1", "0"],
             fee_type="weather_fees", fees_enabled=True, schedule=_WF),
        _mkt("m2", "0x2", ["t3", "t4"], ["0", "1"], gband="21°C",
             fee_type="weather_fees", fees_enabled=True, schedule=_WF2),  # conflict
    ])
    with pytest.raises(discovery.FeeScheduleConflict):
        discovery.ingest_event(con, ev, "ds_conf2")
    assert _count(con, "markets", "ds_conf2") == 0
    assert _count(con, "outcomes", "ds_conf2") == 0
    assert _count(con, "market_fee_schedule", "ds_conf2") == 0
    assert _count(con, "data_quality", "ds_conf2") == 0


def test_helpers_do_not_autocommit(con):
    """db.insert / db.upsert must NOT autonomously commit: a write made inside a
    manual transaction must be undone by ROLLBACK (ingest_event owns the txn). If a
    helper autocommitted, per-event atomicity would be impossible."""
    con.execute("BEGIN TRANSACTION;")
    database.insert(con, "dataset_versions", {"version": "probe_i", "source": "probe"})
    database.upsert(con, "dataset_versions", {"version": "probe_u", "source": "probe"}, ["version"])
    con.execute("ROLLBACK;")
    n = database.query(con, "SELECT COUNT(*) c FROM dataset_versions "
                            "WHERE version IN ('probe_i', 'probe_u')")[0]["c"]
    assert n == 0


def test_checkpoint_advances_only_after_commit(con):
    """discover advances the checkpoint ONLY for events that COMMITTED. Event 1
    commits and is checkpointed; event 2 fee-conflicts, rolls back, and is NOT
    checkpointed (so it is retried on the next resume)."""
    e1 = _ev("e1", [_mkt("e1m", "0xe1", ["e1a", "e1b"], ["1", "0"],
                         fee_type="weather_fees", fees_enabled=True, schedule=_WF)])
    e2 = _ev("e2", [_mkt("e2m", "0xe2", ["e2a", "e2b"], ["0", "1"],
                         fee_type="weather_fees", fees_enabled=True, schedule=_WF2)])
    cp: set = set()
    summary = discovery.discover(con, "ds_ckpt2", page_limit=10, max_pages=1,
                                 session=_StubSession(_Resp(200, [e1, e2])), checkpoint=cp)
    assert "e1" in cp                 # committed -> checkpointed
    assert "e2" not in cp             # rolled back -> NOT checkpointed (retry on resume)
    assert summary["status"] == "DATA_ERROR"
    assert summary["stopped_early"] is True
    assert _count(con, "markets", "ds_ckpt2", market_id="e1m") == 1
    assert _count(con, "markets", "ds_ckpt2", market_id="e2m") == 0   # fully rolled back
