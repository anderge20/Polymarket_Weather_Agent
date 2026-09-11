"""
weather_agent.paper — paper execution engine (R23)
==================================================
STATUS: IMPLEMENTED + TESTED (tests/test_paper.py, offline). NOT VALIDATED: a
paper run against the live catalogue is R24 and needs its own preregistration.

WHAT THIS IS
------------
Strategy A produces a signal and an *indicative* price. An indicative price is not
a fill: it is a midpoint the venue publishes, and a strategy backtested on it is
backtested on a price nobody could have traded. This module closes that gap — it
takes the order book the collector actually observed, walks it, and reports what
the position would have cost. Hence `price_layer='SIMULATED_EXECUTABLE'`: better
than INDICATIVE, and explicitly not EXECUTABLE, which is reserved for a real fill.

GATE D0 IS STRUCTURAL HERE, NOT A POLICY NOTE
---------------------------------------------
The user's standing constraint is that no real money moves without their explicit
permission. This module cannot break it: it has no wallet, no signer, no private
key, no order endpoint, and imports nothing that has one. `tests/test_paper.py`
asserts that as a property of the source text, so a future edit that adds an order
path fails the suite rather than shipping quietly.

THE COST MODEL IS D19's, NOT A NEW ONE
--------------------------------------
Taken verbatim from FEES_SEMANTICS.md §2 (adopted as D19):
    c_taker(p) = r · (p·(1-p))^e            with r = feeSchedule.rate, e = exponent
    fee_total  = round5(sum_i C_i · c_taker(p_i))
    outlay     = sum_i C_i·p_i + fee_total
    edge_net_per_share = (p_model - p_fill) - c_taker(p_fill) - exit_cost - x_exec
Rounding follows the refutation's correction: 0.00001 USDC is NOT a floor —
"anything smaller rounds to zero" — so a fee that rounds to 0 IS 0.
Fail-closed per D19: fee_status != 'KNOWN', or an exponent other than 1, yields no
fee and therefore no trade. A position is never opened on an unpriced cost.

FADE IS BOUGHT, NOT INFERRED
----------------------------
D19 writes FADE as "NO at 1-p", which is the *pricing* identity, not an execution
plan. Assuming the No token's ask equals 1 - (Yes ask) would fabricate a price:
the two tokens have separate books and separate spreads, and in these markets
(`neg_risk: true`, OBSERVED 2026-09-09) they are not even the same instrument
mechanically. So a FADE is simulated as what it is — a taker BUY of the No token
against the No token's own observed book.

MINIMUM ORDER SIZE — a declared ambiguity, resolved conservatively
------------------------------------------------------------------
OBSERVED (CLOB /markets, 2026-09-09): `minimum_order_size: 5`, alongside
`minimum_tick_size: 0.001`. The field name says "size", and `size` in the book
payload is a share count, so the literal reading is 5 SHARES. But Polymarket's UI
speaks of a $5 minimum, which would be 5 USDC of notional — a stricter bound at
every price below 1. Which one the matching engine enforces is UNKNOWN to us.
This module therefore requires BOTH (>= 5 shares AND >= $5 notional) before it
will call a fill executable. That can only reject trades the venue would have
accepted; it can never invent one it would have refused. Under-reporting paper
activity is a survivable error, over-reporting executability is not.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Sequence

from . import database as db

SOURCE = "paper_engine_v1"
PRICE_LAYER = "SIMULATED_EXECUTABLE"

#: USDC decimals used for fee rounding (docs: "rounded to 5 decimal places").
FEE_DECIMALS = 5

#: Conservative dual bound on order size — see the module docstring.
MIN_ORDER_SHARES = 5.0
MIN_ORDER_NOTIONAL_USDC = 5.0


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require(name: str, value: Any) -> Any:
    if value is None:
        raise ValueError(f"paper: obligatory parameter {name!r} is missing (fail-closed)")
    return value


# =============================================================================
# Fees (D19 / FEES_SEMANTICS.md §2)
# =============================================================================
def taker_fee_per_share(price: float, *, rate: float, exponent: float = 1.0) -> float:
    """c_taker(p) = r · (p·(1-p))^e — USDC per share, before rounding.

    Symmetric by construction: buying Yes at p and No at 1-p cost the same."""
    p = float(price)
    if not (0.0 <= p <= 1.0):
        raise ValueError(f"paper: price {p!r} outside [0,1]")
    return float(rate) * (p * (1.0 - p)) ** float(exponent)


def round_fee(fee: float) -> float:
    """Round to 5 decimals. Sub-0.00001 fees round to ZERO — the docs say
    "anything smaller rounds to zero", so 0.00001 is a resolution, not a floor.
    (This was a live correction from D19's refutation; do not reintroduce a floor.)"""
    return round(float(fee), FEE_DECIMALS)


@dataclass(frozen=True)
class FeeParams:
    """Resolved, trade-ready fee parameters. Existence == the fee is KNOWN."""
    rate: float
    exponent: float
    regime: str


def resolve_fee_params(market_row: dict) -> FeeParams | None:
    """Turn a `market_fee_schedule`-shaped row into usable parameters, or None.

    Returns None (fail-closed, D19) when the fee is not KNOWN, when the rate is
    missing, or when the exponent is anything but 1 — the non-linear curve has
    never been observed live, so trading on an assumed shape is not allowed."""
    if not market_row:
        return None
    if market_row.get("fee_status") != "KNOWN":
        return None
    rate = market_row.get("taker_fee")
    if rate is None:
        return None
    raw = market_row.get("raw_fee_fields") or {}
    schedule = raw.get("feeSchedule") if isinstance(raw, dict) else None
    exponent = 1.0
    if isinstance(schedule, dict) and schedule.get("exponent") is not None:
        exponent = float(schedule["exponent"])
    if exponent != 1.0:
        return None
    return FeeParams(rate=float(rate), exponent=exponent,
                     regime=str(market_row.get("fee_regime") or "UNKNOWN"))


# =============================================================================
# Fill simulation
# =============================================================================
@dataclass
class Fill:
    """The outcome of walking a book. `executable` is the only field a caller
    should branch on; the rest explain why."""
    shares: float = 0.0
    notional: float = 0.0            # sum(shares_i * price_i), fees excluded
    vwap: float | None = None
    fee: float | None = None
    outlay: float | None = None      # notional + fee (what leaves the bankroll)
    levels_used: int = 0
    executable: bool = False
    reason: str | None = None
    book_exhausted: bool = False
    book_truncated: bool = False
    detail: list[dict] = field(default_factory=list)


def select_book(con, *, token_id: str, dataset_version: str, asof) -> dict | None:
    """The ONE way a book is chosen for a fill. Both the live cycle and the replay
    call this, and that is the point.

    They used to differ: the cycle took the latest book of its own collector
    session with NO time predicate, while the replay took the latest book at or
    before `prediction_time`. Two different predicates over the same table select
    different rows, so the replay could report NOT REPRODUCIBLE for a cycle that
    was perfectly correct — and, worse, the cycle could fill against a book
    timestamped AFTER the as-of it claims to respect. Writing the predicate once
    removes the whole class.

    `asof` is the decision instant. `orderbook_snapshots."timestamp"` is OUR
    capture instant (the collector sets it), so `timestamp <= asof` is the honest
    as-of test for a book. Returns the parsed snapshot, or None when no admissible
    book exists — which is a legitimate reason to decline a trade, not an error."""
    from . import database as db

    rows = db.query(
        con,
        'SELECT book_snapshot FROM orderbook_snapshots '
        'WHERE token_id = ? AND dataset_version = ? AND "timestamp" <= ? '
        'ORDER BY "timestamp" DESC LIMIT 1',
        [str(token_id), dataset_version, asof],
    )
    if not rows:
        return None
    snap = rows[0]["book_snapshot"]
    if isinstance(snap, str):
        import json as _json
        try:
            snap = _json.loads(snap)
        except ValueError:
            return None
    return snap if isinstance(snap, dict) else None


def _levels_from_snapshot(book_snapshot: dict, side: str) -> list[tuple[float, float]]:
    """Read one side out of a stored snapshot, best-first.

    The collector already sorts and truncates, but this re-sorts anyway: a
    snapshot may have been written by an older collector, and getting the side
    order wrong silently produces a fill at the WORST price in the book."""
    key = "asks" if side == "ask" else "bids"
    out: list[tuple[float, float]] = []
    for lvl in (book_snapshot or {}).get(key) or []:
        try:
            out.append((float(lvl["price"]), float(lvl["size"])))
        except (KeyError, TypeError, ValueError):
            continue
    out = [(p, s) for p, s in out if math.isfinite(p) and math.isfinite(s) and s > 0]
    return sorted(out, key=(lambda lv: lv[0]) if side == "ask" else (lambda lv: -lv[0]))


def simulate_taker_buy(
    book_snapshot: dict,
    *,
    max_cash: float,
    fee: FeeParams,
    max_shares: float | None = None,
    min_shares: float = MIN_ORDER_SHARES,
    min_notional: float = MIN_ORDER_NOTIONAL_USDC,
) -> Fill:
    """Simulate a marketable taker BUY against an observed ask ladder.

    `max_cash` is the TOTAL outlay budget: notional plus fee, because that is what
    actually leaves the bankroll (D19 (2): fees are charged on top of the pre-fee
    notional). Sizing against the notional alone would systematically overspend by
    the fee on every trade.

    Walks levels best-first, never crossing more depth than the level holds, and
    stops when the budget or the share cap binds. A partial fill is a legitimate
    result and is reported as such — but it is only `executable` if it clears the
    conservative minimum-size bound.

    BUDGET TOLERANCE: `outlay` can exceed `max_cash` by up to half of 10^-5 USDC.
    Shares are sized against the exact fee, then the fee is rounded to the venue's
    5-decimal resolution, and that rounding can go up. Shaving shares to absorb a
    sub-cent rounding artefact would be false precision — the bound is declared
    here instead, and it is smaller than the smallest fee the venue charges."""
    levels = _levels_from_snapshot(book_snapshot, "ask")
    fill = Fill(book_truncated=bool((book_snapshot or {}).get("truncated")))
    if not levels:
        fill.reason = "empty_book_side"
        return fill
    if max_cash <= 0:
        fill.reason = "no_budget"
        return fill

    budget = float(max_cash)
    shares_total = 0.0
    notional = 0.0
    fee_total = 0.0

    for price, size in levels:
        if budget <= 0:
            break
        unit_fee = taker_fee_per_share(price, rate=fee.rate, exponent=fee.exponent)
        unit_cost = price + unit_fee
        if unit_cost <= 0:                       # a free level cannot bound the walk
            break
        take = size
        if max_shares is not None:
            take = min(take, max(0.0, max_shares - shares_total))
        take = min(take, budget / unit_cost)
        if take <= 0:
            break
        shares_total += take
        notional += take * price
        fee_total += take * unit_fee
        budget -= take * unit_cost
        fill.levels_used += 1
        fill.detail.append({"price": price, "shares": take,
                            "size_available": size})
        if max_shares is not None and shares_total >= max_shares:
            break

    # "Exhausted" means the STORED ladder ran out while we still had budget and
    # room — the case where a real, deeper book might have filled more. Derived
    # explicitly rather than from a for/else, which would also fire when the
    # budget happened to bind on the last level.
    cap_left = max_shares is None or shares_total < max_shares
    fill.book_exhausted = (fill.levels_used == len(levels) and budget > 1e-9
                           and cap_left)

    if shares_total <= 0:
        fill.reason = "no_depth_within_budget"
        return fill

    fill.shares = shares_total
    fill.notional = notional
    fill.vwap = notional / shares_total
    fill.fee = round_fee(fee_total)
    fill.outlay = notional + fill.fee

    if shares_total < min_shares:
        fill.reason = "below_min_order_shares"
        return fill
    if notional < min_notional:
        fill.reason = "below_min_order_notional"
        return fill

    fill.executable = True
    return fill


# =============================================================================
# Sizing and the net-edge gate
# =============================================================================
@dataclass(frozen=True)
class PaperParams:
    """Every knob the engine uses, obligatory and explicit.

    There are no defaults on purpose: a paper run's numbers are only meaningful
    against a preregistration that names them (R24), and a silent default is a
    parameter nobody registered."""
    bankroll: float
    fixed_fraction: float
    size_cap: float
    #: Execution threshold. NOT the same quantity as Strategy A's `tau`, and the
    #: two must not share a name: `strategy_a` compares `fair_value - p_market`
    #: (GROSS edge against the indicative mid) while this gates
    #: `net_edge_per_share` (NET of fees, against the VWAP actually achievable).
    #: One number applied to two different operands is a threshold with two
    #: meanings — the defect class that sank another preregistration's `n >= 30`.
    #: They may hold the same value, but that has to be a stated choice.
    tau_exec: float
    exit_mode: str                    # 'hold_to_resolution' | 'taker_close'
    x_exec: float                     # spread/slippage add-on, USDC per share
    min_shares: float = MIN_ORDER_SHARES
    min_notional: float = MIN_ORDER_NOTIONAL_USDC

    def __post_init__(self) -> None:
        for name in ("bankroll", "fixed_fraction", "size_cap", "tau_exec", "x_exec"):
            _require(name, getattr(self, name))
        if self.exit_mode not in ("hold_to_resolution", "taker_close"):
            raise ValueError(f"paper: unknown exit_mode {self.exit_mode!r}")
        if not self.tau_exec > 0:
            raise ValueError("paper: tau_exec must be > 0")
        if self.x_exec < 0:
            raise ValueError("paper: x_exec must be >= 0")
        if not 0 < self.fixed_fraction <= 1 or not 0 < self.size_cap <= 1:
            raise ValueError("paper: fractions must be in (0, 1]")


def position_cash(params: PaperParams, *, bankroll: float | None = None) -> float:
    """Cash budget for one position: bankroll × min(fixed_fraction, size_cap)."""
    bank = params.bankroll if bankroll is None else float(bankroll)
    return max(0.0, bank) * min(params.fixed_fraction, params.size_cap)


def net_edge_per_share(
    *, p_model: float, fill_price: float, fee: FeeParams, params: PaperParams,
    exit_price: float | None = None,
) -> float:
    """D19 (3), evaluated at the price the fill ACTUALLY got.

    Strategy A's own `edge` is computed against the indicative price; using it
    here would credit the strategy with an edge it never had to pay the spread
    for. The gate below is the one that decides whether a position opens."""
    entry_fee = taker_fee_per_share(fill_price, rate=fee.rate, exponent=fee.exponent)
    if params.exit_mode == "taker_close":
        px = fill_price if exit_price is None else float(exit_price)
        exit_cost = taker_fee_per_share(px, rate=fee.rate, exponent=fee.exponent)
    else:
        exit_cost = 0.0               # redemption at resolution carries no venue fee
    return (float(p_model) - float(fill_price)) - entry_fee - exit_cost - params.x_exec


# =============================================================================
# Execution
# =============================================================================
def decide_and_fill(
    *,
    signal: str,
    p_model: float,
    book_snapshot: dict,
    fee: FeeParams | None,
    params: PaperParams,
    bankroll: float | None = None,
) -> dict:
    """Decide whether a signal becomes a paper position, and at what price.

    Order of checks matters and is deliberate: the book is walked BEFORE the edge
    is judged, because the edge must be measured at the achievable price, not the
    quoted one. Returns a dict with `open` (bool), `reason`, the `Fill`, and the
    net edge — never writes anything."""
    out: dict[str, Any] = {"open": False, "reason": None, "fill": None,
                           "net_edge": None, "side_token": None}
    if signal not in ("BUY", "FADE"):
        out["reason"] = f"signal_not_actionable:{signal}"
        return out
    if fee is None:
        out["reason"] = "fee_unknown_fail_closed"
        return out

    # A FADE buys the complement, so both the model probability and the book are
    # the complement's. The caller supplies the No token's book; p_model flips.
    p_target = float(p_model) if signal == "BUY" else 1.0 - float(p_model)

    cash = position_cash(params, bankroll=bankroll)
    fill = simulate_taker_buy(
        book_snapshot, max_cash=cash, fee=fee,
        min_shares=params.min_shares, min_notional=params.min_notional,
    )
    out["fill"] = fill
    if not fill.executable:
        out["reason"] = fill.reason or "not_executable"
        return out

    # YOU CAN FILL A BUY AGAINST A BOOK THAT HAS NO BID AT ALL, and under
    # `taker_close` the cost model prices the exit as if you could sell back.
    #
    # `net_edge_per_share` charges the exit at `fill_price` plus a fee when
    # `exit_price` is None, which assumes a buyer at exactly what you paid. On a
    # book quoted on the ask side only there is no buyer at ANY price, so that
    # exit is not expensive — it is impossible, and `x_exec` cannot stand in for
    # it because a flat half-spread is not a model of an absent side.
    #
    # This is not hypothetical arithmetic. Measured over the 36 850 books
    # collected 2026-09-09..11: 25 736 two-sided (69.8 %), **5 557 ask-only
    # (15.1 %)** and 5 557 bid-only. The ask-only ones are exactly the ones a BUY
    # fills against. (The two counts are equal because a market is quoted on one
    # side or both, never one side per token: in 2 244 of 2 244 markets both
    # tokens shared their liquidity state.)
    #
    # `hold_to_resolution` — the default — is untouched: redemption needs no
    # counterparty, so a missing bid costs nothing there. The refusal applies
    # only to the mode that plans to sell.
    #
    # HOW OFTEN THIS BITES IS SMALLER THAN 15 %, AND THE HONEST ANSWER IS THAT
    # NOBODY CAN SAY BY HOW MUCH. A one-sided book has no mid, so it cannot be
    # placed in a price bin at all; the 15.1 % is over ALL observations, not over
    # the ones a strategy would look at. What IS measured (session B, same
    # corpus) is that intermittently-quoted markets sit at the price EXTREMES:
    # among two-sided observations, the doubt zone (bins 1-8) is 97.3 % served by
    # always-liquid markets while the extremes are 41.6 % intermittent. So these
    # markets are liquid mostly where the outcome is already decided — and a rule
    # that trades the zone of doubt will meet this case rarely.
    #
    # Rarely is not never, and a cost model that prices an impossible exit is
    # wrong at any frequency. That is why this is a REFUSAL and not a warning.
    if params.exit_mode == "taker_close" and not _levels_from_snapshot(
            book_snapshot, "bid"):
        out["reason"] = "no_exit_liquidity"
        return out

    edge = net_edge_per_share(p_model=p_target, fill_price=fill.vwap, fee=fee,
                              params=params)
    out["net_edge"] = edge
    if edge < params.tau_exec:
        out["reason"] = "net_edge_below_tau"
        return out

    out["open"] = True
    return out


def record_paper_trade(
    con,
    *,
    backtest_id: str,
    market_id: str,
    token_id: str,
    entry_time: Any,
    fill: Fill,
    bankroll_after: float,
    dataset_version: str,
    target_date: Any,
    slippage: float = 0.0,
) -> int:
    """Persist an OPEN paper position. Exit fields stay NULL until settlement.

    `target_date` is REQUIRED and is the caller's parameter (2D §C), not something
    to be recovered later from `endDate`. A position that does not carry the day
    it was opened for forces every downstream stage to re-derive it from a source
    §C prohibits — and `markets` is re-discovered every cycle, so a revised
    `endDate` would silently move the day a settled trade is settled against.

    `gross_pnl`/`net_pnl` are NULL while open — writing 0 there would make an
    unsettled position indistinguishable from a flat one in every aggregate."""
    now = _utcnow_iso()
    con.execute(
        """
        INSERT INTO paper_trades (
            backtest_id, market_id, token_id, entry_time, target_date,
            entry_price, fees, slippage, size, bankroll_after, price_layer,
            source, source_timestamp, ingestion_timestamp,
            dataset_version, record_version
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        RETURNING paper_trade_id
        """,
        [backtest_id, market_id, token_id, entry_time, target_date, fill.vwap,
         fill.fee, slippage, fill.shares, bankroll_after, PRICE_LAYER,
         SOURCE, entry_time, now, dataset_version, 1],
    )
    return int(con.fetchone()[0])


def settle_paper_trade(
    con,
    paper_trade_id: int,
    *,
    settlement: float,
    exit_time: Any,
    exit_fee: float = 0.0,
) -> dict:
    """Close a position at its 0/1 settlement and book the P&L.

        gross_pnl = shares · (settlement - entry_price)
        net_pnl   = gross_pnl - entry_fee - exit_fee - slippage

    `settlement` must be exactly 0 or 1: these are binary outcome tokens, and a
    fractional settlement would mean the label was averaged somewhere upstream."""
    if settlement not in (0, 1, 0.0, 1.0):
        raise ValueError(f"paper: settlement must be 0 or 1, got {settlement!r}")
    rows = db.query(
        con,
        "SELECT paper_trade_id, entry_price, size, fees, slippage "
        "FROM paper_trades WHERE paper_trade_id = ?",
        [paper_trade_id],
    )
    if not rows:
        raise ValueError(f"paper: no paper_trade {paper_trade_id}")
    row = rows[0]
    shares = float(row["size"] or 0.0)
    entry = float(row["entry_price"] or 0.0)
    entry_fee = float(row["fees"] or 0.0)
    slip = float(row["slippage"] or 0.0)

    gross = shares * (float(settlement) - entry)
    fees_total = entry_fee + float(exit_fee)
    net = gross - fees_total - slip
    con.execute(
        "UPDATE paper_trades SET exit_time = ?, exit_price = ?, settlement = ?, "
        "fees = ?, gross_pnl = ?, net_pnl = ? WHERE paper_trade_id = ?",
        [exit_time, float(settlement), float(settlement), fees_total, gross, net,
         paper_trade_id],
    )
    return {"paper_trade_id": paper_trade_id, "gross_pnl": gross, "net_pnl": net,
            "fees": fees_total, "settlement": float(settlement)}


def open_positions(con, *, backtest_id: str, dataset_version: str) -> list[dict]:
    """Positions with no exit yet — the ledger the next cycle must settle."""
    return db.query(
        con,
        "SELECT paper_trade_id, market_id, token_id, entry_time, entry_price, size "
        "FROM paper_trades WHERE backtest_id = ? AND dataset_version = ? "
        "AND exit_time IS NULL ORDER BY paper_trade_id",
        [backtest_id, dataset_version],
    )


def ledger_summary(con, *, backtest_id: str, dataset_version: str) -> dict:
    """Aggregate P&L. Open positions are counted but contribute no P&L."""
    rows = db.query(
        con,
        "SELECT count(*) AS n, "
        "sum(CASE WHEN exit_time IS NULL THEN 1 ELSE 0 END) AS n_open, "
        "sum(coalesce(net_pnl, 0)) AS net_pnl, "
        "sum(coalesce(gross_pnl, 0)) AS gross_pnl, "
        "sum(coalesce(fees, 0)) AS fees "
        "FROM paper_trades WHERE backtest_id = ? AND dataset_version = ?",
        [backtest_id, dataset_version],
    )
    row = rows[0] if rows else {}
    return {
        "backtest_id": backtest_id,
        "n_trades": int(row.get("n") or 0),
        "n_open": int(row.get("n_open") or 0),
        "net_pnl": float(row.get("net_pnl") or 0.0),
        "gross_pnl": float(row.get("gross_pnl") or 0.0),
        "fees": float(row.get("fees") or 0.0),
    }
