"""
Feature builder — Phase 2C Blocker 2.

The only purpose of this module at this stage is to construct an
as-of-safe feature row. Resolution/settlement data is NEVER a feature.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from weather_agent import database as db
from weather_agent.probability import (
    band_probability,
    quantiles_to_distribution,
)


# Fields which are labels / settlement facts and therefore forbidden
# from entering the predictor set.
FORBIDDEN_FEATURE_FIELDS = {
    "winning_outcome",
    "resolution_timestamp",
    "settlement_timestamp",
    "is_winner",
}


def build_feature(
    con,
    *,
    prediction_time: Any,
    market_id: str,
    token_id: str,
    station: str,
    model: str,
    target_date: Any,
    dataset_version: str,
) -> dict | None:
    """
    Build one feature row using only information knowable at prediction_time.

    Price:
        latest price_history observation_time <= prediction_time.

    Forecast:
        latest weather_forecasts available_at <= prediction_time.

    Weather probability:
        probability mass of this token's temperature band under the
        forecast-derived discrete temperature distribution.

    Observation:
        intentionally NOT used as a predictor at this stage.

    Resolution:
        intentionally NOT read.

    Returns None when a required as-of input is unavailable.
    """

    # Normalize the cutoff once so DuckDB TIMESTAMPTZ values
    # can be compared safely with the caller-provided ISO timestamp.
    if isinstance(prediction_time, str):
        prediction_time = datetime.fromisoformat(
            prediction_time.replace("Z", "+00:00")
        )

    # ------------------------------------------------------------------
    # 1. MARKET PRICE — market-time as-of
    # ------------------------------------------------------------------

    prices = db.latest_asof(
        con,
        "price_history",
        time_col="observation_time",
        asof=prediction_time,
        partition_cols=["token_id"],
        where="market_id = ?",
        params=[market_id],
    )

    if not prices:
        return None

    price = prices[0]

    # Defensive invariant: never allow an executable price semantics.
    if price.get("price_semantics") == "EXECUTABLE":
        raise ValueError("EXECUTABLE price cannot enter features")

    # ------------------------------------------------------------------
    # 2. WEATHER FORECAST — SOURCE AVAILABILITY as-of
    # ------------------------------------------------------------------

    forecasts = db.latest_asof(
        con,
        "weather_forecasts",
        time_col="available_at",
        asof=prediction_time,
        partition_cols=["station", "model", "target_date"],
        where="station = ? AND model = ? AND target_date = ?",
        params=[station, model, target_date],
    )

    if not forecasts:
        return None

    forecast = forecasts[0]

    # ------------------------------------------------------------------
    # 3. OUTCOME BAND — predictor metadata only
    #
    # IMPORTANT:
    #   We read lo/hi for the requested token, but NEVER read is_winner.
    #   Resolution remains strictly a training label.
    # ------------------------------------------------------------------

    outcomes = db.query(
        con,
        """
        SELECT token_id, band_label, lo, hi
        FROM outcomes
        WHERE market_id = ?
          AND token_id = ?
          AND dataset_version = ?
        ORDER BY record_version DESC
        LIMIT 1
        """,
        [market_id, token_id, dataset_version],
    )

    outcome = outcomes[0] if outcomes else None

    # ------------------------------------------------------------------
    # 4. FORECAST QUANTILES → TEMPERATURE DISTRIBUTION → BAND PROBABILITY
    # ------------------------------------------------------------------

    distribution = None
    weather_prob = None

    if outcome is not None:
        distribution = quantiles_to_distribution(
            p10=forecast.get("forecast_p10"),
            p25=forecast.get("forecast_p25"),
            p50=forecast.get("forecast_p50"),
            p75=forecast.get("forecast_p75"),
            p90=forecast.get("forecast_p90"),
        )

        weather_prob = band_probability(
            distribution,
            lo=outcome.get("lo"),
            hi=outcome.get("hi"),
        )

    # ------------------------------------------------------------------
    # 5. Build predictor-only row.
    #
    # IMPORTANT:
    #   Do NOT copy the market row.
    #   Do NOT copy outcomes wholesale.
    #   Do NOT copy resolution fields.
    # ------------------------------------------------------------------

    row = {
        "prediction_time": prediction_time,
        "market_id": market_id,
        "token_id": token_id,
        "market_prob": price["indicative_price"],
        "weather_prob": weather_prob,
        "forecast_tmax": forecast.get("forecast_tmax"),
        "forecast_p10": forecast.get("forecast_p10"),
        "forecast_p25": forecast.get("forecast_p25"),
        "forecast_p50": forecast.get("forecast_p50"),
        "forecast_p75": forecast.get("forecast_p75"),
        "forecast_p90": forecast.get("forecast_p90"),
        "feature_json": {
            "price_observation_time": str(price["observation_time"]),
            "forecast_available_at": str(forecast["available_at"]),
            "forecast_issue_time": str(forecast["issue_time"]),
            "outcome_band_label": outcome.get("band_label") if outcome else None,
            "outcome_lo": outcome.get("lo") if outcome else None,
            "outcome_hi": outcome.get("hi") if outcome else None,
            "weather_distribution": distribution,
        },
        "no_lookahead_verified": False,
        "source": "AS_OF_BUILDER",
        "source_timestamp": prediction_time,
        "dataset_version": dataset_version,
        "record_version": 1,
    }

    # ------------------------------------------------------------------
    # 6. FINAL NO-LOOKAHEAD GUARD
    # ------------------------------------------------------------------

    if price["observation_time"] > prediction_time:
        raise AssertionError("price input is after prediction_time")

    if forecast["available_at"] > prediction_time:
        raise AssertionError("forecast input is after prediction_time")

    # The feature row itself must not contain settlement facts.
    if FORBIDDEN_FEATURE_FIELDS.intersection(row):
        raise AssertionError("resolution field leaked into features")

    if FORBIDDEN_FEATURE_FIELDS.intersection(row["feature_json"]):
        raise AssertionError("resolution field leaked into feature_json")

    if weather_prob is not None and not 0.0 <= weather_prob <= 1.0:
        raise AssertionError("weather_prob must be between 0 and 1")

    row["no_lookahead_verified"] = True

    return row
