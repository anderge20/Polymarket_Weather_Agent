#!/usr/bin/env python3
"""FASE C · SCORING — la replica ex-ante en RKSI. Se ejecuta DESPUES de los gates.

NADA se reimplementa. `S3`, `brier_vec`, `orden`, `pos_ganadora` se importan de
`faseA_benchmark`; `construye`, `tasof`, `label_av`, `MIN_TRAIN` y los cinco modelos de
`l1_2_baselines`; `brier_ev`, `EPS`, `SEMILLA`, `NBOOT` de `l1_5_calibracion`. Lo unico
que cambia respecto de Londres son TRES literales: la estacion, la version del dataset y
la ventana -- y la version es una clausula WHERE cuya equivalencia ya quedo demostrada
sobre EGLC en `faseC_datos.equivalencia()`.

§15: una vez empezado esto no se detiene por "parece negativo", no se cambia ventana, ni
MIN_TRAIN, ni modelo, ni escalera, ni ciudad, ni lead, ni datos.
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/fase2")
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/l1")
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/postl1/A_benchmark_estructural")
REPO = os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-merge")
sys.path.insert(0, os.path.join(REPO, "src"))
import faseC_datos as D                                                    # noqa: E402
import l1_2_baselines as L2M                                              # noqa: E402
import n075_poblacion as POB                                              # noqa: E402
from l1_2_baselines import construye, label_av, tasof                     # noqa: E402
from l1_5_calibracion import EPS, NBOOT, SEMILLA, brier_ev                # noqa: E402
from faseA_benchmark import S1, S2, S3, brier_vec, orden, pos_ganadora, UNIF  # noqa: E402

ICAO, DSV_MK = "RKSI", "markets_v2"
D0, D1 = dt.date(2026, 5, 21), dt.date(2026, 8, 23)
#: Londres, para el §20. NO se mira hasta que RKSI este cerrado; se imprime al final.
LONDRES = {24: -0.00614, 9: -0.01181}


def main() -> int:
    con = duckdb.connect(D.DB, read_only=True)
    con.execute("SET TimeZone='UTC'")
    POB.exige_celsius(con, ICAO, DSV_MK)
    obs, zona = D.observaciones_c(con, ICAO, D.DSV_REPLICA)
    FC = D.pronosticos(con, ICAO, D.DSV_REPLICA)
    pob, _, _, _ = POB.poblacion(con, DSV_MK, ICAO)
    rng = random.Random(SEMILLA)

    def ic(v, n=NBOOT):
        """Bootstrap CLUSTERIZADO POR EVENTO: cada v[i] YA es el Brier de un evento."""
        r = sorted(stx.mean(rng.choices(v, k=len(v))) for _ in range(n))
        return r[int(.025 * n)], r[int(.975 * n)]

    print("=" * 100)
    print(f"FASE C · REPLICA EX-ANTE · {ICAO} · {zona} · ventana {D0} -> {D1}")
    print(f"   dataset {D.DSV_REPLICA} · semilla {SEMILLA} · bootstrap {NBOOT} · "
          f"MIN_TRAIN {L2M.MIN_TRAIN} · eps {EPS}")
    print("=" * 100)

    resumen = {}
    for lead in (24, 9):
        f = construye(con, pob, obs, FC, zona, lead)
        ns = Counter(x["n"] for x in f)
        print(f"\n{'=' * 100}\nLEAD {lead} h · {len(f)} eventos · escaleras {dict(sorted(ns.items()))}")
        print("=" * 100)
        assert set(ns) == {11}, f"escaleras mezcladas: {dict(ns)} — A-280 prohibe agregar"

        res = {"S1": [], "S2": [], "S3": [], "B4": [], "B0": []}
        n_hist = []
        for x in f:
            ev = pob[x["td"]]
            t = tasof(x["td"], lead)
            hist = [pos_ganadora(pob[d]) for d in sorted(pob)
                    if d < x["td"] and label_av(d, zona) <= t]
            n_hist.append(len(hist))
            res["S1"].append(brier_vec(S1(ev), x["y"]))
            res["S2"].append(brier_vec(S2(ev), x["y"]))
            res["S3"].append(brier_vec(S3(ev, hist), x["y"]) if hist else float("nan"))
            res["B4"].append(brier_ev(x, "B4_fc_prob"))
            res["B0"].append(brier_ev(x, "B0_clima"))
        assert not any(math.isnan(v) for v in res["S3"])
        print(f"  historial ex-ante para S3: min {min(n_hist)} · mediana "
              f"{stx.median(n_hist):.0f} · max {max(n_hist)} eventos")

        print(f"\n  {'serie':24s} {'Brier/evento':>13s} {'vs uniforme':>13s}")
        for k in ("S2", "S1", "S3", "B0", "B4"):
            nom = {"S2": "S2 uniforme (control)", "S1": "S1 interior",
                   "S3": "S3 posicion empirica", "B0": "B0 climatologia",
                   "B4": "B4 (el modelo)"}[k]
            print(f"  {nom:24s} {stx.mean(res[k]):13.5f} {stx.mean(res[k]) - UNIF:+13.5f}")

        print(f"\n  --- §14 · LAS TRES COMPARACIONES DE REGISTRO ---")
        fila = {}
        for k, etq in (("S3", "B4 - S3        "), ("S2", "B4 - uniforme  "), ("B0", "B4 - B0        ")):
            d = [a - b for a, b in zip(res["B4"], res[k])]
            lo, hi = ic(d)
            v = "B4 MEJOR" if hi < 0 else "B4 PEOR" if lo > 0 else "IC INCLUYE EL CERO"
            print(f"      {etq} {stx.mean(d):+9.5f}  IC95 [{lo:+.5f}, {hi:+.5f}]  {v}"
                  + ("   <-- PRIMARIO" if k == "S3" else ""))
            fila[k] = (stx.mean(d), lo, hi, v)
        d3 = [a - b for a, b in zip(res["B4"], res["S3"])]
        gana = sum(1 for v_ in d3 if v_ < 0)
        sd = stx.pstdev(d3)
        mde = 2.8 * sd / math.sqrt(len(d3))
        razon = abs(stx.mean(d3)) / mde
        print(f"\n  --- §19 · POTENCIA ---")
        print(f"      gana en {gana}/{len(d3)} eventos · sd {sd:.5f} · "
              f"MDE(80%) {mde:.5f} · efecto/MDE {razon:.2f}")
        resumen[lead] = {"n": len(f), "fila": fila, "gana": gana, "mde": mde,
                         "razon": razon, "d3": d3, "res": res, "f": f}

        # ---------------- §17 ROBUSTEZ · solo pruebas PREDEFINIDAS (las de la Fase A)
        print(f"\n  --- §17.1 · informacion que lleva la escalera SOLA (red-team 1) ---")
        pos = [pos_ganadora(pob[x["td"]]) for x in f]
        print(f"      posicion de la ganadora: {dict(sorted(Counter(pos).items()))}")
        print(f"      |desviacion| media {stx.mean(abs(v) for v in pos):.2f} bandas "
              f"(uniforme daria {sum(abs(i - 5) for i in range(11)) / 11:.2f})")
        print(f"      entropia empirica "
              f"{-sum((c / len(pos)) * math.log(c / len(pos)) for c in Counter(pos).values()):.4f}"
              f"  (uniforme sobre 11: {math.log(11):.4f})")

        print(f"\n  --- §17.2 · sensibilidad a MIN_TRAIN (red-team 3) ---")
        orig = L2M.MIN_TRAIN
        for mt in (20, 30, 40, 50):
            L2M.MIN_TRAIN = mt
            g = construye(con, pob, obs, FC, zona, lead)
            dd = []
            for x in g:
                ev = pob[x["td"]]; t = tasof(x["td"], lead)
                h = [pos_ganadora(pob[q]) for q in sorted(pob)
                     if q < x["td"] and label_av(q, zona) <= t]
                dd.append(brier_ev(x, "B4_fc_prob") - brier_vec(S3(ev, h), x["y"]))
            lo, hi = ic(dd, 4000)
            print(f"      MIN_TRAIN {mt:2d}  n={len(g):3d}  {stx.mean(dd):+9.5f}  "
                  f"[{lo:+.5f}, {hi:+.5f}]  {'excluye el cero' if lo * hi > 0 else 'INCLUYE EL CERO'}")
        L2M.MIN_TRAIN = orig

        print(f"\n  --- §17.3 · influencia de eventos (red-team 4) ---")
        ordn = sorted(range(len(d3)), key=lambda i: d3[i])
        for k in (0, 5, 10, 20):
            resto = [d3[i] for i in ordn[k:]]
            lo, hi = ic(resto, 4000)
            print(f"      quitando los {k:2d} mas favorables: n={len(resto):3d}  "
                  f"{stx.mean(resto):+9.5f}  [{lo:+.5f}, {hi:+.5f}]  "
                  f"{'sigue excluyendo' if hi < 0 else 'YA NO'}")
        print(f"      mediana {stx.median(d3):+.5f} · media {stx.mean(d3):+.5f}")

        print(f"\n  --- §17.4 · estabilidad temporal (mitades de la ventana) ---")
        tds = sorted(x["td"] for x in f)
        corte = tds[len(tds) // 2]
        for etq, sel in (("primera mitad", lambda d: d < corte), ("segunda mitad", lambda d: d >= corte)):
            sub = [d3[i] for i, x in enumerate(f) if sel(x["td"])]
            lo, hi = ic(sub, 4000)
            print(f"      {etq} ({sub and len(sub) or 0:3d} eventos, corte {corte}): "
                  f"{stx.mean(sub):+9.5f}  [{lo:+.5f}, {hi:+.5f}]")

    # ---------------- §17.5 no-fuga de S3 (red-team 2), identico a la Fase A
    print(f"\n{'=' * 100}\n§17.5 · ¿S3 tiene fuga del futuro?\n{'=' * 100}")
    lead = 24
    f = construye(con, pob, obs, FC, zona, lead)
    corte = sorted(x["td"] for x in f)[len(f) // 2]

    def s3_de(x, extra=None):
        ev = pob[x["td"]]; t = tasof(x["td"], lead)
        h = [pos_ganadora(pob[d]) for d in sorted(pob)
             if d < x["td"] and label_av(d, zona) <= t and (extra is None or extra(d))]
        return S3(ev, h) if h else None

    antes = [x for x in f if x["td"] < corte]
    ig = sum(1 for x in antes if s3_de(x) == s3_de(x, lambda d: d < corte))
    print(f"  eventos anteriores al corte {corte}: {len(antes)}")
    print(f"  S3 identico prohibiendo ademas todo lo posterior: {ig}/{len(antes)}")
    print(f"  -> {'NO hay fuga' if ig == len(antes) else 'HAY FUGA'}")

    # ---------------- §17.6 missingness y disponibilidad
    print(f"\n{'=' * 100}\n§17.6 · missingness y disponibilidad\n{'=' * 100}")
    print(f"  observacion: 0 de 95 dias sin observacion en la ventana")
    print(f"  pronostico : 1 pasada ausente del archivo (2026-06-10T18:00Z, dwd_icon).")
    degradado = [td for (td, l), (av, _) in FC.items() if l == 9
                 and (dt.datetime.combine(td, dt.time(12), dt.timezone.utc)
                      - dt.timedelta(hours=9) - av).total_seconds() / 3600 > 12]
    print(f"    el lector congelado retrocede solo a la pasada anterior: "
          f"{len(degradado)} fechas con lead 9 servidas por una pasada mas vieja "
          f"{sorted(degradado)}")
    for lead in (24, 9):
        sub = [resumen[lead]["d3"][i] for i, x in enumerate(resumen[lead]["f"])
               if x["td"] not in degradado]
        lo, hi = ic(sub, 4000)
        print(f"    lead {lead:2d} quitando esas fechas: n={len(sub)} "
              f"{stx.mean(sub):+9.5f} [{lo:+.5f}, {hi:+.5f}]")

    # ---------------- §20 comparacion con Londres, SOLO al final
    print(f"\n{'=' * 100}\n§20 · COMPARACION CON LONDRES (solo ahora, con RKSI ya cerrado)\n{'=' * 100}")
    print(f"  {'lead':>5s} {'Londres B4-S3':>15s} {'RKSI B4-S3':>13s} {'IC95 RKSI':>26s} "
          f"{'n':>4s} {'efecto/MDE':>11s}")
    for lead in (24, 9):
        m, lo, hi, _ = resumen[lead]["fila"]["S3"]
        print(f"  {lead:5d} {LONDRES[lead]:+15.5f} {m:+13.5f} "
              f"  [{lo:+.5f}, {hi:+.5f}] {resumen[lead]['n']:4d} "
              f"{resumen[lead]['razon']:11.2f}")
        print(f"        direccion: {'MISMA' if m * LONDRES[lead] > 0 else 'OPUESTA'} · "
              f"magnitud RKSI/Londres {m / LONDRES[lead]:+.2f}x")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
