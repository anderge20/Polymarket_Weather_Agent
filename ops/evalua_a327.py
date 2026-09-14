#!/usr/bin/env python3
"""EVALUACION DETERMINISTA DE A-327. No edita ningun parametro: los lee de aqui, congelados.

A-327 (53b8642) predijo, ANTES de que el ciclo existiera:
    decide 02:40Z del 2026-09-15   duracion ~2.144 s
    collect 03:07Z siguiente       espera   ~524 s
    AVISO 300 s  CRUZA   ·   ALARMA 600 s  NO CRUZA

CRITERIO, copiado del encargo y NO modificable aqui:
    300 <= espera < 600   ->  CONFIRMADA
    espera < 300          ->  FALLIDA
    espera >= 600         ->  ALARMA
    instrumento incapaz   ->  INDETERMINADA   (la AUSENCIA del ciclo NO es indeterminada:
                                               significa que todavia no ha ocurrido)

El tiempo canonico sale del IDENTIFICADOR contra la RANURA (A-326), nunca de una
estimacion verbal ni del instante de fin del ciclo anterior.

Sale 0 si pudo evaluar, 2 si el ciclo aun no existe, 1 si el instrumento falla.
"""
from __future__ import annotations

import datetime as dt
import glob
import gzip
import json
import os
import re
import sys

PAPER = os.environ.get("PMW_PAPER", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-paper")

#: CONGELADO por A-327 / A-328 §8. No se toca en esta evaluacion.
PRED_DURACION = 2144.0
PRED_ESPERA = 524.0
AVISO, ALARMA = 300.0, 600.0
DECIDE = dt.datetime(2026, 9, 15, 2, 40, 0, tzinfo=dt.timezone.utc)
COLLECT = dt.datetime(2026, 9, 15, 3, 7, 0, tzinfo=dt.timezone.utc)


def filas():
    out = []
    for p in sorted(glob.glob(f"{PAPER}/paper_state/cycle_params/*/*/*/*.ndjson.gz")):
        for ln in gzip.open(p, "rt"):
            d = json.loads(ln)
            m = re.match(r"col_(\d{8}T\d{6}Z)_", d.get("session_id", ""))
            if not m:
                continue
            t = dt.datetime.strptime(m.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
            prof = json.loads(d["stage_profile"]) if d.get("stage_profile") else []
            et = {e["stage"]: e["elapsed_s"] for e in prof}
            out.append({
                "t": t, "sid": d["session_id"], "shard": os.path.basename(p),
                "dur": max((e["at_s"] for e in prof), default=None),
                "disc": et.get("discover"), "mk": et.get("load:markets"),
                "cb": et.get("collect:books"), "filas": d.get("store_rows_loaded"),
                "mb": (d.get("store_total_bytes") or 0) / 1e6,
                "commit": d.get("code_commit"), "razon": d.get("collect_only_reason"),
                "rec": d.get("recorded_at"), "ini": d.get("cycle_started_at"),
            })
    out.sort(key=lambda c: c["t"])
    return out


def de_la_ranura(fs, ranura, tope_h=3.0):
    """La fila cuyo id cae en [ranura, ranura + tope]. Es la definicion de A-326."""
    c = [f for f in fs
         if ranura <= f["t"] <= ranura + dt.timedelta(hours=tope_h)]
    return c[0] if c else None


def main() -> int:
    fs = filas()
    print("=" * 92)
    print(f"EVALUACION DE A-327 · {dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ}")
    print("=" * 92)
    print(f"  prediccion CONGELADA:  duracion ~{PRED_DURACION:.0f} s · espera ~{PRED_ESPERA:.0f} s")
    print(f"  criterio: {AVISO:.0f} <= espera < {ALARMA:.0f} CONFIRMADA · "
          f"< {AVISO:.0f} FALLIDA · >= {ALARMA:.0f} ALARMA")

    dec = de_la_ranura(fs, DECIDE)
    col = de_la_ranura(fs, COLLECT)
    if dec is None or col is None:
        que = "el decide de las 02:40" if dec is None else "el collect de las 03:07"
        print(f"\n  EL CICLO AUN NO EXISTE: falta {que} del {DECIDE:%Y-%m-%d}.")
        print("  NO es INDETERMINADA: es que todavia no ha ocurrido. No se puntua.")
        print("=" * 92)
        return 2

    espera = (col["t"] - COLLECT).total_seconds()
    print(f"\n  DECIDE   {dec['sid']}")
    print(f"     shard {dec['shard']}")
    print(f"     duracion {dec['dur']:.1f} s · discover {dec['disc']} · load:markets {dec['mk']}"
          f" · collect:books {dec['cb']}")
    print(f"     filas {dec['filas']} · {dec['mb']:.1f} MB · "
          f"ms/fila {(dec['dur'] or 0)/ (dec['filas'] or 1) * 1000:.2f}")
    print(f"     commit {str(dec['commit'])[:12]} · razon {dec['razon']!r} · "
          f"inicio {dec['ini']} · fin {dec['rec']}")
    print(f"\n  COLLECT  {col['sid']}")
    print(f"     shard {col['shard']} · ranura {COLLECT:%H:%M}Z")
    print(f"     ESPERA DERIVADA (id - ranura) = {espera:.0f} s")
    print(f"     duracion {col['dur']:.1f} s · commit {str(col['commit'])[:12]}")

    print(f"\n  --- PREGUNTA A: ¿acerto A-327 sobre ESTE ciclo? ---")
    print(f"     espera   predicha {PRED_ESPERA:7.0f} · real {espera:7.0f} · "
          f"error {espera - PRED_ESPERA:+.0f} s ({abs(espera-PRED_ESPERA)/PRED_ESPERA:.1%})")
    print(f"     duracion predicha {PRED_DURACION:7.0f} · real {dec['dur']:7.1f} · "
          f"error {dec['dur'] - PRED_DURACION:+.0f} s "
          f"({abs(dec['dur']-PRED_DURACION)/PRED_DURACION:.1%})")
    print(f"     cruza 300: {'SI' if espera >= AVISO else 'NO'} · "
          f"cruza 600: {'SI' if espera >= ALARMA else 'NO'}")
    ver = ("CONFIRMADA" if AVISO <= espera < ALARMA
           else "ALARMA" if espera >= ALARMA else "FALLIDA")
    print(f"\n     VEREDICTO SOBRE A-327: {ver}")
    print(f"     (la relacion espera ≈ ciclo − 1620 tiene sesgo medido +12,4 s sobre n=3;")
    print(f"      NO se incorpora a esta puntuacion, solo a predicciones futuras)")
    print("\n  PREGUNTA B (tendencia) y PREGUNTA C (cuando se pierde una ranura) NO se")
    print("  responden aqui: se responden con `vigila_colector.py`, y no se usa A para")
    print("  declarar B ni B para declarar C.")
    print("=" * 92)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
