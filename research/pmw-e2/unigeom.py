import json, urllib.request, ssl, certifi, time, os
CTX=ssl.create_default_context(cafile=certifi.where()); UA={"User-Agent":"Mozilla/5.0"}
M=json.load(open('COORD_MASTER.json'))
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
    return {"s":"ok","lat":round(d["latitude"],5),"lon":round(d["longitude"],5),
            "elev":d.get("elevation"),"t":h.get("temperature_2m",[])}
def probe(lat,lon):
    e=fc("ecmwf_ifs025",lat,lon); ref=fc("icon_seamless",lat,lon)
    comp="UNKNOWN"
    if ref["s"]=="ok":
        W=[i for i,v in enumerate(ref["t"][:24]) if v is not None]
        if W:
            hits=[]
            for m in ("icon_d2","icon_eu","icon_global"):
                d=fc(m,lat,lon)
                if d["s"]!="ok" or (d["lat"],d["lon"])!=(ref["lat"],ref["lon"]): continue
                if all(d["t"][i] is not None and d["t"][i]==ref["t"][i] for i in W): hits.append(m)
            if len(hits)==1: comp=hits[0]
    return dict(ecmwf_cell=([e["lat"],e["lon"]] if e["s"]=="ok" else None),
                ecmwf_t=(e["t"][12] if e["s"]=="ok" and len(e["t"])>12 else None),
                icon_cell=([ref["lat"],ref["lon"]] if ref["s"]=="ok" else None),
                icon_t=(ref["t"][12] if ref["s"]=="ok" and len(ref["t"])>12 else None),
                component=comp)
OUT=json.load(open('COORD_UNIGEOM.json')) if os.path.exists('COORD_UNIGEOM.json') else {}
print(f"reanudando: {len(OUT)}/{len(M)}",flush=True)
try:
    for m in M:
        k=m['icao']
        if k in OUT: continue
        rec={"icao":k,"city":m['city'],"n_markets":m['n_markets'],
             "d_noaa_oa":m['d_noaa_oa'],"d_noaa_iem":m['d_noaa_iem']}
        for src in ("noaa","oa","iem"):
            rec[src]=probe(m[src][0],m[src][1])
        cells_e={tuple(rec[s]['ecmwf_cell']) if rec[s]['ecmwf_cell'] else None for s in ("noaa","oa","iem")}
        cells_i={tuple(rec[s]['icon_cell'])  if rec[s]['icon_cell']  else None for s in ("noaa","oa","iem")}
        comps ={rec[s]['component'] for s in ("noaa","oa","iem")}
        rec['n_celdas_ecmwf']=len(cells_e); rec['n_celdas_icon']=len(cells_i); rec['n_componentes']=len(comps)
        ts=[rec[s]['icon_t'] for s in ("noaa","oa","iem") if rec[s]['icon_t'] is not None]
        te=[rec[s]['ecmwf_t'] for s in ("noaa","oa","iem") if rec[s]['ecmwf_t'] is not None]
        rec['spread_t_icon']=(round(max(ts)-min(ts),2) if len(ts)>1 else None)
        rec['spread_t_ecmwf']=(round(max(te)-min(te),2) if len(te)>1 else None)
        OUT[k]=rec; json.dump(OUT,open('COORD_UNIGEOM.json','w'),indent=1)
        print(f"  {k:<6}celdas_ec={rec['n_celdas_ecmwf']} celdas_ic={rec['n_celdas_icon']} "
              f"comp={rec['n_componentes']} spread_ic={rec['spread_t_icon']} spread_ec={rec['spread_t_ecmwf']}",flush=True)
except Quota:
    json.dump(OUT,open('COORD_UNIGEOM.json','w'),indent=1)
    print(f"CUOTA_AGOTADA tras {len(OUT)}/{len(M)}",flush=True); raise SystemExit(3)
json.dump(OUT,open('COORD_UNIGEOM.json','w'),indent=1); print("LISTO n=",len(OUT))
