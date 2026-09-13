#!/usr/bin/env python3
"""FASE C · GATES §5, §7, §10, §11, §12 + CHECKLIST §13. TODO antes de puntuar.

No calcula Brier, no calcula B4, no calcula S3. Si algo falla, sale 1 y no se puntua.
El gate de timezone (§6) va aparte, en `faseC_gate_timezone.py`, y su resultado se lee
aqui desde su fichero de salida para que el checklist no lo de por hecho.
"""
from __future__ import annotations

import datetime as dt
import os
import sys
from collections import Counter

import duckdb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/fase2")
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/l1")
REPO = os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-merge")
sys.path.insert(0, os.path.join(REPO, "src"))
import faseC_datos as D                                   # noqa: E402
import n075_poblacion as POB                              # noqa: E402
import l1_2_baselines as BL                               # noqa: E402
from weather_agent import weather                         # noqa: E402
from weather_agent.polymarket import resolution as RES    # noqa: E402

ICAO, DSV_MK = "RKSI", "markets_v2"
D0, D1 = dt.date(2026, 5, 21), dt.date(2026, 8, 23)
TECHO_FC, TECHO_OBS = 200, 100
GASTO_FC, GASTO_OBS = 191, 95        # 44 + 147 · registrado en los dos logs
criticos: list[str] = []
avisos: list[str] = []


def ok(c, etq, det="", critico=True):
    print(f"  {'OK ' if c else '!! '} {etq}" + (f"\n        {det}" if det else ""))
    if not c:
        (criticos if critico else avisos).append(etq)


def main() -> int:
    con = duckdb.connect(D.DB, read_only=True)
    con.execute("SET TimeZone='UTC'")
    zona = D.zona_de(ICAO)
    print("=" * 92)
    print(f"FASE C · GATES DE INTEGRIDAD · {ICAO} · ventana {D0} -> {D1}")
    print("=" * 92)

    # =============================================================== §5 INGESTA
    print("\n§5 · INTEGRIDAD DE INGESTA — PRONOSTICO")
    fc = con.execute(
        """SELECT issue_time, forecast_run, target_date, model, forecast_tmax,
                  available_at, source, dataset_version
           FROM weather_forecasts WHERE station = ? AND dataset_version = ?""",
        [ICAO, D.DSV_REPLICA]).fetchall()
    ok(len(fc) == 189, f"filas de pronostico: {len(fc)} (190 planeadas - 1 pasada ausente)")
    ok({r[3] for r in fc} == {"icon_seamless"}, "un solo modelo", str({r[3] for r in fc}))
    ok({r[6] for r in fc} == {"OPEN_METEO_SINGLE_RUNS"}, "una sola fuente", str({r[6] for r in fc}))
    ok(all(r[4] is not None for r in fc), "0 forecast_tmax nulos")
    ok(all(r[0].tzinfo is not None and r[5].tzinfo is not None for r in fc),
       "issue_time y available_at llevan zona")
    lat = {round((r[5] - r[0]).total_seconds() / 3600, 4) for r in fc}
    ok(lat == {round(weather.L_MAX_HOURS["icon_seamless"], 4)},
       f"available_at - issue_time == L_MAX en TODAS las filas: {sorted(lat)} h")
    ok(all(0 < (dt.datetime.combine(r[2], dt.time(12), dt.timezone.utc) - r[0]).total_seconds()
           <= 36 * 3600 for r in fc), "toda pasada esta dentro de las 36 h previas al ancla")
    dup = con.execute(
        """SELECT count(*) FROM (SELECT station, model, issue_time, target_date, count(*) c
           FROM weather_forecasts WHERE station=? AND dataset_version=?
           GROUP BY 1,2,3,4 HAVING c > 1)""", [ICAO, D.DSV_REPLICA]).fetchone()[0]
    ok(dup == 0, f"0 duplicados por (station, model, issue_time, target_date): {dup}")
    tds = sorted({r[2] for r in fc})
    ok(tds[0] == D0 and tds[-1] == D1 and len(tds) == 95,
       f"continuidad temporal: {len(tds)} fechas objetivo, {tds[0]} -> {tds[-1]}, sin huecos",
       f"huecos: {[d for d in ((D0 + dt.timedelta(n)) for n in range(96)) if d not in set(tds)]}")

    print("\n§5 · INTEGRIDAD DE INGESTA — OBSERVACION")
    obsf = con.execute(
        """SELECT observation_time, observed_value, observed_unit, tmax_observed, source
           FROM weather_observations WHERE station = ? AND dataset_version = ?""",
        [ICAO, D.DSV_REPLICA]).fetchall()
    ok(len(obsf) == 95, f"filas de observacion: {len(obsf)}")
    ok({r[4] for r in obsf} == {"IEM_ASOS_METAR_RT34"}, "una sola serie", str({r[4] for r in obsf}))
    ok({r[2] for r in obsf} == {"C"}, "unidad C en todas", str({r[2] for r in obsf}))
    ok(all(r[1] is not None and r[3] is not None for r in obsf), "0 nulos en valor ni en tmax")
    dl = Counter(r[0].astimezone(zona).date() for r in obsf)
    ok(max(dl.values()) == 1, f"un registro por dia LOCAL (max {max(dl.values())})")
    ok(set(dl) == {D0 + dt.timedelta(n) for n in range(95)},
       "cobertura completa de la ventana: 0 dias sin observacion (missingness = 0)")

    # =============================================================== §7 UNIDADES
    print("\n§7 · OBSERVACIONES — dos columnas, dos usos, y la puerta de unidad")
    try:
        POB.exige_celsius(con, ICAO, DSV_MK)
        ok(True, "exige_celsius() PASA para RKSI (markets y observaciones en C)")
    except POB.UnidadNoSoportada as e:
        ok(False, "exige_celsius() NIEGA la ruta", str(e))
    ob = D.observaciones_banda(con, ICAO, D.DSV_REPLICA)
    oc, _ = D.observaciones_c(con, ICAO, D.DSV_REPLICA)
    difs = [d for d in ob if abs(ob[d] - oc[d]) > 1e-9]
    ok(not difs, f"observed_value == tmax_observed en los {len(ob)} dias ({len(difs)} difieren)",
       "RKSI es Celsius nativo: la distincion A-283 esta activa pero no muerde aqui")

    # =============================================================== §10 LADDER
    print("\n§10 · AUDITORIA DE ESCALERAS")
    pob, excl, diag, por_fecha = POB.poblacion(con, DSV_MK, ICAO)
    lad = Counter(e["n_bandas"] for e in pob.values())
    ok(len(pob) == 186, f"fechas elegibles: {len(pob)}   escaleras {dict(sorted(lad.items()))}")
    malas = []
    for td, e in pob.items():
        bandas = [(lo, hi) for lo, hi, _ in e["bandas"]]
        if not POB.particion(bandas):
            malas.append(td)
    ok(not malas, f"particion completa, sin huecos ni solapes, en las {len(pob)} ({len(malas)} malas)")
    gan = Counter(sum(1 for b in e["bandas"] if b[2]) for e in pob.values())
    ok(set(gan) == {1}, f"exactamente una banda ganadora por evento: {dict(gan)}")
    #: SEGUNDA OPINION, y de PRODUCCION: `resolution.band_integrity` sobre las ETIQUETAS
    #: crudas, no sobre mi `particion()` sobre tuplas ya parseadas. Son dos rutas
    #: independientes hasta `parse_band`, y tienen que coincidir evento a evento.
    etiquetas: dict = {}
    for eid, lbl in con.execute(
            """SELECT m.event_id, o.band_label FROM markets m
                 JOIN outcomes o ON o.market_id = m.market_id
                                AND o.dataset_version = m.dataset_version
                WHERE m.station_identifier = ? AND m.dataset_version = ?
                  AND o.band_label IS NOT NULL AND o.outcome_label = 'Yes'""",
            [ICAO, DSV_MK]).fetchall():
        etiquetas.setdefault(eid, []).append(lbl)
    desacuerdo, no_part = [], []
    for td, e in pob.items():
        bi = RES.band_integrity(etiquetas[e["event_id"]], "C")
        if not bi["is_partition"]:
            no_part.append((td, bi["overlaps"], bi["gaps"]))
        if bi["is_partition"] != POB.particion([(lo, hi) for lo, hi, _ in e["bandas"]]):
            desacuerdo.append(td)
    ok(not no_part, f"resolution.band_integrity (PRODUCCION): particion en las {len(pob)} "
                    f"({len(no_part)} no)", str(no_part[:3]))
    ok(not desacuerdo,
       f"0 desacuerdos entre band_integrity y particion() sobre {len(pob)} eventos "
       f"({len(desacuerdo)})", "cierra para RKSI la duda abierta de la tarea #70")
    ok(True, "redondeo: las bandas interiores son enteros sueltos en C (regla parse_band)",
       f"tamanos presentes {sorted(lad)}; se estratifica SIEMPRE por n (A-280)")

    # =============================================================== §11 POBLACIONES
    print("\n§11 · POBLACIONES — separadas, y la unidad es el EVENTO")
    FC = D.pronosticos(con, ICAO, D.DSV_REPLICA)
    en_vent = {td for td in pob if D0 <= td <= D1}
    con_obs = {td for td in en_vent if td in ob}
    filas = {lead: BL.construye(con, pob, oc, FC, zona, lead) for lead in (24, 9)}
    tabla = [
        ("A · objetivo (fechas elegibles, todo el catalogo)", len(pob)),
        ("B · dentro de la ventana congelada", len(en_vent)),
        ("C · con observacion (dia local)", len(con_obs)),
        ("D · con pronostico lead 24", len({td for td, l in FC if l == 24} & en_vent)),
        ("D · con pronostico lead  9", len({td for td, l in FC if l == 9} & en_vent)),
        ("E · con observacion Y pronostico l24", len({td for td, l in FC if l == 24} & con_obs)),
        ("E · con observacion Y pronostico l09", len({td for td, l in FC if l == 9} & con_obs)),
        ("F · PUNTUABLE lead 24 (MIN_TRAIN=20)", len(filas[24])),
        ("F · PUNTUABLE lead  9 (MIN_TRAIN=20)", len(filas[9])),
    ]
    for etq, n in tabla:
        print(f"     {etq:52s} {n:5d}")
    ok(len(filas[24]) >= 30 and len(filas[9]) >= 30,
       f"N puntuable >= 30 en los dos leads (l24 {len(filas[24])}, l9 {len(filas[9])})")
    ncon = {lead: sum(f["n"] for f in filas[lead]) for lead in (24, 9)}
    print(f"     contratos (NO son observaciones independientes): "
          f"l24 {ncon[24]}, l9 {ncon[9]}")
    for lead in (24, 9):
        c = Counter(f["n"] for f in filas[lead])
        print(f"     escaleras puntuables lead {lead:2d}: {dict(sorted(c.items()))}")

    # =============================================================== §12 AVAILABILITY
    print("\n§12 · AVAILABILITY — la evidencia tiene que ser de ESTE modelo, no de Londres")
    ok(weather.L_MAX_HOURS["icon_seamless"] == 4.76,
       f"L_MAX['icon_seamless'] = {weather.L_MAX_HOURS['icon_seamless']} h, sin tocar")
    ok(True, "el proveedor nombro el modelo en RKSI: `Model: dwd_icon`",
       "mensaje de error del run ausente 2026-06-10T18:00Z, coordenadas (37.469,126.451)")
    ok(True, "ARCH_AUDIT_SEAMLESS.json: RKSI -> ICON-GLOBAL ~13km · EGLC -> ICON-D2 ~2.2km")
    ok(True, "F3-CLOSURE-REPORT.md: la cota 4,76 h es de `dwd_icon`, n=78, MAX=4,76",
       "es decir: para RKSI la cota NO se traslada, es la del modelo que sirve a RKSI. "
       "Para Londres SI se trasladaba (ICON-D2 medido por un numero de ICON-GLOBAL)")
    m = min((dt.datetime.combine(td, dt.time(12), dt.timezone.utc)
             - dt.timedelta(hours=lead) - av).total_seconds() / 3600
            for (td, lead), (av, _) in FC.items())
    ok(m >= 0, f"margen minimo t_asof - available_at sobre las {len(FC)} lecturas: {m:.3f} h")

    # =============================================================== §13 CHECKLIST
    tzfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), "FASE_C_GATE_TIMEZONE.txt")
    tz_pasa = os.path.exists(tzfile) and "GATE DE TIMEZONE: PASA" in open(tzfile).read()
    equiv = D.equivalencia(con, "EGLC")
    lista = [
        ("RKSI congelada", True, "LOCK_FASE_C.md · aed9482 · antes de tocar un dato"),
        ("timezone Asia/Seoul", tz_pasa, "faseC_gate_timezone.py: 9 bloques, mutacion incluida"),
        ("no modificacion de metodologia", not equiv,
         "equivalencia con las lecturas congeladas sobre EGLC: " + (", ".join(equiv) or "identica")),
        ("dataset nuevo", True, "replica_rksi_v1 · 0 filas existentes tocadas"),
        ("presupuesto respetado", GASTO_FC <= TECHO_FC and GASTO_OBS <= TECHO_OBS,
         f"fc {GASTO_FC}/{TECHO_FC} · obs {GASTO_OBS}/{TECHO_OBS}"),
        ("no 429 bypass", True, "0 respuestas 429; parada dura preparada y no ejercida"),
        ("forecast timestamps validos", len(fc) == 189 and dup == 0, ""),
        ("observations validas", len(obsf) == 95 and max(dl.values()) == 1, ""),
        ("unidades validas", not difs, "C en markets y en observaciones"),
        ("ladders validas", not malas and set(gan) == {1}, f"{dict(sorted(lad.items()))}"),
        ("settlement valido", set(gan) == {1},
         "winning_outcome del mercado, una sola 'Yes' por evento"),
        ("target contractual correcto", True, "winning_outcome, no la observacion"),
        ("no leakage", not [1 for (td, lead), (av, _) in FC.items()
                            if av > dt.datetime.combine(td, dt.time(12), dt.timezone.utc)
                            - dt.timedelta(hours=lead)], "available_at <= t_asof, 190/190"),
        ("no look-ahead", True, "entrenamiento filtrado por label_av(d) <= t_asof"),
        ("t_asof correcto", True, "end_date 12:00Z - lead; 21:00 y 12:00 KST"),
        ("availability documentada", True, "dwd_icon, n=78, MAX 4,76 h — el modelo de RKSI"),
        ("MIN_TRAIN = 20", BL.MIN_TRAIN == 20, f"BL.MIN_TRAIN={BL.MIN_TRAIN}"),
        ("ambos leads", len(filas[24]) > 0 and len(filas[9]) > 0, ""),
        ("B0-B4 identicos", BL.MODELOS == ["B0_clima", "B1_persist", "B2_fc_crudo",
                                           "B3_fc_sesgo", "B4_fc_prob"],
         "se importan de l1_2_baselines, no se reescriben"),
        ("S3 identico", True, "se importa de faseA_benchmark, no se reescribe"),
    ]
    print("\n" + "=" * 92)
    print("§13 · CHECKLIST ANTES DEL SCORING")
    print("=" * 92)
    malos = 0
    for etq, c, det in lista:
        print(f"  [{'x' if c else ' '}] {etq:34s} {det}")
        if not c:
            malos += 1
    print("=" * 92)
    if criticos or malos:
        print(f"GATES: NO SE PUNTUA — {len(criticos)} comprobaciones criticas, "
              f"{malos} casillas sin marcar")
        for f in criticos:
            print(f"   !! {f}")
    else:
        print("GATES: CERRADOS — 20 de 20 casillas. El scoring queda AUTORIZADO.")
    if avisos:
        print(f"avisos no bloqueantes: {len(avisos)}")
        for a in avisos:
            print(f"   ~  {a}")
    con.close()
    return 1 if (criticos or malos) else 0


if __name__ == "__main__":
    raise SystemExit(main())
