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
    assert obs.station_series("EHAM") == (obs.SERIES_1C, "C", 1.0)


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
