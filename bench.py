import json, urllib.request, ssl, certifi, csv, io, re, time
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo
CTX=ssl.create_default_context(cafile=certifi.where()); UA={"User-Agent":"Mozilla/5.0"}
S=json.load(open("MODELSEL_SAMPLE.json")); TZ=json.load(open("STATIONS_TZ.json"))
MODELS=["ecmwf_ifs025","gfs_seamless","icon_seamless","ukmo_global_deterministic_10km","jma_gsm"]
BODY=re.compile(r'\s(M?\d{2})/(M?\d{2})\s'); num=lambda s: -int(s[1:]) if s.startswith('M') else int(s)
def GET(u,t=70):
    for a in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=t,context=CTX) as r: return r.read()
        except Exception:
            if a==3: raise
            time.sleep(1.2*(a+1))
# ---------- Y desde IEM ----------
Y={}
sts=sorted({e["icao"] for e in S})
for st in sts:
    ds=sorted(e["target_date"] for e in S if e["icao"]==st)
    d0=date.fromisoformat(ds[0])-timedelta(days=2); d1=date.fromisoformat(ds[-1])+timedelta(days=2)
    st_iem = st[1:] if st.startswith("K") else st
    u=(f"https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station={st_iem}&data=metar"
       f"&year1={d0.year}&month1={d0.month}&day1={d0.day}&year2={d1.year}&month2={d1.month}&day2={d1.day}"
       f"&tz=UTC&format=onlycomma&latlon=no&report_type=3&report_type=4")
    obs=[]
    for x in csv.DictReader(io.StringIO(GET(u,180).decode())):
        try: t=datetime.strptime(x["valid"],"%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except: continue
        b=BODY.search(x.get("metar") or "")
        if b: obs.append((t,num(b.group(1))))
    Y[st]=obs; print(f"  IEM {st}: {len(obs)} obs",flush=True)
# ---------- f desde Single Runs ----------
LEADS={1:"A",6:"A",9:"B",24:"C"}
cells={}; rows=[]
cache={}
for i,e in enumerate(S):
    td=date.fromisoformat(e["target_date"]); Z=ZoneInfo(e["tz"])
    ws=datetime(td.year,td.month,td.day,tzinfo=Z); we=ws+timedelta(days=1)
    yv=[v for t,v in Y[e["icao"]] if ws<=t<we]
    y=max(yv) if yv else None
    runs={"A":datetime(td.year,td.month,td.day,6,tzinfo=timezone.utc),
          "B":datetime(td.year,td.month,td.day,0,tzinfo=timezone.utc),
          "C":datetime(td.year,td.month,td.day,tzinfo=timezone.utc)-timedelta(hours=12)}
    # coordenadas de estación desde IEM no disponibles aquí -> usar las del catálogo via TZ file si existen
    lat,lon = e.get("lat"), e.get("lon")
    for m in MODELS:
        fc={}
        for tag,rt in runs.items():
            key=(m,e["icao"],rt.isoformat())
            if key not in cache:
                u=(f"https://single-runs-api.open-meteo.com/v1/forecast?latitude={e['req_lat']}&longitude={e['req_lon']}"
                   f"&hourly=temperature_2m&models={m}&run={rt.strftime('%Y-%m-%dT%H:%M')}&timezone=UTC")
                d=None
                try: d=json.loads(GET(u))
                except Exception as ex: cache[key]=None
                if d is None or d.get("error"): cache[key]=None
                else:
                    cells[(m,e["icao"])]=(d["latitude"],d["longitude"],d.get("elevation"))
                    h=d["hourly"]; cache[key]=[(datetime.fromisoformat(t+"+00:00"),v) for t,v in zip(h["time"],h["temperature_2m"])]
            ser=cache[key]
            fc[tag]= max([v for t,v in ser if ws<=t<we and v is not None], default=None) if ser else None
        for lead,tag in LEADS.items():
            rows.append(dict(event_id=e["event_id"],icao=e["icao"],city=e["city"],tz=e["tz"],
                             target_date=e["target_date"],model=m,lead=lead,run_tag=tag,
                             run=runs[tag].strftime("%Y-%m-%dT%H:%MZ"),f=fc[tag],y=y))
    if (i+1)%6==0: print(f"  eventos {i+1}/{len(S)}",flush=True)
json.dump(rows,open("BENCH_RAW.json","w"),indent=1)
json.dump({f"{k[0]}|{k[1]}":v for k,v in cells.items()},open("BENCH_CELLS.json","w"),indent=1)
print("filas:",len(rows))
