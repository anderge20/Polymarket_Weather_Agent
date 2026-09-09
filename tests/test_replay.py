"""Tests for scripts/replay_cycle.py — the instrument R24's criterion C3 invokes.

A reproducibility check that cannot FAIL is worthless, so most of these tests
corrupt the record on purpose and assert that the replay notices.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from weather_agent import database, paper, store

_SPEC = importlib.util.spec_from_file_location(
    "replay_cycle", Path(__file__).resolve().parents[1] / "scripts" / "replay_cycle.py")
replay_cycle = importlib.util.module_from_spec(_SPEC)
sys.modules["replay_cycle"] = replay_cycle
_SPEC.loader.exec_module(replay_cycle)


T0 = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
PT = T0.isoformat()
DSV = "ds1"
SESSION = "cyc_test"

BOOK = {"asks": [{"price": 0.50, "size": 10_000}], "bids": [{"price": 0.49, "size": 100}],
        "truncated": False}


def _seed(tmp_path, *, entry_price=None, size=None, extra_trade=False,
          tau=0.03, drop_trade=False):
    """Build a store holding one cycle: params, catalogue, book, signal, trade."""
    con = database.init_db(database.connect(":memory:"))
    con.execute(
        "INSERT INTO markets (market_id, event_id, fee_regime, source_timestamps, "
        "ingestion_timestamp, dataset_version, record_version) VALUES (?,?,?,?,?,?,?)",
        ["m1", "e1", "weather_fees", '{"endDate":"2026-09-10T12:00:00Z"}', T0, DSV, 1])
    con.execute(
        "INSERT INTO market_fee_schedule (fee_regime, taker_fee, fee_status, "
        "raw_fee_fields, ingestion_timestamp, dataset_version, record_version) "
        "VALUES (?,?,?,?,?,?,?)",
        ["weather_fees", 0.05, "KNOWN",
         '{"feeSchedule":{"exponent":1,"rate":0.05}}', T0, DSV, 1])
    for tok, lab in (("t_yes", "Yes"), ("t_no", "No")):
        con.execute(
            "INSERT INTO outcomes (market_id, token_id, outcome_label, band_label, "
            "ingestion_timestamp, dataset_version, record_version) VALUES (?,?,?,?,?,?,?)",
            ["m1", tok, lab, "15C", T0, DSV, 1])
    # The book is stamped BEFORE prediction_time, which is the real ordering the
    # cycle produces (collection first, decision instant settled after it). An
    # earlier fixture put both at the same instant — a situation main() cannot
    # produce, which is how the replay's predicate mismatch went unnoticed.
    con.execute(
        'INSERT INTO orderbook_snapshots (token_id, "timestamp", market_id, '
        "book_snapshot, ingestion_timestamp, dataset_version, record_version) "
        "VALUES (?,?,?,?,?,?,?)",
        ["t_yes", T0 - timedelta(minutes=5), "m1", json.dumps(BOOK), T0, DSV, 1])
    con.execute(
        'INSERT INTO signals (market_id, token_id, strategy, "timestamp", signal, '
        "fair_value, price_assumption, edge, ingestion_timestamp, dataset_version, "
        "record_version) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ["m1", "t_yes", "strategy_a_v1", T0, "BUY", 0.70, 0.50, 0.20, T0, DSV, 1])

    params = paper.PaperParams(bankroll=10_000.0, fixed_fraction=0.02, size_cap=0.02,
                              tau_exec=tau, exit_mode="hold_to_resolution", x_exec=0.0)
    decision = paper.decide_and_fill(signal="BUY", p_model=0.70, book_snapshot=BOOK,
                                     fee=paper.FeeParams(0.05, 1.0, "weather_fees"),
                                     params=params)
    assert decision["open"]
    fill = decision["fill"]
    if not drop_trade:
        con.execute(
            "INSERT INTO paper_trades (backtest_id, market_id, token_id, entry_time, "
            "entry_price, fees, size, price_layer, ingestion_timestamp, "
            "dataset_version, record_version) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [SESSION, "m1", "t_yes", T0,
             entry_price if entry_price is not None else fill.vwap,
             fill.fee, size if size is not None else fill.shares,
             "SIMULATED_EXECUTABLE", T0, DSV, 1])
    if extra_trade:
        con.execute(
            "INSERT INTO paper_trades (backtest_id, market_id, token_id, entry_time, "
            "entry_price, fees, size, price_layer, ingestion_timestamp, "
            "dataset_version, record_version) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [SESSION, "m1", "t_ghost", T0, 0.5, 0.1, 10.0,
             "SIMULATED_EXECUTABLE", T0, DSV, 1])

    for table in ("markets", "market_fee_schedule", "outcomes",
                  "orderbook_snapshots", "signals", "paper_trades"):
        store.dump_table(con, table, run_id=SESSION, root=tmp_path, when=T0)
    con.close()

    store.write_shard([{
        "session_id": SESSION, "dataset_version": DSV, "prediction_time": PT,
        "target_date": "2026-09-10", "tau_exec": tau, "bankroll": 10_000.0,
        "fixed_fraction": 0.02, "size_cap": 0.02, "x_exec": 0.0,
        "exit_mode": "hold_to_resolution", "model": "icon_seamless",
    }], table="cycle_params", run_id=SESSION, root=tmp_path, when=T0)
    return fill


# --------------------------------------------------------------------------- happy path
def test_an_untouched_cycle_replays_exactly(tmp_path):
    _seed(tmp_path)
    out = replay_cycle.replay(str(tmp_path), SESSION)
    assert out["ok"] is True
    assert out["trades"]["mismatched"] == 0
    assert out["trades"]["matched"] == 1


def test_the_replay_uses_the_recorded_prediction_time_not_the_clock(tmp_path):
    _seed(tmp_path)
    out = replay_cycle.replay(str(tmp_path), SESSION)
    assert out["params"]["prediction_time"] == PT


def test_the_replay_uses_the_recorded_parameters_not_todays_defaults(tmp_path):
    _seed(tmp_path, tau=0.03)
    out = replay_cycle.replay(str(tmp_path), SESSION)
    assert out["params"]["tau_exec"] == 0.03
    assert out["ok"] is True


# --------------------------------------------------------------------------- it must be able to fail
def test_a_tampered_entry_price_is_caught(tmp_path):
    _seed(tmp_path, entry_price=0.42)
    out = replay_cycle.replay(str(tmp_path), SESSION)
    assert out["ok"] is False
    assert out["trades"]["mismatched"] == 1
    assert "entry_price" in out["trades"]["examples"][0]["diffs"]


def test_a_tampered_size_is_caught(tmp_path):
    _seed(tmp_path, size=1.0)
    out = replay_cycle.replay(str(tmp_path), SESSION)
    assert out["ok"] is False
    assert "size" in out["trades"]["examples"][0]["diffs"]


def test_a_trade_with_no_supporting_signal_is_caught(tmp_path):
    """The audit that matters most: a position in the ledger the decision path
    cannot account for."""
    _seed(tmp_path, extra_trade=True)
    out = replay_cycle.replay(str(tmp_path), SESSION)
    assert out["ok"] is False
    assert ("m1", "t_ghost") in [tuple(k) for k in out["trades"]["only_persisted"]]


def test_a_missing_trade_is_caught(tmp_path):
    _seed(tmp_path, drop_trade=True)
    out = replay_cycle.replay(str(tmp_path), SESSION)
    assert out["ok"] is False
    assert out["trades"]["only_recomputed"]


def test_a_cycle_with_no_recorded_params_cannot_be_replayed(tmp_path):
    _seed(tmp_path)
    out = replay_cycle.replay(str(tmp_path), "some_other_session")
    assert out["ok"] is False and "no cycle_params" in out["error"]


def test_a_collect_only_cycle_replays_as_trivially_reproducible(tmp_path):
    store.write_shard([{"session_id": "c0", "dataset_version": DSV,
                        "prediction_time": PT, "tau_exec": None}],
                      table="cycle_params", run_id="c0", root=tmp_path, when=T0)
    out = replay_cycle.replay(str(tmp_path), "c0")
    assert out["ok"] is True
    assert "skipped" in out["trades"]


def test_the_cli_exit_code_gates_on_the_verdict(tmp_path, capsys):
    _seed(tmp_path, entry_price=0.42)
    rc = replay_cycle.main(["--session-id", SESSION, "--store-root", str(tmp_path)])
    assert rc == 1                                   # non-zero: it can gate a run
    assert "NOT REPRODUCIBLE" in capsys.readouterr().out

    _seed(tmp_path / "clean")
    rc = replay_cycle.main(["--session-id", SESSION,
                            "--store-root", str(tmp_path / "clean")])
    assert rc == 0
    assert "VERDICT: REPRODUCIBLE" in capsys.readouterr().out


def test_a_book_stamped_after_the_decision_is_never_used(tmp_path):
    """The as-of invariant of the execution layer: a fill must not use a book that
    did not exist yet at prediction_time. Both the cycle and the replay go through
    paper.select_book, so this pins it for both."""
    from weather_agent import database, paper
    con = database.init_db(database.connect(":memory:"))
    try:
        for offset, price in ((-5, 0.50), (+5, 0.10)):
            con.execute(
                'INSERT INTO orderbook_snapshots (token_id, "timestamp", market_id, '
                "book_snapshot, ingestion_timestamp, dataset_version, record_version) "
                "VALUES (?,?,?,?,?,?,?)",
                ["t", T0 + timedelta(minutes=offset), "m",
                 json.dumps({"asks": [{"price": price, "size": 1000}], "bids": []}),
                 T0, DSV, 1])
        snap = paper.select_book(con, token_id="t", dataset_version=DSV, asof=T0)
        assert snap["asks"][0]["price"] == 0.50      # the past one, not the future one
    finally:
        con.close()
