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


# --------------------------------------------------------------------------- timing
def test_t_end_is_noon_utc_on_the_target_date():
    assert paper_cycle.t_end(date(2026, 9, 10)) == \
        datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


def test_t_asof_is_t_end_minus_the_lead():
    for lead, expected in ((24, datetime(2026, 9, 9, 12, tzinfo=timezone.utc)),
                           (9, datetime(2026, 9, 10, 3, tzinfo=timezone.utc))):
        out = paper_cycle.decision_time(date(2026, 9, 10), lead,
                                        datetime(2026, 9, 9, 0, tzinfo=timezone.utc))
        assert out["t_asof"] == expected


def test_firing_early_decides_at_now_and_uses_less_information():
    now = datetime(2026, 9, 9, 11, 40, tzinfo=timezone.utc)     # 20 min early
    out = paper_cycle.decision_time(date(2026, 9, 10), 24, now)
    assert out["prediction_time"] == now
    assert out["fired_early"] is True
    assert out["lead_effective_h"] == pytest.approx(24 + 1 / 3)  # LONGER lead, safe
    assert out["drift_h"] < 0


def test_firing_late_clamps_to_t_asof_so_the_declared_lead_stays_true():
    """The defect A-32 found in someone else's document: an availability rule
    stated in prose and never applied. Without this clamp a drifted run would use
    data that arrived after T_asof while still claiming to be as-of T_asof."""
    now = datetime(2026, 9, 9, 14, 30, tzinfo=timezone.utc)     # 2.5 h late
    out = paper_cycle.decision_time(date(2026, 9, 10), 24, now)
    assert out["prediction_time"] == out["t_asof"]              # clamped
    assert out["prediction_time"] < now
    assert out["lead_effective_h"] == pytest.approx(24.0)
    assert out["drift_h"] == pytest.approx(2.5)


def test_the_decision_instant_is_never_after_t_asof():
    for offset_h in (-6, -1, 0, 1, 6, 48):
        now = datetime(2026, 9, 9, 12, tzinfo=timezone.utc) + timedelta(hours=offset_h)
        out = paper_cycle.decision_time(date(2026, 9, 10), 24, now)
        assert out["prediction_time"] <= out["t_asof"]


# --------------------------------------------------------------------------- fees
def test_the_fee_lookup_joins_through_the_market_not_the_schedule_key(con):
    """`market_fee_schedule` is keyed by fee_regime; it has NO market_id column, so
    querying it by market_id raises a binder error. This test exists because the
    first version did exactly that, and it would have crashed on the first cycle
    that produced an actionable signal — never on a collect-only smoke run."""
    con.execute(
        "INSERT INTO markets (market_id, event_id, fee_regime, source_timestamps, "
        "ingestion_timestamp, dataset_version, record_version) VALUES (?,?,?,?,?,?,?)",
        ["m1", "e1", "weather_fees", '{"endDate":"2026-09-10T12:00:00Z"}', T0, "ds1", 1])
    con.execute(
        "INSERT INTO market_fee_schedule (fee_regime, taker_fee, maker_rebate, "
        "fee_status, raw_fee_fields, ingestion_timestamp, dataset_version, "
        "record_version) VALUES (?,?,?,?,?,?,?,?)",
        ["weather_fees", 0.05, 0.25, "KNOWN",
         '{"feeSchedule":{"exponent":1,"rate":0.05}}', T0, "ds1", 1])

    rows = con.execute(
        "SELECT f.taker_fee, f.fee_status FROM markets m JOIN market_fee_schedule f "
        "ON f.fee_regime = m.fee_regime AND f.dataset_version = m.dataset_version "
        "WHERE m.market_id = ? AND m.dataset_version = ?", ["m1", "ds1"]).fetchall()
    assert rows == [(0.05, "KNOWN")]

    with pytest.raises(Exception):
        con.execute("SELECT taker_fee FROM market_fee_schedule WHERE market_id = ?",
                    ["m1"]).fetchall()


def test_the_cycle_source_uses_the_join_and_not_the_broken_predicate():
    src = (Path(__file__).resolve().parents[1] / "scripts" / "paper_cycle.py").read_text()
    assert "FROM market_fee_schedule WHERE market_id" not in src
    assert "JOIN market_fee_schedule f" in src


# --------------------------------------------------------------------------- guard
def _price(con, *, token="t1", dsv="ds1", rv=1, when=T0):
    con.execute(
        "INSERT INTO price_history (observation_time, market_id, token_id, "
        "indicative_price, ingestion_timestamp, dataset_version, record_version) "
        "VALUES (?,?,?,?,?,?,?)", [when, "m1", token, 0.5, T0, dsv, rv])


def test_the_guard_passes_on_a_single_version_database(con):
    _price(con)
    out = paper_cycle.stage_guard_dataset_version(_cycle(), con, dataset_version="ds1")
    assert out["ok"] is True


def test_the_guard_stops_the_cycle_when_two_versions_coexist(con):
    """build_feature takes dataset_version and never uses it. With one version
    that is harmless; with two it silently mixes a backfilled price with a
    prospectively-collected one. Paper mode is what introduces the second."""
    _price(con, token="t1", dsv="backfill_2b_v1")
    _price(con, token="t2", dsv="ds_paper_v1")
    with pytest.raises(SystemExit, match="ambiguous"):
        paper_cycle.stage_guard_dataset_version(_cycle(), con,
                                                dataset_version="ds_paper_v1")


def test_the_guard_stops_when_the_database_is_a_different_version(con):
    _price(con, dsv="someone_elses_backfill")
    with pytest.raises(SystemExit):
        paper_cycle.stage_guard_dataset_version(_cycle(), con,
                                                dataset_version="ds_paper_v1")


def test_the_guard_stops_on_a_superseded_record_version(con):
    """latest_asof partitions by token only, so a record_version 2 row that
    supersedes a 1 could be missed or mixed."""
    _price(con, token="t1", dsv="ds1", rv=1)
    _price(con, token="t1", dsv="ds1", rv=2, when=T0 + timedelta(minutes=1))
    with pytest.raises(SystemExit, match="record_version"):
        paper_cycle.stage_guard_dataset_version(_cycle(), con, dataset_version="ds1")


def test_an_empty_database_does_not_trip_the_guard(con):
    out = paper_cycle.stage_guard_dataset_version(_cycle(), con, dataset_version="ds1")
    assert out["ok"] is True
