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


from datetime import datetime, timedelta, timezone


def _avail(d):
    """Label availability under v2 §3, for a UTC station: end of day + 24 h."""
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc) + timedelta(hours=48)


def _pairs(n, station="EFHK", lead=24, errs=None):
    out = []
    for i in range(n):
        e = errs[i] if errs else (i % 7) - 3.0
        d = date(2026, 5, 1 + (i % 28))
        out.append(
            em.Pair(
                station=station,
                target_date=d,
                lead_h=lead,
                forecast_c=20.0,
                observed_c=20.0 + e,
                label_available_at=_avail(d),
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


def test_training_uses_only_labels_already_available():
    """v2 §3. Filtering on `target_date < D` instead leaked in 8/8 stations at
    both leads, by -9 h to -43 h: the previous day's label is still in the future
    at a 24 h-lead decision."""
    ps = [
        em.Pair("EFHK", date(2026, 5, d), 24, 20.0, 21.0, _avail(date(2026, 5, d)))
        for d in (1, 2, 3)
    ]
    # The 1st's label lands on the 3rd at 00:00Z (end of day + 24 h); the 2nd's on
    # the 4th. Half way through the 3rd, only the first is usable.
    t = datetime(2026, 5, 3, 12, tzinfo=timezone.utc)
    assert [p.target_date for p in em.training_pairs(ps, t, 24)] == [date(2026, 5, 1)]

    # exactly at its availability instant it counts: the filter is <=
    assert [p.target_date for p in em.training_pairs(
        ps, datetime(2026, 5, 3, 0, tzinfo=timezone.utc), 24)] == [date(2026, 5, 1)]

    # and one day later the second becomes usable too
    assert [p.target_date for p in em.training_pairs(
        ps, datetime(2026, 5, 4, 0, tzinfo=timezone.utc), 24)] == [
        date(2026, 5, 1), date(2026, 5, 2)]


def test_a_pair_without_known_availability_is_never_used():
    ps = [em.Pair("EFHK", date(2026, 5, 1), 24, 20.0, 21.0, None)]
    assert em.training_pairs(ps, datetime(2027, 1, 1, tzinfo=timezone.utc), 24) == []


def test_leads_are_never_mixed():
    ps = _pairs(40, lead=9) + _pairs(40, lead=24)
    got = em.training_pairs(ps, datetime(2026, 12, 1, tzinfo=timezone.utc), 9)
    assert {p.lead_h for p in got} == {9}


# --- §4: stratification ---------------------------------------------------


def test_stratum_is_always_pooled_by_lead():
    """v2 §4 removed the per-station stratum: n >= 30 held in 4 of 98 groups, so
    it bought no coverage and added uncontrolled heterogeneity."""
    ps = _pairs(60, station="EFHK") + _pairs(60, station="KDAL")
    q = em.quantiles_for(ps, datetime(2026, 12, 1, tzinfo=timezone.utc), 24)
    assert q.scope == em.SCOPE_POOLED


def test_calibration_is_the_falsifiable_criterion():
    """v2 §5.1: a declared 80 % interval that covers half the outcomes fails."""
    q = em.Quantiles(em.SCOPE_POOLED, 100, {10: -2.0, 25: -1.0, 50: 0.0, 75: 1.0, 90: 2.0})
    good = _pairs(100, errs=[(-3.0 if i < 10 else (3.0 if i >= 90 else 0.0)) for i in range(100)])
    assert em.calibration(good, q)["passes"] is True

    # a distribution far too narrow for the outcomes: most fall outside p10..p90
    bad = _pairs(100, errs=[(-5.0 if i % 2 else 5.0) for i in range(100)])
    assert em.calibration(bad, q)["passes"] is False


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
