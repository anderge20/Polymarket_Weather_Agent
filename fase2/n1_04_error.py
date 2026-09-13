"""NIVEL 1 §1+§4 — auditoria descriptiva del forecast y su error. EGLC.

Pareja = (target_date, lead). El forecast es el MAS RECIENTE con available_at <= t_asof.
Descriptivo IN-SAMPLE: no es un modelo, es el inventario de lo que hay.
"""
import duckdb, datetime as dt, statistics as st, math
DB="/Users/mariaaleu/workspace/Polymarket_Weather_Agent/data/pmw.duckdb"
con=duckdb.connect(DB, read_only=True); con.execute("SET TimeZone='UTC'")

fc=con.execute("""SELECT target_date, issue_time, available_at, forecast_tmax,
                         forecast_p10, forecast_p25, forecast_p50, forecast_p75, forecast_p90
                  FROM weather_forecasts WHERE station='EGLC' ORDER BY target_date, issue_time""").fetchall()
# DIA LOCAL DE LONDRES, no la fecha UTC. `CAST(observation_time AS DATE)` colisiona
# dos veces en EGLC —los maximos de 00:50 local caen en el dia UTC anterior— y en las
# dos el dia siguiente sobrescribia al real: 05-03 perdia 20,0 y quedaba 15,0; 05-26
# perdia 34,0 y quedaba 24,0. Lo encontro la sesion B revisando A-237.
from zoneinfo import ZoneInfo as _Z
obs={}
for _t,_v in con.execute("""SELECT observation_time, observed_value
                            FROM weather_observations WHERE station='EGLC'""").fetchall():
    obs[_t.astimezone(_Z("Europe/London")).date()] = _v
def tasof(td, lead): return dt.datetime.combine(td, dt.time(12), dt.timezone.utc) - dt.timedelta(hours=lead)

pares={}
for lead in (24, 9):
    for td, iss, av, tmax, p10,p25,p50,p75,p90 in fc:
        if av > tasof(td, lead): continue
        k=(td, lead)
        if k not in pares or av > pares[k][0]:
            pares[k]=(av, iss, tmax, p10,p25,p50,p75,p90)

print("=== §1 INVENTARIO (EGLC)")
print(f"   dias con forecast            {len({td for td,_,_,_,_,_,_,_,_ in fc})}")
print(f"   filas de forecast            {len(fc)}   (2 emisiones por dia: 06z y 18z del dia anterior)")
print(f"   dias con observacion         {len(obs)}")
print(f"   pares (dia, lead) formables  {len(pares)}")
for lead in (24,9):
    ks=[k for k in pares if k[1]==lead]
    con_obs=[k for k in ks if k[0] in obs]
    print(f"     lead {lead:2d}h: {len(ks)} pares, {len(con_obs)} con observacion")

print("\n=== §4 ERROR DEL FORECAST   (error = observado - forecast)")
def resumen(vs):
    vs=sorted(vs); n=len(vs)
    return dict(n=n, bias=st.mean(vs), mae=st.mean(abs(v) for v in vs),
                rmse=math.sqrt(st.mean(v*v for v in vs)),
                medae=st.median([abs(v) for v in vs]), sd=st.pstdev(vs),
                p05=vs[int(.05*n)], p95=vs[int(.95*n)])
tab={}
for lead in (24,9):
    e=[obs[td]-p[2] for (td,l),p in pares.items() if l==lead and td in obs]
    tab[lead]=resumen(e)
    r=tab[lead]
    print(f"   lead {lead:2d}h  n={r['n']:3d}  bias {r['bias']:+.3f}  MAE {r['mae']:.3f}  RMSE {r['rmse']:.3f}"
          f"  MedAE {r['medae']:.3f}  sd {r['sd']:.3f}  [p05 {r['p05']:+.1f}, p95 {r['p95']:+.1f}]")

print("\n=== §4 COBERTURA DE INTERVALOS   (¿cae el observado dentro?)")
for lead in (24,9):
    ps=[(obs[td], p) for (td,l),p in pares.items()
        if l==lead and td in obs and p[3] is not None and p[7] is not None]
    n=len(ps)
    for etq,(a,b),nom in ((" p10-p90 (80%)",(3,7),80), (" p25-p75 (50%)",(4,6),50)):
        c=sum(1 for o,p in ps if p[a] <= o <= p[b])
        print(f"   lead {lead:2d}h {etq}: {c}/{n} = {100*c/n:5.1f} %   (nominal {nom} %)")
    anch=[p[7]-p[3] for _,p in ps]
    print(f"   lead {lead:2d}h  anchura p90-p10: mediana {st.median(anch):.2f} C  media {st.mean(anch):.2f} C")

print("\n   NOTA §10: forecast_p10..p90 NO son incertidumbre nativa del modelo")
print("   meteorologico. Las escribe fit_m2.py: son NUESTRO modelo de error M2")
print("   sumado al pronostico puntual. El modelo solo nos da forecast_tmax.")
print("   Por tanto esta cobertura mide la calibracion de M2, no la del tiempo.")

print("\n=== §4 ERROR POR MES")
print(f"   {'mes':8s} {'lead':>5s} {'n':>4s} {'bias':>7s} {'MAE':>6s} {'RMSE':>6s}")
for lead in (24,9):
    por={}
    for (td,l),p in pares.items():
        if l!=lead or td not in obs: continue
        por.setdefault(td.strftime('%Y-%m'), []).append(obs[td]-p[2])
    for m in sorted(por):
        r=resumen(por[m]); print(f"   {m:8s} {lead:5d} {r['n']:4d} {r['bias']:+7.3f} {r['mae']:6.3f} {r['rmse']:6.3f}")
