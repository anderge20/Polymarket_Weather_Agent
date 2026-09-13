#!/usr/bin/env python3
"""FASE C — INGESTA DE OBSERVACIONES DE RKSI. Metodologia IDENTICA a la de EGLC.

Usa `observations.ingest_daily_high`, la MISMA funcion de produccion que uso la
reingesta de EGLC (n1_35). UNA peticion por dia: no se sustituye por una peticion de
rango, porque eso seria una ruta de ingesta distinta y el lock congela la metodologia.

  techo duro        100 peticiones (preinscrito en LOCK_FASE_C.md)   --max-requests
  parada dura       cualquier 429 o error de proveedor · discrepancia con el oraculo
  oraculo           evidence/B-133/raw_iem_55_estaciones.tgz, serie rt34 de RKSI,
                    descargado el 2026-09-13 ANTES de esta ingesta
  dataset_version   NUEVO. No se toca ni una fila existente.
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
from zoneinfo import ZoneInfo

REPO = os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-merge")
sys.path.insert(0, os.path.join(REPO, "src"))
from weather_agent import database as db          # noqa: E402
from weather_agent import observations as obs     # noqa: E402
from weather_agent import stations                # noqa: E402

ICAO = "RKSI"
TZ = stations.timezone_of(ICAO)
ZONA = ZoneInfo(TZ)
TARBALL = "/Users/mariaaleu/pmw-e2/evidence/B-133/raw_iem_55_estaciones.tgz"


def oraculo() -> dict[dt.date, float]:
    """Maximo por dia local de la serie rt34 del tarball. Independiente de la API."""
    out: dict[dt.date, float] = {}
    with tarfile.open(TARBALL) as t:
        datos = t.extractfile(f"raw/{ICAO}_rt34.csv").read().decode()
    for r in csv.DictReader(io.StringIO(datos)):
        try:
            f = float(r["tmpf"])
        except (TypeError, ValueError):
            continue
        loc = (dt.datetime.strptime(r["valid"], "%Y-%m-%d %H:%M")
               .replace(tzinfo=dt.timezone.utc).astimezone(ZONA))
        c = round((f - 32.0) * 5.0 / 9.0)
        d = loc.date()
        out[d] = max(out.get(d, -999), c)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/Users/mariaaleu/workspace/Polymarket_Weather_Agent/data/pmw.duckdb")
    ap.add_argument("--dataset-version", default="replica_rksi_v1")
    ap.add_argument("--desde", default="2026-04-08")
    ap.add_argument("--hasta", default="2026-08-23")
    ap.add_argument("--max-requests", type=int, default=100)
    ap.add_argument("--sleep", type=float, default=1.0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    serie, unidad, res = obs.station_series(ICAO)
    if "RT34" not in serie:
        print(f"NEGADO: station_series({ICAO}) = {serie}, no es la serie RT34.", file=sys.stderr)
        return 2
    print(f"{ICAO} · tz {TZ} · serie {serie} ({unidad}, res {res})", flush=True)

    d0 = dt.date.fromisoformat(a.desde); d1 = dt.date.fromisoformat(a.hasta)
    con = db.init_db(db.connect(a.db))
    ya = {t.astimezone(ZONA).date() for (t,) in con.execute(
        "SELECT observation_time FROM weather_observations WHERE station = ? "
        "AND dataset_version = ?", [ICAO, a.dataset_version]).fetchall()}
    dias = [d0 + dt.timedelta(n) for n in range((d1 - d0).days + 1) if d0 + dt.timedelta(n) not in ya]
    ora = oraculo()
    cub = sum(1 for d in dias if d in ora)
    print(f"ventana {d0} -> {d1} · dias a pedir {len(dias)} · techo {a.max_requests} · "
          f"ya ingestados {len(ya)}", flush=True)
    print(f"con oraculo {cub} · sin oraculo {len(dias) - cub}", flush=True)
    if len(dias) > a.max_requests:
        print(f"NEGADO: {len(dias)} dias contra un techo de {a.max_requests}. "
              f"El techo esta preinscrito; se estrecha la ventana, no el techo.", file=sys.stderr)
        con.close(); return 2
    if a.dry_run:
        print("DRY-RUN: cero peticiones.", flush=True); con.close(); return 0

    hechas = fallos = disc = 0
    for d in dias:
        if hechas >= a.max_requests:
            print(f"TECHO alcanzado en {hechas}. Parando.", flush=True); break
        try:
            dh = obs.ingest_daily_high(con, ICAO, d, TZ, a.dataset_version)
            hechas += 1
        except obs.NoObservation as e:
            hechas += 1; fallos += 1
            print(f"  {d} sin observacion utilizable: {e}", flush=True)
            time.sleep(a.sleep); continue
        except Exception as e:                      # noqa: BLE001 — 429, red, lo que sea
            hechas += 1
            print(f"  {d} ERROR {type(e).__name__}: {e}", flush=True)
            print("PARADA DURA: no se rodea un fallo de proveedor (regla de cuota).", flush=True)
            con.close(); print(f"peticiones emitidas: {hechas}", flush=True); return 1
        if d in ora and round(dh.tmax_c) != round(ora[d]):
            disc += 1
            print(f"  {d} DISCREPANCIA con el oraculo: ingestado {dh.tmax_c:.2f} vs "
                  f"tarball {ora[d]:.2f}", flush=True)
            print("PARADA: oraculo e ingesta no coinciden.", flush=True)
            con.close(); print(f"peticiones emitidas: {hechas}", flush=True); return 1
        if hechas % 20 == 0:
            print(f"  ... {hechas} peticiones", flush=True)
        time.sleep(a.sleep)
    con.close()
    print(f"HECHO peticiones={hechas} (techo {a.max_requests}) "
          f"dias_sin_observacion={fallos} discrepancias={disc}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
