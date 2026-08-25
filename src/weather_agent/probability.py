from __future__ import annotations

import math


def _validate_quantile(name: str, value: float | None) -> float:
    if value is None:
        raise ValueError(f"{name} cannot be None")

    value = float(value)

    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")

    return value


def quantiles_to_distribution(
    *,
    p10: float | None,
    p25: float | None,
    p50: float | None,
    p75: float | None,
    p90: float | None,
) -> dict[int, float]:
    """
    Convert forecast quantiles into a discrete integer-temperature
    probability distribution.

    The current implementation uses piecewise-linear interpolation
    of the quantile CDF and allocates probability mass to integer
    temperatures.

    This function is intentionally independent from Polymarket,
    database access and resolution data.
    """

    q = {
        0.10: _validate_quantile("p10", p10),
        0.25: _validate_quantile("p25", p25),
        0.50: _validate_quantile("p50", p50),
        0.75: _validate_quantile("p75", p75),
        0.90: _validate_quantile("p90", p90),
    }

    ordered = list(q.items())

    for (_, previous), (_, current) in zip(ordered, ordered[1:]):
        if current < previous:
            raise ValueError("quantiles must be non-decreasing")

    # Extend the empirical CDF with conservative tails.
    #
    # The quantiles describe the central part of the distribution.
    # We use the nearest quantile spacing to define finite integer
    # support around the observed forecast range.
    values = [value for _, value in ordered]

    minimum = math.floor(values[0])
    maximum = math.ceil(values[-1])

    if minimum == maximum:
        return {minimum: 1.0}

    # Build a CDF by piecewise-linear interpolation.
    def cdf(x: float) -> float:
        if x <= values[0]:
            return 0.10 * (x - (values[0] - 1.0)) / 1.0

        for i in range(len(ordered) - 1):
            p_left, x_left = ordered[i]
            p_right, x_right = ordered[i + 1]

            if x <= x_right:
                if x_right == x_left:
                    return p_right

                fraction = (x - x_left) / (x_right - x_left)
                return p_left + fraction * (p_right - p_left)

        # Upper tail.
        return 0.90 + 0.10 * min(
            1.0,
            (x - values[-1]) / 1.0,
        )

    distribution: dict[int, float] = {}

    # Probability mass at integer t is approximated by the CDF
    # difference over [t - 0.5, t + 0.5].
    for temperature in range(minimum, maximum + 1):
        lower = cdf(temperature - 0.5)
        upper = cdf(temperature + 0.5)

        probability = max(0.0, min(1.0, upper - lower))

        if probability > 0:
            distribution[temperature] = probability

    total = sum(distribution.values())

    if total <= 0:
        raise ValueError("could not construct probability distribution")

    # Numerical normalization.
    return {
        temperature: probability / total
        for temperature, probability in distribution.items()
    }


def band_probability(
    distribution: dict[int, float],
    *,
    lo: float | None,
    hi: float | None,
) -> float:
    """
    Sum probability mass inside an inclusive temperature band.

    lo=None means open-ended lower tail.
    hi=None means open-ended upper tail.
    """

    if lo is not None:
        lo = float(lo)

    if hi is not None:
        hi = float(hi)

    if lo is not None and hi is not None and lo > hi:
        raise ValueError("lo cannot be greater than hi")

    probability = 0.0

    for temperature, mass in distribution.items():
        temperature = float(temperature)

        if lo is not None and temperature < lo:
            continue

        if hi is not None and temperature > hi:
            continue

        probability += float(mass)

    return probability
