#!/usr/bin/env python3
"""
gate_arithmetic.py - can Strategy A's signal gate ever open?
=============================================================

Reads the repo's OWN versioned artifact (`artifacts/m2_quantiles.json`) through the
repo's OWN code (`probability`, `backtest.calibration_margin`, `costs`) and asks, for
each 1 F band, the only question that decides whether a trade is possible at all:

    at what market mid would `edge_net > margin` still hold?

The answer is 16-83 % of `p_model`: the market must be that cheap, in RELATIVE terms,
before the strategy may fire. Decomposing the required gap, mass-weighted, the binding
constraint is NOT the cost stack - it is the model's own admitted imprecision:

    calibration margin 74 % | slippage 17 % | fees 9 %

Offline, no network, no database. See docs/research/EDGE_RESEARCH_2026-09-11.md S11.
"""

import json
import os, sys
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "src"))
from weather_agent.probability import quantiles_to_distribution, band_probability
from weather_agent import backtest as bt, costs, error_model as em

art = json.load(open(os.path.join(_ROOT, "artifacts", "m2_quantiles.json")))
print(f"artifact model={art['model']} dataset={art['dataset_version']}")

SPEC = costs.FeeSpec(enabled=True, rate=0.05, exponent=1, taker_only=True)

def max_mid(p_model, margin, x_exec=0.01):
    """Largest market mid at which edge_net > margin. None if never."""
    lo, hi = -0.5, 1.0
    # g(p_exec) = p_exec + fee ; need g(p_exec) < p_model - margin
    target = p_model - margin
    # solve p_exec + 0.05*p_exec*(1-p_exec) = target  (monotone increasing on [0,1])
    def g(pe): return pe + 0.05*pe*(1-pe)
    if target <= 0: return None
    if g(1.0) <= target: pe = 1.0
    else:
        a, b = 0.0, 1.0
        for _ in range(80):
            m = (a+b)/2
            if g(m) < target: a = m
            else: b = m
        pe = a
    mid = pe - x_exec
    return mid if mid > 0 else None

for lead in ("9", "24"):
    st = art["strata"][lead]
    qc = {int(k): v for k, v in st["values"].items()}   # error quantiles, CELSIUS
    print(f"\n{'='*88}\nLEAD {lead}h  n={st['n']}  scope={st['scope']}  error quantiles (C): {qc}")
    # A market in Fahrenheit (the common case), forecast f=25C -> quantile LEVELS in F
    f_c = 25.0
    lev_c = {lvl: f_c + qc[lvl] for lvl in (10,25,50,75,90)}
    qF = em.to_market_unit(lev_c, "F")
    print(f"  forecast {f_c}C -> quantile levels (F): " + ", ".join(f"p{k}={v:.2f}" for k,v in sorted(qF.items())))
    print(f"  80% interval width: {qF[90]-qF[10]:.2f} F   (model support adds only +/-1F beyond)")
    dist = quantiles_to_distribution(p10=qF[10], p25=qF[25], p50=qF[50], p75=qF[75], p90=qF[90])
    print(f"  model support: {min(dist)}..{max(dist)} F  ({len(dist)} integer bins)")
    print(f"  mass profile: " + " ".join(f"{t}:{p:.3f}" for t,p in sorted(dist.items())))
    print(f"\n  {'band':>10} {'pos':>13} {'p_model':>8} {'margin':>8} {'max_mid':>8} {'mid/p_model':>12}")
    rows=[]
    for t in range(min(dist)-2, max(dist)+3):
        lo, hi = float(t), float(t)      # 1-degree F band, integer grid
        pm = band_probability(dist, lo=lo, hi=hi)
        mg = bt.calibration_margin(lev_c, unit="F", lo=lo, hi=hi)
        mm = max_mid(pm, mg)
        pos = bt.band_position(qF, lo, hi)
        rows.append((t,pos,pm,mg,mm))
        print(f"  {t:>10} {pos:>13} {pm:>8.4f} {mg:>8.4f} " +
              (f"{mm:>8.4f} {mm/pm:>11.1%}" if mm else f"{'NEVER':>8} {'-':>12}"))
    tradable=[r for r in rows if r[4]]
    print(f"\n  bands where a trade is POSSIBLE at any price: {len(tradable)}/{len(rows)}")
    print(f"  total model mass in those bands: {sum(r[2] for r in tradable):.4f}")
