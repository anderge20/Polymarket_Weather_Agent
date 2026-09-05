"""
test_market_asof.py — market price/trade as-of  (PENDING / STUB)
===============================================================
Historical CLOB price ingestion is tested with injected responses; it does not
claim that a CLOB midpoint is an executable fill.

WHAT IT WILL ASSERT (once 2B+ lands):
  * "The indicative price at or before the lead" = latest_asof(price_history,
    'observation_time', lead_ts, partition=[token_id]) — never a later point.
  * The price used is INDICATIVE (price_semantics != 'EXECUTABLE'; enforced by a
    CHECK constraint in 2A) and is never treated as a fillable/executable price.
  * trades/orderbook (FORWARD-ONLY) are only read at times they actually exist;
    no historical L2 is assumed.

SCHEMA SUPPORT ALREADY IN 2A:
  * price_history.observation_time + price_semantics + source_window (DIRECT/DERIVED)
  * trades."timestamp", orderbook_snapshots."timestamp"
  * database.query_asof / database.latest_asof
"""
from __future__ import annotations

from datetime import datetime, timezone

from weather_agent import database as db
from weather_agent.polymarket import prices


class _Response:
    def __init__(self, status_code, body):
        self.status_code, self._body = status_code, body

    def json(self):
        return self._body


class _Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, *, params, timeout):
        self.calls.append((url, params, timeout))
        return self.responses.pop(0)


def test_indicative_price_asof_lead(con):
    """latest_asof(price_history, 'observation_time', lead_ts) must return the last
    point at or before the lead, and it must be INDICATIVE."""
    session = _Session([_Response(200, {"history": [
        {"t": 100, "p": 0.30}, {"t": 160, "p": 0.40}, {"t": 220, "p": 0.90},
    ]})])
    got = prices.ingest_history(con, session, market_id="m", token_id="yes",
                                start_ts=0, end_ts=300, dataset_version="d")
    assert got["status"] == prices.S_OK and got["points_written"] == 3
    at_lead = db.latest_asof(
        con, "price_history", time_col="observation_time",
        asof=datetime.fromtimestamp(180, timezone.utc), partition_cols=["token_id"],
    )
    assert len(at_lead) == 1
    assert at_lead[0]["observation_time"] == datetime.fromtimestamp(160, timezone.utc)
    assert at_lead[0]["indicative_price"] == 0.40
    assert session.calls[0][1]["fidelity"] == 1


def test_no_executable_price_assumed_and_reingest_is_idempotent(con):
    """No component may treat price_history.indicative_price as an executable price."""
    body = {"history": [{"t": 100, "p": 0.30}]}
    first = prices.ingest_history(con, _Session([_Response(200, body)]),
                                  market_id="m", token_id="yes", start_ts=0,
                                  end_ts=200, dataset_version="d")
    second = prices.ingest_history(con, _Session([_Response(200, body)]),
                                   market_id="m", token_id="yes", start_ts=0,
                                   end_ts=200, dataset_version="d")
    row = db.query(con, "SELECT * FROM price_history")[0]
    assert first["points_written"] == second["points_written"] == 1
    assert row["price_semantics"] == "MIDPOINT_ESTIMATED"
    assert row["price_semantics"] != "EXECUTABLE"
    assert row["source_window"] == "DIRECT"


def test_rate_limit_writes_nothing(con):
    got = prices.ingest_history(con, _Session([_Response(429, {})]), market_id="m",
                                token_id="yes", start_ts=0, end_ts=200,
                                dataset_version="d")
    assert got["status"] == prices.S_RATE_LIMITED
    assert db.query(con, "SELECT * FROM price_history") == []


def test_stitches_at_48h_without_partial_write_on_late_error(con):
    start, middle, end = 0, 48 * 60 * 60, 49 * 60 * 60
    session = _Session([
        _Response(200, {"history": [{"t": 60, "p": 0.30}]}),
        _Response(429, {}),
    ])
    got = prices.ingest_history(con, session, market_id="m", token_id="yes",
                                start_ts=start, end_ts=end, dataset_version="d")
    assert got["status"] == prices.S_RATE_LIMITED
    assert db.query(con, "SELECT * FROM price_history") == []
    assert [c[1]["startTs"] for c in session.calls] == [start, middle]
