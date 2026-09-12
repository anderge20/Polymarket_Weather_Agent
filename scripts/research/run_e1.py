#!/usr/bin/env python3
"""
run_e1.py — execute PREREG_E1_MARKET_CALIBRATION and report its four criteria
=============================================================================

Is the MARKET PRICE systematically wrong in some range? No forecast is involved and
`p_model` is never read: this is the one hypothesis that does not compete on
information, which is why it survived when every other one in the audit did not.

Everything decidable was frozen in `prereg/PREREG_E1_MARKET_CALIBRATION.md` before
any outcome was seen — buckets, statistic, bootstrap, the four criteria, the
multiplicity count, and the negative outcome. This script reports what comes out.

§7 declares the negative IN ADVANCE: if no bucket clears C1-C4 after Holm, the
answer is "no exploitable price bias in this substrate", published as it stands,
with no alternative cuts tried.

Usage:
    python3 scripts/research/run_e1.py --db data/pmw.duckdb --out .
    python3 scripts/research/run_e1.py --self-test      # no DB needed
"""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

#: §2, frozen. Nine buckets. Not added to, merged or re-cut after the fact.
BUCKETS = [(0.0, .02), (.02, .05), (.05, .10), (.10, .15), (.15, .20),
           (.20, .30), (.30, .50), (.50, .75), (.75, 1.01)]
MIN_EVENTS = 100          # §5 C1 — R22's number, not a new one
N_BOOT = 2000             # §4
SEED = 20260911           # §4
SE_MULTIPLE = 2.0         # §5 C2
ALPHA = 0.05              # §6
FEE_RATE = 0.05           # D19
#: §5 C4 fallback when a bucket has too few real books to measure its own spread.
FALLBACK_HALF_SPREAD = 0.0150   # p75 of the measured half-spread (book_measurements)
MIN_BOOKS_PER_BUCKET = 100


def bucket_of(p: float) -> int | None:
    for i, (lo, hi) in enumerate(BUCKETS):
        if lo <= p < hi:
            return i
    return None


def delta(rows) -> float:
    """§3: realised frequency minus mean price. Negative = market OVERPRICES,
    which is the sign the favourite-longshot mechanism predicts in cheap buckets."""
    if not rows:
        return 0.0
    freq = sum(1 for r in rows if r["won"]) / len(rows)
    return freq - sum(r["p_mid"] for r in rows) / len(rows)


def event_aggregates(rows):
    """Per event: (wins, sum of price, count) — delta is exactly reconstructible
    from these, so resampling them is arithmetically identical to resampling rows
    while keeping the EVENT as the block (§4)."""
    agg = {}
    for r in rows:
        a = agg.setdefault(r["event_id"], [0.0, 0.0, 0])
        a[0] += 1.0 if r["won"] else 0.0
        a[1] += r["p_mid"]
        a[2] += 1
    return list(agg.values())


def delta_from(agg) -> float:
    n = sum(a[2] for a in agg)
    return (sum(a[0] for a in agg) - sum(a[1] for a in agg)) / n if n else 0.0


def bootstrap(rows, rng):
    """§4: SE and a two-sided p-value for H0: delta = 0, by BLOCK bootstrap over
    events. Never over rows — the bands of one event resolve together."""
    agg = event_aggregates(rows)
    if len(agg) < 2:
        return float("inf"), 1.0
    obs = delta_from(agg)
    reps = [delta_from(rng.choices(agg, k=len(agg))) for _ in range(N_BOOT)]
    se = statistics.pstdev(reps)
    centred = [r - obs for r in reps]
    p = (sum(1 for c in centred if abs(c) >= abs(obs)) + 1) / (len(centred) + 1)
    return se, p


def holm(pvals: dict) -> dict:
    """§6: Holm-Bonferroni over the FAMILY OF NINE, regardless of how many survive."""
    m = len(BUCKETS)
    out, prev = {}, 0.0
    for rank, (k, p) in enumerate(sorted(pvals.items(), key=lambda kv: kv[1])):
        adj = min(1.0, max(prev, (m - rank) * p))
        out[k] = adj
        prev = adj
    return out


def cost_of(bucket_idx: int, mean_price: float, half_spreads: dict) -> tuple[float, bool]:
    """§5 C4: cost CONDITIONED ON PRICE BUCKET, never a constant — Addendum 3's
    operating consequence. Returns (cost, measured) so the report can say which
    buckets fell back."""
    hs = half_spreads.get(bucket_idx)
    measured = hs is not None
    if not measured:
        hs = FALLBACK_HALF_SPREAD
    return hs + FEE_RATE * mean_price * (1.0 - mean_price), measured


def evaluate(rows, half_spreads: dict) -> dict:
    rng = random.Random(SEED)
    by_b = defaultdict(list)
    for r in rows:
        b = bucket_of(r["p_mid"])
        if b is not None:
            by_b[b].append(r)

    dates = sorted(r["target_date"] for r in rows)
    midpoint = dates[len(dates) // 2] if dates else None

    per_bucket, pvals = {}, {}
    for b in range(len(BUCKETS)):
        rs = by_b.get(b, [])
        n_ev = len({r["event_id"] for r in rs})
        d = delta(rs)
        mean_p = (sum(r["p_mid"] for r in rs) / len(rs)) if rs else 0.0
        se, p = bootstrap(rs, rng) if rs else (float("inf"), 1.0)
        first = [r for r in rs if r["target_date"] <= midpoint]
        second = [r for r in rs if r["target_date"] > midpoint]
        d1, d2 = delta(first), delta(second)
        cost, measured = cost_of(b, mean_p, half_spreads)
        per_bucket[b] = {
            "rango": f"[{BUCKETS[b][0]:.2f}, {BUCKETS[b][1]:.2f})",
            "n_filas": len(rs), "n_eventos": n_ev,
            "precio_medio": mean_p,
            "frecuencia": (sum(1 for r in rs if r["won"]) / len(rs)) if rs else None,
            "delta": d, "se": se, "p": p,
            "delta_1a_mitad": d1, "delta_2a_mitad": d2,
            "n_1a_mitad": len(first), "n_2a_mitad": len(second),
            "coste": cost, "coste_medido": measured,
            "C1_cobertura": n_ev >= MIN_EVENTS,
            "C2_significacion": abs(d) > SE_MULTIPLE * se,
            "C3_estabilidad": bool(first and second and d1 * d2 > 0
                                   and abs(d) > SE_MULTIPLE * se),
            "C4_economico": abs(d) > cost,
        }
        pvals[b] = p

    adj = holm(pvals)
    for b, a in adj.items():
        per_bucket[b]["p_holm"] = a
        per_bucket[b]["sobrevive_holm"] = a < ALPHA

    passing = [b for b, v in per_bucket.items()
               if v["C1_cobertura"] and v["C2_significacion"]
               and v["C3_estabilidad"] and v["C4_economico"]]
    confirmed = [b for b in passing if per_bucket[b]["sobrevive_holm"]]

    return {
        "prereg": "PREREG_E1_MARKET_CALIBRATION.md",
        "n_filas": len(rows), "n_eventos": len({r["event_id"] for r in rows}),
        "corte_mitades": str(midpoint),
        "buckets": per_bucket,
        "pasan_C1_C4": sorted(passing),
        "confirmados_tras_holm": sorted(confirmed),
        "veredicto": (
            "EDGE DE PRECIO CONFIRMADO en los buckets " + str(sorted(confirmed))
            if confirmed else
            "C — SPECULATIVE: pasa C1–C4 pero no sobrevive a Holm en " + str(sorted(passing))
            if passing else
            "NO EXISTE SESGO DE PRECIO EXPLOTABLE EN ESTE SUBSTRATO (§7)"),
    }


def report(res: dict) -> None:
    print(f"\nE1 — calibración del PRECIO de mercado · {res['prereg']}")
    print(f"filas {res['n_filas']} · eventos {res['n_eventos']} · "
          f"corte de mitades {res['corte_mitades']}\n")
    h = (f"{'bucket':>14} {'n_ev':>6} {'precio':>7} {'frec':>7} {'Delta':>8} "
         f"{'2xSE':>8} {'coste':>7} {'C1':>3} {'C2':>3} {'C3':>3} {'C4':>3} {'Holm':>7}")
    print(h); print("-" * len(h))
    for b in range(len(BUCKETS)):
        v = res["buckets"][b]
        y = lambda c: " ok" if v[c] else "  ."
        fr = f"{v['frecuencia']:.4f}" if v["frecuencia"] is not None else "    -"
        se = f"{SE_MULTIPLE*v['se']:.4f}" if v["se"] != float("inf") else "  inf"
        print(f"{v['rango']:>14} {v['n_eventos']:>6} {v['precio_medio']:>7.4f} {fr:>7} "
              f"{v['delta']:>+8.4f} {se:>8} {v['coste']:>7.4f} "
              f"{y('C1_cobertura')} {y('C2_significacion')} {y('C3_estabilidad')} "
              f"{y('C4_economico')} {v['p_holm']:>7.4f}")
    fell = [res["buckets"][b]["rango"] for b in range(len(BUCKETS))
            if not res["buckets"][b]["coste_medido"]]
    if fell:
        print(f"\ncoste NO medido (fallback {FALLBACK_HALF_SPREAD}): {', '.join(fell)}")
    print(f"\nVEREDICTO: {res['veredicto']}")
    if not res["confirmados_tras_holm"] and not res["pasan_C1_C4"]:
        print("\nE1 era la última hipótesis viva del proyecto. §7 del preregistro:")
        print("  la categoría se abandona y el universo se busca fuera del tiempo.")


# --------------------------------------------------------------------------- self-test
def _synthetic(bias: float, n_events: int = 400, seed: int = 5):
    """Rows with a KNOWN bias injected in the cheap buckets, so the harness can be
    shown to detect what is there and not detect what is not — the only honest way
    to ship a script whose real substrate this session cannot reach."""
    rng = random.Random(seed)
    rows = []
    for e in range(n_events):
        for _ in range(8):
            p = rng.choice([0.01, 0.03, 0.07, 0.12, 0.17, 0.25, 0.40, 0.60, 0.85])
            true_p = max(0.0, min(1.0, p + bias if p < 0.10 else p))
            rows.append({"event_id": f"e{e}", "p_mid": p,
                         "won": rng.random() < true_p,
                         "target_date": f"2026-0{5 + e % 4}-01"})
    return rows


def self_test() -> int:
    print("SELF-TEST — no database needed.\n")
    print("A) NULL: the market is perfectly calibrated. Nothing may be confirmed.")
    null = evaluate(_synthetic(0.0), {})
    print(f"   confirmed: {null['confirmados_tras_holm']}  -> "
          f"{'PASS' if not null['confirmados_tras_holm'] else 'FAIL'}")
    print("\nB) INJECTED: cheap buckets pay 4 points MORE than their price")
    print("   (the opposite of longshot bias, so a sign error cannot hide).")
    inj = evaluate(_synthetic(+0.04), {})
    cheap = [b for b in inj["confirmados_tras_holm"] if b <= 2]
    print(f"   confirmed: {inj['confirmados_tras_holm']}  -> "
          f"{'PASS' if cheap else 'FAIL'}")
    for b in sorted(inj["buckets"]):
        v = inj["buckets"][b]
        if b <= 2:
            print(f"     {v['rango']}: delta {v['delta']:+.4f} "
                  f"(injected +0.0400), 2xSE {2*v['se']:.4f}")
    ok = (not null["confirmados_tras_holm"]) and bool(cheap)
    print(f"\nSELF-TEST {'PASSED' if ok else 'FAILED'}")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db")
    ap.add_argument("--out", default=".")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.db:
        ap.error("--db is required (or use --self-test)")

    from weather_agent import backtest, database as db          # noqa: E402
    from weather_agent.m2 import DATASET_VERSION                # noqa: E402

    con = db.init_db(db.connect(a.db))
    days = [r["d"] for r in db.query(
        con, """SELECT DISTINCT CAST(end_date AS DATE) d FROM markets
                WHERE dataset_version = ? AND end_date IS NOT NULL
                  AND uma_resolution_status = 'resolved' ORDER BY 1""",
        [DATASET_VERSION])]
    cands = backtest.candidates(con, days, dataset_version=DATASET_VERSION,
                                counters={})
    meta = {r["market_id"]: r["event_id"] for r in db.query(
        con, "SELECT market_id, event_id FROM markets WHERE dataset_version = ?",
        [DATASET_VERSION])}
    rows = [{"event_id": meta.get(c.market_id, c.market_id), "p_mid": c.p_mid,
             "won": c.won, "target_date": c.target_date}
            for c in cands if meta.get(c.market_id) is not None]
    print(f"filas {len(rows)} · eventos {len({r['event_id'] for r in rows})}")

    res = evaluate(rows, half_spreads={})   # see C4: measured spreads go here
    report(res)
    path = os.path.join(a.out, "E1_REPORT.json")
    json.dump(res, open(path, "w"), indent=2, default=str)
    print(f"\nescrito: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
