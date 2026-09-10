"""V5.2 — re-extracción de f con coordenadas canónicas (D1). Reanudable; 429 = guardar y salir.
Misma muestra, mismos run, misma ventana W(m) y misma regla de f que V3 (geoval3.py)."""
import json, urllib.request, ssl, certifi, time, os, sys
SMOKE=int(sys.argv[sys.argv.index("--smoke")+1]) if "--smoke" in sys.argv else None
from datetime import datetime, timedelta, date, timezone
from zoneinfo import ZoneInfo
CTX=ssl.create_default_context(cafile=certifi.where()); UA={"User-Agent":"Mozilla/5.0"}
R=json.load(open('MODELSEL_GEOVAL_V3_RAW.json'))
SNAP={s['icao']:(s['lat'],s['lon']) for s in json.load(open('STATION_COORDS_SNAPSHOT_v1.json'))['stations']}
MODELS=["icon_seamless","icon_d2","icon_eu","icon_global","ecmwf_ifs025"]
# (icao, run, lead) únicos de V3 con run no nulo, más su target_date/tz/event_id/y
ICON_FAMILY=["icon_seamless","icon_d2","icon_eu","icon_global"]
KEYS={}
for r in R:
    if r['model'] in ('icon_seamless','ecmwf_ifs025') and r['run']:
        k=KEYS.setdefault((r['icao'],r['run'],r['lead']),dict(target_date=r['target_date'],tz=r['tz'],
                        event_id=r['event_id'],city=r['city'],region=r['region'],y=r['y'],models=[]))
        k['models']+= ICON_FAMILY if r['model']=='icon_seamless' else ["ecmwf_ifs025"]
class Quota(Exception): pass
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
                    "elev":d.get("elevation"),"series":{t:v for t,v in zip(h["time"],h["temperature_2m"])}}
        except urllib.error.HTTPError as e:
            if e.code==400: return {"status":"out_of_domain"}
            if e.code==429: raise Quota(e.read().decode()[:150])
            if a==3: return {"status":"http_error"}
        except Exception:
            if a==3: return {"status":"error"}
        time.sleep(1.5*(a+1))
OUT=json.load(open('V5_EXTRACT.json')) if os.path.exists('V5_EXTRACT.json') else {}
cache={}   # (model, icao, run) -> respuesta; un run sirve a un solo lead en V3, pero se cachea por seguridad
def save(): json.dump(OUT,open('V5_EXTRACT.json','w'),indent=1)
print(f"reanudando extracción: {len(OUT)}/{len(KEYS)} claves" + (f"  [SMOKE: sólo {SMOKE} claves nuevas]" if SMOKE else ""),flush=True)
nuevas=0
try:
    for i,((icao,run,lead),meta) in enumerate(sorted(KEYS.items())):
        k=f"{icao}|{run}|{lead}"
        if k in OUT: continue
        if SMOKE is not None and nuevas>=SMOKE: break
        nuevas+=1
        la,lo=SNAP[icao]; rt=run.replace("Z","")
        td=date.fromisoformat(meta['target_date']); Z=ZoneInfo(meta['tz'])
        ws=datetime(td.year,td.month,td.day,tzinfo=Z); we=ws+timedelta(days=1)
        meta2={k2:v for k2,v in meta.items() if k2!='models'}
        rec=dict(icao=icao,run=run,lead=lead,req_lat=la,req_lon=lo,coord_source="STATION_COORDS_SNAPSHOT_v1",
                 models_fetched=sorted(set(meta['models'])),**meta2)
        for m in rec['models_fetched']:
            ck=(m,icao,run)
            if ck not in cache: cache[ck]=sr(m,la,lo,rt)
            d=cache[ck]
            if d["status"]!="ok":
                rec[m]=dict(status=d["status"]); continue
            W={t:v for t,v in d["series"].items() if v is not None and ws<=datetime.fromisoformat(t+"+00:00")<we}
            rec[m]=dict(status="ok",cell_lat=d["lat"],cell_lon=d["lon"],cell_elev=d["elev"],
                        f=(max(W.values()) if W else None),n_horas_ventana=len(W),
                        ventana={t:v for t,v in W.items()})
        # identificación de componente sobre W(m) (regla V5.1 §4 bis)
        ref=rec.get("icon_seamless")
        if ref is None:
            rec["component"]=None; rec["unknown_kind"]=None
        elif ref["status"]=="ok" and ref["ventana"]:
            hits=[m for m in ("icon_d2","icon_eu","icon_global")
                  if rec[m]["status"]=="ok" and (rec[m]["cell_lat"],rec[m]["cell_lon"])==(ref["cell_lat"],ref["cell_lon"])
                  and all(rec[m]["ventana"].get(t)==v for t,v in ref["ventana"].items())]
            rec["component"]=hits[0] if len(hits)==1 else "UNKNOWN"
            rec["unknown_kind"]=None if len(hits)==1 else ("AMBIGUO" if hits else "SIN_COINCIDENCIA")
        else:
            rec["component"]="UNKNOWN"; rec["unknown_kind"]="SEAMLESS_NO_DISPONIBLE"
        OUT[k]=rec
        if len(OUT)%25==0: save(); print(f"  {len(OUT)}/{len(KEYS)}",flush=True)
except Quota as e:
    save(); print(f"CUOTA_AGOTADA tras {len(OUT)}/{len(KEYS)} -> {e}",flush=True); raise SystemExit(3)
save()
if SMOKE is not None:
    smoke=[OUT[k] for k in list(OUT)[-nuevas:]] if nuevas else []
    comps=[r.get('component') for r in smoke if 'icon_seamless' in r]
    fs=[(m,r[m].get('f')) for r in smoke for m in r['models_fetched'] if r[m].get('status')=='ok']
    print("SMOKE:",len(smoke),"claves;","componentes:",comps,"; f no nulos:",sum(1 for _,f in fs if f is not None),"/",len(fs))
    if comps and all(c=='UNKNOWN' for c in comps): print("SMOKE_FALLO: todos los componentes UNKNOWN — revisar regla antes de gastar cuota"); raise SystemExit(4)
    if fs and all(f is None for _,f in fs): print("SMOKE_FALLO: ningún f — revisar ventana"); raise SystemExit(4)
    print("SMOKE_OK"); raise SystemExit(0)
print("LISTO_EXTRACT n=",len(OUT))
