#!/usr/bin/env python3
"""R30 §5.5 — construye el sustrato (p_mid, desenlace, evento, estacion, fecha).

Reutiliza EXACTAMENTE la via de scripts/run_r22.py: las mismas `candidates` bajo
disciplina as-of, el mismo DATASET_VERSION. No re-define nada: si el sustrato de
R30 no fuera el de R22, las cifras de R22 citadas en la Enmienda H no aplicarian.
"""
import json, os, sys
sys.path.insert(0, "src"); sys.path.insert(0, "scripts")
from weather_agent import database as db, backtest
import importlib.util
spec = importlib.util.spec_from_file_location("run_r22", "scripts/run_r22.py")
r22 = importlib.util.module_from_spec(spec); spec.loader.exec_module(r22)

OUT = os.path.expanduser("~/pmw-e2/R30_ROWS.json")
con = db.init_db(db.connect("data/pmw.duckdb"))
days = [r["d"] for r in db.query(
    con, """SELECT DISTINCT CAST(end_date AS DATE) d FROM markets
            WHERE dataset_version = ? AND end_date IS NOT NULL
              AND uma_resolution_status = 'resolved' ORDER BY 1""",
    [r22.DATASET_VERSION])]
print(f"dataset={r22.DATASET_VERSION}  dias resueltos={len(days)}", flush=True)

cands = backtest.candidates(con, days, dataset_version=r22.DATASET_VERSION, counters={})
meta = {r["market_id"]: r for r in db.query(
    con, """SELECT m.market_id, m.event_id, m.discovered_at,
                   count(*) OVER (PARTITION BY m.event_id) AS event_bands
            FROM markets m WHERE m.dataset_version = ?""", [r22.DATASET_VERSION])}
rows = []
for c in cands:
    m = meta.get(c.market_id)
    if m is None:
        continue
    rows.append({
        "event_id": m["event_id"], "station": c.station, "lead_h": c.lead_h,
        "unit": c.unit, "p_mid": c.p_mid, "won": c.won,
        "target_date": str(c.target_date),
        "band_pos": backtest.band_position(c.q_market, c.lo, c.hi),
        "spread_fc": c.q_market[90] - c.q_market[10],
        "event_bands": m["event_bands"],
    })
print(f"filas {len(rows)}  eventos {len({r['event_id'] for r in rows})}", flush=True)
json.dump(rows, open(OUT, "w"))
print(f"escrito {OUT}", flush=True)
con.close()
