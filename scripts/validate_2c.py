#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/validate_2c.py — Phase 2C validation harness (Blocker 1: checkpoint/resume)
====================================================================================
Same discipline as the 2B harness: IMPLEMENTED != TESTED != VALIDATED; NOTHING is
VALIDATED without this REAL run. `scripts/validate_2b.py` is NOT touched.

What it does (Blocker 1 only; Blocker 2 stays an open BLOCKER):
  * PREFLIGHT (python, duckdb, pytest, project structure, runner present).
  * Deterministic cross-process evidence via tests/support/checkpoint_runner.py:
      - before_event2 : REAL subprocess; child signals EVENT_1_COMMITTED then blocks;
        the PARENT sends SIGKILL; a SECOND process resumes from the persisted
        discovery_checkpoint. (No sleep / no timing sync.)
      - during_event2 : SIGKILL inside event 2's txn -> DuckDB WAL rollback; resume.
  * pytest tests/test_checkpoint_resume.py  (the same criteria, as unit tests).
  * FULL pytest suite = Phase 2B REGRESSION (schema-agnostic; must stay green at Alt C).
  * OPTIONAL (--gamma): real-Gamma two-process resume (needs network; Hetzner/Actions).
  * Writes results/PHASE_2C_VALIDATION_REPORT.md with per-item evidence + a VERDICT.

Usage:
  python3 scripts/validate_2c.py            # deterministic scenarios + pytest + regression
  python3 scripts/validate_2c.py --gamma    # also the real-Gamma two-process resume
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import signal
import subprocess
import sys
import tempfile
import uuid

import weather_agent.database as db

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
SRC = os.path.join(ROOT, "src")
TESTS = os.path.join(ROOT, "tests")
RUNNER = os.path.join(TESTS, "support", "checkpoint_runner.py")
RESULTS = os.path.join(ROOT, "results")
REPORT = os.path.join(RESULTS, "PHASE_2C_VALIDATION_REPORT.md")
SENTINEL = "EVENT_1_COMMITTED"
NYC_ID, ANKARA_ID = "128661", "869074"
FACT_TABLES = ("markets", "outcomes", "market_fee_schedule", "data_quality")

sys.path.insert(0, SRC)
sys.path.insert(0, TESTS)

RUN = {
    "validation_run_id": "vc2c_" + uuid.uuid4().hex[:12],
    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "python": platform.python_version(),
    "os": platform.platform(),
}
PROBLEMS: list[str] = []
LINES: list[str] = []


def log(msg):
    LINES.append(msg)
    print(msg)


def git_commit():
    try:
        return subprocess.check_output(["git", "-C", ROOT, "rev-parse", "HEAD"],
                                       text=True).strip()
    except Exception:
        return "UNKNOWN"


def _child_env():
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([SRC, TESTS, env.get("PYTHONPATH", "")])
    return env


def run_runner(mode, db_path, dsv, kill_point=None):
    cmd = [sys.executable, RUNNER, "--db", db_path, "--dsv", dsv, "--mode", mode]
    if kill_point:
        cmd += ["--kill-point", kill_point]
    return subprocess.run(cmd, capture_output=True, text=True, env=_child_env(), timeout=180)


def run_interrupt(db_path, dsv, kill_point):
    """Deterministic rendezvous: read SENTINEL on the child's stdout, then the PARENT
    issues SIGKILL. Returns the child's returncode (expected -SIGKILL)."""
    proc = subprocess.Popen(
        [sys.executable, RUNNER, "--db", db_path, "--dsv", dsv,
         "--mode", "interrupt", "--kill-point", kill_point],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, env=_child_env())
    saw = False
    for line in proc.stdout:
        if line.strip() == SENTINEL:
            saw = True
            break
    if not saw:
        try:
            proc.kill()
        except Exception:
            pass
        return None
    proc.kill()
    rc = proc.wait(timeout=60)
    for s in (proc.stdin, proc.stdout, proc.stderr):
        try:
            s.close()
        except Exception:
            pass
    return rc


def _q1(con, sql, params):
    return con.execute(sql, params).fetchone()[0]


def _state(con, dsv):
    return {
        "nyc_markets": _q1(con, "SELECT COUNT(*) FROM markets WHERE event_id=? AND dataset_version=?", [NYC_ID, dsv]),
        "ankara_markets": _q1(con, "SELECT COUNT(*) FROM markets WHERE event_id=? AND dataset_version=?", [ANKARA_ID, dsv]),
        "nyc_ckpt": _q1(con, "SELECT COUNT(*) FROM discovery_checkpoint WHERE dataset_version=? AND event_id=?", [dsv, NYC_ID]),
        "ankara_ckpt": _q1(con, "SELECT COUNT(*) FROM discovery_checkpoint WHERE dataset_version=? AND event_id=?", [dsv, ANKARA_ID]),
        "counts": {t: _q1(con, f"SELECT COUNT(*) FROM {t} WHERE dataset_version=?", [dsv]) for t in FACT_TABLES},
        "dupes": _dupes(con, dsv),
        "identity": _identity(con, dsv),
    }


def _dupes(con, dsv):
    return {
        "markets": _q1(con, "SELECT COUNT(*) FROM (SELECT 1 FROM markets WHERE dataset_version=? GROUP BY market_id,dataset_version,record_version HAVING COUNT(*)>1)", [dsv]),
        "outcomes": _q1(con, "SELECT COUNT(*) FROM (SELECT 1 FROM outcomes WHERE dataset_version=? GROUP BY token_id,dataset_version,record_version HAVING COUNT(*)>1)", [dsv]),
        "fees": _q1(con, "SELECT COUNT(*) FROM (SELECT 1 FROM market_fee_schedule WHERE dataset_version=? GROUP BY fee_regime,dataset_version,record_version HAVING COUNT(*)>1)", [dsv]),
        "checkpoint": _q1(con, "SELECT COUNT(*) FROM (SELECT 1 FROM discovery_checkpoint WHERE dataset_version=? GROUP BY dataset_version,event_id HAVING COUNT(*)>1)", [dsv]),
    }


def _identity(con, dsv):
    """STRONG equivalence fingerprint (NOT totals alone): PK identity sets per table +
    processed event_ids + final checkpoint event_ids + counts. Two different results
    with equal counts cannot pass as equivalent. Volatile columns (ingestion_timestamp)
    are excluded on purpose."""
    def rows(sql):
        return con.execute(sql, [dsv]).fetchall()
    return {
        "markets_pk": sorted(rows("SELECT market_id, record_version FROM markets WHERE dataset_version=?")),
        "outcomes_pk": sorted(rows("SELECT token_id, record_version FROM outcomes WHERE dataset_version=?")),
        "fees_pk": sorted(rows("SELECT fee_regime, record_version FROM market_fee_schedule WHERE dataset_version=?")),
        "data_quality_pk": sorted(rows("SELECT ref FROM data_quality WHERE dataset_version=?")),
        "market_event_ids": sorted({r[0] for r in rows("SELECT DISTINCT event_id FROM markets WHERE dataset_version=?")}),
        "checkpoint_event_ids": sorted(r[0] for r in rows("SELECT event_id FROM discovery_checkpoint WHERE dataset_version=?")),
        "counts": {t: rows(f"SELECT COUNT(*) FROM {t} WHERE dataset_version=?")[0][0] for t in FACT_TABLES},
    }


def scenario(db, kill_point):
    """Run one cross-process scenario; return (ok, evidence dict)."""
    dsv = "ds_ckpt"
    tmp = tempfile.mkdtemp(prefix="pmw2c_")
    db_clean = os.path.join(tmp, "clean.duckdb")
    db_test = os.path.join(tmp, "test.duckdb")
    ev = {"kill_point": kill_point}

    r_clean = run_runner("clean", db_clean, dsv)
    ev["clean_rc"] = r_clean.returncode
    rc = run_interrupt(db_test, dsv, kill_point)
    ev["interrupt_rc"] = rc
    ev["killed_by_sigkill"] = (rc == -signal.SIGKILL)

    con = db.init_db(db_path=db_test)
    ev["after_kill"] = _state(con, dsv)
    con.close()

    r_res = run_runner("resume", db_test, dsv)
    ev["resume_rc"] = r_res.returncode

    con = db.init_db(db_path=db_test)
    ev["after_resume"] = _state(con, dsv)
    con.close()
    con = db.init_db(db_path=db_clean)
    ev["clean"] = _state(con, dsv)
    con.close()

    ak = ev["after_kill"]
    ar = ev["after_resume"]
    ok = (
        ev["clean_rc"] == 0 and ev["resume_rc"] == 0 and ev["killed_by_sigkill"]
        and ak["nyc_markets"] > 0 and ak["nyc_ckpt"] == 1                 # event1 + ckpt survive
        and ak["ankara_markets"] == 0 and ak["ankara_ckpt"] == 0         # event2 + ckpt absent
        and ar["ankara_markets"] > 0 and ar["ankara_ckpt"] == 1          # resume processes event2
        and ar["identity"] == ev["clean"]["identity"]                    # STRONG: resume == clean (identity sets)
        and all(v == 0 for v in ar["dupes"].values())                   # zero duplicates
    )
    return ok, ev


def run_pytest(target=None):
    cmd = [sys.executable, "-m", "pytest", "-q"]
    if target:
        cmd.append(target)
    r = subprocess.run(cmd, capture_output=True, text=True, env=_child_env(), cwd=ROOT, timeout=1800)
    tail = "\n".join((r.stdout + r.stderr).strip().splitlines()[-8:])
    return r.returncode == 0, tail


def preflight():
    import importlib
    checks = []
    checks.append(("python", True, RUN["python"]))
    for mod in ("duckdb", "pytest"):
        try:
            m = importlib.import_module(mod)
            checks.append((mod, True, getattr(m, "__version__", "?")))
        except Exception as e:
            checks.append((mod, False, str(e)))
            PROBLEMS.append(f"missing dependency: {mod}")
    for p in (SRC, TESTS, RUNNER):
        ok = os.path.exists(p)
        checks.append((os.path.relpath(p, ROOT), ok, "present" if ok else "MISSING"))
        if not ok:
            PROBLEMS.append(f"missing path: {p}")
    if not hasattr(signal, "SIGKILL"):
        PROBLEMS.append("SIGKILL unavailable (non-POSIX) — the interruption evidence cannot run here")
    return checks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gamma", action="store_true", help="also run the real-Gamma two-process resume")
    args = ap.parse_args()
    os.makedirs(RESULTS, exist_ok=True)

    RUN["git_commit"] = git_commit()
    log(f"# PHASE 2C — VALIDATION REPORT (Blocker 1: checkpoint/resume)")
    log(f"run_id={RUN['validation_run_id']} utc={RUN['timestamp_utc']} commit={RUN['git_commit']}")
    log(f"python={RUN['python']} os={RUN['os']}")
    log("")

    log("## 1. PREFLIGHT")
    for name, ok, detail in preflight():
        log(f"- {name}: {'OK' if ok else 'FAIL'} ({detail})")
    if PROBLEMS:
        log("\n**PREFLIGHT FAILED — stopping before scenarios.**")
        for p in PROBLEMS:
            log(f"- {p}")
        _write()
        sys.exit(1)

    log("\n## 1b. SCHEMA (Alt C compliance — no version bump, operational table)")
    con = db.init_db(db_path=":memory:")
    sv = db.get_schema_version(con)
    tbls = set(db.table_names(con))
    con.close()
    schema_ok = (sv == db.SCHEMA_VERSION and
                 "discovery_checkpoint" in tbls
                 and "discovery_checkpoint" not in db.ALL_TABLES)
    log(f"- SCHEMA_VERSION = {sv} (expected db.SCHEMA_VERSION = {db.SCHEMA_VERSION})")
    log(f"- discovery_checkpoint present = {'discovery_checkpoint' in tbls}")
    log(f"- discovery_checkpoint NOT in ALL_TABLES = {'discovery_checkpoint' not in db.ALL_TABLES}")
    log(f"- SCHEMA (Alt C): {'OK' if schema_ok else 'FAIL'}")

    results = {}
    for kp in ("before_event2", "during_event2"):
        log(f"\n## 2. SCENARIO {kp}")
        ok, ev = scenario(db, kp)
        results[kp] = ok
        log(f"- interrupt returncode = {ev['interrupt_rc']} (killed_by_SIGKILL={ev['killed_by_sigkill']})")
        log(f"- after kill : {ev['after_kill']['nyc_markets']} nyc mkts / nyc_ckpt={ev['after_kill']['nyc_ckpt']} ; "
            f"ankara mkts={ev['after_kill']['ankara_markets']} / ankara_ckpt={ev['after_kill']['ankara_ckpt']}")
        log(f"- after resume: ankara mkts={ev['after_resume']['ankara_markets']} / ankara_ckpt={ev['after_resume']['ankara_ckpt']}")
        log(f"- resume == clean (STRONG identity: PK sets + event_ids + checkpoints + counts): "
            f"{ev['after_resume']['identity'] == ev['clean']['identity']} ; "
            f"dupes={ev['after_resume']['dupes']}")
        log(f"- SCENARIO {kp}: {'PASS' if ok else 'FAIL'}")

    log("\n## 3. pytest tests/test_checkpoint_resume.py")
    ck_ok, ck_tail = run_pytest("tests/test_checkpoint_resume.py")
    log(f"```\n{ck_tail}\n```\n- checkpoint pytest: {'PASS' if ck_ok else 'FAIL'}")

    log("\n## 4. FULL pytest suite (Phase 2B REGRESSION)")
    reg_ok, reg_tail = run_pytest(None)
    log(f"```\n{reg_tail}\n```\n- 2B regression: {'PASS' if reg_ok else 'FAIL'}")

    gamma_ok = None
    log("\n## 5. REAL-GAMMA two-process resume")
    if args.gamma:
        gamma_ok = real_gamma(db)
        log(f"- real-Gamma two-process: {'PASS' if gamma_ok is True else 'FAIL/SKIP'} (gamma_ok={gamma_ok})")
    else:
        log("- NOT RUN (no --gamma). Real Gamma is REQUIRED for VALIDATED: the "
            "deterministic scenarios + pytest + 2B regression can be TESTED, but Blocker 1 "
            "stays NOT VALIDATED until a real --gamma run passes.")

    # VALIDATED requires REAL Gamma to have actually run and passed. A skipped/absent
    # Gamma (gamma_ok is None) or a failed one (False) => NOT VALIDATED. Never treat a
    # Gamma SKIP as VALIDATED.
    checkpoint_validated = (schema_ok
                            and results.get("before_event2") and results.get("during_event2")
                            and ck_ok and reg_ok and (gamma_ok is True))
    log("\n## 6. STATUS  (a green pytest is TESTED, NOT VALIDATED)")
    log(f"- TESTED (pytest green): checkpoint pytest={ck_ok}; 2B regression={reg_ok}")
    log(f"- VALIDATED evidence (REAL cross-process SIGKILL + disk checkpoint + resume, "
        f"asserted against the actual DuckDB — NOT inferred from a green test): "
        f"before_event2={results.get('before_event2')}, during_event2={results.get('during_event2')}, "
        f"schema_altC={schema_ok}, real_gamma={gamma_ok} (REQUIRED: must be True; None/False => NOT VALIDATED)")
    log(f"- => checkpoint/resume VALIDATED = {checkpoint_validated} "
        f"(requires the real cross-process evidence AND real Gamma passing AND green suites; "
        f"a green pytest or a skipped Gamma is NOT enough)")
    blocker2_validated = validate_no_lookahead()

    log("\n## 7. VERDICT")
    log(f"PHASE 2C BLOCKER 1 (checkpoint/resume) = {'VALIDATED' if checkpoint_validated else 'NOT VALIDATED'}")
    log(f"PHASE 2C BLOCKER 2 (no-look-ahead) = {'VALIDATED' if blocker2_validated else 'NOT VALIDATED'}")

    overall_validated = checkpoint_validated and blocker2_validated

    log(
        f"PHASE 2C OVERALL = "
        f"{'VALIDATED' if overall_validated else 'NOT VALIDATED'}"
    )
    log("END OF REPORT")
    _write()
    sys.exit(0 if overall_validated else 1)


def _gamma_proc(runner, path, dsv):
    """Run ONE independent gamma_runner subprocess; return (parsed_json | None, proc)."""
    r = subprocess.run([sys.executable, runner, "--db", path, "--dsv", dsv],
                       capture_output=True, text=True, env=_child_env(), timeout=300)
    line = next((l for l in r.stdout.splitlines() if l.startswith("GAMMA_RESULT ")), None)
    if r.returncode != 0 or line is None:
        return None, r
    try:
        return json.loads(line[len("GAMMA_RESULT "):]), r
    except Exception:
        return None, r


def real_gamma(db):
    """Real-Gamma two-process resume, as TWO INDEPENDENT OS PROCESSES sharing the SAME
    DuckDB (via tests/support/gamma_runner.py). Returns:
      True  = VALIDATED (process 2 loaded process 1's persisted checkpoint AND the
              already-committed events were NOT reprocessed AND zero duplicates),
      False = a real consistency violation,
      None  = infra SKIP (no network / rate-limit / no events) — never a PASS.
    A Gamma rate-limit is classified as SKIP (None), never inferred as PASS/FAIL."""
    from weather_agent.polymarket import discovery as disc   # for S_OK constant only
    runner = os.path.join(TESTS, "support", "gamma_runner.py")
    if not os.path.exists(runner):
        log("- gamma_runner.py missing -> SKIP")
        return None
    tmp = tempfile.mkdtemp(prefix="pmw2c_gamma_")
    path = os.path.join(tmp, "gamma.duckdb")
    dsv = "ds_gamma_2c"

    p1, r1 = _gamma_proc(runner, path, dsv)      # PROCESS 1 (independent)
    p2, r2 = _gamma_proc(runner, path, dsv)      # PROCESS 2 (independent, same DB)
    if p1 is None or p2 is None:
        log(f"- real-Gamma subprocess failed/no result -> SKIP "
            f"(rc1={getattr(r1, 'returncode', None)}, rc2={getattr(r2, 'returncode', None)})")
        return None

    after1 = set(p1["checkpoint_after"])
    before2 = set(p2["checkpoint_before"])
    after2 = set(p2["checkpoint_after"])

    # Infra SKIP: process 1 must have really reached Gamma and committed >=1 event.
    if p1["status"] != disc.S_OK or (p1["events_ingested"] or 0) < 1 or not after1:
        log(f"- real-Gamma process1 status={p1['status']} events={p1['events_ingested']} "
            f"ckpt_after={len(after1)} -> SKIP (infra / no data); NOT VALIDATED")
        return None
    if p2["status"] != disc.S_OK:
        log(f"- real-Gamma process2 status={p2['status']} -> SKIP (infra); NOT VALIDATED")
        return None

    distinct_pids = (p1["pid"] != p2["pid"])
    loaded = (before2 == after1)                                   # process 2 loaded the persisted checkpoint
    new_events = after2 - before2
    not_reprocessed = ((p2["events_ingested"] or 0) == len(new_events)) and after1.issubset(after2)

    con = db.init_db(db_path=path)
    dupes = _dupes(con, dsv)
    con.close()
    no_dupes = all(v == 0 for v in dupes.values())

    log(f"- process1 pid={p1['pid']} events_ingested={p1['events_ingested']} ckpt_after={len(after1)}")
    log(f"- process2 pid={p2['pid']} ckpt_before={len(before2)} events_ingested={p2['events_ingested']} ckpt_after={len(after2)}")
    log(f"- two DISTINCT processes: {distinct_pids}")
    log(f"- process2 LOADED process1 checkpoint (before2 == after1): {loaded}")
    log(f"- already-committed events NOT reprocessed (p2 ingested only new): {not_reprocessed}")
    log(f"- zero duplicates: {no_dupes} ({dupes})")
    ok = distinct_pids and loaded and not_reprocessed and no_dupes
    return True if ok else False


def validate_no_lookahead():
    """Validate Phase 2C Blocker 2 using real executable tests.

    This validator deliberately relies on the adversarial test suite rather than
    treating the existence of build_feature() as sufficient evidence.
    """
    log("\n## 5b. BLOCKER 2 — NO-LOOK-AHEAD")

    checks = [
        ("adversarial no-look-ahead",
         "tests/test_no_lookahead_adversarial.py"),
        ("resolution separated from features",
         "tests/test_resolution_not_in_features.py"),
    ]

    all_ok = True

    for name, target in checks:
        ok, tail = run_pytest(target)
        log(f"- {name}: {'PASS' if ok else 'FAIL'}")
        log(f"  ```\n{tail}\n  ```")
        all_ok = all_ok and ok

    # Explicit source-level guard: build_feature must not read settlement data.
    feature_path = os.path.join(SRC, "weather_agent", "features.py")
    try:
        with open(feature_path, "r", encoding="utf-8") as fh:
            feature_src = fh.read()
    except OSError as e:
        log(f"- feature builder source: FAIL ({e})")
        return False

    forbidden_reads = (
        "market.get(\"winning_outcome\")",
        "market.get(\"resolution_timestamp\")",
        "market.get(\"settlement_timestamp\")",
        "outcome.get(\"is_winner\")",
    )

    leaked = [x for x in forbidden_reads if x in feature_src]

    source_ok = not leaked
    log(
        "- feature builder resolution isolation: "
        f"{'PASS' if source_ok else 'FAIL'}"
        + (f" (forbidden reads={leaked})" if leaked else "")
    )

    # Explicit source-level guard: the TRUE flag can only be assigned after
    # the as-of guards in build_feature().
    true_marker = 'row["no_lookahead_verified"] = True'
    guard_markers = (
        'price["observation_time"] > prediction_time',
        'forecast["available_at"] > prediction_time',
    )

    flag_ok = true_marker in feature_src and all(
        marker in feature_src for marker in guard_markers
    )

    log(
        "- no_lookahead_verified guard present: "
        f"{'PASS' if flag_ok else 'FAIL'}"
    )

    return all_ok and source_ok and flag_ok

def _write():
    try:
        with open(REPORT, "w", encoding="utf-8") as fh:
            fh.write("\n".join(LINES) + "\n")
        print(f"\n[*] report written: {REPORT}")
    except OSError as e:
        print(f"[!] could not write report: {e}")


if __name__ == "__main__":
    main()
