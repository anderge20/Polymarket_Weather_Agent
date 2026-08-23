# HARNESS_CHANGELOG — 2A+2B real/reproducible/auditable validation

**Date:** 2026-08-21 · **Status:** IMPLEMENTED (authored here; NOT executed).
The REAL run — and therefore any TESTED/VALIDATED status and the VERDICT — is
produced only when the USER runs this on Hetzner. Nothing here is marked
TESTED/VALIDATED.

This revision implements the user's FINAL 14-condition spec (which supersedes the
earlier 5-point note). `scripts/validate_2b.py` was rewritten; `run.sh` /
`package.sh` are unchanged and still valid.

## Revision 2 — per-event ATOMICITY (turns the checkpoint caveat into a guarantee)

Bounded change (no scope expansion; nothing marked TESTED/VALIDATED here).

- **`discovery.py` — `ingest_event` is now transactional per event.** The whole
  event is written inside ONE DuckDB transaction:
  `BEGIN → market → outcomes → fee schedule → provenance/evidence → COMMIT`.
  If ANY operation fails (including a `FeeScheduleConflict`), the ENTIRE event is
  `ROLLBACK`-ed — an event can never be persisted partially. Row payloads are
  built (pure) BEFORE `BEGIN`. On rollback, the fee_regime keys this event added
  to the SHARED `fee_registry` are reverted, so a resume can retry the event and
  re-detect a genuine conflict.
- **Checkpoint advances only AFTER a successful COMMIT.** `discover` already adds
  the event id to the checkpoint only after `ingest_event` returns (i.e. after its
  COMMIT); a rolled-back event raises before that line and is retried on resume.
  Comment added to make the ordering explicit. `ingest_event → writes OK → COMMIT
  → checkpoint` (never `ingest → checkpoint → commit`).
- **`fee_schedule_conflict` ⇒ full event ROLLBACK.** market OK + outcomes OK, then
  a fee conflict → rollback of market+outcomes+fee for that event → event FAILED
  (`DATA_ERROR fee_schedule_conflict`), `discover` stops, checkpoint does NOT
  advance, and the prior committed fee row is untouched (no silent overwrite, no
  info loss, no false success).
- **New tests (`tests/test_ingest_atomic.py`)**: `test_ingest_event_atomic_success`,
  `test_ingest_event_atomic_rollback` (injected failure on the last write →
  everything rolls back), `test_fee_conflict_rolls_back_entire_event` (within-event
  conflict rolls back the already-written 1st market too),
  `test_checkpoint_advances_only_after_commit` (discover: event1 committed+
  checkpointed; event2 conflicts, rolls back, NOT checkpointed). Added to the
  harness pytest 2B set.
- **Harness `validate_2b.py`**:
  - §20 fee guard now COMMITS event A (weather_fees @0.05), then ingests a
    conflicting event B (@0.10) and asserts: conflict raised, prior row NOT
    overwritten, and event B rolled back ENTIRELY (market fB absent).
  - §21 checkpoint now exercises the REAL transaction: event1 commit→checkpoint;
    event2 injected-fault→rollback→checkpoint NOT advanced; resume retries event2→
    commit→checkpoint; event1 not duplicated (WRITE/RESUME/NO_DUPLICATION). Still
    TESTED/UNVERIFIED (in-memory checkpoint + injected fault), never VALIDATED.
  - **`FLAGS["J_no_inferred"]` and `FLAGS["K_evidence_backed"]` now START FALSE.**
    J flips true only after §23 shows distinct statuses + stop-on-error. K is a
    FINAL audit: every VALIDATED item must carry a real-execution `EVIDENCE`
    record (kind starting `real_`); if any VALIDATED item lacks one, K=False and
    the VERDICT is `PHASE 2B NOT VALIDATED`. Each `mark_real(...)` now attaches an
    evidence record, and §24 prints the evidence audit.

## Revision 3 — evidence hardening + explicit transaction-ownership check

Three MINOR hardenings before the Hetzner run (no other functional change; nothing
marked TESTED/VALIDATED here).

1. **Evidence audit strengthened (`_check_evidence` + `REQUIRED_EVIDENCE`).** K no
   longer passes on a `real_*` kind alone: each VALIDATED item must carry the
   MINIMUM evidence fields for its kind (each non-None) or K=False → VERDICT
   `PHASE 2B NOT VALIDATED`. `timestamp_utc` is auto-added to every record. Required
   fields per kind:
   - migration: `db` + `schema_before` + `schema_after`
   - discovery: `markets` (count) + `market_ids` (the processed market ids) + `event_id` + `dataset_version`
   - idempotency: `counts_before`/`counts_after` + `checksum_before`/`checksum_after` (SHA-1 of the content snapshot) + `dataset_version`
   - provenance: `n_rows` + `dataset_version`
   - duplicates: `dataset_version`
   - token: `event_id` + `conflicts` (observed) + `dataset_version`
   - winner: `event_id` + `status` (observed)
   - band: `event_id` + `n_bands` + `is_partition` (observed)
   - fee: `regimes` (fee_regime list) + `conflict_observed` + `dataset_version`

   §24 prints a per-item audit (ok / missing-fields).
2. **Checkpoint/resume classification unchanged** — remains **TESTED/UNVERIFIED,
   never VALIDATED** (offline stubs + in-memory checkpoint). Reconfirmed; no change.
3. **Explicit transaction-ownership check (atomicity).**
   - `database.py`: `insert` and `upsert` docstrings now state they run ONE
     statement and do NOT commit/rollback/change autocommit — the CALLER owns the
     transaction. (Verified by inspection: `insert`/`insert_many`/`upsert`/`query`
     are simple `con.execute(...)` calls with no `commit()`/`rollback()`/`BEGIN`.)
   - Harness §11 now runs a runtime PROBE: open a transaction, `db.insert` then
     `ROLLBACK` (again with `db.upsert`), assert the row is gone. If a helper
     autocommitted the row would survive → `helpers-do-not-autocommit` FAILED →
     atomicity FAILED (not VALIDATED) → NOT VALIDATED. §11 retitled
     "MIGRATION RESULT + TRANSACTION OWNERSHIP".
   - New pytest `test_helpers_do_not_autocommit` asserts the same at unit level.

## Master status rule (enforced by the report generator)
IMPLEMENTED = written, not executed. TESTED = executed + passed (unit test /
synthetic fixture / offline stub / schema-config check). VALIDATED = behaviour
executed AND checked against a real run and, where it applies, real data. FAILED
/ SKIPPED as usual. A pytest PASS is **never** auto-VALIDATED. Classification is
by evidence TYPE, not by "it passed".

## Condition-by-condition

1. **Migration v1→v2 REAL (§11).** Distinguishes (A) CLEAN INIT V2 (baseline,
   NOT a migration) from (B) REAL v1→v2: builds a DuckDB at schema **v1** only
   (applies `db.MIGRATIONS[1].statements` explicitly + records schema_version=1),
   inserts representative v1 rows (markets/outcomes/market_fee_schedule/
   dataset_versions), then runs the REAL migration path `db.init_db()` to reach
   v2 and verifies: schema_version BEFORE=1 / AFTER=2, v2 columns absent at v1 and
   present after, v1 data SURVIVES with original values, new columns NULL-able for
   old rows, row COUNTS preserved across the migration, PK still enforced (old row
   unique), and the migration is IDEMPOTENT (2nd `init_db` is a no-op).
   The real path EXISTS (`db.MIGRATIONS` + `db.init_db`), so this is a real
   migration test, not UNIMPLEMENTED. If no reusable path existed, the harness
   marks `REAL_V1_V2_MIGRATION = UNIMPLEMENTED` and explains what is missing —
   it never calls a clean v2 init a "validated migration".

2. **Idempotency COMPLETE (§15).** Re-ingests the same event under the same
   dataset_version and checks ALL discovery entities — markets, outcomes,
   market_fee_schedule, data_quality, dataset_versions: identical row counts, an
   unchanged business-content snapshot (identity + version + values, excluding
   ingestion_timestamp), and `max(record_version)` staying 1 (identical input ⇒
   NO new version). The 2nd ingestion must be a logical NO-OP; any new
   record_version is a FAIL.

3. **Duplicates vs versioning (§16).** Uses the REAL schema PK/UNIQUE identity per
   table (markets (market_id,dataset_version,record_version); outcomes
   (token_id,…); market_fee_schedule (fee_regime,…); data_quality
   (ref,dataset_version)) — NOT market_id alone. Physical PK-duplicates must be 0;
   multiple record_versions for one natural key are legitimate versioning, not
   duplicates. The report states which identity was used per table.

4. **Checkpoint / RESUME (§21).** Real resume-after-interruption with three named
   results: CHECKPOINT_WRITE_TEST, CHECKPOINT_RESUME_TEST,
   CHECKPOINT_NO_DUPLICATION_TEST. Scenario: a 2-event stream; event 1 is
   processed, then a page-2 fetch FAILS (500) → interruption BEFORE event 2; the
   checkpoint retains event 1; a second run reads the checkpoint, SKIPS event 1,
   processes event 2, and no duplication occurs. Because it uses OFFLINE stubs +
   an IN-MEMORY checkpoint, it is **TESTED/UNVERIFIED, not VALIDATED**, and the
   limitation (real interruption vs live gamma + disk-persisted checkpoint) is a
   recorded BLOCKER.

5. **Fee schedule guard (§20).** Deliberately provokes same fee_regime +
   different feeSchedule (rate 0.05 vs 0.10) and checks: FeeScheduleConflict
   raised, the previous row (0.05) is NOT overwritten (verified by re-reading it),
   no false success. Synthetic ⇒ TESTED. Fee mapping from the REAL sample ⇒
   VALIDATED. makerBaseFee/takerBaseFee captured RAW only, used in NO calculation.

6. **Winner / outcome / band (§18, §19).** Real data + ADVERSARIAL fixtures.
   Winner counts 0→UNKNOWN, 1→VERIFIED, >1→DATA_ERROR. Resolution is exact-numeric
   (exactly one price==1.0, rest==0.0 ⇒ RESOLVED; else INVALID_RESOLUTION) with
   tests that startswith/truthiness/first-match are NOT used (['1','0']→Yes;
   ['0.5','0.5'], ['1','0.3'], ['0','0']→None). Band adversarials: clean partition,
   gap, overlap, multiple open-ended — structure detected, never forced to a
   perfect partition.

7. **Token integrity (§17).** Real sample: token_id → exactly one market_id within
   the dataset_version (VALIDATED). Adversarial: a token deliberately placed on two
   markets is detected IN-MEMORY from `build_market_records` output, BEFORE any
   PK/UPSERT could hide it (TESTED).

8. **available_at / as-of (§22).** Verifies available_at stays NULL /
   confidence=UNKNOWN for ingested markets and is never auto-set to
   ingestion_timestamp/createdAt/updatedAt, and that AS_OF_COLUMNS keys weather on
   `available_at`. This is a SCHEMA/CONFIG check ⇒ **TESTED**, explicitly **NOT
   VALIDATED**; end-to-end no-look-ahead is NOT validated yet (BLOCKER, deferred to
   price/weather ingestion + feature builder).

9. **Polymarket real data (§13, §14 + 14b JSON appendix).** Smoke ingests ≤5 REAL
   markets and records, per market: event_id, market_id, token_id(s), city, target
   date, station, ICAO, measurement_rule, unit, resolution status, winner, fee
   regime, tick, min order, dataset_version, fetched_at, source endpoint, plus a
   DIRECT/DERIVED/UNKNOWN classification (nothing inferred).

10. **Rate limit / network (§23).** Explicitly distinguishes SUCCESS, EMPTY,
    HTTP_ERROR, NOT_FOUND(→HTTP_ERROR), RATE_LIMITED, INVALID_PAYLOAD(→PARSE_ERROR),
    TIMEOUT, NETWORK_ERROR (timeout ≠ empty ≠ rate-limit; none filled by inference)
    and confirms discover() records UNVERIFIED and STOPS on an error status.

11. **Report.** `results/PHASE_2B_VALIDATION_REPORT.md` now carries the required
    fields: 1 run_id, 2 UTC, 3 git commit, 4 Python, 5 OS, 6 dep versions,
    7 dataset_version, 8 DB path, 9 schema BEFORE, 10 schema AFTER, then sections
    11 migration, 12 pytest, 13 discovery, 14 real markets (+14b JSON), 15
    idempotency, 16 duplicate/version, 17 token, 18 winner/outcome, 19 band, 20 fee
    guard, 21 checkpoint/resume, 22 as-of/no-look-ahead, 23 error taxonomy, 24 final
    matrix — plus a **BLOCKERS FOR PHASE 2C** section and a **VERDICT**.

12. **No auto-pass.** Status is assigned by evidence type at runtime (pytest→TESTED;
    real gamma fetched+parsed+persisted+checked→VALIDATED; schema existence→TESTED;
    real v1→v2 migration→VALIDATED only if actually executed; no-look-ahead
    fixture→TESTED; real as-of data→VALIDATED, deferred).

13. **No advance.** No 2C/feature builder/Strategy A/backtest/forecasting/paper/
    execution/wallet/orders/L2.

14. **Verdict.** The report emits "PHASE 2B VALIDATED" only if A pytest ran, B no
    critical FAIL, C migration validated-or-explicitly-UNIMPLEMENTED, D discovery
    works, E idempotency, F token, G winner/outcome/band, H fee guard, I
    checkpoint (demonstrated or explicitly limited), J nothing inferred, K nothing
    VALIDATED without evidence — otherwise "PHASE 2B NOT VALIDATED" + a blockers
    list.

## Retained
Preflight (11 checks, critical/non-critical + hard stop); #3 fee guard in code;
fees RAW only; local report is the source of truth; paste.rs `--upload` OFF by
default (upload failure ≠ validation failure; return one-liner is separate);
isolation in /opt/pmw-validate; ≤5 real markets; scope 2B only.

## Files
- `scripts/validate_2b.py` — rewritten (this revision).
- `scripts/HARNESS_CHANGELOG.md` — this file.
- `scripts/run.sh`, `scripts/package.sh` — unchanged (still valid).
- code: `fees.py` (fee_schedule_hash), `discovery.py` (FeeScheduleConflict + guard),
  `tests/test_fee_schedule_identity.py`, `PHASE_2B_MARKET_DISCOVERY.md` §9 — from the
  prior revision, unchanged here.
