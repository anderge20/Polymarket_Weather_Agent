#!/bin/sh
# INSTANTANEA DE A-327 — todo lo que tiene que seguir igual hasta la medicion del 15-09.
#
# El "antes" y el "despues" los produce ESTE MISMO script. Si los produjeran dos textos
# escritos a mano, el diff compararia mi memoria conmigo mismo, no el sistema con el sistema.
#
# Uso:  ops/instantanea_a327.sh > ops/congelacion/A327_ANTES.txt
set -eu
CORPUS="${PMW_CORPUS:-/Users/mariaaleu/pmw-e2}"
REPO="${PMW_REPO:-/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-main}"

echo "## entrada A-327 en DECISIONS.md (inmutable)"
awk '/^## A-327 /{f=1} f&&/^## A-328 /{exit} f' "$CORPUS/DECISIONS.md" > /tmp/_a327_entrada.txt
echo "  lineas   $(wc -l < /tmp/_a327_entrada.txt | tr -d ' ')"
echo "  sha256   $(shasum -a 256 /tmp/_a327_entrada.txt | cut -d' ' -f1)"
echo
echo "## evalua_a327.py — el CRITERIO, escrito antes del dato"
echo "  sha256   $(shasum -a 256 "$CORPUS/ops/evalua_a327.py" | cut -d' ' -f1)"
grep -E "^PRED_|^AVISO|^ALARMA|^DECIDE|^COLLECT" "$CORPUS/ops/evalua_a327.py" | sed 's/^/    /'
echo
echo "## vigila_colector.py — el INSTRUMENTO"
echo "  sha256   $(shasum -a 256 "$CORPUS/ops/vigila_colector.py" | cut -d' ' -f1)"
echo
echo "## configuracion operacional de la que el instrumento DERIVA sus constantes"
echo "  install.sh   $(shasum -a 256 "$REPO/ops/hetzner/install.sh" | cut -d' ' -f1)"
echo "  launcher.sh  $(shasum -a 256 "$REPO/ops/hetzner/launcher.sh" | cut -d' ' -f1)"
echo
echo "## valores efectivos derivados AHORA"
PMW_REPO="$REPO" python3 -c "
import sys; sys.path.insert(0,'$CORPUS/ops')
import vigila_colector as v
print(f'    RANURAS      {v.RANURAS}')
print(f'    ESPERA_MAX   {v.ESPERA_MAX}')
print(f'    HUECO        {v.HUECO}')
print(f'    HOLGURA      {v.HOLGURA}')
print(f'    AVISO/ALARMA {v.AVISO}/{v.ALARMA}')
print(f'    ERA_CRON     {v.ERA_CRON:%Y-%m-%dT%H:%M:%SZ}')
"
