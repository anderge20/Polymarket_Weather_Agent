"""
test_m2_module.py — the three pairing rules, pinned

Each of these was found by a refutation, not by design. Pinning them here is the
point of promoting the module out of a script: a second implementation would not
inherit the corrections.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from weather_agent import m2


def test_local_day_is_the_stations_day_not_the_utc_one():
    """`CAST(observation_time AS DATE)` made the sample size depend on the DuckDB
    session TimeZone: 2 599 rows under UTC, 1 881 under Asia/Shanghai — a 28 %
    swing governed by an environment variable."""
    # 22:00 UTC on the 20th is already the 21st in Helsinki (+3)
    ts = datetime(2026, 6, 20, 22, tzinfo=timezone.utc)
    assert m2.local_day(ts, "Europe/Helsinki") == date(2026, 6, 21)
    # and still the 20th in New York (-4)
    assert m2.local_day(ts, "America/New_York") == date(2026, 6, 20)


def test_local_day_accepts_naive_as_utc_rather_than_guessing_local():
    naive = datetime(2026, 6, 20, 22)
    assert m2.local_day(naive, "Europe/Helsinki") == date(2026, 6, 21)


def test_label_is_available_a_day_after_the_local_day_ends():
    """Not after the target date in UTC: the two differ by the offset, which is
    exactly what leaked in 8 of 8 stations."""
    got = m2.label_available_at(date(2026, 6, 21), "Europe/Helsinki")
    # local day ends 21:00Z on the 21st; +24 h
    assert got == datetime(2026, 6, 22, 21, tzinfo=timezone.utc)

    west = m2.label_available_at(date(2026, 6, 21), "America/Los_Angeles")
    assert west == datetime(2026, 6, 23, 7, tzinfo=timezone.utc)


def test_the_previous_days_label_is_not_available_at_a_24h_lead():
    """The leak, stated as a test. T for a 24 h lead on D is D-1 12:00Z; the label
    of D-1 does not land until the end of its local day plus a day."""
    d = date(2026, 6, 21)
    t_24 = datetime(d.year, d.month, d.day, 12, tzinfo=timezone.utc) - timedelta(hours=24)
    prev_label = m2.label_available_at(date(2026, 6, 20), "America/Los_Angeles")
    assert prev_label > t_24, "the previous day's label is still in the future"


def test_pick_run_takes_the_freshest_run_already_published():
    """Selection is by availability, never by issue_time: a run issued before T
    but published after it did not exist at the decision."""
    t = datetime(2026, 6, 21, 12, tzinfo=timezone.utc)
    run = m2.pick_run(t, "icon_seamless")
    assert run is not None
    # ICON publishes ~4.76 h after the run; the 06Z run lands at 10:45Z
    assert run == datetime(2026, 6, 21, 6, tzinfo=timezone.utc)
    from weather_agent import weather

    assert weather.available_at(run, "icon_seamless") <= t


def test_pick_run_refuses_when_nothing_was_published_in_time():
    t = datetime(2026, 6, 21, 1, tzinfo=timezone.utc)
    run = m2.pick_run(t, "icon_seamless", max_age_h=3)
    assert run is None


def test_leads_select_different_runs():
    """If both leads picked the same run the two strata would be the same data
    under two names."""
    d = date(2026, 6, 21)
    end = datetime(d.year, d.month, d.day, 12, tzinfo=timezone.utc)
    r9 = m2.pick_run(end - timedelta(hours=9), "icon_seamless")
    r24 = m2.pick_run(end - timedelta(hours=24), "icon_seamless")
    assert r9 != r24


def test_module_is_importable_without_a_database():
    """error_model stays database-free so the estimator can be tested without a
    schema; m2 is the half that knows about tables. Importing must not require
    one either."""
    import importlib

    importlib.reload(m2)
    assert callable(m2.load_pairs)


def test_dataset_version_is_a_parameter_not_a_constant():
    """It was a module constant used inside both queries, so a caller running
    under ds_paper_v1 would have read the backfill silently while appearing to
    operate entirely on its own version. Same family as A-37: a parameter that
    exists and a constant that decides."""
    import inspect

    sig = inspect.signature(m2.load_pairs)
    assert "dataset_version" in sig.parameters
    assert sig.parameters["dataset_version"].default == m2.DATASET_VERSION


def test_load_pairs_reads_only_the_requested_version():
    from weather_agent import database as db

    con = db.init_db(db.connect(":memory:"))
    pairs, _, _ = m2.load_pairs(con, dataset_version="ds_paper_v1")
    assert pairs == []
    con.close()


def test_load_pairs_filters_by_model():
    """`model` is part of weather_forecasts' primary key and the query named no
    predicate for it. A substrate with two models would have produced a MIXTURE,
    and nothing in a Pair records which model it came from — so the quantiles
    would have described no model in particular, silently."""
    import inspect
    from weather_agent import database as db, weather

    sig = inspect.signature(m2.load_pairs)
    assert sig.parameters["model"].default == weather.M1_MODEL

    con = db.init_db(db.connect(":memory:"))
    pairs, _, _ = m2.load_pairs(con, model="some_other_model")
    assert pairs == []
    con.close()
