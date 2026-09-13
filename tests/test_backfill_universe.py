"""The one selection both backfills use. Every guarantee in its docstring is pinned here.

The defect this replaces kept the three lowest market ids of each target date and
stored 1 028 of 1 464 events truncated to their lowest bands (B-136)."""
from __future__ import annotations

import pytest

from weather_agent import backfill_universe as bu


def _event(event_id, station, day, n_bands, first_market=1000):
    return [
        {"event_id": str(event_id), "market_id": str(first_market + i),
         "station_identifier": station, "city": "x",
         "endDate": f"{day}T12:00:00Z", "clobTokenIds": '["y","n"]'}
        for i in range(n_bands)
    ]


def _catalog():
    return (_event(321062, "EGLC", "2026-04-02", 11, 1773885)
            + _event(341797, "EGLC", "2026-04-08", 11, 1854400)
            + _event(500666, "EDDM", "2026-05-21", 11, 2299303)
            + _event(600000, None, "2026-05-21", 9, 2400000))


def _sizes(selection):
    out = {}
    for m in selection.rows:
        out[m["event_id"]] = out.get(m["event_id"], 0) + 1
    return out


def test_a_chosen_event_always_carries_every_one_of_its_bands():
    """The property the old sampling broke: no selection returns part of a ladder."""
    sel = bu.select_events(_catalog(), max_events=2)
    assert sel.events == ["321062", "341797"]
    assert _sizes(sel) == {"321062": 11, "341797": 11}


def test_the_cap_counts_EVENTS_and_says_how_many_it_left_out():
    sel = bu.select_events(_catalog(), max_events=1)
    assert sel.events == ["321062"] and len(sel.rows) == 11
    assert sel.excluded[bu.EXCLUDED_BEYOND_CAP] == 2
    assert sel.excluded[bu.EXCLUDED_NO_STATION] == 1


def test_the_cap_order_is_target_date_then_the_event_id_AS_AN_INTEGER():
    """A string sort puts "1000000" before "900000". Harmless while every id has six
    digits, wrong the day one has seven."""
    rows = _event(1000000, "EGLC", "2026-06-01", 2) + _event(900000, "EGLC", "2026-06-01", 2, 5000)
    assert bu.select_events(rows).events == ["900000", "1000000"]
    later_date_low_id = _event(100000, "EGLC", "2026-06-02", 2, 7000)
    assert bu.select_events(rows + later_date_low_id).events == ["900000", "1000000", "100000"]
    assert bu.Selection(rows=[], events=[]).order == "target_date, int(event_id)"


def test_a_non_numeric_event_id_raises_instead_of_being_sorted_as_text():
    with pytest.raises(ValueError, match="not an integer"):
        bu.select_events(_event("abc", "EGLC", "2026-06-01", 2))


def test_filters_apply_to_whole_events_and_every_exclusion_is_counted():
    sel = bu.select_events(_catalog(), stations=["eglc"], since="2026-04-05", until="2026-05-30")
    assert sel.events == ["341797"] and _sizes(sel) == {"341797": 11}
    assert sel.excluded == {
        bu.EXCLUDED_NO_STATION: 1,
        bu.EXCLUDED_STATION_FILTER: 1,
        bu.EXCLUDED_BEFORE_SINCE: 1,
    }


def test_require_forecast_keeps_only_station_days_that_have_one():
    sel = bu.select_events(_catalog(), forecast_pairs={("EGLC", "2026-04-08")})
    assert sel.events == ["341797"]
    assert sel.excluded[bu.EXCLUDED_NO_FORECAST] == 2


def test_markets_come_back_in_ladder_order_inside_each_event():
    rows = list(reversed(_event(341797, "EGLC", "2026-04-08", 4, 1854400)))
    assert [m["market_id"] for m in bu.select_events(rows).rows] == [
        "1854400", "1854401", "1854402", "1854403"]


def test_an_event_spanning_two_dates_raises_rather_than_being_filed_under_one():
    rows = _event(1, "EGLC", "2026-06-01", 1) + _event(1, "EGLC", "2026-06-02", 1, 2000)
    with pytest.raises(ValueError, match="several target dates"):
        bu.select_events(rows)


def test_the_summary_a_dry_run_prints_counts_events_markets_and_unpriceable_bands():
    rows = _catalog()
    rows[0]["clobTokenIds"] = None
    s = bu.summarize(bu.select_events(rows))
    assert (s["events"], s["markets"], s["markets_without_clob_token_ids"]) == (3, 33, 1)
    assert s["by_station"] == {"EDDM": 1, "EGLC": 2}
    assert s["by_month"] == {"2026-04": 2, "2026-05": 1}
    assert s["order"] == bu.ORDER and s["excluded"] == {bu.EXCLUDED_NO_STATION: 1}


def test_a_NULL_station_read_through_DuckDB_is_no_station(tmp_path):
    """Through the real read path: `fetchdf()` decides the type of a NULL VARCHAR, and
    the first run against the real catalogue crashed on it (it came back as float NaN).
    A hand-written NaN would pass for the reason the author had in mind; this one
    passes for whatever pandas actually returns."""
    import duckdb

    path = tmp_path / "cat.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE mk (market_id VARCHAR, event_id VARCHAR, station_identifier VARCHAR, "
                "city VARCHAR, endDate VARCHAR, clobTokenIds VARCHAR)")
    con.execute("INSERT INTO mk VALUES ('1','700000',NULL,'x','2026-06-01T12:00:00Z',NULL), "
                "('2','700001','EGLC','x','2026-06-01T12:00:00Z','[\"y\",\"n\"]')")
    con.close()

    rows = bu.load_catalog_rows(str(path))
    sel = bu.select_events(rows, stations=["EGLC"])
    assert sel.events == ["700001"]
    assert sel.excluded == {bu.EXCLUDED_NO_STATION: 1}
    assert bu.summarize(bu.select_events(rows))["markets_without_clob_token_ids"] == 0

