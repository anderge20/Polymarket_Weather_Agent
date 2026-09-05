# AUDITORÍA ARQUITECTÓNICA READ-ONLY — PIPELINE ESPACIAL DE OPEN-METEO
## `coordenada → celda → (¿interpolación?) → ajuste de elevación → temperature_2m`

**Alcance:** `ecmwf_ifs025` vs `icon_seamless`
**Fecha:** 2026-09-05
**Naturaleza:** READ-ONLY. No se ha modificado código, schema, DuckDB, pipeline, configuración ni Git del proyecto. No se ha creado `weather_forecasts`. No se ha seleccionado M1. No se ha ejecutado V5.
**Ubicación:** fuera del proyecto (`/Users/mariaaleu/pmw-e2/`)

---

## §1. FUENTES OFICIALES CONSULTADAS

Única fuente utilizada: documentación oficial de Open-Meteo (`https://open-meteo.com/en/docs`). No se han usado blogs ni fuentes secundarias.

### 1.1 Citas literales obtenidas

| Concepto | Cita literal |
|---|---|
| `cell_selection` | *"Set a preference how grid-cells are selected. The default `land` finds a suitable grid-cell on land with **similar elevation** to the requested coordinates using a 90-meter digital elevation model. `sea` prefers grid-cells on sea. `nearest` selects the nearest possible grid-cell."* |
| `latitude` / `longitude` devueltos | *"WGS84 of the **center of the weather grid-cell** which was used to generate this forecast. This coordinate might be a few kilometres away from the requested coordinate."* |
| `elevation` | *"The elevation used for **statistical downscaling**. Per default, a 90 meter digital elevation model is used."* |
| `elevation=nan` | *"You can manually set the elevation to correctly match mountain peaks. If `&elevation=nan` is specified, **downscaling will be disabled** and the API uses the **average grid-cell height**."* |
| `seamless` | *"Seamless combines all models from a given provider into a seamless prediction."* |

### 1.2 Lagunas documentales (declaradas explícitamente)

| Pregunta de §OBJETIVO | Estado documental |
|---|---|
| ¿Existe interpolación horizontal? | **NO DOCUMENTADO.** La documentación no menciona interpolación horizontal ni la afirma ni la niega. |
| ¿Qué componentes concretos integra `icon_seamless` y con qué criterio de prioridad? | **NO DOCUMENTADO** a nivel de componente/región. |
| ¿Qué lapse rate usa el downscaling estadístico? | **NO DOCUMENTADO** numéricamente. |
| ¿Difiere el método de extracción entre modelos? | **NO DOCUMENTADO.** |

Estas cuatro lagunas son precisamente las que las pruebas empíricas §2–§6 resuelven. Todo lo que sigue marcado como *observado* proviene de medición, no de documentación.

---

## §2. PRUEBAS EMPÍRICAS READ-ONLY — 16 ESTACIONES, 6 REGIONES

Estaciones: las 16 de la muestra `MODELSEL_GEOVAL_V3_SAMPLE.json` (hash `7a57ce0a040a237b…`), coordenadas reales `req_lat`/`req_lon` sin modificar.
Consulta: Historical Forecast API, `2026-07-15`, `hourly=temperature_2m`, `timezone=UTC`, valor `T12` = hora 12 UTC.
Artefactos: `ARCH_AUDIT_PROBES.json`, `ARCH_AUDIT_CELLSEL.json`, `ARCH_AUDIT_SEAMLESS.json`.

| est | región | modelo | celda devuelta | dist km | elev devuelta | elev celda cruda | T (down) | T (raw) | Δdown |
|---|---|---|---|---|---|---|---|---|---|
| RKSI | ASIA_ESTE | ecmwf_ifs025 | 37.5000, 126.5000 | 5.76 | 6.0 | 10.0 | 24.1 | 24.1 | +0.00 |
| RKSI | ASIA_ESTE | icon_seamless | 37.6250, 126.5000 | 18.15 | 6.0 | 0.0† | 24.1 | 24.3 | −0.20† |
| ZGSZ | ASIA_ESTE | ecmwf_ifs025 | 22.5000, 114.0000 | 11.68 | 14.0 | 45.0 | 27.1 | 26.9 | +0.20 |
| ZGSZ | ASIA_ESTE | icon_seamless | 22.5000, 114.1250 | 6.12 | 14.0 | 141.0 | 26.3 | 25.5 | +0.80 |
| ZSJN | ASIA_ESTE | ecmwf_ifs025 | 36.7500, 117.2500 | 12.37 | 24.0 | 46.0 | 27.2 | 27.1 | +0.10 |
| ZSJN | ASIA_ESTE | icon_seamless | 36.8750, 117.2500 | 4.47 | 24.0 | 12.0 | 27.7 | 27.8 | −0.10 |
| ZSQD | ASIA_ESTE | ecmwf_ifs025 | 36.2500, 120.2500 | 21.71 | 38.0 | 0.0† | 24.1 | 23.8 | +0.30† |
| ZSQD | ASIA_ESTE | icon_seamless | 36.1250, 120.3750 | 7.49 | 38.0 | 15.0 | 24.2 | 24.4 | −0.20 |
| OPKC | ASIA_SUR | ecmwf_ifs025 | 24.7500, 67.2500 | 13.89 | 13.0 | 3.0 | 29.5 | 29.6 | −0.10 |
| OPKC | ASIA_SUR | icon_seamless | 24.8750, 67.1250 | 4.92 | 13.0 | 34.0 | 32.0 | 31.9 | +0.10 |
| VILK | ASIA_SUR | ecmwf_ifs025 | 26.7500, 81.0000 | 11.05 | 123.0 | 117.0 | 32.7 | 32.8 | −0.10 |
| VILK | ASIA_SUR | icon_seamless | 26.7500, 80.8750 | 1.85 | 123.0 | 123.0 | 34.4 | 34.4 | +0.00 |
| EFHK | EUROPA | ecmwf_ifs025 | 60.2500, 25.0000 | 7.74 | 48.0 | 24.0 | 25.6 | 25.8 | −0.20 |
| EFHK | EUROPA | icon_seamless | 60.3125, 24.9375 | 1.51 | 48.0 | 39.0 | 25.3 | 25.4 | −0.10 |
| EGLC | EUROPA | ecmwf_ifs025 | 51.5000, 0.0000 | 3.87 | 4.0 | 17.0 | 26.6 | 26.6 | +0.00 |
| EGLC | EUROPA | icon_seamless | 51.5000, 0.0600 | 0.67 | 4.0 | 13.0 | 26.1 | 26.0 | +0.10 |
| LIMC | EUROPA | ecmwf_ifs025 | 45.7500, 8.7500 | 13.51 | 221.0 | 278.0 | 29.3 | 28.9 | +0.40 |
| LIMC | EUROPA | icon_seamless | 45.6400, 8.7200 | 1.14 | 221.0 | 230.0 | 32.7 | 32.6 | +0.10 |
| UUWW | EUROPA | ecmwf_ifs025 | 55.5000, 37.2500 | 10.20 | 196.0 | 182.0 | 23.2 | 23.3 | −0.10 |
| UUWW | EUROPA | icon_seamless | 55.5625, 37.2500 | 3.30 | 196.0 | 179.0 | 22.4 | 22.6 | −0.20 |
| FACT | HEM_SUR | ecmwf_ifs025 | −34.0000, 18.5000 | 9.94 | 43.0 | 96.0 | 15.4 | 15.1 | +0.30 |
| FACT | HEM_SUR | icon_seamless | −34.0000, 18.6250 | 4.36 | 43.0 | 64.0 | 17.0 | 16.9 | +0.10 |
| SBGR | HEM_SUR | ecmwf_ifs025 | −23.5000, −46.5000 | 8.17 | 743.0 | 780.0 | 11.4 | 11.2 | +0.20 |
| SBGR | HEM_SUR | icon_seamless | −23.3750, −46.5000 | 7.07 | 743.0 | 871.0 | 13.2 | 12.4 | +0.80 |
| MMMX | LATAM_NORTE | ecmwf_ifs025 | 19.5000, −99.0000 | 10.36 | 2223.0 | 2356.0 | 14.3 | 13.4 | +0.90 |
| MMMX | LATAM_NORTE | icon_seamless | 19.3750, −99.1250 | 8.79 | 2223.0 | 2256.0 | 15.4 | 15.2 | +0.20 |
| MPMG | LATAM_NORTE | ecmwf_ifs025 | 9.0000, −79.5000 | 2.61 | 17.0 | 41.0 | 26.9 | 26.7 | +0.20 |
| MPMG | LATAM_NORTE | icon_seamless | 9.0000, −79.5000 | 2.61 | 17.0 | 39.0 | 27.0 | 26.9 | +0.10 |
| LLBG | ORIENTE_MEDIO | ecmwf_ifs025 | 32.0000, 35.0000 | 10.76 | 36.0 | 188.0 | 33.6 | 32.7 | +0.90 |
| LLBG | ORIENTE_MEDIO | icon_seamless | 32.0000, 34.8750 | 1.68 | 36.0 | 38.0 | 31.1 | 31.1 | +0.00 |
| LTFM | ORIENTE_MEDIO | ecmwf_ifs025 | 41.2500, 28.7500 | 1.61 | 106.0 | 85.0 | 27.3 | 27.4 | −0.10 |
| LTFM | ORIENTE_MEDIO | icon_seamless | 41.2500, 28.7500 | 1.61 | 106.0 | 109.0 | 27.3 | 27.3 | +0.00 |

† En estos dos casos `elevation=nan` **también cambió la celda** (ver §5.3), por lo que su Δdown no es un contraste limpio y queda excluido de la verificación cuantitativa.

### 2.1 Metadato espacial disponible

Los únicos metadatos espaciales que la API expone son: `latitude`, `longitude` (centro de celda), `elevation` (DEM 90 m **en la coordenada solicitada**, no de la celda) y `generationtime_ms`. **No expone**: resolución nativa, identificador de dominio, distancia, ni índice de celda. La identificación de resolución de §6 se ha hecho por inferencia empírica, no por metadato declarado.

### 2.2 Asimetría de distancia observada

```
distancia media  ICON = 4.73 km   ECMWF = 9.70 km   ratio = 2.05x
mediana          ICON = 3.83 km   ECMWF = 10.28 km
ICON está más cerca en 13/16 estaciones
```

Esta asimetría **no es ruido de muestreo**: es una consecuencia determinista de la geometría de rejilla (§6).

---

## §3. TEST DE PERTURBACIÓN

Diseño: barridos controlados de la coordenada solicitada, **con el downscaling desactivado (`elevation=nan`)** para aislar la geometría de rejilla del ajuste vertical, y después **con downscaling activo** para medir el efecto conjunto.

### 3.1 Barrido grueso en longitud, `elevation=nan`, EGLC (51.5053), paso 0.05°

**ecmwf_ifs025**
```
lon=−0.10 → celda 51.5000, 0.0000   T12=26.6
lon=−0.05 → celda 51.5000, 0.0000   T12=26.6   (misma celda)
lon=+0.00 → celda 51.5000, 0.0000   T12=26.6   (misma celda)
lon=+0.05 → celda 51.5000, 0.0000   T12=26.6   (misma celda)
lon=+0.10 → celda 51.5000, 0.0000   T12=26.6   (misma celda)
lon=+0.15 → celda 51.5000, 0.2500   T12=26.2   ← SALTO DE CELDA
lon=+0.20 → celda 51.5000, 0.2500   T12=26.2   (misma celda)
lon=+0.25 → celda 51.5000, 0.2500   T12=26.2   (misma celda)
lon=+0.30 → celda 51.5000, 0.2500   T12=26.2   (misma celda)
```

**Este es el resultado decisivo del §3.** La coordenada solicitada recorre **0.20° de longitud (~14 km)** dentro de una única celda y `temperature_2m` permanece **exactamente invariante** (26.6, cuatro consultas idénticas). Cualquier esquema de interpolación horizontal (bilineal, IDW, barycéntrica) produciría variación monótona a lo largo de ese trayecto, porque la ponderación de los vecinos cambiaría continuamente. **No la produce.**

**icon_seamless** (mismo barrido)
```
lon=−0.10 → celda 51.5000, −0.1000   T12=26.2
lon=−0.05 → celda 51.5000, −0.0400   T12=26.2   ← salto
lon=+0.00 → celda 51.5000,  0.0000   T12=26.1   ← salto
lon=+0.05 → celda 51.5000,  0.0600   T12=26.0   ← salto
lon=+0.10 → celda 51.5000,  0.1000   T12=26.0   ← salto
lon=+0.15 → celda 51.5000,  0.1600   T12=25.8   ← salto
lon=+0.20 → celda 51.5000,  0.2000   T12=25.3   ← salto
lon=+0.25 → celda 51.5000,  0.2600   T12=25.9   ← salto
lon=+0.30 → celda 51.5000,  0.3000   T12=25.8   ← salto
```
Con paso 0.05° e ICON sobre Londres (rejilla 0.02°) cada paso cambia de celda, por lo que este barrido **no discrimina**. Nótese además que la serie **no es monótona** (25.3 → 25.9), lo cual es incompatible con interpolación y compatible con muestreo puntual de un campo con estructura.

### 3.2 Barrido fino en longitud, `elevation=nan`, ICON, paso 0.005°

```
lon=0.040 → celda 51.500000, 0.040000   T12=26.0   ← salto
lon=0.045 → celda 51.500000, 0.040000   T12=26.0   (MISMA celda)
lon=0.050 → celda 51.500000, 0.060000   T12=26.0   ← salto
lon=0.055 → celda 51.500000, 0.060000   T12=26.0   (MISMA celda)
lon=0.060 → celda 51.500000, 0.060000   T12=26.0   (MISMA celda)
lon=0.065 → celda 51.500000, 0.060000   T12=26.0   (MISMA celda)
lon=0.070 → celda 51.500000, 0.080000   T12=26.0   ← salto
lon=0.075 → celda 51.500000, 0.080000   T12=26.0   (MISMA celda)
lon=0.080 → celda 51.500000, 0.080000   T12=26.0   (MISMA celda)
```
Dos hechos: (i) dentro de cada celda `T` es exactamente constante; (ii) la frontera está en el punto medio entre centros (entre 0.045 y 0.050 para centros 0.04/0.06) — firma exacta de **vecino más próximo**.

### 3.3 Barrido en latitud **con downscaling ACTIVO**, terreno alpino (LIMC, 8.723 E), paso 0.004°

**ecmwf_ifs025**
```
lat=45.620 → celda 45.5000,8.7500  elev_DEM=216.0  T_down=29.6   [celda cruda: elev=120.0  T_raw=30.3]
lat=45.624 → celda 45.5000,8.7500  elev_DEM=218.0  T_down=29.6   [celda cruda: elev=120.0  T_raw=30.3]
lat=45.628 → celda 45.7500,8.7500  elev_DEM=220.0  T_down=29.3   [celda cruda: elev=278.0  T_raw=28.9]
lat=45.632 → celda 45.7500,8.7500  elev_DEM=222.0  T_down=29.3   [celda cruda: elev=278.0  T_raw=28.9]
lat=45.636 → celda 45.7500,8.7500  elev_DEM=225.0  T_down=29.2   [celda cruda: elev=278.0  T_raw=28.9]
lat=45.640 → celda 45.7500,8.7500  elev_DEM=228.0  T_down=29.2   [celda cruda: elev=278.0  T_raw=28.9]
lat=45.644 → celda 45.7500,8.7500  elev_DEM=228.0  T_down=29.2   [celda cruda: elev=278.0  T_raw=28.9]
lat=45.648 → celda 45.7500,8.7500  elev_DEM=233.0  T_down=29.2   [celda cruda: elev=278.0  T_raw=28.9]
```
Dentro de la celda 45.75/8.75, `T_raw` es **exactamente 28.9** en las seis consultas, mientras `T_down` desciende 29.3 → 29.2 siguiendo el DEM (220 → 233 m). **Toda la variación intracelda procede del término de elevación, ninguna de interpolación horizontal.**

**icon_seamless** (mismo barrido): idéntico patrón — `T_raw` constante 32.6 dentro de la celda 45.64/8.72, `T_down` variando 32.7 → 32.6 con el DEM.

### 3.4 Clasificación exigida en §3 (A–E)

| Clase | ¿Observada? | Evidencia |
|---|---|---|
| **A — pequeñas variaciones mantienen exactamente la misma temperatura** | **SÍ, en ambos modelos** | §3.1 ECMWF: T=26.6 invariante en 4 consultas sobre 0.20°. §3.2 ICON: T=26.0 invariante intracelda. §3.3: `T_raw` exactamente constante intracelda en ambos. Condición: mismo celda **y** mismo DEM. |
| **B — cambia la celda pero no la temperatura** | **SÍ** | §3.2 ICON: celdas 0.040, 0.060 y 0.080 → todas T12=26.0. Un cambio de celda **no implica** cambio de valor. |
| **C — cambia la temperatura suavemente** | **SÍ, pero SOLO vía elevación** | §3.3: con downscaling activo T_down varía en pasos finos (29.3→29.2) siguiendo el DEM de 90 m dentro de una celda fija. Suavidad atribuible **íntegramente** al término vertical. Con `elevation=nan` la suavidad **desaparece por completo**. |
| **D — cambia la temperatura de forma discreta al saltar de celda** | **SÍ, en ambos modelos** | §3.1 ECMWF: 26.6 → 26.2 en la frontera 0.10/0.15. §3.3 ECMWF: T_raw 30.3 → 28.9 al cruzar de la celda 45.50 a la 45.75. |
| **E — existe evidencia de interpolación (horizontal)** | **NO. REFUTADA.** | Test decisivo §3.1: invarianza exacta de `T` a lo largo de ~14 km dentro de una celda ECMWF. Corroborado por §3.2 (constancia intracelda + frontera en el punto medio) y §3.3 (`T_raw` exactamente constante intracelda). No es una inferencia a partir de "el valor cambia"; es una inferencia a partir de que **el valor NO cambia donde la interpolación obligaría a que cambiase**. |

**Conclusión §3:** el pipeline es **A + B + D** en el plano horizontal (vecino más próximo puro, sin interpolación) y **C** en la vertical (ajuste continuo por elevación). **E queda refutada para la componente horizontal.**

Limitación declarada: la refutación de E se apoya en la resolución de salida de la API (**0.1 °C**). Una interpolación cuya variación total a lo largo del trayecto fuese < 0.05 °C sería indistinguible de la invarianza. Sin embargo, el salto observado entre celdas contiguas es de 0.4 °C (ECMWF §3.1) y de 1.4 °C (ECMWF §3.3), de modo que una interpolación entre esos mismos vecinos produciría variación muy por encima del umbral de detección. **La refutación es robusta al redondeo.**

---

## §4. `cell_selection` — `land` vs `nearest`

16 estaciones × 2 modelos = 32 contrastes (`ARCH_AUDIT_CELLSEL.json`).

### 4.1 Resultado agregado

| | celdas distintas `land` vs `nearest` |
|---|---|
| `ecmwf_ifs025` | **1 / 16** |
| `icon_seamless` | **1 / 16** |

En **30 de 32** contrastes `land` y `nearest` devuelven exactamente la misma celda, la misma `elevation` y la misma temperatura.

### 4.2 Los dos casos en que sí cambia

| est | modelo | d(land) | d(nearest) | Δd | T(land) | T(nearest) | ΔT |
|---|---|---|---|---|---|---|---|
| RKSI (Incheon) | `icon_seamless` | 18.15 km | 5.76 km | **+12.39 km** | 24.1 | 24.2 | −0.1 |
| ZSQD (Qingdao) | `ecmwf_ifs025` | 21.71 km | 10.54 km | **+11.17 km** | 24.1 | 23.6 | +0.5 |

Ambas son **estaciones costeras/insulares**. El heurístico `land` rechaza la celda más próxima (que cae sobre mar) y salta a una celda terrestre más lejana. Ese es exactamente el comportamiento descrito en la documentación (*"finds a suitable grid-cell on land"*).

### 4.3 Respuestas a las cuatro preguntas de §4

- **¿Cuándo cambia la celda?** Solo cuando la celda más próxima no satisface el criterio tierra/elevación — en esta muestra, únicamente en estaciones costeras (2/32 = 6.25 %).
- **¿Cuándo cambia la temperatura?** Solo cuando cambia la celda. En los 30 casos con celda idéntica, ΔT = 0.0 exacto. En los 2 casos con celda distinta, ΔT = −0.1 y +0.5.
- **¿Cuándo cambia la elevación?** **Nunca.** `elevation` fue idéntica en 32/32 contrastes. Esto es consistente con la documentación: `elevation` es el DEM de 90 m **en la coordenada solicitada**, no una propiedad de la celda; por construcción es invariante a `cell_selection`.
- **¿Afecta de forma diferente a ICON y ECMWF?** **No sistemáticamente** (1 caso cada uno). Pero el *mecanismo* sí es asimétrico en su consecuencia: al ser la rejilla de ICON más fina, un rechazo de celda por `land` puede desplazarlo proporcionalmente mucho más (RKSI pasa de 5.76 a 18.15 km, ×3.15), mientras que ECMWF, ya grueso, se desplaza ×2.06. En RKSI el heurístico `land` **destruye la ventaja de proximidad de ICON** y lo deja más lejos que ECMWF (18.15 vs 5.76 km). Este es el único punto de la muestra donde ICON está sustancialmente más lejos que ECMWF, y **es un artefacto de configuración, no de modelo**.

---

## §5. ELEVACIÓN — ¿QUÉ ES EXACTAMENTE `temperature_2m`?

### 5.1 Test de forzado de elevación (EGLC 51.5053 / 0.0553, misma coordenada, solo varía `elevation`)

```
ecmwf_ifs025:  sin elevation  → celda 51.5, 0.0    elev=4.0   T12=26.6
               elevation=0    → T12=26.7   (ΔT respecto al DEM: +0.10)
               elevation=100  → T12=26.0   (ΔT −0.60)
               elevation=500  → T12=23.4   (ΔT −3.20)
               elevation=1000 → T12=20.2   (ΔT −6.40)
icon_seamless: sin elevation  → celda 51.5, 0.06   elev=4.0   T12=26.1
               elevation=1000 → T12=19.6   (ΔT −6.50)

gradiente implícito:  ECMWF −6.50 °C/1000 m   ·   ICON −6.50 °C/1000 m   → IDÉNTICO
```

### 5.2 Verificación cuantitativa del modelo de downscaling

Hipótesis contrastada: `T_down − T_raw = (elev_celda − elev_solicitada) × 0.0065 °C/m`.

Sobre los 30 contrastes limpios (excluidos los 2 de §5.3):

```
n = 30   |error| medio = 0.0376 °C   |error| máximo = 0.0895 °C
casos con |error| > 0.05 °C (= mitad del paso de redondeo de la API): 4/30
```

El error residual es del orden del redondeo de salida (0.1 °C). **La hipótesis del lapse rate constante de −6.5 °C/km queda confirmada cuantitativamente sobre todo el rango observado (elev_celda − elev_solicitada de −152 m a +152 m, y elevaciones absolutas de 4 m a 2 223 m).**

### 5.3 Hallazgo colateral relevante: `elevation=nan` puede cambiar la celda

En 2 de 32 casos (**RKSI/`icon_seamless`** y **ZSQD/`ecmwf_ifs025`**) declarar `elevation=nan` alteró también la celda seleccionada:

```
RKSI icon_seamless   def = 37.6250,126.5000   nan = 37.5000,126.5000
ZSQD ecmwf_ifs025    def = 36.2500,120.2500   nan = 36.0000,120.2500
```

Son **exactamente las mismas dos estaciones** en que `land` ≠ `nearest` (§4.2). Interpretación coherente: al desactivar el downscaling se desactiva también el componente "elevación similar" del heurístico `land`, y la selección revierte a proximidad. Esto **no invalida** ninguna otra medición, pero obliga a excluir esos 2 casos del contraste de §5.2 (hecho) y a no tratar `elevation=nan` como un cambio puramente vertical.

### 5.4 Conclusión de §5

`temperature_2m` **no está tomado directamente del grid**. Es:

```
temperature_2m(lat_req, lon_req)  =  T_grid[ celda_seleccionada ]
                                   − 0.0065 × ( DEM90(lat_req, lon_req) − h_media_celda )
```

es decir, **el valor de la celda ajustado estadísticamente a la elevación de la coordenada solicitada**, con un lapse rate fijo de −6.5 °C/km. No se ha detectado ninguna otra transformación.

**Punto crítico para MODELSEL: este ajuste es idéntico para ambos modelos.** El downscaling vertical **no es un diferenciador** entre `ecmwf_ifs025` e `icon_seamless`.

---

## §6. `seamless` — QUÉ ES Y QUÉ COMPONENTE ACTÚA EN CADA REGIÓN

### 6.1 Método de identificación

La API no declara qué componente usa. Se identificó por **comparación directa**: para cada estación se consultó `icon_seamless` y, por separado, `icon_d2`, `icon_eu` e `icon_global`, y se buscó cuál reproduce **simultáneamente** el centro de celda exacto y **la serie horaria completa de 24 valores**. La coincidencia triple (celda + 24 valores) hace la identificación inequívoca.

Validación del método en dos puntos europeos donde los tres componentes están disponibles:

```
EGLC (Londres)
  icon_seamless → celda 51.500000, 0.060000    T12=26.1
  icon_global   → celda 51.500000, 0.000000    T12=26.0   (difiere)
  icon_eu       → celda 51.500000, 0.062500    T12=26.0   (difiere)
  icon_d2       → celda 51.500000, 0.060000    T12=26.1   ← IDÉNTICO a seamless

LFPG (París)
  icon_seamless → celda 49.020000, 2.560000    T12=29.7
  icon_global   → celda 49.000000, 2.500000    T12=29.4   (difiere)
  icon_eu       → celda 49.000000, 2.562500    T12=29.4   (difiere)
  icon_d2       → celda 49.020000, 2.560000    T12=29.7   ← IDÉNTICO a seamless
```

El método discrimina limpiamente: los tres componentes dan celdas y valores distintos, y `seamless` reproduce exactamente uno.

### 6.2 Mapa de composición sobre las 16 estaciones de MODELSEL

| región | estación → componente activo |
|---|---|
| EUROPA | EGLC → **ICON-D2** · LIMC → **ICON-D2** · EFHK → **ICON-EU** · UUWW → **ICON-EU** |
| ORIENTE_MEDIO | LLBG → **ICON-EU** · LTFM → **ICON-EU** |
| ASIA_ESTE | RKSI, ZGSZ, ZSJN, ZSQD → **ICON-GLOBAL** |
| ASIA_SUR | OPKC, VILK → **ICON-GLOBAL** |
| HEM_SUR | FACT, SBGR → **ICON-GLOBAL** |
| LATAM_NORTE | MMMX, MPMG → **ICON-GLOBAL** |

**Reparto: ICON-GLOBAL 10/16 · ICON-EU 4/16 · ICON-D2 2/16.**

Resoluciones inferidas de la retícula de centros de celda devueltos: ICON-D2 ≈ 0.02° (~2.2 km), ICON-EU ≈ 0.0625° (~7 km), ICON-GLOBAL ≈ 0.125° (~13 km), frente a ECMWF IFS 0.25° (~28 km) **uniforme en todo el globo**.

### 6.3 Respuesta a §6

De las cuatro opciones planteadas, `seamless` es la **segunda**: *combinación de diferentes dominios/resoluciones ICON*. Concretamente, una **jerarquía de anidamiento por prioridad de dominio**: se sirve el dominio disponible más fino (D2 → EU → GLOBAL). No es un único modelo con resolución variable, ni una combinación de modelos de proveedores distintos.

### 6.4 Consecuencia arquitectónica — el hallazgo central de esta auditoría

**`icon_seamless` no es un modelo. Es tres modelos, y cuál actúa depende de la región.**

Y la composición **está correlacionada con la variable de estratificación de V3**:

```
EUROPA        → D2/EU  (2.2–7 km)
ORIENTE_MEDIO → EU     (7 km)
resto         → GLOBAL (13 km)
```

Esto significa que **MODELSEL_GEOVAL_V3, que se diseñó como test de generalización geográfica, fue de facto también un test entre regímenes de composición de modelo**, sin que eso estuviera declarado en su preregistro (`135d46f9…`). Región y componente ICON están casi perfectamente confundidos en esa muestra. Es una limitación de especificación de V3 que esta auditoría descubre a posteriori; **no altera V3 ni su preregistro**, pero condiciona cómo debe leerse su resultado.

`ecmwf_ifs025`, en cambio, es un único modelo con una única resolución en todas las regiones. **La comparación V3 no era simétrica en este eje.**

---

## §7. CONCLUSIÓN ARQUITECTÓNICA

De las opciones A–F planteadas, el pipeline real se clasifica como:

> ### **E — combinación distinta según modelo/región**

Con la descomposición precisa siguiente:

| Componente | `ecmwf_ifs025` | `icon_seamless` | ¿Comparable? |
|---|---|---|---|
| **Selección de celda** | vecino más próximo + heurístico `land` (tierra/elevación similar, DEM 90 m) | idéntico | **SÍ — mismo algoritmo** |
| **Interpolación horizontal** | **ninguna** (refutada empíricamente, §3) | **ninguna** (refutada empíricamente, §3) | **SÍ — ambos sin interpolación** |
| **Ajuste vertical** | downscaling estadístico, lapse rate fijo −6.5 °C/km, DEM 90 m en la coordenada solicitada | **idéntico, mismo lapse rate** (§5.1–5.2) | **SÍ — cuantitativamente idéntico** |
| **Rejilla subyacente** | 0.25° (~28 km), **uniforme global** | **0.02 / 0.0625 / 0.125° según dominio y región** | **NO — asimétrico** |
| **Identidad del modelo** | única | **tres modelos según región** | **NO — asimétrico** |

**Lectura:** en términos del *algoritmo de extracción*, ambos modelos reciben un tratamiento **idéntico** — la clasificación de la transformación pura sería **B (grid-cell selection + ajuste de elevación), sin interpolación**. Lo que hace que la respuesta global sea **E** no es el algoritmo, sino **el objeto sobre el que opera**: rejillas de resolución muy distinta y, en el caso de ICON, variable por región.

Formalmente:

```
B  =  clasificación de la transformación   (idéntica para ambos modelos)
E  =  clasificación del pipeline completo  (porque el sustrato — rejilla y
      composición de modelo — difiere entre modelos y, en ICON, entre regiones)
```

### 7.1 Elementos que permanecen UNKNOWN

Se declaran explícitamente, sin sustituirlos por inferencia:

1. **Criterio exacto de prioridad y de mezcla de `seamless` en las fronteras de dominio.** Se ha observado que el dominio más fino disponible gana en 16/16 estaciones, pero **ninguna estación de la muestra cae cerca del borde de un dominio**. Si existe suavizado, ponderación o transición en la frontera, esta auditoría **no lo ha probado**. UNKNOWN.
2. **Estabilidad temporal de la composición.** La asignación estación→componente se midió para una única fecha (2026-07-15). Si D2/EU cambian de dominio, resolución o disponibilidad a lo largo del histórico, la composición podría no ser constante en el periodo de MODELSEL. **No verificado.** UNKNOWN.
3. **Tolerancia exacta del heurístico `land`** (qué diferencia de elevación o qué fracción de tierra dispara el rechazo de celda). Solo se han observado 2 activaciones. UNKNOWN.
4. **Si `temperature_2m` incorpora alguna corrección adicional dependiente del modelo** por debajo del umbral de 0.1 °C de la API. No detectable con la resolución de salida disponible. UNKNOWN, aunque acotado a < 0.1 °C.

---

## §8. IMPLICACIÓN PARA MODELSEL — LA PREGUNTA CRÍTICA

> *"¿La distancia estación→celda es una variable de confusión que debemos neutralizar para seleccionar M1, o es parte intrínseca de la representación espacial de cada modelo y por tanto debe formar parte de la evaluación operativa?"*

### 8.1 Respuesta

**Es parte intrínseca de la representación espacial de cada modelo. NO es una variable de confusión y NO debe neutralizarse igualando distancias.**

### 8.2 Argumento

**(a) Estructura causal.** Un confusor es una causa común del tratamiento y del resultado. Aquí el "tratamiento" es la identidad del modelo. La distancia estación→celda **no causa** la elección del modelo: es una **consecuencia determinista** de ella. Dada la coordenada de la estación y la rejilla del modelo, la distancia queda completamente determinada — no hay ninguna aleatoriedad ni ninguna tercera variable que la genere:

```
resolución de rejilla  →  distancia al centro de celda  →  error de representatividad  →  error de pronóstico
        ↑
   identidad del modelo
```

La distancia es un **mediador** en la cadena causal que va del modelo al error, no un confusor. Controlar por un mediador **bloquea precisamente la parte del efecto que queremos medir** y, además, puede inducir sesgo de colisionador si existen causas no observadas comunes a la distancia y al error (p. ej., la complejidad orográfica local, que afecta tanto a dónde cae la celda de tierra como a la magnitud del error).

**(b) El estimando contrafactual sería inexistente.** Igualar distancias responde a la pregunta: *"¿qué error tendría ICON si tuviera la rejilla de ECMWF?"*. Ese modelo **no existe y no puede desplegarse**. La pregunta operativa que MODELSEL debe responder es otra: *"dada una estación y un horizonte, ¿qué modelo, consultado exactamente como lo consulta nuestro pipeline, produce menor error?"* — y ese estimando **incluye** la distancia que la rejilla del modelo impone.

**(c) La resolución fina es parte del producto, no un sesgo de medición.** Que ICON esté en promedio a 4.73 km y ECMWF a 9.70 km (§2.2) no es un artefacto de extracción: es la manifestación de que ICON resuelve el terreno mejor. Penalizar o neutralizar esa ventaja equivaldría a descontar de la comparación exactamente aquello por lo que un modelo de alta resolución es preferible.

**(d) La componente vertical del error de representatividad ya está parcialmente corregida, y de forma simétrica.** El downscaling (§5) ajusta ambos modelos a la elevación real de la estación con el mismo lapse rate. Lo que queda de "error por distancia" es la componente **horizontal** de representatividad, que es irreductiblemente una propiedad de la rejilla.

### 8.3 Matiz esencial — sí hay algo que debe neutralizarse, pero no es la distancia

La auditoría identifica **dos categorías estrictamente distintas** que el V4 no separaba:

| | Naturaleza | ¿Neutralizar? |
|---|---|---|
| **Resolución de rejilla y geometría de celda** | Propiedad **intrínseca** del modelo | **NO.** Es el objeto de la comparación. |
| **`cell_selection` y `elevation`** | **Configuración del cliente**, aplicada por igual a ambos modelos | **SÍ, en el sentido de fijarla y preregistrarla** — nunca de ajustarla por modelo. |
| **Composición región-dependiente de `icon_seamless`** | **Defecto de especificación de la entidad comparada** | **SÍ — debe declararse y estratificarse**, no promediarse en silencio. |

El caso RKSI es la ilustración exacta de la segunda fila: `cell_selection=land` (el **defecto**, es decir, lo que el pipeline usa hoy sin haberlo decidido) desplaza a ICON de 5.76 km a 18.15 km, invirtiendo su posición relativa frente a ECMWF. Eso **no** es la representación espacial de ICON; es una **decisión de configuración no preregistrada** que actúa de forma desigual sobre modelos de distinta resolución. Debe fijarse explícitamente y documentarse — no dejarse en el valor por defecto por omisión.

### 8.4 Consecuencia sobre la lectura de V4

El V4 (veredicto **B**: ventaja persiste pero pequeña/no concluyente) no queda invalidado, pero **cambia su estatus interpretativo**:

- **Sigue siendo válido como diagnóstico descriptivo**: responde a *"¿la ventaja de ICON se explica únicamente por geometría?"*, y su respuesta (a 9 h la ventaja **se refuerza** bajo control de distancia, con IC que excluye el 0 en U=2 y U=5) es informativa y ahora tiene una lectura arquitectónica clara: la ventaja de ICON a 9 h **no** es un simple artefacto de proximidad.
- **No debe usarse como estimador de ajuste** para seleccionar M1. Su especificación condiciona por un mediador; su coeficiente no tiene interpretación causal como "efecto del modelo neutralizando la distancia".
- **La reversión de signo a 24 h a favor de ECMWF en los tres umbrales** conserva todo su interés y ahora admite una hipótesis arquitectónica concreta y contrastable: a 24 h la ventaja de resolución se disipa y domina la calidad del modelo global, algo consistente con que 10/16 estaciones estén servidas por ICON-GLOBAL a 13 km.

### 8.5 El verdadero problema descubierto — y no es la distancia

El hallazgo con mayor impacto sobre MODELSEL **no es** el confusor espacial que motivó el V4. Es §6.4:

> **`icon_seamless` no es una entidad única.** En la muestra V3, la región y el componente ICON están confundidos casi perfectamente (EUROPA → D2/EU, resto → GLOBAL). Un resultado agregado sobre `icon_seamless` mezcla tres modelos de resoluciones entre 2.2 y 13 km, y su composición **no es la misma** que tendría en el universo real de mercados del catálogo.

Esto tiene una consecuencia operativa directa: **la composición de `icon_seamless` en la muestra de evaluación debe coincidir con su composición en el universo de despliegue**, o el resultado no es transportable. Nada de lo hecho hasta ahora ha verificado esa correspondencia.

---

## §9. DECISIÓN SOBRE V5

> ### **C — V5 necesario, pero debe diseñarse de otra forma; NO modificar artificialmente coordenadas para igualar distancias.**

### 9.1 Por qué no A

La comparación actual **es** operacionalmente válida en lo relativo a la distancia (§8.1–8.3): ese eje está cerrado y no requiere corrección. Pero **no** es válida en lo relativo a la entidad comparada: `icon_seamless` es tres modelos con composición confundida con la región (§6.4), y eso **no estaba declarado en ningún preregistro**. Un resultado agregado sobre una entidad heterogénea no declarada no es una base suficiente para fijar M1.

### 9.2 Por qué no B

**No existe sesgo de extracción que corregir.** El algoritmo de extracción es demostrablemente idéntico para ambos modelos: mismo criterio de selección de celda, ausencia de interpolación en ambos, y downscaling vertical cuantitativamente idéntico (−6.5 °C/km verificado con error medio de 0.038 °C sobre 30 contrastes). Lo que difiere es la rejilla subyacente, y eso **es el modelo**, no un sesgo del método de extracción.

La única excepción — el heurístico `land` en estaciones costeras — afecta al 6.25 % de los contrastes y es una **decisión de configuración**, no un sesgo sistemático de extracción. Se trata fijándola y declarándola, no corrigiendo el benchmark.

### 9.3 Por qué no D

La arquitectura de extracción está ahora **suficientemente caracterizada** para decidir. Los cuatro UNKNOWN residuales de §7.1 son acotados y ninguno afecta a la validez de la comparación: el criterio de frontera de dominio (ninguna estación está en un borde), la tolerancia del heurístico `land` (aislada a 2 casos identificados), y las correcciones sub-0.1 °C (por debajo del umbral de decisión). El único UNKNOWN con peso real — la **estabilidad temporal de la composición de `seamless`** — es precisamente uno de los objetos que V5 debe verificar, no un impedimento para diseñarlo.

### 9.4 Qué debería ser V5 — recomendación (no ejecutada)

Presentada como recomendación para revisión, sin preregistro, sin ejecución, y sin fijar métricas — el preregistro precede siempre a la ejecución.

**No** un experimento de igualación de distancias. En su lugar, un benchmark que corrija el **defecto de especificación de la entidad**:

1. **Declarar la composición como estrato explícito.** Estratificar por componente ICON efectivo (D2 / EU / GLOBAL), medido y registrado por estación-fecha, **no** por región. Región y componente deben dejar de estar confundidos: la muestra debe incluir estaciones servidas por GLOBAL dentro de Europa y, si existen, estaciones servidas por EU fuera de ella.
2. **Verificar la estabilidad temporal de la composición** a lo largo de todo el periodo de evaluación, no en una única fecha (UNKNOWN 2 de §7.1). Si la composición no es estable, la entidad `icon_seamless` no es siquiera constante en el tiempo y eso debe declararse antes de cualquier métrica.
3. **Fijar y preregistrar la configuración de extracción** — `cell_selection` y política de `elevation` — con el **mismo** valor para todos los modelos, documentando cuál es y por qué. Hoy el pipeline usa los valores por defecto sin haberlo decidido. Considerar explícitamente si `land` es la política deseada para estaciones aeroportuarias costeras, dado el caso RKSI.
4. **Comparar contra los componentes nombrados**, no solo contra el agregado: incluir `icon_global` como brazo separado permite distinguir *"ICON es mejor"* de *"la alta resolución es mejor donde está disponible"*. Son dos conclusiones distintas con implicaciones operativas distintas.
5. **Verificar la correspondencia de composición con el universo de despliegue**: la distribución de componentes ICON en la muestra debe reflejar la del universo real de mercados de CATALOG_V2, o el resultado no es transportable (§8.5).
6. **Conservar la distancia como covariable descriptiva reportada, nunca como ajuste** del estimando principal (§8.2).

---

## §10. LIMITACIONES DE ESTA AUDITORÍA

1. **Fecha única.** Todas las pruebas usan `2026-07-15`. La geometría de rejilla es estructural y no depende de la fecha, pero la **composición de `seamless`** sí podría variar (declarado como UNKNOWN 2 en §7.1).
2. **Resolución de salida de 0.1 °C.** Acota la detección de efectos finos. La refutación de la interpolación horizontal es robusta a este límite (§3.4), pero eventuales correcciones dependientes del modelo por debajo de 0.1 °C serían indetectables.
3. **16 estaciones, 6 regiones.** Cobertura suficiente para las conclusiones estructurales, insuficiente para caracterizar el heurístico `land` (solo 2 activaciones observadas) o el comportamiento en fronteras de dominio (0 observaciones).
4. **Resoluciones inferidas, no declaradas.** Los pasos de rejilla (0.02 / 0.0625 / 0.125 / 0.25°) se infirieron de la retícula de centros de celda devueltos y del test de perturbación, no de metadatos de la API. La **identificación de componente** de §6, en cambio, es directa y no inferida (coincidencia exacta de celda + serie horaria completa de 24 valores).
5. **Un único primer intento de clasificación de rejilla fue erróneo** y fue corregido: la divisibilidad de una sola coordenada no identifica el paso de rejilla (un centro en 0.25° es también múltiplo de 0.125° y de 0.0625°). Los resultados aquí presentados usan el método de comparación directa contra modelos nombrados, que no tiene esa ambigüedad.
6. **Solo `temperature_2m`.** No se han auditado otras variables ni los cuantiles `p10..p90`.
7. **Solo Historical Forecast API.** No se ha verificado que Single Runs API o Previous Runs API apliquen la misma transformación espacial.

---

## §11. RESUMEN EJECUTIVO

| § | Pregunta | Respuesta |
|---|---|---|
| 3 | ¿Hay interpolación horizontal? | **NO, en ninguno de los dos modelos.** Refutada, no inferida: `T` es exactamente invariante a lo largo de ~14 km dentro de una celda ECMWF. Clases observadas: **A + B + D** en horizontal, **C** solo vía elevación. |
| 4 | ¿`cell_selection` afecta distinto a ICON y ECMWF? | **No sistemáticamente** (1/16 cada uno), pero el heurístico `land` puede desplazar a ICON ×3.15 en estaciones costeras (RKSI: 5.76 → 18.15 km), anulando su ventaja de proximidad. Es **configuración**, no modelo. |
| 5 | ¿Qué es `temperature_2m`? | Valor de celda **ajustado a la elevación** de la coordenada solicitada, lapse rate **−6.5 °C/km**, **idéntico en ambos modelos** (verificado: error medio 0.038 °C, n=30). |
| 6 | ¿Qué es `seamless`? | **Combinación de dominios/resoluciones ICON** (D2 → EU → GLOBAL, el más fino disponible). En la muestra: **10 GLOBAL / 4 EU / 2 D2**, con composición **confundida con la región**. |
| 7 | Clasificación del pipeline | **E — combinación distinta según modelo/región.** La *transformación* es B e idéntica para ambos; el *sustrato* (rejilla, composición) es asimétrico. |
| 8 | ¿La distancia es confusor? | **NO. Es intrínseca.** Es un mediador determinista, no un confusor; igualarla responde a un contrafactual inexistente. **No debe neutralizarse.** |
| 9 | ¿V5? | **C — necesario, pero con otro diseño.** No igualar distancias; corregir el defecto de especificación de la entidad `icon_seamless`. |

**Hallazgo de mayor impacto:** el problema serio para MODELSEL **no era** el confusor espacial que motivó el V4 — ese eje se cierra a favor de mantener la distancia en la evaluación. El problema serio es que **`icon_seamless` no es un modelo único**, y su composición está confundida con la región de estratificación de V3.

---

**ESTADO: M1 NO SELECCIONADO. V5 NO EJECUTADO. NADA DEL PROYECTO MODIFICADO.**
