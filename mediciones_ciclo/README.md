# Mediciones del ciclo y de la puerta del catálogo · 2026-09-11/12

**Por qué están aquí.** Cada una de estas mediciones sostiene una afirmación de
`DECISIONS.md`, y todas vivieron hasta ahora **en un solo disco de trabajo**. La sesión A
encontró el mismo defecto en `R30_ROWS.json` —doce horas en una sola máquina, siendo el
sustrato de la única hipótesis de edge viva— y esto es la otra mitad del mismo barrido:
*el registro existe, es exacto, y está donde nadie va a buscarlo.*

**Lo que NO son.** No son herramientas: son instrumentos de un día, con rutas fijas a
`~/workspace/Polymarket_Weather_Agent` y a worktrees que ya no existen, y varios leen
`origin/paper-state` dando por hecho que está traído. Se publican para que una cifra
citada se pueda **re-derivar**, no para que se puedan ejecutar sin tocarlos.

| fichero | qué mide | sostiene |
|---|---|---|
| `decomp.py` | reparto del ciclo entre CATÁLOGO y libros+precios, y su delta | B-87 (el 72 % es regresión del #31, no del sustrato) |
| `rows.py` | `store_rows_loaded` / `rows_resident` / `total_bytes` por ciclo | B-87 (la ley de 13,50 ms por fila) |
| `order.py` | directorios-día con dos o más generaciones de id conviviendo | B-88 y el #36 (tres generaciones; la más vieja ordena la última) |
| `diff.py` | diff campo a campo de dos shards de catálogo consecutivos | B-88 (falla en la mitad exacta de las filas) |
| `st.py` | qué clave cambia DENTRO de `source_timestamps` | B-88 (sólo `updatedAt`, el reloj de Polymarket) |
| `rate.py` | cambios de contenido contra cambios de sólo-reloj, por par | B-88, B-90 bis (`tick_size` en 33, 34, 11, 64) |
| `collide.py` | colisiones de clave si el replay va mal ordenado | B-90 (cero: ninguna fila derivada está mal hoy) |
| `dir.py` | shard → `load_shards` → base, la dirección que recorre la caja | B-89 (7 columnas, 3 familias; y sólo 5 con `export_rows`) |
| `type.py` | una fila, escrita desde la base y comparada consigo misma | B-88 (la puerta era un `False` constante) |
| `real3.py` | la puerta **ya fusionada** sobre los ocho pares reales | B-96 bis (`markets` no salta nunca; media 35 %) |
| `rev_audit.py` | revisiones y comentarios previos al merge, por PR | B-92 (11 de 30 sin ninguna huella) |

**El que falta a propósito:** `rss.py`, ya espejado en la raíz, mide el pico de RSS cargando
los 194 shards reales — 281,9 MB, el 7,4 % de la caja — y es el que refuta la hipótesis de
memoria de B-91.
