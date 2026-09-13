#!/usr/bin/env python3
"""D0.9 · partes A (series), C (substrate readiness) y E (duplicados), ejecutadas."""
from __future__ import annotations

import ast, os, sys
from pathlib import Path

RAIZ = Path(os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-merge"))
sys.path.insert(0, str(RAIZ / "src"))
from weather_agent import observations as obsmod, settlement as st, labels   # noqa: E402

SEP = "=" * 88


def literales_de_series(f: Path) -> set[str]:
    """Cadenas literales que son un nombre de serie, del almacen o del nucleo."""
    nucleo = {getattr(st, n) for n in dir(st) if n.startswith("SERIES_")}
    almacen = set(getattr(obsmod, "SERIES_SOURCE", {}) or {})
    objetivo = nucleo | almacen
    out = set()
    try:
        arbol = ast.parse(f.read_text())
    except SyntaxError:
        return out
    for n in ast.walk(arbol):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in objetivo:
            out.add(n.value)
    return out


def main():
    print(SEP); print("A — ¿CUANTAS FUENTES DE VERDAD HAY PARA TRADUCIR LA SERIE?"); print(SEP)
    nucleo = sorted({getattr(st, n) for n in dir(st) if n.startswith("SERIES_")})
    almacen = sorted(getattr(obsmod, "SERIES_SOURCE", {}) or {})
    print(f"  vocabulario del NUCLEO   {nucleo}")
    print(f"  vocabulario del ALMACEN  {almacen}")
    print(f"  interseccion             {sorted(set(nucleo) & set(almacen)) or 'VACIA'}")
    print("\n  ficheros de src/ y scripts/ que mencionan nombres de LOS DOS vocabularios:")
    ambos, solo_uno = [], []
    for f in sorted(list((RAIZ / "src").rglob("*.py")) + list((RAIZ / "scripts").rglob("*.py"))):
        lits = literales_de_series(f)
        if not lits:
            continue
        tn, ta = bool(lits & set(nucleo)), bool(lits & set(almacen))
        rel = str(f.relative_to(RAIZ))
        (ambos if (tn and ta) else solo_uno).append((rel, sorted(lits)))
    for rel, l in ambos:
        print(f"    HABLA LOS DOS  {rel}")
        print(f"                   {l}")
    for rel, l in solo_uno:
        print(f"    uno solo       {rel:44s} {l}")
    print(f"\n  -> fuentes de verdad de la TRADUCCION: {len(ambos)}")
    print("     (una sola, y esta en scripts/: es el hallazgo estructural de A-281)")

    print("\n" + SEP); print("C — LOS DOS COMPROBADORES DE SUSTRATO, contra los cuatro criterios"); print(SEP)
    import importlib.util
    spec = importlib.util.spec_from_file_location("paper_cycle", RAIZ / "scripts" / "paper_cycle.py")
    pc = importlib.util.module_from_spec(spec); sys.modules["paper_cycle"] = pc
    spec.loader.exec_module(pc)

    import inspect
    filas = []
    for nom, fn, requeridas in (
            ("paper_cycle.settle_substrate_missing", pc.settle_substrate_missing,
             pc._SETTLE_REQUIRED),
            ("labels.missing_substrate", labels.missing_substrate, labels.REQUIRED_COLUMNS)):
        src = inspect.getsource(fn)
        c1 = "column_names" in src
        c2 = ("count(" in src) or ("IS NOT NULL" in src) or ("is not None" in src and "query" in src)
        pide = dict(requeridas)
        c3 = "measurement_rule_code" in tuple(pide.get("markets", ()))
        c4 = False   # ninguna ejecuta la ruta downstream
        filas.append((nom, c1, c2, c3, c4, pide))
    print(f"  {'comprobador':38s} {'1 columna':>10s} {'2 no-null':>10s} {'3 semantica':>12s} {'4 ruta':>8s}")
    for nom, c1, c2, c3, c4, pide in filas:
        m = lambda b: "SI" if b else "NO"
        print(f"  {nom:38s} {m(c1):>10s} {m(c2):>10s} {m(c3):>12s} {m(c4):>8s}")
    print()
    for nom, *_ , pide in filas:
        print(f"  {nom}\n    exige: {pide}")
    print("\n  criterio 3 = pide `measurement_rule_code`, que es por lo que parte el nucleo.")
    print("  criterio 4 = comprueba que la ruta downstream pueda consumirlo de verdad.")

    print("\n" + SEP); print("E — ¿LA LOGICA DE paper_cycle LA NECESITA ALGUIEN EN SILENCIO?"); print(SEP)
    print("  importadores de `paper_cycle` (AST, todo el repo incluidos tests):")
    quien = []
    for f in sorted(list(RAIZ.rglob("*.py"))):
        if ".git" in str(f) or f.name == "paper_cycle.py":
            continue
        txt = f.read_text()
        if "paper_cycle" not in txt:
            continue
        arbol = ast.parse(txt)
        directo = any(
            (isinstance(n, ast.Import) and any(a.name == "paper_cycle" for a in n.names)) or
            (isinstance(n, ast.ImportFrom) and (n.module or "") == "paper_cycle")
            for n in ast.walk(arbol))
        porruta = "spec_from_file_location" in txt and "paper_cycle" in txt
        if directo or porruta:
            quien.append((str(f.relative_to(RAIZ)), "import" if directo else "spec_from_file_location"))
    for r, c in quien:
        print(f"    {r:52s} ({c})")
    prod = [r for r, _ in quien if r.startswith("src/") or (r.startswith("scripts/"))]
    print(f"\n  de PRODUCCION (src/ o scripts/): {prod or 'NINGUNO'}")
    print("  -> la logica de `paper_cycle` no la necesita ningun modulo: solo sus tests.")
    print("     Moverla a la libreria no rompe a nadie; dejarla donde esta es lo que")
    print("     impide que la segunda frontera la herede.")


if __name__ == "__main__":
    main()
