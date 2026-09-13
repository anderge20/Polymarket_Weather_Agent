# D10 — MAPA DE FRONTERAS SEMÁNTICAS

**No se implementa ningún arreglo de producción durante D10.** Level 1 sigue cerrado: no se
modela, no se seleccionan modelos, no se calcula poder predictivo, edge ni PnL, no se activa
trading y no se toca el gate D0.

**D09-1 no se reabre.** Queda como `REFUTED AS PRODUCTION DEFECT` (A-283): el problema estaba
en `n075_metricas`/`n075_poblacion` usando `observed_value` sin unidad en lugar de
`tmax_observed`, que es Celsius. `exige_celsius()` se mantiene como guardia defensiva del
análisis.

## Método, y por qué no basta `grep`

1. **Grafo de importaciones por AST** (`d09_grafo.py`) — resuelve `from weather_agent import x`
   a módulos concretos.
2. **Barrido de PORTADORES SEMÁNTICOS por AST** (`d10_portadores.py`) — cinco portadores
   (`series`, `measurement_rule`, `observación`, `label`, `winning_outcome`) contra los 48
   módulos de `src/`, `scripts/` y el corpus de análisis, marcando **lee / escribe /
   TRANSFORMA**. *El candidato lo elige el barrido, no yo* — listar las fronteras que ya
   conocía habría confirmado lo que ya creía.
3. **Ejecución real** contra `pmw.duckdb` y contra los módulos (`d09_cadena.py`,
   `d09_spec_labels.py`, `d10_dos_semanticas.py`).

`grep` no es evidencia única en ningún punto: en A-281 `grep Observation(` enganchaba
`NoObservation(`, que no es una frontera.

---

# CADENA R — MODEL SELECTION

`forecast → observation → label → probability → scoring`

### R1 · FORECAST

| campo | contenido |
|---|---|
| **módulo** | `weather_agent/weather.py` (escritor) · `n075_poblacion.pronosticos` (lector) |
| **función** | `weather.*` → tabla `weather_forecasts` → `pronosticos(con, station, leads)` |
| **input** | `(station, target_date, issue_time, available_at, forecast_tmax, dataset_version)` |
| **unidad** | **Celsius en las 49 estaciones.** `weather_forecasts` **NO tiene columna de unidad** |
| **semántica** | máximo previsto del día objetivo, último disponible en `t_asof = end_date − lead` |
| **transformación** | ninguna de unidad; selección por `available_at ≤ t_asof` |
| **output** | `{(target_date, lead): (available_at, forecast_tmax)}` |
| **guard** | `forecast_tmax IS NOT NULL`; `exige_celsius()` aguas arriba |
| **failure mode** | **silencioso** si se compara con una observación en otra unidad (A-283) |
| **test** | `test_m2_module.py`, `test_observations.py` |
| **test real** | NO para la unidad |
| **caller producción** | SÍ (`paper_cycle`) |

### R2 · OBSERVATION

| campo | contenido |
|---|---|
| **módulo** | `weather_agent/observations.py` (escritor) · `n075_poblacion.observaciones` (lector) |
| **función** | `observations.to_row(daily_high, dsv)` → `weather_observations` |
| **input** | METAR horario de IEM, por estación y día civil local |
| **unidad** | **DOS columnas a propósito**: `tmax_observed` **siempre Celsius**; `observed_value` en la **rejilla de la fuente** con `observed_unit` ∈ {C, F} |
| **semántica** | `tmax_observed` = magnitud física normalizada · `observed_value` = lo que la fuente publicó, para liquidar en su propia rejilla (A-41) |
| **transformación** | `_grid(dh)` elige rejilla y unidad; conversión F→C para `tmax_observed` |
| **output** | fila con `observation_time, observed_value, observed_unit, tmax_observed, series, available_at, record_version` |
| **guard** | regla de cobertura `PEAK_LOCAL_HOURS`; `observed_unit <> 'UNKNOWN'` en los lectores |
| **failure mode** | **fail-closed** al ingerir; **silencioso** si el lector elige la columna equivocada |
| **test** | `test_observations.py` |
| **test real** | **SÍ** — `test_observations_real_payload.py`, contra un payload servido |
| **caller producción** | SÍ (`paper_cycle`, `backfill_observations`) |

**Medido (`d10_dos_semanticas.py`, filas reales):**

    EGLC 2026-04-08  observed_value 26,0 C  tmax_observed 26,00 C  -> MISMA banda
    KHOU 2026-04-08  observed_value 78,0 F  tmax_observed 25,56 C
        banda por observed_value : 78-79°F   <- la GANADORA declarada
        banda por tmax_observed  : 67°F or below
    KORD 2026-04-08  71,0 F / 21,67 C  ->  '50°F or higher' (ganadora) contra '31°F or below'

### R3 · LABEL

| campo | contenido |
|---|---|
| **módulo** | `n075_poblacion.poblacion` + `resolution.parse_band` |
| **función** | `poblacion(con, dsv, station)` → evento elegido por `(station, target_date)` |
| **input** | `markets` × `outcomes` con `o.dataset_version = m.dataset_version` |
| **unidad** | **la unidad CONTRACTUAL del mercado** (`markets.unit`) |
| **semántica** | la etiqueta es `markets.winning_outcome = 'Yes'` — **la resolución que el mercado declaró**, no nuestra liquidación |
| **transformación** | `parse_band(label, unit)`; regla de población A-275 (resolved + partición + una ganadora + desempate por `close_time`) |
| **output** | `{fecha: {event_id, bandas[(lo,hi,ganó)], n_bandas, close}}` |
| **guard** | `exige_celsius()` — **se NIEGA** fuera de Celsius en vez de convertir |
| **failure mode** | **fail-closed** desde A-283; antes era silencioso |
| **test** | `d10_dos_semanticas.py` (aislado), `n075_identidades.py` (18 comprobaciones) |
| **test real** | **SÍ** — sobre `pmw.duckdb` |
| **caller producción** | **NO** — es análisis (categoría C) |

> **Defecto conocido y abierto**: `parse_band(banda, "C")` fijo. Hoy inocuo por
> `exige_celsius()`. Tarea #70 · categoría **C**.

### R4 · PROBABILITY

| campo | contenido |
|---|---|
| **módulo** | `n075_metricas.filas` |
| **función** | `filas(pob, obs, FC, lead)` |
| **input** | población R3 + `obs` + `FC` |
| **unidad** | Celsius (garantizado por `exige_celsius`) |
| **semántica** | **REFERENCE / SANITY CONTROLS — NOT LEVEL 1.** `REF_uniforme` = `1/n`, control estructural. `B0`…`B4` = líneas base de referencia |
| **transformación** | `round()` a la rejilla; masa empírica del error para B3/B4 |
| **output** | filas `(event_id, lead, banda, y, {control: p})` |
| **guard** | `len(tr) ≥ 20`; `label_av(d) ≤ t_asof`; probabilidades suman 1 (**verificado, error máx 2,22·10⁻¹⁶**) |
| **failure mode** | fail-closed (evento sin FC o sin 20 pares → fuera) |
| **test** | `n75_h4.py` verifica las fórmulas contra fuerza bruta a `1e-12` |
| **test real** | **SÍ** |
| **caller producción** | **NO** (categoría C) |

### R5 · SCORING

| campo | contenido |
|---|---|
| **módulo** | `n075_metricas` + `n75_h4` |
| **función** | Brier y Log Loss por contrato / evento / evento×lead |
| **input** | filas de R4 |
| **unidad** | adimensional |
| **semántica** | **control de cordura del instrumento**, nunca poder predictivo |
| **transformación** | `clip(p, 1e-6)`; media dentro del evento y luego sobre eventos |
| **output** | Brier/LL por unidad + `BSS_n`/`LSS_n` + `−ln q_ganadora` |
| **guard** | **estratificar por `n` SIEMPRE; prohibido agregar entre escaleras** (H4 = INVALIDADA, A-280) |
| **failure mode** | **silencioso** si se agregan escaleras — la línea base cambia 48 % de 7 a 11 |
| **test** | `n75_h4.py` (derivaciones verificadas) |
| **test real** | **SÍ** |
| **caller producción** | **NO** (categoría C) |

---

# CADENA P — SETTLEMENT

`market → settlement`

### P1 · INGESTA DE MERCADO — **EN VIVO** (`discovery`)

| campo | contenido |
|---|---|
| **módulo** | `weather_agent/polymarket/discovery.py` |
| **función** | `ingest_event(...)`, líneas 378-398 |
| **input** | payload de Gamma + `evidence["resolution_contract"]` |
| **unidad** | n/a (escribe identificadores) |
| **semántica** | **escribe la terna**: `contract_source` y `measurement_rule_code` (el **CÓDIGO**, no la prosa) |
| **transformación** | `classify_measurement_rule` / `parse_resolution_text` (R29) |
| **output** | fila de `markets` con `source='gamma'` |
| **guard** | **`column_names` — sólo escribe si la columna EXISTE** |
| **failure mode** | **silencioso**: si la columna no existe (o la caché de columnas está caducada), deja de escribirla sin avisar — documentado en `database.py:958` |
| **test** | `test_discovery.py`, `test_rule_classifier.py`, `test_ingest_atomic.py`, … |
| **test real** | parcial (`gamma_runner.py` con fixtures) |
| **caller producción** | **SÍ** (`paper_cycle`) |

### P1′ · INGESTA DE MERCADO — **BACKFILL** (`backfill_markets`) ← **FRONTERA NO AUDITADA**

| campo | contenido |
|---|---|
| **módulo** | `scripts/backfill_markets.py` |
| **función** | el `db.upsert` de la línea ~215 |
| **input** | `CATALOG_V2.duckdb`, tabla `mk` |
| **unidad** | n/a |
| **semántica** | **NO escribe `contract_source`, ni `measurement_rule_code`, ni `measurement_rule`** — no están en el dict de la fila |
| **transformación** | ninguna sobre la terna |
| **output** | fila de `markets` con `source='CATALOG_V2'` |
| **guard** | **NINGUNA** |
| **failure mode** | **silencioso y total** |
| **test** | **NINGUNO. Cero ficheros de test mencionan este módulo.** |
| **test real** | NO |
| **caller producción** | **NO en el ciclo paper — pero es quien construyó TODO el almacén de análisis** |

> **Medido:** las **85 878** filas de `markets` tienen `source = 'CATALOG_V2'`. **Cero** vienen
> de `discovery`. Y `ingestion_timestamp` es NULL en las 85 878.
>
> **Ésta es la causa de los 85 878 NULL de la terna, y no es un defecto de `discovery`:** el
> almacén de análisis nunca pasó por la frontera que escribe la terna. **No puede ser
> settlement-ready por construcción**, y que los dos comprobadores digan READY sobre él es por
> tanto doblemente falso.

### P2 · OBSERVACIÓN → NÚCLEO (dos fronteras, una traduce y otra no)

| campo | `paper_cycle.stage_settle` | `labels.observations_for` / `context_for` |
|---|---|---|
| **módulo** | `scripts/paper_cycle.py:1511,1544` | `src/weather_agent/labels.py:136,169` |
| **input** | filas de `markets`+`outcomes`+`weather_observations` | idem |
| **unidad** | `observed_value` + `observed_unit` (rejilla de la fuente) | idem |
| **semántica** | terna + serie traducidas al vocabulario del núcleo | **sin traducir** |
| **transformación** | `to_core_series()` · lee `measurement_rule_code` | **ninguna** · lee `measurement_rule` (**PROSA**) |
| **guard** | `settle_substrate_missing` (sólo presencia) | `missing_substrate` (sólo presencia, y pide la columna equivocada) |
| **failure mode** | **falso READY** | **falso READY** + rechazo total |
| **test** | `test_paper_cycle.py`, `test_observations_real_payload.py` | `test_labels.py` — **clava el defecto como esperado** (línea 119) |
| **test real** | **SÍ** | NO |
| **caller producción** | SÍ | **NO — ningún módulo lo importa** |

### P3 · NÚCLEO CONGELADO

| campo | contenido |
|---|---|
| **módulo** | `weather_agent/settlement.py` — **congelado por sha** `a6d92667…` |
| **función** | `select_operator(contract_source, measurement_rule_code, unit, rounding_rule)` → `try_settle` |
| **unidad** | la del mercado; la serie en el vocabulario del núcleo |
| **semántica** | partición de 11 clases; fail-closed fuera de ella |
| **guard** | la partición misma |
| **failure mode** | **fail-closed, verificado en las SEIS variantes de NULL probadas** |
| **test** | `test_settlement.py` |
| **test real** | **SÍ** (`test_observations_real_payload.py` llega hasta aquí) |
| **caller producción** | SÍ |

> **Es la única pieza de toda la cadena que hace exactamente lo que promete ante un `NULL`.**

### P4 · `labeling.build_label` — frontera huérfana

| campo | contenido |
|---|---|
| **módulo** | `weather_agent/labeling.py` (63 líneas) |
| **input** | `prediction_time`, `resolution_timestamp`, `winning_outcome` |
| **semántica** | etiqueta de entrenamiento sólo si `prediction_time < resolution_timestamp` |
| **guard** | `if not winning_outcome or resolution_timestamp is None` |
| **failure mode** | **SILENCIOSO** — `resolution_timestamp` es NULL en 1 997/1 997, llega como `NaT`, `NaT is None` es `False` y `datetime >= NaT` también, así que **emite una etiqueta con el sello a `NaT`** |
| **test** | `test_resolution_not_in_features.py` (no cubre el `NaT`) |
| **test real** | NO |
| **caller producción** | **NO** |

---

# PUNTO 3 — ¿HAY TERCERAS FRONTERAS? SÍ. **DETENGO Y DOCUMENTO**

El barrido de portadores marcó como **transformadores** seis módulos. Tres **no** estaban en
ninguna auditoría anterior:

| módulo | portador que transforma | estado |
|---|---|---|
| `polymarket/discovery.py` | `measurement_rule` | **NUEVA** — es el escritor correcto de la terna |
| `scripts/backfill_markets.py` | — (omite la terna) | **NUEVA** — construyó las 85 878 filas del almacén |
| `strategy/strategy_a.py` | `winning_outcome` | **NUEVA** — fuera de la ruta de Level 1, pero interpreta la ganadora |
| `features.py` | `observación` | ya conocida; compara `observation_time` para el as-of, no convierte unidades |
| `labeling.py` | `winning_outcome` | ya documentada (D09-5) |
| `settlement.py`, `observations.py`, `labels.py` | varios | ya documentadas |

**Conclusión del punto 3: las fronteras no eran cuatro. Son al menos siete, y la más
consecuente —`backfill_markets`— no tiene un solo test.** Por la regla del encargo, esto solo
ya impide cerrar D10.

---

# PUNTO 4 — CLASIFICACIÓN DE D09-1…D09-6

| id | defecto | **categoría** | por qué |
|---|---|---|---|
| **D09-1** | unidad forecast/observation | **C — análisis** | `REFUTED AS PRODUCTION DEFECT` (A-283). Guardia `exige_celsius()` puesta. Producción elige bien |
| **D09-2** | `parse_band(banda,"C")` fijo | **C — análisis** | vive en `n075_poblacion.py`. Producción usa `band_integrity`, que es correcta |
| **D09-3** | los dos comprobadores de sustrato | **A — infraestructura / guard** | no cambia la interpretación de ningún dato: cambia **cuándo la ruta se niega** |
| **D09-4** | `context_for` pasa prosa por código | **B — semántica de producción** | cambia qué operador selecciona el núcleo |
| **D09-5** | `build_label` deja pasar `NaT` | **B — semántica de producción** | cambia qué filas se consideran etiquetadas |
| **D09-6** | traducción de series fuera de la librería | **B — semántica de producción** | cambia qué observaciones acepta el núcleo |
| **D10-7** | `backfill_markets` omite la terna | **B — semántica de producción** | decide si un `dataset_version` puede liquidarse |

**Los cinco de categoría B quedan pendientes de revisión independiente §34 y no se fusionan.**
Los de categoría C ya están hechos o especificados en el corpus de análisis; el de categoría A
está especificado en `N075_SUSTRATO_LIQUIDACION.md` y **no se implementa durante D10**.

---

# PUNTO 6 — `READY` ≠ `column_exists`. ESPECIFICACIÓN MÍNIMA

```python
def substrate_ready(con, *, scope) -> list[str]:
    """Vacío == la ruta PUEDE ejecutar sobre `scope`. Cualquier otra cosa es una promesa."""
```

`scope` = **las filas que la ruta va a leer** (los `market_id` de las posiciones abiertas y su
`dataset_version`), nunca la tabla entera: un recuento global se deja engañar por una fila
poblada en otra estación.

Cinco condiciones, en orden, cada una con su cadena de diagnóstico:

| # | condición | falla como |
|---|---|---|
| 1 | **esquema** — la columna está declarada | `markets.measurement_rule_code (ausente)` |
| 2 | **no-null obligatorio** — poblada en las filas de `scope` | `markets.measurement_rule_code (presente, 0 de 12 filas pobladas)` |
| 3 | **semántica compatible** — el valor pertenece al vocabulario que el consumidor parte | `markets.measurement_rule_code (valor fuera de la partición de 11 clases)` |
| 4 | **traducción disponible** — existe mapeo para el valor observado | `weather_observations.series (IEM_ASOS_TMPF_0.1F sin traducción declarada)` |
| 5 | **capacidad efectiva** — la siguiente frontera acepta **una** muestra real | `settlement.select_operator rechaza la muestra: context_out_of_snapshot` |

La condición 5 es la que convierte la promesa en hecho: **ejecutar la frontera siguiente sobre
una fila real de `scope` y exigir que no se niegue.** Es barata (una fila) y es la única que no
se puede satisfacer por accidente.

**Invariante que hay que poder afirmar:** *si `substrate_ready` devuelve vacío y la ruta se
niega después, es un defecto de `substrate_ready`, no de la ruta.* Hoy esa frase es falsa para
los dos comprobadores.

---

# PUNTO 7 — `NaT` / RESOLUCIÓN: COMPORTAMIENTO ESPERADO

**Defecto confirmado y mantenido.** Especificación del arreglo (**no implementado**):

```
DADO   resolution_timestamp ausente en cualquiera de sus formas (None, NaT, NaN, "")
CUANDO se pide build_label(...)
ENTONCES no se produce etiqueta liquidada: se devuelve None
Y       la razón queda distinguible de "el mercado no está resuelto"
```

* La comprobación es de **ausencia**, no de identidad con `None`: `pandas.isna(x) or x is None`.
* **Dos razones distintas, no una**: `unresolved` (no hay `winning_outcome`) y
  `missing_resolution_timestamp` (lo hay y falta el sello). Hoy las dos salen como `None` y el
  docstring promete la primera cuando ocurre la segunda.
* **Test de regresión exigido**: conducir la función con una fila **leída del almacén**, no con
  un `datetime` tecleado en un fixture. Un fixture escribe `None` porque es lo que el autor
  tenía en la cabeza, que es justo el caso que la guarda ya cubre.

---

# PUNTO 8 — SERIES: PROPUESTA DE MOVIMIENTO, SIN SEGUNDA TABLA

**Unicidad confirmada**: una sola tabla, `SERIES_CORRESPONDENCE`, cero duplicados por barrido
AST, y mapea **por referencia** a `settlement.SERIES_*` (un renombrado del núcleo se propaga).
El problema es de capa: vive en `scripts/` y **ningún módulo de `src/` importa de `scripts/`**.

**Propuesta (no implementada):** mover la tabla y su lectura a
`weather_agent/observations.py` — dueño natural, ya tiene `SERIES_SOURCE` y `station_series`.
**No a `settlement.py`**, que está congelado por sha.

```python
# weather_agent/observations.py
CORE_SERIES: dict[str, str]          # IEM_* -> settlement.SERIES_*, POR REFERENCIA
def to_core_series(series: str | None) -> str | None: ...
```

`scripts/paper_cycle.py` **reexporta** `SERIES_CORRESPONDENCE = observations.CORE_SERIES` para
no romper los tres tests que la nombran por su nombre actual. **Una sola tabla, dos nombres
para el mismo objeto — nunca dos tablas.**

**Prueba de que el movimiento está completo**: `test_las_fronteras_del_nucleo_son_exactamente_las_declaradas`
(PR #54) sigue verde **y** las dos fronteras llaman a la misma función.

---

# PUNTO 9 — LAS DOS SEMÁNTICAS, DEMOSTRADAS

Reglas mantenidas explícitamente:

1. **las bandas se interpretan en la unidad contractual del mercado** (`markets.unit`);
2. **`tmax_observed` está normalizada a Celsius** (1 486/1 486, error de conversión 0,000000);
3. **pertenencia a banda y error forecast−observación son dos operaciones distintas**;
4. **no se reutiliza una sola variable de temperatura para las dos semánticas.**

`d10_dos_semanticas.py` lo demuestra con filas reales de las dos clases de estación, **todas
las afirmaciones verdes**:

    KHOU 2026-04-08   observed_value 78,0 F        tmax_observed 25,56 C
      banda por observed_value : 78-79°F          <- COINCIDE con la ganadora declarada
      banda por tmax_observed  : 67°F or below    <- otra banda, misma fila
      error correcto   tmax_observed - forecast = -0,24 C
      error incorrecto observed_value - forecast = +52,20   sin excepcion

    EGLC 2026-04-08   las dos lecturas dan la MISMA banda -> aqui el defecto es invisible

---

# PUNTO 10 — CRITERIO DE CIERRE

| condición | estado |
|---|---|
| no existe una tercera frontera no auditada | **NO SE CUMPLE** — aparecen tres nuevas (`discovery`, `backfill_markets`, `strategy_a`) |
| cada frontera tiene contrato semántico explícito | **PARCIAL** — las once de arriba sí; `strategy_a` y `features` quedan descritas, no contratadas |
| se conoce qué arreglos afectan producción | **SÍ** — clasificación A/B/C del punto 4 |
| se conocen sus tests | **NO** — `backfill_markets` no tiene ninguno |
| ningún falso READY sin especificación de reparación | **SÍ** — punto 6 |
| cadenas R y P completamente separadas | **SÍ** — verificado por grafo de importaciones: el análisis importa **una** cosa de la librería, `resolution.parse_band` |

# VEREDICTO

## `D10 = BLOCKED`

Fallan dos condiciones de cierre, y la misma frontera las causa las dos: **`backfill_markets.py`
escribió las 85 878 filas del almacén de análisis sin la terna de liquidación, sin guarda y sin
un solo test.** Es la frontera con más consecuencias del repositorio y no estaba en ningún mapa.

**Lo que esto NO cambia:** las cadenas R y P están limpiamente separadas y la cadena R no
depende de ninguno de los defectos de categoría B. El bloqueo de Level 1 no viene de aquí: viene
de que D10 exige el mapa completo antes de tocar nada, y el mapa acaba de crecer.

**Level 1 sigue cerrado. D0 = BLOCKED. Ningún arreglo de producción implementado.**
