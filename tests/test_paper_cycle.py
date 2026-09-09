"""Tests for scripts/paper_cycle.py — offline, no network.

The cycle itself needs gamma and the CLOB, so what is pinned here is the part that
decides WHAT gets persisted and WHICH markets are in scope: the catalogue/ledger
split that keeps the git-backed store from growing without bound, and the universe
filter that must never become a target_date derivation.
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from weather_agent import database, store

_SPEC = importlib.util.spec_from_file_location(
    "paper_cycle", Path(__file__).resolve().parents[1] / "scripts" / "paper_cycle.py")
paper_cycle = importlib.util.module_from_spec(_SPEC)
sys.modules["paper_cycle"] = paper_cycle
_SPEC.loader.exec_module(paper_cycle)


T0 = datetime(2026, 9, 9, 7, 30, tzinfo=timezone.utc)


@pytest.fixture
def con():
    c = database.init_db(database.connect(":memory:"))
    try:
        yield c
    finally:
        c.close()


def _market(con, *, market_id, event_id, end_date, dsv="ds1", station="EGLC"):
    con.execute(
        "INSERT INTO markets (market_id, event_id, station, unit, rounding_rule, "
        "source_timestamps, ingestion_timestamp, dataset_version, record_version) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        [market_id, event_id, station, "C", "whole degree",
         f'{{"endDate":"{end_date}"}}', T0, dsv, 1])
    for i, (tok, label) in enumerate(((f"{market_id}_yes", "Yes"),
                                      (f"{market_id}_no", "No"))):
        con.execute(
            "INSERT INTO outcomes (market_id, token_id, band_label, outcome_index, "
            "outcome_label, ingestion_timestamp, dataset_version, record_version) "
            "VALUES (?,?,?,?,?,?,?,?)",
            [market_id, tok, "15C or below", i, label, T0, dsv, 1])


# --------------------------------------------------------------------------- universe
def test_universe_selects_only_the_callers_target_date(con):
    _market(con, market_id="m1", event_id="e1", end_date="2026-09-10T12:00:00Z")
    _market(con, market_id="m2", event_id="e2", end_date="2026-09-11T12:00:00Z")
    rows = paper_cycle.select_universe(con, dataset_version="ds1",
                                       target_date=date(2026, 9, 10))
    assert {r["market_id"] for r in rows} == {"m1"}
    assert len(rows) == 2                       # both tokens of the market


def test_universe_returns_both_tokens_so_a_fade_can_be_executed(con):
    _market(con, market_id="m1", event_id="e1", end_date="2026-09-10T12:00:00Z")
    rows = paper_cycle.select_universe(con, dataset_version="ds1",
                                       target_date=date(2026, 9, 10))
    assert {r["outcome_label"] for r in rows} == {"Yes", "No"}


def test_universe_ignores_other_dataset_versions(con):
    _market(con, market_id="m1", event_id="e1", end_date="2026-09-10T12:00:00Z",
            dsv="other")
    rows = paper_cycle.select_universe(con, dataset_version="ds1",
                                       target_date=date(2026, 9, 10))
    assert rows == []


def test_a_market_with_an_unparseable_end_date_is_skipped_not_guessed(con):
    _market(con, market_id="m1", event_id="e1", end_date="not-a-date")
    rows = paper_cycle.select_universe(con, dataset_version="ds1",
                                       target_date=date(2026, 9, 10))
    assert rows == []


def test_the_date_boundary_is_taken_in_utc(con):
    """endDate is 12:00Z (R8), comfortably inside the UTC day — but the predicate
    must not drift with the machine's local zone."""
    _market(con, market_id="m1", event_id="e1", end_date="2026-09-10T12:00:00Z")
    assert paper_cycle.select_universe(con, dataset_version="ds1",
                                       target_date=date(2026, 9, 10))
    assert not paper_cycle.select_universe(con, dataset_version="ds1",
                                           target_date=date(2026, 9, 9))


# --------------------------------------------------------------------------- dumping
def _cycle():
    return paper_cycle.Cycle(session_id="cyc1")


def test_the_catalogue_is_not_dumped_on_an_ordinary_cycle(con, tmp_path):
    """8 collections a day × the full catalogue would add ~120 MB/month to git."""
    _market(con, market_id="m1", event_id="e1", end_date="2026-09-10T12:00:00Z")
    paper_cycle.stage_dump(_cycle(), con, root=str(tmp_path), session_id="cyc1",
                           dataset_version="ds1", since=T0 - timedelta(days=1))
    assert store.iter_shards(tmp_path, "markets") == []
    assert store.iter_shards(tmp_path, "outcomes") == []


def test_the_catalogue_is_dumped_when_the_daily_flag_is_passed(con, tmp_path):
    _market(con, market_id="m1", event_id="e1", end_date="2026-09-10T12:00:00Z")
    paper_cycle.stage_dump(_cycle(), con, root=str(tmp_path), session_id="cyc1",
                           dataset_version="ds1", since=T0 - timedelta(days=1),
                           dump_catalogue=True)
    assert len(store.iter_shards(tmp_path, "markets")) == 1
    assert len(store.iter_shards(tmp_path, "outcomes")) == 1


def test_the_catalogue_snapshot_is_full_not_incremental(con, tmp_path):
    """Catalogue rows are re-stamped on every discovery, so a `since` filter would
    take all of them or none. The snapshot is therefore explicitly complete."""
    _market(con, market_id="m1", event_id="e1", end_date="2026-09-10T12:00:00Z")
    paper_cycle.stage_dump(_cycle(), con, root=str(tmp_path), session_id="cyc1",
                           dataset_version="ds1",
                           since=T0 + timedelta(days=365),   # far in the future
                           dump_catalogue=True)
    rows = list(store.read_shard(store.iter_shards(tmp_path, "markets")[0]))
    assert len(rows) == 1                       # not filtered away by `since`


def test_the_ledger_is_dumped_incrementally(con, tmp_path):
    from weather_agent import paper
    fill = paper.Fill(shares=100.0, notional=50.0, vwap=0.5, fee=0.625,
                      outlay=50.625, executable=True)
    paper.record_paper_trade(con, backtest_id="cyc1", market_id="m", token_id="t",
                             entry_time=T0, fill=fill, bankroll_after=1.0,
                             dataset_version="ds1")
    # a cutoff after the row was written must exclude it
    paper_cycle.stage_dump(_cycle(), con, root=str(tmp_path), session_id="cyc1",
                           dataset_version="ds1", since=T0 + timedelta(days=365))
    assert store.iter_shards(tmp_path, "paper_trades") == []
    # a cutoff before it must include it
    paper_cycle.stage_dump(_cycle(), con, root=str(tmp_path), session_id="cyc1",
                           dataset_version="ds1", since=T0 - timedelta(days=365))
    assert len(store.iter_shards(tmp_path, "paper_trades")) == 1


def test_every_persisted_table_has_a_known_conflict_key():
    """A table in STATE_TABLES with no key in the store cannot be reloaded, which
    would be discovered only on the next Actions run."""
    for table in paper_cycle.STATE_TABLES:
        assert table in store.CONFLICT_COLS, f"{table} has no conflict key"


def test_the_catalogue_and_ledger_partition_the_state():
    assert set(paper_cycle.CATALOGUE_TABLES) | set(paper_cycle.LEDGER_TABLES) == \
        set(paper_cycle.STATE_TABLES)
    assert not set(paper_cycle.CATALOGUE_TABLES) & set(paper_cycle.LEDGER_TABLES)


# --------------------------------------------------------------------------- contract
def test_target_date_is_obligatory():
    """PHASE_2D_STRATEGY_A_DESIGN.md §C: the caller supplies it, always."""
    parser = paper_cycle.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--dataset-version", "ds1"])


def test_no_tau_means_no_trading_rather_than_a_default_tau():
    parser = paper_cycle.build_parser()
    args = parser.parse_args(["--target-date", "2026-09-10",
                              "--dataset-version", "ds1"])
    assert args.tau is None                     # fail-closed, not 0.03
