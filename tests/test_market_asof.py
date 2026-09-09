"""
test_market_asof.py — market price as-of  (Phase 2B: IMPLEMENTED)
=================================================================
Was a PENDING stub in 2A. Exercises `weather_agent.polymarket.prices` against the
real 2A schema with a fake session, so no test touches the network.

Merges two independent test sets: Codex's (transport discipline — rate limiting,
atomicity, no partial writes) and Claude's (as-of semantics, windowing, the
"never executable" invariant).

Asserts the frozen contract:
  * The price at the lead is the last point at or before it, never a later one.
  * The stored price is INDICATIVE; 'EXECUTABLE' is unrepresentable (2A CHECK).
  * A missing price fails CLOSED.
  * A 429 stops and writes NOTHING; it is never retried (gate D0).
  * A failure part-way through a stitched interval writes NOTHING.
  * Contradictory prices for the same instant are refused, not silently resolved.
  * The endpoint range is [startTs, endTs) — measured, and honoured in validation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from weather_agent import database as db
from weather_agent.polymarket import prices

DSV = "ds_test_2b"
TOKEN = "0xtoken-yes"
MARKET = "0xmarket"


def _t(h: int, m: int = 0) -> datetime:
    return datetime(2026, 8, 16, h, m, tzinfo=timezone.utc)


def _ts(h: int, m: int = 0) -> int:
    return int(_t(h, m).timestamp())


class _Resp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {"history": []}

    def json(self):
        return self._payload


class _Session:
    """A `requests`-shaped session serving a fixed series, honouring [start, end)."""

    def __init__(self, series: dict[int, float], status_code=200, fail_after=None):
        self.series = series
        self.status_code = status_code
        self.fail_after = fail_after  # nth call (1-based) returns 429
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        if self.fail_after is not None and self.calls >= self.fail_after:
            return _Resp(429)
        if self.status_code != 200:
            return _Resp(self.status_code)
        a, b = params["startTs"], params["endTs"]
        # the real endpoint includes BOTH ends; the fake must too, or the
        # tests pass against a behaviour the API does not have.
        hist = [{"t": t, "p": p} for t, p in sorted(self.series.items()) if a <= t <= b]
        return _Resp(200, {"history": hist})


SERIES = {_ts(9): 0.40, _ts(10): 0.45, _ts(11): 0.55, _ts(13): 0.60}


@pytest.fixture
def ingested(con):
    s = _Session(SERIES)
    prices.ingest(con, s, TOKEN, MARKET, _t(9), _t(14), DSV)
    return con


# --------------------------------------------------------------------------
# as-of semantics
# --------------------------------------------------------------------------


def test_indicative_price_asof_lead(ingested):
    """The price at the lead is the last point at or before it, never a later one."""
    row = prices.price_asof(ingested, TOKEN, _t(12), dataset_version=DSV)
    assert row["indicative_price"] == 0.55  # the 11:00 point, not the 13:00 one
    assert row["price_semantics"] != "EXECUTABLE"
    assert row["price_semantics"] == prices.PRICE_SEMANTICS


def test_asof_exactly_on_a_point_takes_that_point(ingested):
    assert prices.price_asof(ingested, TOKEN, _t(11), dataset_version=DSV)[
        "indicative_price"
    ] == 0.55


def test_asof_before_first_point_fails_closed(ingested):
    """No price yet is an error, never a zero, a default, or the next point."""
    with pytest.raises(prices.NoPriceAsOf):
        prices.price_asof(ingested, TOKEN, _t(8), dataset_version=DSV)


def test_asof_never_leaks_another_token(ingested):
    with pytest.raises(prices.NoPriceAsOf):
        prices.price_asof(ingested, "0xother-token", _t(12), dataset_version=DSV)


# --------------------------------------------------------------------------
# "never executable"
# --------------------------------------------------------------------------


def test_no_executable_price_assumed(ingested):
    """Every stored row is indicative, and 'EXECUTABLE' cannot be written at all."""
    rows = db.query(ingested, "SELECT DISTINCT price_semantics FROM price_history")
    assert [r["price_semantics"] for r in rows] == [prices.PRICE_SEMANTICS]

    with pytest.raises(Exception):  # 2A CHECK constraint
        db.insert(
            ingested,
            "price_history",
            {
                "observation_time": _t(14).isoformat(),
                "market_id": MARKET,
                "token_id": TOKEN,
                "indicative_price": 0.5,
                "price_semantics": "EXECUTABLE",
                "dataset_version": DSV,
                "record_version": 1,
            },
        )


def test_source_window_is_direct(ingested):
    rows = db.query(ingested, "SELECT DISTINCT source_window FROM price_history")
    assert [r["source_window"] for r in rows] == [prices.SOURCE_WINDOW_DIRECT]


# --------------------------------------------------------------------------
# transport discipline: rate limits and atomicity
# --------------------------------------------------------------------------


def test_rate_limit_writes_nothing_and_is_not_retried(con):
    """A 429 stops the walk. Nothing is written, and the call is made ONCE."""
    s = _Session(SERIES, fail_after=1)
    summary = prices.ingest(con, s, TOKEN, MARKET, _t(9), _t(14), DSV)
    assert summary["status"] == prices.S_RATE_LIMITED
    assert summary["points_written"] == 0
    assert db.query(con, "SELECT count(*) AS n FROM price_history")[0]["n"] == 0
    assert s.calls == 1  # never retried — gate D0


def test_rate_limit_is_a_stop_status():
    assert prices.S_RATE_LIMITED in prices.STOP_STATUSES


def test_late_error_leaves_no_partial_write(con):
    """A stitched interval that fails on its second window writes nothing at all."""
    long_series = {_ts(0) + i * 3600: 0.5 for i in range(100)}
    s = _Session(long_series, fail_after=2)
    start = _t(0)
    summary = prices.ingest(con, s, TOKEN, MARKET, start, start + timedelta(hours=99), DSV)
    assert summary["status"] in prices.ERROR_STATUSES
    assert db.query(con, "SELECT count(*) AS n FROM price_history")[0]["n"] == 0
    assert s.calls == 2


def test_http_error_writes_nothing(con):
    s = _Session(SERIES, status_code=500)
    summary = prices.ingest(con, s, TOKEN, MARKET, _t(9), _t(14), DSV)
    assert summary["status"] == prices.S_HTTP_ERROR
    assert db.query(con, "SELECT count(*) AS n FROM price_history")[0]["n"] == 0


def test_point_outside_the_requested_range_is_refused(con):
    class Rogue(_Session):
        def get(self, url, params=None, timeout=None):
            self.calls += 1
            return _Resp(200, {"history": [{"t": params["endTs"] + 60, "p": 0.5}]})

    summary = prices.ingest(con, Rogue({}), TOKEN, MARKET, _t(9), _t(14), DSV)
    assert summary["status"] == prices.S_PARSE
    assert db.query(con, "SELECT count(*) AS n FROM price_history")[0]["n"] == 0


def test_contradictory_price_for_same_instant_is_refused(con):
    """Two windows reporting different prices for one instant is a source
    contradiction; picking one silently would invent data."""
    flip = {"n": 0}

    class Contradictory(_Session):
        def get(self, url, params=None, timeout=None):
            self.calls += 1
            flip["n"] += 1
            t = params["startTs"]
            return _Resp(200, {"history": [{"t": t, "p": 0.4 if flip["n"] == 1 else 0.9}]})

    # two windows, both reporting a point at their own start: the stitcher only
    # sees a contradiction if the same instant differs, so force that instant.
    class SameInstant(Contradictory):
        def get(self, url, params=None, timeout=None):
            self.calls += 1
            flip["n"] += 1
            return _Resp(200, {"history": [{"t": params["startTs"], "p": 0.4}]}) if flip["n"] == 1 else _Resp(
                200, {"history": [{"t": _ts(0), "p": 0.9}]}
            )

    start = _t(0)
    summary = prices.ingest(
        con, SameInstant({}), TOKEN, MARKET, start, start + timedelta(hours=99), DSV
    )
    assert summary["status"] == prices.S_PARSE
    assert db.query(con, "SELECT count(*) AS n FROM price_history")[0]["n"] == 0


# --------------------------------------------------------------------------
# windowing and idempotency
# --------------------------------------------------------------------------


def test_windows_are_capped_and_contiguous():
    ws = list(prices.windows(_ts(0), _ts(0) + 150 * 3600))
    assert all((b - a) <= prices.MAX_WINDOW_SECONDS for a, b in ws)
    assert ws[0][0] == _ts(0) and ws[-1][1] == _ts(0) + 150 * 3600
    assert all(ws[i][1] == ws[i + 1][0] for i in range(len(ws) - 1))


def test_range_start_is_inclusive():
    """A point at exactly startTs belongs to the window (measured 2026-09-06)."""
    s = _Session({_ts(9): 0.4})
    status, pts = prices.fetch_history(s, TOKEN, _ts(9), _ts(14))
    assert status == prices.S_OK
    assert [p["t"] for p in pts] == [_ts(9)]


def test_stitching_covers_a_long_interval_without_duplicates():
    long_series = {_ts(0) + i * 3600: 0.5 for i in range(100)}
    s = _Session(long_series)
    status, pts = prices.fetch_history(s, TOKEN, _ts(0), _ts(0) + 100 * 3600)
    assert status == prices.S_OK
    ts = [p["t"] for p in pts]
    assert len(ts) == len(set(ts)) == 100
    assert ts == sorted(ts)
    assert s.calls == 3  # 100 h over 48 h windows


def test_ingest_is_idempotent(con):
    s = _Session(SERIES)
    first = prices.ingest(con, s, TOKEN, MARKET, _t(9), _t(14), DSV)
    prices.ingest(con, _Session(SERIES), TOKEN, MARKET, _t(9), _t(14), DSV)
    total = db.query(con, "SELECT count(*) AS n FROM price_history")[0]["n"]
    assert total == first["points_written"] == len(SERIES)


def test_empty_history_is_not_an_error(con):
    s = _Session({})
    summary = prices.ingest(con, s, TOKEN, MARKET, _t(9), _t(14), DSV)
    assert summary["status"] == prices.S_EMPTY
    assert summary["points_written"] == 0


def test_naive_datetime_rejected():
    """As-of logic is undefined without a timezone; refuse rather than guess."""
    with pytest.raises(ValueError):
        list(prices.windows_dt(datetime(2026, 8, 16, 9), _t(13)))


def test_fidelity_below_native_rejected():
    with pytest.raises(ValueError):
        prices.fetch_window(_Session({}), TOKEN, _ts(9), _ts(10), fidelity=0)


def test_backwards_range_rejected():
    with pytest.raises(ValueError):
        list(prices.windows(_ts(13), _ts(9)))


def test_range_end_is_inclusive_too():
    """Regression: a point at exactly endTs is legitimate and must be kept.

    Measured 2026-09-08 (Dallas/KDAL, target 2026-04-08): the endpoint returned a
    point at exactly endTs, and an end-exclusive check discarded all 2 862 points
    of that window as PARSE_ERROR. Absence of a boundary point in an earlier probe
    was mistaken for evidence of exclusion.
    """
    s = _Session({_ts(9): 0.4, _ts(14): 0.9})
    status, pts = prices.fetch_history(s, TOKEN, _ts(9), _ts(14))
    assert status == prices.S_OK
    assert [p["t"] for p in pts] == [_ts(9), _ts(14)]
