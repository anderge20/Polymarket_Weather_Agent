#!/usr/bin/env python3
"""NIVEL 0.75 — construccion de la POBLACION segun la regla definitiva (A-275 + encargo).

Una sola implementacion, parametrizada por `dataset_version` de `markets`. Todo lo demas
es identico entre brazos: observaciones, pronosticos, definicion de fecha objetivo,
elegibilidad, desempate y deduplicacion.

REGLA (aceptada por el usuario, punto 2 de su mensaje):
  * (station, target_date) es la dimension de DEDUPLICACION.
  * event_id sigue siendo la identidad primaria.
  * Elegible = resolved + exactamente una ganadora + particion completa.
  * Si hay varios elegibles, escoger el close_time mas proximo POR ENCIMA de la fecha objetivo.
  * Si ninguno es elegible, excluir el (station,date), contabilizarlo y nombrarlo.
  * `arch-` no participa en la seleccion; solo describe el fenomeno.

FECHA OBJETIVO = CAST(end_date AS DATE). Verificado contra el slug en 2 804 de 2 804
filas de las dos versiones, y `end_date` es 12:00 UTC en las 1 997, asi que no hay
riesgo de zona horaria al proyectar a fecha.
"""
from __future__ import annotations

import datetime as dt
import os
import sys
from collections import Counter
from zoneinfo import ZoneInfo

import duckdb

REPO = os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-main")
sys.path.insert(0, os.path.join(REPO, "src"))
from weather_agent.polymarket.resolution import parse_band   # noqa: E402

LON = ZoneInfo("Europe/London")
DB = os.environ.get("PMW_DB", "/Users/mariaaleu/workspace/Polymarket_Weather_Agent/data/pmw.duckdb")


def particion(bandas) -> bool:
    ab = [b for b in bandas if b[0] is None]
    ar = [b for b in bandas if b[1] is None]
    if len(ab) != 1 or len(ar) != 1:
        return False
    cer = sorted(int(a) for a, b in bandas if a is not None and b is not None and a == b)
    return cer == list(range(int(ab[0][1]) + 1, int(ar[0][0])))


def observaciones(con, station="EGLC"):
    """Maximo por DIA LOCAL sobre TODAS las series. Identico en los dos brazos.

    Medido: `max` sobre las dos series coincide con la serie RT34 sola en los 138 dias
    (las 16 diferencias son todas RT34 = METAR + 1,0). La regla declarada es RT34, y el
    `max` la reproduce exactamente en estos datos -- hecho medido, no supuesto.
    """
    obs = {}
    for t, v in con.execute(
            "SELECT observation_time, observed_value FROM weather_observations WHERE station = ?",
            [station]).fetchall():
        d = t.astimezone(LON).date()
        if d not in obs or v > obs[d]:
            obs[d] = v
    return obs


def pronosticos(con, station="EGLC", leads=(24, 9)):
    def tasof(td, lead):
        return dt.datetime.combine(td, dt.time(12), dt.timezone.utc) - dt.timedelta(hours=lead)
    FC = {}
    for td, av, tm in con.execute(
            "SELECT target_date, available_at, forecast_tmax FROM weather_forecasts "
            "WHERE station = ? AND forecast_tmax IS NOT NULL ORDER BY target_date, issue_time",
            [station]).fetchall():
        for lead in leads:
            if av <= tasof(td, lead) and ((td, lead) not in FC or av > FC[(td, lead)][0]):
                FC[(td, lead)] = (av, tm)
    return FC


def poblacion(con, dsv, station="EGLC"):
    """Devuelve (elegidos, diag) donde elegidos: fecha -> dict del evento escogido."""
    ev = {}
    for eid, td, ct, uma, banda, gan in con.execute(
            """SELECT m.event_id, CAST(m.end_date AS DATE), m.close_time,
                      m.uma_resolution_status, o.band_label, m.winning_outcome
               FROM markets m JOIN outcomes o ON o.market_id = m.market_id
                                              AND o.dataset_version = m.dataset_version
               WHERE m.station_identifier = ? AND m.dataset_version = ?
                 AND o.band_label IS NOT NULL AND o.outcome_label = 'Yes'""",
            [station, dsv]).fetchall():
        lo, hi = parse_band(banda, "C")
        e = ev.setdefault(eid, {"event_id": eid, "fecha": td, "close": ct,
                                "uma": set(), "bandas": []})
        e["uma"].add(uma)
        e["bandas"].append((lo, hi, str(gan).strip().lower() == "yes"))
        if ct is not None and (e["close"] is None or ct > e["close"]):
            e["close"] = ct

    diag = Counter()
    por_fecha = {}
    for e in ev.values():
        bandas = [(lo, hi) for lo, hi, _ in e["bandas"]]
        gan = sum(1 for _, _, w in e["bandas"] if w)
        e["n_bandas"] = len(bandas)
        e["elegible"] = True
        if e["uma"] != {"resolved"}:
            e["elegible"] = False; diag["no_resolved"] += 1
        elif not particion(bandas):
            e["elegible"] = False; diag["particion_incompleta"] += 1
        elif gan != 1:
            e["elegible"] = False
            diag["sin_ganadora" if gan == 0 else "ganadoras_multiples"] += 1
        else:
            diag["elegible"] += 1
        por_fecha.setdefault(e["fecha"], []).append(e)

    elegidos, excluidos = {}, {}
    for td, es in por_fecha.items():
        cands = [e for e in es if e["elegible"]]
        if not cands:
            excluidos[td] = es
            diag["fecha_sin_elegible"] += 1
            continue
        # close_time mas proximo POR ENCIMA de la fecha objetivo
        corte = dt.datetime.combine(td + dt.timedelta(days=1), dt.time(0), LON).astimezone(dt.timezone.utc)
        arriba = [e for e in cands if e["close"] is not None and e["close"] > corte]
        pool = arriba or cands
        elegidos[td] = min(pool, key=lambda e: (e["close"] is None, e["close"] or corte))
        if len(cands) > 1:
            diag["fecha_con_desempate"] += 1
    return elegidos, excluidos, diag, por_fecha


def main():
    con = duckdb.connect(DB, read_only=True)
    con.execute("SET TimeZone='UTC'")
    obs = observaciones(con)
    FC = pronosticos(con)
    print(f"observaciones: {len(obs)} dias locales   {min(obs)} -> {max(obs)}")
    print(f"pronosticos: {len(FC)} pares (fecha,lead)   "
          f"lead24 {sum(1 for k in FC if k[1]==24)}  lead9 {sum(1 for k in FC if k[1]==9)}")
    for dsv in ("backfill_2b_v1", "markets_v2"):
        el, ex, diag, pf = poblacion(con, dsv)
        lad = Counter(e["n_bandas"] for e in el.values())
        print(f"\n=== {dsv}")
        print(f"  eventos totales      {sum(len(v) for v in pf.values()):5d}")
        print(f"  fechas distintas     {len(pf):5d}")
        for k in sorted(diag): print(f"  {k:24s} {diag[k]:5d}")
        print(f"  fechas ELEGIDAS      {len(el):5d}   escaleras {dict(sorted(lad.items()))}")
        print(f"  fechas EXCLUIDAS     {len(ex):5d}")
        con_obs = sum(1 for td in el if td in obs)
        con_fc24 = sum(1 for td in el if td in obs and (td, 24) in FC)
        con_fc9 = sum(1 for td in el if td in obs and (td, 9) in FC)
        print(f"  con observacion      {con_obs:5d}   con obs+FC24 {con_fc24}   con obs+FC9 {con_fc9}")
    con.close()


if __name__ == "__main__":
    main()
