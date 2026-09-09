#!/usr/bin/env python3
"""
run_r22.py — where, if anywhere, does the model beat the market?
=================================================================

`PREREG_R22_SKILL_LOCUS.md` sha `c23ca0b6…` (v3), frozen before any Brier existed.
v2 was withdrawn as incomplete after session A's second refutation; v1 before it.

R22 answers a SKILL question, not a money question. §6 forbids computing any PnL
here. And §0 fixes what its answer is allowed to license:

  * a NEGATIVE result is strong, and is enough not to preregister R21.2;
  * a POSITIVE result is NOT a finding. Brier is an average over the whole
    distribution; profit lives in a chosen subset. Necessary, never sufficient.

THE UNIT OF OBSERVATION IS THE EVENT (§1). The bands of one event are a partition
summing to 1: if the forecast is wrong for that event it is wrong for all of them
at once. Treating rows as independent observations overstates precision — session
A's blocker 2, already demonstrated on R21, where 468 trades were 211 events.
Every resample here is a BLOCK bootstrap over events; none is over rows.

Usage:
    python3 scripts/run_r22.py --db data/pmw.duckdb --out ~/pmw-e2
"""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from weather_agent import backtest, database as db  # noqa: E402
from weather_agent.m2 import DATASET_VERSION  # noqa: E402

PREREG_SHA = "0508ced1213c39e17766bbc6ccf249a1071849b1fe4d2d852dc104cb00b15796"
MIN_EVENTOS = 100      # §3, session A's number, not mine
N_BOOT = 2000          # §5
N_PERM = 2000          # §5
SEED = 20260909        # §5
SE_MULTIPLE = 2.0      # §5
ALPHA = 0.05           # §5


def brier(rows, key) -> float:
    return sum((key(r) - (1.0 if r["won"] else 0.0)) ** 2 for r in rows) / len(rows)


def bss(rows, key) -> float:
    """Brier Skill Score against the CELL's own base rate (§5bis).

    A REPORTING rule, not a scoring rule: it does not change the ordering inside a
    cell, so it cannot make anyone pass. It makes visible that in the cheap price
    deciles both sides have skill ~0, so "the market wins" there reads as what it
    is — uninformative.
    """
    base = sum(1 for r in rows if r["won"]) / len(rows)
    ref = sum((base - (1.0 if r["won"] else 0.0)) ** 2 for r in rows) / len(rows)
    return 1.0 - brier(rows, key) / ref if ref > 0 else 0.0


def delta(rows) -> float:
    """Positive = the model beats the market, in the SAME subset (§2 of R21's §)."""
    return brier(rows, lambda r: r["p_mid"]) - brier(rows, lambda r: r["p_model"])


def event_aggregates(rows) -> list:
    """Per event: (sum sq. error of the market, of the model, count).

    Δ is a difference of means of squared errors, so it is exactly reconstructible
    from these three numbers per block:

        Δ = (Σ_ev sse_mid − Σ_ev sse_model) / Σ_ev n

    Resampling and permuting over these aggregates is ARITHMETICALLY IDENTICAL to
    doing it over the rows, and turns 200 million row visits into a few million.
    The block is still the event: nothing about §1 is relaxed.
    """
    agg: dict = {}
    for r in sorted(rows, key=lambda x: str(x["event_id"])):
        y = 1.0 if r["won"] else 0.0
        a = agg.setdefault(r["event_id"], [0.0, 0.0, 0])
        a[0] += (r["p_mid"] - y) ** 2
        a[1] += (r["p_model"] - y) ** 2
        a[2] += 1
    return list(agg.values())


def delta_from(agg) -> float:
    n = sum(a[2] for a in agg)
    return (sum(a[0] for a in agg) - sum(a[1] for a in agg)) / n if n else 0.0


def se_by_event(rows, rng) -> float:
    """§5: standard error of Δ by BLOCK bootstrap over events. Never over rows."""
    agg = event_aggregates(rows)
    if len(agg) < 2:
        return float("inf")
    out = []
    for _ in range(N_BOOT):
        out.append(delta_from(rng.choices(agg, k=len(agg))))
    return statistics.pstdev(out)


def terciles(values):
    v = sorted(values)
    if not v:
        return (0.0, 0.0)
    return (v[len(v) // 3], v[2 * len(v) // 3])


def build_cells(rows, *, drop_age: bool = False) -> dict:
    """§2: MARGINAL axes only, declared in advance. No crossing of axes."""
    cells: dict = defaultdict(list)
    w_lo, w_hi = terciles([r["spread_fc"] for r in rows])
    c_lo, c_hi = terciles([r["event_bands"] for r in rows])
    a_lo, a_hi = terciles([r["age_days"] for r in rows if r["age_days"] is not None])
    for r in rows:
        cells[f"lead={r['lead_h']}"].append(r)
        cells[f"unidad={r['unit']}"].append(r)
        cells[f"banda={r['band_pos']}"].append(r)
        cells[f"precio_decil={min(int(r['p_mid'] * 10), 9)}"].append(r)
        cells[f"estacion={r['station']}"].append(r)
        cells[f"anchura_fc={'baja' if r['spread_fc'] <= w_lo else 'alta' if r['spread_fc'] > w_hi else 'media'}"].append(r)
        cells[f"completitud={'baja' if r['event_bands'] <= c_lo else 'alta' if r['event_bands'] > c_hi else 'media'}"].append(r)
        if not drop_age:
            cells[f"antiguedad={'baja' if r['age_days'] <= a_lo else 'alta' if r['age_days'] > a_hi else 'media'}"].append(r)
    return cells


def n_events(rows) -> int:
    return len({r["event_id"] for r in rows})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/pmw.duckdb")
    ap.add_argument("--out", default=os.path.expanduser("~/pmw-e2"))
    ap.add_argument("--rows-cache", default=None,
                    help="reuse the as-of candidate rows instead of rebuilding "
                         "them; the rebuild is deterministic, so this changes "
                         "nothing but the wall clock")
    args = ap.parse_args()
    rng = random.Random(SEED)

    if args.rows_cache and os.path.exists(args.rows_cache):
        rows = json.load(open(args.rows_cache))
        print(f"filas desde cache: {len(rows)} · eventos: {n_events(rows)}", flush=True)
        return evaluate(rows, rng, args.out)

    con = db.init_db(db.connect(args.db))
    days = [r["d"] for r in db.query(
        con, """SELECT DISTINCT CAST(end_date AS DATE) d FROM markets
                WHERE dataset_version = ? AND end_date IS NOT NULL
                  AND uma_resolution_status = 'resolved' ORDER BY 1""",
        [DATASET_VERSION])]

    # §4: p_model is RECOMPUTED under as-of discipline, never reused from R21, and
    # with the CDF that carries session A's lower-tail fix — a DIFFERENT CDF from
    # the one that produced R21, which is why R22 is not row-comparable with it.
    cands = backtest.candidates(con, days, dataset_version=DATASET_VERSION,
                                counters={})
    meta = {r["market_id"]: r for r in db.query(
        con, """SELECT m.market_id, m.event_id, m.discovered_at,
                       count(*) OVER (PARTITION BY m.event_id) AS event_bands
                FROM markets m WHERE m.dataset_version = ?""", [DATASET_VERSION])}

    rows = []
    for c in cands:
        m = meta.get(c.market_id)
        if m is None:
            continue
        disc = m.get("discovered_at")
        age = ((c.decision_time - disc).total_seconds() / 86400.0
               if disc is not None else None)
        rows.append({
            "event_id": m["event_id"], "station": c.station, "lead_h": c.lead_h,
            "unit": c.unit, "p_mid": c.p_mid, "p_model": c.p_model, "won": c.won,
            "target_date": c.target_date,
            "band_pos": backtest.band_position(c.q_market, c.lo, c.hi),
            "spread_fc": c.q_market[90] - c.q_market[10],
            "event_bands": m["event_bands"],
            "age_days": age,
        })
    print(f"filas: {len(rows)} · eventos: {n_events(rows)}", flush=True)
    con.close()
    if args.rows_cache:
        json.dump(rows, open(args.rows_cache, "w"), default=str)
    return evaluate(rows, rng, args.out)


def evaluate(rows, rng, out_dir) -> int:
    if not rows:
        print("SIN FILAS — nada que evaluar.", flush=True)
        return 2

    # `age_days` is NULL wherever `discovered_at` was never written — and it was
    # never written for any of the 6 143 markets. An axis with no data does NOT
    # become three equal buckets: every NaN comparison is False, so all three
    # tercile tests fail and every row lands in "media" — ONE cell wearing the
    # shape of three, which is the same defect as the string 'nan' in
    # `station_identifier` and as a fixture certifying a world that does not
    # exist. The axis is DROPPED and reported as unavailable.
    n_age = sum(1 for r in rows if r["age_days"] is not None)
    ejes_no_disponibles = {}
    if n_age < len(rows) / 2:
        ejes_no_disponibles["antiguedad"] = (
            f"discovered_at nulo en {len(rows) - n_age}/{len(rows)} filas; "
            "el eje no se evalua y no se colapsa a una celda")
        print(f"  EJE ANTIGUEDAD NO DISPONIBLE: discovered_at nulo en "
              f"{len(rows) - n_age}/{len(rows)}", flush=True)
    # the book-spread axis was already declared impossible in the preregistration
    ejes_no_disponibles["spread_libro"] = (
        "orderbook_snapshots vacia y todo price_history es MIDPOINT_ESTIMATED; "
        "PREREG_R22 §0 premisa 1")

    cells = build_cells(rows, drop_age="antiguedad" in ejes_no_disponibles)
    print(f"celdas construidas: {len(cells)}", flush=True)

    # ---- evaluable cells, and the observed statistics
    evaluables, insuficientes = {}, {}
    for name, rs in sorted(cells.items()):
        ne = n_events(rs)
        if ne < MIN_EVENTOS:
            insuficientes[name] = {"eventos": ne, "filas": len(rs)}
            continue
        d = delta(rs)
        evaluables[name] = {
            "eventos": ne, "filas": len(rs), "delta": d,
            "brier_modelo": brier(rs, lambda r: r["p_model"]),
            "brier_mercado": brier(rs, lambda r: r["p_mid"]),
            "bss_modelo": bss(rs, lambda r: r["p_model"]),
            "bss_mercado": bss(rs, lambda r: r["p_mid"]),
            "tasa_base": sum(1 for r in rs if r["won"]) / len(rs),
            "se": se_by_event(rs, rng),
        }
    print(f"  evaluables (>= {MIN_EVENTOS} eventos): {len(evaluables)} · "
          f"INSUFICIENTE: {len(insuficientes)}", flush=True)
    if not evaluables:
        print("NINGUNA CELDA EVALUABLE.", flush=True)
        return 2

    t_obs = max(v["delta"] for v in evaluables.values())

    # ---- §5: permutation on the MAXIMUM statistic, PAIRED, by whole event.
    # The null is that the two predictors are exchangeable, so under it Delta is
    # symmetric about zero. Swapping `p_model` and `p_mid` for a WHOLE event at a
    # time keeps §1's blocks intact by construction, needs no size matching, and
    # never touches which cell a row belongs to. A swap simply exchanges the two
    # sums in that event's aggregate, so the whole test runs on aggregates.
    #
    # v3 froze a different scheme — "shuffle the assignment of events to cells" —
    # and it is not implementable with MARGINAL axes: a row's cell is determined by
    # its own attributes, so reassigning would change what the cells are. Found
    # while implementing, before any Brier existed, and re-frozen as v4 rather than
    # quietly implementing something else.
    # SORTED, not a set: set iteration order depends on PYTHONHASHSEED, so the
    # flip vector would differ between runs despite the fixed seed and the
    # published p-value would not be reproducible. A frozen procedure that cannot
    # be re-run to the same number is not frozen.
    ev_index = {e: i for i, e in enumerate(sorted({r["event_id"] for r in rows}))}
    cell_agg = {}
    for name in evaluables:
        per_ev: dict = {}
        for r in cells[name]:
            y = 1.0 if r["won"] else 0.0
            a = per_ev.setdefault(ev_index[r["event_id"]], [0.0, 0.0, 0])
            a[0] += (r["p_mid"] - y) ** 2
            a[1] += (r["p_model"] - y) ** 2
            a[2] += 1
        n = sum(a[2] for a in per_ev.values())
        cell_agg[name] = ([(i, a[0], a[1]) for i, a in per_ev.items()], n)

    n_ev_total = len(ev_index)
    hits = 0
    for _ in range(N_PERM):
        flip = [rng.random() < 0.5 for _ in range(n_ev_total)]
        best = None
        for name, (items, n) in cell_agg.items():
            tot = 0.0
            for i, s_mid, s_mod in items:
                tot += (s_mod - s_mid) if flip[i] else (s_mid - s_mod)
            d = tot / n
            if best is None or d > best:
                best = d
        if best is not None and best >= t_obs:
            hits += 1
    p_familia = (1 + hits) / (1 + N_PERM)

    ganadoras = {
        n: v for n, v in evaluables.items()
        if v["delta"] > 0 and v["delta"] >= SE_MULTIPLE * v["se"] and p_familia < ALPHA
    }

    print(f"\nT_obs (mejor delta) = {t_obs:+.5f} · p_familia = {p_familia:.4f}", flush=True)
    print(f"{'celda':34} {'ev':>5} {'delta':>9} {'2*SE':>9} {'BSS mod':>8} {'BSS mkt':>8}")
    for n, v in sorted(evaluables.items(), key=lambda kv: -kv[1]["delta"]):
        print(f"{n:34} {v['eventos']:>5} {v['delta']:>+9.5f} {2*v['se']:>9.5f} "
              f"{v['bss_modelo']:>8.3f} {v['bss_mercado']:>8.3f}", flush=True)

    veredicto = ("HAY_CANDIDATO" if ganadoras else
                 "EL_MODELO_NO_SUPERA_AL_MERCADO_EN_NINGUNO_DE_LOS_ESTRATOS_DECLARADOS")
    print(f"\nganadoras: {list(ganadoras)}\nVEREDICTO: {veredicto}", flush=True)

    os.makedirs(out_dir, exist_ok=True)
    json.dump({
        "prereg_sha256": PREREG_SHA, "min_eventos": MIN_EVENTOS,
        "n_filas": len(rows), "n_eventos": n_events(rows),
        "t_obs": t_obs, "p_familia": p_familia, "n_permutaciones": N_PERM,
        "celdas_evaluables": evaluables, "celdas_insuficientes": insuficientes,
        "ganadoras": ganadoras, "VEREDICTO": veredicto,
        "ejes_no_disponibles": ejes_no_disponibles,
        "nota": ("Un resultado POSITIVO no es un hallazgo: es un candidato sobre el "
                 "que preregistrar otra cosa (PREREG_R22 §0). Brier es un promedio "
                 "sobre toda la distribucion; el beneficio vive en un subconjunto "
                 "elegido. Condicion necesaria, nunca suficiente."),
    }, open(os.path.join(out_dir, "R22_SKILL_LOCUS.json"), "w"), indent=1, default=str)
    print(f"escrito {os.path.join(out_dir, 'R22_SKILL_LOCUS.json')}", flush=True)
    return 0 if veredicto.startswith("EL_MODELO_NO") else 3


if __name__ == "__main__":
    raise SystemExit(main())
