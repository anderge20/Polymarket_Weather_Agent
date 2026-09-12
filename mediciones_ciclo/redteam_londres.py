"""Red team del hallazgo de Londres. Cinco ataques y un placebo."""
import json, collections, random, statistics as st, math
rows=[r for r in json.load(open("R30_ROWS.json")) if r.get("station")=="EGLC"]
g=collections.defaultdict(list)
for r in rows: g[(r["event_id"], r["lead_h"])].append(r)
suma={k:sum(x["p_mid"] for x in v) for k,v in g.items()}
VIVOS={k for k in g if suma[k]>=0.50}
POB={"completa (la de A)": rows,
     "particion (libro vivo)": [x for k in VIVOS for x in g[k]]}
BANDA=(0.07,0.60)
rng=random.Random(20260912)

def dif(fs):
    "mean(p_mid) - mean(won) en puntos porcentuales, sobre las filas dadas"
    if not fs: return float("nan")
    return 100*(st.mean(r["p_mid"] for r in fs) - st.mean(r["won"] for r in fs))

def en_banda(fs, lo=BANDA[0], hi=BANDA[1]):
    return [r for r in fs if lo <= r["p_mid"] < hi]

for etq, fs in POB.items():
    ev=collections.defaultdict(list)
    for r in fs: ev[r["event_id"]].append(r)
    b=en_banda(fs)
    evb={r["event_id"] for r in b}
    print(f"=== {etq}: {len(fs)} filas, {len(ev)} eventos")
    print(f"    banda [0,07 , 0,60):  {len(b)} filas, {len(evb)} eventos   "
          f"dif = {dif(b):+.2f} pp")

    # (2) IC por bloques sobre EVENTOS
    bloques=[v for v in ev.values()]
    reps=[]
    for _ in range(10000):
        m=[x for bl in rng.choices(bloques,k=len(bloques)) for x in bl]
        d=dif(en_banda(m))
        if d==d: reps.append(d)
    reps.sort()
    lo,hi=reps[int(.025*len(reps))],reps[int(.975*len(reps))]
    print(f"    IC 95 % por bloques sobre EVENTOS: [{lo:+.2f} , {hi:+.2f}]   "
          f"{'EXCLUYE el 0' if lo*hi>0 else 'INCLUYE el 0'}")

    # (4) particion temporal
    fe=sorted({str(r['target_date'])[:10] for r in fs})
    corte=fe[len(fe)//2]
    p1=[r for r in fs if str(r['target_date'])[:10]<corte]
    p2=[r for r in fs if str(r['target_date'])[:10]>=corte]
    print(f"    mitades por fecha (corte {corte}): "
          f"1a {dif(en_banda(p1)):+.2f} pp (n={len(en_banda(p1))})   "
          f"2a {dif(en_banda(p2)):+.2f} pp (n={len(en_banda(p2))})")

    # PLACEBO: un ganador por grupo, sorteado ∝ p_mid
    if etq.startswith("particion"):
        gv={k:g[k] for k in VIVOS}
        peor=0; obs=dif(b); nrep=2000
        for _ in range(nrep):
            sim=[]
            for k,v in gv.items():
                s=sum(x["p_mid"] for x in v)
                w=[x["p_mid"]/s for x in v]
                idx=rng.choices(range(len(v)),weights=w,k=1)[0]
                for i,x in enumerate(v):
                    sim.append({"p_mid":x["p_mid"],"won":1.0 if i==idx else 0.0})
            d=dif(en_banda(sim))
            if d>=obs: peor+=1
        print(f"    PLACEBO (un ganador por grupo ∝ p_mid, {nrep} replicas): "
              f"p = {(peor+1)/(nrep+1):.4f}")
    print()
