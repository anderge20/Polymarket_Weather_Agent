#!/usr/bin/env python3
"""NIVEL 0.5/0.75 — comprueba las identidades I1..I10 de NIVEL0_5_CRITERIO_COMPLETITUD.md.

El criterio se escribio a las 16:46Z con la reingesta todavia corriendo (marca de git).
Este guion NO lo interpreta: lo ejecuta. Cualquier fallo deja el dataset INVALID.
"""
import duckdb, os, sys
from collections import Counter

CAT = os.path.expanduser("~/pmw-catalog-v2/CATALOG_V2.duckdb")
DB  = "/Users/mariaaleu/workspace/Polymarket_Weather_Agent/data/pmw.duckdb"
DSV = "markets_v2"
cat = duckdb.connect(CAT, read_only=True)
con = duckdb.connect(DB, read_only=True)
fallos = []

def chk(nombre, ok, detalle):
    print(f"  [{'OK ' if ok else 'FALLA'}] {nombre:52s} {detalle}")
    if not ok: fallos.append(nombre)

print("=" * 100)
print("IDENTIDADES I1..I10")
print("=" * 100)

# I2 — el dry-run no mintio
ev = con.execute("SELECT count(DISTINCT event_id) FROM markets WHERE dataset_version=?", [DSV]).fetchone()[0]
mk = con.execute("SELECT count(*) FROM markets WHERE dataset_version=?", [DSV]).fetchone()[0]
chk("I2 eventos escritos == 7331", ev == 7331, f"{ev}")
chk("I2 mercados escritos == 79735", mk == 79735, f"{mk}")

# I1 — conservacion del universo
cat_ev = cat.execute("SELECT count(DISTINCT event_id) FROM mk WHERE station_identifier IS NOT NULL").fetchone()[0]
cat_mk = cat.execute("SELECT count(*) FROM mk WHERE station_identifier IS NOT NULL").fetchone()[0]
excl_ev, excl_mk = 2, 22          # del dry-run: 2 eventos sin tokens, 22 mercados sin clobTokenIds
chk("I1 eventos catalogo == escritos + excluidos", cat_ev == ev + excl_ev, f"{cat_ev} == {ev} + {excl_ev}")
chk("I1 mercados catalogo == escritos + excluidos", cat_mk == mk + excl_mk, f"{cat_mk} == {mk} + {excl_mk}")

# I3 — atomicidad por evento
parciales = con.execute(f"""
  WITH c AS (SELECT CAST(event_id AS VARCHAR) e, count(*) n FROM '{CAT}'.mk
             WHERE station_identifier IS NOT NULL GROUP BY 1),
       w AS (SELECT CAST(event_id AS VARCHAR) e, count(*) n FROM markets
             WHERE dataset_version='{DSV}' GROUP BY 1)
  SELECT count(*) FROM w JOIN c USING (e) WHERE w.n <> c.n""").fetchone()[0] if False else None
# duckdb no cruza ficheros asi: se hace en python
cat_por_ev = dict(cat.execute("""SELECT CAST(event_id AS VARCHAR), count(*) FROM mk
                                 WHERE station_identifier IS NOT NULL GROUP BY 1""").fetchall())
w_por_ev = dict(con.execute("SELECT CAST(event_id AS VARCHAR), count(*) FROM markets WHERE dataset_version=? GROUP BY 1",
                            [DSV]).fetchall())
parciales = [e for e, n in w_por_ev.items() if cat_por_ev.get(e) != n]
chk("I3 ningun evento escrito a medias", not parciales, f"{len(parciales)} parciales")

# I4 — outcomes
out = con.execute("SELECT count(*) FROM outcomes WHERE dataset_version=?", [DSV]).fetchone()[0]
chk("I4 outcomes == 2 x mercados", out == 2 * mk, f"{out} vs {2*mk}")
mal = con.execute("""SELECT count(*) FROM (SELECT market_id, count(*) n,
                     sum(CASE WHEN lower(trim(outcome_label))='yes' THEN 1 ELSE 0 END) y
                     FROM outcomes WHERE dataset_version=? GROUP BY 1 HAVING n<>2 OR y<>1)""", [DSV]).fetchone()[0]
chk("I4 cada mercado con exactamente un Yes y un No", mal == 0, f"{mal} mal formados")

# I5 — duplicados
d1 = con.execute("""SELECT count(*) FROM (SELECT market_id FROM markets WHERE dataset_version=?
                    GROUP BY 1 HAVING count(*)>1)""", [DSV]).fetchone()[0]
d2 = con.execute("""SELECT count(*) FROM (SELECT token_id FROM outcomes WHERE dataset_version=?
                    GROUP BY 1 HAVING count(*)>1)""", [DSV]).fetchone()[0]
chk("I5 sin market_id duplicado", d1 == 0, f"{d1}")
chk("I5 sin token_id duplicado", d2 == 0, f"{d2}")

# I6 — bandas
sinb = con.execute("""SELECT count(*) FROM outcomes WHERE dataset_version=?
                      AND lower(trim(outcome_label))='yes' AND band_label IS NULL""", [DSV]).fetchone()[0]
chk("I6 todo token Yes tiene band_label", sinb == 0, f"{sinb} sin banda")

# I7 — el dataset viejo intacto
v_mk = con.execute("SELECT count(*) FROM markets WHERE dataset_version='backfill_2b_v1'").fetchone()[0]
v_out = con.execute("SELECT count(*) FROM outcomes WHERE dataset_version='backfill_2b_v1'").fetchone()[0]
chk("I7 backfill_2b_v1 sigue en 6143 mercados", v_mk == 6143, f"{v_mk}")
chk("I7 backfill_2b_v1 sigue en 12286 outcomes", v_out == 12286, f"{v_out}")

# I8 — particiones EGLC
eg = con.execute("""SELECT count(DISTINCT event_id) FROM markets
                    WHERE dataset_version=? AND station_identifier='EGLC'""", [DSV]).fetchone()[0]
tam = Counter(n for _, n in con.execute("""SELECT event_id, count(*) FROM markets
                  WHERE dataset_version=? AND station_identifier='EGLC' GROUP BY 1""", [DSV]).fetchall())
chk("I8 EGLC 187 eventos", eg == 187, f"{eg}")
chk("I8 EGLC tamanos {7:2, 9:26, 11:159}", dict(tam) == {7: 2, 9: 26, 11: 159}, f"{dict(sorted(tam.items()))}")

# I9 — observaciones
o = dict(con.execute("""SELECT series, count(*) FROM weather_observations
                        WHERE station='EGLC' GROUP BY 1""").fetchall())
dos = con.execute("""SELECT count(*) FROM (SELECT CAST(observation_time AS DATE) d FROM weather_observations
                     WHERE station='EGLC' GROUP BY 1 HAVING count(DISTINCT series)=2)""").fetchone()[0]
rep = con.execute("""SELECT count(*) FROM (SELECT CAST(observation_time AS DATE) d, series
                     FROM weather_observations WHERE station='EGLC' GROUP BY 1,2 HAVING count(*)>1)""").fetchone()[0]
chk("I9 EGLC 118 viejas + 138 nuevas", o.get("IEM_ASOS_METAR_1C") == 118 and o.get("IEM_ASOS_METAR_1C_RT34") == 138, f"{o}")
chk("I9 118 dias con las dos series", dos == 118, f"{dos}")
chk("I9 ningun dia con dos filas de la MISMA serie", rep == 0, f"{rep}")

# I10 — leakage
lk = con.execute("""SELECT count(*) FROM weather_observations
                    WHERE available_at < observation_time""").fetchone()[0]
chk("I10 ninguna observacion disponible antes de ocurrir", lk == 0, f"{lk}")

print("=" * 100)
print(f"RESULTADO: {'DATASET COMPLETO' if not fallos else 'INVALID / INCOMPLETE -> ' + ', '.join(fallos)}")
sys.exit(0 if not fallos else 1)
