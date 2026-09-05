# COORDINATE_AUDIT — FUENTE CANÓNICA DE `station_latitude` / `station_longitude`

**Fecha:** 2026-09-05 · **Naturaleza:** READ-ONLY
**Bloqueo externo vigente:** `single-runs-api` y `historical-forecast-api` devuelven
HTTP 429 (cuota diaria). **No se ha sorteado.** Los sondeos de §5/§6 usan el endpoint de
pronóstico `api.open-meteo.com` (cuota independiente) **exclusivamente para geometría**;
no se ha ejecutado ninguna parte del benchmark V5 ni calculado ninguna métrica de precisión.

---

## §0. RESULTADO PRINCIPAL — LA PROCEDENCIA YA NO ES DESCONOCIDA

El BLOCKER se planteó como *"las coordenadas de V3 proceden del artefacto de muestra y no de
una tabla definida"*. La auditoría identifica su origen:

> **Las coordenadas de V3 son las de la metadata de estación de IEM ASOS.**

| ICAO | IEM | V3 | distancia |
|---|---|---|---|
| MPMG | 8.9833333333, −79.5166666667 | 8.9833, −79.5167 | **5.2 m** |
| ZSQD | 36.06667, 120.33333 | 36.0667, 120.3333 | 4.3 m |
| VILK | 26.76059, 80.88934 | 26.7606, 80.8893 | 4.1 m |
| EGLC | 51.50528, 0.05528 | 51.5053, 0.0553 | 2.6 m |
| ZGSZ | 22.55, 114.1 | 22.55, 114.1 | 0.0 m |
| LTFM / UUWW / MMMX / ZSJN | — | — | 0.0 m |

**Máximo sobre las 16 estaciones: 5,2 m** — puro redondeo a 4 decimales. La coincidencia es
exacta. V3 no usó coordenadas arbitrarias: usó IEM, es decir **la misma fuente que produce
la etiqueta `Y`**.

Esto reduce el problema: ya no es *"de dónde salieron"*, sino *"¿es IEM la fuente correcta?"*.
La respuesta de esta auditoría es **no del todo**, y por un motivo concreto y acotado.

---

## §1. INVENTARIO DE FUENTES

| # | Fuente | Naturaleza | Cobertura del universo | ¿Nueva? |
|---|---|---|---|---|
| 1 | **IEM ASOS metadata** (`mesonet.agron.iastate.edu/api/1/station/<ID>.json`) | metadata del proveedor observacional que sirve el METAR | **55/55** | no — ya en uso (V2/V3/V5) |
| 2 | **Coordenadas usadas en V3/V5** | artefacto `MODELSEL_GEOVAL_V3_SAMPLE.json` | 16/16 de la muestra | no — **es (1) redondeada** |
| 3 | **OurAirports** (`airports.csv`) | registro aeronáutico público, versionado en GitHub | **55/55** | ya utilizada en esta ronda y en la anterior |
| 4 | **Polymarket / CATALOG_V2** | `station` + `station_identifier` en la descripción del mercado | 79 757 mercados con ICAO | no aporta coordenadas |
| 5 | **Repositorio del proyecto** | — | **0** | — |

Sobre (4): Polymarket publica el **nombre y el identificador** de la estación
(`"London City Airport"`, `EGLC`; `"Incheon Intl Airport"`, `RKSI`) pero **ninguna coordenada**.
Es autoritativo sobre *qué estación* rige el settlement, no sobre *dónde está*.

Sobre (5): árbol completo del commit `5287122e141f972eaca9b7c62e88496343931457` recuperado
del almacén de objetos local **en copia aislada**, sin escribir en el repositorio. Búsqueda de
`latitude|longitude|lat|lon` en `src/` y `scripts/`:

```
src/weather_agent/config.py:103:  "params": "latitude, longitude, start_date, end_date, hourly=temperature_2m, "
```

Única aparición. **El proyecto no define ninguna coordenada de estación.** El BLOCKER es real.

**No se ha incorporado ninguna fuente nueva.**

---

## §2. JERARQUÍA DE AUTORIDAD

| Criterio | IEM ASOS metadata | OurAirports | Polymarket |
|---|---|---|---|
| **Quién publica** | Iowa Environmental Mesonet (Iowa State Univ.), reempaquetando metadata NOAA/WMO | proyecto abierto, datos derivados de registros aeronáuticos públicos | Polymarket (emisor del contrato) |
| **¿Representa la estación física observacional?** | **Parcialmente — falla en 7/55** (ver §4) | **Sí — el aeródromo**, que es el emisor del METAR | no aplica: no da coordenada |
| **Precisión disponible** | heterogénea: 34/55 a 5 decimales, **4/55 a ≤2 decimales** | 5–7 decimales, uniforme | — |
| **Estabilidad histórica** | campo `modified` (2020–2025) y `archive_begin`; **sin historial de coordenadas por fecha** | dataset versionado en Git → **pinnable a un commit** | contrato inmutable por mercado |
| **Reproducibilidad** | alta (API estable, JSON) pero **no versionada**: una corrección silenciosa cambia el valor sin traza | **alta y auditable**: se puede fijar commit/fecha | alta |
| **Cobertura** | 55/55 ICAO | 55/55 ICAO | 55/55 ICAO (identificador) |
| **Relación con la fuente de settlement/observación** | **directa** — es quien sirve el METAR del que sale `Y` | indirecta — describe el aeródromo que **emite** ese METAR | **directa** — define qué estación rige |

Ninguna fuente domina en todos los criterios: IEM gana en *relación con el dato*,
OurAirports en *representación física, precisión y reproducibilidad versionada*.

---

## §3. COMPARACIÓN — UNIVERSO COMPLETO (55 estaciones)

Tabla completa en `COORD_FULL_TABLE.txt`. Distancia IEM ↔ OurAirports:

```
n = 55    p50 = 0.87 km    p75 = 2.86 km    p90 = 13.82 km    máx = 39.52 km    media = 3.99 km
> 5 km: 7 estaciones     > 10 km: 6     > 20 km: 4
```

**La distribución es bimodal**: 48 estaciones concordantes (mediana 0,87 km, del orden del
tamaño de un aeropuerto) y **7 discordantes** que forman un grupo homogéneo:

| ICAO | ciudad | d (km) | nombre en IEM | nombre en OurAirports | dec. | WIGOS |
|---|---|---|---|---|---|---|
| ZSQD | Qingdao | **39.52** | `Qingdao` | Qingdao Jiaodong Intl Airport | 5 | `0-20000-0-54857` |
| ZGSZ | Shenzhen | **32.05** | `Shenzhen` | Shenzhen Bao'an Intl Airport | **2** | — |
| ZHCC | Zhengzhou | **27.92** | `Zhengzhou` | Zhengzhou Xinzheng Intl Airport | 10 | `0-20000-0-57083` |
| ZUCK | Chongqing | **27.08** | `Chongqing` | Chongqing Jiangbei Intl Airport | **2** | `0-20000-0-57516` |
| ZHHH | Wuhan | **18.98** | `Wuhan` | Wuhan Tianhe Intl Airport | **2** | `0-20000-0-57494` |
| ZUUU | Chengdu | **13.82** | `Chengdu` | Chengdu Shuangliu Intl Airport | 10 | `0-20000-0-56294` |
| OPKC | Karachi | **6.77** | `Karachi` | Jinnah Intl Airport | 5 | `0-20000-0-41780` |

El patrón es inequívoco: en las 7, **el `name` de IEM es la CIUDAD, no el aeropuerto**, y
6 de 7 llevan identificador **WIGOS/WMO de estación sinóptica**. IEM ha catalogado bajo el
ICAO del aeródromo la coordenada de la **estación sinóptica urbana**.

La baja precisión decimal es un indicador parcial pero no suficiente:

```
IEM con <=2 decimales: n= 4   d media = 19.63 km   máx = 32.05 km
IEM con  >2 decimales: n=51   d media =  2.76 km   máx = 39.52 km   <- ZSQD, 5 decimales y aun así 39.5 km
```

Es decir: **no basta con filtrar por precisión**; ZSQD tiene 5 decimales y es el peor caso.

---

## §4. LA FUENTE OBSERVACIONAL PRIMARIA — PRUEBA DIRECTA

**¿Contiene IEM coordenadas oficiales y corresponden al ICAO usado para las observaciones?**

- **¿Las contiene?** Sí, en `longitude`/`latitude`, con `elevation`, `tzname`, `network`,
  `archive_begin`, `modified` y `wigos`. **Estáticas** (un único valor por estación),
  **reproducibles** (API pública estable), **cobertura 55/55**.
- **¿Corresponden al ICAO observacional?** **En 48/55 sí. En 7/55 NO.**

Prueba directa ejecutada sobre las estaciones discordantes — se descargó el dato crudo que
IEM sirve, con `latlon=yes`:

```
ZSQD: 24 obs;  lat/lon adjuntada por IEM = (36.0667, 120.3333)
      ZSQD 150000Z VRB01MPS CAVOK 27/24 Q1002 NOSIG
ZGSZ: 24 obs;  lat/lon adjuntada por IEM = (22.5500, 114.1000)
      ZGSZ 150000Z 14004MPS 9999 BKN020 27/25 Q1006 NOSIG
ZUUU: 24 obs;  lat/lon adjuntada por IEM = (30.6667, 104.0167)
      ZUUU 150000Z 35002MPS 320V030 CAVOK 28/23 Q1002 NOSIG
```

El dato **es un METAR de aeródromo legítimo** — formato METAR, emitido bajo el ICAO del
aeropuerto. Un METAR es por definición un *informe meteorológico de aeródromo*: lo emite el
aeropuerto, no la estación sinóptica urbana. Sin embargo IEM le adjunta la coordenada urbana.

> **Conclusión §4:** para estas 7 estaciones, la coordenada de IEM **no representa el lugar
> físico donde se mide la observación que usamos como `Y`**. La observación viene del
> aeródromo; la coordenada apunta a la ciudad, hasta 39,5 km de distancia.

Esto invierte la expectativa inicial. La preferencia conceptual del encargo —*"la coordenada
debe representar la ubicación física de la estación observacional que genera el dato usado
como label"*— **no se satisface usando IEM**, precisamente en las estaciones donde más importa.

---

## §5. SENSIBILIDAD OPERATIVA (geometría, sin métricas de precisión)

38 estaciones sondeadas (las 32 con d ≥ 0,5 km más 13 europeas por proximidad a dominios;
solapan). Para cada una, coordenada IEM vs coordenada OurAirports:

```
cambia celda ECMWF:        9/38
cambia celda ICON:        15/38
cambia COMPONENTE ICON:    0/38
|ΔT| ECMWF: media 0.37   p50 0.00   p90 1.30   máx 3.10 °C   (>=0.5 °C en  8/38)
|ΔT| ICON : media 0.28   p50 0.10   p90 0.90   máx 2.00 °C   (>=0.5 °C en  9/38)
```

Estaciones con |ΔT| ≥ 0,5 °C:

| ICAO | ciudad | d (km) | ΔT ECMWF | ΔT ICON | comp. IEM | comp. OA |
|---|---|---|---|---|---|---|
| ZSQD | Qingdao | 39.52 | −0.5 | +0.9 | global | global |
| ZGSZ | Shenzhen | 32.05 | −0.7 | −0.8 | global | global |
| ZHCC | Zhengzhou | 27.92 | **+3.1** | **+2.0** | global | global |
| ZUCK | Chongqing | 27.08 | +1.3 | +1.2 | global | global |
| ZHHH | Wuhan | 18.98 | −1.2 | +0.6 | global | global |
| ZUUU | Chengdu | 13.82 | **+2.3** | +1.6 | global | global |
| OPKC | Karachi | 6.77 | **−2.8** | +0.1 | global | global |
| ZSPD | Shanghai | 4.71 | −1.1 | 0.0 | global | global |
| LEMD | Madrid | 3.29 | +0.1 | +0.6 | eu | eu |
| KMIA | Miami | 2.86 | 0.0 | −0.8 | global | global |
| KAUS | Austin | 2.35 | 0.0 | +0.7 | global | global |

**Magnitud en contexto:** las bandas de los mercados tienen anchura de **1 °C**. Una
diferencia de 3,1 °C (ZHCC) o 2,8 °C (OPKC) **desplaza el pronóstico varias bandas**. La
elección de coordenada no es un detalle de segundo orden: es comparable o superior a la
diferencia de precisión entre modelos que MODELSEL intenta medir.

**Impacto cuantificado:**
- **5 de las 16 estaciones de V3/V5** tienen d > 1 km: ZSQD (39.5), ZGSZ (32.1), OPKC (6.8),
  MPMG (4.4), LTFM (1.5). En ZSQD, ZGSZ y OPKC **cambia la celda ECMWF**.
- **40 545 de 91 285 mercados** del universo (44,4 %) corresponden a estaciones con d > 1 km.
- **10 670 mercados** (11,7 %) a estaciones con d > 5 km.

---

## §6. FRONTERAS DE COMPONENTE ICON

Sondeo de desplazamiento sobre las 13 estaciones asignadas a **D2** (EGLC, EDDM, EHAM, LFPB,
LFPG, LIMC) o **EU** (EFHK, EPWA, LEMD, LLBG, LTAC, LTFM, UUWW), con offsets de
**±0.2° y ±0.4°** en latitud y longitud:

```
13/13 estaciones: ningún cambio de componente hasta ±0.4°
```

Combinado con §5 (0/38 cambios de componente entre fuentes de coordenadas), la conclusión es:

> **La asignación de componente ICON es ROBUSTA a la elección de fuente de coordenadas**,
> para todo el rango de discrepancia observado (máx. 39,5 km ≈ 0,35°).

**Limitación declarada:** se probaron únicamente **4 direcciones cardinales** en 2 magnitudes.
Una frontera situada en diagonal dentro de la región no muestreada no quedaría detectada. El
resultado se enuncia como *"no se detectó frontera dentro de ±0.4° sobre los ejes cardinales"*,
**no** como *"no existe frontera"*. Para las estaciones concretas del universo, en las que la
discrepancia real máxima entre fuentes es de 1,6 km en Europa (LFPG), el margen es amplio.

---

## §7. DEFINICIÓN CANÓNICA PROPUESTA

> **Para cada ICAO, las coordenadas canónicas serán las del AERÓDROMO identificado por ese
> código ICAO — el emisor del METAR del que se deriva `Y` —, tomadas de OurAirports
> `airports.csv` fijado a un commit concreto del repositorio, y contrastadas contra la
> metadata de IEM ASOS; toda discrepancia superior a 1 km se resuelve documentalmente,
> estación por estación, antes de usarse.**

### Justificación

1. **Criterio conceptual del encargo.** La coordenada debe representar la ubicación física de
   la estación observacional que genera el label. El label es un METAR; un METAR es un
   informe de aeródromo; luego la ubicación física es el aeródromo. §4 demuestra con el dato
   crudo que IEM **incumple** esto en 7/55 estaciones.
2. **No favorece a ningún modelo.** La regla se define por la fuente del label, sin referencia
   a ninguna rejilla. §6 confirma además que no altera la asignación de componente ICON, de
   modo que no puede sesgar el contraste ICON vs ECMWF por la vía del régimen de resolución.
3. **Reproducibilidad auditable.** OurAirports es un dataset versionado en Git: fijando el
   commit, la coordenada es reproducible bit a bit y cualquier cambio futuro es visible en el
   histórico. IEM expone `modified` pero **no versiona coordenadas**: una corrección silenciosa
   cambiaría el valor sin dejar traza reproducible.
4. **Cobertura.** 55/55 estaciones con ICAO.
5. **IEM se conserva como control, no se descarta.** Es la fuente del label y su metadata
   (`tzname`, `archive_begin`, `elevation`) sigue siendo necesaria. Se usa como verificación
   cruzada: concordancia < 1 km en 48/55 es una validación mutua fuerte.

### Lo que esta definición NO resuelve

- **2 estaciones sin ICAO**: Hong Kong (1 859 mercados, 169 eventos) y Taipei (77 mercados,
  7 eventos). Hong Kong se resuelve por otra vía (settlement HKO, estación ya identificada en
  ronda anterior); Taipei queda **UNKNOWN**.
- **Precisión intra-aeródromo.** OurAirports da el punto de referencia del aeródromo, no la
  ubicación exacta del sensor. Para un aeropuerto de ~3 km esto es irrelevante frente a la
  celda de ECMWF (28 km) pero es del orden de la celda de ICON-D2 (2,2 km). **No cuantificado.**
- **Verificación independiente de las 7 discordantes.** Se dispone de la afirmación de
  OurAirports frente a la de IEM, y del argumento estructural del §4 — pero **no** de una
  confirmación contra una fuente aeronáutica oficial (AIP nacional, ICAO Doc 7910). Es la
  comprobación que falta.

---

## §8. CAMBIOS HISTÓRICOS DE COORDENADAS

**Sí existen, y uno afecta directamente a la muestra V5.**

Evidencia de OurAirports:

```
Qingdao:  ident=CN-0164  type=closed         Qingdao Liuting Intl Airport    (36.2658, 120.3746)
          ident=ZSQD     type=large_airport  Qingdao Jiaodong Intl Airport   (36.3620, 120.0882)
```

El código **ZSQD se transfirió de Liuting a Jiaodong**; Liuting figura como `closed`. Las tres
coordenadas candidatas para ZSQD son **mutuamente distantes**:

| candidata | coordenada | comentario |
|---|---|---|
| IEM (usada en V3/V5) | 36.06667, 120.33333 | estación sinóptica urbana WMO 54857 — **nunca fue el aeropuerto** |
| Liuting (histórico) | 36.2658, 120.3746 | aeródromo hasta la transferencia; hoy cerrado |
| Jiaodong (actual) | 36.3620, 120.0882 | aeródromo vigente en el periodo V5 (2026) |

Para el resto del universo no se detectó reubicación relevante en el periodo: LTFM (aeropuerto
nuevo de Estambul) figura en ambas fuentes en la ubicación actual, con discrepancia de 1,5 km;
LFPG/LFPB y RCTP/RCSS son aeródromos distintos con códigos distintos, no reubicaciones.

**IEM no publica historial de coordenadas por fecha** — sólo un campo `modified`
(distribución por año: 2020:5, 2021:1, 2022:2, 2023:36, 2024:1, 2025:10) y `archive_begin`.
No permite reconstruir qué coordenada estaba vigente en una fecha dada.

### ¿Hace falta versionar `station_lat/lon` por fecha?

**Para el periodo de V5 (2026-06-03 → 2026-09-04): NO.** Todas las reubicaciones detectadas son
anteriores y dentro del periodo la coordenada es constante. Basta una coordenada única por ICAO.

**Para el catálogo histórico completo (desde 2025-12-30): NO se ha verificado.** No se ha
comprobado si algún ICAO cambió de emplazamiento dentro de ese rango. Si en el futuro se
evalúan periodos más largos, el esquema debería admitir versionado por fecha
(`valid_from` / `valid_to`). **Recomendación: diseñar el campo como versionable aunque hoy se
poble con un único registro por estación.** No se propone implementarlo ahora.

---

## §9. DECISIÓN

> ### **B — existe candidata clara pero requiere una comprobación adicional.**

**Por qué no A.** La candidata (coordenada del aeródromo, OurAirports fijado por commit) está
bien fundamentada conceptual y empíricamente, pero para las **7 estaciones discordantes** sólo
dispongo de la afirmación de OurAirports contra la de IEM más el argumento estructural del §4.
Fijar la convención antes de confirmar esas 7 contra una fuente aeronáutica oficial significaría
apoyar el 11,7 % de los mercados del universo en una fuente colaborativa no verificada. La
comprobación pendiente es acotada y barata: **7 estaciones**, no 55.

**Por qué no C.** Las coordenadas no son UNKNOWN. Su procedencia está identificada (§0), hay
cobertura 55/55 en dos fuentes independientes que **concuerdan dentro de 1 km en 48/55**, la
discrepancia restante tiene una explicación mecánica documentada (estación sinóptica urbana
frente a aeródromo, §4) y su efecto geométrico está cuantificado (§5) y acotado (§6: no altera
el componente ICON). Esto no es un BLOCKER irresoluble; es una verificación pendiente.

### Comprobación adicional requerida (no ejecutada)

Para ZSQD, ZGSZ, ZHCC, ZUCK, ZHHH, ZUUU y OPKC: confirmar la coordenada del aeródromo contra
una fuente aeronáutica oficial (AIP nacional o ICAO Doc 7910). Sólo entonces la convención
puede pasar de **B** a **A**.

### Consecuencia que debe registrarse

Los benchmarks **V2, V3 y V4 ya ejecutados** usaron la coordenada de IEM. En 3 de las 16
estaciones de V3 (ZSQD, ZGSZ, OPKC) esa coordenada dista 6,8–39,5 km del aeródromo y **cambia
la celda de ECMWF**. Si la convención canónica se fija como aquí se propone, esos resultados
quedan calculados sobre una coordenada distinta de la canónica. No se propone recalcularlos en
esta ronda: es una decisión que corresponde revisar junto con el diseño de V5.

---

## §10. V5

**NO ejecutado y no debe ejecutarse todavía**, conforme a la instrucción. La convención de
coordenadas requiere revisión y aprobación previa. El HTTP 429 permanece como bloqueo externo
independiente y **no ha sido sorteado**.

---

## §11. INTEGRIDAD

| Comprobación | Estado |
|---|---|
| project files modificados | **NO** |
| DB modificada | **NO** (DuckDB abierto con `read_only=True`) |
| schema modificado | **NO** |
| pipeline modificado | **NO** |
| `weather_forecasts` modificada | **NO** |
| Git commit | **NO** |
| Git push | **NO** |
| M1 seleccionado | **NO** |
| Benchmark V5 ejecutado | **NO** |
| Métricas de precisión calculadas | **NINGUNA** |
| HTTP 429 sorteado | **NO** |

El árbol del proyecto se inspeccionó en copia aislada fuera de `/private/tmp/pmw-publish`;
el `.git` original no fue escrito.

**Artefactos:** `COORD_IEM_RAW.json` · `COORD_TABLE.json` · `COORD_FULL_TABLE.txt` ·
`COORD_SENSITIVITY.json` · `COORD_BOUNDARY.json` · `COORD_PROBE_LIST.json` ·
`V5_UNIVERSE_STATIONS.json` — todos en `/Users/mariaaleu/pmw-e2/`.
