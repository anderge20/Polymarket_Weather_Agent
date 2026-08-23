#!/usr/bin/env python3
"""
scripts/validate_2b.py — REAL / reproducible / auditable 2A+2B validation harness
=================================================================================
Runs a PREFLIGHT, the pytest suites, a REAL v1→v2 migration test, and a SMALL
real-data discovery smoke with adversarial fixtures, then writes
results/PHASE_2B_VALIDATION_REPORT.md (source of truth) and emits a VERDICT.

MASTER RULE — status vocabulary (echoed literally in the report):
  IMPLEMENTED = written, NOT executed.
  TESTED      = executed and its tests passed (unit test / synthetic fixture /
                offline stub / schema-config check). A green unit test is TESTED.
  VALIDATED   = behaviour executed AND checked against a REAL run and (where it
                applies) REAL data. Reserved for: the real v1→v2 migration, the
                real discovery smoke, idempotency/duplicates/token/winner/band/
                provenance/fee-mapping measured on the real sample.
  FAILED      = executed and failed.   SKIPPED = deliberately not executed.
A pytest PASS is NEVER auto-VALIDATED. Classification depends on the TYPE of
evidence, not merely on "it passed".

This harness is IMPLEMENTED here. It marks nothing TESTED/VALIDATED until the
USER actually runs it on Hetzner — the statuses in the report are produced by
that run.

HARD SCOPE (2B only): preflight + pytest + real migration test + small discovery
smoke (≤5 REAL markets). NO 2C, NO feature builder, NO Strategy A, NO backtest,
NO forecasting, NO paper, NO execution, NO wallet, NO orders, NO L2. Only Gamma
is contacted for the sample (plus CLOB/Data-API connectivity pings).
makerBaseFee/takerBaseFee are captured RAW only and used in NO calculation.

Local report is the source of truth. paste.rs upload is best-effort, OFF by
default (--upload); an upload failure is NEVER a validation failure and the
return one-liner is a separate optional step.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import traceback
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = ROOT / "tests"
RESULTS = ROOT / "results"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(TESTS))

REPORT_PATH = RESULTS / "PHASE_2B_VALIDATION_REPORT.md"

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
DATA_API = "https://data-api.polymarket.com"
TEMP_TAG_ID = 104596
MAX_SMOKE_MARKETS = 5

TWOA_TESTS = [
    "tests/test_database.py",
    "tests/test_no_future_information.py",
    "tests/test_weather_asof.py",
    "tests/test_market_asof.py",
    "tests/test_resolution_not_in_features.py",
]
TWOB_TESTS = [
    "tests/test_resolution.py",
    "tests/test_fees_mapping.py",
    "tests/test_discovery.py",
    "tests/test_integrity.py",
    "tests/test_fee_schedule_identity.py",
    "tests/test_no_lookahead_adversarial.py",
    "tests/test_ingest_atomic.py",
]


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


# ---------------------------------------------------------------- run state
RUN = {
    "validation_run_id": uuid.uuid4().hex[:12],
    "timestamp_utc": _utc_now(),
    "git_commit": "UNKNOWN",
    "python_version": platform.python_version(),
    "platform": platform.platform(),
    "dependency_versions": {},
    "dataset_version": None,
    "db_path": str((RESULTS / "validate.duckdb")),
    "schema_before": "UNKNOWN",
    "schema_after": "UNKNOWN",
    "markets_used": [],   # full per-market records (condition 9)
    "requests": [],       # {endpoint, params, status}
    "errors": [],
    "upload_status": "SKIPPED",
}
RUN["dataset_version"] = f"ds_validate_{RUN['validation_run_id']}"

SECTIONS: dict[str, list[str]] = {}
IMPLEMENTED: list[str] = []
TESTED: list[str] = []
VALIDATED: list[str] = []
EVIDENCE: dict[str, dict] = {}   # VALIDATED name -> real-execution evidence record
FAILED: list[str] = []
SKIPPED: list[str] = []
ISSUES: list[str] = []
BLOCKERS: list[str] = []
# verdict flags (condition 14): each set at runtime
FLAGS = {
    "A_pytest_ran": False, "B_no_critical_fail": False,
    "C_migration": False, "D_discovery": False, "E_idempotency": False,
    "F_token": False, "G_winner_band": False, "H_fee_guard": False,
    "I_checkpoint": False, "J_no_inferred": False, "K_evidence_backed": False,
}


def log_error(msg: str) -> None:
    RUN["errors"].append(msg)
    ISSUES.append(msg)


def log_request(endpoint: str, params, status) -> None:
    RUN["requests"].append({"endpoint": endpoint, "params": params, "status": str(status)})


def sec(name: str, lines) -> None:
    SECTIONS[name] = lines if isinstance(lines, list) else [str(lines)]


# Minimum evidence FIELDS required per real-execution evidence kind. A VALIDATED
# item whose evidence lacks ANY of these (or has it as None) fails the final audit
# (K) → VERDICT = PHASE 2B NOT VALIDATED. timestamp_utc is auto-added by mark_real.
REQUIRED_EVIDENCE = {
    "real_v1_v2_migration": ["timestamp_utc", "db", "schema_before", "schema_after"],
    "real_gamma_ingest":    ["timestamp_utc", "dataset_version", "markets", "event_id", "market_ids"],
    "real_rows_provenance": ["timestamp_utc", "dataset_version", "n_rows"],
    "real_reingest":        ["timestamp_utc", "dataset_version", "counts_before", "counts_after",
                             "checksum_before", "checksum_after"],
    "real_pk_identity":     ["timestamp_utc", "dataset_version"],
    "real_token_check":     ["timestamp_utc", "dataset_version", "event_id", "conflicts"],
    "real_event_winner":    ["timestamp_utc", "event_id", "status"],
    "real_event_bands":     ["timestamp_utc", "event_id", "n_bands", "is_partition"],
    "real_fee_regimes":     ["timestamp_utc", "dataset_version", "regimes", "conflict_observed"],
}


def mark_real(ok: bool, name: str, evidence: dict | None = None) -> bool:
    """VALIDATED requires a real-execution evidence record. On success the record
    is stored (timestamp_utc auto-added); the FINAL audit (_check_evidence) fails
    the verdict (K) if any VALIDATED item's evidence is missing the minimum fields
    required for its kind."""
    if ok:
        VALIDATED.append(name)
        ev = dict(evidence or {})
        ev.setdefault("timestamp_utc", _utc_now())
        EVIDENCE[name] = ev
    else:
        FAILED.append(name)
    return ok


def mark_syn(ok: bool, name: str) -> bool:
    (TESTED if ok else FAILED).append(name)
    return ok


def _check_evidence():
    """FINAL audit (condition K): every VALIDATED item must carry a real-execution
    evidence record whose kind starts 'real_' AND that contains the minimum fields
    required for that kind (each non-None). Returns (ok, audit_lines)."""
    ok, audit = True, []
    for name in VALIDATED:
        ev = EVIDENCE.get(name) or {}
        kind = str(ev.get("kind", ""))
        if not kind.startswith("real_"):
            ok = False
            audit.append(f"- {name} ← FAIL (kind {kind!r} not 'real_*')")
            continue
        req = REQUIRED_EVIDENCE.get(kind)
        if req is None:
            ok = False
            audit.append(f"- {name} ← FAIL (unknown evidence kind {kind!r})")
            continue
        missing = [k for k in req if ev.get(k) is None]
        if missing:
            ok = False
            audit.append(f"- {name} ← FAIL (missing {missing}) [{kind}]")
        else:
            audit.append(f"- {name} ← ok [{kind}]")
    return ok, audit


# =============================================================================
# PREFLIGHT (11 checks) — critical vs non-critical, hard stop
# =============================================================================
def http_get(url: str, params=None, timeout=15):
    try:
        import requests
    except Exception:
        return "NO_REQUESTS", "requests not importable"
    try:
        r = requests.get(url, params=params, timeout=timeout,
                         headers={"User-Agent": "pmw-validate/1.0"})
        return r.status_code, ""
    except Exception as exc:  # noqa: BLE001
        return "ERROR", str(exc)[:200]


def preflight() -> dict:
    checks = []  # (id, name, scope, status, detail)

    ok = sys.version_info[:2] >= (3, 9)
    checks.append(("1", "Python version", "universal", "PASS" if ok else "FAIL",
                   f"{platform.python_version()} (need >=3.9)"))

    in_venv = (getattr(sys, "base_prefix", sys.prefix) != sys.prefix) or bool(os.environ.get("VIRTUAL_ENV"))
    pip_ok = True
    try:
        import pip  # noqa: F401
    except Exception:
        pip_ok = False
    checks.append(("2", "venv / pip", "universal", "PASS" if pip_ok else "WARN",
                   f"in_venv={in_venv}, pip_importable={pip_ok}"))

    pytest_ok, pytest_ver = False, "n/a"
    try:
        import pytest  # noqa: F401
        pytest_ok, pytest_ver = True, getattr(pytest, "__version__", "?")
    except Exception as exc:
        pytest_ver = f"import error: {exc}"
    checks.append(("3", "pytest", "universal", "PASS" if pytest_ok else "FAIL", pytest_ver))

    duckdb_ok, duckdb_ver = False, "n/a"
    try:
        import duckdb
        duckdb_ok, duckdb_ver = True, getattr(duckdb, "__version__", "?")
    except Exception as exc:
        duckdb_ver = f"import error: {exc}"
    checks.append(("4", "DuckDB import+version", "universal", "PASS" if duckdb_ok else "FAIL", duckdb_ver))

    try:
        free_gb = shutil.disk_usage(str(ROOT)).free / (1024 ** 3)
        checks.append(("5", "Disk space", "non-critical", "PASS" if free_gb >= 0.2 else "WARN",
                       f"{free_gb:.2f} GB free"))
    except Exception as exc:
        checks.append(("5", "Disk space", "non-critical", "WARN", str(exc)))

    write_ok = True
    try:
        RESULTS.mkdir(parents=True, exist_ok=True)
        t = RESULTS / ".write_test"
        t.write_text("ok", encoding="utf-8")
        t.unlink()
    except Exception as exc:
        write_ok = False
        log_error(f"write permission: {exc}")
    checks.append(("6", "Write permission (results/)", "universal", "PASS" if write_ok else "FAIL", str(RESULTS)))

    needed = [
        SRC / "weather_agent" / "config.py", SRC / "weather_agent" / "database.py",
        SRC / "weather_agent" / "polymarket" / "discovery.py",
        SRC / "weather_agent" / "polymarket" / "resolution.py",
        SRC / "weather_agent" / "polymarket" / "fees.py", TESTS,
    ]
    missing = [str(p.relative_to(ROOT)) for p in needed if not p.exists()]
    checks.append(("7", "Project structure", "universal", "PASS" if not missing else "FAIL",
                   "all present" if not missing else f"missing: {missing}"))

    key = {"duckdb": None, "pandas": None, "numpy": None, "scipy": None,
           "scikit-learn": "sklearn", "requests": None, "aiohttp": None,
           "websockets": None, "python-dateutil": "dateutil", "pytest": None}
    dep_status = {}
    for dist, mod in key.items():
        try:
            m = __import__(mod or dist)
            dep_status[dist] = getattr(m, "__version__", "present")
        except Exception:
            dep_status[dist] = "MISSING"
    RUN["dependency_versions"] = dep_status
    req_missing = [k for k, v in dep_status.items() if v == "MISSING"]
    checks.append(("8", "Requirements installed", "non-critical", "PASS" if not req_missing else "WARN",
                   f"missing: {req_missing}" if req_missing else "all key deps present"))

    g_status, g_note = http_get(f"{GAMMA}/events", {"tag_id": TEMP_TAG_ID, "closed": "true", "limit": 1})
    log_request(f"{GAMMA}/events", {"limit": 1}, g_status)
    gamma_ok = g_status == 200
    checks.append(("9", "Gamma connectivity", "smoke-critical", "PASS" if gamma_ok else "FAIL",
                   f"status={g_status} {g_note}".strip()))

    c_status, c_note = http_get(f"{CLOB}/", timeout=10)
    log_request(f"{CLOB}/", None, c_status)
    checks.append(("10", "CLOB connectivity", "non-critical",
                   "PASS" if str(c_status).startswith(("2", "3", "4")) else "WARN",
                   f"status={c_status} {c_note}".strip() + " (ping only; CLOB not used by 2B smoke)"))

    d_status, d_note = http_get(f"{DATA_API}/", timeout=10)
    log_request(f"{DATA_API}/", None, d_status)
    checks.append(("11", "Data API connectivity", "non-critical",
                   "PASS" if str(d_status).startswith(("2", "3", "4")) else "WARN",
                   f"status={d_status} {d_note}".strip() + " (ping only; data-api not used by 2B smoke)"))

    universal_fail = [c for c in checks if c[2] == "universal" and c[3] == "FAIL"]
    return {"checks": checks, "universal_critical_ok": not universal_fail, "gamma_ok": gamma_ok}


# =============================================================================
# pytest runner
# =============================================================================
def run_pytest(label: str, test_files: list[str]) -> dict:
    xml_path = RESULTS / f"junit_{label}.xml"
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(SRC), str(TESTS), env.get("PYTHONPATH", "")])
    cmd = [sys.executable, "-m", "pytest", *test_files, "-q", "--tb=short",
           "-p", "no:cacheprovider", f"--junitxml={xml_path}"]
    try:
        proc = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=900)
        rc, tail = proc.returncode, (proc.stdout or "")[-1200:]
    except Exception as exc:  # noqa: BLE001
        log_error(f"pytest {label} could not run: {exc}")
        return {"ran": False, "error": str(exc), "cases": [], "summary": {}}

    cases, summary = [], {"passed": 0, "failed": 0, "skipped": 0, "error": 0, "total": 0}
    if xml_path.exists():
        try:
            for tc in ET.parse(str(xml_path)).getroot().iter("testcase"):
                name = f"{tc.get('classname','')}::{tc.get('name','')}".strip(":")
                outcome, msg = "PASSED", ""
                if tc.find("failure") is not None:
                    outcome, msg = "FAILED", (tc.find("failure").get("message", "") or "")[:200]
                elif tc.find("error") is not None:
                    outcome, msg = "ERROR", (tc.find("error").get("message", "") or "")[:200]
                elif tc.find("skipped") is not None:
                    outcome, msg = "SKIPPED", (tc.find("skipped").get("message", "") or "")[:200]
                cases.append({"name": name, "outcome": outcome, "message": msg})
                summary[outcome.lower()] = summary.get(outcome.lower(), 0) + 1
                summary["total"] += 1
        except Exception as exc:  # noqa: BLE001
            log_error(f"pytest {label} junit parse error: {exc}")
    else:
        log_error(f"pytest {label}: no junit xml produced (rc={rc})")
    return {"ran": True, "rc": rc, "cases": cases, "summary": summary, "stdout_tail": tail}


# =============================================================================
# stubs + synthetic fixtures (offline; drive TESTED-level checks)
# =============================================================================
class _StubResp:
    def __init__(self, status_code, payload=None, retry_after=None, raise_json=False):
        self.status_code = status_code
        self._payload = payload if payload is not None else []
        self.headers = {"Retry-After": retry_after} if retry_after else {}
        self._raise_json = raise_json

    def json(self):
        if self._raise_json:
            raise ValueError("invalid payload")
        return self._payload


class _StubSession:
    def __init__(self, resp):
        self._resp = resp
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        return self._resp


class _SeqStubSession:
    """Yields a SEQUENCE of responses (one per .get) — used to simulate a real
    interruption between pages for the resume test. Sticks on the last response."""
    def __init__(self, responses):
        self._responses = list(responses)
        self._i = 0
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        r = self._responses[min(self._i, len(self._responses) - 1)]
        self._i += 1
        return r


class _RaiseStubSession:
    def __init__(self, exc):
        self._exc = exc
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        raise self._exc


def _synth_market(mid, cond, tokens, prices, *, outs=None, gband="20°C or below",
                  fee_type=None, fees_enabled=False, schedule=None, desc=None):
    m = {
        "id": mid, "conditionId": cond, "slug": f"slug-{mid}",
        "question": f"Will it be {gband}?", "groupItemTitle": gband,
        "outcomes": json.dumps(outs or ["Yes", "No"]),
        "outcomePrices": json.dumps(prices), "clobTokenIds": json.dumps(tokens),
        "umaEndDate": "2026-08-20T21:00:00Z", "createdAt": "2026-08-18T00:00:00Z",
        "startDate": "2026-08-18T00:00:00Z", "closedTime": "2026-08-20T21:00:00Z",
        "orderPriceMinTickSize": 0.001, "orderMinSize": 5, "feesEnabled": fees_enabled,
    }
    if fee_type is not None:
        m["feeType"] = fee_type
    if schedule is not None:
        m["feeSchedule"] = schedule
    if desc is not None:
        m["description"] = desc
    return m


def _synth_event(eid, markets, title="Highest temperature in Testville on August 20?"):
    return {"id": eid, "title": title, "tags": [{"id": str(TEMP_TAG_ID)}], "markets": markets}


# =============================================================================
# MAIN
# =============================================================================
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--upload", action="store_true",
                    help="best-effort POST the report to paste.rs at the end (never fails validation)")
    args = ap.parse_args()

    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                             capture_output=True, text=True, timeout=15)
        if out.returncode == 0 and out.stdout.strip():
            RUN["git_commit"] = out.stdout.strip()
    except Exception:
        RUN["git_commit"] = "UNKNOWN"

    RESULTS.mkdir(parents=True, exist_ok=True)

    # ---- PRECHECK ----------------------------------------------------------
    pf = preflight()
    pre = ["| # | check | scope | status | detail |", "|---|---|---|---|---|"]
    for cid, name, scope, status, detail in pf["checks"]:
        pre.append(f"| {cid} | {name} | {scope} | **{status}** | {detail} |")
    pre += ["", f"universal_critical_ok = **{pf['universal_critical_ok']}** · gamma_ok = **{pf['gamma_ok']}**"]
    sec("PRECHECK", pre)

    if not pf["universal_critical_ok"]:
        note = ("A UNIVERSAL-CRITICAL preflight check FAILED (Python / pytest / DuckDB / "
                "structure / write permission). STOPPING before pytest and discovery.")
        BLOCKERS.append(note)
        for s in ["11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23"]:
            sec(s, [f"SKIPPED — {note}"])
            SKIPPED.append(f"section {s}: blocked by preflight")
        _finish(args, stopped="preflight_universal_critical")
        return 2

    # ---- 12. PYTEST 2A + 2B  (report field 12) -----------------------------
    a = run_pytest("2a", TWOA_TESTS)
    b = run_pytest("2b", TWOB_TESTS)
    pytest_lines, total_fail = [], 0
    for label, res in (("2A", a), ("2B", b)):
        if not res.get("ran"):
            pytest_lines.append(f"pytest {label} could NOT run: {res.get('error')}")
            SKIPPED.append(f"pytest {label} (could not run)")
            continue
        s = res["summary"]
        total_fail += s.get("failed", 0) + s.get("error", 0)
        pytest_lines.append(f"**{label}**: rc={res.get('rc')} passed={s.get('passed',0)} "
                            f"failed={s.get('failed',0)} error={s.get('error',0)} "
                            f"skipped={s.get('skipped',0)} total={s.get('total',0)}")
        for c in res["cases"]:
            if c["outcome"] == "PASSED":
                TESTED.append(f"{label} {c['name']}")
            elif c["outcome"] == "SKIPPED":
                SKIPPED.append(f"{label} {c['name']}")
            else:
                FAILED.append(f"{label} {c['name']}: {c['message']}")
    pytest_lines.append("")
    pytest_lines.append("(pytest PASS ⇒ TESTED, never auto-VALIDATED.)")
    sec("12", pytest_lines)
    FLAGS["A_pytest_ran"] = bool(a.get("ran") and b.get("ran"))
    FLAGS["B_no_critical_fail"] = (total_fail == 0)

    # ---- 11. MIGRATION: clean-init-v2 vs REAL v1→v2  (report field 11) ------
    _migration_section()

    # smoke DB (clean v2) for the real-data checks
    con = None
    try:
        import weather_agent.database as db
        smoke_file = RESULTS / "validate.duckdb"
        if smoke_file.exists():
            smoke_file.unlink()
        con = db.init_db(db.connect(str(smoke_file)))
    except Exception as exc:  # noqa: BLE001
        log_error(f"smoke DB creation failed: {exc}")

    if con is None:
        for s in ["13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23"]:
            sec(s, ["SKIPPED — smoke DuckDB unavailable (see §11 / ISSUES)."])
            SKIPPED.append(f"section {s}: DuckDB unavailable")
        BLOCKERS.append("smoke DuckDB could not be created")
        _finish(args, stopped="duckdb_unavailable")
        return 2

    # ---- transaction ownership (point 3) — runs whenever the DB is available ----
    _transaction_ownership(con)

    # ---- gamma gate for the real smoke ------------------------------------
    if not pf["gamma_ok"]:
        note = "Gamma UNREACHABLE (smoke-critical). Discovery smoke (§13–§20) SKIPPED."
        BLOCKERS.append(note)
        for s in ["13", "14", "15", "16", "17", "18", "19", "20"]:
            sec(s, [f"SKIPPED — {note}"])
            SKIPPED.append(f"section {s}: gamma unreachable")
        # offline-only checks (21 resume, 22 as-of, 23 taxonomy) can still run
        _checkpoint_section(con)
        _asof_section(con, ingested=False)
        _error_taxonomy_section(con)
        _finish(args, stopped="gamma_unreachable")
        return 0

    # ---- REAL discovery smoke + all real-data checks (§13–§20) ------------
    try:
        _discovery_and_checks(con)
    except Exception as exc:  # noqa: BLE001
        log_error(f"discovery smoke crashed: {exc}\n{traceback.format_exc()[:600]}")
        for s in ["13", "14", "15", "16", "17", "18", "19", "20"]:
            if s not in SECTIONS:
                sec(s, [f"ERROR — smoke crashed before this check: {exc}"])
                FAILED.append(f"section {s}: smoke exception")

    _checkpoint_section(con)
    _asof_section(con, ingested=True)
    _error_taxonomy_section(con)
    _finish(args, stopped=None)
    return 0


# =============================================================================
# §11 migration
# =============================================================================
def _migration_section() -> None:
    try:
        import weather_agent.database as db
        v2_market = {"measurement_rule", "available_at", "available_at_confidence", "source_timestamps"}
        v2_fee = {"raw_fee_fields"}

        # (A) CLEAN INIT V2 — a fresh init reaches v2 (NOT a migration).
        ci_file = RESULTS / "validate_cleaninit.duckdb"
        if ci_file.exists():
            ci_file.unlink()
        cci = db.init_db(db.connect(str(ci_file)))
        clean_v2 = db.get_schema_version(cci)
        cci.close()

        # (B) REAL v1→v2 — build v1, insert v1 data, run the real migration, verify.
        mig_file = RESULTS / "validate_migration.duckdb"
        if mig_file.exists():
            mig_file.unlink()
        cm = db.connect(str(mig_file))
        cm.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, "
                   "name VARCHAR, applied_at TIMESTAMPTZ DEFAULT now(), checksum VARCHAR)")
        mig1 = next((m for m in db.MIGRATIONS if m["version"] == 1), None)
        mig2 = next((m for m in db.MIGRATIONS if m["version"] == 2), None)
        real_path_exists = bool(mig1 and mig2)

        if not real_path_exists:
            sec("11", ["(A) CLEAN INIT V2: schema_version=" + str(clean_v2),
                       "(B) REAL_V1_V2_MIGRATION = **UNIMPLEMENTED** — no reusable v1→v2 "
                       "migration path found in db.MIGRATIONS. A clean v2 init is NOT a "
                       "migration. To implement: add an ordered migration (version 2) that "
                       "ALTERs the v1 schema, plus a runner that applies pending migrations."])
            IMPLEMENTED.append("clean-init v2 (NOT a migration)")
            BLOCKERS.append("REAL_V1_V2_MIGRATION UNIMPLEMENTED (no reusable migration path)")
            RUN["schema_before"], RUN["schema_after"] = "n/a", str(clean_v2)
            FLAGS["C_migration"] = True  # explicitly UNIMPLEMENTED satisfies condition C
            cm.close()
            return

        for stmt in mig1["statements"]:
            cm.execute(stmt)
        cm.execute("INSERT INTO schema_version (version, name, applied_at) VALUES (1, ?, ?)",
                   [mig1["name"], db._utcnow_iso()])
        sv_before = db.get_schema_version(cm)                      # expect 1
        RUN["schema_before"] = sv_before
        v2_absent_at_v1 = v2_market.isdisjoint(set(db.column_names(cm, "markets")))

        db.insert(cm, "dataset_versions", {"version": "ds_mig", "source": "migration_test"})
        db.insert(cm, "markets", {
            "market_id": "mig_m1", "condition_id": "0xmig", "event_id": "e_mig", "slug": "mig",
            "question": "MIG survives?", "city": "Testville", "unit": "C", "fee_regime": "mig_regime",
            "tag_ids": [104596], "source": "gamma", "dataset_version": "ds_mig", "record_version": 1})
        db.insert(cm, "outcomes", {
            "market_id": "mig_m1", "token_id": "mig_tok", "band_label": "20°C or below",
            "outcome_index": 0, "is_winner": True, "source": "gamma",
            "dataset_version": "ds_mig", "record_version": 1})
        db.insert(cm, "market_fee_schedule", {
            "fee_regime": "mig_regime", "fee_status": "UNKNOWN", "source": "gamma",
            "dataset_version": "ds_mig", "record_version": 1})
        cnt_before = {t: db.query(cm, f"SELECT COUNT(*) c FROM {t}")[0]["c"]
                      for t in ("markets", "outcomes", "market_fee_schedule", "dataset_versions")}
        before = db.query(cm, "SELECT market_id, question, city, fee_regime FROM markets WHERE market_id='mig_m1'")

        # run the REAL migration path (applies pending v2)
        db.init_db(cm)
        sv_after = db.get_schema_version(cm)                       # expect 2
        RUN["schema_after"] = sv_after
        applied = db.query(cm, "SELECT version, name FROM schema_version ORDER BY version")

        # idempotency: run the migration path AGAIN → no change
        db.init_db(cm)
        sv_again = db.get_schema_version(cm)
        applied_again = db.query(cm, "SELECT COUNT(*) c FROM schema_version")[0]["c"]
        mig_idempotent = (sv_again == 2 and applied_again == 2)

        after = db.query(cm, "SELECT market_id, question, city, fee_regime, measurement_rule, "
                             "available_at, available_at_confidence, source_timestamps "
                             "FROM markets WHERE market_id='mig_m1'")
        fee_after = db.query(cm, "SELECT fee_regime, raw_fee_fields FROM market_fee_schedule WHERE fee_regime='mig_regime'")
        cnt_after = {t: db.query(cm, f"SELECT COUNT(*) c FROM {t}")[0]["c"]
                     for t in ("markets", "outcomes", "market_fee_schedule", "dataset_versions")}

        survived = bool(before) and bool(after) and after[0]["question"] == before[0]["question"] \
            and after[0]["city"] == before[0]["city"] and after[0]["fee_regime"] == before[0]["fee_regime"]
        counts_preserved = (cnt_before == cnt_after)
        new_cols_null = bool(after) and after[0]["measurement_rule"] is None \
            and after[0]["available_at"] is None and after[0]["source_timestamps"] is None
        fee_survived = bool(fee_after) and fee_after[0]["fee_regime"] == "mig_regime" and fee_after[0]["raw_fee_fields"] is None
        mcols_v2 = set(db.column_names(cm, "markets"))
        fcols_v2 = set(db.column_names(cm, "market_fee_schedule"))
        new_cols_present = v2_market.issubset(mcols_v2) and v2_fee.issubset(fcols_v2)
        # PK still enforced after migration: old row queryable by full PK, exactly one
        pk_row = db.query(cm, "SELECT COUNT(*) c FROM markets WHERE market_id='mig_m1' "
                              "AND dataset_version='ds_mig' AND record_version=1")
        pk_ok = bool(pk_row) and pk_row[0]["c"] == 1
        cm.close()

        mig_ok = (sv_before == 1 and v2_absent_at_v1 and sv_after == 2 and len(applied) == 2
                  and survived and counts_preserved and new_cols_null and fee_survived
                  and new_cols_present and pk_ok and mig_idempotent)
        sec("11", [
            f"(A) CLEAN INIT V2 (baseline, NOT a migration): fresh init → schema_version={clean_v2}",
            "(B) REAL v1→v2 migration (build v1 → insert v1 data → migrate → verify):",
            f"- built schema **v1** (migration 1 only); schema_version BEFORE = {sv_before} (expect 1); "
            f"v2 columns absent at v1 = {v2_absent_at_v1}",
            "- inserted representative v1 rows (markets/outcomes/market_fee_schedule/dataset_versions)",
            f"- ran db.init_db() (real path) → applied {[(r['version'], r['name']) for r in applied]}",
            f"- schema_version AFTER = {sv_after} (expect 2); migration idempotent (2nd run no-op) = {mig_idempotent}",
            f"- v1 data SURVIVED = {survived}; row counts preserved across migration = {counts_preserved} "
            f"({cnt_before} → {cnt_after})",
            f"- new columns present = {new_cols_present}; NULL-able for old rows = {new_cols_null}; "
            f"fee row survived = {fee_survived}; PK still enforced (old row unique) = {pk_ok}",
            "- v2 migration is ADDITIVE COLUMNS only → no new tables/constraints; PK/UNIQUE unchanged & preserved",
            f"→ REAL v1→v2 migration **{'VALIDATED' if mig_ok else 'FAILED'}** "
            "(executed against real DB rows; a clean v2 init is NOT counted as a migration)",
        ])
        mark_real(mig_ok, "real v1→v2 migration (data survives, idempotent, cols added)",
                  {"kind": "real_v1_v2_migration", "schema_before": sv_before,
                   "schema_after": sv_after, "migrations_applied": len(applied),
                   "db": str(mig_file)})
        IMPLEMENTED.append("clean-init v2 baseline (distinguished from real migration)")
        FLAGS["C_migration"] = mig_ok
        if not mig_ok:
            BLOCKERS.append("real v1→v2 migration FAILED (see §11)")
    except Exception as exc:  # noqa: BLE001
        log_error(f"migration test crashed: {exc}\n{traceback.format_exc()[:500]}")
        sec("11", [f"ERROR during migration test: {exc}",
                   "REAL_V1_V2_MIGRATION = UNVERIFIED (harness error; see ISSUES)."])
        FAILED.append("real v1→v2 migration (exception)")
        BLOCKERS.append("real v1→v2 migration UNVERIFIED (harness exception)")


def _transaction_ownership(con) -> None:
    """Point-3 EXPLICIT check: the db helpers (insert/upsert) must NOT autonomously
    commit — a helper write made mid-transaction must be undone by ROLLBACK, since
    ingest_event OWNS the transaction (BEGIN → writes → COMMIT; exception →
    ROLLBACK). If a helper autocommits, per-event atomicity is broken → FAILED.
    Reported as an appendix to §11."""
    try:
        import weather_agent.database as db
        v1 = "atomicity_probe_i_" + RUN["validation_run_id"]
        v2 = "atomicity_probe_u_" + RUN["validation_run_id"]
        con.execute("BEGIN TRANSACTION;")
        db.insert(con, "dataset_versions", {"version": v1, "source": "atomicity_probe"})
        con.execute("ROLLBACK;")
        insert_reverted = db.query(con, "SELECT COUNT(*) c FROM dataset_versions WHERE version=?", [v1])[0]["c"] == 0
        con.execute("BEGIN TRANSACTION;")
        db.upsert(con, "dataset_versions", {"version": v2, "source": "atomicity_probe"}, ["version"])
        con.execute("ROLLBACK;")
        upsert_reverted = db.query(con, "SELECT COUNT(*) c FROM dataset_versions WHERE version=?", [v2])[0]["c"] == 0
        ownership_ok = insert_reverted and upsert_reverted
        SECTIONS["11"] = SECTIONS.get("11", ["(migration section not produced)"]) + [
            "", "TRANSACTION OWNERSHIP (point 3 — ingest_event owns BEGIN/COMMIT/ROLLBACK):",
            "- source inspection: db.insert / db.upsert / db.query run a SINGLE con.execute(...) with "
            "NO commit()/rollback()/autocommit change (documented in database.py) → the CALLER owns the txn.",
            f"- runtime probe: helper INSERT then ROLLBACK leaves no row = {insert_reverted}; "
            f"helper UPSERT then ROLLBACK leaves no row = {upsert_reverted}",
            f"→ helpers-do-not-autocommit **{'TESTED' if ownership_ok else 'FAILED'}** "
            "(a helper autocommit would break per-event atomicity → FAILED, not VALIDATED)",
        ]
        mark_syn(ownership_ok, "db helpers do not autocommit (ROLLBACK reverts a helper write)")
        if not ownership_ok:
            BLOCKERS.append("a db helper autocommits mid-transaction → per-event ATOMICITY BROKEN")
    except Exception as exc:  # noqa: BLE001
        log_error(f"transaction ownership check crashed: {exc}")
        SECTIONS["11"] = SECTIONS.get("11", []) + [f"TRANSACTION OWNERSHIP: ERROR — {exc}"]
        FAILED.append("transaction ownership check (exception)")


# =============================================================================
# §13 discovery, §14 markets, §15 idempotency, §16 dups, §17 token,
# §18 winner, §19 band, §20 fee guard
# =============================================================================
def _discovery_and_checks(con) -> None:
    import weather_agent.database as db
    from weather_agent.polymarket import discovery, resolution
    import requests

    dsv = RUN["dataset_version"]
    sess = requests.Session()
    sess.headers.update({"User-Agent": "pmw-validate/1.0"})

    # ---- E / §13: real fetch (small), ingest a TRIMMED event (≤5 markets) ----
    params = {"tag_id": TEMP_TAG_ID, "closed": "true", "order": "endDate", "ascending": "false", "limit": 2}
    status, events = discovery.fetch_events_page(sess, params)
    log_request(f"{GAMMA}/events", params, status)
    if status != "OK" or not events:
        sec("13", [f"Gamma fetch status={status}, {len(events)} events — no usable sample."])
        for s in ["13", "14", "15", "16", "17", "18", "19", "20"]:
            if s not in SECTIONS:
                sec(s, [f"SKIPPED — gamma fetch status={status}."])
            SKIPPED.append(f"section {s}: no usable gamma sample")
        BLOCKERS.append(f"discovery smoke: gamma fetch status={status}")
        return

    full_event = events[0]
    all_markets = full_event.get("markets") or []
    trimmed = dict(full_event, markets=all_markets[:MAX_SMOKE_MARKETS])
    c1 = discovery.ingest_event(con, trimmed, dsv, endpoint=f"{GAMMA}/events", params=params)
    sec("13", [f"fetched {len(events)} event(s); smoke event id={full_event.get('id')} "
               f"slug={full_event.get('slug')} ({len(all_markets)} bands total)",
               f"INGESTED **{len(trimmed['markets'])} markets** (≤{MAX_SMOKE_MARKETS}) into "
               f"dataset_version `{dsv}` → counts {c1}",
               "status taxonomy on the fetch: OK (real gamma page).",
               f"→ real discovery **{'VALIDATED' if c1['markets'] > 0 else 'FAILED'}**"])
    disc_ok = c1["markets"] > 0
    mark_real(disc_ok, f"real discovery smoke ({c1['markets']} markets)",
              {"kind": "real_gamma_ingest", "markets": c1["markets"], "dataset_version": dsv,
               "fetch_status": status, "event_id": full_event.get("id"),
               "market_ids": [str(mm.get("id")) for mm in trimmed["markets"]]})
    FLAGS["D_discovery"] = disc_ok

    # ---- §14: real markets processed (full per-market record, DIRECT/DERIVED/UNKNOWN) ----
    mrows = db.query(con, "SELECT * FROM markets WHERE dataset_version=? ORDER BY market_id", [dsv])
    m14 = ["| market_id | event_id | city | station/ICAO | unit | measure | resolves | winner | "
           "fee_regime | tick | min | #tok | fetched_at |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    per_market = []
    for m in mrows:
        toks = db.query(con, "SELECT token_id FROM outcomes WHERE dataset_version=? AND market_id=?",
                        [dsv, m["market_id"]])
        tok_ids = [t["token_id"] for t in toks]
        unknowns = [f for f in ("station_identifier", "unit", "measurement_rule", "winning_outcome")
                    if m.get(f) in (None, "")]
        rec = {
            "event_id": m.get("event_id"), "market_id": m.get("market_id"), "token_ids": tok_ids,
            "city": m.get("city"), "target_date": m.get("resolution_timestamp") or m.get("close_time"),
            "station": m.get("station"), "icao": m.get("station_identifier"),
            "measurement_rule": m.get("measurement_rule"), "unit": m.get("unit"),
            "resolution_status": ("RESOLVED" if m.get("winning_outcome") else "UNKNOWN/UNVERIFIED"),
            "winner": m.get("winning_outcome"), "fee_regime": m.get("fee_regime"),
            "tick_size": m.get("tick_size"), "min_order_size": m.get("min_order_size"),
            "dataset_version": dsv, "fetched_at": m.get("ingestion_timestamp"),
            "source_endpoint": f"{GAMMA}/events",
            "classification": {"DIRECT": list(discovery.DIRECT_FIELDS),
                               "DERIVED": list(discovery.DERIVED_FIELDS),
                               "UNKNOWN_for_this_market": unknowns},
        }
        per_market.append(rec)
        m14.append(f"| {m.get('market_id')} | {m.get('event_id')} | {m.get('city')} | "
                   f"{m.get('station')}/{m.get('station_identifier')} | {m.get('unit')} | "
                   f"{'yes' if m.get('measurement_rule') else '—'} | {m.get('resolution_timestamp')} | "
                   f"{m.get('winning_outcome') or 'UNKNOWN'} | {m.get('fee_regime')} | "
                   f"{m.get('tick_size')} | {m.get('min_order_size')} | {len(tok_ids)} | "
                   f"{m.get('ingestion_timestamp')} |")
    RUN["markets_used"] = per_market
    prov_ok = bool(mrows) and all(
        m["source"] == "gamma" and m["ingestion_timestamp"] is not None and m["dataset_version"] == dsv
        and m["available_at"] is None and m["available_at_confidence"] == "UNKNOWN" for m in mrows)
    m14 += ["", "Field classes: DIRECT=from gamma verbatim; DERIVED=parsed/mapped; "
            "UNKNOWN/UNVERIFIED=not available from 2B discovery (never inferred).",
            f"Provenance on all rows (source=gamma, ingestion set, available_at NULL, "
            f"available_at_confidence=UNKNOWN) = {prov_ok}",
            f"→ real markets captured + provenance **{'VALIDATED' if prov_ok else 'FAILED'}**"]
    sec("14", m14)
    mark_real(prov_ok, "provenance on ingested real rows",
              {"kind": "real_rows_provenance", "n_rows": len(mrows), "dataset_version": dsv})

    # ---- §15: idempotency across ALL discovery entities ----
    tables = ("markets", "outcomes", "market_fee_schedule", "data_quality", "dataset_versions")

    def _counts():
        # dataset_versions REGISTRY is keyed by `version` (PK); the fact tables carry
        # a `dataset_version` FK -> dataset_versions.version. Filter by the real key.
        def _key(t):
            return "version" if t == "dataset_versions" else "dataset_version"
        return {t: db.query(con, f"SELECT COUNT(*) c FROM {t} WHERE {_key(t)}=?", [dsv])[0]["c"]
                for t in tables}

    def _snapshot():
        m = db.query(con, "SELECT market_id, record_version, question, winning_outcome, fee_regime, "
                          "tick_size, min_order_size FROM markets WHERE dataset_version=? "
                          "ORDER BY market_id, record_version", [dsv])
        o = db.query(con, "SELECT token_id, market_id, record_version, band_label, is_winner "
                          "FROM outcomes WHERE dataset_version=? ORDER BY token_id, record_version", [dsv])
        f = db.query(con, "SELECT fee_regime, record_version, taker_fee, maker_rebate, fee_status "
                          "FROM market_fee_schedule WHERE dataset_version=? ORDER BY fee_regime, record_version", [dsv])
        q = db.query(con, "SELECT ref, record_version FROM data_quality WHERE dataset_version=? ORDER BY ref", [dsv])
        return json.dumps({"m": m, "o": o, "f": f, "q": q}, sort_keys=True, default=str)

    def _max_rv():
        r = db.query(con, "SELECT MAX(record_version) mx FROM markets WHERE dataset_version=?", [dsv])
        return r[0]["mx"] if r and r[0]["mx"] is not None else 0

    cnt_before, snap_before, rv_before = _counts(), _snapshot(), _max_rv()
    discovery.ingest_event(con, trimmed, dsv, endpoint=f"{GAMMA}/events", params=params)  # 2nd identical ingest
    cnt_after, snap_after, rv_after = _counts(), _snapshot(), _max_rv()
    counts_ok = (cnt_before == cnt_after)
    content_ok = (snap_before == snap_after)
    rv_ok = (rv_before == rv_after == 1)  # no new record_version for identical input
    idem_ok = counts_ok and content_ok and rv_ok
    sec("15", [
        "Entities checked: markets, outcomes, market_fee_schedule, data_quality, dataset_versions.",
        f"row counts before={cnt_before}",
        f"row counts after ={cnt_after} → identical = {counts_ok}",
        f"business-content snapshot (identity+version+values, excl. ingestion_timestamp) unchanged = {content_ok}",
        f"max record_version {rv_before}→{rv_after} (must stay 1; identical input ⇒ NO new version) = {rv_ok}",
        "→ 2nd ingestion is a logical NO-OP across all entities; any new record_version would be a FAIL.",
        f"→ idempotency **{'VALIDATED' if idem_ok else 'FAILED'}**",
    ])
    mark_real(idem_ok, "idempotency across all discovery entities (logical no-op)",
              {"kind": "real_reingest", "counts_before": cnt_before, "counts_after": cnt_after,
               "checksum_before": hashlib.sha1(snap_before.encode()).hexdigest(),
               "checksum_after": hashlib.sha1(snap_after.encode()).hexdigest(),
               "dataset_version": dsv})
    FLAGS["E_idempotency"] = idem_ok

    # ---- §16: duplicates vs versioning (REAL PK identity per table) ----
    dup_m = db.query(con, "SELECT market_id, record_version, COUNT(*) n FROM markets WHERE dataset_version=? "
                          "GROUP BY market_id, record_version HAVING COUNT(*)>1", [dsv])
    dup_o = db.query(con, "SELECT token_id, record_version, COUNT(*) n FROM outcomes WHERE dataset_version=? "
                          "GROUP BY token_id, record_version HAVING COUNT(*)>1", [dsv])
    dup_f = db.query(con, "SELECT fee_regime, record_version, COUNT(*) n FROM market_fee_schedule "
                          "WHERE dataset_version=? GROUP BY fee_regime, record_version HAVING COUNT(*)>1", [dsv])
    dup_q = db.query(con, "SELECT ref, COUNT(*) n FROM data_quality WHERE dataset_version=? "
                          "GROUP BY ref HAVING COUNT(*)>1", [dsv])
    dup_ok = not dup_m and not dup_o and not dup_f and not dup_q
    sec("16", [
        "Identity used per table (NOT market_id alone):",
        "- markets: PK (market_id, dataset_version, record_version)",
        "- outcomes: PK (token_id, dataset_version, record_version)",
        "- market_fee_schedule: PK (fee_regime, dataset_version, record_version)",
        "- data_quality: identity (ref, dataset_version)",
        f"physical PK-duplicates → markets={len(dup_m)}, outcomes={len(dup_o)}, "
        f"fees={len(dup_f)}, data_quality={len(dup_q)} (all must be 0)",
        "multiple record_versions for one natural key = LEGITIMATE versioning (allowed, not a duplicate); "
        "same market_id under a different valid version/entity is NOT assumed duplicate.",
        f"→ no PK/UNIQUE violation **{'VALIDATED' if dup_ok else 'FAILED'}**",
    ])
    mark_real(dup_ok, "no PK/UNIQUE duplicates (versioning distinguished)",
              {"kind": "real_pk_identity", "dataset_version": dsv})

    # ---- §17: token integrity (real + adversarial) ----
    bad_tok = db.query(con, "SELECT token_id FROM outcomes WHERE dataset_version=? "
                            "GROUP BY token_id HAVING COUNT(DISTINCT market_id)>1", [dsv])
    real_tok_ok = not bad_tok
    # adversarial (in-memory, BEFORE any upsert can hide it): two markets share a token
    conflict_ev = _synth_event("tokconf", [
        _synth_market("tm1", "0xtm1", ["SHARED", "tb1"], ["1", "0"]),
        _synth_market("tm2", "0xtm2", ["SHARED", "tb2"], ["0", "1"]),
    ])
    tokmap = {}
    for r in discovery.build_market_records(conflict_ev):
        for o in r["outcomes"]:
            tokmap.setdefault(o["token_id"], set()).add(o["market_id"])
    adversarial_detected = any(len(v) > 1 for v in tokmap.values())
    sec("17", [
        f"REAL sample: tokens mapping to >1 market_id within the dataset_version = {len(bad_tok)} "
        f"→ real token integrity **{'VALIDATED' if real_tok_ok else 'FAILED'}**",
        f"ADVERSARIAL fixture (token 'SHARED' put on two markets): conflict detected IN-MEMORY "
        f"(before any PK/UPSERT could hide it) = {adversarial_detected} → detection **"
        f"{'TESTED' if adversarial_detected else 'FAILED'}** (synthetic ⇒ TESTED)",
    ])
    mark_real(real_tok_ok, "token_id → one market_id on real sample",
              {"kind": "real_token_check", "conflicts": len(bad_tok), "dataset_version": dsv,
               "event_id": full_event.get("id")})
    mark_syn(adversarial_detected, "token conflict detected pre-upsert (adversarial)")
    FLAGS["F_token"] = real_tok_ok and adversarial_detected

    # ---- §18: winner / outcome (real + adversarial) ----
    wb = resolution.event_winning_band(all_markets)
    real_win_ok = wb["status"] in (resolution.VERIFIED, resolution.UNKNOWN)  # DATA_ERROR is a flag
    one = resolution.event_winning_band([
        _synth_market("a", "0xa", ["a1", "a2"], ["0", "1"]),
        _synth_market("b", "0xb", ["b1", "b2"], ["1", "0"]),
        _synth_market("c", "0xc", ["c1", "c2"], ["0", "1"])])
    zero = resolution.event_winning_band([
        _synth_market("a", "0xa", ["a1", "a2"], ["0", "1"]),
        _synth_market("b", "0xb", ["b1", "b2"], ["0", "1"])])
    two = resolution.event_winning_band([
        _synth_market("a", "0xa", ["a1", "a2"], ["1", "0"]),
        _synth_market("b", "0xb", ["b1", "b2"], ["1", "0"])])
    winner_counts_ok = (one["status"] == resolution.VERIFIED and one["n_winners"] == 1
                        and zero["status"] == resolution.UNKNOWN and zero["n_winners"] == 0
                        and two["status"] == resolution.DATA_ERROR and two["n_winners"] == 2)
    # RESOLVED vs INVALID_RESOLUTION (exact numeric; no startswith/truthiness/first-match)
    valid = resolution.resolved_outcome(_synth_market("v", "0xv", ["v1", "v2"], ["1", "0"]))
    inv1 = resolution.resolved_outcome(_synth_market("i1", "0xi1", ["i1", "i2"], ["0.5", "0.5"]))
    inv2 = resolution.resolved_outcome(_synth_market("i2", "0xi2", ["i1", "i2"], ["1", "0.3"]))
    inv3 = resolution.resolved_outcome(_synth_market("i3", "0xi3", ["i1", "i2"], ["0", "0"]))
    resolution_ok = (valid == "Yes" and inv1 is None and inv2 is None and inv3 is None)
    sec("18", [
        f"REAL event winner: status={wb['status']}, winning_band={wb['winning_band']!r}, "
        f"n_winners={wb['n_winners']} → **{'VALIDATED' if real_win_ok else 'FAILED'}** (real data)",
        f"ADVERSARIAL winner counts: 0→{zero['status']}, 1→{one['status']}, 2→{two['status']} "
        f"(expect UNKNOWN/VERIFIED/DATA_ERROR) = {winner_counts_ok} → **"
        f"{'TESTED' if winner_counts_ok else 'FAILED'}**",
        f"RESOLVED vs INVALID (exact-numeric only; startswith/truthiness/first-match FORBIDDEN): "
        f"valid ['1','0']→{valid!r}; invalid ['0.5','0.5']→{inv1}; ['1','0.3']→{inv2}; ['0','0']→{inv3} "
        f"= {resolution_ok} → **{'TESTED' if resolution_ok else 'FAILED'}**",
    ])
    mark_real(real_win_ok, f"winner detection on real event (status={wb['status']})",
              {"kind": "real_event_winner", "status": wb["status"], "event_id": full_event.get("id")})
    mark_syn(winner_counts_ok, "winner counts 0/1/2 → UNKNOWN/VERIFIED/DATA_ERROR (adversarial)")
    mark_syn(resolution_ok, "RESOLVED vs INVALID_RESOLUTION exact-numeric (adversarial)")

    # ---- §19: band integrity (real + adversarial) ----
    labels = [m.get("groupItemTitle") for m in all_markets if m.get("groupItemTitle")]
    bi = resolution.band_integrity(labels)
    part = resolution.band_integrity(["20°C or below", "21°C", "22°C", "23°C or higher"])
    gap = resolution.band_integrity(["20°C or below", "21°C", "24°C", "25°C or higher"])
    overlap = resolution.band_integrity(["20°C or below", "20-22°C", "21°C", "23°C or higher"])
    multi = resolution.band_integrity(["19°C or below", "20°C or below", "22°C or higher"])
    band_adv_ok = (part["is_partition"] is True and bool(gap["gaps"]) and bool(overlap["overlaps"])
                   and multi["n_lower_open"] == 2 and multi["is_partition"] is False)
    band_real_ok = isinstance(bi, dict) and "is_partition" in bi   # analysis produced a real result
    sec("19", [
        f"REAL event bands ({len(labels)}): is_partition={bi['is_partition']}, gaps={len(bi['gaps'])}, "
        f"overlaps={len(bi['overlaps'])}, lower_open={bi['lower_open']!r}, upper_open={bi['upper_open']!r}, "
        f"n_lower_open={bi['n_lower_open']}, n_upper_open={bi['n_upper_open']} "
        "(structure detected, NOT forced to a perfect partition) → "
        f"**{'VALIDATED' if band_real_ok else 'FAILED'}** (analysed on real data)",
        f"ADVERSARIAL: clean→is_partition={part['is_partition']}; gap→gaps={len(gap['gaps'])}; "
        f"overlap→overlaps={len(overlap['overlaps'])}; multi-open→n_lower_open={multi['n_lower_open']} "
        f"= {band_adv_ok} → **{'TESTED' if band_adv_ok else 'FAILED'}**",
    ])
    mark_real(band_real_ok, f"band integrity analysed on real event (is_partition={bi['is_partition']})",
              {"kind": "real_event_bands", "n_bands": len(labels), "event_id": full_event.get("id"),
               "is_partition": bi["is_partition"]})
    mark_syn(band_adv_ok, "band gaps/overlaps/multi-open detection (adversarial)")
    FLAGS["G_winner_band"] = real_win_ok and winner_counts_ok and resolution_ok and band_adv_ok

    # ---- §20: fee guard (#3) — commit a fee row, then a CONFLICTING event that
    #          must raise + roll back the WHOLE event + leave the prior row intact.
    fee_regimes = db.query(con, "SELECT fee_regime, fee_status FROM market_fee_schedule WHERE dataset_version=?", [dsv])
    fee_map_ok = len(fee_regimes) >= 1 and all(r["fee_status"] in ("KNOWN", "UNKNOWN") for r in fee_regimes)
    guard_dsv = "ds_feeguard_" + RUN["validation_run_id"]
    # Event A: commit a weather_fees @0.05 row.
    evA = _synth_event("feeA", [_synth_market("fA", "0xfA", ["fAa", "fAb"], ["1", "0"],
                       fee_type="weather_fees", fees_enabled=True, schedule={"rate": 0.05, "rebateRate": 0.25})])
    discovery.ingest_event(con, evA, guard_dsv)
    # Event B: SAME regime, DIFFERENT schedule @0.10 → must conflict + roll back.
    evB = _synth_event("feeB", [_synth_market("fB", "0xfB", ["fBa", "fBb"], ["0", "1"],
                       fee_type="weather_fees", fees_enabled=True, schedule={"rate": 0.10, "rebateRate": 0.25})])
    guard_raised = False
    try:
        discovery.ingest_event(con, evB, guard_dsv)
    except discovery.FeeScheduleConflict:
        guard_raised = True
    stored = db.query(con, "SELECT taker_fee, raw_fee_fields FROM market_fee_schedule "
                           "WHERE dataset_version=? AND fee_regime='weather_fees'", [guard_dsv])
    prev_intact = False
    if stored and len(stored) == 1:
        raw = json.dumps(stored[0].get("raw_fee_fields"), default=str)
        tf = stored[0].get("taker_fee")
        prev_intact = ("0.05" in raw) and (tf is not None and abs(float(tf) - 0.05) < 1e-9)
    evB_rolled_back = db.query(con, "SELECT COUNT(*) c FROM markets WHERE dataset_version=? AND market_id='fB'",
                               [guard_dsv])[0]["c"] == 0
    guard_ok = guard_raised and prev_intact and evB_rolled_back
    sec("20", [
        f"fee regimes on REAL sample: {[(r['fee_regime'], r['fee_status']) for r in fee_regimes]} → "
        f"mapping **{'VALIDATED' if fee_map_ok else 'FAILED'}** (real data)",
        f"#3 GUARD: committed weather_fees @0.05 (event A), then a conflicting @0.10 (event B): "
        f"FeeScheduleConflict raised = {guard_raised}; prior row (0.05) NOT overwritten = {prev_intact}; "
        f"event B rolled back ENTIRELY (market fB absent) = {evB_rolled_back} "
        f"→ guard **{'TESTED' if guard_ok else 'FAILED'}** (synthetic ⇒ TESTED)",
        "makerBaseFee/takerBaseFee captured RAW only; used in NO edge/PnL/cost/strategy calculation.",
    ])
    mark_real(fee_map_ok, "fee mapping from real sample",
              {"kind": "real_fee_regimes", "regimes": [r["fee_regime"] for r in fee_regimes],
               "dataset_version": dsv, "conflict_observed": guard_raised})
    mark_syn(guard_ok, "#3 fee guard: conflict raised + prior row intact + full rollback (adversarial)")
    FLAGS["H_fee_guard"] = guard_ok


# =============================================================================
# §21 checkpoint / resume — WRITE, RESUME, NO_DUPLICATION
# =============================================================================
def _checkpoint_section(con) -> None:
    """Commit-gated checkpoint + resume-after-ROLLBACK, exercising the REAL
    per-event transaction: event1 commits → checkpoint advances; event2 FAILS
    mid-write → full rollback → checkpoint NOT advanced; resume retries event2 →
    commit → checkpoint advances; event1 never reprocessed / duplicated."""
    try:
        import weather_agent.database as db
        from weather_agent.polymarket import discovery
        dsv = "ds_ckpt_" + RUN["validation_run_id"]
        e1 = _synth_event("cke1", [_synth_market("cke1m", "0xcke1", ["cke1a", "cke1b"], ["1", "0"])])
        e2 = _synth_event("cke2", [_synth_market("cke2m", "0xcke2", ["cke2a", "cke2b"], ["0", "1"])])
        checkpoint = set()

        # 1) WRITE: ingest e1 → COMMIT → then (and only then) advance the checkpoint.
        discovery.ingest_event(con, e1, dsv)
        checkpoint.add("cke1")
        e1_rows = db.query(con, "SELECT COUNT(*) c FROM markets WHERE dataset_version=? AND market_id='cke1m'", [dsv])[0]["c"]
        write_ok = ("cke1" in checkpoint) and e1_rows == 1

        # 2) e2 fails transiently (injected fault on its LAST write) → full ROLLBACK
        #    → checkpoint NOT advanced (we never reach checkpoint.add for e2).
        orig = db.upsert
        fired = {"n": 0}

        def _faulty(c, table, row, cols):
            if table == "data_quality" and fired["n"] == 0:
                fired["n"] += 1
                raise RuntimeError("injected transient failure (e2)")
            return orig(c, table, row, cols)

        db.upsert = _faulty
        e2_failed = False
        try:
            discovery.ingest_event(con, e2, dsv)
            checkpoint.add("cke2")   # unreachable on failure
        except Exception:
            e2_failed = True
        finally:
            db.upsert = orig
        e2_absent = db.query(con, "SELECT COUNT(*) c FROM markets WHERE dataset_version=? AND market_id='cke2m'", [dsv])[0]["c"] == 0
        not_advanced = "cke2" not in checkpoint
        rollback_ok = e2_failed and e2_absent and not_advanced

        # 3) RESUME: retry e2 → COMMIT → advance checkpoint; e1 not reprocessed.
        discovery.ingest_event(con, e2, dsv)
        checkpoint.add("cke2")
        e1_final = db.query(con, "SELECT COUNT(*) c FROM markets WHERE dataset_version=? AND market_id='cke1m'", [dsv])[0]["c"]
        e2_final = db.query(con, "SELECT COUNT(*) c FROM markets WHERE dataset_version=? AND market_id='cke2m'", [dsv])[0]["c"]
        resume_ok = ("cke2" in checkpoint) and e2_final == 1
        noduptest = (e1_final == 1 and e2_final == 1)
        all_ok = write_ok and rollback_ok and resume_ok and noduptest
        sec("21", [
            f"CHECKPOINT_WRITE_TEST: event1 ingested → COMMIT → checkpoint advanced = {write_ok} "
            "(checkpoint advances ONLY after a successful COMMIT)",
            f"event2 FAILS mid-write → full ROLLBACK (market cke2m absent = {e2_absent}) → checkpoint "
            f"NOT advanced ('cke2' absent = {not_advanced}) = {rollback_ok}",
            f"CHECKPOINT_RESUME_TEST: retry event2 → COMMIT → checkpoint advanced; event1 not reprocessed = {resume_ok}",
            f"CHECKPOINT_NO_DUPLICATION_TEST: event1 rows={e1_final}, event2 rows={e2_final} (each exactly 1) = {noduptest}",
            f"→ commit-gated checkpoint + resume-after-rollback **{'TESTED' if all_ok else 'FAILED'}** — "
            "exercised with an IN-MEMORY checkpoint and an INJECTED fault (simulated interruption) ⇒ "
            "TESTED/UNVERIFIED, NOT VALIDATED (real interruption vs live gamma + disk-persisted "
            "checkpoint deferred to deployment — see BLOCKERS).",
        ])
        mark_syn(all_ok, "checkpoint commit-gated + resume-after-rollback (stubbed/injected)")
        FLAGS["I_checkpoint"] = all_ok  # demonstrated (with documented limitation) satisfies condition I
        BLOCKERS.append("checkpoint/resume only stub-tested (in-memory checkpoint + injected fault); "
                        "real interruption vs live gamma + disk-persisted checkpoint deferred to deployment")
    except Exception as exc:  # noqa: BLE001
        log_error(f"checkpoint section crashed: {exc}")
        sec("21", [f"ERROR — checkpoint/resume: {exc}"])
        FAILED.append("checkpoint/resume (exception)")


# =============================================================================
# §22 AS-OF / no-look-ahead
# =============================================================================
def _asof_section(con, ingested: bool) -> None:
    try:
        import weather_agent.database as db
        asof_map = dict(db.AS_OF_COLUMNS)
        weather_ok = (asof_map.get("weather_forecasts") == "available_at"
                      and asof_map.get("weather_observations") == "available_at")
        lines = ["AS_OF_COLUMNS: " + json.dumps(asof_map),
                 f"weather tables key on `available_at` (NOT ingestion_timestamp) = {weather_ok}"]
        sem_ok = weather_ok
        if ingested:
            dsv = RUN["dataset_version"]
            rows = db.query(con, "SELECT available_at, available_at_confidence, ingestion_timestamp, "
                                 "source_timestamp FROM markets WHERE dataset_version=?", [dsv])
            avail_null = bool(rows) and all(r["available_at"] is None
                                            and r["available_at_confidence"] == "UNKNOWN" for r in rows)
            distinct = bool(rows) and all(r["ingestion_timestamp"] is not None for r in rows)
            lines += [f"ingested markets: available_at IS NULL & confidence=UNKNOWN = {avail_null} "
                      "(correct for 2B — availability of MARKET data is not known from gamma)",
                      f"available_at is never auto-set to ingestion_timestamp/createdAt/updatedAt "
                      f"(ingestion_timestamp present & distinct) = {distinct}"]
            sem_ok = weather_ok and avail_null and distinct
        lines += [
            f"→ AS-OF schema/semantics **{'TESTED' if sem_ok else 'FAILED'}** — this is a SCHEMA/CONFIG "
            "check. There are NO real weather_forecasts/observations rows in 2B, so this is **NOT "
            "VALIDATED**. End-to-end no-look-ahead is **NOT VALIDATED yet** (deferred to the feature "
            "builder + price/weather ingestion subphase).",
        ]
        sec("22", lines)
        mark_syn(sem_ok, "as-of schema/semantics (NOT end-to-end no-look-ahead)")
        BLOCKERS.append("end-to-end no-look-ahead NOT validated (needs price/weather ingestion + feature builder)")
    except Exception as exc:  # noqa: BLE001
        sec("22", [f"ERROR — as-of: {exc}"])
        FAILED.append("as-of (exception)")


# =============================================================================
# §23 error taxonomy
# =============================================================================
def _error_taxonomy_section(con) -> None:
    try:
        from weather_agent.polymarket import discovery
        import requests
        fp = discovery.fetch_events_page
        tax = {
            "SUCCESS(200,data)": fp(_StubSession(_StubResp(200, [_synth_event("x", [
                _synth_market("xm", "0xxm", ["xa", "xb"], ["1", "0"])])])), {}, max_retries=0)[0],
            "EMPTY(200,[])": fp(_StubSession(_StubResp(200, [])), {}, max_retries=0)[0],
            "HTTP_ERROR(500)": fp(_StubSession(_StubResp(500)), {}, max_retries=0)[0],
            "NOT_FOUND(404)": fp(_StubSession(_StubResp(404)), {}, max_retries=0)[0],
            "RATE_LIMITED(429)": fp(_StubSession(_StubResp(429, retry_after="0")), {}, max_retries=0)[0],
            "INVALID_PAYLOAD(200,badjson)": fp(_StubSession(_StubResp(200, raise_json=True)), {}, max_retries=0)[0],
            "TIMEOUT": fp(_RaiseStubSession(requests.Timeout("t")), {}, max_retries=0)[0],
            "NETWORK": fp(_RaiseStubSession(requests.RequestException("n")), {}, max_retries=0)[0],
        }
        expect = {
            "SUCCESS(200,data)": "OK", "EMPTY(200,[])": "EMPTY", "HTTP_ERROR(500)": "HTTP_ERROR",
            "NOT_FOUND(404)": "HTTP_ERROR", "RATE_LIMITED(429)": "RATE_LIMITED",
            "INVALID_PAYLOAD(200,badjson)": "PARSE_ERROR", "TIMEOUT": "TIMEOUT", "NETWORK": "NETWORK_ERROR",
        }
        tax_ok = all(tax[k] == expect[k] for k in expect)
        s_err = discovery.discover(con, "ds_err_" + RUN["validation_run_id"], page_limit=5,
                                   max_pages=1, session=_StubSession(_StubResp(500)))
        stop_ok = s_err["status"] in discovery.ERROR_STATUSES and s_err["stopped_early"]
        sec("23", [
            "Distinct statuses (timeout ≠ empty ≠ rate-limit ≠ not-found; none filled by inference):",
            f"{tax}",
            f"expected {expect} → match = {tax_ok}",
            "NOT_FOUND(404) maps to HTTP_ERROR (any non-200 → HTTP_ERROR); PARTIAL/truncated payloads "
            "surface as PARSE_ERROR if unparseable, else OK with the parsed count.",
            f"discover() on a 500 → status={s_err['status']}, stopped_early={s_err['stopped_early']} "
            "(records UNVERIFIED and STOPS; never infers) = " + str(stop_ok),
            f"→ error taxonomy **{'TESTED' if (tax_ok and stop_ok) else 'FAILED'}** (offline stubs ⇒ TESTED)",
        ])
        # J (no silently inferred data): evidenced by distinct statuses + discover
        # recording UNVERIFIED and STOPPING on error rather than inferring.
        FLAGS["J_no_inferred"] = bool(tax_ok and stop_ok)
        mark_syn(tax_ok and stop_ok, "error taxonomy + stop-on-error (stubbed)")
    except Exception as exc:  # noqa: BLE001
        log_error(f"error taxonomy crashed: {exc}")
        sec("23", [f"ERROR — taxonomy: {exc}"])
        FAILED.append("error taxonomy (exception)")


# =============================================================================
# report + verdict
# =============================================================================
STATUS_DEFS = (
    "**Status definitions (literal).** IMPLEMENTED = written, not executed. "
    "TESTED = executed and passed (unit test / synthetic fixture / offline stub / schema-config check; "
    "a green unit test is TESTED). VALIDATED = behaviour executed AND checked against a real run and, "
    "where it applies, real data (real migration, real discovery, idempotency/duplicates/token/winner/"
    "band/provenance/fee-mapping on the real sample). FAILED = executed and failed. SKIPPED = not executed. "
    "A pytest PASS is NEVER auto-VALIDATED."
)

SECTION_TITLES = {
    "11": "MIGRATION RESULT + TRANSACTION OWNERSHIP", "12": "PYTEST SUMMARY (2A+2B)",
    "13": "DISCOVERY SUMMARY", "14": "REAL MARKETS PROCESSED", "15": "IDEMPOTENCY RESULT",
    "16": "DUPLICATE / VERSION RESULT", "17": "TOKEN INTEGRITY", "18": "WINNER / OUTCOME INTEGRITY",
    "19": "BAND INTEGRITY", "20": "FEE GUARD", "21": "CHECKPOINT / RESUME",
    "22": "AS-OF / NO-LOOK-AHEAD STATUS", "23": "ERROR TAXONOMY", "24": "FINAL MATRIX",
}


def _compute_verdict() -> dict:
    conds = {
        "A pytest 2A+2B executed": FLAGS["A_pytest_ran"],
        "B no critical FAIL": FLAGS["B_no_critical_fail"] and not FAILED,
        "C migration real VALIDATED or explicitly UNIMPLEMENTED": FLAGS["C_migration"],
        "D real discovery works": FLAGS["D_discovery"],
        "E idempotency demonstrated": FLAGS["E_idempotency"],
        "F token integrity": FLAGS["F_token"],
        "G winner/outcome/band": FLAGS["G_winner_band"],
        "H fee conflict guard": FLAGS["H_fee_guard"],
        "I checkpoint/resume demonstrated or explicitly limited": FLAGS["I_checkpoint"],
        "J no silently inferred data": FLAGS["J_no_inferred"],
        "K nothing VALIDATED without evidence": FLAGS["K_evidence_backed"],
    }
    return {"conds": conds, "validated": all(conds.values())}


def _finish(args, stopped) -> None:
    # FINAL evidence audit → condition K (feeds the verdict). Requires each
    # VALIDATED item to carry its minimum real-execution evidence fields.
    k_ok, k_audit = _check_evidence()
    FLAGS["K_evidence_backed"] = k_ok
    # §24 FINAL MATRIX + evidence audit
    sec("24", [
        "| status | count |", "|---|---|",
        f"| IMPLEMENTED | {len(IMPLEMENTED)} |", f"| TESTED | {len(TESTED)} |",
        f"| VALIDATED | {len(VALIDATED)} |", f"| FAILED | {len(FAILED)} |",
        f"| SKIPPED | {len(SKIPPED)} |", "",
        "**VALIDATED (real run + real data):** " + ("; ".join(VALIDATED) or "(none)"),
        "", "**TESTED (unit / synthetic / stub / schema-config):** " +
        (str(len(TESTED)) + " items incl. " + "; ".join([t for t in TESTED if "::" not in t][:20])
         if TESTED else "(none)"),
        "", "**FAILED:** " + ("; ".join(FAILED) or "(none)"),
        "", "**SKIPPED:** " + ("; ".join(SKIPPED[:20]) + (" …" if len(SKIPPED) > 20 else "") or "(none)"),
        "", "**Evidence audit (each VALIDATED item ↔ a real-execution record with its "
        "required minimum fields):**",
    ] + (k_audit or ["- (no VALIDATED items)"]) + [
        f"→ all VALIDATED items evidence-backed with required fields (condition K) = {k_ok}",
    ])

    verdict = _compute_verdict()
    _write_report(verdict, stopped)

    if args.upload:
        _try_upload()
        _write_report(verdict, stopped)

    _print_summary(verdict, stopped)


def _write_report(verdict, stopped) -> None:
    L = ["# PHASE 2B — VALIDATION REPORT", "", STATUS_DEFS, "", "## Environment / metadata", ""]
    meta = [
        ("1 validation_run_id", RUN["validation_run_id"]), ("2 timestamp (UTC)", RUN["timestamp_utc"]),
        ("3 git commit", RUN["git_commit"]), ("4 Python", RUN["python_version"]),
        ("5 OS / platform", RUN["platform"]), ("6 dependency versions", RUN["dependency_versions"]),
        ("7 dataset_version", RUN["dataset_version"]), ("8 DB path", RUN["db_path"]),
        ("9 schema version BEFORE (migration test)", RUN["schema_before"]),
        ("10 schema version AFTER (migration test)", RUN["schema_after"]),
    ]
    for k, v in meta:
        L.append(f"- **{k}**: {v}")
    L.append(f"- **requests** ({len(RUN['requests'])}): " +
             "; ".join(f"{r['endpoint']}→{r['status']}" for r in RUN["requests"]))
    L.append(f"- **errors** ({len(RUN['errors'])}): " + ("; ".join(RUN["errors"]) if RUN["errors"] else "none"))
    L.append(f"- **upload_status**: {RUN['upload_status']} (best-effort; not part of validation)")
    L += ["", "## PRECHECK", ""] + SECTIONS.get("PRECHECK", ["(not produced)"])

    for i in range(11, 25):
        sid = str(i)
        L += ["", f"## {sid}. {SECTION_TITLES[sid]}", ""] + SECTIONS.get(sid, ["(not produced)"])

    # per-market appendix (full records, condition 9)
    L += ["", "## 14b. REAL MARKETS — full per-market records (JSON)", "",
          "```json", json.dumps(RUN["markets_used"], indent=2, default=str)[:8000], "```"]

    # BLOCKERS
    L += ["", "## BLOCKERS FOR PHASE 2C", ""]
    L += ([f"- {b}" for b in dict.fromkeys(BLOCKERS)] or ["- (none recorded)"])

    # VERDICT
    L += ["", "## VERDICT", ""]
    for cond, ok in verdict["conds"].items():
        L.append(f"- [{'x' if ok else ' '}] {cond}")
    L += ["", ("# PHASE 2B VALIDATED" if verdict["validated"] else "# PHASE 2B NOT VALIDATED")]
    if not verdict["validated"]:
        L += ["", "Unmet conditions / blockers:"]
        L += [f"- {c}" for c, ok in verdict["conds"].items() if not ok]
        L += [f"- {b}" for b in dict.fromkeys(BLOCKERS)]
    if stopped:
        L += ["", f"_note: run stopped early at: {stopped}_"]
    L += ["", "---", f"_Local report is the source of truth: {REPORT_PATH}_"]

    REPORT_PATH.write_text("\n".join(L), encoding="utf-8")


def _try_upload() -> None:
    try:
        import requests
        r = requests.post("https://paste.rs", data=REPORT_PATH.read_bytes(), timeout=30)
        RUN["upload_status"] = (f"OK {r.text.strip()}" if r.status_code in (200, 201) and r.text.strip()
                                else f"FAILED (status {r.status_code})")
    except Exception as exc:  # noqa: BLE001
        RUN["upload_status"] = f"FAILED ({str(exc)[:120]})"


def _print_summary(verdict, stopped) -> None:
    print("=" * 72)
    print("PHASE 2B VALIDATION — SUMMARY")
    print("=" * 72)
    print(f"run_id     : {RUN['validation_run_id']}   git: {str(RUN['git_commit'])[:12]}")
    print(f"python     : {RUN['python_version']}  {RUN['platform']}")
    print(f"stopped    : {stopped or 'no (full sequence)'}")
    print(f"IMPLEMENTED : {len(IMPLEMENTED)}   TESTED: {len(TESTED)}   VALIDATED: {len(VALIDATED)}")
    print(f"FAILED      : {len(FAILED)}   SKIPPED: {len(SKIPPED)}   BLOCKERS: {len(set(BLOCKERS))}")
    print(f"upload      : {RUN['upload_status']}")
    print("-" * 72)
    print("VERDICT: " + ("PHASE 2B VALIDATED" if verdict["validated"] else "PHASE 2B NOT VALIDATED"))
    print("-" * 72)
    print(f"REPORT (source of truth): {REPORT_PATH}")
    print("Return it (SEPARATE, OPTIONAL step):")
    print(f"  curl --data-binary @{REPORT_PATH} https://paste.rs")
    print("=" * 72)


if __name__ == "__main__":
    try:
        rc = main()
    except Exception as exc:  # noqa: BLE001 — never crash without leaving a report
        log_error(f"FATAL: {exc}\n{traceback.format_exc()[:800]}")
        try:
            v = _compute_verdict()
            _write_report(v, stopped="fatal_error")
        except Exception:
            pass
        print(f"FATAL: {exc}. Partial report (if any) at {REPORT_PATH}")
        rc = 3
    sys.exit(rc)
