"""
costs.py — the frozen cost model of D19, and the sizing rule of R20
===================================================================

Deliberately DATABASE-FREE, like `error_model`: this is arithmetic over declared
parameters and must be testable without a schema. The module that knows about
tables is `backtest.py`.

D19 (`FEES_SEMANTICS.md`, sha `4dbad3ab…`) established, from the venue's own docs:

    fee = C · rate · p · (1 − p)      in USDC, TAKER ONLY
    "Makers are never charged fees."  Weather: rate 0.05, exponent 1.

and that the canonical source of the parameters is the market's own `feeSchedule`,
read PER MARKET. The activation was **by batch**, not by creation order — the
30-mar cohort is mixed 275/143 — so any rule of the form "markets after date X pay
fees" is wrong for that cohort, in both directions.

FAIL-CLOSED is the whole point of `taker_fee` returning `None`. A market whose fee
schedule we cannot read is not a free market; it is a market whose cost we do not
know. Returning 0.0 there would credit the strategy with an execution nobody
priced — the same family as evaluating at the quoted price, which
`PREREG_R21 §1` forbids. `None` propagates to `edge_net = None` and the trade is
counted as refused, never taken.

SIZING (R20, and PREREG_R21_ENMIENDA_A §A.6): one share. Not Kelly, not
confidence-weighted. B-12 measured that `p_model` is worse calibrated per market
than in aggregate and that the difference is **not correctable** with this
substrate; sizing by confidence would stake more precisely where the number is
known to be wrong.
"""

from __future__ import annotations

from dataclasses import dataclass

#: D19 §"Modelo de coste congelado". H1 is the DECISION metric; H2 and H3 exist
#: only as sensitivity columns and must never decide anything.
H1_PRIMARY = "H1_rate_p_1mp"
H2_BPS_FULL = "H2_1000bps_full"
H3_DOUBLE = "H3_double_H1"

#: PREREG_R21_ENMIENDA_A §A.2. There is no order-book history — `orderbook_snapshots`
#: is empty and every one of the 16 165 636 price rows is MIDPOINT_ESTIMATED — so
#: slippage is an ASSUMPTION, not a measurement. The primary is therefore the most
#: adverse rung of the D19 ladder: an assumption about something unmeasured must
#: not be the thing that manufactures a positive result.
X_EXEC_PRIMARY = 0.01
X_EXEC_SENSITIVITY = (0.005, 0.001, 0.0)

#: R20 / §A.6.
SIZE_SHARES = 1.0


@dataclass(frozen=True)
class FeeSpec:
    """A market's fee parameters, exactly as the catalogue declares them."""

    enabled: bool | None
    rate: float | None
    exponent: float | None
    taker_only: bool | None

    @property
    def known(self) -> bool:
        """True only when the fee is computable. `enabled is False` IS known: the
        fee is zero, and D19 says so. `enabled is None` is not known."""
        if self.enabled is False:
            return True
        if self.enabled is not True:
            return False
        return self.rate is not None and self.exponent is not None


def taker_fee(price: float, spec: FeeSpec, model: str = H1_PRIMARY) -> float | None:
    """USDC per share. `None` when the schedule is not readable — fail closed.

    `exponent != 1` is refused rather than raised to that power: D19 froze H1 as
    `rate·(p(1−p))^exponent` with exponent 1 observed across all 84 451 markets
    that have a schedule, so a different exponent is an unseen regime, not a
    parameter to extrapolate into.
    """
    if not spec.known:
        return None
    if spec.enabled is False:
        return 0.0
    if spec.exponent != 1:
        return None
    p = float(price)
    if not 0.0 <= p <= 1.0:
        raise ValueError(f"price {p} outside [0, 1]")
    base = spec.rate * (p * (1.0 - p))
    if model == H1_PRIMARY:
        return base
    if model == H3_DOUBLE:
        return 2.0 * base
    if model == H2_BPS_FULL:
        # The alternative reading of makerBaseFee/takerBaseFee = 1000 bps as the
        # whole fee rather than an on-chain cap. D19 keeps it as a column because
        # the relation between 1000 bps and rate 0.05 is NOT documented.
        return 0.10 * min(p, 1.0 - p)
    raise ValueError(f"unknown cost model {model!r}")


def exec_price(mid: float, x_exec: float = X_EXEC_PRIMARY) -> float:
    """The achievable price for a BUY: adverse to us, never the quoted mid.

    Long-only (§A.6), so the adjustment has one sign. Clamped below 1.0 because a
    price of 1 or more is not a purchase, it is a donation.
    """
    return min(float(mid) + float(x_exec), 1.0)


def edge_net(
    *,
    p_model: float,
    mid: float,
    spec: FeeSpec,
    x_exec: float = X_EXEC_PRIMARY,
    model: str = H1_PRIMARY,
) -> tuple[float | None, float, float | None]:
    """`(edge_net, p_exec, fee)` in USDC per share, for one long YES share.

    PREREG_R21_ENMIENDA_A §A.3: the cost lives INSIDE this number. The caller
    compares it against the calibration margin ALONE — adding `tau_costes` on top
    would subtract the cost twice, which is the defect session A found in R24 v2.
    """
    p_exec = exec_price(mid, x_exec)
    fee = taker_fee(p_exec, spec, model)
    if fee is None:
        return None, p_exec, None
    return float(p_model) - p_exec - fee, p_exec, fee


def realised_pnl(*, won: bool, p_exec: float, fee: float,
                 size: float = SIZE_SHARES) -> float:
    """Realised net PnL of one settled long-YES position.

    Exit is `hold_to_resolution` (D19): redemption pays 1 for a winner and 0 for a
    loser, and carries no fee. So the entry fee is the only fee, and it is paid
    whether or not the position wins — which is why it is subtracted outside the
    win branch rather than inside it.
    """
    return size * ((1.0 if won else 0.0) - p_exec) - size * fee
