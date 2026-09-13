#!/usr/bin/env python3
"""LEVEL 1 · L1.5 — RED-TEAM. Intentar demostrar que el resultado de B4 es FALSO.

No consulta precios, no calcula EV ni PnL, no busca umbrales, no toca produccion.
Todo lo de aqui es DIAGNOSTICO DESCRIPTIVO: no modifica ningun modelo ni selecciona nada.
"""
from __future__ import annotations

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
from l1_2_baselines import MODELOS, construye, observaciones_c             # noqa: E402
from l1_5_calibracion import brier_ev, UNIF, EPS, SEMILLA, NBOOT           # noqa: E402


def ic(v, rng, n=NBOOT):
    r = sorted(stx.mean(rng.choices(v, k=len(v))) for _ in range(n))
    return r[int(.025 * n)], r[int(.975 * n)]


def main():
    con = duckdb.connect(DB, read_only=True); con.execute("SET TimeZone='UTC'")
    obs, zona = observaciones_c(con, "EGLC")
    FC = pronosticos(con, "EGLC"); pob, _, _, _ = poblacion(con, "markets_v2", "EGLC")
    rng = random.Random(SEMILLA)
    SEP = "-" * 100

    for lead in (24, 9):
        f = construye(con, pob, obs, FC, zona, lead)
        b4 = [brier_ev(x, "B4_fc_prob") for x in f]
        b0 = [brier_ev(x, "B0_clima") for x in f]
        d_b0 = [a - b for a, b in zip(b4, b0)]
        d_un = [a - UNIF for a in b4]
        fechas = [x["td"] for x in f]

        print(f"\n{'=' * 100}\nLEAD {lead} h · {len(f)} eventos\n{'=' * 100}")
        print(f"  B4 - B0       {stx.mean(d_b0):+9.5f}  IC95 {ic(d_b0, rng)}")
        print(f"  B4 - uniforme {stx.mean(d_un):+9.5f}  IC95 {ic(d_un, rng)}")

        # ---- 1. BLOQUES MENSUALES (descriptivo)
        print(f"\n{SEP}\n1. BLOQUES MENSUALES (descriptivo; NO se selecciona periodo)\n{SEP}")
        por = defaultdict(list)
        for i, td in enumerate(fechas):
            por[td.strftime("%Y-%m")].append(i)
        print(f"  {'mes':9s} {'n':>4s} {'B4':>9s} {'B0':>9s} {'unif':>9s} "
              f"{'B4-B0':>9s} {'B4-unif':>9s}")
        for mes in sorted(por):
            idx = por[mes]
            print(f"  {mes:9s} {len(idx):4d} {stx.mean(b4[i] for i in idx):9.5f} "
                  f"{stx.mean(b0[i] for i in idx):9.5f} {UNIF:9.5f} "
                  f"{stx.mean(d_b0[i] for i in idx):+9.5f} {stx.mean(d_un[i] for i in idx):+9.5f}")
        meses_ok = sum(1 for mes in por if stx.mean(d_un[i] for i in por[mes]) < 0)
        print(f"  -> B4 mejor que el uniforme en {meses_ok} de {len(por)} meses")

        # ---- 2. INFLUENCIA: ¿lo explican unos pocos eventos?
        print(f"\n{SEP}\n2. INFLUENCIA (descriptivo): quitar los k eventos MAS favorables a B4\n{SEP}")
        orden = sorted(range(len(f)), key=lambda i: d_un[i])       # mas negativo = mas favorable
        for k in (0, 1, 3, 5, 10, 20):
            resto = [d_un[i] for i in orden[k:]]
            lo, hi = ic(resto, rng, 2000)
            print(f"  quitando los {k:2d} mas favorables: n={len(resto):3d}  "
                  f"delta {stx.mean(resto):+9.5f}  IC95 [{lo:+.5f}, {hi:+.5f}]  "
                  f"{'sigue MEJOR' if hi < 0 else 'YA NO excluye el cero'}")
        peor = sorted(range(len(f)), key=lambda i: -d_un[i])
        for k in (1, 3, 5):
            resto = [d_un[i] for i in peor[k:]]
            print(f"  quitando los {k:2d} mas DESfavorables: delta {stx.mean(resto):+9.5f}"
                  f"   (simetria: el resultado no vive de la cola mala)")

        # ---- 3. ¿CUANTOS EVENTOS GANAN?
        gana = sum(1 for v in d_un if v < 0); pierde = sum(1 for v in d_un if v > 0)
        print(f"\n{SEP}\n3. REPARTO EVENTO A EVENTO\n{SEP}")
        print(f"  B4 mejor que el uniforme en {gana} eventos · peor en {pierde} · "
              f"igual en {len(d_un)-gana-pierde}")
        print(f"  mediana del delta {stx.median(d_un):+.5f} · media {stx.mean(d_un):+.5f}")
        print(f"  -> si la media fuera de unos pocos casos, mediana y media divergirian")

        # ---- 4. BINNING ALTERNATIVO
        print(f"\n{SEP}\n4. BINNING ALTERNATIVO (red-team del diagnostico de calibracion)\n{SEP}")
        for nombre, bins in (("predefinido", [0, .05, .1, .2, .3, .5, 1.01]),
                             ("deciles fijos", [i / 10 for i in range(11)] + [1.01]),
                             ("grueso", [0, .1, .3, 1.01])):
            s = [(a, c) for x in f for a, c in zip(x["p"]["B4_fc_prob"], x["y"])]
            ece = 0.0
            for i in range(len(bins) - 1):
                sub = [(a, c) for a, c in s if bins[i] <= a < bins[i + 1]]
                if sub:
                    ece += len(sub) / len(s) * abs(stx.mean(c for _, c in sub)
                                                   - stx.mean(a for a, _ in sub))
            print(f"  {nombre:14s} bins={len(bins)-1:2d}   ECE de B4 = {ece:.5f}")
        print("  -> ECE es SECUNDARIA por preinscripcion; se muestra su sensibilidad al binning")

    # ---- 5. LA OBJECION DE FONDO
    print(f"\n{'=' * 100}")
    print("5. LA OBJECION MAS FUERTE CONTRA B4, Y ES ESTRUCTURAL")
    print("=" * 100)
    print("""  B4 asigna a cada banda la FRECUENCIA EMPIRICA de round(f + e) sobre los errores
  del train. Si la distribucion de error es estacionaria, B4 esta calibrado POR
  CONSTRUCCION: es un estimador de frecuencia de la misma cantidad que luego se mide.

  -> que B4 salga bien calibrado NO es evidencia independiente de habilidad predictiva.
     Es evidencia de que la distribucion de error es ESTABLE entre train y test.

  Lo que NO es tautologico, y es donde vive la señal:
     que el pronostico PUNTUAL este centrado cerca de la banda ganadora. Eso es lo que
     hace que la masa caiga donde tiene que caer, y se mide en el ranking (rango medio
     2,34-2,71 contra 6,0 del azar) y en el Brier contra el uniforme.""")
    con.close()


if __name__ == "__main__":
    main()
