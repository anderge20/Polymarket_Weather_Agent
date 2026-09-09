#!/usr/bin/env python3
"""
fit_m2_v3.py — per-station location shift with empirical-Bayes shrinkage
=========================================================================

Implements `PREREG_M2_ERROR_v3.md` (sha 11c2c69f...), frozen before computing
anything. v2 is withdrawn: it calibrated in aggregate while 43 of 45 stations
were miscalibrated, because opposite station biases cancel (B-11).

Two rules that make or break this, both preregistered:

  * the shift is SHRUNK. The raw per-station median overcorrects, because the
    observed spread between medians contains signal AND estimation noise. `w` is
    estimated from each training window's own variance decomposition, with the SE
    of the median measured by bootstrap rather than the normal-theory formula,
    which overestimates it by ~25 % on this skewed sample.
  * the shift is estimated WALK-FORWARD. Estimating 45 shifts on the same pairs
    the calibration is then measured on would make v3 pass by construction: with
    ~30 points and one free parameter per station, in-sample calibration is
    nearly automatic.

Usage:
    python3 scripts/fit_m2_v3.py --db data/pmw.duckdb --out ~/pmw-e2
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from fit_m2 import DATASET_VERSION, LEADS, load_pairs  # noqa: E402

from weather_agent import database as db  # noqa: E402
from weather_agent import error_model as em  # noqa: E402

PREREG_SHA = "11c2c69f8cc73b49e9caebdfde61c2cd7f48227d7842c0ddf3359aef32627251"

#: v3 §4.1 — share of stations that must be calibrated. Fixed here, before running.
MIN_CALIBRATED_SHARE = 0.70
MIN_STATION_EVAL_N = 15


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/pmw.duckdb")
    ap.add_argument("--out", default=os.path.expanduser("~/pmw-e2"))
    ap.add_argument("--write", action="store_true", help="write quantiles if VALID")
    args = ap.parse_args()

    con = db.init_db(db.connect(args.db))
    pairs, issue_by_key, stats = load_pairs(con)
    print(f"pares: {len(pairs)} · {stats}", flush=True)

    # The training window depends only on (target_date, lead), so shifts and the
    # shrinkage factor are computed once per window, not once per station-day.
    windows = sorted({(p.target_date, p.lead_h) for p in pairs})
    per_pair: dict[tuple, dict] = {}
    diag_by_window: dict[str, dict] = {}
    scopes: Counter = Counter()

    for target, lead in windows:
        end = datetime(target.year, target.month, target.day, 12, tzinfo=timezone.utc)
        t = end - timedelta(hours=lead)
        train = em.training_pairs(pairs, t, lead)
        q = em.fit((p.error_c for p in train), em.SCOPE_POOLED)
        if not q.values:
            scopes["INSUFFICIENT"] += 1
            continue
        shifts, diag = em.station_shifts(train, rng=random.Random(em.BOOTSTRAP_SEED))
        diag_by_window[f"{target.isoformat()}|{lead}"] = diag
        for p in pairs:
            if p.target_date != target or p.lead_h != lead:
                continue
            shift = shifts.get(p.station)
            scope = em.SHIFT_STATION if shift is not None else em.SHIFT_NONE
            scopes[scope] += 1
            per_pair[(p.station, p.target_date, p.lead_h)] = {
                "q": q, "shift": shift or 0.0, "scope": scope,
            }

    print(f"ámbitos de desplazamiento: {dict(scopes)}", flush=True)
    ws = [d["w"] for d in diag_by_window.values() if d.get("w")]
    if ws:
        print(f"  w estimado por ventana: min {min(ws):.3f} · medio {sum(ws)/len(ws):.3f} "
              f"· max {max(ws):.3f}", flush=True)

    # ---- v3 §4: acceptance, OUT OF SAMPLE (each pair against the quantiles
    # written for it, which were estimated without it)
    by_station: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    agg = {lead: [0, 0, 0] for lead in LEADS}
    mae = {lead: [0.0, 0] for lead in LEADS}
    for p in pairs:
        rec = per_pair.get((p.station, p.target_date, p.lead_h))
        if rec is None:
            continue
        fq = em.forecast_quantiles_v3(p.forecast_c, rec["q"], rec["shift"])
        y = p.observed_c
        r = by_station[p.station]
        r[2] += 1
        if y < fq[10]:
            r[0] += 1
        if y < fq[90]:
            r[1] += 1
        a = agg[p.lead_h]
        a[2] += 1
        if y < fq[10]:
            a[0] += 1
        if y < fq[90]:
            a[1] += 1
        mae[p.lead_h][0] += abs(p.error_c)
        mae[p.lead_h][1] += 1

    lo10, hi10 = em.CALIBRATION_P10_RANGE
    lo90, hi90 = em.CALIBRATION_P90_RANGE
    evaluable = {s: r for s, r in by_station.items() if r[2] >= MIN_STATION_EVAL_N}
    ok_stations = [
        s for s, (a, b, c) in evaluable.items()
        if lo10 <= a / c <= hi10 and lo90 <= b / c <= hi90
    ]
    share = len(ok_stations) / len(evaluable) if evaluable else 0.0

    agg_ok = all(
        lo10 <= a / c <= hi10 and lo90 <= b / c <= hi90
        for a, b, c in agg.values() if c
    )
    maes = {k: (v[0] / v[1] if v[1] else None) for k, v in mae.items()}
    mono_ok = (maes.get(24) or 0) >= (maes.get(9) or 0)

    print(f"\n=== §4.1 calibración POR ESTACIÓN (fuera de muestra) ===")
    print(f"  estaciones evaluables (n>={MIN_STATION_EVAL_N}): {len(evaluable)}")
    print(f"  calibradas: {len(ok_stations)} → {share:.1%} "
          f"(umbral {MIN_CALIBRATED_SHARE:.0%})  "
          f"{'PASA' if share >= MIN_CALIBRATED_SHARE else '*** FALLA ***'}")
    for lead, (a, b, c) in agg.items():
        if c:
            print(f"  agregado lead {lead:2}h: bajo p10 {a/c:.3f} · bajo p90 {b/c:.3f} · n={c}")
    print(f"  MAE 9h {maes.get(9)} · 24h {maes.get(24)} · monotonía {'ok' if mono_ok else 'FALLA'}")

    peores = sorted(
        ((s, a / c, b / c, c) for s, (a, b, c) in evaluable.items()),
        key=lambda x: -abs(x[1] - 0.10),
    )[:6]
    print("  peores estaciones:")
    for s, a, b, c in peores:
        print(f"    {s}: bajo p10 {a:.2f} · bajo p90 {b:.2f} · n={c}")

    valid = share >= MIN_CALIBRATED_SHARE and agg_ok and mono_ok
    print(f"\nVEREDICTO v3: {'VALIDO' if valid else 'NO VALIDO'}", flush=True)

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "M2_V3_ACCEPTANCE.json"), "w") as fh:
        json.dump({
            "prereg_version": "v3", "prereg_sha256": PREREG_SHA,
            "n_pairs": len(pairs), "scopes": dict(scopes),
            "share_calibrated": share, "n_evaluable": len(evaluable),
            "n_calibrated": len(ok_stations), "aggregate": {str(k): v for k, v in agg.items()},
            "mae": {str(k): v for k, v in maes.items()},
            "w_by_window": diag_by_window, "verdict": "VALIDO" if valid else "NO_VALIDO",
        }, fh, indent=1, default=str)

    if valid and args.write:
        con.execute(
            """UPDATE weather_forecasts SET forecast_p10=NULL, forecast_p25=NULL,
               forecast_p50=NULL, forecast_p75=NULL, forecast_p90=NULL
               WHERE dataset_version = ?""", [DATASET_VERSION])
        written = 0
        for (station, target, lead), rec in per_pair.items():
            issue = issue_by_key.get((station, target, lead))
            if issue is None:
                continue
            rows = db.query(
                con,
                """SELECT issue_time, forecast_tmax FROM weather_forecasts
                   WHERE station=? AND target_date=? AND issue_time=? AND dataset_version=?""",
                [station, target.isoformat(), issue, DATASET_VERSION])
            for r in rows:
                fq = em.forecast_quantiles_v3(
                    float(r["forecast_tmax"]), rec["q"], rec["shift"])
                con.execute(
                    """UPDATE weather_forecasts SET forecast_p10=?, forecast_p25=?,
                       forecast_p50=?, forecast_p75=?, forecast_p90=?
                       WHERE station=? AND target_date=? AND issue_time=? AND dataset_version=?""",
                    [fq[10], fq[25], fq[50], fq[75], fq[90], station,
                     target.isoformat(), r["issue_time"], DATASET_VERSION])
                written += 1
        print(f"cuantiles escritos: {written}", flush=True)
    elif not valid:
        print("NO se escriben cuantiles: v3 no pasa §4. Ver PREREG v3 §4 — si falla (1), "
              "M2 no soporta calibración por estación con este sustrato, y eso se publica "
              "tal cual en vez de forzarlo.", flush=True)

    con.close()
    return 0 if valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
