"""Tests for scripts/paper_cycle.py — offline, no network.

The cycle itself needs gamma and the CLOB, so what is pinned here is the part that
decides WHAT gets persisted and WHICH markets are in scope: the catalogue/ledger
split that keeps the git-backed store from growing without bound, and the universe
filter that must never become a target_date derivation.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from unittest import mock

from weather_agent import database, database as db_mod, store
from weather_agent import observations as obs_mod

_SPEC = importlib.util.spec_from_file_location(
    "paper_cycle", Path(__file__).resolve().parents[1] / "scripts" / "paper_cycle.py")
paper_cycle = importlib.util.module_from_spec(_SPEC)
sys.modules["paper_cycle"] = paper_cycle
_SPEC.loader.exec_module(paper_cycle)


T0 = datetime(2026, 9, 9, 7, 30, tzinfo=timezone.utc)

#: The caller's target_date (2D §C). A trade carries the day it was opened
#: for; nothing downstream rebuilds it from `endDate`.
TD_TEST = date(2026, 9, 10)



@pytest.fixture
def con():
    c = database.init_db(database.connect(":memory:"))
    try:
        yield c
    finally:
        c.close()


def _market(con, *, market_id, event_id, end_date, dsv="ds1", station="EGLC"):
    # ICAO in `station_identifier`, `station` NULL — what live discovery produces
    # (A-56: `markets.station` is NULL in 1 100 of 1 100 rows). A fixture that
    # puts the ICAO in `station` makes the two columns indistinguishable, which is
    # how Strategy A shipped a total, deterministic failure with a green suite.
    con.execute(
        "INSERT INTO markets (market_id, event_id, station, station_identifier, "
        "unit, rounding_rule, "
        "source_timestamps, ingestion_timestamp, dataset_version, record_version) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        [market_id, event_id, None, station, "C", "whole degree",
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
                             dataset_version="ds1", target_date=TD_TEST)
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
    assert args.tau_signal is None              # fail-closed, not 0.03
    assert args.tau_exec is None


def test_the_two_thresholds_are_separate_parameters():
    """One number applied to two different operands is a threshold with two
    meanings. Strategy A gates the GROSS edge against the indicative mid; the
    paper engine gates the NET edge against the achievable VWAP. They may take
    the same value, but that has to be stated, not assumed."""
    parser = paper_cycle.build_parser()
    args = parser.parse_args(["--target-date", "2026-09-10",
                              "--dataset-version", "ds1",
                              "--tau-signal", "0.03", "--tau-exec", "0.01"])
    assert args.tau_signal == 0.03 and args.tau_exec == 0.01


def test_paper_params_rejects_the_old_single_tau_name():
    from weather_agent import paper as _paper
    with pytest.raises(TypeError):
        _paper.PaperParams(bankroll=1.0, fixed_fraction=0.02, size_cap=0.02,
                           tau=0.03, exit_mode="hold_to_resolution", x_exec=0.0)


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


def test_the_guard_refuses_the_decision_when_two_versions_coexist(con):
    """build_feature takes dataset_version and never uses it. With one version
    that is harmless; with two it silently mixes a backfilled price with a
    prospectively-collected one. Paper mode is what introduces the second."""
    _price(con, token="t1", dsv="backfill_2b_v1")
    _price(con, token="t2", dsv="ds_paper_v1")
    cy = _cycle()
    out = paper_cycle.stage_guard_dataset_version(cy, con,
                                                  dataset_version="ds_paper_v1")
    assert out["ok"] is False
    assert any("dataset_versions present" in p for p in out["problems"])


def test_the_guard_refuses_when_the_database_is_a_different_version(con):
    _price(con, dsv="someone_elses_backfill")
    out = paper_cycle.stage_guard_dataset_version(_cycle(), con,
                                                  dataset_version="ds_paper_v1")
    assert out["ok"] is False


def test_the_guard_refuses_on_a_superseded_record_version(con):
    """latest_asof partitions by token only, so a record_version 2 row that
    supersedes a 1 could be missed or mixed."""
    _price(con, token="t1", dsv="ds1", rv=1)
    _price(con, token="t1", dsv="ds1", rv=2, when=T0 + timedelta(minutes=1))
    out = paper_cycle.stage_guard_dataset_version(_cycle(), con,
                                                  dataset_version="ds1")
    assert out["ok"] is False
    assert any("record_version" in p for p in out["problems"])


def test_a_refused_guard_still_reaches_the_dump_and_decides_nothing(con, tmp_path,
                                                                    monkeypatch):
    """The guard refuses the DECISION, not the cycle — which is what it always said.

    Its own message reads "refusing to DECIDE" and the call site says a cycle
    that only collects is harmless; the implementation raised SystemExit and took
    the whole run down. Session B found it while approving PR #19: the guard sits
    between `stage_collect` — the order-book capture, which cannot be re-fetched —
    and `stage_dump`, the only place that capture is persisted, with the dump
    inside the `try`. So a guard protecting a decision was discarding the
    collection, and the asymmetry runs the wrong way: tomorrow's cycle can decide
    again, tomorrow's book is gone.
    """
    monkeypatch.setattr(paper_cycle, "stage_discover",
                        lambda cy, *a, **k: cy.stage("discover", paper_cycle.OK))
    monkeypatch.setattr(paper_cycle, "stage_collect",
                        lambda cy, *a, **k: cy.stage("collect:books", paper_cycle.OK))
    # THE REAL GUARD RUNS. An earlier version of this test monkeypatched it to
    # return {"ok": False}, and then PASSED with the `raise SystemExit` put back:
    # it exercised the caller's branch and could not fail on the thing it names.
    # Same shape as the WAL test discarded for passing with and without its fix.
    # So the database is made genuinely ambiguous instead, and the guard decides.
    from weather_agent import database as _db
    dbpath = tmp_path / "t.duckdb"
    seed = _db.init_db(_db.connect(str(dbpath)))
    _price(seed, token="t1", dsv="ds1")
    _price(seed, token="t2", dsv="someone_elses_backfill")
    seed.close()

    rc = paper_cycle.main([
        "--target-date", "2026-09-10", "--dataset-version", "ds1",
        "--store-root", str(tmp_path / "store"), "--db", str(dbpath),
        "--tau-signal", "0.02", "--tau-exec", "0.02",
        "--summary-json", str(tmp_path / "s.json")])

    import json as _json
    stages = {s["stage"]: s for s in
              _json.loads((tmp_path / "s.json").read_text())["stages"]}
    assert stages["guard:dataset_version"]["status"] == "STOPPED"
    for st in ("forecasts", "signals", "paper", "observations"):
        assert stages[st]["status"] == "SKIPPED"
        assert stages[st]["reason"] == "guard_refused_dataset_version", (
            "and the reason must name the guard, not say collect_only — the two "
            "are different facts about the run")
    assert "dump" in stages, "the capture must still be persisted"
    assert rc == 0


def test_a_guard_that_cannot_look_REFUSES_rather_than_skipping(con, monkeypatch):
    """"I could not check" is not "it is fine", and the difference is the guard.

    Session B's residual on PR #21. Removing the deliberate `raise` left the
    incidental one: the two `db.query` probes were unwrapped, still sitting
    between the capture and the dump. The tempting remedy is `_non_fatal` — and
    it is the wrong one, because it records SKIPPED and CONTINUES, which for a
    guard means deciding on a substrate nobody managed to inspect.

    So an exception is a REFUSAL: same STOPPED status, the error carried in
    `problems`, the cycle degraded to collect-only and still reaching the dump.
    Fails closed in both directions — when it finds ambiguity, and when it cannot
    look.
    """
    def _boom(*a, **k):
        raise RuntimeError("database is locked")
    monkeypatch.setattr(paper_cycle.db, "query", _boom)

    cy = _cycle()
    out = paper_cycle.stage_guard_dataset_version(cy, con, dataset_version="ds1")
    assert out["ok"] is False, "a guard that cannot look must not report ok"
    assert any("database is locked" in p for p in out["problems"])


def test_an_empty_database_does_not_trip_the_guard(con):
    out = paper_cycle.stage_guard_dataset_version(_cycle(), con, dataset_version="ds1")
    assert out["ok"] is True


# --------------------------------------------------------------------------- as-of ordering
def test_the_decision_instant_is_after_the_collection_it_consumes():
    """The third form of the same defect. `prediction_time` computed at cycle
    start lands BEFORE the `observation_time` of the prices the cycle is about to
    collect, and build_feature's filter (`observation_time <= prediction_time`)
    then rejects every one of them: 0 signals again.

    Real numbers: cron fires 11:40Z, T_asof is 12:00Z, collection finishes 11:45Z.
    """
    start = datetime(2026, 9, 9, 11, 40, tzinfo=timezone.utc)
    collected = start + timedelta(minutes=5)
    target = date(2026, 9, 10)

    at_start = paper_cycle.decision_time(target, 24, start)["prediction_time"]
    assert collected > at_start                    # the bug, pinned

    after = paper_cycle.decision_time(target, 24, collected)["prediction_time"]
    assert collected <= after                      # the fix: the price qualifies


def test_a_late_cycle_still_never_decides_after_t_asof():
    """The clamp must survive the reordering: running late may make this cycle's
    own prices unusable, but it must not let them in by moving the as-of."""
    target = date(2026, 9, 10)
    t_asof = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
    collected = datetime(2026, 9, 9, 14, 30, tzinfo=timezone.utc)   # 2.5 h late
    out = paper_cycle.decision_time(target, 24, collected)
    assert out["prediction_time"] == t_asof
    assert collected > out["prediction_time"]      # own prices correctly excluded
    assert out["drift_h"] == pytest.approx(2.5)


def test_main_settles_prediction_time_after_collection_not_before():
    """Source-level: the ordering is the whole fix, so pin it.

    It pins the ORDER, not the line. The earlier version matched the whole
    statement including `_utcnow()`, and broke when the clock read was hoisted
    into `cycle_now` so both this stage and the complementary-lead coverage
    derive their anchors from ONE reading. A rename that does not touch the
    ordering must not fail a test about the ordering.
    """
    src = (Path(__file__).resolve().parents[1] / "scripts" / "paper_cycle.py").read_text()
    i_collect = src.index("stage_collect(cy, con")
    i_settle = src.index("timing = decision_time(target_date, args.lead_hours,")
    assert i_settle > i_collect, "prediction_time must be settled after collection"


def test_own_prices_are_usable_exactly_when_the_clamp_did_not_bind():
    """Spotted in a live run: the cycle reported `late_firing=False` and
    `own_prices_usable=False` in the same breath, which cannot both be true."""
    target = date(2026, 9, 10)
    early = paper_cycle.decision_time(target, 24,
                                      datetime(2026, 9, 9, 10, 8, tzinfo=timezone.utc))
    assert early["fired_early"] is True
    assert early["prediction_time"] == datetime(2026, 9, 9, 10, 8, tzinfo=timezone.utc)

    late = paper_cycle.decision_time(target, 24,
                                     datetime(2026, 9, 9, 14, 0, tzinfo=timezone.utc))
    assert late["fired_early"] is False
    assert late["prediction_time"] == late["t_asof"]     # clamped -> own prices too new


def _with_b_substrate(con):
    """Ensure the settle substrate exists, whether or not the schema already has it.

    IDEMPOTENT on purpose. The first version issued a bare ALTER TABLE ADD COLUMN,
    which is correct while session B's migration is unmerged and a hard error the
    moment it lands. Each branch was green alone and six tests failed on the
    merge — the class of defect that only a trial merge finds."""
    have_obs = set(db_mod.column_names(con, "weather_observations"))
    for col, typ in (("observed_value", "DOUBLE"), ("observed_unit", "VARCHAR"),
                     ("series", "VARCHAR")):
        if col not in have_obs:
            con.execute(f"ALTER TABLE weather_observations ADD COLUMN {col} {typ}")
    if "contract_source" not in set(db_mod.column_names(con, "markets")):
        con.execute("ALTER TABLE markets ADD COLUMN contract_source VARCHAR")



# --------------------------------------------------------------------------- settle
def test_settle_names_the_substrate_it_is_missing(con, monkeypatch):
    """A SKIP that says 'not wired yet' leaves the next reader to guess. This one
    names the columns.

    Written against a column DROPPED on purpose rather than against whatever the
    schema happens to lack today: the original version asserted that
    `observed_value` was absent, which was true on one branch and false once
    session B's migration merged. Two green branches broke on merge, and this test
    was the reason."""
    # Reported through `column_names` rather than by dropping the column: DuckDB
    # refuses to drop one an index depends on, so schema surgery is not a portable
    # way to simulate absence.
    real = db_mod.column_names
    monkeypatch.setattr(
        db_mod, "column_names",
        lambda c, t: [x for x in real(c, t) if x != "observed_value"])
    missing = paper_cycle.settle_substrate_missing(con)
    assert any("weather_observations.observed_value" in m for m in missing)


def test_settle_reports_ready_on_a_complete_substrate(con, monkeypatch):
    """The other half, and the one that actually matters going forward."""
    _with_b_substrate(con)
    _fake_stations(monkeypatch)
    assert paper_cycle.settle_substrate_missing(con) == []


def test_settle_is_a_noop_with_no_open_positions(con):
    out = paper_cycle.stage_settle(_cycle(), con, dataset_version="ds1")
    assert out == {"positions_open": 0, "settled": 0}


def test_settle_skips_loudly_rather_than_guessing_a_winner(con, monkeypatch):
    """The shortcut this refuses to take — picking a winner from the last traded
    price — is what turns a paper ledger into fiction."""
    real = db_mod.column_names
    monkeypatch.setattr(
        db_mod, "column_names",
        lambda c, t: [x for x in real(c, t) if x != "series"])
    from weather_agent import paper as _paper
    fill = _paper.Fill(shares=100.0, notional=50.0, vwap=0.5, fee=0.6,
                       outlay=50.6, executable=True)
    _paper.record_paper_trade(con, backtest_id="r", market_id="m1", token_id="t1",
                              entry_time=T0, fill=fill, bankroll_after=1.0,
                              dataset_version="ds1", target_date=TD_TEST)
    out = paper_cycle.stage_settle(_cycle(), con, dataset_version="ds1")
    assert out["positions_open"] == 1 and out["settled"] == 0
    assert out["missing"], "it must say what it lacks"
    row = con.execute("SELECT exit_time, settlement FROM paper_trades").fetchone()
    assert row[0] is None and row[1] is None      # untouched, not guessed


def _settleable_market(con, *, band="17°C", outcome="Yes", token="t1"):
    from weather_agent.polymarket import resolution as res
    # The CODE in `measurement_rule_code` and the PROSE in `measurement_rule` —
    # which is what live discovery writes. The old fixture put the P_* code in
    # `measurement_rule`, a value discovery never produces there, so the suite
    # could not see that `stage_settle` was feeding the human string into the
    # partition key. Fourth fixture today certifying a world that does not exist.
    con.execute(
        "INSERT INTO markets (market_id, event_id, contract_source, "
        "measurement_rule_code, measurement_rule, "
        "unit, rounding_rule, station_identifier, source_timestamps, "
        "ingestion_timestamp, dataset_version, record_version) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        ["m1", "e1", res.SRC_NOAA, res.P_NOAA_TEMPCOL,
         res.MEASUREMENT_RULE_TEXT[res.P_NOAA_TEMPCOL],
         "C", "whole degree", "EGLC",
         '{"endDate":"2026-09-10T12:00:00Z"}', T0, "ds1", 1])
    con.execute(
        "INSERT INTO outcomes (market_id, token_id, band_label, outcome_label, "
        "ingestion_timestamp, dataset_version, record_version) VALUES (?,?,?,?,?,?,?)",
        ["m1", token, band, outcome, T0, "ds1", 1])
    con.execute(
        "INSERT INTO weather_observations (station, observation_time, tmax_observed, "
        "observed_value, observed_unit, series, source, ingestion_timestamp, "
        "dataset_version, record_version) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ["EGLC", datetime(2026, 9, 10, 14, tzinfo=timezone.utc), 17.0, 17.0, "C",
         # What the INGESTER writes, not what the frozen core requires. The old
         # fixture wrote `metar_body_c` — a value no ingester has ever produced —
         # so the suite could not see that every real settlement was refused for
         # `series_mismatch`. Fifth fixture today certifying a world that is not
         # the one the code runs in.
         obs_mod.SERIES_1C, "IEM", T0, "ds1", 1])
    from weather_agent import paper as _paper
    fill = _paper.Fill(shares=100.0, notional=50.0, vwap=0.5, fee=0.6,
                       outlay=50.6, executable=True)
    return _paper.record_paper_trade(
        con, backtest_id="r", market_id="m1", token_id=token, entry_time=T0,
        fill=fill, bankroll_after=1.0, dataset_version="ds1", target_date=TD_TEST)


def _fake_stations(monkeypatch):
    import sys, types
    mod = types.ModuleType("weather_agent.stations")
    mod.timezone_of = lambda icao: "Europe/London"   # the real name (B's stations.py)
    monkeypatch.setitem(sys.modules, "weather_agent.stations", mod)


def test_a_yes_token_on_the_winning_band_settles_to_one(con, monkeypatch):
    _with_b_substrate(con); _fake_stations(monkeypatch)
    tid = _settleable_market(con, band="17°C", outcome="Yes")
    out = paper_cycle.stage_settle(_cycle(), con, dataset_version="ds1")
    assert out["settled"] == 1, out
    row = con.execute("SELECT settlement, net_pnl FROM paper_trades "
                      "WHERE paper_trade_id = ?", [tid]).fetchone()
    assert row[0] == 1.0 and row[1] > 0


def test_a_yes_token_on_a_losing_band_settles_to_zero(con, monkeypatch):
    _with_b_substrate(con); _fake_stations(monkeypatch)
    tid = _settleable_market(con, band="21°C", outcome="Yes")
    paper_cycle.stage_settle(_cycle(), con, dataset_version="ds1")
    row = con.execute("SELECT settlement, net_pnl FROM paper_trades "
                      "WHERE paper_trade_id = ?", [tid]).fetchone()
    assert row[0] == 0.0 and row[1] < 0


def test_a_no_token_pays_when_the_band_does_not_contain_the_key(con, monkeypatch):
    """The complement, and it is easy to get backwards: a No token wins exactly
    when its own band did NOT happen."""
    _with_b_substrate(con); _fake_stations(monkeypatch)
    tid = _settleable_market(con, band="21°C", outcome="No")
    paper_cycle.stage_settle(_cycle(), con, dataset_version="ds1")
    assert con.execute("SELECT settlement FROM paper_trades WHERE paper_trade_id = ?",
                       [tid]).fetchone()[0] == 1.0


def test_an_open_ended_band_settles_correctly(con, monkeypatch):
    _with_b_substrate(con); _fake_stations(monkeypatch)
    tid = _settleable_market(con, band="15°C or below", outcome="Yes")
    paper_cycle.stage_settle(_cycle(), con, dataset_version="ds1")
    assert con.execute("SELECT settlement FROM paper_trades WHERE paper_trade_id = ?",
                       [tid]).fetchone()[0] == 0.0     # 17 is not <= 15


def test_a_refused_settlement_leaves_the_position_open_with_its_reason(con, monkeypatch):
    """A stratum with no operator must not settle. The position stays open and the
    reason is counted — never a guessed winner."""
    from weather_agent.polymarket import resolution as res
    _with_b_substrate(con); _fake_stations(monkeypatch)
    tid = _settleable_market(con)
    con.execute("UPDATE markets SET measurement_rule_code = ? WHERE market_id = 'm1'",
                [res.P_BY_FORECAST])
    con.execute("UPDATE markets SET contract_source = ? WHERE market_id = 'm1'",
                [res.SRC_WU])
    out = paper_cycle.stage_settle(_cycle(), con, dataset_version="ds1")
    assert out["settled"] == 0
    assert out["refusals"].get("no_settlement_operator:by_forecast") == 1
    assert con.execute("SELECT exit_time FROM paper_trades WHERE paper_trade_id = ?",
                       [tid]).fetchone()[0] is None


# --------------------------------------------------------------------------- forecasts
def _artifact(tmp_path, *, fit_instant=None, max_age_hours=336.0, lead=24,
              values=None, name="m2_quantiles.json"):
    """A real artifact on disk. The forecast tests go through the same loader and
    the same guards the cycle uses; a monkeypatched `quantiles_for` would have
    tested a path that no longer exists."""
    from weather_agent import error_model as em, m2, quantile_artifact as qa
    fit_instant = fit_instant or datetime(2026, 9, 9, 6, tzinfo=timezone.utc)
    values = values or {10: -1.5, 25: -0.5, 50: 0.4, 75: 1.3, 90: 2.2}
    payload = qa.build_payload(
        prereg_sha256=m2.PREREG_SHA_V2, model="icon_seamless",
        dataset_version=m2.DATASET_VERSION, fit_instant=fit_instant,
        max_age_hours=max_age_hours,
        strata={lead: em.Quantiles(em.SCOPE_POOLED, 147, values)},
        windows={lead: (fit_instant - timedelta(days=40), fit_instant)})
    return str(qa.dump(payload, tmp_path / name) and (tmp_path / name))
def test_forecasts_picks_the_run_already_published_not_the_newest(con, monkeypatch):
    """Publication latency is real (L_MAX 4.76 h for icon_seamless). Selecting a run
    by issue time alone would use a forecast that did not exist yet at the decision
    instant."""
    from weather_agent import m2, weather
    t = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
    issue = m2.pick_run(t, weather.M1_MODEL)
    assert issue is not None
    assert weather.available_at(issue, weather.M1_MODEL) <= t, \
        "the chosen run must already have been published at the decision instant"


def test_forecasts_skips_when_no_station_is_in_the_universe(con, tmp_path):
    out = paper_cycle.stage_forecasts(
        _cycle(), con, dataset_version="ds1", target_date=date(2026, 9, 10),
        universe=[], model="icon_seamless", lead_hours=24,
        artifact_path=_artifact(tmp_path),
        prediction_time=datetime(2026, 9, 9, 12, tzinfo=timezone.utc))
    assert out == {"written": 0, "quantiles": 0}


def test_forecasts_stops_on_a_rate_limit_and_never_retries_through(con, monkeypatch, tmp_path):
    """Standing constraint: a 429 ends the stage. The user pays for no key."""
    from weather_agent import weather

    def boom(*a, **k):
        raise RuntimeError("HTTP 429 Too Many Requests")
    monkeypatch.setattr(weather, "ingest_run", boom)
    monkeypatch.setattr("weather_agent.stations.timezone_of", lambda i: "Europe/London")
    out = paper_cycle.stage_forecasts(
        _cycle(), con, dataset_version="ds1", target_date=date(2026, 9, 10),
        universe=[{"station_identifier": "EGLC"}, {"station_identifier": "EDDM"}], model="icon_seamless",
        lead_hours=24, artifact_path=_artifact(tmp_path),
        prediction_time=datetime(2026, 9, 9, 12, tzinfo=timezone.utc))
    assert out.get("stopped") is True and out["written"] == 0


def test_forecasts_writes_quantiles_in_celsius_from_the_backfill_substrate(
        con, monkeypatch, tmp_path):
    """The training substrate is a DIFFERENT dataset_version on purpose: M2's error
    distribution lives in the backfill, the cycle runs as ds_paper_v1. Since R30
    the crossing is not just visible, it is RECORDED — the artifact names the
    substrate it was fitted on and the cycle writes its id into cycle_params."""
    from weather_agent import m2, weather

    # one forecast row for the cycle's own dataset_version
    t = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
    issue = m2.pick_run(t, weather.M1_MODEL)
    con.execute(
        "INSERT INTO weather_forecasts (issue_time, target_date, station, model, "
        "forecast_tmax, available_at, ingestion_timestamp, dataset_version, "
        "record_version) VALUES (?,?,?,?,?,?,?,?,?)",
        [issue, date(2026, 9, 10), "EGLC", "icon_seamless", 17.0,
         weather.available_at(issue, "icon_seamless"), T0, "ds_paper_v1", 1])
    monkeypatch.setattr(weather, "ingest_run", lambda *a, **k: None)
    monkeypatch.setattr("weather_agent.stations.timezone_of", lambda i: "Europe/London")

    out = paper_cycle.stage_forecasts(
        _cycle(), con, dataset_version="ds_paper_v1", target_date=date(2026, 9, 10),
        universe=[{"station_identifier": "EGLC"}], model="icon_seamless", lead_hours=24,
        artifact_path=_artifact(tmp_path), prediction_time=t)
    assert out["quantiles"] == 1
    prov = out["provenance"]
    assert prov["quantile_artifact_dataset_version"] == m2.DATASET_VERSION
    assert prov["quantile_stratum_lead_h"] == 24 and prov["quantile_stratum_n"] == 147
    row = con.execute("SELECT forecast_p10, forecast_p50, forecast_p90 "
                      "FROM weather_forecasts WHERE station = 'EGLC'").fetchone()
    # forecast_pXX = f + percentile_XX(e), in Celsius; f = 17.0
    assert row == (pytest.approx(15.5), pytest.approx(17.4), pytest.approx(19.2))


def test_quantiles_never_cross_between_record_versions(con, monkeypatch, tmp_path):
    """`record_version` is part of the PK of weather_forecasts. An UPDATE that does
    not name it writes to EVERY version of the key, so the last forecast processed
    would set the quantiles of all of them — a row whose p50 is not derived from
    its own forecast_tmax. Two versions, two different tmax, two different p50."""
    from weather_agent import m2, weather

    t = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
    issue = m2.pick_run(t, weather.M1_MODEL)
    for rv, tmax in ((1, 10.0), (2, 20.0)):
        con.execute(
            "INSERT INTO weather_forecasts (issue_time, target_date, station, model, "
            "forecast_tmax, available_at, ingestion_timestamp, dataset_version, "
            "record_version) VALUES (?,?,?,?,?,?,?,?,?)",
            [issue, date(2026, 9, 10), "EGLC", "icon_seamless", tmax,
             weather.available_at(issue, "icon_seamless"), T0, "ds_paper_v1", rv])
    monkeypatch.setattr(weather, "ingest_run", lambda *a, **k: None)
    monkeypatch.setattr("weather_agent.stations.timezone_of", lambda i: "Europe/London")

    out = paper_cycle.stage_forecasts(
        _cycle(), con, dataset_version="ds_paper_v1", target_date=date(2026, 9, 10),
        universe=[{"station_identifier": "EGLC"}], model="icon_seamless",
        lead_hours=24, prediction_time=t,
        artifact_path=_artifact(tmp_path, values={10: -1.0, 25: -0.5, 50: 0.0,
                                                  75: 0.5, 90: 1.0}))
    assert out["quantiles"] == 2
    got = dict(con.execute(
        "SELECT record_version, forecast_p50 FROM weather_forecasts "
        "WHERE station = 'EGLC' ORDER BY record_version").fetchall())
    assert got[1] == pytest.approx(10.0)
    assert got[2] == pytest.approx(20.0)


def test_a_non_integral_lead_refuses_instead_of_truncating_the_stratum(
        con, monkeypatch, tmp_path):
    """`training_pairs` matches `p.lead_h == lead_h` exactly. int(9.5) -> 9 would
    return the 9 h stratum for a 9.5 h decision without raising anything."""
    from weather_agent import weather
    monkeypatch.setattr(weather, "ingest_run", lambda *a, **k: None)
    monkeypatch.setattr("weather_agent.stations.timezone_of", lambda i: "Europe/London")
    out = paper_cycle.stage_forecasts(
        _cycle(), con, dataset_version="ds_paper_v1", target_date=date(2026, 9, 10),
        universe=[{"station_identifier": "EGLC"}], model="icon_seamless",
        lead_hours=9.5, artifact_path=_artifact(tmp_path),
        prediction_time=datetime(2026, 9, 9, 12, tzinfo=timezone.utc))
    assert out.get("stopped") is True and out["quantiles"] == 0


def test_a_stale_artifact_stops_the_stage_and_writes_no_quantiles(con, monkeypatch, tmp_path):
    """Session B's condition, at the level where it bites: the cycle REFUSES,
    it does not warn. `build_feature` needs the five quantiles and returns None
    without them, so a stale artifact used in silence would not raise — it would
    quietly produce a distribution fitted on a world that has moved."""
    from weather_agent import m2, weather
    t = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
    issue = m2.pick_run(t, weather.M1_MODEL)
    con.execute(
        "INSERT INTO weather_forecasts (issue_time, target_date, station, model, "
        "forecast_tmax, available_at, ingestion_timestamp, dataset_version, "
        "record_version) VALUES (?,?,?,?,?,?,?,?,?)",
        [issue, date(2026, 9, 10), "EGLC", "icon_seamless", 17.0,
         weather.available_at(issue, "icon_seamless"), T0, "ds_paper_v1", 1])
    calls = []
    monkeypatch.setattr(weather, "ingest_run", lambda *a, **k: calls.append(a))
    monkeypatch.setattr("weather_agent.stations.timezone_of", lambda i: "Europe/London")

    cy = _cycle()
    out = paper_cycle.stage_forecasts(
        cy, con, dataset_version="ds_paper_v1", target_date=date(2026, 9, 10),
        universe=[{"station_identifier": "EGLC"}], model="icon_seamless",
        lead_hours=24, prediction_time=t,
        artifact_path=_artifact(tmp_path, max_age_hours=1.0,
                                fit_instant=t - timedelta(hours=48)))
    assert out["stopped"] is True and out["quantiles"] == 0
    assert out["artifact_refusal"] == "artifact_stale"
    # AND NOT ONE REQUEST WAS MADE. Without quantiles the cycle produces no signal
    # at all, so fetching 50 stations first would spend 50 Open-Meteo requests on
    # forecasts nothing can use. The user pays for no key (A-29.1).
    assert calls == []
    assert out["written"] == 0
    row = con.execute("SELECT forecast_tmax, forecast_p50 FROM weather_forecasts "
                      "WHERE station = 'EGLC'").fetchone()
    assert row[0] == 17.0 and row[1] is None


def test_an_artifact_fitted_after_the_decision_stops_the_stage(con, monkeypatch, tmp_path):
    """The replay case. Forward in time it cannot happen; reproducing an old
    cycle against a refitted artifact is exactly where it does."""
    from weather_agent import weather
    t = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(weather, "ingest_run", lambda *a, **k: None)
    monkeypatch.setattr("weather_agent.stations.timezone_of", lambda i: "Europe/London")
    out = paper_cycle.stage_forecasts(
        _cycle(), con, dataset_version="ds_paper_v1", target_date=date(2026, 9, 10),
        universe=[{"station_identifier": "EGLC"}], model="icon_seamless",
        lead_hours=24, prediction_time=t,
        artifact_path=_artifact(tmp_path, fit_instant=t + timedelta(hours=1)))
    assert out["artifact_refusal"] == "artifact_fitted_after_decision"


def test_a_missing_artifact_is_a_labelled_refusal_not_a_crash(con, monkeypatch, tmp_path):
    from weather_agent import weather
    monkeypatch.setattr(weather, "ingest_run", lambda *a, **k: None)
    monkeypatch.setattr("weather_agent.stations.timezone_of", lambda i: "Europe/London")
    out = paper_cycle.stage_forecasts(
        _cycle(), con, dataset_version="ds_paper_v1", target_date=date(2026, 9, 10),
        universe=[{"station_identifier": "EGLC"}], model="icon_seamless",
        lead_hours=24, prediction_time=datetime(2026, 9, 9, 12, tzinfo=timezone.utc),
        artifact_path=str(tmp_path / "there-is-no-artifact.json"))
    assert out["artifact_refusal"] == "artifact_missing"


def test_the_cycle_records_which_artifact_it_used(tmp_path):
    """B's second condition, end to end: the id lands in the `cycle_params`
    shard, so a later reader can say which fit produced a given cycle's numbers
    without trusting a commit date."""
    import argparse
    args = argparse.Namespace(
        target_date=date(2026, 9, 10), model="icon_seamless", tau_signal=0.03,
        tau_exec=0.03, bankroll=10_000.0, fixed_fraction=0.02, size_cap=0.02,
        x_exec=0.0, exit_mode="hold_to_resolution", weather_sum_tolerance=0.05,
        market_sum_min=0.9, market_sum_max=1.1, collect_only=False,
        max_artifact_age_h=48.0)
    timing = {"t_end": T0, "t_asof": T0, "prediction_time": T0,
              "lead_nominal_h": 24.0, "lead_effective_h": 24.0, "drift_h": 0.0}
    prov = {"quantile_artifact_id": "abc123", "quantile_stratum_n": 147}
    params = paper_cycle.stage_params(
        _cycle(), root=str(tmp_path), session_id="cyc_prov", args=args,
        timing=timing, dataset_version="ds_paper_v1", quantile_provenance=prov)
    assert params["quantile_artifact_id"] == "abc123"
    assert params["quantile_stratum_n"] == 147
    assert params["max_artifact_age_h"] == 48.0


def test_a_deciding_cycle_dumps_its_own_catalogue(con, tmp_path):
    """C3 is only a criterion if the replay can rebuild the universe the cycle
    DECIDED on. Restricted to one firing a day, the other cycle was replayed
    against a snapshot up to 15 h older: markets discovered in between were
    absent, their trades came back as `only_persisted`, and the verdict was NOT
    REPRODUCIBLE for a reason that is not reproducibility. Measured cost of doing
    it every deciding cycle: 206 KiB, 8.5 MiB over the run."""
    con.execute(
        "INSERT INTO markets (market_id, event_id, source, ingestion_timestamp, "
        "dataset_version, record_version) VALUES (?,?,?,?,?,?)",
        ["m1", "e1", "test", T0, "ds1", 1])
    cy = _cycle()
    paper_cycle.stage_dump(cy, con, root=str(tmp_path), session_id="cyc",
                           dataset_version="ds1", since=T0 - timedelta(days=1),
                           dump_catalogue=True)
    assert (tmp_path / "markets").exists()
    stages = {s["stage"]: s for s in cy.summary()["stages"]}
    assert stages["dump"]["catalogue"] == "dumped"


def test_a_collect_only_cycle_skips_the_catalogue_and_says_why(con, tmp_path):
    """The saving lives here: the collector fires 8 times a day, decides nothing,
    and leaves the replay nothing to reproduce."""
    con.execute(
        "INSERT INTO markets (market_id, event_id, source, ingestion_timestamp, "
        "dataset_version, record_version) VALUES (?,?,?,?,?,?)",
        ["m1", "e1", "test", T0, "ds1", 1])
    cy = _cycle()
    paper_cycle.stage_dump(cy, con, root=str(tmp_path), session_id="cyc",
                           dataset_version="ds1", since=T0 - timedelta(days=1),
                           dump_catalogue=False)
    assert not (tmp_path / "markets").exists()
    stages = {s["stage"]: s for s in cy.summary()["stages"]}
    assert stages["dump:catalogue"]["reason"] == "collect_only_nothing_to_replay"


# --------------------------------------------------------------------------- observations
def _open_position(con, *, market_id="m1", end_date="2026-09-10T12:00:00Z",
                   station="EGLC", dsv="ds1"):
    _market(con, market_id=market_id, event_id="e1", end_date=end_date,
            dsv=dsv, station=station)
    # `target_date` travels WITH the position (2D §C). A fixture that leaves it
    # NULL is a fixture for a trade written before the column existed — which is a
    # real case, tested separately, but not the normal one.
    con.execute(
        "INSERT INTO paper_trades (backtest_id, market_id, token_id, entry_time, "
        "target_date, entry_price, fees, size, price_layer, ingestion_timestamp, "
        "dataset_version, record_version) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        ["cyc", market_id, f"{market_id}_yes", T0,
         datetime.fromisoformat(end_date.replace("Z", "+00:00")).date(),
         0.5, 0.1, 10.0, "SIMULATED_EXECUTABLE", T0, dsv, 1])


def test_the_label_is_fetched_only_once_the_station_local_day_has_ended(con, monkeypatch):
    """The METAR high of a day still running is not that day's high. Ingesting it
    would write a wrong label and never revisit it — the settlement would then be
    confident and wrong, which is worse than open."""
    from weather_agent import observations as obs
    calls = []
    monkeypatch.setattr(obs, "ingest_daily_high",
                        lambda con, i, d, tz, dsv: calls.append((i, d)))
    monkeypatch.setattr("weather_agent.stations.timezone_of", lambda i: "Europe/London")
    _open_position(con, end_date="2026-09-10T12:00:00Z")

    # London is UTC+1 in September, so the local day of the 10th runs
    # 2026-09-09T23:00Z .. 2026-09-10T23:00Z. The boundary is where an off-by-one
    # would hide, so both sides of it are pinned rather than a comfortable margin.
    out = paper_cycle.stage_observations(
        _cycle(), con, dataset_version="ds1",
        now=datetime(2026, 9, 10, 22, 59, tzinfo=timezone.utc))
    assert calls == [] and out["ingested"] == 0 and out["pending"] == 1

    # The day has ENDED here and it is still not read: the window closing does not
    # mean IEM holds the day's last METAR, and an incomplete maximum written once
    # is never revisited — the next cycle sees a row and skips it.
    out = paper_cycle.stage_observations(
        _cycle(), con, dataset_version="ds1",
        now=datetime(2026, 9, 10, 23, 0, tzinfo=timezone.utc))
    assert calls == [] and out["pending"] == 1

    out = paper_cycle.stage_observations(
        _cycle(), con, dataset_version="ds1",
        now=datetime(2026, 9, 11, 1, 0, tzinfo=timezone.utc))
    assert calls == [("EGLC", date(2026, 9, 10))] and out["ingested"] == 1


def test_a_label_already_in_the_table_is_not_fetched_again(con, monkeypatch):
    from weather_agent import observations as obs
    calls = []
    monkeypatch.setattr(obs, "ingest_daily_high",
                        lambda con, i, d, tz, dsv: calls.append(i))
    monkeypatch.setattr("weather_agent.stations.timezone_of", lambda i: "Europe/London")
    _open_position(con)
    con.execute(
        "INSERT INTO weather_observations (station, source, observation_time, "
        "tmax_observed, ingestion_timestamp, dataset_version, record_version) "
        "VALUES (?,?,?,?,?,?,?)",
        ["EGLC", "METAR", datetime(2026, 9, 10, 14, tzinfo=timezone.utc), 21.0,
         T0, "ds1", 1])
    out = paper_cycle.stage_observations(
        _cycle(), con, dataset_version="ds1",
        now=datetime(2026, 9, 12, tzinfo=timezone.utc))
    assert calls == [] and out["ingested"] == 0


def test_observations_stop_on_a_rate_limit_and_never_retry_through(con, monkeypatch):
    from weather_agent import observations as obs

    def boom(*a, **k):
        raise RuntimeError("HTTP 429 Too Many Requests")
    monkeypatch.setattr(obs, "ingest_daily_high", boom)
    monkeypatch.setattr("weather_agent.stations.timezone_of", lambda i: "Europe/London")
    _open_position(con)
    out = paper_cycle.stage_observations(
        _cycle(), con, dataset_version="ds1",
        now=datetime(2026, 9, 12, tzinfo=timezone.utc))
    assert out.get("stopped") is True and out["ingested"] == 0


def test_nothing_is_fetched_when_no_position_is_waiting_on_a_label(con, monkeypatch):
    from weather_agent import observations as obs
    calls = []
    monkeypatch.setattr(obs, "ingest_daily_high",
                        lambda *a, **k: calls.append(a))
    out = paper_cycle.stage_observations(
        _cycle(), con, dataset_version="ds1",
        now=datetime(2026, 9, 12, tzinfo=timezone.utc))
    assert out == {"wanted": 0, "ingested": 0} and calls == []


def test_a_settled_position_stops_pulling_its_label(con, monkeypatch):
    """`exit_time IS NULL` is the whole scope. A run that kept re-fetching the
    labels of closed positions would spend quota on rows nothing reads."""
    from weather_agent import observations as obs
    calls = []
    monkeypatch.setattr(obs, "ingest_daily_high",
                        lambda con, i, d, tz, dsv: calls.append(i))
    monkeypatch.setattr("weather_agent.stations.timezone_of", lambda i: "Europe/London")
    _open_position(con)
    con.execute("UPDATE paper_trades SET exit_time = ?", [T0])
    out = paper_cycle.stage_observations(
        _cycle(), con, dataset_version="ds1",
        now=datetime(2026, 9, 12, tzinfo=timezone.utc))
    assert out["wanted"] == 0 and calls == []


def test_settlement_refuses_when_the_rule_CODE_was_never_classified(con, monkeypatch):
    """The partition is keyed on the P_* code. Substituting the human string —
    which is what the cycle did until the column existed — is refused by the core
    as an unknown terna, and that reads as "this market has no operator" when the
    truth is "this row was never classified". The two must not be confusable."""
    _with_b_substrate(con); _fake_stations(monkeypatch)
    _settleable_market(con)
    con.execute("UPDATE markets SET measurement_rule_code = NULL WHERE market_id = 'm1'")
    out = paper_cycle.stage_settle(_cycle(), con, dataset_version="ds1")
    assert out["settled"] == 0
    assert out["refusals"].get("no_measurement_rule_code") == 1


def test_a_series_with_no_declared_correspondence_is_refused_not_guessed(con, monkeypatch):
    """`metar_tgroup_tmpf` names the METAR T-group; IEM_ASOS_TMPF_1F and
    IEM_ASOS_TMPF_0.1F are `tmpf` at two DIFFERENT resolutions, and the operator's
    own note says the resolution decides the label. Collapsing both onto one name
    would settle KBKF off its own grid (A-42). Undeclared means refused."""
    _with_b_substrate(con); _fake_stations(monkeypatch)
    _settleable_market(con)
    con.execute("UPDATE weather_observations SET series = ?", [obs_mod.SERIES_TENTH_F])
    out = paper_cycle.stage_settle(_cycle(), con, dataset_version="ds1")
    assert out["settled"] == 0
    assert out["refusals"].get("series_correspondence_undeclared") == 1


def test_the_declared_correspondence_is_the_one_the_ingester_writes():
    """A mapping keyed on a name no ingester produces is a mapping that never
    fires. Pinned against `observations`, not against a literal."""
    assert paper_cycle.to_core_series(obs_mod.SERIES_1C) == "metar_body_c"
    # Settled by the audit: of four candidate columns over the 14 Fahrenheit rows,
    # only `tmpf` lands inside the winning band, 14/14, on whole degrees.
    assert paper_cycle.to_core_series(obs_mod.SERIES_1F) == "metar_tgroup_tmpf"
    # KBKF's series stays undeclared, and its stratum (9, P_NOAA_HourlyData) is
    # fail-closed in the core anyway, so nothing is lost by it.
    assert paper_cycle.to_core_series(obs_mod.SERIES_TENTH_F) is None
    assert paper_cycle.to_core_series(None) is None


def test_the_settlement_tail_settles_and_decides_nothing(con, tmp_path, monkeypatch):
    """R24 §5. A position opened on the last day of the run resolves the day
    AFTER it, so without these cycles the last two days' positions would stay
    open and their PnL would not exist — the ledger would close on a tail
    truncated by the calendar, not by the market."""
    from weather_agent import observations as obs
    calls = []
    monkeypatch.setattr(obs, "ingest_daily_high",
                        lambda con, i, d, tz, dsv: calls.append(i))
    monkeypatch.setattr("weather_agent.stations.timezone_of", lambda i: "Europe/London")
    # A cycle that discovers or collects in the tail would be deciding, and would
    # also move `markets.available_at`. Both must be untouched.
    monkeypatch.setattr(paper_cycle, "stage_discover",
                        lambda *a, **k: pytest.fail("the tail must not discover"))
    monkeypatch.setattr(paper_cycle, "stage_collect",
                        lambda *a, **k: pytest.fail("the tail must not collect"))

    store_root = tmp_path / "store"
    _open_position(con)
    con.execute("UPDATE weather_observations SET station = 'EGLC'")  # no-op if empty
    rc = paper_cycle.main([
        "--target-date", "2026-09-10", "--dataset-version", "ds1",
        "--store-root", str(store_root), "--db", str(tmp_path / "t.duckdb"),
        "--settle-only", "--summary-json", str(tmp_path / "s.json")])
    assert rc == 0
    import json as _json
    stages = {s["stage"]: s for s in _json.loads((tmp_path / "s.json").read_text())["stages"]}
    for st in ("discover", "universe", "collect:books", "forecasts", "signals", "paper"):
        assert stages[st]["status"] == "SKIPPED"
        assert stages[st]["reason"] == "settle_only_tail"
    assert "observations" in stages and "settle" in stages


def test_a_trade_with_no_target_date_is_left_open_not_guessed(con, monkeypatch):
    """A position written before `target_date` existed is NOT settled by
    recovering the day from `endDate`. 2D §C makes that a prohibited derivation,
    and `markets` is re-discovered every cycle: a revised `endDate` under an open
    position would fetch — and settle against — a day it was never opened for."""
    from weather_agent import observations as obs
    calls = []
    monkeypatch.setattr(obs, "ingest_daily_high",
                        lambda con, i, d, tz, dsv: calls.append(i))
    monkeypatch.setattr("weather_agent.stations.timezone_of", lambda i: "Europe/London")
    _open_position(con)
    con.execute("UPDATE paper_trades SET target_date = NULL")
    out = paper_cycle.stage_observations(
        _cycle(), con, dataset_version="ds1",
        now=datetime(2026, 9, 12, tzinfo=timezone.utc))
    assert calls == [] and out["wanted"] == 0

    _with_b_substrate(con); _fake_stations(monkeypatch)
    settled = paper_cycle.stage_settle(_cycle(), con, dataset_version="ds1")
    assert settled["settled"] == 0
    assert settled["refusals"].get("trade_without_target_date") == 1


def test_stage_paper_opens_a_position_carrying_the_callers_target_date(con):
    """`stage_paper` had NO stage-level test at all — 525 of them passed while the
    stage that OPENS positions raised NameError on its first live signal. This is
    the missing one, and it asserts the thing that matters: the position carries
    the caller's target_date (2D §C), not a value some later stage rebuilds."""
    T = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
    _market(con, market_id="m1", event_id="e1", end_date="2026-09-10T12:00:00Z")
    con.execute(
        "INSERT INTO market_fee_schedule (fee_regime, taker_fee, fee_status, "
        "raw_fee_fields, ingestion_timestamp, dataset_version, record_version) "
        "VALUES (?,?,?,?,?,?,?)",
        ["weather_fees", 0.05, "KNOWN", '{"feeSchedule":{"exponent":1,"rate":0.05}}',
         T0, "ds1", 1])
    con.execute("UPDATE markets SET fee_regime = 'weather_fees'")
    con.execute(
        'INSERT INTO orderbook_snapshots (token_id, "timestamp", market_id, '
        "book_snapshot, ingestion_timestamp, dataset_version, record_version) "
        "VALUES (?,?,?,?,?,?,?)",
        ["m1_yes", T - timedelta(minutes=5), "m1",
         json.dumps({"asks": [{"price": 0.50, "size": 10_000}],
                     "bids": [{"price": 0.49, "size": 100}], "truncated": False}),
         T0, "ds1", 1])
    con.execute(
        'INSERT INTO signals (market_id, token_id, strategy, "timestamp", signal, '
        "fair_value, price_assumption, edge, ingestion_timestamp, dataset_version, "
        "record_version) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ["m1", "m1_yes", "strategy_a_v1", T, "BUY", 0.70, 0.50, 0.20, T0, "ds1", 1])

    from weather_agent import paper as _paper
    out = paper_cycle.stage_paper(
        _cycle(), con, dataset_version="ds1", session_id="cyc",
        params=_paper.PaperParams(bankroll=10_000.0, fixed_fraction=0.02,
                                  size_cap=0.02, tau_exec=0.03,
                                  exit_mode="hold_to_resolution", x_exec=0.0),
        prediction_time=T, target_date=date(2026, 9, 10))
    assert out["opened"] == 1
    td = con.execute("SELECT target_date FROM paper_trades").fetchone()[0]
    assert (td.date() if hasattr(td, "date") else td) == date(2026, 9, 10)


def test_the_signals_stage_records_both_rungs_with_their_denominators(con, monkeypatch):
    """A rate is not a measurement until its denominator is written next to it.

    Two cross-session numbers called "eligible" turned out to have different
    denominators — 14 % was structural completeness, 80.2 % was
    actionable-among-complete — and the second was the PRODUCT of two rungs that
    happened to be nearly equal, which is what makes two denominators look like
    one. The cycle records both rungs and the tau that produced them instead of
    leaving a later reader to infer which is which.
    """
    T = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
    for i, mid in enumerate(("m1", "m2")):
        _market(con, market_id=mid, event_id=f"e{i}", end_date="2026-09-10T12:00:00Z")
    # `available_at` is what the as-of universe filter reads: a market we could not
    # have known existed at prediction_time is not decidable (R26).
    con.execute("UPDATE markets SET available_at = ?", [T - timedelta(hours=1)])
    con.execute(
        "INSERT INTO weather_forecasts (issue_time, target_date, station, model, "
        "forecast_tmax, forecast_p50, available_at, ingestion_timestamp, "
        "dataset_version, record_version) VALUES (?,?,?,?,?,?,?,?,?,?)",
        [T, date(2026, 9, 10), "EGLC", "icon_seamless", 17.0, 17.0, T, T0, "ds1", 1])
    # one event produces an actionable signal, the other does not
    con.execute(
        'INSERT INTO signals (market_id, token_id, strategy, "timestamp", signal, '
        "fair_value, price_assumption, edge, ingestion_timestamp, dataset_version, "
        "record_version) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ["m1", "m1_yes", "strategy_a_v1", T, "BUY", 0.70, 0.50, 0.20, T0, "ds1", 1])
    con.execute(
        'INSERT INTO signals (market_id, token_id, strategy, "timestamp", signal, '
        "fair_value, price_assumption, edge, ingestion_timestamp, dataset_version, "
        "record_version) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ["m2", "m2_yes", "strategy_a_v1", T, "HOLD", 0.51, 0.50, 0.01, T0, "ds1", 1])

    cy = _cycle()
    monkeypatch.setattr(
        "weather_agent.strategy.strategy_a.generate_event_signals",
        lambda con, **kw: {"eligible": True, "signals_written": 1})
    out = paper_cycle.stage_signals(
        cy, con, dataset_version="ds1", target_date=date(2026, 9, 10),
        universe=[{"market_id": "m1", "event_id": "e0"},
                  {"market_id": "m2", "event_id": "e1"}],
        model="icon_seamless", tau=0.03, weather_sum_tolerance=0.02,
        market_sum_min=0.9, market_sum_max=1.15, prediction_time=T)

    assert out["events_discovered"] == 2
    assert out["events_admissible"] == 2
    assert out["eligible"] == 2
    assert out["events_actionable"] == 1          # only m1's event has BUY/FADE
    assert out["rung1_structural_rate"] == 1.0    # 2 of 2 pass the structural gate
    assert out["rung2_actionable_rate"] == 0.5    # 1 of 2 eligible is actionable
    assert out["tau_signal"] == 0.03


def test_venue_coverage_is_fail_closed_per_event_and_runs_without_deciding(con, tmp_path):
    """Rung 1 measured where it can actually be measured.

    `stage_signals` never runs in Actions — every scheduled cycle is
    `--collect-only` because `vars.PAPER_TAU` is unset — so instrumentation that
    lives there records nothing (verified on the real store: `signals` 0 shards).
    Rung 1 needs only prices, so it runs on every cycle and the multi-day series
    accumulates for free.

    ONE UNPRICED BAND EXCLUDES THE WHOLE EVENT, because Strategy A is fail-closed
    per event: the count is the CEILING on what could ever be decided, not a
    count of what is nearly decidable.
    """
    T = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
    # e0: both bands priced. e1: one band priced, one not.
    for mid, ev in (("m1", "e0"), ("m2", "e0"), ("m3", "e1"), ("m4", "e1")):
        _market(con, market_id=mid, event_id=ev, end_date="2026-09-10T12:00:00Z")
    for mid in ("m1", "m2", "m3"):
        con.execute(
            "INSERT INTO price_history (market_id, token_id, observation_time, "
            "indicative_price, price_semantics, source, ingestion_timestamp, "
            "dataset_version, record_version) VALUES (?,?,?,?,?,?,?,?,?)",
            [mid, f"{mid}_yes", T - timedelta(minutes=5), 0.5,
             "MIDPOINT_ESTIMATED", "test", T0, "ds1", 1])

    universe = [{"event_id": "e0", "market_id": "m1"}, {"event_id": "e0", "market_id": "m2"},
                {"event_id": "e1", "market_id": "m3"}, {"event_id": "e1", "market_id": "m4"}]
    out = paper_cycle.stage_venue_coverage(
        _cycle(), con, dataset_version="ds1", universe=universe, prediction_time=T,
        t_asof=T, root=str(tmp_path), session_id="cyc", target_date=date(2026, 9, 10), lead_h=24.0)

    assert out["events"] == 2
    assert out["events_complete"] == 1          # e1 dies for ONE unpriced band
    assert out["bands"] == 4 and out["bands_priced"] == 3
    assert out["complete_rate_over_events"] == 0.5
    assert out["priced_rate_over_bands"] == 0.75


def test_venue_coverage_respects_the_as_of_instant(con, tmp_path):
    """A price stamped after the decision instant does not make a band priced:
    the ceiling has to be the one that existed at `prediction_time`."""
    T = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
    _market(con, market_id="m1", event_id="e0", end_date="2026-09-10T12:00:00Z")
    con.execute(
        "INSERT INTO price_history (market_id, token_id, observation_time, "
        "indicative_price, price_semantics, source, ingestion_timestamp, "
        "dataset_version, record_version) VALUES (?,?,?,?,?,?,?,?,?)",
        ["m1", "m1_yes", T + timedelta(minutes=5), 0.5,
         "MIDPOINT_ESTIMATED", "test", T0, "ds1", 1])
    out = paper_cycle.stage_venue_coverage(
        _cycle(), con, dataset_version="ds1",
        universe=[{"event_id": "e0", "market_id": "m1"}], prediction_time=T,
        t_asof=T, root=str(tmp_path), session_id="cyc", target_date=date(2026, 9, 10), lead_h=24.0)
    assert out["events_complete"] == 0 and out["bands_priced"] == 0


def test_venue_coverage_is_written_to_the_STORE_not_only_to_the_summary(con, tmp_path,
                                                                        monkeypatch):
    """The series has to survive the run, and the summary does not.

    The first version reported the coverage in `cy.stage` and stopped there. That
    lands in the cycle summary, which the workflow uploads as a per-run ARTIFACT
    kept for 90 days; only `paper_state/` is committed to the data branch. So the
    numbers would have existed in 42 separate artifacts and in no series at all —
    "accumulates for free" was false as built.

    The `github_event` goes with it: a series that cannot tell a scheduled cycle
    from a hand-dispatched one measures the operator's attention, not the host.
    """
    T = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
    _market(con, market_id="m1", event_id="e0", end_date="2026-09-10T12:00:00Z")
    con.execute(
        "INSERT INTO price_history (market_id, token_id, observation_time, "
        "indicative_price, price_semantics, source, ingestion_timestamp, "
        "dataset_version, record_version) VALUES (?,?,?,?,?,?,?,?,?)",
        ["m1", "m1_yes", T - timedelta(minutes=5), 0.5,
         "MIDPOINT_ESTIMATED", "test", T0, "ds1", 1])
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")

    paper_cycle.stage_venue_coverage(
        _cycle(), con, dataset_version="ds1",
        universe=[{"event_id": "e0", "market_id": "m1"}], prediction_time=T,
        t_asof=T, root=str(tmp_path), session_id="cyc", target_date=date(2026, 9, 10), lead_h=24.0)

    shards = store.iter_shards(tmp_path, "venue_coverage")
    assert len(shards) == 1
    import gzip as _gz
    row = json.loads(_gz.open(shards[0], "rt").readline())
    assert row["events"] == 1 and row["events_complete"] == 1
    assert row["github_event"] == "schedule"
    assert row["target_date"] == "2026-09-10"


def test_venue_coverage_row_says_whether_the_count_is_FINAL(con, tmp_path, monkeypatch):
    """A partial row must not be averaged into the series that fixes the threshold.

    The cutoff is effectively `t_asof` whichever branch of `min(now, t_asof)`
    applies — before it there is no later price to exclude, after it the min IS
    `t_asof` — so rows for one target are comparable and A-92's worry about that
    was wrong. What is NOT the same is whether more prices can still land: while
    `now < t_asof` the count is partial and will grow. The row therefore carries
    the fact rather than leaving it to be inferred from `recorded_at` against
    `prediction_time`, which happens to work today and is one clamp change away
    from silently not working.
    """
    T = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
    _market(con, market_id="m1", event_id="e0", end_date="2026-09-10T12:00:00Z")

    def _row(now, t_asof, root):
        monkeypatch.setattr(paper_cycle, "_utcnow", lambda: now)
        paper_cycle.stage_venue_coverage(
            _cycle(), con, dataset_version="ds1",
            universe=[{"event_id": "e0", "market_id": "m1"}],
            prediction_time=min(now, t_asof), t_asof=t_asof,
            root=str(root), session_id="cyc", target_date=date(2026, 9, 10), lead_h=24.0)
        import gzip as _gz
        return json.loads(_gz.open(store.iter_shards(root, "venue_coverage")[0],
                                   "rt").readline())

    before = _row(T - timedelta(hours=3), T, tmp_path / "a")
    assert before["is_final"] is False
    assert before["t_asof"].startswith("2026-09-09T12:00:00")

    after = _row(T + timedelta(hours=3), T, tmp_path / "b")
    assert after["is_final"] is True

    # THE CASE SESSION B FOUND, and the reason `is_final` may not take a second
    # clock read. The cron fires ~20 min EARLY on purpose, so the cutoff is set
    # before `t_asof` and the row is written after it — here a 25-minute cycle
    # that starts at 11:40 and writes at 12:05. A fresh `_utcnow()` at write
    # time is past the anchor and stamps a PARTIAL count as final; the cutoff
    # that produced the count never reached it.
    monkeypatch.setattr(paper_cycle, "_utcnow", lambda: T + timedelta(minutes=5))
    root = tmp_path / "early_fire"
    paper_cycle.stage_venue_coverage(
        _cycle(), con, dataset_version="ds1",
        universe=[{"event_id": "e0", "market_id": "m1"}],
        prediction_time=T - timedelta(minutes=20),   # fired early: cutoff 11:40
        t_asof=T,                                    # anchor 12:00
        root=str(root), session_id="cyc", target_date=date(2026, 9, 10), lead_h=24.0)
    import gzip as _gz
    row = json.loads(_gz.open(store.iter_shards(root, "venue_coverage")[0],
                              "rt").readline())
    assert row["is_final"] is False, (
        "a count cut at 11:40 is partial no matter what the clock says at 12:05")


def test_venue_coverage_join_does_not_fan_out_on_record_version(con, tmp_path):
    """`record_version` is part of the key, so the join must carry it.

    Found by session B: `select_universe` joins on it and this query did not —
    two queries in the same module disagreeing about whether a key column
    matters, which is the shape of the `fit_m2` gap and of the read that
    returned another token's price. It cannot fire in production today
    (`discovery.ingest_event` writes record_version 1 literally everywhere and
    `next_record_version` is called from nowhere) and `stage_guard_dataset_version`
    does not watch markets/outcomes either — so the day someone starts versioning,
    `bands` would silently double with no guard in the way.
    """
    T = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
    _market(con, market_id="m1", event_id="e0", end_date="2026-09-10T12:00:00Z")
    # a second version of the SAME market and its outcomes, as the helper would
    con.execute(
        "INSERT INTO markets (market_id, event_id, station, station_identifier, "
        "unit, rounding_rule, source_timestamps, ingestion_timestamp, "
        "dataset_version, record_version) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ["m1", "e0", None, "EGLC", "C", "whole degree",
         '{"endDate":"2026-09-10T12:00:00Z"}', T0, "ds1", 2])
    for i, (tok, label) in enumerate((("m1_yes", "Yes"), ("m1_no", "No"))):
        con.execute(
            "INSERT INTO outcomes (market_id, token_id, band_label, outcome_index, "
            "outcome_label, ingestion_timestamp, dataset_version, record_version) "
            "VALUES (?,?,?,?,?,?,?,?)",
            ["m1", tok, "15C or below", i, label, T0, "ds1", 2])

    out = paper_cycle.stage_venue_coverage(
        _cycle(), con, dataset_version="ds1",
        universe=[{"event_id": "e0", "market_id": "m1"}], prediction_time=T,
        t_asof=T, root=str(tmp_path), session_id="cyc",
        target_date=date(2026, 9, 10), lead_h=24.0)
    assert out["bands"] == 2, "one band per (market, record_version), not the cross product"


def test_coverage_row_carries_the_lead_and_says_what_kind_of_row_it_is(con, tmp_path):
    """`lead_h` and `row_kind`, both stated rather than inferable.

    The consumer rule is "the last final row per (target_date, lead)" and the
    lead was NOT in the row — derivable from `target_date` and `t_asof`, which is
    the derivable-but-fragile shape removed everywhere else. And `row_kind`
    exists so nobody counts coverage rows as decision cycles: a cycle emits one
    for the lead it carries and one for the lead it does not, and only the first
    corresponds to a decision it could have made.
    """
    T = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)
    _market(con, market_id="m1", event_id="e0", end_date="2026-09-10T12:00:00Z")
    paper_cycle.stage_venue_coverage(
        _cycle(), con, dataset_version="ds1",
        universe=[{"event_id": "e0", "market_id": "m1"}], prediction_time=T,
        t_asof=T, root=str(tmp_path), session_id="cyc",
        target_date=date(2026, 9, 10), lead_h=9.0, row_kind="other_lead")
    import gzip as _gz
    row = json.loads(_gz.open(store.iter_shards(tmp_path, "venue_coverage")[0],
                              "rt").readline())
    assert row["lead_h"] == 9.0
    assert row["row_kind"] == "other_lead"


def test_a_late_row_is_what_ESTABLISHES_the_early_row_was_complete(con, tmp_path):
    """The complementary-lead row is not a re-stamped flag: it is the measurement.

    Session B's escalation, and it changes what this feature is for. The lead-9
    cycle fires at 02:40 against a 03:00 anchor, so its cutoff is its own `now` —
    after its own collection, before the anchor. Whether any price arrives in
    (cutoff, anchor] can only be known AFTER the anchor. The early row is
    BETTING that none did; a row cut AT the anchor is the only thing that can
    settle it.

    Measured on the live store for 2026-09-10: 1 492 observations at or before
    the 02:49:13 cutoff and 1 492 at or before the 03:00 anchor — the bet paid
    that day, and only the late row could show it. Note the mechanism is NOT
    "no collection slot in the window": the decide cycle collects its own prices
    at 02:48, 646 of them, inside the window B first proposed. They fall before
    its cutoff, which is why they are already counted.

    The assertion is on `bands_priced` alone. `bands` and `events` legitimately
    grow between the two rows because `markets`/`outcomes` are re-discovered
    every cycle, so demanding equality of everything would fail on discovery and
    send someone chasing a ghost.
    """
    T_ANCHOR = datetime(2026, 9, 10, 3, tzinfo=timezone.utc)
    early_cut = T_ANCHOR - timedelta(minutes=11)      # the 02:49 row
    _market(con, market_id="m1", event_id="e0", end_date="2026-09-10T12:00:00Z")
    con.execute(
        "INSERT INTO price_history (market_id, token_id, observation_time, "
        "indicative_price, price_semantics, source, ingestion_timestamp, "
        "dataset_version, record_version) VALUES (?,?,?,?,?,?,?,?,?)",
        ["m1", "m1_yes", T_ANCHOR - timedelta(minutes=12), 0.5,
         "MIDPOINT_ESTIMATED", "test", T0, "ds1", 1])

    def _row(pt, root, kind):
        paper_cycle.stage_venue_coverage(
            _cycle(), con, dataset_version="ds1",
            universe=[{"event_id": "e0", "market_id": "m1"}],
            prediction_time=pt, t_asof=T_ANCHOR, root=str(root),
            session_id="cyc", target_date=date(2026, 9, 10), lead_h=9.0,
            row_kind=kind)
        import gzip as _gz
        return json.loads(_gz.open(store.iter_shards(root, "venue_coverage")[0],
                                   "rt").readline())

    early = _row(early_cut, tmp_path / "early", "own")
    late = _row(T_ANCHOR, tmp_path / "late", "other_lead")

    assert early["is_final"] is False, "cut before the anchor: a bet, not a fact"
    assert late["is_final"] is True, "cut AT the anchor: this is what settles it"
    assert late["bands_priced"] == early["bands_priced"], (
        "nothing arrived in (cutoff, anchor]; if these ever differ, the series "
        "has been holding rows whose completeness nobody checked")


def test_a_price_inside_the_window_makes_the_early_row_genuinely_partial(con, tmp_path):
    """And the assertion has to be able to FAIL, or it measures nothing.

    Same setup with one price landing between the early cutoff and the anchor —
    which is what a collector slot moving into that window would do. The counts
    then differ, and that difference is the warning.
    """
    T_ANCHOR = datetime(2026, 9, 10, 3, tzinfo=timezone.utc)
    early_cut = T_ANCHOR - timedelta(minutes=11)
    _market(con, market_id="m1", event_id="e0", end_date="2026-09-10T12:00:00Z")
    con.execute(
        "INSERT INTO price_history (market_id, token_id, observation_time, "
        "indicative_price, price_semantics, source, ingestion_timestamp, "
        "dataset_version, record_version) VALUES (?,?,?,?,?,?,?,?,?)",
        ["m1", "m1_yes", T_ANCHOR - timedelta(minutes=5), 0.5,
         "MIDPOINT_ESTIMATED", "test", T0, "ds1", 1])

    def _row(pt, root):
        paper_cycle.stage_venue_coverage(
            _cycle(), con, dataset_version="ds1",
            universe=[{"event_id": "e0", "market_id": "m1"}],
            prediction_time=pt, t_asof=T_ANCHOR, root=str(root),
            session_id="cyc", target_date=date(2026, 9, 10), lead_h=9.0)
        import gzip as _gz
        return json.loads(_gz.open(store.iter_shards(root, "venue_coverage")[0],
                                   "rt").readline())

    early = _row(early_cut, tmp_path / "early")
    late = _row(T_ANCHOR, tmp_path / "late")
    assert early["bands_priced"] == 0 and late["bands_priced"] == 1, (
        "the early row missed a price that landed before the anchor — exactly "
        "what the equality assertion is there to catch")


def test_coverage_also_is_validated_in_argparse_before_any_request(tmp_path):
    """A malformed `--coverage-also` must die at parse time, not mid-cycle.

    Session B's blocking finding, and the severity is structural: the coverage
    stage sits between `stage_collect` — the order-book capture, the one thing
    here that cannot be re-fetched — and `stage_dump`, the only place that
    capture is persisted. `stage_dump` is inside the `try`; the `finally` only
    closes the connection. So a bare `float()` inside the stage put a
    destroy-the-capture path one mistyped character away in a cron line:
    `9:2026-13-45` would collect 1 078 tokens and then throw, and the dump would
    never run.
    """
    parser = paper_cycle.build_parser()
    base = ["--target-date", "2026-09-10", "--dataset-version", "ds1"]
    for bad in ("9:2026-13-45", "nine:2026-09-10", "9", "0:2026-09-10",
                "-9:2026-09-10", ":2026-09-10"):
        with pytest.raises(SystemExit):
            parser.parse_args(base + ["--coverage-also", bad])
    ok = parser.parse_args(base + ["--coverage-also", "9:2026-09-10"])
    assert ok.coverage_also == [(9.0, date(2026, 9, 10))]


def test_a_failing_measurement_stage_does_not_destroy_the_capture(con, tmp_path,
                                                                  monkeypatch):
    """Nothing between `stage_collect` and `stage_dump` may kill the cycle.

    Measurement is worth a great deal and worth strictly less than the capture,
    and they were coupled the other way round: a failure to MEASURE destroyed the
    thing being measured. Here the coverage stage raises and the cycle must still
    reach the dump, with the failure recorded as a SKIPPED stage rather than
    swallowed.
    """
    monkeypatch.setattr(paper_cycle, "stage_discover",
                        lambda cy, *a, **k: cy.stage("discover", paper_cycle.OK))
    monkeypatch.setattr(paper_cycle, "stage_collect",
                        lambda cy, *a, **k: cy.stage("collect:books", paper_cycle.OK))
    def _boom(*a, **k):
        raise RuntimeError("measurement exploded")
    monkeypatch.setattr(paper_cycle, "stage_venue_coverage", _boom)

    store_root = tmp_path / "store"
    rc = paper_cycle.main([
        "--target-date", "2026-09-10", "--dataset-version", "ds1",
        "--store-root", str(store_root), "--db", str(tmp_path / "t.duckdb"),
        "--collect-only", "--summary-json", str(tmp_path / "s.json")])

    import json as _json
    stages = {s["stage"]: s for s in
              _json.loads((tmp_path / "s.json").read_text())["stages"]}
    assert stages["venue_coverage"]["status"] == "SKIPPED"
    assert "measurement exploded" in stages["venue_coverage"]["error"]
    assert "dump" in stages, "the capture must still be persisted"
    assert rc == 0


def test_coverage_also_actually_writes_a_row_through_main(con, tmp_path, monkeypatch):
    """The WIRING, not the stage. This is the test that was missing.

    Every other coverage test calls `stage_venue_coverage` directly, so the
    `--coverage-also` path through `main` had no test at all — and it shipped
    with `NameError: name 'now' is not defined`, found by the first live run at
    06:07Z on 2026-09-10. Same class as the `stage_paper` NameError that 526
    tests passed over: the stage was covered, the call site was not.

    It cost nothing only because session B's `_non_fatal` wrapper was already in
    place from PR #19 — the stage landed as SKIPPED carrying the error and the
    cycle still reached the dump. Without it, this NameError sat between the
    order-book capture and the only place that capture is persisted.
    """
    monkeypatch.setattr(paper_cycle, "stage_discover",
                        lambda cy, *a, **k: cy.stage("discover", paper_cycle.OK))
    monkeypatch.setattr(paper_cycle, "stage_collect",
                        lambda cy, *a, **k: cy.stage("collect:books", paper_cycle.OK))

    # A market for EACH target, or both stages report `empty_universe` and the
    # test passes without either row being written — the vacuous shape again.
    from weather_agent import database as _db
    dbpath = tmp_path / "t.duckdb"
    seed = _db.init_db(_db.connect(str(dbpath)))
    _market(seed, market_id="m11", event_id="e11",
            end_date="2026-09-11T12:00:00Z", dsv="ds1")
    _market(seed, market_id="m10", event_id="e10",
            end_date="2026-09-10T12:00:00Z", dsv="ds1")
    seed.close()

    store_root = tmp_path / "store"
    rc = paper_cycle.main([
        "--target-date", "2026-09-11", "--dataset-version", "ds1",
        "--store-root", str(store_root), "--db", str(dbpath),
        "--collect-only", "--coverage-also", "9:2026-09-10",
        "--summary-json", str(tmp_path / "s.json")])
    assert rc == 0

    import json as _json
    stages = [s for s in _json.loads((tmp_path / "s.json").read_text())["stages"]]
    other = [s for s in stages if s["stage"] == "venue_coverage:other_lead"]
    assert other, "the complementary-lead stage did not run at all"
    assert other[0]["status"] == "OK", (
        f"the complementary-lead stage failed: {other[0].get('error')}")

    import gzip as _gz
    rows = [_json.loads(l)
            for p in store.iter_shards(store_root, "venue_coverage")
            for l in _gz.open(p, "rt").read().splitlines()]
    kinds = {r["row_kind"]: r for r in rows}
    assert set(kinds) == {"own", "other_lead"}, (
        "one cycle must write exactly one row per lead")
    assert kinds["own"]["target_date"] == "2026-09-11"
    assert kinds["other_lead"]["target_date"] == "2026-09-10"
    assert kinds["other_lead"]["lead_h"] == 9.0
    # BOTH ANCHORS FROM ONE CLOCK READ: the two rows of a cycle must not straddle
    # an anchor between two readings, which is the `is_final` defect's shape.
    assert kinds["own"]["session_id"] == kinds["other_lead"]["session_id"]

    # AND THE TWO STAGES MUST BE DISTINGUISHABLE IN THE SUMMARY. Both were
    # recorded as `venue_coverage`, so a cycle writing one row per lead produced
    # two identical names and anything counting stages — which is what §4quater
    # does — would count one measurement twice.
    names = [s["stage"] for s in stages if s["stage"].startswith("venue_coverage")]
    assert names == ["venue_coverage", "venue_coverage:other_lead"], names


def test_the_stage_profile_reaches_the_committed_shard_not_only_the_summary(
        con, tmp_path, monkeypatch):
    """Session B's blocking finding on PR #23, and it is A-106 committed again.

    `cy.stage()` reaches `$ROOT/last_summary.json` — OUTSIDE `paper_state`,
    overwritten every cycle, never committed, because `run_cycle.sh:115` adds
    only `paper_state`. So per-stage timings written there would be ONE point,
    the last one, not a series. The same defect this file documents at the
    `venue_coverage` stage, committed again by the person who wrote it down.

    `cycle_params` is written on every cycle including collect-only, so the
    profile lands there: ten points a day rather than two.
    """
    monkeypatch.setattr(paper_cycle, "stage_discover",
                        lambda cy, *a, **k: cy.stage("discover", paper_cycle.OK))
    monkeypatch.setattr(paper_cycle, "stage_collect",
                        lambda cy, *a, **k: cy.stage("collect:books", paper_cycle.OK))
    store_root = tmp_path / "store"
    rc = paper_cycle.main([
        "--target-date", "2026-09-11", "--dataset-version", "ds1",
        "--store-root", str(store_root), "--db", str(tmp_path / "t.duckdb"),
        "--collect-only", "--summary-json", str(tmp_path / "s.json")])
    assert rc == 0

    import gzip as _gz
    shards = store.iter_shards(store_root, "cycle_params")
    assert shards, "no cycle_params shard was written"
    row = json.loads(_gz.open(shards[0], "rt").readline())
    prof = json.loads(row["stage_profile"])
    assert prof, "the shard carries no stage profile"
    names = [p["stage"] for p in prof]
    assert "collect:books" in names
    assert all(p["at_s"] is not None and p["elapsed_s"] is not None for p in prof), \
        "every stage must carry both its offset and its own duration"


def test_the_collect_stage_reports_how_long_the_pass_took(con, tmp_path, monkeypatch):
    """The lag from cycle start to the books landing, recorded per cycle.

    Session B measured it across 2026-09-10 and it was NOT constant:
    8.45 → 8.97 → 10.07 → 11.60 minutes over the day's four collect slots,
    monotone, while token counts stayed flat at 846/854/880/868 — so it is not
    "more work". Four points are not a trend; they are a reason to instrument.

    It matters because R24 §6bis.4septies's warm-up premise depends on no pass
    landing between a cycle's cutoff and its anchor, and this lag MOVES that
    window: a growing lag shifts it earlier, which LOWERS the delay a late slot
    would need to break the premise.

    AND THIS TEST EXISTS BECAUSE THE FIRST VERSION OF THE CHANGE WAS VACUOUS.
    The stage-side code went in, the collector-side edit silently did not apply —
    the pattern it matched occurs in four summary dicts — and the suite passed
    with 585 green because the field was simply absent and the reporting block
    skipped itself. A feature that does nothing passes every test that does not
    demand it does something.
    """
    fetched = datetime(2026, 9, 10, 9, 18, 41, tzinfo=timezone.utc)
    monkeypatch.setattr(paper_cycle.collector, "collect_books",
                        lambda *a, **k: {"tokens_requested": 3, "tokens_pending": 3,
                                         "rows_written": 3, "prices_written": 2,
                                         "prices_skipped_one_sided": 1,
                                         "requests": 1, "stopped": False,
                                         "error": None, "collected_at": fetched})
    cy = _cycle()
    cy.started_at = fetched - timedelta(minutes=11, seconds=36)
    paper_cycle.stage_collect(
        cy, con, dataset_version="ds1", session_id="cyc",
        universe=[{"token_id": "t1", "market_id": "m1"}],
        session=None, chunk_size=10)

    st = [x for x in cy.stages if x["stage"] == "collect:books"][0]
    assert st["collected_at"].startswith("2026-09-10T09:18:41")
    assert st["lag_from_cycle_start_min"] == 11.6


def _events(root):
    import gzip as _gz
    shards = store.iter_shards(root, "host_events")
    return [json.loads(l) for p in shards
            for l in _gz.open(p, "rt").read().splitlines()]


def test_host_events_queue_reaches_the_store(tmp_path):
    """A slot lost to the lock must not be indistinguishable from a dead host.

    Session B's finding on PR #15: a skip that lives only in the box's
    collect.log leaves exactly the trace of a host that never fired — no shard,
    a hole in "delivered", nothing to tell them apart. That is the distinction
    §4quater rests on when it attributes NO EVALUABLE to the host, and it also
    breaks "GitHub stays the record; nothing lives only on the box".
    """
    q = tmp_path / "pending.ndjson"
    q.write_text('{"event":"lock_timeout","mode":"collect","waited_s":900}\n'
                 '{"event":"lock_timeout","mode":"decide","waited_s":900}\n',
                 encoding="utf-8")
    out = paper_cycle.stage_host_events(_cycle(), queue_path=str(q),
                                        root=str(tmp_path), session_id="cyc")
    assert out["rows"] == 2
    rows = _events(tmp_path)
    assert [r["mode"] for r in rows] == ["collect", "decide"]
    assert all(r["drained_by_session"] == "cyc" for r in rows)
    assert not q.exists(), "the queue is consumed, not replayed every cycle"


def test_host_events_drain_does_not_lose_a_crashed_previous_drain(tmp_path):
    """The sidecar is removed only after the shard exists, so a crash re-drains.

    Read-then-truncate would drop whatever the launcher appended between the
    read and the truncate. The rename is atomic and the leftover is merged.
    """
    q = tmp_path / "pending.ndjson"
    sidecar = q.with_suffix(q.suffix + ".draining")
    sidecar.write_text('{"event":"lock_timeout","mode":"older"}\n', encoding="utf-8")
    q.write_text('{"event":"lock_timeout","mode":"newer"}\n', encoding="utf-8")

    out = paper_cycle.stage_host_events(_cycle(), queue_path=str(q),
                                        root=str(tmp_path), session_id="cyc")
    assert out["rows"] == 2
    assert {r["mode"] for r in _events(tmp_path)} == {"older", "newer"}
    assert not sidecar.exists() and not q.exists()


def test_host_events_drain_waits_for_the_queue_lock(tmp_path):
    """The drain must take the same lock the appender uses, or the rename races.

    The appending launcher does NOT hold the run lock — it is the process that
    just failed to get it — so appender and drainer genuinely meet here. A
    `write()` landing in the renamed or already-unlinked inode loses the event,
    and the event lost is the one that EXPLAINS a gap, which is the only reason
    the queue exists. Verified on the box that bash's `flock` and Python's
    `fcntl.flock` exclude each other on the same file; this pins the Python half.
    """
    import subprocess, sys as _sys, time as _time
    q = tmp_path / "pending.ndjson"
    q.write_text('{"event":"lock_timeout","mode":"collect"}\n', encoding="utf-8")
    lock = str(q) + ".lock"
    holder = subprocess.Popen(
        [_sys.executable, "-c",
         f"import fcntl,time\nfh=open({lock!r},'a+')\n"
         f"fcntl.flock(fh,fcntl.LOCK_EX)\nprint('held',flush=True)\ntime.sleep(1.5)"],
        stdout=subprocess.PIPE, text=True)
    assert holder.stdout.readline().strip() == "held"

    t0 = _time.monotonic()
    out = paper_cycle.stage_host_events(_cycle(), queue_path=str(q),
                                        root=str(tmp_path), session_id="cyc")
    waited = _time.monotonic() - t0
    holder.wait()

    assert out["rows"] == 1
    assert waited >= 1.0, f"the drain did not wait for the lock (took {waited:.2f}s)"


def test_host_events_gives_up_on_the_queue_lock_rather_than_hanging_the_cycle(
        tmp_path, monkeypatch):
    """A held queue lock must SKIP the drain, never block the cycle.

    Session B's asymmetry on PR #15: the appender waits `-w 30` while this side
    used a plain LOCK_EX with no limit — and it runs INSIDE the cycle, holding
    the run lock throughout. A pathological hold would become a hung cycle, then
    every later slot skipping, then a schedule stopped in silence: the very
    failure this PR removes, re-entering through the door the PR added.

    Nothing is lost by giving up: the queue is durable and the next cycle drains
    it. That is what makes skipping strictly better than blocking here.
    """
    import subprocess, sys as _sys, time as _time
    q = tmp_path / "pending.ndjson"
    q.write_text('{"event":"lock_timeout","mode":"collect"}\n', encoding="utf-8")
    lock = str(q) + ".lock"
    monkeypatch.setenv("PMW_QUEUE_LOCK_WAIT", "0.3")
    holder = subprocess.Popen(
        [_sys.executable, "-c",
         f"import fcntl,time\nfh=open({lock!r},'a+')\n"
         f"fcntl.flock(fh,fcntl.LOCK_EX)\nprint('held',flush=True)\ntime.sleep(2.0)"],
        stdout=subprocess.PIPE, text=True)
    assert holder.stdout.readline().strip() == "held"

    t0 = _time.monotonic()
    out = paper_cycle.stage_host_events(_cycle(), queue_path=str(q),
                                        root=str(tmp_path), session_id="cyc")
    waited = _time.monotonic() - t0
    holder.wait()

    assert out["skipped"] == "queue_locked_elsewhere"
    assert waited < 1.5, f"the drain blocked the cycle for {waited:.2f}s"
    assert q.exists() and q.read_text(encoding="utf-8").strip(), (
        "the queue must survive so the next cycle drains it")


def test_host_events_counts_malformed_lines_instead_of_swallowing_them(tmp_path):
    q = tmp_path / "pending.ndjson"
    q.write_text('{"event":"lock_timeout","mode":"collect"}\n'
                 'not json at all\n', encoding="utf-8")
    out = paper_cycle.stage_host_events(_cycle(), queue_path=str(q),
                                        root=str(tmp_path), session_id="cyc")
    assert out["rows"] == 1 and out["malformed"] == 1


def test_host_events_without_a_queue_is_a_skip_not_a_crash(tmp_path):
    out = paper_cycle.stage_host_events(_cycle(), queue_path=None,
                                        root=str(tmp_path), session_id="cyc")
    assert out["rows"] == 0
    out = paper_cycle.stage_host_events(_cycle(),
                                        queue_path=str(tmp_path / "absent.ndjson"),
                                        root=str(tmp_path), session_id="cyc")
    assert out["rows"] == 0


def test_the_profile_contains_the_dump_it_used_to_end_before(con, tmp_path,
                                                             monkeypatch):
    """Session B, reviewing the merged PR #23: the profile could not contain the
    stage that writes it.

    `stage_profile` is snapshotted inside `stage_params`, which ran BEFORE
    `stage_dump`. So the dump — the stage whose cost most plausibly grows with
    the store, which is the whole question the profile exists to answer — was
    absent. And absent SILENTLY: the entries that were there still summed to a
    plausible whole, with nothing saying one was missing, so its cost would have
    been attributed to no one on the day we finally read the series.

    The fix is the order, not a new mechanism. What stays outside is
    `stage_params` itself, which is irreducible, so the row DECLARES it rather
    than leaving the next reader to notice.

    Drives `main`, because the defect is in the call site — the stage was never
    wrong."""
    monkeypatch.setattr(paper_cycle, "stage_discover",
                        lambda cy, *a, **k: cy.stage("discover", paper_cycle.OK))
    monkeypatch.setattr(paper_cycle, "stage_collect",
                        lambda cy, *a, **k: cy.stage("collect:books", paper_cycle.OK))
    monkeypatch.setattr(paper_cycle, "stage_venue_coverage",
                        lambda cy, *a, **k: cy.stage("venue_coverage", paper_cycle.OK))

    store_root = tmp_path / "store"
    rc = paper_cycle.main([
        "--target-date", "2026-09-10", "--dataset-version", "ds1",
        "--store-root", str(store_root), "--db", str(tmp_path / "t.duckdb"),
        "--collect-only", "--summary-json", str(tmp_path / "s.json")])
    assert rc == 0

    shards = store.iter_shards(store_root, "cycle_params")
    rows = [r for sh in shards for r in store.read_shard(sh)]
    assert len(rows) == 1, "one cycle, one params row"
    row = rows[0]

    profile = {e["stage"]: e for e in json.loads(row["stage_profile"])}
    assert "dump" in profile, (
        "the dump is the stage the profile exists to measure and it was the one "
        "stage the profile could never contain")
    assert profile["dump"]["elapsed_s"] is not None

    # The irreducible omission is declared, not inferred.
    assert row["stage_profile_excludes"] == "params"
    assert "params" not in profile

    # And the series has an absolute anchor. `at_s` is relative to the start of
    # the cycle; on Actions the session_id carries the run id, not a timestamp,
    # so without this field the point cannot be placed in time at all.
    assert row["cycle_started_at"], "at_s without an anchor is not a series"
    datetime.fromisoformat(row["cycle_started_at"])

    # And the store's own size, which was computed every cycle and discarded.
    # B's third finding of this family: `store_stats` reached `cy.stage()` and
    # stopped there, so it lived in a file outside `paper_state` that nobody
    # commits — while its docstring said it existed so the growth would be
    # "visible in the run log before it becomes a problem".
    #
    # It is not curiosity. The store only grows, the cycle rebuilds it in memory
    # every run, and the host has no swap: exhausting RAM does not raise, the
    # kernel kills the process, and none of the exception machinery can see it.
    assert "store_total_bytes" in row and "store_rows_loaded" in row



def test_the_store_size_reaches_the_shard_and_is_not_always_zero(con, tmp_path,
                                                                 monkeypatch):
    """`>= 0` would have passed on a store that is always empty.

    Asserting that the FIELDS EXIST is not asserting they carry the measurement.
    So the store is seeded with real rows first and the cycle must report them:
    if the field were decorative this reads 0 and the test says so.

    The first draft of this test ran the cycle twice and expected the second to
    load what the first left. It FAILED — with every stage mocked, the first
    cycle dumps no state rows, so the store really was empty and the premise was
    mine, not the code's. Written down because a test that fails on a false
    premise looks exactly like a test that found a defect.
    """
    monkeypatch.setattr(paper_cycle, "stage_discover",
                        lambda cy, *a, **k: cy.stage("discover", paper_cycle.OK))
    monkeypatch.setattr(paper_cycle, "stage_collect",
                        lambda cy, *a, **k: cy.stage("collect:books", paper_cycle.OK))
    monkeypatch.setattr(paper_cycle, "stage_venue_coverage",
                        lambda cy, *a, **k: cy.stage("venue_coverage", paper_cycle.OK))

    store_root = tmp_path / "store"
    seeded = [{"market_id": f"m{i}", "dataset_version": "ds1", "record_version": 1,
               "event_id": "e1", "question": f"q{i}"} for i in range(3)]
    store.write_shard(seeded, table="markets", run_id="seed", root=str(store_root))

    assert paper_cycle.main([
        "--target-date", "2026-09-10", "--dataset-version", "ds1",
        "--store-root", str(store_root), "--db", str(tmp_path / "t.duckdb"),
        "--collect-only", "--summary-json", str(tmp_path / "s.json")]) == 0

    rows = [r for sh in store.iter_shards(store_root, "cycle_params")
            for r in store.read_shard(sh)]
    assert len(rows) == 1
    row = rows[0]

    assert row["store_rows_loaded"] == len(seeded), (
        "the store size never reaches the shard, or counts something else")
    assert row["store_total_bytes"] > 0

    # It is the same number the load stages of this cycle reported, not a
    # coincidence of magnitude.
    summary = json.loads((tmp_path / "s.json").read_text())
    loaded = sum(st.get("rows", 0) for st in summary["stages"]
                 if st["stage"].startswith("load:")
                 and st["stage"] != "load:store_stats")
    assert row["store_rows_loaded"] == loaded
# --------------------------------------------------------------------------- #
# THE ONE THING THAT MAKES `stage_settle`'S OBSERVATION QUERY SAFE, PINNED HERE
#
# That query asks for a station's WHOLE history — every row for (station,
# dataset_version), with no predicate on the day — and hands it to the frozen
# core. That is correct for a LOCAL_CIVIL_DAY operator, which windows the rows
# itself against `ctx.target_date`. It is WRONG for a SOURCE_DAILY_ROW operator:
# the core applies no temporal predicate there ("the row the caller hands over IS
# the source's row for target_date") and then aggregates with `max`. Handing it
# several days of history would settle a position against the maximum of the run
# so far — a plausible number, no refusal, and biased upward by construction,
# growing worse the longer the run lasts.
#
# Today that cannot happen, and NOT because of anything at the call site: the only
# SOURCE_DAILY_ROW operator requires `SERIES_HKO`, and `SERIES_CORRESPONDENCE` is
# structurally incapable of emitting that name. The safety lives three modules
# away from the query it protects, which is precisely why it is pinned here
# instead of merely argued in a comment: the day someone adds a daily-summary
# operator over a METAR series — the natural unblock for strata 5, 7 and 8 — this
# test fails and names it, instead of the run quietly settling against the wrong
# day.
# --------------------------------------------------------------------------- #
def _wide_history_offenders(operators, core_series_names):
    """Operators that would receive a multi-day history and not window it."""
    from weather_agent import settlement as _s
    return sorted(op.operator_id for op in operators
                  if op.required_series in core_series_names
                  and op.window_kind != _s.WINDOW_LOCAL_CIVIL_DAY)


def test_no_declared_series_reaches_a_source_daily_row_operator():
    from weather_agent import settlement

    declared = set(paper_cycle.SERIES_CORRESPONDENCE.values())
    assert declared, "the correspondence map is empty — the premise is gone"

    # THE SAME THESIS ONE LEVEL UP, and session B caught it on review: the check
    # below passes over an EMPTY operator registry, and so does the test written
    # to prove it can fail. That test shows the predicate FIRES; it says nothing
    # about the population being non-empty. Demonstrated by running: with
    # `OPERATORS = ()` all three assertions still held.
    #
    # The sharp form is not `len(OPERATORS) > 0` — the filter is equally vacuous
    # if the table is full of operators and NONE of them uses a series this
    # boundary can emit. So the population asserted here is the one the check is
    # actually about.
    reachable = [op.operator_id for op in settlement.OPERATORS
                 if op.required_series in declared]
    assert reachable, (
        "no operator requires a series `SERIES_CORRESPONDENCE` can emit, so the "
        "check below filters an empty set and would pass on anything")

    assert _wide_history_offenders(settlement.OPERATORS, declared) == [], (
        "stage_settle hands the station's whole history to the core. An operator "
        "that does not window by target_date would settle against the max of "
        "every day ingested so far. Either window the query in stage_settle or "
        "refuse this terna at the call site."
    )


def test_the_offender_check_can_actually_fail():
    """The check above is worthless if it cannot see the case it denies.

    A test that passes because it looks at nothing passes forever. This one
    builds the hypothetical operator — a daily-summary product over the METAR
    series the cycle really does emit — and requires the check to name it."""
    from dataclasses import replace

    from weather_agent import settlement

    declared = set(paper_cycle.SERIES_CORRESPONDENCE.values())
    hazardous = replace(
        settlement.OP_HKO_ABSMAX,
        operator_id="HYPOTHETICAL_DAILY_SUMMARY_OVER_METAR",
        required_series=next(iter(declared)),
    )
    assert hazardous.window_kind == settlement.WINDOW_SOURCE_DAILY_ROW
    assert _wide_history_offenders(
        settlement.OPERATORS + (hazardous,), declared
    ) == ["HYPOTHETICAL_DAILY_SUMMARY_OVER_METAR"]


def test_a_collect_only_cycle_persists_the_catalogue(con, tmp_path, monkeypatch):
    """The universe is not recoverable, so it cannot live only in RAM.

    `dump_catalogue` used to be `deciding or args.dump_catalogue`, reasoned
    entirely about REPLAY: a cycle that decided nothing has no decision to
    reproduce, so it needs no catalogue pinned against it. That is correct, and
    it missed what the catalogue also is — the only record of WHICH MARKETS
    EXISTED.

    Every cycle since 2026-09-09 has been collect-only, so `markets` was rebuilt
    each run from one frozen shard plus live discovery IN RAM, and the live part
    was never written. Two rows stamped `is_final: True` for the same target,
    lead and cutoff disagreed — 561 bands, then 539 — because the two events
    discovered after the freeze evaporated when their markets closed.

    Gamma's `closed=false` feed does not return what has closed. So this is the
    one thing this project treats as unrecoverable, arriving through the
    catalogue instead of through the book.

    Drives `main` with `--collect-only`, which is the path that was losing it.
    """
    monkeypatch.setattr(paper_cycle, "stage_collect",
                        lambda cy, *a, **k: cy.stage("collect:books", paper_cycle.OK))
    monkeypatch.setattr(paper_cycle, "stage_venue_coverage",
                        lambda cy, *a, **k: cy.stage("venue_coverage", paper_cycle.OK))

    def _discover(cy, con, **kw):
        db_mod.upsert(con, "markets",
                      {"market_id": "m1", "dataset_version": "ds1",
                       "record_version": 1, "event_id": "e1", "question": "q"},
                      ("market_id", "dataset_version", "record_version"))
        cy.stage("discover", paper_cycle.OK)
    monkeypatch.setattr(paper_cycle, "stage_discover", _discover)

    store_root = tmp_path / "store"
    assert paper_cycle.main([
        "--target-date", "2026-09-10", "--dataset-version", "ds1",
        "--store-root", str(store_root), "--db", str(tmp_path / "t.duckdb"),
        "--collect-only", "--summary-json", str(tmp_path / "s.json")]) == 0

    rows = [r for sh in store.iter_shards(store_root, "markets")
            for r in store.read_shard(sh)]
    assert rows, (
        "a collect-only cycle discovered a market and did not persist it — the "
        "universe existed only in RAM and the feed will not return it once the "
        "market closes")
    assert rows[0]["market_id"] == "m1"

    summary = json.loads((tmp_path / "s.json").read_text())
    dump = next(s for s in summary["stages"] if s["stage"] == "dump")
    assert dump["catalogue"] == "dumped"


def test_rows_resident_does_not_count_a_duplicate_shard_twice(con, tmp_path,
                                                              monkeypatch):
    """`rows_loaded` and `rows_resident` must diverge, and by the copy.

    Dumping the catalogue every cycle (this PR) means the store holds many
    copies of the same market rows. Each copy loads as its OWN batch, so
    `upsert_many` — which deduplicates only WITHIN a batch — returns its full
    size again, and `rows_loaded` counts it again. That number is correct about
    the work done and wrong for the RAM projection, which needs DISTINCT rows.

    Session B caught it on review of this PR. Without this test the two fields
    would be equal in every fixture and nothing would show the difference.
    """
    monkeypatch.setattr(paper_cycle, "stage_discover",
                        lambda cy, *a, **k: cy.stage("discover", paper_cycle.OK))
    monkeypatch.setattr(paper_cycle, "stage_collect",
                        lambda cy, *a, **k: cy.stage("collect:books", paper_cycle.OK))
    monkeypatch.setattr(paper_cycle, "stage_venue_coverage",
                        lambda cy, *a, **k: cy.stage("venue_coverage", paper_cycle.OK))

    store_root = tmp_path / "store"
    fila = [{"market_id": "m1", "dataset_version": "ds1", "record_version": 1,
             "event_id": "e1", "question": "q"}]
    # THE SAME row in three separate shards — exactly what a per-cycle catalogue
    # dump produces.
    for run in ("a", "b", "c"):
        store.write_shard(fila, table="markets", run_id=run, root=str(store_root))

    assert paper_cycle.main([
        "--target-date", "2026-09-10", "--dataset-version", "ds1",
        "--store-root", str(store_root), "--db", str(tmp_path / "t.duckdb"),
        "--collect-only", "--summary-json", str(tmp_path / "s.json")]) == 0

    summary = json.loads((tmp_path / "s.json").read_text())
    st = next(s for s in summary["stages"] if s["stage"] == "load:store_stats")

    assert st["rows_loaded"] == 3, "three shards, three batches, three counted"
    assert st["rows_resident"] == 1, (
        "one distinct market row occupies memory once — if this reads 3 the "
        "ceiling projection is inflated by every duplicate copy")

    # AND IT HAS TO REACH THE SHARD, which is where the first version of this
    # test did not look. It asserted on the STAGE, so it passed while
    # `stage_params` never wrote the field — the value stopped exactly where PR
    # #23 taught us values stop, and the test was standing at the same place.
    row = [r for sh in store.iter_shards(store_root, "cycle_params")
           for r in store.read_shard(sh)][0]
    assert row["store_rows_loaded"] == 3
    assert row["store_rows_resident"] == 1, (
        "the resident count reached the stage and not the row — a reader dating "
        "the RAM ceiling from the committed series would find the field absent")

def test_an_identical_catalogue_is_not_dumped_twice(con, tmp_path, monkeypatch):
    """Two cycles over the same universe must leave ONE catalogue shard.

    Counted in the STORE, not asserted on the stage. That is the lesson PR #34
    cost us: `rows_resident` reached `cy.stage()` and never the row, and the test
    that should have caught it was reading the stage too — standing in the same
    place as the error, so it confirmed it instead of detecting it.

    The cost this prevents is dated: a catalogue row loads in 21.3 ms on the box,
    the snapshot is 2 200 rows, and ten dumps a day put `load:*` past the
    42-minute budget between day +2 and +3 — after which the `flock` makes the
    next cycle skip, and what it skips is a book slot.
    """
    monkeypatch.setattr(paper_cycle, "stage_collect",
                        lambda cy, *a, **k: cy.stage("collect:books", paper_cycle.OK))
    monkeypatch.setattr(paper_cycle, "stage_venue_coverage",
                        lambda cy, *a, **k: cy.stage("venue_coverage", paper_cycle.OK))

    def _discover(cy, con, **kw):
        db_mod.upsert(con, "markets",
                      {"market_id": "m1", "dataset_version": "ds1",
                       "record_version": 1, "event_id": "e1", "question": "q"},
                      ("market_id", "dataset_version", "record_version"))
        cy.stage("discover", paper_cycle.OK)
    monkeypatch.setattr(paper_cycle, "stage_discover", _discover)

    store_root = tmp_path / "store"

    def _run(tag):
        assert paper_cycle.main([
            "--target-date", "2026-09-10", "--dataset-version", "ds1",
            "--store-root", str(store_root), "--db", str(tmp_path / f"{tag}.duckdb"),
            "--collect-only", "--summary-json", str(tmp_path / f"{tag}.json")]) == 0

    _run("first")
    tras_uno = len(store.iter_shards(store_root, "markets"))
    _run("second")
    tras_dos = len(store.iter_shards(store_root, "markets"))

    assert tras_uno == 1, "el primer ciclo debe escribir el catalogo"
    assert tras_dos == 1, (
        "el segundo ciclo vio el MISMO universo y volvio a volcarlo: cada copia "
        "cuesta 21,3 ms por fila en todos los replays posteriores")


def test_a_changed_catalogue_is_dumped_again(con, tmp_path, monkeypatch):
    """And the skip must not be a ban: a universe that GREW has to be written.

    Without this the previous test passes on a `stage_dump` that never dumps the
    catalogue at all — which would re-create the defect PR #31 exists to fix, and
    the shard count alone cannot tell the two apart."""
    monkeypatch.setattr(paper_cycle, "stage_collect",
                        lambda cy, *a, **k: cy.stage("collect:books", paper_cycle.OK))
    monkeypatch.setattr(paper_cycle, "stage_venue_coverage",
                        lambda cy, *a, **k: cy.stage("venue_coverage", paper_cycle.OK))

    store_root = tmp_path / "store"
    vistos = {"n": 0}

    def _discover(cy, con, **kw):
        vistos["n"] += 1
        for i in range(vistos["n"]):          # 1 mercado, luego 2
            db_mod.upsert(con, "markets",
                          {"market_id": f"m{i}", "dataset_version": "ds1",
                           "record_version": 1, "event_id": "e1", "question": "q"},
                          ("market_id", "dataset_version", "record_version"))
        cy.stage("discover", paper_cycle.OK)
    monkeypatch.setattr(paper_cycle, "stage_discover", _discover)

    def _run(tag):
        assert paper_cycle.main([
            "--target-date", "2026-09-10", "--dataset-version", "ds1",
            "--store-root", str(store_root), "--db", str(tmp_path / f"{tag}.duckdb"),
            "--collect-only", "--summary-json", str(tmp_path / f"{tag}.json")]) == 0

    _run("first")
    _run("second")
    assert len(store.iter_shards(store_root, "markets")) == 2, (
        "el universo crecio de 1 a 2 mercados y el segundo volcado NO se escribio: "
        "el salto se ha convertido en una prohibicion")


def test_a_failing_catalogue_gate_dumps_anyway_AND_says_so(con, tmp_path,
                                                           monkeypatch):
    """Fail-open is half the requirement; the other half is not being silent.

    Session B named the case: `CONFLICT_COLS[table]` raising `KeyError` the day a
    catalogue table is added without declaring its keys is PERMANENT. A silent
    fail-open would return False forever, the catalogue would go back to 2 200
    rows a cycle, and the 2-3 day budget crossing this stage removes would come
    back through the error path with nothing in any log.

    So the dump must still happen AND the failure must reach the profile — which
    is where someone looks in three days asking why the cycle grew again."""
    monkeypatch.setattr(paper_cycle, "stage_collect",
                        lambda cy, *a, **k: cy.stage("collect:books", paper_cycle.OK))
    monkeypatch.setattr(paper_cycle, "stage_venue_coverage",
                        lambda cy, *a, **k: cy.stage("venue_coverage", paper_cycle.OK))

    def _discover(cy, con, **kw):
        db_mod.upsert(con, "markets",
                      {"market_id": "m1", "dataset_version": "ds1",
                       "record_version": 1, "event_id": "e1", "question": "q"},
                      ("market_id", "dataset_version", "record_version"))
        cy.stage("discover", paper_cycle.OK)
    monkeypatch.setattr(paper_cycle, "stage_discover", _discover)

    def _boom(*a, **k):
        raise KeyError("no conflict cols for this table")
    monkeypatch.setattr(paper_cycle, "catalogue_is_unchanged", _boom)

    store_root = tmp_path / "store"
    assert paper_cycle.main([
        "--target-date", "2026-09-10", "--dataset-version", "ds1",
        "--store-root", str(store_root), "--db", str(tmp_path / "t.duckdb"),
        "--collect-only", "--summary-json", str(tmp_path / "s.json")]) == 0

    assert store.iter_shards(store_root, "markets"), (
        "the gate raised and the dump did not happen — fail-open is the whole "
        "point: a spurious dump costs seconds, a skipped one loses the universe")

    stages = {st["stage"]: st for st in
              json.loads((tmp_path / "s.json").read_text())["stages"]}
    gate = stages.get("dump:markets:gate")
    assert gate is not None, (
        "the gate failed and nothing recorded it — a permanent failure would "
        "restore the per-cycle dump with no line anywhere")
    assert gate["status"] == paper_cycle.STOPPED
    assert "no conflict cols" in gate["error"]


def test_code_commit_is_asked_of_git_when_actions_is_not_there(tmp_path, monkeypatch):
    """The sha must reach the ROW off Actions, which is where we now run.

    `GITHUB_SHA` is an Actions variable and collection moved to the box on
    2026-09-09, so this field has written None into every shard since -- six of
    six on 2026-09-11. The project's own rule is that a count without its sha is
    not a fact, and the box has been producing exactly those.

    Asserted on the SHARD and not on the stage, for the reason PR #34 already
    cost us once.
    """
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    monkeypatch.setattr(paper_cycle, "stage_discover",
                        lambda cy, *a, **k: cy.stage("discover", paper_cycle.OK))
    monkeypatch.setattr(paper_cycle, "stage_collect",
                        lambda cy, *a, **k: cy.stage("collect:books", paper_cycle.OK))
    monkeypatch.setattr(paper_cycle, "stage_venue_coverage",
                        lambda cy, *a, **k: cy.stage("venue_coverage", paper_cycle.OK))

    store_root = tmp_path / "store"
    assert paper_cycle.main([
        "--target-date", "2026-09-10", "--dataset-version", "ds1",
        "--store-root", str(store_root), "--db", str(tmp_path / "t.duckdb"),
        "--collect-only", "--summary-json", str(tmp_path / "s.json")]) == 0

    row = [r for sh in store.iter_shards(store_root, "cycle_params")
           for r in store.read_shard(sh)][0]
    sha = row["code_commit"]
    assert sha, "no sha in the row — the cycle recorded no code identity at all"
    assert len(sha.split("-")[0]) == 40, f"not a full sha: {sha!r}"


def test_code_commit_prefers_the_actions_variable_when_it_is_set():
    """Running ON Actions must keep reporting what Actions says.

    The repo checkout there is the code that runs, but `GITHUB_SHA` is the
    authority for WHICH sha that is (for a pull_request run it is the merge
    commit, which `rev-parse HEAD` would also give -- and if the two ever
    disagree, the platform is right about its own run).
    """
    import os as _os
    prev = _os.environ.get("GITHUB_SHA")
    _os.environ["GITHUB_SHA"] = "deadbeef" * 5
    try:
        assert paper_cycle.code_commit() == "deadbeef" * 5
    finally:
        if prev is None:
            _os.environ.pop("GITHUB_SHA", None)
        else:
            _os.environ["GITHUB_SHA"] = prev


def test_code_commit_marks_a_dirty_tree_rather_than_naming_a_tree_that_did_not_run(
        monkeypatch):
    """A sha names a tree. If the working copy was edited, it names the wrong one.

    A false fact is worse than a missing one: `<sha>-dirty` says the row cannot
    be reproduced from that commit alone, which is the honest claim.
    """
    monkeypatch.delenv("GITHUB_SHA", raising=False)

    class _Done:
        def __init__(self, out):
            self.returncode, self.stdout = 0, out

    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        if "rev-parse" in cmd:
            return _Done("a" * 40 + "\n")
        return _Done(" M scripts/paper_cycle.py\n")

    monkeypatch.setattr(paper_cycle.subprocess, "run", fake_run)
    assert paper_cycle.code_commit() == "a" * 40 + "-dirty(1 modified, 0 untracked)"


def test_dirty_says_WHAT_dirtied_it_because_the_two_cases_are_not_alike(monkeypatch):
    """A stray artefact and a hand-placed source file are not the same finding.

    Both used to produce the identical `-dirty`, and the harmless one is the one
    that actually happens -- so the reader would learn to skip it, and the day it
    meant something they would skip it too. B's objection, and the counts cost
    nothing: `git status --porcelain` already returns the lines.
    """
    monkeypatch.delenv("GITHUB_SHA", raising=False)

    class _Done:
        def __init__(self, out):
            self.returncode, self.stdout = 0, out

    def fake_run(cmd, **kw):
        if "rev-parse" in cmd:
            return _Done("b" * 40 + "\n")
        return _Done("?? scripts/hotfix.py\n?? notes.txt\n M src/weather_agent/paper.py\n")

    monkeypatch.setattr(paper_cycle.subprocess, "run", fake_run)
    assert paper_cycle.code_commit() == "b" * 40 + "-dirty(1 modified, 2 untracked)"


def test_code_commit_degrades_to_none_instead_of_aborting_a_cycle(monkeypatch):
    """No field is worth killing a cycle over -- least of all a bookkeeping one.

    It runs after `stage_dump` (PR #25), so a throw could not lose a capture. It
    could still end a cycle, and the failure it would be reacting to leaves us
    exactly where we already are: no sha.
    """
    monkeypatch.delenv("GITHUB_SHA", raising=False)

    def boom(cmd, **kw):
        raise OSError("git not found")

    monkeypatch.setattr(paper_cycle.subprocess, "run", boom)
    assert paper_cycle.code_commit() is None


# ---------------------------------------------------------------------------
# The machine the cycle did not fit into
# ---------------------------------------------------------------------------

def test_ru_maxrss_is_converted_on_linux_and_not_on_macos():
    """`ru_maxrss` is KiB on Linux and BYTES on macOS. The box is Linux.

    Written as a test and not as a comment because the failure is silent and
    exactly 1 024x: a field that reads 24 MB where the truth is 24 GB, or the
    reverse, and nothing in the number says which. Development runs on macOS and
    production on Linux, so whichever platform the author checked on would look
    right.
    """
    class _Uso:
        ru_maxrss = 1000

    for plataforma, esperado in (("linux", 1000 * 1024), ("darwin", 1000)):
        with mock.patch.object(paper_cycle.sys, "platform", plataforma), \
             mock.patch("resource.getrusage", return_value=_Uso()):
            assert paper_cycle.machine_stats()["rss_peak_bytes"] == esperado, (
                f"en {plataforma} el pico sale mal por un factor de 1024")


def test_meminfo_is_parsed_in_bytes_and_both_fields_come_out():
    meminfo = ("MemTotal:        3911132 kB\n"
               "MemFree:          128880 kB\n"
               "MemAvailable:     402312 kB\n"
               "Buffers:            1234 kB\n")
    with mock.patch("builtins.open", mock.mock_open(read_data=meminfo)):
        out = paper_cycle.machine_stats()
    assert out["mem_total_bytes"] == 3911132 * 1024
    assert out["mem_available_bytes"] == 402312 * 1024


def test_an_unavailable_measurement_is_None_and_never_zero():
    """"No lo medí" y "medí cero" son hechos distintos.

    This field exists to be believed on the day it reports a small number. A 0
    standing in for "there is no /proc here" would read as "no memory left",
    which is the alarm it is meant to raise for real.
    """
    with mock.patch("builtins.open", side_effect=OSError("no /proc")):
        out = paper_cycle.machine_stats()
    assert out["mem_available_bytes"] is None
    assert out["mem_total_bytes"] is None
    assert out["rss_peak_bytes"] is not None, (
        "getrusage sigue disponible: sin /proc se pierde la memoria libre, no el pico")


def test_the_machine_fields_reach_the_SHARD_and_not_only_the_stage(
        tmp_path, monkeypatch):
    """The lesson PR #34 cost, applied before it costs it again.

    `rows_resident` was computed, passed to `cy.stage()` and never written to the
    row — and the test that should have caught it was reading the stage too,
    standing in the same place as the error. So this asserts on the SHARD.
    """
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    for nombre in ("stage_discover", "stage_collect", "stage_venue_coverage"):
        monkeypatch.setattr(paper_cycle, nombre,
                            lambda cy, *a, **k: cy.stage("x", paper_cycle.OK))

    store_root = tmp_path / "store"
    assert paper_cycle.main([
        "--target-date", "2026-09-10", "--dataset-version", "ds1",
        "--store-root", str(store_root), "--db", str(tmp_path / "t.duckdb"),
        "--collect-only", "--summary-json", str(tmp_path / "s.json")]) == 0

    fila = [r for sh in store.iter_shards(store_root, "cycle_params")
            for r in store.read_shard(sh)][0]
    for campo in ("rss_peak_bytes", "mem_available_bytes", "mem_total_bytes"):
        assert campo in fila, (
            f"{campo} no llego a la fila: es el defecto del #23 otra vez, un "
            "valor que se queda en la etapa")
    assert fila["rss_peak_bytes"] and fila["rss_peak_bytes"] > 1_000_000, (
        f"pico de {fila['rss_peak_bytes']!r} bytes: un proceso de Python no "
        "cabe en eso, asi que o la unidad esta mal o no se midio")
