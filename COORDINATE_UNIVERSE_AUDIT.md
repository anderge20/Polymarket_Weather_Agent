# COORDINATE_UNIVERSE_AUDIT — COBERTURA COMPLETA DE COORDENADAS (55 ESTACIONES)

**Fecha:** 2026-09-05 · **Naturaleza:** READ-ONLY
**Bloqueo externo vigente:** `single-runs-api` en HTTP 429. **No consultado, no sorteado.**
Toda la geometría de §9 usa `api.open-meteo.com` (cuota independiente). No se ha calculado
ninguna métrica de precisión. No se ha ejecutado V5. No se ha recalculado V2/V3/V4.

---

## §0. CORRECCIÓN A MI INFORME ANTERIOR

`COORDINATE_PRIMARY_VALIDATION.md` afirmó que *"IEM reproduce literalmente las coordenadas del
registro sinóptico oficial de la OMM"*. **Eso es cierto para las 7 estaciones discordantes,
pero NO es una ley universal.** Sobre las 41 estaciones resolubles en OSCAR:

```
d(IEM, OSCAR):  p50 = 0.905 km   p90 = 7.97 km   max = 30.23 km (ZBAA Beijing)
IEM a <=0.2 km de OSCAR: 13/41
```

La afirmación correcta es la de §3 de este informe: IEM y NOAA pertenecen a la **misma estirpe
de registro** (la estación observadora), y NOAA es la versión operativamente corregida.

---

## §1. UNIVERSO

Las **55 estaciones con ICAO resoluble** de `V5_UNIVERSE_STATIONS.json` (91 285 mercados).

**Fuera:** Hong Kong (1 859 mercados) y Taipei (77 mercados) sin ICAO en el catálogo.
Ver §8.3: no son estaciones sin ICAO, son **periodos** en que el mercado no declaró ICAO.

---

## §2. FUENTES RECOPILADAS

| Fuente | Cobertura | Endpoint |
|---|---|---|
| **A. NOAA AviationWeather** — registro operativo de estaciones METAR/TAF | **55/55**, `siteType` incluye METAR en 55/55 | `aviationweather.gov/api/data/stationinfo` |
| **B. OurAirports** | 55/55 | `airports.csv` (versionado en Git) |
| **C. IEM ASOS metadata** | 55/55 | `mesonet.agron.iastate.edu/api/1/station/<ID>.json` |
| **D. WMO OSCAR/Surface** | **41/55** (14 sin `wmoId` utilizable) | `oscar.wmo.int/surface/rest/api/search/station` |
| **E. ARP aeronáutico publicado** | **15/55** (7 de la ronda anterior + 8 de ésta) | SkyVector (derivado de AIP); **el eAIP de la CAAC sigue sin resolver DNS** |

Tabla completa de las 55 con las cuatro coordenadas: **`COORD_UNIVERSE_TABLE.txt`**.

---

## §3. ¿QUÉ REPRESENTA LA COORDENADA NOAA? — SEMÁNTICA DETERMINADA

Método: contrastar NOAA, OurAirports e IEM contra el **ARP publicado** en 9 estaciones.

| ICAO | d(NOAA, ARP) | d(OA, ARP) | d(IEM, ARP) | Lectura |
|---|---|---|---|---|
| KLAX | 2.03 | **0.00** | 2.04 | OA = ARP; NOAA desplazado |
| EDDM | 2.09 | **0.01** | 1.77 | OA = ARP; NOAA desplazado |
| KMIA | 2.80 | **0.09** | 2.80 | OA = ARP; NOAA desplazado |
| OPKC | 2.51 | **0.30** | 7.00 | OA = ARP; NOAA desplazado |
| KORD | 2.69 | **0.33** | 2.69 | OA = ARP; NOAA desplazado |
| KAUS | 1.64 | **0.82** | 1.60 | OA = ARP; NOAA desplazado |
| WSSS | 1.28 | 1.13 | 1.07 | ambas equidistantes |
| LEMD | **0.84** | 2.55 | 0.76 | **OA erróneo**; NOAA ≈ ARP |
| ZUUU | **0.47** | 2.43 | 11.65 | **OA erróneo**; NOAA ≈ ARP |

Y la relación NOAA↔IEM sobre las 55:

```
d(NOAA, IEM) <= 0.2 km en 30/55    <= 1 km en 39/55
NOAA difiere de IEM > 5 km en 8 estaciones — exactamente las que NOAA corrige
```

Ejemplos exactos (KORD, KMIA): `NOAA 41.96017,-87.93161` ≡ `IEM 41.96020,-87.93160`;
`NOAA 25.78806,-80.31692` ≡ `IEM 25.78805,-80.31693`.

### Respuesta a la pregunta clave

> **La coordenada NOAA NO es el ARP.** Es la posición de la **estación observadora** inscrita
> en el registro de estaciones de NOAA — la misma estirpe que IEM, pero mantenida
> operativamente y corregida donde IEM está obsoleto (los 8 casos > 5 km, ZSQD incluido).
> El desplazamiento sistemático de 1,6–2,8 km respecto al ARP en aeropuertos grandes es
> **coherente con la ubicación descentrada del sensor ASOS**, no con un error.

Y por tanto, respecto a *"¿es una representación suficientemente fiel y reproducible de la
ubicación física que genera el METAR?"*:

- **Fidelidad física: SÍ, y es la mejor de las cuatro** — es la única que apunta a la estación
  observadora y no a una referencia geométrica (OurAirports) ni a una estación sinóptica
  urbana obsoleta (IEM/OSCAR en los 7 casos).
- **Reproducibilidad: NO por sí sola.** Es una API viva, sin versionado ni fecha de corte. Una
  corrección silenciosa cambiaría el valor sin traza. **Esto tiene solución** (§10: congelar
  un snapshot propio), pero debe declararse.
- **LIMITACIÓN NO RESUELTA:** la identificación "NOAA = sensor" es una **inferencia a partir
  del patrón sistemático de desplazamiento**, no una verificación contra un documento de
  ubicación de sensor. No he confirmado la posición real de ningún sensor ASOS.

---

## §4. COMPARACIÓN COMPLETA — DISTRIBUCIÓN

Tabla íntegra en `COORD_UNIVERSE_TABLE.txt` (55 filas: ICAO, ciudad, NOAA, OurAirports, IEM,
WMO, d(NOAA,OA), d(NOAA,IEM), nº de celdas ECMWF/ICON, nº de componentes, mercados).

```
NOAA vs OurAirports   n=55  p50=0.74  p75=1.57  p90=2.25  max=3.38 km
NOAA vs IEM           n=55  p50=0.07  p75=1.37  p90=11.93 max=39.58 km
```

## §5. BANDAS DE DISCREPANCIA — Y POR QUÉ NO SIRVEN COMO REGLA

| Banda | NOAA vs OurAirports | NOAA vs IEM |
|---|---|---|
| **< 1 km** | 33 | 39 |
| **1–2 km** | 13 | 5 |
| **2–5 km** | 9 | 3 |
| **> 5 km** | 0 | 8 |

**Contraste empírico decisivo — la banda NO predice el cambio de celda:**

```
NOAA-vs-OA  <1km    n=33   cambia celda en  6/33
NOAA-vs-OA  1-2km   n=13   cambia celda en  7/13
NOAA-vs-OA  2-5km   n= 9   cambia celda en  6/9
```

Una discrepancia **por debajo de 1 km cambia la celda en 6 de 33 casos**. Un umbral de
distancia —incluido el de 1 km que yo mismo propuse en la ronda anterior— **es el instrumento
equivocado**: no separa lo material de lo inmaterial, porque lo que decide es la posición
relativa al borde de celda, no la magnitud de la discrepancia.

> **Consecuencia congelada: el umbral de 1 km propuesto en `COORDINATE_PRIMARY_VALIDATION.md`
> §8 queda RETIRADO.** La regla debe fundarse en autoridad de la fuente y correspondencia
> física, aplicada uniformemente, no en una tolerancia métrica.

---

## §6. LAS 9 ESTACIONES CON NOAA vs OurAirports > 2 km

Investigadas individualmente contra el ARP publicado (§3). **Ninguna es un conflicto de
identidad de aeródromo**: las 9 nombran el mismo aeropuerto en ambas fuentes
(`Madrid/Barajas`, `Chicago/O'Hare`, `Miami Intl`, `Austin/Bergstrom`, `Singapore/Changi`,
`Karachi/Jinnah`, `Munich Intl`, `Los Angeles Intl`, `Chengdu/Shuangliu`).

| ICAO | Mercados | Veredicto |
|---|---|---|
| KORD, KMIA, KLAX, KAUS, EDDM, OPKC | 11 292 | **OurAirports = ARP; NOAA = estación observadora.** No es error de ninguna: son **magnitudes distintas**. |
| LEMD, ZUUU | 3 707 | **OurAirports es erróneo** (2,4–2,6 km del ARP). NOAA ≈ ARP. |
| WSSS | 1 908 | **Ambiguo**: NOAA 1,28 km y OA 1,13 km del ARP. Sin resolución. |

**Conclusión de §6:** la premisa de la ronda anterior —que estas 9 eran "conflictos por
resolver"— era incorrecta. En 6 de 9 no hay conflicto: hay dos cantidades diferentes, ambas
correctas en su propia definición. En 2 de 9 el error es de OurAirports. En 1 queda abierto.

**Esto invierte la conclusión anterior sobre OurAirports:** no puede ser fuente primaria,
porque mide el ARP —una referencia geométrica— y no el punto de observación; y además tiene
errores propios documentados (LEMD, ZUUU).

---

## §7. ZSQD — DOCUMENTACIÓN COMPLETA

| Elemento | Coordenada | Evidencia |
|---|---|---|
| **Qingdao Liuting** (aeródromo anterior) | 36.2658, 120.3746 | OurAirports `ident=CN-0164 type=closed`; **cerrado 2021-08-12** |
| **Qingdao Jiaodong** (aeródromo actual) | 36.3620, 120.0882 (OA) · ARP 36.3650, 120.0983 | inaugurado 2021-08-12 |
| **ZSQD → NOAA** | 36.362, 120.087 | `{"icaoId":"ZSQD","site":"Qingdao/Jiaodong Arpt","wmoId":"54857","siteType":["METAR","TAF"]}` |
| **ZSQD → IEM** | 36.06667, 120.33333 | = OSCAR WMO 54857 `"QINGDAO"`, `hp 77`, `Land (fixed)` |
| **ZSQD → NCEI ISD** | 36.266, 120.374 | `LIUTING / QINGDAO INTL`, **27,84 km del sitio NOAA** — ISD sigue en el aeropuerto cerrado |
| **METAR 2026 verificado** | — | `ZSQD 150000Z VRB01MPS CAVOK 27/24 Q1002 NOSIG` (24 obs. el 2026-07-15) |

**Ubicación del METAR durante 2025–2026: Qingdao Jiaodong.** El aeródromo anterior está
cerrado desde 2021 y no puede emitir METAR; la estación sinóptica 54857 es `Land (fixed)`, no
un aeródromo, y un METAR es por definición un informe de aeródromo.

> **¿Es válida una única coordenada durante todo el periodo del proyecto?**
> **SÍ.** El cambio ocurrió el 2021-08-12, **más de cuatro años antes** del inicio del catálogo
> (2025-12-30). Dentro de 2025-12-30 → 2026-09-04 la ubicación de ZSQD es constante.

**ZSQD es además el mejor argumento contra usar ISD o IEM:** ambos siguen desactualizados
cinco años después del traslado. Sólo NOAA AviationWeather refleja el cambio.

---

## §8. CAMBIOS TEMPORALES — LAS 55

### 8.1 Traslado de aeródromo
Comprobadas las 55 contra NCEI ISD (`BEGIN`/`END`) y contra las entradas `closed` de
OurAirports en 40 km. **Una única señal real: ZSQD** (d(ISD, NOAA) = 27,84 km). En las 54
restantes, ISD queda a ≤ 2,6 km del sitio NOAA. Las numerosas entradas `closed` cercanas son
aeródromos históricos y helipuertos sin relación con el ICAO evaluado.

### 8.2 Cambio de la ubicación física dentro del periodo
**Ninguno detectado** en 2025-12-30 → 2026-09-04.

### 8.3 Cambio de ICAO — HALLAZGO NUEVO, y NO es un traslado

El catálogo revela que **la estación declarada por el mercado cambia con el tiempo para tres
ciudades**:

```
Hong Kong:  VHHH        2026-03-13 .. 2026-03-14      18 mercados
            (sin ICAO)  2026-03-16 .. 2026-09-03    1859 mercados

Paris:      LFPG        2026-02-18 .. 2026-04-18     575 mercados
            LFPB        2026-04-19 .. 2026-09-04    1540 mercados

Taipei:     (sin ICAO)  2026-03-17 .. 2026-03-22      77 mercados
            RCTP        2026-03-23 .. 2026-04-04     132 mercados
            RCSS        2026-04-05 .. 2026-09-04    1672 mercados
```

París pasó de **Charles de Gaulle a Le Bourget** el 2026-04-19; Taipéi de **Taoyuan a
Songshan** el 2026-04-05. **Son aeródromos distintos, no reubicaciones.** El emisor del METAR
cambió porque **el contrato cambió de estación**, no porque la estación se moviera.

### 8.4 ¿Hace falta `valid_from` / `valid_to`?

> **NO para `station_lat/lon`.** Ningún ICAO cambia de ubicación dentro del periodo del
> proyecto; una coordenada estática por ICAO es correcta y suficiente.
>
> **La dependencia temporal existe, pero vive en otro sitio:** en la relación
> `mercado → ICAO`, que el catálogo ya registra por mercado (`icao2`). La regla correcta es
> resolver el ICAO **desde el propio mercado**, nunca desde la ciudad. Usar la ciudad
> introduciría un error de aeródromo completo en París y Taipéi.
>
> **Recomendación de diseño (no de implementación):** definir el campo como versionable
> (`valid_from`/`valid_to`) aunque hoy se pueble con un registro único por ICAO. ZSQD demuestra
> que un ICAO puede migrar conservando el código y que los catálogos de referencia tardan años
> en reflejarlo. **No se modifica el schema.**

---

## §9. SENSIBILIDAD DE CELDA Y COMPONENTE — 55 × 3 FUENTES

```
celda ECMWF distinta entre fuentes :  9/55
celda ICON  distinta entre fuentes : 16/55
alguna celda distinta              : 19/55
COMPONENTE ICON distinto           :  0/55
spread T ICON  : p50 0.00  p90 0.80  max 2.00 °C   (=0 en 31/55)
spread T ECMWF : p50 0.00  p90 1.10  max 3.10 °C   (=0 en 34/55)
mercados con celda dependiente de la fuente: 32 031 de 91 285  (35.1 %)
```

Estaciones con mayor efecto: ZHCC (ΔT ECMWF 3,1 °C), ZUUU (2,3), OPKC (2,8), ZUCK (1,3),
ZHHH (1,2), ZSPD (1,1), KMIA (ICON 0,8), KAUS (0,7), LEMD (0,6).

**Dos conclusiones:**
1. **El componente ICON es completamente robusto** (0/55). Confirma y extiende el resultado de
   la auditoría anterior: la elección de fuente **no puede** sesgar el contraste ICON vs ECMWF
   por la vía del régimen de resolución.
2. **La celda no lo es.** Un tercio de los mercados del universo tiene una celda que depende de
   qué fuente se elija, con desviaciones de hasta 3,1 °C frente a bandas de mercado de 1 °C.
   **La convención de coordenadas debe fijarse antes de V5, y aplicarse uniformemente.**

---

## §10. DEFINICIÓN CANÓNICA PROPUESTA

> **Para una observación METAR identificada por ICAO y fecha T, la coordenada de solicitud del
> forecast es:**
>
> **`station_lat/lon` = la posición de la estación observadora registrada para ese ICAO en el
> registro operativo de estaciones METAR de NOAA AviationWeather, tomada de un SNAPSHOT
> CONGELADO por el proyecto con fecha de extracción, exigiendo que `siteType` incluya `METAR`.**
>
> - El **ICAO se resuelve desde el propio mercado** (`icao2` del catálogo), **nunca desde la
>   ciudad** (§8.3: París y Taipéi cambian de aeródromo dentro del periodo).
> - **OurAirports = CONTROL**, no fuente primaria ni secundaria. Su función es señalar
>   divergencias para revisión manual; **nunca** sustituir a NOAA automáticamente.
> - **IEM y WMO OSCAR quedan PROHIBIDOS como `station_lat/lon`.** IEM se conserva para `tzname`,
>   `archive_begin` y como proveedor del label.
> - **Sin umbral de tolerancia métrica** (§5: no discrimina).

### Cómo satisface las cuatro prioridades

1. **Correspondencia física con el METAR** — es la única fuente que apunta a la estación
   observadora (§3), y la única que refleja el traslado de ZSQD (§7).
2. **Autoridad de la fuente** — registro operativo que gobierna el intercambio de METAR/TAF;
   cobertura 55/55 con `siteType` METAR verificado.
3. **Reproducibilidad** — **no viene de NOAA sino del snapshot**: congelado, fechado y
   versionado por el proyecto. Es la pieza que convierte una API viva en una fuente reproducible.
4. **Estabilidad temporal** — coordenada estática por ICAO, válida en todo el periodo (§8.4);
   el snapshot se re-extrae y se compara de forma explícita, nunca en silencio.

### Procedimiento para una estación nueva

1. Consultar el registro NOAA; exigir `siteType` ⊇ `{METAR}`.
2. Contrastar contra OurAirports **como control**. Si divergen, **no** se cambia la coordenada:
   se registra la divergencia y se revisa manualmente contra el ARP publicado para verificar
   que **ambas apuntan al mismo aeródromo**. Divergencias de 1–3 km dentro del mismo aeródromo
   son esperables (ARP vs sensor) y **no** son motivo de cambio.
3. Si apuntan a aeródromos distintos → escalar a AIP/autoridad nacional antes de usar.
4. Congelar en el snapshot con fecha de extracción.

---

## §11. CONFLICTOS RESIDUALES

| ICAO | Problema | Fuentes | Impacto | Decisión |
|---|---|---|---|---|
| **WSSS** | NOAA y OurAirports equidistantes del ARP (1,28 / 1,13 km); no se puede discriminar cuál es el sensor | NOAA, OA, ARP | 1 908 mercados; celda ICON **no** cambia | **ABIERTO.** Se usa NOAA por la regla general; se marca para verificación. |
| **OPKC** | NOAA a 2,51 km del ARP, la mayor desviación NOAA-ARP medida; podría ser sensor o error | NOAA, OA, ISD, ARP | 1 551 mercados; **celda ECMWF cambia**, ΔT 2,8 °C | **ABIERTO.** Alto impacto. Requiere AIP de Pakistán. |
| **Premisa "NOAA = sensor"** | Inferida del patrón sistemático, **no verificada** contra ningún documento de ubicación de sensor | — | afecta a la justificación de toda la regla | **ABIERTO.** Es la verificación que separa B de A. |
| **Hong Kong** | 1 859 mercados sin ICAO (settlement HKO, no METAR) | catálogo | 1 859 mercados | **FUERA DE ALCANCE** de esta regla: no es una observación METAR. |
| **Taipei (77 mercados)** | Periodo 2026-03-17..22 sin ICAO declarado | catálogo | 77 mercados | **UNKNOWN.** |
| **14 estaciones sin `wmoId`** | No verificables contra OSCAR | NOAA, OA, IEM | — | Sin impacto: OSCAR no es fuente candidata. |

**Ninguno oculto.** Los dos primeros afectan a 3 459 mercados (3,8 %).

---

## §12. LIMITACIONES

1. **No se accedió a ninguna AIP.** El eAIP de la CAAC no resuelve DNS. Los 15 ARP usados
   proceden de un republicador (SkyVector), categoría D empleada como control.
2. **La semántica de NOAA es inferida, no verificada** (§3, §11). Es la limitación principal.
3. **ARP disponible sólo en 15/55.** Las 40 restantes se aceptan por concordancia NOAA↔OA
   (< 2 km) sin contraste independiente.
4. **Geometría en una sola fecha** y con el endpoint de pronóstico, no Single Runs. La
   asignación de celda es estructural (depende de coordenada y rejilla, no de la fecha) según
   `ARCH_AUDIT_OPENMETEO.md` §7, pero no se ha verificado con Single Runs por el bloqueo 429.
5. **Componente ICON probado en 4 direcciones cardinales** en la ronda anterior; una frontera
   diagonal no quedaría detectada.
6. **No se han recalculado V2/V3/V4**, por instrucción. El impacto de cambiar la convención
   sobre esos resultados queda sin cuantificar.

---

## §13. RESULTADO

> ### **B — regla clara, pero existen estaciones que requieren excepción.**

La regla canónica está definida, es reproducible mediante snapshot y cubre 55/55. Pero:

- **WSSS y OPKC quedan sin resolver** (§11), y OPKC tiene impacto real: cambia la celda ECMWF
  con ΔT de 2,8 °C sobre 1 551 mercados.
- **La premisa que sostiene la regla —que la coordenada NOAA es la estación observadora— es una
  inferencia**, sólida por el patrón sistemático pero no verificada contra documentación de
  ubicación de sensor. Fijar la convención como **A** exigiría esa verificación.
- **40 de 55 estaciones no tienen ARP de contraste independiente.**

No es **C**: existe una regla fundada, con cobertura completa, semántica determinada,
reproducibilidad resuelta vía snapshot y un único caso de dependencia temporal (ZSQD) que
resulta estar fuera del periodo.

---

## §14. INTEGRIDAD

| Comprobación | Estado |
|---|---|
| project files modificados | **NO** |
| DB | **NO** (DuckDB abierto `read_only=True`) |
| schema | **NO** |
| pipeline | **NO** |
| `weather_forecasts` | **NO** |
| Git commit | **NO** |
| Git push | **NO** |
| V5 ejecutado | **NO** |
| M1 seleccionado | **NO** |
| V2/V3/V4 recalculados | **NO** |
| Métricas de precisión / MAE | **NINGUNA** |
| Single Runs consultado | **NO** — HTTP 429 respetado |

**Artefactos:** `COORD_UNIVERSE_TABLE.txt` · `COORD_MASTER.json` · `COORD_UNIGEOM.json` ·
`COORD_OSCAR.json` · `COORD_ARP9.json` · `COORD_NOAA_STATIONS.json` · `COORD_IEM_RAW.json` ·
`_ourairports.csv` · `_isd.csv` — en `/Users/mariaaleu/pmw-e2/`.

**Fuentes:** NOAA AviationWeather `aviationweather.gov/api/data/stationinfo` ·
NOAA NCEI `isd-history.csv` · WMO OSCAR/Surface `oscar.wmo.int/surface/rest/api` ·
IEM `mesonet.agron.iastate.edu/api/1/station/` · OurAirports `airports.csv` ·
SkyVector `skyvector.com/airport/<ICAO>` · CAAC eAIP **no accesible (DNS)**.
