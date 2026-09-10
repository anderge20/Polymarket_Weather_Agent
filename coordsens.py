import json, urllib.request, ssl, certifi, time, os, math
CTX=ssl.create_default_context(cafile=certifi.where()); UA={"User-Agent":"Mozilla/5.0"}
R={r['icao']:r for r in json.load(open('COORD_TABLE.json'))}
SEL=json.load(open('COORD_PROBE_LIST.json'))
class Quota(Exception): pass
def GET(u,t=60):
    for a in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=t,context=CTX) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code==400: return {"_out":True}
            if e.code==429: raise Quota(e.read().decode()[:150])
            if a==3: return None
        except Exception:
            if a==3: return None
        time.sleep(1.2*(a+1))
def fc(model,lat,lon):
    # endpoint de PRONÓSTICO (cuota independiente). NO es Single Runs. NO es el benchmark V5.
    d=GET(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
          f"&hourly=temperature_2m&forecast_days=2&models={model}&timezone=UTC")
    if d is None: return {"s":"err"}
    if d.get("_out"): return {"s":"out"}
    h=d.get("hourly",{})
    return {"s":"ok","lat":round(d["latitude"],5),"lon":round(d["longitude"],5),
            "elev":d.get("elevation"),"t":h.get("temperature_2m",[]),"time":h.get("time",[])}
def comp(lat,lon):
    ref=fc("icon_seamless",lat,lon)
    if ref["s"]!="ok": return "UNKNOWN",ref
    W=[i for i,v in enumerate(ref["t"][:24]) if v is not None]
    if not W: return "UNKNOWN",ref
    hits=[]
    for m in ("icon_d2","icon_eu","icon_global"):
        d=fc(m,lat,lon)
        if d["s"]!="ok" or (d["lat"],d["lon"])!=(ref["lat"],ref["lon"]): continue
        if all(d["t"][i] is not None and d["t"][i]==ref["t"][i] for i in W): hits.append(m)
    return (hits[0] if len(hits)==1 else "UNKNOWN"), ref
OUT=json.load(open('COORD_SENSITIVITY.json')) if os.path.exists('COORD_SENSITIVITY.json') else {}
try:
    for icao in SEL:
        if icao in OUT: continue
        r=R[icao]; rec={"icao":icao,"city":r['city'],"d_iem_oa":r['d_iem_oa']}
        for src,(la,lo) in (("IEM",r['iem']),("OurAirports",r['oa'])):
            e=fc("ecmwf_ifs025",la,lo)
            c,ref=comp(la,lo)
            rec[src]=dict(lat=la,lon=lo,
                ecmwf_cell=([e["lat"],e["lon"]] if e["s"]=="ok" else None),
                ecmwf_elev=(e.get("elev") if e["s"]=="ok" else None),
                ecmwf_t0=(e["t"][12] if e["s"]=="ok" and len(e["t"])>12 else None),
                icon_cell=([ref["lat"],ref["lon"]] if ref.get("s")=="ok" else None),
                icon_elev=(ref.get("elev") if ref.get("s")=="ok" else None),
                icon_t0=(ref["t"][12] if ref.get("s")=="ok" and len(ref.get("t",[]))>12 else None),
                component=c)
        a,b=rec["IEM"],rec["OurAirports"]
        rec["cambia_celda_ecmwf"]= a["ecmwf_cell"]!=b["ecmwf_cell"]
        rec["cambia_celda_icon"] = a["icon_cell"]!=b["icon_cell"]
        rec["cambia_componente"] = a["component"]!=b["component"]
        rec["delta_t_ecmwf"]= (round(a["ecmwf_t0"]-b["ecmwf_t0"],2) if None not in (a["ecmwf_t0"],b["ecmwf_t0"]) else None)
        rec["delta_t_icon"] = (round(a["icon_t0"]-b["icon_t0"],2)  if None not in (a["icon_t0"],b["icon_t0"])  else None)
        OUT[icao]=rec; json.dump(OUT,open('COORD_SENSITIVITY.json','w'),indent=1)
        print(f"  {icao:<6}d={rec['d_iem_oa']:>6.2f}km  ECMWF celda{'≠' if rec['cambia_celda_ecmwf'] else '='}"
              f"  ICON celda{'≠' if rec['cambia_celda_icon'] else '='}"
              f"  comp {a['component']}->{b['component']}{'  <<< CAMBIA' if rec['cambia_componente'] else ''}"
              f"  ΔT_ec={rec['delta_t_ecmwf']} ΔT_ic={rec['delta_t_icon']}",flush=True)
except Quota as e:
    json.dump(OUT,open('COORD_SENSITIVITY.json','w'),indent=1)
    print(f"CUOTA_AGOTADA tras {len(OUT)}/{len(SEL)} -> {e}",flush=True); raise SystemExit(3)
json.dump(OUT,open('COORD_SENSITIVITY.json','w'),indent=1)
print("LISTO n=",len(OUT))
