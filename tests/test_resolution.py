"""
test_resolution.py — Phase 2B resolution-discovery parsing (ground truth)
=========================================================================
STATUS: IMPLEMENTED, NOT EXECUTED here. Runnable on Hetzner. Uses REAL gamma
descriptions (NYC legacy Fahrenheit/KLGA + Ankara recent Celsius/LTAC).
"""
from __future__ import annotations

from weather_agent.polymarket import resolution as res
from gamma_fixtures import NYC_EVENT, ANKARA_EVENT


def test_parse_nyc_legacy():
    p = res.parse_resolution_text(NYC_EVENT["description"])
    assert p["station"] == "LaGuardia Airport"
    assert p["station_identifier"] == "KLGA"
    assert p["unit"] == "F"
    assert p["rounding_rule"] == "whole degree"
    assert "Forecast" in p["measurement_rule"]           # legacy template
    assert p["resolution_source"].endswith("KLGA")


def test_parse_ankara_recent():
    p = res.parse_resolution_text(ANKARA_EVENT["description"])
    assert p["station"] == "Esenboğa Intl Airport"
    assert p["station_identifier"] == "LTAC"
    assert p["unit"] == "C"
    assert p["rounding_rule"] == "whole degree"
    assert "Daily Observations" in p["measurement_rule"]  # recent template


def test_icao_from_us_4segment_url():
    # regression: the US URL .../us/ny/new-york-city/KLGA has an extra state
    # segment; the ICAO must be the TAIL (KLGA), never an intermediate segment.
    p = res.parse_resolution_text(NYC_EVENT["description"])
    assert p["station_identifier"] == "KLGA"


def test_parse_band():
    assert res.parse_band("27°F or below") == (None, 27.0)
    assert res.parse_band("32-33°F") == (32.0, 33.0)
    assert res.parse_band("38°F or higher") == (38.0, None)
    assert res.parse_band("31°C") == (31.0, 31.0)
    assert res.parse_band("25°C or below") == (None, 25.0)


def test_resolved_outcome():
    win = NYC_EVENT["markets"][1]    # 32-33°F, outcomePrices ["1","0"]
    lose = NYC_EVENT["markets"][0]   # 27°F or below, ["0","1"]
    assert res.resolved_outcome(win) == "Yes"
    assert res.resolved_outcome(lose) == "No"


def test_event_winning_band_exactly_one_verified():
    r = res.event_winning_band(NYC_EVENT["markets"])
    assert r["status"] == res.VERIFIED
    assert r["winning_band"] == "32-33°F"
    assert r["n_winners"] == 1


def test_event_winning_band_zero_is_unknown():
    # every band resolved "No" -> no winner -> UNKNOWN (never a first match)
    markets = [dict(m, outcomePrices="[\"0\", \"1\"]") for m in NYC_EVENT["markets"]]
    r = res.event_winning_band(markets)
    assert r["status"] == res.UNKNOWN
    assert r["winning_band"] is None
    assert r["n_winners"] == 0


def test_event_winning_band_multiple_is_data_error():
    # two bands resolved "Yes" -> inconsistent resolution -> DATA_ERROR
    markets = [dict(m, outcomePrices="[\"1\", \"0\"]") for m in NYC_EVENT["markets"][:2]]
    r = res.event_winning_band(markets)
    assert r["status"] == res.DATA_ERROR
    assert r["n_winners"] == 2
    assert r["winning_band"] is None


def test_discover_rule_market_specific():
    m = NYC_EVENT["markets"][1]
    rule = res.discover_rule(m, NYC_EVENT, resolution_timestamp="2025-12-31T09:10:57+00:00")
    assert rule.station_identifier == "KLGA"
    assert rule.unit == "F"
    assert rule.winning_outcome == "Yes"
    assert rule.resolution_timestamp == "2025-12-31T09:10:57+00:00"
    assert rule.confidence["station_identifier"] == res.VERIFIED
    assert rule.confidence["winning_outcome"] == res.VERIFIED


def test_ground_truth_fixtures():
    for fx in res.GROUND_TRUTH_FIXTURES:
        p = res.parse_resolution_text(fx["description"])
        for k, v in fx["expect"].items():
            assert p.get(k) == v, f"{fx['city']}: {k} {p.get(k)!r} != {v!r}"


# ------------------------------------------------------ resolved_outcome exactness (#2)
def test_resolved_outcome_invalid_combinations():
    base = NYC_EVENT["markets"][0]
    assert res.resolved_outcome(dict(base, outcomePrices="[\"1\", \"1\"]")) is None    # two 1s
    assert res.resolved_outcome(dict(base, outcomePrices="[\"0\", \"0\"]")) is None    # unresolved
    assert res.resolved_outcome(dict(base, outcomePrices="[\"0.5\", \"0.5\"]")) is None  # fractional
    assert res.resolved_outcome(dict(base, outcomePrices="[\"1\", \"0\"]")) == "Yes"   # valid


# ------------------------------------------------------------ band integrity (#6)
_FULL_NYC_BANDS = ["27°F or below", "28-29°F", "30-31°F", "32-33°F",
                   "34-35°F", "36-37°F", "38°F or higher"]


def test_band_integrity_clean_partition():
    r = res.band_integrity(_FULL_NYC_BANDS)
    assert r["is_partition"] is True
    assert r["overlaps"] == []
    assert r["gaps"] == []
    assert r["lower_open"] == "27°F or below"
    assert r["upper_open"] == "38°F or higher"
    assert r["n_lower_open"] == 1 and r["n_upper_open"] == 1
    assert r["ordered"][0] == "27°F or below"
    assert r["ordered"][-1] == "38°F or higher"


def test_band_integrity_detects_gaps():
    # the trimmed real fixture (3 of 7 bands) MUST show gaps -> not a partition
    labels = [m["groupItemTitle"] for m in NYC_EVENT["markets"]]  # 27below, 32-33, 38higher
    r = res.band_integrity(labels)
    assert r["is_partition"] is False
    assert len(r["gaps"]) >= 1


def test_band_integrity_detects_overlap():
    r = res.band_integrity(["28-29°F", "29-30°F"])
    assert len(r["overlaps"]) >= 1
    assert r["is_partition"] is False


def test_band_integrity_flags_double_open_ended():
    r = res.band_integrity(["27°F or below", "20°F or below", "38°F or higher"])
    assert r["n_lower_open"] == 2
    assert r["is_partition"] is False
