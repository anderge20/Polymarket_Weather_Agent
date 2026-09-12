import subprocess, gzip, json, sys
sys.path.insert(0,"src")
from weather_agent.store import CONFLICT_COLS
REPO="/Users/mariaaleu/workspace/Polymarket_Weather_Agent"
def sh(*a): return subprocess.run(a,cwd=REPO,capture_output=True,text=True).stdout
def rows(p):
    raw=subprocess.run(["git","show",f"origin/paper-state:{p}"],cwd=REPO,capture_output=True).stdout
    return [json.loads(l) for l in gzip.decompress(raw).decode().splitlines()]
paths=[p for p in sh("git","ls-tree","-r","origin/paper-state","--name-only").split()
       if p.endswith(".ndjson.gz")]
import collections, re
bydir=collections.defaultdict(list)
for p in paths: bydir[p.rsplit("/",1)[0]].append(p)

print("Donde el orden de ruta INVIERTE el orden de tiempo, buscamos colision de clave:\n")
for d,fs in sorted(bydir.items()):
    fs=sorted(fs)
    table=d.split("/")[1]
    key=CONFLICT_COLS.get(table)
    if not key: continue
    gen=lambda f: ("ts" if re.search(r"__col_\d{8}T",f) else
                   "cyc" if "__cyc_" in f else
                   "runid" if re.search(r"__col_\d{6,}_",f) else "?")
    if len({gen(f) for f in fs})<2: continue
    ultimo=fs[-1]
    otros=[f for f in fs if f is not ultimo and gen(f)!=gen(ultimo)]
    if not otros: continue
    ident=lambda r: tuple(str(r.get(c)) for c in key)
    ku={ident(r) for r in rows(ultimo)}
    for f in otros:
        inter=ku & {ident(r) for r in rows(f)}
        if inter:
            print(f"  {table}: {ultimo.rsplit('/',1)[1][:50]}")
            print(f"           pisa {len(inter)} claves de {f.rsplit('/',1)[1][:50]}")
    if not any(ku & {ident(r) for r in rows(f)} for f in otros):
        print(f"  {table}/{d.rsplit('/',3)[-3:] and d[-10:]}: "
              f"generaciones mezcladas, CERO claves en comun -> el replay no cambia nada")
