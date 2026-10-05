"""B5 — el plazo propio del ciclo, y la mitigacion de la espera del lock.

QUE PROBLEMA CIERRAN ESTOS TESTS. El ciclo de produccion reconstruye el almacen
entero en cada vuelta: 6 543 s de los 6 641 s medidos en
`col_20261005T180705Z_e88fee` son etapas `load:*`. El coste por fila es constante
(A-317) y el almacen crece ~19 200 filas/dia, asi que la duracion crece sin techo
y se come las ventanas siguientes. 3 y 4 de octubre: 6 de 8 ranuras de collect,
faltan 03:07 y 12:07 los dos dias.

LO QUE AQUI SE FIJA NO ES EL RENDIMIENTO. B5 queda MITIGADO, no resuelto: el
arreglo es la carga incremental (tarea #55), que no esta hecha. Lo que se fija es
que un ciclo no pueda crecer indefinidamente consumiendo el calendario, que su
terminacion por plazo sea distinguible de un exito, y que el valor del plazo
siga atado a la aritmetica de las ventanas en vez de a un numero de gusto.
"""
from __future__ import annotations

import fcntl
import importlib.util
import os
import subprocess
import sys
import textwrap
from datetime import timedelta
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "paper_cycle_deadline", _ROOT / "scripts" / "paper_cycle.py")
pc = importlib.util.module_from_spec(_SPEC)
sys.modules["paper_cycle_deadline"] = pc
_SPEC.loader.exec_module(pc)


#: Medido en produccion, no supuesto. Es la cota inferior del plazo: por debajo
#: de esto el plazo abortaria ciclos sanos.
DURACION_OBSERVADA_S = 6641.04
#: collect :07 cada 3 h -> 10 800 s. Las ventanas de `decide` son 02:40 y 11:40,
#: asi que la separacion mas estrecha es collect 00:07 -> decide 02:40 = 9 180 s.
SEPARACION_COLLECT_S = 10800.0
SEPARACION_A_DECIDE_S = 9180.0


def _ciclo(*, deadline_s=None, edad_s=0.0):
    """Un ciclo cuyo arranque se puede empujar al pasado, sin dormir."""
    cy = pc.Cycle(deadline_s=deadline_s, session_id="cyc_b5")
    if edad_s:
        cy.started_at = cy.started_at - timedelta(seconds=edad_s)
    return cy


# ============================================================ 1. ciclo normal
def test_un_ciclo_por_debajo_del_plazo_no_se_corta():
    cy = _ciclo(deadline_s=9000.0, edad_s=120.0)
    assert cy.over_deadline() is False
    pc.check_deadline(cy, next_stage="discover")   # no debe lanzar
    assert cy.stages == []                          # ni anotar nada
    assert cy.summary()["stopped"] is False


def test_el_plazo_consta_en_el_resumen_tambien_cuando_no_corta():
    """Un plazo que solo aparece cuando salta no permite comprobar con que plazo
    corrio el ciclo que NO salto."""
    assert _ciclo(deadline_s=9000.0).summary()["deadline_s"] == 9000.0


def test_un_plazo_nulo_lo_desactiva():
    cy = _ciclo(deadline_s=None, edad_s=10_000_000.0)
    assert cy.over_deadline() is False
    pc.check_deadline(cy, next_stage="discover")


# =================================================== 2-5. el ciclo que lo agota
@pytest.fixture
def agotado():
    cy = _ciclo(deadline_s=9000.0, edad_s=9001.0)
    with pytest.raises(pc.DeadlineExceeded):
        pc.check_deadline(cy, next_stage="collect:books")
    return cy


def test_el_ciclo_que_agota_el_plazo_queda_stopped(agotado):
    assert agotado.stages[-1]["status"] == pc.STOPPED
    assert agotado.summary()["stopped"] is True


def test_queda_registrada_la_etapa_activa(agotado):
    e = agotado.stages[-1]
    assert e["stage"] == "deadline"
    assert e["active_stage"] == "collect:books"


def test_queda_registrado_el_elapsed(agotado):
    e = agotado.stages[-1]
    # `elapsed_s` es el de SIEMPRE, entre etapas. `elapsed_s_total` es el
    # acumulado del ciclo, que es lo que el plazo mide.
    assert "elapsed_s" in e
    assert e["elapsed_s_total"] >= 9001.0
    assert e["deadline_s"] == 9000.0


def test_queda_registrado_el_motivo(agotado):
    assert agotado.stages[-1]["reason"] == "DEADLINE_SLOT"


def test_la_terminacion_por_plazo_no_se_confunde_con_un_exito(agotado):
    """Requisito 7: que no quede como OK por ninguna via."""
    estados = {s["status"] for s in agotado.stages}
    assert pc.OK not in estados
    assert agotado.summary()["stopped"] is True


# ====================================== el plazo por defecto y su justificacion
def test_el_plazo_por_defecto_respeta_sus_dos_cotas():
    """El numero no es de gusto: queda atado a la aritmetica de las ventanas.

    Si alguien lo cambia sin recalcular, este test cae."""
    d = pc.DEADLINE_S_DEFAULT
    # cota inferior: no abortar ciclos sanos
    assert d > DURACION_OBSERVADA_S, "abortaria ciclos sanos"
    # cota superior: no invadir la ventana de `decide` mas cercana, menos el
    # desmontaje (dump+params medidos en 8,04 s; se reservan 120 s)
    assert d <= SEPARACION_A_DECIDE_S - 120.0, "invadiria la ventana de decide"
    # y, por construccion, tampoco la suya propia
    assert d < SEPARACION_COLLECT_S


def test_la_espera_del_lock_esta_acotada_por_el_plazo():
    """(c) es segura SOLO porque (a) existe: el que sostiene el lock muere.

    Sin plazo, subir la espera permitiria esperar a un ciclo inmortal."""
    espera = 4800.0   # el valor que install.sh pone en el crontab
    assert espera < pc.DEADLINE_S_DEFAULT, (
        "una espera mayor que el plazo del titular permitiria una espera inutil")


# =============================== el corte NO puede ocurrir sobre la captura
def test_el_plazo_nunca_corta_entre_la_captura_y_su_volcado():
    """Polymarket no publica el libro L2 historico: `stage_collect` captura lo
    unico irrecuperable del proyecto y solo `stage_dump` lo persiste. Un corte
    entre las dos tiraria un dia de libros. Se fija sobre el texto fuente, como
    el proyecto ya hace con la puerta D0."""
    src = (_ROOT / "scripts" / "paper_cycle.py").read_text(encoding="utf-8")
    i_check = src.index('check_deadline(cy, next_stage="collect:books")')
    i_collect = src.index("stage_collect(cy, con,")
    i_dump = src.index("stage_dump(cy, con, root=args.store_root, session_id=session_id,\n"
                       "                   dataset_version=args.dataset_version",
                       i_collect)
    assert i_check < i_collect, "el ultimo control debe ir ANTES de capturar"
    assert "check_deadline" not in src[i_collect:i_dump], (
        "no puede haber un corte entre la captura y su volcado")


def test_tras_la_captura_el_exceso_se_anota_pero_no_aborta():
    src = (_ROOT / "scripts" / "paper_cycle.py").read_text(encoding="utf-8")
    assert 'reason="DEADLINE_SLOT_AFTER_CAPTURE"' in src
    assert '"deadline:overrun"' in src


# ============================================ 6-7. el lock y la vuelta siguiente
def _tomar_lock_en_subproceso(path: Path) -> subprocess.Popen:
    """Un hijo que toma el flock y se queda esperando, como hace el lanzador."""
    code = textwrap.dedent(f"""
        import fcntl, sys, time
        f = open({str(path)!r}, "w")
        fcntl.flock(f, fcntl.LOCK_EX)
        sys.stdout.write("tomado\\n"); sys.stdout.flush()
        time.sleep(60)
    """)
    p = subprocess.Popen([sys.executable, "-c", code],
                         stdout=subprocess.PIPE, text=True)
    assert p.stdout.readline().strip() == "tomado"
    return p


def _intentar_lock(path: Path) -> bool:
    with open(path, "w") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(f, fcntl.LOCK_UN)
            return True
        except OSError:
            return False


def test_el_lock_se_libera_al_terminar_el_proceso(tmp_path):
    lock = tmp_path / "run.lock"
    hijo = _tomar_lock_en_subproceso(lock)
    try:
        assert _intentar_lock(lock) is False, "el titular deberia excluir"
    finally:
        hijo.terminate(); hijo.wait(timeout=10)
    # El fichero sigue ahi -- es asi por diseno -- pero el cerrojo no.
    assert lock.exists()
    assert _intentar_lock(lock) is True, "el lock debe soltarse al morir el proceso"


def test_una_ejecucion_posterior_puede_arrancar(tmp_path):
    lock = tmp_path / "run.lock"
    primero = _tomar_lock_en_subproceso(lock)
    primero.terminate(); primero.wait(timeout=10)
    segundo = _tomar_lock_en_subproceso(lock)
    try:
        assert _intentar_lock(lock) is False   # el segundo lo tiene de verdad
    finally:
        segundo.terminate(); segundo.wait(timeout=10)


# ==================================== 8. la atribucion del salto sigue en pie
def test_el_lanzador_conserva_su_flock_y_su_evento_lock_timeout():
    """(c) cambia un valor de espera, NO el mecanismo de exclusion ni la
    atribucion. Una ranura perdida tiene que seguir siendo distinguible de un
    host que nunca disparo."""
    src = (_ROOT / "ops" / "hetzner" / "launcher.sh").read_text(encoding="utf-8")
    assert 'flock -w "${PMW_LOCK_WAIT:-900}" 9' in src, "el flock no se sustituye"
    assert '"event":"lock_timeout"' in src, "la atribucion del salto no se toca"
    assert "holder_age_s" in src


def test_el_crontab_desplegado_lleva_la_espera_y_su_justificacion():
    """El valor tiene que estar donde produccion lo lee de verdad."""
    src = (_ROOT / "ops" / "hetzner" / "install.sh").read_text(encoding="utf-8")
    lineas = [l for l in src.splitlines()
              if "launcher.sh" in l and l.lstrip().startswith(("7 ", "40 "))]
    assert len(lineas) == 3, f"se esperaban 3 lineas de cron, hay {len(lineas)}"
    for l in lineas:
        assert "PMW_LOCK_WAIT=4800" in l, f"sin espera declarada: {l}"
    assert "MITIGACION TEMPORAL DE B5" in src, "debe constar que es temporal"
    assert "#55" in src, "debe apuntar al arreglo de fondo pendiente"


# =============== 9. la espera no puede influir en ningun calculo
def test_la_espera_del_lock_no_entra_en_ningun_calculo():
    """`PMW_LOCK_WAIT` lo lee el lanzador y NADIE mas. Si un modulo de Python
    llegara a leerlo, podria influir en una senal, un edge o un PnL; mientras no
    lo lea, cambiarlo no puede alterar ningun resultado."""
    lectores = []
    for d in ("src", "scripts"):
        for f in (_ROOT / d).rglob("*.py"):
            if "PMW_LOCK_WAIT" in f.read_text(encoding="utf-8"):
                lectores.append(str(f.relative_to(_ROOT)))
    assert lectores == [], f"la espera del lock llega al codigo: {lectores}"


def test_el_plazo_tampoco_entra_en_ningun_calculo():
    """El plazo solo puede CORTAR el ciclo. No puede aparecer en las rutas que
    calculan senal, edge o PnL."""
    prohibidos = []
    for f in (_ROOT / "src" / "weather_agent").rglob("*.py"):
        txt = f.read_text(encoding="utf-8")
        if "deadline_s" in txt or "DEADLINE_SLOT" in txt:
            prohibidos.append(str(f.relative_to(_ROOT)))
    assert prohibidos == [], f"el plazo ha entrado en la libreria: {prohibidos}"


# ===================================== B5 esta mitigado, no resuelto
def test_el_plazo_declara_su_propia_caducidad():
    """El margen se consume: ~260 s de carga mas al dia. Que eso conste en el
    codigo es la diferencia entre mitigar y tapar."""
    src = (_ROOT / "scripts" / "paper_cycle.py").read_text(encoding="utf-8")
    bloque = src[src.index("DEADLINE_S_DEFAULT") - 2000:src.index("DEADLINE_S_DEFAULT") + 200]
    assert "#55" in bloque, "debe remitir al arreglo de fondo"
    margen_dias = (pc.DEADLINE_S_DEFAULT - DURACION_OBSERVADA_S) / 260.0
    assert 5.0 < margen_dias < 15.0, (
        f"el margen es de {margen_dias:.1f} dias; si cambia, recalcula el plazo "
        "y el texto que lo justifica")
