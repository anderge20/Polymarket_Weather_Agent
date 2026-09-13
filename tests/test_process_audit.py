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
    monkeypatch.setattr(process_audit, "merged_prs", lambda limit: [{"number": 1, "createdAt": "2026-09-12T10:00:00Z", "mergedAt": "2026-09-12T13:00:00Z", "reviews": [], "comments": []}])
    monkeypatch.setattr(process_audit, "check_d16",
                        lambda **kw: (_ for _ in ()).throw(
                            process_audit.CheckFailed("gh failed: not logged in")))
    monkeypatch.setattr(process_audit, "check_objection_window_was_used",
                        lambda **kw: [])
    monkeypatch.setattr(process_audit, "check_mainline", lambda since: [])
    monkeypatch.setattr(process_audit, "check_collector", lambda: [])
    assert process_audit.main([]) == 1
    out = capsys.readouterr().out
    assert "[UNMEASURABLE] D16 merge window" in out
    assert "[ok]   collector freshness" in out


def test_main_is_green_only_when_both_checks_are_green(monkeypatch, capsys):
    monkeypatch.setattr(process_audit, "merged_prs", lambda limit: [{"number": 1, "createdAt": "2026-09-12T10:00:00Z", "mergedAt": "2026-09-12T13:00:00Z", "reviews": [], "comments": []}])
    monkeypatch.setattr(process_audit, "check_d16", lambda **kw: [])
    monkeypatch.setattr(process_audit, "check_objection_window_was_used",
                        lambda **kw: [])
    monkeypatch.setattr(process_audit, "check_mainline", lambda since: [])
    monkeypatch.setattr(process_audit, "check_collector", lambda: [])
    assert process_audit.main([]) == 0
    assert capsys.readouterr().out.count("[ok]") == 4


def test_main_runs_the_window_check_and_not_only_the_clock(monkeypatch, capsys):
    """Si el check nuevo no estuviera cableado, la prueba de arriba seguiria verde.

    Contarlo por numero de `[ok]` dice cuantos corrieron, no cuales — y un check
    que existe sin estar cableado es exactamente la forma de la comprobacion del
    colector que paso en vacio dos dias."""
    monkeypatch.setattr(process_audit, "merged_prs", lambda limit: [{"number": 1, "createdAt": "2026-09-12T10:00:00Z", "mergedAt": "2026-09-12T13:00:00Z", "reviews": [], "comments": []}])
    monkeypatch.setattr(process_audit, "check_d16", lambda **kw: [])
    monkeypatch.setattr(process_audit, "check_objection_window_was_used",
                        lambda **kw: ["PR #38: window of 2.19 h left NO trace"])
    monkeypatch.setattr(process_audit, "check_mainline", lambda since: [])
    monkeypatch.setattr(process_audit, "check_collector", lambda: [])
    assert process_audit.main([]) == 1
    out = capsys.readouterr().out
    assert "[ok]   D16 merge window" in out
    assert "[FAIL] D16 window was used" in out and "PR #38" in out


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


# ---------------------------------------------------------------------------
# D16 is a window for objections, and the clock check cannot see whether one
# was ever raised in it
# ---------------------------------------------------------------------------

def _pr_traza(number, created, merged, *, reviews=(), comments=()):
    return {"number": number, "createdAt": created, "mergedAt": merged,
            "reviews": [{"submittedAt": t} for t in reviews],
            "comments": [{"createdAt": t} for t in comments]}


def test_a_window_honoured_to_the_minute_and_silent_is_reported():
    """PR #38 as it actually happened: 2,19 h waited, nothing written on it.

    `check_d16` passes this and is right to. The rule was kept. What the pair of
    checks exists to separate is that the reason for the rule was not.
    """
    payload = json.dumps([_pr_traza(38, "2026-09-12T00:01:31Z", "2026-09-12T02:12:57Z")])
    problems = process_audit.check_objection_window_was_used(
        runner=_runner_for(payload))
    assert any("PR #38" in p and "NO trace" in p for p in problems), problems
    assert process_audit.check_d16(runner=_runner_for(payload)) == [], (
        "el reloj deberia estar limpio: si no, esta prueba no demuestra que los "
        "dos checks miden cosas distintas")


def test_a_comment_before_the_merge_counts_as_a_trace():
    """A comment is what review looks like here — 0 formal reviews in 30 PRs."""
    payload = json.dumps([_pr_traza(
        26, "2026-09-11T14:51:04Z", "2026-09-11T16:51:46Z",
        comments=["2026-09-11T15:40:00Z"])])
    assert [p for p in process_audit.check_objection_window_was_used(
        runner=_runner_for(payload)) if "PR #26" in p] == []


def test_a_comment_written_AFTER_the_merge_is_not_a_trace():
    """Otherwise the check would accept a note added once the merge is done.

    That is not an objection window, it is a changelog — and the whole defect
    being corrected here is a weaker measurement read as a stronger claim.
    """
    payload = json.dumps([_pr_traza(
        26, "2026-09-11T14:51:04Z", "2026-09-11T16:51:46Z",
        comments=["2026-09-11T18:00:00Z"])])
    assert any("PR #26" in p for p in process_audit.check_objection_window_was_used(
        runner=_runner_for(payload)))


def test_zero_formal_reviews_is_reported_even_when_every_window_left_a_trace():
    """The comment stream is where review lives, and nothing else looks there.

    Measured 2026-09-12: `reviews` is 0 on all 30 merged PRs. If that goes
    unsaid, a green run reads as "reviews happen", which is the same conflation
    this file was written to stop.
    """
    payload = json.dumps([_pr_traza(
        26, "2026-09-11T14:51:04Z", "2026-09-11T16:51:46Z",
        comments=["2026-09-11T15:40:00Z"])])
    problems = process_audit.check_objection_window_was_used(
        runner=_runner_for(payload))
    assert len(problems) == 1 and "0 formal reviews" in problems[0], problems


def test_the_window_check_refuses_to_pass_when_there_is_nothing_to_audit():
    with pytest.raises(process_audit.CheckFailed, match="no merged PRs"):
        process_audit.check_objection_window_was_used(runner=_runner_for("[]"))


def test_an_open_pr_is_not_counted_as_a_silent_window():
    payload = json.dumps([
        _pr_traza(40, "2026-09-12T03:00:00Z", None),
        _pr_traza(26, "2026-09-11T14:51:04Z", "2026-09-11T16:51:46Z",
                  reviews=["2026-09-11T15:40:00Z"])])
    problems = process_audit.check_objection_window_was_used(
        runner=_runner_for(payload))
    assert not any("PR #40" in p for p in problems), problems


# ---------------------------------------------------------------------------
# The population, not only the predicate: a truncated listing is not a history
# ---------------------------------------------------------------------------

def test_a_listing_that_came_back_FULL_is_unmeasurable_and_never_audited():
    """A full page is indistinguishable from a truncated one.

    THE NUMBER OF VIOLATIONS THE AUDIT FOUND WAS BEING CHOSEN BY A DEFAULT. With
    the 20 this file shipped with it reported 2; with 30, 7; over the whole
    history there are 9 — and the two it never saw are the worst, PRs #4 and #5,
    merged 10 and 3 SECONDS after opening. On the narrow window both sessions
    concluded "the pattern started yesterday". It started on 2026-09-09 and
    yesterday was its tail.

    Session A's finding, on the file A wrote and the PR B widened without closing
    it. It is this file's own rule applied to the POPULATION rather than the
    predicate: refusing to pass on an empty list does nothing if the list was cut
    before you looked.
    """
    lleno = json.dumps([_pr(n, "2026-09-11T10:00:00Z", "2026-09-11T14:00:00Z")
                        for n in range(5)])
    with pytest.raises(process_audit.CheckFailed, match="came back full"):
        process_audit.merged_prs(limit=5, runner=_runner_for(lleno))


def test_a_listing_with_room_to_spare_is_audited():
    casi = json.dumps([_pr(n, "2026-09-11T10:00:00Z", "2026-09-11T14:00:00Z")
                       for n in range(4)])
    assert len(process_audit.merged_prs(limit=5, runner=_runner_for(casi))) == 4


def test_main_states_the_size_of_what_it_audited_on_every_run(monkeypatch, capsys):
    """Pase o falle, la corrida dice sobre cuántos PRs habló.

    Without it the coverage lives in a default value that nobody reads, and a
    green run over a window that excludes the history reads exactly like a green
    run over the history.
    """
    monkeypatch.setattr(process_audit, "merged_prs",
                        lambda limit: [_pr(4, "2026-09-12T10:00:00Z", "2026-09-12T13:00:00Z"),
                                       _pr(38, "2026-09-12T11:00:00Z", "2026-09-12T14:00:00Z")])
    monkeypatch.setattr(process_audit, "check_d16", lambda **kw: [])
    monkeypatch.setattr(process_audit, "check_objection_window_was_used",
                        lambda **kw: [])
    monkeypatch.setattr(process_audit, "check_mainline", lambda since: [])
    monkeypatch.setattr(process_audit, "check_collector", lambda: [])
    assert process_audit.main([]) == 0
    out = capsys.readouterr().out
    assert "2 merged PRs audited" in out and "#4-#38" in out, out


def test_both_pr_checks_run_over_the_SAME_population(monkeypatch):
    """One fetch, one set. Two checks reported side by side must not have looked
    at different histories — which is what separate `--limit` defaults produced."""
    vistas = []
    poblacion = [_pr(4, "2026-09-09T10:28:28Z", "2026-09-09T10:28:38Z")]
    monkeypatch.setattr(process_audit, "merged_prs", lambda limit: poblacion)
    monkeypatch.setattr(process_audit, "check_d16",
                        lambda merged, **kw: vistas.append(("d16", id(merged))) or [])
    monkeypatch.setattr(process_audit, "check_objection_window_was_used",
                        lambda merged, **kw: vistas.append(("win", id(merged))) or [])
    monkeypatch.setattr(process_audit, "check_mainline", lambda since: [])
    monkeypatch.setattr(process_audit, "check_collector", lambda: [])
    process_audit.main([])
    assert len(vistas) == 2 and vistas[0][1] == vistas[1][1], (
        "los dos chequeos recibieron objetos distintos: pueden divergir")


def test_the_seven_violations_of_2026_09_09_are_found_when_the_window_reaches_them():
    """PRs #4 and #5 merged 10 and 3 seconds after opening, and were invisible.

    Pinned as a regression on the DATA, not on the mechanism: these two are the
    ones a narrowed window loses first, because they are the oldest.
    """
    payload = json.dumps([
        _pr(35, "2026-09-11T21:55:50Z", "2026-09-11T23:33:19Z"),
        _pr(5, "2026-09-09T10:31:08Z", "2026-09-09T10:31:11Z"),
        _pr(4, "2026-09-09T10:28:28Z", "2026-09-09T10:28:38Z")])
    problems = process_audit.check_d16(runner=_runner_for(payload))
    assert len(problems) == 3
    assert any("PR #4" in p and "120 min short" in p for p in problems), problems
    assert any("PR #5" in p and "120 min short" in p for p in problems), problems


# ------------------------------------------------------- deuda heredada y su fijación
def test_without_a_policy_every_era_is_enforced():
    """EL DEFECTO POR DEFECTO ES EL ESTRICTO, y eso es deliberado.

    Si `enforced_from` valiera `ENFORCED_FROM` por defecto, cualquier llamada que
    olvidara el argumento obtendría en silencio la versión indulgente: la forma
    permisiva, una capa más abajo. La función cuenta violaciones; QUÉ ÉPOCA SE
    EXIGE es una decisión, y las decisiones van en el punto de entrada."""
    viejo = [_pr(4, "2026-09-09T10:28:28Z", "2026-09-09T10:28:38Z")]
    assert len(process_audit.check_d16(merged=viejo)) == 1


def test_a_short_window_before_the_cutoff_is_legacy_and_not_a_failure():
    viejo = [_pr(4, "2026-09-09T10:28:28Z", "2026-09-09T10:28:38Z")]
    out = process_audit.check_d16(merged=viejo, legacy=(dt.date(2026, 9, 13), 1))
    assert out == [], out


def test_a_short_window_ON_the_cutoff_day_still_fails():
    """La frontera es `<`, no `<=`: el día que se empieza a exigir, se exige."""
    hoy = [_pr(99, "2026-09-13T10:00:00Z", "2026-09-13T10:30:00Z")]
    out = process_audit.check_d16(merged=hoy, legacy=(dt.date(2026, 9, 13), 0))
    assert len(out) == 1 and "PR #99" in out[0], out


def test_the_legacy_pin_fails_when_the_count_drifts():
    """LO QUE IMPIDE QUE ESTA DIVISIÓN SEA UN 'YA NO PUEDE FALLAR'.

    Sacar la deuda heredada de la lista de fallos sólo es honesto si el recuento
    queda clavado: si cambia, o se reescribió la historia o el pin está obsoleto,
    y las dos cosas necesitan a alguien."""
    viejo = [_pr(4, "2026-09-09T10:28:28Z", "2026-09-09T10:28:38Z")]
    out = process_audit.check_d16(merged=viejo, legacy=(dt.date(2026, 9, 13), 7))
    assert len(out) == 1 and "legacy baseline moved" in out[0] and "pinned at 7" in out[0]


def test_a_silent_window_before_the_cutoff_is_legacy_and_the_pin_still_bites():
    mudo = [_pr_traza(4, "2026-09-09T08:00:00Z", "2026-09-09T12:00:00Z")]
    assert process_audit.check_objection_window_was_used(
        merged=mudo, legacy=(dt.date(2026, 9, 13), 1)) == [
            "0 formal reviews across 1 merged PRs: whatever review happens is in "
            "the comment stream, and no check but this one looks there"]
    drift = process_audit.check_objection_window_was_used(
        merged=mudo, legacy=(dt.date(2026, 9, 13), 0))
    assert any("legacy baseline moved" in x for x in drift), drift


def test_the_measurements_state_the_frozen_debt_even_when_nothing_fails():
    """Sacarlas de los fallos sin imprimirlas no habría acortado la auditoría:
    la habría callado. Nueve incumplimientos de la regla de fusión del propio
    repositorio no desaparecen por ser viejos."""
    pobl = [_pr_traza(4, "2026-09-09T10:28:28Z", "2026-09-09T10:28:38Z"),
            _pr_traza(40, "2026-09-12T08:00:00Z", "2026-09-12T12:00:00Z",
                      reviews=["2026-09-12T11:00:00Z"])]
    lineas = process_audit.measure_process_state(pobl, dt.date(2026, 9, 13))
    assert "1 of 2 merged PRs carry a formal review" in lineas[0]
    assert "1 of 2 PRs merged before 2026-09-13 left no trace" in lineas[1]
    assert "1 of 2 PRs merged before 2026-09-13 merged INSIDE" in lineas[2]


def test_the_cutoff_cannot_be_taken_without_the_pin():
    """EL HALLAZGO DE B SOBRE LA PRIMERA VERSIÓN DE ESTE FICHERO.

    Con dos parámetros, `enforced_from` sin `legacy_short` daba la exclusión sin
    el pin: nueve filas fuera de la lista de fallos y nada comprobando el
    recuento. El test de cableado nombraba ese modo de fallo y lo guardaba
    probando al llamador de HOY — un llamador futuro se lleva la mitad
    indulgente en silencio.

    Dos parámetros hacían el estado malo REPRESENTABLE. Un par no, y lo que
    queda representable —media tupla— se niega en voz alta."""
    viejo = [_pr(4, "2026-09-09T10:28:28Z", "2026-09-09T10:28:38Z")]
    with pytest.raises(ValueError, match="without the pin"):
        process_audit.check_d16(merged=viejo, legacy=(dt.date(2026, 9, 13), None))
    with pytest.raises(ValueError, match="without the pin"):
        process_audit.check_objection_window_was_used(
            merged=viejo, legacy=(dt.date(2026, 9, 13), None))


def test_main_hands_the_checks_the_frozen_debt_as_one_object(monkeypatch, capsys):
    """CABLEADO, no existencia: el defecto vive en la llamada y ninguna prueba de
    unidad lo vería."""
    visto = {}
    monkeypatch.setattr(process_audit, "merged_prs",
                        lambda limit: [_pr_traza(4, "2026-09-09T10:00:00Z",
                                                 "2026-09-09T10:10:00Z")])
    monkeypatch.setattr(process_audit, "check_d16",
                        lambda **kw: visto.update(d16=kw) or [])
    monkeypatch.setattr(process_audit, "check_objection_window_was_used",
                        lambda **kw: visto.update(win=kw) or [])
    monkeypatch.setattr(process_audit, "check_mainline", lambda since: [])
    monkeypatch.setattr(process_audit, "check_collector", lambda: [])
    process_audit.main([])
    assert visto["d16"]["legacy"] == process_audit.LEGACY_SHORT_WINDOWS
    assert visto["win"]["legacy"] == process_audit.LEGACY_TRACE
