"""Tests for scripts/process_audit.py — offline, no gh, no network.

THE POINT OF THESE TESTS IS THE VACUOUS PASS. The check this script replaces
reported green for two days after the thing it measured had been switched off,
so the cases that matter most here are not "does it spot a violation" but "does
it REFUSE to say ok when it cannot see anything". Those are the two
`CheckFailed` tests, and the `main` test that drives the whole path.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "process_audit", Path(__file__).resolve().parents[1] / "scripts" / "process_audit.py")
process_audit = importlib.util.module_from_spec(_SPEC)
sys.modules["process_audit"] = process_audit
_SPEC.loader.exec_module(process_audit)


def _pr(number, created, merged):
    return {"number": number, "createdAt": created, "mergedAt": merged}


def _runner_for(payload):
    def runner(cmd):
        return payload
    return runner


def test_d16_flags_a_window_that_was_six_minutes_short():
    # PR #24 as it actually happened on 2026-09-11.
    payload = json.dumps([_pr(24, "2026-09-11T14:36:59Z", "2026-09-11T16:31:07Z")])
    problems = process_audit.check_d16(runner=_runner_for(payload))
    assert len(problems) == 1
    assert "PR #24" in problems[0]
    assert "6 min short" in problems[0]


def test_d16_accepts_a_window_that_cleared_by_under_a_minute():
    # PR #26 cleared its declared deadline by 59 seconds. Passing is correct:
    # the rule is >= 2 h, not "comfortably more than 2 h".
    payload = json.dumps([_pr(26, "2026-09-11T14:51:04Z", "2026-09-11T16:51:46Z")])
    assert process_audit.check_d16(runner=_runner_for(payload)) == []


def test_d16_refuses_to_pass_when_there_is_nothing_to_audit():
    with pytest.raises(process_audit.CheckFailed, match="no merged PRs"):
        process_audit.check_d16(runner=_runner_for("[]"))


def test_d16_ignores_open_prs_rather_than_counting_them_as_instant_merges():
    payload = json.dumps([
        _pr(36, "2026-09-11T23:47:29Z", None),
        _pr(24, "2026-09-11T14:36:59Z", "2026-09-11T16:31:07Z"),
    ])
    problems = process_audit.check_d16(runner=_runner_for(payload))
    assert [p.split(":")[0] for p in problems] == ["PR #24"]


def _collector_runner(log_output):
    def runner(cmd):
        return "" if cmd[:2] == ["git", "fetch"] else log_output
    return runner


def test_collector_flags_a_stale_push():
    log = "2026-09-11T21:24:09+00:00 paper-state: collect lead=24h target=2026-09-12\n"
    problems = process_audit.check_collector(
        runner=_collector_runner(log),
        now=dt.datetime(2026, 9, 12, 6, 0, tzinfo=dt.timezone.utc))
    assert len(problems) == 1 and "8.6 h ago" in problems[0]


def test_collector_accepts_a_push_within_the_slot():
    log = "2026-09-11T21:24:09+00:00 paper-state: collect lead=24h target=2026-09-12\n"
    assert process_audit.check_collector(
        runner=_collector_runner(log),
        now=dt.datetime(2026, 9, 11, 23, 40, tzinfo=dt.timezone.utc)) == []


def test_collector_refuses_to_pass_on_a_branch_with_only_decide_commits():
    # The failure that motivated this file: a branch that still receives commits,
    # from a stage that is NOT the collector. "Recent activity" is not evidence.
    log = ("2026-09-11T23:00:00+00:00 paper-state: decide lead=24h target=2026-09-12\n"
           "2026-09-11T20:00:00+00:00 paper-state: decide lead=9h target=2026-09-12\n")
    with pytest.raises(process_audit.CheckFailed, match="no collect commits"):
        process_audit.check_collector(runner=_collector_runner(log))


def test_main_reports_failure_when_a_check_cannot_be_measured(monkeypatch, capsys):
    monkeypatch.setattr(process_audit, "check_d16",
                        lambda limit: (_ for _ in ()).throw(
                            process_audit.CheckFailed("gh failed: not logged in")))
    monkeypatch.setattr(process_audit, "check_mainline", lambda since: [])
    monkeypatch.setattr(process_audit, "check_collector", lambda: [])
    assert process_audit.main([]) == 1
    out = capsys.readouterr().out
    assert "[UNMEASURABLE] D16 merge window" in out
    assert "[ok]   collector freshness" in out


def test_main_is_green_only_when_both_checks_are_green(monkeypatch, capsys):
    monkeypatch.setattr(process_audit, "check_d16", lambda limit: [])
    monkeypatch.setattr(process_audit, "check_mainline", lambda since: [])
    monkeypatch.setattr(process_audit, "check_collector", lambda: [])
    assert process_audit.main([]) == 0
    assert capsys.readouterr().out.count("[ok]") == 3


def _mainline_runner(log_output, record=None):
    def runner(cmd):
        if record is not None:
            record.append(cmd)
        return "" if cmd[:2] == ["git", "fetch"] else log_output
    return runner


def test_mainline_flags_a_commit_pushed_straight_to_main():
    log = ("6232e71|85cc100 0442adc|Merge PR #35: skip an identical catalogue snapshot\n"
           "85cc100|97e7111|a quick fix, straight to main\n")
    problems = process_audit.check_mainline(runner=_mainline_runner(log))
    assert len(problems) == 1
    assert "85cc100" in problems[0] and "straight to main" in problems[0]


def test_mainline_flags_a_merge_that_names_no_pr():
    log = "6232e71|85cc100 0442adc|Merge branch 'feat/something' into main\n"
    problems = process_audit.check_mainline(runner=_mainline_runner(log))
    assert len(problems) == 1 and "names no PR" in problems[0]


def test_mainline_accepts_the_real_shape_of_main():
    log = ("6232e71|85cc100 0442adc|Merge PR #35: skip an identical catalogue snapshot\n"
           "85cc100|97e7111 79340d0|Merge PR #34: rows_resident reached the stage\n")
    assert process_audit.check_mainline(runner=_mainline_runner(log)) == []


def test_mainline_refuses_to_pass_when_the_window_holds_no_commits():
    with pytest.raises(process_audit.CheckFailed, match="nothing to audit"):
        process_audit.check_mainline(runner=_mainline_runner(""))


def test_mainline_walks_the_first_parent_and_nothing_else():
    # LATCHES THE FLAG, not the result. Without `--first-parent`, `git log` lists
    # every reachable commit -- including the branch commits that arrived INSIDE
    # merges -- and reports them as direct pushes. That mistake was made once
    # already and produced "24 direct commits", all of them branch commits. It
    # fails in the ALARMING direction, which is the kind that gets believed.
    record = []
    process_audit.check_mainline(
        runner=_mainline_runner("6232e71|a b|Merge PR #35: x\n", record))
    log_cmd = [c for c in record if c[:2] == ["git", "log"]][0]
    assert "--first-parent" in log_cmd
