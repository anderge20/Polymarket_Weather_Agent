#!/usr/bin/env python3
"""Particion GENERALIZADA a bandas de anchura arbitraria, y la prueba de que no cambia
nada donde ya funcionaba.

`n075_poblacion.particion()` exige que las bandas interiores sean ENTEROS SUELTOS
(`a == b`). Eso es la forma de la escalera en Celsius. Las escaleras estadounidenses son
de 2 °F (`'54-55°F'`), asi que la prueba las rechaza TODAS -- y por eso las 12 estaciones
en Fahrenheit salian `SIN_EVENTO_ELEGIBLE` en la primera pasada de #63. Era un limite de
mi instrumento, no un hecho sobre los datos.

La version general pide que los intervalos cerrados TESELEN el hueco entre la banda
abierta por abajo y la abierta por arriba, sin huecos ni solapes, con la anchura que sea.
Sobre una escalera de enteros sueltos es la MISMA condicion.
"""
from __future__ import annotations


def particion_general(bandas) -> bool:
    ab = [b for b in bandas if b[0] is None]
    ar = [b for b in bandas if b[1] is None]
    if len(ab) != 1 or len(ar) != 1:
        return False
    lo_ini = ab[0][1] + 1
    hi_fin = ar[0][0] - 1
    cerradas = sorted((a, b) for a, b in bandas if a is not None and b is not None)
    if not cerradas:
        return lo_ini > hi_fin
    if cerradas[0][0] != lo_ini or cerradas[-1][1] != hi_fin:
        return False
    for (a1, b1), (a2, _) in zip(cerradas, cerradas[1:]):
        if b1 < a1 or a2 != b1 + 1:
            return False
    return True


if __name__ == "__main__":
    import os, sys
    import duckdb
    sys.path.insert(0, os.environ.get("PMW_REPO",
        "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-main") + "/src")
    sys.path.insert(0, "/Users/mariaaleu/pmw-e2/fase2")
    from weather_agent.polymarket.resolution import parse_band
    from n075_poblacion import DB, particion

    con = duckdb.connect(DB, read_only=True); con.execute("SET TimeZone='UTC'")
    ev = {}
    for eid, banda, unidad in con.execute(
            """SELECT m.event_id, o.band_label, m.unit FROM markets m JOIN outcomes o
               ON o.market_id=m.market_id AND o.dataset_version=m.dataset_version
               WHERE m.dataset_version='markets_v2' AND o.outcome_label='Yes'
               AND o.band_label IS NOT NULL""").fetchall():
        ev.setdefault(eid, []).append(parse_band(banda, unidad or "C"))
    d = a = solo_gen = solo_vieja = 0
    for eid, bs in ev.items():
        v, g = particion(bs), particion_general(bs)
        d += 1; a += v == g
        solo_gen += (g and not v); solo_vieja += (v and not g)
    print(f"eventos comparados         {d}")
    print(f"las dos coinciden          {a}")
    print(f"solo la GENERAL acepta     {solo_gen}   <- las escaleras de anchura > 1")
    print(f"solo la VIEJA acepta       {solo_vieja}  <- tiene que ser 0")
    assert solo_vieja == 0, "la generalizacion NO es conservadora"
    print("\nLA GENERALIZACION ES CONSERVADORA: no rechaza nada que la vieja aceptara.")
