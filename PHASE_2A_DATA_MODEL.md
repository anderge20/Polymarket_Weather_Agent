# PHASE 2A — DATA MODEL (DuckDB)

**Scope:** Phase **2A only** (data model / DuckDB). No market discovery, no
collectors, no ingestion, no features/models/backtest — those are **2B+** and are
**not** built here.
**Author/date:** Claude (Cowork) · 2026-08-20
**Environment caveat:** authored in an environment **without Python**. Every
deliverable is **IMPLEMENTED**; **nothing is TESTED or VALIDATED** until you run
the suite on the Hetzner box (§9–§10 below). Do not treat anything here as
"validated".

This document is the required 2A closure and is organised as the **10 points**
you asked for.

---

## 1. What this is (PHASE_2A_DATA_MODEL.md)

`database.py` (DuckDB) is the spine of MVP 3.0: a single embedded, columnar
database that stores markets, outcomes, indicative price history, forward-only
order book / trades, weather forecasts / observations / error stats, features,
predictions, signals, paper trades, backtest runs, an exclusions ledger
(survivor-bias) and data-quality records — each with **full provenance** so a
backtest can be reproduced months later against the exact data version that
produced it.

Files delivered in 2A:

| File | Purpose |
|---|---|
| `src/weather_agent/database.py` | Connection, idempotent init, migrations, insert/upsert/query, **as-of** and **versioning** helpers, full schema. |
| `src/weather_agent/config.py` | DB path (env), documented endpoints, configurable `city_registry` (no hardcoded stations), fee/defaults. |
| `requirements-pipeline.txt` | Compute-tier deps (duckdb, pandas, numpy, scipy, scikit-learn, requests, aiohttp, websockets, python-dateutil, pytest). |
| `requirements-dashboard.txt` | Thin read-only dashboard deps (streamlit, duckdb, pandas, plotly). |
| `tests/test_database.py` | Schema create + round-trip of **every** table + as-of/upsert/versioning/CHECK tests. |
| `tests/test_no_future_information.py` (one **runnable** semantic test + skipped builder stubs), `test_weather_asof.py`, `test_market_asof.py`, `test_resolution_not_in_features.py` | §72 / as-of checks; the runnable test validates the no-look-ahead invariants on sample data. |
| `data/processed/.gitkeep` | Default DuckDB directory. |
| `PHASE_2A_DATA_MODEL.md` | This document. |

---

## 2. Complete table structure

All human timestamps are `TIMESTAMPTZ` (UTC). JSON blobs use DuckDB's `JSON`
type; the helpers `json.dumps` dicts/lists on write and you `json.loads` on read.
**Provenance quintet** = `source, source_timestamp, ingestion_timestamp,
dataset_version, record_version` (present on every fact/derived table).

**Meta / reference**

- **`schema_version`** — `version INT`, `name`, `applied_at`, `checksum`. Tracks applied migrations.
- **`dataset_versions`** — `version`, `created_at`, `source`, `query_parameters JSON`, `description`, `code_version`, `git_commit`. The reproducibility anchor.
- **`market_fee_schedule`** — `fee_regime`, `taker_fee`, `maker_rebate`, `effective_from`, `effective_to`, `fee_status` (`KNOWN|UNKNOWN|ESTIMATED|DEPRECATED`), + provenance. Epoch-dependent fees; **never assume 0** (NULL fee + `fee_status='UNKNOWN'`). **Versioned / append-only** (PK includes `dataset_version, record_version`) so a superseded fee-regime version is never lost.

**Catalog + resolution**

- **`markets`** (§24 catalog + resolution) — `market_id`, `condition_id`, `event_id`, `slug`, `question`, `city`, `station`, `station_identifier`, `resolution_source`, `unit` (`C|F|UNKNOWN`), `rounding_rule`, `resolution_timestamp`, `settlement_timestamp`, `winning_outcome`, `open_time`, `close_time`, `last_traded_time`, `last_meaningful_market_time`, `daily_high_time`, `data_start`, `data_end`, `available_resolution` (`native_1min|coarse|none|unknown`), `fee_regime`, `tick_size`, `min_order_size`, `tag_ids JSON`, `discovered_at`, + provenance. `tick_size`/`min_order_size` are **NULL when unknown** (NO hardcoded default — they come from the real market at discovery).
- **`outcomes`** — `market_id`, `token_id`, `band_label`, `lo`, `hi` (NULL = open-ended side), `outcome_index`, `is_winner`, + provenance.

**Market time series**

- **`price_history`** — `observation_time`, `market_id`, `token_id`, `indicative_price`, `price_semantics` (default `MIDPOINT_ESTIMATED`), `price_source` (default `CLOB_PRICES_HISTORY`), `fidelity` (min; `>=1`), `source_window` (`DIRECT|DERIVED`), `fetched_at`, + provenance. **Indicative only, never executable** (CHECK forbids `EXECUTABLE`).
- **`orderbook_snapshots`** *(forward-only — capture-layer property)* — `"timestamp"`, `market_id`, `token_id`, `best_bid`, `best_ask`, `mid`, `spread`, `bid_depth_1/5/10`, `ask_depth_1/5/10`, `imbalance`, `book_snapshot JSON`, `collected_at`, `collector_session_id`, `collector_started_at`, + provenance.
- **`trades`** *(forward-only — capture-layer property)* — `"timestamp"`, `market_id`, `token_id`, `price`, `size`, `side` (`BUY|SELL`), `trade_id`, `fetched_at`, `collected_at`, `collector_session_id`, `collector_started_at`, + provenance.

**Weather**

- **`weather_forecasts`** — `issue_time` (= forecast_issued_at), `forecast_run`, `target_date DATE` (= forecast valid date), **`available_at`** (as-of anchor — when it became available at the source), `city`, `station`, `model`, `forecast_tmax`, `forecast_p10/p25/p50/p75/p90`, `fetched_at`, + provenance.
- **`weather_observations`** — `observation_time` (when it occurred), **`available_at`** (as-of anchor — when it became available at the source), `city`, `station`, `source` (provider == provenance source), `tmax_observed`, `daily_high_time`, `fetched_at`, + provenance.
- **`weather_errors`** (**DERIVED_STATISTICS** — not a primary source; reconstructible from forecast + realized observation under as-of/walk-forward) — `city`, `station`, `model`, `lead_hours`, `month`, `mean_error`, `median_error`, `std_error`, `mae`, `rmse`, `q05/q10/q25/q50/q75/q90/q95`, `derived_from_dataset_version` (dataset it was computed from), + provenance.

**Modelling / execution**

- **`features`** — `prediction_time` (as-of cutoff), `market_id`, `token_id`, `market_prob`, `weather_prob`, `forecast_tmax/p10/p25/p50/p75/p90`, `feature_json JSON`, `no_lookahead_verified BOOL`, + provenance.
- **`predictions`** — `"timestamp"`, `market_id`, `token_id`, `p_market`, `p_weather`, `p_model`, `fair_value`, `edge_gross`, `edge_net`, `confidence`, `model_version`, + provenance.
- **`signals`** — `"timestamp"`, `market_id`, `token_id`, `strategy`, `signal` (`BUY|SELL|FADE|HOLD|NONE`), `fair_value`, `price_assumption` (indicative, not executable), `edge`, `net_edge`, `confidence`, `reason`, + provenance.
- **`paper_trades`** — `paper_trade_id` (surrogate), `backtest_id`, `market_id`, `token_id`, `entry_time`, `entry_price`, `exit_time`, `exit_price`, `fees`, `slippage`, `gross_pnl`, `net_pnl`, `settlement`, `size`, `bankroll_after`, `price_layer` (CHECK: `INDICATIVE` | `SIMULATED_EXECUTABLE` | `EXECUTABLE`), + provenance.
- **`backtest_results`** — `backtest_id`, `run_timestamp`, `dataset_version`, `model_version`, `parameters JSON`, `metrics JSON`, `walk_forward_config JSON`, `random_seed`, `feature_list JSON`, `train_window`, `validation_window`, `test_window`, `code_version`, + partial provenance.

**Bookkeeping / QC**

- **`markets_excluded`** (survivor-bias ledger) — `market_id`, `reason`, `excluded_at`, `stage`, `details JSON`, + provenance.
- **`data_quality`** — `ref`, `weather_data_quality JSON`, `market_data_quality JSON`, `orderbook_quality JSON`, `resolution_quality JSON`, `checked_at`, + provenance.

---

## 3. Primary keys / uniques

Revisioned fact tables are **append-only**: `(dataset_version, record_version)`
is part of the PK so corrections coexist with the originals.

| Table | PRIMARY KEY |
|---|---|
| `schema_version` | `(version)` |
| `dataset_versions` | `(version)` |
| `market_fee_schedule` | `(fee_regime, dataset_version, record_version)` |
| `markets` | `(market_id, dataset_version, record_version)` |
| `outcomes` | `(token_id, dataset_version, record_version)` |
| `price_history` | `(token_id, observation_time, dataset_version, record_version)` |
| `orderbook_snapshots` | `(token_id, "timestamp", dataset_version, record_version)` |
| `trades` | `(trade_id, dataset_version, record_version)` |
| `weather_forecasts` | `(station, model, issue_time, target_date, dataset_version, record_version)` |
| `weather_observations` | `(station, source, observation_time, dataset_version, record_version)` |
| `weather_errors` | `(station, model, lead_hours, month, dataset_version, record_version)` |
| `features` | `(market_id, token_id, prediction_time, dataset_version, record_version)` |
| `predictions` | `(market_id, token_id, model_version, "timestamp", dataset_version, record_version)` |
| `signals` | `(market_id, token_id, strategy, "timestamp", dataset_version, record_version)` |
| `paper_trades` | `(paper_trade_id)` — surrogate via `seq_paper_trades` |
| `backtest_results` | `(backtest_id)` |
| `markets_excluded` | `(market_id, reason, dataset_version)` |
| `data_quality` | `(ref, dataset_version)` |

**CHECK constraints (schema-encoded rules):** `price_history.price_semantics`
∈ the indicative set (forbids `EXECUTABLE`); `price_history.source_window` ∈
{DIRECT, DERIVED}; `price_history.fidelity >= 1`; `markets.unit` ∈ {C,F,UNKNOWN};
`markets.available_resolution` ∈ {native_1min, coarse, none, unknown};
`trades.side` ∈ {BUY, SELL}; `signals.signal` ∈ {BUY, SELL, FADE, HOLD, NONE};
`market_fee_schedule.fee_status` ∈ {KNOWN, UNKNOWN, ESTIMATED, DEPRECATED};
`paper_trades.price_layer` ∈ {INDICATIVE, SIMULATED_EXECUTABLE, EXECUTABLE}.

---

## 4. Relationships between tables

Foreign keys are **logical / documented, not DB-enforced** (so partial, out-of-order
ingestion never fails). 2B ingestion maintains integrity in code + `data_quality`.

- `outcomes.market_id → markets.market_id`
- `price_history.{market_id,token_id} → markets/outcomes`
- `orderbook_snapshots.{market_id,token_id} → markets/outcomes`
- `trades.{market_id,token_id} → markets/outcomes`
- `features/predictions/signals.{market_id,token_id} → markets/outcomes`
- `markets.fee_regime → market_fee_schedule.fee_regime` (business key; the fee schedule is versioned — resolve the applicable version by `effective_from/to` + max `record_version`)
- `paper_trades.backtest_id → backtest_results.backtest_id`
- `weather_forecasts/observations.station ↔ markets.station` (join on discovered station)
- **`*.dataset_version → dataset_versions.version`** (every fact points at its batch)
- `backtest_results.dataset_version → dataset_versions.version`

---

## 5. Temporal / as-of strategy (no-look-ahead) + availability semantics

Time-sensitive facts keep **three distinct timestamps** apart, and the as-of
engine keys on **availability**, never on when we happened to ingest:

- **occurrence** — when the thing physically happened (`observation_time`,
  `daily_high_time`; forecast `issue_time` / `target_date`).
- **`available_at`** — when it became knowable **at the source**. *This is what the
  as-of engine filters on.*
- **`ingestion_timestamp`** — when **we** wrote it to the lake. **Never** a
  substitute for `available_at`.

`AS_OF_COLUMNS` (in `database.py`) registers the canonical as-of column per table;
`query_asof` / `latest_asof` default `time_col` from it:

| Table | Canonical as-of column |
|---|---|
| `price_history` | `observation_time` (the point IS the market state then) |
| `orderbook_snapshots`, `trades` | `"timestamp"` |
| `weather_forecasts` | **`available_at`** (NOT `issue_time`, NOT `ingestion_timestamp`) |
| `weather_observations` | **`available_at`** (NOT `observation_time`/`daily_high_time`) |
| `features` | `prediction_time` (single cutoff for the row) |
| `predictions`, `signals` | `"timestamp"` |

`markets` additionally carries `open/close/last_traded/last_meaningful_market/
daily_high/resolution/settlement` times so 2B can compute `lead_to_last_trade /
_last_meaningful_market / _daily_high / _resolution`.

Two primitives implement it (both default `time_col` to `AS_OF_COLUMNS[table]`):

- `query_asof(table, time_col=None, asof=...)` → all rows with the as-of column `<= asof`.
- `latest_asof(table, time_col=None, asof=..., partition_cols=[...])` → the single
  most-recent row per partition at or before `asof` (e.g. *the indicative price at
  or before the lead*, *the forecast known as of prediction_time*).

Goal: for any `prediction_time T`, know exactly what was knowable at `T`.

**`no_lookahead_verified` is a RESULT, not a source of truth.** It is set TRUE
**only** by the 2B+ feature builder after it runs the as-of checks (market inputs
`<= T`; forecast `available_at <= T`; observation `available_at <= T`; resolution
info absent from features). A manual TRUE is not authoritative. The **runnable**
test `test_no_lookahead_semantics_on_sample_data` validates these semantics on
sample data; the full behavioural test is pending the real builder (2B+).

---

## 6. Versioning / reproducibility strategy

Goal: **re-run a backtest in 3 months and know exactly which data produced it.**

**`dataset_version` — batch identity (how it's assigned).** Each ingestion/pull
run creates one row in `dataset_versions` (suggested id `ds_<UTC-date>_<source>_<seq>`,
e.g. `ds_2026-08-20_gamma_v1`) capturing `source`, the exact `query_parameters`,
`code_version`/`git_commit`, and `created_at`. **Every fact row written by that
run carries that same `dataset_version`.** Re-pulling the same slice with the same
code → same `dataset_version` and an idempotent `upsert` (no duplicates).

**`record_version` — per-fact revision (how a revised record is versioned).**
First write of a logical fact = `record_version = 1`. If the *same* fact is later
corrected (resolution restated, a better backfill, a re-issued forecast), you
**append a new row** with `record_version = next_record_version(...)` — the old
row is retained (append-only, never destructive). "Current" = the max
`(dataset_version, record_version)` per natural key; a point-in-time view filters
to a chosen `dataset_version` and its max `record_version`.

**How a backtest references its data.** `backtest_results` stores the
`dataset_version` used (plus `model_version`, `random_seed`, `feature_list`,
`walk_forward_config`, `parameters`, `code_version`, and the
train/validation/test windows). To reproduce: read `backtest_results`, take its
`dataset_version`, and re-select facts filtered to that version — the inputs are
byte-for-byte the ones the run saw. `paper_trades` link to their run via
`backtest_id` and also carry `dataset_version`.

**Versioned reference data.** `market_fee_schedule` is append-only (PK includes
`dataset_version, record_version`) so a superseded fee regime is never lost.
**Derived tables record their lineage:** `weather_errors` (DERIVED_STATISTICS)
carries `derived_from_dataset_version` — the dataset of the forecast+observation it
was computed from — so the stats can be traced back to (and rebuilt from) their
inputs under the same as-of / walk-forward discipline.

---

## 7. Tests created

In `tests/`:

- **`test_database.py`** (runnable): `test_all_tables_created`,
  `test_schema_version_recorded`, `test_init_is_idempotent`,
  `test_idempotent_on_reopened_file`, `test_every_fact_table_has_provenance`,
  `test_round_trip_each_table` (parametrized over **all 17 tables**),
  `test_json_column_round_trips`, `test_insert_many`,
  `test_upsert_updates_in_place`, `test_next_record_version`,
  `test_append_only_revision_coexists`, `test_price_semantics_rejects_executable`,
  `test_source_window_check`, `test_query_asof_and_latest_asof`,
  `test_latest_asof_excludes_future`, `test_fee_schedule_versioned`,
  `test_price_layer_check_rejects_unknown`, `test_price_layer_check_allows_vocabulary`,
  `test_asof_defaults_to_available_at_for_weather`.
- **`test_no_future_information.py`** (§72): `test_no_lookahead_semantics_on_sample_data`
  is **runnable** — it validates the as-of invariants a TRUE `no_lookahead_verified`
  must satisfy, on sample data; the builder-dependent tests stay skipped (2B+).
- **Pending stubs (skipped):** `test_weather_asof.py`, `test_market_asof.py`,
  `test_resolution_not_in_features.py`. Each documents what it will assert and
  notes the 2A schema already supports the as-of check.
- **`conftest.py`**: `con` fixture (fresh in-memory initialised DuckDB) + `src/`
  path shim.

---

## 8. Tests executed (here)

**None.** There is no Python/DuckDB in the authoring environment, so **0 tests
were run**. Everything in §7 is **IMPLEMENTED, not TESTED**.

---

## 9. Tests pending execution (run on Hetzner)

Prerequisites: Python 3.11+, network **off the Enel/GlobalProtect firewall**, a
dedicated user/dir **isolated from cmle-bot** (not `/home/trader/Bot`).

```bash
# from the repo root, on the Hetzner box
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-pipeline.txt

# initialise the DuckDB file (path overridable via WEATHER_AGENT_DB_PATH)
export WEATHER_AGENT_DB_PATH="$PWD/data/processed/weather_agent.duckdb"
PYTHONPATH=src python -c "from weather_agent.database import init_db; init_db(); print('schema initialised')"

# run the suite (the 4 as-of/§72 stubs report as SKIPPED/pending)
PYTHONPATH=src pytest -q
```

Expected once run: `test_database.py` passes; the 4 stub files show as skipped.
Only after this run may any component be marked **TESTED**; **VALIDATED** requires
running against real ingested data (2B+).

---

## 10. Design decisions affecting 2B+

1. **`STATIONS` retired from `config.py`.** Resolution station/ICAO/unit/rounding
   are now per-market facts (written to `markets` by 2B discovery). Consequence:
   the legacy flat modules that `import STATIONS` (`weather.py`, `backtest.py`)
   will not import until ported in 2B+; keep the old Streamlit app pinned to
   legacy code until then. (No import shadowing in 2A — no sub-packages were
   created; only flat `config.py`/`database.py`.)
2. **Append-only versioned PKs.** 2B ingestion must set `dataset_version`, use
   `upsert` on the **full** PK for idempotent re-runs, and use
   `next_record_version` for corrections. "Current view" queries must select the
   max `(dataset_version, record_version)` per natural key.
3. **FKs are logical, not enforced.** 2B must maintain referential integrity in
   code and record violations in `data_quality`.
4. **Price is indicative, never executable.** No bid/ask/executable price in
   `price_history`. 2B+ execution must model cost from `market_fee_schedule` +
   spread/slippage, never from the indicative price. Backfill must use
   `startTs/endTs + fidelity=1` (≤48h windows + stitching), **never `interval=max`**.
5. **Order book / trades are forward-only.** 2B live collector fills them; no
   historical L2 backfill exists.
6. **JSON via DuckDB `JSON` type.** Helpers `json.dumps` on write; 2B reads
   `json.loads`.
7. **Added fields beyond the literal 2A list** (documented): surrogate
   `paper_trade_id` + `market_id/token_id/backtest_id` on `paper_trades`;
   `code_version` on `backtest_results`; `stage`/`details` on `markets_excluded`;
   `checked_at` on `data_quality`; `description/code_version/git_commit` on
   `dataset_versions`; `forecast_run`/percentiles on weather tables. Reconcile
   against the authoritative MVP-3.0 §23–§29/§65/§66 field lists when available
   (that spec is **not** in the repo; `markets` §24 fields were derived from the
   documented Gamma API + `phase1_5/resolution_discovery.py`).
8. **Timestamps are `TIMESTAMPTZ` (UTC).** 2B must pass UTC ISO-8601 strings or
   timezone-aware datetimes.
9. **Availability vs ingestion.** The as-of engine filters on `available_at`
   (weather) / occurrence time (prices) via `AS_OF_COLUMNS`, **never**
   `ingestion_timestamp`. 2B ingestion MUST populate `available_at` from the
   source — do not leave it NULL and do not backfill it from ingestion time.
10. **Forward-only is an ingestion-LAYER property, not a schema property.**
    `orderbook_snapshots`/`trades` carry `collector_session_id`,
    `collector_started_at`, `collected_at` so a book can never be presented
    retrospectively as if our agent had captured it then. 2B collector must set
    these; consumers must treat rows without a collector session as un-captured.
11. **`market_fee_schedule` is versioned** (PK `(fee_regime, dataset_version,
    record_version)`); resolve the applicable regime by `effective_from/to` + max
    `record_version`.
12. **`price_layer` is constrained** to INDICATIVE / SIMULATED_EXECUTABLE /
    EXECUTABLE (schema CHECK + `config.PRICE_LAYERS`).
13. **`weather_errors` is DERIVED_STATISTICS** with `derived_from_dataset_version`;
    rebuildable, and must not be treated as a primary source.
14. **`tick_size` / `min_order_size` have NO default** — NULL when unknown; they
    come from the real market at discovery.

---

## Appendix A — how each 1.5B conclusion is encoded

| 1.5B conclusion | Where it lives in the schema |
|---|---|
| Historical price is **INDICATIVE, never executable** | `price_history.indicative_price` + `price_semantics` (CHECK forbids `EXECUTABLE`, default `MIDPOINT_ESTIMATED`) + `price_source` (`CLOB_PRICES_HISTORY`) |
| Backfill = `startTs/endTs + fidelity=1`, ≤48h windows + stitching; `DIRECT`/`DERIVED`; **never `interval=max`** | `price_history.fidelity` (`>=1`) + `source_window` CHECK ∈ {DIRECT, DERIVED}; rule documented in `config.ENDPOINTS['clob_prices_history']` |
| Time anchors for lead metrics | `markets.last_traded_time`, `last_meaningful_market_time`, `daily_high_time`, `resolution_timestamp` (formal), `settlement_timestamp` |
| Resolution discovery retires hardcoded stations | `markets.station`, `station_identifier` (ICAO), `resolution_source`, `unit`, `rounding_rule`, `winning_outcome`, `resolution_timestamp`, `settlement_timestamp` |
| Fees are epoch-dependent; **never assume 0** | `market_fee_schedule` (`taker_fee`, `maker_rebate`, `effective_from/to`, `fee_status` with `UNKNOWN`), **versioned** (PK includes `dataset_version, record_version`) + `markets.fee_regime` |
| No historical L2 order book (forward-only is a *layer* property) | `orderbook_snapshots` + `trades` are **forward-only**, tagged `collector_session_id` / `collector_started_at` / `collected_at` (live collector fills them) |
| No-look-ahead / as-of (availability) | `available_at` on weather + `AS_OF_COLUMNS` + `features.prediction_time` + `no_lookahead_verified` (a RESULT) + `query_asof` / `latest_asof` |
| Reproducibility | `dataset_versions` + provenance quintet on every fact + `backtest_results.dataset_version/model_version/random_seed/feature_list/code_version` |

## Appendix B — the §24 "market catalog"

The `markets` table is the §24 catalog **plus** the per-market resolution rule in
one row: identity (`market_id`, `condition_id`, `event_id`, `slug`, `question`,
`city`, `tag_ids`), lifecycle times (`open/close/last_traded/last_meaningful/
daily_high` + `data_start/data_end`), resolution (`station`,
`station_identifier`, `resolution_source`, `unit`, `rounding_rule`,
`winning_outcome`, `resolution_timestamp`, `settlement_timestamp`), trading
params (`tick_size`, `min_order_size`, `fee_regime`), the data-capability flag
(`available_resolution`), and provenance. Field names were derived from the
documented Gamma `/events` response and `phase1_5/resolution_discovery.py` — see
decision §10.7 for reconciliation with the authoritative spec.
