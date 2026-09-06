"""
test_rule_classifier_adversarial.py — R29 review: cases CATALOG_V2 does NOT exercise
=====================================================================================
The catalogue has exactly 4 primary-clause heads ('Wunderground', 'NOAA', 'the Hong
Kong Observatory', 'the Taipei Central Weather Administration') and exactly 2 fallback
sentences, so the validator cannot see regex-ordering defects. These tests build
descriptions FROM the verbatim fixtures (never invented templates) and pin
  * the source must never be guessed from station/URL text outside the clause head;
  * a NOAA description whose primary clause is truncated must stay P_UNKNOWN
    (rule never inferred from the fallback sentence);
  * the HKO ordering defect: the NOAA pattern `weather\\.gov` also matches
    `weather.gov.hk` and NOAA is tried before HKO -> an HKO description without an
    'information from' clause (INFERRED path) is labelled NOAA. Marked xfail(strict)
    so the suite is green but the defect cannot be forgotten: fix by ordering HKO
    before NOAA in _SOURCE_NAME_RES or with `weather\\.gov(?!\\.hk)`.
"""
from __future__ import annotations

import pytest

from weather_agent.polymarket import resolution as res
from gamma_fixtures import (
    NOAA_FALLBACK_DAILYOBS_DESC, HKO_DESC, WU_GENERIC_DESC, NYC_EVENT,
)


def test_truncated_noaa_excerpt_never_infers_rule_from_fallback():
    # first sentence + fallback only: source NOAA is INFERRED, but the rule stays
    # P_UNKNOWN and no 'measurement_rule' key (the fallback's 'Daily Observations'
    # wording must not leak into the primary rule — the R12 defect).
    parts = NOAA_FALLBACK_DAILYOBS_DESC.split("\n\n")
    d = parts[0] + "\n\n" + parts[2]
    assert d.startswith("This market will resolve") and d.rstrip().endswith("resolution source.")
    p = res.parse_resolution_text(d)
    assert p["primary_clause"] is None
    assert p["contract_source"] == res.SRC_NOAA
    assert p["contract_source_confidence"] == res.INFERRED
    assert p["measurement_rule_code"] == res.P_UNKNOWN
    assert "measurement_rule" not in p
    assert p["fallback_source"] == res.SRC_WU


def test_unknown_source_in_primary_head_is_unknown_not_guessed():
    d = NOAA_FALLBACK_DAILYOBS_DESC.replace(
        "information from NOAA, specifically", "information from the National Weather Service, specifically")
    p = res.parse_resolution_text(d)
    assert p["contract_source"] == res.SRC_UNKNOWN
    assert p["contract_source_confidence"] == res.UNKNOWN
    assert p["measurement_rule_code"] == res.P_UNKNOWN
    assert "measurement_rule" not in p


def test_noaa_wording_outside_the_clause_head_does_not_flip_wu():
    # 'recorded by NOAA at the ... Station' in sentence 1 (station text) must not
    # override 'information from Wunderground' in the primary clause head.
    d = WU_GENERIC_DESC.replace("recorded at the London City", "recorded by NOAA at the London City")
    p = res.parse_resolution_text(d)
    assert p["contract_source"] == res.SRC_WU
    assert p["measurement_rule_code"] == res.P_WU_GENERIC


def test_by_forecast_wins_over_later_daily_observations_mention():
    d = NYC_EVENT["description"] + "\n\nSee the Daily Observations table."
    p = res.parse_resolution_text(d)
    assert p["measurement_rule_code"] == res.P_BY_FORECAST


def test_lowercase_if_mid_sentence_does_not_change_classification():
    # a non-fallback conditional ('even if a reading is missing') is swallowed by
    # _FALLBACK_RE (re.I): classification must still be unaffected.
    d = WU_GENERIC_DESC.replace("This market can not resolve until",
                                "This market can not resolve, even if a reading is missing, until")
    p = res.parse_resolution_text(d)
    assert (p["contract_source"], p["measurement_rule_code"], p["fallback_source"]) == \
        (res.SRC_WU, res.P_WU_GENERIC, None)


def test_hko_verbatim_clause_is_hko_even_after_fallback_removal():
    body, fallbacks = res.split_fallback_clauses(HKO_DESC)
    assert fallbacks == [] and body == HKO_DESC
    assert res.classify_source(res.primary_clause(HKO_DESC)) == res.SRC_HKO


@pytest.mark.xfail(strict=True, reason=(
    "R29 defect: _SOURCE_NAME_RES tries NOAA (`weather\\.gov`) before HKO, and "
    "`weather.gov.hk` matches it -> an HKO description without 'information from' "
    "clause (INFERRED path, whole-body search) is labelled NOAA."))
def test_hko_without_primary_clause_is_not_noaa():
    d = HKO_DESC.replace(
        "The resolution source for this market will be information from the Hong Kong Observatory, specifically",
        "The resolution source is")
    assert "information from" not in d and "weather.gov.hk" in d and "Hong Kong Observatory" in d
    p = res.parse_resolution_text(d)
    assert p["primary_clause"] is None
    assert p["contract_source"] == res.SRC_HKO
    assert p["contract_source"] != res.SRC_NOAA


@pytest.mark.xfail(strict=True, reason="same ordering defect, fallback sentence naming HKO by URL only")
def test_fallback_naming_hko_by_url_is_not_noaa():
    d = WU_GENERIC_DESC + ("\n\nIf Wunderground data is unavailable, the data at "
                           "https://www.weather.gov.hk/en/cis/climat.htm will be used.")
    p = res.parse_resolution_text(d)
    assert p["contract_source"] == res.SRC_WU
    assert p["fallback_source"] == res.SRC_HKO
