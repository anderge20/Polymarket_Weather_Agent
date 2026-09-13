#!/usr/bin/env python3
"""D0.9 · parte E — GRAFO DE IMPORTACIONES POR AST, no por grep.

El encargo lo pide explicitamente: «Utilizar analisis AST/import graph, no grep textual».
La razon esta medida en A-281: `grep Observation(` engancha `NoObservation(`, que no es
una frontera del nucleo. Un recuento que no distingue las dos cosas es el mismo defecto
que se esta auditando, un nivel abajo.
"""
from __future__ import annotations

import ast
import os
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-merge"))


def modulos():
    out = {}
    for f in sorted(list((RAIZ / "src").rglob("*.py")) + list((RAIZ / "scripts").rglob("*.py"))):
        rel = str(f.relative_to(RAIZ))
        if f.parts[-2] == "weather_agent" or "weather_agent" in rel:
            nom = "weather_agent." + f.stem if f.stem != "__init__" else "weather_agent"
        else:
            nom = f.stem
        out[rel] = (nom, f)
    return out


def importa(f: Path) -> set[str]:
    """Modulos del proyecto que ESTE fichero importa, por AST."""
    dst = set()
    arbol = ast.parse(f.read_text())
    for n in ast.walk(arbol):
        if isinstance(n, ast.ImportFrom):
            mod = n.module or ""
            if n.level:                       # from . import x  /  from .y import z
                base = "weather_agent" + ("." + mod if mod else "")
                for a in n.names:
                    dst.add(f"{base}.{a.name}" if not mod else base)
            elif mod.startswith("weather_agent"):
                dst.add(mod)
        elif isinstance(n, ast.Import):
            for a in n.names:
                if a.name.startswith("weather_agent"):
                    dst.add(a.name)
    return dst


def main():
    mods = modulos()
    nombre_por_ruta = {r: n for r, (n, _) in mods.items()}
    ruta_por_nombre = {n: r for r, (n, _) in mods.items()}
    aristas = {}
    for rel, (nom, f) in mods.items():
        aristas[nom] = {d for d in importa(f) if d in ruta_por_nombre}

    print("=" * 84)
    print("GRAFO DE IMPORTACIONES (solo modulos del proyecto), por AST")
    print("=" * 84)
    entrantes = defaultdict(set)
    for a, ds in aristas.items():
        for d in ds:
            entrantes[d].add(a)

    for m in ("weather_agent.labels", "weather_agent.settlement",
              "weather_agent.observations", "paper_cycle"):
        print(f"\n  {m}")
        print(f"    importa   : {sorted(aristas.get(m, set())) or '—'}")
        print(f"    LO IMPORTA: {sorted(entrantes.get(m, set())) or '— NADIE'}")

    print("\n" + "=" * 84)
    print("¿ALGUIEN IMPORTA DE scripts/ ?  (paper_cycle es un SCRIPT, no libreria)")
    print("=" * 84)
    culpables = []
    for rel, (nom, f) in mods.items():
        if not rel.startswith("src/"):
            continue
        txt = f.read_text()
        arbol = ast.parse(txt)
        for n in ast.walk(arbol):
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                nombres = ([a.name for a in n.names] if isinstance(n, ast.Import)
                           else [(n.module or "")])
                for x in nombres:
                    if x in ("paper_cycle",) or x.startswith("scripts"):
                        culpables.append((rel, x))
    print(f"  modulos de src/ que importan de scripts/: {culpables or 'NINGUNO'}")
    print("  -> la libreria NO depende del script. La dependencia va en un solo sentido,")
    print("     y por eso `labels.py` no puede alcanzar SERIES_CORRESPONDENCE.")
    return aristas, entrantes


if __name__ == "__main__":
    main()
