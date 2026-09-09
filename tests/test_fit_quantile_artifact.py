"""Tests for scripts/fit_quantile_artifact.py — the ONLY writer of the artifact.

A fitter authored without execution is how this project produced most of its
defects, so this runs it: a seeded backfill in, a loadable artifact out, through
every guard the cycle will apply to it.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from weather_agent import database, error_model as em, m2, quantile_artifact as qa

_SPEC = importlib.util.spec_from_file_location(
    "fit_quantile_artifact",
    Path(__file__).resolve().parents[1] / "scripts" / "fit_quantile_artifact.py")
fit_artifact = importlib.util.module_from_spec(_SPEC)
sys.modules["fit_quantile_artifact"] = fit_artifact
_SPEC.loader.exec_module(fit_artifact)

DSV = "backfill_test_v1"
STATION = "EGLC"
MODEL = "icon_seamless"
LEAD = 24
NOW = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)


def _err(i: int) -> float:
    """A spread of errors, not a constant. `error_model.fit` REJECTS a stratum
    whose p90-p10 is zero (MIN_SPREAD_C is a strict bound: a degenerate sample is
    not a distribution), so a fixture with one repeated error would have proved
    the guard fires, not that the fit works."""
    return round(-1.5 + (i % 7) * 0.5, 3)


def _seed(con, *, days=45, model=MODEL, station=STATION, with_obs=True,
          dataset_version=DSV):
    """`days` (forecast, realized) pairs at the 24 h lead, with known errors.

    The issue_time is taken from `m2.pick_run` rather than assumed, because
    `load_pairs` assigns the lead by matching the issue against exactly that —
    an assumed run would be counted as `unmatched_lead` and produce no pair.
    """
    made = 0
    for i in range(days):
        td = date(2026, 6, 1) + timedelta(days=i)
        end = datetime(td.year, td.month, td.day, 12, tzinfo=timezone.utc)
        issue = m2.pick_run(end - timedelta(hours=LEAD), MODEL)
        if issue is None:
            continue
        f = 20.0
        con.execute(
            "INSERT INTO weather_forecasts (issue_time, target_date, station, model, "
            "forecast_tmax, available_at, ingestion_timestamp, dataset_version, "
            "record_version) VALUES (?,?,?,?,?,?,?,?,?)",
            [issue, td, station, model, f, issue, NOW, dataset_version, 1])
        if with_obs:
            # The realized high is a property of the STATION AND DAY, not of the
            # model: a second model under the same dataset_version shares these
            # rows, which is exactly why a mixed substrate pools silently.
            con.execute(
                "INSERT INTO weather_observations (station, source, "
                "observation_time, tmax_observed, ingestion_timestamp, "
                "dataset_version, record_version) VALUES (?,?,?,?,?,?,?)",
                [station, "METAR", datetime(td.year, td.month, td.day, 15,
                                            tzinfo=timezone.utc),
                 f + _err(i), NOW, dataset_version, 1])
        made += 1
    return made


@pytest.fixture
def con():
    c = database.init_db(database.connect(":memory:"))
    yield c
    c.close()


def test_a_seeded_backfill_produces_a_loadable_artifact(con, tmp_path):
    n = _seed(con)
    assert n >= em.MIN_N, "the fixture must clear MIN_N or the test proves nothing"
    strata, windows, diag = fit_artifact.fit(
        con, model=MODEL, fit_instant=NOW, dataset_version=DSV)
    assert strata[LEAD].scope == em.SCOPE_POOLED
    assert strata[LEAD].n == n
    # e = y - f, and the seeded errors run -1.5 .. +1.5 in steps of 0.5
    assert strata[LEAD].values[10] == pytest.approx(-1.5, abs=0.5)
    assert strata[LEAD].values[90] == pytest.approx(1.5, abs=0.5)
    assert strata[LEAD].values[90] > strata[LEAD].values[10]
    assert windows[LEAD][0] is not None and windows[LEAD][1] is not None

    payload = qa.build_payload(
        prereg_sha256=m2.PREREG_SHA_V2, model=MODEL, dataset_version=DSV,
        fit_instant=NOW, max_age_hours=336.0, strata=strata, windows=windows)
    art = qa.load(qa.dump(payload, tmp_path / "a.json") and (tmp_path / "a.json"))
    q = art.quantiles(LEAD, NOW + timedelta(hours=1), model=MODEL,
                      prereg_sha256=m2.PREREG_SHA_V2)
    assert q.n == n


def test_the_fit_instant_is_a_cutoff_and_not_a_timestamp(con):
    """Pairs enter only if their label was already available. Moving the cutoff
    back must shrink the sample, or the artifact's `fit_instant` would be
    decoration rather than the thing the leakage guard compares against."""
    _seed(con)
    late, _, _ = fit_artifact.fit(con, model=MODEL, fit_instant=NOW,
                                 dataset_version=DSV)
    early, _, _ = fit_artifact.fit(con, model=MODEL,
                                   fit_instant=datetime(2026, 6, 20, tzinfo=timezone.utc),
                                   dataset_version=DSV)
    assert 0 < early[LEAD].n < late[LEAD].n


def test_two_models_under_one_dataset_version_are_refused_not_pooled(con):
    """`m2.load_pairs` reads weather_forecasts with NO model predicate, though
    `model` is part of that table's primary key. A mixed sample would produce
    quantiles describing no model in particular, silently — nothing in a Pair
    says which model it came from."""
    _seed(con)
    _seed(con, model="ecmwf_ifs025", with_obs=False)
    with pytest.raises(fit_artifact.MixedModels) as e:
        fit_artifact.fit(con, model=MODEL, fit_instant=NOW, dataset_version=DSV)
    assert "ecmwf_ifs025" in str(e.value)


def test_an_empty_substrate_is_refused_rather_than_fitted_on_nothing(con):
    with pytest.raises(fit_artifact.MixedModels):
        fit_artifact.fit(con, model=MODEL, fit_instant=NOW, dataset_version="nope")


def test_a_refit_that_loses_a_stratum_is_reported_as_a_regression(tmp_path):
    good = qa.build_payload(
        prereg_sha256=m2.PREREG_SHA_V2, model=MODEL, dataset_version=DSV,
        fit_instant=NOW, max_age_hours=336.0,
        strata={9: em.Quantiles(em.SCOPE_POOLED, 100,
                                {10: -1.0, 25: -0.5, 50: 0.0, 75: 0.5, 90: 1.0}),
                24: em.Quantiles(em.SCOPE_POOLED, 147,
                                 {10: -1.5, 25: -0.5, 50: 0.4, 75: 1.3, 90: 2.2})})
    old = qa.load(qa.dump(good, tmp_path / "old.json") and (tmp_path / "old.json"))

    shrunk = qa.build_payload(
        prereg_sha256=m2.PREREG_SHA_V2, model=MODEL, dataset_version=DSV,
        fit_instant=NOW, max_age_hours=336.0,
        strata={24: em.Quantiles(em.SCOPE_INSUFFICIENT, 12, {})})
    regs = fit_artifact._regressions(old, shrunk)
    assert any("9 h disappeared" in r for r in regs)
    assert any("POOLED -> INSUFFICIENT" in r for r in regs)
    assert any("n 147 -> 12" in r for r in regs)


def test_the_cli_refuses_to_publish_a_fit_with_no_usable_stratum(con, tmp_path, capsys):
    """A fit that produced nothing must not overwrite a good artifact with an
    empty one — the cycle would then stop for `stratum_not_pooled` and the
    reason would point at the artifact instead of at the fit that emptied it."""
    _seed(con, days=5)                       # below MIN_N on purpose
    db_path = tmp_path / "b.duckdb"
    disk = database.init_db(database.connect(str(db_path)))
    _seed(disk, days=5)
    disk.close()
    rc = fit_artifact.main(["--db", str(db_path), "--out", str(tmp_path / "out.json"),
                            "--dataset-version", DSV, "--max-age-hours", "336"])
    assert rc == 1
    assert "no lead produced a POOLED stratum" in capsys.readouterr().err
    assert not (tmp_path / "out.json").exists()


def test_the_cli_writes_an_artifact_it_can_read_back(con, tmp_path, capsys):
    db_path = tmp_path / "c.duckdb"
    disk = database.init_db(database.connect(str(db_path)))
    n = _seed(disk)
    disk.close()
    out = tmp_path / "m2_quantiles.json"
    rc = fit_artifact.main(["--db", str(db_path), "--out", str(out),
                            "--dataset-version", DSV, "--max-age-hours", "336",
                            "--fit-instant", NOW.isoformat()])
    assert rc == 0
    art = qa.load(out)                       # every guard, again, from the file
    assert art.strata[LEAD].n == n
    assert art.dataset_version == DSV
    assert art.code_sha256                   # recorded for the audit trail
    # the id the script announced is the id the file carries
    report = json.loads(capsys.readouterr().out.split("wrote ")[0])
    assert report["artifact_id"] == art.artifact_id
    assert report["per_lead"][str(LEAD)]["used"] == n


def test_a_dry_run_writes_nothing(tmp_path):
    db_path = tmp_path / "d.duckdb"
    disk = database.init_db(database.connect(str(db_path)))
    _seed(disk)
    disk.close()
    out = tmp_path / "dry.json"
    assert fit_artifact.main(["--db", str(db_path), "--out", str(out),
                              "--dataset-version", DSV, "--max-age-hours", "336",
                              "--dry-run"]) == 0
    assert not out.exists()
