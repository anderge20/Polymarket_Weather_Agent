#!/usr/bin/env python3
"""NIVEL 1, paso 1 de §6bis — reingesta de las observaciones de EGLC con tipos 3+4.

EJECUTA LO QUE PREREGISTRA `fase2/PREREG_PRESUPUESTO_IEM.md` (A-252) Y NADA MAS:

  techo duro          200 peticiones         --max-requests
  estacion            EGLC unicamente
  concurrencia        1, secuencial
  pausa               >= 1,0 s               --sleep
  parada dura         cualquier 429, o dos errores sobre el mismo dia, o el techo

NO SE RODEA LA PARADA. Si IEM devuelve 429 el guion termina con codigo != 0 y deja
escrito cuantas peticiones habia emitido. Esa es la regla de cuota del proyecto, no
una preferencia de este guion.

EL ORACULO. `evidence/B-133/raw_iem_55_estaciones.tgz` trae `EGLC_rt34.csv` con 151
dias ya descargados en otro momento y por otra mano. NO se usa como fuente -- una fila
de produccion cuya procedencia no consta es el defecto que este proyecto lleva una
semana desenterrando -- pero si como CONTROL: para cada dia que el tarball cubre, el
maximo reingestado tiene que coincidir con el suyo, y si no coincide la pasada SE PARA.
Es la comprobacion mas barata que existe contra un ingestor que acaba de cambiar de
serie: gratis, independiente, y con la respuesta guardada antes de preguntar.

REQUIERE el PR #49 fusionado: sin el, `station_series('EGLC')` sigue siendo la serie de
tipo 3 y esta reingesta no cambiaria nada. El guion lo COMPRUEBA y se niega si no.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import os
import sys
import tarfile
import time
from collections import defaultdict
from zoneinfo import ZoneInfo

REPO = os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-main")
sys.path.insert(0, os.path.join(REPO, "src"))

from weather_agent import database as db          # noqa: E402
from weather_agent import observations as obs     # noqa: E402

ICAO = "EGLC"
TZ = "Europe/London"
LON = ZoneInfo(TZ)
TARBALL = os.path.expanduser(
    "~/.claude/jobs/324ffe40/tmp/wt-research/evidence/B-133/raw_iem_55_estaciones.tgz")


def oraculo(path: str) -> dict[dt.date, float]:
    """maximo por DIA LOCAL de Londres segun el CSV ya descargado (rt3+rt4)."""
    with tarfile.open(path) as t:
        miembro = next(m for m in t.getmembers() if m.name.endswith("EGLC_rt34.csv"))
        texto = t.extractfile(miembro).read().decode()
    por_dia: dict[dt.date, float] = {}
    for r in csv.DictReader(io.StringIO(texto)):
        try:
            f = float(r["tmpf"])
        except (TypeError, ValueError):
            continue
        ts = dt.datetime.strptime(r["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc)
        d = ts.astimezone(LON).date()
        c = (f - 32.0) * 5.0 / 9.0
        if d not in por_dia or c > por_dia[d]:
            por_dia[d] = c
    return por_dia


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dataset-version", required=True)
    ap.add_argument("--since", required=True, help="YYYY-MM-DD inclusive")
    ap.add_argument("--until", required=True, help="YYYY-MM-DD inclusive")
    ap.add_argument("--max-requests", type=int, default=200,
                    help="techo duro preregistrado (A-252)")
    ap.add_argument("--sleep", type=float, default=1.0)
    ap.add_argument("--dry-run", action="store_true",
                    help="cuenta los dias y no pide nada")
    args = ap.parse_args(argv)

    # LA GUARDA DEL #49, comprobada y no supuesta: sin el arreglo esto no cambia nada.
    serie = obs.station_series(ICAO)[0]
    if serie != getattr(obs, "SERIES_1C_RT34", None):
        print(f"NEGADO: station_series('{ICAO}') = {serie!r}. Esta reingesta necesita "
              f"el PR #49 fusionado (serie 3+4); sin el reescribiria lo mismo.",
              file=sys.stderr)
        return 2

    d0 = dt.date.fromisoformat(args.since)
    d1 = dt.date.fromisoformat(args.until)
    dias = [d0 + dt.timedelta(days=i) for i in range((d1 - d0).days + 1)]
    if len(dias) > args.max_requests:
        print(f"NEGADO: {len(dias)} dias contra un techo de {args.max_requests}. "
              f"El techo esta preregistrado; se estrecha la ventana, no el techo.",
              file=sys.stderr)
        return 2

    ora = oraculo(TARBALL)
    print(f"oraculo: {len(ora)} dias en el tarball "
          f"({min(ora)} -> {max(ora)})", flush=True)
    print(f"ventana: {d0} -> {d1} = {len(dias)} dias · techo {args.max_requests} · "
          f"pausa {args.sleep}s · serie {serie}", flush=True)
    cubiertos = sum(1 for d in dias if d in ora)
    print(f"de ellos con oraculo: {cubiertos}; sin oraculo (no comprobables): "
          f"{len(dias) - cubiertos}", flush=True)
    if args.dry_run:
        print("DRY-RUN: cero peticiones.", flush=True)
        return 0

    con = db.init_db(db.connect(args.db))
    hechas = fallos = discrepancias = 0
    for d in dias:
        if hechas >= args.max_requests:
            print(f"TECHO alcanzado en {hechas} peticiones. Parando.", flush=True)
            break
        try:
            dh = obs.ingest_daily_high(con, ICAO, d, TZ, args.dataset_version)
            hechas += 1
        except obs.NoObservation as e:
            hechas += 1
            fallos += 1
            print(f"  {d} sin observacion utilizable: {e}", flush=True)
            time.sleep(args.sleep)
            continue
        except Exception as e:                      # red, 429, lo que sea
            hechas += 1
            print(f"  {d} ERROR {type(e).__name__}: {e}", flush=True)
            print("PARADA DURA: no se rodea un fallo de proveedor (regla de cuota).",
                  flush=True)
            con.close()
            print(f"peticiones emitidas: {hechas}", flush=True)
            return 1
        if d in ora and round(dh.tmax_c) != round(ora[d]):
            discrepancias += 1
            print(f"  {d} DISCREPANCIA con el oraculo: ingestado {dh.tmax_c:.2f} "
                  f"vs tarball {ora[d]:.2f}", flush=True)
            print("PARADA: el oraculo y la ingesta no coinciden. No se sigue "
                  "escribiendo hasta entender por que.", flush=True)
            con.close()
            print(f"peticiones emitidas: {hechas}", flush=True)
            return 1
        time.sleep(args.sleep)

    con.close()
    print(f"HECHO peticiones={hechas} (techo {args.max_requests}) "
          f"dias_sin_observacion={fallos} discrepancias={discrepancias}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
