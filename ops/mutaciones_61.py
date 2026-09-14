#!/usr/bin/env python3
"""BANCO DE MUTACIONES DE #61 — §7 del encargo del merge de #58.

Cada mutacion se aplica sobre una COPIA del arbol del repo, nunca sobre el original, y
se exige que la mutacion haya mutado algo (`_muta`): una sustitucion que no sustituye
produce la misma salida que un arreglo, y ya me ha enganado tres veces en esta sesion.

LA PREDICCION ESTA ESCRITA AQUI, EN EL CODIGO, ANTES DE CORRERLO. Si una fila sale
distinta de lo previsto, lo que cambia es el informe, no la prediccion.

DISCREPANCIA DECLARADA CON EL §7 DEL ENCARGO, y se dice antes de medir:
el encargo espera que H2b -- cambiar los tres `PMW_LOCK_WAIT` coherentemente -- PASE.
Eso es cierto del VIGILANTE (fuente unica: recalcula HOLGURA = 1620+1800 = 3420 y sigue
midiendo bien) y es FALSO de la SUITE, a proposito: la guarda fija el valor contratado en
900, asi que un cambio coherente tambien tiene que aparecer en el diff de alguien. Si la
suite dejara pasar un 1800 coherente, el horario contratado podria desplazarse en silencio,
que es justo lo que el criterio 2 del §17 prohibe. Se mide LO QUE HACE CADA UNO.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-main"))
VIGILANTE = Path(__file__).resolve().parent / "vigila_colector.py"
PAPER = os.environ.get("PMW_PAPER", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-paper")


def _arbol(tmp: Path) -> Path:
    """Copia minima del repo: lo que las guardas leen."""
    d = tmp / "repo"
    (d / "ops" / "hetzner").mkdir(parents=True)
    (d / "tests").mkdir()
    (d / "scripts").mkdir()
    for r in ("ops/hetzner/install.sh", "ops/hetzner/launcher.sh",
              "tests/test_configuracion_operacional.py", "scripts/paper_cycle.py"):
        shutil.copy2(REPO / r, d / r)
    return d


def _muta(ruta: Path, viejo: str, nuevo: str, veces: int | None = None) -> None:
    t = ruta.read_text()
    n = t.count(viejo)
    if n == 0:
        raise AssertionError(f"la mutacion no muta: {viejo!r} ausente de {ruta.name}")
    if veces is None:
        ruta.write_text(t.replace(viejo, nuevo))
    else:
        ruta.write_text(t.replace(viejo, nuevo, veces))


def _suite(arbol: Path) -> tuple[int, str]:
    p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:randomly",
                        str(arbol / "tests" / "test_configuracion_operacional.py")],
                       capture_output=True, text=True, cwd=str(arbol))
    return p.returncode, p.stdout + p.stderr


def _vigila(arbol: Path) -> tuple[int, str]:
    env = dict(os.environ, PMW_REPO=str(arbol), PMW_PAPER=PAPER)
    p = subprocess.run([sys.executable, str(VIGILANTE), "--ultimos", "1"],
                       capture_output=True, text=True, env=env)
    return p.returncode, p.stdout + p.stderr


CRON_VIEJO = "7 */3 * * *"
CRON_NUEVO = "9 */4 * * *"


def casos():
    """(nombre, mutador, suite_esperada, vigilante_esperado). 'falla'/'pasa'/'levanta'."""
    def r2(a):
        _muta(a / "ops/hetzner/install.sh", CRON_VIEJO, CRON_NUEVO)

    def h2a(a):
        _muta(a / "ops/hetzner/launcher.sh", "PMW_LOCK_WAIT:-900", "PMW_LOCK_WAIT:-1800", veces=1)

    def h2b(a):
        _muta(a / "ops/hetzner/launcher.sh", "PMW_LOCK_WAIT:-900", "PMW_LOCK_WAIT:-1800")

    def tz_borrar(a):
        p = a / "ops/hetzner/install.sh"
        t = p.read_text()
        m = re.search(r'\[ "\$TZNAME" = "Etc/UTC" \].*?\|\| \{.*?\n\}\n', t, re.S)
        assert m, "no encuentro la guarda de timezone para borrarla"
        p.write_text(t[:m.start()] + t[m.end():])

    def tz_renombrar(a):
        _muta(a / "ops/hetzner/install.sh", "timedatectl show -p Timezone",
              "NOtimedatectl show -p Timezone")

    def tz_degradar(a):
        p = a / "ops/hetzner/install.sh"
        t = p.read_text()
        m = re.search(r'(\[ "\$TZNAME" = "Etc/UTC" \].*?\|\| \{)(.*?)(\n\})', t, re.S)
        assert m, "no encuentro la guarda de timezone para degradarla"
        cuerpo = m.group(2).replace("exit 1", "true")
        assert cuerpo != m.group(2), "la degradacion no degrada: no habia `exit 1`"
        p.write_text(t[:m.start(2)] + cuerpo + t[m.end(2):])

    return [
        ("control (sin mutar)", lambda a: None, "pasa", "pasa"),
        ("R2  horario del cron 7*/3 -> 9*/4", r2, "falla", "levanta"),
        ("H2a un solo PMW_LOCK_WAIT a 1800", h2a, "falla", "levanta"),
        ("H2b los TRES a 1800 (coherente)", h2b, "falla", "pasa"),
        ("TZ-a borrar la guarda entera", tz_borrar, "falla", "pasa"),
        ("TZ-b renombrar el binario", tz_renombrar, "falla", "pasa"),
        ("TZ-c degradar exit 1 -> true", tz_degradar, "falla", "pasa"),
    ]


def main() -> int:
    filas, mal = [], 0
    for nombre, mut, esp_suite, esp_vig in casos():
        with tempfile.TemporaryDirectory() as td:
            a = _arbol(Path(td))
            mut(a)
            ec_s, sal_s = _suite(a)
            ec_v, sal_v = _vigila(a)
        vis_s = "pasa" if ec_s == 0 else "falla"
        # el vigilante "levanta" = se niega a arrancar con un RuntimeError propio
        vis_v = ("levanta" if ("RuntimeError" in sal_v or "Traceback" in sal_v)
                 else "pasa" if ec_v in (0, 1) else "otro")
        ok = (vis_s == esp_suite and vis_v == esp_vig)
        mal += 0 if ok else 1
        filas.append((nombre, esp_suite, vis_s, esp_vig, vis_v, ok))

    print("=" * 96)
    print("BANCO DE MUTACIONES #61 · suite de guardas y vigilante, por separado")
    print("=" * 96)
    print(f"  {'mutacion':38s} {'suite esp':>10s} {'obs':>7s}   {'vigil esp':>10s} {'obs':>9s}")
    for n, es, os_, ev, ov, ok in filas:
        print(f"  [{'OK ' if ok else 'XX '}] {n:33s} {es:>10s} {os_:>7s}   {ev:>10s} {ov:>9s}")
    print("=" * 96)
    print(f"  {len(filas) - mal}/{len(filas)} como se predijo")
    return 1 if mal else 0


if __name__ == "__main__":
    raise SystemExit(main())
