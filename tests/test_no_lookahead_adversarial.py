"""
Phase 2C Blocker 2 — adversarial no-look-ahead tests.
"""

from __future__ import annotations

import pytest

from weather_agent import database as db
from weather_agent.features import build_feature


T = "2026-08-15T12:00:00Z"
DSV = "ds_adversarial"


def _price(con):
    db.insert(con, "price_history", {
        "observation_time": "2026-08-15T11:00:00Z",
        "market_id": "m1",
        "token_id": "tok1",
        "indicative_price": 0.40,
        "price_semantics": "MIDPOINT_ESTIMATED",
        "source_window": "DIRECT",
        "fidelity": 1,
        "dataset_version": DSV,
        "record_version": 1,
    })


def _forecast(
    con,
    *,
    issue_time="2026-08-15T00:00:00Z",
    available_at="2026-08-15T13:00:00Z",
):
    db.insert(con, "weather_forecasts", {
        "issue_time": issue_time,
        "forecast_run": "00z",
        "target_date": "2026-08-16",
        "city": "London",
        "station": "EGLC",
        "model": "ecmwf_ifs025",
        "forecast_tmax": 26.0,
        "forecast_p10": 24.0,
        "forecast_p25": 25.0,
        "forecast_p50": 26.0,
        "forecast_p75": 27.0,
        "forecast_p90": 28.0,
        "available_at": available_at,
        "dataset_version": DSV,
        "record_version": 1,
    })


def test_forecast_issued_before_T_but_available_after_T_is_excluded(con):
    """
    Adversarial #1:
    issue_time < T but available_at > T must NOT be usable.
    """
    _price(con)

    _forecast(
        con,
        issue_time="2026-08-15T00:00:00Z",
        available_at="2026-08-15T13:00:00Z",
    )

    row = build_feature(
        con,
        prediction_time=T,
        market_id="m1",
        token_id="tok1",
        station="EGLC",
        model="ecmwf_ifs025",
        target_date="2026-08-16",
        dataset_version=DSV,
    )

    assert row is None


def test_observation_occurred_before_T_but_available_after_T_is_excluded(con):
    """
    Adversarial #2:
    physical occurrence before T does not make the observation knowable.
    """
    _price(con)

    # Forecast is available and therefore valid.
    _forecast(
        con,
        issue_time="2026-08-15T00:00:00Z",
        available_at="2026-08-15T01:00:00Z",
    )

    # Observation physically occurred before T, but source availability
    # is after T.
    db.insert(con, "weather_observations", {
        "observation_time": "2026-08-15T10:00:00Z",
        "city": "London",
        "station": "EGLC",
        "source": "wunderground",
        "tmax_observed": 26.0,
        "daily_high_time": "2026-08-15T10:00:00Z",
        "available_at": "2026-08-15T13:00:00Z",
        "dataset_version": DSV,
        "record_version": 1,
    })

    # The builder currently does not use realized observations as a
    # predictor, so this must still build successfully.
    row = build_feature(
        con,
        prediction_time=T,
        market_id="m1",
        token_id="tok1",
        station="EGLC",
        model="ecmwf_ifs025",
        target_date="2026-08-16",
        dataset_version=DSV,
    )

    assert row is not None

    observations = db.query_asof(
        con,
        "weather_observations",
        asof=T,
    )

    assert observations == []


def test_resolution_before_T_is_forbidden_as_pre_resolution_feature(con):
    """
    Adversarial #3:
    resolution data must never enter predictor features.
    """
    _price(con)

    _forecast(
        con,
        issue_time="2026-08-15T00:00:00Z",
        available_at="2026-08-15T01:00:00Z",
    )

    db.insert(con, "markets", {
        "market_id": "m1",
        "event_id": "event1",
        "question": "Will London max temperature be 26°C?",
        "city": "London",
        "resolution_timestamp": "2026-08-15T10:00:00Z",
        "settlement_timestamp": "2026-08-15T10:01:00Z",
        "winning_outcome": "Yes",
        "dataset_version": DSV,
        "record_version": 1,
    })

    row = build_feature(
        con,
        prediction_time=T,
        market_id="m1",
        token_id="tok1",
        station="EGLC",
        model="ecmwf_ifs025",
        target_date="2026-08-16",
        dataset_version=DSV,
    )

    assert row is not None

    forbidden = {
        "winning_outcome",
        "resolution_timestamp",
        "settlement_timestamp",
        "is_winner",
    }

    assert forbidden.isdisjoint(row)
    assert forbidden.isdisjoint(row.get("feature_json", {}))
