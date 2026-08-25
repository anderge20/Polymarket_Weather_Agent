"""
Phase 2C Blocker 2 — resolution must never leak into features.

These tests verify:
1. build_feature() constructs a predictor-only row and does not expose
   resolution/settlement/is_winner fields.
2. Resolution is represented separately as a training label, and only when
   prediction_time is strictly before resolution_timestamp.
"""

from datetime import datetime, timezone

import duckdb

from weather_agent import database as db
from weather_agent.features import build_feature
from weather_agent.labeling import build_label


PREDICTION_TIME = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)


def _setup_db():
    con = duckdb.connect(":memory:")
    db.init_db(con)

    dataset_version = "test_resolution_no_leak"
    market_id = "m1"
    token_id = "t1"

    con.execute(
        """
        INSERT INTO price_history (
            market_id, token_id, observation_time,
            indicative_price, price_semantics, dataset_version
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            market_id,
            token_id,
            PREDICTION_TIME.replace(hour=11),
            0.42,
            "INDICATIVE",
            dataset_version,
        ],
    )

    con.execute(
        """
        INSERT INTO weather_forecasts (
            station, model, target_date,
            available_at, issue_time,
            forecast_tmax, forecast_p10, forecast_p25,
            forecast_p50, forecast_p75, forecast_p90,
            dataset_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "NYC",
            "test-model",
            "2026-08-24",
            PREDICTION_TIME.replace(hour=10),
            PREDICTION_TIME.replace(hour=9),
            30.0,
            28.0,
            29.0,
            30.0,
            31.0,
            32.0,
            dataset_version,
        ],
    )

    return con, dataset_version, market_id, token_id


def test_resolution_fields_absent_from_feature_row():
    con, dataset_version, market_id, token_id = _setup_db()

    row = build_feature(
        con,
        prediction_time=PREDICTION_TIME,
        market_id=market_id,
        token_id=token_id,
        station="NYC",
        model="test-model",
        target_date="2026-08-24",
        dataset_version=dataset_version,
    )

    assert row is not None

    forbidden = {
        "winning_outcome",
        "resolution_timestamp",
        "settlement_timestamp",
        "is_winner",
    }

    assert forbidden.isdisjoint(row.keys())
    assert forbidden.isdisjoint(row["feature_json"].keys())

    # The builder must explicitly mark the row as no-look-ahead safe.
    assert row["no_lookahead_verified"] is True


def test_resolved_outcome_used_only_as_label():
    resolution_timestamp = datetime(
        2026, 8, 23, 18, 0, tzinfo=timezone.utc
    )

    label = build_label(
        prediction_time=PREDICTION_TIME,
        resolution_timestamp=resolution_timestamp,
        winning_outcome="Yes",
    )

    assert label is not None
    assert label["label"] == "Yes"

    # Settlement data exists in the label, not in the feature row.
    assert label["resolution_timestamp"] == resolution_timestamp

    # The feature builder itself has no resolution fields.
    con, dataset_version, market_id, token_id = _setup_db()

    row = build_feature(
        con,
        prediction_time=PREDICTION_TIME,
        market_id=market_id,
        token_id=token_id,
        station="NYC",
        model="test-model",
        target_date="2026-08-24",
        dataset_version=dataset_version,
    )

    assert row is not None
    assert "label" not in row
    assert "resolution_timestamp" not in row
    assert "winning_outcome" not in row


def test_resolution_cannot_be_used_when_prediction_is_after_resolution():
    resolution_timestamp = datetime(
        2026, 8, 23, 10, 0, tzinfo=timezone.utc
    )

    label = build_label(
        prediction_time=PREDICTION_TIME,
        resolution_timestamp=resolution_timestamp,
        winning_outcome="Yes",
    )

    assert label is None
