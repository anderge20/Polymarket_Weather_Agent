"""Cuanta RAM cuesta de verdad cargar el almacen: medido, no extrapolado."""
import sys, os, resource, subprocess, tempfile, gzip
from pathlib import Path
sys.path.insert(0,"src")
from weather_agent import database as db, store

def rss_mb():
    k = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return k/1048576 if sys.platform=="darwin" else k/1024

REPO="/Users/mariaaleu/workspace/Polymarket_Weather_Agent"
root=Path(tempfile.mkdtemp())/"paper_state"
paths=[p for p in subprocess.run(["git","ls-tree","-r","origin/paper-state","--name-only"],
       cwd=REPO,capture_output=True,text=True).stdout.split() if p.endswith(".ndjson.gz")]
total=0
for p in paths:
    raw=subprocess.run(["git","show",f"origin/paper-state:{p}"],cwd=REPO,capture_output=True).stdout
    d=root/Path(p).parent.relative_to("paper_state"); d.mkdir(parents=True,exist_ok=True)
    (d/Path(p).name).write_bytes(raw); total+=len(raw)
print(f"almacen extraido: {len(paths)} shards, {total/1e6:.1f} MB comprimidos", flush=True)
print(f"RSS base tras importar y extraer: {rss_mb():.1f} MB", flush=True)

con=db.init_db(db.connect(":memory:"))
filas=0
for t in ("markets","outcomes","market_fee_schedule","orderbook_snapshots",
          "price_history","venue_coverage","cycle_params"):
    try:
        r=store.load_shards(con, table=t, root=str(root))
    except Exception as e:
        print(f"  {t:<22} SALTADO: {str(e)[:50]}", flush=True); continue
    filas+=r.get("rows_read",0)
    print(f"  {t:<22} filas={r.get('rows_read',0):>7}  RSS pico={rss_mb():7.1f} MB", flush=True)
print(f"\nTOTAL filas leidas {filas}   RSS pico {rss_mb():.1f} MB   "
      f"-> {1024*rss_mb()/filas:.2f} KB/fila" if filas else "sin filas", flush=True)
