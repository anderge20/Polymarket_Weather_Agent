#!/usr/bin/env python3
"""
run_r21.py — execute PREREG_R21 and report its four acceptance criteria
=======================================================================

`PREREG_R21_BACKTEST_TAU.md` sha `464226a3…` + `PREREG_R21_ENMIENDA_A.md`
sha `3c7d9b13…`. Both frozen before a single PnL existed; this script is the
first thing in the project that computes one.

It reports whatever comes out. §5 declares the negative outcome in advance:
if fewer than 100 actionable trades survive, or the median net PnL is not
positive, the answer is **THE STRATEGY IS NOT OPERABLE WITH THIS SUBSTRATE**,
published as it stands, with no alternative thresholds tried.

Usage:
    python3 scripts/run_r21.py --db data/pmw.duckdb --out ~/pmw-e2
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from statistics import median

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from weather_agent import backtest, costs, database as db  # noqa: E402
from weather_agent.m2 import DATASET_VERSION  # noqa: E402

PREREG_SHA = "464226a3"
ENMIENDA_SHA = "3c7d9b1301798783bb3259e2dc1cc96a8856493cfb12efc41855d895d50fae2f"
MIN_TRADES = 100          # §4.1, frozen
LEAVE_ONE_OUT_MIN = 1     # a station with no trades cannot break a sign


def evaluate(taken) -> dict:
    """The four criteria of §4. All four are necessary; none may be relaxed."""
    pnls = [c.pnl for c in taken]
    res: dict = {"n": len(taken)}
    res["c1_no_vacuidad"] = len(taken) >= MIN_TRADES
    res["mediana_pnl"] = median(pnls) if pnls else None
    res["media_pnl"] = (sum(pnls) / len(pnls)) if pnls else None
    res["pnl_total"] = sum(pnls) if pnls else 0.0
    res["tasa_acierto"] = (sum(1 for c in taken if c.won) / len(taken)) if taken else None
    res["c2_mediana_positiva"] = bool(pnls) and median(pnls) > 0

    # §4.3 — the sign must survive dropping any ONE station.
    by_st = defaultdict(list)
    for c in taken:
        by_st[c.station].append(c.pnl)
    loo = {}
    for st in by_st:
        rest = [c.pnl for c in taken if c.station != st]
        loo[st] = median(rest) if len(rest) >= LEAVE_ONE_OUT_MIN else None
    res["loo_estacion"] = {k: v for k, v in sorted(loo.items(), key=lambda kv: (kv[1] is None, kv[1]))}
    res["c3_signo_sobrevive_estacion"] = bool(loo) and all(
        v is not None and v > 0 for v in loo.values())

    # §4.4 — the sign must survive dropping the month with the MOST trades.
    by_month = Counter(c.target_date.strftime("%Y-%m") for c in taken)
    res["operaciones_por_mes"] = dict(by_month.most_common())
    if by_month:
        big = by_month.most_common(1)[0][0]
        rest = [c.pnl for c in taken if c.target_date.strftime("%Y-%m") != big]
        res["mes_mayor"] = big
        res["mediana_sin_mes_mayor"] = median(rest) if rest else None
        res["c4_signo_sobrevive_mes"] = bool(rest) and median(rest) > 0
    else:
        res["c4_signo_sobrevive_mes"] = False

    res["VEREDICTO"] = (
        "OPERABLE" if all([res["c1_no_vacuidad"], res["c2_mediana_positiva"],
                           res["c3_signo_sobrevive_estacion"],
                           res["c4_signo_sobrevive_mes"]])
        else ("NO_EVALUABLE" if not res["c1_no_vacuidad"] else "NO_OPERABLE"))
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/pmw.duckdb")
    ap.add_argument("--out", default=os.path.expanduser("~/pmw-e2"))
    ap.add_argument("--dataset-version", default=DATASET_VERSION)
    args = ap.parse_args()

    con = db.init_db(db.connect(args.db))
    days = [r["d"] for r in db.query(
        con,
        """SELECT DISTINCT CAST(end_date AS DATE) d FROM markets
           WHERE dataset_version = ? AND end_date IS NOT NULL
             AND uma_resolution_status = 'resolved' ORDER BY 1""",
        [args.dataset_version])]
    print(f"fechas objetivo con mercados resueltos: {len(days)} "
          f"({days[0]} → {days[-1]})", flush=True)

    counters: dict = {}
    cands = backtest.candidates(con, days, dataset_version=args.dataset_version,
                                counters=counters)
    print(f"candidatos: {len(cands)} · {counters}", flush=True)
    if not cands:
        print("SIN CANDIDATOS: no se puede evaluar §4. NO_EVALUABLE.", flush=True)
        return 2

    # Descriptive, threshold-free — reported BEFORE any tau is chosen so the
    # reader can see the raw material rather than only what survived a filter.
    ex = [c for c in cands if c.passes_exec]
    print(f"  pasan el filtro de ejecucion (edge_net > margen): {len(ex)}", flush=True)
    print(f"  margen mediano: {median([c.margin for c in cands]):.4f}", flush=True)
    print(f"  edge bruto mediano: {median([c.edge_gross for c in cands]):+.4f}", flush=True)
    print(f"  fee no legible (fail-closed): {counters.get('fee_no_legible_fail_closed', 0)}",
          flush=True)

    taken, chosen = backtest.walk_forward(cands)
    verdict = evaluate(taken)
    print("\n=== §4 ===", flush=True)
    print(json.dumps(verdict, indent=1, default=str), flush=True)

    # Sensitivity: x_exec ladder and the H2/H3 cost readings. Columns only —
    # §A.2 forbids any of these from being the decision metric.
    sens = {}
    for x in costs.X_EXEC_SENSITIVITY:
        tk, _ = backtest.walk_forward(backtest.reprice(cands, x_exec=x))
        sens[f"x_exec={x}"] = {"n": len(tk),
                               "mediana": median([c.pnl for c in tk]) if tk else None}
    for cm in (costs.H2_BPS_FULL, costs.H3_DOUBLE):
        tk, _ = backtest.walk_forward(
            backtest.reprice(cands, x_exec=costs.X_EXEC_PRIMARY, cost_model=cm))
        sens[cm] = {"n": len(tk),
                    "mediana": median([c.pnl for c in tk]) if tk else None}
    print("\n=== sensibilidad (NUNCA metrica de decision) ===", flush=True)
    print(json.dumps(sens, indent=1, default=str), flush=True)

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "R21_BACKTEST.json"), "w") as fh:
        json.dump({
            "prereg_sha256": PREREG_SHA, "enmienda_sha256": ENMIENDA_SHA,
            "x_exec_primario": costs.X_EXEC_PRIMARY,
            "modelo_coste_primario": costs.H1_PRIMARY,
            "n_candidatos": len(cands), "contadores": counters,
            "acceptance": verdict, "sensibilidad": sens,
            "tau_por_dia": chosen,
            "operaciones": [
                {"market_id": c.market_id, "estacion": c.station,
                 "fecha": str(c.target_date), "lead": c.lead_h,
                 "p_mid": c.p_mid, "p_model": c.p_model, "p_exec": c.p_exec,
                 "edge_bruto": c.edge_gross, "edge_neto": c.edge_net,
                 "margen": c.margin, "gano": c.won, "pnl": c.pnl}
                for c in taken],
        }, fh, indent=1, default=str)
    print(f"\nescrito {os.path.join(args.out, 'R21_BACKTEST.json')}", flush=True)
    con.close()
    return 0 if verdict["VEREDICTO"] == "OPERABLE" else 3


if __name__ == "__main__":
    raise SystemExit(main())
