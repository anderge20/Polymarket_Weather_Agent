"""
test_backtest.py — R19: the engine's three load-bearing rules.

These fixtures are small ON PURPOSE and they are not the evidence. Three times in
this project a green suite certified a world that did not exist — the fake CLOB
session, `markets.station` holding an airport name, the replay that never pointed
at real data. What these tests can do is pin the rules that a real run cannot
show you because a wrong answer still looks like a number.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from weather_agent import backtest, costs

WEATHER_FEES = costs.FeeSpec(enabled=True, rate=0.05, exponent=1.0, taker_only=True)

Q_C = {10: 18.0, 25: 19.0, 50: 20.0, 75: 21.0, 90: 22.0}


def _cand(**kw):
    base = dict(
        market_id="m", token_id="t", station="EGLC", target_date=date(2026, 5, 1),
        lead_h=24, decision_time=datetime(2026, 4, 30, 12, tzinfo=timezone.utc),
        label_available_at=datetime(2026, 5, 3, 0, tzinfo=timezone.utc),
        unit="C", lo=20.0, hi=20.0, q_market=dict(Q_C), spec=WEATHER_FEES, p_mid=0.20, p_model=0.40, edge_gross=0.20, edge_net=0.10,
        p_exec=0.21, fee=0.008, margin=0.05, won=True, pnl=0.8)
    base.update(kw)
    return backtest.Candidate(**base)


# --------------------------------------------------------------------- margin
def test_tau_in_fahrenheit_scales_and_does_not_offset():
    """§A.4. tau is a DIFFERENCE. Adding 32 would displace the distribution by 18
    degrees and drive the margin to ~1 for every narrow band — the same family as
    the B-7 unit defect, which produced a confident inverted probability."""
    assert backtest.tau_in_unit("C") == pytest.approx(0.545)
    assert backtest.tau_in_unit("F") == pytest.approx(0.981)
    assert backtest.tau_in_unit("F") < 1.0     # NOT 32.545 -> 58.58


def test_margin_is_larger_for_a_narrow_central_band_than_a_wide_tail_one():
    """Why §2 forbids a constant margin in probability points: displacing by tau
    moves a narrow band near the centre a lot and a wide tail band very little.
    One constant would be a threshold with two operands."""
    narrow = backtest.calibration_margin(Q_C, unit="C", lo=20.0, hi=20.0)
    wide_tail = backtest.calibration_margin(Q_C, unit="C", lo=None, hi=14.0)
    assert narrow > wide_tail


def test_margin_is_non_negative_and_bounded():
    for lo, hi in ((None, 15.0), (19.0, 21.0), (25.0, None), (20.0, 20.0)):
        m = backtest.calibration_margin(Q_C, unit="C", lo=lo, hi=hi)
        assert 0.0 <= m <= 1.0


def test_margin_uses_the_worst_direction():
    """max over the two signs, not one — a shift that helps this band in one
    direction hurts it in the other, and the margin must cover the harm."""
    m = backtest.calibration_margin(Q_C, unit="C", lo=22.0, hi=22.0)
    assert m > 0.0


# ----------------------------------------------------------------- passes_exec
def test_fail_closed_row_is_not_actionable():
    """`edge_net is None` is a substrate gap, not a rejection by threshold. It
    must never read as a signal in either direction."""
    assert _cand(edge_net=None).passes_exec is False


def test_execution_filter_compares_against_the_margin_alone():
    assert _cand(edge_net=0.06, margin=0.05).passes_exec is True
    assert _cand(edge_net=0.04, margin=0.05).passes_exec is False


# ------------------------------------------------------------------ select_tau
def test_tau_with_no_training_trades_cannot_win_by_vacuity():
    """A tau that selects nothing has no median. §4.1 blocks this downstream;
    blocking it here too means the walk-forward never PICKS the vacuous one."""
    train = [_cand(edge_gross=0.03, pnl=1.0)]
    tau = backtest.select_tau(train)
    assert tau is not None and tau <= 0.03


def test_ties_go_to_the_larger_tau():
    """§3, frozen: fewer trades, a stricter rule."""
    train = [_cand(edge_gross=0.50, pnl=1.0), _cand(edge_gross=0.50, pnl=1.0)]
    assert backtest.select_tau(train) == max(backtest.TAU_SIGNAL_GRID)


def test_select_tau_returns_none_on_an_empty_window():
    assert backtest.select_tau([]) is None


def test_grid_is_exactly_the_preregistered_one():
    assert backtest.TAU_SIGNAL_GRID == tuple(round(0.02 * k, 4) for k in range(1, 11))
    assert len(backtest.TAU_SIGNAL_GRID) == 10


# ---------------------------------------------------------------- walk_forward
def test_walk_forward_cannot_train_on_a_label_that_was_not_available():
    """THE test. Filtering on `target_date < D` instead of on label availability
    is the leak that withdrew M2 v1 — it leaked in 8 of 8 stations, by -9 h to
    -43 h. Here the only other candidate settles AFTER the decision instant, so a
    correct engine has no training set and takes nothing."""
    d = date(2026, 5, 10)
    t = backtest.decision_time(d, 24)
    today = _cand(target_date=d, label_available_at=t + timedelta(days=2))
    yesterday = _cand(target_date=d - timedelta(days=1),
                      label_available_at=t + timedelta(hours=1))  # 1 h TOO LATE
    taken, chosen = backtest.walk_forward([today, yesterday])
    assert taken == []
    assert all(v["tau"] is None for v in chosen.values())


def test_walk_forward_trains_on_a_label_that_was_available():
    """The mirror of the previous test: move the label one hour earlier and the
    same engine trades. Without this, the test above would also pass on an engine
    that never trades at all."""
    d = date(2026, 5, 10)
    t = backtest.decision_time(d, 24)
    today = _cand(target_date=d, label_available_at=t + timedelta(days=2),
                  edge_gross=0.50)
    earlier = _cand(target_date=d - timedelta(days=1),
                    label_available_at=t - timedelta(hours=1), edge_gross=0.50)
    taken, chosen = backtest.walk_forward([today, earlier])
    assert len(taken) == 1 and taken[0].target_date == d


def test_a_taken_trade_is_never_one_whose_own_label_trained_it():
    """No row may appear in its own training window: `label_available_at` of a
    same-day trade is always after that day's decision instant."""
    d = date(2026, 6, 1)
    t = backtest.decision_time(d, 24)
    c = _cand(target_date=d, label_available_at=t + timedelta(days=2))
    assert c.label_available_at > t


# --------------------------------------------------------------------- reprice
def test_reprice_keeps_the_candidate_set_identical():
    """§A.2's ladder must move only the execution assumption. If repricing could
    drop or add a row, the sensitivity columns would be comparing different
    universes and the comparison would mean nothing."""
    cs = [_cand(p_mid=0.20, p_model=0.40), _cand(p_mid=0.60, p_model=0.10)]
    for x in costs.X_EXEC_SENSITIVITY:
        out = backtest.reprice(cs, x_exec=x)
        assert len(out) == len(cs)
        assert [c.market_id for c in out] == [c.market_id for c in cs]
        assert [c.p_model for c in out] == [c.p_model for c in cs]
        assert [c.margin for c in out] == [c.margin for c in cs]
        assert [c.won for c in out] == [c.won for c in cs]


def test_a_cheaper_execution_never_makes_a_trade_worse():
    """Monotone in x_exec, in both the edge and the realised PnL. A ladder that
    was not monotone would mean the cost was entering somewhere else too."""
    c = _cand(p_mid=0.20, p_model=0.40)
    nets, pnls = [], []
    for x in (0.01, 0.005, 0.001, 0.0):
        r = backtest.reprice([c], x_exec=x)[0]
        nets.append(r.edge_net); pnls.append(r.pnl)
    assert nets == sorted(nets)
    assert pnls == sorted(pnls)


# --------------------------------------------------------------- band_position
def test_band_position_is_declared_from_the_forecast_not_the_outcome():
    """R22 §2: the axis must be observable at the decision instant. It reads only
    the quantiles and the band edges — never `won`."""
    assert backtest.band_position(Q_C, 20.0, 20.0) == "centro"
    assert backtest.band_position(Q_C, 18.5, 18.5) == "cola_cercana"
    assert backtest.band_position(Q_C, 30.0, 30.0) == "cola_lejana"


def test_a_tail_band_uses_its_open_edge_and_not_an_invented_midpoint():
    """A band with one open side has no midpoint; averaging against a made-up
    bound would place it somewhere the contract never said."""
    assert backtest.band_position(Q_C, None, 14.0) == "cola_lejana"
    assert backtest.band_position(Q_C, 26.0, None) == "cola_lejana"
    assert backtest.band_position(Q_C, None, None) == "abierta_ambos"


# ---------------------------------------------------------------------------
# A1 — the objective `select_tau` maximises
# ---------------------------------------------------------------------------

def _obj_cand(p_model, p_mid, won, edge_gross):
    """One candidate at the real fee schedule, for objective tests only."""
    from datetime import date, datetime, timezone
    from weather_agent import backtest as bt, costs
    spec = costs.FeeSpec(enabled=True, rate=0.05, exponent=1, taker_only=True)
    net, p_exec, fee = costs.edge_net(p_model=p_model, mid=p_mid, spec=spec)
    return bt.Candidate(
        market_id="m", token_id="t", station="KJFK", target_date=date(2026, 7, 1),
        lead_h=24, decision_time=datetime(2026, 6, 30, 12, tzinfo=timezone.utc),
        label_available_at=datetime(2026, 7, 2, tzinfo=timezone.utc), unit="F",
        lo=78.0, hi=78.0, q_market={10: 74, 25: 76, 50: 78, 75: 79, 90: 81},
        spec=spec, p_mid=p_mid, p_model=p_model, edge_gross=edge_gross,
        edge_net=net, p_exec=p_exec, fee=fee, margin=0.0, won=won,
        pnl=costs.realised_pnl(won=won, p_exec=p_exec, fee=fee))


def _two_bucket_population():
    """A population where the RIGHT answer is unambiguous and the median gets it
    wrong: a GOOD bucket (real edge, 15-cent tickets) and a CHEAP bucket (tiny
    edge, 2-cent tickets). Both have win rates under 50 %, as every band in this
    universe does — which is the precondition the median cannot survive."""
    import random
    rng = random.Random(11)
    pop = []
    for _ in range(1000):
        pop.append(_obj_cand(0.30, 0.15, rng.random() < 0.30, 0.15))
    for _ in range(1000):
        pop.append(_obj_cand(0.06, 0.02, rng.random() < 0.06, 0.04))
    return pop


def test_median_objective_ranks_by_ticket_price_not_expected_value():
    """The defect, pinned so it cannot come back silently. With every win rate
    below 50 % the median is always a loser's PnL, so maximising it prefers the
    bucket with the CHEAPEST tickets regardless of what they earn."""
    from statistics import mean
    from weather_agent import backtest as bt
    pop = _two_bucket_population()

    cheap = [c.pnl for c in pop if c.edge_gross >= 0.04 and c.passes_exec]
    good = [c.pnl for c in pop if c.edge_gross >= 0.15 and c.passes_exec]
    # the 15-cent bucket earns strictly more per trade...
    assert mean(good) > mean(cheap) * 1.5
    # ...and the median still prefers the other one.
    assert bt.select_tau(pop, objective=bt.OBJ_MEDIAN_R21) == pytest.approx(0.04)


def test_trimmed_mean_objective_picks_the_profitable_bucket():
    """The property, not a magic number: the chosen tau must admit the GOOD bucket
    (edge 0.15) and exclude the CHEAP one (edge 0.04). Every tau in 0.06..0.14
    does exactly that and scores identically, so the documented tie-break to the
    larger tau lands on 0.14 — 0.15 is not even on the grid, which is multiples
    of 0.02."""
    from weather_agent import backtest as bt
    tau = bt.select_tau(_two_bucket_population())
    assert 0.04 < tau <= 0.15, f"tau {tau} does not separate the two buckets"
    taken = [c for c in _two_bucket_population()
             if c.edge_gross >= tau and c.passes_exec]
    assert taken and all(c.edge_gross == pytest.approx(0.15) for c in taken), \
        "the chosen tau admitted the cheap bucket"


def test_the_default_objective_is_the_trimmed_mean():
    from weather_agent import backtest as bt
    pop = _two_bucket_population()
    assert bt.select_tau(pop) == bt.select_tau(pop, objective=bt.OBJ_TRIMMED_MEAN)
    assert bt.select_tau(pop) != bt.select_tau(pop, objective=bt.OBJ_MEDIAN_R21)


def test_the_r21_median_objective_is_still_reachable():
    """PREREG_R21 §3 froze the median and the published R21 numbers came from it.
    Keeping it selectable is what lets that result stay reproducible — the same
    reason `error_model` keeps its withdrawn v3."""
    from weather_agent import backtest as bt
    assert bt.select_tau(_two_bucket_population(),
                         objective=bt.OBJ_MEDIAN_R21) is not None


def test_unknown_objective_is_refused_rather_than_defaulted():
    from weather_agent import backtest as bt
    with pytest.raises(ValueError):
        bt.select_tau(_two_bucket_population(), objective="mean")


def test_trimmed_mean_degenerates_to_the_mean_on_a_small_sample():
    """Never trims to nothing: with fewer than 1/frac points there is no tail to
    cut, and the plain mean is the right answer."""
    from statistics import mean
    from weather_agent.backtest import _trimmed_mean
    for n in (1, 2, 3, 5, 9):
        v = [float(i) for i in range(n)]
        assert _trimmed_mean(v) == pytest.approx(mean(v))


def test_trimmed_mean_actually_cuts_the_tail_it_exists_for():
    """The concern the median was chosen for: one extreme value fixing the mean."""
    from weather_agent.backtest import _trimmed_mean
    base = [1.0] * 20
    assert _trimmed_mean(base + [10_000.0]) == pytest.approx(1.0)
