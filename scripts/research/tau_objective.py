#!/usr/bin/env python3
"""
tau_objective.py - why `backtest.select_tau`'s objective cannot rank thresholds
===============================================================================

`select_tau` maximises the MEDIAN net PnL per trade. Its docstring justifies this: with
few trades the mean is fixed by one tail. True, but the cure is worse here.

Every band in this universe is 5-30 % likely, so the win rate is ALWAYS below 50 % and
the median is therefore ALWAYS a losing trade's PnL, -(p_exec + fee). Maximising it
ranks candidate thresholds by TICKET PRICE, not by expected value: a 2-cent loser
(-0.031) outranks a 16-cent loser (-0.167) even when the 16-cent bucket earns 5x more
per trade in expectation.

Demonstrated below: select_tau picks tau=0.04 (mean +0.0769/trade) over tau=0.15
(mean +0.1253/trade). A trimmed mean would have ranked them correctly.

SCOPE, honestly: in the actual R21 run the optimiser pinned to the TOP of the frozen
grid (0.20 in 239 of 271 decisions), so this defect was NOT the operating cause of that
negative result. It does invalidate the objective for any reuse.

Synthetic data, seed 11. Offline, no network, no database.
See docs/research/EDGE_RESEARCH_2026-09-11.md S11 and defect A1.
"""

import os, sys, random
from statistics import median, mean

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "src"))
from weather_agent import backtest as bt, costs
from datetime import date, datetime, timezone

random.seed(11)
SPEC = costs.FeeSpec(enabled=True, rate=0.05, exponent=1, taker_only=True)
def mk(p_model,p_mid,won,eg):
    net,pe,fee = costs.edge_net(p_model=p_model, mid=p_mid, spec=SPEC)
    return bt.Candidate(market_id="m",token_id="t",station="KJFK",target_date=date(2026,7,1),
        lead_h=24,decision_time=datetime(2026,6,30,12,tzinfo=timezone.utc),
        label_available_at=datetime(2026,7,2,tzinfo=timezone.utc),unit="F",lo=78.0,hi=78.0,
        q_market={10:74,25:76,50:78,75:79,90:81},spec=SPEC,p_mid=p_mid,p_model=p_model,
        edge_gross=eg,edge_net=net,p_exec=pe,fee=fee,margin=0.0,won=won,
        pnl=costs.realised_pnl(won=won,p_exec=pe,fee=fee))

pop=[]
# Bucket GOOD: real edge, moderately priced. p_model=0.30 and TRUE win prob 0.30.
for _ in range(1000):
    pop.append(mk(0.30, 0.15, random.random()<0.30, 0.15))
# Bucket CHEAP: small genuine edge, but tickets cost almost nothing.
for _ in range(1000):
    pop.append(mk(0.06, 0.02, random.random()<0.06, 0.04))

print(f"{'tau':>6} {'n':>6} {'MEDIAN pnl':>12} {'MEAN pnl':>10} {'TOTAL pnl':>11}  which bucket")
for tau in (0.04, 0.15):
    sel=[c for c in pop if c.edge_gross>=tau and c.passes_exec and c.pnl is not None]
    which = "GOOD only" if tau>0.05 else "GOOD + CHEAP"
    print(f"{tau:>6.2f} {len(sel):>6} {median([c.pnl for c in sel]):>+12.4f} "
          f"{mean([c.pnl for c in sel]):>+10.4f} {sum(c.pnl for c in sel):>+11.2f}  {which}")

print(f"\nselect_tau picks tau = {bt.select_tau(pop)}")
print("\nThe tau that maximises the MEDIAN is the one that admits the CHEAP bucket,")
print("because a 2-cent loser (-0.031) outranks a 16-cent loser (-0.166) on the median")
print("even though the 16-cent bucket earns 5x more per trade in expectation.")
print("\nMEAN pnl would have ranked them correctly. MEDIAN inverts the ranking here.")
