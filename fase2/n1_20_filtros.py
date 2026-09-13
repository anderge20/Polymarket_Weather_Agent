"""NIVEL 1 — reejecucion con EXCLUSION POR INTEGRIDAD DE DATOS (no seleccion de modelo).

El hallazgo de B: 74 de 115 eventos EGLC no tienen banda ganadora en el almacen.
El Brier por evento sobre bandas lejanas todas con verdad 0 omite el unico termino
que importa, (q_verdadera - 1)^2. Aqui se reejecuta lo mismo sobre tres poblaciones.
"""
import duckdb, datetime as dt, statistics as st, random, sys, json
from zoneinfo import ZoneInfo
sys.path.insert(0,"/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-main/src")
from weather_agent.polymarket.resolution import parse_band
LON=ZoneInfo("Europe/London")
con=duckdb.connect("/Users/mariaaleu/workspace/Polymarket_Weather_Agent/data/pmw.duckdb", read_only=True)
con.execute("SET TimeZone='UTC'")
obs={t.astimezone(LON).date(): v for t,v in con.execute(
  "SELECT observation_time, observed_value FROM weather_observations WHERE station='EGLC'").fetchall()}
def tasof(td,l): return dt.datetime.combine(td, dt.time(12), dt.timezone.utc)-dt.timedelta(hours=l)
def label_av(td): return dt.datetime.combine(td+dt.timedelta(days=1), dt.time(0), LON).astimezone(dt.timezone.utc)+dt.timedelta(hours=24)
FC={}
for td,av,tm in con.execute("""SELECT target_date, available_at, forecast_tmax FROM weather_forecasts
                               WHERE station='EGLC' ORDER BY target_date, issue_time""").fetchall():
    for l in (24,9):
        if av<=tasof(td,l) and ((td,l) not in FC or av>FC[(td,l)][0]): FC[(td,l)]=(av,tm)
dia={r['market_id']: dt.date.fromisoformat(r['fecha']) for r in json.load(open('/Users/mariaaleu/pmw-e2/LONDON_CANDIDATES.json'))}
eventos={}
for mid,b,w in con.execute("""SELECT m.market_id, o.band_label, m.winning_outcome
      FROM markets m JOIN outcomes o ON o.market_id=m.market_id
      WHERE m.station_identifier='EGLC' AND m.uma_resolution_status='resolved'
        AND o.band_label IS NOT NULL AND o.outcome_label='Yes'""").fetchall():
    td=dia.get(mid)
    if td is None or td not in obs: continue
    lo,hi=parse_band(b,'C'); eventos.setdefault(td,[]).append((lo,hi,str(w).strip().lower()=='yes'))

def particion(bs):
    if not any(w for _,_,w in bs): return False
    ab=[x for x in bs if x[0] is None]; ar=[x for x in bs if x[1] is None]
    if len(ab)!=1 or len(ar)!=1: return False
    cer=sorted(int(a) for a,b,_ in bs if a is not None and b is not None and a==b)
    return cer==list(range(int(ab[0][1])+1, int(ar[0][0])))

def masa(f, errs, lo, hi):
    return sum(1 for e in errs if (lo is None or round(f+e)>=lo) and (hi is None or round(f+e)<=hi))/len(errs)

MOD=['B0_clima30','B2_fc_crudo','B3_fc_error','B4_fc_bias']
def corre(lead, filtro):
    filas=[]
    for td in sorted(eventos):
        bs=eventos[td]
        if filtro=='con_ganadora' and not any(w for _,_,w in bs): continue
        if filtro=='particion' and not particion(bs): continue
        if (td,lead) not in FC: continue
        t=tasof(td,lead); f=FC[(td,lead)][1]
        tr=[(d,obs[d],FC[(d,lead)][1]) for d in sorted(obs) if label_av(d)<=t and (d,lead) in FC]
        if len(tr)<20: continue
        errs=[o-fx for _,o,fx in tr]; bias=st.mean(errs); hist=[o for _,o,_ in tr[-30:]]
        for lo,hi,won in bs:
            dentro=lambda g:(lo is None or g>=lo) and (hi is None or g<=hi)
            filas.append((td,won,{'B0_clima30':sum(1 for o in hist if dentro(round(o)))/len(hist),
                                  'B2_fc_crudo':1.0 if dentro(round(f)) else 0.0,
                                  'B3_fc_error':masa(f,errs,lo,hi),
                                  'B4_fc_bias':masa(f-bias,[e-bias for e in errs],lo,hi)}))
    return filas
def brier(filas,m):
    d={}
    for td,w,p in filas: d.setdefault(td,[]).append((min(max(p[m],1e-6),1-1e-6)-(1.0 if w else 0.0))**2)
    return {td:st.mean(v) for td,v in d.items()}

random.seed(20260913)
for filtro,etq in (('todos','TODOS (mi resultado original)'),
                   ('con_ganadora','solo eventos CON banda ganadora'),
                   ('particion','PARTICION completa + ganadora')):
    print(f"\n{'='*72}\n{etq}\n{'='*72}")
    for lead in (24,9):
        filas=corre(lead,filtro); evs=sorted({td for td,_,_ in filas})
        if not evs: print(f"  lead {lead}: sin eventos"); continue
        B={m:brier(filas,m) for m in MOD}
        print(f"  lead {lead:2d}h  n eventos {len(evs):3d}  bandas {len(filas):4d}   "
              f"B0 {st.mean(B['B0_clima30'].values()):.5f}  B2 {st.mean(B['B2_fc_crudo'].values()):.5f}  "
              f"B3 {st.mean(B['B3_fc_error'].values()):.5f}")
        for m in ('B2_fc_crudo','B3_fc_error'):
            d=[B[m][td]-B['B0_clima30'][td] for td in evs]; n=len(d)
            r=sorted(st.mean(random.choices(d,k=n)) for _ in range(10000))
            lo_,hi_=r[250],r[9750]
            print(f"      {m:12s} - B0: {st.mean(d):+8.5f}  IC95 [{lo_:+.5f}, {hi_:+.5f}]"
                  f"  {'EXCLUYE' if lo_*hi_>0 else 'INCLUYE EL CERO'}")
