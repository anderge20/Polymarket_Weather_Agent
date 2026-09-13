"""NIVEL 1 §6+§7+§14+§15 — forecast -> P(settlement), walk-forward, contra baselines.

PREINSCRIPCION (escrita antes de ejecutar):
  Unidad        (target_date, lead). Brier por banda, promediado DENTRO del evento y
                luego sobre eventos. Nunca las bandas como observaciones sueltas.
  Entrenamiento solo dias cuya ETIQUETA estaba disponible en t_asof del evento
                (fin del dia local + 24 h). Ventana expansiva. Minimo 20 pares.
  Modelos       B0 climatologia 30d · B1 persistencia · B2 forecast crudo
                B3 forecast + error empirico · B4 forecast bias-corregido + error
  CONFIRMA (nivel B): B3 o B4 mejoran a B0 en Brier por evento con IC95 bootstrap
                por evento que EXCLUYE el cero, EN LOS DOS LEADS.
  REFUTA: el intervalo incluye el cero en cualquiera de los dos leads.
  No se elige lead ni modelo despues de mirar: se reportan los cinco.
"""
import duckdb, datetime as dt, statistics as st, math, random, sys, re
from zoneinfo import ZoneInfo
sys.path.insert(0, "/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-main/src")
from weather_agent.polymarket.resolution import parse_band

DB="/Users/mariaaleu/workspace/Polymarket_Weather_Agent/data/pmw.duckdb"
LON=ZoneInfo("Europe/London")
con=duckdb.connect(DB, read_only=True); con.execute("SET TimeZone='UTC'")

obs={t.astimezone(LON).date(): v for t,v in con.execute(
    "SELECT observation_time, observed_value FROM weather_observations WHERE station='EGLC'").fetchall()}
def tasof(td,l): return dt.datetime.combine(td, dt.time(12), dt.timezone.utc)-dt.timedelta(hours=l)
def label_av(td):
    return dt.datetime.combine(td+dt.timedelta(days=1), dt.time(0), LON).astimezone(dt.timezone.utc)+dt.timedelta(hours=24)

FC={}
for td,av,tm in con.execute("""SELECT target_date, available_at, forecast_tmax FROM weather_forecasts
                               WHERE station='EGLC' ORDER BY target_date, issue_time""").fetchall():
    for l in (24,9):
        if av<=tasof(td,l) and (l not in (24,9) or (td,l) not in FC or av>FC[(td,l)][0]):
            FC[(td,l)]=(av,tm)

# eventos: dia -> bandas del mercado, con su (lo,hi) y si gano
EV={}
for mid,tok,band,out,win in con.execute("""SELECT m.market_id, o.token_id, o.band_label, o.outcome_label,
                                                  m.winning_outcome
                                           FROM markets m JOIN outcomes o ON o.market_id=m.market_id
                                           WHERE m.station_identifier='EGLC'
                                             AND m.uma_resolution_status='resolved'
                                             AND o.band_label IS NOT NULL
                                             AND o.outcome_label='Yes'""").fetchall():
    lo,hi=parse_band(band,'C')
    EV.setdefault(mid,{})['band']=(lo,hi); EV[mid]['won']= (str(win).strip().lower()=='yes')
# el dia del evento sale del target_date del mercado via su end_date; lo tomamos de los candidatos
import json
cand=json.load(open('/Users/mariaaleu/pmw-e2/LONDON_CANDIDATES.json'))
dia_de={r['market_id']: dt.date.fromisoformat(r['fecha']) for r in cand}
eventos={}
for mid,d in EV.items():
    td=dia_de.get(mid)
    if td is None or td not in obs: continue
    eventos.setdefault(td, []).append((d['band'][0], d['band'][1], d['won']))
print(f"eventos reconstruidos: {len(eventos)}   bandas: {sum(len(v) for v in eventos.values())}")

def masa_desde_errores(f, errs, lo, hi):
    """P(banda) = fraccion de errores pasados que llevan el forecast dentro de la banda,
    tras redondear al grado que liquida."""
    n=0
    for e in errs:
        g=round(f+e)
        if (lo is None or g>=lo) and (hi is None or g<=hi): n+=1
    return n/len(errs)

def evaluar(lead, minimo=20):
    filas=[]
    for td in sorted(eventos):
        if (td,lead) not in FC: continue
        t=tasof(td,lead); f=FC[(td,lead)][1]
        # entrenamiento: dias con etiqueta disponible en t
        tr=[(d, obs[d], FC[(d,lead)][1]) for d in sorted(obs)
            if label_av(d)<=t and (d,lead) in FC]
        if len(tr)<minimo: continue
        errs=[o-fx for _,o,fx in tr]
        bias=st.mean(errs)
        hist=[o for _,o,_ in tr[-30:]]                     # climatologia 30d
        ayer=[o for d,o,_ in tr if d==td-dt.timedelta(days=1)]
        pers=ayer[0] if ayer else tr[-1][1]
        for lo,hi,won in eventos[td]:
            dentro=lambda g: (lo is None or g>=lo) and (hi is None or g<=hi)
            p={}
            p['B0_clima30']   = sum(1 for o in hist if dentro(round(o)))/len(hist)
            p['B1_persist']   = 1.0 if dentro(round(pers)) else 0.0
            p['B2_fc_crudo']  = 1.0 if dentro(round(f))    else 0.0
            p['B3_fc_error']  = masa_desde_errores(f, errs, lo, hi)
            p['B4_fc_bias']   = masa_desde_errores(f-bias, [e-bias for e in errs], lo, hi)
            filas.append((td, won, p))
    return filas

def brier_por_evento(filas, modelo):
    por={}
    for td,won,p in filas:
        q=min(max(p[modelo],1e-6),1-1e-6)
        por.setdefault(td,[]).append((q-(1.0 if won else 0.0))**2)
    return {td: st.mean(v) for td,v in por.items()}

MODELOS=['B0_clima30','B1_persist','B2_fc_crudo','B3_fc_error','B4_fc_bias']

def calibracion(filas, m):
    """pendiente e intercepto de la recta observado ~ a + b*p, por BANDA (descriptivo)."""
    xs=[min(max(p[m],1e-6),1-1e-6) for _,_,p in filas]; ys=[1.0 if w else 0.0 for _,w,_ in filas]
    mx=st.mean(xs); my=st.mean(ys)
    sxx=sum((x-mx)**2 for x in xs)
    b=sum((x-mx)*(y-my) for x,y in zip(xs,ys))/sxx if sxx else float('nan')
    return b, my-b*mx, st.pstdev(xs)

def fiabilidad(filas, m, bordes=(0,.05,.15,.30,.60,1.01)):
    out=[]
    for i in range(len(bordes)-1):
        s_=[(p[m], 1.0 if w else 0.0) for _,w,p in filas if bordes[i]<=p[m]<bordes[i+1]]
        if s_: out.append((bordes[i],bordes[i+1],len(s_),st.mean(x for x,_ in s_),st.mean(y for _,y in s_)))
    return out
random.seed(20260913)
for lead in (24,9):
    filas=evaluar(lead)
    evs=sorted({td for td,_,_ in filas})
    print(f"\n=== lead {lead}h   eventos evaluados {len(evs)}   bandas {len(filas)}"
          f"   ({evs[0]} .. {evs[-1]})" if evs else f"\n=== lead {lead}h  sin datos")
    if not evs: continue
    B={m: brier_por_evento(filas,m) for m in MODELOS}
    print(f"   {'modelo':14s} {'Brier/evento':>12s}")
    for m in MODELOS:
        print(f"   {m:14s} {st.mean(B[m].values()):12.5f}")
    print(f"\n   contra B0 (climatologia), diferencia pareada por evento  (negativo = MEJOR que B0)")
    for m in MODELOS[1:]:
        d=[B[m][td]-B['B0_clima30'][td] for td in evs]
        n=len(d); reps=sorted(st.mean(random.choices(d,k=n)) for _ in range(10000))
        lo_,hi_=reps[250],reps[9750]
        marca="  EXCLUYE el cero" if lo_*hi_>0 else "  incluye el cero"
        print(f"   {m:14s} {st.mean(d):+9.5f}   IC95 [{lo_:+.5f}, {hi_:+.5f}]{marca}")

    print(f"\n   §7 CALIBRACION (por banda, descriptivo)   pendiente 1 e intercepto 0 = perfecta")
    print(f"   {'modelo':14s} {'pendiente':>10s} {'intercepto':>11s} {'sd(p)=sharpness':>16s}")
    for m in MODELOS:
        b,a,sd=calibracion(filas,m); print(f"   {m:14s} {b:10.3f} {a:+11.4f} {sd:16.4f}")
    print(f"\n   §7 FIABILIDAD de B3_fc_error")
    print(f"   {'tramo':16s} {'n':>5s} {'p medio':>9s} {'real':>8s}")
    for lo_,hi_,n_,pm,re_ in fiabilidad(filas,'B3_fc_error'):
        print(f"   [{lo_:.2f}, {hi_:.2f}){'':4s} {n_:5d} {pm:9.4f} {re_:8.4f}")

    print(f"\n   §18 ESTABILIDAD TEMPORAL (Brier por evento, por mes)")
    print(f"   {'mes':9s} {'n ev':>5s} " + " ".join(f"{m.split('_')[0]:>8s}" for m in MODELOS))
    meses=sorted({td.strftime('%Y-%m') for td,_,_ in filas})
    for mes in meses:
        ev_m=sorted({td for td,_,_ in filas if td.strftime('%Y-%m')==mes})
        fila=f"   {mes:9s} {len(ev_m):5d} "
        for m in MODELOS:
            fila+=f" {st.mean(B[m][td] for td in ev_m):8.5f}"
        print(fila)
