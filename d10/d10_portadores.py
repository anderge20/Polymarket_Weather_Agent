#!/usr/bin/env python3
"""D10 · punto 3 — BUSQUEDA SISTEMATICA DE FRONTERAS, no enumeracion de las conocidas.

La pregunta del encargo es: «¿existen modulos adicionales, aparte de los ya encontrados, que
interpreten o transformen series, measurement_rule_code, observaciones, labels o
winning_outcome?». Responderla listando las que ya conozco seria confirmar lo que ya creo.

METODO. Cinco PORTADORES SEMANTICOS. Para cada modulo de `src/`, `scripts/` y del corpus de
analisis se marca, por AST:

  LEE      aparece el nombre del portador en una cadena o en un acceso a atributo/clave
  ESCRIBE  aparece como clave de un dict literal, o en un INSERT/UPDATE/ALTER
  TRANSFORMA  hay aritmetica, conversion de unidad, mapeo o comparacion SOBRE el portador

Un modulo que solo LEE y pasa adelante no es una frontera. Frontera = TRANSFORMA o decide.
La clasificacion final la hago yo leyendo, pero el CANDIDATO lo elige el barrido, no yo.
"""
from __future__ import annotations

import ast
import os
from collections import defaultdict
from pathlib import Path

REPO = Path(os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-merge"))
ANALISIS = Path("/Users/mariaaleu/pmw-e2")

PORTADORES = {
    "series": ("series", "SERIES_CORRESPONDENCE", "to_core_series", "station_series",
               "SERIES_SOURCE", "metar_body_c", "metar_tgroup_tmpf", "hko_clmmaxt"),
    "measurement_rule": ("measurement_rule", "measurement_rule_code", "contract_source",
                         "classify_measurement_rule", "parse_measurement_rule"),
    "observacion": ("observed_value", "observed_unit", "tmax_observed", "daily_high",
                    "observation_time", "forecast_tmax"),
    "label": ("build_label", "label_market", "LabelRow", "LABEL_WINNER", "LABEL_LOSER",
              "try_settle", "settled_value"),
    "winning_outcome": ("winning_outcome", "is_winner", "outcome_index", "band_label",
                        "parse_band", "band_integrity", "event_winning_band"),
}
ARITMETICA = (ast.BinOp, ast.Compare, ast.UnaryOp)


def ficheros():
    out = []
    for base, etq in ((REPO / "src", "src"), (REPO / "scripts", "scripts"),
                      (ANALISIS / "fase2", "analisis"), (ANALISIS / "d09", "analisis")):
        for f in sorted(base.rglob("*.py")):
            out.append((etq, f))
    return out


def analiza(f: Path):
    """Devuelve {portador: {'lee','escribe','transforma'}}."""
    try:
        arbol = ast.parse(f.read_text())
    except (SyntaxError, UnicodeDecodeError):
        return {}
    marcas = defaultdict(set)
    # indice de nodos padre para saber si un nombre participa en aritmetica
    padres = {}
    for n in ast.walk(arbol):
        for h in ast.iter_child_nodes(n):
            padres[h] = n

    def cadena_padres(n, k=4):
        out = []
        for _ in range(k):
            n = padres.get(n)
            if n is None:
                break
            out.append(n)
        return out

    for n in ast.walk(arbol):
        texto = None
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            texto = n.value
        elif isinstance(n, ast.Attribute):
            texto = n.attr
        elif isinstance(n, ast.Name):
            texto = n.id
        if texto is None:
            continue
        for port, nombres in PORTADORES.items():
            golpe = [x for x in nombres if x == texto or (len(texto) > 40 and x in texto)]
            if not golpe:
                continue
            marcas[port].add("lee")
            ups = cadena_padres(n)
            if any(isinstance(p, ARITMETICA) for p in ups):
                marcas[port].add("transforma")
            if any(isinstance(p, (ast.Call,)) and getattr(getattr(p, "func", None), "attr", "") in
                   ("get", "pop", "setdefault") for p in ups):
                marcas[port].add("lee")
            if isinstance(n, ast.Constant) and any(
                    isinstance(p, ast.Dict) for p in ups):
                marcas[port].add("escribe")
            if isinstance(n, ast.Constant) and len(texto) > 40 and any(
                    k in texto.upper() for k in ("INSERT", "UPDATE", "ALTER", "CREATE")):
                marcas[port].add("escribe")
    return {k: v for k, v in marcas.items()}


def main():
    filas = []
    for etq, f in ficheros():
        m = analiza(f)
        if m:
            filas.append((etq, str(f).replace(str(REPO) + "/", "").replace(str(ANALISIS) + "/", "~/pmw-e2/"), m))
    print("=" * 104)
    print("PORTADORES SEMANTICOS POR MODULO  (l=lee  e=escribe  T=TRANSFORMA)")
    print("=" * 104)
    cab = f"  {'':9s} {'modulo':46s} " + " ".join(f"{p[:12]:>13s}" for p in PORTADORES)
    print(cab); print("  " + "-" * 100)
    for etq, ruta, m in filas:
        cel = []
        for p in PORTADORES:
            s = m.get(p, set())
            cel.append(("T" if "transforma" in s else "") + ("e" if "escribe" in s else "")
                       + ("l" if "lee" in s else "") or "·")
        print(f"  {etq:9s} {ruta:46s} " + " ".join(f"{c:>13s}" for c in cel))
    print("\n  CANDIDATOS A FRONTERA (transforman algun portador):")
    for etq, ruta, m in filas:
        t = [p for p, s in m.items() if "transforma" in s]
        if t:
            print(f"    {etq:9s} {ruta:46s} -> {t}")


if __name__ == "__main__":
    main()
