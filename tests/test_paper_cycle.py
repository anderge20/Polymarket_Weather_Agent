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

from weather_agent import database, database as db_mod, store
from weather_agent import observations as obs_mod

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
    """Source-level: the ordering is the whole fix, so pin it."""
    src = (Path(__file__).resolve().parents[1] / "scripts" / "paper_cycle.py").read_text()
    i_collect = src.index("stage_collect(cy, con")
    i_settle = src.index("timing = decision_time(target_date, args.lead_hours, _utcnow())")
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
                              dataset_version="ds1")
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
        fill=fill, bankroll_after=1.0, dataset_version="ds1")


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
    con.execute(
        "INSERT INTO paper_trades (backtest_id, market_id, token_id, entry_time, "
        "entry_price, fees, size, price_layer, ingestion_timestamp, "
        "dataset_version, record_version) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ["cyc", market_id, f"{market_id}_yes", T0, 0.5, 0.1, 10.0,
         "SIMULATED_EXECUTABLE", T0, dsv, 1])


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

    out = paper_cycle.stage_observations(
        _cycle(), con, dataset_version="ds1",
        now=datetime(2026, 9, 10, 23, 0, tzinfo=timezone.utc))
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
    assert paper_cycle.to_core_series(obs_mod.SERIES_1F) is None
    assert paper_cycle.to_core_series(obs_mod.SERIES_TENTH_F) is None
    assert paper_cycle.to_core_series(None) is None
