#!/usr/bin/env python3
"""LEVEL 1 · L1.2 — BASELINES. Implementacion declarada y verificacion de BUENA FORMA.

NO puntua contra el target. Deliberadamente: puntuar aqui invitaria a retocar las
definiciones despues de ver el resultado, que es justo lo que el orden por etapas evita.
El scoring es L1.4/L1.5.

Las cinco definiciones son las de `PREREG_LEVEL1.md` §7, palabra por palabra, mas la
variante `B4'` declarada ANTES de correr para que no parezca elegida despues.
"""
from __future__ import annotations

import datetime as dt
import math
import os
import statistics as stx
import sys
from collections import Counter

import duckdb

REPO = os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-merge")
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/fase2")
from weather_agent import stations                                        # noqa: E402
from zoneinfo import ZoneInfo                                             # noqa: E402
from n075_poblacion import DB, poblacion, pronosticos                     # noqa: E402

ST, DSV = "EGLC", "markets_v2"
MIN_TRAIN = 20
VENT_CLIMA = 30
#: ENMIENDA DE LA PREINSCRIPCION, L1.2, antes de puntuar NADA contra el target (A-287):
#:   1. el signo. e = obs - fc, E[e] = b > 0 significa que el pronostico va BAJO, asi que
#:      corregirlo es `f + b`. La preinscripcion decia `f - b` y empuja al MISMO lado.
#:   2. `B4'` se RETIRA como modelo distinto: corregir el punto y recentrar los residuos es
#:      `f + b + (e - b) = f + e`, una identidad algebraica. El pronostico probabilistico
#:      YA lleva el sesgo dentro, porque los errores empiricos lo llevan.
#: El conjunto declarado pasa de SEIS a CINCO: menos comparaciones, no mas.
MODELOS = ["B0_clima", "B1_persist", "B2_fc_crudo", "B3_fc_sesgo", "B4_fc_prob"]
fallos: list[str] = []


def ok(c, etq, det=""):
    print(f"  {'OK ' if c else '!! '} {etq}" + (f"   {det}" if det else ""))
    if not c:
        fallos.append(etq)


def tasof(td, lead):
    return dt.datetime.combine(td, dt.time(12), dt.timezone.utc) - dt.timedelta(hours=lead)


def label_av(td, zona):
    return (dt.datetime.combine(td + dt.timedelta(days=1), dt.time(0), zona)
            .astimezone(dt.timezone.utc) + dt.timedelta(hours=24))


def observaciones_c(con, station):
    """Para el ERROR: `tmax_observed`, Celsius (A-283)."""
    zona = ZoneInfo(stations.timezone_of(station))
    o = {}
    for t, v in con.execute(
            "SELECT observation_time, tmax_observed FROM weather_observations WHERE station = ?",
            [station]).fetchall():
        d = t.astimezone(zona).date()
        o[d] = max(o.get(d, float("-inf")), float(v))
    return o, zona


def probabilidades(ev, f, tr):
    """Los seis vectores para UN evento. `tr` = [(dia, obs_C, fc_C)], ya filtrado por
    disponibilidad en `t_asof`. Nada de aqui puede mirar el dia objetivo."""
    errs = [o - fx for _, o, fx in tr]
    sesgo = stx.mean(errs)
    hist = [o for _, o, _ in tr[-VENT_CLIMA:]]
    #: B1 = la ULTIMA etiqueta disponible en t_asof, que es `tr[-1]` porque `tr` ya viene
    #: filtrado por `label_av(d) <= t_asof` y ordenado. (La primera version llevaba un
    #: bucle que asignaba y rompia en la primera vuelta: mismo valor, mas ruido.)
    pers = tr[-1][1]
    bandas = [(lo, hi) for lo, hi, _ in ev["bandas"]]

    def dentro(g, lo, hi):
        return (lo is None or g >= lo) and (hi is None or g <= hi)

    out = {m: [] for m in MODELOS}
    for lo, hi in bandas:
        out["B0_clima"].append(sum(1 for o in hist if dentro(round(o), lo, hi)) / len(hist))
        out["B1_persist"].append(1.0 if dentro(round(pers), lo, hi) else 0.0)
        out["B2_fc_crudo"].append(1.0 if dentro(round(f), lo, hi) else 0.0)
        out["B3_fc_sesgo"].append(1.0 if dentro(round(f + sesgo), lo, hi) else 0.0)
        out["B4_fc_prob"].append(
            sum(1 for e in errs if dentro(round(f + e), lo, hi)) / len(errs))
    return out


def construye(con, pob, obs, FC, zona, lead, obs_alterado=None):
    fuente = obs_alterado if obs_alterado is not None else obs
    filas = []
    for td in sorted(pob):
        if td not in fuente or (td, lead) not in FC:
            continue
        t = tasof(td, lead)
        f = FC[(td, lead)][1]
        tr = [(d, fuente[d], FC[(d, lead)][1]) for d in sorted(fuente)
              if label_av(d, zona) <= t and (d, lead) in FC]
        if len(tr) < MIN_TRAIN:
            continue
        ev = pob[td]
        filas.append({"td": td, "event_id": ev["event_id"], "lead": lead,
                      "n": ev["n_bandas"], "p": probabilidades(ev, f, tr),
                      "y": [1.0 if b[2] else 0.0 for b in ev["bandas"]],
                      "train_max": max(d for d, _, _ in tr), "n_train": len(tr)})
    return filas


def main() -> int:
    con = duckdb.connect(DB, read_only=True)
    con.execute("SET TimeZone='UTC'")
    obs, zona = observaciones_c(con, ST)
    FC = pronosticos(con, ST)
    pob, _, _, _ = poblacion(con, DSV, ST)

    print("=" * 92)
    print("L1.2 — BASELINES · implementacion declarada y BUENA FORMA")
    print("=" * 92)
    print("  NO se puntua contra el target en esta etapa. El scoring es L1.4/L1.5.")

    for lead in (24, 9):
        filas = construye(con, pob, obs, FC, zona, lead)
        print(f"\n{'-' * 92}\nlead {lead} h · eventos {len(filas)} · "
              f"escaleras {dict(Counter(x['n'] for x in filas))}\n{'-' * 92}")

        # --- BUENA FORMA (§8: en [0,1], suman 1, sólo informacion anterior)
        malos = [(x["td"], m) for x in filas for m in MODELOS
                 for p in x["p"][m] if not (0.0 <= p <= 1.0)]
        ok(not malos, "toda p en [0,1]", f"{len(malos)} fuera")
        peor = max(abs(sum(x["p"][m]) - 1.0) for x in filas for m in MODELOS)
        ok(peor < 1e-9, "suman 1 dentro del evento, en los CINCO", f"error maximo {peor:.2e}")
        ok(all(sum(x["y"]) == 1.0 for x in filas), "exactamente un y=1 por evento")
        ok(all(len(x["p"][m]) == x["n"] for x in filas for m in MODELOS),
           "un componente por banda del contrato, en los cinco")
        ok(all(x["train_max"] < x["td"] for x in filas),
           "el dia objetivo NUNCA esta en el entrenamiento",
           f"train_max maximo = td-{min((x['td']-x['train_max']).days for x in filas)} dias")
        ok(all(label_av(x["train_max"], zona) <= tasof(x["td"], lead) for x in filas),
           "la ultima etiqueta de entrenamiento estaba DISPONIBLE en t_asof")
        ok(all(x["n_train"] >= MIN_TRAIN for x in filas), f"minimo {MIN_TRAIN} pares de entrenamiento",
           f"min real {min(x['n_train'] for x in filas)}")

        # --- CARACTERIZACION, sin tocar el target
        print(f"\n  {'modelo':24s} {'p_max medio':>12s} {'entropia':>9s} {'bandas con masa':>16s}"
              f" {'p=0 exactos':>12s} {'p=1 exactos':>12s}")
        for m in MODELOS:
            pmax = stx.mean(max(x["p"][m]) for x in filas)
            ent = stx.mean(-sum(p * math.log(p) for p in x["p"][m] if p > 0) for x in filas)
            viv = stx.mean(sum(1 for p in x["p"][m] if p > 0) for x in filas)
            z = sum(1 for x in filas for p in x["p"][m] if p == 0.0)
            u = sum(1 for x in filas for p in x["p"][m] if p == 1.0)
            print(f"  {m:24s} {pmax:12.4f} {ent:9.4f} {viv:16.2f} {z:12d} {u:12d}")
        print(f"  (entropia maxima de una escalera de 11 bandas: {math.log(11):.4f})")

    # --- PRUEBA EJECUTABLE DE NO-FUGA: alterar el FUTURO no puede mover nada
    print(f"\n{'=' * 92}\nPRUEBA DE NO-FUGA — se altera el FUTURO y se exige que NADA cambie\n{'=' * 92}")
    lead = 24
    base = construye(con, pob, obs, FC, zona, lead)
    corte = base[len(base) // 2]["td"]
    alt = {d: (v + 25.0 if d >= corte else v) for d, v in obs.items()}
    mod = construye(con, pob, obs, FC, zona, lead, obs_alterado=alt)
    antes = {x["td"]: x["p"] for x in base if x["td"] < corte}
    despues = {x["td"]: x["p"] for x in mod if x["td"] < corte}
    iguales = all(antes[d][m] == despues[d][m] for d in antes for m in MODELOS)
    print(f"  se suma +25 C a TODAS las observaciones desde {corte} (incluida)")
    print(f"  eventos anteriores al corte comparados: {len(antes)}")
    ok(iguales, "ninguna probabilidad ANTERIOR al corte cambia: no hay fuga del futuro")
    post = [x for x in mod if x["td"] > corte]
    cambia = any(x["p"][m] != next(b["p"][m] for b in base if b["td"] == x["td"])
                 for x in post for m in ("B0_clima", "B4_fc_prob"))
    ok(cambia, "y las POSTERIORES si cambian: la prueba tiene poder, no pasa por vacia",
       f"{len(post)} eventos posteriores")

    con.close()
    print(f"\n{'=' * 92}")
    print("RESULTADO:", "BUENA FORMA VERIFICADA" if not fallos else f"FALLAN {fallos}")
    print("=" * 92)
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
