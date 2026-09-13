#!/usr/bin/env python3
"""LEVEL 1 · L1.0 — LOCK DEL DATASET. Se ejecuta ANTES de modelar nada.

No modela, no entrena, no calcula edge ni PnL, no selecciona mercados ni umbrales.
Sólo cuenta y registra lo que hay, para que el experimento sea reconstruible.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import os
import subprocess
import sys
from collections import Counter

import duckdb

REPO = os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-merge")
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/fase2")
from n075_poblacion import DB, observaciones, poblacion, pronosticos      # noqa: E402

ST = "EGLC"
DSV = "markets_v2"


def sha_git(ruta):
    try:
        return subprocess.run(["git", "-C", ruta, "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:                                                     # noqa: BLE001
        return "?"


def sha_fichero(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def huella_sql(con, sql, params=None):
    h = hashlib.sha256()
    for fila in con.execute(sql, params or []).fetchall():
        h.update(repr(fila).encode()); h.update(b"\n")
    return h.hexdigest()


def main():
    con = duckdb.connect(DB, read_only=True)
    con.execute("SET TimeZone='UTC'")
    ahora = dt.datetime.now(dt.timezone.utc)

    print("=" * 88); print("LEVEL 1 · LOCK DEL DATASET"); print("=" * 88)
    print(f"  timestamp de ejecucion   {ahora:%Y-%m-%dT%H:%M:%SZ}")
    print(f"  dataset_version markets  {DSV}")
    print(f"  dataset_version obs/fc   backfill_2b_v1  (la unica que existe)")
    print(f"  estacion                 {ST}")
    print(f"  git SHA (repo)           {sha_git(REPO)}")
    print(f"  git SHA (research)       {sha_git('/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-research')}")
    print(f"  base de analisis         {DB}")
    print(f"  guion de poblacion       n075_poblacion.py  sha256 "
          f"{sha_fichero('/Users/mariaaleu/pmw-e2/fase2/n075_poblacion.py')[:16]}…")
    print(f"  BANDERA                  availability_assumption = issue_plus_4h45m36s")
    print(f"                           LOOKAHEAD ASSUMPTION = UNVERIFIED EXTERNALLY")

    print("\n" + "=" * 88); print("POBLACION — todas las definiciones, ninguna silenciada"); print("=" * 88)
    n_ev = con.execute("""SELECT count(DISTINCT event_id) FROM markets
        WHERE station_identifier=? AND dataset_version=?""", [ST, DSV]).fetchone()[0]
    n_mk = con.execute("""SELECT count(*) FROM markets
        WHERE station_identifier=? AND dataset_version=?""", [ST, DSV]).fetchone()[0]
    print(f"  population_total (eventos EGLC en el almacen)        {n_ev}")
    print(f"  mercados                                            {n_mk}")

    el, ex, diag, pf = poblacion(con, DSV, ST)
    print(f"  eventos ELEGIBLES (resolved + particion + 1 ganadora) {diag['elegible']}")
    for k in sorted(diag):
        if k != "elegible":
            print(f"    {k:32s} {diag[k]}")
    print(f"  fechas tras deduplicar (station,target_date)         {len(el)}")

    obs = observaciones(con, ST)
    FC = pronosticos(con, ST)
    con_obs = sorted(td for td in el if td in obs)
    sin_obs = sorted(td for td in el if td not in obs)
    print(f"\n  population_with_observation                         {len(con_obs)}")
    print(f"  population_without_observation                      {len(sin_obs)}")
    print(f"    rango CON observacion   {min(con_obs)} .. {max(con_obs)}")
    print(f"    rango SIN observacion   {min(sin_obs)} .. {max(sin_obs)}")
    print("    -> los 50 NO se eliminan en silencio: son eventos validos fuera de la ventana")
    print("       en que existen observaciones (2026-04-08 -> 2026-08-23).")

    print("\n  ESCALERA por evento (de los elegibles):")
    lad = Counter(e["n_bandas"] for e in el.values())
    print(f"    total        {dict(sorted(lad.items()))}")
    lad_obs = Counter(el[td]["n_bandas"] for td in con_obs)
    print(f"    con obs      {dict(sorted(lad_obs.items()))}")
    for lead in (24, 9):
        d = [td for td in con_obs if (td, lead) in FC]
        lo = Counter(el[td]["n_bandas"] for td in d)
        print(f"    con obs+FC lead {lead:2d}  {len(d):3d} eventos  escaleras {dict(sorted(lo.items()))}")

    print("\n  LEADS disponibles:", sorted({l for _, l in FC}), " (t_asof = end_date 12:00 UTC - lead)")

    print("\n  ESTRATO ACEPTADO POR SETTLEMENT (se reporta, no se usa como filtro):")
    print("    17 eventos · 187 mercados · ('WU','P_WU_DailyObservations')   [A-285]")
    print("    los otros 170 eventos caen en estratos fail-closed DECLARADOS del nucleo.")
    print("    Level 1 NO filtra por esto: el target es winning_outcome, no nuestra liquidacion.")

    print("\n" + "=" * 88); print("HUELLAS DE LAS FILAS QUE ENTRAN"); print("=" * 88)
    print(f"  markets+outcomes  {huella_sql(con, '''SELECT m.event_id, CAST(m.end_date AS DATE),
        m.close_time, m.uma_resolution_status, o.band_label, m.winning_outcome, m.unit
        FROM markets m JOIN outcomes o ON o.market_id=m.market_id
             AND o.dataset_version=m.dataset_version
        WHERE m.station_identifier=? AND m.dataset_version=? AND o.outcome_label='Yes'
          AND o.band_label IS NOT NULL ORDER BY 1,2,5''', [ST, DSV])}")
    print(f"  observaciones     {huella_sql(con, '''SELECT observation_time, observed_value,
        observed_unit, tmax_observed, source FROM weather_observations WHERE station=?
        ORDER BY 1,5''', [ST])}")
    print(f"  pronosticos       {huella_sql(con, '''SELECT target_date, issue_time, available_at,
        forecast_tmax, forecast_p10, forecast_p90, model FROM weather_forecasts
        WHERE station=? AND forecast_tmax IS NOT NULL ORDER BY 1,2''', [ST])}")
    con.close()


if __name__ == "__main__":
    main()
