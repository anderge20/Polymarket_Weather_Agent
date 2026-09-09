"""
test_error_model.py — M2 rules, exactly as preregistered
=========================================================
Every assertion here corresponds to a numbered rule in PREREG_M2_ERROR.md. A
test that drifts from the preregistration is worse than no test: it makes a
changed rule look sanctioned.
"""
from __future__ import annotations

from datetime import date

import pytest

from weather_agent import error_model as em


def _pairs(n, station="EFHK", lead=24, start_day=1, errs=None):
    out = []
    for i in range(n):
        e = errs[i] if errs else (i % 7) - 3.0
        out.append(
            em.Pair(
                station=station,
                target_date=date(2026, 5, 1 + (i % 28)),
                lead_h=lead,
                forecast_c=20.0,
                observed_c=20.0 + e,
            )
        )
    return out


# --- §2: the error and its sign -------------------------------------------


def test_error_sign_is_reality_minus_forecast():
    p = em.Pair("EFHK", date(2026, 5, 1), 24, forecast_c=20.0, observed_c=23.0)
    assert p.error_c == 3.0  # reality beat the forecast -> positive


# --- §7: empirical percentiles, linear ------------------------------------


def test_percentile_is_linear_interpolation():
    v = [0.0, 1.0, 2.0, 3.0, 4.0]
    assert em.percentile(v, 50) == 2.0
    assert em.percentile(v, 10) == pytest.approx(0.4)
    assert em.percentile(v, 90) == pytest.approx(3.6)


def test_quantiles_are_added_to_the_forecast():
    q = em.Quantiles(em.SCOPE_POOLED, 40, {10: -2.0, 25: -1.0, 50: 0.0, 75: 1.0, 90: 2.0})
    got = em.forecast_quantiles_c(18.0, q)
    assert got == {10: 16.0, 25: 17.0, 50: 18.0, 75: 19.0, 90: 20.0}


# --- §8: sufficiency ------------------------------------------------------


def test_below_min_n_emits_nothing():
    """Without a characterised error there is no honest probability."""
    q = em.fit([0.1] * (em.MIN_N - 1), em.SCOPE_POOLED)
    assert q.scope == em.SCOPE_INSUFFICIENT
    assert q.values == {}


def test_degenerate_sample_is_rejected_not_reported_as_certainty():
    """Zero spread means a degenerate sample, not a perfectly known future."""
    q = em.fit([2.0] * 40, em.SCOPE_POOLED)
    assert q.scope == em.SCOPE_REJECTED


def test_absurd_spread_is_rejected():
    q = em.fit([-40.0] * 20 + [40.0] * 20, em.SCOPE_POOLED)
    assert q.scope == em.SCOPE_REJECTED


def test_applying_a_rejected_stratum_raises():
    q = em.fit([2.0] * 40, em.SCOPE_POOLED)
    with pytest.raises(ValueError):
        em.forecast_quantiles_c(18.0, q)


# --- §5: walk-forward -----------------------------------------------------


def test_training_uses_only_strictly_earlier_dates():
    ps = [
        em.Pair("EFHK", date(2026, 5, 1), 24, 20.0, 21.0),
        em.Pair("EFHK", date(2026, 5, 2), 24, 20.0, 22.0),
        em.Pair("EFHK", date(2026, 5, 3), 24, 20.0, 23.0),
    ]
    got = em.training_pairs(ps, date(2026, 5, 2), 24)
    assert [p.target_date for p in got] == [date(2026, 5, 1)]


def test_leads_are_never_mixed():
    ps = _pairs(40, lead=9) + _pairs(40, lead=24)
    got = em.training_pairs(ps, date(2026, 12, 1), 9)
    assert {p.lead_h for p in got} == {9}


# --- §4: stratification ---------------------------------------------------


def test_station_stratum_used_only_with_enough_history():
    thin = _pairs(em.MIN_STATION_N - 1, station="EFHK")
    other = _pairs(60, station="KDAL")
    q = em.quantiles_for(thin + other, "EFHK", date(2026, 12, 1), 24)
    assert q.scope == em.SCOPE_POOLED

    thick = _pairs(60, station="EFHK")
    q2 = em.quantiles_for(thick + other, "EFHK", date(2026, 12, 1), 24)
    assert q2.scope == em.SCOPE_STATION


# --- §3 / B-7: units ------------------------------------------------------


def test_level_and_delta_conversions_are_different_functions():
    """Applying the level formula to a difference adds a spurious 32 degrees,
    and the result still looks like a temperature."""
    assert em.c_to_f_level(0.0) == 32.0
    assert em.c_to_f_delta(0.0) == 0.0
    assert em.c_to_f_level(5.0) == 41.0
    assert em.c_to_f_delta(5.0) == 9.0


def test_quantiles_converted_to_market_unit():
    q_c = {10: 0.0, 25: 5.0, 50: 10.0, 75: 15.0, 90: 20.0}
    assert em.to_market_unit(q_c, "C") == q_c
    assert em.to_market_unit(q_c, "F") == {10: 32.0, 25: 41.0, 50: 50.0, 75: 59.0, 90: 68.0}


def test_unknown_unit_refuses_rather_than_guessing():
    with pytest.raises(ValueError, match="neither C nor F"):
        em.to_market_unit({10: 1.0}, "K")
    with pytest.raises(ValueError):
        em.to_market_unit({10: 1.0}, None)


def test_the_nyc_failure_case_is_now_impossible():
    """B-6's concrete case: a '27F or below' band against a Celsius distribution.

    27 F is -2.8 C. Read as Celsius the band is nearly certain; read correctly it
    is almost impossible. The conversion must move the DISTRIBUTION into the
    market's unit, leaving the band untouched.
    """
    # a December NYC forecast: 0 C, error quantiles around it
    q_c = {10: -3.0, 25: -1.5, 50: 0.0, 75: 1.5, 90: 3.0}
    in_f = em.to_market_unit(q_c, "F")

    # On the market's own scale the median high is 32 F and the 27 F threshold
    # sits below the 10th percentile: the band is unlikely, a few per cent.
    assert in_f[50] == 32.0
    assert in_f[10] < 27.0 < in_f[25]

    # The bug this guards against: reading the SAME band against the Celsius
    # distribution asks "is the high <= 27 C?", which the 90th percentile already
    # satisfies — a near-certainty where the truth is a low-tail event. Same
    # number, opposite conclusion, no error raised.
    assert q_c[90] < 27.0
