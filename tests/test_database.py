"""
test_database.py — Phase 2A data-layer tests (DuckDB)
=====================================================
STATUS: IMPLEMENTED, NOT EXECUTED here (no Python in the authoring env).
Covers: idempotent schema init, schema_version, presence of every table,
provenance columns on every fact table, round-trip of EVERY table, JSON
round-trip, upsert, append-only versioning (next_record_version), the
"price is never executable" CHECK, and the as-of read helpers.

Run:  pip install -r requirements-pipeline.txt && pytest -q
"""
from __future__ import annotations

import json

import pytest

from weather_agent import database as db

TS = "2026-08-16T11:00:00Z"
TS_LATE = "2026-08-16T12:00:00Z"
DSV = "ds_test_v1"


# One representative, valid row per table (PK + a few fields; nullable cols omitted).
SAMPLE_ROWS: dict[str, dict] = {
    "dataset_versions": {
        "version": DSV, "source": "unit_test",
        "query_parameters": {"tag_id": 104596}, "description": "test dataset",
        "code_version": "abc123", "git_commit": "abc123",
    },
    "market_fee_schedule": {
        "fee_regime": "UNKNOWN", "taker_fee": None, "maker_rebate": None,
        "fee_status": "UNKNOWN", "source": "unit_test",
        "ingestion_timestamp": TS, "dataset_version": DSV, "record_version": 1,
    },
    "markets": {
        "market_id": "m1", "condition_id": "0xcond", "event_id": "e1",
        "slug": "highest-temperature-in-london-on-aug-16",
        "question": "Highest temperature in London on Aug 16?",
        "city": "London", "station": "London City Airport",
        "station_identifier": "EGLC",
        "resolution_source": "https://www.wunderground.com/history/daily/gb/london/EGLC",
        "unit": "C", "rounding_rule": "whole degree", "winning_outcome": "26C",
        "available_resolution": "native_1min", "fee_regime": "UNKNOWN",
        "tick_size": None, "min_order_size": None, "tag_ids": [104596],
        "discovered_at": TS, "source": "gamma /events", "ingestion_timestamp": TS,
        "dataset_version": DSV, "record_version": 1,
    },
    "outcomes": {
        "market_id": "m1", "token_id": "tok_yes_1", "band_label": "26C",
        "lo": 26.0, "hi": 26.0, "outcome_index": 0, "is_winner": True,
        "source": "gamma /events", "ingestion_timestamp": TS,
        "dataset_version": DSV, "record_version": 1,
    },
    "price_history": {
        "observation_time": TS, "market_id": "m1", "token_id": "tok_yes_1",
        "indicative_price": 0.42, "price_semantics": "MIDPOINT_ESTIMATED",
        "price_source": "CLOB_PRICES_HISTORY", "fidelity": 1,
        "source_window": "DIRECT", "fetched_at": TS, "source": "clob /prices-history",
        "ingestion_timestamp": TS, "dataset_version": DSV, "record_version": 1,
    },
    "orderbook_snapshots": {
        "timestamp": TS, "market_id": "m1", "token_id": "tok_yes_1",
        "best_bid": 0.41, "best_ask": 0.43, "mid": 0.42, "spread": 0.02,
        "bid_depth_1": 100.0, "bid_depth_5": 500.0, "bid_depth_10": 900.0,
        "ask_depth_1": 120.0, "ask_depth_5": 480.0, "ask_depth_10": 850.0,
        "imbalance": 0.1, "book_snapshot": {"bids": [[0.41, 100]], "asks": [[0.43, 120]]},
        "collected_at": TS, "collector_session_id": "sess-1", "collector_started_at": TS,
        "source": "clob_ws", "ingestion_timestamp": TS,
        "dataset_version": DSV, "record_version": 1,
    },
    "trades": {
        "timestamp": TS, "market_id": "m1", "token_id": "tok_yes_1",
        "price": 0.42, "size": 50.0, "side": "BUY", "trade_id": "tx1",
        "fetched_at": TS, "collected_at": TS, "collector_session_id": "sess-1",
        "collector_started_at": TS, "source": "data-api /trades", "ingestion_timestamp": TS,
        "dataset_version": DSV, "record_version": 1,
    },
    "weather_forecasts": {
        "issue_time": "2026-08-15T00:00:00Z", "forecast_run": "00z",
        "target_date": "2026-08-16", "city": "London",
        "station": "London City Airport", "model": "ecmwf_ifs025",
        "forecast_tmax": 26.5, "forecast_p10": 24.0, "forecast_p25": 25.0,
        "forecast_p50": 26.0, "forecast_p75": 27.0, "forecast_p90": 28.0,
        "available_at": "2026-08-15T00:30:00Z",
        "fetched_at": TS, "source": "open-meteo historical-forecast",
        "ingestion_timestamp": TS, "dataset_version": DSV, "record_version": 1,
    },
    "weather_observations": {
        "observation_time": "2026-08-17T00:00:00Z", "city": "London",
        "station": "London City Airport", "source": "wunderground",
        "tmax_observed": 26.0, "daily_high_time": "2026-08-16T15:00:00Z",
        "available_at": "2026-08-17T06:00:00Z",
        "fetched_at": TS, "ingestion_timestamp": TS, "dataset_version": DSV,
        "record_version": 1,
    },
    "weather_errors": {
        "city": "London", "station": "London City Airport", "model": "ecmwf_ifs025",
        "lead_hours": 24, "month": 8, "mean_error": 0.5, "median_error": 0.4,
        "std_error": 1.2, "mae": 0.9, "rmse": 1.3, "q05": -1.5, "q10": -1.0,
        "q25": -0.4, "q50": 0.4, "q75": 1.1, "q90": 1.8, "q95": 2.2,
        "derived_from_dataset_version": DSV,
        "source": "derived", "ingestion_timestamp": TS, "dataset_version": DSV,
        "record_version": 1,
    },
    "features": {
        "prediction_time": "2026-08-15T12:00:00Z", "market_id": "m1",
        "token_id": "tok_yes_1", "market_prob": 0.40, "weather_prob": 0.45,
        "forecast_tmax": 26.5, "forecast_p50": 26.0,
        "feature_json": {"spread": 0.02, "lead_h": 24}, "no_lookahead_verified": False,
        "source": "features_v1", "ingestion_timestamp": TS, "dataset_version": DSV,
        "record_version": 1,
    },
    "predictions": {
        "timestamp": "2026-08-15T12:00:00Z", "market_id": "m1",
        "token_id": "tok_yes_1", "p_market": 0.40, "p_weather": 0.45,
        "p_model": 0.43, "fair_value": 0.43, "edge_gross": 0.03, "edge_net": 0.01,
        "confidence": 0.6, "model_version": "wx_v1", "source": "model",
        "ingestion_timestamp": TS, "dataset_version": DSV, "record_version": 1,
    },
    "signals": {
        "timestamp": "2026-08-15T12:00:00Z", "market_id": "m1",
        "token_id": "tok_yes_1", "strategy": "resolution", "signal": "BUY",
        "fair_value": 0.43, "price_assumption": 0.40, "edge": 0.03,
        "net_edge": 0.01, "confidence": 0.6, "reason": "edge>=min_edge",
        "source": "strategy", "ingestion_timestamp": TS, "dataset_version": DSV,
        "record_version": 1,
    },
    "paper_trades": {
        "backtest_id": "bt1", "market_id": "m1", "token_id": "tok_yes_1",
        "entry_time": "2026-08-15T12:00:00Z", "entry_price": 0.40,
        "exit_time": "2026-08-16T12:00:00Z", "exit_price": 1.0, "fees": 0.0,
        "slippage": 0.0, "gross_pnl": 0.60, "net_pnl": 0.60, "settlement": 1.0,
        "size": 100.0, "bankroll_after": 10060.0, "price_layer": "INDICATIVE",
        "source": "paper", "ingestion_timestamp": TS, "dataset_version": DSV,
        "record_version": 1,
    },
    "backtest_results": {
        "backtest_id": "bt1", "run_timestamp": TS, "dataset_version": DSV,
        "model_version": "wx_v1", "parameters": {"min_edge": 0.05},
        "metrics": {"hit_rate": 0.5, "brier": 0.24},
        "walk_forward_config": {"min_train": 60}, "random_seed": 42,
        "feature_list": ["market_prob", "weather_prob"],
        "train_window": "2026-01-01/2026-03-31",
        "validation_window": "2026-04-01/2026-04-30",
        "test_window": "2026-05-01/2026-05-31", "code_version": "abc123",
        "source": "backtester", "ingestion_timestamp": TS,
    },
    "markets_excluded": {
        "market_id": "m2", "reason": "no_price_history", "excluded_at": TS,
        "stage": "pricing", "details": {"note": "empty history window"},
        "source": "ingest", "ingestion_timestamp": TS, "dataset_version": DSV,
        "record_version": 1,
    },
    "data_quality": {
        "ref": "m1", "weather_data_quality": {"status": "PASS"},
        "market_data_quality": {"status": "PASS"},
        "orderbook_quality": {"status": "NA"},
        "resolution_quality": {"status": "PASS"}, "checked_at": TS,
        "source": "qc", "ingestion_timestamp": TS, "dataset_version": DSV,
        "record_version": 1,
    },
}

# A scalar (non-timestamp, non-json) column to assert round-tripped per table.
CHECKS: dict[str, tuple] = {
    "dataset_versions": ("version", DSV),
    "market_fee_schedule": ("fee_status", "UNKNOWN"),
    "markets": ("city", "London"),
    "outcomes": ("band_label", "26C"),
    "price_history": ("price_semantics", "MIDPOINT_ESTIMATED"),
    "orderbook_snapshots": ("spread", 0.02),
    "trades": ("side", "BUY"),
    "weather_forecasts": ("model", "ecmwf_ifs025"),
    "weather_observations": ("tmax_observed", 26.0),
    "weather_errors": ("lead_hours", 24),
    "features": ("weather_prob", 0.45),
    "predictions": ("model_version", "wx_v1"),
    "signals": ("signal", "BUY"),
    "paper_trades": ("price_layer", "INDICATIVE"),
    "backtest_results": ("backtest_id", "bt1"),
    "markets_excluded": ("reason", "no_price_history"),
    "data_quality": ("ref", "m1"),
}


# ------------------------------------------------------------------ schema init
def test_all_tables_created(con):
    present = set(db.table_names(con))
    for t in db.ALL_TABLES:
        assert t in present, f"missing table: {t}"
    assert "schema_version" in present


def test_schema_version_recorded(con):
    assert db.get_schema_version(con) == db.SCHEMA_VERSION


def test_dataset_versions_keyed_by_version(con):
    # The dataset_versions REGISTRY is keyed by `version` (PK); the FACT tables carry a
    # `dataset_version` FK -> dataset_versions.version. Guards the harness idempotency
    # counts: dataset_versions must be filtered by `version`, never `dataset_version`.
    dv_cols = set(db.column_names(con, "dataset_versions"))
    assert "version" in dv_cols
    assert "dataset_version" not in dv_cols
    for t in ("markets", "outcomes", "market_fee_schedule", "data_quality"):
        assert "dataset_version" in set(db.column_names(con, t)), f"{t} missing dataset_version"


def test_init_is_idempotent(con):
    before = set(db.table_names(con))
    db.init_db(con)          # run again on the same connection
    db.init_db(con)          # and again
    after = set(db.table_names(con))
    assert before == after
    assert db.get_schema_version(con) == db.SCHEMA_VERSION
    # exactly one row per applied migration
    n = con.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
    assert n == len(db.MIGRATIONS)


def test_idempotent_on_reopened_file(tmp_path):
    path = str(tmp_path / "wa.duckdb")
    c1 = db.init_db(db_path=path)
    c1.close()
    c2 = db.init_db(db_path=path)   # reopen + re-init must not error or duplicate
    try:
        assert db.get_schema_version(c2) == db.SCHEMA_VERSION
        assert set(db.ALL_TABLES).issubset(set(db.table_names(c2)))
    finally:
        c2.close()


# ------------------------------------------------------------------ provenance
def test_every_fact_table_has_provenance(con):
    for t in db.FACT_TABLES:
        cols = set(db.column_names(con, t))
        missing = set(db.PROVENANCE_COLUMNS) - cols
        assert not missing, f"{t} missing provenance columns: {missing}"


# ------------------------------------------------------------------ round-trip
@pytest.mark.parametrize("table", list(SAMPLE_ROWS.keys()))
def test_round_trip_each_table(con, table):
    db.insert(con, table, SAMPLE_ROWS[table])
    rows = db.query(con, f'SELECT * FROM "{table}"')
    assert len(rows) == 1
    col, expected = CHECKS[table]
    assert rows[0][col] == expected


def test_json_column_round_trips(con):
    db.insert(con, "markets", SAMPLE_ROWS["markets"])
    row = db.query(con, 'SELECT tag_ids FROM markets')[0]
    # JSON is returned as text; it must parse back to the original list.
    assert json.loads(row["tag_ids"]) == [104596]


def test_insert_many(con):
    rows = [
        dict(SAMPLE_ROWS["outcomes"], token_id="tok_yes_1", outcome_index=0),
        dict(SAMPLE_ROWS["outcomes"], token_id="tok_no_1", outcome_index=1,
             is_winner=False),
    ]
    n = db.insert_many(con, "outcomes", rows)
    assert n == 2
    assert con.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0] == 2


# ------------------------------------------------------------------ upsert
def test_upsert_updates_in_place(con):
    key = ["market_id", "dataset_version", "record_version"]
    db.upsert(con, "markets", SAMPLE_ROWS["markets"], key)
    revised = dict(SAMPLE_ROWS["markets"], question="REVISED question")
    db.upsert(con, "markets", revised, key)
    rows = db.query(con, "SELECT question FROM markets")
    assert len(rows) == 1
    assert rows[0]["question"] == "REVISED question"


# ------------------------------------------------------------------ versioning
def test_next_record_version(con):
    db.insert(con, "outcomes", SAMPLE_ROWS["outcomes"])
    nxt = db.next_record_version(
        con, "outcomes", {"token_id": "tok_yes_1"}, dataset_version=DSV
    )
    assert nxt == 2
    # a brand-new fact starts at 1
    assert db.next_record_version(con, "outcomes", {"token_id": "nope"}) == 1


def test_append_only_revision_coexists(con):
    db.insert(con, "outcomes", SAMPLE_ROWS["outcomes"])
    rev2 = dict(SAMPLE_ROWS["outcomes"], record_version=2, is_winner=False)
    db.insert(con, "outcomes", rev2)   # same natural key, new record_version
    rows = db.query(con, "SELECT record_version FROM outcomes ORDER BY record_version")
    assert [r["record_version"] for r in rows] == [1, 2]


# ------------------------------------------------------- price is never executable
def test_price_semantics_rejects_executable(con):
    bad = dict(SAMPLE_ROWS["price_history"], price_semantics="EXECUTABLE")
    with pytest.raises(Exception):
        db.insert(con, "price_history", bad)


def test_source_window_check(con):
    bad = dict(SAMPLE_ROWS["price_history"], source_window="SOMETHING_ELSE")
    with pytest.raises(Exception):
        db.insert(con, "price_history", bad)


# ------------------------------------------------------------------ as-of reads
def test_query_asof_and_latest_asof(con):
    base = SAMPLE_ROWS["price_history"]
    for i, t in enumerate(["2026-08-16T11:00:00Z",
                           "2026-08-16T11:30:00Z",
                           "2026-08-16T12:00:00Z"]):
        db.insert(con, "price_history",
                  dict(base, observation_time=t, indicative_price=0.40 + i * 0.01))

    got = db.query_asof(con, "price_history", "observation_time",
                        "2026-08-16T11:35:00Z")
    assert len(got) == 2  # 11:00 and 11:30 only

    latest = db.latest_asof(con, "price_history", "observation_time",
                            "2026-08-16T11:35:00Z", partition_cols=["token_id"])
    assert len(latest) == 1
    assert latest[0]["indicative_price"] == pytest.approx(0.41)  # the 11:30 point


def test_latest_asof_excludes_future(con):
    base = SAMPLE_ROWS["price_history"]
    # Distinguish the two points by value so the assertion is timezone-independent.
    db.insert(con, "price_history",
              dict(base, observation_time="2026-08-16T09:00:00Z", indicative_price=0.09))
    db.insert(con, "price_history",
              dict(base, observation_time="2026-08-16T23:00:00Z", indicative_price=0.23))
    latest = db.latest_asof(con, "price_history", "observation_time",
                            "2026-08-16T10:00:00Z", partition_cols=["token_id"])
    assert len(latest) == 1
    # the 09:00 point (0.09), never the future 23:00 point (0.23)
    assert latest[0]["indicative_price"] == pytest.approx(0.09)


# ---------------------------------------------------- fee-schedule versioning (pt3)
def test_fee_schedule_versioned(con):
    # PK is (fee_regime, dataset_version, record_version): a revised fee regime
    # keeps its history — a historical version is never lost.
    db.insert(con, "market_fee_schedule", SAMPLE_ROWS["market_fee_schedule"])
    rev2 = dict(SAMPLE_ROWS["market_fee_schedule"],
                record_version=2, taker_fee=0.0, fee_status="KNOWN")
    db.insert(con, "market_fee_schedule", rev2)  # same fee_regime, new record_version
    rows = db.query(
        con, "SELECT record_version FROM market_fee_schedule ORDER BY record_version")
    assert [r["record_version"] for r in rows] == [1, 2]


# ---------------------------------------------------- price_layer vocabulary (pt5)
def test_price_layer_check_rejects_unknown(con):
    bad = dict(SAMPLE_ROWS["paper_trades"], price_layer="INDICATIVE_MID")  # not allowed
    with pytest.raises(Exception):
        db.insert(con, "paper_trades", bad)


def test_price_layer_check_allows_vocabulary(con):
    for layer in ("INDICATIVE", "SIMULATED_EXECUTABLE", "EXECUTABLE"):
        db.insert(con, "paper_trades", dict(SAMPLE_ROWS["paper_trades"], price_layer=layer))
    assert con.execute("SELECT COUNT(*) FROM paper_trades").fetchone()[0] == 3


# -------------------------------------------- as-of defaults to available_at (pt1)
def test_asof_defaults_to_available_at_for_weather(con):
    assert db.AS_OF_COLUMNS["weather_forecasts"] == "available_at"
    base = SAMPLE_ROWS["weather_forecasts"]
    T = "2026-08-15T12:00:00Z"
    # knowable at T: available_at before T
    db.insert(con, "weather_forecasts",
              dict(base, issue_time="2026-08-15T00:00:00Z", available_at="2026-08-15T00:30:00Z"))
    # NOT knowable at T: available_at after T (even though issued earlier than T)
    db.insert(con, "weather_forecasts",
              dict(base, issue_time="2026-08-15T06:00:00Z", available_at="2026-08-15T18:00:00Z"))
    # time_col omitted -> uses AS_OF_COLUMNS['weather_forecasts'] == 'available_at'
    got = db.query_asof(con, "weather_forecasts", asof=T)
    assert len(got) == 1
    assert got[0]["available_at"] is not None
