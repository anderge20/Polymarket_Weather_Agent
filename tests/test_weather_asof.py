"""
test_weather_asof.py — weather forecast/observation as-of  (PENDING / STUB)
==========================================================================
STATUS: PENDING. Skipped until the weather ingestion + feature join exist
(Phase 2B+). Documents that the 2A schema already supports as-of weather reads.

WHAT IT WILL ASSERT (once 2B+ lands):
  * Selecting "the forecast known as of T" returns only rows with
    available_at <= T, and the LATEST such row per (station, model, target_date)
    — i.e. no later re-issue leaks in. (database.latest_asof; as-of col = available_at.)
  * weather_observations are never read when their available_at is AFTER the
    prediction cutoff (observation_time / daily_high_time = when the weather
    physically occurred, which is NOT the availability time).

SCHEMA SUPPORT ALREADY IN 2A:
  * weather_forecasts: available_at (as-of anchor) vs issue_time (issued) vs
    target_date (valid) vs ingestion_timestamp (when WE ingested)
  * weather_observations: available_at vs observation_time / daily_high_time
  * database.query_asof / database.latest_asof default to AS_OF_COLUMNS (available_at)
"""
from __future__ import annotations

import pytest


@pytest.mark.skip(reason="PENDING 2B+: weather ingestion + join not implemented in 2A")
def test_forecast_asof_returns_only_past_issues():
    """latest_asof(weather_forecasts, 'issue_time', T, partition=[station,model,
    target_date]) must exclude any issue_time > T."""
    raise NotImplementedError("implement with the Phase 2B+ weather ingestion")


@pytest.mark.skip(reason="PENDING 2B+: weather ingestion + join not implemented in 2A")
def test_observation_not_used_before_it_exists():
    """A weather_observation must not feed a prediction whose cutoff precedes the
    observation's availability."""
    raise NotImplementedError("implement with the Phase 2B+ weather ingestion")
