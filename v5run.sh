#!/bin/bash
# CORREGIDO 2026-09-06 (defecto hallado por la sesión revisora, D9): sin pipefail, `rc=$?` tras `| tee` era el estado de tee.
set -o pipefail
# V5.2/V5.3 — reanudar cuando la cuota diaria de Open-Meteo se haya restablecido. Idempotente.
# 1) SMOKE: 3 claves (≈15 peticiones). Si la identificación de componente o f fallan, se detiene sin gastar cuota.
cd /Users/mariaaleu/pmw-e2 || exit 1
python3 v5extract.py --smoke 3 2>&1 | tee -a v5extract.log; rc=$?; [ $rc -ne 0 ] && { echo "SMOKE falló (rc=$rc); no se lanza la extracción completa"; exit $rc; }
# 2) extracción completa (reanudable) → universo §14 → evaluación
python3 v5extract.py 2>&1 | tee -a v5extract.log; rc=$?; [ $rc -ne 0 ] && exit $rc
python3 v5uni.py     2>&1 | tee -a v5uni.log;     rc=$?; [ $rc -ne 0 ] && exit $rc
python3 v5eval.py    2>&1 | tee -a v5eval.log
