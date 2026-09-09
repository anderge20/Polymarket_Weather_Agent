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
import json
import os
import sys
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

    def stage(self, name: str, status: str, **detail) -> dict:
        entry = {"stage": name, "status": status, **detail}
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
    cy.stage("load:store_stats", OK, tables=len(stats.get("tables", {})),
             total_bytes=stats.get("total_bytes", 0), rows_loaded=total)


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
    problems = []
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
    if problems:
        cy.stage("guard:dataset_version", STOPPED, problems=json.dumps(problems))
        raise SystemExit(
            "paper_cycle: refusing to decide on a database whose unfiltered reads "
            "are ambiguous:\n  - " + "\n  - ".join(problems)
        )
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
    cy.stage("collect:books", STOPPED if out["stopped"] else OK,
             tokens=out["tokens_requested"], pending=out["tokens_pending"],
             rows=out["rows_written"], prices=out["prices_written"],
             one_sided=out["prices_skipped_one_sided"],
             requests=out["requests"], error=out["error"])
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
    cy.stage("signals", OK, events=len(events), **totals)
    return totals


def stage_paper(cy: Cycle, con, *, dataset_version: str, session_id: str,
                params: paper.PaperParams, prediction_time: datetime) -> dict:
    """Turn actionable signals into simulated fills against the observed book."""
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
    "markets": ("contract_source",),
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

    waiting = db.query(
        con,
        "SELECT DISTINCT m.station_identifier AS icao, "
        "       json_extract_string(m.source_timestamps, '$.endDate') AS end_raw "
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
    unparseable = 0
    for r in waiting:
        try:
            target = datetime.fromisoformat(
                str(r["end_raw"]).replace("Z", "+00:00")).astimezone(timezone.utc).date()
        except (TypeError, ValueError):
            unparseable += 1
            continue
        wanted.add((str(r["icao"]).upper(), target))

    ingested = pending = already = 0
    errors: dict[str, int] = {}
    for icao, target in sorted(wanted):
        tz = _station_tz(icao)
        if tz is None:
            errors["unknown_station_tz"] = errors.get("unknown_station_tz", 0) + 1
            continue
        day_start, day_end = weather.target_day_window(target, tz)
        if now < day_end:
            pending += 1                       # the day is still running
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
             unparseable_end_date=unparseable or None,
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
        "SELECT paper_trade_id, market_id, token_id, entry_time "
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
            "SELECT m.market_id, m.event_id, m.contract_source, m.measurement_rule, "
            "       m.unit, m.rounding_rule, m.station_identifier, "
            "       o.band_label, o.outcome_label, "
            "       json_extract_string(m.source_timestamps, '$.endDate') AS end_raw "
            "FROM markets m JOIN outcomes o "
            "  ON o.market_id = m.market_id AND o.dataset_version = m.dataset_version "
            "WHERE m.market_id = ? AND o.token_id = ? AND m.dataset_version = ? LIMIT 1",
            [pos["market_id"], pos["token_id"], dataset_version],
        )
        if not rows:
            refusals["no_market_row"] = refusals.get("no_market_row", 0) + 1
            continue
        m = rows[0]
        try:
            target = datetime.fromisoformat(
                str(m["end_raw"]).replace("Z", "+00:00")).astimezone(timezone.utc).date()
        except (TypeError, ValueError):
            refusals["unparseable_end_date"] = refusals.get("unparseable_end_date", 0) + 1
            continue

        icao = m.get("station_identifier")
        ctx = settlement.MarketContext(
            market_id=m["market_id"], event_id=m["event_id"],
            contract_source=m["contract_source"],
            measurement_rule_code=m["measurement_rule"], unit=m["unit"],
            rounding_rule=m.get("rounding_rule"), target_date=target,
            station_icao=icao, station_tz=_station_tz(icao),
        )
        obs = [
            settlement.Observation(
                ts_utc=r["observation_time"], value=r["observed_value"],
                unit=r["observed_unit"], series=r["series"],
                available_at=r.get("available_at"),
                record_version=r.get("record_version") or 1,
            )
            for r in db.query(
                con,
                "SELECT observation_time, observed_value, observed_unit, series, "
                "       available_at, record_version FROM weather_observations "
                "WHERE station = ? AND dataset_version = ?",
                [icao, dataset_version],
            )
        ]
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
    params = {
        "session_id": session_id,
        "dataset_version": dataset_version,
        "target_date": str(args.target_date),
        "recorded_at": _iso(_utcnow()),
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

    COLLECT-ONLY CYCLES STILL SKIP IT, and that is the whole saving: the collector
    fires 8 times a day and decides nothing, so its cycles have nothing for the
    replay to reproduce (`replay` returns "trivially reproducible" for them). The
    catalogue is dumped where it is needed and nowhere else."""
    tables = LEDGER_TABLES + (CATALOGUE_TABLES if dump_catalogue else ())
    total = 0
    for table in tables:
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
    p.add_argument("--dump-catalogue", action="store_true",
                   help="Force the markets/outcomes/fees snapshot on a "
                        "--collect-only run. Deciding cycles always take it: the "
                        "replay needs the universe the cycle decided on, not a "
                        "snapshot up to 15 h older (see CATALOGUE_TABLES).")
    p.add_argument("--summary-json", default=None,
                   help="Write the cycle summary to this path.")
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

        timing = decision_time(target_date, args.lead_hours, _utcnow())
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
        if not args.collect_only:
            stage_guard_dataset_version(cy, con,
                                        dataset_version=args.dataset_version)

        if args.collect_only:
            cy.stage("forecasts", SKIPPED, reason="collect_only")
            cy.stage("signals", SKIPPED, reason="collect_only")
            cy.stage("paper", SKIPPED, reason="collect_only")
            cy.stage("observations", SKIPPED, reason="collect_only")
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
                        prediction_time=prediction_time)
            # The label BEFORE the settlement that consumes it, and after the
            # positions that name which labels are needed. Same ordering lesson as
            # `prediction_time` settled after collection: a stage that reads what
            # another writes has to run after it, not before.
            stage_observations(cy, con, dataset_version=args.dataset_version,
                               now=_utcnow())
            stage_settle(cy, con, dataset_version=args.dataset_version)

        stage_params(cy, root=args.store_root, session_id=session_id, args=args,
                     quantile_provenance=quantile_provenance,
                     timing=timing, dataset_version=args.dataset_version)
        stage_dump(cy, con, root=args.store_root, session_id=session_id,
                   dataset_version=args.dataset_version, since=cy.started_at,
                   # Every DECIDING cycle carries its own catalogue, so the
                   # replay reproduces it against the universe it actually
                   # decided on. `--dump-catalogue` survives as an override for a
                   # collect-only run someone wants snapshotted anyway.
                   dump_catalogue=(not args.collect_only) or bool(args.dump_catalogue))
    finally:
        con.close()

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
