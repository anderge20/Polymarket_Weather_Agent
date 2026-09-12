import json, subprocess, datetime as dt
def gh(*a):
    return json.loads(subprocess.run(["gh",*a],capture_output=True,text=True).stdout or "[]")
def utc(s): return dt.datetime.fromisoformat(s.replace("Z","+00:00"))
prs = gh("pr","list","--state","merged","--limit","30","--json",
         "number,createdAt,mergedAt,title,reviews,comments")
print(f"{'PR':>5}{'espera h':>10}{'reviews':>9}{'coment.':>9}{'antes del merge':>17}   titulo")
sin=0
for r in sorted(prs,key=lambda r:-r["number"]):
    if not r.get("mergedAt"): continue
    m=utc(r["mergedAt"]); esp=(m-utc(r["createdAt"])).total_seconds()/3600
    revs=r.get("reviews") or []; coms=r.get("comments") or []
    antes=[c for c in coms if utc(c["createdAt"])<m]
    revs_antes=[v for v in revs if v.get("submittedAt") and utc(v["submittedAt"])<m]
    marca = len(revs_antes)+len(antes)
    if marca==0: sin+=1
    print(f"{r['number']:>5}{esp:>10.2f}{len(revs):>9}{len(coms):>9}"
          f"{marca:>17}   {r['title'][:44]}")
print(f"\nPRs fusionados SIN ninguna revision ni comentario previo al merge: {sin} de "
      f"{sum(1 for r in prs if r.get('mergedAt'))}")
