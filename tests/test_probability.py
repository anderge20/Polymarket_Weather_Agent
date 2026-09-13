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
    # The support is no longer entirely negative, and that is CORRECT: a forecast
    # whose p90 is -1 must hold some mass above zero. Asserting `all(t < 0)` only
    # passed because the old tails stopped one degree past p90 — the assertion was
    # testing the truncation, not the negative-temperature handling it names.
    assert min(distribution) < 0
    assert sum(m for t_, m in distribution.items() if t_ < 0) > 0.9


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

    # [p50, p75] held exactly 0.50 while the tails were truncated: every degree
    # past p10/p90 was declared impossible, so the centre absorbed that mass. With
    # tails that carry their 10 % out to where it belongs, the same band holds
    # slightly LESS — which is the direction the fix has to move it.
    p = band_probability(distribution, lo=26.0, hi=27.0)
    assert math.isclose(p, 0.450024, abs_tol=1e-6)
    assert p < 0.50




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
def test_the_lower_tail_is_neither_negative_nor_a_pile_on_one_degree(tmp_path):
    """Two defects in one place, and the second outlived the fix for the first.

    (a) Below `p10 - 1` the old lower-tail expression went NEGATIVE and its
        magnitude was ADDED to the lowest bin by `upper - lower`. A CDF that
        returns a negative value is an arithmetic error, and `max(0.0, ...)` on
        the way out cannot repair it because the damage is in the DIFFERENCE.

    (b) Fixing (a) left the real misspecification: both tails ramped linearly over
        exactly ONE degree and assigned zero beyond, so the whole lower 10 % was
        crushed into a single degree.

    The check is against R21's INDEPENDENTLY MEASURED empirical frequency, not
    against whatever this implementation happens to return — a regression lock on
    the model's own output would have passed happily all through the defect.
    """
    from weather_agent.probability import quantiles_to_distribution
    d = quantiles_to_distribution(p10=18.8333, p25=19.6, p50=20.4111,
                                  p75=21.2, p90=22.2)
    # R21 measured the empirical mass at p50-2 (bin 18 here) as 0.0408, against a
    # model value of 0.0968 — over-assigned by 2.37x. The exponential tail brings
    # it to 0.0447, i.e. 1.10x. Still high, and not claimed to be exact.
    assert d[18] == pytest.approx(0.0447, abs=1e-3)
    assert d[18] / 0.0408 < 1.5, "the near tail is inflated again"
    assert d[18] < d[19] < d[20]
    assert sum(d.values()) == pytest.approx(1.0)


def test_the_far_tail_is_not_declared_impossible():
    """The old model returned EXACTLY ZERO more than one degree past p10/p90,
    where R21 measured the empirical distribution holding 1.7-2.3 %. A band the
    market prices at 3 cents and the model calls a strict zero is not a
    disagreement — it is a misspecification, and it fed the adverse selection.

    p = 0 is a claim no forecast can support, so no reachable outcome may carry it.
    """
    from weather_agent.probability import quantiles_to_distribution
    d = quantiles_to_distribution(p10=18.8333, p25=19.6, p50=20.4111,
                                  p75=21.2, p90=22.2)
    assert min(d) < 17.0 and max(d) > 24.0, "the support is still truncated"
    assert all(m > 0.0 for m in d.values()), "a reachable outcome was given p = 0"
    far = sum(m for t_, m in d.items() if t_ <= 17 or t_ >= 24)
    assert 0.005 < far < 0.06, f"far-tail mass {far} is not in a credible range"


def test_the_tail_scale_comes_from_the_data_not_a_constant():
    """The `1.0` degree was a magic constant with no relation to the distribution
    it extended. A diffuse forecast must get wide tails and a sharp one narrow
    tails; under the old model both got exactly one degree."""
    from weather_agent.probability import quantiles_to_distribution
    sharp = quantiles_to_distribution(p10=20.0, p25=20.2, p50=20.5, p75=20.8,
                                      p90=21.0)
    diffuse = quantiles_to_distribution(p10=10.0, p25=14.0, p50=20.0, p75=26.0,
                                        p90=30.0)
    sharp_reach = min(sharp.keys())
    diffuse_reach = min(diffuse.keys())
    assert (20.0 - sharp_reach) < (10.0 - diffuse_reach), \
        "a sharp forecast got a tail as wide as a diffuse one"


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


# ---------------------------------------------------------------------------
# A2 — the published tail model stays reachable
# ---------------------------------------------------------------------------

def test_linear_r21_reproduces_the_published_numbers_exactly():
    """The point of keeping the old path is that it REPRODUCES, so this test
    pins the actual published values rather than merely asserting the branch
    runs. R21 and R22 were computed with this CDF; if these numbers move, those
    results have silently stopped being reproducible."""
    from weather_agent.probability import (quantiles_to_distribution,
                                           TAIL_LINEAR_R21)
    d = quantiles_to_distribution(p10=18.8333, p25=19.6, p50=20.4111,
                                  p75=21.2, p90=22.2,
                                  tail_model=TAIL_LINEAR_R21)
    assert d[18] == pytest.approx(0.0667, abs=1e-3)
    assert (min(d), max(d)) == (18, 23), "the R21 support was 18..23"
    assert sum(d.values()) == pytest.approx(1.0)


def test_linear_r21_still_gives_the_band_exactly_one_half():
    """[p50, p75] was exactly 0.50 under the truncated tails — the assertion the
    exponential model had to move. Under the reproduction path it must come back
    EXACTLY, not approximately."""
    from weather_agent.probability import (quantiles_to_distribution,
                                           band_probability, TAIL_LINEAR_R21)
    d = quantiles_to_distribution(p10=24.0, p25=25.0, p50=26.0, p75=27.0,
                                  p90=28.0, tail_model=TAIL_LINEAR_R21)
    assert band_probability(d, lo=26.0, hi=27.0) == pytest.approx(0.50, abs=1e-12)


def test_the_default_tail_model_is_the_exponential_one():
    """The reproduction path must never become the deciding path: it assigns
    p = 0 to reachable outcomes."""
    from weather_agent.probability import (quantiles_to_distribution,
                                           TAIL_EXPONENTIAL, TAIL_LINEAR_R21)
    Q = dict(p10=18.8333, p25=19.6, p50=20.4111, p75=21.2, p90=22.2)
    assert quantiles_to_distribution(**Q) == \
        quantiles_to_distribution(**Q, tail_model=TAIL_EXPONENTIAL)
    assert quantiles_to_distribution(**Q) != \
        quantiles_to_distribution(**Q, tail_model=TAIL_LINEAR_R21)


def test_unknown_tail_model_is_refused_rather_than_defaulted():
    from weather_agent.probability import quantiles_to_distribution
    with pytest.raises(ValueError):
        quantiles_to_distribution(p10=24.0, p25=25.0, p50=26.0, p75=27.0,
                                  p90=28.0, tail_model="gaussian")


def test_the_two_models_differ_only_where_they_should():
    """Same binning, same interpolation between quantiles — the difference must
    live in the TAIL and nowhere else, which is why both share `_bin`."""
    from weather_agent.probability import (quantiles_to_distribution,
                                           TAIL_LINEAR_R21)
    Q = dict(p10=24.0, p25=25.0, p50=26.0, p75=27.0, p90=28.0)
    exp = quantiles_to_distribution(**Q)
    lin = quantiles_to_distribution(**Q, tail_model=TAIL_LINEAR_R21)
    # the linear model declares everything outside [24, 28] impossible
    assert (min(lin), max(lin)) == (24, 28)
    assert min(exp) < 24 and max(exp) > 28
    # and inside the quantile range the shapes stay close
    for t in (25, 26, 27):
        assert abs(exp[t] - lin[t]) < 0.06


def test_the_linear_tail_leaves_a_probability_GAP_and_the_exponential_does_not():
    """The defect measured from OUTCOMES rather than from the distribution's shape.

    Session A audited EGLC (London) over 842 live-book rows and found `p_model`
    was EXACTLY 0.0 in 50.5 % of them, with the smallest non-zero values at
    0.0506, 0.0519, 0.0521, 0.0540, 0.0549 — nothing in between. Six of the
    exact-zero rows WON, and the market had priced two of them above 0.10.

    That gap is not a property of London: it is ARITHMETIC. A tail ramp one
    degree wide carrying 10 % of the mass, discretised onto a one-degree grid,
    can only give a band either nothing or roughly a half of that 10 %. This test
    reproduces it from first principles on synthetic quantiles, so the mechanism
    is pinned independently of any one station's data.

    The exponential tail removes the DISCONTINUITY. It does not remove every zero
    and must not be claimed to: the support is finite by construction (truncated
    at 6.9 lambda), so bands far enough out are still zero. What changes is that
    the boundary moves far from the centre and the mass approaches it smoothly.
    """
    import random
    from weather_agent.probability import (quantiles_to_distribution,
                                           band_probability, TAIL_LINEAR_R21)
    rng = random.Random(7)

    def smallest_non_zero(tail_kwargs):
        out = []
        for _ in range(200):
            c, s = rng.uniform(-5, 35), rng.uniform(0.6, 4.0)
            qs = dict(p10=c - 1.28 * s, p25=c - 0.67 * s, p50=c,
                      p75=c + 0.67 * s, p90=c + 1.28 * s)
            d = quantiles_to_distribution(**qs, **tail_kwargs)
            nz = [band_probability(d, lo=float(t), hi=float(t))
                  for t in range(int(min(d)) - 4, int(max(d)) + 5)]
            nz = [v for v in nz if v > 0]
            if nz:
                out.append(min(nz))
        return sorted(out)

    linear = smallest_non_zero({"tail_model": TAIL_LINEAR_R21})
    exponential = smallest_non_zero({})

    # the gap: under the linear tail nothing lands between 0 and ~0.05
    assert min(linear) > 0.04, "the probability gap is gone from the linear model"
    assert linear[len(linear) // 2] > 0.06

    # and it is closed by the fix: mass approaches zero smoothly instead
    assert min(exponential) < 0.001
    assert exponential[len(exponential) // 2] < 0.01, \
        "the exponential tail reintroduced a gap"


def test_an_open_ended_band_can_never_carry_probability_zero():
    """The cleanest case for A2, and it is a LOGICAL impossibility rather than a
    calibration error.

    Session A found it at EGLC on 2026-06-23, lead 9 h: a band "32 or less" —
    open at the bottom — that the model called IMPOSSIBLE, the market priced at
    0.1095, and which WON. An open-ended tail cannot have probability zero under
    any honest specification: there is no lower bound to exclude.

    The mechanism is the old support, `range(floor(p10), ceil(p90) + 1)` — SIX
    integers on both real strata. Anything below it got exactly 0.0, open band or
    not. Session A measured the consequence on the live book: the maximum number
    of non-zero bands per group is exactly 6 and is NEVER exceeded, which makes
    the support arithmetic a hard ceiling rather than a tendency, and accounts for
    42.3 of the 50.5 points of hard zeros.

    Reproduced here from the versioned artifact, so it does not depend on their
    substrate.

    NOTE THE FIX IS PARTIAL AND THE TEST SAYS SO: 0.0196 against a market price of
    0.1095 is still light by more than 5x, which is the same residual session A's
    review measures. What changes is POSSIBLE vs IMPOSSIBLE, and only that is
    asserted here.
    """
    import json
    from weather_agent.probability import (quantiles_to_distribution,
                                           band_probability, TAIL_LINEAR_R21)
    art = json.load(open("artifacts/m2_quantiles.json"))
    qc = {int(k): v for k, v in art["strata"]["9"]["values"].items()}
    lev = {l: 34.5 + qc[l] for l in (10, 25, 50, 75, 90)}   # a heatwave forecast
    kw = {f"p{k}": lev[k] for k in lev}

    old = quantiles_to_distribution(**kw, tail_model=TAIL_LINEAR_R21)
    new = quantiles_to_distribution(**kw)

    # the old support is the six-integer window, so "32 or less" is a strict zero
    assert (min(old), max(old)) == (33, 37)
    assert band_probability(old, lo=None, hi=32.0) == 0.0, \
        "the defect is gone from the reproduction path"

    # the fix makes it POSSIBLE. It does not make it right.
    p_new = band_probability(new, lo=None, hi=32.0)
    assert p_new > 0.0, "an open-ended band was still called impossible"
    assert p_new < 0.1095, \
        "the exponential tail is still lighter than the market price; if this " \
        "ever fails the residual has been fixed and the comment must be updated"
