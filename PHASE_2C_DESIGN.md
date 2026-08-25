# PHASE 2C — DESIGN (Blocker 1: checkpoint/resume → VALIDATED)

STATUS: DESIGN ONLY. No code modified. Nothing committed. Same evidence discipline as
2B (IMPLEMENTED ≠ TESTED ≠ VALIDATED; nothing VALIDATED without a real run).
Scope of THIS document: **Blocker 1 (checkpoint/resume)**. Blocker 2 (no-look-ahead) is
summarized at the end but designed in detail only after Blocker 1 is approved.

Honest scope note: orderbook/trades are forward-only (no historical L2); end-to-end
no-look-ahead VALIDATED is achievable for weather + price_history only (Blocker 2).

---

## 1. Current state of the migrations

- **SCHEMA_VERSION = 2** (`database.py:50`).
- **MIGRATIONS** (`database.py:532-543`) is an ordered list of dicts:
  - v1 `phase2a_initial_schema` → `statements = _SEQUENCES + _DDL` (all 2A tables).
  - v2 `phase2b_market_metadata` → `statements = _DDL_V2` (idempotent `ALTER TABLE …
    ADD COLUMN IF NOT EXISTS` for market metadata + `raw_fee_fields`).
- **How `init_db` applies them** (`database.py:604-627`): ensures `schema_version`
  meta table (`:582`), reads `current = get_schema_version` (= `MAX(version)`, `:595`),
  then for each migration with `version > current`: `BEGIN TRANSACTION` → run every
  statement → `INSERT INTO schema_version(version,name,applied_at)` → `COMMIT`; on any
  error `ROLLBACK` and re-raise. Idempotent and safe to call repeatedly.
- **Transactionality:** each migration is atomic (its own BEGIN/COMMIT). Convention
  (comment `:530-531`): "Add a new dict (version+1) for future changes; never edit a
  shipped migration in place."

## 2. Current state of `ingest_event` / `discover`

- **Transaction bounds** (`discovery.py`): `ingest_event` opens `BEGIN TRANSACTION`
  (`:265`), then upserts, in order, `markets` → `outcomes` → `market_fee_schedule` →
  `data_quality`, and `COMMIT` (`:344`).
- **When an event is "committed":** at that `COMMIT` (`:344`). Only then are its rows
  durable.
- **In-memory checkpoint today:** `discover(…, checkpoint: set[str] | None)` (`:400`),
  init `checkpoint = checkpoint or set()` (`:416`); skip already-seen `if eid in
  checkpoint: continue` (`:445-448`); advance **after** `ingest_event` returns, i.e.
  AFTER COMMIT: `checkpoint.add(eid)` (`:461-468`). The set lives only in the call
  frame — **no disk persistence anywhere** (confirmed repo-wide; the only other
  "checkpoint" is the unrelated `phase1_5/live_collector.py` SQLite table).
- **On rollback** (`:345-352`): `except Exception: con.execute("ROLLBACK;")` →
  reverts the event's rows AND pops this event's additions from the shared
  `fee_registry`, then `raise`. `discover` reacts: on `FeeScheduleConflict` sets
  `status="DATA_ERROR"`, `stopped_early=True` and returns (`:453-460`); on page/HTTP
  errors sets an `UNVERIFIED-…` status and `break`s (`:436-442`). In both cases the
  failed event's id is **never** added to the checkpoint → it is retried on resume.
  Resume is duplicate-safe because writes are upserts on full PKs.
- **Current test coverage** = in-memory checkpoint + injected in-process fault
  (`tests/test_ingest_atomic.py:147`; `scripts/validate_2b.py` §21). Self-labelled
  TESTED/UNVERIFIED: no disk checkpoint, no real interruption, no real-Gamma resume.

## 3. Proposed design — persistent checkpoint/resume

### 3.1 `discovery_checkpoint` table (PK / indices)
```sql
CREATE TABLE IF NOT EXISTS discovery_checkpoint (
    dataset_version VARCHAR NOT NULL,
    event_id        VARCHAR NOT NULL,
    committed_at    TIMESTAMPTZ DEFAULT now(),
    run_id          VARCHAR,               -- discover() run that committed the event
    PRIMARY KEY (dataset_version, event_id)
);
```
PK `(dataset_version, event_id)` gives both the lookup index and idempotency (a retried
event upserts the same key, never duplicates). No extra index needed (lookups are by
`dataset_version`, the PK prefix). Operational/meta table → **NOT added to `ALL_TABLES`**
(keeps 2A/2B round-trip & provenance tests unaffected).

### 3.2 Where it is created (see §4 for the version decision)
Two options depending on the §4 decision: (A) as migration **v3**; or (C) idempotent
`CREATE TABLE IF NOT EXISTS` in `init_db` outside the version list. Both create the same
table; they differ only in whether SCHEMA_VERSION is bumped.

### 3.3 Atomic write of data + checkpoint (single transaction)
The mark is written as the **last statement inside `ingest_event`'s existing
BEGIN…COMMIT**:
```
ingest_event(con, event, dataset_version, run_id=None, …):
    BEGIN TRANSACTION
        upsert markets / outcomes / market_fee_schedule / data_quality      (unchanged)
        checkpoint_mark(con, dataset_version, event_id, run_id)              (NEW, last)
    COMMIT                          # persists rows + mark atomically
    # on ANY exception: ROLLBACK   # neither rows nor mark persist
```
Helper `checkpoint_mark` = one `INSERT … ON CONFLICT (dataset_version,event_id) DO
NOTHING` (single statement; caller owns the txn — same convention as `insert`/`upsert`).

### 3.4 Loading the checkpoint on a new process
```
discover(con, dataset_version, run_id=<new>, checkpoint=None, …):
    processed = checkpoint_load(con, dataset_version) | (checkpoint or set())
    #           ^ SELECT event_id FROM discovery_checkpoint WHERE dataset_version=?
    for ev in events:
        if ev.id in processed: continue
        ingest_event(con, ev, dataset_version, run_id=run_id)
        processed.add(ev.id)        # in-memory mirror; disk table is source of truth
```
A brand-new OS process opening the same DuckDB file resumes exactly where the last one
committed (checkpoint read from disk, not memory).

### 3.5 Exact behaviour under SIGKILL
- Kill **before COMMIT**: the transaction is uncommitted → DuckDB WAL crash-recovery
  rolls it back on next open → NO partial event rows AND NO orphan checkpoint mark.
- Kill **after COMMIT**: rows + mark are durable → the event is skipped on resume.
- There is no interval where the mark and the rows can disagree (both are in the same
  transaction). DuckDB is single-writer: resume is sequential (killed process releases
  the file, then the resumer opens it).

## 4. Compatibility with Phase 2B  (THE DESIGN PROBLEM)

**Problem detected.** Bumping `SCHEMA_VERSION` 2→3 (option A) breaks the **frozen
`validate_2b.py` §11 migration test** if that harness is ever re-run against the new
code.

**Exactly which part breaks.** validate_2b.py §11 builds a v1 DB, runs the real
`db.init_db()`, and asserts (hardcoded to the 2B era):
- `sv_after == 2` (`validate_2b.py:611` comment "expect 2", used in the `mig_ok`
  conjunction `:643`), and
- `len(applied) == 2` (`:643`, where `applied = SELECT … FROM schema_version`).

With a v3 migration, `init_db` reaches schema **3** with **3** applied migrations →
`sv_after==3`, `len(applied)==3` → `mig_ok` becomes False → §11 FAILS. You asked NOT to
modify `validate_2b.py`, so this is a genuine conflict, not a code smell.

Note: the **pytest** suite does NOT hardcode 2 — `test_schema_version_recorded` uses
`db.SCHEMA_VERSION` and `test_init_is_idempotent` uses `len(db.MIGRATIONS)` (both
dynamic) → the pytest suite stays green at v3. Only the `validate_2b.py` harness has the
hardcoded literals.

**Alternatives considered:**

- **Alt A — migration v3 + freeze validate_2b.py.** Add v3 properly; treat
  `validate_2b.py` as immutable 2B evidence (already VALIDATED at its commit; do NOT
  re-run it against the changed schema); run the 2B regression via the **pytest suite**
  (schema-agnostic, green at v3).
  Pros: clean migration-versioning discipline; checkpoint table tracked in
  `schema_version`. Cons: `validate_2b.py` is no longer re-runnable as-is (its §11 is
  stale); relies on accepting the harness as frozen.

- **Alt B — bump to v3 and update validate_2b.py §11 to compare against
  `db.SCHEMA_VERSION` dynamically.** Pros: cleanest long-term. **Cons: edits
  validate_2b.py, which you explicitly forbade → rejected.**

- **Alt C (SMALLEST to avoid the regression) — do NOT bump SCHEMA_VERSION; create
  `discovery_checkpoint` idempotently outside the migration list** (a
  `_ensure_checkpoint_table(con)` = `CREATE TABLE IF NOT EXISTS …` called by `init_db`
  and by `discover` on start). SCHEMA_VERSION stays 2, `MIGRATIONS` unchanged (len 2).
  Pros: **zero 2B regression** — validate_2b.py §11 still sees `sv_after==2`,
  `len(applied)==2` and stays green and re-runnable; `test_init_is_idempotent`
  (`n==len(MIGRATIONS)`) unaffected; smallest possible change. Cons: the checkpoint
  table's creation is not recorded as a numbered migration (it's an operational table,
  created on demand) — a small deviation from the "all schema via MIGRATIONS"
  convention.

**Proposed smallest solution (NOT implemented):** **Alt C.** It avoids the 2B
regression entirely with the least surface, keeps `validate_2b.py` untouched AND
re-runnable, and only costs the (minor) fact that an operational table is created
outside the versioned list. If you prefer strict migration discipline over
re-runnability, choose **Alt A** (v3 + frozen harness + pytest regression). Decision is
yours before any code is written.

## 5. Validation plan (Blocker 1)
1. **Controlled rollback:** inject a failure on the last event write → assert the
   event's rows are absent AND `discovery_checkpoint` has no row for it (atomic).
2. **Real SIGKILL between events (separate OS process, deterministic source):**
   `tests/support/checkpoint_runner.py` runs `discover()` against a canned 2-event
   fixture (stub session, no network). After event 1's COMMIT it does
   `os.kill(os.getpid(), SIGKILL)` before event 2. Test asserts the child died by
   signal −9, event 2 absent, event 1 present, no orphan mark for event 2.
3. **New process / resume:** a fresh subprocess opens the same on-disk DuckDB, loads
   the persisted checkpoint, and completes event 2.
4. **Comparison vs clean run:** run the same fixture once in a single clean process
   into a fresh DB → `counts(interrupted+resumed) == counts(clean)` exactly.
5. **No duplicates:** GROUP BY full PKs HAVING COUNT>1 == ∅ on markets/outcomes/
   market_fee_schedule/data_quality; exactly one `discovery_checkpoint` row per event.
6. **Real Gamma, two processes:** process 1 discover() real Gamma (≤5 events) →
   persists rows + checkpoint, closes; process 2 (new PID) same dataset_version + DB →
   skips committed events, processes remainder, 0 duplicates. (Runs on Hetzner/Actions.)
7. **Full Phase 2B regression:** run the entire pytest suite (`tests/`) after the v3/
   Alt-C change → must stay green (schema-agnostic assertions). Per §4, the frozen
   `validate_2b.py` harness is NOT the regression vehicle (Alt C keeps it green anyway;
   Alt A treats it as frozen).

## 6. Objective criteria to declare Blocker 1 VALIDATED
- schema present & correct after `init_db` (`discovery_checkpoint` exists;
  schema_version = 2 under Alt C or 3 under Alt A, per decision).
- Injected-failure event leaves NO rows and NO mark.
- Real SIGKILL of a SEPARATE process between events leaves no partial event and no
  orphan mark (WAL crash-recovery verified empirically).
- Fresh process resumes from disk checkpoint: 0 reprocessed, remainder completed,
  `counts == clean run`, 0 duplicate PKs.
- Real-Gamma two-process resume: run_ids recorded, per-process event ids, checkpoint
  rows, 0 duplicates.
- Full 2B pytest regression green.
- All produced by a REAL run (Actions/Hetzner) with evidence recorded in
  `PHASE_2C_VALIDATION_REPORT.md`.

## 7. Exact files to create / modify (Blocker 1)
- MODIFY `src/weather_agent/database.py` — checkpoint table (Alt C: `_ensure_checkpoint_
  table` + call in `init_db`; Alt A: `_DDL_V3` + MIGRATIONS v3 + `SCHEMA_VERSION=3`);
  helpers `checkpoint_load`, `checkpoint_mark`. (Do NOT add to `ALL_TABLES`.)
- MODIFY `src/weather_agent/polymarket/discovery.py` — `discover()` loads checkpoint
  from disk + accepts `run_id`; `ingest_event()` writes the mark inside its txn.
- CREATE `tests/test_checkpoint_resume.py` — rollback-no-mark, counts/no-dup, migration/
  regression orchestration.
- CREATE `tests/support/checkpoint_runner.py` — real-subprocess entry point (canned
  source + self-SIGKILL after event 1).
- CREATE `scripts/validate_2c.py` + `PHASE_2C_VALIDATION_REPORT.md` — 2C harness/report.
- **NOT touched:** `scripts/validate_2b.py`; no edits to existing 2B tests' semantics.

## 8. Risks, assumptions, not-yet-proven
- **R1 (decision needed):** the §4 SCHEMA_VERSION-vs-validate_2b.py conflict. Pick Alt C
  (smallest, zero regression) or Alt A (versioning purity + frozen harness).
- **R2:** SIGKILL-before-COMMIT safety relies on DuckDB WAL crash-recovery rolling back
  the uncommitted txn on reopen — a documented ACID guarantee; the SIGKILL test
  VALIDATES it empirically rather than assuming it. NOT YET PROVEN in this repo.
- **R3:** DuckDB is single-writer → resume is sequential (no concurrent writers claimed).
- **R4:** real-Gamma tests need network → run on Hetzner/Actions (Polymarket blocked on
  local nets); deterministic interruption uses the canned source, real Gamma only for
  the two-process resume.
- **R5:** `ingest_event` now also writes `discovery_checkpoint` (needs the table to
  exist; guaranteed by init_db). 2B tests count only fact tables → unaffected; to be
  reverified by the 2B pytest regression.
- **R6:** SIGKILL point is deterministic (`os.kill(getpid(), SIGKILL)` right after
  event 1 returns), not a race.
- **Not yet proven:** disk-checkpoint atomicity under real crash; real-Gamma
  two-process resume with 0 duplicates; full 2B regression green at the new schema.

---

## Blocker 2 (summary only — detailed design after Blocker 1 approval)
Real ingestion `ingest/weather.py` + `ingest/prices.py` (available_at derived from real
source availability; price INDICATIVE), a `features.py` as-of builder (uses only
as-of≤T rows, never resolution fields, sets `no_lookahead_verified=TRUE` after a guard),
un-skip the 5 no-look-ahead tests on real data. VALIDATED = real ingest + builder +
adversarial exclusion of `available_at>T` + resolution-as-label-only + all 5 tests green.
