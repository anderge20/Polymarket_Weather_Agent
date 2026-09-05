import urllib.request, json, ssl, certifi, re, time, csv, io
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
CTX=ssl.create_default_context(cafile=certifi.where()); UA={"User-Agent":"Mozilla/5.0"}
sel=json.load(open("SAMPLE_E2.json")); tz=json.load(open("STATIONS_TZ.json"))
BODY=re.compile(r'\s(M?\d{2})/(M?\d{2})\s'); TG=re.compile(r'\bT([01])(\d{3})([01])(\d{3})\b')
def num(s): return -int(s[1:]) if s.startswith('M') else int(s)
def iem(st,d0,d1):
    u=(f"https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station={st}"
       f"&data=tmpc&data=tmpf&data=metar&year1={d0.year}&month1={d0.month}&day1={d0.day}"
       f"&year2={d1.year}&month2={d1.month}&day2={d1.day}&tz=UTC&format=onlycomma&latlon=no&report_type=3&report_type=4")
    with urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=60,context=CTX) as r:
        return list(csv.DictReader(io.StringIO(r.read().decode())))
out=[]
for i,r in enumerate(sel):
    if not r["icao"]: continue
    st=r["icao"]; st_iem = st[1:] if st.startswith("K") and st in tz else st
    td=datetime.strptime(r["target_date"],"%Y-%m-%d").date()
    try: rows=iem(st_iem, td-timedelta(days=1), td+timedelta(days=2))
    except Exception as e: print(" ERR",st,e); continue
    obs=[]
    for x in rows:
        try: t=datetime.strptime(x["valid"],"%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except: continue
        m=x.get("metar") or ""
        b=BODY.search(m); g=TG.search(m)
        obs.append(dict(t=t,
            body=(num(b.group(1)) if b else None),
            tg=((-1 if g.group(1)=='1' else 1)*int(g.group(2))/10 if g else None),
            tmpc=(float(x["tmpc"]) if x.get("tmpc") not in (None,"","M") else None),
            tmpf=(float(x["tmpf"]) if x.get("tmpf") not in (None,"","M") else None)))
    Z=ZoneInfo(tz[st]["tz"])
    def win(name):
        if name=="H_UTC":
            a=datetime(td.year,td.month,td.day,tzinfo=timezone.utc); b=a+timedelta(days=1)
        else:
            off={"H_LOCAL":0,"H_LOCAL_M1":-1,"H_LOCAL_P1":1}[name]
            d=td+timedelta(days=off)
            a=datetime(d.year,d.month,d.day,tzinfo=Z); b=a+timedelta(days=1)
        return a,b
    rec=dict(event_id=r["event_id"],city=r["city"],rule=r["rule"],unit=r["unit"],rr=r["rr"],
             icao=st,tz=tz[st]["tz"],target_date=r["target_date"],
             win_lo=r["win_lo"],win_hi=r["win_hi"],win_band=r["win_band"],n_obs=len(obs))
    for w in ("H_UTC","H_LOCAL","H_LOCAL_M1","H_LOCAL_P1"):
        a,b=win(w); sub=[o for o in obs if a<=o["t"]<b]
        for f in ("body","tg","tmpc","tmpf"):
            v=[o[f] for o in sub if o[f] is not None]
            rec[f"{w}_{f}"]=max(v) if v else None
        rec[f"{w}_n"]=len(sub)
    out.append(rec); print(f"  [{len(out):>2}] {r['city']:<14} {st} n={len(obs):>3}",flush=True)
    time.sleep(0.3)
json.dump(out,open("E2_RESULTS.json","w"),indent=1,default=str)
print("\nguardado E2_RESULTS.json:",len(out),"eventos")
