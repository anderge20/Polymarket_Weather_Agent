#!/usr/bin/env python3
"""
label_bias_pnl.py — what the observation-derived label would have cost, in money
================================================================================

DIAGNOSTIC, NOT A DECISION METRIC. `PREREG_R21_ENMIENDA_A §A.5` froze the
settlement label as the venue's `winning_outcome`, and this script does not
replace it. It answers one question session A asked and that a rate cannot
answer: if R14's route — labelling from IEM observations — had settled the very
same trades, how much would the PnL have differed?

A rate of 6.8 % says how often the two labels disagree. It does not say whether
the disagreements land on trades that were taken, or on which side. Those are
different questions and only the second one has a number the user can act on.

The IEM label is computed for EVERY trade, not only for the 410 events whose
winning band the substrate happens to hold: given the observed daily high in the
market's own unit, "is it inside [lo, hi]" is answerable for any band.

Usage:
    python3 scripts/label_bias_pnl.py --db data/pmw.duckdb --trades ~/pmw-e2/R21_BACKTEST.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import date
from statistics import median
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from weather_agent import costs, database as db, stations  # noqa: E402


def observed_by_station_day(con) -> dict:
    """(station, LOCAL day) -> (unit, value) of the day's highest reading.

    The local day, never `CAST(observation_time AS DATE)`: that made M2 v1's
    sample size depend on the DuckDB session TimeZone, 2 599 rows against 1 881.
    """
    out: dict = {}
    for r in db.query(con, """SELECT station, observation_time, observed_unit,
                                     observed_value, tmax_observed
                              FROM weather_observations"""):
        try:
            tz = ZoneInfo(stations.timezone_of(r["station"]))
        except Exception:
            continue
        key = (r["station"], r["observation_time"].astimezone(tz).date())
        cand = (r["observed_unit"], float(r["observed_value"]), float(r["tmax_observed"]))
        prev = out.get(key)
        if prev is None or cand[2] > prev[2]:
            out[key] = cand
    return out


def in_unit(rec, unit: str) -> float:
    u0, v0, c0 = rec
    if u0 == unit:
        return v0
    if unit == "F":
        return c0 * 9.0 / 5.0 + 32.0
    return (v0 - 32.0) * 5.0 / 9.0 if u0 == "F" else c0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/pmw.duckdb")
    ap.add_argument("--trades", default=os.path.expanduser("~/pmw-e2/R21_BACKTEST.json"))
    ap.add_argument("--out", default=os.path.expanduser("~/pmw-e2"))
    args = ap.parse_args()

    trades = json.load(open(args.trades))["operaciones"]
    if not trades:
        print("SIN OPERACIONES: no hay PnL cuyo sesgo acotar.", flush=True)
        return 0

    con = db.init_db(db.connect(args.db))
    obs = observed_by_station_day(con)
    bands = {r["market_id"]: (r["lo"], r["hi"], r["unit"]) for r in db.query(
        con, """SELECT o.market_id, o.lo, o.hi, m.unit FROM outcomes o
                JOIN markets m ON m.market_id = o.market_id
                WHERE o.outcome_label = 'Yes'""")}

    rows, missing = [], 0
    for t in trades:
        b = bands.get(t["market_id"])
        rec = obs.get((t["estacion"], date.fromisoformat(t["fecha"])))
        if b is None or rec is None:
            missing += 1
            continue
        lo, hi, unit = b
        y = in_unit(rec, unit)
        won_iem = ((lo is None or y >= float(lo) - 1e-9)
                   and (hi is None or y <= float(hi) + 1e-9))
        # The fee is recovered exactly from the identity the trade was written
        # with: pnl = (won ? 1 : 0) - p_exec - fee. Reconstructing it beats
        # re-reading the schedule, because it guarantees the two labels are
        # compared at the SAME cost — any difference is then the label alone.
        fee = (1.0 if t["gano"] else 0.0) - t["p_exec"] - t["pnl"]
        pnl_iem = costs.realised_pnl(won=won_iem, p_exec=t["p_exec"], fee=fee)
        rows.append({**t, "gano_iem": won_iem, "pnl_iem": pnl_iem,
                     "observado": y, "lo": lo, "hi": hi})

    dis = [r for r in rows if r["gano_iem"] != r["gano"]]
    pv = [r["pnl"] for r in rows]
    pi = [r["pnl_iem"] for r in rows]
    res = {
        "n_operaciones": len(rows), "sin_observacion": missing,
        "n_etiquetas_discrepantes": len(dis),
        "tasa_discrepancia": (len(dis) / len(rows)) if rows else None,
        "mediana_pnl_venue": median(pv) if pv else None,
        "mediana_pnl_iem": median(pi) if pi else None,
        "total_pnl_venue": sum(pv), "total_pnl_iem": sum(pi),
        "diferencia_total": sum(pi) - sum(pv),
        "diferencia_por_operacion": ((sum(pi) - sum(pv)) / len(rows)) if rows else None,
        "direccion": dict(Counter(
            "IEM_dice_gana_venue_dice_pierde" if r["gano_iem"] else
            "IEM_dice_pierde_venue_dice_gana" for r in dis)),
        "discrepancias_por_estacion": dict(Counter(r["estacion"] for r in dis).most_common()),
    }
    print(json.dumps(res, indent=1, default=str), flush=True)
    with open(os.path.join(args.out, "R21_LABEL_BIAS_PNL.json"), "w") as fh:
        json.dump({"resumen": res, "discrepantes": dis}, fh, indent=1, default=str)
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
