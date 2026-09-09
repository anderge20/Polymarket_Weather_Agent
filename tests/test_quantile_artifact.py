"""Tests for the versioned quantile artifact (R30).

The artifact exists to stop a specific failure: a distribution that is silently
wrong — stale, leaked, or fitted under other rules — producing a plausible
number. So almost every test here builds a BAD artifact on purpose and asserts
that the loader refuses it with the right label from the closed enum.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from weather_agent import error_model as em
from weather_agent import quantile_artifact as qa

T = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
FIT = T - timedelta(hours=6)
PREREG = "b2b168d4cddb65c469cbd00bd20cce30c54e5afd194526527714e23cf0d5b34c"
VALUES = {10: -1.5, 25: -0.5, 50: 0.4, 75: 1.3, 90: 2.2}


def _payload(*, fit_instant=FIT, max_age_hours=336.0, model="icon_seamless",
             prereg=PREREG, strata=None, windows=None):
    strata = strata if strata is not None else {
        24: em.Quantiles(em.SCOPE_POOLED, 147, dict(VALUES))}
    windows = windows if windows is not None else {
        24: (FIT - timedelta(days=40), FIT - timedelta(hours=2))}
    return qa.build_payload(
        prereg_sha256=prereg, model=model, dataset_version="backfill_2b_v1",
        fit_instant=fit_instant, max_age_hours=max_age_hours,
        strata=strata, windows=windows, code_sha256="deadbeef")


def _write(tmp_path, payload, name="m2_quantiles.json"):
    p = tmp_path / name
    qa.dump(payload, p)
    return str(p)


def _load(tmp_path, **kw):
    return qa.load(_write(tmp_path, _payload(**kw)))


# --------------------------------------------------------------------------- shape
def test_a_fitted_artifact_round_trips_through_the_file(tmp_path):
    art = _load(tmp_path)
    assert art.schema == qa.SCHEMA
    assert art.model == "icon_seamless"
    assert art.dataset_version == "backfill_2b_v1"
    assert art.fit_instant == FIT
    assert art.max_age_hours == 336.0
    q = art.quantiles(24, T, model="icon_seamless", prereg_sha256=PREREG)
    assert q.scope == em.SCOPE_POOLED and q.n == 147
    assert q.values == VALUES


def test_the_id_is_over_content_not_over_formatting(tmp_path):
    """Two files with the same numbers and different key order are the same
    artifact. Otherwise the id would identify a serialisation, not a fit."""
    a = _payload()
    b = dict(reversed(list(a.items())))
    assert qa.artifact_id_of(a) == qa.artifact_id_of(b) == a["artifact_id"]


def test_the_id_identifies_a_FIT_not_a_set_of_numbers(tmp_path):
    """Identical quantiles fitted at a different instant are a DIFFERENT artifact.

    The docstring of `canonical_bytes` used to promise the opposite — "two fits
    that produced the same numbers get the same id on any machine" — and A-94
    measured it false: a refit against an unchanged substrate returned n, window
    and quantiles identical digit for digit, and a different id, because
    `fit_instant` is hashed with the rest.

    This is NOT a test against an imagined future — session B checked the five
    consumers and two need this property today:

      * `fit_quantile_artifact.py` writes `{"artifact_id": …, "previous": …}`.
        Under a content hash, a refit against an unchanged substrate writes
        `previous == artifact_id` and DISAPPEARS FROM ITS OWN LINEAGE RECORD.
      * `replay_cycle.py` pins the artifact by id, because "the artifact that
        cycle used" is an identity of fit, not of numbers.

    The plausible wrong fix the old docstring invited — drop `fit_instant` from
    the hash so the id becomes a content hash — breaks both. This test fails on
    exactly that edit.
    """
    same_numbers = _payload(fit_instant=FIT + timedelta(hours=48))
    baseline = _payload()
    assert same_numbers["strata"] == baseline["strata"]
    assert same_numbers["artifact_id"] != baseline["artifact_id"], (
        "two refits of the same data are two artifacts; the id is not a content "
        "hash of the quantiles")

    # and pinning the instant is what makes it reproducible across machines
    assert _payload(fit_instant=FIT)["artifact_id"] == baseline["artifact_id"]


def test_changing_any_field_changes_the_id(tmp_path):
    base = _payload()["artifact_id"]
    assert _payload(fit_instant=FIT + timedelta(seconds=1))["artifact_id"] != base
    assert _payload(max_age_hours=337.0)["artifact_id"] != base
    assert _payload(model="ecmwf_ifs025")["artifact_id"] != base
    assert _payload(strata={24: em.Quantiles(em.SCOPE_POOLED, 148, dict(VALUES))}
                    )["artifact_id"] != base


def test_a_file_edited_after_the_fit_is_refused(tmp_path):
    """The point of the id: someone nudges a quantile in the JSON and the cycle
    keeps running with a number nobody fitted."""
    path = _write(tmp_path, _payload())
    body = json.loads(open(path).read())
    body["strata"]["24"]["values"]["50"] = 3.0        # a warmer median, by hand
    open(path, "w").write(json.dumps(body))
    with pytest.raises(qa.ArtifactUnusable) as e:
        qa.load(path)
    assert e.value.reason == qa.R_ARTIFACT_ID_MISMATCH


# --------------------------------------------------------------------------- staleness (B's condition)
def test_a_stale_artifact_is_refused_not_used(tmp_path):
    art = _load(tmp_path, fit_instant=T - timedelta(hours=400), max_age_hours=336.0)
    with pytest.raises(qa.ArtifactUnusable) as e:
        art.quantiles(24, T, model="icon_seamless", prereg_sha256=PREREG)
    assert e.value.reason == qa.R_STALE
    assert "400" in e.value.detail


def test_the_caller_may_tighten_the_declared_age_but_never_extend_it(tmp_path):
    art = _load(tmp_path, fit_instant=T - timedelta(hours=100), max_age_hours=336.0)
    # tighter: refuses
    with pytest.raises(qa.ArtifactUnusable) as e:
        art.quantiles(24, T, model="icon_seamless", prereg_sha256=PREREG,
                      max_age_hours=48)
    assert e.value.reason == qa.R_STALE
    # laxer: IGNORED, the artifact's own limit still governs
    stale = _load(tmp_path, fit_instant=T - timedelta(hours=400), max_age_hours=336.0)
    with pytest.raises(qa.ArtifactUnusable) as e:
        stale.quantiles(24, T, model="icon_seamless", prereg_sha256=PREREG,
                        max_age_hours=100_000)
    assert e.value.reason == qa.R_STALE


def test_an_artifact_exactly_at_its_limit_is_still_usable(tmp_path):
    art = _load(tmp_path, fit_instant=T - timedelta(hours=336), max_age_hours=336.0)
    assert art.quantiles(24, T, model="icon_seamless", prereg_sha256=PREREG).n == 147


# --------------------------------------------------------------------------- leakage
def test_an_artifact_fitted_after_the_decision_is_leakage_and_is_refused(tmp_path):
    """Session B's argument for deferring the refit — an artifact fitted at
    t0 < t uses a SUBSET of what it was entitled to — is exactly what makes the
    mirror case fatal. Forward in time it never happens; a replay meets it the
    first time a cycle is reproduced against a newer artifact."""
    art = _load(tmp_path, fit_instant=T + timedelta(seconds=1))
    with pytest.raises(qa.ArtifactUnusable) as e:
        art.quantiles(24, T, model="icon_seamless", prereg_sha256=PREREG)
    assert e.value.reason == qa.R_FIT_AFTER_DECISION


def test_staleness_is_reported_before_a_missing_stratum(tmp_path):
    """A stale artifact that also lacks the lead is stale. Reporting the missing
    stratum would send a reader looking for the wrong problem."""
    art = _load(tmp_path, fit_instant=T - timedelta(hours=400))
    with pytest.raises(qa.ArtifactUnusable) as e:
        art.quantiles(9, T, model="icon_seamless", prereg_sha256=PREREG)
    assert e.value.reason == qa.R_STALE


# --------------------------------------------------------------------------- the other refusals
def test_a_lead_the_fit_never_covered_is_refused(tmp_path):
    art = _load(tmp_path)
    with pytest.raises(qa.ArtifactUnusable) as e:
        art.quantiles(9, T, model="icon_seamless", prereg_sha256=PREREG)
    assert e.value.reason == qa.R_STRATUM_ABSENT


def test_a_stratum_m2_itself_declined_to_publish_is_never_used(tmp_path):
    """INSUFFICIENT and REJECTED are stored so the artifact is a complete record
    of the fit. Storing them is not publishing them."""
    for scope in (em.SCOPE_INSUFFICIENT, em.SCOPE_REJECTED):
        art = _load(tmp_path, strata={9: em.Quantiles(scope, 12, {})},
                    windows={9: (None, None)})
        with pytest.raises(qa.ArtifactUnusable) as e:
            art.quantiles(9, T, model="icon_seamless", prereg_sha256=PREREG)
        assert e.value.reason == qa.R_STRATUM_NOT_POOLED


def test_an_artifact_fitted_under_another_preregistration_is_refused(tmp_path):
    art = _load(tmp_path, prereg="0" * 64)
    with pytest.raises(qa.ArtifactUnusable) as e:
        art.quantiles(24, T, model="icon_seamless", prereg_sha256=PREREG)
    assert e.value.reason == qa.R_PREREG_MISMATCH


def test_an_artifact_fitted_on_another_weather_model_is_refused(tmp_path):
    art = _load(tmp_path, model="ecmwf_ifs025")
    with pytest.raises(qa.ArtifactUnusable) as e:
        art.quantiles(24, T, model="icon_seamless", prereg_sha256=PREREG)
    assert e.value.reason == qa.R_MODEL_MISMATCH


def test_a_newer_schema_is_not_read_on_a_guess(tmp_path):
    body = _payload()
    body["schema"] = qa.SCHEMA + 1
    body["artifact_id"] = qa.artifact_id_of(body)
    with pytest.raises(qa.ArtifactUnusable) as e:
        qa.load(_write(tmp_path, body))
    assert e.value.reason == qa.R_SCHEMA_UNSUPPORTED


def test_a_missing_file_is_a_reason_not_a_traceback(tmp_path):
    with pytest.raises(qa.ArtifactUnusable) as e:
        qa.load(tmp_path / "nope.json")
    assert e.value.reason == qa.R_MISSING


def test_non_monotone_quantiles_are_malformed(tmp_path):
    body = _payload(strata={24: em.Quantiles(em.SCOPE_POOLED, 147,
                                             {10: 2.0, 25: 1.0, 50: 0.0,
                                              75: -1.0, 90: -2.0})})
    with pytest.raises(qa.ArtifactUnusable) as e:
        qa.load(_write(tmp_path, body))
    assert e.value.reason == qa.R_MALFORMED and "monotone" in e.value.detail


def test_a_published_stratum_missing_a_level_is_malformed(tmp_path):
    """Without this the gap surfaces as a KeyError inside forecast_quantiles_c,
    which is not a refusal reason and would abort the cycle instead of it."""
    partial = {k: v for k, v in VALUES.items() if k != 75}
    body = _payload(strata={24: em.Quantiles(em.SCOPE_POOLED, 147, partial)})
    with pytest.raises(qa.ArtifactUnusable) as e:
        qa.load(_write(tmp_path, body))
    assert e.value.reason == qa.R_MALFORMED


def test_a_fit_instant_without_a_timezone_is_malformed(tmp_path):
    body = _payload()
    body["fit_instant"] = "2026-09-10T06:00:00"
    body["artifact_id"] = qa.artifact_id_of(body)
    with pytest.raises(qa.ArtifactUnusable) as e:
        qa.load(_write(tmp_path, body))
    assert e.value.reason == qa.R_MALFORMED


# --------------------------------------------------------------------------- discipline
def test_the_refusal_is_not_a_value_error(tmp_path):
    """`except ValueError` around the cycle would swallow a staleness refusal
    into the generic error path and report the wrong reason."""
    assert not issubclass(qa.ArtifactUnusable, ValueError)


def test_a_reason_outside_the_closed_enum_cannot_be_raised():
    with pytest.raises(AssertionError):
        raise qa.ArtifactUnusable("something_went_wrong")


def test_provenance_carries_what_the_cycle_must_record(tmp_path):
    """Session B's second condition. The id names the fit exactly; the rest is
    what a reader needs without opening the artifact."""
    art = _load(tmp_path)
    prov = art.provenance(24)
    assert prov["quantile_artifact_id"] == art.artifact_id
    assert prov["quantile_artifact_fit_instant"] == FIT.isoformat()
    assert prov["quantile_artifact_prereg_sha256"] == PREREG
    assert prov["quantile_artifact_dataset_version"] == "backfill_2b_v1"
    assert prov["quantile_artifact_max_age_hours"] == 336.0
    assert prov["quantile_stratum_lead_h"] == 24
    assert prov["quantile_stratum_n"] == 147
    assert prov["quantile_stratum_scope"] == em.SCOPE_POOLED
    assert prov["quantile_window_start"] and prov["quantile_window_end"]
    assert prov["quantile_artifact_age_h"] is None      # no instant given


def test_provenance_records_the_effective_age_at_the_moment_of_use(tmp_path):
    """B's addition to the contract. When a decision has to be audited, the age
    at the moment of use IS the datum; leaving a reader to subtract two instants,
    one of them not in the same row, is how an audit gets the arithmetic wrong."""
    art = _load(tmp_path, fit_instant=T - timedelta(hours=30, minutes=30))
    assert art.provenance(24, T)["quantile_artifact_age_h"] == 30.5


def test_the_vendored_preregistration_matches_the_sha_the_code_asserts():
    """`m2.PREREG_SHA_V2` was a constant nothing could check. The prereg is now
    in the repository, so the assertion is verifiable rather than declared."""
    import hashlib
    from pathlib import Path

    from weather_agent import m2
    p = Path(__file__).resolve().parents[1] / "prereg" / "PREREG_M2_ERROR_v2.md"
    assert p.is_file(), "the preregistration M2 v2 must be vendored with the code"
    assert hashlib.sha256(p.read_bytes()).hexdigest() == m2.PREREG_SHA_V2
