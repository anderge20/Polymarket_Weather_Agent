#!/usr/bin/env python3
"""LEVEL 1 · L1.1 — FORECAST SKILL. Sólo medicion: ¿el pronostico tiene señal meteorologica?

NO entrena modelos, NO convierte nada en probabilidad, NO calcula edge ni PnL.
Ejecuta la §6 de `PREREG_LEVEL1.md`, espejado antes.

PAR VALIDO = (target_date, ejecucion) con `forecast_tmax` y `tmax_observed` presentes.
El error se mide en CELSIUS contra `tmax_observed`, NUNCA contra `observed_value`,
que es la rejilla del mercado (A-283).
"""
from __future__ import annotations

import datetime as dt
import math
import os
import statistics as stx
import sys
from collections import defaultdict

import duckdb

REPO = os.environ.get("PMW_REPO", "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-merge")
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, "/Users/mariaaleu/pmw-e2/fase2")
from weather_agent import stations                                        # noqa: E402
from n075_poblacion import DB                                             # noqa: E402
from zoneinfo import ZoneInfo                                             # noqa: E402

ST = "EGLC"
#: t_asof por lead, y la ejecucion que cada lead puede ver (medido en la preinscripcion §3)
LEAD_ISSUE = {24: 6, 9: 18}


def q(x, p):
    v = sorted(x)
    if not v:
        return float("nan")
    k = (len(v) - 1) * p
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    return v[lo] if lo == hi else v[lo] + (v[hi] - v[lo]) * (k - lo)


def resumen(e):
    if not e:
        return None
    a = [abs(x) for x in e]
    return {
        "n": len(e), "bias": stx.mean(e), "MAE": stx.mean(a),
        "RMSE": math.sqrt(stx.mean([x * x for x in e])),
        "MedAE": stx.median(a), "p10": q(e, .10), "p50": q(e, .50), "p90": q(e, .90),
        "min": min(e), "max": max(e), "sd": stx.pstdev(e),
    }


def linea(etq, r):
    if r is None:
        print(f"  {etq:26s}   (sin pares)"); return
    print(f"  {etq:26s} n={r['n']:4d}  bias {r['bias']:+6.2f}  MAE {r['MAE']:5.2f}  "
          f"RMSE {r['RMSE']:5.2f}  MedAE {r['MedAE']:5.2f}  "
          f"p10 {r['p10']:+6.2f}  p90 {r['p90']:+6.2f}  sd {r['sd']:5.2f}")


def main():
    con = duckdb.connect(DB, read_only=True)
    con.execute("SET TimeZone='UTC'")
    zona = ZoneInfo(stations.timezone_of(ST))

    obs = {}
    for t, v in con.execute(
            "SELECT observation_time, tmax_observed FROM weather_observations WHERE station = ?",
            [ST]).fetchall():
        d = t.astimezone(zona).date()
        if d not in obs or v > obs[d]:
            obs[d] = float(v)

    filas = con.execute(
        """SELECT target_date, issue_time, available_at, forecast_tmax,
                  forecast_p10, forecast_p90
           FROM weather_forecasts WHERE station = ? AND forecast_tmax IS NOT NULL
           ORDER BY target_date, issue_time""", [ST]).fetchall()

    pares = []
    for td, iss, av, f, p10, p90 in filas:
        if td not in obs:
            continue
        lead = next((l for l, h in LEAD_ISSUE.items() if iss.hour == h), None)
        pares.append({"td": td, "lead": lead, "issue_h": iss.hour, "f": float(f),
                      "o": obs[td], "e": obs[td] - float(f),
                      "p10": None if p10 is None else float(p10),
                      "p90": None if p90 is None else float(p90)})

    print("=" * 96)
    print("L1.1 — FORECAST SKILL · EGLC · error = tmax_observed (C) - forecast_tmax (C)")
    print("=" * 96)
    print(f"  filas de pronostico con forecast_tmax: {len(filas)}")
    print(f"  PARES VALIDOS (con observacion del dia): {len(pares)}")
    print(f"  dias objetivo distintos: {len({p['td'] for p in pares})}")
    print(f"  ejecuciones: {sorted({p['issue_h'] for p in pares})} UTC  ->  "
          f"lead 24 = 06z · lead 9 = 18z (preinscripcion §3)")

    print(f"\n{'-' * 96}\nGLOBAL Y POR LEAD\n{'-' * 96}")
    linea("todos", resumen([p["e"] for p in pares]))
    for lead in (24, 9):
        linea(f"lead {lead} h ({LEAD_ISSUE[lead]:02d}z)", resumen([p["e"] for p in pares if p["lead"] == lead]))

    print(f"\n{'-' * 96}\nPOR MES\n{'-' * 96}")
    por = defaultdict(list)
    for p in pares:
        por[(p["td"].strftime("%Y-%m"), p["lead"])].append(p["e"])
    for mes in sorted({k[0] for k in por}):
        for lead in (24, 9):
            linea(f"{mes} lead {lead}", resumen(por.get((mes, lead), [])))

    print(f"\n{'-' * 96}\nPOR RANGO DE TEMPERATURA OBSERVADA\n{'-' * 96}")
    cortes = [(-99, 15), (15, 20), (20, 25), (25, 30), (30, 99)]
    for lo, hi in cortes:
        sub = [p["e"] for p in pares if lo <= p["o"] < hi]
        linea(f"obs [{lo if lo > -99 else '-inf'}, {hi if hi < 99 else '+inf'})", resumen(sub))

    print(f"\n{'-' * 96}\nCOBERTURA Y ANCHURA p10-p90  (cuantiles DEL PROVEEDOR, no se usan como modelo)\n{'-' * 96}")
    for lead in (24, 9):
        s = [p for p in pares if p["lead"] == lead and p["p10"] is not None and p["p90"] is not None]
        if not s:
            continue
        dentro = sum(1 for p in s if p["p10"] <= p["o"] <= p["p90"])
        anch = [p["p90"] - p["p10"] for p in s]
        bajo = sum(1 for p in s if p["o"] < p["p10"])
        alto = sum(1 for p in s if p["o"] > p["p90"])
        print(f"  lead {lead:2d}  n={len(s):3d}  cobertura {100*dentro/len(s):5.1f} % "
              f"(nominal 80 %)   por debajo {bajo:3d}  por encima {alto:3d}   "
              f"anchura media {stx.mean(anch):5.2f} C  mediana {stx.median(anch):5.2f} C")

    print(f"\n{'-' * 96}\nESTABILIDAD DE LAS REVISIONES  06z -> 18z (mismo target_date)\n{'-' * 96}")
    porfecha = defaultdict(dict)
    for p in pares:
        porfecha[p["td"]][p["issue_h"]] = p
    ambas = [d for d, v in porfecha.items() if 6 in v and 18 in v]
    rev = [porfecha[d][18]["f"] - porfecha[d][6]["f"] for d in ambas]
    mejora = [abs(porfecha[d][6]["e"]) - abs(porfecha[d][18]["e"]) for d in ambas]
    print(f"  dias con las DOS ejecuciones: {len(ambas)}")
    linea("revision 18z - 06z", resumen(rev))
    linea("|e06| - |e18|  (>0 = mejora)", resumen(mejora))
    gana = sum(1 for m in mejora if m > 0); empata = sum(1 for m in mejora if m == 0)
    print(f"  la 18z acierta MAS en {gana} de {len(mejora)} dias · empata {empata} · "
          f"peor {len(mejora)-gana-empata}")
    print(f"  revision identica (18z == 06z) en {sum(1 for r in rev if r == 0)} dias")
    con.close()


if __name__ == "__main__":
    main()
