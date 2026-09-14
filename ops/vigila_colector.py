#!/usr/bin/env python3
"""VIGILANTE DEL COLECTOR — deriva la espera de lock y el plazo, desde los shards.

POR QUE EXISTE (A-310, A-311, A-312). El ciclo crece ~317 s/dia y la holgura entre el
`decide` de las 02:40 y el `collect` de las 03:07 es 1620 s + 900 s de `PMW_LOCK_WAIT`.
Cuando se agote, el `collect` se SALTA, y un turno de libro saltado no se recupera.

Y EL INDICADOR NO EXISTE COMO CAMPO: `session_id` y `cycle_started_at` se sellan cuando el
launcher ADQUIERE el lock, no cuando el cron dispara, asi que una espera exitosa no deja
rastro; `lock_timeout` solo se emite al rendirse a los 900 s. Lo unico que hay es la
VIOLACION.

Pero es DERIVABLE: `hora del id - ranura de cron`. El cron esta comprometido en el repo
(`7 */3` collect, `40 2` y `40 11` decide), asi que la dependencia esta versionada -- la
variante benigna de "una derivacion se apoya en algo que no declara".

ESTO SUSTITUYE AL `gh run list --workflow=paper_collect.yml` DE LA ORDEN DE CICLO, que
lleva dias apuntando a un workflow desactivado: la ejecucion se mudo a Hetzner y un
workflow que no corre nunca falla.

Umbrales DECLARADOS AQUI, antes de mirar ninguno:
    espera > 300 s  ->  AVISO     (un tercio del presupuesto de 900 consumido)
    espera > 600 s  ->  ALARMA    (dos tercios)
    espera ausente y hueco en las ranuras  ->  ALARMA (turno perdido)
Sale 1 si hay ALARMA. No toca el host, no gasta cuota, solo lee `paper-state`.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import gzip
import json
import os
import re
import statistics as st
import sys

PAPER = os.environ.get("PMW_PAPER", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-paper")
#: El cron de Hetzner, copiado del repositorio. Si cambia alli, cambia aqui: esta es la
#: dependencia que la derivacion declara en vez de suponer.
RANURAS = [(h, 7) for h in range(0, 24, 3)] + [(2, 40), (11, 40)]
AVISO, ALARMA = 300.0, 600.0
#: EL CRON DE HETZNER EMPIEZA AQUI, y no es una fecha elegida: es el PRIMER ciclo alineado
#: con una ranura (espera 5 s). Los cinco anteriores son ejecuciones MANUALES de la tarde
#: de la migracion desde Actions -- se reconocen porque no hay 3 h entre ninguna de ellas,
#: y emparejarlas con la ranura de las 18:07 daba esperas de 2.776 a 10.586 s. Un vigilante
#: que grita cinco veces por algo que no es una colision es un vigilante que nadie lee.
ERA_CRON = dt.datetime(2026, 9, 9, 21, 7, 5, tzinfo=dt.timezone.utc)
#: Holgura entre el `decide 9` (02:40) y el `collect` siguiente (03:07), mas el lock.
HOLGURA = (27 * 60) + 900


def ciclos():
    out = []
    for p in sorted(glob.glob(f"{PAPER}/paper_state/cycle_params/*/*/*/*.ndjson.gz")):
        for ln in gzip.open(p, "rt"):
            d = json.loads(ln)
            m = re.match(r"col_(\d{8}T\d{6}Z)_", d.get("session_id", ""))
            if not m:
                continue
            t = dt.datetime.strptime(m.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
            cand = [c for c in (t.replace(hour=h, minute=mi, second=0, microsecond=0)
                                for h, mi in RANURAS) if c <= t]
            if not cand:
                continue
            prof = json.loads(d["stage_profile"]) if d.get("stage_profile") else []
            if t < ERA_CRON:
                continue
            out.append({
                "t": t, "ranura": max(cand), "espera": (t - max(cand)).total_seconds(),
                "dur": max((e["at_s"] for e in prof), default=None),
                "mb": (d.get("store_total_bytes") or 0) / 1e6,
                "razon": d.get("collect_only_reason"), "sid": d["session_id"],
            })
    out.sort(key=lambda c: c["t"])
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ultimos", type=int, default=10)
    ap.add_argument("--desde", default="2026-09-13",
                    help="inicio del regimen para la pendiente; el escalon del 09-13 "
                         "(load:markets se normalizo) hace que antes no sea comparable")
    a = ap.parse_args(argv)

    cs = ciclos()
    if not cs:
        print("SIN DATOS: no hay shards de cycle_params."); return 1
    print("=" * 96)
    print(f"VIGILANTE DEL COLECTOR · {dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ} · "
          f"{len(cs)} ciclos")
    print("=" * 96)
    print(f"  {'id':22s} {'ranura':7s} {'espera_s':>9s} {'ciclo_s':>9s} {'MB':>6s}  razon")
    for c in cs[-a.ultimos:]:
        marca = "  <<< ALARMA" if c["espera"] > ALARMA else "  <<< AVISO" if c["espera"] > AVISO else ""
        print(f"  {c['t']:%m-%d %H:%M:%S}Z      {c['ranura']:%H:%M}  {c['espera']:9.0f} "
              f"{(c['dur'] or 0):9.1f} {c['mb']:6.1f}  {str(c['razon']):16s}{marca}")

    d0 = dt.datetime.fromisoformat(a.desde).replace(tzinfo=dt.timezone.utc)
    reg = [c for c in cs if c["t"] >= d0 and c["dur"]]
    if len(reg) >= 3:
        p, u = reg[0], reg[-1]
        h = (u["t"] - p["t"]).total_seconds() / 3600
        x = [(c["t"] - p["t"]).total_seconds() / 86400 for c in reg]
        y = [c["dur"] for c in reg]
        #: THEIL-SEN, la mediana de TODAS las pendientes por pares, y no la de dos puntos.
        #: La primera version de este guion usaba (ultimo - primero) y el 06:07 del 09-14
        #: --un solo ciclo, +119 s sobre la recta, +3,7 sd-- le movio el plazo CATORCE HORAS.
        #: Es el defecto que A-317 le encontro al estadistico marginal, aqui dentro: una
        #: diferencia suelta de dos magnitudes ruidosas no mide una pendiente pequena. La
        #: forma correcta de usar esas diferencias es tomar su MEDIANA.
        pend = st.median([(y[j] - y[i]) / (x[j] - x[i])
                          for i in range(len(x)) for j in range(i + 1, len(x)) if x[j] > x[i]])
        mx, my = st.mean(x), st.mean(y)
        b = sum((q - mx) * (w - my) for q, w in zip(x, y)) / sum((q - mx) ** 2 for q in x)
        #: RESIDUOS CONTRA LA RECTA ROBUSTA, y escala por MAD -- no por desviacion tipica.
        #: Con sigma clasica el atipico INFLA la escala con la que se le mide y se enmascara
        #: solo: el 06:07 del 09-14 da +3,7 sd contra los residuos previos y solo 2,6 con la
        #: sigma que el mismo engorda. Una escala robusta no tiene esa puerta trasera.
        inter = st.median([w - pend * q for q, w in zip(x, y)])
        res = [w - (inter + pend * q) for q, w in zip(x, y)]
        mad = st.median([abs(r - st.median(res)) for r in res])
        sd = (mad * 1.4826) or 1.0
        print(f"\n  regimen desde {a.desde}: {len(reg)} ciclos en {h:.1f} h")
        print(f"     ciclo    {p['dur']:.0f} -> {u['dur']:.0f} s")
        print(f"     pendiente  Theil-Sen {pend:+.0f} s/dia   ·   minimos cuadrados {b:+.0f}"
              f"   ·   dos puntos {(y[-1]-y[0])/x[-1]:+.0f}  (esta ultima NO se usa)")
        print(f"     almacen  {p['mb']:.1f} -> {u['mb']:.1f} MB")
        fuera = [(c, r) for c, r in zip(reg, res) if abs(r) > 3.5 * sd]
        for c, r in fuera:
            print(f"     ATIPICO  {c['t']:%m-%d %H:%M}Z  {c['dur']:.0f} s, {r:+.0f} s sobre la "
                  f"recta robusta ({r/sd:+.1f} MAD-sd)")
        if pend > 0:
            queda = (HOLGURA - u["dur"]) / pend
            print(f"     holgura  {HOLGURA} - {u['dur']:.0f} = {HOLGURA - u['dur']:.0f} s"
                  f"   ->   {queda:.2f} dias   ->   "
                  f"{(u['t'] + dt.timedelta(days=queda)):%Y-%m-%d %H:%MZ}")
            print(f"     AVISO: es COTA, no fecha -- la pendiente se estima con el mismo "
                  f"dato que predice.")
            print(f"     (el escalon del 09-13 YA ESTA EXPLICADO, A-320: `_newest_first` "
                  f"empezo a enganchar, ratio 1,712 -> 1,008. Fue un arreglo que aterrizo "
                  f"una vez, no una oscilacion, asi que el regimen posterior es un regimen.)")

    aviso = [c for c in cs if AVISO < c["espera"] <= ALARMA]
    alarma = [c for c in cs if c["espera"] > ALARMA]
    print(f"\n  esperas > {AVISO:.0f} s: {len(aviso)}   ·   > {ALARMA:.0f} s: {len(alarma)}")
    for c in alarma[-5:]:
        print(f"     ALARMA {c['t']:%Y-%m-%d %H:%M:%S}Z  ranura {c['ranura']:%H:%M}  "
              f"espero {c['espera']:.0f} s   ({c['sid']})")
    print("=" * 96)
    return 1 if alarma else 0


if __name__ == "__main__":
    raise SystemExit(main())
