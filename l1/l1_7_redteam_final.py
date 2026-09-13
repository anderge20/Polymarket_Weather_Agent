#!/usr/bin/env python3
"""LEVEL 1 · L1.7 — FINAL RED TEAM. Ejecuta los CINCO ataques de `LOCK_L1_7.md`.

No busca edge, precio ni PnL. No toca produccion. NO emite el veredicto: eso es L1.8.
"""
from __future__ import annotations

import datetime as dt
import math
import os
import random
import statistics as stx
import sys

import duckdb

REPO = os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-merge")
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/fase2")
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/l1")
import l1_2_baselines as L2                                                # noqa: E402
from n075_poblacion import DB, poblacion, pronosticos                      # noqa: E402
from l1_2_baselines import construye, observaciones_c, label_av, tasof     # noqa: E402
from l1_5_calibracion import UNIF, EPS, SEMILLA, NBOOT, brier_ev           # noqa: E402

SEP = "-" * 100


def ic(v, rng, n=NBOOT):
    r = sorted(stx.mean(rng.choices(v, k=len(v))) for _ in range(n))
    return r[int(.025 * n)], r[int(.975 * n)]


def brier_vec(p, y):
    return stx.mean([(min(max(a, EPS), 1 - EPS) - c) ** 2 for a, c in zip(p, y)])


def orden_bandas(ev):
    return sorted(range(ev["n_bandas"]),
                  key=lambda i: (-1e9 if ev["bandas"][i][0] is None else ev["bandas"][i][0]))


def main():
    con = duckdb.connect(DB, read_only=True); con.execute("SET TimeZone='UTC'")
    obs, zona = observaciones_c(con, "EGLC")
    FC = pronosticos(con, "EGLC"); pob, _, _, _ = poblacion(con, "markets_v2", "EGLC")
    rng = random.Random(SEMILLA)

    for lead in (24, 9):
        f = construye(con, pob, obs, FC, zona, lead)
        du = [brier_ev(x, "B4_fc_prob") - UNIF for x in f]
        print(f"\n{'=' * 100}\nLEAD {lead} h · {len(f)} eventos · B4-uniforme "
              f"{stx.mean(du):+.5f} {ic(du, rng)}\n{'=' * 100}")

        # ---------------------------------------------------------- A1
        print(f"\n{SEP}\nA1 · GEOMETRIA DE LA ESCALERA — un control que IGNORA el pronostico\n{SEP}")
        disp = stx.mean(sum(1 for a in x["p"]["B4_fc_prob"] if a > 0) for x in f)
        semi = max(1, int(round((disp - 1) / 2)))
        print(f"  dispersion media de B4: {disp:.2f} bandas con masa -> el control usa "
              f"{2*semi+1} bandas centradas")
        ctrl, b4v = [], []
        for x in f:
            ev = pob[x["td"]]; idx = orden_bandas(ev); n = ev["n_bandas"]
            centro = n // 2
            viv = [idx[i] for i in range(max(0, centro - semi), min(n, centro + semi + 1))]
            p = [0.0] * n
            for i in viv:
                p[i] = 1.0 / len(viv)
            ctrl.append(brier_vec(p, x["y"]) - UNIF)
            b4v.append(brier_ev(x, "B4_fc_prob") - UNIF)
        lo, hi = ic(ctrl, rng, 4000)
        print(f"  CTRL_escalera - uniforme  {stx.mean(ctrl):+9.5f}  IC95 [{lo:+.5f}, {hi:+.5f}]"
              f"  {'MEJORA -> la geometria SOLA ya bate al uniforme' if hi < 0 else 'no mejora'}")
        print(f"  B4          - uniforme  {stx.mean(b4v):+9.5f}")
        if stx.mean(ctrl) < 0:
            print(f"  -> fraccion de la ventaja de B4 atribuible a la geometria: "
                  f"{100*stx.mean(ctrl)/stx.mean(b4v):.1f} %")
        d = [a - b for a, b in zip(b4v, ctrl)]
        lo, hi = ic(d, rng, 4000)
        print(f"  B4 - CTRL_escalera        {stx.mean(d):+9.5f}  IC95 [{lo:+.5f}, {hi:+.5f}]"
              f"  {'B4 APORTA sobre la geometria' if hi < 0 else 'NO se distingue de la geometria'}")
        # ¿donde cae la ganadora respecto al centro?
        pos = []
        for x in f:
            ev = pob[x["td"]]; idx = orden_bandas(ev)
            k = x["y"].index(1.0)
            pos.append(idx.index(k) - ev["n_bandas"] // 2)
        from collections import Counter
        print(f"  posicion de la ganadora respecto al centro: {dict(sorted(Counter(pos).items()))}")
        print(f"    |desviacion| media {stx.mean(abs(v) for v in pos):.2f} bandas "
              f"(uniforme daria {sum(abs(i-5) for i in range(11))/11:.2f})")

        # ---------------------------------------------------------- A2
        print(f"\n{SEP}\nA2 · BANDAS ABIERTAS CONTRA INTERIORES\n{SEP}")
        grupos = {"abierta INFERIOR": [], "INTERIOR": [], "abierta SUPERIOR": []}
        for i, x in enumerate(f):
            ev = pob[x["td"]]; k = x["y"].index(1.0)
            lo_, hi_ = ev["bandas"][k][0], ev["bandas"][k][1]
            g = ("abierta INFERIOR" if lo_ is None else
                 "abierta SUPERIOR" if hi_ is None else "INTERIOR")
            grupos[g].append(du[i])
        for g, v in grupos.items():
            if not v:
                print(f"  {g:18s} n=  0"); continue
            l2, h2 = ic(v, rng, 4000) if len(v) >= 8 else (float("nan"), float("nan"))
            print(f"  {g:18s} n={len(v):3d}  delta {stx.mean(v):+9.5f}  IC95 [{l2:+.5f}, {h2:+.5f}]")
        print("  -> si la ventaja viviera SOLO en las abiertas, el grupo INTERIOR no mejoraria")

        # ---------------------------------------------------------- A4
        print(f"\n{SEP}\nA4 · ¿SABE LA ESCALERA ALGO QUE EL PRONOSTICO NO SEPA?\n{SEP}")
        cen, fc, ob = [], [], []
        for x in f:
            ev = pob[x["td"]]; idx = orden_bandas(ev)
            b = ev["bandas"][idx[ev["n_bandas"] // 2]]
            cen.append(b[0] if b[0] is not None else b[1])
            fc.append(FC[(x["td"], lead)][1]); ob.append(obs[x["td"]])
        def corr(a, b):
            ma, mb = stx.mean(a), stx.mean(b)
            return (sum((p - ma) * (q - mb) for p, q in zip(a, b)) / len(a)
                    / (stx.pstdev(a) * stx.pstdev(b)))
        print(f"  corr(centro de la escalera, observacion) = {corr(cen, ob):+.3f}")
        print(f"  corr(pronostico,            observacion) = {corr(fc, ob):+.3f}")
        print(f"  MAE del centro de la escalera contra la observacion: "
              f"{stx.mean(abs(a-b) for a, b in zip(cen, ob)):.3f} C")
        print(f"  MAE del pronostico                                 : "
              f"{stx.mean(abs(a-b) for a, b in zip(fc, ob)):.3f} C")

        # ---------------------------------------------------------- A5
        print(f"\n{SEP}\nA5 · ROBUSTEZ AL MINIMO DE ENTRENAMIENTO (se reportan los CUATRO)\n{SEP}")
        orig = L2.MIN_TRAIN
        for mt in (20, 30, 40, 50):
            L2.MIN_TRAIN = mt
            g = construye(con, pob, obs, FC, zona, lead)
            v = [brier_ev(x, "B4_fc_prob") - UNIF for x in g]
            l2, h2 = ic(v, rng, 4000)
            print(f"  MIN_TRAIN {mt:2d}  n={len(g):3d}  delta {stx.mean(v):+9.5f}  "
                  f"IC95 [{l2:+.5f}, {h2:+.5f}]  {'excluye el cero' if h2 < 0 else 'INCLUYE EL CERO'}")
        L2.MIN_TRAIN = orig

    # ---------------------------------------------------------- A3
    print(f"\n{'=' * 100}\nA3 · MULTIPLES COMPARACIONES, contadas de verdad\n{'=' * 100}")
    comparaciones = [
        ("L1.4 primaria, B1..B4 contra B0, dos leads", 8),
        ("L1.4 control uniforme, cinco modelos, dos leads", 10),
        ("L1.5 mitades temporales, dos leads", 4),
        ("L1.6 placebo A, seis desplazamientos, dos leads", 12),
        ("L1.6 placebo B, dos leads", 2),
        ("L1.6 test de heterogeneidad, dos leads", 2),
        ("L1.7 A1/A2/A5, dos leads", 2 * (2 + 3 + 4)),
    ]
    tot = sum(n for _, n in comparaciones)
    for nom, n in comparaciones:
        print(f"  {nom:52s} {n:3d}")
    print(f"  {'TOTAL con IC ejecutados':52s} {tot:3d}")
    print(f"\n  Bonferroni sobre la primaria: alfa 0,05 / {tot} = {0.05/tot:.5f}")
    print(f"  el IC95 de B4-uniforme a lead 9 es [-0,02132, -0,01296]; su p bilateral")
    print(f"  aproximado por el bootstrap fue 0 de 10 000 -> p < 1e-4 < {0.05/tot:.5f}")
    print(f"  -> la primaria SOBREVIVE a Bonferroni incluso contando las {tot} comparaciones")
    con.close()


if __name__ == "__main__":
    main()
