# GATE D0.9 — RUNTIME INTEGRITY

**Alcance: sólo las rutas que usará Level 1.** No se modela, no se entrena, no se
seleccionan modelos, no se calcula edge ni PnL, no se buscan umbrales, no se toca
producción y no se abre trading. Ningún resultado de A-278 se interpreta como evidencia
predictiva.

Todo lo que sigue está **EJECUTADO** contra `pmw.duckdb` y contra los módulos reales.
Guiones y salidas en `~/pmw-e2/d09/`, espejados.

---

## 0. DOS CADENAS, Y HAY QUE DECIR CUÁL ES CUÁL ANTES DE NADA

El encargo nombra `labels.py`, `paper_cycle.py` y los dos comprobadores de sustrato. Al
ejecutar el grafo de importaciones salen **dos cadenas distintas**, y confundirlas
convertiría este informe en una respuesta a la pregunta equivocada:

| | cadena **R** (la que Level 1 ejecutaría) | cadena **P** (liquidación en producción) |
|---|---|---|
| forecast | `weather_forecasts` | `weather.forecast_tmax` |
| observation | `weather_observations` | `observations.to_row` |
| **label** | **`markets.winning_outcome`** | `settlement.try_settle` vía `paper_cycle` o `labels` |
| probability | los controles de referencia (`n075_metricas`) | — |
| scoring | Brier/LL estratificado (A-280) | PnL |

**La cadena R NO pasa por `settlement`, ni por `labels`, ni por la terna, ni por la
traducción de series**: su etiqueta es la resolución que el propio mercado declaró. Los
guiones de Level 1 importan **exactamente una** cosa de la librería: `resolution.parse_band`.

Eso podría leerse como que los defectos de la cadena P no bloquean Level 1. **No es así, y
el motivo es el hallazgo D1: la cadena R tiene su propia frontera semántica inconsistente**,
y es peor que las de P porque nadie la había mirado.

---

## D1 — LA FRONTERA QUE NADIE HABÍA MIRADO: `forecast` y `observation` NO ESTÁN EN LA MISMA ESCALA

    weather_forecasts   columnas con 'unit':  NINGUNA
                        forecast_tmax global: 3,6 .. 43,3        -> CELSIUS en las 49 estaciones
    weather_observations observed_unit:       C  1 195 filas
                                              F    291 filas     -> 11 estaciones en FAHRENHEIT

Ejecutado sobre filas reales del mismo día y estación:

    KHOU 2026-04-08   obs 78,0 F (= 25,6 C)   fc 25,8 C
        error CORRECTO        obs_C - fc_C  =  -0,24 C
        error SIN convertir   obs_F - fc_C  = +52,20     <- ni C ni F: un numero sin unidad
    KMIA 2026-04-08   obs 81,0 F (= 27,2 C)   fc 26,0 C
        error CORRECTO        +1,22 C        sin convertir  +55,00

`n075_metricas.filas()` calcula `errs = [o - fx ...]` **sin tocar la unidad**, porque en
EGLC las dos son Celsius y ahí es correcto. **En las 11 estaciones en Fahrenheit produciría
+52 en vez de −0,24, no levantaría ninguna excepción y devolvería un Brier de aspecto
normal.**

> **`weather_forecasts` no tiene columna de unidad.** La semántica vive fuera de la fila, y
> lo único que hoy impide el error es que el análisis está restringido a una estación que
> resulta ser Celsius. *Abrir Level 1 sin una guarda de unidad significa que la primera
> extensión a otra estación es silenciosamente falsa.*

**Estaciones afectadas: 11 de 49.** Y hay un segundo filo del mismo cuchillo ya registrado:
`n075_poblacion.poblacion()` llama a `parse_band(banda, "C")` **fijo** (A-279 bis, tarea
#70), así que en esas mismas 11 estaciones las bandas se interpretarían en la unidad
equivocada.

---

## D2 — UN TERCER MÓDULO DE ETIQUETAS, Y UN `NULL` QUE ATRAVIESA SU PROPIA GUARDA

El grafo de importaciones encontró `weather_agent.labeling` — **distinto de `labels`**, 63
líneas, huérfano — que construye la etiqueta desde `winning_outcome` + `resolution_timestamp`.
Su docstring promete:

> *«Returns None when: the market is unresolved; **the resolution timestamp is missing**;
> prediction_time is not strictly before resolution.»*

Ejecutado con una fila real de `markets_v2`:

    resolution_timestamp en el almacen:  NaT   (NULL en 1 997 de 1 997 en EGLC)

    build_label(prediction_time=2026-05-26T12:00Z,
                resolution_timestamp=NaT, winning_outcome='Yes')
      -> {'label': 'Yes', 'prediction_time': ..., 'resolution_timestamp': NaT}

**No devuelve `None`. Devuelve una etiqueta con el sello temporal a `NaT`.** La guarda
existe, está documentada, y es inerte: `NaT is None` es `False`, y `datetime >= NaT` también
es `False`, así que la comparación que debía rechazarla la deja pasar.

> Es el caso exacto de H4 y es peor que un fallo: **el `NULL` no rompe nada, produce una
> etiqueta plausible con una marca temporal que no existe**, y el módulo que lo emite dice
> en su propia documentación que eso no puede pasar.

Hoy no corre —no lo importa nadie— pero **es la tercera implementación de «etiqueta» del
repositorio**, y ninguna auditoría anterior la había nombrado.

---

## D3 — LOS DOS COMPROBADORES DE SUSTRATO, CONTRA LOS CUATRO CRITERIOS

| comprobador | 1 columna existe | 2 no-null obligatorio | 3 semántica correcta | 4 la ruta puede consumirlo |
|---|---|---|---|---|
| `paper_cycle.settle_substrate_missing` | **SÍ** | **NO** | SÍ (pide `measurement_rule_code`) | **NO** |
| `labels.missing_substrate` | **SÍ** | **NO** | **NO** (pide `measurement_rule`) | **NO** |

Y sobre el almacén real, ejecutados:

    settle_substrate_missing(pmw.duckdb)  ->  []      "Empty list == ready to settle"
    labels.missing_substrate(con)         ->  []      "Empty means ready"

    measurement_rule_code no-NULL en markets:                 0 de 85 878
    filas de weather_observations con un series del nucleo:   0 de 1 486

**Los dos comprobadores aprueban un almacén en el que la ruta no puede liquidar ni un
mercado.** Éste es el falso READY que da nombre al gate, y hay dos, no uno.

---

## A — SERIES: HAY UNA SOLA FUENTE DE VERDAD, Y ESTÁ EN EL SITIO EQUIVOCADO

    vocabulario del NUCLEO    hko_clmmaxt · metar_body_c · metar_tgroup_tmpf
    vocabulario del ALMACEN   IEM_ASOS_METAR_1C · IEM_ASOS_METAR_1C_RT34
                              IEM_ASOS_TMPF_1F · IEM_ASOS_TMPF_0.1F
    INTERSECCION              VACIA        (y 0 de 1 486 filas llevan un nombre del nucleo)

**Tabla de traducción: exactamente UNA**, `SERIES_CORRESPONDENCE` en
`scripts/paper_cycle.py:1224`, con `to_core_series()` como única lectura. **Cero duplicados**,
verificado por barrido AST de literales de serie en `src/` y `scripts/`.

*Corrección de mi propio instrumento, porque midió mal la primera vez:* el barrido buscaba
ficheros que contuvieran literales de **los dos** vocabularios y devolvió **cero**. La razón
no es que no haya traducción: es que `SERIES_CORRESPONDENCE` mapea literales IEM a
**referencias** `settlement.SERIES_*`, no a cadenas copiadas. **Eso es mejor diseño que lo
que yo buscaba** —renombrar una constante del núcleo se propaga sola— y publicar el «0» sin
mirar habría sido una afirmación falsa con aspecto de hallazgo.

**El problema no es la unicidad: es el alcance.** Verificado por AST: **ningún módulo de
`src/` importa de `scripts/`**. La librería no puede alcanzar la tabla, y por eso `labels.py`
no heredó el arreglo aunque llevaba días hecho.

### API propuesta (definida, NO implementada)

```python
# weather_agent/observations.py   — dueño natural: ya tiene SERIES_SOURCE y station_series
CORE_SERIES: dict[str, str]                      # IEM_* -> nombre del nucleo, POR REFERENCIA
def to_core_series(series: str | None) -> str | None: ...
def core_observation_fields(row: Mapping) -> dict: ...   # value/unit/series ya traducidos
```

**Consumidores demostrados** (no supuestos — son las dos únicas fronteras, verificadas por
AST en el PR #54):

| consumidor | qué usa hoy | qué usaría |
|---|---|---|
| `scripts/paper_cycle.py:1544` | `SERIES_CORRESPONDENCE` local | `observations.to_core_series` |
| `src/weather_agent/labels.py:136` | **nada — pasa el crudo** | `observations.to_core_series` |

**Ausencia de duplicados: verificada.** `settlement.py` sólo declara su propio vocabulario;
`observations.py` sólo el del almacén; `paper_cycle.py` es el único que los une.

**No se implementa.** Falta la revisión independiente de §34 y la sesión B lleva sin
responder desde ~15:00Z.

---

## B — `measurement_rule_code`

**Quién lo consume:** el núcleo congelado parte por la terna
`(contract_source, measurement_rule_code, unit)` — `settlement.select_operator`.

**Quién lo sustituye por la prosa:** `labels.context_for` lee `market.get("measurement_rule")`.
Ejecutado con una fila bien formada de discovery:

    lo que labels pasa   "highest reading under the NOAA 'Temp' column for all times..."
    el codigo real       'P_NOAA_TempColumn'
    select_operator con lo de labels  ->  SettlementUnavailable: context_out_of_snapshot
    select_operator con el codigo     ->  SettlementOperator P_NOAA_TempColumn

`paper_cycle` lee la columna correcta. **De dos fronteras, una la sustituye.**

**Comportamiento ante NULL — ejecutado, seis variantes:**

| terna | resultado |
|---|---|
| completa y correcta | **OK**, devuelve el operador |
| `measurement_rule_code = None` | `context_out_of_snapshot` |
| `measurement_rule_code = ''` | `context_out_of_snapshot` |
| `contract_source = None` | `context_out_of_snapshot` |
| **los dos `None` (lo que hay hoy)** | `context_out_of_snapshot` |
| `unit = None` | `context_out_of_snapshot` |

> **El núcleo congelado falla cerrado en las seis. Es la única pieza de toda la cadena que
> hace exactamente lo que promete ante un `NULL`.** El problema nunca estuvo en el núcleo:
> está en los comprobadores que dicen READY antes de llegar a él.

---

## E — ¿LA LÓGICA DE `paper_cycle` LA NECESITA ALGUIEN EN SILENCIO?

Por AST sobre **todo** el repositorio, no por `grep`:

    importadores de paper_cycle:
      tests/test_observations_real_payload.py   (spec_from_file_location)
      tests/test_paper_cycle.py                 (spec_from_file_location)
    de PRODUCCION (src/ o scripts/):  NINGUNO

**Nadie la necesita en silencio: sólo sus propios tests.** Moverla a la librería no rompe a
nadie, y dejarla donde está es justamente lo que impide que la segunda frontera la herede.

---

## RED-TEAM

### H1 — «READY implica realmente ejecutable»

* **Evidencia a favor:** ninguna.
* **Contraejemplo:** `settle_substrate_missing(pmw.duckdb) == []` y
  `labels.missing_substrate(con) == []`, ejecutados, sobre un almacén con
  `measurement_rule_code` NULL en **85 878 de 85 878** y **0 de 1 486** observaciones con un
  `series` del núcleo. Ninguna de las dos rutas puede ejecutar un solo mercado.
* **Resultado: REFUTADA. Dos falsos READY, no uno.**
* **Confianza: ALTA** (ejecutado sobre el almacén real, no sobre un fixture).

### H2 — «La traducción de series tiene una única fuente de verdad»

* **A favor:** exactamente una tabla, `SERIES_CORRESPONDENCE`; cero duplicados por barrido
  AST; mapea por **referencia** a las constantes del núcleo, así que un renombrado se propaga.
* **En contra:** vive en `scripts/`, y **ningún módulo de `src/` importa de `scripts/`**
  (verificado). La única fuente de verdad es **inalcanzable** desde la mitad de las fronteras.
* **Resultado: SOSTENIDA en unicidad, REFUTADA en alcance.** Una fuente de verdad que una
  frontera no puede leer no es una fuente de verdad para esa frontera.
* **Confianza: ALTA.**
* **Sesgo propio, declarado:** mi primer barrido dio «cero fuentes» y era un artefacto del
  detector. Lo corregí antes de publicarlo; si no lo hubiera mirado, habría publicado lo
  contrario de lo que pasa.

### H3 — «`measurement_rule_code` llega correctamente a las fronteras»

* **A favor:** `paper_cycle` lee la columna correcta.
* **En contra:** `labels.context_for` sustituye por la prosa — ejecutado, el núcleo rechaza.
  Y la columna es **NULL en todas las filas**, así que incluso la frontera correcta recibe
  `None`.
* **Resultado: REFUTADA por dos vías independientes.**
* **Confianza: ALTA.**

### H4 — «`NULL` substrate no puede atravesar silenciosamente un gate READY»

* **A favor:** el núcleo congelado falla cerrado en las seis variantes de `NULL` probadas.
* **En contra:** `labeling.build_label` **emite una etiqueta con `resolution_timestamp: NaT`**
  porque `NaT is None` es `False` y `datetime >= NaT` es `False`. La guarda está escrita,
  documentada e inerte. Y los dos comprobadores de sustrato devuelven `[]` sobre columnas
  enteramente `NULL`.
* **Resultado: REFUTADA.** Y el contraejemplo es de la peor clase: no falla, produce un valor
  plausible.
* **Confianza: ALTA.**

### H5 — «La cadena no tiene una segunda frontera semántica inconsistente»

* **Contraejemplos, cuatro:**
  1. **unidad** `forecast` (C siempre) vs `observation` (C o F) — **en la cadena R**, sin
     columna de unidad en `weather_forecasts`;
  2. **serie** — intersección vacía entre vocabularios, 0 de 1 486 filas;
  3. **terna** — prosa contra código en una de las dos fronteras;
  4. **`parse_band(banda,"C")` fijo** en el guion de población (A-279 bis).
  Y un tercer módulo de etiquetas, `labeling.py`, que ninguna auditoría anterior nombró.
* **Resultado: REFUTADA, con margen.**
* **Confianza: ALTA para las cuatro; las cuatro están ejecutadas o medidas.**

---

# VEREDICTO

## `D0.9 = NOT CLOSED`
## `D0 = BLOCKED`

**No se abre Level 1.** Las cinco hipótesis del red-team están refutadas, y **una de las
cuatro fronteras inconsistentes está en la cadena que Level 1 ejecutaría de verdad** — no en
la de liquidación. Lo que hoy la mantiene inocua no es un arreglo: es que el análisis está
restringido a una estación que resulta ser Celsius.

### Defectos que bloquean, por orden de lo que costaría descubrirlos tarde

| # | defecto | cadena | cómo se manifestaría |
|---|---|---|---|
| **1** | `forecast_tmax` en C contra `observed_value` en F, sin columna de unidad | **R** | Brier de aspecto normal y numéricamente falso en 11 de 49 estaciones |
| **2** | `parse_band(banda, "C")` fijo | **R** | bandas interpretadas en la unidad equivocada en las mismas 11 |
| **3** | dos comprobadores de sustrato que aprueban un almacén vacío | P | «el núcleo rechazó estos mercados» en vez de «no hay sustrato» |
| **4** | `labels.context_for` pasa prosa por código | P | rechazo de todos los mercados, con la causa común oculta |
| **5** | `labeling.build_label` deja pasar `NaT` | R (si se cableara) | etiqueta plausible con sello temporal inexistente |
| **6** | series sin traducir en `labels`, y la tabla fuera del alcance de la librería | P | rechazo de todas las observaciones |

### Especificación de los arreglos, lista y sin implementar

* **`D09-1`** — declarar la unidad de `weather_forecasts` (columna o invariante verificada) y
  **convertir explícitamente en la frontera de scoring**. Guarda mínima: la ruta se niega si
  `observed_unit` de la estación no coincide con la unidad declarada del pronóstico.
* **`D09-2`** — `parse_band` con la unidad del mercado (ya resuelto en `n63_particion_general`;
  además `resolution.band_integrity` ya existe y es la función correcta — A-279 bis).
* **`D09-3`** — los dos comprobadores, contra los cuatro criterios; ámbito = las filas que la
  ruta va a leer, no la tabla entera (propuesta detallada en `N075_SUSTRATO_LIQUIDACION.md`).
* **`D09-4`** — `context_for` lee `measurement_rule_code`; `REQUIRED_COLUMNS` pide la terna.
* **`D09-5`** — `build_label` comprueba `pd.isna`, no `is None`; o se borra el módulo.
* **`D09-6`** — subir la traducción de series a `observations.py` con la API de la sección A.

**Ninguno se implementa aquí.** Los que tocan liquidación necesitan la revisión independiente
de §34 y B lleva sin responder desde ~15:00Z. La prueba aislada `d09_spec_labels.py` deja
`D09-4` y `D09-6` especificados y ejecutables: **todas sus afirmaciones se cumplen hoy**, las
del bloque 1-2 describiendo el defecto y las del bloque 3 el objetivo.

**Nada de esto levanta el gate de dinero real, que sigue siendo exclusivamente del usuario.**
