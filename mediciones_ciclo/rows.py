import json, gzip, subprocess
REPO="/Users/mariaaleu/workspace/Polymarket_Weather_Agent"
def sh(*a): return subprocess.run(a,cwd=REPO,capture_output=True,text=True).stdout
files=sorted(f for f in sh("git","ls-tree","-r","origin/paper-state","--name-only").splitlines() if "cycle_params" in f)
rows=[]
for f in files[-6:]:
    raw=subprocess.run(["git","show",f"origin/paper-state:{f}"],cwd=REPO,capture_output=True).stdout
    for line in gzip.decompress(raw).decode().splitlines():
        d=json.loads(line)
        if d.get("stage_profile"): rows.append(d)
rows.sort(key=lambda d:d.get("session_id",""))
print(f"{'session':<30}{'loaded':>10}{'resident':>10}{'bytes MB':>10}")
prev=None
for d in rows:
    lo=d.get("store_rows_loaded"); re=d.get("store_rows_resident"); by=d.get("store_total_bytes")
    print(f"{d['session_id']:<30}{str(lo):>10}{str(re):>10}"
          f"{(by/1e6 if isinstance(by,(int,float)) else float('nan')):10.1f}")
    if prev and all(isinstance(x,(int,float)) for x in (lo,re,prev[0],prev[1])):
        print(f"{'  delta':<30}{lo-prev[0]:+10d}{re-prev[1]:+10d}")
    prev=(lo,re)
# conteo de shards por tabla
print("\nshards por tabla en el almacen:")
from collections import Counter
c=Counter()
for f in sh("git","ls-tree","-r","origin/paper-state","--name-only").splitlines():
    p=f.split("/")
    if len(p)>1 and f.endswith(".ndjson.gz"): c[p[1] if p[0]=="shards" else p[0]]+=1
for k,v in sorted(c.items(),key=lambda kv:-kv[1])[:12]: print(f"  {k:<30}{v:6d}")
