# ROADMAP — Polymarket_Weather_Agent hasta COMPLETO

**Generado:** 2026-09-05 · **Base:** workflow `wf_4ac97853-aa8` (4 inventarios + síntesis + crítico de completitud) con las 14 correcciones de `WF_critica.md` §F aplicadas · **Mandato:** D0–D8 en `DECISIONS.md` · **Ejecutor efectivo de todos los ítems: Claude (D5)** mientras Codex esté sin cuota (hasta 2026-10-05).

## 0. Definición de COMPLETO

COMPLETO significa que el proyecto Polymarket_Weather_Agent puede ejecutar de extremo a extremo, sobre DATOS REALES y sin operar dinero real, la cadena: (1) catálogo Gamma real ingerido en la DuckDB operativa (markets/outcomes/fees) con checkpoint resumible; (2) price_history real desde CLOB /prices-history (fidelity=1, ventanas <=48h) con dataset_version/provenance; (3) weather_forecasts reales desde Open-Meteo con available_at fail-closed derivado de disponibilidad empírica (F3), para el/los modelos elegidos en M1 y con coordenadas canónicas D1; (4) weather_observations y labels retrospectivos (Y_final) con decisión registrada sobre Y_final vs Y_asof_T; (5) weather_errors -> cuantiles p10..p90 por estación/modelo/lead/mes (M2) preregistrados; (6) features persistidas en la tabla features con no_lookahead_verified=True, filtro por dataset_version y token YES explícito; (7) p_weather calculado con un SettlementOperator explícito por fuente (fail-closed sin operador); (8) Strategy A con tau/tolerancias preregistradas, edge_net con modelo de coste (fees confirmadas) y sizing; (9) motor de backtest walk-forward que escribe backtest_results con métricas Brier/log-loss/PnL bruto y neto segmentadas por epoch/template, ejecutado sobre el catálogo real y con informe de validación versionado en el repo (no en results/ ignorado); (10) modo PAPER: paper_trades con price_layer SIMULATED_EXECUTABLE alimentado por un colector forward-only (orderbook/trades), corriendo N días sin intervención y con informe de evaluación paper vs backtest. Cada uno de estos pasos debe estar IMPLEMENTADO (código en main vía PR, nunca push directo), TESTED (pytest verde, sin stubs skip) y VALIDATED (harness sobre datos reales con informe hasheado). Quedan explícitamente FUERA de COMPLETO: ejecución con dinero real, wallet/órdenes, Strategy B, y cualquier elusión de cuotas (Open-Meteo 429) o borrado de datos. Un preregistro precede a cada ejecución evaluativa (V5, M2, backtest, calibración de tau, paper run).

**Enmiendas a la definición (crítica §E, adoptadas):** (11) el pipeline paper consume mercados con
`endDate` futuro descubiertos en el día, y forecasts obtenidos **antes de T** (captura prospectiva);
(12) criterios de parada y tolerancia de fallos definidos por preregistro: qué cuenta como "día válido",
umbral de 429 sostenidos, tasa máxima de exclusión fail-closed, kill-switch; (13) las fees no se exigen
"confirmadas" sino **modeladas por preregistro con análisis de sensibilidad**, reportando PnL neto bajo
hipótesis declaradas; (14) toda evidencia de validación vive en git (`docs/validation/`, hasheada), no en
`results/` ignorado.

## 1. Estado actual (corregido por la crítica)

- Repo canónico `~/workspace/Polymarket_Weather_Agent`: `main@5287122` (127 passed / 4 skipped). Rama `codex/prices-ingestion-wip@6ed85ad` en `origin`: **131 passed / 2 skipped** (queda skip sólo `test_weather_asof.py:26,33`).
- Nada en `src/` escribe `weather_forecasts`, `weather_observations`, `weather_errors`, `features`, `trades`, `orderbook_snapshots`, `paper_trades`, `backtest_results`; `price_history` sólo desde la rama de rescate. `discovery()` sólo mercados cerrados (`discovery.py:435`). `validate_2d.py:286` fija `validated=False`.
- Investigación (`~/pmw-e2`): M1 NO seleccionado; V5.3 preregistrada (`e8302dc1…`), bloqueada por 429; D1-COORD verificada (11/55 observadas, 43 inferidas; OPKC abierta); snapshot v1.1 (`071b142c…`) y v1.0 restaurado (`ebe21014…`).
- Hechos nuevos del catálogo (crítica §C.2): `endDate = 12:00Z` en 93 221/93 221 (P1 cerrada); (endDate − createdAt) p50 = 55,9 h; **20,8 % de eventos creados <48 h antes de endDate**, 155 <24 h.
- Codex: `usage_limit_exceeded` hasta 2026-10-05 (D3/D5).

## 2. Ítems (orden topológico)

| id | tam | owner efectivo | depende de | título | estado / bloqueo |
|---|---|---|---|---|---|
| **R0** | S | Claude (D5; owner previsto: Codex) | — | Consolidar árboles y custodia de artefactos | PARCIAL |
| **R1** | S | Claude (D5; owner previsto: ambos) | — | Cerrar D3: respuesta de Codex y registro de propiedad por pista | CERRADO POR D5 |
| **R2** | S | Claude | R1 | Alinear v5uni.py y §14 con D1 antes de que vuelva la cuota (V5.3 si procede) | HECHO · Ventana: debe completarse antes de que quota_watch.sh imprima CUOTA_RESTABLECIDA (~2026-09-06); no consultar Open-Meteo. |
| **R3** | S | Claude | R0 | Reconciliar hashes de muestras V2/V3 y documentar método de hashing | PARCIAL |
| **R4** | M | Claude | R2, R3 | Ejecutar V5.2/V5.3 al restablecerse la cuota (sin sortear 429) | PENDIENTE · HTTP 429 Open-Meteo single-runs/historical hasta ~2026-09-06; puerta 'no sortear cuotas'. |
| **R5** | S | Claude (D5; owner previsto: ambos) | R4 | Clasificar §15 y emitir recomendación M1 (§16) | PENDIENTE |
| **R6** | S | Claude (D5; owner previsto: Codex) | R0 | Higiene de comentarios/docstrings desfasados en el repo | PENDIENTE |
| **R7** | M | Claude (D5; owner previsto: Codex) | R0 | Registro de estaciones en el repo: coordenadas D1, ICAO variable en el tiempo, tz y exclusiones | PENDIENTE |
| **R8** | M | Claude (D5; owner previsto: Codex) | R7 | Implementar el ancla 2E: T = endDate − lead_hours y target_date por día civil de estación (cerrar P1) | PENDIENTE |
| **R9** | L | Claude (D5; owner previsto: Codex) | R0, R8, R10 | Orquestador de ingestión de precios CLOB + política 429 + sonda P3 + un-skip test_market_asof | PENDIENTE · Rate limits de CLOB desconocidos (no documentados); no sortear. |
| **R10** | M | Claude (D5; owner previsto: Codex) | R0 | Poblar la DuckDB operativa con el catálogo real y re-validar 2B con evidencia versionada | PENDIENTE |
| **R11** | M | Claude (D5; owner previsto: ambos) | R10 | Resolver semántica de fees y modelo de coste efectivo (edge_net) | PENDIENTE |
| **R12** | L | Claude (D5; owner previsto: ambos) | R0, R10, R13 | SettlementOperator: protocolo, migración de probability/features y operadores por fuente | PENDIENTE |
| **R13** | M | Claude (D5; owner previsto: ambos) | R7, R8 | Ingestión de observaciones (weather_observations) desde IEM y decisión Y_final vs Y_asof_T | PENDIENTE |
| **R14** | S | Claude (D5; owner previsto: Codex) | R10, R13 | Pipeline de labels: generación masiva y persistencia con join features<->labels | PENDIENTE |
| **R15** | L | Claude (D5; owner previsto: ambos) | R5, R7, R8, R0 | Ingestión de forecasts Open-Meteo (weather_forecasts) con available_at fail-closed y plan de cuota | PENDIENTE · HTTP 429 Open-Meteo; presupuesto diario insuficiente para escala completa sin plan de cuota (decisión abierta). |
| **R16** | L | Claude (D5; owner previsto: ambos) | R5, R13, R15, R12 | M2: weather_errors y derivación de cuantiles p10..p90 (preregistrado) | PENDIENTE |
| **R17** | M | Claude (D5; owner previsto: Codex) | R9, R15, R12 | Persistir features y corregir filtros (dataset_version, token YES) + validar no-look-ahead sobre datos reales | PENDIENTE |
| **R18** | S | Claude | R11, R14, R17 | Preregistro del backtest y de parámetros Strategy A (tau, tolerancias, segmentación) | PENDIENTE |
| **R19** | L | Claude (D5; owner previsto: Codex) | R18 | Motor de backtest walk-forward que escribe backtest_results | PENDIENTE |
| **R20** | M | Claude (D5; owner previsto: Codex) | R11, R19 | Sizing y edge_net en la señal (desbloquear 'DO NOT IMPLEMENT YET' de 2D) | PENDIENTE |
| **R21** | M | Claude (D5; owner previsto: ambos) | R19, R20 | Ejecutar backtest real, calibrar tau OOS y publicar informe de validación de Strategy A | PENDIENTE |
| **R22** | L | Claude (D5; owner previsto: Codex) | R9, R10 | Colector forward-only (orderbook/trades) y verificación de CLOB_WS_URL | PENDIENTE · URL websocket sin verificar; requiere host con proceso persistente. |
| **R23** | L | Claude (D5; owner previsto: Codex) | R20, R22, R21 | Motor paper: paper_trades con SIMULATED_EXECUTABLE y comparación paper vs backtest | PENDIENTE |
| **R24** | M | Claude (D5; owner previsto: ambos) | R23, R16 | Corrida paper preregistrada de N días y veredicto COMPLETO | PENDIENTE · Requiere cuota Open-Meteo diaria sostenida y host persistente. |
| **R25** | S | Claude | — | Nomenclatura: fases 2E/2F/2G y desambiguar "D1" | PENDIENTE |
| **R26** | M | Claude | R10 | Descubrimiento de mercados ABIERTOS + markets.available_at para paper | PENDIENTE |
| **R27** | M | Claude | R7 | Migración de esquema v4 explícita | PENDIENTE |
| **R28** | S | Claude | — | Plan de cuota Open-Meteo (decisión con owner y criterio) | PENDIENTE |

## 3. Detalle

### R0 — Consolidar árboles y custodia de artefactos

OBSERVADO: prices.py, PHASE_2E_SETTLEMENT_OPERATOR_DESIGN.md y el diff de tests/test_market_asof.py viven sin commit en /private/tmp/pmw-publish/worktree; PHASE_2E_LEAD_HOURS_ANCHOR.md solo existe en /private/tmp/pmw-publish (raíz con .git sin HEAD); los scripts constructores de CATALOG_V2 están en ~/.claude/jobs/324ffe40/tmp y apuntan a /private/tmp/pmw-publish/src (vacío); ~/pmw-e2 y ~/pmw-catalog-v2 no tienen git. Trabajo: crear rama feature en el canónico ~/workspace/Polymarket_Weather_Agent, traer los cuatro ficheros del worktree y el doc 2E lead_hours, versionar enum_v2.py/desc.py bajo scripts/research/, y poner ~/pmw-e2 bajo git (o un subdirectorio docs/research/ del repo) con los .sha256 existentes. Nunca push a main: todo vía PR.

- **Criterio de hecho:** `git -C ~/workspace/Polymarket_Weather_Agent log --oneline` en rama feature muestra un commit que contiene src/weather_agent/polymarket/prices.py, PHASE_2E_LEAD_HOURS_ANCHOR.md, PHASE_2E_SETTLEMENT_OPERATOR_DESIGN.md y scripts/research/enum_v2.py; `git status` del worktree en /private/tmp queda limpio o el worktree se elimina; ~/pmw-e2 tiene .git con commit inicial y DECISIONS.md rastreado; pytest sigue en >=127 passed.
- **Corrección/nota (crítica):** HECHO 3/4 (rama codex/prices-ingestion-wip@6ed85ad, 131/2). Queda: PHASE_2E_LEAD_HOURS_ANCHOR.md al repo, PR de la rama, versionar ~/pmw-e2 (rama research/…), enum_v2.py/desc.py.

### R1 — Cerrar D3: respuesta de Codex y registro de propiedad por pista

OBSERVADO: DECISIONS.md:43-47 D3 EN CURSO; CODEX_MSG_01.txt enviado con D1-D3 y 4 preguntas; CODEX_REPLY_01.txt = 0 bytes. Trabajo: obtener respuesta de Codex (objeciones a D1/D2/D3, reparto, lista de 'completo'), registrar en DECISIONS.md qué pista posee cada agente (Claude: V5->M1->M2/M3 spec; Codex: ingestión/features/backtest/paper en repo) y resolver la colisión de nombre 'D1' (ancla lead_hours en PHASE_2E vs coordenadas en DECISIONS.md) renombrando una de las dos. Si Codex objeta D1 -> V5.3.

- **Criterio de hecho:** CODEX_REPLY_01.txt no vacío y DECISIONS.md contiene una entrada D3 con estado ADOPTADA, tabla owner->ítems de este roadmap y nota de desambiguación 'D1-coords' vs '2E-D1-anchor'.
- **Corrección/nota (crítica):** Codex sin cuota hasta 2026-10-05 (usage_limit_exceeded). Reparto bajo D5: Claude ejecuta todo con refutador adversarial; colisión de nombres D1 (PHASE_2E vs DECISIONS) sigue vigente → R25.

### R2 — Alinear v5uni.py y §14 con D1 antes de que vuelva la cuota (V5.3 si procede)

OBSERVADO: v5uni.py:6 carga req_lat/req_lon de MODELSEL_GEOVAL_V3_SAMPLE.json (coords IEM) y :42-43 usa OurAirports para el resto; D1 (DECISIONS.md:19-23) prohíbe IEM como posición y relega OurAirports a control; PREREG_MODELSEL_V5.md:218-219 §14 sigue diciendo 'Coordenadas: OurAirports'. Además el vigilante PID 8074 no encadena v5run.sh (línea de comando observada). Trabajo: reescribir v5uni.py para leer STATION_COORDS_SNAPSHOT_v1.json, emitir enmienda V5.3 al §14 con nuevo hash, actualizar V5_STATUS.md a V5.2/V5.3 y D4, y añadir a v5run.sh una validación de 2-3 pares antes de las 4000 peticiones. NO lanzar ninguna petición a Open-Meteo.

- **Criterio de hecho:** `grep -n SNAPSHOT /Users/mariaaleu/pmw-e2/v5uni.py` devuelve la carga del snapshot y no hay referencia a req_lat de V3_SAMPLE; PREREG_MODELSEL_V5.md §14 cita STATION_COORDS_SNAPSHOT_v1 y PREREG_MODELSEL_V5.sha256 coincide con el fichero; V5_STATUS.md menciona v5extract.py, 4000 peticiones y el hash vigente.
- **Corrección/nota (crítica):** v5uni.py alineado con snapshot; V5.3 emitida (e8302dc1…). Queda smoke de 3 pares en v5run.sh (añadido) y V5_STATUS.md (actualizado).
- **Bloqueo:** Ventana: debe completarse antes de que quota_watch.sh imprima CUOTA_RESTABLECIDA (~2026-09-06); no consultar Open-Meteo.

### R3 — Reconciliar hashes de muestras V2/V3 y documentar método de hashing

OBSERVADO: MODELSEL_GEOVAL_V3_SAMPLE.json declarado 7a57ce0a... (V3 report:5, V4:4, PREREG V5:52) vs disco 6e253e38...; MODELSEL_ASOF_V2_SAMPLE.json declarado a0157ed7... vs disco 29464fbb...; ningún .py del directorio usa hashlib. Trabajo: determinar el objeto hasheado, re-declarar hashes en un addendum (sin reescribir informes congelados) y añadir un script hash_manifest.py que genere .sha256 de todos los artefactos JSON.

- **Criterio de hecho:** Existe ~/pmw-e2/HASH_RECONCILIATION.md explicando la discrepancia y un manifest.sha256 cuyo `shasum -a 256 -c` pasa para todos los ficheros listados; el informe V5 citará solo hashes verificables.
- **Corrección/nota (crítica):** D8: hashes V2/V3 no reproducibles → hash de disco canónico. Snapshot v1.0 (ebe21014…) reconstruido bit a bit; v1.1 = 071b142c…. Documentar método de hashing (sha256 del fichero) en cada .sha256.

### R4 — Ejecutar V5.2/V5.3 al restablecerse la cuota (sin sortear 429)

OBSERVADO: v5run.sh encadena v5extract -> v5uni -> v5eval; v5extract reanudable, 429 -> SystemExit(3); V5_EXTRACT.json/V5_EVAL.json no existen; PREREG V5 §1 limita a rebajar confianza o mostrar homogeneidad. Trabajo: cuando quota_watch.sh termine con 200, lanzar manualmente ./v5run.sh (4000 + ~440 peticiones), relanzar tras 429 intermedios, y producir MODELSEL_V5_REPORT.md con hash.

- **Criterio de hecho:** Existen V5_EXTRACT.json (4000 filas o registro explícito de las faltantes), V5_DATASET.json, V5_EVAL.json y MODELSEL_V5_REPORT.md con .sha256; v5eval.py no se negó por extracción incompleta.
- **Bloqueo:** HTTP 429 Open-Meteo single-runs/historical hasta ~2026-09-06; puerta 'no sortear cuotas'.

### R5 — Clasificar §15 y emitir recomendación M1 (§16)

OBSERVADO: categorías A/B/C/D y opciones M1 1-5 congeladas en PREREG_MODELSEL_V5.md:228-259; D2 dice que M1 se decide con esos criterios; V3 empate práctico (Δ −0.0376, IC incluye 0) y V4 signo invertido a 24h. Trabajo: clasificar el resultado V5, recomendar exactamente una opción (posiblemente dependiente de componente/lead u opción 5), declarar límite de transportabilidad a leads >~45h y registrar M1 en DECISIONS.md. Si sale opción 5, preregistrar la ronda confirmatoria con muestra nueva como sub-ítem.

- **Criterio de hecho:** DECISIONS.md contiene entrada 'M1' con estado ADOPTADA, opción elegida, categoría §15 y modelo(s) por componente/lead que consumirá R15.

### R6 — Higiene de comentarios/docstrings desfasados en el repo

OBSERVADO: database.py:641-642 y :667 'SCHEMA_VERSION stays 2' vs :50 = 3; validate_2b.py:1094-1095 BLOCKER de checkpoint stub-tested anterior a 2C; validate_2c.py:17 idem; config.py:11,19 referencia phase1_5/ inexistente; discovery.py:4-5 'NOT tested/validated' pese a suite verde; PHASE_2B_FINAL_BUNDLE.txt checksums PENDING. Trabajo: corregir textos sin cambiar comportamiento, calcular checksums del bundle o marcarlo como histórico.

- **Criterio de hecho:** `grep -rn 'stays 2' src scripts` vacío; `grep -rn phase1_5 src` vacío; pytest sigue 127+ passed; PR mergeado.

### R7 — Registro de estaciones en el repo: coordenadas D1, ICAO variable en el tiempo, tz y exclusiones

OBSERVADO: el repo no define coordenadas (config.py:103 única mención; DEFAULT_CITY_REGISTRY tiene 6 ciudades l.120-181); STATION_COORDS_SNAPSHOT_v1.json (55 estaciones, sha ebe21014...) vive fuera de git; cambios de ICAO París LFPG->LFPB 2026-04-19 y Taipei RCTP->RCSS 2026-04-05 (CATALOG_V2 v3); HK (1859) y Taipei (77) sin ICAO; STATIONS_TZ.json solo 28. Trabajo: tabla station_registry (icao, city, lat, lon, source, status, valid_from/valid_to, tz, settlement_source) cargada desde el snapshot vía migración v4 o fichero de datos versionado; resolver ICAO por (city, fecha); marcar HK/Taipei como sin ruta METAR.

- **Criterio de hecho:** `SELECT count(*) FROM station_registry` = 55 con 53 CANONICA + 2 EXCEPCION_ABIERTA; test que resuelve ('Paris','2026-05-01')->LFPB y ('Paris','2026-03-01')->LFPG pasa; tz definida para las 55.
- **Corrección/nota (crítica):** 54 CANONICA + 1 EXCEPCION_ABIERTA (OPKC). Registrar alcance de verificación: 11/55 observadas, 43 por inferencia declarada; KBKF no verificable (DDMM).

### R8 — Implementar el ancla 2E: T = endDate − lead_hours y target_date por día civil de estación (cerrar P1)

OBSERVADO: PHASE_2E_LEAD_HOURS_ANCHOR.md RATIFIED sin código (:5, :131); endDate solo en markets.source_timestamps JSON (discovery.py:129-131,158); strategy_a/features reciben prediction_time y target_date del caller (2D §C); Wellington endDate 12:00Z = medianoche civil (2E:135-137). Trabajo: helper prediction_time_for(market, lead_hours) y target_date_for(market, station_registry) con test de Wellington; sonda P1 sobre CATALOG_V2 (distribución de endDate por ciudad) documentada; columna derivada o vista sin borrar datos.

- **Criterio de hecho:** tests/test_lead_hours_anchor.py pasa incluyendo caso Wellington (endDate 12:00Z -> target_date local correcto); PHASE_2E_LEAD_HOURS_ANCHOR.md P1 marcada CERRADA con cifras del catálogo.
- **Corrección/nota (crítica):** P1 CERRADA: endDate = 12:00Z en 93 221/93 221. Añadir tabla de existencia del mercado en T por lead: 20.8 % de eventos creados <48 h antes de endDate (p50 = 55.9 h) → lead_hours ≤ 48 h como máximo operativo; ≤ 24 h seguro.

### R9 — Orquestador de ingestión de precios CLOB + política 429 + sonda P3 + un-skip test_market_asof

OBSERVADO: prices.py (worktree) implementa ventanas <=48h, fidelity=1, upsert transaccional, 429 -> RATE_LIMITED sin escribir, sin backoff ni planificación (:69-70, :97-98); no hay orquestación por token ni registro en dataset_versions/data_quality; test_market_asof.py sigue skip en main; P3 (cotización disponible en T) abierta (2E:106-112). Trabajo: run_prices(dataset_version) que recorre tokens YES/NO del catálogo, ventana open_time->endDate, checkpoint resumible como discovery, backoff exponencial/Retry-After, escritura price_semantics MIDPOINT_ESTIMATED documentada; ejecutar sobre una muestra real y luego el catálogo; sonda P3 medida sobre price_history real.

- **Criterio de hecho:** `SELECT count(DISTINCT token_id) FROM price_history` cubre >=95% de tokens de mercados resueltos del catálogo; test_market_asof.py sin skip y verde; PHASE_2E P3 cerrada con % de mercados con cotización en T por lead; informe de ingestión con tasa de 429 y reintentos.
- **Corrección/nota (crítica):** Quitar "un-skip test_market_asof" (ya hecho en la rama). Añadir verificación de puntos en frontera de ventana (prices.py:83). Rate limits CLOB: medir, no suponer.
- **Bloqueo:** Rate limits de CLOB desconocidos (no documentados); no sortear.

### R10 — Poblar la DuckDB operativa con el catálogo real y re-validar 2B con evidencia versionada

OBSERVADO: no existe data/processed/weather_agent.duckdb; CATALOG_V2.duckdb (93221 mercados) es investigación sin ingerir en markets/outcomes; el único run real de validate_2b (Actions 2026-08-23) crasheó, corregido en bbf9f1e sin evidencia de re-run; results/ está en .gitignore:51; CATALOG_V2 se obtuvo desde el Mac en 80 s. Trabajo: ejecutar discover() completo (o import auditado de CATALOG_V2 con dataset_version propia) desde el Mac o Actions (decisión Hetzner en decisiones abiertas), re-ejecutar validate_2b/2c con --gamma, y decidir/crear docs/validation/ versionado para informes.

- **Criterio de hecho:** `SELECT count(*) FROM markets` ≈ 93k y `outcomes` ≈ 186k en weather_agent.duckdb; docs/validation/PHASE_2B_VALIDATION_REPORT.md y PHASE_2C_VALIDATION_REPORT.md con veredicto VALIDATED y hash, commiteados vía PR.

### R11 — Resolver semántica de fees y modelo de coste efectivo (edge_net)

OBSERVADO: 84451 mercados con feeSchedule {rate 0.05, takerOnly, rebateRate 0.25} y makerBaseFee/takerBaseFee=1000 (CATALOG_V2); fees.py:23-27 declara la semántica no documentada; effective_from/to siempre None; config.FEE_CONFIG.effective_cost_components no se consume; strategy_a.py:251,265 net BLOCKED. Trabajo (Claude): documentar con fuentes públicas de Polymarket la fórmula de fee taker en función del precio y confirmar unidades; derivar épocas de fees desde el catálogo. Trabajo (Codex): módulo costs.py que calcule taker_fee, spread_cost estimado y produzca edge_net; poblar effective_from/to.

- **Criterio de hecho:** DECISIONS.md entrada 'FEES' ADOPTADA con fórmula y fuente; tests/test_costs.py verde; predictions.edge_net no NULL para mercados KNOWN; fees_disabled -> edge_net = edge_gross.

### R12 — SettlementOperator: protocolo, migración de probability/features y operadores por fuente

OBSERVADO: PHASE_2E_SETTLEMENT_OPERATOR_DESIGN.md (untracked) declara unsafe el redondeo implícito de probability.py:89-94 y exige operador obligatorio (:5-17, :43-50); HKO floor 164/166 con 2 excepciones (HKO_OPERATOR_TEST.json); WU/NOAA (85.6% del catálogo) sin operador establecido; CWA inaccesible; 2D fija p_weather LOCKED (2D:82-93) lo que colisiona. Trabajo (Claude): auditoría empírica del operador WU/NOAA usando bandas ganadoras de CATALOG_V2 vs Tmax IEM (datos ya en disco, sin Open-Meteo), preregistrada; decisión ambos sobre desbloquear LOCKED. Trabajo (Codex): clase SettlementOperator, distribución continua, argumento obligatorio en build_feature y generate_event_signals, operador de prueba en tests, exclusión fail-closed sin operador.

- **Criterio de hecho:** `grep -rn SettlementOperator src` muestra uso en features.py y strategy_a.py; tests verdes con operador de prueba; docs/research/SETTLEMENT_OPERATOR_AUDIT.md con tasa de compatibilidad por fuente y hash; DECISIONS.md registra operadores adoptados (al menos WU, NOAA, HKO) y los eventos sin operador se excluyen con reason 'no_settlement_operator'.
- **Corrección/nota (crítica):** Operadores por (source, measurement_rule): WU-byForecast, WU-DailyObs, NOAA-TempColumn, NOAA-HourlyData, HKO(floor). Fail-closed sin operador.

### R13 — Ingestión de observaciones (weather_observations) desde IEM y decisión Y_final vs Y_asof_T

OBSERVADO: sin escritor de weather_observations; Y_final definido como max(METAR cuerpo, °C entero) por día civil local vía IEM (PREREG_MODELSEL.md:22-24); Y_asof_T no reconstruible (RECORD_VERSION_ASOF_AUDIT.md:68-71); alternativas A/B/C de REVISION_IMPACT_AUDIT.md:74-85 sin registrar; MTARCH_COVERAGE 25/52. Trabajo (Claude): registrar decisión Y para entrenamiento/evaluación y política available_at de observaciones (fail-closed: available_at = fin del día civil + latencia documentada), preregistrada. Trabajo (Codex): ingest/observations.py sobre IEM asos.py con dataset_version, provenance, sin usar en features (solo labels/errores); no depende de Open-Meteo.

- **Criterio de hecho:** DECISIONS.md entrada 'Y_LABEL' ADOPTADA; `SELECT count(*) FROM weather_observations` cubre los station-days del catálogo con METAR (>=50 estaciones, 2026-03..2026-09); test que verifica available_at > target_date fin de día local pasa.
- **Corrección/nota (crítica):** Decisión Y_final vs Y_asof_T → D-pendiente; alternativas A/B/C de REVISION_IMPACT_AUDIT §74-85.

### R14 — Pipeline de labels: generación masiva y persistencia con join features<->labels

OBSERVADO: labeling.build_label es pura sin pipeline ni tabla (labeling.py:31-63); único consumidor tests; label es 'Yes'/'No' por market, no banda ganadora por evento; 47 'proposed' + 33 sin umaResolutionStatus en el catálogo. Trabajo: labels por market y por evento (winning band vía event_winning_band) desde markets.winning_outcome/resolution_timestamp, cotejados con weather_observations cuando exista operador; tabla labels o columnas en features; exclusión explícita de no resueltos.

- **Criterio de hecho:** Tabla/vista labels con una fila por (market_id, dataset_version) para todos los mercados resolved; test que comprueba que ningún label tiene resolution_timestamp <= prediction_time cuando se une a features.

### R15 — Ingestión de forecasts Open-Meteo (weather_forecasts) con available_at fail-closed y plan de cuota

OBSERVADO: no existe cliente Open-Meteo en el repo (solo config.py:42,99-107); tests/test_weather_asof.py skip; F3: available_at PARTIAL desde 2026-06-03 y UNKNOWN 2026-04-02..06-02, L_max icon 4.76h/gfs 6.93/ukmo 10.48/ecmwf 8.78 (F3-CLOSURE-REPORT.md:51-59); cuota diaria compartida agotada (429); cell_selection=land no preregistrado (ARCH:446). Trabajo (Claude): spec preregistrada: modelos según M1, issue_time explícito (Single Runs), available_at = issue_time + L_max_modelo (fail-closed), cell_selection/elevation fijados, presupuesto de peticiones (55 estaciones × días × runs) y periodo utilizable (>=2026-06-03). Trabajo (Codex): ingest/weather.py con backoff, reanudable, dataset_version/provenance, sin sortear 429; un-skip test_weather_asof.

- **Criterio de hecho:** docs/research/PREREG_FORECAST_INGEST.md con hash; `SELECT count(*) FROM weather_forecasts WHERE available_at IS NOT NULL` > 0 para las 53 estaciones canónicas en el periodo declarado; test_weather_asof.py sin skip y verde; log de ingestión con 0 elusiones de 429.
- **Bloqueo:** HTTP 429 Open-Meteo; presupuesto diario insuficiente para escala completa sin plan de cuota (decisión abierta).

### R16 — M2: weather_errors y derivación de cuantiles p10..p90 (preregistrado)

OBSERVADO: la tabla weather_errors (station/model/lead_hours/month, q05..q95) no tiene escritor ni lector; features.py consume forecast_p10..p90 pero Open-Meteo entrega temperature_2m determinista (INFERIDO: hace falta modelo de error); M2/M3 prohibidos hasta cerrar M1 (PREREG V5:275); semántica de weather_errors.lead_hours pendiente (2E:132-133). Trabajo (Claude): PREREG_M2 (walk-forward por tiempo, error = obs − forecast con operador de settlement, cuantiles por station/model/lead/mes con mínimos de muestra, fallback jerárquico). Trabajo (Codex): errors.py que escribe weather_errors y forecast_p10..p90 en weather_forecasts como filas derivadas (record_version nuevo, sin borrar).

- **Criterio de hecho:** PREREG_M2.md hasheado antes de la primera ejecución; `SELECT count(*) FROM weather_errors` > 0; test que verifica que los cuantiles usan solo observaciones con available_at < fecha de cálculo; informe M2 con cobertura por estación/lead.
- **Corrección/nota (crítica):** Definir discriminador de filas derivadas en weather_forecasts (PK sin discriminador) antes de escribir cuantiles.

### R17 — Persistir features y corregir filtros (dataset_version, token YES) + validar no-look-ahead sobre datos reales

OBSERVADO: build_feature devuelve dict sin insertar en features (features.py); consulta de precio por market_id toma prices[0] sin token_id (l.74-87) y no filtra dataset_version (l.74-82, l.97-105); strategy_a lo compensa con guard (l.203-217). Trabajo: build_feature(token_id YES explícito, dataset_version obligatorio, operador), upsert en features con no_lookahead_verified, y ejecución de validate_2c --gamma más un harness sobre price_history/weather_forecasts reales (cierre real de Blocker 2 de 2C).

- **Criterio de hecho:** `SELECT count(*) FROM features WHERE no_lookahead_verified` > 0 sobre datos reales; tests adversariales pasan con dataset_version múltiple en la misma DB; docs/validation/PHASE_2C_B2_VALIDATION_REPORT.md VALIDATED.

### R18 — Preregistro del backtest y de parámetros Strategy A (tau, tolerancias, segmentación)

OBSERVADO: tau, weather_sum_tolerance, market_sum_min/max OPEN (2D:393-394); segmentación epoch/template OPEN (:395); metodología/ventanas/métricas OPEN (:396); 2D §P/W.10 fijan unidad=evento, walk-forward temporal, Brier/log-loss. Trabajo: PREREG_BACKTEST_A.md: universo (mercados resueltos con operador, cotización en T, forecast as-of), leads, grid de tau OOS, ventanas walk-forward, métricas brutas y netas, criterios de éxito/fracaso, política de exclusión y de HK/Taipei.

- **Criterio de hecho:** PREREG_BACKTEST_A.md con .sha256 commiteado antes de cualquier ejecución del motor; DECISIONS.md registra el hash.

### R19 — Motor de backtest walk-forward que escribe backtest_results

OBSERVADO: backtest_results solo aparece en database.py; no hay productor; Strategy A no hace PnL ni backtest (strategy_a.py:3-6). Trabajo: backtest.py que itera eventos por T=endDate−lead (R8), llama generate_event_signals con operador y tau del preregistro, une con labels, calcula Brier/log-loss/PnL bruto y neto (fill hipotético a precio INDICATIVE con spread modelado de R11), segmenta por epoch/template/estación, y escribe backtest_results con walk_forward_config y parameters.

- **Criterio de hecho:** tests/test_backtest.py verde con datos sintéticos y determinismo; `SELECT count(*) FROM backtest_results` > 0 tras un run real; cada fila referencia el hash del preregistro.

### R20 — Sizing y edge_net en la señal (desbloquear 'DO NOT IMPLEMENT YET' de 2D)

OBSERVADO: 2D §V (:228-235) pospone net_edge y sizing; DEFAULTS bankroll/sizing en config.py:202-211 sin consumidor; signals.net_edge NULL. Trabajo: sizing fraccional preregistrado (p.ej. Kelly fraccional acotado) sobre edge_net, escribir signals.net_edge y size, con tests; no ejecuta nada.

- **Criterio de hecho:** signals.net_edge y size no NULL para señales BUY/FADE en un run real; test que verifica size=0 cuando edge_net<=0; documento de sizing preregistrado.

### R21 — Ejecutar backtest real, calibrar tau OOS y publicar informe de validación de Strategy A

OBSERVADO: validate_2d.py:286 validated=False por diseño; ningún PHASE_*_VALIDATION_REPORT existe en el repo. Trabajo: correr R19 según R18 sobre el catálogo real, seleccionar tau en ventana de calibración y evaluar en ventanas posteriores, reportar por epoch/template/estación, declarar Strategy A VALIDATED o NOT VALIDATED, y especificar M3 (Claude) en función del resultado.

- **Criterio de hecho:** docs/validation/PHASE_2F_STRATEGY_A_BACKTEST_REPORT.md con hash, veredicto explícito, tau adoptado registrado en DECISIONS.md y tabla de métricas OOS; el veredicto no se declara VALIDATED si falla algún criterio del preregistro.

### R22 — Colector forward-only (orderbook/trades) y verificación de CLOB_WS_URL

OBSERVADO: CLOB_WS_URL=None UNVERIFIED (config.py:46,90-98); orderbook_snapshots/trades sin escritor; 2A decisión 5 y 2B decisión 6 lo difieren al 'live collector'; collector_session_id previsto (2A:316-320). Trabajo: verificar endpoint websocket o usar polling REST del book; collector.py con sesiones, persistencia append-only, reconexión; ejecutar en máquina decidida (ver decisiones abiertas).

- **Criterio de hecho:** config.CLOB_WS_URL documentado como VERIFIED o política polling adoptada; `SELECT count(*) FROM orderbook_snapshots` y `trades` > 0 tras 24h de colector; test de reanudación de sesión verde.
- **Bloqueo:** URL websocket sin verificar; requiere host con proceso persistente.

### R23 — Motor paper: paper_trades con SIMULATED_EXECUTABLE y comparación paper vs backtest

OBSERVADO: paper_trades y seq_paper_trades existen sin escritor; price_layer SIMULATED_EXECUTABLE previsto (2A:77,324-325); 2D pospone motor paper. Trabajo: paper.py que consume signals en tiempo real (T según R8, forecasts as-of reales, cotización del colector), simula fill contra el book observado con fees de R11, registra paper_trades y liquida con labels; sin wallet ni órdenes reales.

- **Criterio de hecho:** tests/test_paper.py verde; en un run real `SELECT count(*) FROM paper_trades` > 0 con price_layer='SIMULATED_EXECUTABLE'; ninguna dependencia de claves/wallet (grep API_KEY/SECRET vacío).

### R24 — Corrida paper preregistrada de N días y veredicto COMPLETO

Trabajo: preregistrar (Claude) duración, universo, tau, criterios de éxito y de parada; ejecutar (Codex) el pipeline completo diario (catálogo incremental -> precios -> forecasts as-of -> señales -> paper) durante N días sin intervención; informe final comparando PnL paper vs backtest esperado, calibración, exclusiones y tasas de 429/fallos; decisión conjunta de COMPLETO. INFERIDO: N>=14 días para cubrir varias ventanas de forecast.

- **Criterio de hecho:** PREREG_PAPER_RUN.md hasheado antes del inicio; docs/validation/PAPER_RUN_REPORT.md con N días completos, sin días perdidos no justificados, y DECISIONS.md con entrada 'COMPLETO' (ADOPTADA o NO, con causas) firmada por Claude y Codex; pytest sin skips.
- **Bloqueo:** Requiere cuota Open-Meteo diaria sostenida y host persistente.

### R25 — Nomenclatura: fases 2E/2F/2G y desambiguar "D1"

"2E" designa hoy dos documentos no relacionados (lead_hours RATIFIED; SettlementOperator untracked) y "D1" colisiona (ancla temporal en PHASE_2E vs convención de coordenadas en DECISIONS). Fijar: 2E = ancla temporal + registro de estaciones; 2F = ingestión; 2G = M2/backtest; 2H = paper. Renombrar la decisión de coordenadas como D1-COORD en los documentos nuevos.

- **Criterio de hecho:** Un índice de fases en el repo (PHASES.md) con la correspondencia y los documentos apuntando a él.

### R26 — Descubrimiento de mercados ABIERTOS + markets.available_at para paper

discovery.py:435 fija closed=true: sólo descubre mercados cerrados. El modo paper necesita mercados con endDate futuro, descubiertos cada día, con available_at = instante de descubrimiento (captura prospectiva, alternativa C de REVISION_IMPACT_AUDIT).

- **Criterio de hecho:** discover(open=True) persiste mercados abiertos con available_at no nulo; test con fixture Gamma abierta; R23 lo consume.

### R27 — Migración de esquema v4 explícita

station_registry (coordenadas D1 con valid_from/valid_to, alcance de verificación), tabla labels, linaje paper_trades↔signals, columna de hash de preregistro en backtest_results.

- **Criterio de hecho:** MIGRATIONS v4 idempotente; test_database verde; comentarios "SCHEMA_VERSION stays 2" corregidos (R6).

### R28 — Plan de cuota Open-Meteo (decisión con owner y criterio)

La cuota diaria compartida (single-runs + historical) se agota con ~4-5k peticiones ponderadas. Ingestión a escala (55 estaciones × meses × runs × modelos) no cabe. Opciones: (a) reducir universo/periodo, (b) espaciar en días con reanudación, (c) clave de pago Open-Meteo, (d) captura prospectiva diaria (pocas peticiones/día). Decidir y registrar.

- **Criterio de hecho:** Decisión Dn en DECISIONS.md con presupuesto diario, prioridad de extracción y política ante 429; R15/R16/R24 la referencian.

## 4. Decisiones abiertas (a registrar en DECISIONS.md conforme se tomen)

- M1 (modelo de forecast): no seleccionado; V5 solo puede rebajar o mostrar homogeneidad (PREREG V5 §1); posible resultado 'dependiente de componente/lead' u 'opción 5 continuar', que exigiría otra ronda confirmatoria y retrasa R15/R16.
- Plan de cuota Open-Meteo: la cuota diaria compartida está agotada (429) y la ingestión a escala (55 estaciones × meses × runs) no cabe en la cuota gratuita observada; decidir entre reducir universo/periodo, espaciar en días, o contratar plan de API (gasto, no 'dinero real' de trading, pero requiere aprobación del usuario). Nunca sortear el 429.
- SettlementOperator vs p_weather LOCKED: adoptar el diseño untracked invalida el p_weather de 2D (LOCKED en 2D:82-93) hasta disponer de operadores auditados; decidir si se desbloquea y qué fuentes (WU/NOAA ~85.6%, HKO con 2 excepciones, CWA inaccesible) quedan dentro del universo.
- Y para entrenamiento/evaluación: Y_final (retrospectivo, IEM) vs Y_asof_T (no reconstruible); alternativas A/B/C de REVISION_IMPACT_AUDIT.md:74-85 sin registrar; afecta a R13/R16 y a la interpretación as-of del backtest.
- Periodo utilizable as-of: available_at UNKNOWN 2026-04-02..06-02 (F3); si se exige as-of estricto, entrenamiento/backtest se restringe a >=2026-06-03 (INFERIDO: ~3 meses de datos).
- Semántica de fees: makerBaseFee/takerBaseFee=1000 vs feeSchedule rate 0.05/rebate 0.25; sin confirmación no hay edge_net, sizing ni PnL neto (R11).
- Coordenadas D1: premisa 'NOAA = sensor' no verificada; OPKC (1551 mercados, ΔT 2.8 °C) y WSSS abiertas; 40/55 sin ARP; cell_selection (land por defecto) y política de elevation sin preregistrar.
- Universo: incluir o excluir Hong Kong (1859 mercados, HKO, sin METAR) y Taipei (77, sin ICAO/operador); mercados 'proposed' (47) y sin umaResolutionStatus (33).
- Infraestructura de ejecución: Hetzner (trader@..., pertenece a cmle-bot, SSH puerto 443, ningún uso PMW evidenciado) vs Mac local (CATALOG_V2 en 80 s) vs GitHub Actions (único run real, sin proceso persistente); necesaria para colector forward-only y paper run.
- Dónde vive la evidencia de validación: results/ está en .gitignore:51 y ningún informe está versionado; propuesta docs/validation/ con hashes (requiere decisión ambos).
- Acceso a Wunderground: fuente contractual de 79757 mercados sin acceso programático; decidir si IEM/METAR se acepta como proxy con auditoría de compatibilidad (R12) o si se busca otra vía.
- CLOB_WS_URL: sin verificar (config.py:46); decidir websocket vs polling REST para el colector (R22).
- Nomenclatura de fases: '2E' designa hoy dos documentos no relacionados (lead_hours RATIFIED y SettlementOperator untracked) y 'D1' colisiona entre PHASE_2E y DECISIONS.md; fijar numeración 2E/2F/2G alineada con este roadmap.
- Rate limits de CLOB /prices-history: no documentados en el repo; el orquestador R9 necesita una política de cuota antes del backfill completo (~186k tokens × ventanas 48h).
- Valores de tau y tolerancias de Strategy A y metodología de calibración OOS: OPEN en 2D:393-396; deben preregistrarse (R18) antes de cualquier backtest real.

## 5. Orden de ejecución inmediato (Claude, D5)

1. **R4** en cuanto la cuota vuelva (vigilante activo) → **R5** M1.
2. Mientras tanto, sin cuota: **R25** (nomenclatura), **R28** (plan de cuota — decisión), **R7+R27** (registro de estaciones + migración v4), **R8** (ancla temporal + tabla de existencia por lead), **R26** (descubrimiento abierto), **R6** (higiene).
3. Después: R10 → R9 → R13/R14 → R12 → R11 → R15/R16 → R17 → R18 → R19 → R20 → R21 → R22 → R23 → R24.

Cada ítem evaluativo (R4, R16, R18/R21, R24) lleva preregistro hasheado antes de ejecutarse (D0).
---

## 6. Delta 2026-09-06 (estado tras la madrugada de la sesión B)

| Ítem | Cambio de estado | Evidencia |
|---|---|---|
| R4 | **HECHO** — V5 ejecutada 07:22–07:37 UTC (`v5run2.sh`, 1 200/1 200) | D9 (sesión B) |
| R5 | **HECHO** — categoría B; **M1 = icon_seamless ADOPTADO** por regla §17 congelada; V5.4 retirada (frescura = latencia, V2 §2) | D10, D11, D12; sesión A concurre en D13 |
| R7 | **HECHO por B** — `stations.py` + `data/station_coords_v1.json` (v1.1, hash congelado, `VERIFIED_SENSOR`=11) | `feat/ingest-2b@dcbad88` |
| R27 | **APARCADO** — tabla DB con `valid_from/valid_to` innecesaria en el periodo | D14 |
| R9, R15 | **EN CURSO por B** — `prices.py` (286 l.), `weather.py` (364 l., M1, `available_at = issue + L_max`, guardia de horas pico), tests reales | `feat/ingest-2b@c56de9c`, `scripts/backfill_prices.py` untracked |
| R8 | **PARCIAL** — P1 cerrada; tabla de existencia por lead; falta preregistrar el rango de `lead_hours` | `R8_LEAD_EXISTENCE.json`, D9-bis |
| OPKC | **RESUELTA** por AIP Pakistán; snapshot v1.2, 0 excepciones | D14 |
| R26, R6, R25 | **EN CURSO por A** — workflow `wf_a45d52e2-88a` en worktree `feat/r26-open-discovery` | — |
| R28 | **DECIDIDO** — captura prospectiva diaria; sin clave de pago sin el usuario | D9-bis |

**Reparto vigente (D13):** B → ingestión (R9/R10/R15) y M2 (R16); A → R26/R6/R25, R8, roadmap/tareas, preregistros.
**Regla:** cada sesión en su propio worktree; nunca cambiar la rama del workspace canónico; sólo anexar en `DECISIONS.md`.
| R26, R6, R25 | **HECHO** — `feat/r26-open-discovery`, PR #1, 143/4; revisión adversarial con 6 correcciones | D16 |
| R11 | **EN CURSO por A** — investigación de la semántica de fees + propuesta de modelo de coste preregistrado | workflow |
| PR #1 | **FUSIONADO** (`dfdc73e`), 143/4 en `main`; B debe rebasar `feat/ingest-2b` | D18 |
| R11 | **HECHO** — `FEES_SEMANTICS.md` (sha 4dbad3ab…), modelo de coste H1 + sensibilidad H2/H3; refutado | D19 |
| R18 | **EN CURSO por A** — preregistro del backtest (workflow con 2 refutadores) | — |
