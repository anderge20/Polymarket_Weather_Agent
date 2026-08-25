"""
weather_agent.database  —  DuckDB data layer (Phase 2A)
=======================================================
STATUS: IMPLEMENTED. **Authored in an environment WITHOUT Python** — it has NOT
been executed, so NOTHING here is "tested" or "validated". Run the pytest suite
on the Hetzner box (see PHASE_2A_DATA_MODEL.md) to move components from
IMPLEMENTED -> TESTED -> VALIDATED.

WHAT THIS MODULE PROVIDES
  * connect()            open/create the DuckDB file (parent dir auto-created).
  * init_db()            idempotent schema creation via ordered, idempotent
                         migrations; records applied versions in schema_version.
  * insert / insert_many / upsert / query / query_df   basic helpers.
  * query_asof / latest_asof                          AS-OF (no-look-ahead) reads.
  * next_record_version / add_provenance              versioning/provenance helpers.

DESIGN PRINCIPLES (encoded from the 1.5B conclusions)
  * PROVENANCE ON EVERY FACT: source, source_timestamp, ingestion_timestamp,
    dataset_version, record_version. Goal: recompute a backtest months later and
    know EXACTLY which data version produced it.
  * APPEND-ONLY, VERSIONED FACTS: revisioned fact tables put
    (dataset_version, record_version) IN the primary key, so corrections are new
    rows, never destructive overwrites. "Current" = highest (dataset_version,
    record_version) per natural key; reproducibility = filter by dataset_version.
  * PRICE IS INDICATIVE, NEVER EXECUTABLE: price_history.indicative_price +
    price_semantics (CHECK forbids an 'EXECUTABLE' value) + price_source +
    source_window (DIRECT|DERIVED). fidelity>=1 (native 1-min); interval=max
    is a backfill anti-pattern (documented, enforced by convention).
  * AS-OF EVERYTHING: every fact carries an explicit time column so queries can
    reconstruct exactly what was knowable at a given instant.
  * FEES ARE EPOCH-DEPENDENT: market_fee_schedule with fee_status (UNKNOWN
    allowed); never assume 0.
  * ORDER BOOK / TRADES ARE FORWARD-ONLY: tables exist for the live collector;
    no historical L2 exists.

NOTE ON CONSTRAINTS: PRIMARY KEY, UNIQUE and CHECK constraints are used. Foreign
keys are documented as *logical* relationships (see PHASE_2A_DATA_MODEL.md) but
are NOT enforced at the DB level, to keep partial/append ingestion order-free.
All human timestamps are stored as TIMESTAMPTZ (UTC).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from .config import DB_PATH

SCHEMA_VERSION = 2

# Standard provenance columns present on every fact/derived table.
PROVENANCE_COLUMNS = (
    "source", "source_timestamp", "ingestion_timestamp",
    "dataset_version", "record_version",
)

# Tables that must carry the full provenance quintet (used by tests).
FACT_TABLES = (
    "markets", "outcomes", "price_history", "orderbook_snapshots", "trades",
    "weather_forecasts", "weather_observations", "weather_errors",
    "features", "predictions", "signals",
)

# All application tables (excludes the schema_version meta table).
ALL_TABLES = (
    "dataset_versions", "market_fee_schedule", "markets", "outcomes",
    "price_history", "orderbook_snapshots", "trades", "weather_forecasts",
    "weather_observations", "weather_errors", "features", "predictions",
    "signals", "paper_trades", "backtest_results", "markets_excluded",
    "data_quality",
)

# Canonical AS-OF column per table: the column the as-of engine filters on to
# reconstruct what was knowable at an instant. For weather this is `available_at`
# (when the datum was AVAILABLE at the source) — NEVER `ingestion_timestamp`
# (when WE happened to ingest it), and NEVER `observation_time`/`daily_high_time`
# (when the weather physically occurred).
AS_OF_COLUMNS = {
    "price_history": "observation_time",
    "orderbook_snapshots": "timestamp",
    "trades": "timestamp",
    "weather_forecasts": "available_at",
    "weather_observations": "available_at",
    "features": "prediction_time",
    "predictions": "timestamp",
    "signals": "timestamp",
}


def _asof_column(table: str) -> str:
    """The canonical as-of column for `table` (raises if none is registered)."""
    try:
        return AS_OF_COLUMNS[table]
    except KeyError:
        raise ValueError(
            f"no canonical as-of column registered for {table!r}; pass time_col explicitly"
        )


# =============================================================================
# DDL  (all statements are idempotent: IF NOT EXISTS)
# =============================================================================
_SEQUENCES = [
    "CREATE SEQUENCE IF NOT EXISTS seq_paper_trades START 1;",
]

_DDL: list[str] = [
    # ---- meta: dataset version registry (the reproducibility anchor) ----------
    """
    CREATE TABLE IF NOT EXISTS dataset_versions (
        version          VARCHAR PRIMARY KEY,     -- e.g. 'ds_2026-08-20_gamma_v1'
        created_at       TIMESTAMPTZ DEFAULT now(),
        source           VARCHAR,                 -- pipeline/component that created it
        query_parameters JSON,                    -- exact query params of the pull
        description      VARCHAR,
        code_version     VARCHAR,                 -- git commit / code tag
        git_commit       VARCHAR
    );
    """,

    # ---- fees (epoch-dependent; NEVER assume 0) ------------------------------
    """
    CREATE TABLE IF NOT EXISTS market_fee_schedule (
        fee_regime          VARCHAR,
        taker_fee           DOUBLE,               -- NULL when fee_status='UNKNOWN'
        maker_rebate        DOUBLE,
        effective_from      TIMESTAMPTZ,
        effective_to        TIMESTAMPTZ,
        fee_status          VARCHAR DEFAULT 'UNKNOWN',
        source              VARCHAR,
        source_timestamp    TIMESTAMPTZ,
        ingestion_timestamp TIMESTAMPTZ,
        dataset_version     VARCHAR,
        record_version      INTEGER DEFAULT 1,
        CHECK (fee_status IN ('KNOWN','UNKNOWN','ESTIMATED','DEPRECATED')),
        -- versioned identity so a historical fee regime version is never lost
        PRIMARY KEY (fee_regime, dataset_version, record_version)
    );
    """,

    # ---- markets: catalog (§24) + per-market resolution discovery ------------
    """
    CREATE TABLE IF NOT EXISTS markets (
        market_id                   VARCHAR,
        condition_id                VARCHAR,
        event_id                    VARCHAR,
        slug                        VARCHAR,
        question                    VARCHAR,
        city                        VARCHAR,
        station                     VARCHAR,      -- discovered station name
        station_identifier          VARCHAR,      -- discovered ICAO (e.g. EGLC)
        resolution_source           VARCHAR,      -- Wunderground history URL
        unit                        VARCHAR,      -- 'C' | 'F' | 'UNKNOWN'
        rounding_rule               VARCHAR,      -- 'whole degree' | 'tenths' | ...
        resolution_timestamp        TIMESTAMPTZ,  -- formal_resolution_time
        settlement_timestamp        TIMESTAMPTZ,  -- settlement_time
        winning_outcome             VARCHAR,
        open_time                   TIMESTAMPTZ,
        close_time                  TIMESTAMPTZ,
        last_traded_time            TIMESTAMPTZ,
        last_meaningful_market_time TIMESTAMPTZ,
        daily_high_time             TIMESTAMPTZ,
        data_start                  TIMESTAMPTZ,
        data_end                    TIMESTAMPTZ,
        available_resolution        VARCHAR,      -- native_1min | coarse | none | unknown
        fee_regime                  VARCHAR,      -- -> market_fee_schedule.fee_regime
        tick_size                   DOUBLE,       -- from the real market; NULL if unknown (NO hardcoded default)
        min_order_size              DOUBLE,       -- from the real market; NULL if unknown (NO hardcoded default)
        tag_ids                     JSON,
        discovered_at               TIMESTAMPTZ,  -- business event: first discovery
        source                      VARCHAR,
        source_timestamp            TIMESTAMPTZ,
        ingestion_timestamp         TIMESTAMPTZ,
        dataset_version             VARCHAR,
        record_version              INTEGER DEFAULT 1,
        CHECK (unit IS NULL OR unit IN ('C','F','UNKNOWN')),
        CHECK (available_resolution IS NULL OR
               available_resolution IN ('native_1min','coarse','none','unknown')),
        PRIMARY KEY (market_id, dataset_version, record_version)
    );
    """,

    # ---- outcomes: the Yes/No tokens of each band-market ----------------------
    """
    CREATE TABLE IF NOT EXISTS outcomes (
        market_id           VARCHAR,
        token_id            VARCHAR,              -- clobTokenId
        band_label          VARCHAR,
        lo                  DOUBLE,               -- NULL = open-ended low ('or below')
        hi                  DOUBLE,               -- NULL = open-ended high ('or higher')
        outcome_index       INTEGER,              -- 0/1 (Yes/No)
        is_winner           BOOLEAN,
        source              VARCHAR,
        source_timestamp    TIMESTAMPTZ,
        ingestion_timestamp TIMESTAMPTZ,
        dataset_version     VARCHAR,
        record_version      INTEGER DEFAULT 1,
        PRIMARY KEY (token_id, dataset_version, record_version)
    );
    """,

    # ---- price_history: INDICATIVE only, never executable --------------------
    """
    CREATE TABLE IF NOT EXISTS price_history (
        observation_time    TIMESTAMPTZ,          -- market-time of the point (UTC)
        market_id           VARCHAR,
        token_id            VARCHAR,
        indicative_price    DOUBLE,               -- 0..1, INDICATIVE (never executable)
        price_semantics     VARCHAR DEFAULT 'MIDPOINT_ESTIMATED',
        price_source        VARCHAR DEFAULT 'CLOB_PRICES_HISTORY',
        fidelity            INTEGER,              -- minutes; 1 = native
        source_window       VARCHAR,              -- DIRECT | DERIVED
        fetched_at          TIMESTAMPTZ,
        source              VARCHAR,
        source_timestamp    TIMESTAMPTZ,
        ingestion_timestamp TIMESTAMPTZ,
        dataset_version     VARCHAR,
        record_version      INTEGER DEFAULT 1,
        CHECK (price_semantics IN ('MIDPOINT_ESTIMATED','INDICATIVE',
               'LAST_TRADE_INDICATIVE','NEAREST_TRADE_INDICATIVE','UNKNOWN')),
        CHECK (source_window IS NULL OR source_window IN ('DIRECT','DERIVED')),
        CHECK (fidelity IS NULL OR fidelity >= 1),
        PRIMARY KEY (token_id, observation_time, dataset_version, record_version)
    );
    """,

    # ---- orderbook_snapshots: FORWARD-ONLY (live collector) ------------------
    """
    CREATE TABLE IF NOT EXISTS orderbook_snapshots (
        "timestamp"         TIMESTAMPTZ,
        market_id           VARCHAR,
        token_id            VARCHAR,
        best_bid            DOUBLE,
        best_ask            DOUBLE,
        mid                 DOUBLE,
        spread              DOUBLE,
        bid_depth_1         DOUBLE,
        bid_depth_5         DOUBLE,
        bid_depth_10        DOUBLE,
        ask_depth_1         DOUBLE,
        ask_depth_5         DOUBLE,
        ask_depth_10        DOUBLE,
        imbalance           DOUBLE,
        book_snapshot       JSON,
        collected_at         TIMESTAMPTZ,         -- when OUR collector captured it
        collector_session_id VARCHAR,             -- forward-only provenance: which collector run
        collector_started_at TIMESTAMPTZ,         -- when that collector run began
        source              VARCHAR,
        source_timestamp    TIMESTAMPTZ,
        ingestion_timestamp TIMESTAMPTZ,
        dataset_version     VARCHAR,
        record_version      INTEGER DEFAULT 1,
        PRIMARY KEY (token_id, "timestamp", dataset_version, record_version)
    );
    """,

    # ---- trades: FORWARD-ONLY (live collector / data-api) --------------------
    """
    CREATE TABLE IF NOT EXISTS trades (
        "timestamp"         TIMESTAMPTZ,
        market_id           VARCHAR,
        token_id            VARCHAR,
        price               DOUBLE,
        size                DOUBLE,
        side                VARCHAR,              -- BUY | SELL
        trade_id            VARCHAR,
        fetched_at          TIMESTAMPTZ,
        collected_at         TIMESTAMPTZ,         -- when OUR collector captured it
        collector_session_id VARCHAR,             -- forward-only provenance: which collector run
        collector_started_at TIMESTAMPTZ,         -- when that collector run began
        source              VARCHAR,
        source_timestamp    TIMESTAMPTZ,
        ingestion_timestamp TIMESTAMPTZ,
        dataset_version     VARCHAR,
        record_version      INTEGER DEFAULT 1,
        CHECK (side IS NULL OR side IN ('BUY','SELL')),
        PRIMARY KEY (trade_id, dataset_version, record_version)
    );
    """,

    # ---- weather_forecasts: issued forecasts (issue_time = no-look-ahead anchor)
    """
    CREATE TABLE IF NOT EXISTS weather_forecasts (
        issue_time          TIMESTAMPTZ,          -- when the forecast was issued
        forecast_run        VARCHAR,              -- e.g. '00z' / '12z'
        target_date         DATE,
        city                VARCHAR,
        station             VARCHAR,
        model               VARCHAR,              -- e.g. ecmwf_ifs025
        forecast_tmax       DOUBLE,
        forecast_p10        DOUBLE,
        forecast_p25        DOUBLE,
        forecast_p50        DOUBLE,
        forecast_p75        DOUBLE,
        forecast_p90        DOUBLE,
        available_at        TIMESTAMPTZ,          -- when the forecast became AVAILABLE at the source (as-of engine filters on THIS, not ingestion_timestamp)
        fetched_at          TIMESTAMPTZ,
        source              VARCHAR,
        source_timestamp    TIMESTAMPTZ,
        ingestion_timestamp TIMESTAMPTZ,
        dataset_version     VARCHAR,
        record_version      INTEGER DEFAULT 1,
        PRIMARY KEY (station, model, issue_time, target_date, dataset_version, record_version)
    );
    """,

    # ---- weather_observations: realized station highs ------------------------
    """
    CREATE TABLE IF NOT EXISTS weather_observations (
        observation_time    TIMESTAMPTZ,          -- when the obs became available
        city                VARCHAR,
        station             VARCHAR,
        source              VARCHAR,              -- obs provider == provenance source
        tmax_observed       DOUBLE,
        daily_high_time     TIMESTAMPTZ,          -- when the daily high occurred
        available_at        TIMESTAMPTZ,          -- when the obs became AVAILABLE at the source (as-of engine filters on THIS, not ingestion_timestamp)
        fetched_at          TIMESTAMPTZ,
        source_timestamp    TIMESTAMPTZ,
        ingestion_timestamp TIMESTAMPTZ,
        dataset_version     VARCHAR,
        record_version      INTEGER DEFAULT 1,
        PRIMARY KEY (station, source, observation_time, dataset_version, record_version)
    );
    """,

    # ---- weather_errors: empirical forecast-error stats ----------------------
    """
    CREATE TABLE IF NOT EXISTS weather_errors (
        city                VARCHAR,
        station             VARCHAR,
        model               VARCHAR,
        lead_hours          INTEGER,
        month               INTEGER,              -- 1..12 seasonal bucket
        mean_error          DOUBLE,
        median_error        DOUBLE,
        std_error           DOUBLE,
        mae                 DOUBLE,
        rmse                DOUBLE,
        q05                 DOUBLE,
        q10                 DOUBLE,
        q25                 DOUBLE,
        q50                 DOUBLE,
        q75                 DOUBLE,
        q90                 DOUBLE,
        q95                 DOUBLE,
        derived_from_dataset_version VARCHAR,     -- DERIVED_STATISTICS: dataset_version of the forecast+obs it was computed from
        source              VARCHAR,
        source_timestamp    TIMESTAMPTZ,
        ingestion_timestamp TIMESTAMPTZ,
        dataset_version     VARCHAR,
        record_version      INTEGER DEFAULT 1,
        PRIMARY KEY (station, model, lead_hours, month, dataset_version, record_version)
    );
    """,

    # ---- features: as-of feature rows (prediction_time = the as-of cutoff) ----
    """
    CREATE TABLE IF NOT EXISTS features (
        prediction_time       TIMESTAMPTZ,        -- as-of cutoff for THIS row
        market_id             VARCHAR,
        token_id              VARCHAR,
        market_prob           DOUBLE,
        weather_prob          DOUBLE,
        forecast_tmax         DOUBLE,
        forecast_p10          DOUBLE,
        forecast_p25          DOUBLE,
        forecast_p50          DOUBLE,
        forecast_p75          DOUBLE,
        forecast_p90          DOUBLE,
        feature_json          JSON,
        no_lookahead_verified BOOLEAN DEFAULT FALSE,  -- set TRUE only after §72 guard passes
        source                VARCHAR,
        source_timestamp      TIMESTAMPTZ,
        ingestion_timestamp   TIMESTAMPTZ,
        dataset_version       VARCHAR,
        record_version        INTEGER DEFAULT 1,
        PRIMARY KEY (market_id, token_id, prediction_time, dataset_version, record_version)
    );
    """,

    # ---- predictions: model outputs ------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS predictions (
        "timestamp"         TIMESTAMPTZ,
        market_id           VARCHAR,
        token_id            VARCHAR,
        p_market            DOUBLE,
        p_weather           DOUBLE,
        p_model             DOUBLE,
        fair_value          DOUBLE,
        edge_gross          DOUBLE,
        edge_net            DOUBLE,
        confidence          DOUBLE,
        model_version       VARCHAR,
        source              VARCHAR,
        source_timestamp    TIMESTAMPTZ,
        ingestion_timestamp TIMESTAMPTZ,
        dataset_version     VARCHAR,
        record_version      INTEGER DEFAULT 1,
        PRIMARY KEY (market_id, token_id, model_version, "timestamp", dataset_version, record_version)
    );
    """,

    # ---- signals: strategy outputs (price_assumption = INDICATIVE) -----------
    """
    CREATE TABLE IF NOT EXISTS signals (
        "timestamp"         TIMESTAMPTZ,
        market_id           VARCHAR,
        token_id            VARCHAR,
        strategy            VARCHAR,
        signal              VARCHAR,              -- BUY | SELL | FADE | HOLD | NONE
        fair_value          DOUBLE,
        price_assumption    DOUBLE,               -- indicative price used (not executable)
        edge                DOUBLE,
        net_edge            DOUBLE,
        confidence          DOUBLE,
        reason              VARCHAR,
        source              VARCHAR,
        source_timestamp    TIMESTAMPTZ,
        ingestion_timestamp TIMESTAMPTZ,
        dataset_version     VARCHAR,
        record_version      INTEGER DEFAULT 1,
        CHECK (signal IS NULL OR signal IN ('BUY','SELL','FADE','HOLD','NONE')),
        PRIMARY KEY (market_id, token_id, strategy, "timestamp", dataset_version, record_version)
    );
    """,

    # ---- paper_trades: paper execution (surrogate PK) ------------------------
    """
    CREATE TABLE IF NOT EXISTS paper_trades (
        paper_trade_id      BIGINT PRIMARY KEY DEFAULT nextval('seq_paper_trades'),
        backtest_id         VARCHAR,              -- -> backtest_results.backtest_id
        market_id           VARCHAR,
        token_id            VARCHAR,
        entry_time          TIMESTAMPTZ,
        entry_price         DOUBLE,
        exit_time           TIMESTAMPTZ,
        exit_price          DOUBLE,
        fees                DOUBLE,
        slippage            DOUBLE,
        gross_pnl           DOUBLE,
        net_pnl             DOUBLE,
        settlement          DOUBLE,               -- 0/1 settlement value
        size                DOUBLE,
        bankroll_after      DOUBLE,
        price_layer         VARCHAR,              -- INDICATIVE | SIMULATED_EXECUTABLE | EXECUTABLE
        source              VARCHAR,
        source_timestamp    TIMESTAMPTZ,
        ingestion_timestamp TIMESTAMPTZ,
        dataset_version     VARCHAR,
        record_version      INTEGER DEFAULT 1,
        CHECK (price_layer IS NULL OR
               price_layer IN ('INDICATIVE','SIMULATED_EXECUTABLE','EXECUTABLE'))
    );
    """,

    # ---- backtest_results: run registry (reproducibility) --------------------
    """
    CREATE TABLE IF NOT EXISTS backtest_results (
        backtest_id         VARCHAR PRIMARY KEY,
        run_timestamp       TIMESTAMPTZ,
        dataset_version     VARCHAR,              -- -> dataset_versions.version
        model_version       VARCHAR,
        parameters          JSON,
        metrics             JSON,
        walk_forward_config JSON,
        random_seed         BIGINT,
        feature_list        JSON,
        train_window        VARCHAR,
        validation_window   VARCHAR,
        test_window         VARCHAR,
        code_version        VARCHAR,
        source              VARCHAR,
        ingestion_timestamp TIMESTAMPTZ,
        record_version      INTEGER DEFAULT 1
    );
    """,

    # ---- markets_excluded: survivor-bias ledger ------------------------------
    """
    CREATE TABLE IF NOT EXISTS markets_excluded (
        market_id           VARCHAR,
        reason              VARCHAR,
        excluded_at         TIMESTAMPTZ,
        stage               VARCHAR,              -- discovery|pricing|labeling|feature
        details             JSON,
        source              VARCHAR,
        ingestion_timestamp TIMESTAMPTZ,
        dataset_version     VARCHAR,
        record_version      INTEGER DEFAULT 1,
        PRIMARY KEY (market_id, reason, dataset_version)
    );
    """,

    # ---- data_quality: per-ref QC summary ------------------------------------
    """
    CREATE TABLE IF NOT EXISTS data_quality (
        ref                  VARCHAR,             -- market_id / dataset_version / run ref
        weather_data_quality JSON,
        market_data_quality  JSON,
        orderbook_quality    JSON,
        resolution_quality   JSON,
        checked_at           TIMESTAMPTZ,
        source               VARCHAR,
        ingestion_timestamp  TIMESTAMPTZ,
        dataset_version      VARCHAR,
        record_version       INTEGER DEFAULT 1,
        PRIMARY KEY (ref, dataset_version)
    );
    """,
]

# Phase 2B additions (idempotent ALTERs) — market metadata / availability
# semantics / measurement rule / raw fee fields discovered from gamma.
_DDL_V2 = [
    "ALTER TABLE markets ADD COLUMN IF NOT EXISTS measurement_rule VARCHAR;",
    # availability of MARKET data to an external agent is NOT known from gamma
    # metadata alone -> stays UNKNOWN in 2B (see PHASE_2B doc). Column exists so a
    # later subphase can set it with justification; never = ingestion_timestamp.
    "ALTER TABLE markets ADD COLUMN IF NOT EXISTS available_at TIMESTAMPTZ;",
    "ALTER TABLE markets ADD COLUMN IF NOT EXISTS available_at_confidence VARCHAR;",
    # verbatim capture of ALL raw gamma timestamps for the market (reproducibility)
    "ALTER TABLE markets ADD COLUMN IF NOT EXISTS source_timestamps JSON;",
    # verbatim capture of raw gamma fee fields (makerBaseFee/takerBaseFee/feeType/
    # feeSchedule/feesEnabled) so the interpretation can be confirmed later.
    "ALTER TABLE market_fee_schedule ADD COLUMN IF NOT EXISTS raw_fee_fields JSON;",
]

# Ordered, idempotent migrations. Add a new dict (version+1) for future changes;
# never edit a shipped migration in place.
MIGRATIONS: list[dict] = [
    {
        "version": 1,
        "name": "phase2a_initial_schema",
        "statements": _SEQUENCES + _DDL,
    },
    {
        "version": 2,
        "name": "phase2b_market_metadata",
        "statements": _DDL_V2,
    },
]


# =============================================================================
# connection + schema management
# =============================================================================
def _utcnow_iso() -> str:
    """Current time as an ISO-8601 UTC string (DuckDB casts it to TIMESTAMPTZ)."""
    return datetime.now(timezone.utc).isoformat()


def connect(db_path: str | None = None, read_only: bool = False):
    """Open (creating if needed) the DuckDB database and return the connection.
    Ensures the parent directory exists. Loads the bundled json extension."""
    import duckdb  # imported lazily so the module can be imported for introspection

    path = db_path or DB_PATH
    if path != ":memory:":
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
    con = duckdb.connect(path, read_only=read_only)
    # json is a core/bundled extension in modern DuckDB (autoloaded). Load it
    # defensively; run the two statements separately so a failed INSTALL (e.g.
    # offline) never prevents LOAD, and ignore if it is already available.
    for stmt in ("INSTALL json;", "LOAD json;", "INSTALL icu;", "LOAD icu;"):
        try:
            con.execute(stmt)
        except Exception:
            pass
    # Force UTC rendering of TIMESTAMPTZ for deterministic, host-independent
    # results (icu provides the timezone). Harmless if icu is unavailable.
    try:
        con.execute("SET TimeZone='UTC';")
    except Exception:
        pass
    return con


def _ensure_schema_version_table(con) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version    INTEGER PRIMARY KEY,
            name       VARCHAR,
            applied_at TIMESTAMPTZ DEFAULT now(),
            checksum   VARCHAR
        );
        """
    )


def get_schema_version(con) -> int:
    """Highest applied migration version (0 if none / table missing)."""
    try:
        row = con.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version").fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    except Exception:
        return 0


def init_db(con=None, db_path: str | None = None):
    """Idempotently create/upgrade the schema. Applies every migration whose
    version exceeds the current schema_version, each inside its own transaction.
    Safe to call repeatedly. Returns the (open) connection."""
    if con is None:
        con = connect(db_path)
    _ensure_schema_version_table(con)
    current = get_schema_version(con)
    for mig in MIGRATIONS:
        if mig["version"] <= current:
            continue
        con.execute("BEGIN TRANSACTION;")
        try:
            for stmt in mig["statements"]:
                con.execute(stmt)
            con.execute(
                "INSERT INTO schema_version (version, name, applied_at) VALUES (?, ?, ?)",
                [mig["version"], mig["name"], _utcnow_iso()],
            )
            con.execute("COMMIT;")
        except Exception:
            con.execute("ROLLBACK;")
            raise
    # Phase 2C (Alt C): operational discovery checkpoint table, created idempotently
    # OUTSIDE the numbered MIGRATIONS. SCHEMA_VERSION stays 2 and MIGRATIONS is
    # untouched (keeps validate_2b.py §11 green). Single init point: discover() /
    # ingest_event() assume an init_db'd connection.
    _ensure_checkpoint_table(con)
    return con


def table_names(con) -> list[str]:
    """All base table names in the current database."""
    rows = con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_type='BASE TABLE'"
    ).fetchall()
    return [r[0] for r in rows]


def column_names(con, table: str) -> list[str]:
    rows = con.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = ?",
        [table],
    ).fetchall()
    return [r[0] for r in rows]


# =============================================================================
# Phase 2C — persistent discovery checkpoint (Alt C)
# Operational table, NOT a numbered migration, NOT in ALL_TABLES; SCHEMA_VERSION
# stays 2. The PERSISTED table is the source of truth for resume; discover() keeps
# an in-memory mirror only for speed. checkpoint_mark() MUST run inside the caller's
# per-event transaction (last write before COMMIT) so rows + mark are atomic.
# =============================================================================
def _ensure_checkpoint_table(con) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS discovery_checkpoint (
            dataset_version VARCHAR NOT NULL,
            event_id        VARCHAR NOT NULL,
            committed_at    TIMESTAMPTZ DEFAULT now(),
            run_id          VARCHAR,
            PRIMARY KEY (dataset_version, event_id)
        );
        """
    )


def checkpoint_load(con, dataset_version: str) -> set:
    """Set of already-committed event ids for a dataset_version, read from the
    persisted checkpoint (source of truth for resume). A brand-new process calls
    this to resume exactly where the last one committed."""
    rows = con.execute(
        "SELECT event_id FROM discovery_checkpoint WHERE dataset_version = ?",
        [dataset_version],
    ).fetchall()
    return {r[0] for r in rows}


def checkpoint_mark(con, dataset_version: str, event_id: str,
                    run_id: str | None = None) -> None:
    """Mark one event as committed. MUST be called INSIDE the caller's per-event
    transaction, as the LAST write before COMMIT, so the mark is atomic with the
    event's rows (a crash before COMMIT rolls back both). Idempotent: a retried
    event keeps its original mark (ON CONFLICT DO NOTHING)."""
    con.execute(
        "INSERT INTO discovery_checkpoint (dataset_version, event_id, committed_at, run_id) "
        "VALUES (?, ?, ?, ?) ON CONFLICT (dataset_version, event_id) DO NOTHING",
        [dataset_version, event_id, _utcnow_iso(), run_id],
    )


# =============================================================================
# write / read helpers
# =============================================================================
def _q(ident: str) -> str:
    """Quote an SQL identifier safely (handles reserved words like "timestamp")."""
    return '"' + str(ident).replace('"', '""') + '"'


def _prep(value: Any) -> Any:
    """Prepare a Python value for a parameterized insert. dict/list -> JSON text
    (DuckDB casts VARCHAR -> JSON on insert). Everything else is passed through
    (duckdb handles datetime, str, int, float, bool, None; ISO strings cast to
    TIMESTAMPTZ/DATE)."""
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return value


def insert(con, table: str, row: Mapping[str, Any]) -> None:
    """INSERT a single row (dict of column -> value). Runs ONE statement and does
    NOT commit/rollback or change autocommit — the CALLER owns the transaction
    (e.g. discovery.ingest_event wraps its writes in BEGIN/COMMIT and ROLLBACKs the
    whole event on failure, so a helper write mid-event is undone by that ROLLBACK)."""
    cols = list(row.keys())
    placeholders = ", ".join(["?"] * len(cols))
    sql = (
        f"INSERT INTO {_q(table)} ({', '.join(_q(c) for c in cols)}) "
        f"VALUES ({placeholders})"
    )
    con.execute(sql, [_prep(row[c]) for c in cols])


def insert_many(con, table: str, rows: Sequence[Mapping[str, Any]]) -> int:
    """INSERT many rows that share the SAME set of columns. Returns row count."""
    rows = list(rows)
    if not rows:
        return 0
    cols = list(rows[0].keys())
    placeholders = ", ".join(["?"] * len(cols))
    sql = (
        f"INSERT INTO {_q(table)} ({', '.join(_q(c) for c in cols)}) "
        f"VALUES ({placeholders})"
    )
    con.executemany(sql, [[_prep(r[c]) for c in cols] for r in rows])
    return len(rows)


def upsert(con, table: str, row: Mapping[str, Any], conflict_cols: Iterable[str]) -> None:
    """INSERT ... ON CONFLICT (conflict_cols) DO UPDATE. `conflict_cols` must be a
    PRIMARY KEY or UNIQUE constraint. Idempotent re-ingest of the same
    (natural key + dataset_version + record_version) refreshes the row in place.
    Runs ONE statement and does NOT commit/rollback or change autocommit — the
    CALLER owns the transaction (so a ROLLBACK undoes an upsert made mid-event)."""
    cols = list(row.keys())
    conflict = list(conflict_cols)
    updates = [c for c in cols if c not in conflict]
    placeholders = ", ".join(["?"] * len(cols))
    head = (
        f"INSERT INTO {_q(table)} ({', '.join(_q(c) for c in cols)}) "
        f"VALUES ({placeholders}) "
        f"ON CONFLICT ({', '.join(_q(c) for c in conflict)}) "
    )
    if updates:
        set_clause = ", ".join(f"{_q(c)} = excluded.{_q(c)}" for c in updates)
        sql = head + f"DO UPDATE SET {set_clause}"
    else:
        sql = head + "DO NOTHING"
    con.execute(sql, [_prep(row[c]) for c in cols])


def query(con, sql: str, params: Sequence[Any] | None = None) -> list[dict]:
    """Run a SELECT and return a list of dict rows."""
    cur = con.execute(sql, list(params) if params else [])
    if cur.description is None:
        return []
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def query_df(con, sql: str, params: Sequence[Any] | None = None):
    """Run a SELECT and return a pandas DataFrame."""
    return con.execute(sql, list(params) if params else []).df()


# =============================================================================
# AS-OF (no-look-ahead) helpers
# =============================================================================
def query_asof(
    con,
    table: str,
    time_col: str | None = None,
    asof: Any = None,
    where: str | None = None,
    params: Sequence[Any] | None = None,
    order_desc: bool = True,
) -> list[dict]:
    """Return every row whose as-of column <= `asof` (optionally further filtered
    by a raw `where` clause with its own params). This is the primitive that makes
    the schema reconstruct exactly what was knowable at `asof`.

    `time_col` defaults to the table's canonical as-of column (AS_OF_COLUMNS) — for
    weather tables that is `available_at` (source availability), NEVER
    `ingestion_timestamp`."""
    if time_col is None:
        time_col = _asof_column(table)
    if asof is None:
        raise ValueError("asof is required")
    clauses = [f"{_q(time_col)} <= ?"]
    p: list[Any] = [asof]
    if where:
        clauses.append(f"({where})")
        p.extend(list(params) if params else [])
    order = "DESC" if order_desc else "ASC"
    sql = f"SELECT * FROM {_q(table)} WHERE {' AND '.join(clauses)} ORDER BY {_q(time_col)} {order}"
    return query(con, sql, p)


def latest_asof(
    con,
    table: str,
    time_col: str | None = None,
    asof: Any = None,
    partition_cols: Sequence[str] | None = None,
    where: str | None = None,
    params: Sequence[Any] | None = None,
) -> list[dict]:
    """Return the single most-recent row per partition with the as-of column <=
    `asof`. With no partition, returns the single latest row. `time_col` defaults
    to the table's canonical as-of column (AS_OF_COLUMNS); for weather tables that
    is `available_at`, NEVER `ingestion_timestamp`. Used for 'the forecast known as
    of prediction_time', 'the last indicative price at or before the lead', etc."""
    if time_col is None:
        time_col = _asof_column(table)
    if asof is None:
        raise ValueError("asof is required")
    clauses = [f"{_q(time_col)} <= ?"]
    p: list[Any] = [asof]
    if where:
        clauses.append(f"({where})")
        p.extend(list(params) if params else [])
    base = f"SELECT * FROM {_q(table)} WHERE {' AND '.join(clauses)}"
    if partition_cols:
        part = ", ".join(_q(c) for c in partition_cols)
        sql = (
            f"{base} QUALIFY row_number() OVER "
            f"(PARTITION BY {part} ORDER BY {_q(time_col)} DESC) = 1"
        )
    else:
        sql = f"{base} ORDER BY {_q(time_col)} DESC LIMIT 1"
    return query(con, sql, p)


# =============================================================================
# provenance / versioning helpers
# =============================================================================
def add_provenance(
    row: Mapping[str, Any],
    *,
    source: str,
    dataset_version: str,
    source_timestamp: Any | None = None,
    ingestion_timestamp: Any | None = None,
    record_version: int = 1,
) -> dict:
    """Return a copy of `row` with the standard provenance quintet filled in
    (existing keys are preserved). ingestion_timestamp defaults to now (UTC)."""
    r = dict(row)
    r.setdefault("source", source)
    r.setdefault("source_timestamp", source_timestamp)
    r.setdefault("ingestion_timestamp", ingestion_timestamp or _utcnow_iso())
    r.setdefault("dataset_version", dataset_version)
    r.setdefault("record_version", record_version)
    return r


def next_record_version(
    con,
    table: str,
    natural_key: Mapping[str, Any],
    dataset_version: str | None = None,
) -> int:
    """Compute the next record_version for a logical fact: max(record_version)+1
    over rows matching `natural_key` (optionally scoped to a dataset_version).
    Returns 1 when the fact does not yet exist."""
    clauses = [f"{_q(k)} = ?" for k in natural_key]
    p: list[Any] = list(natural_key.values())
    if dataset_version is not None:
        clauses.append(f"{_q('dataset_version')} = ?")
        p.append(dataset_version)
    where = " AND ".join(clauses) if clauses else "TRUE"
    sql = (
        f"SELECT COALESCE(MAX({_q('record_version')}), 0) + 1 AS v "
        f"FROM {_q(table)} WHERE {where}"
    )
    return int(query(con, sql, p)[0]["v"])
