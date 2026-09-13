#!/usr/bin/env python3
"""D0.9 · parte D — PRUEBA AISLADA de `labels.py`, como ESPECIFICACION del arreglo.

AISLADA A PROPOSITO: no entra en `tests/`. Si entrara, la suite del repositorio pasaria a
afirmar el comportamiento DEFECTUOSO como esperado — que es exactamente lo que hace hoy
`test_labels.py:119` al afirmar `series_mismatch` sobre una fila que lleva dentro el nombre
del ingestor, y por eso ese defecto lleva verde desde siempre.

Tres bloques, los tres EJECUTADOS con una fila construida como la escribe discovery:

  1. COMPORTAMIENTO ACTUAL         lo que `labels.py` hace hoy
  2. FALLO CON EL SUSTRATO ACTUAL  lo que hace con las filas que hay en pmw.duckdb
  3. COMPORTAMIENTO ESPERADO       lo que tiene que hacer despues del arreglo

El bloque 3 es la especificacion. Cuando el arreglo entre, el bloque 1 dejara de valer y
este fichero tendra que editarse: eso es deliberado. Es una especificacion, no una guarda
de regresion.

No toca `labels.py`, no toca produccion y no abre nada.
"""
from __future__ import annotations

import datetime as dt
import os
import sys

import duckdb

REPO = os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-merge")
sys.path.insert(0, os.path.join(REPO, "src"))
DB = "/Users/mariaaleu/workspace/Polymarket_Weather_Agent/data/pmw.duckdb"

from weather_agent import labels, settlement as st                    # noqa: E402
from weather_agent.polymarket import resolution as res                # noqa: E402

OK, KO = "OK ", "KO "
fallos = []


def afirmo(cond, etq, detalle=""):
    print(f"  {OK if cond else KO} {etq}" + (f"   {detalle}" if detalle else ""))
    if not cond:
        fallos.append(etq)


def intenta(terna):
    try:
        op = st.select_operator(*terna)
        return True, f"{op.__class__.__name__} {getattr(op, 'measurement_rule_code', '')}"
    except Exception as e:                                            # noqa: BLE001
        return False, f"{type(e).__name__}: {str(e)[:64]}"


def main() -> int:
    #: LA FILA COMO LA ESCRIBE DISCOVERY: el CODIGO en `measurement_rule_code`, la PROSA
    #: en `measurement_rule`. El fixture viejo ponia el codigo en la prosa, y por eso la
    #: suite no podia ver que la frontera alimentaba la prosa a la clave de particion.
    CODIGO = res.P_NOAA_TEMPCOL
    fila = {
        "market_id": "m-spec", "event_id": "e-spec",
        "contract_source": res.SRC_NOAA,
        "measurement_rule_code": CODIGO,
        "measurement_rule": res.MEASUREMENT_RULE_TEXT[CODIGO],
        "unit": "C", "rounding_rule": "whole degree",
        "station_identifier": "EGLC",
    }
    td = dt.date(2026, 5, 27)

    print("=" * 88)
    print("1. COMPORTAMIENTO ACTUAL de labels.py  (fila bien formada de discovery)")
    print("=" * 88)
    ctx = labels.context_for(fila, td)
    afirmo(ctx.measurement_rule_code == fila["measurement_rule"],
           "context_for pone la PROSA en measurement_rule_code",
           repr(ctx.measurement_rule_code)[:56] + "...")
    afirmo(ctx.measurement_rule_code != CODIGO,
           "...y por tanto NO es el codigo por el que parte el nucleo", f"codigo = {CODIGO!r}")
    ok, det = intenta((ctx.contract_source, ctx.measurement_rule_code, ctx.unit, ctx.rounding_rule))
    afirmo(not ok, "el nucleo RECHAZA la terna que labels construye", det)
    afirmo("context_out_of_snapshot" in det,
           "y la razon es context_out_of_snapshot, no una razon del dominio")

    afirmo("measurement_rule_code" not in labels.REQUIRED_COLUMNS["markets"],
           "REQUIRED_COLUMNS NO pide measurement_rule_code",
           str(labels.REQUIRED_COLUMNS["markets"]))
    afirmo("measurement_rule" in labels.REQUIRED_COLUMNS["markets"],
           "...y en su lugar pide measurement_rule, que el nucleo no usa")

    import inspect
    src_ms = inspect.getsource(labels.missing_substrate)
    afirmo("column_names" in src_ms and "count(" not in src_ms,
           "missing_substrate mira PRESENCIA de columna y no poblacion")
    src_of = inspect.getsource(labels.observations_for)
    afirmo('series=r["series"]' in src_of and "CORRESPONDENCE" not in src_of,
           "observations_for pasa el series CRUDO, sin traducir")

    print("\n" + "=" * 88)
    print("2. FALLO CON EL SUSTRATO ACTUAL  (filas reales de pmw.duckdb)")
    print("=" * 88)
    con = duckdb.connect(DB, read_only=True)
    con.execute("SET TimeZone='UTC'")
    n, nn = con.execute("""SELECT count(*), count(measurement_rule_code) FROM markets""").fetchone()
    afirmo(nn == 0, "measurement_rule_code es NULL en TODAS las filas de markets", f"{nn} de {n}")
    ns, nns = con.execute("""SELECT count(*), count(*) FILTER (WHERE series IN ?)
        FROM weather_observations""", [sorted({getattr(st, x) for x in dir(st)
                                               if x.startswith("SERIES_")})]).fetchone()
    afirmo(nns == 0, "ninguna fila de weather_observations lleva un series del nucleo",
           f"{nns} de {ns}")
    faltan = labels.missing_substrate(con)
    afirmo(faltan == [], "...y aun asi missing_substrate() dice que NO FALTA NADA",
           f"devuelve {faltan}")
    print("      ^ ESTE es el falso READY: el comprobador aprueba un almacen en el que")
    print("        la ruta no puede ejecutar ni un mercado.")
    con.close()

    print("\n" + "=" * 88)
    print("3. COMPORTAMIENTO ESPERADO DESPUES DEL ARREGLO  (la especificacion)")
    print("=" * 88)
    print("  E1  context_for debe leer `measurement_rule_code`, no `measurement_rule`.")
    ok, det = intenta((fila["contract_source"], fila["measurement_rule_code"],
                       fila["unit"], fila["rounding_rule"]))
    afirmo(ok, "E1  con el CODIGO, el nucleo ACEPTA la misma fila", det)

    print("  E2  observations_for debe traducir la serie por la UNICA fuente de verdad.")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "paper_cycle", os.path.join(REPO, "scripts", "paper_cycle.py"))
    pc = importlib.util.module_from_spec(spec); sys.modules["paper_cycle"] = pc
    spec.loader.exec_module(pc)
    crudo = "IEM_ASOS_METAR_1C_RT34"
    afirmo(pc.to_core_series(crudo) == st.SERIES_METAR_C,
           f"E2  {crudo} -> {pc.to_core_series(crudo)}",
           "hoy solo alcanzable importando desde scripts/")
    afirmo(crudo not in {getattr(st, x) for x in dir(st) if x.startswith("SERIES_")},
           "E2  el nombre crudo NO es aceptable para el nucleo, luego traducir es obligatorio")

    print("  E3  REQUIRED_COLUMNS debe pedir la terna por la que parte el nucleo.")
    esperado = ("contract_source", "measurement_rule_code")
    afirmo(set(esperado) <= set(pc._SETTLE_REQUIRED["markets"]),
           "E3  el otro comprobador ya pide exactamente eso",
           str(pc._SETTLE_REQUIRED["markets"]))

    print("  E4  READY debe significar que la ruta puede ejecutar, no que la columna existe.")
    afirmo(True, "E4  criterio escrito: presencia + no-null obligatorio + semantica + ruta")

    print("\n" + "=" * 88)
    print(f"RESULTADO: {'TODAS LAS AFIRMACIONES SE CUMPLEN' if not fallos else 'FALLAN: ' + str(fallos)}")
    print("=" * 88)
    print("Las del bloque 1 y 2 describen el DEFECTO de hoy; las del bloque 3 son el")
    print("objetivo del arreglo. Cuando el arreglo entre, el bloque 1 dejara de cumplirse")
    print("y este fichero tendra que editarse. Es una ESPECIFICACION, no una guarda.")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
