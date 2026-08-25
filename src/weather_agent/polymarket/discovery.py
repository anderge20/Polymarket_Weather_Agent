"""
weather_agent.polymarket.discovery — temperature-market discovery (Phase 2B)
============================================================================
STATUS: IMPLEMENTED. Authored WITHOUT Python execution — NOT tested/validated
here. Run on Hetzner (off the Enel firewall) to actually populate the lake.

WHAT IT DOES (scope 2B only — discovery + resolution + catalog normalization):
  * Pages gamma /events for the temperature tag (newest-first; optional
    date-bounding to cover market ages), READ-ONLY GET.
  * For each event/market: extracts metadata, parses the per-market resolution
    chain (resolution.py) and fee/tick/min (fees.py), and UPSERTs markets +
    outcomes + market_fee_schedule with full provenance and dataset_version.
  * Writes a per-market data_quality EVIDENCE row (endpoint, params, fetched_at,
    DIRECT vs DERIVED vs UNKNOWN fields, resolution confidence).
  * Idempotent (upsert on full PKs) and resumable (checkpoint of processed
    event ids). On any gamma error/rate-limit it STOPS and records
    "UNVERIFIED - RATE LIMIT"/error — it NEVER fills gaps by silent inference (#5).

NOT in 2B: feature builder, Strategy A, models, backtest, paper, execution, L2.

SOURCE/PROVENANCE SEMANTICS (documented in PHASE_2B_MARKET_DISCOVERY.md):
  * source = 'gamma'
  * source_timestamp = market.createdAt (when the market record was CREATED at the
    source). This is provenance, NOT an availability guarantee.
  * ingestion_timestamp / discovered_at = our clock at write time.
  * markets.available_at stays NULL with available_at_confidence='UNKNOWN' — gamma
    metadata does not tell us when the market became knowable/observable to an
    external agent; we do NOT equate it to createdAt/updatedAt/ingestion (#1).
  * markets.source_timestamps = verbatim JSON of ALL gamma timestamps for the row.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..config import GAMMA, TEMP_TAG_ID
from . import fees as fees_mod
from . import resolution as res

# request status taxonomy (gamma only in 2B)
S_OK = "OK"
S_EMPTY = "EMPTY"
S_RATE_LIMITED = "RATE_LIMITED"
S_HTTP_ERROR = "HTTP_ERROR"
S_TIMEOUT = "TIMEOUT"
S_NETWORK = "NETWORK_ERROR"
S_PARSE = "PARSE_ERROR"
ERROR_STATUSES = (S_RATE_LIMITED, S_HTTP_ERROR, S_TIMEOUT, S_NETWORK, S_PARSE)


class FeeScheduleConflict(Exception):
    """#3 GUARD: raised when, within one dataset_version, the SAME fee_regime is
    seen with a DIFFERENT feeSchedule. Discovery STOPS rather than silently
    collapsing the two configs onto one market_fee_schedule row — that situation
    requires a fee_schedule_hash identity. Treated as a DATA_ERROR by discover()."""

# Fields written to markets that come DIRECT from gamma vs DERIVED (parsed/mapped)
# vs UNKNOWN (not available from gamma discovery). Documented in each evidence row.
DIRECT_FIELDS = (
    "market_id", "condition_id", "event_id", "slug", "question", "tag_ids",
    "open_time", "close_time", "source_timestamp", "source_timestamps",
    "tick_size", "min_order_size",
)
DERIVED_FIELDS = (
    "city", "station", "station_identifier", "resolution_source", "unit",
    "rounding_rule", "measurement_rule", "resolution_timestamp",
    "winning_outcome", "fee_regime",
)
UNKNOWN_FIELDS = (
    "available_at", "settlement_timestamp", "last_traded_time",
    "last_meaningful_market_time", "daily_high_time", "data_start", "data_end",
    "available_resolution",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_ts(v: Any) -> str | None:
    """Normalise a gamma timestamp to an ISO-8601 UTC string (DuckDB casts it to
    TIMESTAMPTZ). Handles the THREE gamma formats seen live:
      '2026-08-20T12:00:00Z', '2025-12-28T11:00:18.867429Z' (micros+Z),
      '2025-12-30 09:09:31+00' (space + '+00'), and date-only '2026-08-16'."""
    if v is None:
        return None
    import re
    s = str(v).strip()
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):          # date-only
        s = s + "T00:00:00+00:00"
    if re.match(r"\d{4}-\d{2}-\d{2} ", s):             # space separator
        s = s.replace(" ", "T", 1)
    s = re.sub(r"([+-]\d{2})$", r"\1:00", s)           # '+00' -> '+00:00'
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return s  # last resort: normalized string (DuckDB may still cast/complain)


def _tag_ids(event: dict) -> list:
    tags = event.get("tags") or []
    ids = [t.get("id") for t in tags if isinstance(t, dict) and t.get("id") is not None]
    return ids or [str(TEMP_TAG_ID)]


# =============================================================================
# pure: build the row payloads for one gamma event (no DB, no network)
# =============================================================================
def build_market_records(event: dict) -> list[dict]:
    """Return one record per market (band) in the event. Each record has:
      {'market': {...}, 'outcomes': [...], 'fee': {...}, 'evidence': {...}}
    No provenance/dataset_version yet — those are applied by ingest_event()."""
    records: list[dict] = []
    event_id = str(event.get("id")) if event.get("id") is not None else None
    event_winning_band = res.event_winning_band(event.get("markets") or [])

    for m in event.get("markets") or []:
        rule = res.discover_rule(m, event, resolution_timestamp=_parse_ts(m.get("umaEndDate")))
        fee = fees_mod.map_fees(m)
        tick, min_sz = fees_mod.map_tick_min(m)

        raw_ts = {k: m.get(k) for k in
                  ("createdAt", "updatedAt", "startDate", "endDate", "closedTime",
                   "umaEndDate", "acceptingOrdersTimestamp") if k in m}

        market_row = {
            "market_id": str(m.get("id")) if m.get("id") is not None else None,
            "condition_id": m.get("conditionId"),
            "event_id": event_id,
            "slug": m.get("slug"),
            "question": m.get("question"),
            "city": rule.city,
            "station": rule.station,
            "station_identifier": rule.station_identifier,
            "resolution_source": rule.resolution_source,
            "unit": rule.unit,
            "rounding_rule": rule.rounding_rule,
            "measurement_rule": rule.measurement_rule,
            "resolution_timestamp": rule.resolution_timestamp,      # umaEndDate = formal_resolution_time (VERIFIED)
            "settlement_timestamp": None,                           # settlement_time: UNKNOWN in 2B (not distinctly exposed)
            "last_traded_time": None,                               # UNKNOWN in 2B (no trade data in discovery)
            "winning_outcome": rule.winning_outcome,                # this market's resolved side (exact-numeric)
            "open_time": _parse_ts(m.get("startDate")),
            "close_time": _parse_ts(m.get("closedTime")),
            "available_resolution": None,                           # UNKNOWN in 2B (price-capability flag)
            "fee_regime": fee["fee_regime"],
            "tick_size": tick,
            "min_order_size": min_sz,
            "tag_ids": _tag_ids(event),
            "source_timestamp": _parse_ts(m.get("createdAt")),      # provenance, NOT availability
            "source_timestamps": raw_ts,                            # verbatim gamma timestamps
            "available_at": None,                                   # UNKNOWN (see #1)
            "available_at_confidence": res.UNKNOWN,
        }

        outs = res.jf(m.get("outcomes"))
        prices = res.jf(m.get("outcomePrices"))
        tokens = res.jf(m.get("clobTokenIds"))
        lo, hi = res.parse_band(m.get("groupItemTitle") or m.get("question"), rule.unit)
        outcome_rows = []
        for i, tok in enumerate(tokens):
            # exact-numeric (never startswith): this token resolved iff its price == 1
            try:
                is_winner = (i < len(prices) and float(str(prices[i]).strip()) == 1.0)
            except (TypeError, ValueError):
                is_winner = False
            outcome_rows.append({
                "market_id": market_row["market_id"],
                "token_id": str(tok),
                "band_label": m.get("groupItemTitle"),
                "lo": lo,
                "hi": hi,
                "outcome_index": i,
                "is_winner": bool(is_winner),
            })

        fee_row = {
            "fee_regime": fee["fee_regime"],
            "taker_fee": fee["taker_fee"],
            "maker_rebate": fee["maker_rebate"],
            "effective_from": fee["effective_from"],
            "effective_to": fee["effective_to"],
            "fee_status": fee["fee_status"],
            "raw_fee_fields": fee["raw_fee_fields"],
        }

        uma_statuses = res.jf(m.get("umaResolutionStatuses"))
        evidence = {
            "direct_fields": list(DIRECT_FIELDS),
            "derived_fields": list(DERIVED_FIELDS),
            "unknown_fields": list(UNKNOWN_FIELDS),
            "resolution_confidence": rule.confidence,
            "resolution_warnings": rule.warnings,
            "fee_confidence": fee["confidence"],
            "uma_resolution_status": m.get("umaResolutionStatus"),
            "uma_resolution_statuses": uma_statuses,
            "disputed": any("disput" in str(s).lower() for s in uma_statuses),
            "event_winning_band": event_winning_band,
        }

        records.append({"market": market_row, "outcomes": outcome_rows,
                        "fee": fee_row, "evidence": evidence})
    return records


# =============================================================================
# DB writes (idempotent upserts with provenance)
# =============================================================================
def ensure_dataset_version(con, dataset_version: str, *, source: str = "gamma",
                           query_parameters: dict | None = None,
                           description: str | None = None,
                           code_version: str | None = None) -> None:
    from .. import database as db
    db.upsert(con, "dataset_versions", {
        "version": dataset_version,
        "created_at": _now(),
        "source": source,
        "query_parameters": query_parameters or {},
        "description": description or "phase2b market discovery",
        "code_version": code_version,
        "git_commit": None,
    }, ["version"])


def ingest_event(con, event: dict, dataset_version: str, *,
                 endpoint: str = f"{GAMMA}/events", params: dict | None = None,
                 discovered_at: str | None = None,
                 fee_registry: dict | None = None,
                 run_id: str | None = None) -> dict:
    """Apply provenance + UPSERT markets/outcomes/market_fee_schedule/data_quality
    for one gamma event, ATOMICALLY. The whole event is written inside ONE DuckDB
    transaction (BEGIN -> market -> outcomes -> fee schedule -> provenance/evidence
    -> COMMIT); if ANY step fails the ENTIRE event is ROLLED BACK, so an event can
    never be persisted partially. Idempotent. Returns counts. `fee_registry`
    (fee_regime -> fee_schedule_hash) persists the #3 fee-identity guard across
    events; pass a SHARED dict (discover does) to guard the whole dataset. Raises
    FeeScheduleConflict on a conflicting feeSchedule (no silent collapse) — which,
    like any failure, rolls the event back so the caller's checkpoint does NOT
    advance and the event can be retried on resume."""
    from .. import database as db
    now = _now()
    discovered_at = discovered_at or now
    counts = {"markets": 0, "outcomes": 0, "fees": 0, "evidence": 0}
    if fee_registry is None:
        fee_registry = {}

    # Build the (pure) row payloads BEFORE opening a transaction so a parse error
    # never leaves a dangling transaction.
    records = build_market_records(event)

    # ATOMIC per event: market -> outcomes -> fee schedule -> provenance/evidence,
    # all inside ONE DuckDB transaction. If ANY operation fails (including a
    # FeeScheduleConflict) the ENTIRE event is ROLLED BACK — an event is NEVER
    # persisted partially. The caller (discover) advances its checkpoint ONLY
    # after this returns, i.e. AFTER COMMIT. On rollback we also revert the
    # fee_regime keys this event added to the SHARED registry, so a later resume
    # can retry the event cleanly (and re-detect a genuine conflict).
    registry_added: list[str] = []
    con.execute("BEGIN TRANSACTION;")
    try:
        for rec in records:
            m = dict(rec["market"])
            m.update({"discovered_at": discovered_at, "source": "gamma",
                      "ingestion_timestamp": now, "dataset_version": dataset_version,
                      "record_version": 1})
            db.upsert(con, "markets", m,
                      ["market_id", "dataset_version", "record_version"])
            counts["markets"] += 1

            for o in rec["outcomes"]:
                row = dict(o)
                row.update({"source": "gamma", "source_timestamp": m["source_timestamp"],
                            "ingestion_timestamp": now, "dataset_version": dataset_version,
                            "record_version": 1})
                db.upsert(con, "outcomes", row,
                          ["token_id", "dataset_version", "record_version"])
                counts["outcomes"] += 1

            fee = rec["fee"]
            fee_regime = fee["fee_regime"]
            sched_hash = fees_mod.fee_schedule_hash(fee.get("raw_fee_fields"))
            if fee_regime in fee_registry:
                if fee_registry[fee_regime] != sched_hash:
                    # #3 GUARD: same fee_regime, DIFFERENT feeSchedule within this
                    # dataset -> STOP. Never upsert silently onto one row. Raising
                    # here triggers the FULL-event ROLLBACK below.
                    raise FeeScheduleConflict(
                        f"fee_regime {fee_regime!r} in dataset_version {dataset_version!r} "
                        f"seen with two DIFFERENT feeSchedules this run "
                        f"({fee_registry[fee_regime][:8]} != {sched_hash[:8]}); a "
                        f"fee_schedule_hash identity is required.")
            else:
                # First time this regime is seen this run: also guard against a
                # conflicting row already persisted (e.g. a prior / resumed run).
                existing = db.query(
                    con,
                    "SELECT raw_fee_fields FROM market_fee_schedule "
                    "WHERE fee_regime = ? AND dataset_version = ? LIMIT 1",
                    [fee_regime, dataset_version])
                if existing:
                    existing_hash = fees_mod.fee_schedule_hash(existing[0].get("raw_fee_fields"))
                    if existing_hash != sched_hash:
                        raise FeeScheduleConflict(
                            f"fee_regime {fee_regime!r} in dataset_version {dataset_version!r} "
                            f"already stored with a DIFFERENT feeSchedule "
                            f"({existing_hash[:8]} != {sched_hash[:8]}); a "
                            f"fee_schedule_hash identity is required.")
                fee_registry[fee_regime] = sched_hash
                registry_added.append(fee_regime)
                frow = dict(fee)
                frow.pop("confidence", None)
                frow.update({"source": "gamma", "source_timestamp": m["source_timestamp"],
                             "ingestion_timestamp": now, "dataset_version": dataset_version,
                             "record_version": 1})
                db.upsert(con, "market_fee_schedule", frow,
                          ["fee_regime", "dataset_version", "record_version"])
                counts["fees"] += 1

            db.upsert(con, "data_quality", {
                "ref": m["market_id"],
                "market_data_quality": {"endpoint": endpoint, "params": params or {},
                                        "fetched_at": now,
                                        "direct_fields": rec["evidence"]["direct_fields"],
                                        "derived_fields": rec["evidence"]["derived_fields"],
                                        "unknown_fields": rec["evidence"]["unknown_fields"],
                                        "fee_confidence": rec["evidence"]["fee_confidence"]},
                "resolution_quality": {k: rec["evidence"][k] for k in
                                       ("resolution_confidence", "resolution_warnings",
                                        "uma_resolution_status", "uma_resolution_statuses",
                                        "disputed", "event_winning_band")},
                "weather_data_quality": None,
                "orderbook_quality": None,
                "checked_at": now, "source": "gamma", "ingestion_timestamp": now,
                "dataset_version": dataset_version, "record_version": 1,
            }, ["ref", "dataset_version"])
            counts["evidence"] += 1

        # Phase 2C: the checkpoint mark is the LAST write INSIDE this same
        # transaction, so COMMIT persists {event rows + mark} atomically. A crash
        # before COMMIT rolls back BOTH (DuckDB WAL recovery) and the event is
        # retried on the next resume; there is no window where they disagree.
        db.checkpoint_mark(con, dataset_version, str(event.get("id")), run_id)
        con.execute("COMMIT;")
    except Exception:
        # FULL rollback of the event; revert this event's registry additions so a
        # resume can retry it. Re-raise (FeeScheduleConflict or any error) so
        # discover() records the failure and does NOT advance the checkpoint.
        con.execute("ROLLBACK;")
        for k in registry_added:
            fee_registry.pop(k, None)
        raise

    return counts


# =============================================================================
# network (gamma only; lazy requests import) + orchestration
# =============================================================================
def fetch_events_page(session, params: dict, *, timeout: int = 30,
                      max_retries: int = 4) -> tuple[str, list]:
    """GET gamma /events. Returns (status, events). status in {OK, EMPTY,
    RATE_LIMITED, HTTP_ERROR, TIMEOUT, NETWORK_ERROR, PARSE_ERROR}. Never raises
    for ordinary API errors; the caller must treat any ERROR_STATUS as
    'UNVERIFIED - RATE LIMIT'/error and STOP (no silent inference, #5)."""
    import time
    import requests
    url = f"{GAMMA}/events"
    for attempt in range(max_retries + 1):
        try:
            r = session.get(url, params=params, timeout=timeout)
        except requests.Timeout:
            if attempt < max_retries:
                time.sleep(2 ** attempt); continue
            return S_TIMEOUT, []
        except requests.RequestException:
            if attempt < max_retries:
                time.sleep(2 ** attempt); continue
            return S_NETWORK, []
        if r.status_code == 429:
            ra = r.headers.get("Retry-After")
            try:
                delay = float(ra) if ra is not None else 2 ** attempt
            except ValueError:
                delay = 2 ** attempt
            if attempt < max_retries:
                time.sleep(min(delay, 60)); continue
            return S_RATE_LIMITED, []
        if r.status_code != 200:
            return S_HTTP_ERROR, []
        try:
            data = r.json()
        except Exception:
            return S_PARSE, []
        events = data if isinstance(data, list) else (data.get("data") or [])
        return (S_OK if events else S_EMPTY), events
    return S_RATE_LIMITED, []


def discover(con, dataset_version: str, *, tag_id: int = TEMP_TAG_ID,
             page_limit: int = 100, max_pages: int = 50,
             end_date_min: str | None = None, end_date_max: str | None = None,
             newest_first: bool = True, session=None,
             checkpoint: set[str] | None = None,
             run_id: str | None = None) -> dict:
    """Paginate gamma /events (newest-first, optionally date-bounded) and ingest
    each event. Idempotent + resumable via `checkpoint` (set of processed event
    ids). On any error/rate-limit: record it and STOP (partial result returned,
    marked). Returns a run summary. USER-RUN on Hetzner.

    NOTE: `session` must be a requests.Session (created by the caller so this
    module needs no network at import time)."""
    if session is None:
        import requests
        session = requests.Session()
        session.headers.update({"User-Agent": "weather-agent-2b-discovery/1.0"})
    from .. import database as db
    if run_id is None:
        run_id = f"disc_{_now()}"
    # Phase 2C: the PERSISTED checkpoint (DuckDB discovery_checkpoint) is the source
    # of truth for resume — a fresh process loads it here. The in-memory `processed`
    # set is a mirror + accepts any caller-provided ids (backward compatible).
    processed = db.checkpoint_load(con, dataset_version) | (checkpoint or set())

    base = {"tag_id": tag_id, "closed": "true", "limit": page_limit}
    if newest_first:
        base["order"] = "endDate"; base["ascending"] = "false"
    if end_date_min:
        base["end_date_min"] = end_date_min
    if end_date_max:
        base["end_date_max"] = end_date_max

    summary = {"dataset_version": dataset_version, "pages": 0, "events": 0,
               "markets": 0, "outcomes": 0, "fees": 0, "status": S_OK,
               "errors": [], "stopped_early": False}
    ensure_dataset_version(con, dataset_version, source="gamma", query_parameters=base)
    fee_registry: dict = {}   # shared across events for the #3 fee-identity guard

    for page in range(max_pages):
        params = dict(base, offset=page * page_limit)
        status, events = fetch_events_page(session, params)
        summary["pages"] += 1
        if status in ERROR_STATUSES:
            # #5: do NOT infer; mark and stop.
            summary["status"] = status
            summary["stopped_early"] = True
            summary["errors"].append({"page": page, "params": params,
                                      "status": f"UNVERIFIED - {status}"})
            break
        if status == S_EMPTY or not events:
            break
        for ev in events:
            eid = str(ev.get("id"))
            if eid in processed:
                continue
            try:
                c = ingest_event(con, ev, dataset_version,
                                 endpoint=f"{GAMMA}/events", params=params,
                                 fee_registry=fee_registry, run_id=run_id)
            except FeeScheduleConflict as exc:
                # #3: DATA_ERROR — stop; do NOT infer/collapse.
                summary["status"] = "DATA_ERROR"
                summary["stopped_early"] = True
                summary["errors"].append({"event": eid,
                                          "status": "DATA_ERROR - fee_schedule_conflict",
                                          "detail": str(exc)})
                return summary
            summary["events"] += 1
            summary["markets"] += c["markets"]
            summary["outcomes"] += c["outcomes"]
            summary["fees"] += c["fees"]
            # In-memory mirror only; the DURABLE checkpoint mark was already written
            # inside ingest_event's transaction (atomic with the rows). A rolled-back
            # event raised above and never reaches this line, so neither the mark nor
            # this mirror entry exist → it is retried on the next resume.
            processed.add(eid)
            if checkpoint is not None:
                # backward-compat: if the caller passed an in-memory `checkpoint` set,
                # keep it in sync after a successful (committed) ingest — exactly the
                # pre-2C behaviour. The persisted table remains the source of truth.
                checkpoint.add(eid)
        if len(events) < page_limit:
            break
    return summary
