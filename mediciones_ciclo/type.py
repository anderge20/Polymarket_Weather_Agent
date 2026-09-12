import sys, tempfile, importlib.util
from pathlib import Path
sys.path.insert(0,"src")
from weather_agent import database as db, store
spec=importlib.util.spec_from_file_location("paper_cycle","scripts/paper_cycle.py")
pc=importlib.util.module_from_spec(spec); sys.modules["paper_cycle"]=pc; spec.loader.exec_module(pc)

root=Path(tempfile.mkdtemp())/"store"
con=db.init_db(db.connect(":memory:"))
fila={"market_id":"m1","dataset_version":"ds1","record_version":1,
      "event_id":"e1","question":"q","ingestion_timestamp":"2026-09-09T15:16:32Z"}
db.upsert(con,"markets",fila,("market_id","dataset_version","record_version"))
# el volcado real: se escribe DESDE la base, igual que stage_dump
filas=db.query(con,"SELECT * FROM markets")
store.write_shard(filas,table="markets",run_id="col_A",root=root)
print("MISMA fila, escrita desde la base y comparada consigo misma:")
print("  puerta ->", pc.catalogue_is_unchanged(con,"markets",str(root)))
prev=list(store.read_shard(sorted(store.iter_shards(root,"markets"))[-1]))[0]
cur=db.query(con,"SELECT * FROM markets")[0]
malas={c for c in set(prev)|set(cur) if prev.get(c)!=cur.get(c)}
for c in sorted(malas):
    print(f"  {c:<24} shard={prev.get(c)!r} ({type(prev.get(c)).__name__})"
          f"  base={cur.get(c)!r} ({type(cur.get(c)).__name__})")
if not malas: print("  ninguna columna difiere")
