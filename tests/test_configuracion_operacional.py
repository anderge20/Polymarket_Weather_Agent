"""La configuracion operacional no puede cambiar sin que algo lo diga. Defecto #61.

QUE DEMOSTRO A-330, POR MUTACION. Cambiando SOLO el horario del crontab (`7 */3` -> `9 */4`)
la suite seguia verde. Cambiando SOLO el default de `PMW_LOCK_WAIT` (900 -> 1800) la suite
seguia verde. Y `PMW_LOCK_WAIT` no tiene una definicion: es un default de shell repetido
TRES veces en el mismo fichero.

Estos tests son las guardas que faltaban. No cambian ningun valor: FIJAN el que hay, para
que un cambio tenga que ser deliberado y quede en el diff de alguien.

QUE NO CUBREN, y se dice aqui para que nadie lo lea como mas de lo que es: si el host
exporta `PMW_LOCK_WAIT` en el entorno, el comportamiento real cambia y estas guardas no se
enteran -- leen el FICHERO, no el proceso. Es un defecto DISTINTO (D-3 de A-330) y su
arreglo toca `launcher.sh`, que no se toca antes de la prueba prospectiva. El ultimo test
de este fichero lo deja clavado en vez de dejarlo implicito.
"""
from __future__ import annotations

import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parents[1]
INSTALL = (RAIZ / "ops" / "hetzner" / "install.sh").read_text()
LAUNCHER = (RAIZ / "ops" / "hetzner" / "launcher.sh").read_text()

#: El contrato operacional, escrito una vez aqui y comparado con lo que se instala.
#: `7 */3` collect cada 3 h · `40 2` decide 9 · `40 11` decide 24. Todo UTC.
HORARIO_ESPERADO = {("7", "*/3", "collect"), ("40", "2", "decide"), ("40", "11", "decide")}
ESPERA_LOCK_ESPERADA = "900"


def _lineas_de_cron() -> set[tuple[str, str, str]]:
    """Las planificaciones que `install.sh` mete en el crontab, reconocidas por lo que SON.

    No se delimita por los marcadores `>>> pmw paper mode >>>`: esas cadenas aparecen dos
    veces cada una -- al definir BEGIN/END y al expandirlas dentro del heredoc -- y un
    `re.search` no codicioso casa el hueco vacio entre las dos definiciones.
    """
    out = set()
    for linea in INSTALL.splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "launcher.sh" not in linea:
            continue
        m = re.match(r"^(\d{1,2})\s+(\*/\d{1,2}|\d{1,2})\s+\*\s+\*\s+\*\s+.*?"
                     r"launcher\.sh\s+(\w+)", linea)
        if m:
            out.add((m.group(1), m.group(2), m.group(3)))
    return out


def test_el_horario_instalado_es_el_contratado():
    """R2: cambiar SOLO el crontab tiene que fallar aqui.

    Antes de esta guarda, mutar `7 */3` a `9 */4` dejaba la suite verde y el vigilante
    seguia esperando las ranuras viejas -- alarmaria por ranuras que cron ya no dispara y
    seria ciego a las que si. Las dos direcciones del mismo agujero."""
    visto = _lineas_de_cron()
    assert visto == HORARIO_ESPERADO, (
        f"el horario del crontab ha cambiado.\n  instalado: {sorted(visto)}\n"
        f"  contratado: {sorted(HORARIO_ESPERADO)}\n"
        "Si el cambio es deliberado, actualiza HORARIO_ESPERADO **y** comprueba que "
        "`ops/vigila_colector.py` deriva las mismas ranuras (las lee de este fichero).")


def test_la_espera_del_lock_es_la_contratada_y_UNA_SOLA():
    """H2: cambiar SOLO el default de `PMW_LOCK_WAIT` tiene que fallar aqui.

    Y ademas: los tres sitios donde aparece el default tienen que decir lo MISMO. Tres
    literales iguales por costumbre no son una definicion; son tres oportunidades de
    divergir."""
    vistos = re.findall(r"PMW_LOCK_WAIT:-(\d+)", LAUNCHER)
    assert vistos, "no encuentro el default de PMW_LOCK_WAIT en launcher.sh"
    assert len(set(vistos)) == 1, (
        f"PMW_LOCK_WAIT tiene defaults DISTINTOS en el mismo fichero: {sorted(set(vistos))}")
    assert vistos[0] == ESPERA_LOCK_ESPERADA, (
        f"la espera del lock ha cambiado: {vistos[0]} s (contratada {ESPERA_LOCK_ESPERADA}). "
        "`ops/vigila_colector.py` la lee de aqui para calcular la holgura y el plazo.")


def test_el_host_se_declara_UTC_y_la_instalacion_se_niega_si_no():
    """La ranura `03:07` sólo significa una cosa si el host es UTC, y eso se VERIFICA.

    No es una suposicion documentada: `install.sh` consulta `timedatectl` y aborta. Esta
    guarda existe porque el dia que alguien quite esa comprobacion, las ranuras se
    desplazarian en silencio y todos los `drift_h` de la corrida serian falsos."""
    #: La INVOCACION, no la subcadena. Mi primera version afirmaba `"timedatectl" in
    #: INSTALL` y la mutacion `timedatectl` -> `NOtimedatectl` la dejaba pasar: un `in` de
    #: subcadena no es una asercion sobre lo que el script EJECUTA.
    assert re.search(r"(?<![\w-])timedatectl\s+show\s+-p\s+Timezone", INSTALL), (
        "install.sh ya no consulta `timedatectl show -p Timezone`")
    guarda = re.search(r'\[ "\$TZNAME" = "Etc/UTC" \].*?\|\| \{(.*?)\n\}',
                       INSTALL, re.S)
    assert guarda, "install.sh ya no tiene la guarda `[ TZNAME = Etc/UTC ] || { ... }`\n"
    assert re.search(r"REFUSING", guarda.group(1)), (
        "la guarda de timezone ya no se NIEGA: degradaria en silencio")
    assert re.search(r"\bexit\s+1\b", guarda.group(1)), (
        "la guarda imprime pero ya no aborta: un aviso no es una negativa")


def test_CARACTERIZACION_el_override_de_entorno_no_deja_rastro():
    """DEFECTO VIVO D-3 (A-330). Cuando se arregle, este test cambia a proposito.

    `launcher.sh` usa `${PMW_LOCK_WAIT:-900}` sin exportarlo y el ciclo no registra el valor
    efectivo en `cycle_params` (35 campos, ninguno es este). Un `export PMW_LOCK_WAIT=1800`
    en el host cambia el comportamiento REAL -- cuanto espera el lock antes de saltarse una
    ranura -- y ni la suite ni el vigilante se enteran.

    PRECISION QUE ME COSTO UNA CORRECCION, porque la version anterior de esta nota decia
    "no se registra en ningun sitio" y ESO ES FALSO: `launcher.sh:88` escribe
    `lock_timeout.waited_s` con el valor efectivo, y `stage_host_events` lo arrastra a un
    shard. Pero SOLO por la ruta de timeout. Por la ruta feliz -- el lock se coge, el ciclo
    corre -- no queda en ningun sitio. El efecto util es peor que "invisible": el vigilante
    calcula la HOLGURA con el default del fichero y juzga con ella TODOS los ciclos buenos,
    y solo aprenderia el valor verdadero del primer salto, que es exactamente el evento que
    la holgura existe para anticipar. Se entera cuando ya no sirve.

    El arreglo es de una linea en cada sitio (exportarlo en `launcher.sh`, leerlo en
    `cycle_params` igual que se lee `PMW_GENERATOR`), y NO se hace ahora: tocaria el codigo
    que el host ejecuta antes de la prueba prospectiva de A-327.

    Se clava en vez de dejarse implicito porque un defecto que no esta en ningun test es un
    defecto que se olvida."""
    assert "export PMW_LOCK_WAIT" not in LAUNCHER, (
        "launcher.sh ya exporta PMW_LOCK_WAIT: el defecto D-3 puede estar arreglado. "
        "Comprueba que `cycle_params` registra el valor efectivo y actualiza este test.")
    ciclo = (RAIZ / "scripts" / "paper_cycle.py").read_text()
    assert "PMW_LOCK_WAIT" not in ciclo, (
        "paper_cycle.py ya menciona PMW_LOCK_WAIT: si lo registra, D-3 esta arreglado y "
        "este test de caracterizacion tiene que cambiar.")
