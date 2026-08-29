# PHASE 2D — STRATEGY A — DESIGN (proposal, DESIGN ONLY)

Baseline inmutable = commit **8162b9c** ("Phase 2D: add explicit outcome label contract"),
que es exactamente `d9c167d` (Phase 2C VALIDATED) **+ el contrato preparatorio
`outcome_label` / migración de schema v3**, ya en el repo. Este es el estado sobre el que se
implementará Strategy A V1. Nada de 2A/2B/2C se reabre ni modifica.

**Schema:** Strategy A V1 **NO** modifica el schema. El único cambio de schema (migración v3,
`outcomes.outcome_label`) ya se realizó en 8162b9c como **contrato preparatorio**, fuera del
scope de implementación de Strategy A.

**Fuente de verdad = el repositorio en `8162b9c`, leído directamente.** Ficheros autoritativos
verificados: `src/weather_agent/database.py`, `features.py`, `probability.py`, `labeling.py`,
`polymarket/discovery.py`, `polymarket/resolution.py`, y los `tests/` de 2A/2B/2C/2D. Las
interfaces de 2C (`build_feature`, `quantiles_to_distribution`/`band_probability`,
`build_label`) están confirmadas intactas; el contrato `outcome_label` está confirmado en el
commit.

Principio rector (usuario): que algo sea una implementación conservadora POSIBLE **no** lo
hace LOCKED. Si falta evidencia/decisión, queda **OPEN**. Si depende de un dato/semántica
que aún no tenemos, queda **BLOCKED**.

---

## A. Scope
Generador de señales weather-vs-mercado. Para un evento y un corte `prediction_time T`,
transforma las filas as-of de `features.build_feature` en una vista a nivel de evento y
emite, por banda y por evento, una señal ∈ {BUY, SELL, FADE, HOLD, NONE} con un
`fair_value` y un edge **BRUTO**, escribiendo en `predictions` y `signals`. Reutiliza las
garantías no-look-ahead de 2C sin cambiarlas.

## B. Non-goals
`edge_net`/`net_edge` y decisiones basadas en fees; sizing y `paper_trades`; Strategy B
(microestructura/orderbook/trades); motor de ejecución/paper; calibración o blend de
`p_model` más allá de `p_weather` sin evidencia; backtest de catálogo completo como parte
de v1; cualquier migración/cambio de schema; cualquier cambio a 2A/2B/2C.

## C. Inputs y lineage
Por band-token, desde `features.build_feature(con, *, prediction_time=T, market_id,
token_id, station, model, target_date, dataset_version)` (tabla `features`, columnas
autoritativas): `market_prob` (=`indicative_price` as-of `observation_time<=T`),
`weather_prob` (=prob de banda, forecast as-of `available_at<=T`), `forecast_tmax`,
`forecast_p10..p90`, `feature_json` (`price_observation_time`, `forecast_available_at`,
`forecast_issue_time`, `outcome_band_label`, `outcome_lo`, `outcome_hi`,
`weather_distribution`), `no_lookahead_verified=True`. **Nota de nombres:** en `features`
las columnas se llaman `market_prob`/`weather_prob`; en `predictions` son
`p_market`/`p_weather`. Strategy A LEE `features` y ESCRIBE `predictions`+`signals`.
Inputs prohibidos: `markets.available_at`; resolución/settlement/is_winner como feature;
precio EXECUTABLE; orderbook/trades; fees para net_edge (ver J).

**`target_date` (contrato B2, DECIDED-V1):** es un **parámetro obligatorio proporcionado por
el caller**. Si falta → Strategy A **fail-closed** (no genera señal). **NO** se deriva de
`resolution_timestamp`, `close_time`, `endDate`, `question`, `slug`, `description` ni de
ninguna otra fuente heurística; no existe un campo estructurado de `target_date` en el
catálogo (`markets` no lo tiene). Igualmente `model` es parámetro obligatorio del caller;
`station` se toma de `markets` para el evento.

## D. Event-level representation (autoritativo: 2B §6 + decisión #2)
Un evento = todas las band-markets con el mismo `event_id`. `markets` es **por banda**;
cada band-market tiene **2 tokens** (Yes/No) en `outcomes` con `(lo,hi)`. Strategy A opera
sobre el token **YES** de cada banda (P(Tmax ∈ banda)). La coherencia de evento se apoya en
`resolution.band_integrity`: `is_partition` es True solo con exactamente una banda
inferior-abierta + una superior-abierta + sin solapes + sin huecos enteros. La elegibilidad
y cualquier selección son a nivel de evento; las bandas NO son independientes.

**Identidad del token YES (contrato de 8162b9c, LOCKED — NO es una decisión nueva de Strategy
A).** El token YES se identifica **exclusivamente** por `outcomes.outcome_label == "Yes"`,
poblado verbatim desde gamma `outcomes[i]` en `discovery.build_market_records` (migración v3,
`phase2d_outcome_label`). **Nunca** por `outcome_index == 0`; **nunca** por `is_winner`. Si
`outcome_label` es NULL (datos previos a v3) o el band-market no tiene exactamente un "Yes" +
un "No" válidos → Strategy A **falla cerrada / excluye ese market** (→ `markets_excluded`),
sin inferir el token.

## E. p_market — LOCKED
Por banda = `features.market_prob` = `price_history.indicative_price` as-of
`observation_time<=T` (INDICATIVE; EXECUTABLE rechazado en `build_feature`). Se escribe en
`predictions.p_market` y, como referencia, en `signals.price_assumption`. Falta de precio ⇒
banda NONE. `Σ p_market` del evento se registra (puede ≠ 1).
Evidencia: `features.py` (`db.latest_asof("price_history", time_col="observation_time"…)`);
`database.py` `AS_OF_COLUMNS["price_history"]="observation_time"`; 2A §5.

## F. p_weather — LOCKED
Por banda = `features.weather_prob` = `band_probability(quantiles_to_distribution(p10..p90),
lo, hi)`, con forecast as-of `available_at<=T`. Se escribe en `predictions.p_weather`.
**Matemática de evento (autoritativa):** una única distribución de temperatura por evento
(mismo forecast) → sobre una partición válida (`is_partition` True) `Σ_bandas p_weather = 1`
exactamente (`tests/test_probability.py::test_full_partition_sums_to_one`). Bandas abiertas
vía `lo/hi=None`. Falta de forecast ⇒ banda NONE.
**Cómo se evitan señales incompatibles entre tokens:** (a) misma distribución para todas las
bandas del evento; (b) exigir `is_partition` antes de emitir señales de evento; (c) si
`band_integrity` ≠ partición → evento excluido (→ `markets_excluded`) y todas las bandas
NONE; (d) Yes/No de una banda son complementarios y Strategy A usa el token YES de forma
consistente.

## G. p_model — OPEN
El schema de `predictions` tiene columnas DISTINTAS `p_weather` y `p_model`; ningún código
del repo define la fórmula de `p_model` (`features.py` solo calcula `weather_prob`; no existe
módulo de estrategia). **NO asumir `p_model = p_weather`.**
Decisión: fórmula exacta de `p_model`. Alternativas: (a) `p_model=p_weather` (pass-through
determinista); (b) `p_model=calibrate(p_weather)` (isotónica/Platt sobre outcomes reales);
(c) `p_model=blend(p_weather, p_market)` (shrinkage al mercado). Evidencia necesaria: datos
out-of-sample de calibración (outcomes realizados vs distribución de forecast) sobre el
catálogo real — que NO tenemos (BLOCKED por catálogo). Recomendación: solo si el usuario
aprueba un v1 sin modelado nuevo, `p_model=p_weather`; pero es una DECISIÓN, no LOCKED.

## H. fair_value — OPEN
Columna `predictions.fair_value` / `signals.fair_value` existe; el repo no define su fórmula.
Decisión: mapeo de `p_model`→`fair_value`. Alternativas: (a) `fair_value=p_model` (prob YES
justa de la banda); (b) ajuste por incertidumbre/riesgo. Evidencia: (a) no requiere ninguna
(es la prob justa); (b) requiere modelo de incertidumbre calibrado (no disponible).
Recomendación: `fair_value=p_model`, justificable por la semántica de la columna; queda OPEN
hasta que el usuario lo fije.

## I. edge_gross — OPEN (definible sin look-ahead)
Columnas: `predictions.edge_gross`; en `signals` el edge bruto se llama **`edge`** (net =
`net_edge`). El repo no define fórmula. Decisión: fórmula de edge bruto. Alternativas:
(a) `edge = fair_value − p_market`; (b) log-odds/edge relativo; (c) EV/\$ (`fair_value/price
− 1`). Evidencia: ninguna para elegir (a) como edge aditivo natural dadas las columnas; (b)/
(c) requieren evidencia de backtest. **No introduce información futura:** `fair_value` y
`p_market` derivan solo de inputs as-of ≤ T (features), sin resolución. Recomendación:
`edge = fair_value − p_market` (bruto); queda OPEN. Escribir `predictions.edge_gross` y
`signals.edge`; dejar `edge_net`/`net_edge` NULL.

## J. fees / net_edge — BLOCKED (net_edge) + OPEN (semántica)
Lo que SABEMOS (2B §9, VERIFIED de gamma): recientes `weather_fees` (`feeSchedule.rate=0.05`
taker, `rebateRate=0.25`, `takerOnly=true`); legacy `fees_disabled` (0 justificado por
`feesEnabled=false`); ausente ⇒ UNKNOWN. `makerBaseFee=takerBaseFee=1000` capturados RAW.
Lo que NO sabemos: la relación de UNIDAD entre `…BaseFee=1000` y `rate=0.05` (2B §9 caveat,
decisión #4/#8). **BLOQUEA:** `edge_net`/`net_edge`, sizing, P&L de `paper_trades`. **NO
bloquea:** `p_market`, `p_weather`, `p_model`, `fair_value`, `edge_gross`/`edge`, ni una
señal sobre edge BRUTO. `net_edge` se deja NULL hasta confirmar semántica de fees.

## K. Signal generation — OPEN (umbrales) sobre vocabulario LOCKED
Vocabulario LOCKED: `signals.signal` CHECK {BUY, SELL, FADE, HOLD, NONE} (`database.py`, 2A).
Decisión OPEN: τ (banda muerta) y el mapeo edge→señal; si un edge negativo es FADE/SELL/HOLD;
si v1 emite SELL (Strategy A es generador sin estado de posición). Alternativas: (a) τ
simétrico: BUY si `edge>+τ`, FADE si `edge<−τ` sobre una favorita de `p_market` alto, HOLD si
`|edge|≤τ`, SELL solo con estado de posición externo (si no, no se emite), NONE si inelegible;
(b) τ por percentil/vol por evento. Evidencia necesaria: calibración/backtest sobre catálogo
real (BLOCKED). Recomendación: la ESTRUCTURA de (a) es razonable, pero los NÚMEROS (τ, corte
de FADE, emisión de SELL) quedan **OPEN** — no fijar números sin evidencia.

## L. Exclusions — parte LOCKED, parte OPEN
LOCKED: banda NONE si `build_feature` devuelve None (sin precio/forecast as-of), precio
EXECUTABLE, o `weather_prob` inválido; forecast `available_at>T` excluido (no-look-ahead).
OPEN: umbrales de coherencia de evento — rango aceptable de `Σ p_market`, tolerancia de
`Σ p_weather≈1`, y qué hacer si `band_integrity` no es partición o la resolución está en
DATA_ERROR/UNKNOWN. Registro autoritativo: `markets_excluded(market_id, reason, excluded_at,
stage, details)` — `stage` es VARCHAR sin CHECK, valores documentados
`discovery|pricing|labeling|feature`; para exclusiones de esta fase habría que reutilizar
`feature` o documentar un valor nuevo (permitido, pero a declarar). Recomendación: empezar
estricto (excluir evento incoherente), tolerancias OPEN.

## M. Epoch / template segmentation — LOCKED (debe segmentarse) + OPEN (política)
LOCKED (2B decisión #5, §8/§9): no conflar **epoch de fees** (`weather_fees` vs
`fees_disabled`) ni **template de medición** (`markets.measurement_rule`: "Daily
Observations" vs "by-the-Forecast"); todo backtest que cruce epochs DEBE segmentar. Cada
fila de señal registra ambos. OPEN: la política exacta (modelo por template, por epoch, o
pooled con covariable). Evidencia: suficientes eventos reales por template/epoch. Queda OPEN.

## N. Labels — LOCKED
Resolución entra SOLO vía `labeling.build_label(prediction_time, resolution_timestamp,
winning_outcome)`, que devuelve `{label, prediction_time, resolution_timestamp}` solo si
`winning_outcome` truthy, `resolution_timestamp` no None, y `prediction_time <
resolution_timestamp` (estricto); si no, None. Los labels se almacenan/juntan aparte de las
features; nunca como predictores. Uso: solo para evaluar/backtest.

## O. dataset_version / reproducibility (CORREGIDO tras leer database.py)
`predictions` y `signals` llevan `dataset_version`. Clave de reproducibilidad:
`predictions` PK `(market_id, token_id, model_version, "timestamp", dataset_version,
record_version)`; `signals` PK `(market_id, token_id, strategy, "timestamp",
dataset_version, record_version)`. **Corrección:** `predictions`/`signals` **NO** tienen
columna `random_seed` — `random_seed` solo existe en `backtest_results` (BIGINT). Strategy A
v1 es determinista (p_weather, edge son funciones deterministas de inputs as-of), así que la
reproducibilidad se garantiza por `dataset_version` + `model_version`/`strategy`, no por una
semilla. Mismo `dataset_version`+`model_version` ⇒ señales idénticas.

## P. Backtesting design — OPEN (metodología/walk-forward/sizing)
Unidad temporal = `prediction_time T` (as-of). Unidad de evento = `event_id`. Labels =
`build_label` (`prediction_time<resolution_timestamp`). Walk-forward = consecuencia de la
disciplina as-of/no-look-ahead de 2A (principio LOCKED); la config concreta
(`backtest_results.walk_forward_config`, ventanas train/val/test) queda OPEN. `dataset_version`
= ancla de reproducibilidad (`backtest_results.dataset_version`). Leakage = garantías 2C.
Mínimo de datos = catálogo real completo (2B decisión #7, USER-RUN en Hetzner) → **BLOCKED**.
Sizing = requiere `net_edge`+fees → **BLOCKED**. Métricas GROSS (Brier/log-loss de `p_model`
vs outcome; signo/cobertura de `edge`) OPEN. Sin claim de P&L en \$ hasta que exista net_edge.

## Q. Leakage controls
Reutilizar las garantías de 2C sin cambios: todo input as-of ≤ T
(`observation_time`/`available_at`); `no_lookahead_verified` upstream True; ningún campo de
`FORBIDDEN_FEATURE_FIELDS` en fila/`feature_json` de señal; labels solo si
`prediction_time<resolution_timestamp`; `markets.available_at` nunca como señal (UNKNOWN, 2B
§11); precio EXECUTABLE rechazado. Una fila debe fallar-cerrado (NONE) si cualquier chequeo
falla.

## R. Tests (unit + adversarial)
Unit: `edge = fair_value − p_market` (tras fijar I); mapeo de señal alrededor de τ (tras
fijar K); bandas abiertas vía `band_probability` real; agregación de evento + `Σ p_weather≈1`
sobre partición; inelegibilidad → NONE. Adversarial (reutilizar patrón de
`test_resolution_not_in_features.py`): resolución nunca en una señal
(`FORBIDDEN_FEATURE_FIELDS`); label solo si `prediction_time<resolution_timestamp`; precio
EXECUTABLE rechazado; forecast `available_at>T` excluido; evento incoherente (Σ p_market
absurdo o no-partición) excluido → `markets_excluded`; `net_edge`/`edge_net` NULL.
Determinismo: mismos inputs ⇒ mismas señales.

## S. TESTED criteria
Todos los tests de R en verde bajo `pytest` sobre datos sintéticos/fixtures — prueba SOLO
lógica (TESTED, no VALIDATED).

## T. VALIDATED criteria
Run real (Hetzner/Actions) sobre una porción del catálogo REAL: (1) solo inputs as-of;
(2) sin campo de resolución en ninguna fila; (3) `edge_net`/`net_edge` NULL (sin supuesto de
fee); (4) reproducible para `dataset_version`+`model_version`/`strategy` fijos; (5)
`Σ p_weather≈1` en eventos reales con partición; (6) evidencia en
`PHASE_2D_VALIDATION_REPORT.md` (run_id/commit/dataset_version + evidencia por criterio).
Un pytest verde por sí solo es solo TESTED.

## U. Blockers / dependencies (orden de ejecución)
1. **Decisiones OPEN G/H/I/K/L** (al menos defaults conservadores aprobados por el usuario)
   antes de codificar el generador.
2. **Semántica de fees** (SEPARADA; gatea `net_edge`/sizing): confirmar unidades de
   `raw_fee_fields` + mapeo de epoch.
3. **Catálogo real completo** (backtest representativo/sizing): 2B USER-RUN en Hetzner.
4. **(RESUELTO esta revisión)** columnas reales de `features`/`predictions`/`signals`/
   `paper_trades`/`backtest_results`/`markets_excluded` confirmadas contra `database.py`
   @d9c167d — ver tabla de estados.

## V. DO NOT IMPLEMENT YET
`net_edge`/`edge_net` y decisiones/sizing basados en fees; Strategy B; motor paper;
ejecución real/wallet/órdenes; calibración o blend de `p_model` más allá de `p_weather`;
backtest de catálogo completo; **cualquier migración/cambio de schema en Strategy A** (el
schema ya está en v3 tras 8162b9c por el contrato preparatorio `outcome_label`; **Strategy A
V1 no modifica el schema**); cualquier cambio a
`features.py`/`probability.py`/`labeling.py`/`database.py` o sus tests (salvo contradicción
documental demostrable → PARAR y reportar antes).

---

## W. PROPUESTA DE DISEÑO V1 — decisiones NUEVAS de Strategy A
**Todo lo de esta sección son decisiones NUEVAS de Strategy A (estado DECIDED-V1), NO
heredadas de 2A/2B/2C.** Resuelven, solo para V1, los OPEN de §G/§H/§I/§K y son
explícitamente reemplazables sin tocar el schema.

**W.1 `p_model` V1 = `p_weather`.** Justificación: `p_weather` es el único componente
probabilístico meteorológico ya implementado (2C, Blocker 2). NO se afirma que esté
calibrado de forma óptima; es un baseline V1, reemplazable por calibración/blend (§G)
cuando exista evidencia. Se escribe en `predictions.p_model`.

**W.2 `fair_value` V1 = `p_model`** ( = `p_weather` en V1). Se escribe en
`predictions.fair_value` y `signals.fair_value`.

**W.3 Edge V1.** `predictions.edge_gross = fair_value − p_market`. En `signals`:
`edge = fair_value − price_assumption` (donde `price_assumption` = el `p_market`
indicativo usado). Ambos son BRUTOS. `predictions.edge_net` y `signals.net_edge` = NULL
(ver §J/W.9). Sin look-ahead: `fair_value` y `p_market` solo dependen de inputs as-of ≤ T.

**W.4 Señales V1.** Con `tau > 0` (parámetro, ver W.12):
BUY si `edge >= +tau`; FADE si `edge <= −tau`; HOLD si `|edge| < tau`; NONE si el
evento/mercado no es elegible. **V1 NO emite SELL** (ver W.11). El vocabulario
{BUY,SELL,FADE,HOLD,NONE} es LOCKED (CHECK del schema); V1 solo usa un subconjunto.

**W.5 Event-level (formalización matemática).**
Sea un evento `E` con bandas `b_1..b_n` (band-markets), cada una con su token YES e
intervalo `(lo_i, hi_i)`. Las bandas son sucesos **mutuamente excluyentes** sobre la
variable `Tmax` (no solapan) y, si la partición es válida, **colectivamente exhaustivos**
(una banda inferior-abierta, una superior-abierta, sin huecos enteros — `band_integrity`).
De UNA distribución de evento `D` (mismo forecast) sobre temperaturas enteras:
- `p_weather_i = band_probability(D, lo_i, hi_i) = Σ_{t ∈ b_i} D(t)`.
- Partición válida ⇒ `Σ_i p_weather_i = Σ_t D(t) = 1` (exacto;
  `test_probability.py::test_full_partition_sums_to_one`).
- `p_market_i` = precio indicativo YES de `b_i`. `Σ_i p_market_i` **no** tiene por qué
  valer 1 (spread, fees, mispricing, quoting incompleto).
- **Edge por token sin perder la representación de evento:** `edge_i = fair_value_i −
  p_market_i = p_weather_i − p_market_i` (V1). Cada `edge_i` se calcula de forma
  independiente por banda, PERO todos los `p_weather_i` provienen de la MISMA `D` y el
  conjunto de bandas se valida como partición ANTES de emitir; así los edges por token son
  mutuamente coherentes (referencian una sola distribución de evento). La representación de
  evento se conserva porque (i) `D` es única por evento y (ii) la elegibilidad es de evento.
- **Si las bandas NO forman partición válida** (`is_partition=False`, o `Σ p_market` fuera
  de tolerancia, o resolución en DATA_ERROR/UNKNOWN): el evento COMPLETO se excluye; no se
  emite señal para NINGUNA banda (todas NONE).

**W.6 Coherencia (conservadora).** Si el evento no supera `band_integrity/is_partition` y
las tolerancias definidas, NO se generan señales para ese evento. **No** se oculta la
incoherencia con normalización silenciosa (no se re-escala `p_weather` ni `p_market` para
forzar Σ=1): se excluye y se registra en `markets_excluded` con `details` explicando la
causa.

**W.7 Outputs.** Strategy A V1 escribe `predictions` y `signals` usando los helpers
existentes (`db.insert`/`db.upsert`), sin cambios de schema.
- `predictions.model_version = "stratA_pmodel_v1"` (identifica el modelo `p_model=p_weather`).
- `signals.strategy = "strategy_a_v1"`.
- Ambas filas llevan el MISMO `dataset_version` que las `features` consumidas → vínculo de
  reproducibilidad. Claves: `predictions` reproducible por `(dataset_version, model_version)`;
  `signals` por `(dataset_version, strategy)`.
- `tau` NO tiene columna dedicada: se registra en `signals.reason` (p.ej. `"edge=…;tau=…"`)
  y, en backtests, en `backtest_results.parameters` (JSON) para reproducibilidad.
- **`predictions.confidence` y `signals.confidence` = NULL en V1** (DECIDED-V1). No se
  computa una medida de confianza en V1; la columna existe (2A) y queda reservada,
  reemplazable en una versión posterior. No es un valor heredado de 2A/2B/2C.
- **`predictions."timestamp"` y `signals."timestamp"` = `prediction_time`** (DECIDED-V1). El
  timestamp de cada fila es el corte as-of `T` usado para construir las features, coherente
  con `AS_OF_COLUMNS["predictions"]="timestamp"` y `AS_OF_COLUMNS["signals"]="timestamp"`.
  No es un valor heredado de 2A/2B/2C.

**W.8 `markets_excluded.stage`.** Valores documentados de forma autoritativa (2A;
`database.py`, VARCHAR sin CHECK): `discovery | pricing | labeling | feature`. Strategy A
consume `features`, así que la exclusión ocurre en la frontera de features → **`stage =
"feature"`** (valor documentado; NO se inventa uno nuevo). El motivo concreto
(`event_not_partition`, `sum_pmarket_out_of_tolerance`, `resolution_data_error`, …) va en
`reason`/`details`.

**W.9 Fees (BLOCKED).** Se mantiene `net_edge` BLOCKED: NO se calcula `net_edge`/`edge_net`,
NO hay sizing, NO hay P&L neto por fees. **Qué SÍ funciona sin fees:** `p_market`,
`p_weather`, `p_model`, `fair_value`, `edge_gross`/`edge` (todos brutos, fee-free) y la
señal discreta BUY/FADE/HOLD/NONE sobre el edge bruto, más su evaluación por labels
(Brier/log-loss, aciertos de dirección) — nada de esto necesita fees. Fees solo se
requieren para pasar de edge bruto a neto y de ahí a sizing/P&L.

**W.10 Backtest mínimo de Strategy A.**
Unidad = **evento** (`event_id`). Labels = `labeling.build_label` con
`prediction_time < resolution_timestamp` (estricto). Walk-forward/as-of: cada evento se
evalúa en un `T` anterior a su `resolution_timestamp`, usando solo inputs as-of ≤ T; sin
random split. `dataset_version` fija el snapshot de datos; `model_version="stratA_pmodel_v1"`
fija el modelo; `backtest_results` registra `dataset_version`/`model_version`/`parameters`
(incl. `tau`)/`walk_forward_config`/ventanas. Métricas mínimas (BRUTAS): Brier y log-loss de
`p_model` vs outcome; cobertura y precisión direccional de BUY/FADE; distribución de `edge`.
Separación train/test: por tiempo (test = eventos con `T` posterior al corte de train),
**segmentando por epoch de fees y `measurement_rule`** (§M). Prevención de leakage:
garantías 2C (as-of ≤ T; sin `FORBIDDEN_FEATURE_FIELDS`; label solo si `T<resolution`;
`markets.available_at` nunca as-of). Sizing/P&L neto: **BLOCKED** (fees + catálogo).

**W.11 Por qué V1 no emite SELL.** SELL implica **cerrar/invertir una posición existente**,
lo que requiere estado de inventario que Strategy A (generador sin estado) no tiene. El caso
"mercado sobreprecia YES" ya lo captura **FADE** con `edge <= −tau` (apostar contra YES),
sin necesidad de SELL. Clave de arquitectura: el **significado de `edge` no cambia** al
añadir SELL después — `edge = fair_value − p_market` sigue igual; SELL se incorporará como
una capa de gestión de posición (consumiendo `signals` + estado de posición) que decide
SALIDAS sobre el MISMO signo de edge, no como una redefinición del edge. Así V1 queda
preparada sin deuda semántica.

**W.12 Threshold `tau`.** NO se inventa un valor. `tau` es un **parámetro de configuración
obligatorio** del generador (sin default; el generador se niega a correr sin `tau`
explícito) y su valor queda **OPEN/calibración**. Evidencia necesaria para calibrarlo: un
backtest walk-forward sobre el **catálogo real** (BLOCKED) que mida `edge` vs outcome
realizado y elija `tau` optimizando una métrica out-of-sample (mejora de Brier / precisión-
cobertura de BUY-FADE), **segmentado por epoch/template**. Hasta entonces `tau` no tiene
valor validado.

**W.13 Parámetros obligatorios (sin valor por defecto).** El generador exige, y **falla
cerrado si falta cualquiera**, estos parámetros de configuración — **ninguno tiene default**:
- `tau` — umbral de señal (§W.4/W.12).
- `weather_sum_tolerance` — tolerancia de `|Σ_bandas p_weather − 1|` para aceptar la
  partición del evento.
- `market_sum_min` y `market_sum_max` — rango aceptable de `Σ_bandas p_market` por evento.
`target_date` y `model` (§C) son igualmente parámetros obligatorios del caller. El **mecanismo**
(obligatorios, sin default, fail-closed) es DECIDED-V1; los **valores** de `tau` y de las
tolerancias quedan OPEN/calibración (dependen del catálogo real, BLOCKED).

---

## TABLA FINAL — DECISIÓN | ESTADO | V1 | EVIDENCIA | BLOQUEA IMPLEMENTACIÓN

Estados: **LOCKED** (heredado de fases previas) · **DECIDED-V1** (decisión nueva aprobada
para V1) · **OPEN** (requiere decisión/evidencia) · **BLOCKED** (depende de dependencia
externa pendiente).

| DECISIÓN | ESTADO | V1 | EVIDENCIA (8162b9c) | BLOQUEA IMPLEMENTACIÓN |
|---|---|---|---|---|
| p_market as-of `observation_time<=T` | LOCKED | `features.market_prob`→`predictions.p_market` | `features.py`; 2A §5 | No |
| p_weather = `band_probability∘quantiles_to_distribution` as-of `available_at` | LOCKED | →`predictions.p_weather` | `features.py`+`probability.py` | No |
| forecasts as-of `available_at<=T` | LOCKED | — | `features.py` | No |
| `markets.available_at` no-señal | LOCKED | — | 2B §11 / #3 | No |
| resolución solo label | LOCKED | guardas 2C por fila | `FORBIDDEN_FEATURE_FIELDS` | No |
| label si `prediction_time<resolution_timestamp` | LOCKED | backtest | `labeling.build_label` | No |
| nivel EVENTO | LOCKED | partición por `event_id` | 2B #2 | No |
| **YES ⇔ `outcome_label == "Yes"`** (nunca `outcome_index`/`is_winner`) | LOCKED (de 8162b9c) | identificación del token YES; NULL/estructura inválida → fail-closed | `discovery.py:184`, migración v3 `phase2d_outcome_label`; `tests/test_outcome_label.py` | No |
| orderbook/trades bloqueados | LOCKED | — | 2A; 2B #6 | No |
| segmentar epoch fees + `measurement_rule` | LOCKED | registrar por fila; segmentar backtest | 2B §8/§9/#5 | No |
| walk-forward/as-of (principio) | LOCKED | sin random split | 2A §5/§6 | No |
| repro por `dataset_version`+`model_version`/`strategy` | LOCKED | sin `random_seed` en pred/signals | PKs; 2A §6 | No |
| **p_model = p_weather** | DECIDED-V1 | baseline reemplazable | decisión NUEVA; `p_weather` de 2C | No |
| **fair_value = p_model** | DECIDED-V1 | =p_weather en V1 | decisión NUEVA | No |
| **edge = fair_value − p_market** (`signals.edge = fair_value − price_assumption`) | DECIDED-V1 | bruto; net NULL | decisión NUEVA; sin look-ahead | No |
| **señales BUY/FADE/HOLD/NONE, sin SELL** | DECIDED-V1 | mapeo por `tau` | decisión NUEVA; vocab LOCKED | No |
| **coherencia: excluir evento si no partición** | DECIDED-V1 | `is_partition`+tolerancias; sin normalización silenciosa | `band_integrity` 2B §6 | No |
| **outputs: escribir `predictions`+`signals`** | DECIDED-V1 | `model_version="stratA_pmodel_v1"`, `strategy="strategy_a_v1"` | schema `database.py` | No |
| **`target_date` = param obligatorio del caller (B2)** | DECIDED-V1 | fail-closed si falta; sin inferencia de resolution_timestamp/close_time/endDate/slug/question | `markets` sin `target_date`; §C | No |
| **`model` = param obligatorio del caller** | DECIDED-V1 | fail-closed si falta | firma `build_feature`; §C | No |
| **`confidence` = NULL en V1** (predictions/signals) | DECIDED-V1 | no se computa en V1; columna reservada | columna existe (2A) | No |
| **`timestamp` = `prediction_time`** (predictions/signals) | DECIDED-V1 | corte as-of T por fila | `AS_OF_COLUMNS`; schema 2A | No |
| **`markets_excluded.stage`** | DECIDED-V1 | `"feature"` | valores documentados {discovery,pricing,labeling,feature} | No |
| valor numérico de `tau` | OPEN | parámetro obligatorio, sin default | requiere backtest catálogo | No (parametrizable); sí bloquea señal VALIDATED |
| `weather_sum_tolerance`, `market_sum_min`, `market_sum_max` (tolerancias de coherencia) | DECIDED-V1 (mecanismo) / valores OPEN | parámetros obligatorios, SIN default; fail-closed si faltan | §W.13; §L | No (parametrizable) |
| política segmentación epoch/template (agregado) | OPEN | — | 2B §8/§9 | No (solo afecta backtest agregado) |
| metodología/ventanas/métricas de backtest | OPEN | diseño mínimo en §W.10 | `backtest_results.*` | No (signal-gen); sí backtest VALIDATED |
| semántica de fees (`raw_fee_fields` 1000 vs 0.05) | BLOCKED | `net_edge`=NULL | 2B §9 / #4/#8 | Bloquea net_edge/sizing; NO señal bruta |
| `net_edge`/`edge_net` | BLOCKED | NULL | depende de fees | No (se deja NULL) |
| sizing / `paper_trades` | BLOCKED | fuera de V1 | fees + catálogo | Fuera de V1 |
| catálogo real completo | BLOCKED | — | 2B #7 (USER-RUN) | Bloquea backtest representativo/VALIDATED |
| Strategy B / microestructura | BLOCKED | fuera | forward-only | Fuera de alcance |

---

## TABLA MAESTRA (análisis previo) — DECISIÓN | ESTADO | EVIDENCIA | IMPLICACIÓN

| DECISIÓN | ESTADO | EVIDENCIA (d9c167d) | IMPLICACIÓN |
|---|---|---|---|
| p_market = `indicative_price` as-of `observation_time<=T` | LOCKED | `features.py`; `AS_OF_COLUMNS["price_history"]`; 2A §5 | Se lee de `features.market_prob`; escribir `predictions.p_market` |
| p_weather = `band_probability(quantiles_to_distribution(p10..p90),lo,hi)` as-of `available_at` | LOCKED | `features.py`+`probability.py`; `AS_OF_COLUMNS["weather_forecasts"]` | Escribir `predictions.p_weather`; base de la partición de evento |
| forecasts seleccionados con `available_at<=T` | LOCKED | `features.py` `latest_asof(...available_at...)` | No-look-ahead de forecast garantizado |
| `markets.available_at` NO es señal as-of | LOCKED | 2B §11 + decisión #3; columna UNKNOWN | Usar `observation_time` de precio como as-of |
| resolución/is_winner solo label, nunca feature | LOCKED | `features.FORBIDDEN_FEATURE_FIELDS`; 2B §6 | Guardas 2C reutilizadas en cada fila de señal |
| label solo si `prediction_time<resolution_timestamp` | LOCKED | `labeling.build_label` (`<` estricto) | Labels separados de features |
| Strategy A a nivel EVENTO | LOCKED | 2B decisión #2 | Elegibilidad/partición por `event_id`, no por banda aislada |
| orderbook/trades bloqueados (forward-only) | LOCKED | 2A; 2B decisión #6 | Sin Strategy B/microestructura |
| segmentar por epoch de fees + `measurement_rule` | LOCKED (debe) | 2B §8/§9 + decisión #5 | Cada fila registra epoch+template; política de agregado OPEN |
| walk-forward / evaluación as-of (principio) | LOCKED | 2A §5/§6; diseño as-of | Sin random split; config concreta OPEN |
| Determinismo/repro por `dataset_version`+`model_version`/`strategy` | LOCKED | PKs de `predictions`/`signals`; 2A §6 | `predictions`/`signals` NO tienen `random_seed` (solo `backtest_results`) |
| fórmula de `p_model` | OPEN | schema separa `p_weather`/`p_model`; sin fórmula en código | NO asumir `p_model=p_weather`; decidir (pass-through/calibración/blend) |
| fórmula de `fair_value` | OPEN | columna existe; sin fórmula | Rec. `=p_model`; a fijar por usuario |
| fórmula de `edge_gross` (`signals.edge`) | OPEN | columnas `edge_gross`/`edge`; sin fórmula | Rec. `fair_value−p_market`; definible sin look-ahead |
| umbrales BUY/SELL/FADE/HOLD/NONE (τ, corte FADE, SELL) | OPEN | vocabulario en CHECK; sin umbrales en repo | Estructura razonable; números requieren evidencia (catálogo) |
| umbrales de exclusión de coherencia de evento | OPEN | `markets_excluded` existe; sin política | Empezar estricto; tolerancias OPEN |
| política de segmentación epoch/template | OPEN | 2B §8/§9 | Modelo por template/epoch/pooled: requiere datos |
| metodología de backtest / walk-forward config / métricas | OPEN | `backtest_results.*` columnas; sin config | Definir ventanas/métricas GROSS |
| semántica de fees (`raw_fee_fields`: 1000 vs rate 0.05) | BLOCKED | 2B §9 caveat + decisión #4/#8 | Bloquea `net_edge`/sizing/P&L; NO bloquea señal bruta |
| `net_edge`/`edge_net` | BLOCKED | depende de fees | Dejar NULL en v1 |
| sizing / `paper_trades` | BLOCKED | requiere net_edge + catálogo | Fuera de v1 |
| catálogo real completo (backtest representativo) | BLOCKED | 2B decisión #7 (USER-RUN Hetzner) | Sin claim de P&L/sizing hasta correrlo |
| Strategy B / microestructura | BLOCKED | orderbook/trades vacíos (forward-only) | Fuera de alcance |

---

## Contradicciones encontradas
Entre los documentos/código autoritativos de 2A/2B/2C **no** hay contradicciones internas;
son mutuamente consistentes. Contradicciones del BORRADOR 2D previo frente al repo real, ya
corregidas en esta versión:
1. El borrador afirmaba que `predictions`/`signals` registran `random_seed` → FALSO:
   `random_seed` solo existe en `backtest_results`. Corregido en §O.
2. El borrador trataba `net_edge` como "restricción LOCKED (no se calcula)" → reclasificado
   como **BLOCKED** (depende de la semántica de fees).
3. Nombres de columnas imprecisos: en `signals` el edge bruto es `edge` (neto `net_edge`);
   en `predictions` es `edge_gross`/`edge_net`. Corregido en §I y en la tabla.
4. Blocker previo "no re-leí `database.py`" → RESUELTO: leído íntegro en `d9c167d`.
Nota (no es contradicción): el schema separa `p_weather` de `p_model`, por eso `p_model`
queda OPEN. Salvedad de evidencia: `results/PHASE_2C_VALIDATION_REPORT.md` devolvió cuerpo
vacío en esa ruta; no pude confirmar 2C VALIDATED desde un informe poblado.
