"""B-134: which series settles the C markets? Full (3+4) against type 3, against the settled closed band.
Reads pmw.duckdb read-only and the raw B-133 downloads (evidence/B-133/raw_iem_55_estaciones.tgz, unpacked into ./raw)."""
import duckdb, csv, re, sys, json, collections, datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo
SRC = sys.argv[1] if len(sys.argv) > 1 else "src"
sys.path.insert(0, SRC)
from weather_agent import stations, weather, observations as obs_mod
from weather_agent.polymarket.resolution import parse_band
DB = sys.argv[2] if len(sys.argv) > 2 else "data/pmw.duckdb"
RAW = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("raw")
RES = json.load(open(sys.argv[4])) if len(sys.argv) > 4 else json.load(open("resumen.json"))
con = duckdb.connect(DB, read_only=True); con.execute("SET TimeZone='UTC'")
MESES = {m: i for i, m in enumerate(["January","February","March","April","May","June","July","August","September","October","November","December"], 1)}
def maximos(icao, clave, tz):
    por = collections.defaultdict(list)
    for r in csv.DictReader(open(RAW / f"{icao}_{clave}.csv")):
        if r["tmpf"] in ("", "M", "T"): continue
        t = dt.datetime.strptime(r["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc)
        por[t.astimezone(tz).date()].append((t, float(r["tmpf"])))
    return {d: round(obs_mod.f_to_c(max(f for _, f in rows))) for d, rows in por.items()
            if not set(weather.PEAK_LOCAL_HOURS) - {t.astimezone(tz).hour for t, _ in rows}}
filas = con.execute("""SELECT m.station_identifier, m.resolution_source, m.question, o.band_label
                       FROM markets m JOIN outcomes o ON o.market_id=m.market_id
                       WHERE m.unit='C' AND o.outcome_label='Yes' AND lower(m.winning_outcome)='yes'
                         AND m.station_identifier IS NOT NULL""").fetchall()
agg = collections.defaultdict(collections.Counter); cache = {}
for icao, src, q, band in filas:
    if icao not in RES or "error" in RES[icao] or RES[icao]["unit"] != "C": continue
    lo, hi = parse_band(band, "C")
    if lo is None or hi is None or lo != hi: continue
    m = re.search(r"on ([A-Z][a-z]+) (\d{1,2})\b", q or "")
    if not m or m.group(1) not in MESES: continue
    d = dt.date(2026, MESES[m.group(1)], int(m.group(2)))
    if not (dt.date(2026, 4, 9) <= d <= dt.date(2026, 9, 5)): continue
    tz = ZoneInfo(stations.timezone_of(icao))
    if icao not in cache: cache[icao] = (maximos(icao, "rt3", tz), maximos(icao, "rt34", tz))
    m3, m34 = cache[icao]
    if d not in m34 or d not in m3: continue
    host = re.sub(r"^https?://(www\.)?", "", src or "").split("/")[0]
    f = "WU" if "wunderground" in host else ("NOAA" if "weather.gov" in host else host or "?")
    c = agg[f]; dif = m3[d] != m34[d]
    c["dias"] += 1; c["completa"] += m34[d] == lo; c["tipo3"] += m3[d] == lo; c["difieren"] += dif
    c["dif_completa"] += dif and m34[d] == lo; c["dif_tipo3"] += dif and m3[d] == lo
for f, c in agg.items(): print(f, dict(c))
