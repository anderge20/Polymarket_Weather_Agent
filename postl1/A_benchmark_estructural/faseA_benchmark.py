#!/usr/bin/env python3
"""POST-L1.8 · FASE A — BENCHMARK ESTRUCTURAL COMPLETO. Ejecuta `LOCK_FASE_A.md`.

No toca L2, precios, EV, PnL, trading, ejecucion, order book, umbrales, estrategia,
stake, optimizacion economica, dinero real, paper trading, bot ni produccion.
"""
from __future__ import annotations

import datetime as dt
import math
import os
import random
import statistics as stx
import sys
from collections import Counter

import duckdb

REPO = os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-merge")
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/fase2")
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/l1")
import l1_2_baselines as L2M                                               # noqa: E402
from n075_poblacion import DB, poblacion, pronosticos                      # noqa: E402
from l1_2_baselines import construye, label_av, observaciones_c, tasof     # noqa: E402
from l1_5_calibracion import EPS, SEMILLA, NBOOT, brier_ev                 # noqa: E402

ST, DSV = "EGLC", "markets_v2"
UNIF = 10 / 121


def clip(p):
    return min(max(p, EPS), 1.0 - EPS)


def brier_vec(p, y):
    return stx.mean([(clip(a) - c) ** 2 for a, c in zip(p, y)])


def orden(ev):
    """Indices de las bandas, de FRIO a CALIENTE."""
    return sorted(range(ev["n_bandas"]),
                  key=lambda i: (-1e9 if ev["bandas"][i][0] is None else ev["bandas"][i][0]))


def pos_ganadora(ev):
    """Posicion de la ganadora relativa al CENTRO, en unidades de banda."""
    idx = orden(ev)
    k = next(i for i, b in enumerate(ev["bandas"]) if b[2])
    return idx.index(k) - ev["n_bandas"] // 2


def S1(ev):
    """Uniforme sobre las bandas CERRADAS. La anchura la fija la escalera."""
    n = ev["n_bandas"]
    cerradas = [i for i, b in enumerate(ev["bandas"]) if b[0] is not None and b[1] is not None]
    p = [0.0] * n
    for i in cerradas:
        p[i] = 1.0 / len(cerradas)
    return p


def S2(ev):
    n = ev["n_bandas"]
    return [1.0 / n] * n


def S3(ev, posiciones):
    """POSICION EMPIRICA. `posiciones` = historial disponible en t_asof.

    Las posiciones que caen fuera de la escalera del test se acumulan en la banda
    abierta correspondiente: es exactamente lo que una banda abierta significa.
    """
    n = ev["n_bandas"]; idx = orden(ev); c = n // 2
    p = [0.0] * n
    for r in posiciones:
        j = max(0, min(n - 1, c + r))
        p[idx[j]] += 1.0
    return [v / len(posiciones) for v in p]


def main():
    con = duckdb.connect(DB, read_only=True); con.execute("SET TimeZone='UTC'")
    obs, zona = observaciones_c(con, ST)
    FC = pronosticos(con, ST); pob, _, _, _ = poblacion(con, DSV, ST)
    rng = random.Random(SEMILLA)

    def ic(v, n=NBOOT):
        r = sorted(stx.mean(rng.choices(v, k=len(v))) for _ in range(n))
        return r[int(.025 * n)], r[int(.975 * n)]

    print("=" * 100)
    print("FASE A — BENCHMARK ESTRUCTURAL COMPLETO · EGLC · escalera 11")
    print("=" * 100)

    for lead in (24, 9):
        f = construye(con, pob, obs, FC, zona, lead)
        print(f"\n{'=' * 100}\nLEAD {lead} h · {len(f)} eventos\n{'=' * 100}")

        res = {"S1": [], "S2": [], "S3": [], "B4": []}
        n_hist = []
        for x in f:
            ev = pob[x["td"]]
            t = tasof(x["td"], lead)
            #: HISTORIAL EX-ANTE: eventos con etiqueta disponible en t_asof, sin el propio
            hist = [pos_ganadora(pob[d]) for d in sorted(pob)
                    if d < x["td"] and label_av(d, zona) <= t]
            n_hist.append(len(hist))
            res["S1"].append(brier_vec(S1(ev), x["y"]))
            res["S2"].append(brier_vec(S2(ev), x["y"]))
            res["S3"].append(brier_vec(S3(ev, hist), x["y"]) if hist else float("nan"))
            res["B4"].append(brier_ev(x, "B4_fc_prob"))
        assert not any(math.isnan(v) for v in res["S3"])
        print(f"  historial ex-ante para S3: min {min(n_hist)} · mediana "
              f"{stx.median(n_hist):.0f} · max {max(n_hist)} eventos")

        print(f"\n  {'benchmark':22s} {'Brier':>9s} {'vs uniforme':>12s}")
        for k in ("S2", "S1", "S3", "B4"):
            nom = {"S2": "S2 uniforme (control)", "S1": "S1 interior",
                   "S3": "S3 posicion empirica", "B4": "B4 (el modelo)"}[k]
            print(f"  {nom:22s} {stx.mean(res[k]):9.5f} {stx.mean(res[k])-UNIF:+12.5f}")

        print(f"\n  --- LA COMPARACION DE REGISTRO ---")
        for k in ("S2", "S1", "S3"):
            d = [a - b for a, b in zip(res["B4"], res[k])]
            lo, hi = ic(d)
            v = ("B4 MEJOR" if hi < 0 else "B4 PEOR" if lo > 0 else "IC INCLUYE EL CERO")
            marca = "   <-- PRIMARIO" if k == "S3" else ""
            print(f"      B4 - {k:2s}  {stx.mean(d):+9.5f}  IC95 [{lo:+.5f}, {hi:+.5f}]  {v}{marca}")
            if k == "S3":
                gana = sum(1 for v_ in d if v_ < 0)
                sd = stx.pstdev(d); mde = 2.8 * sd / math.sqrt(len(d))
                print(f"              gana en {gana}/{len(d)} eventos · sd {sd:.5f} · "
                      f"MDE(80%) {mde:.5f} · razon {abs(stx.mean(d))/mde:.2f}")

        # --------- RED-TEAM 1: ¿que sabe la escalera por si sola?
        print(f"\n  --- RED-TEAM 1 · ¿cuanta informacion lleva la escalera SOLA? ---")
        pos = [pos_ganadora(pob[x["td"]]) for x in f]
        print(f"      distribucion de la posicion de la ganadora: {dict(sorted(Counter(pos).items()))}")
        print(f"      |desviacion| media {stx.mean(abs(v) for v in pos):.2f} bandas "
              f"(uniforme daria {sum(abs(i-5) for i in range(11))/11:.2f})")
        print(f"      entropia de la posicion empirica: "
              f"{-sum((c/len(pos))*math.log(c/len(pos)) for c in Counter(pos).values()):.4f}"
              f"  (uniforme sobre 11: {math.log(11):.4f})")

        # --------- RED-TEAM 3: minimo de entrenamiento
        print(f"\n  --- RED-TEAM 3 · robustez de B4-S3 al minimo de entrenamiento ---")
        orig = L2M.MIN_TRAIN
        for mt in (20, 30, 40, 50):
            L2M.MIN_TRAIN = mt
            g = construye(con, pob, obs, FC, zona, lead)
            d = []
            for x in g:
                ev = pob[x["td"]]; t = tasof(x["td"], lead)
                hist = [pos_ganadora(pob[dd]) for dd in sorted(pob)
                        if dd < x["td"] and label_av(dd, zona) <= t]
                d.append(brier_ev(x, "B4_fc_prob") - brier_vec(S3(ev, hist), x["y"]))
            lo, hi = ic(d, 4000)
            print(f"      MIN_TRAIN {mt:2d}  n={len(g):3d}  {stx.mean(d):+9.5f}  "
                  f"[{lo:+.5f}, {hi:+.5f}]  {'excluye el cero' if hi < 0 else 'INCLUYE EL CERO'}")
        L2M.MIN_TRAIN = orig

        # --------- RED-TEAM 4: influencia
        print(f"\n  --- RED-TEAM 4 · influencia sobre B4-S3 ---")
        d = [a - b for a, b in zip(res["B4"], res["S3"])]
        ordn = sorted(range(len(d)), key=lambda i: d[i])
        for k in (0, 5, 10, 20):
            resto = [d[i] for i in ordn[k:]]
            lo, hi = ic(resto, 4000)
            print(f"      quitando los {k:2d} mas favorables: n={len(resto):3d}  "
                  f"{stx.mean(resto):+9.5f}  [{lo:+.5f}, {hi:+.5f}]  "
                  f"{'sigue' if hi < 0 else 'YA NO'}")
        print(f"      mediana {stx.median(d):+.5f} · media {stx.mean(d):+.5f}")

    # --------- RED-TEAM 2: no-fuga de S3
    print(f"\n{'=' * 100}\nRED-TEAM 2 · ¿S3 tiene fuga del futuro?\n{'=' * 100}")
    lead = 24
    f = construye(con, pob, obs, FC, zona, lead)
    corte = sorted(x["td"] for x in f)[len(f) // 2]
    def s3_de(x, filtro_extra=None):
        ev = pob[x["td"]]; t = tasof(x["td"], lead)
        hist = [pos_ganadora(pob[d]) for d in sorted(pob)
                if d < x["td"] and label_av(d, zona) <= t and (filtro_extra is None or filtro_extra(d))]
        return S3(ev, hist) if hist else None
    antes = [x for x in f if x["td"] < corte]
    a1 = [s3_de(x) for x in antes]
    a2 = [s3_de(x, lambda d: d < corte) for x in antes]     # prohibir TODO lo posterior al corte
    ig = sum(1 for p, q in zip(a1, a2) if p == q)
    print(f"  eventos anteriores al corte {corte}: {len(antes)}")
    print(f"  S3 identico prohibiendo ademas todo lo posterior al corte: {ig}/{len(antes)}")
    print(f"  -> {'NO hay fuga: el historial ya estaba limitado a t_asof' if ig == len(antes) else 'HAY FUGA'}")
    con.close()


if __name__ == "__main__":
    main()
