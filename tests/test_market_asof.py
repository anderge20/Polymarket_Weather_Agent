"""
test_market_asof.py — market price as-of  (Phase 2B: IMPLEMENTED)
=================================================================
Was a PENDING stub in 2A. Now exercises `weather_agent.polymarket.prices`
against the real 2A schema, with an injected fetcher so no test touches the
network.

Asserts the frozen contract:
  * "The indicative price at or before the lead" is the last point at or before
    it — never a later one.
  * The stored price is INDICATIVE; 'EXECUTABLE' is unrepresentable (2A CHECK).
  * A missing price fails CLOSED (raises), never a default or a forward-fill.
  * Windows are capped and stitched at native fidelity; re-ingestion is idempotent.
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


def _fake_fetcher(series: dict[datetime, float]):
    """A `fetch_window` stand-in serving `series`, honouring the range bounds."""

    def fetch(token_id, start, end, fidelity=1, **kw):
        return [
            prices.PricePoint(t, p)
            for t, p in sorted(series.items())
            if start <= t <= end
        ]

    return fetch


SERIES = {_t(9): 0.40, _t(10): 0.45, _t(11): 0.55, _t(13): 0.60}


@pytest.fixture
def ingested(con):
    prices.ingest(
        con, TOKEN, MARKET, _t(9), _t(13), DSV, fetcher=_fake_fetcher(SERIES)
    )
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
    row = prices.price_asof(ingested, TOKEN, _t(11), dataset_version=DSV)
    assert row["indicative_price"] == 0.55


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
# windowing, stitching, idempotency
# --------------------------------------------------------------------------


def test_windows_are_capped():
    start = _t(0)
    end = start + timedelta(hours=150)
    ws = list(prices.windows(start, end))
    assert all((b - a) <= timedelta(hours=prices.MAX_WINDOW_HOURS) for a, b in ws)
    assert ws[0][0] == start and ws[-1][1] == end
    # contiguous: each window starts where the previous ended
    assert all(ws[i][1] == ws[i + 1][0] for i in range(len(ws) - 1))


def test_stitching_dedups_window_boundaries():
    """Consecutive windows share an instant; the series must not double it."""
    long_series = {_t(0) + timedelta(hours=i): 0.5 for i in range(0, 100)}
    pts = prices.fetch_series(
        TOKEN, _t(0), _t(0) + timedelta(hours=99), fetcher=_fake_fetcher(long_series)
    )
    ts = [p.t for p in pts]
    assert len(ts) == len(set(ts)) == 100
    assert ts == sorted(ts)


def test_ingest_is_idempotent(con):
    f = _fake_fetcher(SERIES)
    n1 = prices.ingest(con, TOKEN, MARKET, _t(9), _t(13), DSV, fetcher=f)
    prices.ingest(con, TOKEN, MARKET, _t(9), _t(13), DSV, fetcher=f)
    total = db.query(con, "SELECT count(*) AS n FROM price_history")[0]["n"]
    assert total == n1 == len(SERIES)


def test_naive_datetime_rejected():
    """As-of logic is undefined without a timezone; refuse rather than guess."""
    with pytest.raises(ValueError):
        list(prices.windows(datetime(2026, 8, 16, 9), _t(13)))


def test_fidelity_below_native_rejected():
    with pytest.raises(ValueError):
        prices.fetch_window(TOKEN, _t(9), _t(10), fidelity=0)
