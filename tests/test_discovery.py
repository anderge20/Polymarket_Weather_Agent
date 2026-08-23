"""
test_discovery.py — Phase 2B discovery: build + write + idempotency
===================================================================
STATUS: IMPLEMENTED, NOT EXECUTED here. Runnable on Hetzner. Exercises
build_market_records (pure parse) and ingest_event (writes markets/outcomes/
market_fee_schedule/data_quality with provenance + dataset_version, idempotent).
"""
from __future__ import annotations

from weather_agent import database as db
from weather_agent.polymarket import discovery
from gamma_fixtures import NYC_EVENT, ANKARA_EVENT


def test_build_market_records_nyc():
    recs = discovery.build_market_records(NYC_EVENT)
    assert len(recs) == 3
    win = recs[1]                                    # 32-33°F (won, disputed)
    m = win["market"]
    assert m["winning_outcome"] == "Yes"
    assert m["station_identifier"] == "KLGA"
    assert m["unit"] == "F"
    assert m["fee_regime"] == "fees_disabled"
    assert m["tick_size"] == 0.001
    assert m["min_order_size"] == 5.0
    assert m["available_at"] is None
    assert m["available_at_confidence"] == "UNKNOWN"
    assert m["settlement_timestamp"] is None
    assert "closedTime" in m["source_timestamps"]    # raw gamma timestamps captured
    assert m["source_timestamp"] is not None         # from createdAt (provenance)
    assert win["evidence"]["disputed"] is True
    outs = win["outcomes"]
    assert len(outs) == 2
    assert outs[0]["is_winner"] is True and outs[1]["is_winner"] is False
    assert (outs[0]["lo"], outs[0]["hi"]) == (32.0, 33.0)


def test_ingest_event_writes_with_provenance(con):
    discovery.ingest_event(con, NYC_EVENT, "ds_2b_test")
    markets = db.query(con, "SELECT * FROM markets ORDER BY market_id")
    assert len(markets) == 3
    for m in markets:
        assert m["dataset_version"] == "ds_2b_test"
        assert m["source"] == "gamma"
        assert m["source_timestamp"] is not None
        assert m["ingestion_timestamp"] is not None
        assert m["available_at"] is None
        assert m["available_at_confidence"] == "UNKNOWN"
    assert db.query(con, "SELECT COUNT(*) AS c FROM outcomes")[0]["c"] == 6
    fee = db.query(con, "SELECT * FROM market_fee_schedule")
    assert len(fee) == 1 and fee[0]["fee_regime"] == "fees_disabled"
    dq = db.query(con, "SELECT COUNT(*) AS c FROM data_quality")[0]["c"]
    assert dq == 3


def test_ingest_is_idempotent(con):
    discovery.ingest_event(con, NYC_EVENT, "ds_2b_test")
    discovery.ingest_event(con, NYC_EVENT, "ds_2b_test")   # re-run must not duplicate
    assert db.query(con, "SELECT COUNT(*) AS c FROM markets")[0]["c"] == 3
    assert db.query(con, "SELECT COUNT(*) AS c FROM outcomes")[0]["c"] == 6
    assert db.query(con, "SELECT COUNT(*) AS c FROM market_fee_schedule")[0]["c"] == 1


def test_ingest_ankara_weather_fees(con):
    discovery.ingest_event(con, ANKARA_EVENT, "ds_ank")
    m = db.query(con, "SELECT * FROM markets")[0]
    assert m["unit"] == "C"
    assert m["station_identifier"] == "LTAC"
    assert m["measurement_rule"] and "Daily Observations" in m["measurement_rule"]
    fee = db.query(con, "SELECT * FROM market_fee_schedule WHERE fee_regime='weather_fees'")
    assert len(fee) == 1
    assert fee[0]["taker_fee"] == 0.05
    assert fee[0]["fee_status"] == "KNOWN"


def test_dataset_version_registered(con):
    discovery.ensure_dataset_version(con, "ds_reg", query_parameters={"tag_id": 104596})
    rows = db.query(con, "SELECT * FROM dataset_versions WHERE version = 'ds_reg'")
    assert len(rows) == 1
    assert rows[0]["source"] == "gamma"
