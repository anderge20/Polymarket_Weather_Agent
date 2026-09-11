#!/usr/bin/env python3
"""The two process checks that nothing else performs, made executable.

WHY THIS EXISTS. Both checks below were being "done" by a human reading a screen,
and both had already failed silently by the time this was written:

  * D16 requires a >= 2 h objection window before any merge to `main`. Two of the
    ten merges on 2026-09-11 broke it. ONE was caught, and only because its wait
    loop failed VISIBLY (an HHMMSS string compare that goes false at midnight).
    The other, PR #24, merged six minutes early, broke nothing, and sat unnoticed
    for nine hours. A rule nobody can check after the fact is only enforced in the
    cases that also happen to break something.

  * The collector check in the daily routine ran `gh run list
    --workflow=paper_collect.yml` and reported green -- for two days AFTER that
    workflow's schedules were disabled and collection moved to the Hetzner box. A
    workflow that never runs never fails. The check could no longer do anything
    but pass.

THE SECOND FAILURE IS THE REASON FOR THE DESIGN RULE HERE: **neither check may
pass vacuously.** An empty PR list, a `paper-state` branch with no collect commits,
a `gh` that errors -- each of those is a FAILING result, never a quiet OK. The
whole point is to catch the case where the thing being measured stopped existing.

Not wired into CI. It is run by whoever closes a batch of merges, and by the daily
routine in place of the Actions check it replaces.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys

D16_WINDOW = dt.timedelta(hours=2)

# The collector runs at 7 */3 (cron, on the box) and pushes 15-17 minutes later.
# 3.5 h leaves a slot's worth of slack and still catches a missed slot, which is
# the only failure that is PERMANENT -- there is no endpoint that returns a past
# order book, so a slot not collected is a slot that never existed.
COLLECTOR_MAX_AGE = dt.timedelta(hours=3.5)


class CheckFailed(Exception):
    """Raised for a failing check AND for a check that cannot be performed.

    Deliberately one exception for both. "I could not measure it" must not be
    reportable as "it is fine" -- that conflation is exactly what let the Actions
    collector check pass for two days after the schedule was removed.
    """


def _run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise CheckFailed(f"{cmd[0]} failed: {proc.stderr.strip()[:200]}")
    return proc.stdout


def _utc(stamp: str) -> dt.datetime:
    return dt.datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(dt.timezone.utc)


def check_d16(limit: int = 20, runner=_run) -> list[str]:
    """Every merged PR must show >= 2 h between opening and merging.

    `createdAt` is a PROXY and it is the permissive one. D16 dates the window from
    "the entry here" -- the DECISIONS.md record -- which lands at or after the PR
    is opened, so the real deadline is at or later than the one computed here.
    This can therefore UNDER-report and never over-report. It is used anyway
    because it needs no bookkeeping and it caught a real violation on its first
    run; the exact clock stays in the declared deadline written at record time.
    """
    raw = runner(["gh", "pr", "list", "--state", "merged", "--limit", str(limit),
                  "--json", "number,createdAt,mergedAt"])
    rows = json.loads(raw)
    merged = [r for r in rows if r.get("mergedAt")]
    if not merged:
        raise CheckFailed("no merged PRs returned -- cannot audit what is not there")

    violations = []
    for r in sorted(merged, key=lambda r: -r["number"]):
        waited = _utc(r["mergedAt"]) - _utc(r["createdAt"])
        if waited < D16_WINDOW:
            short = (D16_WINDOW - waited).total_seconds() / 60
            violations.append(
                f"PR #{r['number']}: waited {waited.total_seconds()/3600:.2f} h, "
                f"{short:.0f} min short (opened {r['createdAt']}, merged {r['mergedAt']})")
    return violations


def check_collector(max_age: dt.timedelta = COLLECTOR_MAX_AGE, runner=_run,
                    now: dt.datetime | None = None) -> list[str]:
    """The collector is measured where it actually writes, not where it used to.

    Collection moved off GitHub Actions on 2026-09-09 (Actions delivered 2 of 3
    slots on its first day, one dropped entirely, and a dropped BOOK slot is
    unrecoverable). The evidence of a live collector is therefore a recent commit
    on `paper-state`, not a green workflow run.
    """
    runner(["git", "fetch", "-q", "origin", "paper-state"])
    out = runner(["git", "log", "origin/paper-state", "--format=%cI %s", "-40"])
    stamps = [line.split(" ", 1) for line in out.strip().splitlines() if " " in line]
    collects = [s for s in stamps if "collect" in s[1]]
    if not collects:
        raise CheckFailed("no collect commits on paper-state -- the collector left no trace")

    newest = _utc(collects[0][0])
    now = now or dt.datetime.now(dt.timezone.utc)
    age = now - newest
    if age > max_age:
        return [f"last collect was {age.total_seconds()/3600:.1f} h ago "
                f"({collects[0][0]}), limit {max_age.total_seconds()/3600:.1f} h"]
    return []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=20, help="merged PRs to audit")
    args = ap.parse_args(argv)

    failed = False
    for name, fn in (("D16 merge window", lambda: check_d16(args.limit)),
                     ("collector freshness", check_collector)):
        try:
            problems = fn()
        except CheckFailed as exc:
            print(f"[UNMEASURABLE] {name}: {exc}")
            failed = True
            continue
        if problems:
            failed = True
            print(f"[FAIL] {name}: {len(problems)} problem(s)")
            for p in problems:
                print(f"         {p}")
        else:
            print(f"[ok]   {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
