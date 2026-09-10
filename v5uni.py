import json, urllib.request, ssl, certifi, time, os
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
CTX=ssl.create_default_context(cafile=certifi.where()); UA={"User-Agent":"Mozilla/5.0"}
UNI=json.load(open('V5_UNIVERSE_STATIONS.json'))
V3={e['icao']:(e['req_lat'],e['req_lon'],e['tz']) for e in json.load(open('MODELSEL_GEOVAL_V3_SAMPLE.json'))}
SNAP={x['icao']:(x['lat'],x['lon']) for x in json.load(open('STATION_COORDS_SNAPSHOT_v1.json'))['stations']}
class QuotaExceeded(Exception): pass
def GET(u,t=90):
    for a in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=t,context=CTX) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code==400: return {"_out":True}
            if e.code==429: raise QuotaExceeded(e.read().decode()[:200])
            if a==3: return None
        except Exception:
            if a==3: return None
        time.sleep(1.5*(a+1))
def tz_of(lat,lon):
    d=GET(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
          f"&hourly=temperature_2m&forecast_days=1&timezone=auto")
    return d.get("timezone") if d and not d.get("_out") else None
def sr(model,lat,lon,run):
    d=GET(f"https://single-runs-api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
          f"&hourly=temperature_2m&models={model}&run={run}&timezone=UTC")
    if d is None: return {"status":"error"}
    if d.get("_out"): return {"status":"out_of_domain"}
    if d.get("error"): return {"status":"api_error"}
    h=d["hourly"]
    return {"status":"ok","lat":round(d["latitude"],5),"lon":round(d["longitude"],5),
            "series":{t:v for t,v in zip(h["time"],h["temperature_2m"])}}
CASES=[("2026-06-02T18:00","2026-06-03"),("2026-08-14T18:00","2026-08-15")]
ROWS=json.load(open('V5_UNIVERSE_COMPONENTS.json')) if os.path.exists('V5_UNIVERSE_COMPONENTS.json') else []
DONE={r['icao'] for r in ROWS}
print(f"reanudando universo: {len(DONE)}/{len(UNI)}",flush=True)
def save(): json.dump(ROWS,open('V5_UNIVERSE_COMPONENTS.json','w'),indent=1)
try:
    for u in UNI:
        st=u['icao']
        if st in DONE: continue
        # D1: coordenadas canónicas del snapshot; tz de V3 si existe, si no de la API
        la,lo=SNAP[st]; src="STATION_COORDS_SNAPSHOT_v1"
        tz=V3[st][2] if st in V3 else tz_of(la,lo)
        if tz is None:
            ROWS.append(dict(icao=st,city=u['city'],component="UNKNOWN",motivo="tz_no_resoluble",
                             n_markets=u['n_markets'],n_events=u['n_events'],coord_src=src))
            save(); continue
        Z=ZoneInfo(tz); per={}
        for run,td_s in CASES:
            td=date.fromisoformat(td_s)
            ws=datetime(td.year,td.month,td.day,tzinfo=Z); we=ws+timedelta(days=1)
            ref=sr("icon_seamless",la,lo,run)
            if ref["status"]!="ok": per[run]="UNKNOWN"; continue
            W=[t for t,v in ref["series"].items()
               if v is not None and ws<=datetime.fromisoformat(t+"+00:00")<we]
            if not W: per[run]="UNKNOWN"; continue
            hits=[]
            for m in ("icon_d2","icon_eu","icon_global"):
                d=sr(m,la,lo,run)
                if d["status"]!="ok" or (d["lat"],d["lon"])!=(ref["lat"],ref["lon"]): continue
                if all(d["series"].get(t) is not None and d["series"][t]==ref["series"][t] for t in W):
                    hits.append(m)
            per[run]=hits[0] if len(hits)==1 else "UNKNOWN"
        cs=set(per.values())
        ROWS.append(dict(icao=st,city=u['city'],lat=la,lon=lo,tz=tz,coord_src=src,
                         n_markets=u['n_markets'],n_events=u['n_events'],per_run=per,
                         component=(list(cs)[0] if len(cs)==1 else "INESTABLE")))
        save(); print(f"  {st:<6}{str(u['city'])[:18]:<20}{ROWS[-1]['component']}",flush=True)
except QuotaExceeded as e:
    save(); print(f"CUOTA_AGOTADA tras {len(ROWS)}/{len(UNI)} estaciones -> {e}",flush=True); raise SystemExit(3)
save(); print("LISTO_UNI n=",len(ROWS))
