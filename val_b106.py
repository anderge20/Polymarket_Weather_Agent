import json, statistics, math
from collections import defaultdict
rows = json.load(open('/Users/mariaaleu/pmw-e2/LONDON_CANDIDATES.json'))

# libro vivo: grupos (fecha, lead_h) con sum(p_mid) >= 0.50
g = defaultdict(list)
for r in rows: g[(r['fecha'], r['lead_h'])].append(r)
vivos = {k: v for k, v in g.items() if sum(x['p_mid'] for x in v) >= 0.50}
pop = [r for k in vivos for r in vivos[k]]
print(f"grupos totales {len(g)}  vivos {len(vivos)}  filas vivas {len(pop)}")

BANDS = [(0.0,0.05),(0.05,0.15),(0.15,0.30),(0.30,0.60),(0.60,1.01)]
def band(p):
    for i,(a,b) in enumerate(BANDS):
        if a <= p < b: return i
    return len(BANDS)-1

def corr(xs, ys):
    n=len(xs)
    if n<2: return float('nan')
    mx,my=sum(xs)/n,sum(ys)/n
    sx=math.sqrt(sum((x-mx)**2 for x in xs)); sy=math.sqrt(sum((y-my)**2 for y in ys))
    if sx==0 or sy==0: return float('nan')
    return sum((x-mx)*(y-my) for x,y in zip(xs,ys))/(sx*sy)

for key,lab in (('p_model','p_model'),('p_mid','p_mid')):
    print(f"\n--- DENTRO de bandas de {lab}: corr con won")
    print(f"{'banda':16s} {'n':>5s} {'corr(p_mid,won)':>16s} {'corr(p_model,won)':>18s} {'sd(p_model)':>12s} {'sd(p_mid)':>10s}")
    for i,(a,b) in enumerate(BANDS):
        sub=[r for r in pop if band(r[key])==i]
        if not sub: continue
        w=[1.0 if r['won'] else 0.0 for r in sub]
        pm=[r['p_mid'] for r in sub]; pmo=[r['p_model'] for r in sub]
        sd=lambda v: statistics.pstdev(v) if len(v)>1 else 0.0
        print(f"[{a:.2f},{b:.2f})".ljust(16)+f" {len(sub):5d} {corr(pm,w):16.3f} {corr(pmo,w):18.3f} {sd(pmo):12.4f} {sd(pm):10.4f}")

# ¿es p_model constante en la banda baja?
low=[r['p_model'] for r in pop if band(r['p_model'])==0]
print(f"\nbanda [0,0.05) de p_model: n={len(low)} min={min(low):.6g} max={max(low):.6g} distintos={len(set(round(x,12) for x in low))}")
w_low=sum(1 for r in pop if band(r['p_model'])==0 and r['won'])
print(f"  ganadores reales en esa banda: {w_low}  ({100*w_low/len(low):.2f} %)")

# ---- TEST G (preinscrito): resolucion a nivel de grupo (fecha, lead_h) ----
print("\n=== TEST G: ordenacion a nivel de grupo (unidad = (fecha, lead_h)) ===")
un=[]; nwin=defaultdict(int)
for k,v in vivos.items():
    ws=[r for r in v if r['won']]
    nwin[len(ws)]+=1
    if len(ws)!=1 or len(v)<2: continue
    un.append((k,v,ws[0]))
print("grupos vivos por numero de ganadores:", dict(sorted(nwin.items())))
print(f"grupos usables (exactamente 1 ganador y >=2 bandas): {len(un)}")

def rank_of(v, win, key):
    order=sorted(v, key=lambda r: -r[key])
    return order.index(win)+1, order[0] is win
hit_mid=hit_mod=0; b_only=0; m_only=0; ranks_mid=[]; ranks_mod=[]
for k,v,win in un:
    rmid,hmid=rank_of(v,win,'p_mid'); rmod,hmod=rank_of(v,win,'p_model')
    hit_mid+=hmid; hit_mod+=hmod; ranks_mid.append(rmid); ranks_mod.append(rmod)
    if hmid and not hmod: b_only+=1
    if hmod and not hmid: m_only+=1
n=len(un)
print(f"acierto top-1 mercado : {hit_mid}/{n} = {100*hit_mid/n:.1f} %")
print(f"acierto top-1 modelo  : {hit_mod}/{n} = {100*hit_mod/n:.1f} %")
print(f"discordantes: solo mercado {b_only}, solo modelo {m_only}")
d=b_only+m_only
if d:
    p=sum(math.comb(d,i) for i in range(0,min(b_only,m_only)+1))/2**d*2
    print(f"McNemar exacto bilateral sobre {d} discordantes: p = {min(1.0,p):.4g}")
print(f"rango medio del ganador  mercado {statistics.mean(ranks_mid):.3f}  modelo {statistics.mean(ranks_mod):.3f}  (mas bajo = mejor)")
print(f"bandas por grupo (media) {statistics.mean(len(v) for _,v,_ in un):.2f}")
