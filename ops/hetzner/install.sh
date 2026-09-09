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
