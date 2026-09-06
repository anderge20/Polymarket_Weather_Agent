"""
test_weather_asof.py — weather as-of  (Phase 2B: IMPLEMENTED)
=============================================================
Was a PENDING stub in 2A. Now exercises `weather_agent.weather` against the real
2A schema, with an injected fetcher so no test touches the network.

Asserts the frozen contract:
  * "The forecast known as of T" filters on `available_at` (issue + L_MAX), never
    on `issue_time` and never on `ingestion_timestamp`.
  * A later re-issue does not leak in; the latest *available* run wins.
  * Publication latency is NOT equalised between models (V2 §2): ICON's earlier
    availability is a real operational property.
  * An observation may not feed a prediction whose cutoff precedes its availability.
  * The daily high is taken over the station-LOCAL calendar day.
  * Everything fails closed.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from weather_agent import database as db
from weather_agent import weather

DSV = "ds_test_2b"
ICAO = "EFHK"  # Helsinki: in the canonical snapshot, and not on UTC
TZ = "Europe/Helsinki"
TARGET = date(2026, 6, 21)


def _utc(y, mo, d, h, mi=0) -> datetime:
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)


def _series_for_day(temps_by_hour_utc: dict[int, float], day=TARGET) -> dict[str, float]:
    """Hourly UTC series spanning the day before, the day, and the day after."""
    out = {}
    base = datetime(day.year, day.month, day.day, tzinfo=timezone.utc) - timedelta(days=1)
    for i in range(72):
        t = base + timedelta(hours=i)
        out[t.strftime("%Y-%m-%dT%H:%M")] = temps_by_hour_utc.get(i, 10.0)
    return out


def _fetcher(series):
    def fetch(lat, lon, model, issue_time, **kw):
        return {"cell_lat": lat, "cell_lon": lon, "elevation": 0.0, "series": series}

    return fetch


# --------------------------------------------------------------------------
# availability: the rule that makes as-of correct
# --------------------------------------------------------------------------


def test_available_at_is_issue_plus_max_latency():
    run = _utc(2026, 6, 21, 6)
    assert weather.available_at(run, "icon_seamless") == run + timedelta(hours=4.76)
    assert weather.available_at(run, "ecmwf_ifs025") == run + timedelta(hours=8.78)


def test_latency_is_not_equalised_between_models():
    """V2 §2: the faster publication is a real operational advantage, kept as such."""
    run = _utc(2026, 6, 21, 6)
    assert weather.available_at(run, "icon_seamless") < weather.available_at(
        run, "ecmwf_ifs025"
    )


def test_unknown_model_latency_fails_closed():
    with pytest.raises(weather.UnknownModelLatency):
        weather.available_at(_utc(2026, 6, 21, 6), "some_new_model")


def test_naive_issue_time_rejected():
    with pytest.raises(ValueError):
        weather.available_at(datetime(2026, 6, 21, 6), "icon_seamless")


def test_run_not_yet_published_is_not_available():
    run = _utc(2026, 6, 21, 6)
    assert not weather.is_available_at(run, "icon_seamless", _utc(2026, 6, 21, 10))
    assert weather.is_available_at(run, "icon_seamless", _utc(2026, 6, 21, 11))


# --------------------------------------------------------------------------
# as-of selection
# --------------------------------------------------------------------------


@pytest.fixture
def two_runs(con):
    """The 00z and the 06z run of the same target date, both ingested."""
    s = _series_for_day({})
    for h, tmax in ((0, 20.0), (6, 22.0)):
        series = dict(s)
        # put the day's high inside the local day of TARGET
        series["2026-06-21T12:00"] = tmax
        weather.ingest_run(
            con, ICAO, TARGET, TZ, _utc(2026, 6, 21, h), DSV, fetcher=_fetcher(series)
        )
    return con


def test_forecast_asof_returns_only_past_issues(two_runs):
    """At T only runs already published may be seen; the 06z run is not yet out."""
    # 06z becomes available at 10:45:36; at 10:00 only the 00z run (avail 04:45) exists.
    row = weather.forecast_asof(two_runs, ICAO, TARGET, _utc(2026, 6, 21, 10), dataset_version=DSV)
    assert row["forecast_tmax"] == 20.0

    # after 10:45:36 the fresher run wins
    later = weather.forecast_asof(
        two_runs, ICAO, TARGET, _utc(2026, 6, 21, 11), dataset_version=DSV
    )
    assert later["forecast_tmax"] == 22.0


def test_asof_before_any_publication_fails_closed(two_runs):
    with pytest.raises(weather.NoForecastAsOf):
        weather.forecast_asof(two_runs, ICAO, TARGET, _utc(2026, 6, 21, 2), dataset_version=DSV)


def test_asof_filters_on_available_at_not_issue_time(two_runs):
    """The 06z run exists and its issue_time <= T, yet it must NOT be selected at 10:00."""
    rows = db.query(
        two_runs,
        "SELECT issue_time, available_at FROM weather_forecasts ORDER BY issue_time",
    )
    assert len(rows) == 2
    t = _utc(2026, 6, 21, 10)
    # both runs were *issued* before T ...
    assert all(str(r["issue_time"]) <= t.isoformat() for r in rows)
    # ... but only one was *available*, and that is the one as-of returns
    row = weather.forecast_asof(two_runs, ICAO, TARGET, t, dataset_version=DSV)
    assert row["forecast_tmax"] == 20.0


def test_ingest_is_idempotent(con):
    series = dict(_series_for_day({}))
    series["2026-06-21T12:00"] = 21.0
    f = _fetcher(series)
    weather.ingest_run(con, ICAO, TARGET, TZ, _utc(2026, 6, 21, 0), DSV, fetcher=f)
    weather.ingest_run(con, ICAO, TARGET, TZ, _utc(2026, 6, 21, 0), DSV, fetcher=f)
    n = db.query(con, "SELECT count(*) AS n FROM weather_forecasts")[0]["n"]
    assert n == 1


# --------------------------------------------------------------------------
# the observation side
# --------------------------------------------------------------------------


def test_observation_not_used_before_it_exists(con):
    """An observation must not feed a prediction whose cutoff precedes availability.

    The daily high physically *occurs* during the day; it only becomes available
    after the station reports it. Reading it at the prediction cutoff would be
    reading the answer.
    """
    occurred = _utc(2026, 6, 21, 13)  # when the high happened
    published = _utc(2026, 6, 22, 1)  # when it became available
    db.insert(
        con,
        "weather_observations",
        {
            "observation_time": occurred.isoformat(),
            "station": ICAO,
            "source": "unit_test",
            "tmax_observed": 24.0,
            "daily_high_time": occurred.isoformat(),
            "available_at": published.isoformat(),
            "dataset_version": DSV,
            "record_version": 1,
        },
    )
    cutoff = _utc(2026, 6, 21, 12)  # prediction time, before the high even occurred
    visible = db.latest_asof(
        con, "weather_observations", asof=cutoff.isoformat(), partition_cols=["station"]
    )
    assert visible == []

    after = db.latest_asof(
        con,
        "weather_observations",
        asof=_utc(2026, 6, 22, 2).isoformat(),
        partition_cols=["station"],
    )
    assert after and after[0]["tmax_observed"] == 24.0


# --------------------------------------------------------------------------
# the target-day window
# --------------------------------------------------------------------------


def test_window_is_the_station_local_day_not_utc():
    start, end = weather.target_day_window(TARGET, TZ)
    # Helsinki is UTC+3 in June: the local day starts at 21:00 UTC the day before
    assert start == _utc(2026, 6, 20, 21)
    assert end == _utc(2026, 6, 21, 21)


def test_tmax_is_taken_over_the_local_day():
    series = dict(_series_for_day({}))
    series["2026-06-21T22:00"] = 99.0  # outside the local day (already the 22nd there)
    series["2026-06-21T12:00"] = 25.0  # inside
    tmax, n = weather.tmax_from_series(series, TARGET, TZ)
    assert tmax == 25.0
    assert n == 24


def test_run_not_covering_the_day_fails_closed():
    """A partial window would silently report a lower high; refuse instead."""
    with pytest.raises(weather.WeatherIngestError):
        weather.tmax_from_series({"2026-06-25T00:00": 12.0}, TARGET, TZ)


# --------------------------------------------------------------------------
# canonical coordinates (D1)
# --------------------------------------------------------------------------


def test_station_snapshot_matches_frozen_hash():
    from weather_agent import stations

    assert len(stations.load()) == 55
    st = stations.get(ICAO)
    assert (round(st.lat, 3), round(st.lon, 3)) == (60.327, 24.957)


def test_unknown_station_refuses_to_guess():
    from weather_agent import stations

    with pytest.raises(stations.UnknownStation):
        stations.get("ZZZZ")


def test_verified_sensor_scope_is_eleven_stations():
    """D6: the sensor premise is verified for 11 of 55, not universally."""
    from weather_agent import stations

    assert len(stations.VERIFIED_SENSOR) == 11
    assert not stations.get("ZSQD").verified_sensor
    assert stations.get("KATL").verified_sensor
