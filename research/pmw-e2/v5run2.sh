#!/bin/bash
# v5run2.sh — igual que v5run.sh pero con control de estado CORRECTO.
#
# Defecto corregido (REFUTATION, 2026-09-06): v5run.sh hace
#     python3 v5extract.py --smoke 3 | tee -a log ; rc=$?
# y en una tubería `$?` es el estado de `tee`, no el de python. El guardián del smoke
# test por tanto NUNCA dispara: si el smoke falla, se lanzaba igualmente la extracción
# completa de ~4.000 peticiones. Aquí se usa PIPESTATUS (bash) y `set -o pipefail`.
#
# Idempotente y reanudable: cada script retoma desde su artefacto parcial; el 429 se
# trata como guardar-y-salir.

set -o pipefail
cd /Users/mariaaleu/pmw-e2 || exit 1

step () {           # step <script> <log>
  echo "=== $(date -u +%FT%TZ) INICIO $1"
  python3 "$1" 2>&1 | tee -a "$2"
  rc=${PIPESTATUS[0]}
  echo "=== $(date -u +%FT%TZ) FIN $1 rc=$rc"
  if [ "$rc" -ne 0 ]; then
    echo "ABORTADO en $1 con rc=$rc (3 = cuota agotada: relanzar este script continúa donde quedó)"
    exit "$rc"
  fi
}

# El smoke ya se ejecutó y devolvió SMOKE_OK antes de lanzar esto.
step v5extract.py v5extract.log
step v5uni.py     v5uni.log
step v5eval.py    v5eval.log

echo "=== $(date -u +%FT%TZ) CADENA V5 COMPLETA"
