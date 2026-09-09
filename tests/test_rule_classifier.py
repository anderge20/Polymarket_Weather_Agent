"""
test_rule_classifier.py — R29 contract_source / measurement_rule from the PRIMARY clause
========================================================================================
Refutation R12: NOAA markets carry a FALLBACK sentence that mentions the Weather
Underground 'Daily Observations' table; the pre-R29 parser fired on that phrase and
labelled them WU. Every description here is VERBATIM from CATALOG_V2 (see
tests/gamma_fixtures.py, market_id + v3 labels in the comments) or from live gamma
(NYC/Ankara). The expected labels are the catalogue's round-9 v3.primary_source /
v3.primary_rule (the CWA pair is the documented residual, see
scripts/validate_r29_catalog.py).
"""
from __future__ import annotations

import json

from weather_agent import database as db
from weather_agent.polymarket import discovery
from weather_agent.polymarket import resolution as res
from gamma_fixtures import (
    ANKARA_EVENT, NYC_EVENT,
    NOAA_FALLBACK_DAILYOBS_DESC, NOAA_HOURLY_FALLBACK_DESC,
    HKO_DESC, CWA_DESC, WU_GENERIC_DESC,
)

_WU_DAILYOBS_TEXT = "highest temperature in the 'Daily Observations' table (not Day High & Low)"


# ------------------------------------------------------------ the R12 defect itself
def test_noaa_with_wu_dailyobs_fallback_is_not_wu():
    p = res.parse_resolution_text(NOAA_FALLBACK_DAILYOBS_DESC)
    assert p["contract_source"] == res.SRC_NOAA
    assert p["contract_source"] != res.SRC_WU
    assert p["measurement_rule_code"] == "P_NOAA_TempColumn"
    assert "Daily Observations" not in p["measurement_rule"]
    assert p["measurement_rule"] != _WU_DAILYOBS_TEXT
    assert p["fallback_source"] == res.SRC_WU
    assert p["contract_source_confidence"] == res.VERIFIED
    assert p["primary_clause"].startswith("NOAA, specifically the highest reading under the \"Temp\" column")
    # parse_measurement_rule (public, pre-R29 API) must agree
    assert res.parse_measurement_rule(NOAA_FALLBACK_DAILYOBS_DESC) == p["measurement_rule"]


def test_noaa_hourly_with_wu_dailyobs_fallback():
    p = res.parse_resolution_text(NOAA_HOURLY_FALLBACK_DESC)
    assert p["contract_source"] == res.SRC_NOAA
    assert p["measurement_rule_code"] == "P_NOAA_HourlyData"
    assert "Hourly Data" in p["measurement_rule"]
    assert "Daily Observations" not in p["measurement_rule"]
    assert p["fallback_source"] == res.SRC_WU


def test_fallback_sentence_is_split_out_verbatim():
    body, fallbacks = res.split_fallback_clauses(NOAA_FALLBACK_DAILYOBS_DESC)
    assert len(fallbacks) == 1
    assert fallbacks[0] == ("If NOAA data for the observation date is unavailable by 11:59 PM ET on "
                            "the day following the observation date, the Weather Underground Daily "
                            "Observations table will be used as the resolution source.")
    assert "Daily Observations" not in body
    assert "information from NOAA" in body


# ------------------------------------------------------------------ other sources
def test_hko_absolute_daily_max():
    p = res.parse_resolution_text(HKO_DESC)
    assert p["contract_source"] == res.SRC_HKO
    assert p["measurement_rule_code"] == "P_HKO_AbsDailyMax"
    assert "Absolute Daily Max" in p["measurement_rule"]
    assert p["fallback_source"] is None
    assert p["unit"] == "C"
    assert p["rounding_rule"] == "tenths"


def test_cwa_temperature_column():
    # v3 says SIN_CLAUSULA/P_UNKNOWN (source inaccessible); the CLAUSE itself is
    # explicit -> CWA / P_CWA_TemperatureColumn (documented residual).
    p = res.parse_resolution_text(CWA_DESC)
    assert p["contract_source"] == res.SRC_CWA
    assert p["measurement_rule_code"] == "P_CWA_TemperatureColumn"
    assert p["fallback_source"] is None


def test_wu_generic_without_qualifier():
    p = res.parse_resolution_text(WU_GENERIC_DESC)
    assert p["contract_source"] == res.SRC_WU
    assert p["measurement_rule_code"] == "P_WU_GENERIC_sin_calificador"
    assert p["fallback_source"] is None
    assert p["station_identifier"] == "EGLC"


def test_wu_strings_unchanged_from_pre_r29():
    # WU markets keep the exact pre-R29 measurement_rule strings (stored in the lake)
    nyc = res.parse_resolution_text(NYC_EVENT["description"])
    assert nyc["contract_source"] == res.SRC_WU
    assert nyc["measurement_rule_code"] == "P_byForecast"
    assert nyc["measurement_rule"] == "highest temperature 'by the Forecast', once data finalized (legacy template)"
    assert nyc["fallback_source"] is None
    ank = res.parse_resolution_text(ANKARA_EVENT["description"])
    assert ank["contract_source"] == res.SRC_WU
    assert ank["measurement_rule_code"] == "P_WU_DailyObservations"
    assert ank["measurement_rule"] == _WU_DAILYOBS_TEXT
    assert ank["fallback_source"] is None
    assert ank["contract_source_confidence"] == res.VERIFIED


def test_station_in_primary_clause_does_not_leak_into_source():
    # 'information from Wunderground, ... for the Hong Kong International Airport
    # Station' (18 catalogue markets) is WU, never HKO: only the clause HEAD (up to
    # the first comma) names the source.
    d = NYC_EVENT["description"].replace("LaGuardia Airport", "Hong Kong International Airport")
    p = res.parse_resolution_text(d)
    assert p["contract_source"] == res.SRC_WU
    assert p["measurement_rule_code"] == "P_byForecast"


def test_no_primary_clause_is_inferred_or_unknown():
    # truncated Ankara excerpt (GROUND_TRUTH_FIXTURES): no 'information from' clause
    # -> source INFERRED from the non-fallback text; still WU / DailyObservations.
    fx = res.GROUND_TRUTH_FIXTURES[0]
    p = res.parse_resolution_text(fx["description"])
    assert p["primary_clause"] is None
    assert p["contract_source"] == res.SRC_WU
    assert p["contract_source_confidence"] == res.INFERRED
    assert p["measurement_rule_code"] == "P_WU_DailyObservations"
    # nothing recognisable -> UNKNOWN / P_UNKNOWN and NO measurement_rule key (as before)
    p = res.parse_resolution_text("Will it rain tomorrow?")
    assert p["contract_source"] == res.SRC_UNKNOWN
    assert p["measurement_rule_code"] == res.P_UNKNOWN
    assert "measurement_rule" not in p
    assert p["contract_source_confidence"] == res.UNKNOWN
    p = res.parse_resolution_text("")
    assert p["contract_source"] == res.SRC_UNKNOWN


def test_fallback_wording_never_qualifies_the_primary_rule():
    # a NOAA description whose ONLY 'Daily Observations' mention is the fallback:
    # dropping the fallback sentence must not change the primary classification.
    body, fallbacks = res.split_fallback_clauses(NOAA_FALLBACK_DAILYOBS_DESC)
    without = NOAA_FALLBACK_DAILYOBS_DESC.replace(fallbacks[0], "")
    a = res.classify_measurement_rule(NOAA_FALLBACK_DAILYOBS_DESC)
    b = res.classify_measurement_rule(without)
    assert (a["contract_source"], a["measurement_rule_code"]) == (b["contract_source"], b["measurement_rule_code"])
    assert a["fallback_source"] == res.SRC_WU and b["fallback_source"] is None


def test_public_dict_keeps_pre_r29_keys():
    p = res.parse_resolution_text(ANKARA_EVENT["description"])
    for k in ("station", "station_identifier", "resolution_source", "unit",
              "rounding_rule", "measurement_rule"):
        assert k in p, k
    for k in ("contract_source", "measurement_rule_code", "fallback_source",
              "primary_clause", "contract_source_confidence"):
        assert k in p, k


# --------------------------------------------------------------- discover_rule
def _noaa_event() -> dict:
    ev = dict(NYC_EVENT)
    ev["description"] = NOAA_FALLBACK_DAILYOBS_DESC
    ev["markets"] = [dict(m, description=NOAA_FALLBACK_DAILYOBS_DESC) for m in NYC_EVENT["markets"]]
    return ev


def test_discover_rule_carries_contract_source():
    ev = _noaa_event()
    rule = res.discover_rule(ev["markets"][0], ev)
    assert rule.contract_source == res.SRC_NOAA
    assert rule.fallback_source == res.SRC_WU
    assert rule.measurement_rule_code == "P_NOAA_TempColumn"
    assert rule.confidence["contract_source"] == res.VERIFIED
    assert "Daily Observations" not in rule.measurement_rule


def test_discover_rule_event_desc_fallback_is_inferred():
    ev = _noaa_event()
    m = dict(ev["markets"][0], description="")
    rule = res.discover_rule(m, ev)
    assert rule.contract_source == res.SRC_NOAA
    assert rule.confidence["contract_source"] == res.INFERRED


# ------------------------------------------------------------ discovery persistence
def _resolution_quality(con, market_id: str) -> dict:
    rows = db.query(con, "SELECT resolution_quality FROM data_quality WHERE ref = ?", [market_id])
    assert len(rows) == 1
    rq = rows[0]["resolution_quality"]
    return json.loads(rq) if isinstance(rq, str) else rq


def test_ingest_persists_contract_source_in_evidence_json(con):
    # The evidence JSON carries the full resolution contract regardless of the
    # schema. It used to also assert that markets had NO contract_source column,
    # which encoded "R27/v4 will add it" — and v4 never did, so the classifier's
    # output was persisted nowhere. The migration now creates it, so the column and
    # the evidence must AGREE rather than the column being absent.
    ev = _noaa_event()
    discovery.ingest_event(con, ev, "ds_r29")
    m = db.query(con, "SELECT * FROM markets WHERE market_id = ?", [ev["markets"][0]["id"]])[0]
    assert m["contract_source"] == res.SRC_NOAA
    assert "Daily Observations" not in m["measurement_rule"]
    rc = _resolution_quality(con, ev["markets"][0]["id"])["resolution_contract"]
    assert rc["contract_source"] == res.SRC_NOAA
    assert rc["fallback_source"] == res.SRC_WU
    assert rc["measurement_rule_code"] == "P_NOAA_TempColumn"
    assert rc["contract_source_confidence"] == res.VERIFIED


def test_ingest_writes_contract_source_column_when_present(con):
    # No longer forward-compatible-in-principle: the migration creates the column,
    # so this is the actual path. The ALTER that used to live here is gone — it now
    # collides with the migration, which is how the missing migration was found.
    assert "contract_source" in db.column_names(con, "markets")
    discovery.ingest_event(con, ANKARA_EVENT, "ds_r29_col")
    rows = db.query(con, "SELECT contract_source, measurement_rule FROM markets")
    assert rows and all(r["contract_source"] == res.SRC_WU for r in rows)
    assert all("Daily Observations" in r["measurement_rule"] for r in rows)
    ev = _noaa_event()
    discovery.ingest_event(con, ev, "ds_r29_col")
    rows = db.query(con, "SELECT contract_source FROM markets WHERE market_id = ?",
                    [ev["markets"][0]["id"]])
    assert rows[0]["contract_source"] == res.SRC_NOAA


def test_build_market_records_evidence_has_resolution_contract():
    recs = discovery.build_market_records(_noaa_event())
    for r in recs:
        rc = r["evidence"]["resolution_contract"]
        assert rc["contract_source"] == res.SRC_NOAA
        assert rc["fallback_source"] == res.SRC_WU
        assert "contract_source" not in r["market"]      # not a markets column yet
