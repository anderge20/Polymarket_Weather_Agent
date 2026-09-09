"""
quantile_artifact.py — M2's error quantiles as a VERSIONED ARTIFACT (R30)
=========================================================================

WHY THIS EXISTS AT ALL.

`stage_forecasts` used to refit M2 inside every cycle: load every (forecast,
realized) pair and take the empirical percentiles of `e = y - f`. That is
correct and it is also unrunnable where the cycle actually runs. The training
substrate lives in the BACKFILL (`m2.DATASET_VERSION`); the cycle in GitHub
Actions rebuilds its DuckDB from the prospective NDJSON shards and has no
realized observations to learn from at all. The live cycle therefore reported
`quantiles=0 quantile_scope=INSUFFICIENT` — forecast rows written, no
distribution attached, `build_feature` returning None, zero signals. The
pipeline was complete and produced nothing.

Session B settled the design and gave the argument that carries it:

    deferring the refit is CONSERVATIVE, never leaked. An artifact fitted at
    t0 < t uses a SUBSET of what it was entitled to. Using less information
    than permitted cannot create lookahead.

That is right, and it has a corollary this module enforces: **the symmetric
case is not conservative, it is leakage.** An artifact fitted at t0 > t saw
labels that did not exist at the decision instant. It never happens forward in
time; it happens the moment `replay_cycle.py` replays an old cycle against a
newer artifact. So `fit_instant > prediction_time` is a refusal, not a warning.

B also attached the condition that makes the whole thing safe:

    the cycle REFUSES if the artifact exceeds a declared age, instead of using
    it. Fail closed on staleness, do not warn. An old artifact used in silence
    is exactly the class of failure we have spent two days hunting: it does not
    break, it produces a plausible number.

WHAT AN ARTIFACT IS.

A single JSON object, `artifacts/m2_quantiles.json`, fitted OUT of band on the
backfill and committed to the repository, so the cycle reads a file instead of
a database it does not have. It carries everything needed to answer "where did
this number come from" without opening another file:

    schema           int, this module understands SCHEMA
    prereg_sha256    sha256 of the M2 preregistration the fit obeyed
    model            the weather model the pairs came from
    dataset_version  the TRAINING substrate, named explicitly (A-51): it is a
                     different dataset_version from the cycle's, on purpose
    fit_instant      when it was fitted, UTC
    code_sha256      sha256 of error_model.py at fit time (recorded, see below)
    max_age_hours    the artifact's OWN declared shelf life
    strata           by integer lead: scope, n, the five quantiles, and the
                     bounds of the training window by `label_available_at`
    artifact_id      sha256 of the canonical JSON of everything above

THE FOUR REFUSALS (closed enum, `R_*`).

    R_STALE               prediction_time - fit_instant > max_age
    R_FIT_AFTER_DECISION  fit_instant > prediction_time         (leakage)
    R_STRATUM_ABSENT      no stratum for this lead
    R_STRATUM_NOT_POOLED  the stratum exists but is INSUFFICIENT or REJECTED
    R_PREREG_MISMATCH     fitted under a different preregistration
    R_MODEL_MISMATCH      fitted on another weather model
    R_SCHEMA_UNSUPPORTED  written by a newer builder
    R_ARTIFACT_ID_MISMATCH  the file was edited after it was fitted

WHAT IS RECORDED BUT NOT GATED, AND WHY.

`code_sha256` is written and reported, never used to refuse. The rules that
decide the numbers are frozen in the PREREGISTRATION, and `prereg_sha256` IS a
refusal — that is the substantive guard. Gating on the source sha of
`error_model.py` would stop the paper run for a corrected typo in a docstring,
and the refit that would clear it needs the backfill database, which does not
exist inside Actions. So the sha is kept for the audit trail: if the fitter
changed in a way the preregistration did not authorise, the calibration
criterion is what must catch it, not a hash of a comment.

THE REFIT WINDOW ENDS AT T_asof, NOT AT "now". Because the cycle settles
`prediction_time = min(now, T_asof)`, an artifact fitted after T_asof is refused
as leakage even though it was fitted "before the cycle". Verified live: a fit at
12:39Z was refused by a cycle whose prediction_time was 12:00Z. In practice the
refit must finish before 12:00Z for the 24 h lead and before 03:00Z for the 9 h
lead (R24 §4bis.7).

THE CYCLE MAY ONLY TIGHTEN. `--max-artifact-age-h` on `paper_cycle.py` lowers
the artifact's declared age, never raises it. An operator does not extend the
life of an artifact from the command line.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from . import error_model as em

#: Bumped when the on-disk shape changes incompatibly. A file whose `schema`
#: exceeds this was written by a newer builder and is NOT read on a guess.
SCHEMA = 1

#: The default location in the repository. Passed explicitly everywhere; this
#: constant exists so the fitter and the cycle cannot drift apart.
DEFAULT_PATH = "artifacts/m2_quantiles.json"

# ---------------------------------------------------------------------------
# refusals — closed enum, same discipline as the settlement core
# ---------------------------------------------------------------------------
R_STALE = "artifact_stale"
R_FIT_AFTER_DECISION = "artifact_fitted_after_decision"
R_STRATUM_ABSENT = "no_stratum_for_lead"
R_STRATUM_NOT_POOLED = "stratum_not_pooled"
R_PREREG_MISMATCH = "prereg_sha_mismatch"
R_MODEL_MISMATCH = "model_mismatch"
R_SCHEMA_UNSUPPORTED = "schema_unsupported"
R_ARTIFACT_ID_MISMATCH = "artifact_id_mismatch"
R_MISSING = "artifact_missing"
R_MALFORMED = "artifact_malformed"

REFUSALS = (
    R_STALE, R_FIT_AFTER_DECISION, R_STRATUM_ABSENT, R_STRATUM_NOT_POOLED,
    R_PREREG_MISMATCH, R_MODEL_MISMATCH, R_SCHEMA_UNSUPPORTED,
    R_ARTIFACT_ID_MISMATCH, R_MISSING, R_MALFORMED,
)


class ArtifactUnusable(Exception):
    """The artifact cannot be used for THIS decision. Carries a reason from the
    closed enum, so a caller records a label and never a free-text guess.

    Deliberately NOT a subclass of ValueError: `except ValueError` around the
    cycle would swallow a staleness refusal into the generic error path and the
    stage would report the wrong reason.
    """

    def __init__(self, reason: str, detail: str = ""):
        if reason not in REFUSALS:
            raise AssertionError(f"reason {reason!r} is not in the closed enum")
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}: {detail}" if detail else reason)


# ---------------------------------------------------------------------------
# canonical form
# ---------------------------------------------------------------------------


def canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    """The bytes an artifact_id is taken over: the JSON of everything EXCEPT
    `artifact_id`, keys sorted, no insignificant whitespace. Two fits that
    produced the same numbers get the same id on any machine."""
    body = {k: v for k, v in payload.items() if k != "artifact_id"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def artifact_id_of(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _parse_ts(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ArtifactUnusable(R_MALFORMED, f"{field} is not a string")
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ArtifactUnusable(R_MALFORMED, f"{field}: {exc}") from exc
    if ts.tzinfo is None:
        raise ArtifactUnusable(R_MALFORMED, f"{field} has no timezone")
    return ts.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# the artifact
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Stratum:
    """One lead's quantiles, plus the bounds of the sample they came from.

    `window_start`/`window_end` are over `label_available_at` — the instant a
    pair's realized high could first be known — because that, not the target
    date, is what M2 v2 trains on (§0, D-2). Reporting the window in the same
    terms as the training filter is what lets a reader check the two agree.
    """

    lead_h: int
    scope: str
    n: int
    values: dict[int, float]
    window_start: datetime | None
    window_end: datetime | None

    def as_quantiles(self) -> em.Quantiles:
        return em.Quantiles(scope=self.scope, n=self.n, values=dict(self.values))


@dataclass(frozen=True)
class QuantileArtifact:
    artifact_id: str
    schema: int
    prereg_sha256: str
    model: str
    dataset_version: str
    fit_instant: datetime
    code_sha256: str | None
    max_age_hours: float
    strata: dict[int, Stratum]
    path: str | None = None

    # -- the guards ---------------------------------------------------------
    def age_at(self, prediction_time: datetime) -> timedelta:
        return prediction_time - self.fit_instant

    def check(self, prediction_time: datetime, *, model: str,
              prereg_sha256: str, max_age_hours: float | None = None) -> None:
        """Every check that does not depend on the lead. Raises ArtifactUnusable.

        `max_age_hours` from the caller may only TIGHTEN the artifact's own
        declared shelf life; a larger value is ignored rather than honoured.
        """
        if self.model != model:
            raise ArtifactUnusable(
                R_MODEL_MISMATCH, f"artifact fitted on {self.model!r}, cycle runs {model!r}")
        if self.prereg_sha256 != prereg_sha256:
            raise ArtifactUnusable(
                R_PREREG_MISMATCH,
                f"artifact declares {self.prereg_sha256[:12]}…, code expects "
                f"{prereg_sha256[:12]}…")

        age = self.age_at(prediction_time)
        if age < timedelta(0):
            # NOT a warning. An artifact fitted after the decision instant saw
            # labels that did not exist yet; B's own argument for deferring the
            # refit is exactly what makes the mirror case leakage.
            raise ArtifactUnusable(
                R_FIT_AFTER_DECISION,
                f"fit_instant {self.fit_instant.isoformat()} is after "
                f"prediction_time {prediction_time.isoformat()}")

        limit_h = self.max_age_hours
        if max_age_hours is not None:
            limit_h = min(limit_h, float(max_age_hours))
        if age > timedelta(hours=limit_h):
            raise ArtifactUnusable(
                R_STALE,
                f"age {age.total_seconds() / 3600:.1f} h exceeds the "
                f"{limit_h:g} h limit in force")

    def quantiles(self, lead_h: int, prediction_time: datetime, *, model: str,
                  prereg_sha256: str, max_age_hours: float | None = None) -> em.Quantiles:
        """The stratum for this lead, or a refusal. Runs `check` first, so a
        stale artifact is refused even when the lead is missing too — the
        staleness is the more informative fact."""
        self.check(prediction_time, model=model, prereg_sha256=prereg_sha256,
                   max_age_hours=max_age_hours)
        st = self.strata.get(int(lead_h))
        if st is None:
            raise ArtifactUnusable(
                R_STRATUM_ABSENT,
                f"lead {lead_h} h not in {sorted(self.strata)}")
        if st.scope != em.SCOPE_POOLED or not st.values:
            # An INSUFFICIENT or REJECTED stratum is a fit that M2 itself
            # declined to publish. It is stored so the artifact is a complete
            # record of the fit, and it is never used.
            raise ArtifactUnusable(
                R_STRATUM_NOT_POOLED,
                f"lead {lead_h} h has scope {st.scope} (n={st.n})")
        return st.as_quantiles()

    # -- provenance, for cycle_params ---------------------------------------
    def provenance(self, lead_h: int | None = None,
                   prediction_time: datetime | None = None) -> dict:
        """What the cycle records about the artifact it used. Small on purpose:
        the id identifies the file exactly, the rest is what a reader needs
        without opening it.

        `quantile_artifact_age_h` is B's addition and it earns its place: when a
        decision has to be audited, the EFFECTIVE age at the moment of use is the
        datum. Leaving a reader to subtract two instants — one of them not in the
        same row — is how an audit gets the arithmetic wrong."""
        st = self.strata.get(int(lead_h)) if lead_h is not None else None
        return {
            "quantile_artifact_id": self.artifact_id,
            "quantile_artifact_fit_instant": self.fit_instant.isoformat(),
            "quantile_artifact_age_h": (
                round(self.age_at(prediction_time).total_seconds() / 3600, 4)
                if prediction_time is not None else None),
            "quantile_artifact_prereg_sha256": self.prereg_sha256,
            "quantile_artifact_dataset_version": self.dataset_version,
            "quantile_artifact_max_age_hours": self.max_age_hours,
            "quantile_artifact_code_sha256": self.code_sha256,
            "quantile_stratum_lead_h": int(lead_h) if lead_h is not None else None,
            "quantile_stratum_n": st.n if st else None,
            "quantile_stratum_scope": st.scope if st else None,
            "quantile_window_start": (st.window_start.isoformat()
                                      if st and st.window_start else None),
            "quantile_window_end": (st.window_end.isoformat()
                                    if st and st.window_end else None),
        }


# ---------------------------------------------------------------------------
# read / write
# ---------------------------------------------------------------------------


def from_payload(payload: Mapping[str, Any], *, path: str | None = None) -> QuantileArtifact:
    """Parse and VERIFY a payload. The id is recomputed and compared, so a file
    edited by hand after the fit is refused rather than trusted."""
    if not isinstance(payload, Mapping):
        raise ArtifactUnusable(R_MALFORMED, "payload is not an object")
    schema = payload.get("schema")
    if not isinstance(schema, int):
        raise ArtifactUnusable(R_MALFORMED, "schema is missing or not an int")
    if schema > SCHEMA:
        raise ArtifactUnusable(
            R_SCHEMA_UNSUPPORTED, f"file says schema {schema}, this build reads {SCHEMA}")

    declared = payload.get("artifact_id")
    computed = artifact_id_of(payload)
    if declared != computed:
        raise ArtifactUnusable(
            R_ARTIFACT_ID_MISMATCH,
            f"declared {str(declared)[:12]}…, recomputed {computed[:12]}…")

    for field in ("prereg_sha256", "model", "dataset_version"):
        if not isinstance(payload.get(field), str) or not payload[field]:
            raise ArtifactUnusable(R_MALFORMED, f"{field} is missing or empty")
    max_age = payload.get("max_age_hours")
    if not isinstance(max_age, (int, float)) or max_age <= 0:
        raise ArtifactUnusable(R_MALFORMED, "max_age_hours must be a positive number")

    raw_strata = payload.get("strata")
    if not isinstance(raw_strata, Mapping) or not raw_strata:
        raise ArtifactUnusable(R_MALFORMED, "strata is missing or empty")
    strata: dict[int, Stratum] = {}
    for key, body in raw_strata.items():
        try:
            lead = int(key)
        except (TypeError, ValueError) as exc:
            raise ArtifactUnusable(R_MALFORMED, f"stratum key {key!r}") from exc
        if not isinstance(body, Mapping):
            raise ArtifactUnusable(R_MALFORMED, f"stratum {lead} is not an object")
        scope = body.get("scope")
        if scope not in (em.SCOPE_POOLED, em.SCOPE_STATION, em.SCOPE_REJECTED,
                         em.SCOPE_INSUFFICIENT):
            raise ArtifactUnusable(R_MALFORMED, f"stratum {lead}: scope {scope!r}")
        values_in = body.get("values") or {}
        if not isinstance(values_in, Mapping):
            raise ArtifactUnusable(R_MALFORMED, f"stratum {lead}: values is not an object")
        values: dict[int, float] = {}
        for lvl, v in values_in.items():
            try:
                values[int(lvl)] = float(v)
            except (TypeError, ValueError) as exc:
                raise ArtifactUnusable(
                    R_MALFORMED, f"stratum {lead}: level {lvl!r} -> {v!r}") from exc
        if scope == em.SCOPE_POOLED:
            # A usable stratum carries EVERY level M2 declared, in order. A
            # partial one would be caught later by a KeyError deep in
            # `forecast_quantiles_c`, which is not a refusal reason.
            if set(values) != set(em.LEVELS):
                raise ArtifactUnusable(
                    R_MALFORMED,
                    f"stratum {lead}: levels {sorted(values)} != {list(em.LEVELS)}")
            ordered = [values[lvl] for lvl in em.LEVELS]
            if any(a > b for a, b in zip(ordered, ordered[1:])):
                raise ArtifactUnusable(
                    R_MALFORMED, f"stratum {lead}: quantiles are not monotone: {ordered}")
        n = body.get("n")
        if not isinstance(n, int) or n < 0:
            raise ArtifactUnusable(R_MALFORMED, f"stratum {lead}: n is missing or negative")
        strata[lead] = Stratum(
            lead_h=lead, scope=scope, n=n, values=values,
            window_start=(_parse_ts(body["window_start"], f"stratum {lead} window_start")
                          if body.get("window_start") else None),
            window_end=(_parse_ts(body["window_end"], f"stratum {lead} window_end")
                        if body.get("window_end") else None),
        )

    return QuantileArtifact(
        artifact_id=computed,
        schema=schema,
        prereg_sha256=payload["prereg_sha256"],
        model=payload["model"],
        dataset_version=payload["dataset_version"],
        fit_instant=_parse_ts(payload.get("fit_instant"), "fit_instant"),
        code_sha256=payload.get("code_sha256"),
        max_age_hours=float(max_age),
        strata=strata,
        path=path,
    )


def load(path: str | Path) -> QuantileArtifact:
    p = Path(path)
    if not p.is_file():
        raise ArtifactUnusable(R_MISSING, str(p))
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactUnusable(R_MALFORMED, f"{p}: {exc}") from exc
    return from_payload(payload, path=str(p))


def build_payload(*, prereg_sha256: str, model: str, dataset_version: str,
                  fit_instant: datetime, max_age_hours: float,
                  strata: Mapping[int, em.Quantiles],
                  windows: Mapping[int, tuple[datetime | None, datetime | None]] | None = None,
                  code_sha256: str | None = None) -> dict:
    """Assemble a payload and stamp its id. The fitter's only entry point, so an
    artifact can never be written with an id that does not match its content."""
    if fit_instant.tzinfo is None:
        raise ValueError("fit_instant must be timezone-aware")
    windows = windows or {}
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "prereg_sha256": prereg_sha256,
        "model": model,
        "dataset_version": dataset_version,
        "fit_instant": fit_instant.astimezone(timezone.utc).isoformat(),
        "code_sha256": code_sha256,
        "max_age_hours": float(max_age_hours),
        "strata": {},
    }
    for lead in sorted(strata):
        q = strata[lead]
        w_start, w_end = windows.get(lead, (None, None))
        body["strata"][str(int(lead))] = {
            "scope": q.scope,
            "n": q.n,
            "values": {str(lvl): float(v) for lvl, v in sorted(q.values.items())},
            "window_start": w_start.astimezone(timezone.utc).isoformat() if w_start else None,
            "window_end": w_end.astimezone(timezone.utc).isoformat() if w_end else None,
        }
    body["artifact_id"] = artifact_id_of(body)
    return body


def dump(payload: Mapping[str, Any], path: str | Path) -> str:
    """Write the artifact, pretty-printed so a diff of a refit is readable, and
    return its id. The id is over the CANONICAL bytes, not over these, so the
    formatting here is free."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                 encoding="utf-8")
    return payload["artifact_id"]


def source_sha256(module) -> str | None:
    """sha256 of a module's source file, for the audit trail. Never used to
    refuse: see the module docstring."""
    f = getattr(module, "__file__", None)
    if not f:
        return None
    try:
        return hashlib.sha256(Path(f).read_bytes()).hexdigest()
    except OSError:
        return None
