#!/usr/bin/env python3
"""
partition_arb.py - the hurdle on a partition-coherence basket
==============================================================

The bands of one weather event are an exhaustive partition, so buying ALL of them pays
exactly 1. That makes the trade MODEL-FREE: it needs no forecast and is immune to the
adverse-selection mechanism R21/R22 identified.

What it is not immune to is the cost of N legs. Closed-form arithmetic, no inputs:

    taker  cost = S + N*x_exec + 0.05*sum(p_i*(1-p_i))   ->  N=9 needs S <= 0.8656
    maker  cost = S - N*h                                 ->  N=9 needs S <= 1.0900

So the taker version needs a 13.4 % underpricing of a set that must pay 1 (it does not
happen), while the maker is PAID to do it in almost any book - and carries fill risk
instead, because an incomplete basket is a naked directional position.

The fee component of the hurdle is 0.05*(1-1/N), independent of the prices.

Offline, no network, no database. See docs/research/EDGE_RESEARCH_2026-09-11.md S11.
"""

print("Buy ALL N bands of a valid partition -> guaranteed payoff of exactly 1.")
print("cost = S + N*x_exec + 0.05*sum(p_i*(1-p_i))   [taker]")
print("cost = S - N*h                                [maker, no fee, earns half-spread h]\n")
print(f"{'N':>3} {'S_max taker(x=.01)':>19} {'S_max taker(x=.005)':>20} {'S_max maker(h=.01)':>19} {'S_max maker(h=.02)':>19}")
for N in (3,5,7,9,12,15):
    p = 1.0/N
    feesum = 0.05*N*p*(1-p)          # = 0.05*(1 - 1/N)
    print(f"{N:>3} {1-N*0.01-feesum:>19.4f} {1-N*0.005-feesum:>20.4f} "
          f"{1+N*0.01:>19.4f} {1+N*0.02:>19.4f}")
print("\nRead: with 9 bands a TAKER needs the partition trading at <= 0.866 —")
print("a 13.4% underpricing of a set that must pay exactly 1. A MAKER needs only")
print("S <= 1.09, i.e. is paid to do it in almost any book — but only on the legs")
print("that actually fill. An incomplete basket is a naked directional position.")
print("\nfee share of the hurdle is fixed at 0.05*(1-1/N) and is INDEPENDENT of prices.")
