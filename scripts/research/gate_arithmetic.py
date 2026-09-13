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
from weather_agent.probability import (quantiles_to_distribution, band_probability,
                                      TAIL_LINEAR_R21)

#: The published S11 table (74 % margin / 17 % slippage / 9 % fees) was computed
#: with the LINEAR one-degree tails, before PR #33. Pinned so this script keeps
#: reproducing what the report states.
#:
#: IT MUST GO TO BOTH CALL SITES. `calibration_margin` builds its OWN
#: distributions, so pinning only the p_model side gives 71/19/10 -- neither the
#: published triple nor a clean exponential run, and it LOOKS right. That third
#: number wearing the old one's name is the reason `calibration_margin` took a
#: tail_model parameter at all.
TAIL = TAIL_LINEAR_R21
from weather_agent import backtest as bt, costs, error_model as em

art = json.load(open(os.path.join(_ROOT, "artifacts", "m2_quantiles.json")))
print(f"artifact model={art['model']} dataset={art['dataset_version']}")

SPEC = costs.FeeSpec(enabled=True, rate=0.05, exponent=1, taker_only=True)

#: PREREG_R21_ENMIENDA_A A.2.
X_EXEC = 0.01

def max_mid(p_model, margin, x_exec=X_EXEC):
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
    dist = quantiles_to_distribution(p10=qF[10], p25=qF[25], p50=qF[50],
                                     p75=qF[75], p90=qF[90], tail_model=TAIL)
    print(f"  model support: {min(dist)}..{max(dist)} F  ({len(dist)} integer bins)")
    print(f"  mass profile: " + " ".join(f"{t}:{p:.3f}" for t,p in sorted(dist.items())))
    print(f"\n  {'band':>10} {'pos':>13} {'p_model':>8} {'margin':>8} {'max_mid':>8} {'mid/p_model':>12}")
    rows=[]
    for t in range(min(dist)-2, max(dist)+3):
        lo, hi = float(t), float(t)      # 1-degree F band, integer grid
        pm = band_probability(dist, lo=lo, hi=hi)
        mg = bt.calibration_margin(lev_c, unit="F", lo=lo, hi=hi, tail_model=TAIL)
        mm = max_mid(pm, mg)
        pos = bt.band_position(qF, lo, hi)
        rows.append((t,pos,pm,mg,mm))
        print(f"  {t:>10} {pos:>13} {pm:>8.4f} {mg:>8.4f} " +
              (f"{mm:>8.4f} {mm/pm:>11.1%}" if mm else f"{'NEVER':>8} {'-':>12}"))
    tradable=[r for r in rows if r[4]]
    print(f"\n  bands where a trade is POSSIBLE at any price: {len(tradable)}/{len(rows)}")
    print(f"  total model mass in those bands: {sum(r[2] for r in tradable):.4f}")

    # The decomposition the report quotes in S11 and in the S36 reproducibility
    # table. It lived in a scratchpad script that was never committed, so the
    # report attributed a number to a script that did not produce it -- the same
    # class of defect this whole session keeps finding, in the section whose
    # entire job is reproducibility. Produced here now.
    tot={"margin":0.0,"x":0.0,"fee":0.0}
    for _t,_pos,pm,mg,_mm in rows:
        if pm<=0: continue
        tot["margin"]+=mg*pm
        tot["x"]+=X_EXEC*pm
        tot["fee"]+=0.05*pm*(1-pm)*pm
    s=sum(tot.values())
    print(f"\n  REQUIRED-GAP DECOMPOSITION, mass-weighted:")
    print(f"    calibration margin {tot['margin']/s:.0%}  <- the model's own imprecision")
    print(f"    slippage (x_exec {X_EXEC})  {tot['x']/s:.0%}")
    print(f"    fees (0.05*p*(1-p))  {tot['fee']/s:.0%}")

    # The maker counterfactual, also quoted in S11: fee 0, earning half-spread.
    print(f"\n  MAKER COUNTERFACTUAL (fee 0, earning half-spread h):")
    tk=[r[4]/r[2] for r in rows if r[4] and r[2]>0]
    print(f"    taker, x_exec {X_EXEC}: mean max_mid/p_model {sum(tk)/len(tk):.1%}")
    for h in (0.0,0.01,0.02):
        rr=[(pm-mg+h)/pm for _t,_p,pm,mg,_m in rows if pm>0 and (pm-mg+h)>0]
        print(f"    maker, half-spread {h:.2f}: mean max_mid/p_model {sum(rr)/len(rr):.1%}")
