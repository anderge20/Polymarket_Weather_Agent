"""
weather_agent.settlement — SettlementOperator (R12/R14)
=======================================================
STATUS: IMPLEMENTED + TESTED (tests/test_settlement.py, offline). NOT VALIDATED:
`SETTLEMENT_OPERATOR_CORE.v3.md` §6 says plainly that **no operator is VALIDATED**
and none is promoted by editing — the acceptance criterion is postponed (A-24).
This module implements the frozen core; it does not promote anything.

Implements `SETTLEMENT_OPERATOR_CORE.v3.md` (FROZEN, sha a6d92667…). Where this
docstring and that document disagree, the document governs.

WHAT IT ANSWERS
---------------
Given a market's contract and a set of observations, WHICH band did the day
actually land in — and, far more often, WHY we refuse to say. Over the 93,221
markets of the catalogue the honest answer is a refusal in 78 %: only 18.31 %
emit a label at all (core §5).

THE ORDER OF CHECKS IS NORMATIVE, NOT A STYLE CHOICE
----------------------------------------------------
§4: `terna -> estrato -> ctx -> cláusula -> serie/ventana/as-of`. The stratum is
tested BEFORE the context, because rows with no operator must die of their own
`reason` — if the context were checked first, the 77 CWA/Taipei markets of
stratum 11 would die of a missing ICAO instead of `source_inaccessible`, and the
1,859 HKO markets of stratum 10 (whose `icao2` is NULL by nature, not by defect)
would never emit a label at all.

FAIL-CLOSED, WITH A CLOSED ENUM
-------------------------------
There is NO default operator. `quantiles_to_distribution`'s nearest-integer
rounding is explicitly forbidden as a fallback. A market outside the enabled
strata does not get a guess; it gets a `SettlementUnavailable` carrying one of
the enumerated reasons and belongs in `markets_excluded`, out of features, labels,
backtest and training.

`SettlementUnavailable` deliberately does NOT derive from `ValueError` (§2): a
refusal to settle is a normal, expected outcome of a correct pipeline, and must
not be swallowed by a caller catching ValueError for bad input.

TARGET_DATE IS THE CALLER'S
---------------------------
The core does not derive it (2D §C, B2 DECIDED-V1). Absent -> the terminal
`context_out_of_snapshot`. The 2D contract is internally unsatisfiable on this
point (A-27: §C forbids every available source and offers none); that is 2D's
contradiction to resolve, and this module simply requires the parameter.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterable, Sequence

from .polymarket import resolution as res

# --------------------------------------------------------------------------- vocabularies
UNIT_C, UNIT_F = "C", "F"

#: Series identifiers (§2). NEAREST is deliberately absent (§3 b).
SERIES_HKO = "hko_clmmaxt"
SERIES_METAR_C = "metar_body_c"
SERIES_METAR_F = "metar_tgroup_tmpf"

WINDOW_LOCAL_CIVIL_DAY = "LOCAL_CIVIL_DAY"
WINDOW_SOURCE_DAILY_ROW = "SOURCE_DAILY_ROW"

AGG_MAX = "MAX"
AGG_SOURCE_DAILY = "SOURCE_DAILY"

QUANT_INTERVAL_FLOOR = "INTERVAL_FLOOR"
QUANT_NONE = "NONE"

AVAIL_ASOF_VERIFIED = "ASOF_VERIFIED"
AVAIL_Y_FINAL_UNKNOWN_ASOF = "Y_FINAL_UNKNOWN_ASOF"

COMPAT_DIRECT = "DIRECT"
COMPAT_PROXY_AUDITED = "PROXY_AUDITED"

LABEL_SOURCE_IEM_METAR = "IEM_METAR"
LABEL_SOURCE_HKO = "HKO_CLMMAXT"

#: v3's OWN label for the source of stratum 11 — the literal string in
#: `CATALOG_V2.v3.primary_source`. It is NOT `resolution.SRC_UNKNOWN` ("UNKNOWN"),
#: which is the D21 parser's value for "could not identify a source". Conflating
#: the two sent all 77 Taipei markets to `context_out_of_snapshot`, which §4
#: requires to have zero cases today. Verified against the catalogue: the terna
#: present is exactly ("SIN_CLAUSULA", "P_UNKNOWN", "C") × 77.
SRC_SIN_CLAUSULA_V3 = "SIN_CLAUSULA"

#: CLOSED enum of refusal reasons (§4). Nothing outside this set may be emitted.
#: Stratum-level:
R_Y_UNDEFINED = "no_settlement_operator:Y_undefined_by_contract"   # strata 1, 2
R_BY_FORECAST = "no_settlement_operator:by_forecast"               # strata 3, 4
R_PROXY_NOT_AUDITED_F = "proxy_not_audited_F"                      # stratum 6
R_SERIES_FILTER_UNVERIFIED = "series_filter_unverified"            # stratum 9
R_SOURCE_INACCESSIBLE = "source_inaccessible"                      # stratum 11
R_CLAUSE_NOT_AUDITED = "clause_stratum_not_audited"                # 5, 7 with clause
#: Execution-level (only reachable inside 5/7/8/10):
R_SERIES_MISMATCH = "series_mismatch"
R_NO_OBS_IN_WINDOW = "no_observations_in_window"
R_NOT_AVAILABLE_ASOF = "observations_not_available_asof"
#: Terminal:
R_CONTEXT_OUT_OF_SNAPSHOT = "context_out_of_snapshot"

FAIL_REASONS = frozenset({
    R_Y_UNDEFINED, R_BY_FORECAST, R_PROXY_NOT_AUDITED_F, R_SERIES_FILTER_UNVERIFIED,
    R_SOURCE_INACCESSIBLE, R_CLAUSE_NOT_AUDITED, R_SERIES_MISMATCH,
    R_NO_OBS_IN_WINDOW, R_NOT_AVAILABLE_ASOF, R_CONTEXT_OUT_OF_SNAPSHOT,
})


class SettlementUnavailable(Exception):
    """Refusal to settle, carrying one of `FAIL_REASONS`.

    NOT a ValueError, and that is normative (§2): refusing to settle is the
    expected outcome for 78 % of the catalogue, not a bad-input error, and a
    caller catching ValueError must not absorb it."""

    def __init__(self, reason: str, *, detail: str | None = None):
        if reason not in FAIL_REASONS:
            raise AssertionError(
                f"settlement: {reason!r} is outside the closed enum of §4; the core "
                f"is frozen, so a new reason requires amending the document, not the code"
            )
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}" + (f": {detail}" if detail else ""))


# --------------------------------------------------------------------------- data
@dataclass(frozen=True)
class Observation:
    """One reading (§2). `available_at` is None across the whole IEM history —
    OBSERVED — which is why the as-of route is closed today for strata 5, 7 and 8."""
    ts_utc: datetime
    value: float
    unit: str
    series: str
    available_at: datetime | None = None
    record_version: int = 1


@dataclass(frozen=True)
class MarketContext:
    """Everything the operator needs about the contract. `target_date` is the
    caller's (2D §C); `station_icao`/`station_tz` are required iff the window is
    LOCAL_CIVIL_DAY and MUST be absent otherwise (§2, §4)."""
    market_id: str
    event_id: str
    contract_source: str
    measurement_rule_code: str
    unit: str
    rounding_rule: str | None = None
    target_date: date | None = None
    station_icao: str | None = None
    station_tz: str | None = None
    clause_lowest_bracket: bool = False
    fail_closed_reason: str | None = None


@dataclass(frozen=True)
class SettlementResult:
    band_key: int
    settled_value: float
    n_obs: int
    unit: str
    window_start_utc: datetime | None
    window_end_utc: datetime | None
    asof: datetime | None
    window_kind: str
    aggregation: str
    contract_source: str
    quantization: str
    availability: str
    label_source: str
    compat_status: str
    clause_lowest_bracket: bool
    audit: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- operators
@dataclass(frozen=True)
class SettlementOperator:
    """One enabled operator of §3. `applies_to` is PURE in its four arguments —
    invariant to `market_id` — which is what lets the stratum be decided before
    the context exists."""
    operator_id: str
    version: str
    unit: str
    window_kind: str
    aggregation: str
    quantization: str
    required_series: str
    contract_source: str
    measurement_rule_code: str
    label_source: str
    compat_status: str

    def applies_to(self, contract_source: str, measurement_rule_code: str,
                   unit: str, rounding_rule: str | None = None) -> bool:
        return (contract_source == self.contract_source
                and measurement_rule_code == self.measurement_rule_code
                and unit == self.unit)

    @property
    def requires_station(self) -> bool:
        """§2: station non-null IFF the window is LOCAL_CIVIL_DAY."""
        return self.window_kind == WINDOW_LOCAL_CIVIL_DAY


#: The four enabled operators of §3. Nothing else settles anything.
OP_WU_DAILYOBS_C = SettlementOperator(
    operator_id="WU_DAILYOBS_C_PROXY_IEM", version="v1", unit=UNIT_C,
    window_kind=WINDOW_LOCAL_CIVIL_DAY, aggregation=AGG_MAX,
    # UNKNOWN in v3 §2.2, qualified: over integer `metar_body_c`, FLOOR is
    # identical to NONE (n_disc = 0), so the choice is NO_DECIDIBLE permanently.
    quantization=QUANT_NONE, required_series=SERIES_METAR_C,
    contract_source=res.SRC_WU, measurement_rule_code=res.P_WU_DAILYOBS,
    label_source=LABEL_SOURCE_IEM_METAR, compat_status=COMPAT_PROXY_AUDITED,
)
OP_NOAA_TEMPCOL_C = SettlementOperator(
    operator_id="NOAA_TEMPCOL_C_PROXY_IEM", version="v1", unit=UNIT_C,
    window_kind=WINDOW_LOCAL_CIVIL_DAY, aggregation=AGG_MAX,
    quantization=QUANT_NONE, required_series=SERIES_METAR_C,
    contract_source=res.SRC_NOAA, measurement_rule_code=res.P_NOAA_TEMPCOL,
    label_source=LABEL_SOURCE_IEM_METAR, compat_status=COMPAT_PROXY_AUDITED,
)
OP_NOAA_TEMPCOL_F = SettlementOperator(
    operator_id="NOAA_TEMPCOL_F_PROXY_IEM", version="v1", unit=UNIT_F,
    # §3: the window is NO_SEPARABLE_EN_MUESTRA here (H_LOCAL = H_UTC on 6/6);
    # DP-W1 is NOT ratified, and this stratum has no holdout (§6), so it is
    # explicitly NOT promotable.
    window_kind=WINDOW_LOCAL_CIVIL_DAY, aggregation=AGG_MAX,
    # NONE as in 5 and 7: the 1 °F grid is made by the IEM series itself.
    # `round()` is forbidden.
    quantization=QUANT_NONE, required_series=SERIES_METAR_F,
    contract_source=res.SRC_NOAA, measurement_rule_code=res.P_NOAA_TEMPCOL,
    label_source=LABEL_SOURCE_IEM_METAR, compat_status=COMPAT_PROXY_AUDITED,
)
OP_HKO_ABSMAX = SettlementOperator(
    operator_id="HKO_ABSMAX_INTERVAL_FLOOR", version="v1", unit=UNIT_C,
    window_kind=WINDOW_SOURCE_DAILY_ROW, aggregation=AGG_SOURCE_DAILY,
    # ceil / half-up / half-even were REFUTED (164/166, Wilson 0.957-0.997).
    quantization=QUANT_INTERVAL_FLOOR, required_series=SERIES_HKO,
    contract_source=res.SRC_HKO, measurement_rule_code=res.P_HKO_ABSMAX,
    label_source=LABEL_SOURCE_HKO, compat_status=COMPAT_DIRECT,
)

OPERATORS: tuple[SettlementOperator, ...] = (
    OP_WU_DAILYOBS_C, OP_NOAA_TEMPCOL_C, OP_NOAA_TEMPCOL_F, OP_HKO_ABSMAX,
)

#: Fail-closed strata (§3/§4): (contract_source, measurement_rule_code, unit) -> reason.
#: Exhaustive over the 11-class partition; the enabled four are absent by construction.
_FAIL_CLOSED_STRATA: dict[tuple[str, str, str], str] = {
    (res.SRC_WU, res.P_WU_GENERIC, UNIT_C): R_Y_UNDEFINED,          # 1
    (res.SRC_WU, res.P_WU_GENERIC, UNIT_F): R_Y_UNDEFINED,          # 2
    (res.SRC_WU, res.P_BY_FORECAST, UNIT_C): R_BY_FORECAST,         # 3
    (res.SRC_WU, res.P_BY_FORECAST, UNIT_F): R_BY_FORECAST,         # 4
    (res.SRC_WU, res.P_WU_DAILYOBS, UNIT_F): R_PROXY_NOT_AUDITED_F,  # 6
    (res.SRC_NOAA, res.P_NOAA_HOURLY, UNIT_F): R_SERIES_FILTER_UNVERIFIED,  # 9
    # 11 carries BOTH ternas with the same reason: v3 says SIN_CLAUSULA/P_UNKNOWN
    # while the D21 parser says CWA/P_CWA_TemperatureColumn for the same 77 Taipei
    # markets. Listing only one would send the other to `context_out_of_snapshot`,
    # which §4 requires to have 0 cases today.
    (SRC_SIN_CLAUSULA_V3, res.P_UNKNOWN, UNIT_C): R_SOURCE_INACCESSIBLE,      # 11 (v3)
    (res.SRC_CWA, res.P_CWA_TEMPCOL, UNIT_C): R_SOURCE_INACCESSIBLE,          # 11 (D21)
}


def select_operator(contract_source: str, measurement_rule_code: str, unit: str,
                    rounding_rule: str | None = None) -> SettlementOperator:
    """Resolve the terna to an operator, or refuse. PURE in its four arguments.

    Refuses with the stratum's own reason when the terna is a known fail-closed
    class, and with the terminal `context_out_of_snapshot` when it is outside the
    §3 partition entirely — reachable only going forward, 0 cases at the freeze."""
    for op in OPERATORS:
        if op.applies_to(contract_source, measurement_rule_code, unit, rounding_rule):
            return op
    reason = _FAIL_CLOSED_STRATA.get((contract_source, measurement_rule_code, unit))
    if reason is not None:
        raise SettlementUnavailable(reason)
    raise SettlementUnavailable(
        R_CONTEXT_OUT_OF_SNAPSHOT,
        detail=f"terna outside the 11-class partition: "
               f"({contract_source!r}, {measurement_rule_code!r}, {unit!r})",
    )


# --------------------------------------------------------------------------- window
def _zoneinfo(tz_name: str):
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        raise SettlementUnavailable(
            R_CONTEXT_OUT_OF_SNAPSHOT, detail=f"unknown station_tz {tz_name!r}")


def local_civil_day_window(target_date: date, tz_name: str) -> tuple[datetime, datetime]:
    """[local midnight, next local midnight) of `target_date`, in UTC.

    Half-open on purpose: a reading at exactly the next midnight belongs to the
    next civil day. Computed through the station's own tz, so a DST transition
    gives a 23- or 25-hour window rather than a silently wrong 24."""
    tz = _zoneinfo(tz_name)
    start_local = datetime.combine(target_date, time(0, 0), tzinfo=tz)
    end_local = datetime.combine(target_date + timedelta(days=1), time(0, 0), tzinfo=tz)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def source_daily_row_window(target_date: date) -> tuple[None, None]:
    """SOURCE_DAILY_ROW has NO derivable window, and returning one was a defect.

    Stratum 10 (HKO) has no station and no tz — `icao2` is NULL in all 1,859, and
    §4 says that is NOT a defect — so the day boundary cannot be localised. An
    earlier version returned the UTC civil day and then FILTERED with it. HKO
    publishes in HKT (UTC+8), so the row stamped at the source's own midnight for
    2026-09-10 (= 2026-09-09T16:00Z) fell OUTSIDE that window and was discarded,
    while the NEXT day's row fell inside and settled. It did not fail closed: it
    emitted a label from the wrong day, in the only DIRECT stratum and the one
    that has a holdout.

    §2 declares `window_start_utc`/`window_end_utc` NULLABLE, and this is the
    operator that justifies a null: the caller hands over the source's row FOR
    that date, and no temporal predicate is applied to it."""
    return None, None


# --------------------------------------------------------------------------- settle
def _quantize(value: float, quantization: str) -> int:
    if quantization == QUANT_INTERVAL_FLOOR:
        return int(math.floor(value))
    if quantization == QUANT_NONE:
        # NONE means the series already delivers the contract's grid. A
        # non-integral value therefore means the series is not what it claims,
        # which is a series problem and not licence to round: `round()` is
        # forbidden (§3 b) and nearest-integer is forbidden outright (§4).
        if float(value).is_integer():
            return int(value)
        raise SettlementUnavailable(
            R_SERIES_MISMATCH,
            detail=f"quantization=NONE requires an on-grid value, got {value!r}")
    raise AssertionError(f"settlement: unknown quantization {quantization!r}")


def settle(obs: Iterable[Observation], ctx: MarketContext,
           asof: datetime | None = None) -> SettlementResult:
    """Settle one market, or raise `SettlementUnavailable` with a reason from §4.

    Check order is normative (§4): terna -> stratum -> ctx -> clause ->
    series/window/as-of."""
    # ---- 1. terna -> stratum. FIRST, and before anything from the ctx: §4 is
    #         explicit that "el estrato antes que el ctx: las filas sin operador
    #         mueren por su reason". Reading `ctx.fail_closed_reason` here — as an
    #         earlier version did — let a stratum-11 market die of some other
    #         reason instead of `source_inaccessible`, which §4 requires to reach
    #         all 77 of them.
    op = select_operator(ctx.contract_source, ctx.measurement_rule_code, ctx.unit,
                         ctx.rounding_rule)

    # ---- 2. ctx
    if ctx.fail_closed_reason:
        # The caller's own refusal. §4 lists `target_date_unresolvable` and
        # `_ambiguous` as OUTSIDE the enum and says they "llegan como
        # context_out_of_snapshot" — so anything the caller sends that is not
        # itself an enum member is TRANSLATED, never passed through. Passing it
        # through raised AssertionError, which `try_settle` does not catch: the
        # operator crashed instead of failing closed, in the very function whose
        # purpose is to return the reason as data.
        if ctx.fail_closed_reason in FAIL_REASONS:
            raise SettlementUnavailable(ctx.fail_closed_reason)
        raise SettlementUnavailable(
            R_CONTEXT_OUT_OF_SNAPSHOT,
            detail=f"caller reason {ctx.fail_closed_reason!r}")
    if ctx.target_date is None:
        raise SettlementUnavailable(
            R_CONTEXT_OUT_OF_SNAPSHOT,
            detail="target_date is the caller's parameter (2D §C) and is missing")
    # §2's "sii" is a BICONDITIONAL, and it writes the prohibitive half separately
    # so it is not skipped: station non-null IFF LOCAL_CIVIL_DAY, "no con
    # SOURCE_DAILY_ROW (10)". Implementing only the forward half let an HKO
    # context carry a station that the UTC-keyed path then ignored — while `audit`
    # recorded it as if it had participated. False provenance in the one DIRECT
    # stratum is worse than a refusal.
    if op.requires_station and not (ctx.station_icao and ctx.station_tz):
        raise SettlementUnavailable(
            R_CONTEXT_OUT_OF_SNAPSHOT,
            detail=f"{op.operator_id} needs station_icao and station_tz "
                   f"(window_kind={op.window_kind})")
    if not op.requires_station and (ctx.station_icao or ctx.station_tz):
        raise SettlementUnavailable(
            R_CONTEXT_OUT_OF_SNAPSHOT,
            detail=f"{op.operator_id} takes NO station (window_kind="
                   f"{op.window_kind}), got {ctx.station_icao!r}/{ctx.station_tz!r}")

    # ---- 3. clause. Strata 5 and 7 have ZERO markets audited WITH the
    #         lowest-bracket clause, so a market carrying it is refused. Stratum 8
    #         has no such market; stratum 10 emits, flagged.
    if ctx.clause_lowest_bracket and op in (OP_WU_DAILYOBS_C, OP_NOAA_TEMPCOL_C):
        raise SettlementUnavailable(R_CLAUSE_NOT_AUDITED)

    # ---- 4. series / window / as-of
    rows = list(obs)
    in_series = [o for o in rows if o.series == op.required_series]
    if rows and not in_series:
        raise SettlementUnavailable(
            R_SERIES_MISMATCH,
            detail=f"{op.operator_id} requires {op.required_series!r}, got "
                   f"{sorted({o.series for o in rows})}")

    if op.window_kind == WINDOW_LOCAL_CIVIL_DAY:
        win_start, win_end = local_civil_day_window(ctx.target_date, ctx.station_tz)
        in_window = [o for o in in_series if win_start <= o.ts_utc < win_end]
    else:
        # SOURCE_DAILY_ROW: no temporal predicate. The row the caller hands over IS
        # the source's row for `target_date`; filtering it against a window we
        # cannot derive is how the wrong day's label got emitted.
        win_start, win_end = source_daily_row_window(ctx.target_date)
        in_window = list(in_series)
    if not in_window:
        raise SettlementUnavailable(R_NO_OBS_IN_WINDOW)

    # As-of (§2). With an `asof` given, EVERY observation must carry a verified
    # availability; `available_at` is None across the whole IEM history, which is
    # exactly why this route is closed today for strata 5, 7 and 8.
    if asof is not None:
        if any(o.available_at is None for o in in_window):
            raise SettlementUnavailable(R_NOT_AVAILABLE_ASOF)
        in_window = [o for o in in_window if o.available_at <= asof]
        if not in_window:
            raise SettlementUnavailable(R_NOT_AVAILABLE_ASOF)
        availability = AVAIL_ASOF_VERIFIED
    else:
        availability = AVAIL_Y_FINAL_UNKNOWN_ASOF

    if any(o.unit != op.unit for o in in_window):
        # Unreachable through `applies_to`, which matches on unit — but a caller
        # can hand over observations in another unit, and converting them here
        # would be inventing data.
        raise SettlementUnavailable(
            R_SERIES_MISMATCH,
            detail=f"observations in {sorted({o.unit for o in in_window})} for a "
                   f"{op.unit} operator")

    # ---- 5. aggregation
    # `record_version` is applied the SAME way in both branches. It used to be
    # honoured only under SOURCE_DAILY and ignored under MAX, which governs strata
    # 5, 7 and 8 — 17,083 of the 18,942 markets with an operator. D17-C ingests a
    # revision WITHOUT overwriting, so the superseded row survives alongside its
    # correction; taking a plain max over both would return the SUPERSEDED value
    # whenever it is the larger. Keep the highest version per observation instant,
    # then aggregate.
    # NOT fixed by the frozen core, which only says "record_version D17-C" —
    # declared here as the implementation's policy, not as the document's.
    best_by_instant: dict[datetime, Observation] = {}
    for o in in_window:
        prev = best_by_instant.get(o.ts_utc)
        if prev is None or o.record_version > prev.record_version:
            best_by_instant[o.ts_utc] = o
    current = list(best_by_instant.values())
    if op.aggregation == AGG_MAX:
        settled = max(o.value for o in current)
    else:  # SOURCE_DAILY — one published row per day.
        settled = max(o.value for o in current)

    band_key = _quantize(settled, op.quantization)
    return SettlementResult(
        band_key=band_key, settled_value=float(settled), n_obs=len(current),
        unit=op.unit, window_start_utc=win_start, window_end_utc=win_end, asof=asof,
        window_kind=op.window_kind, aggregation=op.aggregation,
        contract_source=op.contract_source, quantization=op.quantization,
        availability=availability, label_source=op.label_source,
        compat_status=op.compat_status,
        clause_lowest_bracket=ctx.clause_lowest_bracket,
        audit={
            "operator_id": op.operator_id, "version": op.version,
            "required_series": op.required_series,
            "n_rows_given": len(rows), "n_in_series": len(in_series),
            "market_id": ctx.market_id, "event_id": ctx.event_id,
            "station_icao": ctx.station_icao, "station_tz": ctx.station_tz,
        },
    )


def try_settle(obs: Iterable[Observation], ctx: MarketContext,
               asof: datetime | None = None) -> tuple[SettlementResult | None, str | None]:
    """`settle` without the exception: returns (result, None) or (None, reason).

    For callers that classify a whole catalogue and need the refusal reason as
    data — the paper cycle's settle stage, and `markets_excluded`."""
    try:
        return settle(obs, ctx, asof), None
    except SettlementUnavailable as exc:
        return None, exc.reason


def band_key_wins(band_label: str, band_key: int, unit: str | None = None) -> bool:
    """Did the settled band_key land inside this band label?

    Uses `resolution.parse_band`, so the open-ended 'or below' / 'or higher' bands
    are handled by the same code that built them. Bounds are INCLUSIVE, matching
    parse_band's contract."""
    lo, hi = res.parse_band(band_label, unit)
    if lo is not None and band_key < lo:
        return False
    if hi is not None and band_key > hi:
        return False
    return True
