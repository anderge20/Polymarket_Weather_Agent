#!/usr/bin/env python3
"""D0.9 · EJECUCION DE LA CADENA forecast -> observation -> label -> probability -> scoring.

No es inspeccion estatica: cada frontera se EJECUTA con las entradas reales del almacen y
se mira lo que sale, incluido el comportamiento ante NULL.

No modela, no entrena, no selecciona modelos, no calcula edge ni PnL, no busca umbrales,
no toca produccion y no abre trading.
"""
from __future__ import annotations

import datetime as dt
import os
import sys
import traceback
from collections import Counter

import duckdb

REPO = os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-merge")
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/fase2")
DB = "/Users/mariaaleu/workspace/Polymarket_Weather_Agent/data/pmw.duckdb"

from weather_agent import labeling, labels, observations as obsmod, settlement as st  # noqa: E402
from weather_agent.polymarket import resolution as res                                 # noqa: E402

SEP = "=" * 88


def titulo(t):
    print(f"\n{SEP}\n{t}\n{SEP}")


def nulos(con, tabla, cols, where="", params=None):
    sel = ", ".join([f"count(*) AS n"] + [f"count({c}) AS {c}" for c in cols])
    r = con.execute(f"SELECT {sel} FROM {tabla} {where}", params or []).fetchone()
    n = r[0]
    return n, {c: n - v for c, v in zip(cols, r[1:])}


def main():
    con = duckdb.connect(DB, read_only=True)
    con.execute("SET TimeZone='UTC'")

    # ----------------------------------------------------------------- 1. FORECAST
    titulo("FRONTERA 1 — FORECAST.  Entradas reales: weather_forecasts")
    n, nul = nulos(con, "weather_forecasts",
                   ["station", "target_date", "issue_time", "available_at",
                    "forecast_tmax", "dataset_version"])
    print(f"  filas {n}   NULL por columna: { {k: v for k, v in nul.items() if v} or 'ninguno'}")
    cols = [r[1] for r in con.execute("PRAGMA table_info('weather_forecasts')").fetchall()]
    print(f"  ¿existe columna de UNIDAD?  {[c for c in cols if 'unit' in c.lower()] or 'NO'}")
    print("  -> `forecast_tmax` no lleva unidad declarada en la fila. La semantica vive fuera.")
    r = con.execute("SELECT min(forecast_tmax), max(forecast_tmax) FROM weather_forecasts").fetchone()
    print(f"  rango global de forecast_tmax: {r[0]} .. {r[1]}")
    porst = con.execute("""SELECT station, min(forecast_tmax), max(forecast_tmax), count(*)
        FROM weather_forecasts GROUP BY 1 ORDER BY 3 DESC LIMIT 4""").fetchall()
    for x in porst:
        print(f"     {x[0]:6s} [{x[1]:6.1f} .. {x[2]:6.1f}]  n={x[3]}")

    # ----------------------------------------------------------------- 2. OBSERVATION
    titulo("FRONTERA 2 — OBSERVATION.  Entradas reales: weather_observations")
    n, nul = nulos(con, "weather_observations",
                   ["station", "observation_time", "observed_value", "observed_unit",
                    "series", "available_at", "record_version", "dataset_version"])
    print(f"  filas {n}   NULL por columna: { {k: v for k, v in nul.items() if v} or 'ninguno'}")
    print("  unidades presentes:",
          con.execute("SELECT observed_unit, count(*) FROM weather_observations GROUP BY 1").fetchall())
    print("  series presentes  :",
          con.execute("SELECT series, count(*) FROM weather_observations GROUP BY 1 ORDER BY 2 DESC").fetchall())
    print("\n  TRADUCCION DE SERIES — lo que el nucleo acepta:")
    del_nucleo = sorted({getattr(st, nm) for nm in dir(st) if nm.startswith("SERIES_")})
    del_almacen = sorted(x[0] for x in con.execute(
        "SELECT DISTINCT series FROM weather_observations").fetchall())
    print(f"    nucleo   {del_nucleo}")
    print(f"    almacen  {del_almacen}")
    print(f"    INTERSECCION: {sorted(set(del_nucleo) & set(del_almacen)) or 'VACIA'}")

    # ----------------------------------------------------------------- 3. LABEL
    titulo("FRONTERA 3 — LABEL.  TRES implementaciones distintas, ejecutadas")
    fila = con.execute("""SELECT market_id, event_id, contract_source, measurement_rule_code,
               measurement_rule, unit, rounding_rule, station_identifier,
               winning_outcome, resolution_timestamp, uma_resolution_status,
               CAST(end_date AS DATE) AS td
        FROM markets WHERE station_identifier='EGLC' AND dataset_version='markets_v2'
          AND winning_outcome='Yes' ORDER BY end_date LIMIT 1""").fetchdf().to_dict("records")[0]
    print("  fila real de markets (EGLC, markets_v2, ganadora):")
    for k in ("market_id", "event_id", "contract_source", "measurement_rule_code",
              "measurement_rule", "unit", "rounding_rule", "winning_outcome",
              "resolution_timestamp", "uma_resolution_status"):
        v = fila[k]
        print(f"    {k:24s} {repr(v)[:70]}")

    print("\n  (3a) markets.winning_outcome — la que USA el Nivel 1")
    r = con.execute("""SELECT count(*), count(winning_outcome) FROM markets
        WHERE dataset_version='markets_v2'""").fetchone()
    print(f"       filas {r[0]}  no-NULL {r[1]}  -> NULL {r[0]-r[1]}")

    print("\n  (3b) weather_agent.labeling.build_label — modulo huerfano, EJECUTADO")
    out = labeling.build_label(
        prediction_time=dt.datetime(2026, 5, 26, 12, tzinfo=dt.timezone.utc),
        resolution_timestamp=fila["resolution_timestamp"],
        winning_outcome=fila["winning_outcome"])
    print(f"       con la fila REAL -> {out}")
    print("       docstring: «Returns None when: the market is unresolved»")
    print(f"       pero uma_resolution_status = {fila['uma_resolution_status']!r} y "
          f"winning_outcome = {fila['winning_outcome']!r}")
    out2 = labeling.build_label(
        prediction_time=dt.datetime(2026, 5, 26, 12, tzinfo=dt.timezone.utc),
        resolution_timestamp=dt.datetime(2026, 5, 28, 0, tzinfo=dt.timezone.utc),
        winning_outcome=fila["winning_outcome"])
    print(f"       con resolution_timestamp INVENTADO -> {out2}")

    print("\n  (3c) weather_agent.labels.context_for + settlement.select_operator — EJECUTADO")
    ctx = labels.context_for(fila, fila["td"])
    print(f"       measurement_rule_code que llega al nucleo: {repr(ctx.measurement_rule_code)[:60]}")
    print(f"       el CODIGO de la fila era                 : {fila['measurement_rule_code']!r}")
    for etiqueta, terna in (("lo que pasa labels",
                             (ctx.contract_source, ctx.measurement_rule_code, ctx.unit, ctx.rounding_rule)),
                            ("la terna de la FILA",
                             (fila["contract_source"], fila["measurement_rule_code"],
                              fila["unit"], fila["rounding_rule"]))):
        try:
            op = st.select_operator(*terna)
            print(f"       {etiqueta:22s} -> {op.__class__.__name__} "
                  f"{getattr(op, 'measurement_rule_code', '')}")
        except Exception as e:                                    # noqa: BLE001
            print(f"       {etiqueta:22s} -> {type(e).__name__}: {str(e)[:90]}")

    # ----------------------------------------------------------------- NULL
    titulo("COMPORTAMIENTO ANTE NULL — ejecutado, no supuesto")
    casos = [
        ("terna completa y correcta", (res.SRC_NOAA, res.P_NOAA_TempColumn if hasattr(res, 'P_NOAA_TempColumn') else res.P_NOAA_TEMPCOL, "C", "whole degree")),
        ("measurement_rule_code = None", (res.SRC_NOAA, None, "C", "whole degree")),
        ("measurement_rule_code = ''", (res.SRC_NOAA, "", "C", "whole degree")),
        ("contract_source = None", (None, res.P_NOAA_TEMPCOL, "C", "whole degree")),
        ("los dos None (lo que hay HOY)", (None, None, "C", "whole degree")),
        ("unit = None", (res.SRC_NOAA, res.P_NOAA_TEMPCOL, None, "whole degree")),
    ]
    for etq, terna in casos:
        try:
            op = st.select_operator(*terna)
            print(f"  {etq:34s} -> OK  {op.__class__.__name__}")
        except Exception as e:                                     # noqa: BLE001
            print(f"  {etq:34s} -> {type(e).__name__}: {str(e)[:78]}")

    con.close()


if __name__ == "__main__":
    main()
