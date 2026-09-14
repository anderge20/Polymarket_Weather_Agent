"""La clave de conflicto de cada tabla esta declarada en VARIOS sitios: que coincidan.

EL DEFECTO DE CLASE (tarea #61, A-242). La clave de `weather_observations` vive en TRES
sitios independientes:

  1. el `PRIMARY KEY` del DDL, en `database.py`
  2. `store.CONFLICT_COLS["weather_observations"]`, que usa la recarga desde shards
  3. `observations.CONFLICT_COLS`, el literal que la INGESTA pasa a `upsert`

y `store.upsert` da **preferencia al argumento del llamante sobre el mapa**. Asi que
arreglar la clave en `store.py` NO arregla la ingesta prospectiva: tocaria uno de tres y
pareceria completo. Ese es el punto -- no que hoy difieran, que no difieren, sino que
**nada se enteraria el dia que difieran**.

Medido al escribir esto: 13 tablas tienen dos o mas declaraciones y las 13 coinciden.
Estas pruebas existen para que eso siga siendo verdad, no para arreglar nada.

NO SE USA `grep`: el DDL se parsea y las llamadas se recorren por AST, que es la regla del
proyecto para este tipo de barrido (D10).
"""
from __future__ import annotations

import ast
import pathlib
import re

from weather_agent import observations as obs_mod
from weather_agent import store

RAIZ = pathlib.Path(__file__).resolve().parents[1]
DDL = (RAIZ / "src" / "weather_agent" / "database.py").read_text()


def _pk_por_tabla(texto: str) -> dict[str, tuple[str, ...]]:
    """El `PRIMARY KEY` de cada `CREATE TABLE`, con la ULTIMA definicion ganando.

    Dos formas: la clausula `PRIMARY KEY (a, b, c)` al final del cuerpo y la columna
    suelta `col TIPO PRIMARY KEY`. Las comillas dobles se quitan porque `"timestamp"` va
    entrecomillada en el DDL y sin comillas en el mapa.
    """
    out: dict[str, tuple[str, ...]] = {}
    for m in re.finditer(r"CREATE TABLE IF NOT EXISTS\s+(\w+)\s*\((.*?)\n\s*\);", texto, re.S):
        tabla, cuerpo = m.group(1), m.group(2)
        mm = re.search(r"PRIMARY KEY\s*\(([^)]*)\)", cuerpo)
        if mm:
            out[tabla] = tuple(c.strip().strip('"') for c in mm.group(1).split(","))
            continue
        mm2 = re.search(r"^\s*(\w+)\s+[\w()]+\s+PRIMARY KEY", cuerpo, re.M)
        if mm2:
            out[tabla] = (mm2.group(1),)
    return out


def _literales_de_llamada() -> dict[str, list[tuple[str, int, tuple[str, ...]]]]:
    """Cada `upsert(..., conflict_cols=X)` del arbol, con X resuelto.

    X puede ser una tupla literal o el nombre de una constante de modulo del MISMO
    fichero -- que es justo la forma que tiene `observations.py`, y darle un nombre no
    la convierte en una sola definicion: sigue siendo un tercer sitio.
    """
    out: dict[str, list[tuple[str, int, tuple[str, ...]]]] = {}
    for p in sorted(RAIZ.rglob("*.py")):
        s = str(p.relative_to(RAIZ))
        if s.startswith((".git", "tests/")) or "/.venv" in s:
            continue
        try:
            arbol = ast.parse(p.read_text())
        except (SyntaxError, UnicodeDecodeError):
            continue
        consts = {
            n.targets[0].id: tuple(e.value for e in n.value.elts)
            for n in arbol.body
            if isinstance(n, ast.Assign) and len(n.targets) == 1
            and isinstance(n.targets[0], ast.Name)
            and isinstance(n.value, (ast.Tuple, ast.List))
            and all(isinstance(e, ast.Constant) for e in n.value.elts)
        }
        for n in ast.walk(arbol):
            if not isinstance(n, ast.Call):
                continue
            f = n.func
            if (f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")) != "upsert":
                continue
            if not (len(n.args) >= 2 and isinstance(n.args[1], ast.Constant)):
                continue
            tabla = n.args[1].value
            for kw in n.keywords:
                if kw.arg != "conflict_cols":
                    continue
                if isinstance(kw.value, (ast.Tuple, ast.List)):
                    v = tuple(e.value for e in kw.value.elts)
                elif isinstance(kw.value, ast.Name) and kw.value.id in consts:
                    v = consts[kw.value.id]
                else:
                    continue
                out.setdefault(tabla, []).append((s, n.lineno, v))
    return out


def test_las_declaraciones_de_la_clave_coinciden_tabla_por_tabla():
    """Donde hay dos o mas declaraciones de la misma clave, tienen que ser la misma."""
    pks = _pk_por_tabla(DDL)
    lits = _literales_de_llamada()
    tablas = set(pks) | set(store.CONFLICT_COLS) | set(lits)

    con_varias, malas = 0, []
    for t in sorted(tablas):
        decls: list[tuple[str, tuple[str, ...]]] = []
        if t in pks:
            decls.append(("DDL", pks[t]))
        if t in store.CONFLICT_COLS:
            decls.append(("store.CONFLICT_COLS", tuple(store.CONFLICT_COLS[t])))
        for fichero, ln, v in lits.get(t, []):
            decls.append((f"{fichero}:{ln}", v))
        if len(decls) < 2:
            continue                      # una sola declaracion no puede contradecirse
        con_varias += 1
        if len({d[1] for d in decls}) > 1:
            malas.append((t, decls))

    assert con_varias >= 13, (
        f"solo {con_varias} tablas con >=2 declaraciones; el barrido ha dejado de "
        f"encontrarlas y entonces no esta vigilando nada")
    assert not malas, "\n".join(
        f"{t}: " + " | ".join(f"{d[0]}={d[1]}" for d in decls) for t, decls in malas)


def test_la_clave_de_weather_observations_es_la_misma_en_los_TRES_sitios():
    """El caso concreto de la tarea #61, por su nombre, para quien lo busque.

    `store.upsert` prefiere el argumento del llamante al mapa, asi que el tercer sitio
    —el de `observations.py`— es el que MANDA en la ingesta prospectiva. Arreglar solo
    `store.CONFLICT_COLS` dejaria la ingesta intacta y pareceria hecho."""
    ddl = _pk_por_tabla(DDL)["weather_observations"]
    mapa = tuple(store.CONFLICT_COLS["weather_observations"])
    llamante = tuple(obs_mod.CONFLICT_COLS)
    assert ddl == mapa == llamante, (
        f"DDL={ddl}\nstore.CONFLICT_COLS={mapa}\nobservations.CONFLICT_COLS={llamante}")
    assert "source" in ddl, (
        "`source` es lo que separa las series de una misma estacion; si sale de la "
        "clave, dos series colapsan en una fila y la de menor resolucion gana")
