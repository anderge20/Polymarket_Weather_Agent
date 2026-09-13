#!/usr/bin/env python3
"""LEVEL 1 · L1.6 — INFERENCE. Ejecuta `LOCK_L1_6.md`, espejado antes.

No busca precios, EV, PnL, umbrales, estrategias ni ciudades. No toca produccion.
NO emite el veredicto de Level 1: eso es L1.8.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import math
import os
import random
import statistics as stx
import sys
from collections import defaultdict

import duckdb

REPO = os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-merge")
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/fase2")
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/l1")
from n075_poblacion import DB, poblacion, pronosticos                      # noqa: E402
from l1_2_baselines import (MODELOS, MIN_TRAIN, VENT_CLIMA, construye,     # noqa: E402
                            label_av, observaciones_c, probabilidades, tasof)
from l1_5_calibracion import UNIF, EPS, SEMILLA, NBOOT, brier_ev           # noqa: E402

DESPLAZAMIENTOS = (-7, -3, -1, 1, 3, 7)      # DECLARADOS en el lock
NPERM = 1000                                  # DECLARADO en el lock
CORTE = dt.date(2026, 6, 23)                  # pre-registrado en LOCK_L1_4


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def ic(v, rng, n=NBOOT):
    r = sorted(stx.mean(rng.choices(v, k=len(v))) for _ in range(n))
    return r[int(.025 * n)], r[int(.975 * n)]


def brier_vec(p, y):
    return stx.mean([(min(max(a, EPS), 1 - EPS) - c) ** 2 for a, c in zip(p, y)])


def main():
    print("=" * 100)
    print("INTEGRIDAD DEL LOCK, verificada antes de nada")
    print("=" * 100)
    base = "/Users/mariaaleu/pmw-e2/l1"
    esp = "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-research/l1"
    for f in ("PREREG_LEVEL1.md", "LOCK_L1_4.md", "LOCK_L1_5.md", "LOCK_L1_6.md",
              "l1_2_baselines.py", "l1_4_walkforward.py"):
        a, b = sha(os.path.join(base, f)), sha(os.path.join(esp, f))
        print(f"  {'OK ' if a == b else '!! '} {f:26s} {a[:16]}…")
        assert a == b, f

    con = duckdb.connect(DB, read_only=True); con.execute("SET TimeZone='UTC'")
    obs, zona = observaciones_c(con, "EGLC")
    FC = pronosticos(con, "EGLC"); pob, _, _, _ = poblacion(con, "markets_v2", "EGLC")
    rng = random.Random(SEMILLA)

    for lead in (24, 9):
        f = construye(con, pob, obs, FC, zona, lead)
        d0 = [brier_ev(x, "B4_fc_prob") - brier_ev(x, "B0_clima") for x in f]
        du = [brier_ev(x, "B4_fc_prob") - UNIF for x in f]
        print(f"\n{'=' * 100}\nLEAD {lead} h · {len(f)} eventos (clusters)\n{'=' * 100}")
        lo, hi = ic(d0, rng); print(f"  B4 - B0        {stx.mean(d0):+9.5f}  IC95 [{lo:+.5f}, {hi:+.5f}]")
        lo, hi = ic(du, rng); print(f"  B4 - uniforme  {stx.mean(du):+9.5f}  IC95 [{lo:+.5f}, {hi:+.5f}]")

        # ---------------------------------------------------- PLACEBO A
        print(f"\n  --- PLACEBO A · desalineamiento temporal (6 desplazamientos DECLARADOS) ---")
        print(f"      se empareja el pronostico del dia t con el evento del dia t+k")
        print(f"      {'k':>4s} {'n':>4s} {'B4-uniforme':>13s} {'IC95':>26s}   veredicto")
        for k in DESPLAZAMIENTOS:
            filas = []
            for x in f:
                td = x["td"]; orig = td - dt.timedelta(days=k)
                if (orig, lead) not in FC or orig not in obs:
                    continue
                t = tasof(td, lead)
                tr = [(d, obs[d], FC[(d, lead)][1]) for d in sorted(obs)
                      if label_av(d, zona) <= t and (d, lead) in FC]
                if len(tr) < MIN_TRAIN:
                    continue
                p = probabilidades(pob[td], FC[(orig, lead)][1], tr)
                filas.append(brier_vec(p["B4_fc_prob"], x["y"]) - UNIF)
            if len(filas) < 20:
                print(f"      {k:+4d} {len(filas):4d}   (muestra insuficiente)"); continue
            l2, h2 = ic(filas, rng, 4000)
            v = "MEJORA (MAL SIGNO)" if h2 < 0 else ("peor" if l2 > 0 else "IC INCLUYE EL CERO  <- lo esperado")
            print(f"      {k:+4d} {len(filas):4d} {stx.mean(filas):+13.5f}  [{l2:+.5f}, {h2:+.5f}]   {v}")

        # ---------------------------------------------------- PLACEBO B
        print(f"\n  --- PLACEBO B · {NPERM} permutaciones de la ganadora dentro del evento ---")
        rp = random.Random(SEMILLA)
        obsv = stx.mean(du)
        nulos = []
        for _ in range(NPERM):
            v = []
            for x in f:
                k = rp.randrange(x["n"])
                y = [1.0 if i == k else 0.0 for i in range(x["n"])]
                v.append(brier_vec(x["p"]["B4_fc_prob"], y) - UNIF)
            nulos.append(stx.mean(v))
        nulos.sort()
        peor = sum(1 for z in nulos if z <= obsv)
        print(f"      delta OBSERVADO           {obsv:+.5f}")
        print(f"      nulo permutado: media {stx.mean(nulos):+.5f} · "
              f"p2,5 {nulos[int(.025*NPERM)]:+.5f} · p97,5 {nulos[int(.975*NPERM)]:+.5f}")
        print(f"      permutaciones tan buenas o mejores que la observada: {peor}/{NPERM}"
              f"  -> p = {(peor+1)/(NPERM+1):.4f}")

        # ---------------------------------------------------- TEST TEMPORAL
        print(f"\n  --- TEST TEMPORAL · estabilidad entre mitades (corte {CORTE}) ---")
        a = [du[i] for i, x in enumerate(f) if x["td"] < CORTE]
        b = [du[i] for i, x in enumerate(f) if x["td"] >= CORTE]
        la, ha = ic(a, rng, 4000); lb, hb = ic(b, rng, 4000)
        print(f"      1a mitad n={len(a):3d}  {stx.mean(a):+.5f}  IC95 [{la:+.5f}, {ha:+.5f}]")
        print(f"      2a mitad n={len(b):3d}  {stx.mean(b):+.5f}  IC95 [{lb:+.5f}, {hb:+.5f}]")
        dif = []
        for _ in range(4000):
            dif.append(stx.mean(rng.choices(a, k=len(a))) - stx.mean(rng.choices(b, k=len(b))))
        dif.sort()
        l3, h3 = dif[100], dif[3899]
        print(f"      diferencia 1a-2a {stx.mean(a)-stx.mean(b):+.5f}  IC95 [{l3:+.5f}, {h3:+.5f}]"
              f"  {'ESTABLE (incluye el cero)' if l3 <= 0 <= h3 else 'INESTABLE'}")

        # ---------------------------------------------------- POTENCIA
        print(f"\n  --- POTENCIA ---")
        sd = stx.pstdev(du); n = len(du)
        mde = 2.8 * sd / math.sqrt(n)      # 80 % potencia, alfa 0,05 bilateral: (1,96+0,84)
        print(f"      n clusters {n} · sd del delta por evento {sd:.5f}")
        print(f"      efecto minimo detectable (80 %, alfa 0,05) = {mde:.5f}")
        print(f"      efecto observado {abs(obsv):.5f}  -> "
              f"{'DETECTABLE (|obs| > MDE)' if abs(obsv) > mde else 'POR DEBAJO DEL MDE'}")
        print(f"      razon observado/MDE = {abs(obsv)/mde:.2f}")

    # ---------------------------------------------------- CORRELACION ENTRE LEADS
    print(f"\n{'=' * 100}\nCORRELACION ENTRE LEADS — los 191 event x lead NO son 191 clusters\n{'=' * 100}")
    f24 = {x["td"]: brier_ev(x, "B4_fc_prob") - UNIF for x in construye(con, pob, obs, FC, zona, 24)}
    f09 = {x["td"]: brier_ev(x, "B4_fc_prob") - UNIF for x in construye(con, pob, obs, FC, zona, 9)}
    com = sorted(set(f24) & set(f09))
    xs = [f24[d] for d in com]; ys = [f09[d] for d in com]
    mx, my = stx.mean(xs), stx.mean(ys)
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / len(xs)
    r = cov / (stx.pstdev(xs) * stx.pstdev(ys))
    print(f"  eventos con los dos leads: {len(com)}   correlacion de Pearson r = {r:+.3f}")
    n_ef = 2 * len(com) / (1 + r)
    print(f"  tamano efectivo aproximado con dos medidas correlacionadas: {n_ef:.0f} "
          f"(contra {2*len(com)} si fueran independientes)")
    con.close()


if __name__ == "__main__":
    main()
