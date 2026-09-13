"""Sizing of the REPORT_TYPE=3 defect across the station registry (B-131 follow-up).

For each station: IEM asos.py over 2026-04-09..2026-09-05, report_type=3 and report_type=3+4.
Sequential, 2 s pause, NO retries, STOP at the first HTTP 429. Read-only: writes nothing to the repo.
"""
import csv, io, json, sys, time, collections, urllib.request, urllib.error, urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0, "/Users/mariaaleu/.claude/jobs/43deec01/tmp/wt-nf/src")
from weather_agent import stations, observations as obs_mod, weather

OUT = Path(__file__).resolve().parent
URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
Y1, Y2 = ("2026", "4", "9"), ("2026", "9", "6")   # day2 exclusive when it differs

class HTTP429(Exception):
    pass

def fetch(icao, tipos):
    import subprocess
    q = [("station", icao), ("data", "tmpf"), ("year1", Y1[0]), ("month1", Y1[1]), ("day1", Y1[2]),
         ("year2", Y2[0]), ("month2", Y2[1]), ("day2", Y2[2]), ("tz", "Etc/UTC"), ("format", "onlycomma"),
         ("latlon", "no"), ("missing", "M"), ("trace", "T"), ("direct", "no")] + [("report_type", t) for t in tipos]
    url = f"{URL}?{urllib.parse.urlencode(q)}"
    tmp = OUT / "raw" / "_cuerpo.tmp"
    r = subprocess.run(["curl", "-s", "-o", str(tmp), "-w", "%{http_code}", "--max-time", "180",
                        "-A", "pmw-agent/sizing-b131", url], capture_output=True, text=True)
    code = r.stdout.strip()
    if code == "429":
        raise HTTP429(icao)
    if code != "200":
        raise RuntimeError(f"HTTP {code or 'sin respuesta'} (curl rc={r.returncode})")
    return tmp.read_text(errors="replace")

def filas(body):
    out = []
    for r in csv.DictReader(io.StringIO(body)):
        if r.get("tmpf") in (None, "", "M", "T"): continue
        t = datetime.strptime(r["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        out.append((t, float(r["tmpf"])))
    return out

def on_grid(unit, res, f):
    raw = f if unit == "F" else obs_mod.f_to_c(f)
    return abs(raw - round(raw / res) * res) < 1e-4

resumen = {}
icaos = stations.all_icaos()
print(f"{len(icaos)} estaciones", flush=True)
for i, icao in enumerate(icaos, 1):
    tz = ZoneInfo(stations.timezone_of(icao)); series, unit, res = obs_mod.station_series(icao)
    cuerpos = {}
    try:
        for clave, tipos in (("rt3", ["3"]), ("rt34", ["3", "4"])):
            cuerpos[clave] = fetch(icao, tipos); time.sleep(2)
    except HTTP429:
        print(f"HTTP 429 en {icao}: PARO sin reintentar", flush=True); resumen["_parado_429_en"] = icao; break
    except Exception as e:
        resumen[icao] = {"error": repr(e)[:200]}; print(f"{icao}: {e!r}", flush=True); continue
    for k, b in cuerpos.items(): (OUT / "raw" / f"{icao}_{k}.csv").write_text(b)
    a, b = filas(cuerpos["rt3"]), filas(cuerpos["rt34"])
    ca, cb = collections.Counter(a), collections.Counter(b)
    extra = list((cb - ca).elements())
    faltan_en_34 = sum((ca - cb).values())
    def por_dia(rows):
        d = collections.defaultdict(list)
        for t, f in rows: d[t.astimezone(tz).date()].append((t, f))
        return d
    da, db = por_dia(a), por_dia(b)
    cambios, deltas, max_offgrid = 0, collections.Counter(), 0
    dias_etiquetables = 0
    for dia, rows in da.items():
        horas = {t.astimezone(tz).hour for t, _ in rows}
        if set(weather.PEAK_LOCAL_HOURS) - horas: continue       # daily_high la rechazaria hoy
        dias_etiquetables += 1
        ma = max(f for _, f in rows); mb = max(f for _, f in db.get(dia, rows))
        conv = (lambda f: f) if unit == "F" else obs_mod.f_to_c
        if round(conv(mb) / res) * res != round(conv(ma) / res) * res:
            cambios += 1; deltas[round((conv(mb) - conv(ma)) / res) * res] += 1
            if not on_grid(unit, res, mb): max_offgrid += 1
    resumen[icao] = {
        "series": series, "unit": unit, "res": res,
        "n_rt3": len(a), "n_rt34": len(b), "extra_en_34": len(extra), "rt3_no_en_34": faltan_en_34,
        "frac_descartada": round(len(extra) / len(b), 4) if b else None,
        "minutos_rt3": collections.Counter(t.minute for t, _ in a).most_common(3),
        "minutos_extra": collections.Counter(t.minute for t, _ in extra).most_common(3),
        "extra_fuera_rejilla": sum(not on_grid(unit, res, f) for _, f in extra),
        "dias_etiquetables": dias_etiquetables, "dias_cambian": cambios,
        "deltas": {str(k): v for k, v in sorted(deltas.items())}, "max_nuevo_fuera_rejilla": max_offgrid,
    }
    r = resumen[icao]
    print(f"[{i}/{len(icaos)}] {icao} {unit} n3={r['n_rt3']} n34={r['n_rt34']} descartada={r['frac_descartada']} "
          f"dias={r['dias_etiquetables']} cambian={r['dias_cambian']} deltas={r['deltas']} fuera_rejilla_extra={r['extra_fuera_rejilla']}", flush=True)
    (OUT / "resumen.json").write_text(json.dumps(resumen, indent=1, default=str))
(OUT / "resumen.json").write_text(json.dumps(resumen, indent=1, default=str))
print("FIN", flush=True)
