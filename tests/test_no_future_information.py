"""
test_no_future_information.py — §72 no-look-ahead guard
=======================================================
STATUS: partly RUNNABLE (semantic check on sample data), partly PENDING (the real
feature builder is 2B+). Authored without Python execution — not run here.

`features.no_lookahead_verified` is a RESULT, never a source of truth: it is set
TRUE *only* by the feature builder after it runs the as-of checks below. A manual
TRUE is not authoritative. The runnable test here validates the SEMANTICS those
checks must enforce, using hand-built sample data; the behavioural tests that need
the real builder stay skipped (2B+).

INVARIANTS a TRUE `no_lookahead_verified` must satisfy (as-of engine filters on the
canonical AS_OF_COLUMNS — for weather that is `available_at`, NEVER
`ingestion_timestamp`, NEVER the physical `observation_time`/`daily_high_time`):
  * every market input used has its as-of time <= prediction_time
  * the forecast used has available_at <= prediction_time
  * NO observation with available_at > prediction_time is used
  * NO market resolution/settlement field is present in `features`
"""
from __future__ import annotations

import pytest


# ------------------------------------------------------- RUNNABLE semantic check
def test_no_lookahead_semantics_on_sample_data(con):
    """Build a consistent as-of scenario and assert the invariants a TRUE
    no_lookahead_verified must hold. This validates the SEMANTICS; the flag itself
    is set by the 2B+ feature builder, not by hand."""
    from weather_agent import database as db

    T = "2026-08-15T12:00:00Z"
    dsv = "ds_test"

    # market price knowable before T
    db.insert(con, "price_history", {
        "observation_time": "2026-08-15T11:00:00Z", "market_id": "m1",
        "token_id": "tok", "indicative_price": 0.40,
        "price_semantics": "MIDPOINT_ESTIMATED", "source_window": "DIRECT",
        "fidelity": 1, "dataset_version": dsv, "record_version": 1})

    # forecast AVAILABLE before T
    db.insert(con, "weather_forecasts", {
        "issue_time": "2026-08-15T00:00:00Z", "target_date": "2026-08-16",
        "station": "EGLC", "model": "ecmwf_ifs025", "forecast_tmax": 26.0,
        "available_at": "2026-08-15T00:30:00Z", "dataset_version": dsv,
        "record_version": 1})

    # realized observation only AVAILABLE after T (must NOT be usable at T)
    db.insert(con, "weather_observations", {
        "observation_time": "2026-08-16T00:00:00Z", "station": "EGLC",
        "source": "wunderground", "tmax_observed": 26.0,
        "available_at": "2026-08-16T06:00:00Z", "dataset_version": dsv,
        "record_version": 1})

    # the features row a builder would emit (flag is the RESULT of the checks below)
    db.insert(con, "features", {
        "prediction_time": T, "market_id": "m1", "token_id": "tok",
        "market_prob": 0.40, "weather_prob": 0.45, "no_lookahead_verified": True,
        "dataset_version": dsv, "record_version": 1})

    # (1) market input is at/before T
    price = db.latest_asof(con, "price_history", asof=T, partition_cols=["token_id"])
    assert len(price) == 1

    # (2) forecast used is AVAILABLE at/before T (as-of defaults to available_at)
    fc = db.latest_asof(con, "weather_forecasts", asof=T,
                        partition_cols=["station", "model", "target_date"])
    assert len(fc) == 1

    # (3) the realized observation is NOT knowable at T (available_at > T)
    obs = db.query_asof(con, "weather_observations", asof=T)
    assert obs == []

    # (4) resolution/settlement fields never live in `features`
    fcols = set(db.column_names(con, "features"))
    assert fcols.isdisjoint(
        {"winning_outcome", "resolution_timestamp", "settlement_timestamp", "is_winner"})


# ------------------------------------------------------ PENDING (needs 2B+ builder)
@pytest.mark.skip(reason="PENDING 2B+: real feature builder must set the flag from as-of checks")
def test_builder_sets_flag_only_after_asof_checks():
    """The feature builder sets no_lookahead_verified=TRUE only after it verifies
    every input's as-of time <= prediction_time. Never a manual flag."""
    raise NotImplementedError("implement with the Phase 2B+ feature builder")


@pytest.mark.skip(reason="PENDING 2B+: feature builder + labeler not implemented in 2A")
def test_features_use_no_future_price_or_forecast():
    """For every features row, all price_history used has observation_time <=
    prediction_time and the forecast used has available_at <= prediction_time."""
    raise NotImplementedError("implement with the Phase 2B+ feature builder")
