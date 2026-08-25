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
