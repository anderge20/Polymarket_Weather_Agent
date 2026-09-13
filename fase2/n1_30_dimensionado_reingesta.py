"""NIVEL 1 — DIMENSIONADO de la reingesta. NO reejecuta ningun criterio.

Que responde y que NO:
  RESPONDE: cuantos eventos EGLC tendrian banda ganadora identificable si se
            reingestaran las escaleras completas que YA estan en CATALOG_V2.duckdb.
  NO RESPONDE: nada sobre poder predictivo. No se toca ningun criterio, ningun
            umbral y ninguna clasificacion A/B/C/D. El veredicto vigente sigue
            siendo D - INCONCLUSO (A-240) hasta que exista la reingesta.

Por que se hace ANTES: dimensionar dice si la reingesta merece la pena y con que n
se escribe el preregistro de la reejecucion. Se declara aqui, antes de mirarlo, que
este numero NO puede usarse para elegir poblacion, lead, banda ni estadistico.

Fuentes, ambas en disco, sin red:
  ~/pmw-catalog-v2/CATALOG_V2.duckdb   tabla mk  (escalera completa por evento)
  data/pmw.duckdb                      weather_observations (EGLC, maximo diario)
"""
import duckdb, os, re, sys, datetime as dt
from collections import Counter
from zoneinfo import ZoneInfo

LON = ZoneInfo("Europe/London")
cat = duckdb.connect(os.path.expanduser("~/pmw-catalog-v2/CATALOG_V2.duckdb"), read_only=True)
pmw = duckdb.connect("/Users/mariaaleu/workspace/Polymarket_Weather_Agent/data/pmw.duckdb",
                     read_only=True)
pmw.execute("SET TimeZone='UTC'")

# El maximo observado por DIA LOCAL de Londres (A-238: nunca CAST(... AS DATE)).
obs = {}
for t, v in pmw.execute("""SELECT observation_time, observed_value
                           FROM weather_observations WHERE station='EGLC'""").fetchall():
    obs[t.astimezone(LON).date()] = v

# LOS EVENTOS DEL CATALOGO, no los del almacen. La primera version partia de
# `markets`, y eso deja fuera por construccion los eventos que el almacen NO tiene
# NINGUNA banda: 196 en el catalogo contra 163 en `markets`, 36 ausentes enteros.
# Dimensionar la reparacion partiendo de lo que la reparacion va a arreglar es
# contar con la poblacion recortada.
eids = sorted({str(r[0]) for r in cat.execute(
    """SELECT DISTINCT CAST(event_id AS VARCHAR) FROM mk
       WHERE station_identifier='EGLC'
          OR slug LIKE 'highest-temperature-in-london-%'""").fetchall()})
# UNION de las dos definiciones a proposito: 187 eventos por `station_identifier`
# y 196 por slug, y no son el mismo conjunto. Quedarse con una sola es elegir la
# poblacion por la etiqueta que mas convenga, que es lo que este nivel no hace.
en_almacen = {str(r[0]) for r in pmw.execute(
    """SELECT DISTINCT event_id FROM markets WHERE station_identifier='EGLC'""").fetchall()}

def banda(titulo):
    """(lo, hi) en C a partir del group_item_title, con los extremos abiertos."""
    s = (titulo or "").replace("°", "").strip()
    m = re.match(r"^(-?\d+)\s*C?\s*or below$", s, re.I)
    if m: return (float("-inf"), float(m.group(1)) + 0.5)
    m = re.match(r"^(-?\d+)\s*C?\s*or higher$", s, re.I)
    if m: return (float(m.group(1)) - 0.5, float("inf"))
    m = re.match(r"^(-?\d+)\s*C?$", s, re.I)
    if m: return (float(m.group(1)) - 0.5, float(m.group(1)) + 0.5)
    return None

res = Counter()
detalle = []
for eid in eids:
    rows = cat.execute("""SELECT group_item_title, endDate, winning_outcome FROM mk
                          WHERE CAST(event_id AS VARCHAR)=?""", [eid]).fetchall()
    if not rows:
        res["sin_evento_en_catalogo"] += 1; continue
    fecha = rows[0][1]
    # `endDate` es un VARCHAR ISO en el catalogo, no una fecha: sin esto el
    # `hasattr(..., "date")` es False y la comparacion falla en silencio para
    # TODOS los eventos, que es lo que hizo la primera version (0 de 163).
    if isinstance(fecha, str):
        fecha = dt.datetime.fromisoformat(fecha.replace("Z", "+00:00")).date()
    elif hasattr(fecha, "date"):
        fecha = fecha.date()
    bandas = [banda(t) for t, _, _ in rows]
    if any(b is None for b in bandas):
        res["banda_no_parseable"] += 1; continue
    # LA VERDAD LA PONE EL MERCADO (§5 de la preinscripcion): se cuenta con
    # `winning_outcome` del catalogo, no con nuestro maximo observado. La
    # observacion solo sirve para la comprobacion de integridad (c).
    ganadoras = [str(w).strip().lower() == "yes" for _, _, w in rows]
    if sum(ganadoras) != 1:
        res["sin_ganadora_declarada" if not any(ganadoras) else "ganadoras_multiples"] += 1
        continue
    if fecha not in obs:
        res["con_ganadora_SIN_observacion"] += 1; continue
    y = obs[fecha]
    bg = bandas[ganadoras.index(True)]
    res["CON_GANADORA"] += 1
    res["   de ellos AUSENTES enteros hoy"] += (eid not in en_almacen)
    res["   de ellos con la obs FUERA de la banda ganadora"] += (not (bg[0] <= y < bg[1]))
    detalle.append((eid, fecha, y, len(rows)))

print("=== DIMENSIONADO (no es un resultado de NIVEL 1) ===")
for k, v in res.most_common():
    print(f"  {k:26s} {v:4d}")
print(f"\n  n disponible hoy en el almacen : 19  (A-240, eventos completos)")
print(f"  n tras reingestar el catalogo  : {res['CON_GANADORA']}")
if detalle:
    ns = Counter(n for _, _, _, n in detalle)
    print(f"  tamano de escalera de esos eventos: {dict(sorted(ns.items()))}")
    fs = sorted(f for _, f, _, _ in detalle)
    print(f"  rango de fechas: {fs[0]} -> {fs[-1]}")
