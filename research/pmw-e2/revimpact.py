import urllib.request, re, ssl, certifi, json, time
from collections import defaultdict
CTX=ssl.create_default_context(cafile=certifi.where()); UA={"User-Agent":"Mozilla/5.0"}
S=json.load(open("REVISION_SAMPLE.json")); STS=set(S["stations"]); DAYS=S["days"]
BODY=re.compile(r'\s(M?\d{2})/(M?\d{2})[\s=]')
num=lambda s: -int(s[1:]) if s.startswith('M') else int(s)
recs=[]   # (station, day, obstime, hour_file, seq, is_cor, temp, raw_hash)
for day in DAYS:
    y,m,d=day.split("-")
    got=0
    for h in range(24):
        u=f"https://mtarchive.geol.iastate.edu/{y}/{m}/{d}/text/sao/{y}{m}{d}{h:02d}_sao.txt"
        try: t=urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=120,context=CTX).read().decode("utf-8","replace")
        except Exception: continue
        got+=1
        for st in STS:
            for mt in re.finditer(rf'\b{st} (\d{{6}})Z', t):
                a=max(0,mt.start()-14); b=min(len(t), mt.end()+220)
                seg=t[a:b]
                end=seg.find('=', mt.end()-a)
                body=seg[mt.end()-a: (end if end>0 else len(seg))]
                is_cor = ('COR' in seg[:mt.end()-a+8]) or (' COR ' in body[:12])
                bm=BODY.search(body+' ')
                temp = num(bm.group(1)) if bm else None
                recs.append((st, day, mt.group(1), h, mt.start(), is_cor, temp))
    print(f"  {day}: {got}/24 ficheros, acumulado {len(recs)} mensajes", flush=True)
json.dump(recs, open("REVISION_RAW.json","w"))
print("TOTAL mensajes:", len(recs))
