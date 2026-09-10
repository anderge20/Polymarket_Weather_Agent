# PREREG_BACKTEST_STRATEGY_A.md

> **Preregistro del backtest de Strategy A V1 — versión 2.0 (RONDA 1 de refutación aplicada; borrador para congelar).**
> Fecha de redacción: 2026-09-07. Sustituye a `PREREG_BACKTEST_STRATEGY_A.draft.md` (v1.0, sha `2f02fb6bf334fd4dfeea534eebf8e2371d96427542f8e31dc83f29e295bd5848`, OBSERVADO 2026-09-07).
> Aplica los **31 hallazgos** de `WF_r18_refutations.json` (sha `d94885a525a28b30c626fcb0cb9bc08c1ea4f882b7e92930cf90eac098a37c83`; 3 refutadores, 3 BLOQUEANTES, 13 IMPORTANTES, 15 MENORES). El detalle hallazgo → acción + motivo está en la sección **«Changelog v2»**, al final; no hay ningún hallazgo rechazado, y los tres ajustes sobre correcciones propuestas se declaran allí.
> Baseline de código: `origin/main` = `dfdc73e` (worktree read-only `/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-main`).
> Este documento se congela y se hashea (`PREREG_BACKTEST_STRATEGY_A.sha256`) **antes** de implementar el motor de backtest (ROADMAP R19) y **antes** de cualquier ejecución que produzca métricas (R21). Cualquier cambio posterior es una **enmienda numerada** (§10.3), nunca una edición in situ.

**Convención de evidencia (sustituye a la leyenda [OBS]/[INF]/[DEC] de v1.0, que confundía «leído» con «inferido»):**

- **OBSERVADO** — leído o recomputado por el autor sobre código congelado, artefacto en disco o `CATALOG_V2.duckdb` (`read_only=True`), con la fecha del recómputo.
- **STRONGLY SUPPORTED** — categoría heredada de un informe con n e IC Wilson 95 %; no se eleva aquí.
- **INFERIDO** — razonamiento sin artefacto que lo separe de alternativas.
- **UNKNOWN** — no determinado; donde una condición del universo o del as-of sea UNKNOWN, la regla es **fail-closed**.
- **DEC** — decisión que este preregistro fija ahora, con su justificación. Una vez congelado el documento, deja de estar abierta.
- **DV-k** — desviación deliberada respecto de un documento congelado, declarada como tal.

**Citas.** Las decisiones se citan **por identificador (D0…D19)** y nunca por número de línea, junto con el sha256 de la versión de `DECISIONS.md` usada. El código se cita por `ruta:líneas` sobre `dfdc73e` (ficheros versionados, estables bajo el commit).

**Fuentes y hashes (OBSERVADO, recomputados 2026-09-07):**

| Artefacto | sha256 |
|---|---|
| `DECISIONS.md` — sha **declarado** en `DECISIONS.sha256` | `d36749bf30677733b1cff57b2c5fd0a67844c88c63d2f71b0cc8403307b1f0af` |
| `DECISIONS.md` — sha **del fichero en disco 2026-09-07** | `f2b3ce2545a0fa5aa1b4ab12f37a9adf2500bb1656fc4582089060483ba23602` |
| `SETTLEMENT_OPERATORS_SPEC.v2.md` (v2, **borrador pendiente de congelar**) | `c2b59dd6d3091e77662a519921e2aac0e4c4a36d1a2c05cda315d9b3fa063003` |
| `STATION_REGION_COMPONENT_v1.json` | `b6aeeacb69ed9bbe18a9e9ab3c48c85ae8bbb14a1079d3857e648d0055adf24e` |
| `STATION_TZ_v1.json` | `35d68e6532a99b97e9d9596491f40e20d13e05bee9fc9feb7a1897318b050bd2` |
| `STATION_COORDS_SNAPSHOT_v1.3.json` | `c1617939e91d43a69e100a10fe69f73eab4aacf52b1968cd09754ef5f0f25f2f` |
| `FEES_SEMANTICS.md` (D19) | `4dbad3ab090ea9264821f5a35f144d69c321b953f93fe826e3f8d57f4ef39465` |
| `PREREG_LEAD_HOURS_RANGE.md` | `1d4161e8943aa9a7813b95ffc1e47fd04f501f8f1643724017b8f974e67354f7` |
| `PREREG_MODELSEL_ASOF_V2.md` | `2b815fcb6b43051b4422a879f3ff0ba53d32b8fe9dd15f1d34c5f6a85af3af46` |
| `PREREG_E2.md` | `c7f031ec9c266295417621426bdb14b222bc91d508d282cafed81b123df033d7` |
| `MODELSEL_V5_REPORT.md` (fichero vigente) | `9b4eb1885850cd0ac93e3341f2c61a125722149d6cb82a044c16eeea6fd4a2b0` |
| `MODELSEL_V5_CORRECTION_01.md` | `1a7a0275fc3356d9ba7ebfefc66b9719098cb5e58f430554eb35127338bbf9d9` |
| `PHASE_2E_LEAD_HOURS_ANCHOR.md` (untracked, `/private/tmp/pmw-publish`) | `6e405d1a0fb2e60ab94af239ec5e17efe696c7c13d03017e8ab0bb4d2ee6d72b` |
| `WF_r18_refutations.json` | `d94885a525a28b30c626fcb0cb9bc08c1ea4f882b7e92930cf90eac098a37c83` |

> **Precondición documental BLOQUEANTE para el congelado (OBSERVADO 2026-09-07):** `DECISIONS.sha256` vuelve a estar desactualizado — declara `d36749bf…` mientras el fichero en disco hashea `f2b3ce25…` (se han añadido D20, D21 y D22 el 2026-09-07). Además **el identificador `D21` aparece duplicado** (sesión A «R29: la clasificación de la fuente de settlement se corrige en el código» y sesión B «prices.py reconciliado…»), y `ROADMAP.md` cita `D18`, que no existe. Citar por identificador exige identificadores únicos: antes de hashear este preregistro deben (a) regenerarse `DECISIONS.sha256`, (b) desambiguarse el `D21` duplicado, (c) corregirse o registrarse `D18`. Este documento cita D0, D1, D9-bis, D12, D16, D17 y D19, todos ellos **únicos** en la versión `f2b3ce25…`, y el manifiesto del run (§9) registrará el sha vigente en el momento del congelado, no el declarado hoy.

---

## 0. Pregunta única y qué NO decide

### 0.1 Pregunta única (H0/H1)

> **¿Genera Strategy A V1 — señales BUY/FADE sobre `edge_gross = p_weather − p_market`, con `p_weather` derivado del forecast as-of de M1 = `icon_seamless` (D12) y un umbral `tau` seleccionado exclusivamente fuera de muestra y con criterio as-of — un PnL neto bajo H1 (`pnl_net_H1`) acumulado positivo, con IC95 bootstrap que excluya 0 y signo estable bajo leave-one-station-out, sobre el universo cerrado de §1.1 (estratos con operador de settlement habilitado por `SETTLEMENT_OPERATORS_SPEC` v2), en el periodo as-of estricto (`target_date ∈ [2026-06-03, D_fin]`), al lead de veredicto de 24 h, con ejecución hipotética a precio no ejecutable, `x_exec = 0`, `hold_to_resolution` y tamaño fijo de 1 share?**

- H0: `pnl_net_H1` acumulado OOS ≤ 0 (o IC95 incluye 0).
- H1: `pnl_net_H1` acumulado OOS > 0 con IC95 que excluye 0 y signo estable LOSO.

### 0.2 Qué NO decide este backtest [DEC]

1. **No decide sizing.** Tamaño fijo 1 share; Kelly/fixed_fraction (`config.py:202-212`, sin consumidor, OBSERVADO) quedan para R20 con preregistro propio.
2. **No revisa M1 — y M1 NO es exógeno respecto a este backtest.** `icon_seamless` es ADOPTADO (D12). **Declaración obligatoria (R2.H4): M1 y `L_max` se fijaron con datos del MISMO periodo que aquí se evalúa** (`target_date ∈ [2026-06-03, 2026-09-04]`, `PREREG_MODELSEL_ASOF_V2.md`, `PREREG_MODELSEL_GEOVAL_V3.md`) y en **24 de las 55 estaciones canónicas** (`STATION_REGION_COMPONENT_v1.json`, campo `in_modelsel`, 24 True / 31 False; OBSERVADO). Este backtest **no es un test confirmatorio de M1**: hay sesgo de selección («el modelo que mejor lo hizo aquí, evaluado aquí»), de magnitud no acotada por este diseño. La defensa preregistrada es el **segmento obligatorio `in_modelsel` sí/no** (§6.3(i)) y el veredicto secundario sobre las estaciones no usadas (§7.2). `L_max = 4,76 h` es el **máximo de 78 pasadas de `dwd_icon`** (`F3-CLOSURE-REPORT.md`, OBSERVADO; las 307 pasadas son el total de los 4 modelos — cifra corregida respecto a v1.0), estimado también dentro del periodo evaluado; se reporta sensibilidad `L_max + 1 h` sin reselección (§2.2).
3. **No decide la semántica real de fees.** H1 es hipótesis (D19); H2/H3 son sensibilidad. El test de falsación forward con el primer fill real (`FEES_SEMANTICS` §7) es independiente. `fee_regime`, `feeSchedule` y `tick` son **el estado ACTUAL de Gamma, no una lectura as-of**: la vigencia histórica es UNKNOWN (`FEES_SEMANTICS` §7; OBSERVADO por el refutador: los 51.051 mercados del periodo estricto comparten `feeSchedule`, luego el riesgo es un reescalado uniforme, parcialmente cubierto por H3 = 2·H1).
4. **No estima `x_exec`.** `x_exec = 0` es supuesto declarado; `0,5·tick` y 1 pt son estrés, no estimaciones (R22).
5. **No evalúa la época `fees_disabled` ni la sub-época CLOB V1.** Ambas caen fuera del periodo con `available_at` PARTIAL (INFERIDO sobre `FEES_SEMANTICS` × `F3-CLOSURE-REPORT`).
6. **No autoriza dinero real ni órdenes** (D0).
7. **No valida el ancla temporal 2E ni la cota `L_max`**: los hereda (§2.1, §2.2).
8. **No decide el lead operativo por defecto**; el lead de veredicto (24 h) es una elección metodológica (§2.1).
9. **No es una comparación entre modelos meteorológicos** (eso fue MODELSEL V5).
10. **No implementa ni valida el `SettlementOperator` de R12.** `p_weather` se calcula con el mapeo CDF→banda **legado de 2D LOCKED**. La consecuencia — que ese mapeo está **REFUTADO** para el estrato HKO y es **UNKNOWN** para los estratos °C — se decide ahora en §3.1 (DV-1) y determina el universo de señales; no se deja a un componente futuro.
11. **No congela la `SETTLEMENT_OPERATORS_SPEC` v2.** Esa spec es un **borrador pendiente de congelar** (sha `c2b59dd6…`). Para que el universo de este backtest no dependa de un documento no congelado, **la enumeración cerrada de estratos y sus recuentos se fijan en este documento (§1.1 y Anexo D)**; un cambio posterior de la spec **no** cambia el universo salvo enmienda §10.3.

---

## 1. Universo y periodo

### 1.1 Universo por enumeración cerrada [DEC] — sustituye a U3 y U5 de v1.0

**Motivo (R1.H0, BLOQUEANTE).** En v1.0 el universo quedaba definido por `compat_status` «según la salida de R14», un componente inexistente, con un vocabulario (`COMPATIBLE`/`UNKNOWN`/`INCOMPATIBLE`) que no existe en ningún documento. Eso delegaba a después del congelado la decisión más grande del diseño: si entra o no `P_WU_GENERIC_sin_calificador`, el 62 % del catálogo de la ventana. Se sustituye por una **lista cerrada de estratos `(contract_source, primary_rule, unit, rounding_rule)` con sus recuentos**, alineada con los estratos que `SETTLEMENT_OPERATORS_SPEC` v2 §2.2/§2.3 declara con `settle` **HABILITADO** o **HABILITADO_CON_PROXY**, y con el vocabulario `compat_status ∈ {DIRECT, PROXY_AUDITED, PROXY_NOT_AUDITED, NONE}` de esa spec.

**Fuente de la clasificación [DEC]: `v3.primary_source` y `v3.primary_rule` de `CATALOG_V2.duckdb`, NUNCA `markets.measurement_rule` ni `cls2.measurement_rule`.** Motivo (R0.H0 BLOQUEANTE + spec v2 §5 paso 0): la columna `measurement_rule` la produce `resolution.parse_measurement_rule` (`polymarket/resolution.py:126-138`), que devuelve `None` salvo que la descripción contenga «Daily Observations» / «by the Forecast» / «Day High & Low». En la ventana con `endDate ≥ 2026-06-03` hay **38.665/51.051 mercados con `measurement_rule` NULL** (jun 14.894/14.894, jul 16.687/16.687, ago 7.051/17.259, sep 33/2.211) y **P_HKO_AbsDailyMax es NULL en 1.859/1.859** (OBSERVADO por el refutador). Mantener el U5 de v1.0 («`measurement_rule` no nulo») vaciaba junio y julio, dejaba E1 imposible **antes de ver un dato** y excluía el 100 % de HKO contradiciendo al propio U3. Además la misma regex clasifica como regla WU la frase de **fallback** NOAA en **3.333 mercados** (spec v2 §5 paso 0). Por tanto: **`measurement_rule` deja de ser filtro y pasa a ser etiqueta de segmentación** con valor declarado `NULL/GENERIC` (§6.3(c)).

#### 1.1.1 Enumeración completa de la ventana estricta (OBSERVADO 2026-09-07; `v3`, `event_endDate ∈ [2026-06-03, 2026-09-04]`; 51.051 mercados / 4.641 eventos; los eventos particionan exactamente: 2.195+692+636+187+696+11+131+93 = 4.641)

| # spec v2 | contract_source | primary_rule | unit | rounding | n_mercados | n_eventos | `settle` (spec v2) | Estado en este preregistro |
|---|---|---|---|---|---|---|---|---|
| 1 | WU | `P_WU_GENERIC_sin_calificador` | C | whole degree | **24.145** | **2.195** | FAIL_CLOSED (`Y_undefined_by_contract`) | **EXCLUIDO** |
| 2 | WU | `P_WU_GENERIC_sin_calificador` | F | whole degree | **7.612** | **692** | FAIL_CLOSED | **EXCLUIDO** |
| 3-4 | WU | `P_byForecast` | C / F | whole degree | **0** | **0** | FAIL_CLOSED | EXCLUIDO (0 casos en ventana) |
| 5 | WU | `P_WU_DailyObservations` | C | whole degree | 6.996 | 636 | HABILITADO_CON_PROXY (`PROXY_AUDITED`, prereg E2 7/7) | **INCLUIDO** menos cláusula → **6.941 / 631** |
| 6 | WU | `P_WU_DailyObservations` | F | whole degree | **2.057** | **187** | FAIL_CLOSED (`proxy_not_audited_F`, 0 casos en E2) | **EXCLUIDO** |
| 7 | NOAA | `P_NOAA_TempColumn` | C | whole degree | 7.656 | 696 | HABILITADO_CON_PROXY (`PROXY_AUDITED`, prereg E2 16/16) | **INCLUIDO** menos cláusula → **5.841 / 531** |
| 8 | NOAA | `P_NOAA_TempColumn` | F | whole degree | 121 | 11 | HABILITADO_CON_PROXY (`PROXY_AUDITED`, prereg E2 6/6) | **INCLUIDO** → **121 / 11** |
| 9 | NOAA | `P_NOAA_HourlyData` | F | whole degree | **1.441** | **131** | FAIL_CLOSED (`series_filter_unverified`, spec v2 §4.3) | **EXCLUIDO** |
| 10 | HKO | `P_HKO_AbsDailyMax` | C | tenths | 1.023 | 93 | HABILITADO (`DIRECT`, floor 164/166) | **INCLUIDO en el universo de label; EXCLUIDO del universo de señales V1** (§3.1, DV-1) |
| 11 | SIN_CLAUSULA (CWA) | `P_UNKNOWN` | C | tenths | **0** | **0** | FAIL_CLOSED (`source_inaccessible`) | EXCLUIDO (los 77/7 del catálogo son de 2026-03-17..22, fuera de la ventana; OBSERVADO) |

**Mercados con cláusula «resolve to the lowest bracket»** (`v3.descr ILIKE '%lowest bracket%'`; OBSERVADO en ventana): NOAA TempColumn C **1.815 / 165**; WU DailyObs C **55 / 5**; NOAA HourlyData F 594 / 54 (ya excluido por fila 9); HKO **11 / 1**; resto 0. Por `SETTLEMENT_OPERATORS_SPEC` v2 §4.2 cond. 6, el estrato «con cláusula» de las filas 5, 7 y 8 tiene **0 casos auditados** → `compat_status = PROXY_NOT_AUDITED` → **excluidos** (`reason = clause_stratum_not_audited`, `stage = universe`): **1.870 mercados / 170 eventos**. Los **11 mercados HKO con cláusula** sí reciben label `DIRECT` flagueado (spec v2 §2.3) y permanecen en el universo de label, marcados `clause_lowest_bracket = TRUE`.

#### 1.1.2 Totales del universo [DEC]

| Universo | n_mercados | n_eventos | n_estaciones | % del catálogo de la ventana |
|---|---|---|---|---|
| Catálogo de la ventana estricta | 51.051 | 4.641 | 55 (canónicas) | 100 % |
| **U-LABEL** — estratos con `settle` habilitado (filas 5, 7, 8, 10; sin cláusula salvo HKO) | **13.926** | **1.266** | **51** | 27,28 % |
| **U-SIGNAL** — U-LABEL menos HKO (§3.1, DV-1) | **12.903** | **1.173** | **50** | 25,28 % |
| Excluido por regla de estrato + cláusula | 37.125 | 3.375 | — | 72,72 % |
| Excluido adicionalmente por mapeo p_weather (HKO) | 1.023 | 93 | 1 | 2,00 % |

Desglose del excluido por regla (suma exacta: 24.145 + 7.612 + 2.057 + 1.441 + 1.870 = **37.125**).

**Todos los eventos del universo tienen exactamente 11 bandas** (mediana = mín = máx = 11; OBSERVADO).

**Cualquier cambio de esta lista o de estos recuentos es una enmienda §10.3 con nuevo hash y re-run completo etiquetado.** Un cambio de `SETTLEMENT_OPERATORS_SPEC` posterior al congelado **no** modifica el universo por sí solo.

#### 1.1.3 Tabla congelada `primary_rule → compat_status` y su evidencia (R0.H1)

| Estrato | `compat_status` | Evidencia preregistrada | Evidencia no preregistrada | Origen |
|---|---|---|---|---|
| WU / `P_WU_DailyObservations` / C | `PROXY_AUDITED` (`IEM_METAR`) | E2 **7/7** (IC Wilson 0,646–1,0) | 7/7 LOCAL_ONLY | `PREREG_E2.md` sha `c7f031ec…` → `E2_RESULTS.json` |
| NOAA / `P_NOAA_TempColumn` / C | `PROXY_AUDITED` | E2 **16/16** (0,806–1,0) | 8/9 (excepción abierta Taipei 322448, NEITHER) | ídem |
| NOAA / `P_NOAA_TempColumn` / F | `PROXY_AUDITED` | E2 **6/6** (0,610–1,0) | 0 | ídem |
| HKO / `P_HKO_AbsDailyMax` / C | `DIRECT` (`HKO_CLMMAXT`) | `HKO_OPERATOR_TEST.json`: floor **164/166** (0,957–0,997); discriminantes `band_key` **n_disc = 81**, floor 81/81 vs half-up 4/81 | — | D17; spec v2 fila 10 |
| WU / `P_WU_GENERIC_sin_calificador` / C, F | `NONE` (Y indefinida por contrato) | **excluida del universo auditado de E2** | compat proxy local 41/41, **no define el operador** | `PREREG_E2.md`; spec v2 filas 1-2 |
| WU / `P_WU_DailyObservations` / F | `NONE` | **0 casos** | 0 | spec v2 fila 6 |
| NOAA / `P_NOAA_HourlyData` / F | `PROXY_NOT_AUDITED` | E2 8/8 pero **subconjunto de observaciones UNKNOWN**; H_hourly vs H_series no separadas (N=4) | — | spec v2 fila 9, §4.3 |
| Estratos «con cláusula» de filas 5, 7, 8 | `PROXY_NOT_AUDITED` | **0 casos auditados con cláusula** | — | spec v2 §4.2 cond. 6 |

La cifra «54/57 compatibles» de D17 **no** se usa como justificación del universo: procede de una muestra que excluyó `P_WU_GENERIC` y `P_byForecast` y mezcla muestra preregistrada y no preregistrada. Se sustituye por la tabla anterior, estrato a estrato.

#### 1.1.4 Reglas de elegibilidad restantes (fail-closed) [DEC]

Un mercado `m` (par `market_id`, `token_id` YES) entra en U-SIGNAL **si y sólo si** cumple TODAS:

| # | Condición | Fuente / mecanismo |
|---|---|---|
| **U1** | Pertenece a un evento de temperatura máxima diaria sobre una de las **55 estaciones canónicas** (Anexo C), coordenadas del snapshot D1-COORD v1.3 (D1, D14, D15). Estación fuera del snapshot → exclusión `stage = station`. | `STATION_COORDS_SNAPSHOT_v1.3.json` sha `c1617939…` |
| **U2** | `build_label(prediction_time=T, resolution_timestamp, winning_outcome)` devuelve un dict no nulo (§2.4). `None` → exclusión `stage = label`, `reason ∈ {unresolved, no_resolution_timestamp, prediction_after_resolution}`. **Filtro ex post declarado** (R2.H7). | `labeling.py:31-63` |
| **U3** | El estrato `(v3.primary_source, v3.primary_rule, v3.unit, v3.rounding_rule)` está en la lista INCLUIDO de §1.1.1 y el mercado **no** lleva `clause_lowest_bracket` salvo HKO. Distinto → `stage = universe`, `reason ∈ {stratum_not_enabled, clause_stratum_not_audited}`. | §1.1.1 |
| **U4** | `markets.fee_regime` (por mercado, de Gamma) **JOIN** `market_fee_schedule` con `fee_status = 'KNOWN'` (§1.1.5). | `database.py:129-144, :172` |
| ~~U5~~ | **ELIMINADO** (R0.H0). `measurement_rule` es ahora sólo etiqueta de segmentación con valor declarado `NULL/GENERIC`. | — |
| **U6** | `umaResolutionStatus = 'resolved'` (**enumeración cerrada**, no «≠ proposed»). OBSERVADO: en el catálogo completo `resolved` 93.141, `proposed` 47, NULL 33; **en la ventana estricta 51.051/51.051 `resolved`** y `winning_outcome` no nulo, luego U6 no excluye nada en la capa que decide. **Filtro ex post declarado** (R2.H7). | `cls2.umaResolutionStatus` |
| **U7** | `endDate` presente y con hora **12:00:00Z** (cumplido en 8.557/8.557 eventos del catálogo; OBSERVADO). Distinto → `stage = anchor`. La igualdad `target_date = fecha(endDate)` es una **regla que este preregistro fija** (§1.5), no un hecho observado (corrección R0.H7). | `PREREG_LEAD_HOURS_RANGE.md` sha `1d4161e8…` |
| **U8** | El evento tiene **partición estructural válida de bandas**: `band_integrity(labels)['is_partition'] == True`, evaluado **sólo sobre las etiquetas de banda**, **sin** forecast ni precio (2D §F; `strategy_a.res.band_integrity`). Corrige la circularidad de v1.0, que citaba 2D §G y exigía `Σ p_weather ≈ 1` (R1.H4). Si no → evento entero excluido, `stage = feature`, `reason = not_partition`. | `PHASE_2D_STRATEGY_A_DESIGN.md` §F |
| **U9** | `price_semantics ∈ {MIDPOINT_ESTIMATED, INDICATIVE}` (§2.3). | `database.py:215, :225-226` |
| **U10** | `closedTime > T` para **todas** las bandas del evento (§2.1, `stage = closed_before_T`). | `cls2.closedTime` |

**U2 y U6 son filtros ex post sobre el estado de resolución** (usan información posterior a T para definir el universo). En la capa estricta **no excluyen ningún evento** (4.641/4.641 `resolved`); en cualquier otra capa el informe reporta su fracción como posible sesgo de supervivencia.

Toda exclusión se registra con `(market_id, event_id, lead_hours, stage, reason)` en `exclusions.csv` (§9). **Nunca se imputa ni se desplaza T para rescatar un mercado** (2E §5).

#### 1.1.5 U4: consulta exacta [DEC] (R0.H3, R1.H7)

`markets.fee_status` **no existe** (OBSERVADO: `markets` sólo tiene `fee_regime` y `tick_size`, `database.py:149-186`); `fee_status` vive en `market_fee_schedule` con PK `(fee_regime, dataset_version, record_version)`, es decir **por régimen, no por mercado**; `exponent` no es columna, sólo aparece dentro del JSON `raw_fee_fields` (`database.py:532`; `polymarket/fees.py:55-57, :68`). U4 se ejecuta así y no de otro modo:

```sql
SELECT m.market_id
FROM markets m
JOIN (
  SELECT fee_regime, dataset_version, fee_status, raw_fee_fields,
         row_number() OVER (PARTITION BY fee_regime, dataset_version
                            ORDER BY record_version DESC) AS rn
  FROM market_fee_schedule
) s
  ON s.fee_regime      = m.fee_regime
 AND s.dataset_version = m.dataset_version
 AND s.rn              = 1
WHERE s.fee_status = 'KNOWN'
  AND m.fee_regime IN ('fees_disabled','weather_fees')
  AND CAST(json_extract(s.raw_fee_fields, '$.feeSchedule.exponent') AS INTEGER) = 1;
```

`fee_status ≠ 'KNOWN'`, `exponent ≠ 1` o `raw_fee_fields` ausente → mercado excluido de métricas netas, contado en `exclusions.csv` con `stage = fees`. **Se declara que «lectura por mercado» significa en realidad `fee_regime` por mercado + estado por régimen dentro del `dataset_version`**, y que ese estado es el **actual de Gamma**, no el vigente en T (§0.2.3).

### 1.2 Unidad de análisis [DEC]

- **Unidad de predicción**: banda (fila de `features`/`predictions`).
- **Unidad de elegibilidad**: **evento** (2D §D LOCKED: exclusión entera, sin sumas parciales, W.6). Toda exclusión de banda por precio, forecast o frescura **propaga al evento completo**.
- **Unidad de señal/trade**: fila de `signals` con `signal ∈ {BUY, FADE}` (HOLD no genera trade).
- **Unidad de bootstrap**: bloque **estación-mes** (§6.4).
- **Unidad de conteo de cobertura**: evento (`event_id`) por lead.

### 1.3 Periodo: dos capas [DEC]

**Capa ESTRICTA (única que soporta el veredicto):** `target_date ∈ [2026-06-03, D_fin]`, con `D_fin` = último `target_date` con evento de U-SIGNAL y `resolution_timestamp` no nulo en el `dataset_version` fijado, y `≤ 2026-09-04`. **OBSERVADO 2026-09-07: el último `target_date` con evento en U-SIGNAL es 2026-09-02** (en U-LABEL, 2026-09-04 por el evento HKO con cláusula). Justificación del inicio: F-3 declara la disponibilidad de forecasts PARTIAL sólo desde 2026-06-03; el benchmark V2 fijó exactamente este rango; R15/D9-bis fijan el backfill a ≥ 2026-06-03.

**Capa EXTENDIDA (sólo sensibilidad, etiqueta obligatoria `NOT_ASOF`):** `target_date ∈ [2026-04-02, 2026-06-02]` (disponibilidad UNKNOWN). Se ejecuta con el mismo código, el **mismo `tau*` del run primario, sin reselección** (§4.6) y las mismas tolerancias, **únicamente si** `weather_forecasts` contiene filas M1 con `available_at` poblado para ese rango bajo la misma regla `issue_time + L_max`. Si no, el informe registra `EXTENDED = NOT_AVAILABLE`. Ningún criterio de §7 lee esta capa. `fees_disabled` (endDate ≤ 2026-03-30) y CLOB V1 (< 2026-04-28) quedan **NO EVALUABLES**.

### 1.4 Composición mensual del universo (OBSERVADO 2026-09-07) [DEC — cuantificación exigida antes de congelar]

**U-SIGNAL por mes** (mes = mes UTC de `target_date`):

| Mes | n_mercados | n_eventos | n_estaciones | Estaciones |
|---|---|---|---|---|
| 2026-06 | 924 | 84 | **3** | LTFM, LLBG, UUWW |
| 2026-07 | 1.023 | 93 | **3** | LTFM, LLBG, UUWW |
| 2026-08 | 10.912 | 992 | **50** | todas menos DNMM, RCTP, LFPG, WIHH, VHHH |
| 2026-09 (01–02) | 44 | 4 | **3** | RCSS, MPMG, ZSJN |
| **Total** | **12.903** | **1.173** | **50** | — |

**U-SIGNAL por estrato × mes:**

| Estrato | 2026-06 | 2026-07 | 2026-08 | 2026-09 |
|---|---|---|---|---|
| NOAA / `P_NOAA_TempColumn` / C | 924 mk / 84 ev | 1.023 / 93 | 3.883 / 353 | 11 / 1 |
| NOAA / `P_NOAA_TempColumn` / F | 0 | 0 | 121 / 11 (todos `target_date` 2026-08-23) | 0 |
| WU / `P_WU_DailyObservations` / C | 0 | 0 | 6.908 / 628 (primer `target_date` 2026-08-06) | 33 / 3 |

**U-LABEL por mes** (añade HKO): 1.232/112/4 · 1.364/124/4 · 11.253/1.023/51 · 77/7/4.

**Consecuencias que este preregistro declara ANTES de ejecutar (INFERIDO sobre las cifras OBSERVADAS):**

1. El universo es **fuertemente asimétrico en el tiempo**: 84,6 % de los mercados y 84,6 % de los eventos de U-SIGNAL caen en 2026-08, porque `P_WU_DailyObservations` sólo aparece desde 2026-08-06 y `P_NOAA_TempColumn` se multiplica por ~4 en agosto.
2. **Junio y julio tienen exactamente 3 estaciones (LTFM, LLBG, UUWW) y las tres tienen `in_modelsel = True`** (Anexo C). Es decir: el mes de calibración pura y el primer mes de test están compuestos **al 100 % por estaciones usadas para elegir M1**. Esto agrava §0.2.2 y es de reporte obligatorio (§7.4 C7).
3. **Septiembre aporta 4 eventos / 44 mercados en 3 estaciones**: su contribución al OOS es marginal por construcción y se declara ahora, no después.
4. **E6 (≥ 3 estaciones con trades) queda exactamente en el límite** en julio y septiembre: la pérdida de una sola estación por cobertura convierte el mes en no evaluable. Declarado a priori.

### 1.5 Estaciones, `target_date` y ventana de observación W(m) [DEC] (R0.H7, R1.H2)

**Regla congelada, sin depender de ningún helper futuro:**

```
target_date(m) := fecha UTC de endDate(evento)              # endDate = 12:00:00Z (U7)
W(m)           := día civil local completo de target_date(m)
                  en la zona STATION_TZ_v1.json[icao].tz
```

- `STATION_TZ_v1.json` (sha `35d68e65…`) resuelve la tz de **55/55** estaciones desde el `tzname` del registro ASOS de IEM, con `missing = []` y `conflicts = []` (OBSERVADO). tz ausente → fail-closed `stage = station`, `reason = station_tz_unknown`. Sustituye a `STATIONS_TZ.json` (28 estaciones) usado por los refutadores.
- **Tensión con 2D §C declarada como herencia** (R1.H2): 2D §C (DECIDED-V1) prohíbe que **Strategy A** derive `target_date` de `endDate`. Aquí la derivación ocurre en el **motor de backtest (caller)**, que pasa `target_date` ya resuelto a `build_feature`; `strategy_a` sigue sin derivarlo. No se modifica 2D.
- **Se retira la etiqueta [OBS] de v1.0** sobre `target_date = fecha(endDate)`: lo OBSERVADO es que la **hora** de `endDate` es 12:00:00Z en 8.557/8.557 eventos; la igualdad de fechas es la regla que aquí se fija (categoría: DEC, apoyada en `PREREG_E2.md`, que la dejaba como hipótesis a verificar).

**Desfase de W(m) respecto de `endDate` (OBSERVADO, calculado con `STATION_TZ_v1` para 2026-07-15; Anexo C columnas `inicio`/`fin`):** el inicio de W(m) va de **−24 h** (NZWN) a **−5 h** (KLAX/KSEA/KSFO) y el fin de **0 h** (NZWN) a **+19 h**. De ahí se deriva la **fracción de W(m) ya transcurrida en T**:

```
transcurrido(T) = max(0, −lead_hours − inicio_h)   horas de las 24 de W(m)
```

- **Lead 24 h (veredicto): `transcurrido = 0` en las 55 estaciones**, NZWN incluida, que queda exactamente en el borde (`inicio = −24 h`). En el lead que decide, ninguna parte de la ventana de observación había ocurrido en T.
- **Lead 9 h: `transcurrido > 0` en 34 estaciones**, con máximo **15 h de 24 (62,5 %) en NZWN**, 12 h en RJTT/RKPK/RKSI, 11 h en el bloque Asia/Shanghai-Taipei-Manila-KL-Singapur-HKO, 0 h en todas las estaciones americanas. Es un régimen de información distinto y se reporta como segmento (§6.3(j)).

**Tratamiento explícito de NZWN (Wellington) [DEC]:** NZWN **entra** en el universo con la regla anterior. OBSERVADO: NZWN aporta **275 mercados / 25 eventos** a U-SIGNAL, todos en agosto (`P_WU_DailyObservations` C 187/17, `target_date` 2026-08-07..23; `P_NOAA_TempColumn` C 88/8, 2026-08-24..31); en la ventana tiene además 715/65 en `P_WU_GENERIC`, ya excluidos por §1.1.1. Bajo esta regla el día civil local de Wellington **cierra exactamente en `endDate`** (`fin = 0 h`), de modo que a 24 h el evento es plenamente prospectivo y a 9 h el 62,5 % de la ventana ya ha ocurrido. La lectura alternativa (`target_date = fecha(endDate) + 1`, ventana que **empieza** en `endDate`) **no se adopta**: implicaría que el mercado cierra antes de que comience el día observado. Queda registrada como **cuestión abierta heredada** (2E §8 «cuestión adyacente abierta»; ROADMAP R8 PARCIAL) y como **variante de sensibilidad prohibida en V1** (sólo por enmienda §10.3). NZWN es **segmento obligatorio** del informe (§6.3(k)); si el signo del PnL depende de NZWN, se declara.

---

## 2. Datos y as-of

### 2.1 Instante de decisión T y leads [DEC, hereda 2E]

```
T = endDate − lead_hours · 3600            (PHASE_2E_LEAD_HOURS_ANCHOR.md sha 6e405d1a…, RATIFICADO 2026-09-04)
```

- Prohibido anclar en `target_start/midpoint/end`, `expected_max_time`, `daily_high_time`, `last_meaningful_market_time`, `closedTime`, o redefinir `lead_hours` como `issue_time − target_date`.
- **Leads primarios**: `{9 h, 24 h}`. **Lead de veredicto: 24 h** (la evidencia MODELSEL a favor de M1 es concluyente a 24 h y queda INCONCLUSA a 9 h con runs iguales, Δ = −0,060; `MODELSEL_V5_CORRECTION_01.md`). El lead 9 h recibe veredicto propio etiquetado `LEAD_9H`, que **no** entra en el veredicto de fase.
- **Leads secundarios**: `{36 h, 48 h}`, sólo sensibilidad, con exclusión fail-closed del evento inexistente en T (`createdAt > T`) y reporte obligatorio de la fracción excluida. **Se etiquetan además `NOT_ASOF_QUANTILES` salvo que la historia de M2 use el corte dependiente del lead de §3.2** (R2.H1). Leads > 48 h: no se ejecutan.
- **Existencia del evento en T**: `createdAt ≤ T` para todos los leads; si no, `stage = existence`.
- **Cierre anticipado — stage nuevo `closed_before_T`** (R2.H6) [DEC]: si **alguna** banda del evento tiene `closedTime ≤ T`, el **evento** se excluye para ese lead. OBSERVADO en U-SIGNAL (1.173 eventos, `closedTime` no nulo en todas las bandas): **1 evento a 9 h** (936283, Panamá, `target_date` 2026-09-01, `closedTime − endDate = −17,32 h`) y **0 eventos a 24 h**.
- **Cifras corregidas de `closedTime − endDate` (OBSERVADO 2026-09-07 sobre U-SIGNAL, máximo por evento; sustituyen a la cita heredada de 2E «+0,38 h a +15,33 h», medida sobre 9 ciudades un día):** mín **−14,75 h**, mediana **+9,82 h**, p95 **+19,26 h**, máx **+63,77 h**. `closedTime == umaEndDate` en todo el periodo.
- **Coincidencia de run** (regla V2 §4): si a 9 h y a 24 h se selecciona el mismo run de M1 para un evento, se reporta la fracción. **No se construye ningún agregado que mezcle leads.**
- **Guarda anti-fuga del instante de decisión** (2E §4.3): R19 debe incluir un test que verifique que `T` se deriva únicamente de `endDate` y que `prediction_time_for` no recibe ni lee `resolution_timestamp`, `closedTime`, `daily_high_time` ni `last_meaningful_market_time`. Sin ese test en verde, el motor no está TESTED (E5).

### 2.2 Forecast as-of [DEC, hereda V2/F-3]

- Modelo **M1 = `icon_seamless`** (D12). `available_at = issue_time + L_max(icon_seamless) = issue_time + 4,76 h`; **`L_max` es el máximo observado sobre 78 pasadas de `dwd_icon`** (no 307; las 307 son el total de 4 modelos — corrección de v1.0), **no** la mediana.
- **Clave de join estación [DEC]** (R0.H6): la partición y el filtro de `weather_forecasts` usan **`station_identifier` (ICAO, D1-COORD v1.3)**, no `markets.station` («discovered station name», `database.py:156`). OBSERVADO: `feat/ingest-2b` escribe `weather_forecasts.station = ICAO` (`weather.py:269,285`), mientras `features.py:97-105` filtra por el `station` que le pasa el caller; el motor debe pasar el ICAO. **Test obligatorio de R19 (E5): falla si el join devuelve 0 forecasts para cualquier estación del snapshot presente en el universo.** Sin ese test, el 100 % de los eventos caería en `stage = forecast` y la puerta de cobertura dispararía NOT_EVALUABLE sin diagnóstico.
- Selección: `latest_asof(weather_forecasts, time_col='available_at', asof=T, partition=(station, model, target_date))`, con los requisitos adicionales de §2.5 y §2.6 (filtro por `dataset_version`, desempate por `record_version DESC`, `quantiles_available_at ≤ T`). `issue_time ≤ T` **nunca** es criterio suficiente.
- Ausencia de forecast con `available_at ≤ T` → banda NONE y **evento** excluido para ese lead, `stage = forecast`. No se imputa.
- **Sensibilidad `L_max + 1 h`** (R2.H4) [DEC]: variante única, sin reselección de `tau*`, que recalcula `available_at = issue_time + 5,76 h` y por tanto puede cambiar el run seleccionado. Se reporta `n_eventos` con run distinto y el PnL resultante; no entra en el veredicto.
- **Limitación declarada (obligatoria en cada tabla del informe):** `L_max` es empírica, no garantizada; la cola no está caracterizada; `created_at ≠ fin de escrituras` (hasta 93,7 min); la API sólo expone la última pasada; y `L_max` se estimó **dentro del periodo evaluado** (§0.2.2).

### 2.3 Precio as-of [DEC, hereda 2C/2D]

- `p_market = latest_asof(price_history, time_col='observation_time', asof=T, partition=token_id YES, where market_id)` (`features.py:74-82`), con filtro por `dataset_version` (§2.6).
- **Semánticas admisibles (enumeración cerrada, decidida ahora)** [DEC] (R0.H4): `price_semantics ∈ {MIDPOINT_ESTIMATED, INDICATIVE}` (U9). `LAST_TRADE_INDICATIVE` y `NEAREST_TRADE_INDICATIVE` se ejecutan **sólo** como variante de sensibilidad declarada, con el mismo `tau*`, sin reselección; `UNKNOWN` → exclusión fail-closed. Motivo: el CHECK del schema (`database.py:225-226`) admite cinco valores y **no incluye `EXECUTABLE`**, de modo que la guarda de `features.py:90-91` es vacua sobre este schema (OBSERVADO); sin enumeración cerrada, la elección de semánticas quedaría abierta a posteriori. `fidelity` y `source_window` **no** son filtros (para no repetir el defecto de U5) sino **segmentos descriptivos obligatorios** del informe. `price_layer` registrado en `paper_trades` = `'INDICATIVE'` en el sentido de «no ejecutable», con la semántica exacta anotada por fila.
- **Frescura mínima de la cotización — `stale_quote` POR EVENTO** [DEC] (R0.H4): se exige `observation_time ∈ (T − 6 h, T]` para **todas** las bandas del evento; si **alguna** banda incumple, **el evento entero se excluye** para ese lead, `stage = pricing`, `reason = stale_quote`. Se implementa como **prefiltro anterior a `generate_event_signals`**, no como un filtro posterior a la emisión de señales. Motivo: 2D §D/§E son LOCKED y fijan la elegibilidad **por evento** (exclusión entera, sin sumas parciales, W.6); la formulación por mercado de v1.0 contradecía esa unidad y permitía que `strategy_a` calculara `Σ p_market` y emitiera señal con una cotización vieja antes de la exclusión. Justificación del valor 6 h: ninguna sonda P3 de 2E ha verificado la disponibilidad real de cotización en T; 6 h < 9 h (lead primario más corto), de modo que el precio pertenece al mismo estado de información que el forecast. Es un parámetro de cobertura, no de estrategia; se reporta la fracción excluida.
- Sin cotización → `stage = pricing`, `reason = no_quote`, evento excluido. **Nunca se desplaza T.**
- **Puerta de cobertura, con denominador y numerador definidos** [DEC] (R1.H4):
  - **Denominador** = eventos que pasan U1, U3, U6, U7, U8, U9, U10 (condiciones **estructurales**, evaluables sin forecast ni precio) en el lead de veredicto.
  - **Numerador** = eventos excluidos por `existence` + `forecast` + `pricing` (`no_quote` ∪ `stale_quote`).
  - Si numerador/denominador > **30 %**, el lead se etiqueta `COVERAGE_INSUFFICIENT` y el veredicto de fase es NOT_EVALUABLE (E2).
  - **`sum_pweather_out_of_tolerance` y `sum_pmarket_out_of_tolerance` (§4.4) se reportan aparte y NO entran en la puerta** (decisión tomada ahora, no a conveniencia).
  - Justificación del 30 %: la exclusión estructural conocida a 24 h es 1,8 % por existencia; 30 % deja margen para la incógnita P3 sin aceptar un universo que ya no representa el catálogo. Es una puerta a priori, no un criterio de éxito.

### 2.4 Label [DEC, hereda D17] (R0.H2)

**Definición ejecutable, sin juicio del implementador:**

```
lab = labeling.build_label(prediction_time=T,
                           resolution_timestamp=markets.resolution_timestamp,
                           winning_outcome=markets.winning_outcome)

lab is None              -> mercado excluido, stage='label'
lab['label'] == 'Yes'    -> label = 1
lab['label'] == 'No'     -> label = 0
cualquier otro valor     -> fail-closed, reason='winning_outcome_unexpected_value'
```

Motivo: OBSERVADO, `markets.winning_outcome` es `'Yes' | 'No'` (`polymarket/resolution.py:72`, `discovery.py:188`) y `build_label` devuelve `{'label': str(winning_outcome), …}` (`labeling.py:59`); en el catálogo hay 8.553 `'Yes'`, 84.629 `'No'` y 39 NULL. La redacción de v1.0 («label = 1 si `winning_outcome` es el `token_id` YES») **nunca sería verdadera** en una implementación literal: daría label = 0 siempre. **Test obligatorio en R19 (E5)** con fixture `'Yes'`/`'No'`/NULL/valor inesperado.

- El gate temporal `prediction_time < resolution_timestamp` es **estricto** y es la única vía (2D §N LOCKED).
- Es **Y_final retrospectivo** (D17 = A + C).
- **Limitación D17 obligatoria en cada tabla del informe:** «label de evaluación disponible retrospectivamente tras el settlement; revisiones NEGLIGIBLE demostrado sólo para IEM/METAR en 578 station-days (23/53 estaciones, 20 días; 0/578 cambian bracket; cota superior 95 % = 0,519 %); UNKNOWN para Wunderground, HKO y CWA» (`REVISION_IMPACT_AUDIT.md`).
- **Reformulación de la frase contradictoria de v1.0** (R1.H9): «**Y_final no se usa como feature de la fila ni se presenta jamás como Y_asof; sí alimenta M2 como observación de entrenamiento, y únicamente por la vía walk-forward con el corte dependiente del lead de §3.2**». La redacción anterior («Y_final no se usa como observación de entrenamiento as-of») contradecía §3.1.
- Ningún campo de `FORBIDDEN_FEATURE_FIELDS = {winning_outcome, resolution_timestamp, settlement_timestamp, is_winner}` puede aparecer en `features`, `predictions` o `signals` (`features.py:20-27, 199-213`). El JOIN con labels ocurre **sólo** en el motor de backtest, después de generar señales, por `(market_id, token_id, dataset_version)`.

### 2.5 Features persistidas y **disponibilidad de los cuantiles** [DEC, depende de R17/R16] (R2.H0, BLOQUEANTE)

**Problema OBSERVADO.** `features.py:97-105` selecciona la fila de `weather_forecasts` con `available_at ≤ T` y lee `forecast_p10..p90` de **esa misma fila** (`features.py:144-150`); la guarda final (`features.py:199-215`) sólo comprueba `forecast.available_at ≤ T` y `price.observation_time ≤ T`. El schema (`database.py:289-311`) **no tiene ninguna columna que registre cuándo fueron calculables los cuantiles**, y R16 prevé escribirlos como filas derivadas con `record_version` nuevo heredando el `available_at` de la pasada. Si M2 calcula los cuantiles con errores posteriores a T (p. ej. agregados de `weather_errors`, cuyo esquema es `(station, model, lead_hours, month)` y **no admite historia por evento**), `no_lookahead_verified` seguirá siendo `TRUE` y el motor **no puede detectarlo**. Es el único canal por el que Y_final puede entrar en `p_weather`, y v1.0 sólo tenía una defensa documental.

**Requisitos congelados:**

1. **`quantiles_available_at` es obligatorio** [DEC]: toda fila de `weather_forecasts` con cuantiles no nulos debe llevar su propio instante de disponibilidad, definido como `max(available_at)` de las observaciones de la historia usada para estimarlos (equivalentemente, `computed_at` de la ejecución de M2 junto con `derived_from_dataset_version`, siendo el criterio operativo el **máximo** de ambos). El motor y `build_feature` exigen **`quantiles_available_at ≤ T` además de `forecast.available_at ≤ T`**. Fila sin ese campo → exclusión fail-closed `stage = quantiles`, `reason = quantiles_available_at_missing`.
2. **Test adversarial obligatorio en E5**: construir una fila con cuantiles calculados sobre la muestra completa (`quantiles_available_at > T`) y verificar que la fila **queda excluida** y no produce feature.
3. **Declaración explícita**: `no_lookahead_verified` (`features.py:215`) **NO certifica los cuantiles**; certifica únicamente `available_at` del forecast y `observation_time` del precio.
4. **Hasta que (1) y (2) estén implementados y verdes, cualquier run es como máximo `EXPLORATORY`** (§7.3). El chequeo documental de PREREG_M2 **no basta**.
5. Añadir `quantiles_available_at` es un **campo de datos nuevo en `weather_forecasts`**; si su introducción exige tocar `features.py` (2D §F LOCKED), se tramita como **enmienda del diseño 2D** antes del congelado, con el diff citado. Este preregistro no autoriza tocar `labeling.py` ni el schema de `features`.
6. El motor lee `features` persistidas con `no_lookahead_verified = TRUE`; `FALSE` o NULL → exclusión `stage = features`. `feature_json` no puede contener claves prohibidas.

### 2.6 `dataset_version`, `model_version`, `code_version` [DEC] (R0.H8, R2.H3)

- **Exactamente un `dataset_version` para todo el run**, escrito en el manifiesto antes de calcular métrica alguna. **El nombre concreto NO se deja a «la última versión registrada al arrancar R21»** (regla que no es un valor a priori y que, OBSERVADO, podría seleccionar una versión sin precios: `dataset_versions` está vacía mientras `price_history` contiene 1.152.000 filas con `dataset_version = 'backfill_2b_v1'` no registrada). **Regla congelada:** el `dataset_version` del run se **nombra explícitamente en la enmienda que cierre R15/R17** (§10.3, punto 7) y debe satisfacer, verificado y reportado antes de la primera métrica: (a) estar registrado en `dataset_versions`; (b) tener ≥ 1 fila en `price_history` y ≥ 1 en `weather_forecasts` para **cada** mes de la capa estricta; (c) tener filas de `features` con `no_lookahead_verified = TRUE`. Si no lo satisface → NOT_EVALUABLE (E4).
- **Condición de evaluabilidad nueva E7** [DEC]: el motor y `build_feature` **filtran por `dataset_version = <el del run>`** en `price_history` y `weather_forecasts`, y `latest_asof` **desempata explícitamente por `record_version DESC`**. Motivo OBSERVADO: `features.py:74-82` y `:97-105` **no** filtran por `dataset_version` ni `record_version`; `strategy_a.py:204-213` repite la consulta («NO dataset_version filter — matching features.py»); `db.latest_asof` (`database.py:851-859`) usa `row_number() OVER (PARTITION … ORDER BY available_at DESC)` **sin criterio secundario**, luego dos filas con el mismo `available_at` (la cruda sin cuantiles y la derivada por R16, o dos backfills distintos) se eligen de forma **no determinista**. Es un canal por el que una fila escrita después puede entrar en T con el `available_at` original. **Test obligatorio en E5**: dos `dataset_version` en la misma DB, verificar que sólo se lee el fijado; y dos `record_version` con idéntico `available_at`, verificar que gana el mayor con cuantiles no nulos. **Este es un cambio de código en 2C/2D LOCKED (no de esquema) y se tramita como enmienda antes del hash** (§10.3, punto 7); sin él, la promesa de «un único `dataset_version`» es inejecutable.
- **`model_version` del motor = `'backtestA_v1|<M2_run_id>'`**, distinto de `MODEL_VERSION = 'stratA_pmodel_v1'` (`strategy_a.py:48`, 2D W.10) y con `record_version` propio, para no colisionar con la PK de `predictions` (`database.py:406`). Las filas producidas por Strategy A V1 fuera del motor conservan `edge_net`/`net_edge` **NULL** (`test_strategy_a.py:272`); **sólo las filas escritas por el motor de backtest bajo `model_version = 'backtestA_v1|…'` llevan `edge_net` relleno con H1**, según autoriza D19.
- `code_version` = commit SHA del motor (R19), que debe ser un commit de una rama fusionada por PR (D16).
- `backtest_results.parameters` incluye obligatoriamente `prereg_sha256` (el schema no tiene columna dedicada, `database.py:465-482`).

---

## 3. Modelo de probabilidad

### 3.1 `p_weather` (2D LOCKED) y alineación con `SETTLEMENT_OPERATORS_SPEC` v2 — **DV-1** [DEC]

```
p_weather(banda) = band_probability(quantiles_to_distribution(p10..p90), lo, hi)   (2D §F/§G LOCKED)
Σ_bandas p_weather = 1 sobre partición válida
```

**Se usa `p_weather` sin `SettlementOperator` (R12)**, con el forecast as-of de §2.2. Justificación: (a) `p_weather` es LOCKED en 2D y sus tests validan esa definición; (b) adoptar R12 invalidaría el LOCKED y exigiría re-testar 2D; (c) la spec v2 de R12 es un **borrador pendiente de congelar**. Si R12 se fusiona antes de R21, su incorporación es la **enmienda V-1.1**, nunca un cambio silencioso.

**Consecuencia que este preregistro decide ahora, en vez de dejarla implícita (DV-1):** `quantiles_to_distribution` (`probability.py:89-98`) es un operador **nearest-integer implícito**; su mapeo CDF→banda equivale a `P([lo,hi]) = F(hi+0,5) − F(lo−0,5)` (`NEAREST` en el vocabulario de la spec v2 §1.4). Confrontado con la evidencia de la spec v2 estrato a estrato:

| Estrato del universo | Semántica de banda | Mapeo correcto según spec v2 | El mapeo legado es… | Decisión V1 |
|---|---|---|---|---|
| HKO / `P_HKO_AbsDailyMax` / C / **tenths** | `N ≡ [N, N+1)` | `INTERVAL_FLOOR`: `F(hi+1) − F(lo)` | **REFUTADO**: half-up 87/166 frente a floor 164/166; en los `n_disc = 81` discriminantes, 4/81 frente a 81/81. El legado desplaza la banda 0,5 °C | **HKO excluido del universo de señales V1** (`stage = pweather_mapping`, `reason = pweather_mapping_refuted`): **1.023 mercados / 93 eventos / 1 estación**. Conserva label y `settle` (§1.1.1) y se reporta en Brier/log-loss como descriptivo etiquetado `REFUTED_MAPPING` |
| WU `P_WU_DailyObservations` C y NOAA `P_NOAA_TempColumn` C / **whole degree** | `N ≡ Y entero` | `NEAREST` sólo donde la cuantización esté observada; la spec la declara **UNKNOWN y NOT_TESTABLE con IEM** (`H_LOCAL_tg = None` en 24/24 filas °C) | **UNKNOWN, no refutado**: coincide con `NEAREST`, que es la lectura natural de la banda entera, pero cómo el observador produce el entero desde el valor continuo no está establecido | **INCLUIDOS**, con la limitación `quantization_unknown_C` declarada en cada tabla y como categoría interpretativa C8 |
| NOAA `P_NOAA_TempColumn` F / **whole degree** | `N ≡ Y entero` | `NEAREST` (serie `metar_tgroup_tmpf`, `tmpf == round(F(tg))` 14/14) | **alineado** con la evidencia de cuantización | **INCLUIDO**, con la limitación de **ventana no discriminada en EE. UU./°F** (spec v2 `NO_SEPARABLE_EN_MUESTRA`, DP-W1) declarada. Son 121 mercados / 11 eventos de un solo `target_date` (2026-08-23) |

**Inversión post-R12 declarada ahora:** bajo la spec v2 §3.1, el universo con `band_probability` habilitado es **exactamente el contrario**: sólo HKO (fila 10). Es decir, cuando R12 se incorpore por enmienda V-1.1, HKO pasará a ser el único estrato con mapeo evidenciado y los estratos °C quedarán FAIL_CLOSED para `p_weather`. Esta inversión no puede usarse a posteriori para elegir la versión que dé mejor resultado: **los resultados de V1 y de V1.1 se publican ambos, con sus veredictos separados y sin editar el anterior** (§10.3).

**Segmentación obligatoria derivada** (§6.3(c)): todas las métricas se reportan además por `pweather_mapping ∈ {NEAREST_ALIGNED (fila 8), NEAREST_UNKNOWN_C (filas 5 y 7)}`, y HKO aparte como `REFUTED_MAPPING` (sin trades).

### 3.2 Requisitos mínimos que este preregistro impone a M2 [DEC] (R1.H1, R2.H1)

`p_weather` —y con él todo el edge— depende de los cuantiles p10..p90 de M2, que **no tiene preregistro ni escritor** (`features.py:40-45` lee `forecast_p10..p90` de `weather_forecasts`). v1.0 dejaba libres método, estratificación, mínimos de muestra y jerarquía de fallback: exactamente los grados de libertad que determinan el signo del edge. Se congela el **mínimo** que el backtest exige:

1. **Definición del error**: `error = Y_final − forecast_M1` para el par (estación, `target_date`), con `Y_final` construido por `build_label`/settlement retrospectivo (D17), nunca por una observación as-of inexistente.
2. **Estratificación**: cuantiles por `(station, model, lead_hours)`. Sin fallback silencioso: si un estrato no alcanza el mínimo, la banda es **NONE** y el evento se excluye (`stage = quantiles`, `reason = insufficient_history`), no se sustituye por un estrato agregado.
3. **Mínimo de historia declarado**: `n ≥ 10` errores en el estrato, heredado de la regla V2 de desbiasing (`PREREG_MODELSEL_V5.md`); `n < 10` → NONE.
4. **Corte de historia dependiente del lead** [DEC] (R2.H1):

```
historia(e | lead ℓ) = eventos de la misma (estación, modelo) con
                       target_date ≤ D − 2 − ceil(ℓ / 24)
```
   ⇒ **D−3 a 9 h y a 24 h; D−4 a 36 h y a 48 h**.

   Motivo OBSERVADO por el refutador: la afirmación de v1.0 de que `D−2` «garantiza que Y_final histórico ya estaba disponible en T» **es falsa fuera del lead ≤ 24 h**: a 36 h (T = D−1 00:00Z) la observación de D−2 no estaba disponible en 15/28 estaciones con tz conocida, y a 48 h falla en 28/28. La frase «garantiza» se reescribe como **afirmación condicionada al lead**, y la latencia citada pasa a ser la de **observación** (fin del día civil local + ~1,3 h), **no** la de resolución del mercado — cuya distribución real en el periodo estricto es mediana +9,82 h, p95 +19,26 h, máx +63,77 h (§2.1). **Nota sobre la corrección recibida (ajuste declarado):** el hallazgo R2.H1 propone la fórmula `D − 2 − ceil(lead/24)` y, en su ejemplo, «D−3 a 36 h»; la fórmula da **D−4** a 36 h. Se aplica **la fórmula**, que es la más conservadora, y se declara la discrepancia con su ejemplo.
   Si las figuras de 36/48 h se reportaran con el corte D−2, se etiquetan `NOT_ASOF_QUANTILES` igual que la capa extendida.
5. **Regla de selección de fila en `weather_forecasts`** [DEC]: la fila elegida es la de mayor `record_version` con `forecast_p10..p90` **no nulos**, `available_at ≤ T` y `quantiles_available_at ≤ T`, dentro del `dataset_version` del run (§2.6, E7). Test obligatorio.
6. **`prereg_m2_sha256` registrado en el manifiesto ANTES de la primera métrica**, y **una sola versión de M2 por versión de este preregistro**: cualquier segunda variante de M2 es enmienda con re-run etiquetado (§10.3, punto 3). Condición de evaluabilidad E3.

### 3.3 Desbiasing: V2, no en este run [DEC]

- V1 (este preregistro): sin desbiasing adicional al que M2 incorpore.
- V2 (preregistrada aquí para no reinventarla): `historia(e)` con el **mismo corte dependiente del lead de §3.2**; `|historia| < 10` → banda NO EVALUABLE sin imputación; `bias_hat = media(f − Y_final)`; forecast corregido `f − bias_hat`. Prohibido estimar el sesgo con toda la muestra y evaluar sobre ella. V2 se ejecuta sólo tras una enmienda con su propio criterio; sus resultados no alteran el veredicto V1.

### 3.4 Referencia de mercado [DEC]

Brier y log-loss de `p_market` frente al label sobre la misma muestra que `p_weather`, como línea base descriptiva. No es criterio de veredicto.

---

## 4. Strategy A: edge, umbral y tolerancias

### 4.1 Definiciones (DECIDED-V1 de 2D, sin cambios; OBSERVADO)

```
p_model    = p_weather                       (W.1; strategy_a.py:243)
fair_value = p_model                         (W.2; strategy_a.py:244)
edge_gross = fair_value − p_market           (W.3; strategy_a.py:245)
signal     = BUY  si edge_gross ≥ +tau
           = FADE si edge_gross ≤ −tau
           = HOLD si |edge_gross| < tau      (signal_for, strategy_a.py:78-84)
```
`SELL` nunca se emite; `NONE` no se emite en V1 (W.11, opción A).

**Interpretación de trade [DEC]:** BUY = compra de 1 share YES a `p_market`; FADE = compra de 1 share NO a `1 − p_market` (equivalente a short YES). Se asume complementariedad `p_NO = 1 − p_YES` (supuesto declarado; `price_history` se lee sólo para el token YES, `strategy_a.py:204-218`).

### 4.2 Rejilla preregistrada de `tau` [DEC]

```
TAU_GRID = {0.01, 0.02, 0.03, 0.05, 0.08}     (puntos de probabilidad)
```
Cubre desde el orden del coste máximo H1 en p = 0,5 (0,0125) hasta 8 pt; el 0,05 del fixture de tests es sólo un punto de la rejilla. `min_edge_grid` de `config.py:207` **no** es autoritativo ni se lee (vestigio sin consumidor).

### 4.3 Selección de `tau` OUT-OF-SAMPLE **y as-of** (walk-forward mensual, expanding) [DEC] (R2.H2)

**Corrección respecto de v1.0:** la ventana de calibración era «todo el mes M−1» de calendario, pero los últimos eventos de M−1 **no estaban resueltos en los primeros T del mes M** (OBSERVADO por el refutador: ≈3,5 % de cada ventana; a 24 h el evento D−1 no está resuelto en T en 4.569/4.570 casos). Aunque la selección era OOS respecto de los labels de test, `tau*(ℓ, M)` **no era conocible** en los primeros ~2 días de M, contradiciendo la disciplina as-of que el propio documento impone a los cuantiles. **Regla congelada:**

```
calibración(ℓ, M) = eventos de U-SIGNAL con target_date < primer target_date de M
                    Y resolution_timestamp ≤ T_primero(ℓ, M),
                    donde T_primero(ℓ, M) = min(endDate de M) − ℓ·3600
```

**Tabla walk-forward con cifras OBSERVADAS (2026-09-07, U-SIGNAL, lead 24 h):**

| Mes de test | `T_primero(24 h)` | Eventos de calibración (expanding) | Excluidos por el corte as-of | Eventos de test | Mercados de test |
|---|---|---|---|---|---|
| **2026-07** | 2026-06-30 12:00Z | **81 / 84** (mercados 891/924) | 3 eventos (33 mk) | 93 | 1.023 |
| **2026-08** | 2026-07-31 12:00Z | **174 / 177** (mercados 1.914/1.947) | 3 eventos (33 mk) | 992 | 10.912 |
| **2026-09** | 2026-08-31 12:00Z | **1.147 / 1.169** (mercados 12.617/12.859) | 22 eventos (242 mk) | 4 | 44 |

(A lead 9 h el corte es más laxo — `T_primero(9 h)` cae ya en el mes de test — y quedan 84/84, 177/177 y 1.168/1.169 eventos de calibración; se reporta igualmente.)

- **2026-06 nunca es mes de test** (calibración pura).
- `tau*(ℓ, M)` = el `tau ∈ TAU_GRID` que **maximiza `pnl_net_H1` acumulado** en la ventana de calibración, sujeto a `n_trades_calibración(tau) ≥ 30`. Empate → el `tau` mayor (más conservador). Si ningún `tau` alcanza 30 trades → el mes se etiqueta `NO_CALIBRATION` y no aporta trades OOS.
- La selección es **pooled** sobre estratos y estaciones dentro del lead («pooled para seleccionar, segmentado para reportar»). Motivo: con 3 estaciones en junio y julio, una selección por estrato quedaría bajo `n ≥ 30` en la mayoría de meses. La selección por estrato es variante V2 (enmienda).
- El conjunto OOS = unión de los trades de todos los meses de test con su `tau*` respectivo. **Ninguna métrica del veredicto se calcula in-sample.** La tabla completa `pnl_net_H1(tau, mes)` se publica etiquetada IN-SAMPLE, sin entrar en el veredicto.
- El `tau` adoptado para operación futura será `tau*(24 h, último mes con calibración válida)`; su adopción es un acto separado del veredicto.
- **Declaración a priori (INFERIDO sobre §1.4):** dada la asimetría del universo, es esperable que el PnL OOS esté dominado por 2026-08 (84,6 % de los mercados) y que 2026-09 aporte ≤ 4 eventos. Si el mes de julio resulta `NO_CALIBRATION`, sólo quedarían 2 meses de test y E1 se cumpliría al límite.

### 4.4 Tolerancias (obligatorias, sin default, fail-closed; `strategy_a.py:109-123`) [DEC]

| Parámetro | Valor primario | Sensibilidad (una sola variante, sin reselección) |
|---|---|---|
| `weather_sum_tolerance` | `1e-6` | — (Σ p_weather es aritmética sobre una partición; sólo absorbe error de coma flotante) |
| `market_sum_min` | `0.80` | `0.90` |
| `market_sum_max` | `1.30` | `1.15` |

Justificación (INFERIDO): Σ p_market YES sobre las bandas de un evento refleja overround; < 0,80 o > 1,30 indica al menos una banda sin cotización fresca o con precio degenerado. Los valores de tests (`0.0 / 5.0`) son fixtures permisivos y no se usan. La variante se ejecuta con el mismo `tau*` y reporta el cambio en `n_trades` y `pnl_net_H1`; no entra en el veredicto. **Las exclusiones por tolerancia se reportan aparte y no cuentan en la puerta de cobertura** (§2.3).

### 4.5 Segmentación epoch/estrato en señales [DEC]

`predictions`/`signals` no tienen columnas de epoch ni de estrato y `strategy_a.py` no las escribe (discrepancia doc-código respecto de 2D §M). Resolución: el motor reconstruye `fee_regime`, `primary_source`, `primary_rule`, `unit`, `rounding_rule`, `clause_lowest_bracket`, `measurement_rule` (etiqueta `NULL/GENERIC`), `region`, `component`, `in_modelsel` por JOIN con `markets` × `v3` × Anexo C sobre `(market_id, dataset_version)`; **no se modifica el schema**. El informe declara la discrepancia.

### 4.6 Congelación del run primario y qué recalcula cada variante [DEC] (R1.H5)

**Regla única, sin ambigüedad:**

> **Las señales, los trades y `tau*` se fijan en el run primario** (lead 24 h, capa estricta, `x_exec = 0`, tolerancias primarias, semánticas primarias, H1). **Toda variante recalcula ÚNICAMENTE el PnL sobre ese mismo conjunto de trades**, sin regenerar señales y sin reseleccionar `tau*`.

Alcance de la regla: H2/H3, estrés `x_exec`, `market_sum` de sensibilidad, semánticas `LAST_TRADE_INDICATIVE`/`NEAREST_TRADE_INDICATIVE`, **LOSO**, capa extendida y sensibilidad `L_max + 1 h` (esta última es la **única excepción parcial**: al cambiar `available_at` puede cambiar el run de forecast seleccionado y por tanto el `p_weather`; se ejecuta como run separado etiquetado `LMAX_PLUS_1H`, con el `tau*` del run primario, y se reporta el número de eventos con run distinto). **LOSO no resel8ecciona `tau*`.**

---

## 5. Coste, ejecución y sizing

### 5.1 Modelo de coste (D19, `FEES_SEMANTICS` §2) [adoptado]

```
H1 (primaria):      c_taker(p) = 0.05 · p · (1 − p)      USDC/share
H2 (sensibilidad):  c(p)       = 0.10 · min(p, 1 − p)
H3 (sensibilidad):  c(p)       = 0.10 · p · (1 − p)      (= 2·H1)
fees_disabled → c = 0 (no aplica en capa estricta)
fee_status ≠ KNOWN o exponent ≠ 1 → edge_net = None (fail-closed; trade contado, excluido de métricas netas)
fee = round5(1 · c(p)); fees < 0.000005 redondean a 0
```
`p` = precio del share comprado (`p_market` para BUY, `1 − p_market` para FADE); H1/H2/H3 son simétricas en `p ↔ 1−p`. **`fee_regime`, `feeSchedule` y `tick` son el estado actual de Gamma, no una lectura as-of** (§0.2.3): limitación obligatoria del informe.

### 5.2 Ejecución [DEC, alineado con `FEES_SEMANTICS` §6]

- `exit_mode = hold_to_resolution`: salida a 0/1 por redención; `exit_cost = 0` (supuesto declarado, no verificado).
- `x_exec = 0` primario. Estrés: `x_exec = 0,5·tick` y `x_exec = 0,01` (1 pt). **`tick` se lee por mercado** (`orderPriceMinTickSize`: 0,001 mayoritario, 0,01 en 411 mercados); nunca default; es estado actual de Gamma.
- Rebate maker = 0; taker rebate = 0; builder fee = 0.
- No hay modelo de spread/slippage (R22 pendiente); el fill es hipotético a precio no ejecutable.

### 5.3 PnL por trade (size = 1 share) [DEC] — fórmula única bajo estrés (R1.H5)

**Se adopta la fórmula de `FEES_SEMANTICS` §2 (5): el fee se evalúa en `p`, y `x_exec` se resta aparte.** v1.0 evaluaba el fee en `p_entrada = p + x_exec`, lo que producía dos PnL distintos bajo estrés y dos lecturas de SUCCESS_ROBUST.

```
BUY :  pnl_gross   = label − p                       ,  p = p_market
       pnl_net_Hk  = (label − p) − c_k(p) − x_exec

FADE:  pnl_gross   = (1 − label) − (1 − p)
       pnl_net_Hk  = ((1 − label) − (1 − p)) − c_k(1 − p) − x_exec

edge_net_H1 = edge_gross − sign(signal) · c_1(p_share)
```
`predictions.edge_net` y `signals.net_edge` se rellenan con H1 **sólo** en las filas producidas por el motor de backtest bajo `model_version = 'backtestA_v1|…'` (§2.6); las filas de Strategy A V1 siguen NULL.

### 5.4 Sizing [DEC]

**1 share por señal**, sin Kelly, sin fixed_fraction, sin bankroll. `paper_trades.size = 1`, `bankroll_after = NULL`. Sizing fraccional es R20 con preregistro propio.

---

## 6. Métricas

### 6.1 Primarias (entran en el veredicto)

| Métrica | Definición | Muestra |
|---|---|---|
| `pnl_net_H1_total` | Σ `pnl_net_H1` sobre trades OOS | Lead 24 h, capa estricta, meses de test con calibración válida |
| `IC95(pnl_net_H1_total)` | bootstrap por bloques (§6.4), percentiles 2,5/97,5 | ídem |
| `LOSO_sign_stability` | fracción de réplicas leave-one-station-out **con ≥ 1 trade restante** con `pnl_net_H1_total > 0` | ídem |

### 6.2 Secundarias (reportadas, no deciden)

- `pnl_net_H1_per_trade`, `pnl_gross_total`, `pnl_net_H2_total`, `pnl_net_H3_total`, `pnl_net_H1` bajo estrés `x_exec ∈ {0,5·tick, 1 pt}`, bajo `L_max + 1 h` y bajo semánticas de precio de sensibilidad.
- `hit_rate` = fracción de trades con `pnl_gross > 0`.
- `n_signals` (BUY, FADE, HOLD), `n_trades`, `n_events`, `n_markets`, `n_estaciones`, `n_días efectivos`.
- `brier(p_weather)`, `logloss(p_weather)` (clip `p ∈ [1e-6, 1−1e-6]`) y los mismos para `p_market`, sobre **todas** las bandas con feature válida (no sólo señales). Para HKO se calculan y publican etiquetados `REFUTED_MAPPING`, sin trades.
- Curva de PnL acumulado por fecha de resolución.
- Fracciones de exclusión por `stage` y por `reason`, y fracción de coincidencia de run entre leads.
- Misma batería para lead 9 h (`LEAD_9H`), leads 36/48 h (sensibilidad, etiquetados según §3.2) y capa extendida (`NOT_ASOF`).

### 6.3 Segmentación obligatoria de toda métrica secundaria [DEC, hereda 2D §M LOCKED]

Pooled y por cada uno de:
(a) epoch de fees (`fee_regime`; en capa estricta sólo `weather_fees`, fila `fees_disabled` con `n = 0` declarada);
(b) sub-época CLOB (V2 únicamente en capa estricta; declarado);
(c) **estrato de settlement** `(primary_source, primary_rule, unit)` **y** `pweather_mapping ∈ {NEAREST_ALIGNED, NEAREST_UNKNOWN_C, REFUTED_MAPPING}` **y** `measurement_rule` como etiqueta con valor declarado `NULL/GENERIC`;
(d) lead;
(e) componente ICON (`icon_d2` / `icon_eu` / `icon_global`, Anexo C);
(f) **región** (Anexo C, partición cerrada por país; ASIA_SUR y HEM_SUR destacadas como vigilancia);
(g) mes de test;
(h) tipo de señal (BUY/FADE);
(i) **`in_modelsel` sí/no** (24 estaciones vs 31; en U-SIGNAL: 24 estaciones / 6.842 mk / 622 ev frente a 26 estaciones / 6.061 mk / 551 ev; OBSERVADO) — **obligatorio por §0.2.2**;
(j) **régimen de información**: `transcurrido(T)` de W(m) en cuartiles {0 h; (0, 6] h; (6, 12] h; > 12 h} (§1.5);
(k) **NZWN aparte** (275 mk / 25 ev; §1.5);
(l) `clause_lowest_bracket` (sólo HKO en U-LABEL: 11 mk / 1 ev).

Cada celda reporta `n_trades`, `n_estaciones` y `n_días efectivos`; celdas con `n_trades < 10` se muestran marcadas `LOW_N` y **sin IC**.

### 6.4 Bootstrap [DEC] — estadístico definido (R0.H9, R1.H6)

- **Bloques** = `(station_id, mes del target_date)`. Sea `B` el número de bloques **observados** en el OOS del lead de veredicto.
- **Estadístico remuestreado (fórmula explícita):** en cada réplica se extraen **`B` bloques con reemplazo** del conjunto de los `B` bloques observados (**muestreo NO estratificado por mes ni por estación**) y el estadístico es la **SUMA de `pnl_net_H1` de todos los trades de los bloques extraídos** (no la media por bloque, no reescalado por número de trades). El IC95 son los percentiles 2,5 y 97,5 de las 4.000 réplicas de esa suma.
- **4.000** réplicas, semilla **20260906** (`numpy.random.default_rng(20260906)`); `backtest_results.random_seed = 20260906`.
- **LOSO**: réplicas deterministas, una por estación con ≥ 1 trade OOS; `LOSO_sign_stability` se define sólo sobre réplicas que dejan **≥ 1 trade** restante. **Sensibilidad no decisoria obligatoria:** repetir LOSO excluyendo además las estaciones con **< 5 trades**, y reportar ambas cifras. Motivo: `LOSO_sign_stability = 1.0` es trivialmente sensible a estaciones con 1 trade.

---

## 7. Criterios de éxito/fracaso (congelados)

### 7.1 Condiciones de evaluabilidad (todas necesarias)

- **E1**: capa estricta con **≥ 2 meses de test** con calibración válida (`≠ NO_CALIBRATION`) en el lead 24 h. Meses de test posibles por construcción: 2026-07, 2026-08, 2026-09 (§4.3).
- **E2**: puerta de cobertura §2.3 superada (exclusiones `existence + forecast + pricing` ≤ 30 % de los eventos que pasan las condiciones estructurales).
- **E3**: cuantiles M2 con corte dependiente del lead (§3.2), `prereg_m2_sha256` registrado y una sola versión de M2; en caso contrario `NOT_ASOF_QUANTILES`.
- **E4**: `dataset_version` (con los requisitos (a)-(c) de §2.6), `code_version` y `prereg_sha256` únicos y registrados **antes** de la primera métrica.
- **E5**: en verde sobre `code_version`: todos los tests as-of de 2C/2D (`test_no_future_information.py`, `test_no_lookahead_adversarial.py`, `test_resolution_not_in_features.py`, `test_strategy_a.py`) **más** los tests nuevos de este preregistro: anti-fuga de T (§2.1), label `'Yes'`/`'No'` (§2.4), adversarial de `quantiles_available_at` (§2.5), `dataset_version`/`record_version` (§2.6), join por ICAO (§2.2), y el **test de universo** (§7.1-E8).
- **E6** (nueva): **≥ 3 estaciones con ≥ 1 trade OOS** en el lead de veredicto. Mínimo estructural (para que el estadístico por bloques exista), no umbral de tamaño; heredado de `PREREG_MODELSEL_V5.md` §8. Si no → NOT_EVALUABLE. **Declarado a priori: julio y septiembre tienen exactamente 3 estaciones elegibles** (§1.4).
- **E7** (nueva): filtro por `dataset_version` y desempate por `record_version DESC` implementados y testeados (§2.6).
- **E8** (nueva): el motor reproduce **exactamente** los recuentos de §1.1.1/§1.4 sobre el catálogo congelado (13.926 / 1.266 / 51 en U-LABEL; 12.903 / 1.173 / 50 en U-SIGNAL; 924/84, 1.023/93, 10.912/992, 44/4 por mes). Discrepancia → NOT_EVALUABLE, nunca ajuste del filtro.

Si falla alguna → veredicto **NOT_EVALUABLE** (con la condición fallida nombrada). **No se reintenta con otros parámetros.**

### 7.2 Veredicto (lead 24 h, capa estricta, OOS)

| Veredicto | Condición |
|---|---|
| **SUCCESS_ROBUST** | `IC95(pnl_net_H1_total)` enteramente > 0 **y** `LOSO_sign_stability = 1.0` **y** `pnl_net_H2_total > 0` con IC95 bootstrap que excluya 0 **y** estimación puntual `pnl_net_H1_total > 0` bajo estrés `x_exec = 1 pt` |
| **SUCCESS_H1** | `IC95(pnl_net_H1_total)` enteramente > 0 **y** `LOSO_sign_stability = 1.0`, pero falla alguna condición adicional de ROBUST |
| **FAILURE** | `IC95(pnl_net_H1_total)` enteramente < 0 |
| **INCONCLUSIVE** | Cualquier otro caso |

**DV-2 — desviación declarada respecto de `FEES_SEMANTICS` §6** (R1.H10): `FEES_SEMANTICS` §6 (congelado en D19) define «robusta a semántica de fees» como `pnl_net_H2 > 0` en **estimación puntual**; este preregistro lo **endurece** a IC95 bootstrap que excluya 0. Es una desviación **deliberada y más estricta**, declarada aquí y de repetición obligatoria en el informe. El informe reporta además la estimación puntual de H2, para que la lectura conforme a `FEES_SEMANTICS` §6 sea directamente legible.

**Veredicto secundario obligatorio (no de fase)** [DEC, §0.2.2]: la misma batería restringida a las **estaciones con `in_modelsel = False`**, etiquetada `OUT_OF_MODELSEL`. Si el signo del PnL se sostiene **sólo** en las 24 estaciones usadas para elegir M1, se declara como limitación en el titular del informe.

No hay umbrales adicionales de hit-rate, Brier o número mínimo de trades en el veredicto: IC95 bootstrap y LOSO son los únicos árbitros.

### 7.3 Mapeo a estado de fase (PHASES.md / ROADMAP R21) [DEC]

- `SUCCESS_ROBUST` o `SUCCESS_H1` → Strategy A V1 puede marcarse **VALIDATED (backtest)** sólo si el informe vive en `docs/validation/` con hash.
- `FAILURE` → VALIDATED = NO; Strategy A V1 queda **REFUTED_AS_SPECIFIED**; no se re-ejecuta con otra rejilla.
- `INCONCLUSIVE` o `NOT_EVALUABLE` → VALIDATED = NO; se declara explícitamente; sólo una enmienda autoriza otro run.
- Run con `NOT_ASOF_QUANTILES`, o sin `quantiles_available_at` implementado (§2.5 punto 4), o sin E7 → estado máximo **EXPLORATORY**, nunca VALIDATED.

### 7.4 Categorías de interpretación (descriptivas, obligatorias en el informe)

- **C1 Calibración**: `brier(p_weather) < brier(p_market)` (mejor que el mercado) / `≥` (no mejor).
- **C2 Origen del PnL**: concentración por estrato (¿> 80 % del PnL en un estrato?), por componente ICON, por región; ¿aparece PnL sólo en `icon_eu` como predijo MODELSEL?
- **C3 Sensibilidad a fees**: signo de `pnl_net_H2` y `pnl_net_H3` (con la lectura de `FEES_SEMANTICS` §6 explícita, DV-2).
- **C4 Sensibilidad a ejecución**: signo bajo `x_exec` de estrés.
- **C5 Consistencia entre leads**: coincidencia de signo 9 h vs 24 h.
- **C6 Vigilancia M1**: si ASIA_SUR o HEM_SUR muestran `pnl_net_H1 < 0` con IC95 que excluya 0, se registra como evidencia para M2/M3 (D12 «vigilancia»), **sin** cambiar M1 en este ciclo.
- **C7 Endogeneidad de M1** (nueva): comparación explícita `in_modelsel` sí/no, y declaración de que junio y julio están compuestos al 100 % por estaciones `in_modelsel = True`.
- **C8 Incertidumbre de cuantización** (nueva): fracción del PnL procedente de estratos con `pweather_mapping = NEAREST_UNKNOWN_C` (los dos estratos °C, que son el 99,1 % de U-SIGNAL), declarando que la cuantización del observador es UNKNOWN y NOT_TESTABLE con IEM.
- **C9 Régimen de información** (nueva): PnL por cuartil de `transcurrido(T)` y NZWN aparte.

---

## 8. Prohibiciones

1. **No cambiar** el universo de §1.1, `TAU_GRID`, tolerancias, ventanas walk-forward, métricas, semilla, bloques de bootstrap ni criterios de §7 después de ver cualquier resultado, ni siquiera parcial. Todo cambio es enmienda con hash nuevo y re-run completo etiquetado.
2. **No usar `Y_asof`**: no existe reconstrucción as-of de observaciones (`RECORD_VERSION_ASOF_AUDIT.md`); el label es Y_final con la limitación D17 y jamás se presenta como observación as-of.
3. **No imputar** forecasts, precios, cuantiles, labels ni eventos inexistentes en T; **no desplazar T**.
4. **No usar** `issue_time ≤ T`, `ingestion_timestamp` ni tiempos físicos de observación como criterio de disponibilidad; **no** aceptar cuantiles sin `quantiles_available_at ≤ T`.
5. **No leer** `winning_outcome`, `resolution_timestamp`, `settlement_timestamp`, `is_winner` antes del JOIN de labels en el motor; **no** derivar T de `closedTime`, `daily_high_time` o `last_meaningful_market_time`.
6. **No usar `markets.measurement_rule` ni `cls2.measurement_rule` como clave de elegibilidad ni de segmentación del operador** (§1.1); sólo como etiqueta descriptiva con valor declarado `NULL/GENERIC`.
7. **No excluir mercados por identidad** (`market_id`, `event_id`) ni por prefijo (`arch-`) ni por su `winning_outcome`: la elegibilidad es función de `(contract_source, primary_rule, unit, rounding_rule, clause_lowest_bracket)` y de las condiciones as-of, nunca del resultado (spec v2 §1.4).
8. **No sortear cuotas** de Open-Meteo ni 429; no consultar Open-Meteo desde el motor (sólo lee `weather_forecasts` persistidas); no contratar clave de pago sin decisión explícita del usuario (D9-bis).
9. **No dinero real, no órdenes**, no semánticas ejecutables (D0).
10. **No inferir `fee_regime` por fecha**; leer por mercado + régimen (§1.1.5).
11. **No seleccionar `tau` in-sample** ni reportar como OOS ninguna cifra calculada sobre la ventana de calibración; **no reseleccionar `tau*` en ninguna variante ni en LOSO** (§4.6).
12. **No agregar** leads distintos en una misma métrica; **no** mezclar capa estricta y extendida.
13. **No mezclar `dataset_version`** dentro de un run; **no borrar** datos (sólo añadir/versionar).
14. **No push a main**; motor e informe entran por PR con revisión adversarial, pytest verde y ≥ 2 h de ventana de objeción (D16).
15. **No declarar VALIDATED** con evidencia que viva sólo en `results/` (ignorado por git).

---

## 9. Artefactos y hashes

| Artefacto | Ruta | Contenido | Hash |
|---|---|---|---|
| Este preregistro | `PREREG_BACKTEST_STRATEGY_A.md` + `.sha256` | congelado antes de R19 | `prereg_sha256`, registrado en DECISIONS.md (D-nueva) |
| Manifiesto del run | `docs/validation/backtest_a/RUN_MANIFEST.json` | `backtest_id`, `run_timestamp`, `dataset_version`, `model_version`, `code_version`, `prereg_sha256`, `prereg_m2_sha256`, `settlement_spec_sha256` (`c2b59dd6…`), `station_snapshot_sha256` (`c1617939…`), `station_tz_sha256` (`35d68e65…`), `station_region_component_sha256` (`b6aeeacb…`), `decisions_sha256` (**el vigente al congelar**), `fees_semantics_sha256` (`4dbad3ab…`), `lead_range_sha256` (`1d4161e8…`), `asof_v2_sha256` (`2b815fcb…`), `modelsel_v5_report_sha256` (**`9b4eb188…`**, el del fichero vigente), `random_seed = 20260906`, `TAU_GRID`, tolerancias, ventanas, recuentos del universo (§1.1.1) | sha256 propio |
| Universo congelado | `docs/validation/backtest_a/universe.csv` | una fila por `market_id` de U-LABEL con estrato, `clause_lowest_bracket`, `in_signal_universe`, `icao`, `region`, `component`, `in_modelsel`, `tz`, `target_date` | `SHA256SUMS` |
| Filas `backtest_results` | DuckDB, una fila por `(lead, capa, variante)` | `parameters` JSON = §4-§5 + `prereg_sha256`; `metrics` JSON = §6; `walk_forward_config` JSON = §4.3; `train_window/test_window`; `random_seed`; `feature_list` | — |
| Filas `paper_trades` | DuckDB | un registro por trade con `backtest_id`, `entry_time = T`, `entry_price`, `exit_time = resolution_timestamp`, `exit_price ∈ {0,1}`, `fees` (H1), `slippage = x_exec`, `gross_pnl`, `net_pnl`, `size = 1`, `price_layer`, `price_semantics` | — |
| Tablas planas | `docs/validation/backtest_a/{signals_oos,metrics_by_segment,tau_selection_table,bootstrap_draws,loso,exclusions,costs_sensitivity,coverage,universe}.csv` | como §4-§6; `costs_sensitivity` con `hipotesis_id ∈ {H1,H2,H3}` | `SHA256SUMS` |
| Informe | `docs/validation/PHASE_2F_STRATEGY_A_BACKTEST_REPORT.md` + `.sha256` | veredicto §7 explícito, veredicto secundario `OUT_OF_MODELSEL`, tabla OOS, limitaciones §0.2.2/§2.2/§2.4/§2.5/§3.1, discrepancia §4.5, categorías §7.4, DV-1/DV-2, `tau` adoptado | registrado en DECISIONS.md |
| Log de tests | `docs/validation/backtest_a/pytest_<code_version>.log` | salida completa de E5 | sha256 |

Todo artefacto de `docs/validation/` se commitea en la PR del run; `results/` puede contener copias pero **no es evidencia**.

**Vocabulario de exclusiones [DEC]** (R1.H11): el enum documentado de `markets_excluded.stage` es `{discovery, pricing, labeling, feature}` (comentario de `database.py:491`, DECIDED-V1 en 2D §L). Este preregistro **declara la extensión** del vocabulario con: `universe`, `station`, `target_date`, `anchor`, `existence`, `forecast`, `quantiles`, `features`, `label`, `fees`, `closed_before_T`, `pweather_mapping`. No hay CHECK en la tabla, luego no requiere migración. **Las exclusiones dependientes del lead se persisten ÚNICAMENTE en `exclusions.csv`**, porque la PK de `markets_excluded` es `(market_id, reason, dataset_version)` **sin `lead_hours`** y colisionaría; en `markets_excluded` sólo se escriben exclusiones independientes del lead, con `details` JSON = `{event_id, contract_source, primary_rule, unit, rounding_rule, clause_lowest_bracket, spec_version, prereg_sha256}`. **Sin cambio de schema.**

---

## 10. Dependencias explícitas y enmiendas

### 10.1 Dependencias (estado al congelar; OBSERVADO)

| Dep. | Qué aporta | Estado | Consecuencia si no está |
|---|---|---|---|
| **R15** (`feat/ingest-2b`, no fusionada) | `weather_forecasts` M1 con `available_at = issue_time + 4,76 h`, `station = ICAO` | rama sin fusionar | Sin datos: NOT_EVALUABLE (E2). Debe fusionarse por PR antes de R21 |
| **R13/R14** (labels) | Ya **no** define el universo (§1.1). Aporta la ejecución de `build_label` sobre el catálogo | sin escritor en main | Sin labels: U2 vacía el universo |
| **R16 / PREREG_M2** | cuantiles p10..p90 con corte §3.2 **y `quantiles_available_at`** | sin preregistro ni escritor | Sin cuantiles: `p_weather` no calculable. Sin `quantiles_available_at`: máximo EXPLORATORY (§2.5) |
| **R17** (features persistidas) | filas `features` con `no_lookahead_verified = TRUE`, `dataset_version` fijo, filtro de `dataset_version` y desempate por `record_version` | sin productor; el defecto de `latest_asof` está reconocido en ROADMAP R17 | Sin E7: NOT_EVALUABLE |
| **R19** (motor) | iteración por `T = endDate − lead`, universo §1.1, JOIN labels, coste §5, bootstrap §6.4, LOSO, escritura `backtest_results`/`paper_trades`, y los 6 tests nuevos de E5 | no existe | Sin motor: nada se ejecuta. El motor se implementa **después** del hash de este documento |
| **`SETTLEMENT_OPERATORS_SPEC` v2** | justificación de los estratos habilitados | **borrador pendiente de congelar** (sha `c2b59dd6…`) | El universo **no** depende de su congelado: está enumerado aquí (§1.1). Su congelado posterior con otros estratos = enmienda |
| **R8 helpers** | ya **no** son dependencia: `target_date` y W(m) están fijados en §1.5 | pendientes | Ninguna |
| **`PHASE_2E_LEAD_HOURS_ANCHOR.md`** | ancla T | untracked (`/private/tmp/pmw-publish`, sha `6e405d1a…`) | Debe commitearse antes de R19; hasta entonces este preregistro cita el sha del borrador |

### 10.2 Inconsistencias documentales que deben corregirse antes de referenciar por hash (OBSERVADO 2026-09-07)

- `DECISIONS.sha256` declara `d36749bf…`; el fichero en disco hashea `f2b3ce25…`. **Regenerar.**
- El identificador **`D21` está duplicado** (sesión A y sesión B). **Desambiguar**: citar por identificador exige unicidad.
- `ROADMAP.md:296` cita **`D18`**, que no existe (`DECISIONS.md` salta de D17 a D19). Corregir a D16 o registrar D18.
- `MODELSEL_V5_REPORT.sha256` contiene **tres líneas y dos hashes distintos** para el mismo fichero (`6c3c2a66…` y `9b4eb188…`). El fichero vigente es **`9b4eb188…`**, que es el que el manifiesto citará.
- Ítem **R29** (corrección de la clasificación de la fuente de settlement en código) referenciado por la spec v2 §5 paso 0: registrado en `DECISIONS.md` como D21 (sesión A), pendiente de aparecer en `ROADMAP.md`.

### 10.3 Procedimiento de enmienda (V-enmienda) [DEC]

Cualquiera de los siguientes cambios **obliga** a una nueva versión `PREREG_BACKTEST_STRATEGY_A.md v2.(k+1)` con «Changelog» explícito, nuevo `.sha256`, registro en DECISIONS.md y re-run completo etiquetado (los resultados de la versión anterior se conservan sin editar):

1. Cambio en la **lista de estratos del universo §1.1** o en sus recuentos.
2. Cambio en R17 que altere columnas de `features`, la definición de `no_lookahead_verified` o el `dataset_version` usado.
3. Cambio en R16/M2 que altere la definición de cuantiles, su corte de historia, `quantiles_available_at` o su estratificación; **o una segunda variante de M2**.
4. Cambio en R19 que altere la derivación de T, el modelo de coste, el bootstrap o los criterios; correcciones de bugs que **no** cambien definiciones se registran como `code_version` nuevo con diff citado, sin enmienda, siempre que ninguna métrica haya sido observada con el código defectuoso; si ya se observó, enmienda.
5. **Incorporación de R12 (`SettlementOperator`)** → enmienda **V-2.1**, que sustituye `p_weather` legado por `operator.band_probability` e **invierte el universo de señales** (§3.1): HKO entra, los estratos °C salen. Ambos veredictos se publican; ninguno se retira.
6. Desbiasing V2, selección de `tau` por estrato, sizing fraccional, o cualquier lead/tau fuera de las rejillas.
7. **Cambios de código en 2C/2D LOCKED requeridos por este preregistro**: filtro por `dataset_version` y desempate por `record_version` en `latest_asof`/`build_feature`/`strategy_a` (E7), y `quantiles_available_at` (§2.5). Deben tramitarse **antes** del hash, con el diff citado y con la autorización expresa de ambos revisores; en esa misma enmienda se **nombra el `dataset_version` del run**.
8. Cambio de `L_max`, del ancla 2E, del snapshot D1-COORD, de `STATION_TZ_v1` o de `STATION_REGION_COMPONENT_v1`.
9. Adopción de la lectura alternativa de `target_date` para NZWN (§1.5).

Las enmiendas **no** pueden motivarse por los resultados observados para mover el veredicto; el informe de la versión anterior mantiene su veredicto.

---

## Anexo A. Parámetros congelados (resumen máquina-legible)

```json
{
  "prereg_version": "2.0",
  "baseline_commit": "dfdc73e",
  "settlement_spec": "SETTLEMENT_OPERATORS_SPEC.v2.md#c2b59dd6",
  "universe_rule": "closed enumeration of (v3.primary_source, v3.primary_rule, v3.unit, v3.rounding_rule); NEVER markets.measurement_rule",
  "universe_included_strata": [
    ["WU",   "P_WU_DailyObservations", "C", "whole degree"],
    ["NOAA", "P_NOAA_TempColumn",      "C", "whole degree"],
    ["NOAA", "P_NOAA_TempColumn",      "F", "whole degree"],
    ["HKO",  "P_HKO_AbsDailyMax",      "C", "tenths"]
  ],
  "universe_excluded_strata": [
    ["WU","P_WU_GENERIC_sin_calificador","C",24145,2195],
    ["WU","P_WU_GENERIC_sin_calificador","F",7612,692],
    ["WU","P_WU_DailyObservations","F",2057,187],
    ["NOAA","P_NOAA_HourlyData","F",1441,131],
    ["clause_lowest_bracket rows 5/7",null,null,1870,170]
  ],
  "universe_label_markets": 13926, "universe_label_events": 1266, "universe_label_stations": 51,
  "universe_signal_markets": 12903, "universe_signal_events": 1173, "universe_signal_stations": 50,
  "universe_signal_by_month": {"2026-06":[924,84,3],"2026-07":[1023,93,3],"2026-08":[10912,992,50],"2026-09":[44,4,3]},
  "hko_excluded_from_signals": {"markets":1023,"events":93,"reason":"pweather_mapping_refuted"},
  "model_M1": "icon_seamless",
  "L_max_hours": 4.76, "L_max_n_runs_dwd_icon": 78, "L_max_sensitivity_hours": 5.76,
  "anchor": "T = endDate - lead_hours*3600",
  "target_date_rule": "UTC date of endDate; W(m) = local civil day in STATION_TZ_v1 tz",
  "leads_primary_hours": [9, 24], "lead_verdict_hours": 24, "leads_secondary_hours": [36, 48],
  "quantile_history_cutoff": "target_date <= D - 2 - ceil(lead_hours/24)",
  "period_strict": ["2026-06-03", "D_fin<=2026-09-04 (observed 2026-09-02 in U-SIGNAL)"],
  "period_extended_not_asof": ["2026-04-02", "2026-06-02"],
  "stations": 55, "station_snapshot": "D1-COORD v1.3#c1617939",
  "station_tz": "STATION_TZ_v1.json#35d68e65",
  "station_region_component": "STATION_REGION_COMPONENT_v1.json#b6aeeacb",
  "price_semantics_primary": ["MIDPOINT_ESTIMATED", "INDICATIVE"],
  "price_semantics_sensitivity": ["LAST_TRADE_INDICATIVE", "NEAREST_TRADE_INDICATIVE"],
  "quote_max_age_hours": 6, "stale_quote_unit": "event",
  "coverage_gate_max_excluded_fraction": 0.30,
  "coverage_denominator": "events passing structural U1,U3,U6,U7,U8,U9,U10",
  "tau_grid": [0.01, 0.02, 0.03, 0.05, 0.08],
  "tau_selection": "walk-forward monthly expanding, as-of: calibration = events with resolution_timestamp <= T_first(lead, test month); maximize pnl_net_H1; n_trades>=30; tie->larger tau; pooled by lead; frozen for all variants and LOSO",
  "test_months": ["2026-07", "2026-08", "2026-09"],
  "weather_sum_tolerance": 1e-6, "market_sum_min": 0.80, "market_sum_max": 1.30,
  "market_sum_sensitivity": [0.90, 1.15],
  "cost_primary": "H1: 0.05*p*(1-p)", "cost_sensitivity": ["H2: 0.10*min(p,1-p)", "H3: 0.10*p*(1-p)"],
  "pnl_formula": "pnl_net = (Y - p) - c(p) - x_exec   (FEES_SEMANTICS §2(5))",
  "exit_mode": "hold_to_resolution", "x_exec_primary": 0.0, "x_exec_stress": ["0.5*tick", 0.01],
  "size_per_signal_shares": 1,
  "bootstrap_block": "station-month",
  "bootstrap_statistic": "sum of pnl_net_H1 over B blocks resampled with replacement (B = observed blocks), unstratified",
  "bootstrap_reps": 4000, "random_seed": 20260906,
  "evaluability": ["E1>=2 test months","E2 coverage<=30%","E3 M2 as-of + prereg_m2_sha256","E4 versions",
                   "E5 tests green","E6>=3 stations with trades","E7 dataset_version filter + record_version tiebreak",
                   "E8 universe counts reproduced"],
  "verdict_metric": "pnl_net_H1_total OOS, IC95 bootstrap excluding 0, LOSO sign stability == 1.0",
  "declared_deviations": ["DV-1 p_weather 2D LOCKED sin R12; HKO fuera de señales",
                          "DV-2 ROBUST mas estricto que FEES_SEMANTICS §6"]
}
```

---

## Anexo B. Referencias

**Decisiones — citadas por identificador, nunca por línea** (versión de `DECISIONS.md` a registrar en el manifiesto; sha declarado hoy `d36749bf…`, sha en disco `f2b3ce25…`, OBSERVADO 2026-09-07):
**D0** puertas autoimpuestas · **D1** convención canónica de coordenadas · **D9-bis** roadmap y custodia de artefactos · **D12** M1 ADOPTADO = `icon_seamless` · **D14/D15** OPKC y snapshot v1.3 · **D16** política de fusión por PR · **D17** Y_final + captura prospectiva y regla de etiquetado por fuente contractual · **D19** semántica de fees y modelo de coste.

**Código (`origin/main` = `dfdc73e`; ficheros versionados, líneas estables bajo el commit):**
- `src/weather_agent/strategy/strategy_a.py`: `MODEL_VERSION` :48; `signal_for` :78-84; `_require` :87-117; validaciones :118-123; exclusión `executable_or_invalid_price` :190-198; linaje de precio :204-218; elegibilidad por evento :224-237; W.1-W.3 :243-245; `edge_net`/`net_edge` NULL :252, :266.
- `src/weather_agent/features.py`: `FORBIDDEN_FEATURE_FIELDS` :20-27; cuantiles :40-45; precio as-of :74-82; guarda EXECUTABLE (vacua sobre el CHECK actual) :90-91; forecast as-of :97-105; lectura de `forecast_p10..p90` :144-150; guardas finales :199-215.
- `src/weather_agent/probability.py`: `quantiles_to_distribution` :66-98 (operador nearest implícito); `band_probability` :57-109.
- `src/weather_agent/labeling.py` :31-63.
- `src/weather_agent/database.py`: `AS_OF_COLUMNS` :79-93; `market_fee_schedule` :129-144; `markets` :149-186; `price_history` + CHECK de `price_semantics` :215-228; `weather_forecasts` :289-311; `weather_errors` :334-352; `features` :364-384; `predictions` :389-407; `signals` :412-431; `paper_trades` :436-460; `backtest_results` :465-482; `markets_excluded` :487-499; ALTER `raw_fee_fields` :532; `query_asof`/`latest_asof` :803-865.
- `src/weather_agent/polymarket/resolution.py`: `winning_outcome` :72; `parse_measurement_rule` :126-138.
- `src/weather_agent/polymarket/fees.py` :14-28, :48-104; `src/weather_agent/config.py` :202-212 (DEFAULTS sin consumidor).
- `PHASE_2D_STRATEGY_A_DESIGN.md` (origin/main): §C :53-58; §D :65-66; §F/§G :66-106; §I :116-124; §L :151-153; §M :156-161; §N :163-168; §T :208-218; W.1-W.4 :246-262; W.10 :322-333; tabla OPEN :393-398.
- Tests: `tests/test_no_future_information.py:13-182`; `tests/test_no_lookahead_adversarial.py:56-181`; `tests/test_resolution_not_in_features.py:79-211`; `tests/test_strategy_a.py:51-52, 221-229, 265-272`.

**Artefactos de `/Users/mariaaleu/pmw-e2/`** (hashes en la cabecera): `SETTLEMENT_OPERATORS_SPEC.v2.md`, `STATION_REGION_COMPONENT_v1.json`, `STATION_TZ_v1.json`, `STATION_COORDS_SNAPSHOT_v1.3.json`, `FEES_SEMANTICS.md`, `PREREG_LEAD_HOURS_RANGE.md`, `PREREG_MODELSEL_ASOF_V2.md`, `PREREG_E2.md`, `E2_RESULTS.json`, `E2_DISCRIMINATION_EVIDENCE.json`, `HKO_OPERATOR_TEST.json`, `MODELSEL_V5_REPORT.md`, `MODELSEL_V5_CORRECTION_01.md`, `REVISION_IMPACT_AUDIT.md`, `RECORD_VERSION_ASOF_AUDIT.md`, `F3-CLOSURE-REPORT.md`, `PREREG_MODELSEL_V5.md`, `PREREG_MODELSEL_GEOVAL_V3.md`, `WF_r18_refutations.json`.

**Catálogo:** `/Users/mariaaleu/pmw-catalog-v2/CATALOG_V2.duckdb` (`read_only=True`), tablas `v3`, `cls2`, `ev`, `mk`. Todos los recuentos de §1.1, §1.4, §2.1 y §4.3 son recómputos propios OBSERVADOS el 2026-09-07.

---

## Anexo C. Tabla congelada estación → (región, componente ICON, `in_modelsel`, tz, ventana) [R0.H5, R1.H3]

**Fuente única: `STATION_REGION_COMPONENT_v1.json` sha `b6aeeacb69ed9bbe18a9e9ab3c48c85ae8bbb14a1079d3857e648d0055adf24e` + `STATION_TZ_v1.json` sha `35d68e6532a99b97e9d9596491f40e20d13e05bee9fc9feb7a1897318b050bd2`.** Sustituye a la referencia incorrecta de v1.0 a `PREREG_MODELSEL_V5.md` (OBSERVADO por el refutador: ese documento **no contiene** «ASIA_SUR» ni «HEM_SUR»; la partición regional con esas etiquetas es de `PREREG_MODELSEL_GEOVAL_V3.md` y sólo cubría 16 estaciones). La región es aquí una **partición cerrada por país** (mapa `region_map` del propio artefacto, 32 países → 9 regiones), el componente procede de `V5_UNIVERSE_COMPONENTS.json` recalculado con coordenadas D1-COORD v1.3, y `v3_conflicts = []` (OBSERVADO).

**Totales (OBSERVADO):** 55 estaciones; `in_modelsel` **24 sí / 31 no**; componentes 42 `icon_global` / 7 `icon_eu` / 6 `icon_d2`; regiones ASIA_ESTE 16, NORTEAMERICA 12, EUROPA 10, HEM_SUR 4, ORIENTE_MEDIO 4, SUDESTE_ASIA 4, ASIA_SUR 2, LATAM_NORTE 2, AFRICA_OESTE 1.

Columnas: `inicio`/`fin` = desfase en horas del inicio y del fin de W(m) respecto de `endDate` (calculado para 2026-07-15); `t9` = horas de W(m) ya transcurridas en T con lead 9 h (a lead 24 h es **0 en las 55**); `mk`/`ev` = presencia en el universo (U-SIGNAL; la fila VHHH da los recuentos de HKO en U-LABEL).

| ICAO | Ciudad | País | Región | Componente | `in_modelsel` | tz | inicio | fin | t9 | mk | ev |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CYYZ | Toronto | CA | NORTEAMERICA | icon_global | no | America/Toronto | −8 | +16 | 0 | 275 | 25 |
| DNMM | Lagos | NG | AFRICA_OESTE | icon_global | no | Africa/Lagos | −13 | +11 | 4 | 0 | 0 |
| EDDM | Munich | DE | EUROPA | icon_d2 | no | Europe/Berlin | −14 | +10 | 5 | 264 | 24 |
| EFHK | Helsinki | FI | EUROPA | icon_eu | **sí** | Europe/Helsinki | −15 | +9 | 6 | 264 | 24 |
| EGLC | London | GB | EUROPA | icon_d2 | **sí** | Europe/London | −13 | +11 | 4 | 264 | 24 |
| EHAM | Amsterdam | NL | EUROPA | icon_d2 | no | Europe/Amsterdam | −14 | +10 | 5 | 275 | 25 |
| EPWA | Warsaw | PL | EUROPA | icon_eu | no | Europe/Warsaw | −14 | +10 | 5 | 264 | 24 |
| FACT | Cape Town | ZA | HEM_SUR | icon_global | **sí** | Africa/Johannesburg | −14 | +10 | 5 | 264 | 24 |
| KATL | Atlanta | US | NORTEAMERICA | icon_global | **sí** | America/New_York | −8 | +16 | 0 | 11 | 1 |
| KAUS | Austin | US | NORTEAMERICA | icon_global | no | America/Chicago | −7 | +17 | 0 | 11 | 1 |
| KBKF | Denver | US | NORTEAMERICA | icon_global | **sí** | America/Denver | −6 | +18 | 0 | 11 | 1 |
| KDAL | Dallas | US | NORTEAMERICA | icon_global | **sí** | America/Chicago | −7 | +17 | 0 | 11 | 1 |
| KHOU | Houston | US | NORTEAMERICA | icon_global | **sí** | America/Chicago | −7 | +17 | 0 | 11 | 1 |
| KLAX | Los Angeles | US | NORTEAMERICA | icon_global | **sí** | America/Los_Angeles | −5 | +19 | 0 | 11 | 1 |
| KLGA | NYC | US | NORTEAMERICA | icon_global | **sí** | America/New_York | −8 | +16 | 0 | 11 | 1 |
| KMIA | Miami | US | NORTEAMERICA | icon_global | **sí** | America/New_York | −8 | +16 | 0 | 11 | 1 |
| KORD | Chicago | US | NORTEAMERICA | icon_global | no | America/Chicago | −7 | +17 | 0 | 11 | 1 |
| KSEA | Seattle | US | NORTEAMERICA | icon_global | no | America/Los_Angeles | −5 | +19 | 0 | 11 | 1 |
| KSFO | San Francisco | US | NORTEAMERICA | icon_global | no | America/Los_Angeles | −5 | +19 | 0 | 11 | 1 |
| LEMD | Madrid | ES | EUROPA | icon_eu | no | Europe/Madrid | −14 | +10 | 5 | 264 | 24 |
| LFPB | Paris | FR | EUROPA | icon_d2 | no | Europe/Paris | −14 | +10 | 5 | 264 | 24 |
| LFPG | Paris | FR | EUROPA | icon_d2 | no | Europe/Paris | −14 | +10 | 5 | 0 | 0 |
| LIMC | Milan | IT | EUROPA | icon_d2 | **sí** | Europe/Rome | −14 | +10 | 5 | 264 | 24 |
| LLBG | Tel Aviv | IL | ORIENTE_MEDIO | icon_eu | **sí** | Asia/Jerusalem | −15 | +9 | 6 | 979 | 89 |
| LTAC | Ankara | TR | ORIENTE_MEDIO | icon_eu | no | Europe/Istanbul | −15 | +9 | 6 | 275 | 25 |
| LTFM | Istanbul | TR | ORIENTE_MEDIO | icon_eu | **sí** | Europe/Istanbul | −15 | +9 | 6 | 979 | 89 |
| MMMX | Mexico City | MX | LATAM_NORTE | icon_global | **sí** | America/Mexico_City | −6 | +18 | 0 | 275 | 25 |
| MPMG | Panama City | PA | LATAM_NORTE | icon_global | **sí** | America/Panama | −7 | +17 | 0 | 297 | 27 |
| **NZWN** | **Wellington** | NZ | HEM_SUR | icon_global | no | Pacific/Auckland | **−24** | **+0** | **15** | 275 | 25 |
| OEJN | Jeddah | SA | ORIENTE_MEDIO | icon_global | no | Asia/Riyadh | −15 | +9 | 6 | 264 | 24 |
| OPKC | Karachi | PK | ASIA_SUR | icon_global | **sí** | Asia/Karachi | −17 | +7 | 8 | 264 | 24 |
| RCSS | Taipei | TW | ASIA_ESTE | icon_global | no | Asia/Taipei | −20 | +4 | 11 | 297 | 27 |
| RCTP | Taipei | TW | ASIA_ESTE | icon_global | no | Asia/Taipei | −20 | +4 | 11 | 0 | 0 |
| RJTT | Tokyo | JP | ASIA_ESTE | icon_global | no | Asia/Tokyo | −21 | +3 | 12 | 275 | 25 |
| RKPK | Busan | KR | ASIA_ESTE | icon_global | no | Asia/Seoul | −21 | +3 | 12 | 275 | 25 |
| RKSI | Seoul | KR | ASIA_ESTE | icon_global | **sí** | Asia/Seoul | −21 | +3 | 12 | 275 | 25 |
| RPLL | Manila | PH | SUDESTE_ASIA | icon_global | no | Asia/Manila | −20 | +4 | 11 | 275 | 25 |
| SAEZ | Buenos Aires | AR | HEM_SUR | icon_global | no | America/Argentina/Buenos_Aires | −9 | +15 | 0 | 275 | 25 |
| SBGR | Sao Paulo | BR | HEM_SUR | icon_global | **sí** | America/Sao_Paulo | −9 | +15 | 0 | 275 | 25 |
| UUWW | Moscow | RU | EUROPA | icon_eu | **sí** | Europe/Moscow | −15 | +9 | 6 | 979 | 89 |
| VHHH | Hong Kong | HK | ASIA_ESTE | icon_global | no | Asia/Hong_Kong | −20 | +4 | 11 | **1.023 (sólo U-LABEL)** | **93** |
| VILK | Lucknow | IN | ASIA_SUR | icon_global | **sí** | Asia/Kolkata | −18 | +6 | 8 | 275 | 25 |
| WIHH | Jakarta | ID | SUDESTE_ASIA | icon_global | no | Asia/Jakarta | −19 | +5 | 10 | 0 | 0 |
| WMKK | Kuala Lumpur | MY | SUDESTE_ASIA | icon_global | no | Asia/Kuala_Lumpur | −20 | +4 | 11 | 275 | 25 |
| WSSS | Singapore | SG | SUDESTE_ASIA | icon_global | no | Asia/Singapore | −20 | +4 | 11 | 275 | 25 |
| ZBAA | Beijing | CN | ASIA_ESTE | icon_global | no | Asia/Shanghai | −20 | +4 | 11 | 275 | 25 |
| ZGGG | Guangzhou | CN | ASIA_ESTE | icon_global | no | Asia/Shanghai | −20 | +4 | 11 | 275 | 25 |
| ZGSZ | Shenzhen | CN | ASIA_ESTE | icon_global | **sí** | Asia/Shanghai | −20 | +4 | 11 | 275 | 25 |
| ZHCC | Zhengzhou | CN | ASIA_ESTE | icon_global | no | Asia/Shanghai | −20 | +4 | 11 | 275 | 25 |
| ZHHH | Wuhan | CN | ASIA_ESTE | icon_global | no | Asia/Shanghai | −20 | +4 | 11 | 275 | 25 |
| ZSJN | Jinan | CN | ASIA_ESTE | icon_global | **sí** | Asia/Shanghai | −20 | +4 | 11 | 286 | 26 |
| ZSPD | Shanghai | CN | ASIA_ESTE | icon_global | no | Asia/Shanghai | −20 | +4 | 11 | 275 | 25 |
| ZSQD | Qingdao | CN | ASIA_ESTE | icon_global | **sí** | Asia/Shanghai | −20 | +4 | 11 | 275 | 25 |
| ZUCK | Chongqing | CN | ASIA_ESTE | icon_global | **sí** | Asia/Chongqing | −20 | +4 | 11 | 275 | 25 |
| ZUUU | Chengdu | CN | ASIA_ESTE | icon_global | no | Asia/Chongqing | −20 | +4 | 11 | 275 | 25 |

**Estaciones canónicas SIN presencia en el universo elegible (OBSERVADO): DNMM, RCTP, LFPG, WIHH** (0 mercados en U-LABEL). El universo cubre por tanto 51 de las 55 (50 ICAO + HKO).

**Reparto `in_modelsel` (OBSERVADO):**
- U-SIGNAL: `sí` 24 estaciones / **6.842 mk / 622 ev**; `no` 26 estaciones / **6.061 mk / 551 ev**.
- U-LABEL: `sí` 24 / 6.842 / 622; `no` 27 / 7.084 / 644 (VHHH tiene `in_modelsel = false`).
- **Junio y julio: 3 estaciones, las tres con `in_modelsel = true`** (LTFM, LLBG, UUWW).

**Advertencia de alcance (heredada, no elevada):** `verification_scope` es `OBSERVADA` en 11 estaciones e `INFERIDA` en 44; `STATION_REGION_COMPONENT_v1` acota la transferencia de M1, no el operador de settlement.

---

## Anexo D. Vocabulario cerrado de `stage` y `reason`

**`stage`** (documentado `{discovery, pricing, labeling, feature}` + extensión declarada en §9): `universe`, `station`, `target_date`, `anchor`, `existence`, `forecast`, `quantiles`, `pricing`, `features`, `label`, `fees`, `closed_before_T`, `pweather_mapping`, `feature`.

**`reason`** (enumeración cerrada; los valores marcados ⟨spec⟩ coinciden con el enum de `SETTLEMENT_OPERATORS_SPEC` v2 §3.4): `stratum_not_enabled`, `clause_stratum_not_audited`⟨spec⟩, `station_not_in_snapshot`, `station_tz_unknown`⟨spec⟩, `unit_unknown`⟨spec⟩, `enddate_not_1200Z`, `event_not_created_at_T`, `no_forecast_asof`, `quantiles_available_at_missing`, `quantiles_available_at_after_T`, `insufficient_history`, `no_quote`, `stale_quote`, `price_semantics_not_admissible`, `not_partition`, `sum_pmarket_out_of_tolerance`, `sum_pweather_out_of_tolerance`, `no_lookahead_flag_false`, `unresolved`, `no_resolution_timestamp`, `prediction_after_resolution`, `winning_outcome_unexpected_value`, `fee_status_not_known`, `fee_exponent_not_1`, `closed_before_T`, `pweather_mapping_refuted`, `dataset_version_mismatch`.

Cualquier exclusión que no encaje en un valor de este enum → **el run se detiene** y la situación se trata como enmienda, nunca como un `reason` nuevo improvisado.

---

## Changelog v2 (hallazgo → acción + motivo)

### Refutador 1 (`WF_r18_refutations.json[0]`)

- **R0.H0 (BLOQUEANTE — U5 × §4.3 × E1)** → **APLICADO.** `U5` (`measurement_rule` no nulo) **eliminado como filtro**; `measurement_rule` pasa a etiqueta de segmentación con valor declarado `NULL/GENERIC` (§1.1, §6.3(c)); la elegibilidad usa `v3.primary_rule`. **Motivo:** con U5, jun y jul quedaban vacíos (38.665/51.051 mercados con `measurement_rule` NULL; HKO 1.859/1.859 NULL) y E1 fallaba **antes de ver un dato**, además de contradecir U3 y la celda HKO de §6.3. Se añade la cuantificación exigida: universo por estrato y por mes en §1.1.1 y §1.4 (recómputo propio 2026-09-07), y la tabla walk-forward de §4.3 con las cifras reales.
- **R0.H1 (IMPORTANTE — `compat_status` «según R14»)** → **APLICADO.** §1.1.3 congela la tabla `primary_rule → compat_status` con la evidencia E2 por estrato; `P_WU_GENERIC_sin_calificador` y `P_byForecast` quedan **UNKNOWN → excluidos**, cuantificados (31.757 mk / 2.887 ev en el catálogo, **24.145+7.612 mk y 2.195+692 ev en la ventana**); los valores admisibles de `compat_status` se fijan aquí (`{DIRECT, PROXY_AUDITED, PROXY_NOT_AUDITED, NONE}`) y no en R14. **Motivo:** delegar el universo a un componente futuro es una elección a posteriori encubierta.
- **R0.H2 (IMPORTANTE — definición del label)** → **APLICADO.** §2.4: `label = 1 iff build_label(...)['label'] == 'Yes'`, `0 iff 'No'`, `None → stage=label`, valor inesperado → fail-closed; test obligatorio con fixture. **Motivo:** OBSERVADO, `winning_outcome ∈ {'Yes','No'}` y la comparación con un `token_id` daría `label = 0` siempre.
- **R0.H3 (IMPORTANTE — U4 no ejecutable)** → **APLICADO.** §1.1.5 escribe la consulta SQL exacta con JOIN a `market_fee_schedule` (`record_version` máximo) y `json_extract(raw_fee_fields,'$.feeSchedule.exponent') = 1`, y declara que la lectura es **por régimen** dentro del `dataset_version`. **Motivo:** `markets.fee_status` y `exponent` no existen como columnas.
- **R0.H4 (IMPORTANTE — `stale_quote`, puerta, `price_semantics`)** → **APLICADO íntegro.** `stale_quote` excluye el **evento** completo y se implementa como **prefiltro anterior a `generate_event_signals`** (§2.3); la puerta de cobertura recibe denominador y numerador explícitos (§2.3); `price_semantics` admisibles = enumeración cerrada `{MIDPOINT_ESTIMATED, INDICATIVE}` con `UNKNOWN` → exclusión y las dos semánticas de trade como sensibilidad; `fidelity`/`source_window` como segmentos, no filtros. **Motivo:** 2D §D/§E fijan la elegibilidad por evento; sin enumeración cerrada, la elección de semánticas quedaba abierta a posteriori. **Ajuste declarado:** `fidelity`/`source_window` **no** se convierten en filtros, para no reproducir el defecto de U5 (vaciar el universo con una condición no cuantificada antes de congelar).
- **R0.H5 (IMPORTANTE — región y componente)** → **APLICADO con artefacto nuevo.** Anexo C con las 55 estaciones (región por partición cerrada de país, componente recalculado sobre v1.3, `in_modelsel`, tz), `STATION_REGION_COMPONENT_v1.json` sha `b6aeeacb…` en el manifiesto; se **corrige** la referencia errónea a `PREREG_MODELSEL_V5.md` (no contiene ASIA_SUR/HEM_SUR). **Motivo:** sin tabla cerrada, la segmentación regional y C6 se asignarían a posteriori.
- **R0.H6 (MENOR — clave de join de estación)** → **APLICADO.** §2.2 fija la partición y el filtro por **`station_identifier` (ICAO)** y exige un test de R19 que falle si el join devuelve 0 forecasts para una estación del snapshot presente en el universo. **Motivo:** `markets.station` es el nombre descubierto y `feat/ingest-2b` escribe ICAO.
- **R0.H7 (MENOR — `target_date` presentado como OBS)** → **APLICADO.** Se retira [OBS] de la igualdad de fechas; lo OBSERVADO es la hora 12:00:00Z en 8.557/8.557 eventos; la regla `target_date := fecha UTC de endDate` es DEC (§1.5), con W(m) por `STATION_TZ_v1` y **NZWN tratada explícitamente** (entra; ventana que cierra en `endDate`; 62,5 % transcurrido a 9 h y 0 % a 24 h; lectura alternativa registrada como abierta y prohibida en V1).
- **R0.H8 (MENOR — `dataset_version`, `model_version`, `edge_net`)** → **APLICADO.** §2.6: el `dataset_version` se **nombra** en la enmienda que cierre R15/R17 y debe cumplir tres condiciones verificables; `model_version = 'backtestA_v1|<M2_run>'` con `record_version` propio, distinto de `stratA_pmodel_v1`; `edge_net`/`net_edge` sólo en las filas del motor, autorizado por D19; las filas de Strategy A V1 siguen NULL.
- **R0.H9 (MENOR — definiciones estadísticas y cifras)** → **APLICADO íntegro.** §6.4 escribe la fórmula del estadístico bootstrap (suma sobre `B` bloques remuestreados con reemplazo, sin estratificar) y añade la sensibilidad LOSO excluyendo estaciones con < 5 trades; §0.2.2 corrige `L_max` a **78 pasadas de `dwd_icon`** (307 = 4 modelos); §9 declara la extensión del enum de `stage`; §10.2 y §9 fijan el hash **`9b4eb188…`** para `MODELSEL_V5_REPORT.md` y registran el desajuste de `DECISIONS.sha256` y el `D18` inexistente.

### Refutador 2 (`WF_r18_refutations.json[1]`)

- **R1.H0 (BLOQUEANTE — universo delegado a R14)** → **APLICADO íntegro.** §1.1 sustituye U3 por **enumeración cerrada** con `n_mercados`/`n_eventos` de la ventana estricta (recómputo propio: WU_GENERIC 24.145+7.612 / 2.195+692; WU_DailyObs C 6.996/636 y F 2.057/187; NOAA_TempColumn C 7.656/696 y F 121/11; NOAA_Hourly 1.441/131; HKO 1.023/93; byForecast y CWA 0). Se excluyen explícitamente `P_WU_GENERIC_sin_calificador`, `P_byForecast`, `WU_DailyObs °F`, `NOAA_HourlyData °F` y CWA; **HKO se decide ahora** (entra en el universo de label con `compat_status = DIRECT`, sale del universo de señales por §3.1); el vocabulario se alinea con `{DIRECT, PROXY_AUDITED}`; se declara que el label del backtest es `winning_outcome` y **no depende** de `compat_status` (U3 es restricción de universo por operador auditado, coincidente con el universo de entrenamiento de M2). Cualquier cambio = enmienda.
- **R1.H1 (IMPORTANTE — M2 sin preregistro)** → **APLICADO.** §3.2 congela el mínimo exigido a M2 (error = Y_final − forecast M1; estratificación `(station, model, lead)`; `n ≥ 10` sin fallback silencioso; corte de historia por lead; regla de selección de fila por `record_version` máximo con cuantiles no nulos y mismo `available_at`; test obligatorio) y añade `prereg_m2_sha256` y **una sola versión de M2 por versión del preregistro** como condición de evaluabilidad E3.
- **R1.H2 (IMPORTANTE — `target_date` delegado a R8)** → **APLICADO.** §1.5 fija la regla sin helper futuro, con W(m) por tz de estación, y **decide NZWN** (entra; 275 mk / 25 ev; efectos por lead cuantificados). Se anota la tensión con 2D §C como herencia: la derivación ocurre en el caller.
- **R1.H3 (IMPORTANTE — región no reproducible)** → **APLICADO.** Anexo C cerrado y hasheado; se retira la promesa de reproducir «las etiquetas de MODELSEL V5».
- **R1.H4 (IMPORTANTE — circularidad de U8 y de la puerta)** → **APLICADO.** U8 pasa a ser **estructural** (`band_integrity(...).is_partition`, sin forecast), citando 2D §F en lugar de §G; denominador y numerador de la puerta definidos; las exclusiones por tolerancia se declaran **fuera** de la puerta.
- **R1.H5 (IMPORTANTE — qué recalcula cada variante)** → **APLICADO íntegro.** §4.6: señales, trades y `tau*` congelados en el run primario; toda variante recalcula sólo el PnL; LOSO sin reselección; y §5.3 adopta **una sola fórmula**, la de `FEES_SEMANTICS` §2(5) (`pnl_net = (Y − p) − c(p) − x_exec`). Única excepción explicitada: la sensibilidad `L_max + 1 h`, que por construcción puede cambiar el run de forecast y se ejecuta como run separado etiquetado.
- **R1.H6 (MENOR — mínimo estructural de estaciones)** → **APLICADO.** **E6: ≥ 3 estaciones con ≥ 1 trade OOS**; `LOSO_sign_stability` definida sobre réplicas con ≥ 1 trade restante. Se añade la advertencia a priori de que julio y septiembre tienen exactamente 3 estaciones.
- **R1.H7 (MENOR — `markets.fee_status`)** → **APLICADO.** Etiqueta [OBS] corregida y U4 reescrito como JOIN (§1.1.5).
- **R1.H8 (MENOR — U6 abierto)** → **APLICADO.** `U6 := umaResolutionStatus = 'resolved'` (enumeración cerrada) con los recuentos (93.141 / 47 / 33 NULL; 51.051/51.051 en la ventana).
- **R1.H9 (MENOR — contradicción §2.4 vs §3.1)** → **APLICADO.** Frase reformulada en §2.4 con la redacción propuesta, adaptada al corte dependiente del lead.
- **R1.H10 (MENOR — ROBUST vs FEES_SEMANTICS §6)** → **APLICADO.** Declarado como **DV-2**, desviación deliberada y más estricta, con obligación de reportar también la estimación puntual de H2.
- **R1.H11 (MENOR — `stage` y PK de `markets_excluded`)** → **APLICADO.** §9 declara la extensión del enum de `stage` y fija que **las exclusiones por lead viven sólo en `exclusions.csv`**, porque la PK `(market_id, reason, dataset_version)` no tiene `lead_hours`. Sin cambio de schema.
- **R1.H12 (MENOR — citas por línea a DECISIONS.md)** → **APLICADO y ampliado.** Todo el documento cita **por identificador D0…D19** más el sha de `DECISIONS.md`; se retira el Anexo B de citas por línea a `DECISIONS.md`. **Hallazgo propio añadido:** `DECISIONS.sha256` vuelve a estar desactualizado (declara `d36749bf…`, disco `f2b3ce25…`, OBSERVADO 2026-09-07) y **`D21` está duplicado**; ambas cosas son precondición documental del congelado (§10.2).

### Refutador 3 (`WF_r18_refutations.json[2]`)

- **R2.H0 (BLOQUEANTE — cuantiles y `no_lookahead_verified`)** → **APLICADO íntegro, los 4 puntos.** §2.5 exige **`quantiles_available_at ≤ T`** como requisito de datos; añade el **test adversarial** en E5; declara explícitamente que `no_lookahead_verified` **no certifica los cuantiles**; y fija que **hasta que exista ese campo, cualquier run es como máximo EXPLORATORY**. Se declara que su introducción, si toca `features.py`, se tramita como enmienda del diseño 2D antes del congelado (§10.3, punto 7).
- **R2.H1 (IMPORTANTE — corte D−2 y leads secundarios)** → **APLICADO con un ajuste declarado.** §3.2 adopta el **corte dependiente del lead `D − 2 − ceil(lead/24)`**; se reescribe «garantiza» como afirmación condicionada al lead ≤ 24 h; se usa la latencia de **observación** (fin de día civil local + ~1,3 h) y no la de resolución; 36/48 h se etiquetan `NOT_ASOF_QUANTILES` si se reportaran con D−2. **Ajuste:** el ejemplo del hallazgo dice «D−3 a 36 h», pero su propia fórmula da **D−4**; se aplica la fórmula (más conservadora) y se declara la discrepancia.
- **R2.H2 (IMPORTANTE — walk-forward de calendario)** → **APLICADO.** §4.3 define la calibración con criterio **as-of** (`resolution_timestamp ≤ T_primero(ℓ, M)`), con las cifras de exclusión recomputadas sobre el universo real (81/84, 174/177, 1.147/1.169 a 24 h; 84/84, 177/177, 1.168/1.169 a 9 h). **Ajuste declarado:** se adopta la primera alternativa del hallazgo (corte as-of por mes) y **no** la segunda (`tau*` recalculado por evento sin frontera de mes), porque esta última multiplica los grados de libertad de la selección y no es reproducible sin fijar además la regla de expansión; queda registrada como variante V2 por enmienda.
- **R2.H3 (IMPORTANTE — `dataset_version` inejecutable)** → **APLICADO.** Nueva condición **E7**: filtro por `dataset_version` en `price_history` y `weather_forecasts` y desempate por `record_version DESC`, con test en E5 (dos `dataset_version` y dos `record_version` con el mismo `available_at`). Se declara que es **cambio de código en 2C/2D LOCKED, no de esquema**, y se tramita como enmienda **antes** del hash (§10.3, punto 7).
- **R2.H4 (IMPORTANTE — M1 y L_max endógenos)** → **APLICADO íntegro.** §0.2.2 declara que M1 y `L_max` se fijaron con **datos del mismo periodo y en 24 de las 55 estaciones**; §6.3(i) añade el segmento obligatorio `in_modelsel` sí/no (24 vs 31; en U-SIGNAL 6.842/622 vs 6.061/551); §7.2 añade el **veredicto secundario `OUT_OF_MODELSEL`**; §2.2 añade la sensibilidad `L_max + 1 h` sin reselección. **Refuerzo propio:** OBSERVADO que junio y julio están compuestos **al 100 %** por estaciones `in_modelsel = True` (LTFM, LLBG, UUWW), lo que agrava el hallazgo respecto de lo que el refutador pudo ver.
- **R2.H5 (MENOR — fees y tick no as-of)** → **APLICADO.** §0.2.3 y §5.1 reformulados: `fee_regime`, `feeSchedule` y `tick` son el **estado actual de Gamma**, la vigencia histórica es UNKNOWN, y consta en la limitación obligatoria del informe.
- **R2.H6 (MENOR — cifras de `closedTime` y stage nuevo)** → **APLICADO.** §2.1 sustituye la cita heredada de 2E por la distribución **recomputada sobre el universo real** (mín −14,75 h, mediana +9,82 h, p95 +19,26 h, máx +63,77 h) y añade el stage **`closed_before_T`**, cuantificado: **1 evento a 9 h (936283, Panamá) y 0 a 24 h**.
- **R2.H7 (MENOR — U2/U6 como filtros ex post)** → **APLICADO.** §1.1.4 añade la frase exigida: U2 y U6 son filtros ex post sobre el estado de resolución; en la capa estricta **no excluyen ningún evento** (4.641/4.641 `resolved`); en cualquier otra capa se reporta su fracción como posible sesgo de supervivencia.

### Hallazgos rechazados

**Ninguno.** Tres correcciones se aplican con **ajuste declarado**, no con rechazo: R0.H4 (`fidelity`/`source_window` como segmentos y no como filtros, para no repetir el defecto de U5), R2.H1 (se aplica la fórmula `D − 2 − ceil(lead/24)` y no su ejemplo «D−3 a 36 h», que la contradice) y R2.H2 (se adopta el corte as-of por mes y no el `tau*` por evento, que se difiere a V2 por enmienda).

### Contenido nuevo no exigido por ningún hallazgo (introducido por el autor y sujeto a refutación)

1. **DV-1 (§3.1)**: el mapeo CDF→banda legado de 2D está **REFUTADO** para HKO (bandas `[N, N+1)`) por la evidencia de `SETTLEMENT_OPERATORS_SPEC` v2 (floor 164/166; 81/81 vs 4/81 en discriminantes). Se decide ahora excluir HKO del universo de **señales** (1.023 mk / 93 ev), manteniéndolo en el universo de **label**, y se declara que la incorporación de R12 (enmienda V-2.1) **invertirá** el universo de señales.
2. **§1.4**: composición mensual del universo y sus cuatro consecuencias declaradas a priori (concentración del 84,6 % en agosto; 3 estaciones en jun/jul, todas `in_modelsel`; septiembre marginal; E6 al límite).
3. **§1.5**: cuantificación del desfase de W(m) por estación y de la fracción de ventana transcurrida en T, con NZWN en el borde exacto (`fin = 0 h`) y **0 % transcurrido en las 55 estaciones al lead de veredicto**.
4. **E8 (§7.1)**: test de universo — el motor debe reproducir exactamente los recuentos congelados o el run es NOT_EVALUABLE.
5. **§10.2**: `DECISIONS.sha256` desactualizado por segunda vez y **`D21` duplicado**, ambos precondición del congelado.
6. **Anexo D**: enumeración cerrada de `stage` y `reason`, con parada del run ante cualquier exclusión fuera del enum.

---

*Fin del documento v2. Para congelar: resolver §10.2 (regenerar `DECISIONS.sha256`, desambiguar D21, corregir D18), tramitar la enmienda de §10.3 punto 7 (E7 + `quantiles_available_at` + nombre del `dataset_version`), `shasum -a 256 PREREG_BACKTEST_STRATEGY_A.md > PREREG_BACKTEST_STRATEGY_A.sha256`, commit por PR con revisión adversarial, y registro del hash en DECISIONS.md. Sólo después: R19.*