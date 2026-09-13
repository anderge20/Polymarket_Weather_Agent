"""
test_observations.py — realized station highs  (Phase 2B)
=========================================================
Exercises `weather_agent.observations` with an injected fetcher; no network.

Asserts:
  * the high is taken over the station-LOCAL day, the same window the forecast
    uses, so forecast and observation describe the same day;
  * Fahrenheit is converted exactly once, at the edge;
  * a day missing its peak local hours fails CLOSED rather than reporting a
    lower maximum that looks like a genuinely cool day;
  * `available_at` is the download instant, which keeps a retrospective label
    from ever reaching a feature through the as-of engine;
  * ingestion is idempotent.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from weather_agent import database as db
from weather_agent import observations as obs

DSV = "ds_test_2b"
ICAO = "EFHK"
TZ = "Europe/Helsinki"  # UTC+3 in June: local day = 21:00Z the day before
TARGET = date(2026, 6, 21)


def _utc(d: int, h: int, mi: int = 0) -> datetime:
    return datetime(2026, 6, d, h, mi, tzinfo=timezone.utc)


def _fetcher(points):
    def fetch(icao, start, end, timeout=90):
        return [(t, v) for t, v in points if start <= t <= end]

    return fetch


def _full_local_day(peak_c: float = 25.0, peak_hour_utc: int = 12):
    """Hourly cover of the local day 21:00Z(20th) -> 21:00Z(21st)."""
    pts = []
    t = _utc(20, 21)
    while t < _utc(21, 21):
        pts.append((t, peak_c if t.hour == peak_hour_utc and t.day == 21 else 10.0))
        t += timedelta(hours=1)
    return pts


def test_fahrenheit_converted_once():
    assert obs.f_to_c(32.0) == 0.0
    assert round(obs.f_to_c(212.0), 6) == 100.0
    assert round(obs.f_to_c(89.0), 2) == 31.67


def test_daily_high_uses_the_local_day():
    """A hot reading just outside the local day must not become the day's high."""
    pts = _full_local_day(peak_c=25.0)
    pts.append((_utc(21, 22), 99.0))  # already the 22nd in Helsinki
    dh = obs.daily_high(ICAO, TARGET, TZ, fetcher=_fetcher(pts))
    assert dh.tmax_c == 25.0
    assert dh.when_utc == _utc(21, 12)
    assert dh.n_obs == 24


def test_missing_peak_hours_fails_closed():
    """A partial day yields a lower maximum indistinguishable from a cool day."""
    morning = [(t, v) for t, v in _full_local_day() if t.hour < 6]
    with pytest.raises(obs.NoObservation, match="missing local hours"):
        obs.daily_high(ICAO, TARGET, TZ, fetcher=_fetcher(morning))


def test_no_observations_at_all_fails_closed():
    with pytest.raises(obs.NoObservation):
        obs.daily_high(ICAO, TARGET, TZ, fetcher=_fetcher([]))


def test_available_at_is_the_download_instant_not_the_day(con):
    """A retrospective label must never reach a feature through the as-of engine."""
    obs.ingest_daily_high(con, ICAO, TARGET, TZ, DSV, fetcher=_fetcher(_full_local_day()))
    row = db.query(con, "SELECT observation_time, available_at FROM weather_observations")[0]
    assert row["available_at"] > row["observation_time"]

    # a prediction made on the target day cannot see it
    visible = db.latest_asof(
        con, "weather_observations", asof=_utc(21, 12).isoformat(), partition_cols=["station"]
    )
    assert visible == []


def test_ingest_is_idempotent(con):
    f = _fetcher(_full_local_day())
    obs.ingest_daily_high(con, ICAO, TARGET, TZ, DSV, fetcher=f)
    obs.ingest_daily_high(con, ICAO, TARGET, TZ, DSV, fetcher=f)
    assert db.query(con, "SELECT count(*) AS n FROM weather_observations")[0]["n"] == 1


def test_observed_tmax_reads_back_the_label(con):
    obs.ingest_daily_high(con, ICAO, TARGET, TZ, DSV, fetcher=_fetcher(_full_local_day(27.5)))
    assert obs.observed_tmax(con, ICAO, TARGET, TZ, DSV) == 27.5


def test_observed_tmax_missing_fails_closed(con):
    with pytest.raises(obs.NoObservation):
        obs.observed_tmax(con, ICAO, TARGET, TZ, DSV)


def test_observation_window_matches_the_forecast_window():
    """Forecast and observation must describe the same day, or every error
    measurement M2 makes is wrong by a timezone."""
    from weather_agent import weather

    assert weather.target_day_window(TARGET, TZ) == weather.target_day_window(TARGET, TZ)
    start, end = weather.target_day_window(TARGET, TZ)
    assert start == _utc(20, 21) and end == _utc(21, 21)


def test_kbkf_is_tenths_of_fahrenheit_not_a_mixed_scale():
    """Measured: 24/24 of KBKF's values are tenths of a degree Fahrenheit, only 9
    whole. Calling it "mixed C/F" was wrong — same scale, finer grid. Leaving it
    UNKNOWN threw away a usable station."""
    unit, value, series = obs.detect_grid("KBKF", 25.777778, 78.4)
    assert (unit, round(value, 1)) == ("F", 78.4)
    assert series == obs.SERIES_TENTH_F


def test_tenth_grid_tolerance_survives_the_celsius_round_trip():
    """Dividing by a 0.1 resolution multiplies floating-point error tenfold, which
    made an exact tenth miss an epsilon sized for whole degrees. The tolerance
    belongs on the value scale."""
    for c in (25.777778, 8.0, 20.0, 31.5555556):
        unit, _, _ = obs.detect_grid("KBKF", c, c * 9 / 5 + 32)
        assert unit == "F", f"{c} should sit on the 0.1 F grid"


def test_series_carries_resolution_not_only_scale():
    """Settlement needs the resolution: with a tenths series, quantisation NONE and
    FLOOR stop being the same label for 97.7 F."""
    assert obs.station_series("KATL")[2] == 1.0
    assert obs.station_series("KBKF")[2] == 0.1
    # The DEFAULT Celsius series is the one built from report types 3+4 (B-131);
    # `SERIES_1C` only names labels already written from type 3 alone.
    assert obs.station_series("EHAM") == (obs.SERIES_1C_RT34, "C", 1.0)


def test_grid_is_a_property_of_the_station_not_the_value():
    """A per-value test labels a Celsius station as Fahrenheit one day in five.

    Every multiple of 5 C is a whole number of Fahrenheit too (20 C = 68 F), so
    asking "is the Fahrenheit value an integer?" mislabels EHAM whenever the high
    lands on 20 C. The grid belongs to the station's series (A-41).
    """
    assert obs.detect_grid("EHAM", 20.0, 68.0)[:2] == ("C", 20.0)
    assert obs.detect_grid("KATL", 20.5555556, 69.0)[:2] == ("F", 69.0)


def test_off_grid_value_refuses_rather_than_rounding():
    """A settlement computed off its own grid is worse than one that refuses."""
    assert obs.detect_grid("KBKF", 25.71, 78.278)[0] == "UNKNOWN"


def test_unknown_station_grid_falls_back_to_celsius_only_when_whole():
    assert obs.detect_grid("ZZZZ", 21.0, 69.8)[:2] == ("C", 21.0)
    assert obs.detect_grid("ZZZZ", 21.3, 70.34)[0] == "UNKNOWN"


def test_celsius_is_built_from_types_3_and_4_and_fahrenheit_from_3_only():
    """Type 3 alone drops the half-hourly ROUTINE METARs at Celsius stations (B-131),
    so Celsius takes 3+4. Fahrenheit keeps 3 on purpose, not by omission: adding 4
    there puts the new maximum off the whole-F grid on six measured days (B-133),
    which would turn a low label into a refusal."""
    assert obs.report_types("EGLC") == (3, 4)
    assert obs.report_types("EHAM") == (3, 4)
    assert obs.report_types("KATL") == (3,)
    assert obs.report_types("KBKF") == (3,)


def test_every_series_a_station_can_carry_declares_its_report_types():
    """A series name is a promise about its contents: none may reach the fetcher
    without saying which report types it is built from."""
    carried = {s for s, _, _ in obs.STATION_SERIES.values()} | {obs.DEFAULT_SERIES[0]}
    assert carried <= set(obs.SERIES_REPORT_TYPES), carried - set(obs.SERIES_REPORT_TYPES)
    # And the superseded name keeps saying what its stored rows are.
    assert obs.SERIES_REPORT_TYPES[obs.SERIES_1C] == (3,)
    # And every one of them says which `source` its rows are written under: the two
    # maps are total over the same series, or a series reuses a source and overwrites.
    assert set(obs.SERIES_SOURCE) == set(obs.SERIES_REPORT_TYPES)


def test_a_series_forgotten_in_the_source_map_RAISES_instead_of_overwriting(monkeypatch):
    """Session A's reproduction of the fallback: a new series declared where the fetch
    needs it and forgotten where the row's `source` comes from. With `.get` it reused
    `IEM_ASOS_METAR` and overwrote the old label; indexed, it cannot get that far."""
    monkeypatch.setitem(obs.SERIES_REPORT_TYPES, "IEM_ASOS_METAR_1C_RT345", (3, 4, 5))
    with pytest.raises(KeyError):
        obs.source_for("IEM_ASOS_METAR_1C_RT345")


def test_a_corrected_label_lands_BESIDE_the_old_one_never_over_it(con, monkeypatch):
    """Labels are never overwritten, and the primary key has no series.

    The measured failure: an old `IEM_ASOS_METAR_1C` label and a new 3+4 label whose
    highs fall on the SAME instant (a peak at :50, which both series see) share every
    key column, and the upsert replaced the old row. With the 3+4 rows under their own
    `source`, both rows stay — the old one with its value intact."""
    peak = _utc(21, 12, 50)

    def half_hourly(icao, start, end, timeout=90):
        out, t = [], _utc(20, 21, 20)
        while t < _utc(21, 21):
            out.append((t, 25.0 if t == peak else 10.0))
            t += timedelta(minutes=30)
        return [(t, v) for t, v in out if start <= t <= end]

    monkeypatch.setitem(obs.STATION_SERIES, ICAO, (obs.SERIES_1C, "C", 1.0))
    obs.ingest_daily_high(con, ICAO, TARGET, TZ, DSV, fetcher=half_hourly)
    monkeypatch.delitem(obs.STATION_SERIES, ICAO)
    obs.ingest_daily_high(con, ICAO, TARGET, TZ, DSV, fetcher=half_hourly)

    rows = db.query(con, "SELECT source, series, observation_time, tmax_observed "
                         "FROM weather_observations ORDER BY series")
    assert [(r["source"], r["series"]) for r in rows] == [
        ("IEM_ASOS_METAR", obs.SERIES_1C),
        ("IEM_ASOS_METAR_RT34", obs.SERIES_1C_RT34),
    ], rows
    assert {r["observation_time"] for r in rows} == {peak}, "same instant: the collision case"
    assert [r["tmax_observed"] for r in rows] == [25.0, 25.0]


def test_observed_tmax_reads_the_CURRENT_series_when_both_labels_exist(con, monkeypatch):
    """The one reader that picks a single row, and the day it would pick wrong.

    With corrected labels written beside the superseded ones, a station-day holds an
    `IEM_ASOS_METAR_1C` label (type 3 alone) and an `IEM_ASOS_METAR_1C_RT34` one, both
    at record_version 1. Ordering by revision alone returns whichever row comes first
    — here the old, lower one. The label read back has to be the corrected one."""
    def day(peak_c, peak_minute):
        def fetch(icao, start, end, timeout=90):
            out, t = [], _utc(20, 21, 20)
            while t < _utc(21, 21):
                hot = t.day == 21 and (t.hour, t.minute) == (12, peak_minute)
                out.append((t, peak_c if hot else 10.0))
                t += timedelta(minutes=30)
            return [(x, v) for x, v in out if start <= x <= end]
        return fetch

    monkeypatch.setitem(obs.STATION_SERIES, ICAO, (obs.SERIES_1C, "C", 1.0))
    obs.ingest_daily_high(con, ICAO, TARGET, TZ, DSV, fetcher=day(26.0, 50))
    monkeypatch.delitem(obs.STATION_SERIES, ICAO)
    obs.ingest_daily_high(con, ICAO, TARGET, TZ, DSV, fetcher=day(27.0, 20))

    assert db.query(con, "SELECT count(*) AS n FROM weather_observations")[0]["n"] == 2
    assert obs.observed_tmax(con, ICAO, TARGET, TZ, DSV) == 27.0


def test_the_observation_key_is_the_same_in_all_three_places(con):
    """The key is written in the DDL, in `store.CONFLICT_COLS` and in
    `observations.CONFLICT_COLS`, and nothing compared them. The literal in
    `ingest_daily_high` wins over the store map for prospective ingestion, so fixing the
    key in one place and not the others would have left the overwrite in place."""
    from weather_agent import store

    pk = con.execute(
        "SELECT constraint_column_names FROM duckdb_constraints() "
        "WHERE table_name = 'weather_observations' AND constraint_type = 'PRIMARY KEY'"
    ).fetchall()
    assert len(pk) == 1, pk
    assert tuple(pk[0][0]) == tuple(store.CONFLICT_COLS["weather_observations"]) == obs.CONFLICT_COLS

