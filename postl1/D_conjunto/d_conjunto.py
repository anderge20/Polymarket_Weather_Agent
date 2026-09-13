#!/usr/bin/env python3
"""D — ANALISIS CONJUNTO LONDRES + RKSI. Ejecuta `PREREG_ANALISIS_CONJUNTO.md` (bfd7cb0).

Orden obligatorio: primero el GATE DE COMPARABILIDAD (C1..C5), que puede BLOQUEAR; solo
despues el pooling. 0 peticiones a ningun proveedor. Nada se recalcula de B4, S3,
MIN_TRAIN, epsilon ni de las ventanas congeladas.
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

sys.path.insert(0, "/Users/mariaaleu/pmw-e2/fase2")
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/l1")
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/postl1/A_benchmark_estructural")
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/postl1/C_replica")
REPO = os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-merge")
sys.path.insert(0, os.path.join(REPO, "src"))
import faseC_datos as D                                                   # noqa: E402
import n075_poblacion as POB                                             # noqa: E402
from l1_2_baselines import construye, label_av, observaciones_c, tasof   # noqa: E402
from l1_5_calibracion import NBOOT, SEMILLA, brier_ev                    # noqa: E402
from faseA_benchmark import S2, S3, brier_vec, pos_ganadora              # noqa: E402

VENT = (dt.date(2026, 5, 21), dt.date(2026, 8, 23))   # la ventana congelada de RKSI
PUBLICADO = {("EGLC", 24): -0.00605, ("EGLC", 9): -0.01181,
             ("RKSI", 24): -0.00485, ("RKSI", 9): -0.00892}
rng = random.Random(SEMILLA)


def difs(con, st, dsv, lead, ventana=None):
    """Las diferencias B4-S3 por EVENTO. Codigo congelado; solo cambia la estacion."""
    if dsv is None:
        obs, zona = observaciones_c(con, st)
        FC = POB.pronosticos(con, st)
    else:
        obs, zona = D.observaciones_c(con, st, dsv)
        FC = D.pronosticos(con, st, dsv)
    if ventana:
        obs = {d: v for d, v in obs.items() if ventana[0] <= d <= ventana[1]}
    pob, _, _, _ = POB.poblacion(con, "markets_v2", st)
    f = construye(con, pob, obs, FC, zona, lead)
    out, ns, nt, nh = [], Counter(), [], []
    for x in f:
        ev = pob[x["td"]]; t = tasof(x["td"], lead)
        h = [pos_ganadora(pob[q]) for q in sorted(pob) if q < x["td"] and label_av(q, zona) <= t]
        out.append((x["td"], brier_ev(x, "B4_fc_prob") - brier_vec(S3(ev, h), x["y"])))
        ns[x["n"]] += 1; nt.append(x["n_train"]); nh.append(len(h))
    return out, ns, nt, nh


def ic_boot(v, n=NBOOT):
    r = sorted(stx.mean(rng.choices(v, k=len(v))) for _ in range(n))
    return r[int(.025 * n)], r[int(.975 * n)]


def main() -> int:
    con = duckdb.connect(D.DB, read_only=True); con.execute("SET TimeZone='UTC'")
    print("=" * 100)
    print("D · ANALISIS CONJUNTO LONDRES + RKSI · preregistro bfd7cb0 · 0 peticiones")
    print("=" * 100)

    base = {}
    for st, dsv in (("EGLC", None), ("RKSI", D.DSV_REPLICA)):
        for lead in (24, 9):
            d, ns, nt, nh = difs(con, st, dsv, lead)
            base[(st, lead)] = [v for _, v in d]
            m = stx.mean(base[(st, lead)])
            coincide = abs(m - PUBLICADO[(st, lead)]) < 5e-5
            print(f"  {st} lead {lead:2d}: n={len(d):3d}  B4-S3 {m:+.5f}  "
                  f"publicado {PUBLICADO[(st, lead)]:+.5f}  "
                  f"{'REPRODUCE' if coincide else '!! NO REPRODUCE'}  escaleras {dict(ns)}")
            if not coincide:
                print("PARADA: el conjunto no puede partir de numeros que no reproducen.")
                return 1

    # =============================================================== C1
    print(f"\n{'=' * 100}\nC1 · VENTANA EQUIPARADA — Londres recortado a los 95 dias de RKSI\n{'=' * 100}")
    print(f"  C1a (95 dias mas recientes de EGLC) y C1b (calendario de RKSI) COINCIDEN:")
    print(f"  las dos ventanas acaban el 2026-08-23, asi que el recorte es el mismo:")
    print(f"  {VENT[0]} -> {VENT[1]}. Se mide UNA vez y responde a las dos.")
    c1 = {}
    for lead in (24, 9):
        d, ns, nt, nh = difs(con, "EGLC", None, lead, VENT)
        c1[lead] = [v for _, v in d]
        lo, hi = ic_boot(c1[lead], 4000)
        dR, nsR, ntR, nhR = difs(con, "RKSI", D.DSV_REPLICA, lead)
        print(f"\n  lead {lead:2d}")
        print(f"    EGLC completo   n={len(base[('EGLC', lead)]):3d}  "
              f"{stx.mean(base[('EGLC', lead)]):+.5f}")
        print(f"    EGLC recortado  n={len(c1[lead]):3d}  {stx.mean(c1[lead]):+.5f}  "
              f"[{lo:+.5f}, {hi:+.5f}]   n_train mediana {stx.median(nt):.0f} · "
              f"S3 hist mediana {stx.median(nh):.0f}")
        print(f"    RKSI            n={len(base[('RKSI', lead)]):3d}  "
              f"{stx.mean(base[('RKSI', lead)]):+.5f}           "
              f"n_train mediana {stx.median(ntR):.0f} · S3 hist mediana {stx.median(nhR):.0f}")
        if set(ns) != {11}:
            print(f"    !! escaleras {dict(ns)} — C2 BLOQUEA"); return 1
    e_full, e_cut, r_full = (stx.mean(base[("EGLC", 9)]), stx.mean(c1[9]),
                             stx.mean(base[("RKSI", 9)]))
    print(f"\n  LECTURA DE C1 (regla escrita antes, lead 9):")
    if e_cut > 0:
        print("    Londres recortado CAMBIA DE SIGNO -> BLOQUEA el pooling."); return 1
    cerca = abs(e_cut - r_full) < abs(e_full - r_full)
    print(f"    completo {e_full:+.5f} · recortado {e_cut:+.5f} · RKSI {r_full:+.5f}")
    print(f"    -> el recorte {'ACERCA' if cerca else 'NO acerca'} Londres a RKSI: "
          f"|recortado-RKSI| {abs(e_cut - r_full):.5f} vs |completo-RKSI| {abs(e_full - r_full):.5f}")
    print(f"    -> la diferencia entre ciudades es "
          f"{'en buena parte DE VENTANA' if cerca else 'DE CIUDAD, no de ventana'}")

    # =============================================================== C3/C4/C5
    print(f"\n{'=' * 100}\nC3/C4/C5 · lo que NO se puede equiparar y se declara\n{'=' * 100}")
    print("  C3 availability : EGLC -> ICON-D2 (cota TRASLADADA de ICON-GLOBAL, 1 medicion "
          "de dominio)\n                    RKSI -> ICON-GLOBAL (cota DIRECTA, 2 fechas, 2 canales)")
    print("  C4 clima        : maritimo templado vs monzonico continental. NO equiparable.")
    print("  C5 independencia: mismo proveedor (ICON) y misma plataforma (Polymarket). "
          "Comparten modo de fallo.")

    # =============================================================== POOLING
    print(f"\n{'=' * 100}\nESTIMADOR CONJUNTO — primario lead 9\n{'=' * 100}")

    def pool(ds: dict):
        w, num, q = {}, 0.0, 0.0
        for c, v in ds.items():
            se = stx.pstdev(v) / math.sqrt(len(v))
            w[c] = 1.0 / se ** 2
            num += w[c] * stx.mean(v)
        th = num / sum(w.values())
        se = math.sqrt(1.0 / sum(w.values()))
        for c, v in ds.items():
            q += w[c] * (stx.mean(v) - th) ** 2
        i2 = max(0.0, (q - (len(ds) - 1)) / q) * 100 if q > 0 else 0.0
        return th, se, q, i2, w

    def boot_jer(ds: dict, n=NBOOT):
        r = []
        for _ in range(n):
            m = {c: rng.choices(v, k=len(v)) for c, v in ds.items()}
            r.append(pool(m)[0])
        r.sort()
        return r[int(.025 * n)], r[int(.975 * n)]

    for lead, etq in ((9, "PRIMARIO"), (24, "SECUNDARIO EXPLORATORIO — no desbloquea nada")):
        ds = {"EGLC": base[("EGLC", lead)], "RKSI": base[("RKSI", lead)]}
        th, se, q, i2, w = pool(ds)
        lo_a, hi_a = th - 1.96 * se, th + 1.96 * se
        lo_b, hi_b = boot_jer(ds)
        todos = ds["EGLC"] + ds["RKSI"]
        lo_n, hi_n = ic_boot(todos, 4000)
        pq = 1 - _chi1(q)
        print(f"\n  lead {lead:2d} · {etq}")
        print(f"    pesos  EGLC {w['EGLC'] / sum(w.values()):.3f} · "
              f"RKSI {w['RKSI'] / sum(w.values()):.3f}")
        print(f"    analitico (efectos fijos)  theta {th:+.5f}  IC95 [{lo_a:+.5f}, {hi_a:+.5f}]")
        print(f"    bootstrap jerarquico       theta {th:+.5f}  IC95 [{lo_b:+.5f}, {hi_b:+.5f}]  <- manda")
        print(f"    pool ingenuo (control)     media {stx.mean(todos):+.5f}  "
              f"IC95 [{lo_n:+.5f}, {hi_n:+.5f}]  n={len(todos)}")
        print(f"    heterogeneidad  Q {q:.3f} (gl 1, p {pq:.3f})  I2 {i2:.1f}%  "
              f"-> {'AGREGABLE' if pq > 0.05 else 'NO AGREGABLE'}")
        if lead == 9:
            print(f"\n    --- §7 · el pooling pasa las MISMAS pruebas que pasaron las partes ---")
            for frac in (0.05, 0.10, 0.20):
                m = {}
                for c, v in ds.items():
                    k = int(round(frac * len(v)))
                    m[c] = sorted(v)[k:]
                t2, s2, _, _, _ = pool(m)
                l2b, h2b = boot_jer(m, 4000)
                print(f"      quitando el {frac:.0%} mas favorable de cada ciudad: "
                      f"n={sum(len(v) for v in m.values()):3d}  {t2:+.5f}  "
                      f"[{l2b:+.5f}, {h2b:+.5f}]  {'sigue' if h2b < 0 else 'YA NO'}")
            print(f"      una ciudad fuera (k=2, asi que es cada ciudad sola):")
            for c, v in ds.items():
                lo, hi = ic_boot(v, 4000)
                print(f"        solo {c}: n={len(v):3d}  {stx.mean(v):+.5f}  [{lo:+.5f}, {hi:+.5f}]")
    con.close()
    return 0


def _chi1(x):
    """P(X <= x) para chi-cuadrado con 1 gl = erf(sqrt(x/2))."""
    return math.erf(math.sqrt(x / 2.0)) if x > 0 else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
