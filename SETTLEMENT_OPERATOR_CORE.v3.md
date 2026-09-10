# SETTLEMENT_OPERATOR_CORE.md — v2 (final)

**Propósito único:** qué operador aplicar a cada mercado y cuándo fallar cerrado, para R14 (labels) y R17 (features). De `SETTLEMENT_OPERATORS_SPEC.v3.md` (`f6fcd2e4…`, borrador vivo) por **A-24**; no eleva categorías e2e (las de componente, en su fila).
**Anclas:** `DECISIONS.md` **`8b1b0f3e…`** = `DECISIONS.sha256`; **D0–D17, D9-bis, D19–D22 (D18 no existe), A-23…A-27**; `D21` por sesión.
**Cifras:** recómputo 2026-09-08, `CATALOG_V2.duckdb` `8fc07207` (`read_only=True`). Evidencia (sha): PREREG_E2 c7f031ec · E2R ec500428 · DISCRIM 9d925bf3 · HKO 093e5891 · TARGET_DATE c63060b1 · STATION_TZ 35d68e65 · SAMPLE_E2 28af1b79 · GEOVAL 6e253e38.

## 1. Objeto y alcance

Para los **93.221 mercados / 8.557 eventos**: estrato, `SettlementOperator` (ventana; agregación; cuantización; serie) y `reason` de fallo cerrado. **NO decide:** p_weather ni la CDF (v3 §1.4, §3.1); 2D §F/§L/§V; fees (D19); **el preregistro de validación y su criterio de aceptación (pospuestos, A-24)**; migración ni rule-map (v3 §5). §6 fija qué es out-of-sample (fallo cerrado), no promoción.
**No sustituye el label de pago**: ése es `winning_outcome` (`labeling.build_label`, gate `prediction_time < resolution_timestamp`; código, no D17). De D17 viene el etiquetado por fuente contractual: proxy sólo con auditoría declarada y `label_source`/`contract_source`/`compat_status`. `settle()` como target de M2: **DP-D17y**.

## 2. Interfaz (sin implementar)

```
SettlementOperator: operator_id, version, unit, window_kind, aggregation, quantization, required_series
  applies_to(contract_source, measurement_rule_code, unit, rounding_rule) -> bool   # PURA en esos 4
  settle(obs, ctx, asof) -> SettlementResult
Observation: ts_utc, value, unit, series, available_at|None, record_version
MarketContext: market_id, event_id, contract_source, measurement_rule_code, unit, rounding_rule,
  target_date, station_icao|None, station_tz|None, clause_lowest_bracket, fail_closed_reason|None
SettlementResult: band_key, settled_value, n_obs, unit, window_start_utc, window_end_utc, asof (nulables),
  window_kind{LOCAL_CIVIL_DAY,SOURCE_DAILY_ROW}, aggregation{MAX,SOURCE_DAILY}, contract_source,
  quantization{INTERVAL_FLOOR,NONE}, availability{ASOF_VERIFIED,Y_FINAL_UNKNOWN_ASOF}, label_source,
  compat_status{DIRECT,PROXY_AUDITED}, clause_lowest_bracket, audit. v3 §4.4
```
- `Unit{C,F}`; `Series{hko_clmmaxt, metar_body_c, metar_tgroup_tmpf}`; NEAREST fuera (§3 b); otra conducta ⇒ otra `version`; `…Unavailable` no deriva de `ValueError`; `market_id`/`event_id` sólo linaje; `record_version` D17-C; `contract_source` por D17.
- **Estación no nula sii `window_kind == LOCAL_CIVIL_DAY`** (5,7,8); no con `SOURCE_DAILY_ROW` (10). **Pureza:** `applies_to` invariante al `market_id`.
- **`Source`:** el `ctx` lo produce el parser de D21 (`polymarket/resolution.py`): enum `{WU,NOAA,HKO,CWA,UNKNOWN}`, **divergente de `v3.primary_source` en los 77 de Taipéi** (`SIN_CLAUSULA`/`P_UNKNOWN` vs `CWA`/`P_CWA_TemperatureColumn`; los otros seis, idénticos): la fila 11 lista ambas ternas con el mismo `reason`.
- **`target_date`: el núcleo NO lo deriva** (2D §C, B2 DECIDED-V1): **parámetro del caller**, fail-closed si falta. **Contradicción declarada, a tramitar por 2D §V:** A-25 decía «no viola 2D §C» y A-26 lo corrigió a medias; **A-27 cierra el punto**: §C prohíbe `question`, **`slug`** y **`description`** —las dos vías— y no ofrece ninguna fuente («no existe campo estructurado»), luego el contrato es insatisfacible tal como está y la contradicción es de 2D, no de la lectura. Queda como **evidencia** de constructibilidad al 100 %: slug `-<month>-<day>[-<YYYY>]` vs `on <D> <Mon> '<YY>`, mes+día **93.221/93.221** (0 disc.), año en **93.088** y **vía única** en **133** (77 de 2025-12, 56 de 2026-01). De `endDate`: **440** con el día equivocado.
- **As-of:** con `asof` no nulo y algún `available_at is None` ⇒ `observations_not_available_asof`; `asof is None` ⇒ `availability='Y_FINAL_UNKNOWN_ASOF'`. **OBSERVADO:** `available_at` es `None` en todo el histórico IEM ⇒ ruta **hoy cerrada al 100 % en 5, 7 y 8**.

## 3. Tabla de habilitación

Partición de los **93.221** por `(contract_source, measurement_rule_code, unit)` de `v3`: **11 clases excluyentes y exhaustivas**, 0 nulos; la terna fija `rounding_rule` (*tenths* en 10-11, resto *whole degree*). Cláusula lowest-bracket transversal, no de la partición; ningún evento cruza estratos; Σ ev. = **8.557**.
**HABILITADO ⟺ FAIL_CLOSED:** **(0)** el contrato ha de definir Y como **observación de fuente accesible** — no lo hacen 1-2 (Y indefinida), 3-4 (pronóstico) ni 11 (inaccesible), y ninguna auditoría las habilita; superado (0), **(i)** ≥1 auditoría preregistrada *sin cláusula* con `k/n` e IC Wilson y **(ii)** ningún componente bloqueante (UNKNOWN/INFERIDO/NO_SEPARABLE) **sin calificar aquí**. Fallan (0) 1-4 y 11; (i) la 6 (n=0); (ii) la 9.

| # | contract_source / measurement_rule_code / unit | Merc. | Estado |
|---|---|---|---|
| 1-2 | WU / P_WU_GENERIC_sin_calificador / C, F | 26.763 + 8.459 | FC |
| 3-4 | WU / P_byForecast / C, F | 25.982 + 9.500 | FC |
| 5 | WU / P_WU_DailyObservations / C | 6.996 | **HP** |
| 6 | WU / P_WU_DailyObservations / F | 2.057 | FC |
| 7-8 | NOAA / P_NOAA_TempColumn / C, F | 9.966 + 121 | **HP** |
| 9 | NOAA / P_NOAA_HourlyData / F | 1.441 | FC |
| 10 | HKO / P_HKO_AbsDailyMax / C | 1.859 | **H** |
| 11 | SIN_CLAUSULA / P_UNKNOWN / C (v3) ≡ **CWA / P_CWA_TemperatureColumn / C** (D21) | 77 | FC |
| | **Σ** | **93.221** | 1.722 ev. con operador, 6.835 sin |

FC = FAIL_CLOSED · HP = HABILITADO_CON_PROXY · H = HABILITADO. **Habilitados** (ventana; agregación; cuantización; serie · n·k/n·IC · cat. · `validation_state`):
- **5** `WU_DAILYOBS_C_PROXY_IEM v1` y **7** `NOAA_TEMPCOL_C_PROXY_IEM v1` — LOCAL_CIVIL_DAY; MAX; **NONE**; `metar_body_c` · 7·7/7·0,646–1,0 y 16·16/16·0,806–1,0 (no prereg 8/9; 322448 abierta) · (a) · `quantization` **UNKNOWN** (v3 §2.2), calificado: en `metar_body_c` entero FLOOR ≡ NONE (`n_disc = 0`) ⇒ **NO_DECIDIBLE permanente**.
- **8** `NOAA_TEMPCOL_F_PROXY_IEM v1` — LOCAL_CIVIL_DAY con **`window` NO_SEPARABLE_EN_MUESTRA** (H_LOCAL=H_UTC 6/6, n_disc=0 en EE.UU./°F; **DP-W1 NO ratificada**); MAX; **NONE** (b); `metar_tgroup_tmpf` · 6·6/6·0,610–1,0 · (a) · SELECCION_IN_SAMPLE (ventana NO_DECIDIDO).
- **10** `HKO_ABSMAX_INTERVAL_FLOOR v1` — SOURCE_DAILY_ROW; SOURCE_DAILY; INTERVAL_FLOOR; `hko_clmmaxt` · 164/166·0,957–0,997 (ceil/half-up/half-even REFUTADOS) · STRONGLY_SUPPORTED de D17, `label_source`/`compat_status` **DP-D17x no ratificada** · SELECCION_IN_SAMPLE.
- **Cerrados** (UNKNOWN e2e): 9, n=8 y 8/8, pero 0/4 filas separan H_hourly de H_series ⇒ serie **INFERIDA**; 11, 0/7 con valor; resto n=0.
- (a) categoría **del proxy** IEM/METAR (`IEM_METAR`/`PROXY_AUDITED`), no de la fuente contractual, UNKNOWN; la 10 es directa (`HKO_CLMMAXT`/`DIRECT`). (b) **`NONE` como en 5 y 7:** la rejilla de 1 °F la hace la serie IEM; `round()` prohibido.

## 4. Política fail-closed

`settle()` **sii** estrato HP/H **y** ninguna condición de ejecución; si no, `…Unavailable(reason)` + `markets_excluded` (`stage='feature'`, sin schema nuevo) y **fuera de features, labels M2, backtest y entrenamiento**. **Sin operador por defecto** (nearest-integer de `quantiles_to_distribution` prohibido).
**Orden:** terna → estrato → `ctx` → cláusula → serie/ventana/as-of; el estrato antes que el `ctx`: las filas sin operador mueren por su `reason` (`source_inaccessible` alcanza los **77 mk. / 7 ev.** de la 11). **`ctx`** (habilitados): 5-8 exigen estación — **51 ICAO, 0 nulos, 51/51 con tz** (`missing=[]`); la 10 no, y su `icao2` es NULL en los 1.859, como en los 77 de la 11: **no es defecto**. `target_date` no nulo.
**Enum cerrado.** *Estrato:* `no_settlement_operator:Y_undefined_by_contract` (1,2) · `:by_forecast` (3,4) · `proxy_not_audited_F` (6) · `series_filter_unverified` (9) · `source_inaccessible` (11, ambas ternas) · `clause_stratum_not_audited` (5,7; **0 auditados con cláusula**; la 8 no tiene; la 10 emite flagueada). *Ejecución* (5/7/8/10): `series_mismatch` · `no_observations_in_window` · `observations_not_available_asof`. *Terminal:* **`context_out_of_snapshot`** — terna fuera del §3 o `ctx` no construible, **falta de `target_date` o de texto parseable incluidas**; **0 casos hoy**, alcanzable sólo hacia delante.
**Fuera del enum** (sólo se enumera lo diagnosticable por el operador): `target_date_unresolvable`/`_ambiguous` (del **caller**; llegan como `context_out_of_snapshot`) · `unit_mismatch` (inalcanzable: `applies_to` casa sobre `unit`) · `unit_unknown` · `no_data_clause_possible` (flag) · las dos puertas de p_weather.

## 5. Cobertura

**(i) Partición por estado de `settle`** (`asof=None`), **93.221 = 100 %**: emite label (5,7,8 sin cláusula + 10 entera) **17.072 = 18,31 %** · cláusula (5,7) **1.870 = 2,01 %** · serie sin verificar (9) **1.441 = 1,55 %** · sin operador (1-4, 6, 11) **72.838 = 78,13 %**; sin label **76.149**.
**(ii)** con operador **18.942/1.722**; cláusula 5+7 **1.870/170** (catálogo **2.475/225**); as-of ≥2026-06-03 **51.051/4.641** (**15.796/1.436** con operador).

## 6. Holdout

**Regla a priori (dos partes):** entra todo mercado con operador de **`target_date` ≥ 2026-09-01** **y** `event_id` **fuera** de la muestra de selección = los cinco artefactos (HKO 166 ∪ E2R 38 ∪ discrim. 57 ∪ SAMPLE_E2 46 ∪ GEOVAL 400) = **662 ev. / 7.282 mk.** El corte solo **no** basta: dejaría dentro **22 ev. / 242 mk.** (5→3/33, 7→18/198, 10→1/11); sólo la exclusión nominal lo hace out-of-sample.
**mk/ev · cláusula · evaluable (`settle`):** 5 **55/5** · 22 · **33/3** — 7 **1.419/129** · 1.408 · **11/1** — 8 **0/0** · 0 · **0/0** — 10 **22/2** · 11 (emite flagueada) · **22/2** — **Σ 1.496/136 · 1.441 · 66/6**.
**Limitaciones:** (1) el **8 no tiene holdout** (121 mk., `target_date` min = max = 2026-08-23; catálogo hasta 2026-09-04) ⇒ **no promocionable**, sobre su `window` NO_SEPARABLE_EN_MUESTRA. (2) **n independiente = eventos (6)**, no mercados (66). (3) **945943 vuelve al holdout** (fila 10, 2026-09-03, 11 mk., con cláusula): no está en los cinco. (4) La cuantización de 5 y 7 es `NO_DECIDIBLE` permanente. **Ningún operador está VALIDADO** ni se promueve por edición: criterio **pospuesto (A-24)**.

## 7. Lo que NO congela

En v3 (`f6fcd2e4…`), no normativo: (1) `band_probability`, `ForecastCDF` y la puerta de p_weather. (2) El preregistro de validación y su criterio (§6); la verificación del estrato 9 (§4.3), única vía para sacarlo de `series_filter_unverified`. (3) Migración (§5), rule-map, 2D y las **DP-\*** de §8 (**DP-W1**, **DP-D17x** —en §3— y **DP-D17y**). (4) Las incógnitas de §7 y `edge_net`. (5) **La contradicción de 2D §C consigo mismo (prohíbe toda fuente y no ofrece ninguna), a tramitar por 2D §V; ver A-27**, y la unificación `v3.primary_source` ↔ parser D21.

## Changelog v2 (respecto a v1 `281d0d14…`)

1. `target_date` = parámetro del caller (2D §C); A-25 baja a evidencia y su contradicción se declara (2D §V); año en 93.088 slugs, **133 de vía única**.
2. Holdout **1.496/136** y **66/6** (corte 2026-09-01 + los 662 eventos de selección); 8 → 0/0; 945943 repuesto; «4 eventos» → **22/242**.
3. Estación nulable (sólo `LOCAL_CIVIL_DAY`) y orden terna → estrato → ctx: sin eso la fila 10 (`icao2` NULL en 1.859) no emitía label, ni la 11 su `source_inaccessible`.
4. Fila 11 con las dos ternas (v3 ≡ parser D21): sin eso `context_out_of_snapshot` tenía 77 casos hoy.
5. §3: condición **(0)** antes de (i)/(ii); 5 y 7 con `quantization` UNKNOWN calificado; 8 con NONE; NEAREST fuera. §4: criterio único del enum; los `reason` de `target_date` al caller; fuera `unit_mismatch`, y `rule_map_missing`/`operator_none`/`station_tz_unknown` → red terminal.
6. Ancla `DECISIONS.md` **`9a496670…`** (v1 y el borrador de v2 citaban `c671ef3a…`, nunca vigente); sha de PREREG_E2/E2R/discriminación; D18 no existe; KB = KiB.
7. Tamaño: **12 KiB** (KB = KiB) cumplidas, sin perder datos. **Rechazado** externalizar §6 y el changelog: la estructura es 7 puntos + changelog, y §6 no es el preregistro de A-24 (no fija criterio de aceptación, sólo qué es out-of-sample).