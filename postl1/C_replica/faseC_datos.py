#!/usr/bin/env python3
"""FASE C — CAPA DE LECTURA, identica a la congelada salvo UNA cosa: filtra por version.

POR QUE HACE FALTA. Las lecturas congeladas (`n075_poblacion.observaciones`,
`n075_poblacion.pronosticos`, `l1_2_baselines.observaciones_c`) NO filtran por
`dataset_version`. En Londres daba igual: `weather_forecasts` de EGLC tiene una sola
version y las dos SERIES de observacion conviven bajo la misma. RKSI tiene DOS versiones
de cada tabla -- la vieja `backfill_2b_v1` y la nueva `replica_rksi_v1` -- y leerlas
juntas mezclaria la replica con datos de fuera de la ventana congelada.

QUE CAMBIA Y QUE NO. Cambia UNA clausula WHERE. No cambia la regla del maximo por dia
LOCAL, ni la zona (sigue saliendo de `stations.timezone_of`), ni la seleccion de pasada
por `available_at <= t_asof`, ni los modelos, ni S3, ni la ventana de entrenamiento.
`equivalencia()` lo demuestra sobre EGLC: con la unica version que EGLC tiene, estas
funciones devuelven EXACTAMENTE lo que devuelven las congeladas.

EFECTO MEDIDO DEL FILTRO EN RKSI (antes de puntuar nada):
  * en los 95 dias de la ventana, `max` sobre TODAS las versiones == `replica_rksi_v1`
    en los 95 dias, cero diferencias;
  * la version vieja solo aporta 9 dias, TODOS anteriores al 2026-05-21, es decir fuera
    de la ventana congelada por ENMIENDA_VENTANA_FASE_C.md.
  El filtro no cambia ningun valor: cambia la VENTANA, que es justo lo que esta
  congelado.
"""
from __future__ import annotations

import datetime as dt
import os
import sys
from zoneinfo import ZoneInfo

REPO = os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-merge")
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/fase2")
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/l1")
from weather_agent import stations                     # noqa: E402
import n075_poblacion as POB                           # noqa: E402
import l1_2_baselines as BL                            # noqa: E402

DB = POB.DB
DSV_REPLICA = "replica_rksi_v1"


def zona_de(station: str) -> ZoneInfo:
    return ZoneInfo(stations.timezone_of(station))


def observaciones_banda(con, station: str, dsv: str | None = None) -> dict[dt.date, float]:
    """`observed_value` (rejilla del mercado) -> pertenencia a banda. Maximo por dia LOCAL."""
    zona = zona_de(station)
    q = ("SELECT observation_time, observed_value FROM weather_observations "
         "WHERE station = ?" + (" AND dataset_version = ?" if dsv else ""))
    obs: dict[dt.date, float] = {}
    for t, v in con.execute(q, [station] + ([dsv] if dsv else [])).fetchall():
        d = t.astimezone(zona).date()
        if d not in obs or v > obs[d]:
            obs[d] = v
    return obs


def observaciones_c(con, station: str, dsv: str | None = None):
    """`tmax_observed` (Celsius siempre) -> error de pronostico. A-283."""
    zona = zona_de(station)
    q = ("SELECT observation_time, tmax_observed FROM weather_observations "
         "WHERE station = ?" + (" AND dataset_version = ?" if dsv else ""))
    o: dict[dt.date, float] = {}
    for t, v in con.execute(q, [station] + ([dsv] if dsv else [])).fetchall():
        d = t.astimezone(zona).date()
        o[d] = max(o.get(d, float("-inf")), float(v))
    return o, zona


def pronosticos(con, station: str, dsv: str | None = None, leads=(24, 9)):
    """La pasada MAS FRESCA cuyo `available_at` <= t_asof. Nunca `issue_time <= t`."""
    q = ("SELECT target_date, available_at, forecast_tmax FROM weather_forecasts "
         "WHERE station = ? AND forecast_tmax IS NOT NULL"
         + (" AND dataset_version = ?" if dsv else "")
         + " ORDER BY target_date, issue_time")
    FC: dict[tuple[dt.date, int], tuple[dt.datetime, float]] = {}
    for td, av, tm in con.execute(q, [station] + ([dsv] if dsv else [])).fetchall():
        for lead in leads:
            t = POB.__dict__["dt"].datetime.combine(td, dt.time(12), dt.timezone.utc) \
                - dt.timedelta(hours=lead)
            if av <= t and ((td, lead) not in FC or av > FC[(td, lead)][0]):
                FC[(td, lead)] = (av, tm)
    return FC


def equivalencia(con, station: str = "EGLC") -> list[str]:
    """Con UNA sola version, estas funciones == las congeladas. Devuelve los fallos."""
    malos = []
    if observaciones_banda(con, station) != POB.observaciones(con, station):
        malos.append("observaciones_banda != n075_poblacion.observaciones")
    a, za = observaciones_c(con, station)
    b, zb = BL.observaciones_c(con, station)
    if a != b or za != zb:
        malos.append("observaciones_c != l1_2_baselines.observaciones_c")
    if pronosticos(con, station) != POB.pronosticos(con, station):
        malos.append("pronosticos != n075_poblacion.pronosticos")
    return malos
