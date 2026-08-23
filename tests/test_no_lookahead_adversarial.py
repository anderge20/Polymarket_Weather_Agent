"""
test_no_lookahead_adversarial.py — the 3 adversarial no-look-ahead specs (PENDING)
=================================================================================
STATUS: PENDING — SPECS ONLY (criterion #2b). These belong to the FEATURE-BUILDER
subphase (a later phase), NOT to 2B. 2B is discovery only and builds no features,
so these are written as documented, SKIPPED specs and must be implemented when the
feature builder exists. The REAL no-look-ahead validation (the 6 checks that gate
`features.no_lookahead_verified=TRUE`, never a manual TRUE) is implemented THEN.

The 2A runnable semantic test (test_no_future_information.py ::
test_no_lookahead_semantics_on_sample_data) already demonstrates the schema
supports these queries via `available_at` + AS_OF_COLUMNS; these three tests are
the ADVERSARIAL cases the builder must survive.
"""
from __future__ import annotations

import pytest


@pytest.mark.skip(reason="PENDING feature-builder subphase (post-2B): forecast available_at guard")
def test_forecast_issued_before_T_but_available_after_T_is_excluded():
    """ADVERSARIAL #1. A forecast with issue_time < T but available_at > T must be
    EXCLUDED from features whose prediction_time == T. I.e. being *issued* early
    does not make it knowable early; only `available_at <= T` counts. The builder
    must select forecasts via latest_asof(weather_forecasts, 'available_at', T) and
    MUST NOT fall back to issue_time/ingestion_timestamp."""
    raise NotImplementedError("implement in the feature-builder subphase")


@pytest.mark.skip(reason="PENDING feature-builder subphase (post-2B): observation available_at guard")
def test_observation_occurred_before_T_but_available_after_T_is_excluded():
    """ADVERSARIAL #2. A weather_observation whose observation_time/daily_high_time
    < T but whose available_at > T must be EXCLUDED from features at prediction_time
    T. The physical occurrence time is NOT the availability time; the builder must
    filter observations by `available_at <= T`."""
    raise NotImplementedError("implement in the feature-builder subphase")


@pytest.mark.skip(reason="PENDING feature-builder subphase (post-2B): resolution-leak guard")
def test_resolution_before_T_is_forbidden_as_pre_resolution_feature():
    """ADVERSARIAL #3. Even if a market's resolution_timestamp < T, the resolved
    outcome (markets.winning_outcome / outcomes.is_winner / settlement) must NEVER
    enter the predictor set for a PRE-RESOLUTION prediction. Resolution is a LABEL,
    used only for scoring rows whose prediction_time precedes the resolution — never
    a feature. The builder must assert resolution fields are absent from features."""
    raise NotImplementedError("implement in the feature-builder subphase")
