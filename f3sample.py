import urllib.request, json, ssl, certifi, time
from datetime import datetime, timezone
CTX=ssl.create_default_context(cafile=certifi.where()); UA={"User-Agent":"Mozilla/5.0"}
B="https://openmeteo.s3.amazonaws.com"
MODELS=["ecmwf_ifs025","dwd_icon","ncep_gfs025","ukmo_global_deterministic_10km"]
# 20 fechas reproducibles: los días 05 y 20 de cada mes + 10 fechas intercaladas, jun-sep
DATES=[]
for mm,dd_list in [("06",[3,8,13,18,23,28]),("07",[3,10,17,24,31]),("08",[5,12,19,26]),("09",[1,2,3,4,5])]:
    for dd in dd_list: DATES.append(f"2026-{mm}-{dd:02d}")
DATES=sorted(DATES)
CYC=["0000Z","0600Z","1200Z","1800Z"]
def get(u,t=30):
    try:
        with urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=t,context=CTX) as r:
            return r.read(), dict(r.headers)
    except Exception: return None,None
def head(u,t=25):
    try:
        rq=urllib.request.Request(u,headers=UA); rq.get_method=lambda:"HEAD"
        with urllib.request.urlopen(rq,timeout=t,context=CTX) as r: return dict(r.headers)
    except Exception: return None
rows=[]
for m in MODELS:
    for d in DATES:
        for c in CYC:
            base=f"{B}/data_run/{m}/{d[:4]}/{d[5:7]}/{d[8:10]}/{c}"
            b,_=get(f"{base}/meta.json")
            if not b: continue
            try: j=json.loads(b)
            except Exception: continue
            ca=j.get("created_at")
            h=head(f"{base}/temperature_2m.om")
            lm=h.get("Last-Modified") if h else None
            init=datetime(int(d[:4]),int(d[5:7]),int(d[8:10]),int(c[:2]),tzinfo=timezone.utc)
            cad=datetime.fromisoformat(ca.replace("Z","+00:00")) if ca else None
            lmd=datetime.strptime(lm,"%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc) if lm else None
            rows.append(dict(model=m,date=d,cycle=c,init=init.isoformat(),created_at=ca,
                last_modified=(lmd.isoformat() if lmd else None),
                lat_created_h=round((cad-init).total_seconds()/3600,4) if cad else None,
                lat_lm_h=round((lmd-init).total_seconds()/3600,4) if lmd else None,
                delta_lm_ca_min=round((lmd-cad).total_seconds()/60,2) if (lmd and cad) else None,
                ref_time=j.get("reference_time")))
            time.sleep(0.05)
    print(f"  {m}: acumuladas {len(rows)}",flush=True)
json.dump(rows,open("evidence/F3_SAMPLE_WIDE.json","w"),indent=1)
print("TOTAL",len(rows))
