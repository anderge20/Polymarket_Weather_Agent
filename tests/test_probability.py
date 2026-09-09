from __future__ import annotations

import math

import pytest

from weather_agent.probability import (
    quantiles_to_distribution,
    band_probability,
)


def test_quantiles_to_distribution_basic():
    distribution = quantiles_to_distribution(
        p10=24.0,
        p25=25.0,
        p50=26.0,
        p75=27.0,
        p90=28.0,
    )

    assert distribution
    assert math.isclose(sum(distribution.values()), 1.0, abs_tol=1e-9)


def test_distribution_contains_integer_temperatures():
    distribution = quantiles_to_distribution(
        p10=24.0,
        p25=25.0,
        p50=26.0,
        p75=27.0,
        p90=28.0,
    )

    assert all(float(t).is_integer() for t in distribution)


def test_distribution_probabilities_are_non_negative():
    distribution = quantiles_to_distribution(
        p10=24.0,
        p25=25.0,
        p50=26.0,
        p75=27.0,
        p90=28.0,
    )

    assert all(p >= 0.0 for p in distribution.values())


def test_invalid_quantile_order_raises():
    with pytest.raises(ValueError):
        quantiles_to_distribution(
            p10=26.0,
            p25=25.0,
            p50=27.0,
            p75=28.0,
            p90=29.0,
        )


def test_missing_quantile_raises():
    with pytest.raises(ValueError):
        quantiles_to_distribution(
            p10=None,
            p25=25.0,
            p50=26.0,
            p75=27.0,
            p90=28.0,
        )


def test_nan_quantile_raises():
    with pytest.raises(ValueError):
        quantiles_to_distribution(
            p10=24.0,
            p25=25.0,
            p50=float("nan"),
            p75=27.0,
            p90=28.0,
        )


def test_band_probability_closed_interval():
    distribution = {
        24: 0.10,
        25: 0.20,
        26: 0.40,
        27: 0.20,
        28: 0.10,
    }

    p = band_probability(
        distribution,
        lo=26.0,
        hi=27.0,
    )

    assert math.isclose(p, 0.60, abs_tol=1e-9)


def test_band_probability_lower_open():
    distribution = {
        24: 0.10,
        25: 0.20,
        26: 0.40,
        27: 0.20,
        28: 0.10,
    }

    p = band_probability(
        distribution,
        lo=None,
        hi=25.0,
    )

    assert math.isclose(p, 0.30, abs_tol=1e-9)


def test_band_probability_upper_open():
    distribution = {
        24: 0.10,
        25: 0.20,
        26: 0.40,
        27: 0.20,
        28: 0.10,
    }

    p = band_probability(
        distribution,
        lo=27.0,
        hi=None,
    )

    assert math.isclose(p, 0.30, abs_tol=1e-9)


def test_full_partition_sums_to_one():
    distribution = {
        24: 0.10,
        25: 0.20,
        26: 0.40,
        27: 0.20,
        28: 0.10,
    }

    bands = [
        (None, 24.0),
        (25.0, 25.0),
        (26.0, 26.0),
        (27.0, 27.0),
        (28.0, None),
    ]

    probabilities = [
        band_probability(distribution, lo=lo, hi=hi)
        for lo, hi in bands
    ]

    assert math.isclose(sum(probabilities), 1.0, abs_tol=1e-9)


def _cdf(distribution, x):
    """CDF of the discrete temperature distribution at x."""
    return sum(
        probability
        for temperature, probability in distribution.items()
        if temperature <= x
    )


def test_reconstructed_distribution_has_reasonable_median():
    distribution = quantiles_to_distribution(
        p10=24.0,
        p25=25.0,
        p50=26.0,
        p75=27.0,
        p90=28.0,
    )

    # The input P50 is 26°C. For this discrete distribution,
    # the median must remain at 26°C.
    assert _cdf(distribution, 25) < 0.50
    assert _cdf(distribution, 26) >= 0.50


def test_reconstructed_distribution_preserves_quantile_order():
    distribution = quantiles_to_distribution(
        p10=20.0,
        p25=22.0,
        p50=25.0,
        p75=27.0,
        p90=30.0,
    )

    # Quantiles recovered from the resulting discrete distribution
    # must remain ordered.
    assert _cdf(distribution, 20) >= 0.0
    assert _cdf(distribution, 22) >= _cdf(distribution, 20)
    assert _cdf(distribution, 25) >= _cdf(distribution, 22)
    assert _cdf(distribution, 27) >= _cdf(distribution, 25)
    assert _cdf(distribution, 30) >= _cdf(distribution, 27)


def test_distribution_mean_is_reasonable_for_symmetric_quantiles():
    distribution = quantiles_to_distribution(
        p10=24.0,
        p25=25.0,
        p50=26.0,
        p75=27.0,
        p90=28.0,
    )

    mean = sum(
        temperature * probability
        for temperature, probability in distribution.items()
    )

    assert math.isclose(mean, 26.0, abs_tol=0.25)


def test_equal_quantiles_collapse_to_single_temperature():
    distribution = quantiles_to_distribution(
        p10=26.0,
        p25=26.0,
        p50=26.0,
        p75=26.0,
        p90=26.0,
    )

    assert distribution == {26: 1.0}


def test_negative_temperatures_are_supported():
    distribution = quantiles_to_distribution(
        p10=-5.0,
        p25=-4.0,
        p50=-3.0,
        p75=-2.0,
        p90=-1.0,
    )

    assert distribution
    assert math.isclose(sum(distribution.values()), 1.0, abs_tol=1e-9)
    assert all(temperature < 0 for temperature in distribution)


def test_invalid_band_raises():
    distribution = {
        24: 0.2,
        25: 0.3,
        26: 0.5,
    }

    with pytest.raises(ValueError):
        band_probability(
            distribution,
            lo=27.0,
            hi=25.0,
        )


def test_weather_band_probability_from_forecast_quantiles():
    from weather_agent.probability import quantiles_to_distribution, band_probability

    distribution = quantiles_to_distribution(
        p10=24.0,
        p25=25.0,
        p50=26.0,
        p75=27.0,
        p90=28.0,
    )

    assert math.isclose(
        band_probability(distribution, lo=26.0, hi=27.0),
        0.50,
        abs_tol=1e-9,
    )


def test_band_covering_the_whole_support_is_exactly_one():
    """Found by the R21 backtest on real data, not by this suite: KSEA, a
    '62 F or above' band whose distribution lived entirely in [68, 75]. The sum of
    every mass is 1 plus the rounding of the normalising division, and
    `build_feature`'s `0 <= p <= 1` guard rejected it — correctly, for a value
    that was wrong by 2e-16."""
    from weather_agent.probability import band_probability, quantiles_to_distribution
    dist = quantiles_to_distribution(p10=68.81, p25=69.845, p50=71.05,
                                     p75=72.32, p90=74.72)
    assert band_probability(dist, lo=62.0, hi=None) == 1.0
    assert band_probability(dist, lo=None, hi=200.0) == 1.0


def test_a_genuinely_broken_probability_is_still_returned_unclamped():
    """The clamp must not become a silencer: only rounding is absorbed."""
    from weather_agent.probability import band_probability
    assert band_probability({20: 0.8, 21: 0.8}, lo=None, hi=None) == pytest.approx(1.6)

def test_the_lower_tail_cdf_never_goes_negative(tmp_path):
    """A CDF that returns a negative value is an arithmetic error, not a modelling
    choice, and `max(0.0, upper - lower)` cannot repair it because the damage is in
    the DIFFERENCE. Below `p10 - 1` the lower-tail expression went negative and its
    magnitude was ADDED to the lowest integer bin.

    Measured on the real M2 artifact (lead 9, p10 = 18.83): the lowest bin came out
    0.0968, of which 0.0333 — 34 % of the bin — was manufactured by the negative
    branch, and the raw mass summed to 1.0333 before normalisation hid it.
    """
    from weather_agent.probability import quantiles_to_distribution
    d = quantiles_to_distribution(p10=18.8333, p25=19.6, p50=20.4111,
                                  p75=21.2, p90=22.2)
    # 18 is floor(p10); its half-open bin [17.5, 18.5) lies almost entirely below
    # p10 - 1 = 17.83, so it must be SMALLER than the bin above it by a wide
    # margin, not comparable to it.
    assert d[18] == pytest.approx(0.0667, abs=1e-3), \
        "the lowest bin is inflated by the unclamped negative tail"
    assert d[18] < d[19] < d[20]
    assert sum(d.values()) == pytest.approx(1.0)


def test_the_two_tails_are_clamped_the_same_way():
    """The upper tail carried a `min(1.0, ...)` and the lower one carried no
    bound at all — the same guard written on one side and not the other."""
    from weather_agent.probability import quantiles_to_distribution
    a = quantiles_to_distribution(p10=10.0, p25=10.5, p50=11.0, p75=11.5, p90=12.0)
    b = quantiles_to_distribution(p10=-12.0, p25=-11.5, p50=-11.0, p75=-10.5,
                                  p90=-10.0)
    # mirrored quantiles must give a mirrored distribution
    assert sorted(round(v, 6) for v in a.values()) == \
           sorted(round(v, 6) for v in b.values())
