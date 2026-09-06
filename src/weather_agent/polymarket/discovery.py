"""
weather_agent.polymarket.discovery — temperature-market discovery (Phase 2B)
============================================================================
STATUS: IMPLEMENTED. Authored WITHOUT Python execution — NOT tested/validated
here. Run on Hetzner (off the Enel firewall) to actually populate the lake.

WHAT IT DOES (scope 2B only — discovery + resolution + catalog normalization):
  * Pages gamma /events for the temperature tag (newest-first; optional
    date-bounding to cover market ages), READ-ONLY GET. Two populations
    (R26, docs/DISCOVERY_OPEN_MARKETS.md): closed=True (default, historical
    catalogue: closed=true) and closed=False (OPEN markets with a future endDate,
    the paper-mode feed: closed=false). Each mode has its OWN checkpoint key.
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
  * markets.available_at — TWO policies, chosen by the discovery mode (R26):
      - closed=True  (historical): stays NULL with available_at_confidence='UNKNOWN'.
        Gamma metadata does not tell us when a past market became knowable to an
        external agent; we do NOT equate it to createdAt/updatedAt/ingestion (#1)
        and we never invent retrospective availability.
      - closed=False (open markets): available_at = the UTC instant at which the
        HTTP request that RETURNED the market was issued (prospective capture:
        we observed it ourselves at that instant), available_at_confidence =
        'OBSERVED_AT_DISCOVERY'. On re-discovery the EARLIEST observed instant is
        kept (never overwritten by a later one).
    In both modes ingestion_timestamp remains a separate clock (our write time).
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

# markets.available_at_confidence for markets discovered while OPEN (closed=False):
# the value was OBSERVED by us at the request instant (prospective capture), not
# read from a gamma field and not inferred from createdAt/updatedAt. Closed-mode
# rows keep resolution.UNKNOWN. See docs/DISCOVERY_OPEN_MARKETS.md.
AVAILABLE_AT_OBSERVED = "OBSERVED_AT_DISCOVERY"
OPEN_CHECKPOINT_SUFFIX = ":open"


def checkpoint_key(dataset_version: str, closed: bool = True) -> str:
    """discovery_checkpoint key for one (dataset_version, mode). The closed
    (historical) mode keeps the bare dataset_version — byte-identical to the
    pre-R26 key, so existing checkpoints resume unchanged. The open mode appends
    ':open' so a paper-mode run under the same dataset_version can never be
    skipped because the same event id was already processed as CLOSED (and vice
    versa): an event seen open today is legitimately re-seen closed later."""
    return dataset_version if closed else f"{dataset_version}{OPEN_CHECKPOINT_SUFFIX}"


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
                # Phase 2D: verbatim gamma outcome name, position-aligned with
                # clobTokenIds[i] (same alignment already used for prices[i]). YES is
                # identified downstream ONLY by outcome_label == "Yes".
                "outcome_label": (str(outs[i]) if i < len(outs) else None),
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
                 run_id: str | None = None,
                 observed_at: str | None = None,
                 checkpoint_key: str | None = None) -> dict:
    """Apply provenance + UPSERT markets/outcomes/market_fee_schedule/data_quality
    for one gamma event, ATOMICALLY. The whole event is written inside ONE DuckDB
    transaction (BEGIN -> market -> outcomes -> fee schedule -> provenance/evidence
    -> COMMIT); if ANY step fails the ENTIRE event is ROLLED BACK, so an event can
    never be persisted partially. Idempotent. Returns counts. `fee_registry`
    (fee_regime -> fee_schedule_hash) persists the #3 fee-identity guard across
    events; pass a SHARED dict (discover does) to guard the whole dataset. Raises
    FeeScheduleConflict on a conflicting feeSchedule (no silent collapse) — which,
    like any failure, rolls the event back so the caller's checkpoint does NOT
    advance and the event can be retried on resume.

    R26 (open-market discovery):
      * `observed_at` — None (default, closed/historical mode): markets.available_at
        stays NULL / 'UNKNOWN' exactly as in 2B. An ISO-8601 UTC instant (open
        mode): the caller OBSERVED this event in a gamma response whose request was
        issued at that instant, so available_at = observed_at and
        available_at_confidence = 'OBSERVED_AT_DISCOVERY'. If the SAME market row
        (market_id, dataset_version, record_version) already carries a non-NULL
        available_at, the EARLIEST instant is kept: availability is 'first time we
        could have known', never 'last time we looked'.
      * `checkpoint_key` — key under which this event is marked in
        discovery_checkpoint; defaults to `dataset_version` (pre-R26 behaviour).
        discover() passes checkpoint_key(dataset_version, closed) so the closed
        and open modes never share a checkpoint."""
    from .. import database as db
    now = _now()
    discovered_at = discovered_at or now
    if checkpoint_key is None:
        checkpoint_key = dataset_version
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
            evidence = dict(rec["evidence"])
            evidence["available_at_policy"] = res.UNKNOWN
            if observed_at is not None:
                # R26 open mode: prospective capture. available_at is the instant we
                # OBSERVED the market (request instant), never createdAt/updatedAt/
                # ingestion. Keep the EARLIEST observation if this exact row was
                # already discovered open in an earlier run (re-discovery must not
                # push availability later).
                prior = db.query(
                    con,
                    "SELECT available_at FROM markets WHERE market_id = ? "
                    "AND dataset_version = ? AND record_version = ? "
                    "AND available_at IS NOT NULL",
                    [m["market_id"], dataset_version, 1])
                keep = observed_at
                if prior and prior[0]["available_at"] is not None:
                    prior_iso = _parse_ts(prior[0]["available_at"])
                    if prior_iso is not None and prior_iso < _parse_ts(observed_at):
                        keep = prior_iso
                m["available_at"] = keep
                m["available_at_confidence"] = AVAILABLE_AT_OBSERVED
                evidence["available_at_policy"] = AVAILABLE_AT_OBSERVED
                evidence["unknown_fields"] = [
                    f for f in evidence["unknown_fields"] if f != "available_at"]
                evidence["observed_fields"] = ["available_at"]
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
                                        "direct_fields": evidence["direct_fields"],
                                        "derived_fields": evidence["derived_fields"],
                                        "unknown_fields": evidence["unknown_fields"],
                                        # R26: which available_at policy produced
                                        # this row + the observed fields (open mode)
                                        "observed_fields": evidence.get("observed_fields", []),
                                        "available_at_policy": evidence["available_at_policy"],
                                        "observed_at": observed_at,
                                        "fee_confidence": evidence["fee_confidence"]},
                "resolution_quality": {k: evidence[k] for k in
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
        # R26: the mark is keyed by `checkpoint_key` (== dataset_version in closed
        # mode; dataset_version + ':open' in open mode) so the two modes never
        # skip each other's events.
        db.checkpoint_mark(con, checkpoint_key, str(event.get("id")), run_id)
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
                      max_retries: int = 4, closed: bool = True,
                      meta: dict | None = None) -> tuple[str, list]:
    """GET gamma /events. Returns (status, events). status in {OK, EMPTY,
    RATE_LIMITED, HTTP_ERROR, TIMEOUT, NETWORK_ERROR, PARSE_ERROR}. Never raises
    for ordinary API errors; the caller must treat any ERROR_STATUS as
    'UNVERIFIED - RATE LIMIT'/error and STOP (no silent inference, #5).

    R26:
      * `closed` selects the population: True -> closed=true (historical, the
        pre-R26 default), False -> closed=false (OPEN markets, future endDate).
        It is written into the query as params['closed'] ONLY when the caller did
        not set that key; an explicit params['closed'] that CONTRADICTS `closed`
        raises ValueError (never silently query the wrong population). `params`
        is not mutated.
      * `meta` (optional out-dict) receives the request provenance of the LAST
        attempt: {'requested_at': ISO-UTC instant immediately BEFORE the HTTP
        request that produced the returned status was sent, 'responded_at': ISO-UTC
        instant after the response/exception, 'attempts': n, 'params': as sent}.
        discover(closed=False) uses meta['requested_at'] as markets.available_at
        (prospective capture). The return type is unchanged for existing callers."""
    import time
    import requests
    url = f"{GAMMA}/events"
    want = "true" if closed else "false"
    params = dict(params or {})
    have = params.get("closed")
    if have is None:
        params["closed"] = want
    elif str(have).strip().lower() != want:
        raise ValueError(
            f"fetch_events_page: params['closed']={have!r} contradicts closed={closed}")
    if meta is None:
        meta = {}
    meta.update({"requested_at": None, "responded_at": None, "attempts": 0,
                 "params": dict(params)})
    for attempt in range(max_retries + 1):
        meta["attempts"] = attempt + 1
        meta["requested_at"] = _now()   # instant the request is issued (per attempt)
        try:
            r = session.get(url, params=params, timeout=timeout)
        except requests.Timeout:
            meta["responded_at"] = _now()
            if attempt < max_retries:
                time.sleep(2 ** attempt); continue
            return S_TIMEOUT, []
        except requests.RequestException:
            meta["responded_at"] = _now()
            if attempt < max_retries:
                time.sleep(2 ** attempt); continue
            return S_NETWORK, []
        meta["responded_at"] = _now()
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
             run_id: str | None = None,
             closed: bool = True) -> dict:
    """Paginate gamma /events (newest-first, optionally date-bounded) and ingest
    each event. Idempotent + resumable via `checkpoint` (set of processed event
    ids). On any error/rate-limit: record it and STOP (partial result returned,
    marked). Returns a run summary. USER-RUN on Hetzner.

    R26 `closed`:
      * True (default) — historical catalogue (gamma closed=true). Behaviour,
        query and checkpoint key are byte-identical to pre-R26: available_at NULL
        / 'UNKNOWN'.
      * False — OPEN markets (gamma closed=false, endDate in the future; the
        paper-mode feed). Every market is persisted with available_at = the UTC
        instant the page request that returned it was issued (prospective
        capture) and available_at_confidence='OBSERVED_AT_DISCOVERY'. Checkpoint
        key = dataset_version + ':open' (see checkpoint_key()), so open and closed
        runs under one dataset_version never skip each other's events. The
        summary carries 'closed' and 'checkpoint_key'.

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
    ckpt_key = checkpoint_key(dataset_version, closed)
    processed = db.checkpoint_load(con, ckpt_key) | (checkpoint or set())

    # `closed` is ALSO written into `base` (not only passed to fetch_events_page)
    # so dataset_versions.query_parameters records which population this
    # dataset_version was built from.
    base = {"tag_id": tag_id, "closed": ("true" if closed else "false"),
            "limit": page_limit}
    if newest_first:
        base["order"] = "endDate"; base["ascending"] = "false"
    if end_date_min:
        base["end_date_min"] = end_date_min
    if end_date_max:
        base["end_date_max"] = end_date_max

    summary = {"dataset_version": dataset_version, "pages": 0, "events": 0,
               "markets": 0, "outcomes": 0, "fees": 0, "status": S_OK,
               "errors": [], "stopped_early": False,
               "closed": closed, "checkpoint_key": ckpt_key}
    ensure_dataset_version(con, dataset_version, source="gamma", query_parameters=base)
    fee_registry: dict = {}   # shared across events for the #3 fee-identity guard

    for page in range(max_pages):
        params = dict(base, offset=page * page_limit)
        meta: dict = {}
        status, events = fetch_events_page(session, params, closed=closed, meta=meta)
        summary["pages"] += 1
        # Open mode: every event on this page becomes knowable to us at the instant
        # THIS page's request was issued (per page, not per run: page N+1 is
        # requested later than page N and its markets are stamped accordingly).
        observed_at = None if closed else meta.get("requested_at")
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
                                 fee_registry=fee_registry, run_id=run_id,
                                 observed_at=observed_at, checkpoint_key=ckpt_key)
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
