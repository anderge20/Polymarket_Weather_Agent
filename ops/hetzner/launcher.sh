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

# ---- ONE WRITER ON THIS HOST ------------------------------------------------
# `run_cycle.sh` commits with `git add -A paper_state` from a checkout SHARED by
# every run on this box. Two overlapping cycles do not collide on shard paths —
# those carry the session id — but the one that commits first sweeps up whatever
# the other is halfway through writing, and a truncated .gz on an append-only
# data branch is not repairable. The runs also both `git reset --hard` the code
# checkout, so a late finisher can have its code swapped underneath it.
#
# It is not hypothetical: on 2026-09-09 a hand-started cycle at 21:03Z overlapped
# the 21:07Z cron slot. That one was harmless only because the second run had not
# reached its dump when the first committed — luck of the calendar, verified
# after the fact (59 shards, `gzip -t` clean), not a property of the design.
#
# So the lock WAITS rather than refuses: a book slot that is skipped is gone for
# good, and a collect takes ~10 min against a 3 h spacing, so the overlap almost
# always clears. It gives up only if the holder is still there after
# PMW_LOCK_WAIT seconds, and then it says so in the log instead of racing.
LOCK=$ROOT/run.lock
mkdir -p "$ROOT/log"
exec 9>"$LOCK"
if ! flock -w "${PMW_LOCK_WAIT:-900}" 9; then
  log "SKIPPED: another cycle still holds $LOCK after ${PMW_LOCK_WAIT:-900}s."
  log "  Not racing it: a concurrent commit can capture a half-written shard."
  # THE SKIP HAS TO BE ATTRIBUTABLE, NOT MERELY LOGGED. Session B's point, and
  # it is the one that would have bitten: a skip that exists only in
  # $ROOT/log/collect.log leaves EXACTLY the trace of a host that never fired —
  # no shard, a hole in "delivered", nothing to tell the two apart. That is the
  # distinction §4quater of R24 rests on, and "GitHub stays the record; nothing
  # lives only on the box" is the decision this would quietly break. Worse: if a
  # cycle truly hangs, every later slot skips and the schedule stops in silence,
  # which is the `git reset --hard` failure again through another door.
  #
  # It is QUEUED rather than pushed. Pushing from here means committing in
  # $STATE while the run that holds the lock is writing there — the very race
  # the lock exists to stop. The next cycle that does get the lock drains it.
  # The append itself is safe against other launchers: one `write()` of ~200
  # bytes under O_APPEND is far below PIPE_BUF, so concurrent appends do not
  # interleave. The race it is NOT safe against is the drainer renaming the queue
  # at that instant — the write would land in the renamed (or already unlinked)
  # inode and the event would vanish. Session B put the size of it correctly:
  # microseconds, one event. But the event that would vanish is precisely the one
  # that EXPLAINS a gap, which is the only reason this queue exists, so it gets
  # the same treatment as everything else today: closed, not documented.
  # `stage_host_events` takes this same lock around its rename.
  QUEUE=$ROOT/pending_host_events.ndjson
  {
    flock -w 30 8 || log "  WARNING: could not lock the event queue; appending anyway"
    printf '{"event":"lock_timeout","recorded_at":"%s","mode":"%s","args":"%s","waited_s":%s,"lock":"%s","holder_age_s":%s,"host":"hetzner"}\n' \
      "$(date -u +%FT%TZ)" "${1:-}" "$*" "${PMW_LOCK_WAIT:-900}" "$LOCK" \
      "$(( $(date -u +%s) - $(stat -c %Y "$LOCK" 2>/dev/null || date -u +%s) ))" \
      >> "$QUEUE"
  } 8>"$QUEUE.lock"
  exit 1
fi
# fd 9 is inherited across the exec below, so the lock covers the whole cycle.


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
