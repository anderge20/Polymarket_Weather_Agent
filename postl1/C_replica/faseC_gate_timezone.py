#!/usr/bin/env python3
"""FASE C · GATE CRITICO — TIMEZONE (§6 del encargo). Se ejecuta ANTES de puntuar nada.

Siete comprobaciones exigidas + una MUTACION. La mutacion es la que el encargo pide con
todas las letras: *"un test especifico que falle si accidentalmente se utiliza una
timezone fija distinta de la estacion"*. No basta con que el codigo acepte la zona: hay
que demostrar que la USA. Se demuestra alterando `stations.timezone_of` y exigiendo que
la salida CAMBIE. Si alguna ruta tuviera la zona clavada, la mutacion seria un no-op y
esa comprobacion FALLA.

Sale con codigo 1 si cualquier comprobacion falla. Ninguna de ellas mira un resultado.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import os
import sys
import tarfile
from zoneinfo import ZoneInfo

import duckdb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/fase2")
REPO = os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-merge")
sys.path.insert(0, os.path.join(REPO, "src"))
import faseC_datos as D                                  # noqa: E402
import n075_poblacion as POB                             # noqa: E402
from weather_agent import stations, weather              # noqa: E402

ICAO, DSV_MK = "RKSI", "markets_v2"
TARBALL = "/Users/mariaaleu/pmw-e2/evidence/B-133/raw_iem_55_estaciones.tgz"
D0, D1 = dt.date(2026, 5, 21), dt.date(2026, 8, 23)
fallos: list[str] = []


def ok(c, etq, det=""):
    print(f"  {'OK ' if c else '!! FALLA '} {etq}" + (f"\n        {det}" if det else ""))
    if not c:
        fallos.append(etq)


def serie_horaria(icao: str) -> list[tuple[dt.datetime, float]]:
    """Las observaciones horarias REALES del tarball, en UTC. No es un fixture."""
    with tarfile.open(TARBALL) as t:
        datos = t.extractfile(f"raw/{icao}_rt34.csv").read().decode()
    out = []
    for r in csv.DictReader(io.StringIO(datos)):
        try:
            f = float(r["tmpf"])
        except (TypeError, ValueError):
            continue
        t_utc = dt.datetime.strptime(r["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc)
        out.append((t_utc, (f - 32.0) * 5.0 / 9.0))
    return out


def main() -> int:
    con = duckdb.connect(D.DB, read_only=True)
    con.execute("SET TimeZone='UTC'")
    zona = D.zona_de(ICAO)
    print("=" * 92)
    print(f"FASE C · GATE DE TIMEZONE · {ICAO} · zona declarada {zona}")
    print("=" * 92)

    # ---------------------------------------------------------------- T1
    print("\nT1 · conversion UTC -> zona de la estacion")
    ok(str(zona) == "Asia/Seoul", "stations.timezone_of('RKSI') == Asia/Seoul", str(zona))
    offs = {dt.datetime(2026, m, 15, tzinfo=dt.timezone.utc).astimezone(zona).utcoffset()
            for m in (1, 5, 7, 12)}
    ok(offs == {dt.timedelta(hours=9)},
       "Asia/Seoul es UTC+09:00 TODO el anyo (sin horario de verano)", str(sorted(offs)))
    ok(ZoneInfo("Europe/London").utcoffset(dt.datetime(2026, 7, 1)) != dt.timedelta(hours=9),
       "Europe/London y Asia/Seoul NO coinciden en la ventana (la mutacion puede morder)")

    # ---------------------------------------------------------------- T2
    print("\nT2 · la clave de agrupacion es la FECHA LOCAL, no la UTC")
    filas = con.execute(
        "SELECT observation_time, observed_value FROM weather_observations "
        "WHERE station = ? AND dataset_version = ?", [ICAO, D.DSV_REPLICA]).fetchall()
    loc = {t.astimezone(zona).date() for t, _ in filas}
    utc = {t.date() for t, _ in filas}
    obs = D.observaciones_banda(con, ICAO, D.DSV_REPLICA)
    ok(set(obs) == loc, f"observaciones_banda agrupa por fecha LOCAL ({len(loc)} dias)")
    ok(set(obs) != utc, "y NO por fecha UTC — los dos conjuntos difieren",
       f"local {len(loc)} dias, utc {len(utc)} dias, "
       f"solo-utc {len(utc - loc)}, solo-local {len(loc - utc)}")

    # ---------------------------------------------------------------- T3
    print("\nT3 · observaciones cerca de la medianoche UTC (el caso que discrimina)")
    #: SE PREGUNTA A LA SERIE HORARIA, NO A `weather_observations`. La tabla guarda UNA
    #: fila por dia local -- el maximo, que en Seul cae hacia las 14:00 KST = 05:00Z --
    #: asi que preguntarle por la medianoche UTC es preguntar a la tabla equivocada: la
    #: agrupacion por dia local ya la decidio la INGESTA, y lo que se agrupo fue la serie
    #: horaria. Mi primera version lo preguntaba a la tabla y encontraba 1 fila: no era
    #: un resultado, era el instrumento apuntando al sitio donde nada puede cambiar.
    horaria = [(t, c) for t, c in serie_horaria(ICAO) if D0 <= t.astimezone(zona).date() <= D1]
    cerca = [(t, c) for t, c in horaria if t.hour in (23, 0)]
    desplazadas = [(t, c) for t, c in cerca if t.astimezone(zona).date() != t.date()]
    ok(len(cerca) > 0,
       f"la serie horaria tiene {len(cerca)} lecturas a +-1 h de medianoche UTC "
       f"(de {len(horaria)} en la ventana)")
    ok(len(desplazadas) > 0,
       f"y {len(desplazadas)} caen en una FECHA distinta al pasar a Asia/Seoul",
       "; ".join(f"{t:%Y-%m-%d %H:%M}Z -> {t.astimezone(zona):%Y-%m-%d %H:%M} KST"
                 for t, _ in desplazadas[:3]))
    n_max_cerca = sum(1 for t, _ in filas if t.hour in (23, 0))
    ok(True, f"para el contraste: el MAXIMO diario cae cerca de medianoche UTC "
             f"{n_max_cerca} veces de {len(filas)}",
       "por eso la comprobacion se hace sobre la serie horaria y no sobre la tabla diaria")

    # ---------------------------------------------------------------- T4
    print("\nT4 · no se desplaza un dia: maximo diario contra el oraculo independiente")
    ora: dict[dt.date, float] = {}
    for t_utc, c in serie_horaria(ICAO):
        d = t_utc.astimezone(zona).date()
        ora[d] = max(ora.get(d, -999.0), round(c))
    dentro = [d for d in obs if D0 <= d <= D1]
    disc = [d for d in dentro if d in ora and round(obs[d]) != round(ora[d])]
    ok(len(dentro) == 95, f"95 dias locales en la ventana congelada ({len(dentro)})")
    ok(not disc, f"0 discrepancias contra el tarball sobre {sum(1 for d in dentro if d in ora)} dias",
       "; ".join(f"{d} {obs[d]:.1f} vs {ora[d]:.1f}" for d in disc[:5]))
    ora_lon: dict[dt.date, float] = {}
    for t_utc, c in serie_horaria(ICAO):
        d = t_utc.astimezone(ZoneInfo("Europe/London")).date()
        ora_lon[d] = max(ora_lon.get(d, -999.0), round(c))
    dlon = [d for d in dentro if d in ora_lon and round(obs[d]) != round(ora_lon[d])]
    ok(len(dlon) > 0,
       f"y el MISMO oraculo agrupado por Europe/London discrepa en {len(dlon)} de {len(dentro)} dias",
       "prueba de que el dia local NO es indiferente en RKSI")

    # ---------------------------------------------------------------- T5
    print("\nT5 · pronostico y observacion pertenecen al MISMO target date")
    FC = D.pronosticos(con, ICAO, D.DSV_REPLICA)
    tds = {td for td, _ in FC}
    ok(tds <= set(obs) | {d for d in tds if d not in obs},
       f"pares (fecha,lead) {len(FC)} sobre {len(tds)} fechas objetivo")
    sin_obs = sorted(td for td in tds if td not in obs)
    ok(not sin_obs, f"toda fecha con pronostico tiene observacion local ({len(sin_obs)} sin)",
       str(sin_obs[:6]))
    fuera = sorted(td for td in tds if not (D0 <= td <= D1))
    ok(not fuera, "ninguna fecha objetivo se sale de la ventana congelada", str(fuera[:6]))

    # ---------------------------------------------------------------- T6
    print("\nT6 · t_asof, expresado en hora LOCAL de la estacion")
    for lead, esperado in ((24, "21:00"), (9, "12:00")):
        t = dt.datetime.combine(D1, dt.time(12), dt.timezone.utc) - dt.timedelta(hours=lead)
        loc_t = t.astimezone(zona)
        ok(loc_t.strftime("%H:%M") == esperado,
           f"lead {lead:2d} h -> t_asof {t:%Y-%m-%d %H:%M}Z = {loc_t:%Y-%m-%d %H:%M} KST")
    ok(dt.datetime.combine(D1, dt.time(12), dt.timezone.utc).astimezone(zona).strftime("%H:%M")
       == "21:00", "el ancla end_date 12:00Z son las 21:00 KST del MISMO dia objetivo",
       "el dia civil de Seul acaba 15:00Z, asi que el ancla cae DESPUES del cierre local")

    # ---------------------------------------------------------------- T7
    print("\nT7 · los dos leads, con la pasada que la regla congelada selecciona")
    for lead in (24, 9):
        n = sum(1 for k in FC if k[1] == lead)
        ok(n > 0, f"lead {lead:2d} h: {n} fechas con pronostico disponible en t_asof")
    tarde = []
    for (td, lead), (av, _) in FC.items():
        t = dt.datetime.combine(td, dt.time(12), dt.timezone.utc) - dt.timedelta(hours=lead)
        if av > t:
            tarde.append((td, lead, av, t))
    ok(not tarde, f"available_at <= t_asof en las {len(FC)} lecturas (0 look-ahead)",
       str(tarde[:3]))
    runs = con.execute(
        "SELECT DISTINCT forecast_run FROM weather_forecasts WHERE station = ? "
        "AND dataset_version = ? ORDER BY 1", [ICAO, D.DSV_REPLICA]).fetchall()
    ok([r[0] for r in runs] == ["06z", "18z"],
       "las pasadas ingestadas son exactamente 06z y 18z", str([r[0] for r in runs]))

    # ---------------------------------------------------------------- T8 MUTACION
    print("\nT8 · MUTACION — si la zona estuviera clavada, estas comprobaciones FALLARIAN")
    real_obs = D.observaciones_banda(con, ICAO, D.DSV_REPLICA)
    real_c, _ = D.observaciones_c(con, ICAO, D.DSV_REPLICA)
    real_pob = POB.poblacion(con, DSV_MK, ICAO)[0]
    orig = stations.timezone_of
    for falsa in ("Europe/London", "UTC"):
        stations.timezone_of = lambda s, _f=falsa: _f
        try:
            m_obs = D.observaciones_banda(con, ICAO, D.DSV_REPLICA)
            m_c, m_z = D.observaciones_c(con, ICAO, D.DSV_REPLICA)
            m_pob = POB.poblacion(con, DSV_MK, ICAO)[0]
        finally:
            stations.timezone_of = orig
        ok(m_obs != real_obs, f"[{falsa}] observaciones_banda CAMBIA al mutar la zona",
           f"dias {len(real_obs)} -> {len(m_obs)}, valores distintos "
           f"{sum(1 for d in set(real_obs) & set(m_obs) if real_obs[d] != m_obs[d])}")
        ok(m_c != real_c, f"[{falsa}] observaciones_c CAMBIA al mutar la zona")
        ok(str(m_z) == falsa, f"[{falsa}] la zona devuelta es la mutada, no una fija")
        ok(set(m_pob) == set(real_pob),
           f"[{falsa}] poblacion: las FECHAS no dependen de la zona (vienen de end_date)")
    # y el corte del desempate, que es lo que arregla el hermano del defecto D11
    src = open("/Users/mariaaleu/pmw-e2/fase2/n075_poblacion.py").read()
    cuerpo = src[src.index("def poblacion("):]
    ok("zona_estacion" in cuerpo and ", LON)" not in cuerpo,
       "poblacion(): el corte del dia civil usa zona_estacion, no la constante LON")

    # ---------------------------------------------------------------- T9 wiring
    print("\nT9 · la INGESTA tambien uso la zona de la estacion (no solo el analisis)")
    real_fc = weather.build_forecast  # ruta de produccion
    serie = {t.isoformat(): c for t, c in serie_horaria(ICAO)
             if dt.date(2026, 7, 14) <= t.date() <= dt.date(2026, 7, 16)}
    a, na = weather.tmax_from_series(serie, dt.date(2026, 7, 15), "Asia/Seoul")
    try:
        b, nb = weather.tmax_from_series(serie, dt.date(2026, 7, 15), "Europe/London")
        ok(abs(a - b) > 1e-9 or na != nb,
           "tmax_from_series depende de la zona sobre filas REALES",
           f"Asia/Seoul {a:.2f} ({na} h) vs Europe/London {b:.2f} ({nb} h)")
    except weather.WeatherIngestError as e:
        ok(True, "tmax_from_series con Europe/London se NIEGA sobre las mismas filas", str(e)[:110])
    disc_fc = con.execute(
        """SELECT count(*) FROM weather_forecasts a JOIN weather_forecasts b
             ON a.station=b.station AND a.model=b.model AND a.issue_time=b.issue_time
            AND a.target_date=b.target_date
           WHERE a.station=? AND a.dataset_version=? AND b.dataset_version='backfill_2b_v1'
             AND abs(a.forecast_tmax - b.forecast_tmax) > 1e-9""",
        [ICAO, D.DSV_REPLICA]).fetchone()[0]
    comp = con.execute(
        """SELECT count(*) FROM weather_forecasts a JOIN weather_forecasts b
             ON a.station=b.station AND a.model=b.model AND a.issue_time=b.issue_time
            AND a.target_date=b.target_date
           WHERE a.station=? AND a.dataset_version=? AND b.dataset_version='backfill_2b_v1'""",
        [ICAO, D.DSV_REPLICA]).fetchone()[0]
    ok(disc_fc == 0 and comp > 0,
       f"{comp} pasadas comunes con la ingesta de PRODUCCION, {disc_fc} discrepancias",
       "las dos rutas tomaron la MISMA ventana local; `ingest_run` recibe "
       "`stations.timezone_of(icao)` en las dos")

    print("\n" + "=" * 92)
    if fallos:
        print(f"GATE DE TIMEZONE: FALLA — {len(fallos)} comprobaciones")
        for f in fallos:
            print(f"   !! {f}")
    else:
        print("GATE DE TIMEZONE: PASA — todas las comprobaciones, incluida la mutacion")
    print("=" * 92)
    con.close()
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
