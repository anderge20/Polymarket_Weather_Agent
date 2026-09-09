#!/usr/bin/env python3
"""
fit_quantile_artifact.py — fit M2 once, out of band, and write the artifact (R30)
=================================================================================

The cycle cannot fit M2. Its DuckDB is rebuilt from the prospective NDJSON
shards and holds no realized observations; the training substrate lives in the
BACKFILL. So the fit happens here, against the backfill database, and the cycle
reads a committed file.

This script is the ONLY writer of `artifacts/m2_quantiles.json`. It refuses to
overwrite an artifact with one that is worse (fewer pairs in a stratum, or a
stratum that stops being POOLED) unless `--allow-regression` is given, because
a refit that silently narrows the model is the failure mode the artifact was
introduced to prevent.

    python3 scripts/fit_quantile_artifact.py --db data/pmw.duckdb \
        --model icon_seamless --max-age-hours 336

THE FIT INSTANT IS THE CUTOFF, NOT A TIMESTAMP. Pairs enter the fit only if
`label_available_at <= fit_instant`, exactly as `error_model.training_pairs`
would apply it inside a cycle. Recording it in the artifact is what lets the
cycle refuse an artifact fitted AFTER the decision it is being used for — the
leakage case that B's "deferring is conservative" argument implies but does not
by itself prevent.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from weather_agent import database, error_model as em, m2  # noqa: E402
from weather_agent import quantile_artifact as qa  # noqa: E402


class MixedModels(Exception):
    """More than one weather model in the training substrate."""


def _assert_single_model(con, *, dataset_version: str, model: str) -> int:
    """`m2.load_pairs` reads `weather_forecasts` WITHOUT a model predicate, and
    `model` is part of that table's primary key. If the backfill ever holds two
    models under one dataset_version, the pairs it returns are a MIXTURE and the
    quantiles describe no model in particular — silently, because nothing in the
    pair carries which model it came from.

    This script cannot separate them from outside, so it refuses rather than
    publish a mixed fit. The predicate belongs in `load_pairs` (session B's
    module, reported to B as the R19 deferred finding: `fit_m2.py` never names
    `model` nor `record_version` though both are PK). Until it is there, this is
    the guard that keeps a mixed artifact from being written.
    """
    rows = database.query(
        con,
        "SELECT model, COUNT(*) AS n FROM weather_forecasts "
        "WHERE dataset_version = ? AND forecast_tmax IS NOT NULL GROUP BY model",
        [dataset_version],
    )
    found = {r["model"]: r["n"] for r in rows}
    if not found:
        raise MixedModels(f"no forecasts at all under dataset_version={dataset_version!r}")
    if set(found) != {model}:
        raise MixedModels(
            f"weather_forecasts holds {found} under dataset_version="
            f"{dataset_version!r}; load_pairs would pool them into one fit")
    return found[model]


def fit(con, *, model: str, fit_instant: datetime, dataset_version: str,
        leads=m2.LEADS) -> tuple[dict, dict, dict]:
    """Returns (strata by lead, windows by lead, per-lead diagnostics)."""
    n_fc = _assert_single_model(con, dataset_version=dataset_version, model=model)
    pairs, _issue_by_key, stats = m2.load_pairs(con, dataset_version=dataset_version)
    strata: dict[int, em.Quantiles] = {}
    windows: dict[int, tuple[datetime | None, datetime | None]] = {}
    diag: dict[int, dict] = {}
    for lead in leads:
        used = em.training_pairs(pairs, fit_instant, lead)
        q = em.fit((p.error_c for p in used), em.SCOPE_POOLED)
        strata[lead] = q
        avail = sorted(p.label_available_at for p in used) if used else []
        windows[lead] = (avail[0], avail[-1]) if avail else (None, None)
        diag[lead] = {
            "candidates": sum(1 for p in pairs if p.lead_h == lead),
            "used": len(used),
            "scope": q.scope,
            "n": q.n,
            "spread_c": (round(q.values[90] - q.values[10], 4) if q.values else None),
        }
    diag["_load"] = stats
    diag["_forecast_rows"] = n_fc
    return strata, windows, diag


def _regressions(old: qa.QuantileArtifact | None, payload: dict) -> list[str]:
    """Ways the new artifact is WORSE than the one on disk. A refit that loses a
    stratum, or shrinks one, is not automatically wrong — but it is never
    something to discover later from a cycle that stopped producing signals."""
    if old is None:
        return []
    out = []
    for lead, st in old.strata.items():
        new = payload["strata"].get(str(lead))
        if new is None:
            out.append(f"lead {lead} h disappeared")
            continue
        if st.scope == em.SCOPE_POOLED and new["scope"] != em.SCOPE_POOLED:
            out.append(f"lead {lead} h: {st.scope} -> {new['scope']}")
        if new["n"] < st.n:
            out.append(f"lead {lead} h: n {st.n} -> {new['n']}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/pmw.duckdb")
    ap.add_argument("--out", default=qa.DEFAULT_PATH)
    ap.add_argument("--model", default="icon_seamless")
    ap.add_argument("--dataset-version", default=m2.DATASET_VERSION,
                    help="the TRAINING substrate; not the cycle's dataset_version")
    ap.add_argument("--max-age-hours", type=float, required=True,
                    help="the artifact's declared shelf life. Set it from the "
                         "measured drift of the pooled quantiles, not by eye.")
    ap.add_argument("--fit-instant", default=None,
                    help="ISO-8601 UTC cutoff on label_available_at (default: now)")
    ap.add_argument("--allow-regression", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    fit_instant = (datetime.fromisoformat(args.fit_instant.replace("Z", "+00:00"))
                   if args.fit_instant else datetime.now(timezone.utc))
    if fit_instant.tzinfo is None:
        print("--fit-instant must carry a timezone", file=sys.stderr)
        return 2

    con = database.connect(args.db, read_only=True)
    try:
        strata, windows, diag = fit(con, model=args.model, fit_instant=fit_instant,
                                    dataset_version=args.dataset_version)
    except MixedModels as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    finally:
        con.close()

    payload = qa.build_payload(
        prereg_sha256=m2.PREREG_SHA_V2, model=args.model,
        dataset_version=args.dataset_version, fit_instant=fit_instant,
        max_age_hours=args.max_age_hours, strata=strata, windows=windows,
        code_sha256=qa.source_sha256(em))

    try:
        old = qa.load(args.out)
    except qa.ArtifactUnusable:
        old = None
    regs = _regressions(old, payload)

    print(json.dumps({"fit_instant": fit_instant.isoformat(),
                      "artifact_id": payload["artifact_id"],
                      "previous": old.artifact_id if old else None,
                      "per_lead": {k: v for k, v in diag.items() if k != "_load"},
                      "regressions": regs}, indent=2, default=str))

    if not any(s.scope == em.SCOPE_POOLED for s in strata.values()):
        print("REFUSED: no lead produced a POOLED stratum; nothing to publish",
              file=sys.stderr)
        return 1
    if regs and not args.allow_regression:
        print("REFUSED: the refit is worse than the artifact on disk. Re-run with "
              "--allow-regression once you can say why.", file=sys.stderr)
        return 1
    if args.dry_run:
        print("dry run: nothing written")
        return 0

    qa.dump(payload, args.out)
    qa.load(args.out)          # read it back through every guard before claiming success
    print(f"wrote {args.out} ({payload['artifact_id'][:12]}…)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
