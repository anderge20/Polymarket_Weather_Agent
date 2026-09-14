#!/usr/bin/env python3
"""REGRESION DE A-329 — los ocho casos del vigilante de ranuras, reproducibles.

POR QUE EXISTE. En A-329 y en A-330 estos ocho casos se corrieron a mano, y a mano se
volvieron a montar la segunda vez. Un banco que hay que reconstruir cada vez no es
reproducible: es una anecdota que sale igual porque la escribe la misma persona. Esto lo
clava.

QUE NO HACE. No toca `vigila_colector.py`. Lo importa y lo interroga. La unica palanca es
`PMW_PAPER`, que el propio vigilante ya expone.

DETERMINISMO. Los casos 1-4 son de CLASIFICACION y se comprueban llamando a `cobertura()`
con un `ahora` FIJO: `main()` usa `now()`, y un banco cuyo veredicto depende de la hora a la
que se ejecuta no es un banco. Los casos 5-8 son de ACCESO AL ALMACEN y ahi lo que importa
es el codigo de salida del proceso entero, asi que se corre `main()` por subproceso.
"""
from __future__ import annotations

import datetime as dt
import gzip
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
ORIGEN = Path(os.environ.get("PMW_PAPER", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-paper"))
#: `ahora` congelado para los casos de clasificacion, DERIVADO DEL BANCO y no escrito a mano.
#: MI PRIMER INTENTO LO ESCRIBIO A MANO (18:00Z) y el caso 4 "fallo": con el ultimo ciclo a
#: las 15:07 y un margen de ~7.000 s, a las 18:00 esa ranura ya NO esta en vuelo, esta
#: perdida -- y el instrumento tenia razon. Es el mismo error de fixture rancia que ya
#: cometi en A-330, por otra puerta: una fecha de banco escrita a mano caduca sola.
DESPUES_DEL_ULTIMO = 600.0   # s dentro del margen, para que la ultima ranura sea "en vuelo"


def _banco(tmp: Path) -> Path:
    """Copia del almacen real. Se muta la copia; el original no se toca NUNCA."""
    dst = tmp / "banco"
    shutil.copytree(ORIGEN / "paper_state" / "cycle_params",
                    dst / "paper_state" / "cycle_params")
    return dst


def _muta_gz(ruta: Path, viejo: str, nuevo: str) -> int:
    """Sustituye dentro de un shard gzip Y EXIGE QUE HAYA SUSTITUIDO ALGO.

    Esta funcion existe por un fallo mio: mute `"session_id": "col_` -- con espacio -- y el
    JSON real no lo lleva. La sustitucion no toco nada, el vigilante dio exit 0, y yo estuve
    a punto de anotar "el defecto D-4 ya no reproduce". Una mutacion que no muta produce
    exactamente la misma salida que un arreglo, y es la tercera vez en esta sesion que me
    pasa. Asi que aqui no se muta: se muta Y SE COMPRUEBA.
    """
    t = gzip.open(ruta, "rt").read()
    n = t.count(viejo)
    if n == 0:
        raise AssertionError(f"la mutacion no muta: {viejo!r} no aparece en {ruta.name}")
    with gzip.open(ruta, "wt") as f:
        f.write(t.replace(viejo, nuevo))
    return n


def _shards(raiz: Path) -> list[Path]:
    return sorted((raiz / "paper_state" / "cycle_params").glob("*/*/*/*.ndjson.gz"))


def _vigilante(paper: Path):
    """Importa el vigilante APUNTANDO a un almacen concreto. Recarga: PMW_PAPER se lee al importar."""
    import importlib
    os.environ["PMW_PAPER"] = str(paper)
    sys.path.insert(0, str(AQUI))
    import vigila_colector
    return importlib.reload(vigila_colector)


def _ahora_del_banco(paper: Path) -> dt.datetime:
    """`ahora` = ultimo ciclo del banco SIN MUTAR + 600 s. Se deriva una vez, del control."""
    v = _vigilante(paper)
    return max(c["t"] for c in v.ciclos()) + dt.timedelta(seconds=DESPUES_DEL_ULTIMO)


def _clasifica(paper: Path, ahora: dt.datetime):
    v = _vigilante(paper)
    cs = v.ciclos()
    perdidas, en_vuelo = v.cobertura(cs, ahora)
    return len(cs), perdidas, en_vuelo


def _exit_de_main(paper: Path) -> tuple[int, str]:
    env = dict(os.environ, PMW_PAPER=str(paper))
    p = subprocess.run([sys.executable, str(AQUI / "vigila_colector.py"), "--ultimos", "2"],
                       capture_output=True, text=True, env=env)
    return p.returncode, (p.stdout + p.stderr)


def main() -> int:
    casos, fallos = [], 0
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # ---- 1 · shard presente (control) -------------------------------------------
        (tmp / "c1").mkdir(); b = _banco(tmp / "c1")
        AHORA = _ahora_del_banco(b)
        n, per, vue = _clasifica(b, AHORA)
        ok = (per == [] and vue == [])
        casos.append(("1 shard presente (control)", ok,
                      f"{n} ciclos · perdidas {len(per)} · en vuelo {len(vue)}"))

        # ---- 2 · shard antiguo ausente ----------------------------------------------
        (tmp / "c2").mkdir(); b = _banco(tmp / "c2")
        sh = _shards(b); victima = sh[-6]; victima.unlink()
        n, per, vue = _clasifica(b, AHORA)
        ok = (len(per) == 1 and len(vue) == 0)
        casos.append(("2 shard antiguo ausente", ok,
                      f"perdidas {[f'{r:%m-%d %H:%M}Z' for r in per]} · en vuelo {len(vue)}"))
        ec, _ = _exit_de_main(b)
        casos.append(("2b main() se queja (exit 1)", ec == 1, f"exit={ec}"))

        # ---- 3 · dos shards ausentes -------------------------------------------------
        (tmp / "c3").mkdir(); b = _banco(tmp / "c3")
        sh = _shards(b); sh[-6].unlink(); sh[-8].unlink()
        n, per, vue = _clasifica(b, AHORA)
        ok = (len(per) == 2 and len(vue) == 0)
        casos.append(("3 dos shards ausentes", ok,
                      f"perdidas {[f'{r:%m-%d %H:%M}Z' for r in per]}"))

        # ---- 4 · ranura reciente: EN VUELO, no perdida -------------------------------
        # El ultimo shard del banco esta dentro del margen respecto de AHORA, asi que
        # quitarlo debe dar "aun no juzgable", NO "turno perdido". Es la distincion que
        # A-329 abrio: "fila ausente" no es "ciclo fallado".
        (tmp / "c4").mkdir(); b = _banco(tmp / "c4")
        sh = _shards(b); sh[-1].unlink()
        n, per, vue = _clasifica(b, AHORA)
        ok = (len(per) == 0 and len(vue) == 1)
        casos.append(("4 ranura reciente = EN VUELO", ok,
                      f"perdidas {len(per)} · en vuelo {[f'{r:%m-%d %H:%M}Z' for r in vue]}"))

        # ---- 5 · almacen inexistente -------------------------------------------------
        ec, sal = _exit_de_main(tmp / "no-existe")
        ok = (ec == 1 and "SIN DATOS" in sal)
        casos.append(("5 almacen inexistente", ok, f"exit={ec} · {'SIN DATOS' if 'SIN DATOS' in sal else sal[:60]!r}"))

        # ---- 6 · almacen vacio -------------------------------------------------------
        vacio = tmp / "c6" / "paper_state" / "cycle_params"; vacio.mkdir(parents=True)
        ec, sal = _exit_de_main(tmp / "c6")
        ok = (ec == 1 and "SIN DATOS" in sal)
        casos.append(("6 almacen vacio", ok, f"exit={ec} · {'SIN DATOS' if 'SIN DATOS' in sal else sal[:60]!r}"))

        # ---- 7 · shard ilegible (permisos) -------------------------------------------
        # Lo que se exige NO es que funcione: es que NO mienta. Un almacen que no se puede
        # leer entero tiene que levantar, no devolver una serie incompleta con exit 0.
        (tmp / "c7").mkdir(); b = _banco(tmp / "c7")
        sh = _shards(b); sh[-4].chmod(0o000)
        ec, sal = _exit_de_main(b)
        ok = (ec != 0)
        casos.append(("7 shard ilegible NO pasa por bueno", ok,
                      f"exit={ec} · {'PermissionError' if 'PermissionError' in sal else 'sin traza'}"))
        sh[-4].chmod(0o644)

        # ---- 7b · gzip ilegible ------------------------------------------------------
        (tmp / "c7b").mkdir(); b = _banco(tmp / "c7b")
        sh = _shards(b); sh[-4].write_bytes(b"esto no es gzip")
        ec, sal = _exit_de_main(b)
        ok = (ec != 0)
        casos.append(("7b gzip ilegible levanta", ok,
                      f"exit={ec} · {'BadGzipFile' if 'BadGzipFile' in sal else 'otra traza'}"))

        # ---- 8 · shard ANTIGUO valido pero con el id corrupto -------------------------
        # ESTO es D-4, y no lo que probe la primera vez: no es un gzip roto (eso levanta,
        # caso 7b) sino un gzip PERFECTO cuya fila no se puede atribuir a una ranura. La
        # fila se descarta, la ranura se queda sin cubrir, y el vigilante dice "TURNO
        # PERDIDO" -- «el ciclo no corrio» -- cuando la verdad es «corrio y su registro
        # esta roto». La deteccion acierta; el texto manda a buscar al sitio equivocado.
        #
        # DEFECTO CONOCIDO NO BLOQUEANTE: se REPRODUCE y se mide, no se arregla. Que este
        # caso diga OK significa "el defecto sigue exactamente donde lo dejamos".
        (tmp / "c8").mkdir(); b = _banco(tmp / "c8")
        sh = _shards(b); victima = sh[-6]
        _muta_gz(victima, '"session_id":"col_', '"session_id":"XXX_')
        ec, sal = _exit_de_main(b)
        confunde = "TURNO PERDIDO" in sal
        casos.append(("8 id corrupto antiguo = D-4 intacto", ec == 1 and confunde,
                      f"exit={ec} · {'dice TURNO PERDIDO (defecto vivo, como se dejo)' if confunde else 'YA NO lo dice: algo cambio'}"))

    print("=" * 92)
    print(f"REGRESION A-329 · {dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ} · "
          f"ahora congelado {AHORA:%Y-%m-%d %H:%MZ}")
    print("=" * 92)
    for nombre, ok, detalle in casos:
        fallos += 0 if ok else 1
        print(f"  [{'OK ' if ok else 'FALLA'}] {nombre:38s} {detalle}")
    print("=" * 92)
    print(f"  {len(casos) - fallos}/{len(casos)} casos como se esperaba")
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
