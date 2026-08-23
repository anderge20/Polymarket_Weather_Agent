"""
test_fees_mapping.py — Phase 2B fee / tick / min mapping
========================================================
STATUS: IMPLEMENTED, NOT EXECUTED here. Runnable on Hetzner. Evidences BOTH fee
epochs (recent weather_fees vs legacy fees_disabled) + tick/min presence.
"""
from __future__ import annotations

from weather_agent.polymarket import fees
from gamma_fixtures import NYC_EVENT, ANKARA_EVENT


def test_recent_weather_fees_known():
    f = fees.map_fees(ANKARA_EVENT["markets"][0])
    assert f["fee_regime"] == "weather_fees"
    assert f["taker_fee"] == 0.05
    assert f["maker_rebate"] == 0.25
    assert f["fee_status"] == "KNOWN"
    assert f["raw_fee_fields"]["makerBaseFee"] == 1000
    assert f["raw_fee_fields"]["takerBaseFee"] == 1000


def test_legacy_fees_disabled_known_zero_justified():
    f = fees.map_fees(NYC_EVENT["markets"][0])   # feesEnabled=False, feeType=None
    assert f["fee_regime"] == "fees_disabled"
    assert f["taker_fee"] == 0.0                  # 0 is JUSTIFIED by feesEnabled=false
    assert f["maker_rebate"] == 0.0
    assert f["fee_status"] == "KNOWN"


def test_absent_fees_unknown():
    f = fees.map_fees({})                         # no fee fields at all
    assert f["fee_regime"] == "UNKNOWN"
    assert f["taker_fee"] is None
    assert f["maker_rebate"] is None
    assert f["fee_status"] == "UNKNOWN"


def test_tick_min_present():
    assert fees.map_tick_min(NYC_EVENT["markets"][0]) == (0.001, 5.0)
    assert fees.map_tick_min(ANKARA_EVENT["markets"][0]) == (0.001, 5.0)


def test_tick_min_absent_is_null():
    # correction #7: NO hardcoded default; NULL when the field is absent.
    assert fees.map_tick_min({}) == (None, None)
