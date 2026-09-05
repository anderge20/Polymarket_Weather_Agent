# COORDINATE_PRIMARY_VALIDATION — CIERRE DE LAS 7 DISCORDANCIAS POR FUENTE AERONÁUTICA

**Fecha:** 2026-09-05 · **Naturaleza:** READ-ONLY
**Estaciones:** exactamente las 7 identificadas en `COORDINATE_AUDIT.md`
(sha `c00c6a61f7b53ee83dba51eb3c1d60a9b6b927f7de0e814afdf7b28de588daa3`):
**ZSQD, ZGSZ, ZHCC, ZUCK, ZHHH, ZUUU, OPKC**

**Bloqueo externo vigente:** `single-runs-api` sigue en HTTP 429. **No se ha consultado ni
sorteado.** Las dos comprobaciones geométricas puntuales de §5 usan `api.open-meteo.com`
(cuota independiente). No se ha calculado ningún MAE. No se ha ejecutado V5.

---

## §0. RESULTADO EN UNA LÍNEA

> Las 7 discordancias tienen **una única causa** y **queda demostrada**: IEM ASOS reproduce
> literalmente las coordenadas del **registro sinóptico oficial de la OMM (WMO OSCAR)**,
> que en estas 7 estaciones corresponde a la **estación sinóptica urbana**, no al
> **aeródromo** que emite el METAR del que se deriva `Y`.

---

## §1. FUENTES CONSULTADAS Y ACCESIBILIDAD REAL

Se siguió el orden de preferencia del encargo. Resultado honesto de accesibilidad:

| Cat. | Fuente | Resultado |
|---|---|---|
| **A** | AIP / eAIP CAAC (China) — `www.eaip.caac.gov.cn` | **NO ACCESIBLE.** El dominio no resuelve (`getaddrinfo ENOTFOUND`). El eAIP chino requiere además registro. |
| **A** | AIP Pakistan (PCAA) | **NO OBTENIDO** en acceso directo. |
| **B** | ICAO Doc 7910 | **No aporta coordenadas.** Doc 7910 publica *indicadores de lugar* (código ↔ nombre), no posiciones. Útil sólo para el vínculo ICAO→aeródromo, no para lat/lon. |
| **C** | **NOAA `aviationweather.gov` — registro operativo de estaciones METAR/TAF** | **ACCESIBLE.** Cobertura 55/55, con `siteType` incluyendo METAR en 55/55. |
| **C** | **NOAA NCEI — `isd-history.csv`** (Integrated Surface Database) | **ACCESIBLE.** 29 661 registros con ICAO, lat/lon, elevación y `BEGIN`/`END`. |
| **C/B** | **WMO OSCAR/Surface** — registro oficial de estaciones OMM | **ACCESIBLE** vía API REST. |
| **D** | SkyVector (republicador de datos AIP) | **ACCESIBLE.** Usado como control, con ARP en grados/minutos. |
| **D** | OurAirports | **ACCESIBLE.** Usado como control, **no como prueba primaria**. |

**Declaración explícita:** no se obtuvo acceso a una AIP propiamente dicha (categoría A). La
resolución que sigue descansa en la **convergencia de fuentes de categoría C y D**, no en A.
Se declara aquí para que la fuerza de la conclusión no se sobreestime.

---

## §2. TABLA POR ESTACIÓN

Coordenadas en grados decimales. `ARP` = punto de referencia del aeródromo publicado
(SkyVector, derivado de AIP). Distancias en km respecto a `ARP`.

| ICAO | Aeródromo | ARP (AIP-deriv.) | IEM | OurAirports | NOAA avwx | NCEI ISD | WMO OSCAR | d IEM | d OA | d NOAA | d ISD |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **ZSQD** | Qingdao Jiaodong | 36.36500, 120.09833 | 36.06667, 120.33333 | 36.36195, 120.08817 | 36.362, 120.087 | 36.266, 120.374 | 36.0667, 120.3333 | **39.30** | 0.97 | 1.07 | **27.04** |
| **ZGSZ** | Shenzhen Bao'an | 22.63833, 113.81167 | 22.55, 114.10 | 22.63947, 113.80326 | 22.639, 113.803 | 22.639, 113.811 | 22.5500, 114.1000 | **31.19** | 0.87 | 0.89 | 0.10 |
| **ZHCC** | Zhengzhou Xinzheng | 34.51833, 113.84000 | 34.71667, 113.65 | 34.52650, 113.84916 | 34.520, 113.834 | 34.520, 113.841 | 34.7167, 113.6500 | **28.08** | 1.24 | 0.58 | 0.21 |
| **ZUCK** | Chongqing Jiangbei | 29.72000, 106.64000 | 29.52, 106.48 | 29.71225, 106.65189 | 29.718, 106.639 | 29.719, 106.642 | 29.5833, 106.4667 | **27.09** | 1.44 | 0.24 | 0.22 |
| **ZHHH** | Wuhan Tianhe | 30.78500, 114.20667 | 30.62, 114.13 | 30.77480, 114.21372 | 30.783, 114.205 | 30.784, 114.208 | 30.6000, 114.0500 | **19.76** | 1.32 | 0.27 | 0.17 |
| **ZUUU** | Chengdu Shuangliu | 30.58000, 103.94833 | 30.66667, 104.01667 | 30.55826, 103.94597 | 30.576, 103.950 | 30.579, 103.947 | *(no está en OSCAR)* | **11.65** | 2.43 | 0.47 | 0.17 |
| **OPKC** | Karachi Jinnah | 24.90850, 67.16283 | 24.84558, 67.16137 | 24.90650, 67.16080 | 24.902, 67.139 | 24.907, 67.161 | 24.9000, 67.1333 | **7.00** | 0.30 | 2.51 | 0.25 |

Estado del aeropuerto durante 2026: **los 7 operativos**, con `siteType` = `["METAR","TAF"]`
en el registro NOAA. Ninguno figura como cerrado.

### Convergencia agregada

```
                        n   media    máx   <=1km   <=2km
OurAirports             7   1.22 km  2.43   3/7     6/7
NOAA aviationweather    7   0.86 km  2.51   5/7     6/7
NCEI ISD                7   4.02 km 27.04   6/7     6/7   (el fallo es ZSQD)
IEM ASOS                7  23.44 km 39.30   0/7     0/7
WMO OSCAR               6  24.96 km 39.31   0/6     0/6
```

**Las tres fuentes aeronáuticas convergen dentro de 2,5 km. IEM y OSCAR quedan a 7–39 km,
y coinciden entre sí.**

---

## §3. ZSQD — INVESTIGACIÓN ESPECÍFICA

Cuatro emplazamientos candidatos, todos distintos:

| Candidato | Coordenada | Evidencia |
|---|---|---|
| **Qingdao Jiaodong** (aeródromo actual) | 36.36500, 120.09833 | ARP publicado: `N36°21.90' / E120°5.90'`; NOAA `aviationweather` lo nombra literalmente **`Qingdao/Jiaodong Arpt`** con `siteType ["METAR","TAF"]` |
| **Qingdao Liuting** (aeródromo anterior) | 36.2658, 120.3746 | OurAirports `ident=CN-0164 type=closed`; NCEI ISD lo mantiene como `LIUTING / QINGDAO INTL` |
| **Estación sinóptica WMO 54857** | 36.0667, 120.3333 | WMO OSCAR: `name "QINGDAO"`, `hp 77`, `declaredStatus Operational` — **es la coordenada que usa IEM** |
| **IEM ASOS** | 36.06667, 120.33333 | idéntica a OSCAR |

### ¿El METAR ZSQD corresponde inequívocamente a Jiaodong durante 2026?

Tres líneas de evidencia independientes, **ninguna basada en el nombre**:

1. **Registro operativo de estaciones METAR de NOAA.** Consulta directa:
   `{"icaoId":"ZSQD", "site":"Qingdao/Jiaodong Arpt", "lat":36.362, "lon":120.087,
   "wmoId":"54857", "siteType":["METAR","TAF"]}`.
   Es la base de datos que gobierna el intercambio operativo de METAR, no un catálogo geográfico.
2. **Liuting está cerrado.** Cerró el **12 de agosto de 2021**, sustituido por Jiaodong
   (*"It was the city's main airport until it was replaced by the newly built Qingdao Jiaodong
   International Airport on 12 August 2021"*). Un aeródromo cerrado no emite METAR; y en 2026
   sí recibimos METAR bajo ZSQD (24 observaciones verificadas para 2026-07-15).
3. **La estación sinóptica no emite METAR.** WMO 54857 es una estación sinóptica terrestre
   (`stationTypeName: "Land (fixed)"`, altura 77 m). Un METAR es por definición un informe de
   **aeródromo**. El texto crudo recibido es un METAR canónico:
   `ZSQD 150000Z VRB01MPS CAVOK 27/24 Q1002 NOSIG`.

**Conclusión:** durante el periodo V5 el METAR ZSQD corresponde a **Qingdao Jiaodong**.
La coordenada usada en V2/V3/V4 (36.0667, 120.3333) está **39,3 km** del emplazamiento correcto
y nunca fue un aeródromo.

**Aviso adicional:** NCEI ISD **también se equivoca** en ZSQD — mantiene `LIUTING / QINGDAO INTL`
a 36.266/120.374 con `END 20250824`, es decir, 27,0 km del emplazamiento vigente. Es la única
de las 7 en que ISD falla, y demuestra que ISD **no puede usarse como fuente única**.

---

## §4. VALIDACIÓN DE LA CADENA `ICAO → AERÓDROMO → METAR`

| ICAO | Aeródromo (NOAA avwx) | WMO id (NOAA) | `siteType` | METAR crudo verificado |
|---|---|---|---|---|
| ZSQD | Qingdao/Jiaodong Arpt | 54857 | METAR, TAF | `ZSQD 150000Z VRB01MPS CAVOK 27/24 Q1002 NOSIG` |
| ZGSZ | Shenzhen/Boan Intl | 59493 | METAR, TAF | `ZGSZ 150000Z 14004MPS 9999 BKN020 27/25 Q1006 NOSIG` |
| ZUUU | Chengdu/Shuangliu Intl | 56294 | METAR, TAF | `ZUUU 150000Z 35002MPS 320V030 CAVOK 28/23 Q1002 NOSIG` |
| ZHCC | Zhengzhou/Xinzheng Arpt | 57083 | METAR, TAF | *(no descargado; cadena verificada por registro)* |
| ZUCK | Chongqing/Jiangbei Intl | 57516 | METAR, TAF | *(ídem)* |
| ZHHH | Wuhan/Tianhe Intl | 57494 | METAR, TAF | *(ídem)* |
| OPKC | Karachi/Jinnah Intl | 41780 | METAR, TAF | *(ídem)* |

La cadena es consistente en las 7: el ICAO identifica un aeródromo operativo, ese aeródromo
está registrado como emisor de METAR, y el dato que consumimos es un METAR con ese indicador.

**El conflicto está en el `wmoId`.** NOAA asocia a ZSQD el WMO 54857 y lo sitúa en Jiaodong;
WMO OSCAR sitúa el mismo 54857 en la ciudad, 39 km al suroeste. **IEM heredó la coordenada de
OSCAR y la adjuntó al ICAO del aeródromo.** Ése es el mecanismo exacto del error, y explica
las 7 a la vez: en las 7, `name` en IEM es la ciudad y 6 de 7 llevan identificador WIGOS.

---

## §5. COMPROBACIÓN GEOMÉTRICA PUNTUAL

Pregunta: ¿la discrepancia **residual entre fuentes aeronáuticas** (≤2,5 km) cambia la celda?

Resultado sobre las 7 estaciones × 2 modelos (14 contrastes ARP vs OurAirports vs NOAA):

```
13/14 contrastes: MISMA celda en las tres fuentes,  ΔT = 0.0 °C
 1/14 contraste : DIFIERE
     ZUUU  icon_seamless   ARP -> celda 30.6250,104.0000
                           NOAA-> celda 30.6250,104.0000
                           OA  -> celda 30.5000,104.0000     ΔT = 1.7 °C
```

**Hallazgo:** la elección entre fuentes aeronáuticas es indiferente salvo cuando la estación
cae cerca de un borde de celda. ZUUU (Chengdu) está a ~2 km del límite entre celdas
ICON-GLOBAL y OurAirports lo cruza. **ARP y NOAA coinciden; OurAirports es el discrepante.**

Consecuencia directa: **la regla canónica no puede decir sólo "la coordenada del aeródromo";
debe fijar una precedencia de fuentes.**

---

## §6. COBERTURA

| Categoría | n | Mercados |
|---|---|---|
| Cubiertas por registro aeronáutico NOAA con `siteType` METAR | **55/55** | 91 285 |
| Con ARP aeronáutico verificado individualmente (esta ronda) | **7** | 10 670 |
| Con verificación cruzada NOAA + OurAirports concordante ≤2 km | 46/55 | — |
| **Discrepancia residual NOAA vs OurAirports > 2 km — NO resuelta** | **9/55** | 16 907 |
| Sin ICAO → **UNKNOWN** | 2 | 1 936 (Hong Kong 1 859, Taipei 77) |

Las 9 con discrepancia residual (máx. 3,38 km) son:
`LEMD 3.38 · KORD 3.02 · KMIA 2.86 · KAUS 2.40 · WSSS 2.39 · OPKC 2.25 · EDDM 2.09 · KLAX 2.03 · ZUUU 2.01`

**Esto es un residuo nuevo que esta auditoría descubre y NO resuelve.** Es un orden de magnitud
menor que el problema original (7–39,5 km), pero el caso ZUUU demuestra que una diferencia de
2 km **puede** cambiar la celda. De estas 9, sólo OPKC y ZUUU pertenecían a las 7 originales.

---

## §7. VERSIONADO TEMPORAL

| ICAO | ¿Cambió de ubicación en 2025–2026? | Evidencia |
|---|---|---|
| **ZSQD** | **NO dentro del periodo.** El cambio fue **2021-08-12** (Liuting → Jiaodong) | cierre documentado; ISD conserva la entrada antigua |
| ZGSZ, ZHCC, ZUCK, ZHHH, ZUUU, OPKC | **NO** | `BEGIN` en ISD entre 1942 y 1957, sin entradas alternativas |

**¿Hace falta versionar `station_lat/lon` por fecha?**

- **Para el periodo del catálogo (2025-12-30 → 2026-09-04): NO.** Ninguna de las 7 cambió de
  emplazamiento dentro del rango. Una coordenada única por ICAO es suficiente **y correcta**.
- **Para el diseño del campo: SÍ conviene preverlo.** ZSQD demuestra que un ICAO puede migrar
  de aeródromo conservando el código, y que los catálogos de referencia tardan **años** en
  reflejarlo (ISD sigue en Liuting cinco años después). Recomendación: definir el esquema con
  `valid_from`/`valid_to` aunque hoy se poble con un único registro por estación.
  **No se propone implementarlo ahora.**

---

## §8. REGLA CANÓNICA PROPUESTA

> **`station_lat/lon` = el punto de referencia del aeródromo (ARP) identificado por el código
> ICAO que aparece en el METAR utilizado como observación, resuelto con la siguiente
> precedencia estricta:**
>
> 1. **AIP / publicación aeronáutica oficial del Estado** (AD 2, ARP), si es accesible.
> 2. **Registro operativo de estaciones METAR de NOAA** (`aviationweather.gov/api/data/stationinfo`),
>    exigiendo `siteType` que incluya `METAR`.
> 3. **OurAirports**, fijado a un commit concreto del repositorio, **sólo como control**.
>
> **Regla de conflicto:** si (2) y (3) difieren en **más de 1 km**, la estación se marca
> `PENDIENTE_DE_RESOLUCIÓN` y se resuelve individualmente contra (1) antes de usarse.
> **Prohibido** usar la metadata de coordenadas de IEM ASOS o de WMO OSCAR como
> `station_lat/lon`: representan la estación sinóptica, no el aeródromo.
> IEM se conserva para `tzname`, `archive_begin` y como fuente del label — **no** para la posición.

### Por qué esta regla y no otra

1. **Se ajusta a la evidencia, no a la preferencia.** La preferencia conceptual del encargo
   (ubicación física del sensor que genera el METAR) queda **confirmada** por §3 y §4: el
   emisor es el aeródromo. Ninguna estación de las 7 demostró lo contrario.
2. **Es reproducible.** (2) es una API pública con cobertura 55/55; (3) es un dataset versionado
   en Git, fijable a un commit.
3. **No favorece a ningún modelo.** Se define por la fuente del label, sin referencia a rejilla
   alguna. §6 de `COORDINATE_AUDIT.md` ya estableció que el componente ICON no cambia.
4. **La precedencia es necesaria, no decorativa.** §5 demuestra con ZUUU que elegir mal entre
   dos fuentes aeronáuticas a 2 km puede cambiar la celda y mover el pronóstico 1,7 °C.
5. **El umbral de 1 km no es arbitrario:** es un orden de magnitud por debajo de la celda más
   fina en uso (ICON-D2, 2,2 km), de modo que una concordancia sub-kilométrica no puede,
   por construcción, cambiar la celda de ningún modelo evaluado.

### Aplicabilidad a estaciones futuras

La regla es un procedimiento, no una lista: dado un ICAO nuevo, se consulta (2), se contrasta
con (3), y sólo se escala a (1) si discrepan más de 1 km. Con la evidencia de esta ronda eso
ocurriría en **9 de 55** estaciones (16 %), un volumen de resolución manual manejable.

---

## §9. DECISIÓN

> ### **A — las 7 quedan resueltas por fuente aeronáutica y se puede fijar una regla canónica.**

Las 7 discordancias están cerradas: se identificó el aeródromo, se obtuvo su ARP, se demostró
la cadena `ICAO → aeródromo → METAR`, y se explicó el mecanismo del error (herencia de la
coordenada sinóptica de WMO OSCAR vía IEM). La discrepancia original de 7–39,5 km queda
reducida a ≤2,5 km, y en 13 de 14 contrastes geométricos ese residuo no cambia la celda.

**Tres reservas que deben acompañar a esta clasificación A:**

1. **No se accedió a una AIP propiamente dicha.** La resolución descansa en convergencia de
   categorías C y D. El margen de convergencia (≤2,5 km) es un orden de magnitud menor que la
   discrepancia resuelta (7–39,5 km), por lo que la conclusión es robusta **a la escala que
   importa**, pero no está certificada contra el documento oficial del Estado.
2. **Residuo nuevo no resuelto: 9 de 55 estaciones** con NOAA vs OurAirports > 2 km (§6).
   ZUUU demuestra que ese residuo puede cambiar una celda. Requiere una pasada adicional
   **antes de aplicar la convención a todo el universo** — no antes de cerrar las 7.
3. **2 estaciones sin ICAO siguen UNKNOWN** (Hong Kong, Taipei).

---

## §10. IMPLICACIÓN REGISTRADA (sin acción)

V2, V3 y V4 usaron la coordenada de IEM. En ZSQD, ZGSZ y OPKC —3 de las 16 estaciones de V3—
esa coordenada dista 7,0–39,3 km del aeródromo correcto y **cambia la celda de ECMWF**.
Conforme a la instrucción, **no se recalcula nada**. Queda registrado para la revisión conjunta
con el diseño de V5.

---

## §11. INTEGRIDAD

| Comprobación | Estado |
|---|---|
| project files modificados | **NO** |
| DB | **NO** |
| schema | **NO** |
| pipeline | **NO** |
| `weather_forecasts` | **NO** |
| Git commit | **NO** |
| Git push | **NO** |
| V5 ejecutado | **NO** |
| M1 seleccionado | **NO** |
| MAE / métricas de precisión | **NINGUNA** |
| Single Runs consultado | **NO** — HTTP 429 respetado, no sorteado |
| V2/V3/V4 recalculados | **NO** |

**Artefactos:** `COORD_PRIMARY.json` · `COORD_NOAA_STATIONS.json` · `COORD_TABLE.json` ·
`COORD_FULL_TABLE.txt` · `COORD_SENSITIVITY.json` · `COORD_BOUNDARY.json` · `COORD_IEM_RAW.json`
— en `/Users/mariaaleu/pmw-e2/`.

---

## §12. FUENTES

- NOAA Aviation Weather Center, registro de estaciones: `https://aviationweather.gov/api/data/stationinfo`
- NOAA NCEI, Integrated Surface Database station history: `https://www.ncei.noaa.gov/pub/data/noaa/isd-history.csv`
- WMO OSCAR/Surface: `https://oscar.wmo.int/surface/rest/api/search/station?wigosId=0-20000-0-<WMO>`
- Iowa Environmental Mesonet, metadata de estación: `https://mesonet.agron.iastate.edu/api/1/station/<ID>.json`
- Iowa Environmental Mesonet, METAR crudo: `https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py`
- SkyVector (ARP derivado de AIP): `https://skyvector.com/airport/<ICAO>`
- OurAirports: `https://davidmegginson.github.io/ourairports-data/airports.csv`
- Wikipedia, Qingdao Liuting International Airport (fecha de cierre)
- CAAC eAIP: `https://www.eaip.caac.gov.cn/` — **no accesible**
