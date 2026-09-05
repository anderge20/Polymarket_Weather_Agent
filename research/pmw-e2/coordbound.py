import json, urllib.request, ssl, certifi, time, os
CTX=ssl.create_default_context(cafile=certifi.where()); UA={"User-Agent":"Mozilla/5.0"}
S=json.load(open('COORD_SENSITIVITY.json'))
class Quota(Exception): pass
def GET(u,t=60):
    for a in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=t,context=CTX) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code==400: return {"_out":True}
            if e.code==429: raise Quota("429")
            if a==3: return None
        except Exception:
            if a==3: return None
        time.sleep(1.2*(a+1))
def fc(model,lat,lon):
    d=GET(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
          f"&hourly=temperature_2m&forecast_days=2&models={model}&timezone=UTC")
    if d is None: return {"s":"err"}
    if d.get("_out"): return {"s":"out"}
    h=d.get("hourly",{})
    return {"s":"ok","lat":round(d["latitude"],5),"lon":round(d["longitude"],5),"t":h.get("temperature_2m",[])}
def comp(lat,lon):
    ref=fc("icon_seamless",lat,lon)
    if ref["s"]!="ok": return "UNKNOWN"
    W=[i for i,v in enumerate(ref["t"][:24]) if v is not None]
    if not W: return "UNKNOWN"
    hits=[]
    for m in ("icon_d2","icon_eu","icon_global"):
        d=fc(m,lat,lon)
        if d["s"]!="ok" or (d["lat"],d["lon"])!=(ref["lat"],ref["lon"]): continue
        if all(d["t"][i] is not None and d["t"][i]==ref["t"][i] for i in W): hits.append(m)
    return hits[0] if len(hits)==1 else "UNKNOWN"
TARGET=[k for k,r in S.items() if r['IEM']['component'] in ('icon_d2','icon_eu')]
OFF=[(0.2,0),(-0.2,0),(0,0.2),(0,-0.2),(0.4,0),(-0.4,0),(0,0.4),(0,-0.4)]
OUT=json.load(open('COORD_BOUNDARY.json')) if os.path.exists('COORD_BOUNDARY.json') else {}
try:
    for k in TARGET:
        if k in OUT: continue
        r=S[k]; la,lo=r['IEM']['lat'],r['IEM']['lon']; base=r['IEM']['component']
        flips={}
        for dla,dlo in OFF:
            c=comp(la+dla,lo+dlo)
            if c!=base: flips[f"{dla:+.1f},{dlo:+.1f}"]=c
        OUT[k]=dict(icao=k,city=r['city'],base=base,lat=la,lon=lo,flips=flips,
                    min_flip_deg=(0.2 if any(abs(float(x.split(',')[0]))==0.2 or abs(float(x.split(',')[1]))==0.2 for x in flips) else (0.4 if flips else None)))
        json.dump(OUT,open('COORD_BOUNDARY.json','w'),indent=1)
        print(f"  {k:<6}{str(r['city'])[:15]:<17}base={base:<12} flips={flips if flips else 'ninguno hasta ±0.4°'}",flush=True)
except Quota:
    json.dump(OUT,open('COORD_BOUNDARY.json','w'),indent=1); print(f"CUOTA_AGOTADA tras {len(OUT)}/{len(TARGET)}",flush=True); raise SystemExit(3)
json.dump(OUT,open('COORD_BOUNDARY.json','w'),indent=1); print("LISTO n=",len(OUT))
