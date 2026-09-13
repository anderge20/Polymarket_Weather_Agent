"""NIVEL 1 §3 — que predice el forecast y que determina el settlement."""
import duckdb, json
DB="/Users/mariaaleu/workspace/Polymarket_Weather_Agent/data/pmw.duckdb"
con=duckdb.connect(DB, read_only=True); con.execute("SET TimeZone='UTC'")

print("=== §3.1 QUE PREDICE EL FORECAST")
print("   columna: weather_forecasts.forecast_tmax")
print("   ventana: weather.target_day_window(target_date, tz) = dia civil LOCAL de la estacion")
print("   naturaleza: maximo diario CONTINUO de un modelo (icon_seamless), en C")

print("\n=== §3.2 QUE DETERMINA EL SETTLEMENT")
r=con.execute("""SELECT unit, rounding_rule, count(*) FROM markets
                 WHERE station_identifier='EGLC' GROUP BY 1,2 ORDER BY 3 DESC""").fetchall()
for u,rr,n in r: print(f"   unit={u!r}  rounding_rule={rr!r}  x{n}")
print("   operador (nucleo congelado): NOAA_TEMPCOL_C_PROXY_IEM")
print("     required_series = metar_body_c · window = LOCAL_CIVIL_DAY · quantization = whole degree")
print("   => maximo de los METAR RUTINARIOS (horarios) del dia civil local, en grados ENTEROS")

print("\n=== §3.3 LOS DOS ESTIMANDOS NO SON EL MISMO")
print("   forecast    : maximo CONTINUO del dia  (el modelo no muestrea)")
print("   settlement  : maximo de una MUESTRA HORARIA, cuantizado a grado entero")
print("   consecuencia: el maximo muestreado es <= el maximo verdadero por construccion.")
print("                 El sesgo no es simetrico y no se puede corregir con una constante.")

print("\n=== §3.4 BANDAS: como se convierte una temperatura en YES/NO")
for r in con.execute("""SELECT o.band_label, count(*) FROM markets m JOIN outcomes o ON o.market_id=m.market_id
                        WHERE m.station_identifier='EGLC' GROUP BY 1 ORDER BY 2 DESC LIMIT 8""").fetchall():
    print(f"   {r[0]!r:22s} x{r[1]}")
n=con.execute("""SELECT count(DISTINCT o.band_label) FROM markets m JOIN outcomes o ON o.market_id=m.market_id
                 WHERE m.station_identifier='EGLC'""").fetchone()[0]
print(f"   bandas distintas: {n}")
print("\n=== §3.5 la observacion que usamos")
print("   weather_observations.observed_value para EGLC: serie IEM_ASOS_METAR_1C, unit C")
r=con.execute("""SELECT count(*), min(observed_value), max(observed_value),
                        sum(CASE WHEN observed_value = round(observed_value) THEN 1 ELSE 0 END)
                 FROM weather_observations WHERE station='EGLC'""").fetchone()
print(f"   n={r[0]}  rango {r[1]} .. {r[2]}  en grado entero: {r[3]} de {r[0]}")
print("   procedencia: fetch_metar pide data=tmpf a IEM y convierte con f_to_c;")
print("   detect_grid la ajusta a la rejilla de 1 C de la estacion o marca UNKNOWN.")
