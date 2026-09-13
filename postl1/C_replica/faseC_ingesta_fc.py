#!/usr/bin/env python3
"""FASE C — INGESTA DE PRONOSTICOS DE RKSI. Metodologia IDENTICA a la de EGLC.

Usa `weather.ingest_run`, la MISMA funcion de produccion que llama
`scripts/backfill_weather.py`, y la MISMA seleccion de pasada: se camina hacia atras
por la rejilla de emision y se toma la primera cuyo `available_at` (emision + L_MAX)
sea <= t_asof. NUNCA `issue_time <= t`.

  leads             24 y 9  ->  t_asof = target_date 12:00Z - lead   (2E/D1, sin tocar)
  ventana congelada 2026-05-21 .. 2026-08-23  (ENMIENDA_VENTANA_FASE_C.md, 95 dias)
  peticiones        190 = 95 dias x 2 pasadas distintas (06z y 18z del dia anterior)
  techo duro        200 peticiones (preinscrito en LOCK_FASE_C.md §5)  --max-requests
  parada dura       429/cuota; discrepancia con el oraculo; mas de 20 pasadas ausentes
  pasada ausente    se cuenta y se sigue, como `backfill_weather.py`: el par se queda SIN
                    pronostico y cae de la poblacion puntuable (ENMIENDA_FALLO_DE_PASADA.md)
  dataset_version   NUEVO (`replica_rksi_v1`). No se toca ni una fila existente.

ORACULO INDEPENDIENTE, Y ES GRATIS. RKSI ya tiene 91 filas de pronostico bajo
`backfill_2b_v1`, escritas semanas antes por la misma ruta de produccion. El archivo
Single-Runs es inmutable: la MISMA (station, model, issue_time, target_date) tiene que
devolver el MISMO `forecast_tmax`. Cada fila reingestada que coincida con una vieja se
compara, y una discrepancia PARA la ingesta: significaria que el archivo del proveedor
no es inmutable y toda la metodologia as-of se apoya en que lo es.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import time

REPO = os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-merge")
sys.path.insert(0, os.path.join(REPO, "src"))
from weather_agent import database as db     # noqa: E402
from weather_agent import stations, weather  # noqa: E402

ICAO = "RKSI"
LEADS_H = (24, 9)                 # los dos, identicos a Londres
ISSUE_HOURS = (0, 6, 12, 18)      # rejilla de emision de ICON seamless
MAX_RUN_AGE_H = 36                # identico a scripts/backfill_weather.py
VIEJA = "backfill_2b_v1"          # la version de la que sale el oraculo


def pick_run(t: dt.datetime, model: str) -> dt.datetime | None:
    """Copia literal de `scripts/backfill_weather.pick_run`.

    NO se importa el guion porque su modulo abre el catalogo y filtra por
    `price_history`, que es justo el universo que la Fase C no usa. La funcion se
    replica tal cual y el test `test_pick_run_identico` comprueba que coincide con la
    de produccion en las 190 decisiones de esta ventana.
    """
    cursor = t.replace(minute=0, second=0, microsecond=0)
    limit = t - dt.timedelta(hours=MAX_RUN_AGE_H)
    while cursor >= limit:
        if cursor.hour in ISSUE_HOURS and weather.is_available_at(cursor, model, t):
            return cursor
        cursor -= dt.timedelta(hours=1)
    return None


def plan(d0: dt.date, d1: dt.date) -> list[tuple[dt.date, dt.datetime, int]]:
    """(target_date, issue_time, lead) deduplicado por (target_date, issue_time)."""
    vistos: dict[tuple[dt.date, dt.datetime], int] = {}
    out = []
    for n in range((d1 - d0).days + 1):
        td = d0 + dt.timedelta(n)
        fin = dt.datetime(td.year, td.month, td.day, 12, tzinfo=dt.timezone.utc)
        for lead in LEADS_H:
            run = pick_run(fin - dt.timedelta(hours=lead), weather.M1_MODEL)
            if run is None:
                print(f"  {td} lead {lead}h SIN PASADA publicada a tiempo", flush=True)
                continue
            if (td, run) in vistos:
                continue
            vistos[(td, run)] = lead
            out.append((td, run, lead))
    return out


def oraculo(con) -> dict[tuple[dt.date, dt.datetime], float]:
    filas = con.execute(
        "SELECT target_date, issue_time, forecast_tmax FROM weather_forecasts "
        "WHERE station = ? AND model = ? AND dataset_version = ? "
        "AND forecast_tmax IS NOT NULL",
        [ICAO, weather.M1_MODEL, VIEJA]).fetchall()
    return {(td, it.astimezone(dt.timezone.utc)): tm for td, it, tm in filas}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/Users/mariaaleu/workspace/Polymarket_Weather_Agent/data/pmw.duckdb")
    ap.add_argument("--dataset-version", default="replica_rksi_v1")
    ap.add_argument("--desde", default="2026-05-21")
    ap.add_argument("--hasta", default="2026-08-23")
    ap.add_argument("--max-requests", type=int, default=200)
    ap.add_argument("--max-fallos", type=int, default=20,
                    help="techo de pasadas ausentes; declarado en ENMIENDA_FALLO_DE_PASADA.md")
    ap.add_argument("--sleep", type=float, default=0.3)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    tz = stations.timezone_of(ICAO)
    print(f"{ICAO} · tz {tz} · modelo {weather.M1_MODEL} · "
          f"L_MAX {weather.L_MAX_HOURS[weather.M1_MODEL]} h", flush=True)

    d0 = dt.date.fromisoformat(a.desde); d1 = dt.date.fromisoformat(a.hasta)
    con = db.init_db(db.connect(a.db))

    ya = {(td, it.astimezone(dt.timezone.utc)) for td, it in con.execute(
        "SELECT target_date, issue_time FROM weather_forecasts WHERE station = ? "
        "AND dataset_version = ?", [ICAO, a.dataset_version]).fetchall()}
    todo = [p for p in plan(d0, d1) if (p[0], p[1]) not in ya]
    ora = oraculo(con)
    cub = sum(1 for td, run, _ in todo if (td, run) in ora)
    print(f"ventana {d0} -> {d1} · dias {(d1 - d0).days + 1} · peticiones a emitir "
          f"{len(todo)} · techo {a.max_requests} · ya ingestadas {len(ya)}", flush=True)
    print(f"con oraculo {cub} · sin oraculo {len(todo) - cub}", flush=True)
    if len(todo) > a.max_requests:
        print(f"NEGADO: {len(todo)} peticiones contra un techo de {a.max_requests}. "
              f"El techo esta preinscrito; se estrecha la ventana, no el techo.", file=sys.stderr)
        con.close(); return 2
    if a.dry_run:
        print("DRY-RUN: cero peticiones.", flush=True); con.close(); return 0

    hechas = disc = fallos = 0
    ausentes: list[tuple[dt.date, dt.datetime, int, str]] = []
    for td, run, lead in todo:
        if hechas >= a.max_requests:
            print(f"TECHO alcanzado en {hechas}. Parando.", flush=True); break
        try:
            fc = weather.ingest_run(con, ICAO, td, tz, run, a.dataset_version,
                                    model=weather.M1_MODEL)
            hechas += 1
        except Exception as e:                      # noqa: BLE001 — clasificado, no tragado
            hechas += 1
            msg = str(e)
            # DOS CLASES, COMO EN `scripts/backfill_weather.py`. Cuota: parada dura, sin
            # reintento y sin rodeo (D0). Hueco del archivo: se cuenta y se sigue, y el par
            # (target_date, lead) se queda SIN pronostico -> fuera de la poblacion
            # puntuable. Retroceder a una pasada anterior seria cambiar `pick_run`, que
            # esta congelado. Ver ENMIENDA_FALLO_DE_PASADA.md.
            if "429" in msg or "quota" in msg.lower():
                print(f"  {td} run {run:%m-%d %Hz} CUOTA AGOTADA: {e}", flush=True)
                print("PARADA DURA: no se rodea el limite del proveedor.", flush=True)
                con.close(); print(f"peticiones emitidas: {hechas}", flush=True); return 1
            fallos += 1
            ausentes.append((td, run, lead, msg))
            print(f"  {td} run {run:%m-%d %Hz} (lead {lead}h) SIN PASADA [{fallos}]: {e}",
                  flush=True)
            if fallos > a.max_fallos:
                print(f"PARADA: {fallos} fallos por encima del techo declarado "
                      f"{a.max_fallos}. Ingesta INCOMPLETA, no se puntua.", flush=True)
                con.close(); print(f"peticiones emitidas: {hechas}", flush=True); return 1
            time.sleep(a.sleep); continue
        viejo = ora.get((td, run))
        if viejo is not None and abs(fc.tmax - viejo) > 1e-9:
            disc += 1
            print(f"  {td} run {run:%m-%d %Hz} DISCREPANCIA con {VIEJA}: "
                  f"reingestado {fc.tmax:.4f} vs viejo {viejo:.4f}", flush=True)
            print("PARADA: el archivo Single-Runs no seria inmutable.", flush=True)
            con.close(); print(f"peticiones emitidas: {hechas}", flush=True); return 1
        if hechas % 25 == 0:
            print(f"  ... {hechas} peticiones · ultima {td} {run:%m-%d %Hz} "
                  f"tmax {fc.tmax:.1f}", flush=True)
        time.sleep(a.sleep)
    con.close()
    print(f"HECHO peticiones={hechas} (techo {a.max_requests}) discrepancias={disc} "
          f"pasadas_ausentes={fallos} (techo {a.max_fallos})", flush=True)
    for td, run, lead, msg in ausentes:
        print(f"  AUSENTE {td} run {run:%Y-%m-%dT%H:%M}Z lead {lead}h :: {msg}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
