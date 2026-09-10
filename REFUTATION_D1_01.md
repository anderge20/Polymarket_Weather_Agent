# REFUTATION_D1_01 — Refutación adversarial de D1 y de COORDINATE_SENSOR_VERIFICATION

**Fecha:** 2026-09-05 · **Ejecutor:** Claude, en rol de revisor adversarial (sustituye a Codex,
sin cuota hasta 2026-10-05; ver D3/D5) · **Naturaleza:** READ-ONLY sobre artefactos; consultas
de red solo a NCEI HOMR (no consume cuota de Open-Meteo)

Objeto: la refutación que `COORDINATE_SENSOR_VERIFICATION.md` §6 declaró **pendiente** por límite
de sesión de subagentes. Ese límite venció; se ejecuta aquí con las tres lentes declaradas.

---

## Lente 1 — CÁLCULO · **PASA**

Recomputadas las 11 distancias con haversine independiente (R = 6371.0088 km), tomando las
coordenadas NOAA del snapshot canónico y las de HOMR de `COORD_HOMR_US.json`, sin usar los
valores `d_noaa_km` ya almacenados.

```
máxima discrepancia con lo publicado: 0.016 m   (todas las demás < 0.001 m)
ASOS CM (n=10): media 8.8 m · máx 71.1 m (KAUS) · ≤10 m en 9/10
informe afirma: media 9 m   · máx 71 m           · ≤10 m en 9/10
```

Los números del informe son correctos. No hay error aritmético.

## Lente 2 — FUENTE · **PASA**

Consultado HOMR de forma independiente:
`https://www.ncei.noaa.gov/access/homr/services/station/search?qid=WBAN:13874&date=all` → HTTP 200.

- El registro vincula **WBAN 13874 ↔ ICAO KATL** en su propio bloque `identifiers`, de modo que
  la correspondencia WBAN→ICAO no depende de una tabla externa del proyecto.
- El par vigente (`beginDate 2021-11-22 → Present`) lleva `source: "ASOS CM"`, `precision: DDddddd`.
- El par anterior (2001-04-13 → 2021-11-22) lleva `source: "ASOS SITE SURVEY"`.

La fuente existe, es pública y dice lo que el informe cita.

## Lente 3 — SEMÁNTICA · **PASA CON RESERVA CUANTIFICADA**

La premisa "coordenada NOAA = ubicación del sensor" queda **observada para la red ASOS de
EE.UU.**. Fuera de ella la evidencia es mucho más delgada de lo que sugiere el titular:

```
universo canónico:            55 estaciones
EE.UU.:                       11        fuera de EE.UU.:  44
verificadas directamente:     11  (10 ASOS CM + WSSS)
fuera de EE.UU. SIN verificar: 43
```

Las 10 verificaciones de EE.UU. **no son 10 evidencias independientes**: proceden de una sola red
(ASOS) y de una sola base de gestión de configuración (NWS ASOS CM). Como evidencia sobre la
práctica de *NOAA AviationWeather al publicar estaciones extranjeras* valen, en rigor, como una.
Fuera de EE.UU. la única verificación es **WSSS** (n = 1), y esa sí es independiente y fuerte
(AIP Singapur + OSCAR + NEA concuerdan en 40–46 m).

China aporta 10 estaciones sin verificar; la eAIP de la CAAC no era accesible (DNS) en la auditoría
previa. Ese es el bloque de exposición mayor.

**Esto no refuta D1.** La regla sigue siendo la mejor fundada: ninguna fuente alternativa apunta al
sensor, y no ha aparecido contraejemplo. Pero el alcance correcto de la afirmación es:

> Verificada por documentación oficial en 11/55 estaciones. En las 43 restantes la regla se
> sostiene por identidad de estirpe de registro y ausencia de contraejemplo, no por verificación
> individual.

---

## Defecto encontrado · **KBKF estaba mal identificada**

`COORDINATE_SENSOR_VERIFICATION.md` §2 registra KBKF con `WBAN 23062`, obtiene un par vigente de
`USGS TOPO` a **11.29 km** y lo despacha como *"otra estación del mismo WBAN; requiere consulta por
otro id"*.

Consultado HOMR por `qid=ICAO:KBKF`:

```
ncdcStnId 20003754 · "AURORA BUCKLEY FIELD ANGB" · WBAN 23036 · ICAO KBKF
  39.71667, -104.75 · precision DDMM · 1987-09-01 → Present
  39.7,     -104.75 · precision DDMM · 1961-03-01 → 1987-09-01
```

**El WBAN de KBKF es 23036, no 23062.** El 23062 es otra estación. Con el registro correcto:

```
d(NOAA aviationweather, HOMR WBAN 23036) = 0.797 km
precisión del registro: DDMM (minuto entero) ⇒ ±0.93 km lat / ±0.71 km lon
```

Consecuencias, en ambos sentidos:

1. **A favor de D1:** desaparece el único aparente contraejemplo de 11 km del informe. No era una
   discrepancia real, era una estación equivocada. La tabla de §2 debe corregirse.
2. **En contra del alcance:** KBKF **no queda verificada**. Su registro HOMR no tiene `ASOS CM` y su
   precisión DDMM es insuficiente para discriminar sensor de ARP (la propia diferencia sensor-ARP
   típica, 1–3 km, cae dentro de la incertidumbre del registro). KBKF está marcada `CANONICA` en el
   snapshot y forma parte del universo V5: **es una canónica no verificada**, no un caso cerrado.

El conteo correcto es por tanto **10 ASOS CM + WSSS = 11 verificadas**, y KBKF pasa de "anomalía
pendiente" a "no verificable con HOMR".

---

## Veredicto

| Lente | Resultado |
|---|---|
| Cálculo | PASA — reproducido con Δ < 0.02 m |
| Fuente | PASA — HOMR consultada de nuevo; `ASOS CM` y el vínculo WBAN↔ICAO confirmados |
| Semántica | PASA CON RESERVA — verificado 11/55; 43 fuera de EE.UU. sin verificación individual |
| Defecto | **1 encontrado y corregido** — WBAN de KBKF (23062 → 23036) |

**D1 se sostiene.** La promoción de la premisa de INFERIDA a OBSERVADA es legítima *para la red
ASOS de EE.UU. y para WSSS*. El salto a las 43 estaciones restantes sigue siendo una inferencia
razonada, y debe declararse como tal en cualquier informe que use la convención — no como hecho
observado universal.

**Correcciones que exige este documento:**

1. `COORDINATE_SENSOR_VERIFICATION.md` §2: WBAN de KBKF y su fila (11.29 km → 0.797 km, DDMM).
2. `COORDINATE_SENSOR_VERIFICATION.md` §5: acotar la conclusión al alcance verificado (11/55).
3. `COORDINATE_SENSOR_VERIFICATION.md` §6: KBKF deja de ser "pendiente de otro id"; pasa a
   "no verificable con HOMR (sin registro ASOS CM, precisión DDMM)".
4. `DECISIONS.md` D1: el estado "categoría A" vale para el alcance verificado; el resto, categoría
   A por inferencia declarada.

**Sigue pendiente y no lo resuelve este documento:** OPKC (excepción abierta, PCAA AIP), y la
verificación de cualquier estación no estadounidense distinta de WSSS.
