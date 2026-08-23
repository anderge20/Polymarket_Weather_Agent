#!/usr/bin/env bash
# ============================================================================
# scripts/run.sh — Hetzner runner for the 2A+2B validation harness.
# Isolated: operates only under its own directory. Does NOT touch cmle-bot,
# no wallet, no orders. Creates a venv, installs the pipeline deps, runs
# scripts/validate_2b.py, and leaves the report in results/.
# The LOCAL report is the source of truth; paste.rs return is a separate step.
# ============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"   # bundle root (parent of scripts/)
cd "$HERE"
echo "[pmw-validate] root        : $HERE"

# ---- hard pre-checks (the harness also re-checks and reports them) ----------
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not found"; exit 1; }
PYV="$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')"
echo "[pmw-validate] python3     : $PYV"
[ -f scripts/validate_2b.py ] || { echo "ERROR: scripts/validate_2b.py missing"; exit 1; }
[ -d src/weather_agent ]       || { echo "ERROR: src/weather_agent missing"; exit 1; }
[ -d tests ]                   || { echo "ERROR: tests/ missing"; exit 1; }

# ---- venv (isolated) --------------------------------------------------------
if [ ! -d .venv ]; then
  python3 -m venv .venv || { echo "ERROR: venv failed (install python3-venv)"; exit 1; }
fi
# shellcheck disable=SC1091
. .venv/bin/activate
python -m pip install --upgrade pip >/dev/null 2>&1 || true
PIP_WARN='[pmw-validate] WARN: pip install reported errors; the harness preflight will record any missing deps'
if [ -f requirements-pipeline.txt ]; then
  python -m pip install -r requirements-pipeline.txt || echo "$PIP_WARN"
else
  python -m pip install duckdb pandas numpy scipy scikit-learn requests aiohttp websockets python-dateutil pytest || echo "$PIP_WARN"
fi

mkdir -p results
echo "[pmw-validate] running harness ..."
set +e
python scripts/validate_2b.py "$@"
RC=$?
set -e

echo "[pmw-validate] harness exit : $RC"
echo "[pmw-validate] REPORT        : $HERE/results/PHASE_2B_VALIDATION_REPORT.md"
echo "[pmw-validate] return (optional, separate step):"
echo "    curl --data-binary @$HERE/results/PHASE_2B_VALIDATION_REPORT.md https://paste.rs"
# The report is always written; a non-zero harness RC (e.g. a failed critical
# pre-check) is informational — the report explains it. Do not fail the wrapper.
exit 0
