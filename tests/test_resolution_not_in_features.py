"""
test_resolution_not_in_features.py — resolution never leaks into features (PENDING / STUB)
=========================================================================================
STATUS: PENDING. Skipped until the feature builder exists (Phase 2B+).
Documents that resolution/settlement facts must never be inputs to features.

WHAT IT WILL ASSERT (once 2B+ lands):
  * No feature derived from a market's resolution appears in `features`:
      - markets.winning_outcome / resolution_timestamp / settlement_timestamp
        must NOT be used to build any features row.
      - outcomes.is_winner must NOT be used as a feature input.
  * The resolved outcome is used ONLY as the training LABEL (a separate step),
    never as a predictor — and only for rows whose prediction_time precedes the
    resolution.

SCHEMA SUPPORT ALREADY IN 2A:
  * Resolution/settlement live on `markets` (resolution_timestamp,
    settlement_timestamp, winning_outcome) and `outcomes.is_winner`, cleanly
    SEPARATED from the `features` table; join-time as-of guards keep them out of
    the predictor set.
"""
from __future__ import annotations

import pytest


@pytest.mark.skip(reason="PENDING 2B+: feature builder not implemented in 2A")
def test_resolution_fields_absent_from_feature_inputs():
    """No resolution/settlement/is_winner field may be present in the predictor
    set used to compute a features row."""
    raise NotImplementedError("implement with the Phase 2B+ feature builder")


@pytest.mark.skip(reason="PENDING 2B+: feature builder + labeler not implemented in 2A")
def test_resolved_outcome_used_only_as_label():
    """The resolved outcome may be used as a label only, for rows whose
    prediction_time precedes the resolution_timestamp."""
    raise NotImplementedError("implement with the Phase 2B+ labeler")
