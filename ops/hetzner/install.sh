#!/usr/bin/env bash
# =============================================================================
# ops/hetzner/install.sh — put the paper-mode schedule on this host
# =============================================================================
# Idempotent: safe to re-run after every `git pull`. Installs the venv, the
# state checkout and the cron entries, and nothing else.
#
# The schedule mirrors what Actions was supposed to do, in UTC:
#   collector   every 3 h at :07     — book snapshots, unrecoverable if missed
#   decide      02:40  lead  9 h     — target = today
#   decide      11:40  lead 24 h     — target = tomorrow
#
# The decision cycles run FAIL-CLOSED until /opt/pmw/PAPER_TAU exists. Creating
# that file is what starts trading, and R24 P12 requires the acceptance
# criterion to be frozen and hashed BEFORE it exists. Do not create it casually.
set -euo pipefail
ROOT=/opt/pmw
REPO=$ROOT/repo

# THE SAME TRAP AS A-89, IN THE SCRIPT THAT EXISTS TO AVOID IT.
# The `git reset --hard` below rewrites the checkout THIS FILE lives in. If the
# target ref does not carry ops/, the reset deletes the script bash is still
# reading — half-executed, no error, and the cron left in whatever state the
# first half produced. Verified on 2026-09-09: origin/main did not contain ops/
# until PR #14 landed, so the condition was live, not theoretical.
#
# A-89 diagnosed this and the fix went only to the launcher, because that was
# where it had hurt. Fixing the instance is not fixing the class. So: copy out
# and re-exec BEFORE touching git. Copied, not symlinked, for the same reason.
# BOTH SIDES RESOLVED. `pwd -P` resolves symlinks, so comparing it against a
# `$REPO` that may not be resolved silently never matches — the guard looks
# installed and does nothing, which is the failure mode it exists to prevent.
# Caught by the test, not by reading it: on a host where /opt is a link, the
# unresolved form would have sailed straight through.
# `$0` ENTIRE, not just its directory. `pwd -P` on `dirname` resolves the
# DIRECTORY while `basename` keeps the LINK's name, so an operator convenience
# like /usr/local/bin/pmw-install -> $REPO/ops/hetzner/install.sh produced a
# SELF that matched nothing while the file bash was reading sat squarely inside
# the checkout. Found by session B, who tried the four invocation forms; the
# other three (direct path, `bash install.sh`, relative path) already fired.
SELF=$(readlink -f "$0")
REPO_P=$(cd "$REPO" 2>/dev/null && pwd -P || echo "$REPO")
case "$SELF" in
  "$REPO_P"/*)
    mkdir -p "$ROOT/bin"
    install -m 0755 "$SELF" "$ROOT/bin/install.sh"
    echo "install.sh: re-exec from $ROOT/bin/install.sh (outside the checkout)"
    exec "$ROOT/bin/install.sh" "$@"
    ;;
esac

command -v git >/dev/null || { echo "git required"; exit 1; }
[ -d "$REPO/.git" ] || git clone -q git@github.com:anderge20/Polymarket_Weather_Agent.git "$REPO"
git -C "$REPO" fetch -q origin && git -C "$REPO" reset -q --hard origin/main

if [ ! -x "$ROOT/venv/bin/python" ]; then
  python3 -m venv "$ROOT/venv"
  "$ROOT/venv/bin/pip" install -q --upgrade pip
fi
"$ROOT/venv/bin/pip" install -q -r "$REPO/requirements-paper.txt"

# The cron block is delimited so re-running replaces it instead of stacking.
BEGIN='# >>> pmw paper mode >>>'
END='# <<< pmw paper mode <<<'
NEW=$(cat <<CRON
$BEGIN
# UTC. Collector every 3 h; a missed book slot is not recoverable.
# PMW_GENERATOR: la linea del crontab es el UNICO sitio que sabe que esto lo
# dispara cron. El launcher se declara `hetzner-launcher` y `run_cycle.sh` no
# inventa nada, asi que los tres casos quedan distinguibles en `cycle_params`.
#
# PMW_LOCK_WAIT=4800 -- MITIGACION TEMPORAL DE B5, NO UN ARREGLO DE RENDIMIENTO.
# El ciclo tarda 6 641 s medidos (col_20261005T180705Z_e88fee) porque reconstruye
# el almacen entero en cada vuelta: 6 543 s de 6 641 son etapas load:*. Con los
# 900 s por defecto, el collect de :07 que cae sobre un decide en marcha espera
# 900 s, se rinde y se salta -- medido los dias 3 y 4 de octubre: faltan 03:07 y
# 12:07 los dos dias, 6 de 8 ventanas.
#
# DE DONDE SALE 4800, que no es copiar un numero redondo:
#   * Hace falta cubrir el solape medido: un decide de 02:40 que dura 6 641 s
#     acaba ~04:30:41, asi que el collect de 03:07 necesita esperar 4 781 s.
#   * El limite sin cascada seria 10 800 - 6 641 = 4 159 s: por encima, el que
#     espera acaba dentro de la ventana siguiente. LOS DOS NO CABEN, y eso es
#     precisamente por que esto es una mitigacion: 4 800 cubre el solape (4 781)
#     y excede el limite sin cascada en 641 s.
#   * La cascada que eso produce esta ACOTADA a una ventana y se despeja sola: el
#     siguiente slot espera ~641 s y corre, y el hueco de 3 h absorbe el resto.
#   * Y no puede ser indefinida, porque el plazo del ciclo lo impide: el que
#     sostiene el lock muere a los 9 000 s (DEADLINE_S_DEFAULT) y el que espera
#     nunca espera mas de 4 800 s. Las dos partes acotadas. SIN el plazo, subir
#     esta espera seria peligroso; con el, es seguro.
#
# La atribucion no cambia: si aun asi se agota, launcher.sh sigue encolando su
# evento lock_timeout con holder_age_s, que es lo que distingue una ranura
# perdida de un host que nunca disparo. El flock tampoco cambia.
#
# ESTO NO RESUELVE EL CRECIMIENTO. El almacen suma ~260 s de carga al dia, asi que
# el margen se consume. El arreglo es la tarea #55 (carga incremental), PENDIENTE.
7 */3 * * * PMW_GENERATOR=hetzner-cron PMW_LOCK_WAIT=4800 $ROOT/bin/launcher.sh collect    >> $ROOT/log/collect.log 2>&1
40 2 * * *  PMW_GENERATOR=hetzner-cron PMW_LOCK_WAIT=4800 $ROOT/bin/launcher.sh decide 9   >> $ROOT/log/cycle.log   2>&1
40 11 * * * PMW_GENERATOR=hetzner-cron PMW_LOCK_WAIT=4800 $ROOT/bin/launcher.sh decide 24  >> $ROOT/log/cycle.log   2>&1
$END
CRON
)
mkdir -p "$ROOT/log" "$ROOT/bin"
# The launcher lives OUTSIDE the checkout so a `git reset` can never delete the
# script that is running. Copied, not symlinked, for the same reason.
install -m 0755 "$REPO/ops/hetzner/launcher.sh" "$ROOT/bin/launcher.sh"
[ -f "$ROOT/REF" ] || echo main > "$ROOT/REF"
( crontab -l 2>/dev/null | sed "/$BEGIN/,/$END/d"; echo "$NEW" ) | crontab -
echo "cron installed:"; crontab -l | sed -n "/$BEGIN/,/$END/p"
echo
# VERIFIED, not assumed: this host is Etc/UTC, so the cron fields above are UTC
# and match the anchors R8/R24 §5 are written in. If this ever prints anything
# else, the schedule is silently shifted and every `drift_h` in the run is wrong.
TZNAME=$(timedatectl show -p Timezone --value 2>/dev/null || date +%Z)
echo "host timezone: $TZNAME"
[ "$TZNAME" = "Etc/UTC" ] || [ "$TZNAME" = "UTC" ] || {
  echo "REFUSING: the cron entries are written in UTC and this host is $TZNAME."
  echo "Set the host to UTC (timedatectl set-timezone Etc/UTC) and re-run."
  exit 1
}
