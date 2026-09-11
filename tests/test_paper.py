"""Tests for weather_agent.paper (R23) — offline, no network, no wallet.

The fee tests reproduce Polymarket's OWN published 100-share table
(p=0.05 -> $0.24, p=0.10 -> $0.45, p=0.50 -> $1.25). That table is the check that
distinguishes D19's adopted semantics (feeSchedule.rate = 0.05) from the rejected
one (makerBaseFee/takerBaseFee = 1000 bps = 10%), which would give $2.50 at p=0.5.
If someone ever "fixes" the fee model to use the bps fields, these fail.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timezone

import pytest

from weather_agent import database, paper


T0 = datetime(2026, 9, 9, 7, 30, tzinfo=timezone.utc)

#: The caller's target_date (2D §C). A trade carries the day it was opened
#: for; nothing downstream rebuilds it from `endDate`.
TD_TEST = date(2026, 9, 10)


FEE = paper.FeeParams(rate=0.05, exponent=1.0, regime="weather_fees")

PARAMS = paper.PaperParams(
    bankroll=10_000.0, fixed_fraction=0.02, size_cap=0.02,
    tau_exec=0.03, exit_mode="hold_to_resolution", x_exec=0.0,
)


def _asks(*levels):
    return {"asks": [{"price": p, "size": s} for p, s in levels],
            "bids": [], "truncated": False}


# =============================================================================
# Fees — D19
# =============================================================================
@pytest.mark.parametrize("price,expected", [(0.05, 0.24), (0.10, 0.45), (0.50, 1.25)])
def test_fee_reproduces_the_official_100_share_table(price, expected):
    fee = paper.round_fee(100 * paper.taker_fee_per_share(price, rate=0.05))
    assert fee == pytest.approx(expected, abs=0.005)


def test_the_rejected_bps_reading_would_not_reproduce_the_table():
    """1000 bps = 10% gives $2.50 at p=0.5, not $1.25 — which is why D19 rejects it."""
    wrong = 100 * paper.taker_fee_per_share(0.5, rate=0.10)
    assert wrong == pytest.approx(2.50)
    assert wrong != pytest.approx(1.25)


def test_fee_is_symmetric_between_a_token_and_its_complement():
    assert paper.taker_fee_per_share(0.3, rate=0.05) == pytest.approx(
        paper.taker_fee_per_share(0.7, rate=0.05))


def test_fee_peaks_at_one_half():
    peak = paper.taker_fee_per_share(0.5, rate=0.05)
    assert peak == pytest.approx(0.0125)
    for p in (0.1, 0.3, 0.7, 0.9):
        assert paper.taker_fee_per_share(p, rate=0.05) < peak


def test_a_sub_resolution_fee_rounds_to_zero_and_is_not_floored():
    """D19's refutation correction: 0.00001 is a rounding resolution, not a floor."""
    tiny = paper.round_fee(0.000004)
    assert tiny == 0.0


def test_price_outside_the_unit_interval_is_rejected():
    with pytest.raises(ValueError):
        paper.taker_fee_per_share(1.5, rate=0.05)


def test_fee_params_fail_closed_when_the_fee_is_not_known():
    assert paper.resolve_fee_params({"fee_status": "UNKNOWN", "taker_fee": 0.05}) is None
    assert paper.resolve_fee_params({"fee_status": "KNOWN", "taker_fee": None}) is None
    assert paper.resolve_fee_params({}) is None
    assert paper.resolve_fee_params(None) is None


def test_fee_params_reject_a_non_linear_exponent():
    row = {"fee_status": "KNOWN", "taker_fee": 0.05,
           "raw_fee_fields": {"feeSchedule": {"exponent": 2, "rate": 0.05}}}
    assert paper.resolve_fee_params(row) is None


def test_fee_params_accept_the_observed_weather_schedule():
    row = {"fee_status": "KNOWN", "taker_fee": 0.05, "fee_regime": "weather_fees",
           "raw_fee_fields": {"feeSchedule": {"exponent": 1, "rate": 0.05,
                                              "takerOnly": True, "rebateRate": 0.25}}}
    fp = paper.resolve_fee_params(row)
    assert fp is not None and fp.rate == 0.05 and fp.exponent == 1.0


def test_disabled_fees_are_a_justified_zero_not_an_unknown():
    row = {"fee_status": "KNOWN", "taker_fee": 0.0, "fee_regime": "fees_disabled"}
    fp = paper.resolve_fee_params(row)
    assert fp is not None and fp.rate == 0.0


# =============================================================================
# Fill simulation
# =============================================================================
def test_a_fill_walks_levels_and_prices_at_vwap():
    book = _asks((0.40, 100), (0.42, 100))
    fill = paper.simulate_taker_buy(book, max_cash=1000.0, fee=FEE, max_shares=150)
    assert fill.executable and fill.levels_used == 2
    assert fill.shares == pytest.approx(150)
    # 100 @ 0.40 + 50 @ 0.42
    assert fill.notional == pytest.approx(100 * 0.40 + 50 * 0.42)
    assert fill.vwap == pytest.approx(fill.notional / 150)


def test_the_budget_covers_the_fee_not_just_the_notional():
    """D19 (2): fees are charged ON TOP of the pre-fee notional. Sizing against the
    notional alone overspends by the fee on every single trade."""
    book = _asks((0.50, 10_000))
    fill = paper.simulate_taker_buy(book, max_cash=200.0, fee=FEE)
    # the budget is spent to the last cent, modulo the venue's 5-decimal fee
    # rounding (documented tolerance: half of 1e-5 USDC)
    assert fill.outlay == pytest.approx(200.0, abs=5e-6)
    assert fill.outlay <= 200.0 + 5e-6
    # naive sizing would have bought 400 shares and spent 200 + 5 in fees
    assert fill.shares < 400
    assert fill.shares == pytest.approx(200.0 / (0.50 + 0.05 * 0.5 * 0.5))


def test_the_fill_never_takes_more_than_a_level_holds():
    book = _asks((0.10, 7), (0.90, 10_000))
    fill = paper.simulate_taker_buy(book, max_cash=1000.0, fee=FEE)
    assert fill.detail[0]["shares"] == pytest.approx(7)
    assert fill.detail[0]["shares"] <= fill.detail[0]["size_available"]


def test_an_empty_ask_side_yields_no_fill():
    fill = paper.simulate_taker_buy({"asks": [], "bids": []}, max_cash=100.0, fee=FEE)
    assert not fill.executable and fill.reason == "empty_book_side"


def test_levels_are_re_sorted_so_a_bad_snapshot_cannot_fill_at_the_worst_price():
    book = {"asks": [{"price": 0.90, "size": 100}, {"price": 0.10, "size": 100}],
            "bids": []}
    fill = paper.simulate_taker_buy(book, max_cash=20.0, fee=FEE)
    assert fill.detail[0]["price"] == 0.10          # best ask first, not payload order


def test_a_fill_below_the_share_minimum_is_not_executable():
    book = _asks((0.50, 10_000))
    fill = paper.simulate_taker_buy(book, max_cash=1.0, fee=FEE)
    assert fill.shares > 0                          # it computed a fill...
    assert not fill.executable                      # ...but refuses to call it real
    assert fill.reason == "below_min_order_shares"


def test_a_fill_below_the_notional_minimum_is_not_executable():
    """6 shares clears the 5-share bound but only $0.60 of notional: the stricter
    of the two readings of `minimum_order_size` rejects it."""
    book = _asks((0.10, 6))
    fill = paper.simulate_taker_buy(book, max_cash=1.0, fee=FEE)
    assert fill.shares == pytest.approx(6, abs=0.5)
    assert not fill.executable and fill.reason == "below_min_order_notional"


def test_exhausting_the_stored_ladder_is_flagged():
    book = _asks((0.40, 100))
    fill = paper.simulate_taker_buy(book, max_cash=10_000.0, fee=FEE)
    assert fill.executable and fill.book_exhausted is True


def test_a_budget_bound_fill_is_not_flagged_as_exhausted():
    book = _asks((0.40, 100_000))
    fill = paper.simulate_taker_buy(book, max_cash=200.0, fee=FEE)
    assert fill.executable and fill.book_exhausted is False


def test_a_budget_that_binds_on_the_last_level_is_not_exhausted():
    """The for/else formulation got this wrong: the budget bound, the ladder did not."""
    book = _asks((0.40, 10), (0.50, 10_000))
    fill = paper.simulate_taker_buy(book, max_cash=100.0, fee=FEE)
    assert fill.book_exhausted is False


def test_truncation_of_the_stored_book_is_carried_into_the_fill():
    book = dict(_asks((0.40, 100)), truncated=True)
    fill = paper.simulate_taker_buy(book, max_cash=10_000.0, fee=FEE)
    assert fill.book_truncated is True


def test_zero_budget_yields_no_fill():
    fill = paper.simulate_taker_buy(_asks((0.4, 100)), max_cash=0.0, fee=FEE)
    assert not fill.executable and fill.reason == "no_budget"


def test_malformed_levels_are_skipped_not_priced():
    book = {"asks": [{"price": "x", "size": 10}, {"price": 0.4, "size": 0},
                     {"price": 0.5, "size": 100}], "bids": []}
    fill = paper.simulate_taker_buy(book, max_cash=100.0, fee=FEE)
    assert fill.detail[0]["price"] == 0.5           # 0-size and unparseable dropped


# =============================================================================
# Sizing and the gate
# =============================================================================
def test_position_cash_takes_the_tighter_of_fraction_and_cap():
    p = paper.PaperParams(bankroll=10_000.0, fixed_fraction=0.10, size_cap=0.02,
                          tau_exec=0.03, exit_mode="hold_to_resolution", x_exec=0.0)
    assert paper.position_cash(p) == pytest.approx(200.0)


def test_params_reject_an_unknown_exit_mode_and_bad_numbers():
    base = dict(bankroll=1.0, fixed_fraction=0.02, size_cap=0.02, tau_exec=0.03,
                x_exec=0.0)
    with pytest.raises(ValueError):
        paper.PaperParams(exit_mode="yolo", **base)
    with pytest.raises(ValueError):
        paper.PaperParams(exit_mode="hold_to_resolution", **{**base, "tau_exec": 0.0})
    with pytest.raises(ValueError):
        paper.PaperParams(exit_mode="hold_to_resolution", **{**base, "x_exec": -0.1})
    with pytest.raises(ValueError):
        paper.PaperParams(exit_mode="hold_to_resolution",
                          **{**base, "fixed_fraction": 1.5})


def test_net_edge_charges_the_entry_fee_and_nothing_else_when_held():
    e = paper.net_edge_per_share(p_model=0.60, fill_price=0.50, fee=FEE, params=PARAMS)
    assert e == pytest.approx(0.10 - 0.0125)


def test_taker_close_charges_an_exit_fee_too():
    p = paper.PaperParams(bankroll=1.0, fixed_fraction=0.02, size_cap=0.02, tau_exec=0.01,
                          exit_mode="taker_close", x_exec=0.0)
    e = paper.net_edge_per_share(p_model=0.60, fill_price=0.50, fee=FEE, params=p,
                                 exit_price=0.50)
    assert e == pytest.approx(0.10 - 2 * 0.0125)


def test_x_exec_is_subtracted_as_declared():
    p = paper.PaperParams(bankroll=1.0, fixed_fraction=0.02, size_cap=0.02, tau_exec=0.01,
                          exit_mode="hold_to_resolution", x_exec=0.005)
    e = paper.net_edge_per_share(p_model=0.60, fill_price=0.50, fee=FEE, params=p)
    assert e == pytest.approx(0.10 - 0.0125 - 0.005)


# =============================================================================
# The decision
# =============================================================================
def test_a_buy_with_enough_edge_opens():
    out = paper.decide_and_fill(signal="BUY", p_model=0.70,
                                book_snapshot=_asks((0.50, 10_000)),
                                fee=FEE, params=PARAMS)
    assert out["open"] is True and out["fill"].executable
    assert out["net_edge"] == pytest.approx(0.20 - 0.0125)


def test_the_edge_is_judged_at_the_fill_price_not_the_quote():
    """A thin top level makes the achievable price worse than the quote. The gate
    must see the worse one, or the engine credits an edge nobody could take."""
    book = _asks((0.50, 1), (0.68, 10_000))
    out = paper.decide_and_fill(signal="BUY", p_model=0.70, book_snapshot=book,
                                fee=FEE, params=PARAMS)
    assert out["fill"].vwap > 0.67                  # dragged up by the deep level
    assert out["open"] is False and out["reason"] == "net_edge_below_tau"


def test_an_edge_below_tau_does_not_open():
    out = paper.decide_and_fill(signal="BUY", p_model=0.52,
                                book_snapshot=_asks((0.50, 10_000)),
                                fee=FEE, params=PARAMS)
    assert out["open"] is False and out["reason"] == "net_edge_below_tau"


def test_an_unknown_fee_blocks_the_trade():
    out = paper.decide_and_fill(signal="BUY", p_model=0.99,
                                book_snapshot=_asks((0.01, 10_000)),
                                fee=None, params=PARAMS)
    assert out["open"] is False and out["reason"] == "fee_unknown_fail_closed"


def test_hold_and_none_signals_are_not_actionable():
    for sig in ("HOLD", "NONE", "SELL"):
        out = paper.decide_and_fill(signal=sig, p_model=0.9,
                                    book_snapshot=_asks((0.1, 10_000)),
                                    fee=FEE, params=PARAMS)
        assert out["open"] is False
        assert out["reason"].startswith("signal_not_actionable")


def test_a_fade_prices_the_complement_against_the_complements_own_book():
    """p_model=0.30 on Yes means 0.70 on No. Buying the No book at 0.50 is a
    +0.20 edge — and the No book is what must be passed in, never 1 - ask_yes."""
    out = paper.decide_and_fill(signal="FADE", p_model=0.30,
                                book_snapshot=_asks((0.50, 10_000)),
                                fee=FEE, params=PARAMS)
    assert out["open"] is True
    assert out["net_edge"] == pytest.approx(0.20 - 0.0125)


def test_a_fade_on_a_high_model_probability_is_rejected():
    out = paper.decide_and_fill(signal="FADE", p_model=0.80,
                                book_snapshot=_asks((0.50, 10_000)),
                                fee=FEE, params=PARAMS)
    assert out["open"] is False and out["reason"] == "net_edge_below_tau"


# =============================================================================
# Ledger
# =============================================================================
@pytest.fixture
def con():
    c = database.init_db(database.connect(":memory:"))
    try:
        yield c
    finally:
        c.close()


def _open_one(con, *, p_model=0.70, ask=0.50):
    out = paper.decide_and_fill(signal="BUY", p_model=p_model,
                                book_snapshot=_asks((ask, 10_000)),
                                fee=FEE, params=PARAMS)
    assert out["open"]
    return paper.record_paper_trade(
        con, backtest_id="run1", market_id="m1", token_id="t1", entry_time=T0,
        fill=out["fill"], bankroll_after=9_800.0, dataset_version="ds1",
        target_date=TD_TEST), out["fill"]


def test_an_open_position_has_no_pnl_yet(con):
    tid, _ = _open_one(con)
    row = con.execute(
        "SELECT price_layer, exit_time, net_pnl, gross_pnl FROM paper_trades "
        "WHERE paper_trade_id = ?", [tid]).fetchone()
    assert row[0] == "SIMULATED_EXECUTABLE"
    assert row[1] is None
    assert row[2] is None and row[3] is None        # NULL, not 0.0


def test_settling_a_winner_books_the_payout_minus_fees(con):
    tid, fill = _open_one(con)
    res = paper.settle_paper_trade(con, tid, settlement=1, exit_time=T0)
    assert res["gross_pnl"] == pytest.approx(fill.shares * (1.0 - fill.vwap))
    assert res["net_pnl"] == pytest.approx(res["gross_pnl"] - fill.fee)
    assert res["net_pnl"] < res["gross_pnl"]        # the fee is really charged


def test_settling_a_loser_loses_the_stake_and_the_fee(con):
    tid, fill = _open_one(con)
    res = paper.settle_paper_trade(con, tid, settlement=0, exit_time=T0)
    assert res["gross_pnl"] == pytest.approx(-fill.shares * fill.vwap)
    assert res["net_pnl"] == pytest.approx(res["gross_pnl"] - fill.fee)


def test_a_fractional_settlement_is_refused(con):
    tid, _ = _open_one(con)
    with pytest.raises(ValueError, match="must be 0 or 1"):
        paper.settle_paper_trade(con, tid, settlement=0.5, exit_time=T0)


def test_settling_an_unknown_trade_raises(con):
    with pytest.raises(ValueError, match="no paper_trade"):
        paper.settle_paper_trade(con, 9999, settlement=1, exit_time=T0)


def test_open_positions_lists_only_the_unsettled(con):
    a, _ = _open_one(con)
    b, _ = _open_one(con)
    paper.settle_paper_trade(con, a, settlement=1, exit_time=T0)
    ids = [r["paper_trade_id"] for r in
           paper.open_positions(con, backtest_id="run1", dataset_version="ds1")]
    assert ids == [b]


def test_ledger_summary_counts_open_positions_without_pnl(con):
    a, _ = _open_one(con)
    _open_one(con)
    paper.settle_paper_trade(con, a, settlement=1, exit_time=T0)
    s = paper.ledger_summary(con, backtest_id="run1", dataset_version="ds1")
    assert s["n_trades"] == 2 and s["n_open"] == 1
    assert s["net_pnl"] > 0
    assert math.isfinite(s["fees"]) and s["fees"] > 0


# =============================================================================
# Gate D0 — structural, not advisory
# =============================================================================
def test_the_engine_cannot_place_a_real_order():
    src = (__import__("pathlib").Path(paper.__file__)).read_text(encoding="utf-8")
    for forbidden in ("private_key", "PRIVATE_KEY", "api_secret", "API_SECRET",
                      "eth_account", "web3", "post_order", "place_order",
                      "requests.post", "signature"):
        assert forbidden not in src, f"paper.py must not reference {forbidden!r}"


# =============================================================================
# select_book — one predicate, shared by the cycle and the replay
# =============================================================================
def test_select_book_honours_the_as_of(con):
    from datetime import timedelta
    for offset, price in ((-10, 0.40), (+10, 0.90)):
        con.execute(
            'INSERT INTO orderbook_snapshots (token_id, "timestamp", market_id, '
            "book_snapshot, ingestion_timestamp, dataset_version, record_version) "
            "VALUES (?,?,?,?,?,?,?)",
            ["t1", T0 + timedelta(minutes=offset), "m1",
             __import__("json").dumps({"asks": [{"price": price, "size": 10}],
                                       "bids": []}),
             T0, "ds1", 1])
    snap = paper.select_book(con, token_id="t1", dataset_version="ds1", asof=T0)
    assert snap["asks"][0]["price"] == 0.40      # the older one, never the future one


def test_select_book_returns_none_when_nothing_is_admissible(con):
    from datetime import timedelta
    con.execute(
        'INSERT INTO orderbook_snapshots (token_id, "timestamp", market_id, '
        "book_snapshot, ingestion_timestamp, dataset_version, record_version) "
        "VALUES (?,?,?,?,?,?,?)",
        ["t1", T0 + timedelta(hours=1), "m1", '{"asks":[],"bids":[]}', T0, "ds1", 1])
    assert paper.select_book(con, token_id="t1", dataset_version="ds1", asof=T0) is None


def test_select_book_is_scoped_to_the_dataset_version(con):
    con.execute(
        'INSERT INTO orderbook_snapshots (token_id, "timestamp", market_id, '
        "book_snapshot, ingestion_timestamp, dataset_version, record_version) "
        "VALUES (?,?,?,?,?,?,?)",
        ["t1", T0, "m1", '{"asks":[],"bids":[]}', T0, "other_dsv", 1])
    assert paper.select_book(con, token_id="t1", dataset_version="ds1", asof=T0) is None


def test_the_cycle_and_the_replay_call_the_same_selector():
    """The regression this closes: two different book predicates over the same
    table select different rows, so the replay reported NOT REPRODUCIBLE for
    cycles that were correct."""
    from pathlib import Path as _P
    root = _P(__file__).resolve().parents[1]
    cyc = (root / "scripts" / "paper_cycle.py").read_text()
    rep = (root / "scripts" / "replay_cycle.py").read_text()
    for src, name in ((cyc, "paper_cycle"), (rep, "replay_cycle")):
        assert "paper.select_book(" in src, f"{name} must use the shared selector"
        assert "FROM orderbook_snapshots" not in src, \
            f"{name} must not hand-roll its own book query"


# --------------------------------------------------------------------------- #
# A BUY FILLS AGAINST A BOOK WITH NO BID, AND `taker_close` PRICES AN EXIT THAT
# CANNOT HAPPEN.
#
# Measured over the 36,850 books collected 2026-09-09..11: 69.8% two-sided,
# **15.1% ask-only**, 15.1% bid-only. The ask-only ones are precisely the books a
# taker BUY walks. Nothing in `decide_and_fill` looked at the bid side — `paper.py`
# named "bids" in exactly one place, the ladder-key selector.
#
# `hold_to_resolution` is unaffected and is the default: redemption needs no
# counterparty. The refusal belongs only to the mode that plans to sell.
# --------------------------------------------------------------------------- #
def _ask_only_book():
    return {"asks": [{"price": 0.40, "size": 500.0}], "bids": []}


def _two_sided_book():
    return {"asks": [{"price": 0.40, "size": 500.0}],
            "bids": [{"price": 0.38, "size": 500.0}]}


def test_taker_close_refuses_a_book_with_no_bid():
    """The exit is impossible, so the position must not open — and must say why."""
    params = paper.PaperParams(bankroll=1000.0, fixed_fraction=0.02, size_cap=0.02,
                               tau_exec=0.001, exit_mode="taker_close", x_exec=0.0)

    out = paper.decide_and_fill(signal="BUY", p_model=0.90,
                                book_snapshot=_ask_only_book(),
                                fee=FEE, params=params)

    assert out["open"] is False
    assert out["reason"] == "no_exit_liquidity", (
        "an exit priced at the fill price on a book with no bid is not an "
        "expensive exit, it is an impossible one")


def test_the_same_book_opens_when_the_plan_is_to_hold():
    """The guard must not be a blanket ban on thin books.

    Redemption at resolution needs no counterparty, so a missing bid costs
    nothing under `hold_to_resolution`. If this test fails the guard has stopped
    being about the exit and started being about liquidity in general."""
    params = paper.PaperParams(bankroll=1000.0, fixed_fraction=0.02, size_cap=0.02,
                               tau_exec=0.001, exit_mode="hold_to_resolution",
                               x_exec=0.0)

    out = paper.decide_and_fill(signal="BUY", p_model=0.90,
                                book_snapshot=_ask_only_book(),
                                fee=FEE, params=params)

    assert out["open"] is True, "hold_to_resolution never needed the bid"


def test_taker_close_still_opens_when_a_bid_exists():
    """And the guard must not refuse the case it was never about."""
    params = paper.PaperParams(bankroll=1000.0, fixed_fraction=0.02, size_cap=0.02,
                               tau_exec=0.001, exit_mode="taker_close", x_exec=0.0)

    out = paper.decide_and_fill(signal="BUY", p_model=0.90,
                                book_snapshot=_two_sided_book(),
                                fee=FEE, params=params)

    assert out["open"] is True
    assert out["reason"] is None
