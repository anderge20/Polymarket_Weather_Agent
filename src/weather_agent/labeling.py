"""
Label builder — Phase 2C Blocker 2.

Resolution/settlement facts are labels only. They are never predictor
features.

A resolved market can provide a training label for a prediction row only
when:

    prediction_time < resolution_timestamp

The label is therefore strictly separated from build_feature().
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    raise TypeError(f"unsupported timestamp type: {type(value)!r}")


def build_label(
    *,
    prediction_time: Any,
    resolution_timestamp: Any,
    winning_outcome: str | None,
) -> dict | None:
    """
    Build a historical training label from final resolution.

    Returns None when:
      - the market is unresolved;
      - the resolution timestamp is missing;
      - prediction_time is not strictly before resolution.

    Resolution data is deliberately not part of the feature row.
    """

    if not winning_outcome or resolution_timestamp is None:
        return None

    prediction_time = _as_datetime(prediction_time)
    resolution_timestamp = _as_datetime(resolution_timestamp)

    # A prediction made at or after resolution cannot use that settlement
    # as a future label for an as-of prediction.
    if prediction_time >= resolution_timestamp:
        return None

    return {
        "label": str(winning_outcome),
        "prediction_time": prediction_time,
        "resolution_timestamp": resolution_timestamp,
    }
