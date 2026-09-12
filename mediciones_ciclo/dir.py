"""La direccion que la caja recorre: shard -> load_shards -> base -> stage_dump -> shard."""
import sys, gzip, json, subprocess, tempfile, os
from pathlib import Path
sys.path.insert(0,"src")
from weather_agent import database as db, store
SH="paper_state/markets/2026/09/12/markets__col_20260912T024005Z_dffd86__0000.ndjson.gz"
raw=subprocess.run(["git","show",f"origin/paper-state:{SH}"],capture_output=True).stdout
root=Path(tempfile.mkdtemp())/"s"; (root/"markets"/"2026"/"09"/"12").mkdir(parents=True)
dest=root/"markets"/"2026"/"09"/"12"/Path(SH).name
dest.write_bytes(raw)

con=db.init_db(db.connect(":memory:"))
res=store.load_shards(con, table="markets", root=str(root))
print("load_shards:", {k:v for k,v in (res or {}).items() if k in ("rows_read","rows_written")})
base=db.query(con,"SELECT * FROM markets")
delshard=list(store.read_shard(dest))
print(f"filas en el shard {len(delshard)}   en la base {len(base)}")
k=("market_id","dataset_version","record_version")
ident=lambda r: tuple(str(r.get(c)) for c in k)
pb={ident(r):r for r in delshard}
import collections
fam=collections.Counter(); ej={}
dif=0
for r in base:
    p=pb.get(ident(r))
    if p is None: continue
    d=[c for c in set(p)|set(r) if p.get(c)!=r.get(c)]
    if d: dif+=1
    for c in d:
        fam[c]+=1; ej.setdefault(c,(p.get(c),r.get(c)))
print(f"\nfilas que difieren shard-contra-base: {dif} de {len(base)}")
for c,n in fam.most_common():
    a,b=ej[c]
    print(f"  {c:<24}{n:>6}  shard={type(a).__name__:<8}{str(a)[:26]!r}  "
          f"base={type(b).__name__:<8}{str(b)[:26]!r}")
if not fam: print("  ninguna columna difiere")

print("\n=== y ahora comparando por el lado SIMETRICO: export_rows contra read_shard")
exp = store.export_rows(con, "markets")
pe = {ident(r): r for r in exp}
fam2 = collections.Counter(); ej2 = {}; dif2 = 0
for p in delshard:
    r = pe.get(ident(p))
    if r is None: continue
    d = [c for c in set(p) | set(r) if p.get(c) != r.get(c)]
    if d: dif2 += 1
    for c in d:
        fam2[c] += 1; ej2.setdefault(c, (p.get(c), r.get(c)))
print(f"filas que difieren: {dif2} de {len(delshard)}")
for c, n in fam2.most_common():
    a, b = ej2[c]
    print(f"  {c:<24}{n:>6}  shard={type(a).__name__:<9} base={type(b).__name__}")
if not fam2: print("  NINGUNA columna difiere")
