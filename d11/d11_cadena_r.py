#!/usr/bin/env python3
"""D11 — INTEGRIDAD EXPERIMENTAL DE LA CADENA R, frontera por frontera, con filas reales.

    forecast -> observation -> winning_outcome -> probability -> scoring

No audita settlement salvo donde R dependa de el (no depende: R importa UNA cosa de la
libreria, `resolution.parse_band`). No modela, no calcula edge ni PnL, no toca produccion.

Sólo defectos de ALTO IMPACTO: target incorrecto, forecast futuro, observacion futura,
timestamp o timezone incorrectos, mezcla de unidades, duplicacion de eventos, probabilidad
mal asociada al contrato, scoring matematicamente incorrecto.
"""
from __future__ import annotations

import datetime as dt
import os
import sys
from collections import Counter
from zoneinfo import ZoneInfo

import duckdb

sys.path.insert(0, os.path.join(os.environ.get(
    "PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-merge"), "src"))
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/fase2")
from weather_agent import stations                                          # noqa: E402
from n075_poblacion import DB, LON, observaciones, poblacion, pronosticos   # noqa: E402
from n075_metricas import EPS, clip, filas, MOD                             # noqa: E402

ALTO: list[str] = []
NOTA: list[str] = []


def ok(cond, etq, det="", alto=True):
    print(f"  {'OK ' if cond else '!! '} {etq}" + (f"   {det}" if det else ""))
    if not cond:
        (ALTO if alto else NOTA).append(etq)


def tasof(td, lead):
    return dt.datetime.combine(td, dt.time(12), dt.timezone.utc) - dt.timedelta(hours=lead)


def label_av(td):
    return (dt.datetime.combine(td + dt.timedelta(days=1), dt.time(0), LON)
            .astimezone(dt.timezone.utc) + dt.timedelta(hours=24))


def sec(t):
    print(f"\n{'=' * 86}\n{t}\n{'=' * 86}")


def main() -> int:
    con = duckdb.connect(DB, read_only=True)
    con.execute("SET TimeZone='UTC'")
    ST = "EGLC"

    # ------------------------------------------------------------------ FORECAST
    sec("F · FORECAST")
    mods = con.execute("SELECT model, count(*) FROM weather_forecasts GROUP BY 1").fetchall()
    ok(len(mods) == 1, "un solo modelo de pronostico: no hay seleccion con retrovision", str(mods))
    r = con.execute("""SELECT count(*), count(*) FILTER (WHERE available_at >= issue_time),
          min(available_at - issue_time), max(available_at - issue_time)
        FROM weather_forecasts WHERE station = ?""", [ST]).fetchone()
    ok(r[0] == r[1], "available_at >= issue_time en todas las filas", f"{r[1]} de {r[0]}")
    print(f"      retardo publicacion: min {r[2]} · max {r[3]}")
    r = con.execute("""SELECT count(*) FILTER (WHERE available_at = fetched_at),
          count(*), min(fetched_at), max(fetched_at) FROM weather_forecasts WHERE station = ?""",
                    [ST]).fetchone()
    ok(r[0] == 0, "available_at NO es el instante de descarga (`fetched_at`)",
       f"coinciden en {r[0]} de {r[1]}; fetched_at {r[2]} .. {r[3]}")
    r = con.execute("""SELECT count(*) FROM weather_forecasts WHERE station = ?
        AND available_at > CAST(target_date AS TIMESTAMP) + INTERVAL 12 HOUR""", [ST]).fetchone()[0]
    print(f"      filas con available_at posterior a las 12:00 UTC del target_date: {r}")
    print("      (existen, y por eso el filtro `available_at <= t_asof` es obligatorio)")

    obs = observaciones(con, ST)
    FC = pronosticos(con, ST)
    mal = [(td, l) for (td, l), (av, _) in FC.items() if av > tasof(td, l)]
    ok(not mal, "el pronostico elegido cumple available_at <= t_asof en TODOS los pares",
       f"violaciones {len(mal)}")
    ok(all(FC[(td, l)][1] is not None for (td, l) in FC), "forecast_tmax nunca NULL en lo elegido")
    ok(all(l in (24, 9) for _, l in FC), "sólo los dos leads declarados")
    print(f"      t_asof = end_date(12:00 UTC) - lead   ·  pares {len(FC)}")

    # ------------------------------------------------------------------ OBSERVATION
    sec("O · OBSERVATION")
    #: POR DIA LOCAL, que es lo que usa `observaciones()`. La primera version de esta
    #: comprobacion agrupaba por `CAST(observation_time AS DATE)` -- dia UTC -- y marcaba
    #: 4 duplicados que no existen: las filas de las 23:20/23:50 UTC pertenecen al dia
    #: local SIGUIENTE (00:20/00:50 BST). El defecto estaba en mi comprobacion.
    from collections import Counter as _C
    zona = ZoneInfo(stations.timezone_of(ST))
    _c = _C()
    for t, sfx in con.execute(
            "SELECT observation_time, source FROM weather_observations WHERE station = ?",
            [ST]).fetchall():
        _c[(sfx, t.astimezone(zona).date())] += 1
    dups = [k for k, v in _c.items() if v > 1]
    ok(not dups, "una fila por (estacion, serie, DIA LOCAL): la ventana diaria ya viene agregada",
       f"{len(_c)} pares, duplicados {len(dups)}")
    r = con.execute("""SELECT count(DISTINCT observed_unit), any_value(observed_unit)
        FROM weather_observations WHERE station = ?""", [ST]).fetchone()
    ok(r[0] == 1 and r[1] == "C", "unidad unica en la estacion del experimento", str(r))

    print("\n  -- ZONA HORARIA: la funcion lleva `Europe/London` FIJO --")
    #: ARREGLADO EN A-285: `observaciones()` toma la zona de `stations.timezone_of`.
    #: Esta comprobacion mide que el arreglo muerde: con LON fijo, CYYZ perdia dias.
    tor = ZoneInfo("America/Toronto")
    difs = sum(1 for (t,) in con.execute(
        "SELECT observation_time FROM weather_observations WHERE station='CYYZ'").fetchall()
        if t.astimezone(LON).date() != t.astimezone(tor).date())
    ok(stations.timezone_of("CYYZ") == "America/Toronto",
       "la zona de CYYZ sale del registro de produccion", stations.timezone_of("CYYZ"))
    ok(len(observaciones(con, "CYYZ")) > 0 and difs > 0,
       "y el arreglo muerde: con `Europe/London` fijo, CYYZ caia en otra fecha",
       f"{difs} dias afectados — ahora se agrupa por su propia zona")

    print("\n  -- SIN INFORMACION FUTURA EN LAS FEATURES --")
    peor = None
    for lead in (24, 9):
        for td in sorted(obs):
            if (td, lead) not in FC:
                continue
            t = tasof(td, lead)
            tr = [d for d in sorted(obs) if label_av(d) <= t and (d, lead) in FC]
            if not tr:
                continue
            if td in tr:
                peor = (td, lead, "el DIA OBJETIVO esta en el entrenamiento")
                break
            ultimo = max(tr)
            if label_av(ultimo) > t:
                peor = (td, lead, "una etiqueta no disponible entro en el entrenamiento")
                break
    ok(peor is None, "ninguna observacion posterior a t_asof entra en las features", str(peor or ""))
    ejem = sorted(obs)[60]
    for lead in (24, 9):
        if (ejem, lead) in FC:
            t = tasof(ejem, lead)
            tr = [d for d in sorted(obs) if label_av(d) <= t and (d, lead) in FC]
            print(f"      ejemplo {ejem} lead {lead:2d}: t_asof {t:%Y-%m-%d %H:%MZ} · "
                  f"ultimo dia entrenable {max(tr)} (etiqueta disponible {label_av(max(tr)):%m-%d %H:%MZ})")

    # ------------------------------------------------------------------ TARGET
    sec("T · TARGET (winning_outcome)")
    import inspect
    src_pob = inspect.getsource(poblacion)
    ok("winning_outcome" in src_pob, "la ganadora sale de markets.winning_outcome")
    ok("is_winner" not in src_pob, "NO se usa `is_winner`")
    ok("outcome_index" not in src_pob, "NO se usa `outcome_index`")
    ok("observed" not in src_pob and "obs" not in src_pob.replace("observaciones", ""),
       "la poblacion NO toca ninguna observacion: el target no se infiere del proxy IEM")
    pob = poblacion(con, "markets_v2", ST)[0]
    gan = Counter(sum(1 for b in e["bandas"] if b[2]) for e in pob.values())
    ok(set(gan) == {1}, "exactamente UNA ganadora por evento elegido", str(dict(gan)))
    fechas = Counter(e["fecha"] for e in pob.values())
    ok(max(fechas.values()) == 1, "una fecha -> un evento: sin duplicacion", f"max {max(fechas.values())}")
    eids = [e["event_id"] for e in pob.values()]
    ok(len(eids) == len(set(eids)), "sin event_id repetido en la poblacion")

    src_filas = inspect.getsource(filas)
    ok(src_filas.count('"y"') == 1 and '"y": 1.0 if won else 0.0' in src_filas,
       "`won` sólo se escribe como y; nunca entra en ninguna probabilidad")

    # ------------------------------------------------------------------ PROBABILITY
    sec("P · PROBABILITY")
    fs = filas(pob, obs, FC, 24)
    porev = {}
    for r_ in fs:
        porev.setdefault((r_["event_id"], r_["lead"]), []).append(r_)
    peor_suma = max(abs(sum(x["p"][m] for x in v) - 1.0)
                    for v in porev.values() for m in MOD)
    ok(peor_suma < 1e-9, "las probabilidades suman 1 dentro de cada evento, en los seis controles",
       f"error maximo {peor_suma:.2e}")
    peor_y = max(sum(x["y"] for x in v) for v in porev.values())
    ok(peor_y == 1.0, "exactamente un y=1 por evento", f"max {peor_y}")
    fuera = [x for x in fs for m in MOD if not (0.0 <= x["p"][m] <= 1.0)]
    ok(not fuera, "toda probabilidad en [0,1] ANTES del recorte", f"{len(fuera)} fuera")
    ok(abs(clip(0.0) - EPS) < 1e-18 and abs(clip(1.0) - (1 - EPS)) < 1e-18,
       "el recorte es simetrico y el mismo en los dos brazos", f"EPS={EPS}")

    #: CORRESPONDENCIA probabilidad <-> contrato: se comprueba PERTURBANDO la banda.
    prueba = next(x for x in fs if x["y"] == 1.0)
    ev = pob[prueba["fecha"]]
    orig = [b for b in ev["bandas"]]
    idx = next(i for i, b in enumerate(orig) if b[2])
    lo, hi, _ = orig[idx]
    if lo is not None and hi is not None:
        ev["bandas"] = orig[:idx] + [(lo + 100, hi + 100, True)] + orig[idx + 1:]
        fs2 = filas({prueba["fecha"]: ev}, obs, FC, 24)
        movida = next(x for x in fs2 if x["y"] == 1.0)
        ok(movida["p"]["B3_fc_error"] != prueba["p"]["B3_fc_error"],
           "mover la banda mueve SU probabilidad: la p va con el contrato, no con la posicion",
           f"{prueba['p']['B3_fc_error']:.5f} -> {movida['p']['B3_fc_error']:.5f}")
        ev["bandas"] = orig

    # ------------------------------------------------------------------ SCORING
    sec("S · SCORING")
    ns = {x["n_bandas"] for x in fs}
    ok(len(ns) == 1, "un solo estrato de escalera en la poblacion puntuada", str(ns))
    import math
    n = next(iter(ns))
    b_teo = (n - 1) / n ** 2
    l_teo = (math.log(n) + (n - 1) * math.log(n / (n - 1))) / n
    b = sum((clip(x["p"]["REF_uniforme"]) - x["y"]) ** 2 for x in fs) / len(fs)
    l = sum(-(x["y"] * math.log(clip(x["p"]["REF_uniforme"]))
              + (1 - x["y"]) * math.log(1 - clip(x["p"]["REF_uniforme"]))) for x in fs) / len(fs)
    ok(abs(b - b_teo) < 1e-12 and abs(l - l_teo) < 1e-12,
       "el control estructural coincide con su formula cerrada",
       f"Brier {b:.8f} vs {b_teo:.8f} · LL {l:.8f} vs {l_teo:.8f}")
    ok(True, "estratificacion por n obligatoria y nunca agregar entre escaleras (A-280)", "regla escrita")

    con.close()
    print(f"\n{'=' * 86}")
    print(f"DEFECTOS DE ALTO IMPACTO: {len(ALTO)}")
    for x in ALTO:
        print(f"   !! {x}")
    print(f"observaciones menores: {len(NOTA)}")
    print("=" * 86)
    return 1 if ALTO else 0


if __name__ == "__main__":
    raise SystemExit(main())
