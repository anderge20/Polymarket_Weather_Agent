#!/usr/bin/env bash
# =============================================================================
# launcher.sh — the ONLY thing cron calls. Lives OUTSIDE the git checkout.
# =============================================================================
# WHY IT IS SEPARATE, and this is not tidiness.
#
# `run_cycle.sh` starts by doing `git reset --hard` on the checkout it lives in.
# If the target ref does not contain `ops/hetzner/`, that reset DELETES THE
# RUNNING SCRIPT while bash is still reading it — a half-executed file, no error
# anyone would recognise, and a schedule that silently stops. It nearly happened:
# `ops/` was only on a branch while the cron already existed, so pointing it at
# `main` would have wiped it on the first firing.
#
# So cron calls this, which lives at /opt/pmw/bin/launcher.sh — outside the
# checkout, updated only by install.sh — and it:
#   1. updates the checkout to the ref named in /opt/pmw/REF (default `main`),
#   2. CHECKS the runner still exists after the update, and stops loudly if not,
#   3. exec's it.
#
# Switching branch is then editing one file, with no code change and no way to
# leave the schedule pointing at a ref that cannot run it.
set -euo pipefail

ROOT=/opt/pmw
REPO=$ROOT/repo
REF=$(cat "$ROOT/REF" 2>/dev/null || echo main)
RUNNER=$REPO/ops/hetzner/run_cycle.sh

log() { printf '%s launcher: %s\n' "$(date -u +%FT%TZ)" "$*"; }

git -C "$REPO" fetch -q origin
if ! git -C "$REPO" rev-parse -q --verify "origin/$REF" >/dev/null; then
  log "FATAL: ref 'origin/$REF' does not exist. Not touching the checkout."
  log "  (a merged branch that was deleted leaves /opt/pmw/REF stale — set it to main)"
  exit 1
fi
git -C "$REPO" reset -q --hard "origin/$REF"

if [ ! -x "$RUNNER" ]; then
  log "FATAL: '$RUNNER' is missing at ref '$REF'. The schedule is stopped, not"
  log "  half-running. Point /opt/pmw/REF at a ref that contains ops/hetzner/."
  exit 1
fi
log "ref=$REF at $(git -C "$REPO" rev-parse --short HEAD) -> $* "
exec "$RUNNER" "$@"
