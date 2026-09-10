import json, urllib.request, ssl, certifi, time
from datetime import datetime, timedelta, date, timezone
from zoneinfo import ZoneInfo
CTX=ssl.create_default_context(cafile=certifi.where()); UA={"User-Agent":"Mozilla/5.0"}
R=json.load(open('MODELSEL_GEOVAL_V3_RAW.json'))
S={e['icao']:(e['req_lat'],e['req_lon']) for e in json.load(open('MODELSEL_GEOVAL_V3_SAMPLE.json'))}
# (icao,run) -> (target_date, tz)
META={}
for r in R:
    if r['model']=='icon_seamless' and r['run']: META[(r['icao'],r['run'])]=(r['target_date'],r['tz'])
pairs=sorted(META)
MODELS=["icon_seamless","icon_d2","icon_eu","icon_global"]
def sr(model,lat,lon,run):
    u=(f"https://single-runs-api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
       f"&hourly=temperature_2m&models={model}&run={run}&timezone=UTC")
    for a in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=90,context=CTX) as r:
                d=json.loads(r.read())
            if d.get("error"): return {"status":"api_error"}
            h=d["hourly"]
            return {"status":"ok","lat":round(d["latitude"],5),"lon":round(d["longitude"],5),
                    "series":{t:v for t,v in zip(h["time"],h["temperature_2m"])}}
        except urllib.error.HTTPError as e:
            if e.code==400: return {"status":"out_of_domain"}
            if e.code==429: raise QuotaExceeded(e.read().decode()[:200])
            if a==3: return {"status":"http_error"}
        except Exception:
            if a==3: return {"status":"error"}
        time.sleep(1.5*(a+1))
class QuotaExceeded(Exception): pass
import os
OUT=json.load(open('V5_COMPONENT_MAP.json')) if os.path.exists('V5_COMPONENT_MAP.json') else {}
print(f"reanudando: {len(OUT)} pares ya resueltos de {len(pairs)}",flush=True)
for i,(icao,run) in enumerate(pairs):
    if f"{icao}|{run}" in OUT: continue
    la,lo=S[icao]; rt=run.replace("Z","")
    td_s,tz=META[(icao,run)]
    td=date.fromisoformat(td_s); Z=ZoneInfo(tz)
    ws=datetime(td.year,td.month,td.day,tzinfo=Z); we=ws+timedelta(days=1)
    try:
        res={m:sr(m,la,lo,rt) for m in MODELS}
    except QuotaExceeded as e:
        json.dump(OUT,open('V5_COMPONENT_MAP.json','w'),indent=1)
        print(f"CUOTA_AGOTADA tras {len(OUT)}/{len(pairs)} pares -> {e}",flush=True); raise SystemExit(3)
    ref=res["icon_seamless"]
    rec={"icao":icao,"run":run,"target_date":td_s,"tz":tz,"seamless_status":ref["status"]}
    if ref["status"]!="ok":
        rec.update(component="UNKNOWN",unknown_kind="SEAMLESS_NO_DISPONIBLE")
    else:
        # ventana W(m): marcas UTC dentro del día civil local, con valor no nulo en seamless
        W=[t for t,v in ref["series"].items()
           if v is not None and ws <= datetime.fromisoformat(t+"+00:00") < we]
        rec["n_horas_ventana"]=len(W); rec["cell"]=[ref["lat"],ref["lon"]]
        if not W:
            rec.update(component="UNKNOWN",unknown_kind="VENTANA_VACIA")
        else:
            matches=[]; status={}
            for m in ("icon_d2","icon_eu","icon_global"):
                d=res[m]; status[m]=d["status"]
                if d["status"]!="ok": continue
                if (d["lat"],d["lon"])!=(ref["lat"],ref["lon"]): continue
                if all(d["series"].get(t) is not None and d["series"][t]==ref["series"][t] for t in W):
                    matches.append(m)
            rec["component_status"]=status; rec["matches"]=matches
            if len(matches)==1: rec["component"]=matches[0]
            elif len(matches)==0: rec.update(component="UNKNOWN",unknown_kind="SIN_COINCIDENCIA")
            else: rec.update(component="UNKNOWN",unknown_kind="AMBIGUO")
    OUT[f"{icao}|{run}"]=rec
    if (i+1)%50==0:
        json.dump(OUT,open('V5_COMPONENT_MAP.json','w'),indent=1); print(f"  {i+1}/{len(pairs)}",flush=True)
json.dump(OUT,open('V5_COMPONENT_MAP.json','w'),indent=1)
print("LISTO. pares:",len(OUT))
