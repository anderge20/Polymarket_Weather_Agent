#!/usr/bin/env python3
"""D10 · punto 9 — DOS OPERACIONES DISTINTAS SOBRE LA MISMA TEMPERATURA.

Categoria C (analisis). No toca produccion, no modela, no calcula edge ni PnL.

LO QUE DEMUESTRA, con filas REALES de las dos clases de estacion:

  (1) PERTENENCIA A BANDA   se resuelve en la UNIDAD CONTRACTUAL DEL MERCADO,
                            con `observed_value` sobre la rejilla de la fuente.
  (2) ERROR DE PRONOSTICO   se resuelve en CELSIUS, con `tmax_observed` contra
                            `forecast_tmax`, que es Celsius en las 49 estaciones.

  (3) SON DOS OPERACIONES DISTINTAS: la misma fila da valores distintos segun cual
      pidas, y reutilizar UNA sola variable para las dos es el defecto de A-283.

En una estacion Celsius las dos coinciden y el defecto es invisible. Por eso el caso
que manda es el de Fahrenheit, y por eso este guion mira las dos.
"""
from __future__ import annotations

import os
import sys

import duckdb

REPO = os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-merge")
sys.path.insert(0, os.path.join(REPO, "src"))
DB = "/Users/mariaaleu/workspace/Polymarket_Weather_Agent/data/pmw.duckdb"

from weather_agent.polymarket.resolution import parse_band                 # noqa: E402

fallos: list[str] = []


def afirmo(cond, etq, det=""):
    print(f"  {'OK ' if cond else 'KO '} {etq}" + (f"   {det}" if det else ""))
    if not cond:
        fallos.append(etq)


def banda_de(v, bandas):
    for lo, hi, lbl in bandas:
        if (lo is None or v >= lo) and (hi is None or v <= hi):
            return lbl
    return None


def caso(con, station):
    print(f"\n{'=' * 84}\n{station}\n{'=' * 84}")
    fila = con.execute("""
        SELECT o.station, CAST(o.observation_time AS DATE) d, o.observed_value, o.observed_unit,
               o.tmax_observed, f.forecast_tmax, any_value(m.unit) mkt_unit
          FROM weather_observations o
          JOIN weather_forecasts f ON f.station = o.station
               AND f.target_date = CAST(o.observation_time AS DATE)
          JOIN markets m ON m.station_identifier = o.station
               AND CAST(m.end_date AS DATE) = CAST(o.observation_time AS DATE)
               AND m.dataset_version = 'markets_v2'
         WHERE o.station = ?
         GROUP BY 1,2,3,4,5,6 ORDER BY 2 LIMIT 1""", [station]).fetchone()
    if fila is None:
        print("  (sin fila comparable)"); return
    st, d, ov, ou, tc, fc, mu = fila
    print(f"  fecha {d}   observed_value {ov:.1f} {ou}   tmax_observed {tc:.2f} C   "
          f"forecast_tmax {fc:.2f} C   unidad del mercado {mu}")

    bandas = [(*parse_band(b, mu), b) for (b,) in con.execute("""
        SELECT DISTINCT o.band_label FROM markets m JOIN outcomes o
          ON o.market_id = m.market_id AND o.dataset_version = m.dataset_version
         WHERE m.station_identifier = ? AND m.dataset_version = 'markets_v2'
           AND CAST(m.end_date AS DATE) = ? AND o.outcome_label = 'Yes'
           AND o.band_label IS NOT NULL""", [station, d]).fetchall()]
    ganadora = con.execute("""
        SELECT o.band_label FROM markets m JOIN outcomes o
          ON o.market_id = m.market_id AND o.dataset_version = m.dataset_version
         WHERE m.station_identifier = ? AND m.dataset_version = 'markets_v2'
           AND CAST(m.end_date AS DATE) = ? AND o.outcome_label = 'Yes'
           AND m.winning_outcome = 'Yes' LIMIT 1""", [station, d]).fetchone()

    afirmo(mu == ou, "(1) la unidad del MERCADO coincide con la de `observed_value`",
           f"mercado {mu} · observacion {ou}")
    b_correcta = banda_de(ov, bandas)
    b_con_celsius = banda_de(tc, bandas)
    print(f"      banda con observed_value ({ov:.1f} {mu}) : {b_correcta}")
    print(f"      banda con tmax_observed  ({tc:.2f} C)    : {b_con_celsius}")
    if ou == "F":
        afirmo(b_correcta != b_con_celsius,
               "(3) en Fahrenheit las dos lecturas dan bandas DISTINTAS -> no son la misma variable")
    else:
        afirmo(b_correcta == b_con_celsius,
               "(3) en Celsius coinciden -> por eso el defecto es invisible aqui")
    if ganadora:
        afirmo(b_correcta == ganadora[0],
               "(1) la banda de `observed_value` es la GANADORA declarada", f"{ganadora[0]}")

    err_bien = tc - fc
    err_mal = ov - fc
    print(f"      error CORRECTO   tmax_observed - forecast_tmax = {err_bien:+.2f} C")
    print(f"      error INCORRECTO observed_value - forecast_tmax = {err_mal:+.2f}")
    afirmo(abs(err_bien) < 15.0, "(2) el error en Celsius es de magnitud meteorologica",
           f"{err_bien:+.2f} C")
    if ou == "F":
        afirmo(abs(err_mal) > 30.0,
               "(2) el error sin convertir NO lo es, y no levanta ninguna excepcion",
               f"{err_mal:+.2f}")
    else:
        afirmo(abs(err_mal - err_bien) < 1e-9,
               "(2) en Celsius las dos formas coinciden exactamente")


def main() -> int:
    con = duckdb.connect(DB, read_only=True)
    con.execute("SET TimeZone='UTC'")
    for st in ("EGLC", "KHOU", "KORD"):
        caso(con, st)
    con.close()
    print(f"\n{'=' * 84}")
    print("RESULTADO:", "TODAS LAS AFIRMACIONES SE CUMPLEN" if not fallos else f"FALLAN {fallos}")
    print("=" * 84)
    print("REGLA: `observed_value` (rejilla del mercado) para PERTENENCIA A BANDA;")
    print("       `tmax_observed` (Celsius) para el ERROR contra `forecast_tmax`.")
    print("       Son dos variables, no una. A-283.")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
