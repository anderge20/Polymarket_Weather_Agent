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

    # The market's contractual unit. Added when B-7 made the unit mandatory:
    # a band cannot be compared against a distribution of unknown scale, so
    # build_feature now refuses instead of silently assuming Celsius.
    con.execute(
        "INSERT INTO markets (market_id, unit, dataset_version, record_version) "
        "VALUES (?, ?, ?, ?)",
        [market_id, "C", dataset_version, 1],
    )

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


def test_feature_builds_weather_probability_from_outcome_band():
    con, dataset_version, market_id, token_id = _setup_db()

    con.execute(
        """
        INSERT INTO outcomes (
            market_id,
            token_id,
            outcome_index,
            band_label,
            lo,
            hi,
            is_winner,
            dataset_version,
            record_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            market_id,
            token_id,
            0,
            "30C",
            30.0,
            30.0,
            None,
            dataset_version,
            1,
        ],
    )

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
    assert row["weather_prob"] is not None
    # 0.2777... was the value under the truncated tails, which declared everything
    # past one degree from p10/p90 impossible and handed that mass to the centre.
    # With tails that carry their own 10 %, the same band holds less. This test is
    # about resolution data never reaching a feature; the exact mass is incidental
    # to it, and is pinned only so a silent change cannot pass.
    assert abs(row["weather_prob"] - 0.2500130636) < 1e-9
    assert row["no_lookahead_verified"] is True

    # Resolution information must still be absent.
    assert "is_winner" not in row
    assert "winning_outcome" not in row
    assert "resolution_timestamp" not in row
    assert "settlement_timestamp" not in row


def test_features_never_cross_dataset_versions():
    """A-37: build_feature accepted dataset_version and never used it.

    Latent while only one version existed. The moment paper mode adds a second,
    the as-of read would mix a backfilled price with a prospective one and raise
    nothing — a feature built from two different worlds.
    """
    con, dsv, market_id, token_id = _setup_db()
    other = "ds_paper_v1"

    # a LATER, cheaper price in the other dataset_version
    con.execute(
        """INSERT INTO price_history (market_id, token_id, observation_time,
               indicative_price, price_semantics, dataset_version)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [market_id, token_id, PREDICTION_TIME.replace(hour=11, minute=59),
         0.99, "INDICATIVE", other],
    )
    con.execute(
        """INSERT INTO outcomes (market_id, token_id, outcome_index, band_label,
               lo, hi, is_winner, dataset_version, record_version)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [market_id, token_id, 0, "30C", 30.0, 30.0, None, dsv, 1],
    )

    row = build_feature(
        con,
        prediction_time=PREDICTION_TIME,
        market_id=market_id,
        token_id=token_id,
        station="NYC",
        model="test-model",
        target_date="2026-08-24",
        dataset_version=dsv,
    )
    assert row is not None
    # the 0.99 from the other dataset_version is nearer in time and must NOT win
    assert row["market_prob"] == 0.42


def test_price_is_never_another_tokens():
    """The price read used to filter by market only and take prices[0].

    With two tokens per market that returns the other side's price under this
    token's name — no exception, no_lookahead_verified still true, and the row
    labelled with the token that did NOT supply the price. A name for a different
    quantity, which is the whole failure class this suite exists to catch.
    """
    con, dsv, market_id, _ = _setup_db()
    for tok, price in (("A", 0.20), ("B", 0.80)):
        con.execute(
            """INSERT INTO price_history (market_id, token_id, observation_time,
                   indicative_price, price_semantics, dataset_version)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [market_id, tok, PREDICTION_TIME.replace(hour=11), price, "INDICATIVE", dsv],
        )
        con.execute(
            """INSERT INTO outcomes (market_id, token_id, outcome_index, band_label,
                   lo, hi, is_winner, dataset_version, record_version)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [market_id, tok, 0, "30C", 30.0, 30.0, None, dsv, 1],
        )
    for tok, expected in (("A", 0.20), ("B", 0.80)):
        row = build_feature(
            con, prediction_time=PREDICTION_TIME, market_id=market_id, token_id=tok,
            station="NYC", model="test-model", target_date="2026-08-24",
            dataset_version=dsv,
        )
        assert row is not None and row["market_prob"] == expected, (
            f"token {tok} got {row and row['market_prob']}, expected {expected}"
        )
