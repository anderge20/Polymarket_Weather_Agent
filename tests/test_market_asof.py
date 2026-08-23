"""
test_market_asof.py — market price/trade as-of  (PENDING / STUB)
===============================================================
STATUS: PENDING. Skipped until price/trade ingestion exists (Phase 2B+).
Documents that the 2A schema already supports as-of market reads.

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

import pytest


@pytest.mark.skip(reason="PENDING 2B+: price/trade ingestion not implemented in 2A")
def test_indicative_price_asof_lead():
    """latest_asof(price_history, 'observation_time', lead_ts) must return the last
    point at or before the lead, and it must be INDICATIVE."""
    raise NotImplementedError("implement with the Phase 2B+ price ingestion")


@pytest.mark.skip(reason="PENDING 2B+: price/trade ingestion not implemented in 2A")
def test_no_executable_price_assumed():
    """No component may treat price_history.indicative_price as an executable price."""
    raise NotImplementedError("implement with the Phase 2B+ execution model")
