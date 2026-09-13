"""LAS FRONTERAS DEL NÚCLEO CONGELADO, enumeradas en vez de recordadas.

A-245 encontró que `labels.py` es un SEGUNDO llamador de `weather_agent.settlement`
y que lleva dentro el defecto que `paper_cycle` ya había arreglado en su propia
frontera. La lección que dejó escrita fue:

    «cuando un arreglo traduce entre dos vocabularios, enumerar los sitios que
     hablan los dos idiomas antes de dar el arreglo por completo»

...y esa enumeración se quedó en una frase. Este fichero la convierte en una
comprobación, porque una frase no se pone roja.

DOS VOCABULARIOS, y nada los conecta salvo una tabla en un script:

    lo que ESCRIBEN los ingestores   IEM_ASOS_METAR_1C · IEM_ASOS_METAR_1C_RT34
                                     IEM_ASOS_TMPF_1F  · IEM_ASOS_TMPF_0.1F
    lo que EXIGE el núcleo congelado metar_body_c · metar_tgroup_tmpf · hko_clmmaxt

    intersección: VACÍA.

Lo mismo con la terna: `markets.measurement_rule` es PROSA («highest reading under
the NOAA 'Temp' column...») y `markets.measurement_rule_code` es el CÓDIGO
(`P_NOAA_TempColumn`). El núcleo parte por el código.
"""
from __future__ import annotations

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

#: Los tipos del núcleo congelado que sólo se pueden construir traduciendo.
TIPOS_DEL_NUCLEO = ("MarketContext", "Observation")

#: LAS FRONTERAS CONOCIDAS. Cada entrada es una promesa: quien la añada tiene que
#: haber contestado «¿cómo traduce esta frontera los dos vocabularios?».
FRONTERAS_DECLARADAS = {
    "src/weather_agent/labels.py",
    "scripts/paper_cycle.py",
}


def _ficheros():
    return sorted(list((RAIZ / "src").rglob("*.py")) + list((RAIZ / "scripts").rglob("*.py")))


def _fronteras_encontradas() -> dict[str, set[str]]:
    """Ficheros que CONSTRUYEN un tipo del núcleo, por lectura del AST.

    Por AST y no por `grep`: `NoObservation(...)` contiene la cadena
    `Observation(` y no es una construcción del núcleo. Un recuento que no
    distingue las dos cosas es el mismo defecto que esto vigila, un nivel abajo.
    """
    out: dict[str, set[str]] = {}
    for f in _ficheros():
        try:
            arbol = ast.parse(f.read_text())
        except SyntaxError:                                   # pragma: no cover
            continue
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Call):
                continue
            func = nodo.func
            nombre = (func.attr if isinstance(func, ast.Attribute)
                      else func.id if isinstance(func, ast.Name) else None)
            if nombre in TIPOS_DEL_NUCLEO:
                out.setdefault(str(f.relative_to(RAIZ)), set()).add(nombre)
    return out


def test_las_fronteras_del_nucleo_son_exactamente_las_declaradas():
    """Si aparece una tercera, este test la nombra ANTES de que liquide nada.

    No comprueba que las fronteras estén bien: comprueba que se sepan todas. Es
    la diferencia entre el defecto de A-245 —que tardó semanas en salir, y salió
    trabajando al lado, no auditando— y un defecto que aparece el día que nace.
    """
    encontradas = set(_fronteras_encontradas())
    nuevas = encontradas - FRONTERAS_DECLARADAS
    desaparecidas = FRONTERAS_DECLARADAS - encontradas
    assert not nuevas, (
        f"FRONTERA NUEVA del núcleo congelado: {sorted(nuevas)}. Antes de añadirla a "
        "FRONTERAS_DECLARADAS hay que contestar cómo traduce los dos vocabularios: el "
        "`series` que escriben los ingestores NO es el que exige el núcleo (intersección "
        "vacía), y `measurement_rule` es prosa mientras el núcleo parte por "
        "`measurement_rule_code`. Ver A-245 y A-281.")
    assert not desaparecidas, (
        f"frontera declarada que ya no construye nada del núcleo: {sorted(desaparecidas)}. "
        "Si se ha borrado o desmontado, quítala de FRONTERAS_DECLARADAS en el mismo commit.")


def test_labels_sigue_sin_llamador_en_produccion():
    """LO QUE HACE INOCUO EL DEFECTO DE `labels.py` NO ES UN ARREGLO: ES QUE NADIE LO LLAMA.

    `labels.py` pasa el `series` CRUDO al núcleo y pasa `markets.measurement_rule`
    —la PROSA— donde el núcleo espera `measurement_rule_code`. Cualquiera de las dos
    cosas basta para que `select_operator` levante `context_out_of_snapshot` en TODOS
    los mercados (medido, A-281). Hoy no liquida nada mal por una sola razón: no lo
    importa nadie fuera de sus tests.

    Esa razón es una propiedad del repositorio, no del módulo, y puede dejar de ser
    cierta en un commit de tres líneas. Así que se vigila.

    ESTE TEST NO CLAVA EL DEFECTO COMO COMPORTAMIENTO ESPERADO — que es justo lo que
    hace `test_labels.py:119` al afirmar `series_mismatch` sobre una fila con el nombre
    del ingestor dentro. Vigila la PRECONDICIÓN que lo mantiene dormido. El día que
    alguien cablee `labels.py`, este test se pone rojo y le obliga a arreglar las dos
    traducciones primero. Tarea #62.
    """
    llamadores = []
    for f in _ficheros():
        if f.name == "labels.py":
            continue
        texto = f.read_text()
        arbol = ast.parse(texto)
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.ImportFrom):
                if any(a.name == "labels" for a in nodo.names):
                    llamadores.append(str(f.relative_to(RAIZ)))
                if (nodo.module or "").endswith("labels"):
                    llamadores.append(str(f.relative_to(RAIZ)))
            elif isinstance(nodo, ast.Import):
                if any(a.name.endswith("labels") for a in nodo.names):
                    llamadores.append(str(f.relative_to(RAIZ)))
    assert not llamadores, (
        f"`labels.py` ha ganado un llamador en producción: {sorted(set(llamadores))}. "
        "Antes de cablearlo hay que traducir DOS vocabularios en él: `series` "
        "(ingestor -> núcleo) y `measurement_rule_code` (el CÓDIGO, no la prosa de "
        "`measurement_rule`). Sin eso el núcleo refuta todos los mercados con "
        "`context_out_of_snapshot`, y `missing_substrate()` dice READY igualmente: "
        "sólo mira presencia de columna, y además `REQUIRED_COLUMNS` pide "
        "`measurement_rule` cuando el núcleo parte por `measurement_rule_code`, así que "
        "pide la columna que no hace falta y no pide la que sí. Ver A-281 y tarea #62.")


# NO HAY UN CUARTO TEST QUE AFIRME `measurement_rule_code` EN `REQUIRED_COLUMNS`, Y LA
# RAZON ES UNA REGLA DEL PROYECTO, NO UN OLVIDO.
#
# Lo escribi, se puso rojo —correctamente: `REQUIRED_COLUMNS` pide `measurement_rule`— y
# lo retire. Un test rojo a proposito «para que la deuda no se olvide» no se puede
# fusionar bajo la regla de tests verdes verificados, y deja la suite rota para todos los
# demas. La deuda se acuerda en la tarea #62 y en A-281, que es donde vive.
#
# Y arreglar `labels.py` aqui tampoco: es codigo de liquidacion, y §34 del encargo de
# FASE 2 pide revision independiente para eso. La sesion B lleva sin responder desde
# ~15:00Z. Queda propuesto y sin tocar.
#
# Lo que si hace esta suite es poner el arreglo COMPLETO como condicion de cablear el
# modulo: el dia que `labels.py` gane un llamador en produccion, el test de arriba se
# pone rojo y nombra las tres cosas que hay que arreglar antes.
