#!/usr/bin/env python3
"""SUPERSEDIDO POR `s02_ventana_estricta.py` Y A-258. El 3,56 % que sale aqui NO es la
cota de conflicto: cuenta dias que el sistema NO PUEDE ETIQUETAR (falta la regla de
cobertura de `daily_high`) y cuenta EMPATES, que liquidan igual con cualquier ventana.
La cota real es 0,80 % de los dias etiquetables. Este guion se conserva porque su
recuento es el denominador del que sale el desglose del s02.

PISTA DE LIQUIDACION — ¿con que frecuencia el maximo del DIA CIVIL LOCAL cae en su
PRIMERA HORA?

POR QUE. `WINDOW_LOCAL_CIVIL_DAY` del nucleo congelado toma el maximo sobre el dia civil
local completo, 00:00 incluido. El 2026-05-27 en EGLC ese maximo fue el calor SOBRANTE
del dia anterior -- 25 C a las 00:20 locales tras un dia de 34 -- y el mercado resolvio
por el maximo diurno, 24 (A-247). Es la PRIMERA observacion que separa la ventana del
operador de una resolucion real.

QUE MIDE ESTE GUION Y QUE NO.
  MIDE:    con que frecuencia el maximo del dia civil local cae en la hora 00 local, en
           las 55 estaciones del tarball de B-133, y con que minuto.
  NO MIDE: si el mercado resolvio distinto. Eso necesita las escaleras completas, que
           hoy estan truncadas (A-244), y se hara tras la reingesta.

CERO PETICIONES: todo sale de `evidence/B-133/raw_iem_55_estaciones.tgz`, ya descargado.

LA SERIE NO CAMBIA LA EXPOSICION, Y ESTO LO MEDI PARA DESMENTIRME A MI MISMO. La primera
version de este comentario afirmaba que con tipo 3 el fenomeno seria "invisible" y que
medirlo con la serie vieja habria dado "un cero tranquilizador". Es FALSO, medido:

    tipo 3     290 de 8202 dias (3,54 %)   51 estaciones con al menos uno
    tipos 3+4  292 de 8202 dias (3,56 %)   50 estaciones
    EGLC        3 con tipo 3   ·   3 con 3+4     <- identico

La EXPOSICION -- que el maximo del dia civil caiga en la primera hora -- es una propiedad
de la VENTANA, no de la serie. Lo que el PR #49 cambia es el VALOR en ese instante (el
2026-05-27 en EGLC: 24 C a las 00:50 con tipo 3, 25 C a las 00:20 con 3+4), y es el valor
el que convirtio un dia expuesto en un conflicto de resolucion.

Escribir la frase dramatica sin medirla habria metido en el corpus una afirmacion falsa
con aspecto de hallazgo.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import os
import sys
import tarfile
from collections import Counter, defaultdict
from zoneinfo import ZoneInfo

REPO = os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-main")
sys.path.insert(0, os.path.join(REPO, "src"))
from weather_agent import stations  # noqa: E402

TARBALL = os.path.expanduser(
    "~/.claude/jobs/324ffe40/tmp/wt-research/evidence/B-133/raw_iem_55_estaciones.tgz")


def main() -> int:
    filas = []
    sin_tz = []
    tot_dias = 0
    tot_h0 = 0
    minutos = Counter()
    with tarfile.open(TARBALL) as t:
        miembros = sorted(m for m in t.getnames() if m.endswith("_rt34.csv"))
        for nombre in miembros:
            icao = os.path.basename(nombre).split("_")[0]
            try:
                tz = ZoneInfo(stations.timezone_of(icao))
            except Exception:
                sin_tz.append(icao)
                continue
            texto = t.extractfile(nombre).read().decode()
            por_dia = defaultdict(list)
            for r in csv.DictReader(io.StringIO(texto)):
                try:
                    f = float(r["tmpf"])
                except (TypeError, ValueError):
                    continue
                ts = dt.datetime.strptime(r["valid"], "%Y-%m-%d %H:%M").replace(
                    tzinfo=dt.timezone.utc)
                loc = ts.astimezone(tz)
                por_dia[loc.date()].append((loc, (f - 32.0) * 5.0 / 9.0))
            h0 = []
            for d, vals in por_dia.items():
                loc, _ = max(vals, key=lambda x: x[1])
                if loc.hour == 0:
                    h0.append((d, loc.strftime("%H:%M")))
                    minutos[loc.minute] += 1
            tot_dias += len(por_dia)
            tot_h0 += len(h0)
            filas.append((icao, len(por_dia), len(h0), 100.0 * len(h0) / max(len(por_dia), 1)))

    filas.sort(key=lambda x: -x[3])
    print(f"{'estacion':9s} {'dias':>5s} {'h00':>4s} {'%':>6s}")
    for icao, n, h, pct in filas:
        if h:
            print(f"{icao:9s} {n:5d} {h:4d} {pct:6.2f}")
    cero = sum(1 for _, _, h, _ in filas if h == 0)
    print(f"\nestaciones con al menos un dia asi: {len(filas)-cero} de {len(filas)}")
    print(f"dias totales {tot_dias} · con el maximo en la hora 00 local {tot_h0} "
          f"({100.0*tot_h0/max(tot_dias,1):.2f} %)")
    print(f"minuto de esas lecturas: {dict(sorted(minutos.items()))}")
    if sin_tz:
        print(f"sin zona horaria en el registro ({len(sin_tz)}): {sin_tz}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
