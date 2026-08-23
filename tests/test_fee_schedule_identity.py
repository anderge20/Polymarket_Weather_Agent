"""
test_fee_schedule_identity.py — Phase 2B fee-regime identity assumption (#3)
===========================================================================
STATUS: IMPLEMENTED, NOT EXECUTED here. Runnable on Hetzner.

`fee_regime` is derived from `feeType` only, and `market_fee_schedule`'s PK is
(fee_regime, dataset_version, record_version). So two markets in the SAME dataset
with the SAME feeType but a DIFFERENT feeSchedule map to the SAME row slot.

CONCLUSION FROM THE REAL 2B SAMPLE: every observed market sharing a fee_regime
shares an IDENTICAL feeSchedule (the only weather_fees schedule seen is
{rate:0.05, rebateRate:0.25}). So fee_regime is treated as **GLOBAL within a
dataset** and NO schema change (no fee_schedule_hash) is made — the assumption is
DOCUMENTED in PHASE_2B_MARKET_DISCOVERY.md. These tests (a) confirm consistency
for same-schedule markets and (b) make the COLLAPSE RISK explicit so any future
gamma change that violates the assumption is caught.
"""
from __future__ import annotations

import pytest

from weather_agent.polymarket import fees


def test_same_regime_same_schedule_is_consistent():
    m1 = {"feeType": "weather_fees", "feesEnabled": True,
          "feeSchedule": {"rate": 0.05, "rebateRate": 0.25}}
    m2 = {"feeType": "weather_fees", "feesEnabled": True,
          "feeSchedule": {"rate": 0.05, "rebateRate": 0.25}}
    f1, f2 = fees.map_fees(m1), fees.map_fees(m2)
    assert f1["fee_regime"] == f2["fee_regime"] == "weather_fees"
    assert f1["raw_fee_fields"] == f2["raw_fee_fields"]   # no divergence -> safe to share a row


def test_same_regime_different_schedule_is_a_documented_collapse_risk():
    # SAME feeType but DIFFERENT feeSchedule -> SAME fee_regime key, DIFFERENT raw
    # fields. With the current PK these two target the SAME market_fee_schedule row
    # -> silent collapse. NOT observed in the real sample (assumption: GLOBAL). If
    # this ever occurs in real data, a fee_schedule_hash identity is required.
    m1 = {"feeType": "weather_fees", "feesEnabled": True,
          "feeSchedule": {"rate": 0.05, "rebateRate": 0.25}}
    m2 = {"feeType": "weather_fees", "feesEnabled": True,
          "feeSchedule": {"rate": 0.10, "rebateRate": 0.25}}
    f1, f2 = fees.map_fees(m1), fees.map_fees(m2)
    assert f1["fee_regime"] == f2["fee_regime"]           # same regime key ...
    assert f1["raw_fee_fields"] != f2["raw_fee_fields"]   # ... but different schedule


def test_ingest_event_raises_on_fee_schedule_conflict(con):
    # #3 GUARD IN CODE: two markets, SAME feeType/fee_regime but DIFFERENT
    # feeSchedule within one dataset_version -> discovery must STOP (raise
    # FeeScheduleConflict), never silently collapse onto one row.
    from weather_agent.polymarket import discovery
    from gamma_fixtures import ANKARA_EVENT
    ev = {
        "id": "evconf",
        "title": "Highest temperature in Conflictville on August 20?",
        "tags": [{"id": "104596"}],
        "markets": [
            dict(ANKARA_EVENT["markets"][0], id="c1",
                 conditionId="0xc1", clobTokenIds="[\"ctok1a\", \"ctok1b\"]",
                 feeSchedule={"exponent": 1, "rate": 0.05, "takerOnly": True, "rebateRate": 0.25}),
            dict(ANKARA_EVENT["markets"][0], id="c2",
                 conditionId="0xc2", clobTokenIds="[\"ctok2a\", \"ctok2b\"]",
                 feeSchedule={"exponent": 1, "rate": 0.10, "takerOnly": True, "rebateRate": 0.25}),
        ],
    }
    with pytest.raises(discovery.FeeScheduleConflict):
        discovery.ingest_event(con, ev, "ds_conf")
