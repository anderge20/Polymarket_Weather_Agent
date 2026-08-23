# PHASE 2B — MARKET DISCOVERY + RESOLUTION DISCOVERY

**Scope (strict, reconfirmed):** market discovery + resolution discovery + catalog
normalization ONLY — `markets`, `outcomes`, market metadata, `tick_size`/
`min_order_size` (when really present), fee-regime discovery. **NOT** in 2B:
feature builder, Strategy A, models, backtesting engine, paper engine, execution
engine, L2 strategy, trading strategy. **No 2C.**
**Author/date:** Claude (Cowork) · 2026-08-21
**Environment:** authored WITHOUT Python. Everything is **IMPLEMENTED**; **nothing
is TESTED or VALIDATED** — the full catalog + pytest are USER-RUN on Hetzner (off
the Enel firewall). GAMMA was fetched read-only for a real SAMPLE (evidence).

This doc is the 2B closure, organized as the **13 delivery points**.

---

## 1. Code

`src/weather_agent/polymarket/` (new package; **supersedes/shadows** the legacy
flat `weather_agent/polymarket.py` — see §13):

- `__init__.py` — package marker + scope note.
- `discovery.py` — gamma `/events` pagination (newest-first, optional
  date-bounding), `build_market_records(event)` (pure parse), `ingest_event(...)`
  and `discover(...)` (idempotent upserts + provenance + dataset_version +
  per-market data_quality evidence + resumable checkpoint + rate-limit-safe error
  taxonomy).
- `resolution.py` — per-market resolution chain parser (ported/extended from
  `phase1_5/resolution_discovery.py`), grounded in the real description template.
- `fees.py` — gamma fee/tick/min mapping.

Schema increment: `database.py` migration **v2** (`phase2b_market_metadata`,
`SCHEMA_VERSION=2`) adds — idempotently — `markets.measurement_rule`,
`markets.available_at`, `markets.available_at_confidence`, `markets.source_timestamps`
(JSON), and `market_fee_schedule.raw_fee_fields` (JSON).

## 2. Tests (authored, NOT executed here)

- `tests/test_resolution.py` — station/ICAO/unit/rounding/measurement parsing;
  the **US 4-segment-URL ICAO regression**; band parsing; **resolved_outcome
  exactness** (exact-numeric; invalid combos → None); **event_winning_band status**
  (exactly-1 VERIFIED / 0 UNKNOWN / >1 DATA_ERROR); **band integrity** (clean
  partition / gaps / overlaps / double-open-ended / ordering); per-market
  confidence; ground-truth fixtures.
- `tests/test_integrity.py` — **token integrity** (#5): a token_id maps to exactly
  one market_id within a dataset; a crafted shared-token event is detected at build
  time (before the outcomes PK overwrites); real-sample post-ingest sanity.
- `tests/test_fee_schedule_identity.py` — **fee-regime identity** (#3): same
  feeType + same feeSchedule is consistent; same feeType + DIFFERENT feeSchedule is
  a documented collapse risk (see §9).
- `tests/test_fees_mapping.py` — recent `weather_fees` (KNOWN), legacy
  `fees_disabled` (KNOWN, 0 justified), absent (UNKNOWN); tick/min present + NULL.
- `tests/test_discovery.py` — `build_market_records`; `ingest_event` writes with
  provenance + dataset_version; **idempotency**; Ankara weather_fees path;
  dataset_version registration. Uses the `con` fixture (temp DuckDB).
- `tests/test_no_lookahead_adversarial.py` — the **3 adversarial specs** (§ below),
  SKIPPED/pending for the feature-builder subphase.
- `tests/gamma_fixtures.py` — REAL gamma events (NYC legacy, Ankara recent).
- The 2A `tests/test_no_future_information.py` semantic test is kept.

## 3. This document — `PHASE_2B_MARKET_DISCOVERY.md`.

---

## 4. Markets discovered (SAMPLE evidence — not the full catalog)

Read-only GAMMA sample fetched this session (full catalog = USER-RUN on Hetzner):

| Event | City | Target date | Age | #markets | Fee epoch | Notes | Confidence |
|---|---|---|---|---|---|---|---|
| id 869074 | Ankara | 2026-08-20 | recent | 11 | `weather_fees` | winner **31°C** | VERIFIED (complete) |
| id 869075 | Wellington | 2026-08-20 | recent | 8 (truncated) | `weather_fees` | station NZWN; body cut by size cap | PARTIAL (see §12) |
| id 128661 | NYC | 2025-12-30 | ~8 mo | 8 | `fees_disabled` (legacy) | winner **32-33°F**, **disputed→resolved** | VERIFIED (complete) |

Discovery evidence recorded per market (in `data_quality`): `endpoint`
(`gamma /events`), `params` (tag_id=104596, closed=true, order=endDate,
ascending=false/true, limit), `fetched_at`, DIRECT vs DERIVED vs UNKNOWN field
lists, resolution confidence, `uma_resolution_statuses`, `disputed`, and
`dataset_version`. Coverage is intentionally small (evidence, not census).

## 5. Outcomes / tokens

Each gamma market (a band) → one `markets` row + **two `outcomes` rows** (Yes,
No). Per outcome: `token_id`=`clobTokenIds[i]` (DIRECT), `band_label`=
`groupItemTitle` (DIRECT), `(lo,hi)` parsed from the band label (DERIVED),
`outcome_index` 0/1, `is_winner` = `float(outcomePrices[i]) == 1.0` (DERIVED,
exact-numeric — settlement ground truth). Example (NYC 32-33°F winner): Yes token
is_winner=True, No token is_winner=False, lo/hi=(32,33).

## 6. Resolution mapping (unambiguous per-market chain)

Parsed from **each market's own** `description`/`resolutionSource`/`umaEndDate`/
`outcomePrices` (never a city/station approximation):

`market → token/outcome → resolution_source → station → station_identifier →
measurement_rule → unit → rounding_rule → resolution_timestamp → winning_outcome`

| Chain field | Source | Confidence |
|---|---|---|
| resolution_source | market `resolutionSource` / URL in description | VERIFIED |
| station | "recorded at the **<name>** Station" in description | VERIFIED |
| station_identifier | **tail** of the Wunderground URL (ICAO) | VERIFIED |
| measurement_rule | description ("Daily Observations" / "by the Forecast") | VERIFIED |
| unit | "degrees Celsius/Fahrenheit" in description | VERIFIED |
| rounding_rule | "measures temperatures to whole degrees …" | VERIFIED |
| resolution_timestamp | `umaEndDate` | VERIFIED |
| winning_outcome | `outcomePrices`, exact-numeric: RESOLVED iff one price=1 & rest=0, else None | VERIFIED / UNKNOWN |

**Winner determination (exact, statused — #1/#2).** `resolved_outcome()` requires
EXACTLY one outcome price == 1 and the rest == 0 (exact numeric, never
`startswith`); any other combination → None (UNKNOWN/INVALID). `event_winning_band()`
returns a STATUS: exactly one winning band → VERIFIED; zero → UNKNOWN (unresolved);
more than one → DATA_ERROR (inconsistent_resolution) — it never returns a "first
match". `outcomes.is_winner` is likewise exact (`float(price)==1.0`).

**Band integrity (#6).** `resolution.band_integrity(labels)` treats a band set as a
probability partition WITHOUT assuming gamma is perfect: it orders the bands,
identifies the single lower-open ('or below') and upper-open ('or higher') bands,
and detects overlaps and integer-temperature gaps (`is_partition` True only when one
lower-open + one upper-open + no overlaps + no gaps). Critical for the future
P(max_temp = band) with sum(prob) ≈ 1. **Token integrity (#5):** within a
dataset_version a token_id must map to exactly one market_id (checked at build time;
the `outcomes` PK enforces one row per token per dataset).

**Ground-truth separation (#3).** We store FOUR distinct things and never conflate
them: **market metadata** (ids/slug/question/times/tick/min/fee_regime),
**resolution metadata** (station/identifier/source/unit/rounding/measurement_rule/
resolution_timestamp), **observed weather data** (**NONE in 2B** — weather
ingestion is a separate subphase), and the **final resolved outcome**
(`markets.winning_outcome` + `outcomes.is_winner`, i.e. Polymarket/UMA
settlement). `measurement_rule` records HOW the outcome was measured but 2B stores
NO observed temperature; the resolved outcome must not be treated as a weather
observation.

## 7. Station mapping (per market, from the sample)

| Market (sample) | station | station_identifier | resolution_source (tail) |
|---|---|---|---|
| NYC 2025-12-30 (all bands) | LaGuardia Airport | **KLGA** | .../us/ny/new-york-city/KLGA |
| Ankara 2026-08-20 (all bands) | Esenboğa Intl Airport | **LTAC** | .../tr/%C3%A7ubuk/LTAC |
| Wellington 2026-08-20 | (per description) | **NZWN** | .../nz/wellington/NZWN |

**Regression captured:** US URLs carry an extra state segment
(`us/ny/new-york-city/KLGA`) vs non-US (`tr/%C3%A7ubuk/LTAC`). The ICAO is the
**last** path segment; a fixed-position regex would mis-read US markets (which
include the target cities NY/Chicago/LA). `resolution.py` extracts the URL tail
and `test_resolution.py::test_icao_from_us_4segment_url` guards it.

## 8. Measurement rules (the template CHANGED over time)

| Epoch (sample) | Description wording | measurement_rule stored |
|---|---|---|
| Recent (Ankara 2026-08) | "highest temperature recorded in the **'Daily Observations'** table … not the 'Day High & Low' summary" | "highest temperature in the 'Daily Observations' table (not Day High & Low)" |
| Legacy (NYC 2025-12) | "highest temperature … **by the Forecast** … once information is finalized" | "highest temperature 'by the Forecast', once data finalized (legacy template)" |

Both are captured verbatim-ish so the epoch difference is explicit and never
conflated. If neither pattern is present → measurement_rule = NULL (UNKNOWN).

## 9. Fee mapping (epoch-dependent; never assume 0 without justification)

Real gamma fee fields (VERIFIED): recent markets carry `makerBaseFee=1000`,
`takerBaseFee=1000`, `feesEnabled=true`, `feeType="weather_fees"`,
`feeSchedule={exponent:1, rate:0.05, takerOnly:true, rebateRate:0.25}`; legacy
markets carry `feeType=null`, `feesEnabled=false` and NO schedule.

| Case | `market_fee_schedule` row | fee_status |
|---|---|---|
| Recent (weather_fees) | fee_regime=`weather_fees`, taker_fee=`0.05`, maker_rebate=`0.25`, raw_fee_fields=verbatim | **KNOWN** |
| Legacy (disabled) | fee_regime=`fees_disabled`, taker_fee=`0.0`, maker_rebate=`0.0` (0 **JUSTIFIED** by `feesEnabled=false`, not a default) | **KNOWN** |
| No fee fields at all | fee_regime=`UNKNOWN`, fees NULL | **UNKNOWN** |

**Interpretation caveat (open decision):** the exact UNIT semantics of
`makerBaseFee/takerBaseFee=1000` and how they relate to `feeSchedule.rate=0.05`
are NOT documented by what we fetched. We store the RAW fields verbatim
(`market_fee_schedule.raw_fee_fields`) and use `feeSchedule.rate`/`rebateRate` as
the best-documented effective values. `fee_status='KNOWN'` means "read from gamma";
the interpretation must be confirmed before any net-edge/execution modeling
(Strategy A). Note the 2A `fee_status` vocabulary is {KNOWN,UNKNOWN,ESTIMATED,
DEPRECATED}; "KNOWN" here == the confidence "VERIFIED" (fields read from source).

**Fee-regime identity (#3) — GLOBAL within a dataset (assumption), now CODE-ENFORCED.**
`fee_regime` is derived from `feeType` only and is part of the `market_fee_schedule`
PK. In the REAL sample every market sharing a fee_regime shares an IDENTICAL
feeSchedule, so fee_regime is treated as **global within a dataset** and **no
`fee_schedule_hash` is introduced yet**. This is no longer just a documented
assumption: `discovery.ingest_event` computes `fees.fee_schedule_hash(raw_fee_fields)`
and keeps a `fee_registry` (shared across events by `discover`). The FIRST time two
markets share a `fee_regime` with a DIFFERENT feeSchedule — this run or already
persisted for the dataset — it **raises `FeeScheduleConflict`**; `discover` catches
it, marks the run **`DATA_ERROR - fee_schedule_conflict`** and **STOPS** (no silent
upsert/collapse). That is the trigger to add a `fee_schedule_hash` identity.
`test_fee_schedule_identity.py::test_ingest_event_raises_on_fee_schedule_conflict`
exercises the guard. NOTE: `makerBaseFee`/`takerBaseFee` are captured RAW only and
are **never** used in any edge / EV / P&L / sizing calculation (2B performs none).

## 10. Tick / min order mapping

Gamma keys (VERIFIED, present on BOTH epochs in the sample):
`orderPriceMinTickSize=0.001` → `markets.tick_size`; `orderMinSize=5` →
`markets.min_order_size`. If a field is absent → **NULL** (correction #7; no
hardcoded default). `test_fees_mapping.py::test_tick_min_absent_is_null` guards it.

## 11. available_at / source-timestamp semantics (criterion #1)

All gamma timestamps are registered as real fields; `available_at` is **not**
assumed from any of them.

| gamma field | example | meaning | 2B mapping | confidence |
|---|---|---|---|---|
| `createdAt` | `2025-12-28T11:00:18.86Z` | market RECORD created at source | `markets.source_timestamp` (provenance) | VERIFIED (record creation) — **not** availability |
| `startDate` | `2025-12-28T11:12:03Z` | market start | `markets.open_time` | VERIFIED |
| `closedTime` | `2025-12-30 09:09:31+00` | market actually closed (space+`+00` fmt) | `markets.close_time` | VERIFIED |
| `umaEndDate` | `2025-12-30T09:09:31Z` | UMA resolution finalized = **formal_resolution_time** | `markets.resolution_timestamp` | VERIFIED |
| `endDate` | `2025-12-30T12:00:00Z` | scheduled close (noon UTC) | `markets.source_timestamps` (JSON) | VERIFIED |
| `updatedAt`, `acceptingOrdersTimestamp` | ISO-Z | last update / order-accept start | `markets.source_timestamps` (JSON) | VERIFIED |
| **available_at** (knowable to an external agent) | — | **NOT derivable from gamma metadata** | `markets.available_at=NULL`, `available_at_confidence='UNKNOWN'` | **UNKNOWN** |
| **settlement_timestamp** (distinct payout time) | — | not distinctly exposed by gamma | `NULL` | **UNKNOWN** |
| **last_traded_time** | — | no trade data in discovery (2B) | `NULL` | **UNKNOWN** |

Policy: **available_at is NEVER set to `createdAt`/`updatedAt`/`ingestion_timestamp`/
`fetched_at`.** It stays UNKNOWN in 2B. The full raw timestamp set is preserved
verbatim in `markets.source_timestamps` for reproducibility and for a later
subphase to derive availability with justification. (Forecast/observation
availability is a POLICY for the weather-ingestion subphase — `weather_*.available_at`
already exists in 2A and is the as-of anchor there; 2B integrates no weather.)

Three clocks, never confused: **occurrence/source event** (createdAt, startDate,
closedTime, umaEndDate) vs **available_at** (UNKNOWN here) vs **ingestion_timestamp**
(our write time).

## 12. Errors / rate limits

- **Size-cap truncation (not a rate limit):** the `limit=4` gamma fetch returned
  ~89k chars and was **truncated by the sandbox web_fetch size cap** — only 2 of 4
  events came back intact (Ankara complete; **Wellington truncated mid-`markets[]`**).
  Marked PARTIAL, not inferred. The `limit=1` fetches returned complete events.
  → On Hetzner (no size cap, real paging) the full catalog is obtainable.
- **No HTTP 429 / rate-limit** was encountered against gamma this session.
- **No CLOB / data-api** was touched in 2B (per instruction — CLOB saturates).
- **Local execution unavailable:** the bash workspace does not start on this device,
  so no code/tests were run here.
- Runtime policy (in `discovery.py`): any gamma error/rate-limit → the run records
  `"UNVERIFIED - <STATUS>"` and **STOPS**; gaps are never filled by silent
  inference (#5). Resumable via the event-id checkpoint.

## 13. IMPLEMENTED / TESTED / VALIDATED

| Component | IMPLEMENTED | TESTED | VALIDATED |
|---|---|---|---|
| discovery.py / resolution.py / fees.py | ✅ | ❌ | ❌ |
| migration v2 (market metadata columns) | ✅ | ❌ | ❌ |
| 2B tests (resolution/fees/discovery) | ✅ authored | ❌ (0 run) | ❌ |
| adversarial no-look-ahead specs | ✅ (pending stubs) | ❌ | ❌ |
| GAMMA sample catalog (evidence) | ✅ (2 complete + 1 partial) | — | — |
| Full catalog | ❌ (USER-RUN on Hetzner) | — | — |

No Python here → **everything IMPLEMENTED; nothing TESTED; nothing VALIDATED.**

### Run on Hetzner
```bash
pip install -r requirements-pipeline.txt
export WEATHER_AGENT_DB_PATH="$PWD/data/processed/weather_agent.duckdb"
PYTHONPATH=src python -c "from weather_agent.database import init_db; init_db(); print('schema v2')"
PYTHONPATH=src pytest -q                      # 2A + 2B tests; adversarial stubs SKIP
# then the real (partial-catalog) discovery, off-firewall:
PYTHONPATH=src python -c "import requests, datetime as dt; \
from weather_agent.database import connect, init_db; \
from weather_agent.polymarket.discovery import discover; \
con=init_db(connect()); \
print(discover(con, 'ds_'+dt.date.today().isoformat()+'_gamma_v1', max_pages=5))"
```

---

## No-look-ahead policy (criterion #2)

2B is discovery only — it builds **no features, prices, or forecasts** — so the
REAL no-look-ahead validation (the 6 checks that gate
`features.no_lookahead_verified=TRUE`, **never** a manual TRUE) is implemented in
the **feature-builder subphase**, not here. In 2B we (a) keep the 2A runnable
semantic test; (b) ship the **3 adversarial specs** as documented, SKIPPED tests
(`test_no_lookahead_adversarial.py`): forecast `issue_time<T` but
`available_at>T` → excluded; observation occurrence `<T` but `available_at>T` →
excluded; `resolution_timestamp<T` → resolution still forbidden as a
pre-resolution feature (label only).

## Decisions affecting Strategy A (later)

1. **Legacy flat `polymarket.py` is shadowed** by the new `polymarket/` package;
   treat it as reference and delete it in a cleanup step once 2B validates.
2. **`markets` is per-band**; `winning_outcome` is per band-market ("Yes"/"No");
   the event's winning band is derivable (band with "Yes") and recorded in the
   evidence — Strategy A must aggregate at the event level itself.
3. **market `available_at` is UNKNOWN** — Strategy A must NOT use market metadata
   timestamps as an as-of signal; use price `observation_time` (from the price
   ingestion subphase) for as-of, per the 2A AS_OF_COLUMNS.
4. **Fee interpretation is unconfirmed** (rate vs base-fee unit). Net-edge and
   execution modeling in Strategy A must confirm the fee semantics from
   `raw_fee_fields` before trusting `taker_fee`/`maker_rebate`.
5. **Fee/measurement templates are epoch-dependent** (weather_fees vs disabled;
   Daily Observations vs by-the-Forecast). Strategy A backtests spanning epochs
   must segment by regime/template.
6. **orderbook/trades remain empty** (forward-only; 2B collects none) — any
   microstructure/Strategy-B work stays blocked on the live collector subphase.
7. **Full catalog is USER-RUN**; 2B delivered code + a small real sample, not the
   census. Strategy A sizing/backtests need the Hetzner-run catalog first.
8. **Fee-regime identity is GLOBAL within a dataset** (documented assumption; no
   `fee_schedule_hash`) — revisit only if gamma varies feeSchedule under one feeType
   (guarded by `test_fee_schedule_identity.py`). Do NOT use fees for net edge yet
   (interpretation still pending, #8).
9. **Resolution/winner determination is exact + statused** (resolved_outcome exact
   numeric; event_winning_band VERIFIED/UNKNOWN/DATA_ERROR). `umaEndDate` =
   formal_resolution_time; settlement_time and last_traded_time are UNKNOWN in 2B.
