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

from weather_agent import collector, config, database as db, paper, store  # noqa: E402
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
#: each cycle would add ~500 KB × 8/day ≈ 120 MB/month of near-identical shards to
#: git. They are therefore dumped once a day, under `--dump-catalogue`, which the
#: daily workflow passes and the frequent collector does not.
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
    CREATE. `features.build_feature` takes `dataset_version` as a parameter and
    then never uses it: its `price_history` and `weather_forecasts` queries filter
    on market/station only (features.py, the two `latest_asof` calls), and
    `strategy_a`'s price-lineage guard repeats the omission. With ONE
    dataset_version in the database that is harmless, which is why session B's
    end-to-end run is not affected — measured 2026-09-09: every table carries only
    `backfill_2b_v1`.

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
        SELECT m.market_id, m.event_id, m.station, m.unit, m.rounding_rule,
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
                    universe: list[dict], model: str, session) -> dict:
    """Fetch the issued forecast for each station and attach M2's error quantiles.

    This stage is the seam with session B's lane. `weather_agent.weather` and
    `weather_agent.error_model` live on `feat/ingest-2b`; until that branch merges
    they are simply absent from `main`, and the stage reports SKIPPED with the
    module name rather than pretending to have forecasts. When the merge lands,
    this runs with no edit here.

    It is imported lazily and by name for exactly that reason: a missing module is
    a SCHEDULING fact (B has not merged yet), not a crash.

    HONEST LIMIT: this stage has NO `OK` branch and writes nothing, even when the
    import succeeds. Wiring the forecast pull and the M2 quantile attachment is
    session B's work, not a line to be flipped here — an earlier version of this
    docstring claimed it would "run with no edit here" once the merge landed, which
    was false. R24's precondition P3 is written against this reality."""
    try:
        from weather_agent import weather as weather_mod      # noqa: F401
        from weather_agent import error_model                 # noqa: F401
    except ImportError as exc:
        cy.stage("forecasts", SKIPPED, reason="ingestion_modules_not_on_this_branch",
                 missing=str(exc).split("'")[-2] if "'" in str(exc) else str(exc))
        return {"written": 0}

    stations = sorted({r["station"] for r in universe if r.get("station")})
    if not stations:
        cy.stage("forecasts", SKIPPED, reason="no_stations_in_universe")
        return {"written": 0}
    cy.stage("forecasts", SKIPPED,
             reason="wiring_owned_by_session_B_see_A-31",
             stations=len(stations), target_date=str(target_date), model=model)
    return {"written": 0}


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

    events = sorted({r["event_id"] for r in universe if r.get("event_id")})
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

        books = db.query(
            con,
            "SELECT book_snapshot FROM orderbook_snapshots "
            "WHERE token_id = ? AND dataset_version = ? AND collector_session_id = ? "
            "ORDER BY \"timestamp\" DESC LIMIT 1",
            [exec_token, dataset_version, session_id],
        )
        if not books:
            rejected += 1
            reasons["no_book_this_cycle"] = reasons.get("no_book_this_cycle", 0) + 1
            continue
        snap = books[0]["book_snapshot"]
        if isinstance(snap, str):
            snap = json.loads(snap)

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


def stage_settle(cy: Cycle, con, *, dataset_version: str) -> dict:
    """Settle open positions whose market has resolved.

    Deliberately unimplemented rather than approximated: settlement needs the
    realized label under the market's own SettlementOperator, and guessing a
    winner from the last traded price is exactly the shortcut that turns a paper
    ledger into fiction. Reports how many positions are waiting."""
    open_rows = db.query(
        con,
        "SELECT count(*) AS n FROM paper_trades "
        "WHERE dataset_version = ? AND exit_time IS NULL",
        [dataset_version],
    )
    n_open = int(open_rows[0]["n"]) if open_rows else 0
    cy.stage("settle", SKIPPED, reason="labels_not_wired_yet", positions_open=n_open)
    return {"positions_open": n_open}


def stage_params(cy: Cycle, *, root: str, session_id: str, args, timing: dict,
                 dataset_version: str) -> dict:
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
        "tau": args.tau,
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
    }
    out = store.write_shard([params], table="cycle_params", run_id=session_id,
                            root=root)
    cy.stage("params", OK, path=out["path"], tau=args.tau,
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
    which is why the filter is uniform instead of per-table."""
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
        cy.stage("dump:catalogue", SKIPPED, reason="daily_snapshot_only")
    cy.stage("dump", OK, tables=len(tables), rows_written=total)


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
    p.add_argument("--tau", type=float, default=None,
                   help="Signal threshold. Required for the signal/paper stages.")
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
                   help="Also snapshot markets/outcomes/fees. Once a day, not on "
                        "every collection cycle (see CATALOGUE_TABLES).")
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
        elif args.tau is None:
            cy.stage("signals", SKIPPED, reason="tau_not_provided_fail_closed")
            cy.stage("paper", SKIPPED, reason="tau_not_provided_fail_closed")
        else:
            stage_forecasts(cy, con, dataset_version=args.dataset_version,
                            target_date=target_date, universe=universe,
                            model=args.model, session=http)
            stage_signals(cy, con, dataset_version=args.dataset_version,
                          target_date=target_date, universe=universe,
                          model=args.model, tau=args.tau,
                          weather_sum_tolerance=args.weather_sum_tolerance,
                          market_sum_min=args.market_sum_min,
                          market_sum_max=args.market_sum_max,
                          prediction_time=prediction_time)
            params = paper.PaperParams(
                bankroll=args.bankroll, fixed_fraction=args.fixed_fraction,
                size_cap=args.size_cap, tau=args.tau, exit_mode=args.exit_mode,
                x_exec=args.x_exec,
            )
            stage_paper(cy, con, dataset_version=args.dataset_version,
                        session_id=session_id, params=params,
                        prediction_time=prediction_time)
            stage_settle(cy, con, dataset_version=args.dataset_version)

        stage_params(cy, root=args.store_root, session_id=session_id, args=args,
                     timing=timing, dataset_version=args.dataset_version)
        stage_dump(cy, con, root=args.store_root, session_id=session_id,
                   dataset_version=args.dataset_version, since=cy.started_at,
                   dump_catalogue=bool(args.dump_catalogue))
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
