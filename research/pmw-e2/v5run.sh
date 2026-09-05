#!/bin/sh
# V5.2 — reanudar cuando la cuota diaria de Open-Meteo se haya restablecido. Idempotente.
cd /Users/mariaaleu/pmw-e2 || exit 1
python3 v5extract.py 2>&1 | tee -a v5extract.log; rc=$?; [ $rc -ne 0 ] && exit $rc
python3 v5uni.py     2>&1 | tee -a v5uni.log;     rc=$?; [ $rc -ne 0 ] && exit $rc
python3 v5eval.py    2>&1 | tee -a v5eval.log
