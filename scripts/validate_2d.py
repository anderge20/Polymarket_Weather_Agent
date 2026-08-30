#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/validate_2d.py — Phase 2D validation harness (Strategy A V1 signal generator).

Same discipline as the 2B/2C harnesses: IMPLEMENTED != TESTED != VALIDATED. NOTHING
in 2A/2B/2C is touched. A GREEN pytest is TESTED, NOT VALIDATED.

What it does:
  * PREFLIGHT (python, duckdb, pytest, strategy module importable).
  * pytest tests/test_strategy_a.py  (unit + adversarial).
  * Deterministic in-memory scenarios asserted against the actual DuckDB:
      - ELIGIBLE event -> predictions + signals (BUY/FADE/HOLD), contract relationships,
        edge_net/net_edge NULL, confidence NULL, timestamp == prediction_time.
      - INELIGIBLE event (not a partition) -> markets_excluded (stage="feature"), and
        NO predictions / NO signals.
      - forecast available_at > prediction_time -> event excluded (no look-ahead).
      - determinism (same inputs -> same rows).
      - resolution fields are NOT columns of predictions/signals.
  * Writes results/PHASE_2D_VALIDATION_REPORT.md with a VERDICT.

VALIDATED requires a REAL catalog run (real markets/outcomes/prices/forecasts, USER-RUN
on Hetzner) — which is BLOCKED in Phase 2D. Therefore this harness can reach at most
TESTED; it NEVER declares Strategy A VALIDATED from synthetic data / a green pytest.

Usage:  PYTHONPATH=src python3 scripts/validate_2d.py
"""
from __future__ import annotations

import datetime
import os
import platform
import subprocess
import sys

import weather_agent.database as db
from weather_agent.features import FORBIDDEN_FEATURE_FIELDS
from weather_agent.probability import quantiles_to_distribution, band_probability
from weather_agent.strategy import generate_event_signals

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
SRC = os.path.join(ROOT, "src")
RESULTS = os.path.join(ROOT, "results")
REPORT = os.path.join(RESULTS, "PHASE_2D_VALIDATION_REPORT.md")

sys.path.insert(0, SRC)

LINES: list[str] = []
PROBLEMS: list[str] = []

DSV = "ds_2d_validate"
STATION, MODEL, TARGET = "VSTN", "vmodel", "2026-08-20"
T = "2026-08-19T12:00:00+00:00"
OBS, ISSUE, AVAIL = "2026-08-19T11:00:00+00:00", "2026-08-19T00:00:00+00:00", "2026-08-19T00:30:00+00:00"
EVENT = "VEVT"
Q = dict(p10=24.0, p25=25.0, p50=25.0, p75=26.0, p90=27.0)
BANDS = [
    ("m1", "24°C or below", None, 24.0, "y1", "n1"),
    ("m2", "25°C", 25.0, 25.0, "y2", "n2"),
    ("m3", "26°C", 26.0, 26.0, "y3", "n3"),
    ("m4", "27°C or higher", 27.0, None, "y4", "n4"),
]
_DIST = quantiles_to_distribution(**Q)
PW = {b[0]: band_probability(_DIST, lo=b[2], hi=b[3]) for b in BANDS}
TOL = dict(weather_sum_tolerance=1e-6, market_sum_min=0.0, market_sum_max=5.0)


def log(m):
    LINES.append(m)
    print(m)


def _seed(con, prices, available_at=AVAIL, bands=BANDS, no_prices=None):
    no_prices = no_prices or {}
    db.insert(con, "weather_forecasts", {
        "issue_time": ISSUE, "forecast_run": "00z", "target_date": TARGET,
        "city": "V", "station": STATION, "model": MODEL, "forecast_tmax": 25.5,
        "forecast_p10": Q["p10"], "forecast_p25": Q["p25"], "forecast_p50": Q["p50"],
        "forecast_p75": Q["p75"], "forecast_p90": Q["p90"], "available_at": available_at,
        "fetched_at": ISSUE, "source": "validate_2d", "ingestion_timestamp": ISSUE,
        "dataset_version": DSV, "record_version": 1,
    })
    for (mid, label, lo, hi, y, n) in bands:
        db.insert(con, "markets", {
            "market_id": mid, "event_id": EVENT, "station": STATION, "unit": "C",
            "source": "validate_2d", "ingestion_timestamp": ISSUE,
            "dataset_version": DSV, "record_version": 1})
        for tok, lab, idx in ((y, "Yes", 0), (n, "No", 1)):
            db.insert(con, "outcomes", {
                "market_id": mid, "token_id": tok, "band_label": label, "lo": lo, "hi": hi,
                "outcome_index": idx, "outcome_label": lab, "source": "validate_2d",
                "ingestion_timestamp": ISSUE, "dataset_version": DSV, "record_version": 1})
        for tok, pval in ((y, prices.get(mid)), (n, no_prices.get(mid))):
            if pval is not None:
                db.insert(con, "price_history", {
                    "observation_time": OBS, "market_id": mid, "token_id": tok,
                    "indicative_price": pval, "price_semantics": "MIDPOINT_ESTIMATED",
                    "price_source": "CLOB_PRICES_HISTORY", "fidelity": 1, "source_window": "DIRECT",
                    "fetched_at": OBS, "source": "validate_2d", "ingestion_timestamp": ISSUE,
                    "dataset_version": DSV, "record_version": 1})


def _run(con, **over):
    kw = dict(event_id=EVENT, prediction_time=T, model=MODEL, target_date=TARGET,
              dataset_version=DSV, tau=0.05, **TOL)
    kw.update(over)
    return generate_event_signals(con, **kw)


def _prices_cov():
    order = sorted(PW, key=lambda k: PW[k])
    buy, fade = order[-1], order[0]
    out = {}
    for mid in PW:
        out[mid] = 0.0 if mid == buy else (min(1.0, PW[mid] + 0.5) if mid == fade else PW[mid])
    return out


def scenario_eligible():
    con = db.init_db(db_path=":memory:")
    try:
        _seed(con, _prices_cov())
        s = _run(con)
        preds = db.query(con, "SELECT * FROM predictions")
        sigs = db.query(con, "SELECT * FROM signals")
        excl = db.query(con, "SELECT * FROM markets_excluded")
        signals = {g["signal"] for g in sigs}
        contract = all(
            p["p_model"] == p["p_weather"] and p["fair_value"] == p["p_model"]
            and abs(p["edge_gross"] - (p["fair_value"] - p["p_market"])) < 1e-12
            and p["edge_net"] is None and p["confidence"] is None
            and p["model_version"] == "stratA_pmodel_v1"
            and str(p["timestamp"])[:19] == "2026-08-19 12:00:00"
            for p in preds)
        sig_ok = all(g["net_edge"] is None and g["confidence"] is None
                     and g["strategy"] == "strategy_a_v1" and g["signal"] != "SELL"
                     for g in sigs)
        ok = (s["eligible"] is True and len(preds) == 4 and len(sigs) == 4 and not excl
              and contract and sig_ok and {"BUY", "FADE", "HOLD"} <= signals
              and signals <= {"BUY", "FADE", "HOLD"})
        log(f"- ELIGIBLE: preds={len(preds)} sigs={len(sigs)} signals={sorted(signals)} "
            f"contract={contract} no_sell={'SELL' not in signals} -> {'PASS' if ok else 'FAIL'}")
        return ok
    finally:
        con.close()


def scenario_excluded():
    con = db.init_db(db_path=":memory:")
    try:
        gap = [("g1", "24°C or below", None, 24.0, "gy1", "gn1"),
               ("g2", "26°C or higher", 26.0, None, "gy2", "gn2")]
        _seed(con, {"g1": 0.3, "g2": 0.3}, bands=gap)
        s = _run(con)
        preds = db.query(con, "SELECT COUNT(*) c FROM predictions")[0]["c"]
        sigs = db.query(con, "SELECT COUNT(*) c FROM signals")[0]["c"]
        excl = db.query(con, "SELECT * FROM markets_excluded")
        ok = (s["eligible"] is False and s["reason"] == "event_not_partition"
              and preds == 0 and sigs == 0 and len(excl) == 2
              and all(e["stage"] == "feature" for e in excl))
        log(f"- EXCLUDED(not_partition): reason={s['reason']} preds={preds} sigs={sigs} "
            f"excluded={len(excl)} stage_feature={all(e['stage'] == 'feature' for e in excl)} "
            f"-> {'PASS' if ok else 'FAIL'}")
        return ok
    finally:
        con.close()


def scenario_no_lookahead():
    con = db.init_db(db_path=":memory:")
    try:
        _seed(con, _prices_cov(), available_at="2026-08-19T18:00:00+00:00")  # after T
        s = _run(con)
        preds = db.query(con, "SELECT COUNT(*) c FROM predictions")[0]["c"]
        ok = (s["eligible"] is False and s["reason"] == "missing_feature" and preds == 0)
        log(f"- NO-LOOK-AHEAD (forecast available_at>T excluded): reason={s['reason']} "
            f"preds={preds} -> {'PASS' if ok else 'FAIL'}")
        return ok
    finally:
        con.close()


def scenario_determinism():
    def fp():
        con = db.init_db(db_path=":memory:")
        try:
            _seed(con, _prices_cov())
            _run(con)
            rows = db.query(con, "SELECT * FROM predictions") + db.query(con, "SELECT * FROM signals")
            return sorted(tuple(sorted((k, str(v)) for k, v in r.items()
                                       if k != "ingestion_timestamp")) for r in rows)
        finally:
            con.close()
    ok = fp() == fp()
    log(f"- DETERMINISM (same inputs -> same rows): {'PASS' if ok else 'FAIL'}")
    return ok


def scenario_no_resolution_columns():
    con = db.init_db(db_path=":memory:")
    try:
        ok = all(FORBIDDEN_FEATURE_FIELDS.isdisjoint(set(db.column_names(con, t)))
                 for t in ("predictions", "signals"))
        log(f"- NO RESOLUTION FIELDS in predictions/signals columns: {'PASS' if ok else 'FAIL'}")
        return ok
    finally:
        con.close()


def scenario_price_guard():
    con = db.init_db(db_path=":memory:")
    try:
        # full partition, but each band-market priced ONLY on its NO token -> the price-lineage
        # guard must fail-closed (market_prob would not be the YES token's price).
        _seed(con, {}, no_prices={b[0]: 0.3 for b in BANDS})
        s = _run(con)
        preds = db.query(con, "SELECT COUNT(*) c FROM predictions")[0]["c"]
        sigs = db.query(con, "SELECT COUNT(*) c FROM signals")[0]["c"]
        ok = (s["eligible"] is False and s["reason"] == "ambiguous_or_wrong_token_price"
              and preds == 0 and sigs == 0)
        log(f"- PRICE-LINEAGE GUARD (only NO priced -> fail-closed): reason={s['reason']} "
            f"preds={preds} sigs={sigs} -> {'PASS' if ok else 'FAIL'}")
        return ok
    finally:
        con.close()


def run_pytest(target):
    cmd = [sys.executable, "-m", "pytest", "-q", target]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([SRC, os.path.join(ROOT, "tests"), env.get("PYTHONPATH", "")])
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=ROOT, timeout=1800)
    tail = "\n".join((r.stdout + r.stderr).strip().splitlines()[-8:])
    return r.returncode == 0, tail


def preflight():
    import importlib
    checks = [("python", True, platform.python_version())]
    for mod in ("duckdb", "pytest"):
        try:
            m = importlib.import_module(mod)
            checks.append((mod, True, getattr(m, "__version__", "?")))
        except Exception as e:
            checks.append((mod, False, str(e)))
            PROBLEMS.append(f"missing dependency: {mod}")
    try:
        importlib.import_module("weather_agent.strategy.strategy_a")
        checks.append(("weather_agent.strategy.strategy_a", True, "import OK"))
    except Exception as e:
        checks.append(("weather_agent.strategy.strategy_a", False, str(e)))
        PROBLEMS.append(f"cannot import strategy_a: {e}")
    return checks


def main():
    os.makedirs(RESULTS, exist_ok=True)
    utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    log("# PHASE 2D — VALIDATION REPORT (Strategy A V1 signal generator)")
    log(f"utc={utc} python={platform.python_version()} os={platform.platform()}")
    log("")
    log("## 1. PREFLIGHT")
    for name, ok, detail in preflight():
        log(f"- {name}: {'OK' if ok else 'FAIL'} ({detail})")
    if PROBLEMS:
        log("\n**PREFLIGHT FAILED — stopping.**")
        for p in PROBLEMS:
            log(f"- {p}")
        _write()
        sys.exit(1)

    log("\n## 2. pytest tests/test_strategy_a.py")
    pt_ok, pt_tail = run_pytest("tests/test_strategy_a.py")
    log(f"```\n{pt_tail}\n```\n- strategy_a pytest: {'PASS' if pt_ok else 'FAIL'}")

    log("\n## 3. Deterministic in-memory scenarios (asserted vs actual DuckDB)")
    sc = [scenario_eligible(), scenario_excluded(), scenario_no_lookahead(),
          scenario_determinism(), scenario_no_resolution_columns(), scenario_price_guard()]
    scenarios_ok = all(sc)

    tested = pt_ok and scenarios_ok
    # VALIDATED requires a REAL catalog run (real markets/outcomes/prices/forecasts),
    # USER-RUN on Hetzner. That catalog is BLOCKED in Phase 2D, so a green run here is
    # TESTED, never VALIDATED. Do NOT flip this to True on synthetic data.
    validated = False

    log("\n## 4. STATUS  (a green pytest is TESTED, NOT VALIDATED)")
    log(f"- TESTED (pytest green AND synthetic scenarios pass): {tested} "
        f"(pytest={pt_ok}, scenarios={scenarios_ok})")
    log(f"- VALIDATED: {validated} — BLOCKED: requires a REAL catalog run "
        "(real markets/outcomes/prices/forecasts, USER-RUN on Hetzner). Synthetic data "
        "and a green pytest are NOT sufficient for VALIDATED.")

    log("\n## 5. VERDICT")
    log(f"PHASE 2D STRATEGY A V1 = {'TESTED' if tested else 'NOT TESTED'} "
        f"(VALIDATED = NO — real catalog BLOCKED)")
    log("END OF REPORT")
    _write()
    sys.exit(0 if tested else 1)


def _write():
    try:
        with open(REPORT, "w", encoding="utf-8") as fh:
            fh.write("\n".join(LINES) + "\n")
        print(f"\n[*] report written: {REPORT}")
    except OSError as e:
        print(f"[!] could not write report: {e}")


if __name__ == "__main__":
    main()
