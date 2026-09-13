import json, statistics, math, random
from collections import defaultdict
rows = json.load(open('/Users/mariaaleu/pmw-e2/LONDON_CANDIDATES.json'))
g = defaultdict(list)
for r in rows: g[(r['fecha'], r['lead_h'])].append(r)
vivos = {k: v for k, v in g.items() if sum(x['p_mid'] for x in v) >= 0.50}

un=[]
for k,v in vivos.items():
    ws=[r for r in v if r['won']]
    if len(ws)==1 and len(v)>=2: un.append((k,v,ws[0]))
n=len(un)

def midrank_and_top(v, win, key):
    """rango medio del ganador con EMPATES a mid-rank; acierto top-1 fraccionado 1/k."""
    vals=sorted((r[key] for r in v), reverse=True)
    w=win[key]
    better=sum(1 for x in vals if x>w); ties=sum(1 for x in vals if x==w)
    rank = better + (ties+1)/2.0
    top_val=vals[0]; ktop=sum(1 for x in vals if x==top_val)
    hit = (1.0/ktop) if w==top_val else 0.0
    return rank, hit, ties

R={}
for key in ('p_mid','p_model'):
    ranks=[]; hits=[]; tied=[]
    for k,v,win in un:
        r,h,t=midrank_and_top(v,win,key); ranks.append(r); hits.append(h); tied.append(t)
    R[key]=(ranks,hits,tied)
    print(f"{key:8s}  top-1 fraccionado {sum(hits):6.2f}/{n} = {100*sum(hits)/n:5.1f} %   rango medio del ganador {statistics.mean(ranks):.3f}   grupos donde el ganador esta empatado: {sum(1 for t in tied if t>1)}")

print(f"\nbandas por grupo (media) {statistics.mean(len(v) for _,v,_ in un):.2f}  -> rango esperado por azar {statistics.mean((len(v)+1)/2 for _,v,_ in un):.3f}")

# test pareado por grupo sobre el rango del ganador: permutacion de signos
d=[R['p_model'][0][i]-R['p_mid'][0][i] for i in range(n)]   # >0 = el mercado ordena mejor
obs=statistics.mean(d)
random.seed(20260913)
B=200000; cnt=0
for _ in range(B):
    s=sum(x if random.random()<0.5 else -x for x in d)/n
    if abs(s)>=abs(obs)-1e-15: cnt+=1
print(f"\ndiferencia media de rango (modelo - mercado) = {obs:+.3f}  (>0 = mercado mejor)")
print(f"permutacion de signos pareada, {B} replicas: p = {(cnt+1)/(B+1):.5f}")
nz=[x for x in d if x!=0]
pos=sum(1 for x in nz if x>0)
pb=sum(math.comb(len(nz),i) for i in range(0,min(pos,len(nz)-pos)+1))/2**len(nz)*2
print(f"signo: mercado mejor en {pos}/{len(nz)} grupos no empatados  (binomial bilateral p = {min(1.0,pb):.4g})")

# top-1 fraccionado, mismo test pareado
dh=[R['p_mid'][1][i]-R['p_model'][1][i] for i in range(n)]
obsh=statistics.mean(dh); cnt=0
for _ in range(B):
    s=sum(x if random.random()<0.5 else -x for x in dh)/n
    if abs(s)>=abs(obsh)-1e-15: cnt+=1
print(f"\ntop-1 fraccionado, diferencia media (mercado - modelo) = {obsh:+.4f}   p = {(cnt+1)/(B+1):.5f}")

# cuanto pesa el cero duro: grupos donde el ganador cae en p_model == 0
z=[(k,win) for k,v,win in un if win['p_model']==0.0]
print(f"\ngrupos cuyo ganador tiene p_model == 0 exacto: {len(z)}")
allz=sum(1 for k,v,win in un for r in v if r['p_model']==0.0)
print(f"filas con p_model == 0 exacto en los grupos usables: {allz} de {sum(len(v) for _,v,_ in un)}")
