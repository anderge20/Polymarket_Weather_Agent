"""NIVEL 1 §9 — ¿de que depende el error?  Descriptivo, in-sample."""
import duckdb, datetime as dt, statistics as st, math
DB="/Users/mariaaleu/workspace/Polymarket_Weather_Agent/data/pmw.duckdb"
con=duckdb.connect(DB, read_only=True); con.execute("SET TimeZone='UTC'")
fc=con.execute("""SELECT target_date, available_at, forecast_tmax, forecast_p10, forecast_p90
                  FROM weather_forecasts WHERE station='EGLC' ORDER BY target_date, issue_time""").fetchall()
obs={r[0]: r[1] for r in con.execute("""SELECT CAST(observation_time AS DATE), observed_value
                                        FROM weather_observations WHERE station='EGLC'""").fetchall()}
def tasof(td,l): return dt.datetime.combine(td, dt.time(12), dt.timezone.utc)-dt.timedelta(hours=l)
P={}
for lead in (24,9):
    for td,av,tm,p10,p90 in fc:
        if av<=tasof(td,lead) and (td,lead) not in P or (av<=tasof(td,lead) and av>P.get((td,lead),(dt.datetime.min.replace(tzinfo=dt.timezone.utc),))[0]):
            if av<=tasof(td,lead): P[(td,lead)]=(av,tm,p10,p90)
def corr(xs,ys):
    n=len(xs); mx=st.mean(xs); my=st.mean(ys)
    sx=math.sqrt(sum((x-mx)**2 for x in xs)); sy=math.sqrt(sum((y-my)**2 for y in ys))
    return sum((x-mx)*(y-my) for x,y in zip(xs,ys))/(sx*sy) if sx and sy else float('nan')

for lead in (24,9):
    d=[(P[(td,lead)][1], obs[td]-P[(td,lead)][1], P[(td,lead)][3], P[(td,lead)][2], td)
       for td in obs if (td,lead) in P]
    print(f"\n=== lead {lead}h   n={len(d)}")
    print(f"   corr(forecast, error)      {corr([x[0] for x in d],[x[1] for x in d]):+.3f}")
    print(f"   corr(forecast, |error|)    {corr([x[0] for x in d],[abs(x[1]) for x in d]):+.3f}")
    anch=[(x[2]-x[3]) for x in d if x[2] is not None and x[3] is not None]
    err =[abs(x[1])   for x in d if x[2] is not None and x[3] is not None]
    print(f"   corr(anchura p90-p10, |error|)  {corr(anch,err):+.3f}   <- ¿la incertidumbre declarada predice el error?")
    print(f"   {'tramo de forecast':22s} {'n':>4s} {'bias':>7s} {'MAE':>6s} {'RMSE':>6s}")
    for lo,hi in ((0,15),(15,20),(20,25),(25,40)):
        s=[x[1] for x in d if lo<=x[0]<hi]
        if len(s)<5: print(f"   [{lo:2d}, {hi:2d}) C{'':11s} {len(s):4d}   (n<5)"); continue
        print(f"   [{lo:2d}, {hi:2d}) C{'':11s} {len(s):4d} {st.mean(s):+7.3f} {st.mean(abs(v) for v in s):6.3f} {math.sqrt(st.mean(v*v for v in s)):6.3f}")
