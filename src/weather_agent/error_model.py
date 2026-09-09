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
  * strata are pooled BY LEAD; per-station only when n >= MIN_STATION_N, because
    ~26 station-days per station cannot support nine per-station quantiles;
  * training is walk-forward and expanding: a target date D may only use pairs
    with `target_date < D`. The first weeks have no coverage and are NOT
    backfilled;
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
from datetime import date, timedelta
from typing import Iterable, Sequence

#: Preregistration §7 — the levels, frozen.
LEVELS = (10, 25, 50, 75, 90)

#: §8.1 — minimum training pairs before any quantile is emitted.
MIN_N = 30

#: §4 — minimum pairs before a per-station stratum is used instead of pooled.
MIN_STATION_N = 30

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
    """One (forecast, realized) observation used to train the error model."""

    station: str
    target_date: date
    lead_h: int
    forecast_c: float
    observed_c: float

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


def training_pairs(
    pairs: Sequence[Pair], target: date, lead_h: int, station: str | None = None
) -> list[Pair]:
    """Walk-forward, expanding: only pairs strictly BEFORE the target date (§5).

    Leads are never mixed — the error grows with the horizon, and a pooled
    distribution over both would describe neither.
    """
    return [
        p
        for p in pairs
        if p.target_date < target
        and p.lead_h == lead_h
        and (station is None or p.station == station)
    ]


def quantiles_for(
    pairs: Sequence[Pair], station: str, target: date, lead_h: int
) -> Quantiles:
    """The stratum to use for one (station, target_date, lead), per §4.

    Per-station when it has enough history of its own; pooled by lead otherwise.
    The choice is recorded in `scope` so a downstream report can say which rows
    rest on station-specific evidence and which on the pool.
    """
    own = training_pairs(pairs, target, lead_h, station)
    if len(own) >= MIN_STATION_N:
        fitted = fit((p.error_c for p in own), SCOPE_STATION)
        if fitted.values:
            return fitted
    pooled = training_pairs(pairs, target, lead_h)
    return fit((p.error_c for p in pooled), SCOPE_POOLED)


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
