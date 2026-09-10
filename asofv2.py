import json, urllib.request, ssl, certifi, csv, io, re, time
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo
CTX=ssl.create_default_context(cafile=certifi.where()); UA={"User-Agent":"Mozilla/5.0"}
S=json.load(open("MODELSEL_ASOF_V2_SAMPLE.json"))
LMAX={"icon_seamless":4.76,"gfs_seamless":6.93,"ukmo_global_deterministic_10km":10.48,"ecmwf_ifs025":8.78}
LEADS=[1,6,9,24]; GRID=[-24,-18,-12,-6,0,6,12,18]
BODY=re.compile(r'\s(M?\d{2})/(M?\d{2})\s'); num=lambda s: -int(s[1:]) if s.startswith('M') else int(s)
def GET(u,t=90):
    for a in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=t,context=CTX) as r: return r.read()
        except Exception:
            if a==3: raise
            time.sleep(1.5*(a+1))
# ---- Y desde IEM ----
Y={}
for st in sorted({e['icao'] for e in S}):
    ds=sorted(e['target_date'] for e in S if e['icao']==st)
    d0=date.fromisoformat(ds[0])-timedelta(days=2); d1=date.fromisoformat(ds[-1])+timedelta(days=2)
    sid=st[1:] if st.startswith("K") else st
    u=(f"https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station={sid}&data=metar"
       f"&year1={d0.year}&month1={d0.month}&day1={d0.day}&year2={d1.year}&month2={d1.month}&day2={d1.day}"
       f"&tz=UTC&format=onlycomma&latlon=no&report_type=3&report_type=4")
    obs=[]
    for x in csv.DictReader(io.StringIO(GET(u,240).decode())):
        try: t=datetime.strptime(x["valid"],"%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except: continue
        b=BODY.search(x.get("metar") or "")
        if b: obs.append((t,num(b.group(1))))
    Y[st]=obs; print(f"  IEM {st}: {len(obs)}",flush=True)
# ---- f desde single-runs ----
cache={}; rows=[]
for i,e in enumerate(S):
    td=date.fromisoformat(e['target_date']); Z=ZoneInfo(e['tz'])
    ws=datetime(td.year,td.month,td.day,tzinfo=Z); we=ws+timedelta(days=1)
    yv=[v for t,v in Y[e['icao']] if ws<=t<we]; y=max(yv) if yv else None
    base=datetime(td.year,td.month,td.day,tzinfo=timezone.utc)
    for m,L in LMAX.items():
        for lead in LEADS:
            Th=12-lead
            cand=[g for g in GRID if g+L<=Th]
            if not cand:
                rows.append(dict(event_id=e['event_id'],icao=e['icao'],city=e['city'],tz=e['tz'],
                    target_date=e['target_date'],model=m,lead=lead,run=None,age_h=None,f=None,y=y)); continue
            g=max(cand); rt=base+timedelta(hours=g)
            key=(m,e['icao'],rt.isoformat())
            if key not in cache:
                u=(f"https://single-runs-api.open-meteo.com/v1/forecast?latitude={e['req_lat']}&longitude={e['req_lon']}"
                   f"&hourly=temperature_2m&models={m}&run={rt.strftime('%Y-%m-%dT%H:%M')}&timezone=UTC")
                d=None
                try: d=json.loads(GET(u))
                except Exception: pass
                if d is None or d.get("error"): cache[key]=None
                else:
                    h=d["hourly"]; cache[key]=(d["latitude"],d["longitude"],d.get("elevation"),
                        [(datetime.fromisoformat(t+"+00:00"),v) for t,v in zip(h["time"],h["temperature_2m"])])
            c=cache[key]
            f=max([v for t,v in c[3] if ws<=t<we and v is not None],default=None) if c else None
            rows.append(dict(event_id=e['event_id'],icao=e['icao'],city=e['city'],tz=e['tz'],
                target_date=e['target_date'],model=m,lead=lead,run=rt.strftime("%Y-%m-%dT%H:%MZ"),
                age_h=round(Th-g,2),f=f,y=y,
                cell_lat=c[0] if c else None,cell_lon=c[1] if c else None,cell_elev=c[2] if c else None))
    if (i+1)%20==0: print(f"  eventos {i+1}/{len(S)}",flush=True)
json.dump(rows,open("MODELSEL_ASOF_V2_RAW.json","w"),indent=1)
print("filas:",len(rows))
