"""Reproduccion de la definicion de B, y desglose de CADA regla por separado."""
import csv, datetime as dt, io, os, sys, tarfile
from collections import Counter, defaultdict
from zoneinfo import ZoneInfo
sys.path.insert(0, "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-main/src")
from weather_agent import stations, weather, observations as obs
TB = os.path.expanduser("~/.claude/jobs/324ffe40/tmp/wt-research/evidence/B-133/raw_iem_55_estaciones.tgz")
PEAK = set(weather.PEAK_LOCAL_HOURS)

def cargar(suf):
    out = {}
    with tarfile.open(TB) as t:
        for nombre in sorted(n for n in t.getnames() if n.endswith(suf)):
            icao = os.path.basename(nombre).split("_")[0]
            try: tz = ZoneInfo(stations.timezone_of(icao))
            except Exception: continue
            d = defaultdict(list)
            for r in csv.DictReader(io.StringIO(t.extractfile(nombre).read().decode())):
                try: f = float(r["tmpf"])
                except (TypeError, ValueError): continue
                loc = dt.datetime.strptime(r["valid"], "%Y-%m-%d %H:%M").replace(
                    tzinfo=dt.timezone.utc).astimezone(tz)
                d[loc.date()].append((loc, f))
            out[icao] = d
    return out

def medir(datos, cobertura, rejilla, estricto):
    tot = arg0 = strict = 0
    mins = Counter(); ests = set(); eglc = [0, 0]
    for icao, dias in datos.items():
        serie, unidad, res = obs.station_series(icao)
        for d, vals in dias.items():
            if cobertura and not PEAK <= {loc.hour for loc, _ in vals}:
                continue
            tot += 1
            def v(f):
                c = (f - 32.0) * 5.0 / 9.0
                if not rejilla: return c
                raw = f if unidad == "F" else c
                return round(raw / res) * res
            punt = [(loc, v(f)) for loc, f in vals]
            mx = max(p for _, p in punt)
            h0 = [p for loc, p in punt if loc.hour == 0]
            resto = [p for loc, p in punt if loc.hour != 0]
            if h0 and max(h0) == mx:
                arg0 += 1
                if icao == "EGLC": eglc[0] += 1
                if (not resto) or max(h0) > max(resto):
                    strict += 1; ests.add(icao)
                    mins[max((loc for loc, p in punt if p == mx and loc.hour == 0)).minute] += 1
                    if icao == "EGLC": eglc[1] += 1
    return tot, arg0, strict, len(ests), dict(sorted(mins.items())), eglc

d3, d34 = cargar("_rt3.csv"), cargar("_rt34.csv")
print(f"{'definicion':46s} {'dias':>6s} {'argmax h0':>10s} {'ESTRICTO':>9s} {'est':>4s}  EGLC(arg/str)")
for nom, cob, rej in (("mia original (sin cobertura, sin rejilla)", False, False),
                      ("+ cobertura (PEAK_LOCAL_HOURS 11-18)", True, False),
                      ("+ rejilla de la estacion", True, True)):
    for etq, datos in (("tipo3", d3), ("3+4  ", d34)):
        tot, a0, s, ne, mn, eg = medir(datos, cob, rej, True)
        print(f"  {etq} {nom:40s} {tot:6d} {a0:10d} {s:9d} {ne:4d}   {eg[0]}/{eg[1]}")
tot, a0, s, ne, mn, eg = medir(d34, True, True, True)
print("\nminuto de los ESTRICTOS (3+4, definicion completa):", mn)
