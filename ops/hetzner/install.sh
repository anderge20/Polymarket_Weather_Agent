#!/usr/bin/env bash
# =============================================================================
# ops/hetzner/install.sh — put the paper-mode schedule on this host
# =============================================================================
# Idempotent: safe to re-run after every `git pull`. Installs the venv, the
# state checkout and the cron entries, and nothing else.
#
# The schedule mirrors what Actions was supposed to do, in UTC:
#   collector   every 3 h at :07     — book snapshots, unrecoverable if missed
#   decide      02:40  lead  9 h     — target = today
#   decide      11:40  lead 24 h     — target = tomorrow
#
# The decision cycles run FAIL-CLOSED until /opt/pmw/PAPER_TAU exists. Creating
# that file is what starts trading, and R24 P12 requires the acceptance
# criterion to be frozen and hashed BEFORE it exists. Do not create it casually.
set -euo pipefail
ROOT=/opt/pmw
REPO=$ROOT/repo

# THE SAME TRAP AS A-89, IN THE SCRIPT THAT EXISTS TO AVOID IT.
# The `git reset --hard` below rewrites the checkout THIS FILE lives in. If the
# target ref does not carry ops/, the reset deletes the script bash is still
# reading — half-executed, no error, and the cron left in whatever state the
# first half produced. Verified on 2026-09-09: origin/main did not contain ops/
# until PR #14 landed, so the condition was live, not theoretical.
#
# A-89 diagnosed this and the fix went only to the launcher, because that was
# where it had hurt. Fixing the instance is not fixing the class. So: copy out
# and re-exec BEFORE touching git. Copied, not symlinked, for the same reason.
# BOTH SIDES RESOLVED. `pwd -P` resolves symlinks, so comparing it against a
# `$REPO` that may not be resolved silently never matches — the guard looks
# installed and does nothing, which is the failure mode it exists to prevent.
# Caught by the test, not by reading it: on a host where /opt is a link, the
# unresolved form would have sailed straight through.
SELF=$(cd "$(dirname "$0")" && pwd -P)/$(basename "$0")
REPO_P=$(cd "$REPO" 2>/dev/null && pwd -P || echo "$REPO")
case "$SELF" in
  "$REPO_P"/*)
    mkdir -p "$ROOT/bin"
    install -m 0755 "$SELF" "$ROOT/bin/install.sh"
    echo "install.sh: re-exec from $ROOT/bin/install.sh (outside the checkout)"
    exec "$ROOT/bin/install.sh" "$@"
    ;;
esac

command -v git >/dev/null || { echo "git required"; exit 1; }
[ -d "$REPO/.git" ] || git clone -q git@github.com:anderge20/Polymarket_Weather_Agent.git "$REPO"
git -C "$REPO" fetch -q origin && git -C "$REPO" reset -q --hard origin/main

if [ ! -x "$ROOT/venv/bin/python" ]; then
  python3 -m venv "$ROOT/venv"
  "$ROOT/venv/bin/pip" install -q --upgrade pip
fi
"$ROOT/venv/bin/pip" install -q -r "$REPO/requirements-paper.txt"

# The cron block is delimited so re-running replaces it instead of stacking.
BEGIN='# >>> pmw paper mode >>>'
END='# <<< pmw paper mode <<<'
NEW=$(cat <<CRON
$BEGIN
# UTC. Collector every 3 h; a missed book slot is not recoverable.
7 */3 * * * $ROOT/bin/launcher.sh collect    >> $ROOT/log/collect.log 2>&1
40 2 * * *  $ROOT/bin/launcher.sh decide 9   >> $ROOT/log/cycle.log   2>&1
40 11 * * * $ROOT/bin/launcher.sh decide 24  >> $ROOT/log/cycle.log   2>&1
$END
CRON
)
mkdir -p "$ROOT/log" "$ROOT/bin"
# The launcher lives OUTSIDE the checkout so a `git reset` can never delete the
# script that is running. Copied, not symlinked, for the same reason.
install -m 0755 "$REPO/ops/hetzner/launcher.sh" "$ROOT/bin/launcher.sh"
[ -f "$ROOT/REF" ] || echo main > "$ROOT/REF"
( crontab -l 2>/dev/null | sed "/$BEGIN/,/$END/d"; echo "$NEW" ) | crontab -
echo "cron installed:"; crontab -l | sed -n "/$BEGIN/,/$END/p"
echo
# VERIFIED, not assumed: this host is Etc/UTC, so the cron fields above are UTC
# and match the anchors R8/R24 §5 are written in. If this ever prints anything
# else, the schedule is silently shifted and every `drift_h` in the run is wrong.
TZNAME=$(timedatectl show -p Timezone --value 2>/dev/null || date +%Z)
echo "host timezone: $TZNAME"
[ "$TZNAME" = "Etc/UTC" ] || [ "$TZNAME" = "UTC" ] || {
  echo "REFUSING: the cron entries are written in UTC and this host is $TZNAME."
  echo "Set the host to UTC (timedatectl set-timezone Etc/UTC) and re-run."
  exit 1
}
