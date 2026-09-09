"""
error_model.py — M2: the forecast error distribution
=====================================================

Turns a deterministic forecast into a distribution, which is what makes a
probability possible at all. Implements `PREREG_M2_ERROR.md` (sha
`16b729e1d28f3cbab8a102ab7ebd67a451471a961a299726714e987d8223e55d`), frozen
before any quantile was computed. Every rule below is quoted from it; none of
them may be changed after seeing results.

  * error is `e = y - f` in Celsius, positive meaning reality beat the forecast;
  * quantiles are the empirical percentiles of `e`, added to `f`;
  * strata are pooled BY LEAD only. The per-station stratum was removed in v2:
    n >= 30 held in 4 of 98 (station, lead) groups, so it bought no coverage and
    added uncontrolled heterogeneity. Lowering the threshold to 20 after seeing
    that 88 of 98 would cross it is choosing a cutoff from results;
  * training is walk-forward on LABEL AVAILABILITY, not on the target date: a
    decision at T may only use pairs whose realized high was already available,
    `end_of_local_day(F) + 24h <= T`. Filtering by `target_date < D` instead
    leaked in 8/8 stations at both leads, by -9 h to -43 h (v2 §0, D-2);
  * a stratum with fewer than MIN_N pairs emits NOTHING, so `build_feature`
    returns None. Without a characterised error there is no honest probability.

DECLARED LIMITATION (preregistration §6): label availability is ASSUMED at 24 h
after the end of the local day. Retrospective ingestion cannot prove when an
observation was published — `available_at` is the download instant (B-4/D17) — and
a strict as-of filter would return nothing. This is an assumption, not a
measurement, and every report using these quantiles must say so.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable, Sequence

#: Preregistration §7 — the levels, frozen.
LEVELS = (10, 25, 50, 75, 90)

#: §8.1 — minimum training pairs before any quantile is emitted.
MIN_N = 30

#: v2 §5 — falsifiable acceptance. A declared 80 % interval that covers half the
#: outcomes is decoration, not a distribution. Fixed here, before seeing results.
CALIBRATION_P10_RANGE = (0.05, 0.15)
CALIBRATION_P90_RANGE = (0.85, 0.95)

#: §8.3 — a stratum whose p90-p10 falls outside this range is rejected. Zero width
#: means a degenerate sample; 30 C means something is broken, not that the weather
#: is uncertain.
MIN_SPREAD_C = 0.0
MAX_SPREAD_C = 30.0

#: §6 — assumed publication lag of the realized daily high, after the local day ends.
ASSUMED_LABEL_LAG = timedelta(hours=24)

SCOPE_STATION = "STATION"
SCOPE_POOLED = "POOLED"
SCOPE_REJECTED = "REJECTED"
SCOPE_INSUFFICIENT = "INSUFFICIENT"


@dataclass(frozen=True)
class Pair:
    """One (forecast, realized) observation used to train the error model.

    `label_available_at` is when this pair's realized high could first be known
    (v2 §3). It is what gates training, not the target date: a label from the day
    before is still in the future at a 24 h-lead decision.
    """

    station: str
    target_date: date
    lead_h: int
    forecast_c: float
    observed_c: float
    label_available_at: "datetime | None" = None

    @property
    def error_c(self) -> float:
        """`e = y - f`. Positive means reality beat the forecast (§2)."""
        return self.observed_c - self.forecast_c


@dataclass(frozen=True)
class Quantiles:
    """Error percentiles for one stratum, in Celsius."""

    scope: str
    n: int
    values: dict[int, float]  # level -> error percentile

    @property
    def spread(self) -> float:
        return self.values[90] - self.values[10]


def percentile(sorted_values: Sequence[float], level: float) -> float:
    """Linear-interpolated percentile, matching numpy's default method.

    Implemented here rather than pulled from numpy so the rule is visible and
    cannot drift with a dependency upgrade — the preregistration fixes the
    method, not the library.
    """
    if not sorted_values:
        raise ValueError("no values")
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    pos = (len(sorted_values) - 1) * (level / 100.0)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = pos - lo
    return float(sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac)


def fit(errors: Iterable[float], scope: str) -> Quantiles:
    """Empirical quantiles of `e`. No smoothing, no parametric fit, no tail
    trimming (§7): if the distribution is skewed or heavy-tailed, that is
    reported, not corrected."""
    vals = sorted(float(e) for e in errors)
    n = len(vals)
    if n < MIN_N:
        return Quantiles(SCOPE_INSUFFICIENT, n, {})
    q = {lvl: percentile(vals, lvl) for lvl in LEVELS}
    ordered = [q[lvl] for lvl in LEVELS]
    monotone = all(a <= b for a, b in zip(ordered, ordered[1:]))
    spread = q[90] - q[10]
    if not monotone or not (MIN_SPREAD_C < spread < MAX_SPREAD_C):
        return Quantiles(SCOPE_REJECTED, n, {})
    return Quantiles(scope, n, q)


def training_pairs(pairs: Sequence[Pair], t, lead_h: int) -> list[Pair]:
    """Pairs whose label was ALREADY AVAILABLE at the decision instant `t` (v2 §3).

    The filter is applied pair by pair, with the timezone of the pair's own
    station — not of the market being evaluated. It is not a fixed offset in days
    but the availability condition itself, evaluated.

    Leads are never mixed: the error grows with the horizon, and a distribution
    pooled over both would describe neither.
    """
    return [
        p
        for p in pairs
        if p.lead_h == lead_h
        and p.label_available_at is not None
        and p.label_available_at <= t
    ]


def quantiles_for(pairs: Sequence[Pair], t, lead_h: int) -> Quantiles:
    """The stratum for a decision at `t` and this lead: pooled, always (v2 §4).

    100 % of rows use the pooled-by-lead stratum. A per-station stratum needs its
    own preregistration with the threshold fixed in advance.
    """
    return fit((p.error_c for p in training_pairs(pairs, t, lead_h)), SCOPE_POOLED)


def calibration(pairs: Sequence[Pair], q: Quantiles) -> dict:
    """Share of realized highs below p10 and below p90 (v2 §5.1).

    Computed on pairs the model did NOT train on; the caller passes the holdout.
    """
    if not q.values or not pairs:
        return {"n": 0, "below_p10": None, "below_p90": None, "passes": False}
    n = len(pairs)
    below10 = sum(1 for p in pairs if p.error_c < q.values[10]) / n
    below90 = sum(1 for p in pairs if p.error_c < q.values[90]) / n
    passes = (
        CALIBRATION_P10_RANGE[0] <= below10 <= CALIBRATION_P10_RANGE[1]
        and CALIBRATION_P90_RANGE[0] <= below90 <= CALIBRATION_P90_RANGE[1]
    )
    return {"n": n, "below_p10": below10, "below_p90": below90, "passes": passes}


def forecast_quantiles_c(forecast_c: float, q: Quantiles) -> dict[int, float]:
    """`forecast_pXX = f + percentile_XX(e)` (§7), in Celsius."""
    if not q.values:
        raise ValueError(f"stratum {q.scope} has no quantiles to apply")
    return {lvl: forecast_c + q.values[lvl] for lvl in LEVELS}


# ---------------------------------------------------------------------------
# unit handling (preregistration §3, decision B-7)
# ---------------------------------------------------------------------------


def c_to_f_level(c: float) -> float:
    """A temperature LEVEL, Celsius to Fahrenheit."""
    return c * 9.0 / 5.0 + 32.0


def c_to_f_delta(c: float) -> float:
    """A temperature DIFFERENCE, Celsius to Fahrenheit.

    A separate function on purpose. Applying the level formula to a difference
    adds a spurious 32 degrees, and the result still looks like a temperature —
    which is exactly how this class of bug survives review.
    """
    return c * 9.0 / 5.0


def to_market_unit(quantiles_c: dict[int, float], unit: str) -> dict[int, float]:
    """Quantile LEVELS expressed in the market's contractual unit.

    The distribution must be built in the market's own unit: it is indexed by
    integer temperatures, and the contract's resolution grid is whole degrees in
    that unit (bands of width 0 in C, 1 in F). Converting the BANDS to Celsius
    instead would make them 0.56 C wide and misaligned with the integer grid —
    see B-7, which corrected B-6 on exactly this point.
    """
    u = (unit or "").strip().upper()
    if u == "C":
        return dict(quantiles_c)
    if u == "F":
        return {lvl: c_to_f_level(v) for lvl, v in quantiles_c.items()}
    raise ValueError(
        f"unit {unit!r} is neither C nor F; refusing to guess — an unknown unit "
        "silently compared against a band is the failure this rule exists to prevent"
    )
