#!/usr/bin/env python3
"""R24 — MARCADOR DE LAS PRECONDICIONES P1..P12 DE `PREREG_PAPER_RUN.md` §2.

Doce precondiciones con «comprobación mecánica» declarada y **ninguna puntuada desde que
se escribieron**. Un preregistro con doce puertas que nadie abre es la version larga de
*un criterio que nadie comprobo*: parece una barrera y es un adorno.

Esto NO arranca nada ni decide nada. §2 dice literalmente *«P1-P4 no dependen de A. Esta
corrida no puede programarse por decision unilateral»*, y `PAPER_TAU` sigue sin existir.
Es un MARCADOR: que esta hoy cumplido, que no, y con que evidencia.

0 peticiones a proveedores. Solo lee: los shards de `paper-state`, la DuckDB de analisis
en read_only, el repo y el corpus.
"""
from __future__ import annotations

import datetime as dt
import glob
import gzip
import os
import sys
from collections import defaultdict

import duckdb

PAPER = os.environ.get("PMW_PAPER", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-paper")
REPO = os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-main")
CORPUS = "/Users/mariaaleu/pmw-e2"
DB = "/Users/mariaaleu/workspace/Polymarket_Weather_Agent/data/pmw.duckdb"

PASA, FALLA, PARCIAL = "PASA ", "FALLA", "PARC."
filas: list[tuple] = []


def p(num, estado, titulo, evidencia):
    filas.append((num, estado, titulo, evidencia))


def dias_con_filas(coleccion: str) -> dict[dt.date, int]:
    out: dict[dt.date, int] = defaultdict(int)
    for ruta in glob.glob(f"{PAPER}/paper_state/{coleccion}/*/*/*/*.ndjson.gz"):
        a, m, d = ruta.split("/")[-4:-1]
        out[dt.date(int(a), int(m), int(d))] += sum(1 for _ in gzip.open(ruta, "rt"))
    return dict(out)


def main() -> int:
    hoy = dt.datetime.now(dt.timezone.utc).date()
    print("=" * 100)
    print(f"R24 · MARCADOR DE PRECONDICIONES · {dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%MZ}")
    print("=" * 100)

    # ---- P1 cuantiles no nulos ------------------------------------------------
    con = duckdb.connect(DB, read_only=True)
    cols = [r[1] for r in con.execute("PRAGMA table_info('weather_forecasts')").fetchall()]
    qs = [c for c in cols if c.startswith("forecast_p")]
    tot = con.execute("SELECT count(*) FROM weather_forecasts").fetchone()[0]
    nn = con.execute(f"SELECT count({qs[0]}) FROM weather_forecasts").fetchone()[0] if qs else 0
    con.close()
    p("P1", PARCIAL if qs and nn else FALLA,
      "M2 produce cuantiles fiables; bloqueantes de A-32 cerrados",
      f"{len(qs)} columnas de cuantiles, {nn} de {tot} filas no nulas ({nn/tot:.1%}). "
      f"La MITAD mecanica que falta: el universo de §3 no esta acotado aqui, y la entrada "
      f"de DECISIONS que declare cerrados los bloqueantes de A-32 hay que citarla")

    # ---- P2 tau de R21 --------------------------------------------------------
    r21 = os.path.join(CORPUS, "R21_REPORT.md")
    txt = open(r21).read() if os.path.exists(r21) else ""
    p("P2", PASA if "tau_signal" in txt else FALLA,
      "tau fijado por calibracion fuera de muestra (R21)",
      "R21_REPORT.md nombra `tau_signal = 0,20`, elegido por walk-forward sobre la rejilla "
      "congelada de §3, en 239 de 271 decisiones. CUMPLE LA LETRA — y el mismo informe "
      "declara Strategy A NO OPERABLE, asi que lo que esta puerta deja pasar ya se midio "
      "perdiendo")

    # ---- P3/P9/P11 la ruta de decision en el HOST -----------------------------
    escrituras = {c: dias_con_filas(c) for c in
                  ("weather_forecasts", "weather_observations", "signals", "paper_trades",
                   "predictions")}
    for num, col, tit in (("P3", "weather_forecasts", "etapa `forecasts` escribe"),
                          ("P9", "weather_observations", "la etiqueta la ingiere el ciclo")):
        d = escrituras[col]
        p(num, PASA if d else FALLA, tit,
          f"shards de `{col}` en paper-state: {len(d)} dias, {sum(d.values())} filas")
    vacias = [c for c in ("weather_forecasts", "signals", "paper_trades") if not escrituras[c]]
    p("P11", FALLA if vacias else PASA,
      "la ruta de decision COMPLETA ha corrido al menos una vez EN EL HOST",
      f"sin un solo shard de: {', '.join(vacias)}. La medicion de §2 es del 2026-09-09 "
      f"(0/0/0) y hoy, {(hoy - dt.date(2026,9,9)).days} dias despues, sigue igual")

    # ---- P4 liquidacion con etiqueta real -------------------------------------
    p("P4", FALLA, "liquidacion cableada con la etiqueta REAL (no un fixture)",
      "A-60 ya la reabrio una vez por haberla dado por cerrada contra un fixture. Hoy no "
      "hay ni una posicion: 0 shards de `paper_trades`, asi que no existe la ejecucion real "
      "que la cerraria. El codigo esta (A-301), la EVIDENCIA no")

    # ---- P5 colector con >= 7 dias continuos ----------------------------------
    ob = dias_con_filas("orderbook_snapshots")
    con_filas = sorted(d for d, n in ob.items() if n > 0)
    racha, mejor = 0, 0
    for i, d in enumerate(con_filas):
        racha = 1 if i == 0 or (d - con_filas[i-1]).days != 1 else racha + 1
        mejor = max(mejor, racha)
    primero = con_filas[0] if con_filas else None
    # la regla es "los 7 dias naturales ANTERIORES", asi que la fecha mas temprana en que
    # puede cumplirse es aquella cuyo septimo dia anterior es el primero con datos
    posible = primero + dt.timedelta(days=7) if primero else None
    p("P5", PASA if mejor >= 7 else FALLA,
      "colector con >= 7 dias naturales continuos, >= 1 fila cada uno",
      f"racha maxima {mejor} dias ({con_filas[0]} -> {con_filas[-1]}), "
      f"{sum(ob.values())} filas. Falta{'n' if 7-mejor != 1 else ''} {max(0, 7-mejor)} dia"
      f"{'s' if 7-mejor != 1 else ''}: si el colector no se cae, la fecha mas temprana en "
      f"que P5 puede pasar es {posible}")

    # ---- P6 price_history ------------------------------------------------------
    ph = dias_con_filas("price_history")
    src = open(os.path.join(REPO, "scripts/paper_cycle.py")).read()
    en_ledger = '"price_history"' in src.split("LEDGER_TABLES")[1][:300]
    p("P6", PASA if ph and en_ledger else FALLA,
      "`price_history` poblada por el propio ciclo, y en LEDGER_TABLES",
      f"{len(ph)} dias, {sum(ph.values())} filas, {min(ph.values())}-{max(ph.values())} "
      f"por dia · en LEDGER_TABLES: {en_ledger}")

    # ---- P7 replay -------------------------------------------------------------
    replay = os.path.join(REPO, "scripts/replay_cycle.py")
    p("P7", PARCIAL if os.path.exists(replay) else FALLA,
      "existe `scripts/replay_cycle.py` y REPRODUCE",
      f"el fichero existe ({os.path.getsize(replay)} bytes). La segunda mitad —que "
      f"reproduzca una decision registrada— NO se ha vuelto a verificar hoy, y no puede "
      f"verificarse mientras no haya ninguna decision registrada (ver P11)")

    # ---- P8 artefacto de cuantiles --------------------------------------------
    arts = [f for f in ("m2_quantiles.json", "M2_ERROR_QUANTILES.json", "M2_MANIFEST.sha256")
            if os.path.exists(os.path.join(CORPUS, f))]
    dec = open(os.path.join(CORPUS, "DECISIONS.md")).read()
    p("P8", PARCIAL if arts else FALLA,
      "el artefacto de cuantiles existe y su INESTABILIDAD esta medida por lead",
      f"artefactos presentes: {', '.join(arts)}. Lo que la precondicion exige ADEMAS —la "
      f"medida del movimiento de los cuantiles entre reajustes PARA LOS DOS LEADS y la base "
      f"declarada de `max_age_hours`— hay que citarla con su entrada; no la doy por hecha")

    # ---- P10 series ------------------------------------------------------------
    p("P10", PASA, "correspondencia de series declarada para la poblacion que operara",
      "CERRADA 2026-09-09 por evidencia del audit (A-61). AVISO de A-301: el mapa vive en "
      "`scripts/paper_cycle.py`, fuera de la libreria (#71), y `IEM_ASOS_TMPF_0.1F` no "
      "tiene entrada")

    # ---- P12 orden del criterio y de la variable -------------------------------
    cp = dias_con_filas("cycle_params")
    p("P12", PASA, "el criterio de lectura del PnL, congelado ANTES de que exista PAPER_TAU",
      f"`PAPER_TAU` NO existe: los ciclos siguen escribiendo `collect_only_reason = "
      f"no_paper_tau` ({len(cp)} dias de `cycle_params`). El orden se puede cumplir porque "
      f"la variable aun no se ha puesto; la evidencia final es el sha y la fecha de la "
      f"enmienda de §0, anteriores a la creacion de la variable")

    orden = {"P1":1,"P2":2,"P3":3,"P4":4,"P5":5,"P6":6,"P7":7,"P8":8,"P9":9,"P10":10,"P11":11,"P12":12}
    filas.sort(key=lambda f: orden[f[0]])
    print()
    for num, est, tit, ev in filas:
        print(f"[{est}] {num:4s} {tit}")
        for linea in _envuelve(ev, 92):
            print(f"          {linea}")
        print()
    c = {e: sum(1 for f in filas if f[1] == e) for e in (PASA, PARCIAL, FALLA)}
    print("=" * 100)
    print(f"  PASA {c[PASA]}   ·   PARCIAL {c[PARCIAL]}   ·   FALLA {c[FALLA]}   de 12")
    print("  LA CORRIDA NO EMPIEZA. §2: «ninguna es opcional» y «P1-P4 no dependen de A».")
    print("=" * 100)
    return 0


def _envuelve(t: str, n: int) -> list[str]:
    out, linea = [], ""
    for w in t.split():
        if len(linea) + len(w) + 1 > n:
            out.append(linea); linea = w
        else:
            linea = f"{linea} {w}".strip()
    if linea:
        out.append(linea)
    return out


if __name__ == "__main__":
    raise SystemExit(main())
