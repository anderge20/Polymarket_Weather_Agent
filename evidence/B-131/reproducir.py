"""B-131: reproduce the two key figures from the two IEM downloads saved alongside.

    python3 reproducir.py [path/to/LONDON_CANDIDATES.json]

1. report_type=3 drops EGLC's :20 METARs (minute count of each download).
2. Against the settled one-degree closed bands, the local-day max of the FULL series
   matches all days; the :50-only series (what REPORT_TYPE=3 yields) does not.
"""
import csv, json, sys, collections
from datetime import datetime, timezone, date
from pathlib import Path
from zoneinfo import ZoneInfo

AQUI = Path(__file__).resolve().parent
L = ZoneInfo("Europe/London")

def leer(nombre):
    out = []
    for r in csv.DictReader(open(AQUI / nombre)):
        if r["tmpf"] in ("", "M"):
            continue
        t = datetime.strptime(r["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        out.append((t, round((float(r["tmpf"]) - 32) * 5 / 9, 1)))
    return out

todo = leer("eglc_iem_rt3y4_2026-04-13_05-20.csv")
rt3 = leer("eglc_iem_rt3_2026-04-13_05-20.csv")
print("tipos 3+4  minutos:", collections.Counter(t.minute for t, _ in todo).most_common(3))
print("tipo 3     minutos:", collections.Counter(t.minute for t, _ in rt3).most_common(3))

def maximos(obs):
    m = {}
    for t, c in obs:
        d = t.astimezone(L).date()
        m[d] = max(m.get(d, -99), c)
    return m

completo, solo3 = maximos(todo), maximos(rt3)
cand_path = Path(sys.argv[1]) if len(sys.argv) > 1 else AQUI.parents[1] / "LONDON_CANDIDATES.json"
liquidado = {}
for r in json.load(open(cand_path)):
    if r["won"] and r["lo"] is not None and r["hi"] is not None:
        liquidado[date.fromisoformat(r["fecha"])] = r["lo"]
dias = [d for d in sorted(liquidado) if date(2026, 4, 13) <= d <= date(2026, 5, 19) and d in completo]
print(f"bandas cerradas liquidadas en rango: {len(dias)}")
print(f"  coincide max serie completa: {sum(completo[d] == liquidado[d] for d in dias)}")
print(f"  coincide max tipo 3 solo:    {sum(solo3.get(d) == liquidado[d] for d in dias)}")
for d in dias:
    if solo3.get(d) != liquidado[d]:
        print(f"    {d}  liquidado {liquidado[d]}  completo {completo[d]}  tipo3 {solo3.get(d)}")
