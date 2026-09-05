"""V5.2 evaluación — consume V5_EXTRACT.json (f re-extraídos con D1) + Y de V3. Métricas y reglas
congeladas en PREREG_MODELSEL_V5.md (§5-§13). No se ejecuta hasta que la extracción esté completa."""
import json, math, random, collections, statistics as st, sys
from datetime import datetime, timedelta, timezone
from v5debias import debias
X=json.load(open('V5_EXTRACT.json'))
S={e['icao']:e for e in json.load(open('MODELSEL_GEOVAL_V3_SAMPLE.json'))}
N_EXPECTED=len({(r['icao'],r['run'],r['lead']) for r in json.load(open('MODELSEL_GEOVAL_V3_RAW.json'))
                if r['model'] in ('icon_seamless','ecmwf_ifs025') and r['run']})
if len(X)<N_EXPECTED:
    print(f"EXTRACCIÓN INCOMPLETA: {len(X)}/{N_EXPECTED}. No se evalúa."); sys.exit(2)
LMAX={"icon_seamless":4.76,"ecmwf_ifs025":8.78}
RES={"icon_d2":0.02,"icon_eu":0.0625,"icon_global":0.125,"ecmwf_ifs025":0.25}
def hav(a,b):
    R=6371.0;p1,p2=math.radians(a[0]),math.radians(b[0])
    return 2*R*math.asin(math.sqrt(math.sin((p2-p1)/2)**2+math.cos(p1)*math.cos(p2)*math.sin(math.radians(b[1]-a[1])/2)**2))
# --- filas planas por (event, icao, lead, model) ---
rows=[]
for k,r in X.items():
    for m in ("icon_seamless","ecmwf_ifs025"):
        if m not in r: continue
        d=r[m]; rt=datetime.fromisoformat(r['run'].replace("Z","+00:00"))
        td=datetime.fromisoformat(r['target_date']).replace(tzinfo=timezone.utc)
        rows.append(dict(event_id=r['event_id'],icao=r['icao'],city=r['city'],region=S[r['icao']]['region'],
            target_date=r['target_date'],lead=r['lead'],model=m,run=r['run'],
            age_h=round((12-r['lead'])-(rt-td).total_seconds()/3600,2),
            T=(td+timedelta(hours=12-r['lead'])).isoformat(),
            availability_safe_at=(rt+timedelta(hours=LMAX[m])).isoformat(),
            req_lat=r['req_lat'],req_lon=r['req_lon'],coord_source=r['coord_source'],
            cell_lat=d.get('cell_lat'),cell_lon=d.get('cell_lon'),
            dist_km=(hav((r['req_lat'],r['req_lon']),(d['cell_lat'],d['cell_lon'])) if d.get('cell_lat') is not None else None),
            f=d.get('f'),y=r['y'],cell_selection="land (defecto, no declarado)",
            component=(r.get('component') if m=='icon_seamless' else 'ecmwf_ifs025'),
            unknown_kind=(r.get('unknown_kind') if m=='icon_seamless' else None)))
E=[r for r in debias(rows) if r['evaluable']]
for r in E:
    r['resolution_deg']=RES.get(r['component']); r['residual_bruto']=r['f']-r['y']; r['residual_debiased']=r['residual']
json.dump(E,open('V5_DATASET.json','w'),indent=1)
excl=collections.Counter(r['motivo'] for r in debias(rows) if not r['evaluable'])
IDX={(r['event_id'],r['icao'],r['lead'],r['model']):r for r in E}
def strata(comp, lead=None):
    out=[]
    for r in E:
        if r['model']!='icon_seamless' or r['component']!=comp: continue
        if lead is not None and r['lead']!=lead: continue
        e=IDX.get((r['event_id'],r['icao'],r['lead'],'ecmwf_ifs025'))
        if e: out.append((r,e))
    return out
def mae(v): return sum(abs(x) for x in v)/len(v) if v else None
def rmse(v): return math.sqrt(sum(x*x for x in v)/len(v)) if v else None
def boot(pairs, nb=4000, seed=20260905):
    by=collections.defaultdict(list)
    for i,e in pairs: by[i['icao']].append((i,e))
    sts=sorted(by)
    if len(sts)<3: return None
    rnd=random.Random(seed); ds=[]
    for _ in range(nb):
        smp=[]
        for _ in range(len(sts)): smp+=by[sts[rnd.randrange(len(sts))]]
        ds.append(mae([a['residual'] for a,_ in smp])-mae([b['residual'] for _,b in smp]))
    ds.sort(); return (ds[int(.025*nb)], ds[int(.975*nb)])
def block(pairs,label):
    if not pairs: return None
    I=[a for a,_ in pairs]; Ec=[b for _,b in pairs]
    d=dict(label=label,n_obs=len(pairs),n_eventos=len({a['event_id'] for a in I}),n_est=len({a['icao'] for a in I}),
        regiones=sorted({a['region'] for a in I}),
        mae_bruto_icon=mae([a['residual_bruto'] for a in I]),mae_bruto_ecmwf=mae([b['residual_bruto'] for b in Ec]),
        mae_res_icon=mae([a['residual'] for a in I]),mae_res_ecmwf=mae([b['residual'] for b in Ec]),
        rmse_icon=rmse([a['residual'] for a in I]),rmse_ecmwf=rmse([b['residual'] for b in Ec]),
        bias_icon=st.mean([a['residual'] for a in I]),bias_ecmwf=st.mean([b['residual'] for b in Ec]))
    d['delta_mae_res']=d['mae_res_icon']-d['mae_res_ecmwf']; d['ic95']=boot(pairs)
    return d
def loso(pairs):
    sts=sorted({a['icao'] for a,_ in pairs})
    if len(sts)<3: return None
    base=block(pairs,'')['delta_mae_res']; out=[]
    for s in sts:
        q=[(a,b) for a,b in pairs if a['icao']!=s]; bb=block(q,'')
        out.append(dict(excluida=s,delta=bb['delta_mae_res'],cambia_signo=(bb['delta_mae_res']*base)<0))
    return dict(base=base,filas=out,algun_cambio=any(o['cambia_signo'] for o in out))
def clasif(b,l):
    if b is None: return None
    if b['n_est']<3: return "INCONCLUSO_POR_DISEÑO"
    if b['ic95'] and b['ic95'][0]<=0<=b['ic95'][1]: return "INCONCLUSO (IC incluye 0)"
    if l and l['algun_cambio']: return "INCONCLUSO (LOSO cambia signo)"
    return "CONCLUYENTE EN SU ESTRATO"
OUT={"n_extract":len(X),"exclusiones":dict(excl),"contrastes":{},"por_lead":{},"por_region":{},"loso":{},
     "regimen":{},"same_run":{},"frescura":{},"sensibilidad_OPKC":{}}
COMPS=["icon_d2","icon_eu","icon_global"]
for c in COMPS:
    p=strata(c); b=block(p,c); l=loso(p)
    OUT["contrastes"][c]=b; OUT["loso"][c]=l
    if b: b['clasificacion']=clasif(b,l)
    for L in (9,24):
        pl=strata(c,L); bl=block(pl,f"{c} {L}h"); ll=loso(pl)
        if bl: bl['clasificacion']=clasif(bl,ll)
        OUT["por_lead"][f"{c}|{L}h"]=bl
        ps=[(a,e) for a,e in pl if a['run']==e['run']]
        if ps: OUT["same_run"][f"{c}|{L}h"]=block(ps,f"{c} same-run {L}h")
        if pl: OUT["frescura"][f"{c}|{L}h"]=dict(n=len(pl),age_icon=st.mean([a['age_h'] for a,_ in pl]),age_ecmwf=st.mean([e['age_h'] for _,e in pl]))
        for reg in sorted({a['region'] for a,_ in pl}):
            pr=[(a,e) for a,e in pl if a['region']==reg]
            if len({a['icao'] for a,_ in pr})>=2: OUT["por_region"][f"{c}|{reg}|{L}h"]=block(pr,f"{c} {reg} {L}h")
    # sensibilidad pre-declarada (V5.2): con y sin OPKC
    if any(a['icao']=='OPKC' for a,_ in p):
        OUT["sensibilidad_OPKC"][c]=dict(con=block(p,c)['delta_mae_res'],sin=block([(a,e) for a,e in p if a['icao']!='OPKC'],c)['delta_mae_res'])
for c in COMPS+["ecmwf_ifs025"]:
    ds=sorted(r['dist_km'] for r in E if r['component']==c and r['dist_km'] is not None)
    if ds:
        q=lambda p: ds[min(len(ds)-1,int(p*len(ds)))]
        OUT["regimen"][c]=dict(n=len(ds),media=st.mean(ds),mediana=st.median(ds),p25=q(.25),p75=q(.75),resolucion_deg=RES.get(c))
OUT["recuento_componentes"]=dict(collections.Counter(r['component'] for r in E if r['model']=='icon_seamless'))
OUT["recuento_unknown"]=dict(collections.Counter(r['unknown_kind'] for r in E if r['model']=='icon_seamless' and r['component']=='UNKNOWN'))
cs=collections.defaultdict(set)
for r in E:
    if r['model']=='icon_seamless': cs[r['icao']].add(r['component'])
OUT["composicion_por_estacion"]={k:sorted(v) for k,v in sorted(cs.items())}; OUT["inestables"]=[k for k,v in cs.items() if len(v)>1]
json.dump(OUT,open('V5_EVAL.json','w'),indent=1,default=str)
print("V5_EVAL.json escrito. contrastes:",{c:(b['clasificacion'] if b else None) for c,b in OUT['contrastes'].items()})
