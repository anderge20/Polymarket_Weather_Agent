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

AND THE RULE HAS A SECOND HALF, which session B supplied and which this file
cannot enforce: **`[UNMEASURABLE]` is only correct while it stays RARE.** Two of
his watchdogs cried wolf on 2026-09-11 -- one evaluated the cycle before the merge
it was checking, another the shard before the fix -- and neither broke anything
except his willingness to believe them. A check that shouts often gets discounted,
and a discounted check is worse than no check because it still LOOKS armed. So the
rate of `[UNMEASURABLE]` is itself a number worth watching: when it climbs, the
thing at fault is the instrument, not the system. It is not automated here because
this script keeps no state across runs, and a frequency needs a memory.

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

#: Deliberately far above anything this repository will hold. THE NUMBER OF
#: VIOLATIONS THE AUDIT FINDS WAS BEING CHOSEN BY A DEFAULT VALUE: with the 20
#: this file shipped with it reported 2, with 30 it reports 7, and over the whole
#: history there are 9 — the two it never saw are the worst of them, PRs #4 and
#: #5, merged 10 and 3 SECONDS after opening. On that window we concluded "the
#: pattern started today"; it started on 2026-09-09 and yesterday was its tail.
#:
#: It is this file's own rule — a check may not pass vacuously — applied to the
#: POPULATION instead of the predicate, which is the half neither session had
#: closed. Refusing to pass on an empty list does nothing if the list was
#: truncated before you looked at it.
DEFAULT_LIMIT = 200

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


def merged_prs(limit: int = DEFAULT_LIMIT, runner=_run) -> list[dict]:
    """Every merged PR, or a refusal — never a silently truncated prefix.

    A listing that comes back FULL is indistinguishable from one that was cut
    short, so it is reported as unmeasurable rather than audited. That is the
    same decision `CheckFailed` already encodes for "gh failed": an audit over a
    window that excludes the history is not an audit over the history, and the
    dangerous version is the one that still returns a plausible number.
    """
    raw = runner(["gh", "pr", "list", "--state", "merged", "--limit", str(limit),
                  "--json", "number,createdAt,mergedAt,reviews,comments"])
    rows = json.loads(raw)
    merged = [r for r in rows if r.get("mergedAt")]
    if not merged:
        raise CheckFailed("no merged PRs returned -- cannot audit what is not there")
    if len(rows) >= limit:
        raise CheckFailed(
            f"the listing came back full at limit={limit}: there may be older PRs "
            "this run never saw, and a count over a window that excludes the "
            "history is not a count over the history")
    return merged


#: THE DAY THESE CHECKS STARTED BEING GATES RATHER THAN A CENSUS, and the counts
#: they found when they did. All three are frozen and none may move forward.
#:
#: Before this date the repository merged 39 PRs of which 15 left no trace at all.
#: Those rows cannot be fixed -- the windows are over -- and reprinting all 15 on
#: every run is how a check stops being read: the same failure mode this file's
#: own docstring names about a marker that shouts every time. A finding that can
#: never be actioned is not a finding, it is furniture.
#:
#: So the legacy rows become a MEASUREMENT, stated on every run, and the check
#: fails only on a silent merge it could still have prevented. What stops that
#: from being the permissive form -- a check that can no longer fail -- is the
#: PIN: if the legacy count ever differs from `LEGACY_SILENT`, history was
#: rewritten and that IS a failure, reported as one.
ENFORCED_FROM = dt.date(2026, 9, 13)
LEGACY_SILENT = 15
LEGACY_SHORT = 9


def check_d16(limit: int = DEFAULT_LIMIT, runner=_run, merged=None,
              enforced_from: "dt.date | None" = None,
              legacy_short: "int | None" = None) -> list[str]:
    """Every merged PR must show >= 2 h between opening and merging.

    `createdAt` is a PROXY and it is the permissive one. D16 dates the window from
    "the entry here" -- the DECISIONS.md record -- which lands at or after the PR
    is opened, so the real deadline is at or later than the one computed here.
    This can therefore UNDER-report and never over-report. It is used anyway
    because it needs no bookkeeping and it caught a real violation on its first
    run; the exact clock stays in the declared deadline written at record time.

    THE SAME LEGACY SPLIT AS THE TRACE CHECK, and for the same reason: nine of
    these are from 2026-09-09 and 09-11, the windows are over, and no action
    exists that changes them. Doing this to one check and not the other would
    have achieved nothing -- the audit would still open with nine permanent
    failures and the reader would still learn to skip to the bottom. The pin
    (`LEGACY_SHORT`) is what keeps it a gate: a tenth short merge fails, and so
    does the count drifting.
    """
    merged = merged if merged is not None else merged_prs(limit, runner)

    violations, legacy = [], 0
    for r in sorted(merged, key=lambda r: -r["number"]):
        waited = _utc(r["mergedAt"]) - _utc(r["createdAt"])
        if waited >= D16_WINDOW:
            continue
        if enforced_from is not None and _utc(r["mergedAt"]).date() < enforced_from:
            legacy += 1
            continue
        short = (D16_WINDOW - waited).total_seconds() / 60
        violations.append(
            f"PR #{r['number']}: waited {waited.total_seconds()/3600:.2f} h, "
            f"{short:.0f} min short (opened {r['createdAt']}, merged {r['mergedAt']})")
    if legacy_short is not None and legacy != legacy_short:
        violations.append(
            f"legacy baseline moved: {legacy} short windows before "
            f"{enforced_from}, pinned at {legacy_short} -- either history was "
            f"rewritten or the pin is stale, and both need a human")
    return violations


def check_objection_window_was_used(limit: int = DEFAULT_LIMIT, runner=_run,
                                    merged=None,
                                    enforced_from: "dt.date | None" = None,
                                    legacy_silent: "int | None" = None) -> list[str]:
    """D16 is a window for OBJECTIONS. `check_d16` can only see the clock.

    A PR that waits 2 h 00 and merges with nothing written on it satisfies
    `check_d16` exactly. That is not a hypothetical: measured on 2026-09-12,

        30 fusionados   0 revisiones formales   11 sin NINGUNA huella
        #38  espero 2,19 h   0 comentarios       #34  espero 2,00 h   0
        #37  espero 2,18 h   0                   #29  espero 2,00 h   0
        #35  espero 1,62 h   0                   #27  espero 2,00 h   0
        #25  espero 2,03 h   0

    `check_d16` reports those as compliant, because they are. The rule was
    honoured and the reason for the rule was not, and the audit could not tell
    the two apart -- so "D16: OK" was being read as "somebody looked", which is
    a claim nothing in this repo had ever measured.

    WHAT THIS CHECK CAN AND CANNOT SEE, because the distinction is the point:

      * it sees whether the window left a TRACE -- a review, or a comment written
        before the merge. Nothing at all is the failure it reports;
      * it CANNOT see whether the trace is a review. A one-line "green" and a
        substantive objection are the same event to the API;
      * it CANNOT see who wrote it. Both sessions push under one GitHub account,
        so a note to oneself and a peer's objection are indistinguishable here.

    So a pass means "the window was not silent", never "this was reviewed". Said
    plainly because the failure this check exists to correct was exactly a
    weaker measurement being read as a stronger claim.

    Formal reviews are counted separately and reported even when zero, since
    `reviews: 0` across all 30 is itself the finding: review is happening in the
    comment stream, where no tooling looks for it.
    """
    merged = merged if merged is not None else merged_prs(limit, runner)

    silent, legacy, formales = [], 0, 0
    for r in sorted(merged, key=lambda r: -r["number"]):
        fin = _utc(r["mergedAt"])
        revs = [v for v in (r.get("reviews") or [])
                if v.get("submittedAt") and _utc(v["submittedAt"]) < fin]
        coms = [c for c in (r.get("comments") or [])
                if c.get("createdAt") and _utc(c["createdAt"]) < fin]
        formales += len(revs)
        if revs or coms:
            continue
        if enforced_from is not None and fin.date() < enforced_from:
            legacy += 1
            continue
        esperado = (fin - _utc(r["createdAt"])).total_seconds() / 3600
        silent.append(
            f"PR #{r['number']}: window of {esperado:.2f} h left NO trace -- "
            f"no review and no comment before the merge")

    out = list(silent)
    # The pin. Without it the split above would be a way of never failing again.
    if legacy_silent is not None and legacy != legacy_silent:
        out.append(
            f"legacy baseline moved: {legacy} silent merges before "
            f"{enforced_from}, pinned at {legacy_silent} -- either history was "
            f"rewritten or the pin is stale, and both need a human")
    if formales == 0:
        out.append(
            f"0 formal reviews across {len(merged)} merged PRs: whatever review "
            "happens is in the comment stream, and no check but this one looks "
            "there")
    return out


def measure_process_state(merged: list[dict],
                          enforced_from: dt.date = ENFORCED_FROM) -> list[str]:
    """Numbers stated on EVERY run, whether or not anything is wrong.

    The separation is the point of this function's existence. `check_*` answers
    "what is broken"; this answers "what is the state", and the state here is a
    debt that predates the instrument and can never be paid. Printing it as a
    failure taught the reader to skip fifteen lines; printing it as a number
    keeps it in front of them at one line, which is the only version that
    survives being read every day.
    """
    fila = []
    anteriores = [r for r in merged if _utc(r["mergedAt"]).date() < enforced_from]
    mudos = 0
    revisados = 0
    for r in merged:
        fin = _utc(r["mergedAt"])
        revs = [v for v in (r.get("reviews") or [])
                if v.get("submittedAt") and _utc(v["submittedAt"]) < fin]
        coms = [c for c in (r.get("comments") or [])
                if c.get("createdAt") and _utc(c["createdAt"]) < fin]
        if revs:
            revisados += 1
        if not revs and not coms and fin.date() < enforced_from:
            mudos += 1
    fila.append(
        f"{revisados} of {len(merged)} merged PRs carry a formal review; "
        f"a review here means only that somebody submitted one, never that it "
        f"was adversarial -- the API cannot tell those apart")
    fila.append(
        f"{mudos} of {len(anteriores)} PRs merged before {enforced_from} left no "
        f"trace at all: frozen debt, not actionable, pinned so it cannot drift")
    # AND THE SHORT WINDOWS, for the reason the whole split exists: moving them
    # out of the FAIL list without printing them here would not have made the
    # audit shorter, it would have made it quieter. Nine violations of the
    # repository's own merge rule are not allowed to vanish because they are old.
    cortos = sum(1 for r in anteriores
                 if _utc(r["mergedAt"]) - _utc(r["createdAt"]) < D16_WINDOW)
    fila.append(
        f"{cortos} of {len(anteriores)} PRs merged before {enforced_from} merged "
        f"INSIDE the 2 h window: same frozen debt, same pin, and the older half "
        f"of it predates the rule being checked at all")
    return fila


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


def check_mainline(since: str = "2026-09-11", runner=_run) -> list[str]:
    """Every commit on main's first-parent line must be a merge carrying a PR.

    THE POPULATION IS `main`, NOT THE PR LIST. Session B found this hole in
    `check_d16`: a commit pushed straight to `main` never appears in `gh pr list`,
    so the audit would report "every PR honoured D16" -- true, and empty. That is
    this file's own rule turned on itself. Refusing to pass vacuously is not enough
    if the thing counted is a PROXY for the thing that matters.

    `--first-parent` IS LATCHED HERE BY A TEST, because dropping it is the natural
    mistake and it fails loudly in the alarming direction: a plain `git log` lists
    everything reachable, including the branch commits that arrived INSIDE merges,
    and reports them all as direct pushes. B's first attempt at this measurement
    returned "24 direct commits"; all 24 were branch commits. Walking the first
    parent only visits the mainline.

    Measured when written: 11 merges since 2026-09-11, zero direct commits. The
    hole is real and does not bite today, which is the moment to close it.
    """
    runner(["git", "fetch", "-q", "origin", "main"])
    out = runner(["git", "log", "origin/main", "--first-parent",
                  "--format=%h|%p|%s", f"--since={since}"])
    lines = [l for l in out.strip().splitlines() if "|" in l]
    if not lines:
        raise CheckFailed(f"no commits on main since {since} -- nothing to audit")

    problems = []
    for line in lines:
        sha, parents, subject = line.split("|", 2)
        if len(parents.split()) < 2:
            problems.append(f"{sha}: pushed straight to main, no merge commit "
                            f"({subject[:60]})")
        elif "PR #" not in subject:
            problems.append(f"{sha}: merge names no PR ({subject[:60]})")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                    help="cap on merged PRs fetched; a listing that comes back "
                         "FULL is reported unmeasurable, never audited as if it "
                         "were the whole history")
    ap.add_argument("--since", default="2026-09-11", help="how far back to walk main")
    args = ap.parse_args(argv)

    failed = False

    # ONE fetch, ONE population, both PR checks over it -- so the two can never
    # be reported side by side having looked at different sets, and so the size
    # of what was audited is stated on every run rather than inferred from a
    # default nobody reads.
    try:
        poblacion = merged_prs(args.limit)
        print(f"[pop]  {len(poblacion)} merged PRs audited "
              f"(#{min(r['number'] for r in poblacion)}-"
              f"#{max(r['number'] for r in poblacion)}, limit {args.limit})")
    except CheckFailed as exc:
        print(f"[UNMEASURABLE] merged-PR population: {exc}")
        return 1

    # Stated before the checks, deliberately: the reader sees the state of the
    # review trace BEFORE the pass/fail lines, so "D16: ok" is read against a
    # number rather than instead of one.
    for linea in measure_process_state(poblacion, ENFORCED_FROM):
        print(f"[med]  {linea}")

    # THE POLICY IS PASSED HERE, NOT DEFAULTED INSIDE THE CHECKS. A default that
    # splits history would mean any caller who forgets the argument silently gets
    # the lenient version -- the permissive form, one layer down. The functions
    # compute violations; WHICH ERA IS ENFORCED is a decision, and a decision
    # belongs at the entry point where it can be read.
    politica = dict(enforced_from=ENFORCED_FROM)
    for name, fn in (("D16 merge window",
                      lambda: check_d16(merged=poblacion, legacy_short=LEGACY_SHORT,
                                        **politica)),
                     # Deliberately adjacent to the clock check, and deliberately
                     # after it: the pair is the finding. The first says the rule
                     # was kept, the second says whether it did anything.
                     ("D16 window was used",
                      lambda: check_objection_window_was_used(
                          merged=poblacion, legacy_silent=LEGACY_SILENT, **politica)),
                     ("mainline integrity", lambda: check_mainline(args.since)),
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
