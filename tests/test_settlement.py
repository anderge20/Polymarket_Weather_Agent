"""Tests for weather_agent.settlement — the frozen SettlementOperator core.

These are written against `SETTLEMENT_OPERATOR_CORE.v3.md`, not against the
implementation: each test names the section it pins. The core is frozen, so a test
failing here means either the code drifted or the document was amended — never
that the test should be relaxed.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from weather_agent import settlement as st
from weather_agent.polymarket import resolution as res


UTC = timezone.utc
D = date(2026, 9, 10)


def _obs(hour, value, *, series=st.SERIES_METAR_C, unit="C", available_at=None,
         day=D, rv=1):
    return st.Observation(
        ts_utc=datetime.combine(day, datetime.min.time(), tzinfo=UTC)
        + timedelta(hours=hour),
        value=value, unit=unit, series=series, available_at=available_at,
        record_version=rv,
    )


def _ctx(**over):
    base = dict(
        market_id="m1", event_id="e1", contract_source=res.SRC_NOAA,
        measurement_rule_code=res.P_NOAA_TEMPCOL, unit="C",
        rounding_rule="whole degree", target_date=D,
        station_icao="EGLC", station_tz="Europe/London",
    )
    base.update(over)
    return st.MarketContext(**base)


# =============================================================================
# §3 — the enablement table: 4 enabled, 7 fail-closed classes
# =============================================================================
@pytest.mark.parametrize("source,rule,unit,op_id", [
    (res.SRC_WU, res.P_WU_DAILYOBS, "C", "WU_DAILYOBS_C_PROXY_IEM"),      # 5
    (res.SRC_NOAA, res.P_NOAA_TEMPCOL, "C", "NOAA_TEMPCOL_C_PROXY_IEM"),  # 7
    (res.SRC_NOAA, res.P_NOAA_TEMPCOL, "F", "NOAA_TEMPCOL_F_PROXY_IEM"),  # 8
    (res.SRC_HKO, res.P_HKO_ABSMAX, "C", "HKO_ABSMAX_INTERVAL_FLOOR"),    # 10
])
def test_the_four_enabled_strata_resolve_to_their_operator(source, rule, unit, op_id):
    assert st.select_operator(source, rule, unit).operator_id == op_id


@pytest.mark.parametrize("source,rule,unit,reason", [
    (res.SRC_WU, res.P_WU_GENERIC, "C", st.R_Y_UNDEFINED),              # 1
    (res.SRC_WU, res.P_WU_GENERIC, "F", st.R_Y_UNDEFINED),              # 2
    (res.SRC_WU, res.P_BY_FORECAST, "C", st.R_BY_FORECAST),             # 3
    (res.SRC_WU, res.P_BY_FORECAST, "F", st.R_BY_FORECAST),             # 4
    (res.SRC_WU, res.P_WU_DAILYOBS, "F", st.R_PROXY_NOT_AUDITED_F),     # 6
    (res.SRC_NOAA, res.P_NOAA_HOURLY, "F", st.R_SERIES_FILTER_UNVERIFIED),  # 9
])
def test_each_fail_closed_stratum_dies_of_its_own_reason(source, rule, unit, reason):
    with pytest.raises(st.SettlementUnavailable) as exc:
        st.select_operator(source, rule, unit)
    assert exc.value.reason == reason


def test_stratum_11_carries_both_ternas_with_the_same_reason():
    """v3 says SIN_CLAUSULA/P_UNKNOWN, the D21 parser says CWA/P_CWA_TemperatureColumn
    for the SAME 77 Taipei markets. Listing only one would send the other to
    `context_out_of_snapshot`, which §4 requires to have 0 cases today."""
    for source, rule in ((st.SRC_SIN_CLAUSULA_V3, res.P_UNKNOWN),
                         (res.SRC_CWA, res.P_CWA_TEMPCOL)):
        with pytest.raises(st.SettlementUnavailable) as exc:
            st.select_operator(source, rule, "C")
        assert exc.value.reason == st.R_SOURCE_INACCESSIBLE


def test_a_terna_outside_the_partition_is_terminal():
    with pytest.raises(st.SettlementUnavailable) as exc:
        st.select_operator("BOM", "P_Whatever", "C")
    assert exc.value.reason == st.R_CONTEXT_OUT_OF_SNAPSHOT


def test_the_parsers_UNKNOWN_is_not_v3s_SIN_CLAUSULA():
    """They are different tokens for different things, and conflating them sent
    all 77 Taipei markets to `context_out_of_snapshot`, which §4 requires to have
    zero cases today."""
    assert st.SRC_SIN_CLAUSULA_V3 != res.SRC_UNKNOWN
    with pytest.raises(st.SettlementUnavailable) as exc:
        st.select_operator(res.SRC_UNKNOWN, res.P_UNKNOWN, "C")
    assert exc.value.reason == st.R_CONTEXT_OUT_OF_SNAPSHOT


def test_applies_to_is_pure_in_its_four_arguments():
    """§2: invariant to market_id — which is what lets the stratum be decided
    before the context exists."""
    op = st.OP_NOAA_TEMPCOL_C
    assert op.applies_to(res.SRC_NOAA, res.P_NOAA_TEMPCOL, "C", "whole degree")
    assert op.applies_to(res.SRC_NOAA, res.P_NOAA_TEMPCOL, "C", "tenths")
    assert not op.applies_to(res.SRC_NOAA, res.P_NOAA_TEMPCOL, "F")


def test_there_is_no_default_operator():
    """§4: no default, and quantiles_to_distribution's nearest-integer is
    explicitly forbidden as a fallback."""
    assert len(st.OPERATORS) == 4
    # Look for a CALL, not for the prose that forbids it: the module documents the
    # prohibition, and a naive text search matches its own warning.
    import ast
    tree = ast.parse((__import__("pathlib").Path(st.__file__)).read_text("utf-8"))
    called = {
        n.func.id for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert "round" not in called, "round() is forbidden (§3 b)"


# =============================================================================
# §4 — order of checks: terna -> stratum -> ctx -> clause -> series/window/as-of
# =============================================================================
def test_the_stratum_is_decided_before_the_context():
    """The 77 CWA markets have no ICAO. If the ctx were checked first they would
    die of a missing station instead of `source_inaccessible`."""
    ctx = _ctx(contract_source=res.SRC_CWA, measurement_rule_code=res.P_CWA_TEMPCOL,
               station_icao=None, station_tz=None, target_date=None)
    with pytest.raises(st.SettlementUnavailable) as exc:
        st.settle([], ctx)
    assert exc.value.reason == st.R_SOURCE_INACCESSIBLE


def test_hko_settles_without_a_station_because_it_needs_none():
    """§4: HKO's icao2 is NULL in all 1,859 markets and that is NOT a defect."""
    ctx = _ctx(contract_source=res.SRC_HKO, measurement_rule_code=res.P_HKO_ABSMAX,
               station_icao=None, station_tz=None)
    r = st.settle([_obs(6, 27.4, series=st.SERIES_HKO)], ctx)
    assert r.band_key == 27 and r.window_kind == st.WINDOW_SOURCE_DAILY_ROW


def test_a_local_civil_day_operator_refuses_without_a_station():
    with pytest.raises(st.SettlementUnavailable) as exc:
        st.settle([_obs(12, 20.0)], _ctx(station_icao=None, station_tz=None))
    assert exc.value.reason == st.R_CONTEXT_OUT_OF_SNAPSHOT


def test_missing_target_date_is_terminal_and_never_derived():
    """2D §C: the caller supplies it; the core never derives it."""
    with pytest.raises(st.SettlementUnavailable) as exc:
        st.settle([_obs(12, 20.0)], _ctx(target_date=None))
    assert exc.value.reason == st.R_CONTEXT_OUT_OF_SNAPSHOT


# =============================================================================
# §3/§4 — the lowest-bracket clause
# =============================================================================
def test_strata_5_and_7_refuse_a_market_carrying_the_clause():
    """ZERO markets audited WITH the clause in 5 and 7."""
    for source, rule in ((res.SRC_WU, res.P_WU_DAILYOBS),
                         (res.SRC_NOAA, res.P_NOAA_TEMPCOL)):
        ctx = _ctx(contract_source=source, measurement_rule_code=rule,
                   clause_lowest_bracket=True)
        with pytest.raises(st.SettlementUnavailable) as exc:
            st.settle([_obs(12, 20.0)], ctx)
        assert exc.value.reason == st.R_CLAUSE_NOT_AUDITED


def test_hko_emits_with_the_clause_but_flagged():
    ctx = _ctx(contract_source=res.SRC_HKO, measurement_rule_code=res.P_HKO_ABSMAX,
               station_icao=None, station_tz=None, clause_lowest_bracket=True)
    r = st.settle([_obs(6, 30.0, series=st.SERIES_HKO)], ctx)
    assert r.clause_lowest_bracket is True          # emitted, and flagged


# =============================================================================
# window, aggregation, quantization
# =============================================================================
def test_the_window_is_the_local_civil_day_not_the_utc_day():
    """A reading at 23:30 local on a UTC+13 station belongs to the local day."""
    ctx = _ctx(station_icao="NZWN", station_tz="Pacific/Auckland")
    start, end = st.local_civil_day_window(D, "Pacific/Auckland")
    assert start < datetime.combine(D, datetime.min.time(), tzinfo=UTC)  # starts on D-1 UTC
    assert (end - start) == timedelta(days=1)


def test_a_dst_transition_gives_a_23_or_25_hour_window():
    """Computed through the station's own tz, so the day is not silently 24 h."""
    spring = st.local_civil_day_window(date(2026, 3, 29), "Europe/London")
    assert (spring[1] - spring[0]) == timedelta(hours=23)


def test_the_window_is_half_open_at_the_next_midnight():
    ctx = _ctx(station_tz="UTC", station_icao="XXXX")
    edge = st.Observation(ts_utc=datetime.combine(D + timedelta(days=1),
                                                  datetime.min.time(), tzinfo=UTC),
                          value=99.0, unit="C", series=st.SERIES_METAR_C)
    with pytest.raises(st.SettlementUnavailable) as exc:
        st.settle([edge], ctx)
    assert exc.value.reason == st.R_NO_OBS_IN_WINDOW


def test_max_aggregation_takes_the_daily_high():
    r = st.settle([_obs(6, 12.0), _obs(14, 19.0), _obs(20, 15.0)], _ctx())
    assert r.settled_value == 19.0 and r.n_obs == 3 and r.aggregation == st.AGG_MAX


def test_hko_quantizes_by_interval_floor_not_by_rounding():
    """ceil / half-up / half-even were REFUTED at 164/166."""
    ctx = _ctx(contract_source=res.SRC_HKO, measurement_rule_code=res.P_HKO_ABSMAX,
               station_icao=None, station_tz=None)
    for value, expected in ((27.9, 27), (27.5, 27), (27.0, 27), (-1.2, -2)):
        r = st.settle([_obs(6, value, series=st.SERIES_HKO)], ctx)
        assert r.band_key == expected, value


def test_quantization_none_refuses_an_off_grid_value_instead_of_rounding():
    """NONE means the series already delivers the grid. Rounding is forbidden, so
    an off-grid value is a series problem, not a licence to round."""
    with pytest.raises(st.SettlementUnavailable) as exc:
        st.settle([_obs(12, 19.4)], _ctx())
    assert exc.value.reason == st.R_SERIES_MISMATCH


# =============================================================================
# §2 — series and as-of
# =============================================================================
def test_the_wrong_series_is_refused_not_converted():
    with pytest.raises(st.SettlementUnavailable) as exc:
        st.settle([_obs(12, 68.0, series=st.SERIES_METAR_F, unit="F")], _ctx())
    assert exc.value.reason == st.R_SERIES_MISMATCH


def test_asof_with_a_null_available_at_is_refused():
    """OBSERVED: available_at is None across the whole IEM history, which is why
    the as-of route is closed today for strata 5, 7 and 8."""
    with pytest.raises(st.SettlementUnavailable) as exc:
        st.settle([_obs(12, 20.0, available_at=None)], _ctx(),
                  asof=datetime(2026, 9, 11, tzinfo=UTC))
    assert exc.value.reason == st.R_NOT_AVAILABLE_ASOF


def test_no_asof_means_the_availability_is_declared_unknown():
    r = st.settle([_obs(12, 20.0)], _ctx(), asof=None)
    assert r.availability == st.AVAIL_Y_FINAL_UNKNOWN_ASOF


def test_asof_verified_when_every_observation_carries_availability():
    a = datetime(2026, 9, 10, 18, tzinfo=UTC)
    r = st.settle([_obs(12, 20.0, available_at=a)], _ctx(),
                  asof=datetime(2026, 9, 11, tzinfo=UTC))
    assert r.availability == st.AVAIL_ASOF_VERIFIED


def test_observations_after_the_asof_are_dropped():
    early = _obs(6, 12.0, available_at=datetime(2026, 9, 10, 7, tzinfo=UTC))
    late = _obs(14, 30.0, available_at=datetime(2026, 9, 11, 7, tzinfo=UTC))
    r = st.settle([early, late], _ctx(), asof=datetime(2026, 9, 10, 12, tzinfo=UTC))
    assert r.settled_value == 12.0 and r.n_obs == 1


# =============================================================================
# contract details
# =============================================================================
def test_unavailable_is_not_a_valueerror():
    """§2, and it matters: refusing to settle is the expected outcome for 78 % of
    the catalogue, and a caller catching ValueError must not absorb it."""
    assert not issubclass(st.SettlementUnavailable, ValueError)


def test_a_reason_outside_the_closed_enum_cannot_be_constructed():
    with pytest.raises(AssertionError):
        raise st.SettlementUnavailable("something_i_made_up")


def test_try_settle_returns_the_reason_as_data():
    r, reason = st.try_settle([], _ctx(contract_source=res.SRC_WU,
                                       measurement_rule_code=res.P_BY_FORECAST))
    assert r is None and reason == st.R_BY_FORECAST
    r, reason = st.try_settle([_obs(12, 20.0)], _ctx())
    assert reason is None and r.band_key == 20


def test_the_result_carries_its_provenance():
    r = st.settle([_obs(12, 20.0)], _ctx())
    assert r.label_source == st.LABEL_SOURCE_IEM_METAR
    assert r.compat_status == st.COMPAT_PROXY_AUDITED
    assert r.audit["operator_id"] == "NOAA_TEMPCOL_C_PROXY_IEM"
    r2 = st.settle([_obs(6, 27.4, series=st.SERIES_HKO)],
                   _ctx(contract_source=res.SRC_HKO,
                        measurement_rule_code=res.P_HKO_ABSMAX,
                        station_icao=None, station_tz=None))
    assert r2.compat_status == st.COMPAT_DIRECT          # HKO is not a proxy


# =============================================================================
# band membership
# =============================================================================
@pytest.mark.parametrize("label,key,expected", [
    ("15°C or below", 14, True),
    ("15°C or below", 15, True),
    ("15°C or below", 16, False),
    ("17°C", 17, True),
    ("17°C", 18, False),
    ("23°C or higher", 25, True),
    ("23°C or higher", 22, False),
])
def test_band_membership_handles_the_open_ended_bands(label, key, expected):
    assert st.band_key_wins(label, key, "C") is expected


# =============================================================================
# Regressions from the hostile refutation of PR #6. Each of these FAILS on the
# version that was pushed; none of the original 43 covered them.
# =============================================================================
def test_a_caller_reason_outside_the_enum_is_translated_not_raised():
    """§4 lists `target_date_unresolvable`/`_ambiguous` as the CALLER's and says
    they arrive as `context_out_of_snapshot`. Passing them through raised
    AssertionError, which try_settle does not catch — the operator crashed
    instead of failing closed, in the very function whose job is to return the
    reason as data."""
    ctx = _ctx(fail_closed_reason="target_date_unresolvable")
    r, reason = st.try_settle([], ctx)
    assert r is None and reason == st.R_CONTEXT_OUT_OF_SNAPSHOT


def test_a_caller_reason_inside_the_enum_is_passed_through():
    ctx = _ctx(fail_closed_reason=st.R_NO_OBS_IN_WINDOW)
    r, reason = st.try_settle([_obs(12, 20.0)], ctx)
    assert r is None and reason == st.R_NO_OBS_IN_WINDOW


def test_the_stratum_still_wins_over_a_caller_reason():
    """§4: the stratum is decided BEFORE the ctx, so a stratum-11 market must die
    of `source_inaccessible` even if the caller attached another reason."""
    ctx = _ctx(contract_source=res.SRC_CWA, measurement_rule_code=res.P_CWA_TEMPCOL,
               station_icao=None, station_tz=None,
               fail_closed_reason=st.R_NO_OBS_IN_WINDOW)
    r, reason = st.try_settle([], ctx)
    assert reason == st.R_SOURCE_INACCESSIBLE


def test_hko_never_settles_a_row_from_the_wrong_day():
    """THE WORST ONE: it did not fail closed, it emitted a label from another day.

    HKO publishes in HKT (UTC+8). Deriving a UTC civil-day window and filtering
    with it discarded the row stamped at the source's own midnight for the target
    date (2026-09-09T16:00Z for 2026-09-10) and accepted the NEXT day's row
    instead — in the only DIRECT stratum, and the one that has a holdout."""
    ctx = _ctx(contract_source=res.SRC_HKO, measurement_rule_code=res.P_HKO_ABSMAX,
               station_icao=None, station_tz=None)
    at_hkt_midnight = st.Observation(
        ts_utc=datetime(2026, 9, 9, 16, tzinfo=UTC), value=27.4, unit="C",
        series=st.SERIES_HKO)
    r, reason = st.try_settle([at_hkt_midnight], ctx)
    assert reason is None, "the source's own row for the date must settle"
    assert r.band_key == 27


def test_source_daily_row_reports_a_null_window_rather_than_inventing_one():
    """§2 declares the window bounds nullable, and this is the operator that
    justifies a null: its day boundary is the source's and we cannot derive it."""
    ctx = _ctx(contract_source=res.SRC_HKO, measurement_rule_code=res.P_HKO_ABSMAX,
               station_icao=None, station_tz=None)
    r = st.settle([_obs(6, 27.4, series=st.SERIES_HKO)], ctx)
    assert r.window_start_utc is None and r.window_end_utc is None


def test_a_station_on_a_source_daily_operator_is_refused():
    """§2's 'sii' is a BICONDITIONAL. Accepting a station here recorded it in
    `audit` as if it had participated, when the path ignores it entirely — false
    provenance in the one DIRECT stratum."""
    ctx = _ctx(contract_source=res.SRC_HKO, measurement_rule_code=res.P_HKO_ABSMAX,
               station_icao="VHHH", station_tz="Asia/Hong_Kong")
    r, reason = st.try_settle([_obs(6, 27.4, series=st.SERIES_HKO)], ctx)
    assert r is None and reason == st.R_CONTEXT_OUT_OF_SNAPSHOT


def test_a_superseded_record_version_never_wins_under_max():
    """D17-C ingests a revision WITHOUT overwriting, so the superseded row lives
    on beside its correction. A plain max over both returns the superseded value
    whenever it is the larger — and MAX governs 17,083 of the 18,942 markets with
    an operator."""
    t = datetime(2026, 9, 10, 14, tzinfo=UTC)
    superseded = st.Observation(ts_utc=t, value=31.0, unit="C",
                                series=st.SERIES_METAR_C, record_version=1)
    correction = st.Observation(ts_utc=t, value=19.0, unit="C",
                                series=st.SERIES_METAR_C, record_version=2)
    r = st.settle([superseded, correction], _ctx(station_tz="UTC"))
    assert r.settled_value == 19.0, "the correction must win, not the larger value"
    assert r.n_obs == 1
