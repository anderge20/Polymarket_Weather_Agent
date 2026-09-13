#!/usr/bin/env python3
"""FASE C — UNIVERSO ELEGIBLE. Aplica los criterios A-F de `CRITERIOS_FASE_C.md`.

NINGUN criterio usa Brier, top-1, correlacion, MAE, B4, B4-S3, PnL, precios, volumen,
liquidez ni rentabilidad. Solo hechos de elegibilidad ex-ante.
No consulta precios, no calcula EV ni PnL, no toca produccion.
"""
from __future__ import annotations

import datetime as dt
import os
import sys
from collections import Counter, defaultdict

import duckdb

REPO = os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-merge")
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/fase2")
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/l1")
from weather_agent import stations                                        # noqa: E402
from weather_agent.polymarket.resolution import band_integrity, parse_band  # noqa: E402
from zoneinfo import ZoneInfo                                             # noqa: E402
from n075_poblacion import DB                                             # noqa: E402

MIN_TRAIN = 20
AUD0, AUD1 = dt.date(2026, 6, 3), dt.date(2026, 9, 4)


def main():
    con = duckdb.connect(DB, read_only=True); con.execute("SET TimeZone='UTC'")
    estaciones = [r[0] for r in con.execute(
        "SELECT DISTINCT station_identifier FROM markets WHERE dataset_version='markets_v2' "
        "ORDER BY 1").fetchall()]
    print(f"universo de partida: {len(estaciones)} estaciones de markets_v2\n")

    filas = []
    for st in estaciones:
        d = {"icao": st}
        # ---- A settlement
        src = [r[0] for r in con.execute(
            "SELECT DISTINCT resolution_source FROM markets WHERE station_identifier=? "
            "AND dataset_version='markets_v2'", [st]).fetchall()]
        d["A1_fuente_unica"] = len(src) == 1 and src[0] is not None
        ev = defaultdict(list); uma = defaultdict(set); uni = {}
        for eid, banda, u, gan, um, td in con.execute(
                """SELECT m.event_id, o.band_label, m.unit, m.winning_outcome,
                          m.uma_resolution_status, CAST(m.end_date AS DATE)
                   FROM markets m JOIN outcomes o
                     ON o.market_id=m.market_id AND o.dataset_version=m.dataset_version
                   WHERE m.station_identifier=? AND m.dataset_version='markets_v2'
                     AND o.outcome_label='Yes' AND o.band_label IS NOT NULL""", [st]).fetchall():
            ev[eid].append((banda, str(gan).strip().lower() == "yes", td))
            uma[eid].add(um); uni[eid] = u
        eleg = {}
        for eid, bs in ev.items():
            if uma[eid] != {"resolved"}:
                continue
            if sum(1 for _, g, _ in bs if g) != 1:
                continue
            if not band_integrity([b for b, _, _ in bs], uni[eid])["is_partition"]:
                continue
            eleg[eid] = (bs[0][2], len(bs), uni[eid])
        d["A_eventos_elegibles"] = len(eleg)
        # ---- C observacion
        r = con.execute("""SELECT count(*), count(DISTINCT observed_unit),
              any_value(observed_unit) FROM weather_observations WHERE station=?""", [st]).fetchone()
        d["C1_obs"] = r[0] > 0
        d["C2_unidad"] = r[2] if r[0] else None
        d["C2_celsius"] = (r[1] == 1 and r[2] == "C") if r[0] else False
        try:
            zona = ZoneInfo(stations.timezone_of(st)); d["C3_tz"] = True
        except Exception:                                                  # noqa: BLE001
            zona = None; d["C3_tz"] = False
        dias = set()
        if zona is not None:
            for (t,) in con.execute(
                    "SELECT observation_time FROM weather_observations WHERE station=?",
                    [st]).fetchall():
                dias.add(t.astimezone(zona).date())
        d["C4_dias_obs"] = len(dias)
        # ---- B forecast
        r = con.execute("""SELECT count(*), count(DISTINCT model), any_value(model)
              FROM weather_forecasts
              WHERE station=? AND forecast_tmax IS NOT NULL""", [st]).fetchone()
        d["B_filas_fc"] = r[0]
        d["B1_modelo"] = (r[1] == 1 and r[2] == "icon_seamless") if r[0] else False
        horas = sorted({h for (h,) in con.execute(
            "SELECT DISTINCT date_part('hour', issue_time) FROM weather_forecasts WHERE station=?",
            [st]).fetchall()})
        d["B3_dos_runs"] = set(horas) == {6, 18}
        fcd = {}
        for td, iss in con.execute("""SELECT target_date, issue_time FROM weather_forecasts
              WHERE station=? AND forecast_tmax IS NOT NULL""", [st]).fetchall():
            fcd.setdefault(td, set()).add(iss.hour)
        # ---- D puntuables (obs + FC + MIN_TRAIN), SIN mirar ningun resultado
        cand = sorted(td for eid, (td, n, u) in eleg.items() if td in dias and td in fcd)
        # la puerta de MIN_TRAIN: dias entrenables antes de cada candidato
        punt = []
        obs_dias = sorted(dias)
        for td in cand:
            entren = sum(1 for dd in obs_dias if dd < td - dt.timedelta(days=1) and dd in fcd)
            if entren >= MIN_TRAIN:
                punt.append(td)
        d["D1_puntuables"] = len(punt)
        lad = Counter(n for eid, (td, n, u) in eleg.items() if td in punt)
        d["F2_estrato_max"] = max(lad.values()) if lad else 0
        d["F2_escaleras"] = dict(sorted(lad.items()))
        d["E2_con_evidencia"] = sum(1 for td in punt if AUD0 <= td <= AUD1)
        filas.append(d)

    print(f"{'icao':6s} {'A_eleg':>7s} {'obsDias':>8s} {'unid':>5s} {'fcFilas':>8s} "
          f"{'2runs':>6s} {'modelo':>7s} {'PUNT':>5s} {'estrato':>8s}  ELEGIBLE")
    universo = []
    for d in sorted(filas, key=lambda x: -x["D1_puntuables"]):
        ok = (d["A1_fuente_unica"] and d["A_eventos_elegibles"] >= 30 and d["C1_obs"]
              and d["C2_celsius"] and d["C3_tz"] and d["C4_dias_obs"] >= 40
              and d["B1_modelo"] and d["B3_dos_runs"] and d["B_filas_fc"] >= 60
              and d["D1_puntuables"] >= 30 and d["F2_estrato_max"] >= 30)
        if ok:
            universo.append(d)
        if d["D1_puntuables"] > 0 or d["C4_dias_obs"] >= 40:
            print(f"{d['icao']:6s} {d['A_eventos_elegibles']:7d} {d['C4_dias_obs']:8d} "
                  f"{str(d['C2_unidad']):>5s} {d['B_filas_fc']:8d} "
                  f"{str(d['B3_dos_runs']):>6s} {str(d['B1_modelo']):>7s} "
                  f"{d['D1_puntuables']:5d} {d['F2_estrato_max']:8d}  {'SI' if ok else 'no'}")

    print(f"\n{'=' * 92}\nUNIVERSO ELEGIBLE: {len(universo)} estaciones\n{'=' * 92}")
    for d in universo:
        print(f"  {d['icao']}  puntuables {d['D1_puntuables']} · escaleras {d['F2_escaleras']} "
              f"· con evidencia F-3 {d['E2_con_evidencia']}/{d['D1_puntuables']}")
    print(f"\n--- POR QUE CAEN LAS DEMAS (recuento de la causa PRIMERA que las excluye) ---")
    causas = Counter()
    for d in filas:
        if d in universo:
            continue
        if not d["C1_obs"]: causas["sin observacion"] += 1
        elif not d["C2_celsius"]: causas[f"unidad != C ({d['C2_unidad']})"] += 1
        elif not d["C3_tz"]: causas["sin timezone"] += 1
        elif d["C4_dias_obs"] < 40: causas["< 40 dias de observacion"] += 1
        elif not d["B1_modelo"]: causas["modelo != icon_seamless"] += 1
        elif not d["B3_dos_runs"]: causas["no tiene las dos ejecuciones 06z/18z"] += 1
        elif d["B_filas_fc"] < 60: causas["< 60 filas de pronostico"] += 1
        elif d["A_eventos_elegibles"] < 30: causas["< 30 eventos elegibles"] += 1
        elif d["D1_puntuables"] < 30: causas["< 30 eventos PUNTUABLES"] += 1
        elif d["F2_estrato_max"] < 30: causas["ningun estrato con 30"] += 1
        else: causas["?"] += 1
    for k, v in causas.most_common():
        print(f"  {k:44s} {v}")
    con.close()


if __name__ == "__main__":
    main()
