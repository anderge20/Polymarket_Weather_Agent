"""NIVEL 1 §2 — temporalidad del forecast y sensibilidad a L_MAX.

Reproducible: python3 n1_02_temporalidad.py
Lee data/pmw.duckdb en modo SOLO LECTURA. No escribe nada.
"""
import duckdb, datetime as dt, sys
DB = "/Users/mariaaleu/workspace/Polymarket_Weather_Agent/data/pmw.duckdb"
con = duckdb.connect(DB, read_only=True); con.execute("SET TimeZone='UTC'")

filas = con.execute("""
  SELECT target_date, issue_time, available_at, forecast_tmax
  FROM weather_forecasts WHERE station='EGLC' ORDER BY target_date, issue_time""").fetchall()

print("=== §2.1 La asuncion, medida sobre las filas")
desf = {round((av-iss).total_seconds()/3600, 4) for _,iss,av,_ in filas}
print(f"   available_at - issue_time  ->  {desf} h, constante en {len(filas)} filas")
print("   origen: weather.py:58-60  L_MAX_HOURS['icon_seamless'] = 4.76")
print("   procedencia: auditoria F-3, n=307 pases, 20 fechas, jun-sep 2026,")
print("                preinscrita en PREREG_MODELSEL_ASOF_V2.md §2")
print("   es el MAXIMO observado, no la mediana: fail-closed por diseno")
print("   ADVERTENCIA REGISTRADA en el propio modulo: el maximo CRECIO al pasar")
print("   de 20 a 307 observaciones; la cola no esta caracterizada. Es una cota")
print("   INFERIOR del peor caso real.")

print("\n=== §2.2 Margen de cada lead contra esa cota")
def tasof(td, lead): return dt.datetime.combine(td, dt.time(12), dt.timezone.utc) - dt.timedelta(hours=lead)
for lead in (24, 9):
    margenes = []
    for td, iss, av, _ in filas:
        t = tasof(td, lead)
        if av <= t: margenes.append((t-av).total_seconds()/3600)
    margenes.sort()
    disp = len(margenes)
    print(f"   lead {lead:2d}h: {disp} de {len(filas)} pronosticos disponibles"
          f"   margen min {min(margenes):.2f} h  mediana {margenes[len(margenes)//2]:.2f} h  max {max(margenes):.2f} h")

print("\n=== §2.3 SENSIBILIDAD: que pasa si L_MAX real fuera mayor")
for lmax in (4.76, 5.5, 6.0, 6.25, 7.0, 9.0, 12.0):
    r = {}
    for lead in (24, 9):
        n = sum(1 for td, iss, _, _ in filas
                if iss + dt.timedelta(hours=lmax) <= tasof(td, lead))
        r[lead] = n
    marca = "  <- el valor en uso" if lmax == 4.76 else ("  <- CAE lead 24 ENTERO" if r[24] == 0 and lmax <= 7 else "")
    print(f"   L_MAX = {lmax:5.2f} h   lead24: {r[24]:3d}/236   lead9: {r[9]:3d}/236{marca}")
print("\n   El 06z se emite a las 06:00 y t_asof de lead 24 son las 12:00 del dia anterior:")
print("   el margen es de 6,00 h EXACTAS menos la latencia. Con L_MAX = 4,76 quedan 1,24 h.")
print("   *** Si la latencia real superara las 6,00 h, lead 24 se queda SIN NINGUN pronostico. ***")
print("   No es una degradacion gradual: es un acantilado.")
