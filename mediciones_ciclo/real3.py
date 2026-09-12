import sys, subprocess, tempfile, importlib.util
from pathlib import Path
sys.path.insert(0,"src")
from weather_agent import database as db, store
sp=importlib.util.spec_from_file_location("pc","scripts/paper_cycle.py")
pc=importlib.util.module_from_spec(sp); sys.modules["pc"]=pc; sp.loader.exec_module(pc)
REPO="/Users/mariaaleu/workspace/Polymarket_Weather_Agent"
def sh(*a): return subprocess.run(a,cwd=REPO,capture_output=True,text=True).stdout
paths=sh("git","ls-tree","-r","origin/paper-state","--name-only").split()
def traer(root,p):
    raw=subprocess.run(["git","show",f"origin/paper-state:{p}"],cwd=REPO,capture_output=True).stdout
    d=root/Path(p).parent.relative_to("paper_state"); d.mkdir(parents=True,exist_ok=True)
    (d/Path(p).name).write_bytes(raw)
print(f"{'par':<20}{'markets':>12}{'outcomes':>12}{'filas ahorradas':>18}")
tot=0; n=0
for tabla_filas in [None]:
    pass
sm=sorted(p for p in paths if "/markets/" in p and "col_2026" in p)
so=sorted(p for p in paths if "/outcomes/" in p and "col_2026" in p)
for (a,b),(c,d) in zip(zip(sm,sm[1:]), zip(so,so[1:])):
    fila=0; res={}
    for tabla,ant,des,nf in (("markets",a,b,2200),("outcomes",c,d,4400)):
        ra=Path(tempfile.mkdtemp())/"paper_state"; ra.mkdir(parents=True); traer(ra,ant)
        rb=Path(tempfile.mkdtemp())/"paper_state"; rb.mkdir(parents=True); traer(rb,des)
        con=db.init_db(db.connect(":memory:")); store.load_shards(con,table=tabla,root=str(rb))
        v=pc.catalogue_is_unchanged(con,tabla,str(ra))
        res[tabla]="SALTA" if v else "vuelca"
        if v: fila+=len(list(store.read_shard(next(rb.rglob('*.ndjson.gz')))))
    tot+=fila; n+=1
    print(f"{a.split('__')[1][9:15]+'->'+b.split('__')[1][9:15]:<20}"
          f"{res['markets']:>12}{res['outcomes']:>12}{fila:>18}")
print(f"\npares {n}   filas ahorradas {tot}   media {tot/n:.0f}/ciclo de 6.600 = {100*tot/n/6600:.0f} %")
