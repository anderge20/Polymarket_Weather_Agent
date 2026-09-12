#!/usr/bin/env python3
"""
paper_cycle.py — one paper-mode cycle, sized for a single GitHub Actions run.
=============================================================================
A cycle is: rebuild state from the shard store, discover open markets, snapshot
their books, generate signals, simulate fills, settle whatever resolved, and write
the new rows back out as shards. It is idempotent and resumable: re-running the
same `--session-id` continues where the previous attempt stopped instead of
starting a second cycle. That is what makes it safe on a cron trigger that can be
delayed, retried, or cancelled mid-job.

STAGES REPORT THEIR OWN STATUS. Any stage whose substrate is missing returns
SKIPPED with the reason instead of failing the run or, worse, inventing an input.
The forecast/signal stages depend on `weather_forecasts` quantiles (M2, owned by
session B); until those exist the cycle still collects books every day — which is
the part that cannot be back-filled later, because order-book history does not
exist retrospectively. Losing a day of book collection is permanent; losing a day
of signals is not.

`--target-date` IS OBLIGATORY, and that is PHASE_2D_STRATEGY_A_DESIGN.md §C being
honoured, not worked around. §C says target_date is "un parámetro obligatorio
proporcionado por el caller" and forbids deriving it from resolution_timestamp,
close_time, endDate, question, slug or description. Here the caller is the
scheduler, and the scheduler states the date. Selecting WHICH open markets belong
to that date is a separate, declared universe filter (`select_universe`), not a
derivation of the contract parameter — the distinction is recorded in DECISIONS.md
rather than blurred in code.

NO CREDENTIALS. Public endpoints only. Gate D0 (no real money) holds structurally:
nothing in this script or in the modules it imports can sign or place an order.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import time
import traceback
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from weather_agent import (collector, config, database as db, paper,  # noqa: E402
                           quantile_artifact, settlement, store)
from weather_agent.polymarket import discovery  # noqa: E402

#: Tables the cycle rebuilds from shards on entry and dumps back on exit — the
#: full paper state. `markets`/`outcomes` are re-discovered from gamma every run,
#: but they are persisted anyway: their prospective `available_at` records the
#: instant we FIRST could have known a market existed, and re-discovering it
#: tomorrow would stamp tomorrow's instant and quietly destroy that evidence.
#: `paper_trades` is the ledger and is the reason any of this exists.
#: Slowly-changing catalogue. Re-discovered from gamma on EVERY cycle, which
#: re-stamps `ingestion_timestamp` on every row — so the `since` filter cannot
#: tell a genuinely new market from one seen eight times today, and dumping these
#: each cycle would add near-identical shards to git. MEASURED, not estimated:
#: 206 KiB compressed per snapshot (markets 83 + outcomes 123 + fees 0.3, at
#: 1 100 / 2 200 / 1 rows). They are therefore dumped on every cycle that DECIDES
#: — two a day, 8.5 MiB over the run, which is the price of C3 being reproducible
#: — and skipped on the eight daily collect-only cycles, which decide nothing and
#: leave the replay nothing to reproduce.
#: Losing the intra-day copies costs nothing: `discovery.ingest_event` already
#: keeps the EARLIEST `available_at` and `discovered_at` across re-ingests, so the
#: first-discovery instant survives in the daily snapshot rather than being
#: overwritten by the last look.
CATALOGUE_TABLES = ("markets", "outcomes", "market_fee_schedule")

#: Append-mostly state. Every row is a new observation or a new decision, so the
#: `since` filter is exact and these are dumped on every cycle.
LEDGER_TABLES = (
    "orderbook_snapshots", "price_history", "trades",
    "weather_forecasts", "weather_observations",
    "predictions", "signals", "markets_excluded", "paper_trades",
)

STATE_TABLES = CATALOGUE_TABLES + LEDGER_TABLES

OK, SKIPPED, STOPPED = "OK", "SKIPPED", "STOPPED"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _coverage_also(spec: str) -> tuple[float, date]:
    """Parse `LEAD:YYYY-MM-DD` IN ARGPARSE, before the cycle makes one request.

    WHERE THIS RUNS IS THE WHOLE POINT, and session B found it. The coverage
    stage sits between `stage_collect` — the order-book capture, the one thing
    in this project that cannot be recovered afterwards — and `stage_dump`, the
    only place that capture is persisted. `stage_dump` is inside the `try`; the
    `finally` only closes the connection. So an exception anywhere in that span
    means the dump never runs and the collection is LOST.

    A bare `float()` and `date.fromisoformat()` inside the stage put a
    destroy-the-capture path one mistyped character away in a cron line:
    `9:2026-13-45` would collect 1 078 tokens and then throw. Validated here it
    costs nothing and fails before the first request.

    THE GENERAL RULE, worth more than this function: between `stage_collect` and
    `stage_dump`, NOTHING MAY THROW. That span is the only one where an
    exception destroys data that cannot be re-fetched.
    """
    lead_s, sep, td_s = spec.partition(":")
    if not sep:
        raise argparse.ArgumentTypeError(
            f"expected LEAD:YYYY-MM-DD, got {spec!r}")
    try:
        lead = float(lead_s)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"lead must be a number, got {lead_s!r} in {spec!r}") from None
    if not lead > 0:
        raise argparse.ArgumentTypeError(f"lead must be positive, got {lead}")
    try:
        td = date.fromisoformat(td_s)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"target must be YYYY-MM-DD, got {td_s!r} in {spec!r}") from None
    return lead, td


def t_end(target_date: date) -> datetime:
    """`T_end` = target_date 12:00:00Z — the end of the resolution window (R8,
    verified on 8 557/8 557 events). It only serves to derive the lead; it is
    never a decision instant."""
    return datetime.combine(target_date, datetime.min.time(),
                            tzinfo=timezone.utc) + timedelta(hours=12)


def decision_time(target_date: date, lead_hours: float, now: datetime) -> dict:
    """Resolve the instant the cycle is allowed to decide at.

        T_asof = T_end - lead_hours          (the declared as-of)
        prediction_time = min(now, T_asof)

    The clamp is the whole point, and it cuts both ways:
      * fired EARLY (the cron does, deliberately) -> `now` wins, so the decision
        uses strictly LESS information than the lead allows. Safe.
      * fired LATE (Actions cron drifts) -> `T_asof` wins, so data that only
        became available during the drift cannot enter a decision that still
        claims to be as-of `T_asof`. Without the clamp the declared lead would be
        a fiction, which is exactly the defect A-32 found in someone else's
        document — the availability rule stated in prose and never applied.

    `lead_effective` is measured, never assumed: it is what actually happened.

    WHEN this is called matters as much as what it computes. It must be evaluated
    AFTER collection, not at cycle start: the decision instant is when we decide,
    which is necessarily after we have gathered what we decide on. Computed at
    start, `prediction_time` lands BEFORE the `observation_time` of the prices the
    same cycle is about to collect, and `build_feature`'s as-of filter
    (`observation_time <= prediction_time`) then rejects every one of them — 0
    signals, for the third time and by a third mechanism."""
    end = t_end(target_date)
    asof = end - timedelta(hours=float(lead_hours))
    pt = min(now, asof)
    return {
        "t_end": end,
        "t_asof": asof,
        "prediction_time": pt,
        "lead_nominal_h": float(lead_hours),
        "lead_effective_h": (end - pt).total_seconds() / 3600.0,
        "fired_early": now < asof,
        "drift_h": (now - asof).total_seconds() / 3600.0,
    }


class Cycle:
    """Accumulates per-stage results so the job log shows one auditable summary."""

    def __init__(self, **meta):
        self.meta = meta
        self.stages: list[dict] = []
        self.started_at = _utcnow()
        self._last_stage_at: datetime | None = None

    def stage(self, name: str, status: str, **detail) -> dict:
        # WHEN EACH STAGE HAPPENED, because an aggregate localises nothing.
        # The cycle's pre-collection time grew 8.23 → 11.38 min over five slots
        # on 2026-09-10 with the token count flat, and no stage recorded a
        # duration, so "something is slow" could not become "this is slow".
        # `at_s` is from cycle start, `elapsed_s` from the previous stage — two
        # fields, and the second is the one that points.
        now = _utcnow()
        prev = self._last_stage_at or self.started_at
        entry = {"stage": name, "status": status,
                 "at_s": round((now - self.started_at).total_seconds(), 2),
                 "elapsed_s": round((now - prev).total_seconds(), 2),
                 **detail}
        self._last_stage_at = now
        self.stages.append(entry)
        line = f"[{status:7}] {name}"
        extras = " ".join(f"{k}={v}" for k, v in detail.items() if k != "traceback")
        print(f"{line}  {extras}".rstrip(), flush=True)
        return entry

    def summary(self) -> dict:
        return {
            **self.meta,
            "started_at": _iso(self.started_at),
            "finished_at": _iso(_utcnow()),
            "stages": self.stages,
            "stopped": any(s["status"] == STOPPED for s in self.stages),
        }


# --------------------------------------------------------------------------- stages
def stage_load_state(cy: Cycle, con, *, root: str) -> None:
    """Rebuild the operational tables from the shard store.

    The DuckDB file is derived state: an Actions runner starts with an empty disk,
    so this is where continuity actually comes from."""
    total = 0
    for table in STATE_TABLES:
        try:
            out = store.load_shards(con, table=table, root=root)
        except Exception as exc:
            cy.stage(f"load:{table}", STOPPED, error=repr(exc))
            raise
        total += out["rows_written"]
        cy.stage(f"load:{table}", OK, shards=out["shards"], rows=out["rows_written"])
    stats = store.store_stats(root)
    # TWO COUNTS, BECAUSE THEY STOPPED BEING THE SAME NUMBER IN THIS PR.
    #
    # `rows_loaded` sums what `upsert_many` returns, which is the batch's size
    # AFTER deduplicating within that batch — a fact about the work this cycle
    # did. Dumping the catalogue every cycle means the store now holds many
    # copies of the same 1 100 market rows, each loaded as its OWN batch, so each
    # returns its own 1 100. Nothing is wrong with that number; it is just not
    # the one the RAM projection needs.
    #
    # `rows_resident` is. What occupies memory is DISTINCT rows in the database,
    # and after this PR the two diverge by about 11 000 rows a day — roughly
    # +57 % on the count, which applied to a per-row slope would move the
    # projected ceiling from ~97 days to ~62. A false alarm planted inside the
    # instrument built to raise real ones.
    #
    # Session B caught it on review, and it is the THIRD time this one field has
    # turned up in an interaction between two PRs that are each correct alone
    # (#25 with #26, now #25 with this one). Twelve `COUNT(*)` against an
    # in-memory database, once per cycle.
    #
    # No `try/except` around the count: `init_db` creates every `STATE_TABLES`
    # entry, this runs BEFORE `stage_collect` so nothing captured can be lost by
    # raising here, and a swallowed exception would under-report residency —
    # which is the alarmist direction for a ceiling projection, and silent.
    resident = sum(int(db.query(con, f"SELECT count(*) AS n FROM {t}")[0]["n"])
                   for t in STATE_TABLES)
    cy.stage("load:store_stats", OK, tables=len(stats.get("tables", {})),
             total_bytes=stats.get("total_bytes", 0), rows_loaded=total,
             rows_resident=resident)


#: Tables `features.build_feature` and `strategy_a` read WITHOUT filtering by
#: dataset_version — see `stage_guard_dataset_version`.
UNFILTERED_READS = ("price_history", "weather_forecasts")


def stage_guard_dataset_version(cy: Cycle, con, *, dataset_version: str) -> dict:
    """Fail loudly if more than one dataset_version is present in the tables the
    feature builder reads WITHOUT filtering.

    THE DEFECT THIS GUARDS AGAINST IS NOT MINE TO FIX, BUT THE RISK IS MINE TO
    CREATE. As of A-37 session B fixed `features.build_feature`, whose two as-of
    reads now DO filter by `dataset_version`. What remains unfiltered is
    `strategy_a`'s price-lineage guard, which still re-queries `price_history`
    without it while its own comment claims to be "matching features.py" — no
    longer true. With ONE dataset_version in the database that is harmless, which
    is why session B's end-to-end run is unaffected: measured 2026-09-09, every
    table carried only `backfill_2b_v1`.

    This docstring said "build_feature never uses it" until PR #8 made that half
    false. A guard whose stated justification is wrong is a guard the next reader
    removes by mistake, so it is corrected here rather than left to age.

    Paper mode is what makes it dangerous: it introduces a SECOND dataset_version
    (`ds_paper_v1`). The day a database holds both, `build_feature` would silently
    mix a backfilled price with a prospectively-collected one and no error would
    be raised. The same applies to `record_version` > 1, where `latest_asof` could
    return a superseded row.

    So rather than edit a file another session has open, this asserts the
    precondition under which the omission is harmless, and stops the cycle when it
    stops holding. Fixing `features.py` is delivered to B as a patch (A-37)."""
    # A GUARD THAT CANNOT LOOK MUST REFUSE, NOT SKIP. Session B's residual on
    # PR #21, and the distinction is the whole point: `_non_fatal` records
    # SKIPPED and CONTINUES, and for a guard continuing is exactly what must not
    # happen — "I could not check whether the substrate is ambiguous" is not
    # "the substrate is fine". A missing table, a locked database, any DuckDB
    # error: the verdict is a REFUSAL with the error inside it, so the cycle
    # degrades to collect-only and still reaches the dump.
    #
    # It now fails closed in BOTH directions: when it finds ambiguity, and when
    # it cannot look.
    problems = []
    try:
        for table in UNFILTERED_READS:
            rows = db.query(
                con,
                f"SELECT dataset_version, count(*) AS n FROM {db._q(table)} "
                "GROUP BY 1 ORDER BY 2 DESC",
            )
            versions = [r["dataset_version"] for r in rows]
            if len(versions) > 1:
                problems.append(
                    f"{table}: {len(versions)} dataset_versions present "
                    f"({', '.join(str(v) for v in versions[:4])}) — build_feature does "
                    f"not filter by it and would mix them silently"
                )
            elif versions and versions[0] != dataset_version:
                problems.append(
                    f"{table}: holds {versions[0]!r}, cycle runs as {dataset_version!r}"
                )
            rv = db.query(
                con, f"SELECT DISTINCT record_version FROM {db._q(table)}"
            )
            if len([r["record_version"] for r in rv if r["record_version"] is not None]) > 1:
                problems.append(
                    f"{table}: more than one record_version — latest_asof may return a "
                    f"superseded row"
                )
    except Exception as exc:                 # noqa: BLE001 — deliberate, above
        detail = f"guard could not run: {type(exc).__name__}: {exc}"[:300]
        cy.stage("guard:dataset_version", STOPPED,
                 problems=json.dumps([detail]),
                 effect="degraded_to_collect_only")
        return {"ok": False, "problems": [detail]}

    if problems:
        # IT REFUSES THE DECISION, NOT THE CYCLE — which is what it always said
        # it did. Its own message reads "refusing to DECIDE" and the call site
        # says "a cycle that only collects is harmless"; the implementation
        # raised SystemExit and took the whole run down with it.
        #
        # That matters because of WHERE it sits: between `stage_collect` — the
        # order-book capture, the one thing here that cannot be re-fetched — and
        # `stage_dump`, the only place that capture is persisted, with
        # `stage_dump` inside the `try`. So a guard that exists to protect a
        # decision was also discarding the collection, and the asymmetry runs
        # the wrong way: tomorrow's cycle can decide again, tomorrow's book is
        # gone. Found by session B while approving PR #19, as the instance of the
        # span rule that PR fixed only where it had been touched.
        #
        # STOPPED is kept as the status: the refusal is real and must stay
        # visible. What changes is that the caller degrades to collect-only
        # instead of the process dying.
        cy.stage("guard:dataset_version", STOPPED, problems=json.dumps(problems),
                 effect="degraded_to_collect_only")
        return {"ok": False, "problems": problems}
    cy.stage("guard:dataset_version", OK, tables=len(UNFILTERED_READS),
             dataset_version=dataset_version)
    return {"ok": True}


def stage_discover(cy: Cycle, con, *, dataset_version: str, target_date: date,
                   horizon_days: int, session, max_pages: int) -> dict:
    """Discover OPEN markets (R26) whose endDate is in the future.

    `available_at` is stamped at the instant of the request, which is what makes a
    prospective catalogue usable as-of — the retrospective backfill cannot claim
    the same (D17)."""
    now = _utcnow()
    end_max = datetime.combine(target_date + timedelta(days=horizon_days),
                               datetime.min.time(), tzinfo=timezone.utc)
    try:
        out = discovery.discover(
            con, dataset_version,
            end_date_min=_iso(now), end_date_max=_iso(end_max),
            closed=False, session=session, max_pages=max_pages,
        )
    except Exception as exc:
        cy.stage("discover", STOPPED, error=repr(exc),
                 traceback=traceback.format_exc())
        return {}
    stopped = out.get("stopped_early") or out.get("status") not in (None, "OK")
    cy.stage("discover", STOPPED if stopped else OK,
             pages=out.get("pages"), events=out.get("events"),
             markets=out.get("markets"), outcomes=out.get("outcomes"),
             api_status=out.get("status"),
             errors=len(out.get("errors") or []))
    return out


def select_universe(con, *, dataset_version: str, target_date: date) -> list[dict]:
    """UNIVERSE FILTER — not a target_date derivation (see the module docstring).

    The caller has already fixed `target_date`; this only asks which of the open
    markets belong to it. The predicate is gamma's `endDate`, which `markets` keeps
    verbatim inside `source_timestamps` (there is no dedicated column, and
    `close_time` is NULL for an open market — it is `closedTime`, which only exists
    once the market has closed). R8 established `endDate = target_date 12:00:00Z`
    across 8 557/8 557 events, so the date part is the anchor.

    Returns one row per tradable outcome token."""
    rows = db.query(
        con,
        """
        SELECT m.market_id, m.event_id, m.station, m.station_identifier, m.unit,
               m.rounding_rule,
               o.token_id, o.outcome_label, o.band_label,
               json_extract_string(m.source_timestamps, '$.endDate') AS end_date_raw
        FROM markets m
        JOIN outcomes o
          ON o.market_id = m.market_id
         AND o.dataset_version = m.dataset_version
         AND o.record_version = m.record_version
        WHERE m.dataset_version = ?
          AND try_cast(
                json_extract_string(m.source_timestamps, '$.endDate') AS TIMESTAMPTZ
              ) IS NOT NULL
          AND CAST(
                try_cast(
                  json_extract_string(m.source_timestamps, '$.endDate') AS TIMESTAMPTZ
                ) AT TIME ZONE 'UTC' AS DATE
              ) = ?
        ORDER BY m.market_id, o.token_id
        """,
        [dataset_version, target_date],
    )
    return rows


def stage_collect(cy: Cycle, con, *, dataset_version: str, session_id: str,
                  universe: list[dict], session, chunk_size: int) -> dict:
    """Snapshot the order book of every token in the universe.

    THE STAGE THAT CANNOT BE DEFERRED: Polymarket publishes no historical L2 book,
    so a day not collected is a day gone. It runs even when every later stage is
    skipped."""
    tokens = [str(r["token_id"]) for r in universe if r.get("token_id")]
    market_by_token = {str(r["token_id"]): r["market_id"] for r in universe
                       if r.get("token_id")}
    if not tokens:
        cy.stage("collect:books", SKIPPED, reason="empty_universe")
        return {}
    out = collector.collect_books(
        con, tokens, dataset_version=dataset_version,
        collector_session_id=session_id, session=session, chunk_size=chunk_size,
        market_id_by_token=market_by_token,
    )
    # HOW LONG THE PASS TOOK TO REACH THE VENUE, measured and not assumed.
    # Measured on 2026-09-10 it was NOT constant: 8.45 → 8.97 → 10.07 → 11.60
    # minutes across the day's four collect slots, monotone, while token counts
    # stayed flat at 846/854/880/868 — so it is not "more work". Four points are
    # not a trend; they are a reason to instrument rather than to conclude.
    #
    # It matters because R24 §6bis.4septies's warm-up premise depends on no pass
    # landing between a cycle's cutoff and its anchor, and this lag MOVES that
    # window: a growing lag shifts it earlier, which LOWERS the delay a late slot
    # would need to break the premise. Session B's point; the value costs nothing
    # because the collector already knows the instant it fetched.
    extra = {}
    if out.get("collected_at") is not None:
        extra = {
            "collected_at": _iso(out["collected_at"]),
            "lag_from_cycle_start_min": round(
                (out["collected_at"] - cy.started_at).total_seconds() / 60, 2),
        }
    cy.stage("collect:books", STOPPED if out["stopped"] else OK,
             tokens=out["tokens_requested"], pending=out["tokens_pending"],
             rows=out["rows_written"], prices=out["prices_written"],
             one_sided=out["prices_skipped_one_sided"],
             requests=out["requests"], error=out["error"], **extra)
    return out


def stage_forecasts(cy: Cycle, con, *, dataset_version: str, target_date: date,
                    universe: list[dict], model: str, lead_hours: float,
                    prediction_time: datetime, artifact_path: str,
                    max_artifact_age_h: float | None = None, session=None) -> dict:
    """Fetch the issued forecast for each station and attach M2's error quantiles.

    Two halves, and they answer different questions:

      1. THE FORECAST — `weather.ingest_run` for the run that was already PUBLISHED
         at `prediction_time` (`m2.pick_run`), never the newest run in existence.
         Publication latency is real (L_MAX 4.76 h for icon_seamless) and picking a
         run by issue time alone would use a forecast that did not exist yet.

      2. THE UNCERTAINTY — a VERSIONED ARTIFACT (R30), not a refit. Applied as
         `forecast_pXX = f + percentile_XX(e)`.

    WHY THE UNCERTAINTY IS READ AND NOT FITTED. The cycle has nothing to fit on.
    M2 trains on the BACKFILL (`m2.DATASET_VERSION`); the cycle runs as
    `ds_paper_v1`, rebuilt in Actions from the prospective shards, holding no
    realized observation at all. Refitting here returned `INSUFFICIENT` on every
    live cycle: forecast rows written, no distribution, `build_feature` returning
    None, zero signals. So the fit happens out of band
    (`scripts/fit_quantile_artifact.py`) and the cycle reads its result.

    That is safe for the reason session B gave: an artifact fitted at `t0 < t`
    uses a SUBSET of what it was entitled to, and using less information than
    permitted cannot create lookahead. The mirror case is NOT safe, and
    `quantile_artifact` refuses it — `fit_instant > prediction_time` means the
    fit saw labels the decision could not. It never happens forward in time; it
    happens the first time a replay meets a newer artifact.

    STALENESS IS A REFUSAL, NOT A WARNING (B's condition). Past the artifact's
    declared `max_age_hours` the stage STOPS with the reason, writes no
    quantiles, and the cycle produces no signal. An old artifact used in silence
    does not break: it produces a plausible number, which is worse.

    Quantiles are written in CELSIUS. `weather_forecasts` is model space, not
    market space; the conversion to the market's contractual unit happens later in
    `build_feature` (B-7), and doing it here would convert twice.

    QUOTA: the user pays for no Open-Meteo key (A-29.1), so this must stay inside
    the free tier. One request per station per cycle, ~51 stations x 2 cycles/day.
    A 429 stops the stage and is reported; it is never retried through."""
    from weather_agent import error_model as em, m2, quantile_artifact as qa
    from weather_agent import stations, weather

    # The ICAO, not the station NAME. `markets.station` is prose ("London City
    # Airport"); `stations.timezone_of` and `weather.ingest_run` both key on the
    # identifier, and passing the name silently resolved nothing.
    stns = sorted({r["station_identifier"] for r in universe
                   if r.get("station_identifier")})
    if not stns:
        cy.stage("forecasts", SKIPPED, reason="no_stations_in_universe")
        return {"written": 0, "quantiles": 0}

    issue_time = m2.pick_run(prediction_time, model)
    if issue_time is None:
        cy.stage("forecasts", SKIPPED, reason="no_run_published_at_prediction_time",
                 prediction_time=_iso(prediction_time))
        return {"written": 0, "quantiles": 0}

    # ---- 0. the artifact, BEFORE spending a single request.
    #
    # The stratum is keyed by an INTEGER lead (`training_pairs` compares
    # `p.lead_h == lead_h`, and the artifact is keyed the same way). `int()` on a
    # non-integral lead would not raise: it would truncate into a NEIGHBOURING
    # stratum and return quantiles for a horizon nobody asked about.
    if float(lead_hours) != int(lead_hours):
        cy.stage("forecasts", STOPPED, reason="non_integral_lead_hours",
                 lead_hours=lead_hours, written=0)
        return {"written": 0, "quantiles": 0, "stopped": True}
    lead_h = int(lead_hours)

    # Checked FIRST, not after the fetch. Without quantiles the cycle produces no
    # signal at all, so ingesting 50 stations before discovering the artifact is
    # stale spends 50 Open-Meteo requests on forecasts nothing can use. The user
    # pays for no key (A-29.1): quota not spent is the point, and a refusal that
    # arrives after the bill is a refusal that arrived late.
    try:
        art = qa.load(artifact_path)
        q = art.quantiles(lead_h, prediction_time, model=model,
                          prereg_sha256=m2.PREREG_SHA_V2,
                          max_age_hours=max_artifact_age_h)
    except qa.ArtifactUnusable as exc:
        # Every reason comes from the closed enum, so the shard record carries a
        # label a later reader can count, not a sentence someone wrote once.
        cy.stage("forecasts", STOPPED, reason=f"quantile_artifact:{exc.reason}",
                 detail=exc.detail, artifact=artifact_path,
                 written=0, quantiles=0, requests_saved=len(stns))
        return {"written": 0, "quantiles": 0, "stopped": True,
                "artifact_refusal": exc.reason}
    prov = art.provenance(lead_h, prediction_time)

    # ---- 1. the forecast
    written = 0
    fetch_errors: dict[str, int] = {}
    for icao in stns:
        try:
            tz = stations.timezone_of(icao)
        except Exception:
            fetch_errors["unknown_station"] = fetch_errors.get("unknown_station", 0) + 1
            continue
        try:
            weather.ingest_run(con, icao, target_date, tz, issue_time, dataset_version,
                               model=model)
            written += 1
        except Exception as exc:
            key = "rate_limited" if "429" in str(exc) else type(exc).__name__
            fetch_errors[key] = fetch_errors.get(key, 0) + 1
            if key == "rate_limited":
                cy.stage("forecasts", STOPPED, reason="http_429_rate_limited",
                         written=written, stations=len(stns))
                return {"written": written, "quantiles": 0, "stopped": True}

    if not written:
        cy.stage("forecasts", SKIPPED, reason="no_forecast_ingested",
                 stations=len(stns), errors=json.dumps(fetch_errors))
        return {"written": 0, "quantiles": 0}

    # ---- 2. the uncertainty, applied
    # `record_version` is PART OF THE PRIMARY KEY of weather_forecasts and was
    # named by NEITHER the read nor the write. With one version per key — all
    # `ingest_run` writes today — the two agree; with two, the SELECT returns both
    # rows and each UPDATE, unscoped, writes to BOTH, so the last forecast_tmax
    # processed would set the quantiles of every version of that key. That is the
    # defect class of "the price read returned another token's price", latent
    # rather than live, and the fix is to name the column.
    rows = db.query(
        con,
        "SELECT station, issue_time, target_date, record_version, forecast_tmax "
        "FROM weather_forecasts "
        "WHERE dataset_version = ? AND model = ? AND target_date = ? "
        "AND issue_time = ? AND forecast_tmax IS NOT NULL",
        [dataset_version, model, target_date, issue_time],
    )
    n_q = 0
    for r in rows:
        qs = em.forecast_quantiles_c(float(r["forecast_tmax"]), q)
        con.execute(
            "UPDATE weather_forecasts SET forecast_p10 = ?, forecast_p25 = ?, "
            "forecast_p50 = ?, forecast_p75 = ?, forecast_p90 = ? "
            "WHERE station = ? AND model = ? AND issue_time = ? AND target_date = ? "
            "AND dataset_version = ? AND record_version = ?",
            [qs[10], qs[25], qs[50], qs[75], qs[90],
             r["station"], model, r["issue_time"], r["target_date"], dataset_version,
             r["record_version"]],
        )
        n_q += 1

    cy.stage("forecasts", OK, stations=len(stns), written=written, quantiles=n_q,
             issue_time=_iso(issue_time), lead_h=lead_h,
             quantile_scope=q.scope, quantile_n=q.n,
             artifact_id=art.artifact_id[:12],
             artifact_age_h=round(art.age_at(prediction_time).total_seconds() / 3600, 2),
             training_dsv=art.dataset_version,
             errors=json.dumps(fetch_errors) if fetch_errors else None)
    return {"written": written, "quantiles": n_q, "scope": q.scope,
            "provenance": prov}


def stage_host_events(cy: Cycle, *, queue_path: str | None, root: str,
                      session_id: str) -> dict:
    """Drain the host's queued events into a shard so they reach the series.

    WHY A QUEUE AND NOT A DIRECT WRITE. `launcher.sh` records an event when it
    gives up waiting for the run lock. It cannot push that itself: committing in
    the state checkout while the run holding the lock is writing there is the
    exact race the lock exists to prevent. So the launcher appends a line and the
    next cycle that DOES get the lock carries it to GitHub.

    WHY IT MATTERS AT ALL. A skip that lives only in `/opt/pmw/log/collect.log`
    leaves precisely the trace of a host that never fired: no shard, a hole in
    "delivered", and nothing to tell the two apart — which is the distinction
    §4quater of R24 rests on when it attributes `NO EVALUABLE` to the host. It
    also breaks "GitHub stays the record; nothing lives only on the box".

    THE RENAME IS THE POINT. The queue is drained by `os.replace` onto a
    sidecar, which is atomic: a launcher appending at that instant creates a
    fresh queue and loses nothing, where read-then-truncate would drop whatever
    landed in between. The sidecar is removed only after the shard is written, so
    a crash mid-drain re-drains rather than swallowing the events.
    """
    if not queue_path:
        cy.stage("host_events", SKIPPED, reason="no_queue_configured")
        return {"rows": 0}
    q = Path(queue_path)
    sidecar = q.with_suffix(q.suffix + ".draining")
    # THE RENAME IS TAKEN UNDER THE SAME LOCK THE APPENDER USES. The appending
    # launcher does not hold the run lock — it is the one that just failed to get
    # it — so the two really can meet here: a `write()` that lands in the renamed
    # or already-unlinked inode loses the event. Microseconds wide and one event
    # deep, and the event lost is exactly the one that EXPLAINS a gap, which is
    # the only thing this queue is for. Session B sized it; it is closed rather
    # than written down.
    # BOUNDED, AND NEVER BLOCKING. The appender waits `-w 30`; this side used a
    # plain LOCK_EX with no limit — and it runs INSIDE the cycle, holding the run
    # lock the whole time. So any pathological hold on the queue lock became a
    # hung cycle, then every later slot skipping, then a schedule stopped in
    # silence: the exact failure this PR exists to remove, re-entering through
    # the door the PR itself added. Session B's asymmetry, and it is my own rule
    # applied where I had not applied it.
    #
    # On exhaustion the drain is SKIPPED, not failed: the queue is durable and
    # the next cycle drains it, so nothing is lost and the cycle cannot hang.
    lock_path = Path(str(q) + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    budget = float(os.environ.get("PMW_QUEUE_LOCK_WAIT", "30"))
    with open(lock_path, "a+") as lock_fh:
        deadline, held = time.monotonic() + budget, False
        while True:
            try:
                fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                held = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    break
                time.sleep(0.05)
        if not held:
            cy.stage("host_events", SKIPPED, reason="queue_locked_elsewhere",
                     waited_s=budget)
            return {"rows": 0, "skipped": "queue_locked_elsewhere"}
        try:
            if q.exists() and q.stat().st_size:
                if sidecar.exists():   # a previous drain died before unlinking
                    with open(sidecar, "a", encoding="utf-8") as dst, \
                         open(q, "r", encoding="utf-8") as src:
                        dst.write(src.read())
                    q.unlink()
                else:
                    os.replace(q, sidecar)
        finally:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)
    if not sidecar.exists() or not sidecar.stat().st_size:
        cy.stage("host_events", SKIPPED, reason="queue_empty")
        return {"rows": 0}

    rows, malformed = [], 0
    for line in sidecar.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1           # counted, never silently dropped
            continue
        row.setdefault("drained_by_session", session_id)
        rows.append(row)
    if not rows:
        sidecar.unlink()
        cy.stage("host_events", SKIPPED, reason="queue_had_no_valid_rows",
                 malformed=malformed)
        return {"rows": 0, "malformed": malformed}

    written = store.write_shard(rows, table="host_events", run_id=session_id,
                                root=root)
    sidecar.unlink()                 # only after the shard exists
    cy.stage("host_events", OK, rows=len(rows), malformed=malformed,
             path=written["path"],
             events=",".join(sorted({str(r.get("event")) for r in rows})))
    return {"rows": len(rows), "malformed": malformed}


def stage_venue_coverage(cy: Cycle, con, *, dataset_version: str,
                         universe: list[dict], prediction_time: datetime,
                         t_asof: datetime, root: str, session_id: str,
                         target_date: date, lead_h: float,
                         row_kind: str = "own") -> dict:
    """RUNG 1 of the funnel, measured on EVERY cycle including collect-only.

    WHY IT LIVES HERE AND NOT IN `stage_signals`. The number the run needs before
    `PAPER_TAU` can be set is how many events have ALL their bands priced — the
    venue property §0 measured once as 86 % exclusion, and which two sessions
    then spent half an hour comparing against a retrospective substrate whose
    completeness was an artefact of which events the backfill chose to complete.
    Getting it live needs several days of it.

    But `stage_signals` never runs in Actions: every scheduled cycle is
    `--collect-only` because `vars.PAPER_TAU` is unset, which is the correct
    fail-closed and also means the instrumentation added to that stage would have
    recorded NOTHING. Measured on the real store: `signals` 0 shards.

    Rung 1 does not need tau, a forecast, a model or a decision — only prices. So
    it is computed here, on every cycle, at no cost in quota and without writing a
    single trade to the run's ledger.

    AND IT IS WRITTEN TO THE SHARD STORE, not only to the summary. The first
    version reported it in `cy.stage` and stopped there — which lands in the
    cycle summary, which the workflow uploads as a per-run ARTIFACT that GitHub
    keeps for 90 days and that nobody aggregates. Only `paper_state/` is committed
    to the data branch. So "the multi-day series accumulates for free" was FALSE
    AS BUILT: the numbers would have existed in 42 separate artifacts and in no
    series at all. It goes to a shard, like `cycle_params`, and the workflow's
    `git add -A paper_state` carries it.

    COMPLETE means every band of the event has a price for its Yes token at or
    before `prediction_time`. Strategy A is fail-closed per event: one unpriced
    band excludes the whole event, so the count IS the ceiling on what could ever
    be decided.
    """
    # THE STAGE NAME CARRIES THE ROW KIND. Both rows were recorded under
    # `venue_coverage`, so a cycle emitting one per lead produced two identical
    # stage names and the summary could not tell them apart. The live 06:07Z run
    # only showed `venue_coverage:other_lead` because `_non_fatal` caught an
    # error and used its own label; had it succeeded it would have been a second
    # anonymous OK. Anything counting stages from the summary — which is what
    # §4quater does — would have counted a measurement twice.
    stage_name = ("venue_coverage" if row_kind == "own"
                  else f"venue_coverage:{row_kind}")
    events = sorted({r["event_id"] for r in universe if r.get("event_id")})
    if not events:
        cy.stage(stage_name, SKIPPED, reason="empty_universe")
        return {"events": 0}

    rows = db.query(
        con,
        "SELECT m.event_id, o.token_id, "
        "       (SELECT count(*) FROM price_history p "
        "         WHERE p.token_id = o.token_id AND p.dataset_version = ? "
        "           AND p.observation_time <= ?) AS n_prices "
        "FROM markets m JOIN outcomes o "
        "  ON o.market_id = m.market_id AND o.dataset_version = m.dataset_version "
        # `record_version` IS PART OF THE KEY, and `select_universe` twenty lines
        # up already joins on it. Two queries in the same module disagreeing about
        # whether a key column matters is the exact shape of the `fit_m2` gap and
        # of the read that returned another token's price. It cannot fire today —
        # `discovery.ingest_event` writes `record_version: 1` literally in all
        # five places and `next_record_version` is defined and called from
        # nowhere — and `stage_guard_dataset_version` does not watch these two
        # tables either. Which is precisely why it would fan out silently the day
        # someone starts using the helper that exists for it. Found by session B.
        "  AND o.record_version = m.record_version "
        "WHERE m.dataset_version = ? AND o.outcome_label = 'Yes'",
        [dataset_version, prediction_time, dataset_version],
    )
    per_event: dict[str, list[int]] = {}
    for r in rows:
        if r["event_id"] in set(events):
            per_event.setdefault(r["event_id"], []).append(int(r["n_prices"] or 0))

    complete = sum(1 for v in per_event.values() if v and all(n > 0 for n in v))
    bands = sum(len(v) for v in per_event.values())
    priced = sum(sum(1 for n in v if n > 0) for v in per_event.values())
    out = {
        "events": len(per_event),
        "events_complete": complete,
        "bands": bands,
        "bands_priced": priced,
        # The denominators, named, because a rate without one is not a
        # measurement (A-78).
        "complete_rate_over_events": round(complete / len(per_event), 4) if per_event else None,
        "priced_rate_over_bands": round(priced / bands, 4) if bands else None,
    }
    row = {
        "session_id": session_id,
        "dataset_version": dataset_version,
        "target_date": str(target_date),
        "prediction_time": _iso(prediction_time),
        "recorded_at": _iso(_utcnow()),
        # The event of the run that produced it: a series that cannot tell a
        # scheduled cycle from a hand-dispatched one measures the operator's
        # attention, not the host (A-72).
        "github_event": os.environ.get("GITHUB_EVENT_NAME"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        # IS THIS ROW'S CUTOFF FINAL? Derived from `prediction_time`, which is
        # the SAME clock read that produced the count — not a second call to
        # `_utcnow()` here. Session B found the bug that made this necessary:
        # the cycle fires ~20 min early ON PURPOSE, so a lead-9 cycle can start
        # at 02:40 (cutoff 02:40, partial), take 25 minutes, and write its row
        # at 03:05, by which time a fresh clock read is past `t_asof` and would
        # stamp a PARTIAL count as final. `prediction_time = min(now, t_asof)`
        # makes `prediction_time >= t_asof` exactly equivalent to `now >= t_asof`
        # at the instant that mattered.
        #
        # AND IT MEANS THE CUTOFF IS FINAL, NOT THE COUNT. A row whose cutoff is
        # final can still be a PREFIX of a later one for the same target: today
        # because several cycles run after `t_asof` and each writes its own row,
        # and — once the price-history backfill lands — because a row with
        # `observation_time <= t_asof` can be INGESTED afterwards. Measured on
        # the live store, that second route is not open yet: every price row is
        # ingested within 27 s of its observation instant (`clob_book_midpoint`,
        # p95 = 22 s), so a late slot writes a late observation and loses the
        # measurement rather than back-filling it. Either way the consumer rule
        # is the same and is written down in the README: take the LAST final row
        # per (target_date, lead), never the mean of the final rows.
        "t_asof": _iso(t_asof),
        "is_final": prediction_time >= t_asof,
        # THE LEAD, STATED. The consumer rule is "the last final row per
        # (target_date, lead)" and the lead was not in the row: it was derivable
        # from `target_date` and `t_asof`, which is the derivable-but-fragile
        # shape this project spent a night removing everywhere else.
        "lead_h": float(lead_h),
        # WHAT KIND OF ROW THIS IS. "own" = the (lead, target) this cycle is
        # deciding or collecting for; "other_lead" = the complementary one,
        # measured because coverage is a property of the venue and does not
        # depend on which lead the cycle happens to carry. Explicit so nobody
        # counts coverage rows as decision cycles — that would be one more wrong
        # denominator, and this project has had four.
        "row_kind": row_kind,
        **out,
    }
    written = store.write_shard([row], table="venue_coverage", run_id=session_id,
                                root=root)
    cy.stage(stage_name, OK, path=written["path"], **out)
    return out


def stage_signals(cy: Cycle, con, *, dataset_version: str, target_date: date,
                  universe: list[dict], model: str, tau: float,
                  weather_sum_tolerance: float, market_sum_min: float,
                  market_sum_max: float, prediction_time: datetime) -> dict:
    """Generate Strategy A signals for each event in the universe.

    Skipped — loudly, with the count — when the forecast substrate for the date is
    absent. Strategy A is fail-closed by design: without quantiles it would exclude
    every event, and a log full of exclusions would look like a strategy decision
    rather than a missing input."""
    from weather_agent.strategy import strategy_a

    have = db.query(
        con,
        "SELECT count(*) AS n FROM weather_forecasts "
        "WHERE target_date = ? AND model = ? AND forecast_p50 IS NOT NULL",
        [target_date, model],
    )
    n_forecasts = int(have[0]["n"]) if have else 0
    if n_forecasts == 0:
        cy.stage("signals", SKIPPED,
                 reason="no_quantile_forecasts_for_target_date",
                 target_date=str(target_date), model=model)
        return {"eligible": 0, "excluded": 0, "signals": 0}

    # The DECISION universe is narrower than the COLLECTION universe, and
    # deliberately so: we collect books for everything discovered (book history is
    # not recoverable), but a market may only be DECIDED on if we could have known
    # it existed by `prediction_time`. `markets.available_at` is stamped at the
    # discovery request (R26). Discovery runs before collection, so on a punctual
    # cycle every market qualifies; on a cycle that ran past T_asof the clamp puts
    # `prediction_time` before the discovery instant and the newly-found markets
    # are correctly excluded.
    admissible = {
        r["event_id"] for r in db.query(
            con,
            "SELECT DISTINCT event_id FROM markets "
            "WHERE dataset_version = ? AND available_at IS NOT NULL "
            "AND available_at <= ?",
            [dataset_version, prediction_time],
        ) if r.get("event_id")
    }
    all_events = {r["event_id"] for r in universe if r.get("event_id")}
    dropped = sorted(all_events - admissible)
    if dropped:
        cy.stage("signals:asof_universe", OK, dropped=len(dropped),
                 kept=len(all_events & admissible),
                 reason="available_at_after_prediction_time")
    events = sorted(all_events & admissible)
    totals = {"eligible": 0, "excluded": 0, "signals": 0}
    for event_id in events:
        try:
            out = strategy_a.generate_event_signals(
                con, event_id=event_id, prediction_time=prediction_time,
                model=model, target_date=target_date,
                dataset_version=dataset_version, tau=tau,
                weather_sum_tolerance=weather_sum_tolerance,
                market_sum_min=market_sum_min, market_sum_max=market_sum_max,
            )
        except Exception as exc:
            cy.stage(f"signals:{event_id}", STOPPED, error=repr(exc))
            continue
        totals["eligible"] += 1 if out.get("eligible") else 0
        totals["excluded"] += 0 if out.get("eligible") else 1
        totals["signals"] += out.get("signals_written", 0)

    # THE FUNNEL, RUNG BY RUNG, WITH ITS DENOMINATORS NAMED.
    #
    # Half an hour of cross-session argument went into discovering, TWICE, that
    # two numbers called "eligible" had different denominators: one session's
    # 14 % was structural completeness (7 of 49 events pass the band/price gates)
    # and the other's 80.2 % was actionable-among-already-complete — and the
    # second turned out to be the PRODUCT of two rungs that happened to be almost
    # equal (0.895 x 0.896), which is exactly what makes two denominators look
    # like one. A rate is not a measurement until its denominator is written down
    # next to it, so the cycle writes them instead of leaving them to be inferred:
    #
    #   rung 1  structural   eligible / discovered      the venue property
    #   rung 2  actionable   with a BUY|FADE / eligible what the rule adds
    #
    # Both, plus the tau of EACH gate, because they are different quantities over
    # different operands (A-32's lesson) and a reader comparing runs needs to know
    # which threshold produced which count.
    actionable_events = {
        r["event_id"] for r in db.query(
            con,
            "SELECT DISTINCT m.event_id FROM signals s JOIN markets m "
            "  ON m.market_id = s.market_id AND m.dataset_version = s.dataset_version "
            "WHERE s.dataset_version = ? AND s.\"timestamp\" = ? "
            "  AND s.signal IN ('BUY','FADE')",
            [dataset_version, prediction_time],
        ) if r.get("event_id")
    }
    # AND THE DENOMINATOR OF RUNG 1 IS THE ADMISSIBLE SET, NOT EVERYTHING
    # DISCOVERED. `eligible` is counted over the events that survived the as-of
    # filter, so dividing it by everything discovered would mix two populations —
    # the very defect this block exists to prevent, committed while writing it.
    # Both counts are published so the as-of drop is visible and never folded in.
    totals["events_discovered"] = len(all_events)
    totals["events_admissible"] = len(events)
    totals["events_actionable"] = len(actionable_events)
    totals["rung1_structural_rate"] = (
        round(totals["eligible"] / len(events), 4) if events else None)
    totals["rung2_actionable_rate"] = (
        round(len(actionable_events) / totals["eligible"], 4)
        if totals["eligible"] else None)
    totals["tau_signal"] = tau
    cy.stage("signals", OK, events=len(events), **totals)
    return totals


def stage_paper(cy: Cycle, con, *, dataset_version: str, session_id: str,
                params: paper.PaperParams, prediction_time: datetime,
                target_date: date) -> dict:
    """Turn actionable signals into simulated fills against the observed book.

    `target_date` is the CALLER'S parameter (2D §C) and is stored on every
    position, because nothing downstream may rebuild it from `endDate` — which is
    re-discovered every cycle and can move under an open trade."""
    signals = db.query(
        con,
        "SELECT market_id, token_id, signal, fair_value, timestamp "
        "FROM signals WHERE dataset_version = ? AND timestamp = ? "
        "AND signal IN ('BUY','FADE') ORDER BY market_id, token_id",
        [dataset_version, prediction_time],
    )
    if not signals:
        cy.stage("paper", SKIPPED, reason="no_actionable_signals")
        return {"opened": 0, "rejected": 0}

    opened = rejected = 0
    reasons: dict[str, int] = {}
    bankroll = params.bankroll
    for sig in signals:
        token_id = str(sig["token_id"])
        # A FADE is executed as a taker BUY of the complementary token, against
        # that token's OWN book (see paper.py) — never as 1 - the Yes ask.
        exec_token = token_id
        if sig["signal"] == "FADE":
            comp = db.query(
                con,
                "SELECT token_id FROM outcomes WHERE market_id = ? "
                "AND dataset_version = ? AND token_id <> ? LIMIT 1",
                [sig["market_id"], dataset_version, token_id],
            )
            if not comp:
                rejected += 1
                reasons["no_complement_token"] = reasons.get("no_complement_token", 0) + 1
                continue
            exec_token = str(comp[0]["token_id"])

        # ONE book predicate, shared with the replay (paper.select_book). Note it
        # is as-of `prediction_time`, NOT "this cycle's collector session": a
        # cycle that ran past T_asof has books newer than the as-of it claims, and
        # filling against those would violate C2 while the summary still reported
        # the nominal lead.
        snap = paper.select_book(con, token_id=exec_token,
                                 dataset_version=dataset_version,
                                 asof=prediction_time)
        if snap is None:
            rejected += 1
            reasons["no_book_asof"] = reasons.get("no_book_asof", 0) + 1
            continue

        # `market_fee_schedule` is keyed by fee_regime, NOT by market_id (its PK is
        # (fee_regime, dataset_version, record_version)) — a regime is shared by
        # thousands of markets. The link is `markets.fee_regime`, so the lookup has
        # to go through it. Querying the schedule by market_id raises a binder
        # error, which would have crashed the first cycle that produced a signal.
        fee_rows = db.query(
            con,
            "SELECT f.fee_regime, f.taker_fee, f.maker_rebate, f.fee_status, "
            "       f.raw_fee_fields "
            "FROM markets m JOIN market_fee_schedule f "
            "  ON f.fee_regime = m.fee_regime AND f.dataset_version = m.dataset_version "
            "WHERE m.market_id = ? AND m.dataset_version = ? LIMIT 1",
            [sig["market_id"], dataset_version],
        )
        fee_row = fee_rows[0] if fee_rows else {}
        if isinstance(fee_row.get("raw_fee_fields"), str):
            try:
                fee_row["raw_fee_fields"] = json.loads(fee_row["raw_fee_fields"])
            except ValueError:
                fee_row["raw_fee_fields"] = {}
        fee = paper.resolve_fee_params(fee_row)

        decision = paper.decide_and_fill(
            signal=sig["signal"], p_model=float(sig["fair_value"]),
            book_snapshot=snap, fee=fee, params=params, bankroll=bankroll,
        )
        if not decision["open"]:
            rejected += 1
            reason = decision["reason"] or "unknown"
            reasons[reason] = reasons.get(reason, 0) + 1
            continue
        fill = decision["fill"]
        bankroll -= fill.outlay
        paper.record_paper_trade(
            con, backtest_id=session_id, market_id=sig["market_id"],
            token_id=exec_token, entry_time=prediction_time, fill=fill,
            bankroll_after=bankroll, dataset_version=dataset_version,
            # The caller's parameter, carried WITH the position. Everything
            # downstream reads it from here instead of rebuilding it from
            # `endDate`, which 2D §C prohibits — and which `markets` can revise
            # under an open position.
            target_date=target_date,
        )
        opened += 1
    cy.stage("paper", OK, opened=opened, rejected=rejected,
             bankroll_after=round(bankroll, 4), reasons=json.dumps(reasons))
    return {"opened": opened, "rejected": rejected, "reasons": reasons}


#: Columns `stage_settle` needs that only exist once session B's migration 4 has
#: merged. Named individually so a SKIP says WHICH one is missing rather than
#: leaving the next reader to guess.
_SETTLE_REQUIRED = {
    "weather_observations": ("observed_value", "observed_unit", "series"),
    # BOTH halves of the terna. `contract_source` alone was listed, and the other
    # half was silently supplied as the human measurement_rule string, which the
    # frozen core rejects as "terna outside the 11-class partition" — every
    # market, always.
    "markets": ("contract_source", "measurement_rule_code"),
}


def settle_substrate_missing(con) -> list[str]:
    """What `stage_settle` still lacks. Empty list == ready to settle."""
    missing = []
    for table, cols in _SETTLE_REQUIRED.items():
        have = set(db.column_names(con, table))
        missing += [f"{table}.{c}" for c in cols if c not in have]
    try:
        from weather_agent import stations  # noqa: F401
    except ImportError:
        missing.append("weather_agent.stations (station timezone registry)")
    return missing


def _station_tz(icao: str | None) -> str | None:
    """The station's IANA timezone, from the registry that owns it.

    Calls `stations.timezone_of` BY NAME. An earlier version looped over three
    plausible names — `timezone_for`, `tz_for`, `get_timezone` — and the real one
    is none of them, so it silently returned None on the merged tree and every
    LOCAL_CIVIL_DAY settlement was refused for want of a timezone. Guessing an API
    instead of reading it is the same failure as assuming a literal instead of
    verifying it (A-42); if the name ever changes, this raises rather than
    degrading to None."""
    if not icao:
        return None
    try:
        from weather_agent import stations
    except ImportError:
        return None
    try:
        return stations.timezone_of(icao)
    except (KeyError, ValueError):
        return None      # unknown station: refuse later, never invent a zone


#: THE TWO MODULES NAME THE SAME SERIES DIFFERENTLY, and nothing connected them.
#:
#: `settlement` is FROZEN (SETTLEMENT_OPERATOR_CORE.v3, sha a6d92667…) and its
#: operators require `metar_body_c` / `metar_tgroup_tmpf`. `observations.to_row`
#: — the only thing that has ever written `weather_observations`, prospectively or
#: in the backfill — writes `IEM_ASOS_METAR_1C`, `IEM_ASOS_TMPF_1F` and
#: `IEM_ASOS_TMPF_0.1F`. So every settlement refused with `series_mismatch`.
#: Verified live on a real position: the terna resolved, the operator was found,
#: and the observation was thrown out for carrying the wrong series name.
#:
#: The ONLY place `metar_body_c` had ever appeared outside the frozen core was a
#: FIXTURE in this repository's own tests. Settlement had therefore never been
#: exercised against a row any ingester produced, and R24's P4 was closed against
#: that fixture.
#:
#: The core cannot be edited — it is frozen by sha — so the correspondence is
#: declared HERE, at the boundary, and only where it is certain:
#:
#:   IEM_ASOS_METAR_1C -> metar_body_c
#:       Both name the whole-degree Celsius value of the METAR body, and
#:       `observations.station_series` assigns it to exactly the stations that are
#:       not on the Fahrenheit list — which is the population of the Celsius
#:       operators. Certain.
#:
#:   IEM_ASOS_TMPF_1F -> metar_tgroup_tmpf
#:       Settled by the audit, not by elimination (B, from E2_RESULTS.json). Of
#:       the four candidate columns over the 14 Fahrenheit rows:
#:           H_LOCAL_tmpf  inside the winning band 14/14, whole degrees 14/14
#:           H_LOCAL_tg    inside the winning band  0/14  (it is tenths of C)
#:           H_LOCAL_body  inside the winning band  0/14
#:           H_LOCAL_tmpc  inside the winning band  0/14
#:       The audit computed the T-group and `tmpf` in SEPARATE columns and settled
#:       against `tmpf`. The core's own v3 §2.1 says the same thing about itself:
#:       "an IEM-derived product: tmpf = round(F(T-group in tenths)), 1 F grid; NOT
#:       a rule of the contractual source". The NAME says T-group; the THING is
#:       tmpf rounded to 1 F.
#:
#: `IEM_ASOS_TMPF_0.1F` stays unmapped, and the reason is no longer uncertainty.
#: Its only station is KBKF, whose audited row carries P_NOAA_HourlyData — stratum
#: 9 — which the frozen core already fails closed on `series_filter_unverified`
#: ("0/4 rows separate H_hourly from H_series"). So KBKF is excluded UPSTREAM by
#: its own stratum, and no market is lost by leaving this series undeclared.
#:
#: Two facts about KBKF that look contradictory and are not, written down so
#: nobody "fixes" one into the other: `IEM_ASOS_TMPF_0.1F` describes the grid the
#: STATION REPORTS ON (A-42, still correct), while the `tmpf` its stratum would
#: settle against is whole-degree — the audited KBKF row carries tmpf = 91.0, a
#: whole degree, with a 90-91 F band and `whole degree` rounding. Collapsing them
#: in either direction is the error.
SERIES_CORRESPONDENCE = {
    "IEM_ASOS_METAR_1C": settlement.SERIES_METAR_C,
    "IEM_ASOS_TMPF_1F": settlement.SERIES_METAR_F,
}


def to_core_series(series: str | None) -> str | None:
    """The frozen core's name for an ingested series, or None when undeclared."""
    return SERIES_CORRESPONDENCE.get(series or "")


#: How long after the station-local day ends before its high is read. NOT the 24 h
#: of `error_model.ASSUMED_LABEL_LAG` — that is M2's TRAINING assumption about when
#: a label could first be known, and using it here would delay every settlement by
#: a day for no reason. This is the operational margin for the last METAR of the
#: day to reach IEM, and it is deliberately small: routine METARs are hourly, so
#: two hours covers the last observation plus a late feed without pushing the
#: settlement into the next cycle.
LABEL_PUBLICATION_MARGIN = timedelta(hours=2)


def stage_observations(cy: Cycle, con, *, dataset_version: str, now: datetime) -> dict:
    """Ingest the realized daily high for the station-days open positions wait on.

    WITHOUT THIS THE LEDGER NEVER CLOSES. `stage_settle` reads
    `weather_observations`, and in paper mode NOTHING wrote it: the table is
    populated by the historical backfill under a different `dataset_version`, and
    the run's own target dates are in the future when the position is opened. So
    every position would sit open for the whole run, refused for
    `context_out_of_snapshot`, and the ledger would report a PnL of zero not
    because the strategy earned nothing but because nothing ever resolved.

    Same shape as `stage_forecasts` before it was wired: the module existed
    (`observations.ingest_daily_high`), the cycle never called it.

    WHAT IS FETCHED, and no more. One request per (station, local day) that:
      * some OPEN position depends on,
      * whose station-local calendar day has ALREADY ENDED at `now` — the METAR
        high of a day still in progress is not that day's high, and ingesting it
        would write a label that is wrong and then never revisit it, and
      * is not already in the table for this dataset_version.
    Everything else is counted as `pending` and reported, not fetched.

    A 429 stops the stage and is never retried through (D0/D21).

    The row carries `available_at` = the download instant (D17): the run
    accumulates a genuine as-of history of when each label could first be known,
    which is exactly what the retrospective backfill cannot prove."""
    from weather_agent import observations as obs, weather

    # `t.target_date`, NOT `endDate`. The day a position was opened for is the
    # caller's parameter (2D §C) and it travels WITH the trade; rebuilding it from
    # `markets.source_timestamps` would read the source §C prohibits, and
    # `markets` is re-discovered every cycle — a revised `endDate` under an open
    # position would fetch the label of a different day, write it, and never look
    # again because the row then exists.
    waiting = db.query(
        con,
        "SELECT DISTINCT m.station_identifier AS icao, t.target_date AS target "
        "FROM paper_trades t JOIN markets m "
        "  ON m.market_id = t.market_id AND m.dataset_version = t.dataset_version "
        "WHERE t.dataset_version = ? AND t.exit_time IS NULL "
        "  AND m.station_identifier IS NOT NULL",
        [dataset_version],
    )
    if not waiting:
        cy.stage("observations", OK, wanted=0, ingested=0,
                 reason="no_open_position_waiting_on_a_label")
        return {"wanted": 0, "ingested": 0}

    wanted: set[tuple[str, date]] = set()
    no_target = 0
    for r in waiting:
        target = r["target"]
        if target is None:
            # A position written before this column existed. It is NOT settled by
            # guessing the day from `endDate`: it is counted and left open.
            no_target += 1
            continue
        wanted.add((str(r["icao"]).upper(), target.date()
                    if hasattr(target, "date") else target))

    ingested = pending = already = 0
    errors: dict[str, int] = {}
    for icao, target in sorted(wanted):
        tz = _station_tz(icao)
        if tz is None:
            errors["unknown_station_tz"] = errors.get("unknown_station_tz", 0) + 1
            continue
        day_start, day_end = weather.target_day_window(target, tz)
        # A PUBLICATION MARGIN, not just "the day ended". The window closing does
        # not mean IEM already holds the day's last METAR, and the failure mode is
        # the worst kind: an incomplete maximum written once and never revisited,
        # because the next cycle sees a row for that station-day and skips it. A
        # label that is plausible and wrong is worse than no label — `settle`
        # refusing costs a cycle, a wrong label costs the ledger.
        if now < day_end + LABEL_PUBLICATION_MARGIN:
            pending += 1
            continue
        have = db.query(
            con,
            "SELECT 1 FROM weather_observations WHERE station = ? "
            "AND observation_time >= ? AND observation_time < ? "
            "AND dataset_version = ? LIMIT 1",
            [icao, day_start, day_end, dataset_version],
        )
        if have:
            already += 1
            continue
        try:
            obs.ingest_daily_high(con, icao, target, tz, dataset_version)
            ingested += 1
        except Exception as exc:
            key = "rate_limited" if "429" in str(exc) else type(exc).__name__
            errors[key] = errors.get(key, 0) + 1
            if key == "rate_limited":
                cy.stage("observations", STOPPED, reason="http_429_rate_limited",
                         ingested=ingested, wanted=len(wanted))
                return {"wanted": len(wanted), "ingested": ingested, "stopped": True}

    cy.stage("observations", OK, wanted=len(wanted), ingested=ingested,
             already_had=already, day_not_over=pending,
             trades_without_target_date=no_target or None,
             errors=json.dumps(errors) if errors else None)
    return {"wanted": len(wanted), "ingested": ingested, "pending": pending}


def stage_settle(cy: Cycle, con, *, dataset_version: str) -> dict:
    """Settle open positions against the realized label, via the SettlementOperator.

    The label is NEVER guessed. `weather_agent.settlement` implements the frozen
    core and refuses far more often than it emits — 78 % of the catalogue has no
    operator at all — and a refusal here means the position stays open with its
    reason recorded, not that we pick a winner from the last traded price. That
    shortcut is what turns a paper ledger into fiction.

    Skips loudly while the substrate is incomplete, naming the missing columns."""
    # Every open position of this dataset_version, regardless of which cycle
    # opened it: a position opened days ago settles when its day resolves, not
    # when the cycle that opened it happens to run again.
    open_rows = db.query(
        con,
        "SELECT paper_trade_id, market_id, token_id, entry_time, target_date "
        "FROM paper_trades WHERE dataset_version = ? AND exit_time IS NULL "
        "ORDER BY paper_trade_id",
        [dataset_version],
    )
    n_open = len(open_rows)
    if not n_open:
        cy.stage("settle", OK, positions_open=0, settled=0)
        return {"positions_open": 0, "settled": 0}

    missing = settle_substrate_missing(con)
    if missing:
        cy.stage("settle", SKIPPED, reason="substrate_incomplete",
                 missing=",".join(missing), positions_open=n_open)
        return {"positions_open": n_open, "settled": 0, "missing": missing}

    settled = 0
    refusals: dict[str, int] = {}
    for pos in open_rows:
        rows = db.query(
            con,
            "SELECT m.market_id, m.event_id, m.contract_source, "
            "       m.measurement_rule_code, "
            "       m.unit, m.rounding_rule, m.station_identifier, "
            "       o.band_label, o.outcome_label "
            "FROM markets m JOIN outcomes o "
            "  ON o.market_id = m.market_id AND o.dataset_version = m.dataset_version "
            "WHERE m.market_id = ? AND o.token_id = ? AND m.dataset_version = ? LIMIT 1",
            [pos["market_id"], pos["token_id"], dataset_version],
        )
        if not rows:
            refusals["no_market_row"] = refusals.get("no_market_row", 0) + 1
            continue
        m = rows[0]
        # THE SAME DEFECT LIVED HERE TOO, and settlement is where it bites hardest:
        # this is the day the realized label is looked up for, so deriving it from
        # a re-discoverable `endDate` could settle a trade against a day it was
        # never opened for. The position carries its own `target_date` (2D §C).
        target = pos.get("target_date")
        if target is None:
            refusals["trade_without_target_date"] = \
                refusals.get("trade_without_target_date", 0) + 1
            continue
        target = target.date() if hasattr(target, "date") else target

        icao = m.get("station_identifier")
        if not m.get("measurement_rule_code"):
            # Never substitute the prose. The partition is keyed on the P_* code
            # and a sentence in its place is refused as an unknown terna, which
            # reads as "this market has no operator" when the truth is "this row
            # was never classified".
            refusals["no_measurement_rule_code"] = \
                refusals.get("no_measurement_rule_code", 0) + 1
            continue
        ctx = settlement.MarketContext(
            market_id=m["market_id"], event_id=m["event_id"],
            contract_source=m["contract_source"],
            measurement_rule_code=m["measurement_rule_code"], unit=m["unit"],
            rounding_rule=m.get("rounding_rule"), target_date=target,
            station_icao=icao, station_tz=_station_tz(icao),
        )
        # NO PREDICATE ON THE DAY, AND THAT IS DELIBERATE: the window belongs to
        # the operator, not to this query. A LOCAL_CIVIL_DAY operator needs the
        # station-local day of `target_date`, whose UTC bounds depend on a
        # timezone the core resolves — computing them here would be a second,
        # divergent implementation of the core's own §4.
        #
        # The cost of that choice is that a SOURCE_DAILY_ROW operator, which
        # applies NO temporal predicate and then aggregates with `max`, would
        # settle against the maximum of every day ingested so far: a plausible
        # number, no refusal, biased upward, and worse the longer the run lasts.
        # That cannot happen today — the only such operator requires SERIES_HKO
        # and `SERIES_CORRESPONDENCE` cannot emit that name — but the protection
        # lives in `settlement.OPERATORS`, three modules from the query it
        # guards, and would vanish silently the day a daily-summary operator over
        # a METAR series is added. So it is pinned as an executable claim rather
        # than left as an argument: `test_no_declared_series_reaches_a_source_
        # daily_row_operator` fails, by name, before the wrong day is ever
        # settled against.
        raw_obs = db.query(
            con,
            "SELECT observation_time, observed_value, observed_unit, series, "
            "       available_at, record_version FROM weather_observations "
            "WHERE station = ? AND dataset_version = ?",
            [icao, dataset_version],
        )
        obs = [
            settlement.Observation(
                ts_utc=r["observation_time"], value=r["observed_value"],
                unit=r["observed_unit"], series=to_core_series(r["series"]),
                available_at=r.get("available_at"),
                record_version=r.get("record_version") or 1,
            )
            for r in raw_obs if to_core_series(r["series"]) is not None
        ]
        if raw_obs and not obs:
            refusals["series_correspondence_undeclared"] = \
                refusals.get("series_correspondence_undeclared", 0) + 1
            continue
        # asof=None: `available_at` on the observation history is the download
        # instant, not a real availability (A-30), so an as-of gate here would be
        # a claim we cannot support. The result carries Y_FINAL_UNKNOWN_ASOF and
        # says so.
        result, reason = settlement.try_settle(obs, ctx, asof=None)
        if result is None:
            refusals[reason] = refusals.get(reason, 0) + 1
            continue
        won = settlement.band_key_wins(m["band_label"], result.band_key, m["unit"])
        # The position is on a specific token. A 'Yes' token pays when the band
        # contains the settled key; a 'No' token pays when it does not.
        pays = won if m.get("outcome_label") == "Yes" else (not won)
        paper.settle_paper_trade(con, int(pos["paper_trade_id"]),
                                 settlement=1 if pays else 0,
                                 exit_time=_iso(_utcnow()))
        settled += 1

    cy.stage("settle", OK, positions_open=n_open, settled=settled,
             refused=n_open - settled, reasons=json.dumps(refusals))
    return {"positions_open": n_open, "settled": settled, "refusals": refusals}


def stage_params(cy: Cycle, *, root: str, session_id: str, args, timing: dict,
                 dataset_version: str, quantile_provenance: dict | None = None) -> dict:
    """Persist the parameters this cycle actually ran with.

    R24 declares the run void if any frozen parameter changes mid-run, but the
    workflow reads them from repository variables (`vars.PAPER_TAU`, ...), which a
    person can edit in the GitHub UI leaving no trace in any repository history.
    Without this the rule would be unauditable — you could not tell afterwards
    which tau a given cycle used. Writing the effective values into the shard store
    makes every cycle carry its own parameters, so a change shows up as a diff in
    an append-only, commit-timestamped record."""
    # Read back from the stage that already measured it rather than measuring
    # again: `store_stats` walks the store, and calling it a second time HERE
    # would report the store AFTER this cycle's dump — a different quantity from
    # the one that was loaded into memory, which is the one the RAM projection
    # needs. Zero when the stage did not run (the settle-only tail), which is
    # honest: nothing was loaded.
    _loaded = next((e for e in cy.stages if e["stage"] == "load:store_stats"), {})
    store_bytes = _loaded.get("total_bytes", 0)
    store_rows = _loaded.get("rows_loaded", 0)
    _resident = _loaded.get("rows_resident", 0)
    params = {
        "session_id": session_id,
        "dataset_version": dataset_version,
        "target_date": str(args.target_date),
        "recorded_at": _iso(_utcnow()),
        # THE PER-STAGE PROFILE GOES IN THE SHARD, not only in the summary.
        # Session B's blocking finding on PR #23: `cy.stage()` reaches
        # `$ROOT/last_summary.json`, which is OUTSIDE `paper_state`, overwritten
        # every cycle and never committed — `run_cycle.sh:115` adds only
        # `paper_state`. So the timings would have been one point, the last one,
        # not a series. It is the defect documented at line 722 of this file
        # three hours earlier, committed again by the person who wrote it down.
        #
        # `cycle_params` is written on EVERY cycle including collect-only, so
        # this is ten points a day rather than two.
        #
        # AND THE PROFILE CANNOT CONTAIN THE STAGE THAT WRITES IT. Session B, on
        # the merged version: the snapshot is taken INSIDE `stage_params`, so
        # whatever runs after it is absent — and the danger is not the absence,
        # it is that the parts would still SUM to a plausible whole with nothing
        # saying a stage is missing. We would attribute its cost to no one, on
        # the day we finally read the profile to find out where the time goes.
        # `stage_params` now runs AFTER `stage_dump` so the dump is measured;
        # what remains outside is this stage itself, which is irreducible and is
        # therefore DECLARED rather than left to be inferred.
        "stage_profile": json.dumps(
            [{"stage": e["stage"], "at_s": e.get("at_s"),
              "elapsed_s": e.get("elapsed_s")} for e in cy.stages]),
        "stage_profile_excludes": "params",
        # THE SIZE OF THE STORE WAS COMPUTED EVERY CYCLE AND THROWN AWAY. Session
        # B's third finding of this family: `store_stats` reaches `cy.stage()`
        # and stops there, so it lands in `last_summary.json` — outside
        # `paper_state`, overwritten every cycle, never committed — and
        # `stage_profile` keeps three keys per stage, so it does not pick the
        # detail up either. Its own docstring says it exists "so the store's
        # growth is visible in the run log before it becomes a problem": visible
        # in a log nobody keeps.
        #
        # WHAT THE SERIES IS FOR, and it is not curiosity. The store only grows —
        # D0 forbids deleting — the cycle rebuilds it in memory every run, and
        # the host has 3.8 GB and NO SWAP. Without swap, exhausting RAM does not
        # raise: the kernel kills the process. `_non_fatal`, the try/except
        # ladder and B's span rule are all built on exceptions and CANNOT SEE IT.
        # So the one failure the span rule exists to prevent — losing a capture
        # between `stage_collect` and `stage_dump` — can arrive by the one route
        # the span rule cannot intercept. These two fields are what lets the
        # crossing be dated from the repository itself instead of reconstructed
        # from the shards by hand.
        #
        # THIS SERIES HAS A SEAM AT PR #26 and must not be differenced across
        # it: that PR changes `rows_written` from rows OFFERED to rows APPLIED,
        # and this field sums it. Offered and applied are equal on every shard
        # written so far, and applied is the better quantity here — what occupies
        # memory is what lands in the database, not what was read off disk.
        #
        # The full account lives in `store.load_shards`'s docstring, where the
        # meaning is CHANGED, and is deliberately not repeated here: two copies
        # of an explanation drift, and the one at the consumer would be the one
        # nobody updates. What belongs here is that a reader of this field must
        # go look. The rule the pair taught us: when you change what a number
        # MEANS, hunt for who CONSUMES it, not who produces it — the change was
        # declared at the producer and the consumer was two modules and one PR
        # away.
        # `store_total_bytes` IS NOT A RAM NUMBER, and after this PR it is not
        # even a clean disk number. `store_stats` sums `st_size` over the
        # shards, so it is (a) GZIPPED bytes and (b) inclusive of every
        # duplicate catalogue copy. Session B measured the three magnitudes
        # on the same store: 8.8 MB gzipped, 60.5 MB uncompressed, 239 MB of
        # process RSS — a factor of 27 between the first and the last, and
        # nowhere written down until now.
        #
        # So: use this to watch the STORE grow against 31 GB of free disk,
        # which is what its docstring claims and what it is good for. Use
        # `rows_resident` for the RAM ceiling. Anyone dating the ceiling from
        # this field gets a compressed number, inflated by redundancy, and
        # 27x too small.
        "store_total_bytes": int(store_bytes),
        "store_rows_loaded": int(store_rows),
        # AND THE ONE THE PROJECTION ACTUALLY NEEDS, which stopped at the
        # stage. `rows_resident` was computed, passed to `cy.stage()` and
        # never written here — so the comment above pointed a reader at a
        # field the row does not contain, which is worse than no pointer.
        #
        # It is PR #23's defect reappearing inside the fix for its own
        # family: a value that reaches the stage and not the shard. And the
        # test could not catch it, because the test read the STAGE too.
        "store_rows_resident": int(_resident),
        # `at_s` is relative to the start of the cycle, so without this the
        # series has no absolute anchor. On Hetzner it can be recovered from the
        # `session_id`; on Actions the id carries the run id instead and it
        # cannot. One field, and it matters the day the box falls over and we go
        # back to `workflow_dispatch`.
        "cycle_started_at": _iso(cy.started_at),
        "t_end": _iso(timing["t_end"]),
        "t_asof": _iso(timing["t_asof"]),
        "prediction_time": _iso(timing["prediction_time"]),
        "lead_nominal_h": timing["lead_nominal_h"],
        "lead_effective_h": timing["lead_effective_h"],
        "drift_h": timing["drift_h"],
        "model": args.model,
        "tau_signal": args.tau_signal,
        "tau_exec": args.tau_exec,
        "bankroll": args.bankroll,
        "fixed_fraction": args.fixed_fraction,
        "size_cap": args.size_cap,
        "x_exec": args.x_exec,
        "exit_mode": args.exit_mode,
        "weather_sum_tolerance": args.weather_sum_tolerance,
        "market_sum_min": args.market_sum_min,
        "market_sum_max": args.market_sum_max,
        "collect_only": bool(args.collect_only),
        "code_commit": os.environ.get("GITHUB_SHA"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        # B's second condition: the cycle records WHICH artifact it used. The id
        # is a sha over the artifact's canonical content, so it names the fit
        # exactly — including a refit that produced identical numbers. When the
        # artifact was REFUSED, the refusal label is recorded instead, so a cycle
        # that produced no signal says why in the same row that says what it ran
        # with.
        "max_artifact_age_h": args.max_artifact_age_h,
    }
    params.update(quantile_provenance or {})
    out = store.write_shard([params], table="cycle_params", run_id=session_id,
                            root=root)
    cy.stage("params", OK, path=out["path"], tau_signal=args.tau_signal,
             tau_exec=args.tau_exec,
             bankroll=args.bankroll, x_exec=args.x_exec)
    return params


def catalogue_is_unchanged(con, table: str, root: str) -> bool:
    """Would this catalogue dump be byte-for-byte the previous one?

    THE CATALOGUE IS A SNAPSHOT, NOT A LEDGER. Dumping an identical snapshot ten
    times a day adds no information and costs replay time on every later cycle,
    because `load_shards` reloads every shard. Measured on the box: a catalogue
    row costs 21.3 ms to load, the snapshot is 2 200 rows, and ten dumps a day put
    `load:*` past the 42-minute budget between day +2 and +3 — at which point the
    `flock` makes the next cycle skip, and what it skips is a book slot.

    THREE CONDITIONS, AND EACH ONE ALONE MISSES A CASE SEEN ON 2026-09-11:

      * the conflict-key SET is identical  — alone it misses a schema migration
        that adds columns without adding rows. `SCHEMA_VERSION 6` added seven
        (`end_date`, `fee_rate`, `fee_exponent`, `fee_taker_only`, `fees_enabled`,
        `measurement_rule_code`, `uma_resolution_status`), and the last of those
        is what R30 §4.3 counts resolved events with;
      * the KEY set of the rows is identical — alone it misses a changed value;
      * no VALUE differs over those keys — alone it misses both of the above.

    "Compare the content" is NOT a specification until it says which comparison:
    on the same two shards, `dict != dict` reported 1 100 differing rows and a
    field-by-field walk over the COMMON keys reported 0. Both are "content".

    RAISES RATHER THAN SWALLOWING, and the CALLER fails open. The direction is
    right -- a spurious dump costs seconds of replay, a skipped one re-creates the
    defect PR #31 exists to fix, and this runs where a capture is still unwritten
    -- but an `except` HERE would be silent, and session B named the case that
    makes silence expensive: `CONFLICT_COLS[table]` raising `KeyError` the day a
    catalogue table is added without declaring its keys is PERMANENT, not
    transient. The gate would return False forever, the catalogue would go back to
    2 200 rows a cycle, and the 2-3 day budget crossing this PR removes would come
    back through the error path WITHOUT ONE LINE ANYWHERE. The defect prevented
    here, reintroduced by the handler for it.

    ONLY SKIPS AGAINST A COMPLETE SNAPSHOT. The comparison is against the most
    recent shard; if that shard were a SUBSET of the real state -- as the frozen
    2026-09-09 one was against tonight's -- the sets differ and the gate says
    "changed". Fail-open again, and stated so nobody reads the skip as stronger
    than it is.

    AS OF 2026-09-12 THIS GATE HAS NEVER RETURNED True IN PRODUCTION, AND CANNOT.
    The third condition compares values, and the OPEN markets are re-inserted by
    discovery on every cycle carrying two fields that follow the cycle clock --
    `ingestion_timestamp` and `source_timestamps.updatedAt`. Measured across the
    21:07 and 00:07 shards: 1 100 rows differ, and they are exactly the 1 100 whose
    `endDate` is in the future (09-12 and 09-13); the 1 100 closed ones (09-10 and
    09-11) are byte-identical. There are always open markets, so condition 3 always
    fails and the function always returns False. **The dump this was written to
    prevent still happens every cycle, and the 42-minute budget crossing is still
    coming.** The fix is to exclude those two bookkeeping fields -- `updatedAt`
    INSIDE the dict, not the dict, which also carries `endDate` -- and it is not in
    this branch. Everything below is true about the comparison as designed; none of
    it is yet true about the comparison as it runs.

    AND "THE MOST RECENT SHARD" MEANS MOST RECENT BY PATH, NOT BY TIME. `sorted()`
    orders `<date>/<table>__<session_id>__NNNN.ndjson.gz` lexicographically: the
    date leads, and the session id breaks ties WITHIN a day. The ids come from two
    generators that do not sort in their own chronological order -- `col_<ISO>_<pid>`
    (the Hetzner cron) and `cyc_<run_id>` (Actions) -- and `col_... < cyc_...` while
    `cyc_` is the OLDER of the two, Actions schedules having been disabled
    2026-09-09 when collection moved to the box. The gate therefore assumes
    lexicographic path order IS temporal order, which holds only while every id in
    a given day comes from one generator.

    That assumption has already been violated, just not here: on 2026-09-09 both
    generators wrote into the same date for THREE tables (`cycle_params`,
    `orderbook_snapshots`, `price_history`). The catalogue tables escaped by
    accident of scheduling, not by design -- `markets`, `outcomes` and
    `market_fee_schedule` have `cyc` on 09-09 and `col` on 09-11, different dates,
    where the date component decides and the ids never compete. Let a third
    generator share a date with `cyc_` and this compares against the wrong shard,
    the sets differ, and it dumps: fail-open a third time. Which is why it is
    written here as a caveat and not fixed as a bug."""
    shards = store.iter_shards(root, table)
    if not shards:
        return False                          # nothing to compare against
    previous = list(store.read_shard(sorted(shards)[-1]))
    current = db.query(con, f"SELECT * FROM {table}")
    key = list(store.CONFLICT_COLS[table])

    ident = lambda r: tuple(str(r.get(c)) for c in key)
    if {ident(r) for r in previous} != {ident(r) for r in current}:
        return False
    if {k for r in previous for k in r} != {k for r in current for k in r}:
        return False
    prev_by = {ident(r): r for r in previous}
    cols = {k for r in current for k in r}
    return all(all(prev_by[ident(r)].get(c) == r.get(c) for c in cols)
               for r in current)


def stage_dump(cy: Cycle, con, *, root: str, session_id: str,
               dataset_version: str, since: datetime,
               dump_catalogue: bool = False) -> None:
    """Write the rows THIS run produced out as shards — the only durable step.

    The `since` filter matters more than it looks: a resumed cycle has just loaded
    its earlier rows back from the shards, so exporting everything would re-emit
    them and grow the store by a full copy on every retry. `ingestion_timestamp`
    is stamped in this process, so it separates what was produced now from what
    was merely reloaded — and it is the one column every one of these tables has,
    which is why the filter is uniform instead of per-table.

    THE CATALOGUE GOES OUT ON EVERY CYCLE THAT DECIDES, and it used to go out once
    a day. The daily snapshot was a size optimisation, and measuring it killed it:
    the three catalogue tables compress to **206 KiB per snapshot** (markets 83,
    outcomes 123, fee schedule 0.3, at 1 100 / 2 200 / 1 rows), so the two daily
    decision cycles cost **8.5 MiB over the 42-cycle run**, against a 200 MB stop
    threshold and ~125 MB of projected volume. What the optimisation bought was
    negligible; what it cost was C3.

    `replay_cycle.py` rebuilds its DuckDB from the shards. Without a catalogue
    shard of its own, a cycle is replayed against the most recent daily snapshot —
    up to 15 h older than the decisions it audits — so every market discovered in
    between is simply absent, its trades come back as `only_persisted`, and the
    verdict is NOT REPRODUCIBLE for a reason that has nothing to do with
    reproducibility. Verified on a live cycle: 21 trades persisted, 0 recomputed,
    21 spurious `only_persisted`, purely because `markets` and `outcomes` had no
    shard. A criterion that fails for half the run on an artefact of the dump
    schedule is not a criterion.

    AND SINCE PR #31 EVERY CYCLE DUMPS IT, collect-only included — this paragraph
    used to say the opposite and PR #31 left it saying so. The reason is not
    replay: it is that the universe is not recoverable from the `closed=false`
    feed, so a market discovered live and never written disappears when it closes.

    WHAT IS SKIPPED NOW IS AN IDENTICAL SNAPSHOT, not a cycle. See
    `catalogue_is_unchanged`: dumping the same 2 200 rows ten times a day costs
    21.3 ms per row on every later replay and crosses the 42-minute budget in two
    to three days."""
    tables = LEDGER_TABLES + (CATALOGUE_TABLES if dump_catalogue else ())
    total = 0
    saltados = 0
    for table in tables:
        if table in CATALOGUE_TABLES:
            # Fail-open WITH A RECORD. The gate raising must not cost the dump,
            # and it must not be invisible either: a permanent failure would
            # silently restore the per-cycle dump this stage exists to avoid.
            try:
                unchanged = catalogue_is_unchanged(con, table, root)
            except Exception as exc:
                unchanged = False
                cy.stage(f"dump:{table}:gate", STOPPED, error=repr(exc))
            if unchanged:
                saltados += 1
                cy.stage(f"dump:{table}", SKIPPED, reason="catalogue_unchanged")
                continue
        # The catalogue is a full snapshot (its rows are re-stamped every run, so a
        # `since` filter would either take everything or nothing); the ledger is
        # incremental.
        where, params = (
            (None, None) if table in CATALOGUE_TABLES
            else ("ingestion_timestamp >= ?", [since])
        )
        out = store.dump_table(con, table, run_id=session_id, root=root,
                               where=where, params=params)
        total += out["n_rows"]
        if out["n_rows"]:
            cy.stage(f"dump:{table}", OK, rows=out["n_rows"], path=out["path"])
    if not dump_catalogue:
        cy.stage("dump:catalogue", SKIPPED, reason="collect_only_nothing_to_replay")
    cy.stage("dump", OK, tables=len(tables), rows_written=total,
             catalogue_tables_skipped=saltados,
             catalogue="dumped" if dump_catalogue else "skipped")


# --------------------------------------------------------------------------- main
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run one paper-mode cycle.")
    p.add_argument("--target-date", required=True,
                   help="OBLIGATORY (2D §C): the date whose temperature is traded, "
                        "YYYY-MM-DD. Never derived from the catalogue.")
    p.add_argument("--dataset-version", required=True)
    p.add_argument("--session-id", default=None,
                   help="Cycle id. Re-passing it RESUMES that cycle; omitting it "
                        "starts a new one.")
    p.add_argument("--store-root", default=store.DEFAULT_ROOT)
    p.add_argument("--db", default=None,
                   help="DuckDB path. Default: in-memory, rebuilt from the shards.")
    p.add_argument("--lead-hours", type=float, default=24.0,
                   help="Nominal lead. With --target-date it fixes T_asof = "
                        "target_date 12:00Z - lead_hours. Operational range {9, 24} "
                        "(PREREG_LEAD_HOURS_RANGE).")
    p.add_argument("--model", default="icon_seamless", help="M1 (D12).")
    p.add_argument("--quantile-artifact", default=None,
                   help="M2's fitted quantiles (R30). Default: the repository copy "
                        "at quantile_artifact.DEFAULT_PATH, resolved against the "
                        "repo root so a cycle run from any cwd finds the same file.")
    p.add_argument("--max-artifact-age-h", type=float, default=None,
                   help="TIGHTEN the artifact's own declared shelf life. A value "
                        "LARGER than the artifact's is ignored: an operator does "
                        "not extend the life of an artifact from the command line.")
    p.add_argument("--tau-signal", type=float, default=None,
                   help="Strategy A threshold, on the GROSS edge (fair_value - "
                        "p_market) against the indicative mid. Required for the "
                        "signal stage.")
    p.add_argument("--tau-exec", type=float, default=None,
                   help="Execution threshold, on the NET edge (after fees, against "
                        "the achievable VWAP). A DIFFERENT quantity from --tau-signal; "
                        "it may take the same value, but that is a stated choice, not "
                        "an identity. Required for the paper stage.")
    p.add_argument("--bankroll", type=float, default=config.DEFAULTS["bankroll"])
    p.add_argument("--fixed-fraction", type=float,
                   default=config.DEFAULTS["fixed_fraction"])
    p.add_argument("--size-cap", type=float, default=config.DEFAULTS["size_cap"])
    p.add_argument("--x-exec", type=float, default=0.0,
                   help="Declared spread/slippage add-on, USDC per share (D19).")
    p.add_argument("--exit-mode", default="hold_to_resolution",
                   choices=["hold_to_resolution", "taker_close"])
    p.add_argument("--weather-sum-tolerance", type=float, default=0.02)
    p.add_argument("--market-sum-min", type=float, default=0.90)
    p.add_argument("--market-sum-max", type=float, default=1.15)
    p.add_argument("--horizon-days", type=int, default=2,
                   help="Discovery window past the target date.")
    p.add_argument("--chunk-size", type=int, default=collector.DEFAULT_CHUNK_SIZE)
    p.add_argument("--max-pages", type=int, default=20)
    p.add_argument("--collect-only", action="store_true",
                   help="Books only: skip signals, paper and settlement.")
    p.add_argument("--settle-only", action="store_true",
                   help="THE SETTLEMENT TAIL (R24 §5). Ingest the labels that open "
                        "positions wait on and settle them; discover nothing, "
                        "collect nothing, decide nothing. A position opened on the "
                        "last day of the run resolves the day AFTER it, so without "
                        "these cycles the last two days' positions would stay open "
                        "and their PnL would not exist — the ledger would close on "
                        "a tail truncated by the calendar, not by the market. These "
                        "cycles do NOT count in the run's 42.")
    p.add_argument("--dump-catalogue", action="store_true",
                   help="Force the markets/outcomes/fees snapshot on a "
                        "--collect-only run. Deciding cycles always take it: the "
                        "replay needs the universe the cycle decided on, not a "
                        "snapshot up to 15 h older (see CATALOGUE_TABLES).")
    p.add_argument("--summary-json", default=None,
                   help="Write the cycle summary to this path.")
    p.add_argument("--coverage-also", default=None, action="append",
                   type=_coverage_also, metavar="LEAD:YYYY-MM-DD",
                   help="Also measure venue coverage for this (lead, target), "
                        "which this cycle is NOT deciding. Coverage is a "
                        "property of the venue, not of the lead the cycle "
                        "happens to carry, and without this the series can "
                        "never hold a FINAL row for lead 9: the only cycle that "
                        "carries a lead-9 target fires 20 min before its anchor "
                        "by design, so `is_final` is False by construction. "
                        "The target is passed, never derived here: 2D §C makes "
                        "it the caller's parameter and a second derivation is "
                        "how two of them end up disagreeing.")
    p.add_argument("--host-events", default=None,
                   help="NDJSON queue the host appends to when a slot is lost "
                        "(a lock timeout, say). Drained into a `host_events` "
                        "shard so a SKIPPED slot is distinguishable from a host "
                        "that never fired — the distinction R24 §4quater rests "
                        "on. Without it a skip lives only in the box's log.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    target_date = date.fromisoformat(args.target_date)
    session_id = args.session_id or collector.new_session_id()
    # Planned only: T_end and T_asof do not depend on the clock, so they can be
    # logged up front. `prediction_time` is NOT settled here — see below.
    plan = decision_time(target_date, args.lead_hours, _utcnow())

    cy = Cycle(session_id=session_id, dataset_version=args.dataset_version,
               target_date=str(target_date), model=args.model,
               collect_only=bool(args.collect_only),
               t_end=_iso(plan["t_end"]), t_asof=_iso(plan["t_asof"]),
               lead_nominal_h=plan["lead_nominal_h"])
    print(f"paper_cycle session={session_id} target_date={target_date} "
          f"dataset_version={args.dataset_version}", flush=True)
    print(f"  T_end={_iso(plan['t_end'])}  T_asof={_iso(plan['t_asof'])}  "
          f"lead nominal={plan['lead_nominal_h']:.0f}h", flush=True)

    con = db.init_db(db.connect(args.db or ":memory:"))
    try:
        import requests
        http = requests.Session()

        stage_load_state(cy, con, root=args.store_root)
        discovery.ensure_dataset_version(con, args.dataset_version)

        if args.settle_only:
            # Nothing is discovered, collected or decided: the tail exists only to
            # close what is already open. Skipping discovery also keeps it from
            # touching `markets.available_at`, which a decision cycle depends on.
            for st in ("discover", "universe", "collect:books", "forecasts",
                       "signals", "paper"):
                cy.stage(st, SKIPPED, reason="settle_only_tail")
            stage_observations(cy, con, dataset_version=args.dataset_version,
                               now=_utcnow())
            stage_settle(cy, con, dataset_version=args.dataset_version)
            # DUMP FIRST, PARAMS LAST — see `stage_params`. The profile is
            # snapshotted inside `stage_params`, so anything after it is
            # invisible; running it last is what puts `dump` in the series.
            stage_dump(cy, con, root=args.store_root, session_id=session_id,
                       dataset_version=args.dataset_version, since=cy.started_at,
                       dump_catalogue=False)
            stage_params(cy, root=args.store_root, session_id=session_id, args=args,
                         quantile_provenance={}, timing=plan | {
                             "prediction_time": plan["t_asof"], "drift_h": 0.0,
                             "lead_effective_h": plan["lead_nominal_h"]},
                         dataset_version=args.dataset_version)
            con.close()
            return _finish(cy, args)

        stage_discover(cy, con, dataset_version=args.dataset_version,
                       target_date=target_date, horizon_days=args.horizon_days,
                       session=http, max_pages=args.max_pages)

        universe = select_universe(con, dataset_version=args.dataset_version,
                                   target_date=target_date)
        cy.stage("universe", OK, tokens=len(universe),
                 markets=len({r["market_id"] for r in universe}),
                 events=len({r["event_id"] for r in universe}))

        stage_collect(cy, con, dataset_version=args.dataset_version,
                      session_id=session_id, universe=universe, session=http,
                      chunk_size=args.chunk_size)

        # THE DECISION INSTANT IS SETTLED HERE, after collection, never at cycle
        # start: everything a decision consumes must already exist at
        # `prediction_time`, and the prices this cycle just wrote carry an
        # `observation_time` of a few minutes ago.
        # Resolved against the REPO ROOT, not the cwd. The workflow runs the
        # script from the checkout root and a person runs it from anywhere; a
        # relative default would make "which artifact did it use" depend on where
        # the shell happened to be.
        artifact_path = args.quantile_artifact or str(
            Path(__file__).resolve().parents[1] / quantile_artifact.DEFAULT_PATH)
        quantile_provenance: dict = {}

        # ONE CLOCK READ FOR THE WHOLE CYCLE'S ANCHORS. Both this stage and the
        # complementary-lead coverage below derive their anchor from it, so two
        # rows written by one cycle can never straddle an anchor between two
        # readings — the `is_final` defect, which was exactly this shape.
        cycle_now = _utcnow()
        timing = decision_time(target_date, args.lead_hours, cycle_now)
        prediction_time = timing["prediction_time"]
        # Usable exactly when the clamp did NOT bind: if `now` is still before
        # T_asof then `prediction_time` IS `now`, which is after the collection
        # that just finished, so this cycle's own prices qualify. If the clamp
        # bound, `prediction_time` is T_asof and the prices are newer than it.
        own_prices_usable = timing["fired_early"]
        cy.stage("timing", OK, t_asof=_iso(timing["t_asof"]),
                 prediction_time=_iso(prediction_time),
                 lead_effective_h=round(timing["lead_effective_h"], 3),
                 drift_h=round(timing["drift_h"], 3),
                 late_firing=timing["drift_h"] > 0,
                 own_prices_usable=own_prices_usable)
        if not own_prices_usable:
            # Ran past T_asof: this cycle's own prices are newer than the as-of it
            # must respect, so the decision falls back to the last price at or
            # before T_asof — which the 3-hourly collector supplies. Reported, not
            # silently absorbed.
            cy.stage("timing:fallback", OK,
                     reason="own_prices_newer_than_t_asof_using_earlier_collection")

        # Guard BEFORE any decision, and after the tables are populated: a cycle
        # that only collects is harmless, one that decides on an ambiguous
        # database is not.
        # A REFUSED GUARD DEGRADES THE CYCLE, it does not kill it. `deciding`
        # replaces `not args.collect_only` from here on, so a cycle whose
        # database is ambiguous still collects, still measures and still dumps —
        # and decides nothing, which is the only thing the guard ever claimed to
        # forbid.
        deciding, guard_refused = not args.collect_only, False
        if deciding:
            guard = stage_guard_dataset_version(
                cy, con, dataset_version=args.dataset_version)
            if not guard.get("ok"):
                deciding = False
                guard_refused = True

        # RUNG 1 ON EVERY CYCLE, deciding or not. It needs only prices, and the
        # collect-only cycles are the ones that actually run in Actions — so this
        # is the only place the live measurement can accumulate before
        # `PAPER_TAU` exists. After collection and after `prediction_time` is
        # settled, so it counts the prices this cycle just wrote.
        # NOTHING BETWEEN `stage_collect` AND `stage_dump` MAY THROW. Session B's
        # rule, and the reason is structural: the order-book capture above is the
        # one thing in this project that cannot be re-fetched, and `stage_dump`
        # below is the only place it is persisted — inside the `try`, with a
        # `finally` that closes the connection and nothing more. An exception in
        # this span means the dump never runs and the capture is lost.
        #
        # Both stages here are MEASUREMENT. Measurement is worth a great deal and
        # is worth strictly less than the capture, and until now they were
        # coupled the other way round: a failure to measure destroyed the thing
        # being measured. Each is wrapped so any failure lands as a SKIPPED stage
        # with its reason and the cycle still reaches the dump.
        def _non_fatal(name, fn):
            try:
                return fn()
            except Exception as exc:      # noqa: BLE001 — deliberate: see above
                cy.stage(name, SKIPPED,
                         reason="stage_failed_non_fatally",
                         error=f"{type(exc).__name__}: {exc}"[:300])
                return None

        # Before anything else that writes: the host's own events are part of
        # "scheduled versus delivered" and must not wait on the cycle succeeding.
        _non_fatal("host_events", lambda: stage_host_events(
            cy, queue_path=args.host_events, root=args.store_root,
            session_id=session_id))

        _non_fatal("venue_coverage", lambda: stage_venue_coverage(
            cy, con, dataset_version=args.dataset_version,
            universe=universe, prediction_time=prediction_time,
            t_asof=plan["t_asof"], root=args.store_root, session_id=session_id,
            target_date=target_date,
            lead_h=float(args.lead_hours), row_kind="own"))

        # THE COMPLEMENTARY LEAD. Not a convenience: without it the series can
        # never hold a FINAL row for lead 9, because the only cycle carrying a
        # lead-9 target fires at 02:40 against a 03:00 anchor — 20 minutes early
        # BY DESIGN — so `now < t_asof` always and `is_final` is False by
        # construction. Nothing else revisits that target.
        #
        # AND THE LATE ROW IS NOT A RE-STAMPED FLAG: IT IS THE MEASUREMENT.
        # Session B's point. Whether any price arrived in (cutoff, anchor] can
        # only be known AFTER the anchor. The early row is BETTING that none did;
        # a row cut at the anchor is the only thing that can settle it. Without
        # this, the series holds rows whose completeness nobody ever checked.
        for other_lead, other_td in (args.coverage_also or []):
            _op = decision_time(other_td, other_lead, cycle_now)
            _non_fatal("venue_coverage:other_lead",
                       lambda l=other_lead, d=other_td,
                              _other=(_op["prediction_time"], _op["t_asof"]): (
                stage_venue_coverage(
                    cy, con, dataset_version=args.dataset_version,
                    universe=select_universe(
                        con, dataset_version=args.dataset_version,
                        target_date=d),
                    prediction_time=_other[0], t_asof=_other[1],
                    root=args.store_root, session_id=session_id,
                    target_date=d, lead_h=l, row_kind="other_lead")))

        if not deciding:
            why = ("guard_refused_dataset_version" if guard_refused
                   else "collect_only")
            cy.stage("forecasts", SKIPPED, reason=why)
            cy.stage("signals", SKIPPED, reason=why)
            cy.stage("paper", SKIPPED, reason=why)
            cy.stage("observations", SKIPPED, reason=why)
        elif args.tau_signal is None or args.tau_exec is None:
            missing = "tau_signal" if args.tau_signal is None else "tau_exec"
            cy.stage("signals", SKIPPED, reason=f"{missing}_not_provided_fail_closed")
            cy.stage("paper", SKIPPED, reason=f"{missing}_not_provided_fail_closed")
        else:
            fc = stage_forecasts(cy, con, dataset_version=args.dataset_version,
                                 target_date=target_date, universe=universe,
                                 model=args.model, lead_hours=args.lead_hours,
                                 prediction_time=prediction_time,
                                 artifact_path=artifact_path,
                                 max_artifact_age_h=args.max_artifact_age_h,
                                 session=http)
            quantile_provenance = fc.get("provenance") or {
                "quantile_artifact_refusal": fc.get("artifact_refusal")}
            stage_signals(cy, con, dataset_version=args.dataset_version,
                          target_date=target_date, universe=universe,
                          model=args.model, tau=args.tau_signal,
                          weather_sum_tolerance=args.weather_sum_tolerance,
                          market_sum_min=args.market_sum_min,
                          market_sum_max=args.market_sum_max,
                          prediction_time=prediction_time)
            params = paper.PaperParams(
                bankroll=args.bankroll, fixed_fraction=args.fixed_fraction,
                size_cap=args.size_cap, tau_exec=args.tau_exec,
                exit_mode=args.exit_mode,
                x_exec=args.x_exec,
            )
            stage_paper(cy, con, dataset_version=args.dataset_version,
                        session_id=session_id, params=params,
                        prediction_time=prediction_time,
                        target_date=target_date)
            # The label BEFORE the settlement that consumes it, and after the
            # positions that name which labels are needed. Same ordering lesson as
            # `prediction_time` settled after collection: a stage that reads what
            # another writes has to run after it, not before.
            stage_observations(cy, con, dataset_version=args.dataset_version,
                               now=_utcnow())
            stage_settle(cy, con, dataset_version=args.dataset_version)

        # DUMP FIRST, PARAMS LAST, and the order buys two things.
        #
        # (1) The profile covers the dump. It is snapshotted inside
        #     `stage_params`, so a stage that runs after it is simply not in the
        #     series — and `dump` is the stage whose cost most plausibly grows
        #     with the store.
        # (2) `stage_params` leaves the protected span. B's rule is that nothing
        #     between `stage_collect` and `stage_dump` may throw, because that is
        #     the only span where an exception destroys a capture that cannot be
        #     re-fetched. Writing the params shard after the dump takes it out of
        #     that span entirely, instead of arguing case by case that its
        #     `json.dumps` cannot raise.
        #
        # WHAT IT COSTS, said plainly: a cycle whose dump raises no longer leaves
        # a `cycle_params` row. That cycle has already lost its collection, which
        # is the loss that matters; knowing which tau it would have used is not.
        stage_dump(cy, con, root=args.store_root, session_id=session_id,
                   dataset_version=args.dataset_version, since=cy.started_at,
                   # Every DECIDING cycle carries its own catalogue, so the
                   # replay reproduces it against the universe it actually
                   # decided on.
                   #
                   # AND NOW ON EVERY CYCLE, BECAUSE THE UNIVERSE IS NOT
                   # RECOVERABLE. The previous rule was `deciding or
                   # args.dump_catalogue`, reasoned entirely about REPLAY: a
                   # cycle that decided nothing has no decision to reproduce, so
                   # it needed no catalogue pinned against it. That reasoning is
                   # correct and it missed what the catalogue also is — the only
                   # record of WHICH MARKETS EXISTED.
                   #
                   # Every cycle since 2026-09-09 has been collect-only (the
                   # fail-closed `PAPER_TAU` gate), so `markets` was rebuilt each
                   # run from ONE frozen shard plus whatever live discovery added
                   # IN RAM — and the live part was never persisted. Measured on
                   # that shard: it holds target 2026-09-10 (51 events) and
                   # 2026-09-11 (49), and NOTHING for 09-12 onward. So the two
                   # 09-11 events discovered later evaporated when their markets
                   # closed, and two rows stamped `is_final: True` for the same
                   # (target, lead, cutoff) disagreed: 561 bands, then 539.
                   #
                   # For 09-12 it is not two events, it is all 51: none of them
                   # are in the shard. Gamma's `closed=false` feed does not return
                   # what has closed, so after 12:00Z that universe is gone the
                   # way an order book is gone. This is the ONE thing this
                   # project treats as unrecoverable, arriving through the
                   # catalogue instead of through the book.
                   #
                   # THE COST WAS COMPUTED AND IS NOT WHAT IT LOOKS LIKE. Ten
                   # dumps a day is ~11 000 shard rows, which sounds like it
                   # accelerates the RAM ceiling. It does not: `record_version`
                   # is 1 on all 1 100 rows and the conflict key is
                   # (market_id, dataset_version, record_version), so every copy
                   # COLLAPSES to the same 1 100 rows on load. RAM cost: zero.
                   # What grows is the store (~1 MB/day gzipped, against 31 GB
                   # free) and the replay (~1 100 redundant upserts per copy) —
                   # and the replay is exactly what PR #26 just made 39x faster.
                   #
                   # A daily dump was considered and REJECTED. It bounds the loss
                   # window to 24 h, and the argument for it — "an event closing
                   # inside the window is one for the target already in the
                   # shard" — is the very reasoning that failed today: 09-10 held
                   # only because its 51 events happened to be in the shard, and
                   # that was luck, not a property.
                   dump_catalogue=True)
        stage_params(cy, root=args.store_root, session_id=session_id, args=args,
                     quantile_provenance=quantile_provenance,
                     timing=timing, dataset_version=args.dataset_version)
    finally:
        con.close()

    return _finish(cy, args)


def _finish(cy: Cycle, args) -> int:
    """Write and print the summary. One exit point for both the full cycle and the
    settlement tail, so the tail cannot drift into reporting differently."""
    summary = cy.summary()
    if args.summary_json:
        Path(args.summary_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.summary_json).write_text(json.dumps(summary, indent=2),
                                           encoding="utf-8")
    print("\n=== cycle summary ===")
    print(json.dumps(summary, indent=2))
    # A stopped stage is reported, not raised: the shards are already written, and
    # a red job would hide the fact that collection succeeded.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
