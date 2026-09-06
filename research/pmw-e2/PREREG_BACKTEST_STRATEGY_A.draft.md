# PREREG_BACKTEST_STRATEGY_A.md

> **Preregistro del backtest de Strategy A V1 — versión 1.0 (borrador para congelar).**
> Fecha de redacción: 2026-09-06. Baseline de código: `origin/main` = `dfdc73e` (worktree `/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-main`).
> Este documento se congela y se hashea (`PREREG_BACKTEST_STRATEGY_A.sha256`) **antes** de implementar el motor de backtest (ROADMAP R19) y **antes** de cualquier ejecución que produzca métricas (R21). Cualquier cambio posterior es una **enmienda numerada** (§10.3), nunca una edición in situ.
>
> Leyenda de trazabilidad usada en todo el documento:
> - **[OBS]** hecho observado en código o documentos congelados (ruta:líneas).
> - **[INF]** inferencia a partir de hechos observados; no verificada directamente.
> - **[DEC]** decisión que este preregistro fija (con justificación). Una vez congelado el documento, deja de ser "abierta".

---

## 0. Pregunta única y qué NO decide

### 0.1 Pregunta única (H0/H1)

> **¿Genera Strategy A V1 — señales BUY/FADE sobre `edge_gross = p_weather − p_market`, con `p_weather` derivado del forecast as-of de M1 = `icon_seamless` (2D LOCKED) y un umbral `tau` seleccionado exclusivamente fuera de muestra — un PnL neto bajo H1 (`pnl_net_H1`) acumulado positivo, con IC95 bootstrap que excluya 0 y signo estable bajo leave-one-station-out, en el catálogo real del periodo as-of estricto (target_date ≥ 2026-06-03), al lead de veredicto de 24 h, con ejecución hipotética a precio INDICATIVE, `x_exec = 0`, `hold_to_resolution` y tamaño fijo de 1 share?**

- H0: `pnl_net_H1` acumulado OOS ≤ 0 (o IC95 incluye 0).
- H1: `pnl_net_H1` acumulado OOS > 0 con IC95 que excluye 0 y signo estable LOSO.

### 0.2 Qué NO decide este backtest [DEC]

1. **No decide sizing.** Tamaño fijo 1 share; Kelly/fixed_fraction (config.py:202-212, sin consumidor [OBS]) quedan para R20 con su propio preregistro.
2. **No revisa M1.** `icon_seamless` es ADOPTADO (D12, `/Users/mariaaleu/pmw-e2/DECISIONS.md:190-210` [OBS]); la segmentación por componente ICON y región (§6.3) es descriptiva y de vigilancia (ASIA_SUR/HEM_SUR), nunca un criterio de conmutación de modelo.
3. **No decide la semántica real de fees.** H1 es hipótesis (D19; `FEES_SEMANTICS.md:27-57` [OBS]); H2/H3 son sensibilidad. El test de falsación forward con el primer fill real (FEES_SEMANTICS §7) es independiente.
4. **No estima `x_exec`.** `x_exec = 0` es supuesto declarado; 0.5·tick y 1 pt son estrés, no estimaciones (R22).
5. **No evalúa la época `fees_disabled` ni la sub-época CLOB V1.** Ambas caen íntegramente fuera del periodo con `available_at` PARTIAL (§1.3) [INF sobre cruce FEES_SEMANTICS.md:61-66 × F3-CLOSURE-REPORT.md:57-59].
6. **No autoriza dinero real ni órdenes** (D0, `DECISIONS.md:12-17` [OBS]).
7. **No valida el ancla temporal 2E ni la cota `L_max`**: los hereda tal cual (§2).
8. **No decide el lead operativo por defecto** de Strategy A más allá de reportar 9 h y 24 h; el lead de veredicto (24 h) es una elección metodológica de este preregistro (§2.1), no una recomendación operativa.
9. **No es una comparación entre modelos meteorológicos** (eso fue MODELSEL V5).

---

## 1. Universo y periodo

### 1.1 Mercados elegibles (regla fail-closed) [DEC]

Un mercado `m` (par `market_id`, `token_id` YES) entra en el universo del backtest **si y sólo si** cumple TODAS las condiciones siguientes en el `dataset_version` fijado (§2.6):

| # | Condición | Fuente / mecanismo |
|---|-----------|--------------------|
| U1 | Pertenece a un evento de temperatura máxima diaria sobre una de las **55 estaciones canónicas** (§1.4). | D1-COORD v1.3 [OBS] |
| U2 | Tiene **label** producido por R14 (`labeling.build_label`, `labeling.py:31-63` [OBS]) con `winning_outcome` no nulo y `resolution_timestamp` no nulo. | R14 |
| U3 | El label lleva `label_source = IEM_METAR`, `contract_source ∈ {WU, NOAA, HKO}` y `compat_status = COMPATIBLE` según la auditoría E2 (54/57 compatibles; HKO floor `[N, N+1)` STRONGLY SUPPORTED; `DECISIONS.md:354-358` [OBS]). **Mercados sin operador de settlement auditado quedan fuera** (fail-closed, D17). CWA/Taipei (77 mercados, fuente inaccesible [OBS]) queda fuera por esta regla. Hong Kong (HKO, 1 859 mercados [OBS]) entra **únicamente** si R14 emite `compat_status = COMPATIBLE` para su operador; si R14 lo marca UNKNOWN/INCOMPATIBLE, se excluye. No hay decisión manual: la regla es la salida de R14. |
| U4 | `markets.fee_status = 'KNOWN'` y `fee_regime ∈ {fees_disabled, weather_fees}` leídos **por mercado** desde Gamma (`polymarket/fees.py:48-104` [OBS]); nunca inferido por fecha. `fee_status ≠ KNOWN` → excluido de métricas netas (contado en `exclusions`, stage=`fees`). |
| U5 | `markets.measurement_rule` no nulo (columna añadida por migración `database.py:522`, poblada por `discovery.py:184` [OBS]). |
| U6 | `umaResolutionStatus` presente y estado no `proposed` (47 `proposed` y 33 sin estado quedan fuera [OBS]). |
| U7 | `endDate` presente y `endDate = target_date 12:00:00Z` (cumplido 8 557/8 557 en CATALOG_V2.ev [OBS]); cualquier `endDate` distinto de 12:00Z → excluido, stage=`anchor`. |
| U8 | El evento al que pertenece tiene **partición válida de bandas** según 2D §G (Σ p_weather ≈ 1); si no, el evento entero va a `markets_excluded` y sus bandas quedan NONE (2D LOCKED [OBS]). |

Toda exclusión se registra con `(market_id, event_id, lead_hours, stage, reason)` en el artefacto `exclusions.csv` (§9). **Nunca se imputa ni se desplaza T para rescatar un mercado** (2E §5, `PHASE_2E_LEAD_HOURS_ANCHOR.md:99-102` [OBS]).

### 1.2 Unidad de análisis [DEC]

- **Unidad de predicción**: banda (fila de `features`/`predictions`).
- **Unidad de señal/trade**: fila de `signals` con `signal ∈ {BUY, FADE}` (HOLD no genera trade).
- **Unidad de bootstrap**: bloque **estación-mes** (§6.4).
- **Unidad de conteo de cobertura**: evento (`event_id`) por lead.

### 1.3 Periodo: dos capas [DEC]

**Capa ESTRICTA (única que soporta el veredicto):**
`target_date ∈ [2026-06-03, D_fin]`, donde `D_fin` = último `target_date` con `resolution_timestamp` no nulo en el `dataset_version` fijado y `≤ 2026-09-04` (último `endDate` de la época `weather_fees` en el catálogo, `FEES_SEMANTICS.md:59-68` [OBS]). Justificación: F-3 declara la disponibilidad de forecasts PARTIAL sólo desde 2026-06-03 (`F3-CLOSURE-REPORT.md:57-59` [OBS]); el benchmark V2 fijó exactamente este rango con fail-closed fuera (`PREREG_MODELSEL_ASOF_V2.md:43-45` [OBS]); R15/D9-bis fijan el backfill a ≥ 2026-06-03 (`DECISIONS.md:252-255` [OBS]). Por construcción, esta capa cubre **sólo la sub-época CLOB V2 con `weather_fees`** [INF].

**Capa EXTENDIDA (sólo sensibilidad, etiqueta obligatoria `NOT_ASOF`):**
`target_date ∈ [2026-04-02, 2026-06-02]` (disponibilidad UNKNOWN [OBS]). Se ejecuta con el mismo código, el mismo `tau` seleccionado en la capa estricta (sin reselección) y las mismas tolerancias, **únicamente si** `weather_forecasts` contiene filas M1 con `available_at` poblado para ese rango bajo la misma regla `issue_time + L_max`. Si no hay datos, el informe registra la fila `EXTENDED = NOT_AVAILABLE`. Ningún criterio de éxito/fracaso (§7) lee esta capa. Las épocas `fees_disabled` (endDate ≤ 2026-03-30) y CLOB V1 (< 2026-04-28) quedan fuera de ambas capas y se declaran **NO EVALUABLES** en este preregistro.

**Meses de la capa estricta**: `2026-06`, `2026-07`, `2026-08`, `2026-09` (parcial, 09-01..D_fin). Huecos de catálogo conocidos (`FEES_SEMANTICS.md:142-144` [OBS]) no afectan a esta ventana, pero el informe reporta `n_mercados` y `n_días efectivos` por mes y segmento.

### 1.4 Estaciones y coordenadas [DEC]

- 55 estaciones canónicas, coordenadas del snapshot **D1-COORD v1.3** (`STATION_COORDS_SNAPSHOT_v1.3.sha256`; 55/55 canónicas, 12/55 verificadas por documentación oficial, 43 por inferencia declarada, OPKC resuelta D14/D15, 0 excepciones abiertas; `DECISIONS.md:19-39, 262-320` [OBS]).
- El hash de ese snapshot se copia en el manifiesto del run (§9). Si la estación no está en el snapshot → excluida, stage=`station`.
- `target_date` por estación se obtiene del helper de R8 (`target_date_for`, ROADMAP.md:116-121 [OBS]) por día civil local de estación. Si el helper no define `target_date` para una estación (caso abierto Wellington: endDate 12:00Z = medianoche civil local, 2E :135-137 [OBS]), la estación queda **excluida fail-closed**, stage=`target_date`, y se reporta.
- Región y componente ICON (`icon_d2` / `icon_eu` / `icon_global`; 10,7 % / 14,2 % / 75,1 % de mercados [OBS]) se asignan por estación con las mismas etiquetas que `PREREG_MODELSEL_V5.md` (partición regional incl. ASIA_SUR y HEM_SUR).

---

## 2. Datos y as-of

### 2.1 Instante de decisión T y leads [DEC, hereda 2E]

```
T = endDate − lead_hours · 3600        (PHASE_2E_LEAD_HOURS_ANCHOR.md:10-14 [OBS], RATIFIED 2026-09-04)
```

- `endDate` = cierre programado del mercado (12:00:00Z del `target_date`). Prohibido anclar en `target_start/midpoint/end`, `expected_max_time`, `daily_high_time`, `last_meaningful_market_time`, `closedTime`, o redefinir `lead_hours` como `issue_time − target_date` (2E :29-33 [OBS]).
- **Leads primarios**: `{9 h, 24 h}` (`PREREG_LEAD_HOURS_RANGE.md` §3-§4, sha `1d4161e8…` [OBS]).
- **Lead de veredicto**: **24 h**. Justificación: la evidencia MODELSEL a favor de M1 es concluyente a 24 h (icon_eu) y a 9 h con runs iguales queda INCONCLUSO (Δ = −0.060; `MODELSEL_V5_CORRECTION_01.md:88-98` [OBS]). Designar un único lead de veredicto evita la multiplicidad entre leads. El lead 9 h se evalúa con idéntica metodología y recibe su propio veredicto etiquetado `LEAD_9H`, que **no** entra en el veredicto de fase.
- **Leads secundarios**: `{36 h, 48 h}`, sólo sensibilidad, con exclusión fail-closed del evento inexistente en T (`createdAt > T`) y reporte obligatorio de la fracción excluida (esperada ~19–21 % [OBS]). No entran en la selección de `tau` ni en el veredicto. Leads > 48 h: no se ejecutan.
- **Existencia del evento en T**: `createdAt ≤ T` es condición para todos los leads (99,3 % a 9 h, 98,2 % a 24 h [OBS]); si no, exclusión stage=`existence`.
- **Coincidencia de run** (regla V2 §4, `PREREG_MODELSEL_ASOF_V2.md:39-41` [OBS]): si para un evento los leads 9 h y 24 h seleccionan el mismo run de M1, se reporta la fracción de coincidencia. No se construye ningún agregado que mezcle leads; cada lead se reporta por separado.
- **Guarda anti-fuga del instante de decisión** (2E §4.3, :85-89 [OBS]): R19 debe incluir un test que verifique que `T` se deriva únicamente de `endDate` (metadato conocible en la creación) y que la función `prediction_time_for` no recibe ni lee `resolution_timestamp`, `closedTime`, `daily_high_time` ni `last_meaningful_market_time`. Sin ese test en verde, el motor no está TESTED.

### 2.2 Forecast as-of [DEC, hereda V2/F-3]

- Modelo: **M1 = `icon_seamless`** (D12 [OBS]; `weather.py` de `feat/ingest-2b` fija `M1_MODEL` y `L_MAX_HOURS = {icon_seamless: 4.76, ecmwf_ifs025: 8.78}` [OBS]).
- `available_at = issue_time + L_max(icon_seamless) = issue_time + 4.76 h`; L_max = máximo observado en F-3 (n = 307 pasadas), **no** mediana (`PREREG_MODELSEL_ASOF_V2.md:15-33` [OBS]).
- Selección: `latest_asof(weather_forecasts, time_col='available_at', asof=T, partition=(station, model, target_date))` (`features.py:97-105` [OBS]). `issue_time ≤ T` **nunca** es criterio suficiente.
- Ausencia de forecast con `available_at ≤ T` → banda NONE y evento excluido para ese lead, stage=`forecast`. No se imputa.
- **Limitación declarada** (obligatoria en el informe): la cota `L_max` es empírica, no garantizada; la cola no está caracterizada; `created_at ≠ fin de escrituras` (hasta 93,7 min); la API sólo expone la última pasada (`F3-CLOSURE-REPORT.md:10-13, 22-32, 37-38` [OBS]).

### 2.3 Precio as-of [DEC, hereda 2C]

- `p_market = latest_asof(price_history, time_col='observation_time', asof=T, partition=token_id YES, where market_id)` (`features.py:74-82` [OBS]); `price_layer = INDICATIVE` obligatorio; EXECUTABLE → `ValueError` → exclusión `executable_or_invalid_price` (`strategy_a.py:191-194` [OBS]).
- **Frescura mínima de la cotización**: se exige `observation_time ∈ (T − 6 h, T]`. Si la última cotización es más antigua, el mercado se excluye para ese lead, stage=`pricing`, reason=`stale_quote`. [DEC; justificación: ninguna sonda P3 de 2E ha verificado la disponibilidad real de cotización en T (2E :104-112 [OBS]); una ventana de 6 h es menor que el lead primario más corto (9 h), de modo que el precio pertenece inequívocamente al mismo "estado de información" que el forecast seleccionado. Es un parámetro de cobertura, no de estrategia; se reporta la fracción excluida por él.]
- Sin cotización → exclusión stage=`pricing`, reason=`no_quote`. Nunca se desplaza T (2E :99-102 [OBS]).
- **Puerta de cobertura**: si en el lead de veredicto la fracción de eventos elegibles (U1–U8) excluidos por `existence + forecast + pricing` supera **30 %**, el lead se etiqueta `COVERAGE_INSUFFICIENT` y el veredicto de fase es NOT_EVALUABLE (§7.3). [DEC; justificación: la exclusión estructural conocida a 24 h es 1,8 % por existencia [OBS]; 30 % deja margen para la incógnita P3 sin aceptar un universo que ya no representa el catálogo. Es una puerta a priori, no un criterio de éxito.]

### 2.4 Label [DEC, hereda D17]

- `label = 1` si `winning_outcome` es el `token_id` YES de la banda; `0` en caso contrario; construido exclusivamente vía `labeling.build_label` con `prediction_time < resolution_timestamp` estricto (`labeling.py:31-63` [OBS]; única vía LOCKED, 2D §N [OBS]).
- Es **Y_final retrospectivo** (D17 = A + C, `DECISIONS.md:340-362` [OBS]).
- **Limitación D17 obligatoria en cada tabla del informe**: "evaluation label available retrospectively after settlement; revisiones NEGLIGIBLE demostrado sólo para IEM/METAR en 578 station-days (23/53 estaciones, 20 días; 0/578 cambian bracket; cota sup. 95 % = 0,519 %); UNKNOWN para Wunderground (85,6 % del catálogo), HKO y CWA" (`REVISION_IMPACT_AUDIT.md:24-31, 87-102` [OBS]). Y_final **no** se usa como feature ni como observación de entrenamiento as-of.
- Ningún campo de `FORBIDDEN_FEATURE_FIELDS = {winning_outcome, resolution_timestamp, settlement_timestamp, is_winner}` puede aparecer en features, predictions o signals (`features.py:20-27, 199-213`; `tests/test_strategy_a.py:265-269` [OBS]). El JOIN con labels ocurre **sólo** en el motor de backtest, después de generar señales, por `(market_id, token_id, dataset_version)`.

### 2.5 Features persistidas [DEC, depende de R17]

- El motor lee `features` persistidas con `no_lookahead_verified = TRUE` (sólo lo escribe el builder tras las guardas; `features.py:215` [OBS]). Filas con `FALSE` o NULL → excluidas, stage=`features`.
- `feature_json` no puede contener claves prohibidas (test `test_resolution_not_in_features.py:79-106` [OBS]).

### 2.6 `dataset_version`, `model_version`, `code_version` [DEC]

- **Exactamente un** `dataset_version` para todo el run, elegido como la última versión registrada en `dataset_versions` en el momento de arranque de R21 y escrito en el manifiesto **antes** de calcular métrica alguna. No se mezclan versiones. Si durante el run aparece una versión nueva, no se usa.
- `model_version` = identificador del run de M2 (cuantiles p10..p90, R16) + `"|p_weather_2D_v1"`.
- `code_version` = commit SHA del motor (R19) sobre el que se ejecuta; debe ser un commit de una rama fusionada por PR (D16 [OBS]).
- `backtest_results.parameters` incluye obligatoriamente `prereg_sha256` (hash de este documento) porque el schema no tiene columna dedicada (`database.py:465-482` [OBS]; deuda ROADMAP :241 [OBS]).

---

## 3. Modelo de probabilidad

### 3.1 `p_weather` tal como está (2D LOCKED) [DEC]

- `p_weather(banda) = band_probability(quantiles_to_distribution(p10..p90), lo, hi)` con el forecast as-of de §2.2; Σ_bandas = 1 sobre partición válida (2D §G, `PHASE_2D_STRATEGY_A_DESIGN.md:84-95` origin/main [OBS]).
- **Se usa `p_weather` sin `SettlementOperator` (R12)** aunque R12 llegue antes de R21. Justificación: (a) `p_weather` es LOCKED en 2D y sus tests (§R) validan esa definición; (b) adoptar R12 invalidaría el LOCKED y exigiría re-testar 2D (segundo informe, decisiones abiertas [OBS]); (c) el sesgo de operador (p.ej. HKO floor vs. entero WU) queda parcialmente absorbido por la segmentación por template (§6.3) y por U3, que ya filtra operadores no auditados. Si R12 se fusiona antes de R21, su incorporación es una **enmienda V-1.1** (§10.3) con nuevo hash, nunca un cambio silencioso.
- Cuantiles: proceden de M2 (R16, `weather_errors`), aún sin preregistro ni escritor [OBS]. **Requisito heredado**: los cuantiles usados en T para el evento `e` (estación s, target_date D) deben calcularse sólo con errores de eventos con `target_date ≤ D − 2` (walk-forward; garantiza que Y_final histórico ya estaba disponible en T, latencia de settlement ~1,3 h; `PREREG_MODELSEL_ASOF_V2.md:69-78` [OBS]). Si PREREG_M2 no garantiza esta condición (cuantiles de muestra completa), el run se etiqueta `NOT_ASOF_QUANTILES` y **no puede** producir VALIDATED: sólo EXPLORATORY (§7.3).

### 3.2 Desbiasing: V2/V3, no en este run [DEC]

- V1 (este preregistro): sin desbiasing adicional al que M2 incorpore.
- V2 (preregistrada aquí para no reinventarla): `historia(e)` = eventos de la misma estación y modelo con `target_date ≤ D − 2`; `|historia| < 10` → banda NO EVALUABLE sin imputación; `bias_hat = media(f − Y_final)`; forecast corregido `f − bias_hat` (`PREREG_MODELSEL_V5.md:140-161` [OBS]). Prohibido estimar el sesgo con toda la muestra y evaluar sobre ella. V2 se ejecuta sólo tras una enmienda que fije su propio criterio; sus resultados no alteran el veredicto V1.

### 3.3 Referencia de mercado [DEC]

- Se reportan Brier y log-loss de `p_market` frente al label con la misma muestra que `p_weather`, como línea base descriptiva. No es criterio de veredicto.

---

## 4. Strategy A: edge, umbral y tolerancias

### 4.1 Definiciones (DECIDED-V1 de 2D, sin cambios) [OBS]

```
p_model    = p_weather                       (W.1; strategy_a.py:243)
fair_value = p_model                         (W.2; strategy_a.py:244)
edge_gross = fair_value − p_market           (W.3; strategy_a.py:245)
signal     = BUY  si edge_gross ≥ +tau
           = FADE si edge_gross ≤ −tau
           = HOLD si |edge_gross| < tau      (signal_for, strategy_a.py:78-84)
```
`SELL` nunca se emite; `NONE` no se emite en V1 (W.11, opción A [OBS]).

Interpretación de trade [DEC]: BUY = compra de 1 share YES a `p_market`; FADE = compra de 1 share NO a `1 − p_market` (equivalente a short YES). Se asume complementariedad INDICATIVE `p_NO = 1 − p_YES` (supuesto declarado; `price_history` se lee sólo para el token YES, `strategy_a.py:204-218` [OBS]).

### 4.2 Rejilla preregistrada de `tau` [DEC]

```
TAU_GRID = {0.01, 0.02, 0.03, 0.05, 0.08}     (puntos de probabilidad)
```
Justificación: cubre desde el orden del coste máximo H1 en p = 0.5 (0.0125) hasta 8 pt; incluye el fixture 0.05 de tests (`tests/test_strategy_a.py:51` [OBS]) sólo como punto de la rejilla, no como valor por defecto. `min_edge_grid` de `config.py:207` **no** es autoritativo ni se lee (vestigio sin consumidor [OBS]); este preregistro es la única fuente de la rejilla.

### 4.3 Regla de selección OUT-OF-SAMPLE (walk-forward mensual, expanding) [DEC]

Para cada lead `ℓ ∈ {9, 24}` y capa estricta:

| Mes de test | Ventana de calibración (expanding) |
|-------------|------------------------------------|
| 2026-07 | 2026-06 |
| 2026-08 | 2026-06 + 2026-07 |
| 2026-09 (parcial) | 2026-06 + 2026-07 + 2026-08 |

- Junio 2026 **nunca** es mes de test (es calibración pura).
- `tau*(ℓ, mes_test)` = el `tau ∈ TAU_GRID` que **maximiza `pnl_net_H1` acumulado** en la ventana de calibración, sujeto a `n_trades_calibración(tau) ≥ 30`. Empate → el `tau` mayor (más conservador). Si ningún `tau` alcanza 30 trades → el mes de test se etiqueta `NO_CALIBRATION` y no aporta trades OOS.
- La selección es **pooled** sobre templates y estaciones dentro del lead (política de segmentación §6.3: "pooled para seleccionar, segmentado para reportar"). Justificación: por template, HKO es 1 estación y NOAA una minoría; una selección por template quedaría por debajo de `n ≥ 30` en la mayoría de meses. La selección por template es variante V2 (enmienda).
- El conjunto OOS = unión de los trades de todos los meses de test con su `tau*` respectivo. **Ninguna métrica del veredicto se calcula in-sample**. La tabla completa `pnl_net_H1(tau, mes)` para todos los `tau` se publica como transparencia, etiquetada IN-SAMPLE, sin entrar en el veredicto.
- El `tau` adoptado para operación futura (DECISIONS.md, ROADMAP R21 [OBS]) será `tau*(24 h, último mes con calibración válida)`; su adopción es un acto separado del veredicto.

### 4.4 Tolerancias (obligatorias, sin default, fail-closed; `strategy_a.py:109-123` [OBS]) [DEC]

| Parámetro | Valor primario | Sensibilidad (una sola variante, sin selección) |
|-----------|----------------|--------------------------------------------------|
| `weather_sum_tolerance` | `1e-6` | — (Σ p_weather es aritmética sobre una partición; sólo absorbe error de coma flotante) |
| `market_sum_min` | `0.80` | `0.90` |
| `market_sum_max` | `1.30` | `1.15` |

Justificación [INF]: Σ p_market YES sobre las bandas de un evento refleja overround; una suma < 0.80 o > 1.30 indica al menos una banda sin cotización fresca o con precio degenerado, y el precio INDICATIVE del evento no es fiable. Los valores de tests (`0.0 / 5.0`) son fixtures permisivos [OBS], no se usan. La variante de sensibilidad se ejecuta con el mismo `tau*` (no se reselecciona) y reporta el cambio en `n_trades` y `pnl_net_H1`; no entra en el veredicto.

### 4.5 Segmentación epoch/template en señales [DEC]

2D §M afirma que "cada fila de señal registra ambos", pero `predictions`/`signals` no tienen columnas de epoch ni template y `strategy_a.py` no las escribe (discrepancia doc-código [INF, segundo informe]). Resolución en este preregistro: el motor reconstruye `fee_regime` y `measurement_rule` por JOIN con `markets` sobre `(market_id, dataset_version)`; **no se modifica el schema** (respeta "V1 no modifica schema"). El informe declara esta discrepancia.

---

## 5. Coste, ejecución y sizing

### 5.1 Modelo de coste (D19, FEES_SEMANTICS §2) [OBS, adoptado]

```
H1 (primaria):      c_taker(p) = 0.05 · p · (1 − p)      USDC/share
H2 (sensibilidad):  c(p)       = 0.10 · min(p, 1 − p)
H3 (sensibilidad):  c(p)       = 0.10 · p · (1 − p)      (= 2·H1)
fees_disabled → c = 0 (no aplica en capa estricta)
fee_status ≠ KNOWN o exponent ≠ 1 → edge_net = None (fail-closed; trade contado, excluido de métricas netas)
fee = round5(1 · c(p)); fees < 0.000005 redondean a 0
```
`p` = precio del share comprado (`p_market` para BUY, `1 − p_market` para FADE); H1/H2/H3 son simétricas en `p ↔ 1−p`.

### 5.2 Ejecución [DEC, hereda FEES_SEMANTICS §6]

- `exit_mode = hold_to_resolution`: salida a 0/1 por redención; `exit_cost = 0` (supuesto declarado: redención sin fee, no verificado [OBS]).
- `x_exec = 0` primario. Estrés: `x_exec = 0.5·tick` y `x_exec = 0.01` (1 pt), aplicados **en contra** al precio de entrada (`p_entrada = p + x_exec`). `tick` se lee **por mercado** (`orderPriceMinTickSize`: 0.001 mayoritario, 0.01 en 411 mercados [OBS]); nunca default.
- Rebate maker = 0; taker rebate = 0; builder fee = 0.
- No hay modelo de spread/slippage (R22 pendiente); el fill es hipotético a precio INDICATIVE. Cada `paper_trades` lleva `price_layer = 'INDICATIVE'`.

### 5.3 PnL por trade (size = 1 share) [DEC]

```
BUY : pnl_gross = label − p_entrada ;            pnl_net_Hk = pnl_gross − c_k(p_entrada)
FADE: pnl_gross = (1 − label) − (1 − p_entrada); pnl_net_Hk = pnl_gross − c_k(1 − p_entrada)
edge_net_H1 = edge_gross − sign(signal)·c_1(p_share)   (predictions.edge_net y signals.net_edge se rellenan con H1 sólo en las filas producidas por el motor de backtest; las filas de Strategy A V1 siguen NULL)
```

### 5.4 Sizing [DEC]

- **1 share por señal**, sin Kelly, sin fixed_fraction, sin bankroll. `paper_trades.size = 1`, `bankroll_after = NULL`. Sizing fraccional es R20 con preregistro propio.

---

## 6. Métricas

### 6.1 Primarias (entran en el veredicto)

| Métrica | Definición | Muestra |
|---------|-----------|---------|
| `pnl_net_H1_total` | Σ pnl_net_H1 sobre trades OOS | Lead 24 h, capa estricta, meses de test con calibración válida |
| `IC95(pnl_net_H1_total)` | bootstrap por bloques (§6.4), percentiles 2.5/97.5 | ídem |
| `LOSO_sign_stability` | fracción de réplicas leave-one-station-out (una por estación presente en OOS) con `pnl_net_H1_total > 0` | ídem |

### 6.2 Secundarias (reportadas, no deciden)

- `pnl_net_H1_per_trade` (media), `pnl_gross_total`, `pnl_net_H2_total`, `pnl_net_H3_total`, `pnl_net_H1` bajo estrés `x_exec ∈ {0.5·tick, 1 pt}`.
- `hit_rate` = fracción de trades con `pnl_gross > 0`.
- `n_signals` (BUY, FADE, HOLD), `n_trades`, `n_events`, `n_markets`, `n_días efectivos`.
- `brier(p_weather)`, `logloss(p_weather)` (clip `p ∈ [1e-6, 1−1e-6]`), y los mismos para `p_market`, calculados sobre **todas** las bandas con feature válida (no sólo señales).
- Curva PnL acumulado por fecha de resolución.
- Fracciones de exclusión por stage (§1.1, §2.1-2.3) y fracción de coincidencia de run entre leads.
- Misma batería para lead 9 h (veredicto `LEAD_9H`), leads 36/48 h (sensibilidad) y capa extendida (`NOT_ASOF`).

### 6.3 Segmentación obligatoria de toda métrica secundaria [DEC, hereda 2D §M LOCKED]

Todas las métricas se reportan pooled y por cada uno de: (a) epoch de fees (`fee_regime`; en capa estricta sólo `weather_fees`, fila `fees_disabled` con `n = 0` declarada), (b) sub-época CLOB (V2 únicamente en capa estricta; declarado), (c) template de settlement (`contract_source` ∈ WU/NOAA/HKO) y `measurement_rule`, (d) lead, (e) componente ICON (`icon_d2`/`icon_eu`/`icon_global`), (f) región (etiquetas MODELSEL V5; ASIA_SUR y HEM_SUR se destacan como vigilancia), (g) mes de test, (h) tipo de señal (BUY/FADE). Cada celda reporta `n_trades` y `n_días efectivos`; celdas con `n_trades < 10` se muestran pero marcadas `LOW_N` y sin IC.

### 6.4 Bootstrap [DEC]

- Bloques = **estación-mes** (`station_id`, mes del `target_date`).
- Remuestreo con reemplazo de bloques, **4 000** réplicas, semilla **20260906** (`numpy.random.default_rng(20260906)`), IC percentil 2.5/97.5.
- `backtest_results.random_seed = 20260906`.
- LOSO: réplicas deterministas (sin aleatoriedad), una por estación con ≥ 1 trade OOS.

---

## 7. Criterios de éxito/fracaso (congelados)

### 7.1 Condiciones de evaluabilidad (todas necesarias)

- E1: capa estricta con ≥ 2 meses de test con calibración válida (`≠ NO_CALIBRATION`) en el lead 24 h.
- E2: puerta de cobertura §2.3 superada (exclusiones `existence + forecast + pricing` ≤ 30 % de eventos elegibles).
- E3: cuantiles M2 walk-forward (§3.1); en caso contrario `NOT_ASOF_QUANTILES`.
- E4: `dataset_version`, `code_version`, `prereg_sha256` únicos y registrados antes de la primera métrica.
- E5: todos los tests as-of de 2C/2D (`test_no_future_information.py`, `test_no_lookahead_adversarial.py`, `test_resolution_not_in_features.py`, `test_strategy_a.py`) más el test anti-fuga de T (§2.1) en verde sobre `code_version`.

Si falla alguna → veredicto **NOT_EVALUABLE** (con la condición fallida nombrada). No se reintenta con otros parámetros.

### 7.2 Veredicto (lead 24 h, capa estricta, OOS)

| Veredicto | Condición |
|-----------|-----------|
| **SUCCESS_ROBUST** | `IC95(pnl_net_H1_total)` enteramente > 0 **y** `LOSO_sign_stability = 1.0` **y** `pnl_net_H2_total > 0` con IC95 bootstrap que excluya 0 **y** estimación puntual `pnl_net_H1_total > 0` bajo estrés `x_exec = 1 pt`. |
| **SUCCESS_H1** | `IC95(pnl_net_H1_total)` enteramente > 0 **y** `LOSO_sign_stability = 1.0`, pero falla alguna condición adicional de ROBUST. |
| **FAILURE** | `IC95(pnl_net_H1_total)` enteramente < 0. |
| **INCONCLUSIVE** | Cualquier otro caso (IC95 incluye 0, o IC95 > 0 pero `LOSO_sign_stability < 1.0`). |

No hay umbrales adicionales de hit-rate, Brier o número mínimo de trades en el veredicto: el IC95 bootstrap y LOSO son los únicos árbitros (evita umbrales inventados). Brier(p_weather) vs Brier(p_market) se reporta como categoría interpretativa (§7.4), no como criterio.

### 7.3 Mapeo a estado de fase (PHASES.md / ROADMAP R21) [DEC]

- `SUCCESS_ROBUST` o `SUCCESS_H1` → Strategy A V1 puede marcarse **VALIDATED (backtest)** en PHASES.md sólo si el informe vive en `docs/validation/` con hash (PHASES.md:3-8, ROADMAP R21 [OBS]).
- `FAILURE` → VALIDATED = NO; Strategy A V1 queda **REFUTED_AS_SPECIFIED**; no se re-ejecuta con otra rejilla.
- `INCONCLUSIVE` o `NOT_EVALUABLE` → VALIDATED = NO; se declara explícitamente; sólo una enmienda (§10.3) autoriza otro run.
- Run con `NOT_ASOF_QUANTILES` → estado máximo **EXPLORATORY**, nunca VALIDATED.

### 7.4 Categorías de interpretación (descriptivas, obligatorias en el informe)

- **C1 Calibración**: `brier(p_weather) < brier(p_market)` (mejor que el mercado) / `≥` (no mejor).
- **C2 Origen del PnL**: concentración por template (¿> 80 % del PnL en un template?), por componente ICON, por región; ¿aparece PnL solo en icon_eu como predijo MODELSEL?
- **C3 Sensibilidad a fees**: signo de `pnl_net_H2` y `pnl_net_H3`.
- **C4 Sensibilidad a ejecución**: signo bajo `x_exec` de estrés.
- **C5 Consistencia entre leads**: coincidencia de signo 9 h vs 24 h.
- **C6 Vigilancia M1**: si ASIA_SUR o HEM_SUR muestran `pnl_net_H1 < 0` con IC95 que excluya 0, se registra como evidencia para M2/M3 (D12 "vigilancia"), **sin** cambiar M1 en este ciclo.

---

## 8. Prohibiciones

1. **No cambiar** `TAU_GRID`, tolerancias, ventanas walk-forward, métricas, semilla, bloques de bootstrap ni criterios de §7 después de ver cualquier resultado, ni siquiera parcial. Todo cambio es enmienda con hash nuevo y re-run completo etiquetado.
2. **No usar `Y_asof`**: no existe reconstrucción as-of de observaciones (`RECORD_VERSION_ASOF_AUDIT.md:83-98` [OBS]); el label es Y_final con la limitación D17 y jamás se presenta como observación as-of.
3. **No imputar** forecasts, precios, labels ni eventos inexistentes en T; **no desplazar T**.
4. **No usar** `issue_time ≤ T`, `ingestion_timestamp` ni tiempos físicos de observación como criterio de disponibilidad.
5. **No leer** `winning_outcome`, `resolution_timestamp`, `settlement_timestamp`, `is_winner` antes del JOIN de labels en el motor; **no** derivar T de `closedTime`, `daily_high_time` o `last_meaningful_market_time`.
6. **No sortear cuotas** de Open-Meteo ni 429; no consultar Open-Meteo desde el motor (sólo lee `weather_forecasts` persistidas); no contratar clave de pago sin decisión explícita del usuario (D9-bis [OBS]).
7. **No dinero real, no órdenes**, no `price_layer` EXECUTABLE (D0 [OBS]).
8. **No inferir `fee_regime` por fecha**; leer por mercado.
9. **No seleccionar `tau` in-sample** ni reportar como OOS ninguna cifra calculada sobre la ventana de calibración.
10. **No agregar** leads distintos en una misma métrica; **no** mezclar capa estricta y extendida.
11. **No mezclar `dataset_version`** dentro de un run; **no borrar** datos (sólo añadir/versionar).
12. **No push a main**; motor e informe entran por PR con revisión adversarial, pytest verde y ≥ 2 h de ventana de objeción (D16 [OBS]).
13. **No declarar VALIDATED** con evidencia que viva sólo en `results/` (ignorado por git).

---

## 9. Artefactos y hashes

| Artefacto | Ruta | Contenido | Hash |
|-----------|------|-----------|------|
| Este preregistro | `PREREG_BACKTEST_STRATEGY_A.md` + `.sha256` | congelado antes de R19 | `prereg_sha256`, registrado en DECISIONS.md (D-nueva) |
| Manifiesto del run | `docs/validation/backtest_a/RUN_MANIFEST.json` | `backtest_id`, `run_timestamp`, `dataset_version`, `model_version`, `code_version`, `prereg_sha256`, `station_snapshot_sha256` (v1.3), `decisions_sha256`, `fees_semantics_sha256` (4dbad3ab…), `lead_range_sha256` (1d4161e8…), `asof_v2_sha256` (2b815fcb…), `random_seed = 20260906`, `TAU_GRID`, tolerancias, ventanas | sha256 propio |
| Filas `backtest_results` | DuckDB, una fila por `(lead, capa, variante de sensibilidad)` | `parameters` JSON = §4-§5 + `prereg_sha256`; `metrics` JSON = §6; `walk_forward_config` JSON = §4.3; `train_window/test_window` como `YYYY-MM..YYYY-MM`; `random_seed`; `feature_list` | — |
| Filas `paper_trades` | DuckDB | un registro por trade con `backtest_id`, `entry_time = T`, `entry_price`, `exit_time = resolution_timestamp`, `exit_price ∈ {0,1}`, `fees` (H1), `slippage = x_exec`, `gross_pnl`, `net_pnl`, `size = 1`, `price_layer = INDICATIVE` | — |
| Tablas planas | `docs/validation/backtest_a/{signals_oos,metrics_by_segment,tau_selection_table,bootstrap_draws,loso,exclusions,costs_sensitivity,coverage}.csv` | como §4-§6; `costs_sensitivity` con `hipotesis_id ∈ {H1,H2,H3}` | `SHA256SUMS` |
| Informe | `docs/validation/PHASE_2F_STRATEGY_A_BACKTEST_REPORT.md` + `.sha256` | veredicto §7 explícito, tabla OOS, limitaciones §2.2/§2.4, discrepancia §4.5, categorías §7.4, `tau` adoptado | registrado en DECISIONS.md |
| Log de tests | `docs/validation/backtest_a/pytest_<code_version>.log` | salida completa de E5 | sha256 |

Todo artefacto de `docs/validation/` se commitea en la PR del run; `results/` puede contener copias pero no es evidencia.

---

## 10. Dependencias explícitas y enmiendas

### 10.1 Dependencias (estado al congelar) [OBS]

| Dep. | Qué aporta | Estado | Consecuencia si no está |
|------|-----------|--------|--------------------------|
| **R15** (`feat/ingest-2b`, no fusionada) | `weather_forecasts` M1 con `available_at = issue_time + 4.76 h` | rama sin fusionar | Sin datos: NOT_EVALUABLE (E2 falla). Debe fusionarse por PR antes de R21. |
| **R13/R14** (labels) | `label`, `label_source`, `contract_source`, `compat_status` | sin escritor en main | Sin labels: universo vacío (U2/U3). |
| **R16 / PREREG_M2** | cuantiles p10..p90 walk-forward | sin preregistro ni escritor | Sin cuantiles: `p_weather` no calculable. Cuantiles no walk-forward: `NOT_ASOF_QUANTILES` → máximo EXPLORATORY. |
| **R17** (features persistidas) | filas `features` con `no_lookahead_verified = TRUE` y `dataset_version` fijo | sin productor | Sin features: universo vacío (§2.5). |
| **R19** (motor) | iteración por `T = endDate − lead`, JOIN labels, coste H1/H2/H3, bootstrap, LOSO, escritura `backtest_results`/`paper_trades`, test anti-fuga de T | no existe (`backtest_results` sin productor [OBS]) | Sin motor: nada se ejecuta. El motor se implementa **después** del hash de este documento. |
| **R8 helpers** (`prediction_time_for`, `target_date_for`) | ancla 2E y target_date por estación | pendientes | Estaciones sin `target_date` definido: excluidas (§1.4). |
| **PHASE_2E_LEAD_HOURS_ANCHOR.md** | ancla T | untracked (`/private/tmp/pmw-publish`, sha `6e405d1a…`) | Debe commitearse antes de R19 para que §2.1 lo referencie por hash; hasta entonces, este preregistro cita el sha del borrador. |

### 10.2 Inconsistencias documentales que deben corregirse antes de referenciar por hash [OBS]

- ROADMAP.md:296 cita "D18" pero DECISIONS.md no contiene D18.
- `DECISIONS.sha256` (mtime 09:51) es anterior a la última edición de DECISIONS.md (12:05): regenerar.
- `MODELSEL_V5_REPORT.sha256` contiene dos hashes (6c3c2a66… y 9b4eb188…): el manifiesto (§9) citará el de la versión con aviso de corrección.

### 10.3 Procedimiento de enmienda (V-enmienda) [DEC]

Cualquiera de los siguientes cambios **obliga** a una nueva versión `PREREG_BACKTEST_STRATEGY_A.md v1.(k+1)` con sección "Changelog" explícita, nuevo `.sha256`, registro en DECISIONS.md, y re-run completo etiquetado con la nueva versión (los resultados de la versión anterior se conservan sin editar):

1. Cambio en R14 que altere la regla de labels, `compat_status` de cualquier operador o la fuente proxy.
2. Cambio en R17 que altere columnas de `features`, la definición de `no_lookahead_verified` o el `dataset_version` usado.
3. Cambio en R16/M2 que altere la definición de cuantiles o su condición walk-forward.
4. Cambio en R19 que altere la derivación de T, el modelo de coste, el bootstrap o los criterios; correcciones de bugs que **no** cambien definiciones se registran como `code_version` nuevo con diff citado, sin enmienda, siempre que ninguna métrica haya sido observada con el código defectuoso; si ya se observó, enmienda.
5. Incorporación de R12 (`SettlementOperator`), desbiasing V2, selección de `tau` por template, sizing fraccional, o cualquier lead/tau fuera de las rejillas.
6. Cambio de `L_max`, del ancla 2E, o del snapshot D1-COORD.

Las enmiendas **no** pueden motivarse por los resultados observados para mover el veredicto; el informe de la versión anterior mantiene su veredicto.

---

## Anexo A. Parámetros congelados (resumen máquina-legible)

```json
{
  "prereg_version": "1.0",
  "baseline_commit": "dfdc73e",
  "model_M1": "icon_seamless",
  "L_max_hours": 4.76,
  "anchor": "T = endDate - lead_hours*3600",
  "leads_primary_hours": [9, 24],
  "lead_verdict_hours": 24,
  "leads_secondary_hours": [36, 48],
  "period_strict": ["2026-06-03", "D_fin<=2026-09-04"],
  "period_extended_not_asof": ["2026-04-02", "2026-06-02"],
  "stations": 55,
  "station_snapshot": "D1-COORD v1.3",
  "price_layer": "INDICATIVE",
  "quote_max_age_hours": 6,
  "coverage_gate_max_excluded_fraction": 0.30,
  "tau_grid": [0.01, 0.02, 0.03, 0.05, 0.08],
  "tau_selection": "walk-forward monthly expanding; maximize pnl_net_H1 in calibration; n_trades>=30; tie->larger tau; pooled by lead",
  "test_months": ["2026-07", "2026-08", "2026-09"],
  "weather_sum_tolerance": 1e-6,
  "market_sum_min": 0.80,
  "market_sum_max": 1.30,
  "market_sum_sensitivity": [0.90, 1.15],
  "cost_primary": "H1: 0.05*p*(1-p)",
  "cost_sensitivity": ["H2: 0.10*min(p,1-p)", "H3: 0.10*p*(1-p)"],
  "exit_mode": "hold_to_resolution",
  "x_exec_primary": 0.0,
  "x_exec_stress": ["0.5*tick", 0.01],
  "size_per_signal_shares": 1,
  "bootstrap_block": "station-month",
  "bootstrap_reps": 4000,
  "random_seed": 20260906,
  "verdict_metric": "pnl_net_H1_total OOS, IC95 bootstrap excluding 0, LOSO sign stability == 1.0"
}
```

## Anexo B. Referencias con línea (baseline `origin/main` = `dfdc73e` salvo indicación)

- `src/weather_agent/strategy/strategy_a.py`: firma y `_require` :87-117; validaciones :118-123; `signal_for` :78-84; W.1-W.3 :243-245; `edge_net`/`net_edge` NULL :252, :266; linaje de precio :204-218.
- `src/weather_agent/features.py`: `FORBIDDEN_FEATURE_FIELDS` :20-27; precio as-of :74-82; EXECUTABLE :90-91; forecast as-of :97-105; guardas :199-215.
- `src/weather_agent/labeling.py:31-63`.
- `src/weather_agent/database.py`: `AS_OF_COLUMNS` :79-93; `features` :364-384; `predictions` :389-407; `signals` :412-431; `paper_trades` :436-460; `backtest_results` :465-482; migración `measurement_rule` :522; `query_asof/latest_asof` :803-865.
- `src/weather_agent/polymarket/fees.py:14-28, 48-104`; `src/weather_agent/config.py:202-212` (DEFAULTS sin consumidor).
- `PHASE_2D_STRATEGY_A_DESIGN.md` (origin/main): §C :53-58; §G :84-106; §I :116-124; §M :156-161; §N :163-168; §T :208-218; W.1-W.4 :246-262; W.10 :322-333; W.12 :344-350; W.13 :352-360; tabla OPEN :395-398.
- `/private/tmp/pmw-publish/PHASE_2E_LEAD_HOURS_ANCHOR.md` (sha `6e405d1a…`): :10-14, :29-33, :47-56, :85-89, :99-102, :104-112, :131-137.
- `/Users/mariaaleu/pmw-e2/`: `DECISIONS.md` D0 :12-17, D1 :19-39, D12 :190-210, D9-bis :252-259, D14/D15 :262-320, D16 :332-336, D17 :340-362, D19 :364-388; `FEES_SEMANTICS.md` :27-68, :87-114, :142-144; `PREREG_LEAD_HOURS_RANGE.md` §1-§4; `PREREG_MODELSEL_ASOF_V2.md` :15-45, :64-87; `PREREG_MODELSEL_V5.md` :140-161, :264-269; `MODELSEL_V5_CORRECTION_01.md` :10-98; `REVISION_IMPACT_AUDIT.md` :24-31, :64-102; `RECORD_VERSION_ASOF_AUDIT.md` :83-98; `F3-CLOSURE-REPORT.md` :10-59; `ROADMAP.md` :116-121, :183-205, :241, :296.
- Tests: `tests/test_no_future_information.py:13-182`; `tests/test_no_lookahead_adversarial.py:56-181`; `tests/test_resolution_not_in_features.py:79-211`; `tests/test_strategy_a.py:51-52, 221-229, 265-269`.

---

*Fin del documento. Para congelar: `shasum -a 256 PREREG_BACKTEST_STRATEGY_A.md > PREREG_BACKTEST_STRATEGY_A.sha256`, commit por PR, registro del hash en DECISIONS.md. Sólo después: R19.*