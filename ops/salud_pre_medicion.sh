#!/bin/sh
# SALUD PREVIA A LA MEDICION DE A-327 — lo unico que el §11 del encargo permite correr
# entre el merge de #58 y el dato del 15-09 03:07Z.
#
# NO mide la prediccion. Comprueba que el ciclo PODRA observarse. Son cosas distintas y la
# segunda no debe contaminar la primera: aqui no se lee ni una espera ni una duracion.
#
# LA TERCERA PUERTA DE #61. El vigilante deriva sus constantes de un CHECKOUT LOCAL
# (`PMW_REPO`), y el host ejecuta `origin/main`. Nada garantiza que coincidan: el checkout
# de `wt-main` estaba 6 commits por detras cuando lo mire, y sus `ops/hetzner/*` resultaron
# identicos por suerte, no por construccion. No es duplicacion (A-331 la cerro) ni override
# de entorno (D-3): es una REF RANCIA, y es la unica de las tres que puedo neutralizar sin
# tocar nada, comprobandola.
set -eu
CORPUS="${PMW_CORPUS:-/Users/mariaaleu/pmw-e2}"
REPO="${PMW_REPO:-/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-main}"
PAPER="${PMW_PAPER:-/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-paper}"
malo=0
di() { printf '  [%s] %s\n' "$1" "$2"; [ "$1" = "OK " ] || malo=1; }

echo "SALUD PRE-MEDICION · $(date -u +%FT%TZ)"

git -C "$REPO" fetch -q origin
for f in ops/hetzner/install.sh ops/hetzner/launcher.sh; do
  a=$(shasum -a 256 "$REPO/$f" | cut -d' ' -f1)
  b=$(git -C "$REPO" show "origin/main:$f" | shasum -a 256 | cut -d' ' -f1)
  [ "$a" = "$b" ] && di "OK " "$f == origin/main" \
                  || di "MAL" "$f DIFIERE de origin/main: el instrumento mide otro contrato"
done

PMW_REPO="$REPO" python3 - "$CORPUS" <<'PY' || malo=1
import sys; sys.path.insert(0, sys.argv[1] + "/ops")
import vigila_colector as v
esperado = {"HOLGURA": 2520.0, "HUECO": 1620.0, "ESPERA_MAX": 900.0,
            "AVISO": 300.0, "ALARMA": 600.0}
mal = [k for k, x in esperado.items() if getattr(v, k) != x]
ranuras = sorted(v.RANURAS) == sorted([(0,7),(2,40),(3,7),(6,7),(9,7),(11,40),(12,7),(15,7),(18,7),(21,7)])
print(f"  [{'OK ' if not mal else 'MAL'}] constantes derivadas: " +
      " ".join(f"{k}={getattr(v,k):.0f}" for k in esperado))
print(f"  [{'OK ' if ranuras else 'MAL'}] las 10 ranuras contratadas")
raise SystemExit(1 if (mal or not ranuras) else 0)
PY

PMW_PAPER="$PAPER" python3 "$CORPUS/ops/vigila_colector.py" --ultimos 1 >/tmp/_salud_vig.txt 2>&1 \
  && di "OK " "el vigilante corre y no ve ranuras perdidas ni alarmas" \
  || di "MAL" "el vigilante se queja: $(grep -m1 'ALARMA\|PERDIDA\|SIN DATOS' /tmp/_salud_vig.txt || echo 'ver /tmp/_salud_vig.txt')"

# `|| ec=$?` y no un comando suelto: con `set -e`, un `exit 2` mata el script ANTES de
# poder clasificarlo -- y 2 aqui no es un error, es "todavia no ha ocurrido".
ec=0; PMW_PAPER="$PAPER" python3 "$CORPUS/ops/evalua_a327.py" >/tmp/_salud_ev.txt 2>&1 || ec=$?
case $ec in
  2) di "OK " "A-327 PENDING: el ciclo del 15-09 aun no existe (correcto antes del dato)" ;;
  0) di "OK " "A-327 YA EVALUABLE: corre ops/evalua_a327.py y registra el resultado" ;;
  *) di "MAL" "el evaluador falla como instrumento: ver /tmp/_salud_ev.txt" ;;
esac

echo
[ "$malo" = 0 ] && echo "  SANO: el ciclo del 15-09 podra observarse." \
                || echo "  NO SANO: arreglar ANTES del dato, y registrar que se toco."
exit "$malo"
