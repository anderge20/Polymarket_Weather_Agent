#!/usr/bin/env python3
"""LEVEL 1 · L1.4 — WALK-FORWARD OOS. Ejecuta `LOCK_L1_4.md`, espejado antes.

NO busca edge, precio ni PnL, no optimiza umbrales, no activa trading, no toca produccion.
NO emite el veredicto final de Level 1: eso requiere L1.5-L1.7.
"""
from __future__ import annotations

import math
import os
import random
import statistics as stx
import sys
from collections import Counter, defaultdict

import duckdb

REPO = os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-merge")
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/fase2")
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/l1")
from n075_poblacion import DB, poblacion, pronosticos                      # noqa: E402
from l1_2_baselines import (MODELOS, construye, observaciones_c)           # noqa: E402

ST, DSV = "EGLC", "markets_v2"
EPS = 1e-6
SEMILLA = 20260913
NBOOT = 10000
CORTE = None            # 2026-06-23, fijado en el LOCK


def clip(p):
    return min(max(p, EPS), 1.0 - EPS)


def metricas_evento(x, m):
    p, y = x["p"][m], x["y"]
    b = stx.mean([(clip(a) - c) ** 2 for a, c in zip(p, y)])
    l = stx.mean([-(c * math.log(clip(a)) + (1 - c) * math.log(1 - clip(a)))
                  for a, c in zip(p, y)])
    k = y.index(1.0)
    #: rango de la ganadora ordenando de MAYOR a menor probabilidad; empates con rango medio
    mayores = sum(1 for a in p if a > p[k])
    iguales = sum(1 for a in p if a == p[k])
    rango = mayores + (iguales + 1) / 2
    return b, l, rango, 1.0 if rango == (iguales + 1) / 2 and mayores == 0 and iguales == 1 else 0.0


def boot_par(dif, rng):
    """Bootstrap CLUSTERIZADO POR EVENTO: se remuestrean eventos, no contratos."""
    n = len(dif)
    r = sorted(stx.mean(rng.choices(dif, k=n)) for _ in range(NBOOT))
    return r[int(.025 * NBOOT)], r[int(.975 * NBOOT)]


def main():
    con = duckdb.connect(DB, read_only=True)
    con.execute("SET TimeZone='UTC'")
    obs, zona = observaciones_c(con, ST)
    FC = pronosticos(con, ST)
    pob, _, _, _ = poblacion(con, DSV, ST)

    print("=" * 100)
    print("L1.4 — WALK-FORWARD OOS · EGLC · escalera 11 · epsilon 1e-6 · semilla 20260913")
    print("=" * 100)

    for lead in (24, 9):
        filas = construye(con, pob, obs, FC, zona, lead)
        ns = {x["n"] for x in filas}
        print(f"\n{'=' * 100}\nLEAD {lead} h · eventos de test {len(filas)} · "
              f"contratos {sum(x['n'] for x in filas)} · escaleras {sorted(ns)}\n{'=' * 100}")
        assert ns == {11}, ns

        M = {m: [metricas_evento(x, m) for x in filas] for m in MODELOS}
        print(f"  {'modelo':16s} {'Brier/ev':>9s} {'Brier/contr':>12s} {'LogLoss':>9s} "
              f"{'rango gan.':>11s} {'top-1':>7s} {'p_max':>7s} {'sharp':>7s}")
        for m in MODELOS:
            b = stx.mean(v[0] for v in M[m])
            bc = stx.mean((clip(a) - c) ** 2 for x in filas for a, c in zip(x["p"][m], x["y"]))
            l = stx.mean(v[1] for v in M[m])
            rg = stx.mean(v[2] for v in M[m])
            t1 = stx.mean(v[3] for v in M[m])
            pm = stx.mean(max(x["p"][m]) for x in filas)
            sh = stx.mean(sum(a * a for a in x["p"][m]) for x in filas)
            marca = "" if m == "B4_fc_prob" else "  (LL no interpretable)" if m != "B0_clima" else ""
            print(f"  {m:16s} {b:9.5f} {bc:12.5f} {l:9.5f} {rg:11.3f} {t1:7.3f} {pm:7.3f} {sh:7.4f}{marca}")
        print(f"  {'azar (1/11)':16s} {10/121:9.5f} {10/121:12.5f} {math.log(11)*0+0.30464:9.5f} "
              f"{6.0:11.3f} {1/11:7.3f} {1/11:7.3f} {1/11:7.4f}")

        print(f"\n  --- METRICA PRIMARIA: Brier por evento, APAREADO contra B0_clima ---")
        print(f"      bootstrap clusterizado por EVENTO · {NBOOT} remuestreos · IC95")
        rng = random.Random(SEMILLA)
        for m in MODELOS[1:]:
            dif = [M[m][i][0] - M["B0_clima"][i][0] for i in range(len(filas))]
            lo, hi = boot_par(dif, rng)
            signo = "MEJORA" if hi < 0 else ("PEOR" if lo > 0 else "IC INCLUYE EL CERO")
            print(f"      {m:16s} delta {stx.mean(dif):+9.5f}  IC95 [{lo:+.5f}, {hi:+.5f}]  {signo}")

        print(f"\n  --- DIAGNOSTICO TEMPORAL (corte 2026-06-23; diagnostico, NO seleccion) ---")
        mitad = sorted(x["td"] for x in filas)[len(filas) // 2]
        for etq, sel in (("1a mitad", lambda t: t < mitad), ("2a mitad", lambda t: t >= mitad)):
            idx = [i for i, x in enumerate(filas) if sel(x["td"])]
            print(f"      {etq} · {len(idx)} eventos:  " + "  ".join(
                f"{m.split('_')[0]} {stx.mean(M[m][i][0] for i in idx):.5f}" for m in MODELOS))

        print(f"\n  --- CALIBRACION BASICA (sobre CONTRATOS; diagnostico: no son independientes) ---")
        bins = [0, .05, .1, .2, .3, .5, 1.01]
        for m in ("B0_clima", "B4_fc_prob"):
            print(f"      {m}")
            for i in range(len(bins) - 1):
                s = [(a, c) for x in filas for a, c in zip(x["p"][m], x["y"])
                     if bins[i] <= a < bins[i + 1]]
                if not s:
                    continue
                print(f"        p en [{bins[i]:.2f},{bins[i+1]:.2f})  n={len(s):5d}  "
                      f"predicho {stx.mean(a for a, _ in s):.4f}  observado {stx.mean(c for _, c in s):.4f}")

        if lead == 24:
            print(f"\n  --- B4: la distribucion de error entre ventanas (solo train) ---")
            for k in (0, len(filas) // 3, 2 * len(filas) // 3, len(filas) - 1):
                x = filas[k]
                print(f"      test {x['td']}  n_train {x['n_train']:3d}  cutoff {x['train_max']}")

    con.close()
    print(f"\n{'=' * 100}")
    print("L1.4 ejecutado. NO se emite veredicto de Level 1: requiere L1.5-L1.7.")
    print("=" * 100)


if __name__ == "__main__":
    main()
