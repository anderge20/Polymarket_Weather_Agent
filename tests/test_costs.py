"""
test_costs.py — R20: D19's frozen cost model.

The numbers asserted here are D19's OWN published figures, not values read back
out of the implementation: max 0.0125 at p=0.5, 4.5 % of notional at p=0.10 and
2.5 % at p=0.50. A test that asserts what the code happens to return certifies
nothing.
"""
from __future__ import annotations

import pytest

from weather_agent import costs

WEATHER = costs.FeeSpec(enabled=True, rate=0.05, exponent=1.0, taker_only=True)


def test_d19_published_figures():
    assert costs.taker_fee(0.5, WEATHER) == pytest.approx(0.0125)
    assert costs.taker_fee(0.10, WEATHER) / 0.10 == pytest.approx(0.045)
    assert costs.taker_fee(0.50, WEATHER) / 0.50 == pytest.approx(0.025)


def test_fee_is_symmetric_and_vanishes_at_the_ends():
    assert costs.taker_fee(0.2, WEATHER) == pytest.approx(costs.taker_fee(0.8, WEATHER))
    assert costs.taker_fee(0.0, WEATHER) == 0.0
    assert costs.taker_fee(1.0, WEATHER) == 0.0


@pytest.mark.parametrize("spec", [
    costs.FeeSpec(None, None, None, None),          # nothing known
    costs.FeeSpec(True, None, 1.0, True),           # enabled, rate missing
    costs.FeeSpec(True, 0.05, None, True),          # enabled, exponent missing
    costs.FeeSpec(True, 0.05, 2.0, True),           # an exponent D19 never observed
])
def test_unreadable_schedule_fails_closed(spec):
    """None, never 0.0. A market whose cost we cannot read is not a free market,
    and crediting it with zero cost is the same defect as pricing at the quoted
    mid: rendering the strategy never had to pay for."""
    assert costs.taker_fee(0.5, spec) is None
    net, _, fee = costs.edge_net(p_model=0.9, mid=0.1, spec=spec)
    assert net is None and fee is None


def test_fees_disabled_is_known_and_zero():
    spec = costs.FeeSpec(enabled=False, rate=None, exponent=None, taker_only=None)
    assert spec.known is True
    assert costs.taker_fee(0.5, spec) == 0.0


def test_exec_price_is_adverse_and_capped():
    assert costs.exec_price(0.20, 0.01) == pytest.approx(0.21)
    assert costs.exec_price(0.995, 0.01) == 1.0


def test_edge_net_carries_the_cost_inside_it():
    """PREREG_R21_ENMIENDA_A §A.3. If the caller also subtracted a cost term the
    cost would be counted twice — the defect session A found in R24 v2."""
    net, p_exec, fee = costs.edge_net(p_model=0.30, mid=0.20, spec=WEATHER, x_exec=0.01)
    assert p_exec == pytest.approx(0.21)
    assert net == pytest.approx(0.30 - 0.21 - fee)
    assert net < 0.30 - 0.20          # strictly worse than the quoted-mid edge


def test_entry_fee_is_paid_by_losers_too():
    """`hold_to_resolution`: redemption is free, so the entry fee is the only fee
    — and it is paid whether or not the position wins."""
    assert costs.realised_pnl(won=True, p_exec=0.21, fee=0.0083) == pytest.approx(0.7817)
    assert costs.realised_pnl(won=False, p_exec=0.21, fee=0.0083) == pytest.approx(-0.2183)
