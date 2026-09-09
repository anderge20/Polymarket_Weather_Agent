"""
test_labels.py — R14: realized-outcome labels

The fixture ADDS the migration-4 columns itself rather than skipping when they are
absent. Session A's settle tests hit exactly this: if the only path a suite
exercises is the SKIP branch, the suite certifies the skip.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from weather_agent import database as db
from weather_agent import labels
from weather_agent import settlement as st

DSV = "ds_test_r14"
MARKET = "m1"
YES, NO = "tok_yes", "tok_no"


@pytest.fixture
def con():
    c = db.init_db(db.connect(":memory:"))
    # simulate the not-yet-merged substrate so the real path is exercised
    # Idempotent by construction: every column is added only if absent, so the
    # fixture works whether or not the migration that adds it has landed. An
    # unconditional ALTER is a bet on merge order.
    for table, cols in (
        ("weather_observations", (("observed_unit", "VARCHAR"),
                                  ("observed_value", "DOUBLE"),
                                  ("series", "VARCHAR"))),
        ("markets", (("contract_source", "VARCHAR"),)),
    ):
        have = set(db.column_names(c, table))
        for col, typ in cols:
            if col not in have:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
    try:
        yield c
    finally:
        c.close()


def test_missing_substrate_names_the_columns(monkeypatch):
    """A caller that cannot run should be told which column to add, not left to
    discover it. This is how markets.contract_source was found missing.

    The absence is SIMULATED rather than asserted against a live schema. Asserting
    "this column is missing" makes the test a hostage of every other branch: the
    moment someone adds it, a green test turns red for a reason that is not a
    defect. That is precisely what broke six of session A's tests when my
    migration 4 landed, and what broke this one when their PR #7 added
    contract_source. A test must not encode the absence of work someone else may
    legitimately do.

    DROP COLUMN is not an option either — DuckDB refuses while an index depends on
    a later column — so the reader is patched instead.
    """
    c = db.init_db(db.connect(":memory:"))
    real = db.column_names
    hidden = {"contract_source", "observed_value"}

    def without_hidden(con, table):
        return [col for col in real(con, table) if col not in hidden]

    monkeypatch.setattr(db, "column_names", without_hidden)
    monkeypatch.setattr(labels.db, "column_names", without_hidden)
    missing = labels.missing_substrate(c)
    assert "markets.contract_source" in missing
    assert "weather_observations.observed_value" in missing
    c.close()


def test_ready_substrate_reports_nothing_missing(con):
    assert labels.missing_substrate(con) == []


def _obs(con, station="KLGA", value=69.0, unit="F"):
    db.insert(con, "weather_observations", {
        "observation_time": datetime(2026, 6, 21, 18, tzinfo=timezone.utc).isoformat(),
        "station": station, "source": "unit_test", "tmax_observed": 20.5555,
        "observed_value": value, "observed_unit": unit,
        "series": "IEM_ASOS_TMPF_1F",
        "available_at": datetime(2026, 6, 23, tzinfo=timezone.utc).isoformat(),
        "dataset_version": DSV, "record_version": 1,
    })


def test_refusal_is_recorded_as_data_with_its_reason(con):
    """When the operator declines, the market is unlabelled WITH the reason.
    Guessing a winner from the last traded price would make the ledger fiction."""
    _obs(con)
    market = {"market_id": MARKET, "event_id": "e1", "contract_source": "",
              "measurement_rule": "", "unit": "F", "station_identifier": "KLGA"}
    rows = labels.label_market(con, market, date(2026, 6, 21),
                               [(YES, "69F"), (NO, None)], DSV)
    assert {r.label for r in rows} == {labels.LABEL_UNLABELLED}
    assert all(r.reason for r in rows), "a refusal must carry its reason"


def test_market_without_station_is_unlabelled_not_guessed(con):
    market = {"market_id": MARKET, "event_id": "e1", "contract_source": "x",
              "measurement_rule": "y", "unit": "F", "station_identifier": None}
    rows = labels.label_market(con, market, date(2026, 6, 21),
                               [(YES, "69F"), (NO, None)], DSV)
    assert [r.reason for r in rows] == ["no_station_identifier"] * 2


def test_persist_leaves_unlabelled_as_null(con):
    """An unlabelled outcome keeps is_winner NULL, which reads as unknown — never
    as False, which would read as 'lost'."""
    db.insert(con, "outcomes", {
        "market_id": MARKET, "token_id": YES, "outcome_index": 0,
        "band_label": "69F", "dataset_version": DSV, "record_version": 1,
    })
    n = labels.persist(con, [labels.LabelRow(MARKET, YES, labels.LABEL_UNLABELLED,
                                             None, None, "series_mismatch")], DSV)
    assert n == 0
    row = db.query(con, "SELECT is_winner FROM outcomes WHERE token_id = ?", [YES])[0]
    assert row["is_winner"] is None


def test_persist_writes_a_settled_verdict(con):
    db.insert(con, "outcomes", {
        "market_id": MARKET, "token_id": YES, "outcome_index": 0,
        "band_label": "69F", "dataset_version": DSV, "record_version": 1,
    })
    n = labels.persist(con, [labels.LabelRow(MARKET, YES, labels.LABEL_WINNER,
                                             69, 69.0, None)], DSV)
    assert n == 1
    assert db.query(con, "SELECT is_winner FROM outcomes WHERE token_id = ?",
                    [YES])[0]["is_winner"] is True


def test_no_token_pays_when_the_band_did_not_occur():
    """The NO token is the complement of the YES band, not a band of its own."""
    assert st.band_key_wins("69F", 69, "F") is True
    assert st.band_key_wins("69F", 70, "F") is False


def test_observations_use_the_source_grid_not_the_celsius_column(con):
    """Settling a Fahrenheit market on the converted Celsius value settles it off
    its own grid (A-41)."""
    _obs(con, value=69.0, unit="F")
    obs = labels.observations_for(con, "KLGA", DSV)
    assert len(obs) == 1
    assert (obs[0].value, obs[0].unit) == (69.0, "F")


def test_unknown_grid_observations_are_excluded(con):
    """A reading that does not sit on its station's grid cannot settle anything."""
    _obs(con, value=20.3, unit="UNKNOWN")
    assert labels.observations_for(con, "KLGA", DSV) == []
