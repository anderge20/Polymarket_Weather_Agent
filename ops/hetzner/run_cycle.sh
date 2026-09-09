#!/usr/bin/env bash
# =============================================================================
# ops/hetzner/run_cycle.sh — one paper-mode cycle on the Hetzner host
# =============================================================================
# WHY THIS EXISTS. GitHub Actions cron did not deliver: on 2026-09-09 it ran 2
# of 3 scheduled collector slots, 86 and 215 minutes late, and dropped one
# entirely (A-70). A lost price slot is recoverable inside Open-Meteo's window;
# A LOST BOOK SLOT IS NOT — and the book is the substrate that R21 had to assume
# away and R22 could not measure at all. So execution moves to a host that
# keeps its own clock.
#
# WHAT DOES NOT MOVE. GitHub stays the record: this script PULLS the code from
# `main` and PUSHES the shards to `paper-state`. Nothing lives only on the box.
# If the box is lost, `git clone` restores everything except the hours of book
# history that were never collected.
#
# ONE WRITER. The Actions schedules are disabled in the same change that
# installs this. Two hosts appending to one data branch would not corrupt a
# shard — shard paths are unique per run — but they would race on the push and
# make "scheduled versus delivered" unreadable, which is the measurement §4quater
# of R24 depends on.
#
# Usage:  run_cycle.sh collect            books only, every 3 h
#         run_cycle.sh decide 24          decision cycle, lead 24 h (target tomorrow)
#         run_cycle.sh decide 9           decision cycle, lead  9 h (target today)
set -euo pipefail

ROOT=/opt/pmw
REPO=$ROOT/repo
STATE=$ROOT/state
VENV=$ROOT/venv
BRANCH=paper-state
DSV=ds_paper_v1
MODE=${1:-collect}
LEAD=${2:-24}

log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*"; }

# ---- 1. the code, from GitHub, always -------------------------------------
git -C "$REPO" fetch -q origin
git -C "$REPO" reset -q --hard origin/main
log "code at $(git -C "$REPO" rev-parse --short HEAD)"

# ---- 2. the state branch ---------------------------------------------------
if [ ! -d "$STATE/.git" ]; then
  git clone -q --branch "$BRANCH" git@github.com:anderge20/Polymarket_Weather_Agent.git "$STATE"
fi
git -C "$STATE" fetch -q origin "$BRANCH"
git -C "$STATE" reset -q --hard "origin/$BRANCH"

# ---- 3. the target date, from the lead (R8) --------------------------------
# lead 24 decides TOMORROW's target; lead 9 decides TODAY's. Derived from the
# clock and never from the catalogue: 2D §C forbids deriving `target_date` from
# any market field, and the caller is this script.
if [ "$LEAD" = "24" ]; then TD=$(date -u -d '+1 day' +%F); else TD=$(date -u +%F); fi

ARGS=(--target-date "$TD" --dataset-version "$DSV"
      --store-root "$STATE/paper_state" --lead-hours "$LEAD"
      --summary-json "$ROOT/last_summary.json")

if [ "$MODE" = "collect" ]; then
  ARGS+=(--collect-only)
else
  # FAIL-CLOSED ON tau, exactly as the workflow did. No PAPER_TAU file, no
  # trades — a threshold picked by a default is a parameter nobody
  # preregistered, and R24 §6bis/P12 require the acceptance criterion to be
  # frozen BEFORE the variable exists.
  if [ -r "$ROOT/PAPER_TAU" ]; then
    TAU=$(tr -d '[:space:]' < "$ROOT/PAPER_TAU")
    TAU_EXEC=$([ -r "$ROOT/PAPER_TAU_EXEC" ] && tr -d '[:space:]' < "$ROOT/PAPER_TAU_EXEC" || echo "$TAU")
    ARGS+=(--tau-signal "$TAU" --tau-exec "$TAU_EXEC")
    log "deciding with tau_signal=$TAU tau_exec=$TAU_EXEC"
  else
    ARGS+=(--collect-only)
    log "no $ROOT/PAPER_TAU — collect-only (fail-closed, R24 P12)"
  fi
fi

log "running: mode=$MODE lead=${LEAD}h target=$TD"
cd "$REPO"
PYTHONPATH=src "$VENV/bin/python" scripts/paper_cycle.py "${ARGS[@]}" || {
  log "cycle exited non-zero — shards already written are still committed below"
}

# ---- 4. push the shards ----------------------------------------------------
cd "$STATE"
if [ -z "$(git status --porcelain)" ]; then
  log "nothing new to commit"
  exit 0
fi
git -c user.name='pmw-hetzner' -c user.email='pmw-hetzner@users.noreply.github.com' \
    add -A paper_state
git -c user.name='pmw-hetzner' -c user.email='pmw-hetzner@users.noreply.github.com' \
    commit -q -m "paper-state: $MODE lead=${LEAD}h target=$TD (hetzner $(date -u +%FT%TZ))"
# Shards never share a path across runs, so a concurrent push can only be a
# fast-forward away: rebase and retry rather than force.
for attempt in 1 2 3; do
  if git push -q origin "$BRANCH"; then log "pushed"; exit 0; fi
  log "push rejected (attempt $attempt) — rebasing"
  git fetch -q origin "$BRANCH" && git rebase -q "origin/$BRANCH" || true
done
log "PUSH FAILED after 3 attempts — shards are on disk at $STATE, not lost"
exit 1
