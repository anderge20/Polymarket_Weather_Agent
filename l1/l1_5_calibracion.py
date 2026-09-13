#!/usr/bin/env python3
"""LEVEL 1 · L1.5 — CALIBRACION + RANKING. Ejecuta `LOCK_L1_5.md`, espejado antes.

NO consulta precios, NO calcula EV ni PnL, NO define entradas/salidas, NO busca umbrales
ni bandas optimas, NO optimiza stake, NO analiza liquidez, NO simula ejecucion, NO elige
ciudades, NO amplia el dataset, NO toca produccion, NO activa nada.
NO emite "hay edge" ni "no hay edge".
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
from l1_2_baselines import MODELOS, construye, observaciones_c             # noqa: E402

ST, DSV, EPS, SEMILLA, NBOOT = "EGLC", "markets_v2", 1e-6, 20260913, 10000
BINS = [0, .05, .1, .2, .3, .5, 1.01]          # predefinidos en LOCK_L1_4
UNIF = 10 / 121


def clip(p):
    return min(max(p, EPS), 1.0 - EPS)


def logit(p):
    p = clip(p)
    return math.log(p / (1 - p))


def brier_ev(x, m):
    return stx.mean([(clip(a) - c) ** 2 for a, c in zip(x["p"][m], x["y"])])


def ll_ev(x, m):
    return stx.mean([-(c * math.log(clip(a)) + (1 - c) * math.log(1 - clip(a)))
                     for a, c in zip(x["p"][m], x["y"])])


def rangos(x, m):
    """Rango de la ganadora (1 = mejor, empates con rango medio) y top-k."""
    p, y = x["p"][m], x["y"]
    k = y.index(1.0)
    may = sum(1 for a in p if a > p[k]); ig = sum(1 for a in p if a == p[k])
    r = may + (ig + 1) / 2
    return r, [1.0 if r <= t else 0.0 for t in (1, 2, 3)]


def logistica(pares, iters=60):
    """y ~ logit^-1(a + b·logit(p)) por Newton. Devuelve (intercepto, pendiente)."""
    #: SIGMOIDE NUMERICAMENTE ESTABLE y predictor lineal acotado. La primera version
    #: hacia `math.exp(-(a+b*z))` directo y reventaba con OverflowError sobre B0, cuyos
    #: logits llegan a ±13,8 por el recorte: con pendientes intermedias el exponente se
    #: sale del rango de un float. El defecto era del ajuste, no de los datos.
    def _sig(t):
        t = max(-30.0, min(30.0, t))
        return 0.5 * (1.0 + math.tanh(t / 2.0))

    a, b = 0.0, 1.0
    for _ in range(iters):
        g = [0.0, 0.0]; H = [[1e-9, 0.0], [0.0, 1e-9]]
        for z, y in pares:
            mu = _sig(a + b * z)
            w = max(mu * (1 - mu), 1e-12)
            r = y - mu
            g[0] += r; g[1] += r * z
            H[0][0] += w; H[0][1] += w * z; H[1][0] += w * z; H[1][1] += w * z * z
        det = H[0][0] * H[1][1] - H[0][1] * H[1][0]
        if abs(det) < 1e-14:
            break
        da = (H[1][1] * g[0] - H[0][1] * g[1]) / det
        db = (-H[1][0] * g[0] + H[0][0] * g[1]) / det
        paso = max(abs(da), abs(db))
        if paso > 2.0:                       # amortigua saltos de Newton en datos separables
            da, db = da * 2.0 / paso, db * 2.0 / paso
        a += da; b += db
        if abs(da) + abs(db) < 1e-10:
            break
    return a, b


def boot_ev(valores_por_evento, rng, f=stx.mean):
    n = len(valores_por_evento)
    r = sorted(f(rng.choices(valores_por_evento, k=n)) for _ in range(NBOOT))
    return r[int(.025 * NBOOT)], r[int(.975 * NBOOT)]


def main():
    con = duckdb.connect(DB, read_only=True)
    con.execute("SET TimeZone='UTC'")
    obs, zona = observaciones_c(con, ST)
    FC = pronosticos(con, ST)
    pob, _, _, _ = poblacion(con, DSV, ST)
    rng = random.Random(SEMILLA)

    print("=" * 104)
    print("L1.5 — CALIBRACION + RANKING · escalera 11 · unidad de inferencia = EVENTO")
    print("=" * 104)

    datos = {}
    for lead in (24, 9):
        f = construye(con, pob, obs, FC, zona, lead)
        assert {x["n"] for x in f} == {11}
        datos[lead] = f

    # ---------------------------------------------------------------- TABLA GENERAL
    print(f"\n{'-' * 104}\nTABLA GENERAL  (LogLoss en cursiva conceptual = NO interpretable "
          f"para B1/B2/B3)\n{'-' * 104}")
    print(f"  {'model':14s} {'lead':>4s} {'Brier':>8s} {'LogLoss':>8s} {'entropia':>9s} "
          f"{'sharp':>7s} {'top1':>6s} {'top2':>6s} {'top3':>6s} {'rango gan':>10s}")
    tabla = {}
    for lead in (24, 9):
        f = datos[lead]
        for m in MODELOS:
            b = [brier_ev(x, m) for x in f]
            l = [ll_ev(x, m) for x in f]
            rr = [rangos(x, m) for x in f]
            ent = stx.mean(-sum(a * math.log(a) for a in x["p"][m] if a > 0) for x in f)
            sh = stx.mean(sum(a * a for a in x["p"][m]) for x in f)
            t = [stx.mean(v[1][i] for v in rr) for i in range(3)]
            rg = stx.mean(v[0] for v in rr)
            tabla[(m, lead)] = dict(brier=stx.mean(b), ll=stx.mean(l), ent=ent, sh=sh,
                                    t1=t[0], t2=t[1], t3=t[2], rango=rg, b_ev=b)
            marca = "" if m in ("B0_clima", "B4_fc_prob") else "  *LL no interpretable"
            print(f"  {m:14s} {lead:4d} {stx.mean(b):8.5f} {stx.mean(l):8.5f} {ent:9.4f} "
                  f"{sh:7.4f} {t[0]:6.3f} {t[1]:6.3f} {t[2]:6.3f} {rg:10.3f}{marca}")
        print(f"  {'uniforme 1/11':14s} {lead:4d} {UNIF:8.5f} {0.30464:8.5f} {math.log(11):9.4f} "
              f"{1/11:7.4f} {1/11:6.3f} {2/11:6.3f} {3/11:6.3f} {6.0:10.3f}   control estructural")

    # ---------------------------------------------------------------- CALIBRACION
    print(f"\n{'-' * 104}\nCURVA DE FIABILIDAD  (sobre CONTRATOS: forma, no inferencia)\n{'-' * 104}")
    for lead in (24, 9):
        for m in ("B4_fc_prob", "B0_clima"):
            print(f"\n  {m} · lead {lead}")
            for i in range(len(BINS) - 1):
                s = [(a, c) for x in datos[lead] for a, c in zip(x["p"][m], x["y"])
                     if BINS[i] <= a < BINS[i + 1]]
                if not s:
                    continue
                pr = stx.mean(a for a, _ in s); ob = stx.mean(c for _, c in s)
                print(f"    [{BINS[i]:.2f},{BINS[i+1]:.2f})  n={len(s):5d}  predicho {pr:.4f}  "
                      f"observado {ob:.4f}  desvio {ob-pr:+.4f}"
                      f"  {'sobre-confianza' if ob < pr else 'infra-confianza'}")

    print(f"\n{'-' * 104}\nINTERCEPTO Y PENDIENTE  (DIAGNOSTICO DESCRIPTIVO, no predefinido)\n"
          f"perfecto = intercepto 0, pendiente 1 · IC95 bootstrap CLUSTERIZADO POR EVENTO\n{'-' * 104}")
    for lead in (24, 9):
        for m in ("B4_fc_prob", "B0_clima"):
            for etq, filtro in (("todos", lambda a: True), ("solo p>0", lambda a: a > 0)):
                porev = [[(logit(a), c) for a, c in zip(x["p"][m], x["y"]) if filtro(a)]
                         for x in datos[lead]]
                porev = [v for v in porev if v]
                a0, b0 = logistica([z for v in porev for z in v])
                muestras = []
                for _ in range(400):          # 400 remuestreos: Newton por remuestreo
                    sel = rng.choices(porev, k=len(porev))
                    try:
                        muestras.append(logistica([z for v in sel for z in v], iters=25))
                    except (OverflowError, ZeroDivisionError):
                        pass
                ia = sorted(x[0] for x in muestras); ib = sorted(x[1] for x in muestras)
                q = lambda v, p: v[int(p * (len(v) - 1))]
                print(f"  {m:14s} lead {lead:2d} {etq:9s}  intercepto {a0:+7.3f} "
                      f"[{q(ia,.025):+7.3f},{q(ia,.975):+7.3f}]   pendiente {b0:+6.3f} "
                      f"[{q(ib,.025):+6.3f},{q(ib,.975):+6.3f}]")

    # ---------------------------------------------------------------- EXTREMOS
    print(f"\n{'-' * 104}\nPROBABILIDADES EXTREMAS  (DIAGNOSTICO DESCRIPTIVO)\n{'-' * 104}")
    for lead in (24, 9):
        for m in MODELOS:
            f = datos[lead]
            tot = sum(len(x["p"][m]) for x in f)
            z = sum(1 for x in f for a in x["p"][m] if a == 0.0)
            u = sum(1 for x in f for a in x["p"][m] if a == 1.0)
            alto = sum(1 for x in f for a in x["p"][m] if a > 0.5)
            fall0 = sum(1 for x in f if x["p"][m][x["y"].index(1.0)] == 0.0)
            print(f"  {m:14s} lead {lead:2d}  p=0 {z:5d}/{tot} ({100*z/tot:4.1f} %)  "
                  f"p=1 {u:4d}  p>0,5 {alto:4d}  "
                  f"EVENTOS con la GANADORA en p=0: {fall0:3d}/{len(f)} ({100*fall0/len(f):4.1f} %)")
    con.close()


if __name__ == "__main__":
    main()
