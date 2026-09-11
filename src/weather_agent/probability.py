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

    # TAIL MODEL — exponential, with a scale taken from the data (A2).
    #
    # What was here: both tails ramped LINEARLY over exactly one degree past
    # p10/p90 and assigned ZERO beyond. The `1.0` was a magic constant with no
    # relation to the distribution it was extending, and it produced two errors at
    # once, in opposite directions:
    #
    #   * it crushed the entire lower 10 % into a single degree. Measured on the
    #     real M2 artifact (lead 9): the innermost tail bin came out 0.0968 against
    #     an empirical 0.0408 — over-assigned by 2.37x (R21 published this);
    #   * it declared everything past that one degree IMPOSSIBLE, where the
    #     empirical error distribution holds 1.7-2.3 %. A band priced at 3 cents
    #     that the model calls a strict zero is not a disagreement, it is a
    #     misspecification — and p = 0 is a claim no forecast can support.
    #
    # The fix takes the tail scale FROM THE QUANTILES instead of hardcoding it.
    # Between p10 and p25 sits 15 % of the mass over a known width, which fixes the
    # density at p10; an exponential tail carrying the remaining 10 % with that
    # density has decay length
    #
    #     lambda_lo = (p25 - p10) * 0.10 / 0.15
    #
    # and mirrors on the upper side. The result is continuous at p10/p90, strictly
    # positive everywhere (no manufactured zeros), and it WIDENS when the forecast
    # is uncertain and TIGHTENS when it is sharp — which the constant never did.
    #
    # Truncation: the support stops where the remaining tail mass falls below 1e-4
    # (k = ln(0.10 / 1e-4) ~= 6.9 decay lengths). A discrete distribution needs
    # finite support; cutting at a mass the integer grid cannot represent is a
    # rounding decision, not a modelling one.
    values = [value for _, value in ordered]

    #: 6.9 decay lengths — see the truncation note above.
    TAIL_CUTOFF_LAMBDAS = 6.9

    span_lo = values[1] - values[0]   # p25 - p10
    span_hi = values[-1] - values[-2]  # p90 - p75
    lambda_lo = span_lo * 0.10 / 0.15
    lambda_hi = span_hi * 0.10 / 0.15

    # A zero scale means the sample gives no information about that tail's width;
    # extending it would be inventing one, so the tail stops at the quantile.
    reach_lo = TAIL_CUTOFF_LAMBDAS * lambda_lo
    reach_hi = TAIL_CUTOFF_LAMBDAS * lambda_hi

    minimum = math.floor(values[0] - reach_lo)
    maximum = math.ceil(values[-1] + reach_hi)

    if minimum == maximum:
        return {minimum: 1.0}

    def cdf(x: float) -> float:
        if x <= values[0]:
            if lambda_lo <= 0.0:
                return 0.0
            # 0.10 * exp((x - p10) / lambda). Strictly positive, never negative —
            # the defect the previous lower tail had was a NEGATIVE cdf, whose
            # magnitude was then added to the lowest bin by `upper - lower`.
            return 0.10 * math.exp((x - values[0]) / lambda_lo)

        for i in range(len(ordered) - 1):
            p_left, x_left = ordered[i]
            p_right, x_right = ordered[i + 1]

            if x <= x_right:
                if x_right == x_left:
                    return p_right

                fraction = (x - x_left) / (x_right - x_left)
                return p_left + fraction * (p_right - p_left)

        if lambda_hi <= 0.0:
            return 1.0
        return 1.0 - 0.10 * math.exp(-(x - values[-1]) / lambda_hi)

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

    # The distribution is normalised to sum to 1, so a band covering the whole
    # support sums to 1 plus the rounding of that division: 1.0000000000000002.
    # Real data found this, not the suite — every fixture band happened to be a
    # strict subset of the support, so the sum never reached the top.
    #
    # The clamp is deliberately NARROW. Outside 1e-9 the value is returned
    # untouched so `build_feature`'s guard still fires: a probability of 1.3 is a
    # broken distribution, and swallowing it here would turn the one assertion
    # that would catch it into decoration.
    if 1.0 < probability <= 1.0 + 1e-9:
        return 1.0
    if -1e-9 <= probability < 0.0:
        return 0.0
    return probability
