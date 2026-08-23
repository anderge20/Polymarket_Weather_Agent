#!/usr/bin/env bash
# ============================================================================
# scripts/package.sh — build a SELF-CONTAINED validator for Hetzner transport.
# Run on YOUR MAC from the repo root:   bash scripts/package.sh
# Produces ./pmw_validate.sh (all needed code embedded as a base64 tar.gz).
# Transport it to Hetzner via paste.rs (see printed instructions); the Hetzner
# side is then a SINGLE command:  curl -fsSL <url> | bash
# ============================================================================
set -euo pipefail

cd "$(cd "$(dirname "$0")/.." && pwd)"   # repo root
OUT="pmw_validate.sh"
PAYLOAD="$(mktemp "${TMPDIR:-/tmp}/pmw_payload.XXXXXX")"

# Minimal file set the harness needs (NO old flat modules, NO app/, NO data/).
FILES=(
  "src/weather_agent/__init__.py"
  "src/weather_agent/config.py"
  "src/weather_agent/database.py"
  "src/weather_agent/polymarket"
  "tests"
  "requirements-pipeline.txt"
  "scripts/validate_2b.py"
  "scripts/run.sh"
)
for f in "${FILES[@]}"; do
  [ -e "$f" ] || { echo "ERROR: missing $f (run from the repo root)"; exit 1; }
done

tar --exclude='__pycache__' --exclude='*.pyc' -czf "$PAYLOAD" "${FILES[@]}"
B64="$(base64 < "$PAYLOAD" | tr -d '\n')"
PSIZE="$(wc -c < "$PAYLOAD" | tr -d ' ')"

{
  printf '%s\n' '#!/usr/bin/env bash'
  printf '%s\n' '# Self-contained 2A+2B validation bundle for Hetzner (isolated in /opt/pmw-validate).'
  printf '%s\n' '# Does NOT touch cmle-bot. No wallet, no orders. Only Gamma sample + connectivity pings.'
  printf '%s\n' 'set -euo pipefail'
  printf '%s\n' 'DIR="${PMW_DIR:-/opt/pmw-validate}"'
  printf '%s\n' 'command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 required"; exit 1; }'
  printf '%s\n' 'command -v base64  >/dev/null 2>&1 || { echo "ERROR: base64 required";  exit 1; }'
  printf '%s\n' 'command -v tar     >/dev/null 2>&1 || { echo "ERROR: tar required";     exit 1; }'
  printf '%s\n' 'if ! mkdir -p "$DIR" 2>/dev/null; then sudo mkdir -p "$DIR" && sudo chown "$(id -u)":"$(id -g)" "$DIR"; fi'
  printf "PMW_PAYLOAD_B64='%s'\n" "$B64"
  printf '%s\n' 'printf "%s" "$PMW_PAYLOAD_B64" | base64 -d | tar -xz -C "$DIR"'
  printf '%s\n' 'echo "[pmw] extracted to $DIR; running validator ..."'
  printf '%s\n' 'bash "$DIR/scripts/run.sh"'
} > "$OUT"

chmod +x "$OUT"
rm -f "$PAYLOAD"
OSIZE="$(wc -c < "$OUT" | tr -d ' ')"
echo "[package] payload ${PSIZE} bytes -> $OUT ${OSIZE} bytes"
echo ""
echo "NEXT (on your Mac):"
echo "  1) upload:  curl --data-binary @$OUT https://paste.rs      # prints a URL, e.g. https://paste.rs/aB"
echo "  2) on the Hetzner console, ONE command:"
echo "        curl -fsSL <that-url> | bash"
echo ""
echo "  If paste.rs rejects the size (HTTP 413) or is blocked, use a GitHub gist"
echo "  (gh gist create $OUT) or the git route (see PHASE_2B doc / report notes)."
echo ""
echo "  AFTER the run, return the report (separate, optional step):"
echo "     curl --data-binary @/opt/pmw-validate/results/PHASE_2B_VALIDATION_REPORT.md https://paste.rs"
