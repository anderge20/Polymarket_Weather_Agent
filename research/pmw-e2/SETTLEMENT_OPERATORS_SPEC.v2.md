# SETTLEMENT_OPERATORS_SPEC.md

**Estado del documento:** v2 — BORRADOR REVISADO TRAS RONDA 1 DE REFUTACIÓN, PENDIENTE DE CONGELAR (2026-09-06).
**Sustituye a:** `SETTLEMENT_OPERATORS_SPEC.draft.md` (v0.1). Aplica los 30 hallazgos de `WF_r12_refutations.json` (2 refutadores; 4 BLOQUEANTES, 14 IMPORTANTES, 12 MENORES); el detalle hallazgo → estado está en la sección «Changelog v2».
**Fuentes:** código `origin/main` (worktree `dfdc73e`, `src/weather_agent/{probability,features,labeling,database}.py`, `src/weather_agent/polymarket/resolution.py`, `src/weather_agent/strategy/strategy_a.py`), `PHASE_2D_STRATEGY_A_DESIGN.md`, `PHASE_2E_SETTLEMENT_OPERATOR_DESIGN.md`, `PHASE_2E_LEAD_HOURS_ANCHOR.md`; artefactos de `/Users/mariaaleu/pmw-e2` (recómputo propio sobre `HKO_OPERATOR_TEST.json` sha `093e5891…`, `E2_RESULTS.json` sha `ec500428…`, `E2_DISCRIMINATION_EVIDENCE.json` sha `9d925bf3…`, `NOAA_DIRECT.json`, `NOAA_DIRECT_EXACT.json`, `STATION_TZ_v1.json` sha `35d68e65…`, `STATION_REGION_COMPONENT_v1.json` sha `b6aeeacb…`, `STATION_COORDS_SNAPSHOT_v1.3.json` sha `c1617939…`, `PREREG_E2.md` sha `c7f031ec…`, `PREREG_LEAD_HOURS_RANGE.md` sha `1d4161e8…`, `FEES_SEMANTICS.md` sha `4dbad3ab…`); `CATALOG_V2.duckdb` (`read_only=True`, tablas `v3`, `cls2`, `ev`). `DECISIONS.md` sha vigente `d36749bf30677733b1cff57b2c5fd0a67844c88c63d2f71b0cc8403307b1f0af` (coincide con `DECISIONS.sha256`, OBSERVADO 2026-09-06 19:48). Las decisiones se citan por identificador (D0…D19), nunca por línea. Nada de este documento consulta Open-Meteo ni fuentes contractuales en vivo.
**Convención de evidencia:** OBSERVADO (leído/recomputado sobre artefacto o catálogo en disco) · DEMONSTRATED / STRONGLY SUPPORTED / REFUTADO (heredadas de los informes, con n e IC Wilson 95 %) · INFERIDO (razonamiento sin artefacto que lo separe de alternativas) · UNKNOWN. **Regla:** donde la evidencia de un componente sea UNKNOWN, el operador es FAIL_CLOSED. Este documento no eleva ninguna categoría respecto a sus fuentes; las cifras «citadas del informe» sin artefacto versionado se marcan como tales.

---

## 0. Objeto y qué NO decide

**Objeto.** Definir el `SettlementOperator`: la función que, dada una serie de observaciones (o de forecast, para las reglas by-the-Forecast) con timestamps, disponibilidad y unidad, produce el valor/banda que liquida un mercado Polymarket de temperatura máxima, y la función dual que mapea una CDF continua de forecast a probabilidades por banda. Fija por (contract_source, measurement_rule, unit, rounding_rule) qué operador existe, con qué evidencia (por componente y end-to-end), y cuál es su estado (HABILITADO / HABILITADO_CON_PROXY / FAIL_CLOSED) y su estado de validación (SELECCION_IN_SAMPLE / VALIDADO / NO_DECIDIDO). Sustituye el operador nearest-integer implícito de `probability.quantiles_to_distribution` (`probability.py:89-98`), declarado «unsafe» en `PHASE_2E_SETTLEMENT_OPERATOR_DESIGN.md` («That is an implicit round-to-nearest operator. It is not established by the market rules»).

**Qué NO decide este documento:**
1. **No decide la forma de la distribución continua de forecast** (colas ±1 al 10 %, soporte, interpolación). `ForecastCDF_v0` (§1.3, §5 paso 1) es la CDF legada **recortada a [0,1]** — ese recorte y el caso degenerado son las dos únicas decisiones que se toman sobre ella y se registran como **DP-CDF0** (§8).
2. **No decide `record_version_asof(T)` ni `source_available_at`** para el histórico: UNKNOWN en 93.221/93.221 mercados (`RECORD_VERSION_ASOF_AUDIT.md`). El operador produce `Y_final` retrospectivo cuando `asof=None` y lo declara (`availability='Y_FINAL_UNKNOWN_ASOF'`, §1.2). **`Y_final` sólo puede usarse como label de evaluación/auditoría (§6) y, para M2, únicamente bajo el preregistro de R16** («cuantiles usan sólo observaciones con `available_at` < fecha de cálculo», ROADMAP R16); la captura prospectiva de D17 (`available_at` real, `record_version` por revisión) es la única vía a `Y_asof_T`.
3. **No decide la reconciliación target_date / día civil en Wellington** (`PHASE_2E_LEAD_HOURS_ANCHOR.md` §8, «cuestión adyacente abierta») ni los eventos con endDate = target_date + 1 (ROADMAP R8, PARCIAL). El operador consume `target_date_contractual` del rule-map (§5 paso 0) y no lo deriva de endDate. El ancla `T = endDate − lead_hours·3600` con `endDate = target_date 12:00:00Z` en 8.557/8.557 eventos (OBSERVADO en `ev`; `PREREG_LEAD_HOURS_RANGE.md`) es la que fija el `asof` de `settle` cuando se use en M2 o backtest; leads operativos {9 h, 24 h} primarios, {36 h, 48 h} secundarios, > 48 h no operativos (PREREG_LEAD_HOURS_RANGE §3).
4. **No decide la política de revisiones de WU/HKO/CWA** (`REVISION_IMPACT_AUDIT.md`: «NO DEMUESTRA NADA sobre Wunderground»; «Lo mismo aplica a HKO y CWA»).
5. **No afirma que IEM/METAR sea la fuente de settlement** de ningún mercado. El proxy se usa bajo D17 con `compat_status` declarado (§4).
6. **No infiere el operador de CWA desde HKO** (proveedores, estaciones y países distintos).
7. **No decide el desbloqueo de p_weather LOCKED de 2D §F**, ni la modificación de `features.py`/`probability.py`/`labeling.py`/`database.py` prohibida por 2D §V, ni el mecanismo de exclusión de 2D §L; §5.5 declara exactamente qué habría que desbloquear (**DP-2D**) y lo deja como decisión explícita de ambos (ROADMAP «SettlementOperator vs p_weather LOCKED»).
8. **No decide fees ni `edge_net`**: D19 (`FEES_SEMANTICS.md`) es independiente del operador; ninguna salida de este documento alimenta `edge_net`.
9. **No define el label de entrenamiento ni el de pago**: ambos son `winning_outcome` vía `labeling.build_label` (gate temporal `prediction_time < resolution_timestamp` intacto). `settle()` produce `Y_source_value`/`band_key` como **covariable de auditoría (§6) y target de M2**, nunca como sustituto del label de pago (§3.3).

---

## 1. Definición formal del operador

### 1.1 Entrada

Una **serie de observaciones** `S = {(t_i, y_i, u, serie, available_at_i, record_version_i)}` donde:
- `t_i` timestamp de la observación con zona (UTC canónico);
- `y_i` valor numérico;
- `u ∈ {C, F}` unidad de toda la serie (una serie no mezcla unidades);
- `serie` identifica el producto: `hko_clmmaxt` (valor diario en décimas, publicado por HKO), `metar_body_c` (entero °C del cuerpo METAR, vía IEM), `metar_tgroup_tmpf` (**producto derivado por IEM**: `tmpf = round(F(grupo T en décimas))`, rejilla 1 °F; NO es una regla de la fuente contractual), `noaa_hourly_f` (valor horario de api.weather.gov; **sin operador con evidencia**, §2 fila 9);
- `available_at_i: datetime | None` — instante en que la observación estuvo disponible (columna as-of de `weather_observations`, `AS_OF_COLUMNS["weather_observations"] = "available_at"`); `None` = desconocido (histórico IEM procesado);
- `record_version_i: int` — versión de la observación (D17: revisiones COR/AMD no sobrescriben).

Más el **contexto del mercado** `MarketContext`, cuya **fuente única** es la tabla congelada `market_rule_map` (§5 paso 0): `contract_source`, `measurement_rule_P`, `unit`, `rounding_rule`, `station_icao`, `station_tz` (de `STATION_TZ_v1.json`), `target_date_contractual`, `clause_lowest_bracket`, `fallback_R1`; y para la dual, las bandas `(lo, hi)` enteras con `None` = banda abierta (`resolution.parse_band`).

Más el **corte temporal** `asof: datetime | None` (§1.3): con `asof` dado, toda observación con `available_at` `None` o `> asof` invalida el cálculo (fail-closed `observations_not_available_asof`); con `asof=None` el resultado es `Y_final` retrospectivo y así se declara.

Para reglas **by-the-Forecast** la entrada sería una serie de forecast. No existe operador con evidencia para ellas (§2 filas 3-4); la interfaz acepta el tipo pero ningún operador lo implementa.

### 1.2 Salida

```
SettlementResult:
  band_key:          int | None       # N que indexa la banda liquidada (N ≡ [N, N+1) en HKO; N ≡ Y entero en whole-degree)
  settled_value:     float | None     # Y_source_value tal como lo publica la fuente/proxy (décimas HKO, entero METAR, tmpf IEM)
  window_start_utc:  datetime | None  # ventana efectivamente usada (None si window_kind = SOURCE_DAILY_ROW)
  window_end_utc:    datetime | None
  window_kind:       'LOCAL_CIVIL_DAY' | 'SOURCE_DAILY_ROW'
  n_obs:             int              # 1 para SOURCE_DAILY_ROW
  aggregation:       'MAX' | 'SOURCE_DAILY'
  quantization:      'INTERVAL_FLOOR' | 'NEAREST' | 'NONE'
  unit:              'C' | 'F'
  availability:      'ASOF_VERIFIED' | 'Y_FINAL_UNKNOWN_ASOF'
  asof:              datetime | None
  max_available_at:  datetime | None  # máximo available_at de las obs usadas (None si alguna es None)
  max_record_version:int
  evidence_category: str              # categoría end-to-end de la EvidenceRef del operador
  label_source:      'HKO_CLMMAXT' | 'IEM_METAR'
  contract_source:   'HKO' | 'WU' | 'NOAA' | 'CWA' | 'SIN_CLAUSULA'
  compat_status:     'DIRECT' | 'PROXY_AUDITED' | 'PROXY_NOT_AUDITED' | 'NONE'   (D17 + extensión §4.1)
  revision_status:   'UNKNOWN_FOR_CONTRACT_SOURCE' | 'UNKNOWN_PUBLISHED_VS_FINALIZED'
  clause_lowest_bracket: bool         # copiado del rule-map; el operador NO reproduce esa rama
  operator_id, operator_version, spec_version
  excluded_reason:   str | None       # enum cerrado §3.4; si no es None, todo lo anterior es None/inaplicable
```

Nota HKO: `band_key = floor(Y)` es una clave de banda, **no** una afirmación de que el escalar liquidado sea `floor(Y)`: floor(Y) y pertenencia a [N, N+1) son observacionalmente indistinguibles (escalar UNKNOWN). Para construir p_weather ambas lecturas convergen.

### 1.3 Interfaz Python (protocolo; sin implementar)

Coherente con `PHASE_2E_SETTLEMENT_OPERATOR_DESIGN.md` «Required interface» (operator_id + versión inmutable; predicados de aplicabilidad; política de unidades; mapeo CDF→outcomes; tests bandas cerradas/abiertas; referencia de evidencia).

```python
from typing import Protocol, Sequence, Literal, NamedTuple
from datetime import datetime, date

Unit = Literal["C", "F"]

class Observation(NamedTuple):
    ts_utc: datetime
    value: float
    unit: Unit
    series: str                      # 'hko_clmmaxt' | 'metar_body_c' | 'metar_tgroup_tmpf' | 'noaa_hourly_f'
    available_at: datetime | None    # D17-C: instante real de disponibilidad; None = desconocido
    record_version: int              # D17-C: revisión (COR/AMD) sin sobrescribir

class MarketContext(NamedTuple):
    market_id: str                   # SOLO para linaje; applies_to NO lo lee (§1.4)
    event_id: str
    contract_source: str             # 'WU' | 'NOAA' | 'HKO' | 'SIN_CLAUSULA' | 'TEST'  (v3.primary_source vía market_rule_map)
    measurement_rule: str            # 'P_WU_DailyObservations' | 'P_NOAA_TempColumn' | 'P_NOAA_HourlyData' | 'P_HKO_AbsDailyMax' | 'P_byForecast' | 'P_WU_GENERIC_sin_calificador' | 'P_UNKNOWN'  (v3.primary_rule)
    unit: Literal["C", "F", "UNKNOWN"]
    rounding_rule: str               # 'whole degree' | 'tenths' | otro
    station_icao: str | None         # v3.icao2; None en HKO (1.859) y CWA (77)
    station_tz: str | None           # IANA, de STATION_TZ_v1.json; None => fail-closed station_tz_unknown
    target_date: date                # contractual, del texto; NO derivada de endDate
    clause_lowest_bracket: bool
    fallback_R1: bool

class EvidenceRef(NamedTuple):
    category: str                    # categoría END-TO-END (band_key vs winning_outcome, misma (fuente, regla, unidad))
    n_agree_prereg: int              # muestra preregistrada (PREREG_E2 / HKO_OPERATOR_TEST)
    n_total_prereg: int
    n_agree_nonprereg: int           # muestra NO preregistrada (E2_DISCRIMINATION_EVIDENCE), declarada como tal
    n_total_nonprereg: int
    wilson95_prereg: tuple[float, float]
    components: dict[str, str]       # {'window': ..., 'aggregation': ..., 'quantization': ..., 'series': ...} con categoría por componente
    validation_state: Literal["SELECCION_IN_SAMPLE", "VALIDADO", "NO_DECIDIDO"]
    artifacts: tuple[str, ...]       # rutas + sha
    exceptions: tuple[str, ...]      # event_ids abiertos (NUNCA se filtran del universo, §1.4)

class ForecastCDF(Protocol):
    """CDF continua PROPIA de la Tmax prevista: F(-inf)=0, F(+inf)=1, no decreciente."""
    unit: Unit
    version: str
    support: tuple[float, float]
    def cdf(self, x: float) -> float: ...

class SettlementOperatorUnavailable(Exception):
    """NO es subclase de ValueError (strategy_a captura ValueError como 'executable_or_invalid_price')."""
    reason: str                      # valor del enum §3.4

class SettlementOperator(Protocol):
    operator_id: str
    version: str                     # inmutable; cambio de comportamiento => nueva versión
    unit: Unit                       # unidad en la que opera; NO convierte observaciones
    window_kind: Literal["LOCAL_CIVIL_DAY", "SOURCE_DAILY_ROW"]
    aggregation: Literal["MAX", "SOURCE_DAILY"]
    quantization: Literal["INTERVAL_FLOOR", "NEAREST", "NONE"]
    required_series: str
    evidence: EvidenceRef
    compat_status: Literal["DIRECT", "PROXY_AUDITED", "PROXY_NOT_AUDITED"]

    def applies_to(self, contract_source: str, measurement_rule: str, unit: str, rounding_rule: str) -> bool: ...
    def settle(self, obs: Sequence[Observation], ctx: MarketContext, asof: datetime | None) -> SettlementResult: ...
    def band_probability(self, F: ForecastCDF, lo: int | None, hi: int | None) -> float: ...
```

### 1.4 Contratos del protocolo (a testear)

- **`applies_to` es función pura de `(contract_source, measurement_rule, unit, rounding_rule)`** y nunca de `market_id`, `event_id`, `target_date`, `station_icao` ni de ningún campo derivado del resultado. Motivo: las excepciones conocidas (322448, 490245, 493669) se identificaron por su `winning_outcome`; excluirlas por identidad sería una selección del universo condicionada al resultado — la misma clase de fuga que `PHASE_2E_LEAD_HOURS_ANCHOR.md` §4 describe («fuga en la selección…, no en las features», invisible a las guardas as-of). Test `test_applies_to_is_identity_blind`: mismo `(fuente, regla, unidad, redondeo)` con `market_id` distinto → mismo resultado, incluidos los tres event_ids de excepción. Las excepciones permanecen en el universo y se reportan en §6.
- `settle` falla cerrado (`SettlementResult.excluded_reason`) si: `not applies_to(...)`; `ctx.station_tz is None` y `window_kind == LOCAL_CIVIL_DAY` (`station_tz_unknown`); `ctx.unit == 'UNKNOWN'` (`unit_unknown`); `obs` vacía en la ventana (`no_observations_in_window`); alguna `obs.unit != self.unit` (`unit_mismatch`); `obs.series != required_series` (`series_mismatch`); `asof` dado y alguna obs con `available_at is None` o `available_at > asof` (`observations_not_available_asof`).
- `settle(asof=None)` devuelve `availability='Y_FINAL_UNKNOWN_ASOF'`; `settle(asof=T)` devuelve `availability='ASOF_VERIFIED'` y `max_available_at ≤ T`. Test `test_settle_rejects_obs_available_after_asof`.
- `band_probability` con `lo > hi` → `ValueError` (conserva el contrato de `probability.band_probability`).
- **Suma sobre partición**: para toda partición válida (`band_integrity(...)['is_partition']`), `|Σ band_probability − 1.0| ≤ 1e-12` sin renormalización, porque `F` es propia y la suma es telescópica (test `test_band_probability_partition_sums_to_one_exact` con tolerancia 1e-12; `weather_sum_tolerance = 1e-6` se conserva como guarda de Strategy A, no como matemática).
- Mapeo por cuantización (único paso que depende de evidencia por fuente):
  - `INTERVAL_FLOOR` (HKO, bandas N ≡ [N, N+1)): `P([lo,hi]) = F(hi+1) − F(lo)`; `(None,hi] → F(hi+1)`; `[lo,None) → 1 − F(lo)`.
  - `NEAREST` (whole-degree con Y = round(valor en décimas), sólo donde OBSERVADO en la serie): `P([lo,hi]) = F(hi+0.5) − F(lo−0.5)`; abiertas análogas. Empates exactos en .5 tienen medida cero bajo una CDF continua; la regla de empate del observador es UNKNOWN y se declara.
  - `NONE`: no definido para forecast → `band_probability` lanza `NotImplementedError` (operador sólo-`settle`).
- **Política de unidades**: el operador NO convierte observaciones (`PREREG_E2.md`: «NO se aplica round(), floor(), ceil() ni conversión C<->F para forzar coincidencia»). `metar_tgroup_tmpf` es una serie **derivada por IEM**; si la ingestión prospectiva (D17-C) parte del METAR crudo, la fórmula `tmpf = round(F(T_grupo))` se preregistra como **definición de la serie** (no como paso del operador) antes de usarla, con test de identidad contra la columna `tmpf` de IEM. La conversión **de la CDF continua** de forecast a la unidad del mercado es una transformación afín exacta (`x·1.8+32`) sobre variable continua; se permite **sólo** en `ForecastCDF` y se registra en linaje (`unit_conversion='C_to_F_affine'`). Decisión de diseño (INFERIDO), **DP-U1**.
- `feature_json` **no** contiene campos de evidencia (`evidence`, `exceptions`, `n_agree*`, `wilson*`): test `test_feature_json_has_no_evidence_fields`.

---

## 2. Tabla por (contract_source, measurement_rule, unit, rounding_rule)

Recuentos exactos: `CATALOG_V2.duckdb` tabla `v3` (93.221 mercados, 8.557 eventos), OBSERVADO por recómputo read-only 2026-09-06; coinciden con el refutador (H0.11). IC = Wilson 95 % (z = 1,96) recomputado.

### 2.1 Componentes transversales (vía proxy IEM/METAR, no vía fuente contractual)

- **Ventana W(m) = día civil local de la estación** (tz de `STATION_TZ_v1.json`, `tzname` del registro ASOS de IEM, 55/55 estaciones, `missing=[]`, `conflicts=[]`; OBSERVADO). Evidencia de discriminación: STRONGLY SUPPORTED 54/57 (IC 0,856–0,982) en `E2_DISCRIMINATION_EVIDENCE.json` (LOCAL_ONLY 54, BOTH 2, NEITHER 1, UTC_ONLY 0); día UTC REFUTADO (compat_utc 2/57, IC 0,010–0,119). **Esa muestra NO está preregistrada** (PREREG_E2 cubre sólo los 38 de E2; ningún preregistro menciona `B_CANDIDATES`/discriminación) y **es toda °C y toda Asia/Pacífico**: Wellington 35 (NZWN), Tokyo 10 (RJTT), Chengdu 5 (ZUUU), Beijing 3 (ZBAA), Seoul 2 (RKSI), Taipei 1 (RCTP), Guangzhou 1 (ZGGG); por regla P_WU_GENERIC 41, P_NOAA_TempColumn 9, P_WU_DailyObservations 7 (OBSERVADO). En E2 (preregistrada) H_UTC y H_LOCAL son idénticas en 37/37 filas con datos (OBSERVADO), incluidas las 14 filas °F de EE. UU. → **para EE. UU./°F, NOAA HourlyData, HKO y CWA la ventana está NO SEPARADA en la muestra**: categoría por componente `NO_SEPARABLE_EN_MUESTRA` (compatible bajo ambas hipótesis); su extensión a EE. UU./Europa es INFERIDO por transferencia (**DP-W1**, §8). Corroboración «2.894/2.913 eventos resuelven tras cerrar la ventana local» es **citada del informe de timeline, sin artefacto en `pmw-e2`**; no se usa como evidencia hasta reproducirse en el artefacto §6.6.
- **Agregación Y = max(observaciones sobre target_date)**: STRONGLY SUPPORTED 37/37 (E2 con datos), identidad exacta 22/22 en °C con banda cerrada (OBSERVADO). Controles ±1 día recomputados sobre `E2_RESULTS.json`: `H_LOCAL_M1` 10/37 = 27 % (IC 0,154–0,430), `H_LOCAL_P1` 6/37 = 16 % (IC 0,077–0,311).
- **Cuantización whole degree °C**: «no hace falta operador de cuantización» DEMONSTRATED **para el proxy** (cuerpo METAR ya entero). Cómo el observador/fuente produce ese entero desde el valor continuo: **UNKNOWN**; y **NOT_TESTABLE con los artefactos existentes** (`H_LOCAL_tg` es `None` en 24/24 filas °C de E2; OBSERVADO) → afecta a `band_probability`, no a `settle` (§6.4).
- **Cuantización °F** (serie `metar_tgroup_tmpf`, derivación IEM, PROXY): `tmpf == round(F(tg))` en 14/14 filas °F (IC 0,785–1,0); compatibilidad con el bracket: tmpf 14/14; `round(F(cuerpo))` 9/14 (IC 0,388–0,836; 5 incompatibles); `floor(F(tg))` 10/14 (IC 0,454–0,883; incompatibles 940515 NYC 73,94; 888238 Atlanta 91,94; 888245 SF 75,92; 888240 Chicago 75,92); `ceil(F(tg))` 11/14 (IC 0,524–0,924; incompatibles 935131 Houston 87,08; 929767 Miami 91,04; 888235 Seattle 75,02) (OBSERVADO, recómputo propio; los ICs de las alternativas solapan con 14/14 — la discriminación NEAREST vs floor/ceil descansa en 4 y 3 casos). Ningún caso está cerca de un empate .5. Lo evidenciado es la derivación de IEM, no el proceso del observador ni de NOAA.

### 2.2 Tabla

Columnas: Ev. prereg = muestra preregistrada; Ev. no-prereg = discriminación (no preregistrada); Val. = estado de validación §6.

| # | contract_source / measurement_rule | unit / rounding | Operador (ventana; agregación; cuantización; serie) | Evidencia end-to-end (prereg · no-prereg) y por componente | Mercados / eventos | `settle` (label) | `band_probability` (p_weather) | Val. |
|---|---|---|---|---|---|---|---|---|
| 1 | WU / P_WU_GENERIC_sin_calificador | C / whole degree | ninguno: Y indefinida por contrato (no nombra tabla ni agregación) | UNKNOWN (Y contractual). Compat proxy local 41/41 (IC 0,914–1,0) es OBSERVADO en muestra no preregistrada pero no define el operador; regla excluida en PREREG_E2 | 26.763 / 2.433 | FAIL_CLOSED (`no_settlement_operator:Y_undefined_by_contract`) | FAIL_CLOSED | — |
| 2 | WU / P_WU_GENERIC_sin_calificador | F / whole degree | ninguno | UNKNOWN | 8.459 / 769 | FAIL_CLOSED | FAIL_CLOSED | — |
| 3 | WU / P_byForecast | C / whole degree | ninguno: liquida un pronóstico; excluida por diseño (PREREG_E2); 0 casos | UNKNOWN | 25.982 / 2.412 | FAIL_CLOSED (`no_settlement_operator:by_forecast`) | FAIL_CLOSED | — |
| 4 | WU / P_byForecast | F / whole degree | ninguno | UNKNOWN | 9.500 / 896 | FAIL_CLOSED | FAIL_CLOSED | — |
| 5 | WU / P_WU_DailyObservations | C / whole degree | `WU_DAILYOBS_C_PROXY_IEM v1`: LOCAL_CIVIL_DAY; MAX; NONE; `metar_body_c` | Fuente WU: UNKNOWN (no reconstruida). Proxy: **prereg E2 7/7** (IC 0,646–1,0) · no-prereg 7/7 LOCAL_ONLY. Componentes: window SS (Asia/Pac., °C), aggregation SS, series DEMONSTRATED, quantization °C UNKNOWN | 6.996 / 636 | HABILITADO_CON_PROXY (`PROXY_AUDITED`; n_prereg=7) — mercados con cláusula lowest-bracket: `PROXY_NOT_AUDITED` (§4.2 cond. 6) | FAIL_CLOSED (`quantization_unknown_C`; Q-test NOT_TESTABLE) | SELECCION_IN_SAMPLE |
| 6 | WU / P_WU_DailyObservations | F / whole degree | ninguno auditado: 0 casos °F en E2 | UNKNOWN | 2.057 / 187 | FAIL_CLOSED (`proxy_not_audited_F`) | FAIL_CLOSED | — |
| 7 | NOAA / P_NOAA_TempColumn | C / whole degree | `NOAA_TEMPCOL_C_PROXY_IEM v1`: LOCAL_CIVIL_DAY; MAX; NONE; `metar_body_c` | Vista contractual wrh/timeseries: UNKNOWN. Proxy: **prereg E2 16/16** (A-C 8/8, B-C 8/8; IC 0,806–1,0) · no-prereg 8/9 (IC 0,565–0,980; excepción Taipei 322448 NEITHER, abierta). Componentes como fila 5 | 9.966 / 906 | HABILITADO_CON_PROXY (`PROXY_AUDITED`; n_prereg=16; 1 excepción abierta) — con cláusula: `PROXY_NOT_AUDITED` | FAIL_CLOSED (`quantization_unknown_C`) | SELECCION_IN_SAMPLE |
| 8 | NOAA / P_NOAA_TempColumn | F / whole degree | `NOAA_TEMPCOL_F_PROXY_IEM v1`: LOCAL_CIVIL_DAY; MAX; NEAREST (vía serie IEM); `metar_tgroup_tmpf` | Proxy: **prereg E2 A-F 6/6** (IC 0,610–1,0; KHOU, KATL, KSFO, KORD, KAUS, KSEA) · no-prereg 0. Componentes: window **NO_SEPARABLE_EN_MUESTRA** (H_LOCAL = H_UTC 6/6; 0 discriminantes EE. UU./°F), aggregation SS, series/quantization SS (14/14 transversal, derivación IEM) | 121 / 11 | HABILITADO_CON_PROXY (`PROXY_AUDITED`; n_prereg=6; end-to-end compatible bajo ambas ventanas) — con cláusula: `PROXY_NOT_AUDITED` | **FAIL_CLOSED** (`window_not_discriminated_US_F`) hasta ratificar DP-W1 o disponer de ≥1 caso discriminante local/UTC en estación EE. UU./°F | SELECCION_IN_SAMPLE |
| 9 | NOAA / P_NOAA_HourlyData | F / whole degree | **ninguno habilitado.** Candidato `NOAA_HOURLY_F_PROXY_IEM v1` pendiente de §4.3 | Proxy IEM tmpf: prereg E2 8/8 (IC 0,676–1,0), **pero el subconjunto de observaciones usado es UNKNOWN**. Directo api.weather.gov 4/8 con datos (`NOAA_DIRECT.json`): Houston KHOU 2026-09-01 `nws_maxF_local = 87,8` (todas las obs, n_local 251) fuera de 86–87 vs `iem_tmpf = 87,0` dentro; `iem_body = 31 = nws_maxC_local`, `iem_tg = 30,6`. «Y es el valor horario» = **INFERIDO** (N=4, 1 caso decisivo, dos hipótesis no separadas: H_hourly vs H_series «grupo T en décimas 30,6→87 vs cuerpo entero 31→87,8»). Ningún artefacto en disco calcula un máximo sólo-horario de api.weather.gov | 1.441 / 131 | **FAIL_CLOSED** (`compat_status='PROXY_NOT_AUDITED'`, `excluded_reason='series_filter_unverified'`); reportados aparte como «pendientes §4.3» | FAIL_CLOSED (`series_filter_unverified`) | — |
| 10 | HKO / P_HKO_AbsDailyMax | C / tenths | `HKO_ABSMAX_INTERVAL_FLOOR v1`: **SOURCE_DAILY_ROW** (fila CLMMAXT de `target_date`, día civil Asia/Hong_Kong = target_date−1 16:00Z → target_date 16:00Z, ventana realizada por la fuente); **SOURCE_DAILY**; INTERVAL_FLOOR (N ≡ [N, N+1)); `hko_clmmaxt` | **Desde la fuente contractual** (`HKO_OPERATOR_TEST.json`, 166 resueltos, OBSERVADO recómputo): floor 164/166 (IC 0,957–0,997); ceil 34/166 (0,150–0,273), half-up 87/166 (0,448–0,599), half-even 95/166 (0,496–0,645) REFUTADOS. Discriminación por `band_key` distinto: **floor vs half-up n_disc = 81: floor 81/81 (0,955–1,0) vs half-up 4/81 (0,019–0,120)**; floor vs half-even n_disc = 73: 73/73 (0,950–1,0) vs 4/73 (0,022–0,133); floor vs ceil n_disc = 145: 143/145 (0,951–0,996) vs 13/145 (0,053–0,147). Sensibilidad «veredicto distinto» (= bandas cerradas): 77 casos, floor 77/77 (0,952–1,0) vs half-up 0/77; los 4 restantes son bandas abiertas compatibles con ambos (426244 26,7→'25°C or higher'; 497005 30,7; 439958 27,6; 469205 31,6). 16 mitades exactas: floor 16/16 (0,806–1,0). Excepciones abiertas, **ambas `arch-`**: 490245 (26,3 → '27°C', sólo ceil) y 493669 (26,4 → '≤22°C', ningún operador; duplicado del 503637 que liquidó 26 °C = floor). Escalar: UNKNOWN. Componentes: window/aggregation **subsumidas en la fila diaria de la fuente** y validadas end-to-end por los 164/166 (mapeo target_date→fila; `closedTime − window_end ≥ 10,795 h` en 168/168, 493669 sin closedTime); quantization SS; series DIRECT | 1.859 / 169 | HABILITADO (`compat_status=DIRECT`; `revision_status='UNKNOWN_PUBLISHED_VS_FINALIZED'`) — con cláusula (945943, 11 mercados): label con `clause_lowest_bracket=True`, reportado aparte | HABILITADO (INTERVAL_FLOOR) | SELECCION_IN_SAMPLE (holdout: 3 eventos / 33 mercados resueltos, §6.2) |
| 11 | SIN_CLAUSULA (CWA Taipei) / P_UNKNOWN | C / tenths | ninguno: fuente inaccesible (401/404/JS), 0/7 con valor fuente; estación e identidad UNKNOWN | UNKNOWN | 77 / 7 | FAIL_CLOSED (`source_inaccessible`) | FAIL_CLOSED | — |

### 2.3 Totales derivados (aritmética sobre las filas; INFERIDO sólo en el sentido de suma)

- **`settle` habilitado** (directo + proxy auditado): filas 5, 7, 8, 10 = 6.996 + 9.966 + 121 + 1.859 = **18.942 mercados (20,3 %)** — de ellos, los mercados con cláusula lowest-bracket en filas 5, 7, 8 (55 + 1.815 + 0 = 1.870) reciben `PROXY_NOT_AUDITED` por §4.2 cond. 6 y **no** reciben label: **settle efectivo = 17.072 (18,3 %)**; los 11 HKO con cláusula sí reciben label DIRECT flagueado.
- **Pendientes §4.3** (fila 9): **1.441 (1,5 %)**, reportados aparte.
- **FAIL_CLOSED `settle`** (resto): 93.221 − 18.942 = **74.279 (79,7 %)**, de los que 1.441 son pendientes y 72.838 (78,1 %) sin operador.
- **`band_probability` habilitado** (p_weather): fila 10 = **1.859 mercados (1,99 %)**; sin p_weather: 91.362 (98,0 %). Si se ratifica DP-W1 (fila 8): 1.980 (2,12 %).
- El nearest-integer legado coincide con la serie evidenciada únicamente en la fila 8 (121 mercados, y sólo por la serie `tmpf` derivada de IEM); en HKO (fila 10) está REFUTADO (half-up 87/166; 4/81 en discriminantes) y en el resto es UNKNOWN.

### 2.4 Subcasos que la tabla no separa (OBSERVADO en `v3`/`cls2`)

- **Fallback NOAA→WU (R1):** `rule_recuperable = 'R1_WU_DailyObservations'` en 2.497 P_NOAA_TempColumn y 836 P_NOAA_HourlyData (= **3.333**) por la cláusula «If NOAA data … unavailable by 11:59 PM ET … the Weather Underground Daily Observations table will be used». El operador aplica a la fuente **primaria** (`v3.primary_source/primary_rule`); si el fallback se activó en un mercado concreto es UNKNOWN por mercado. `applies_to` nunca usa `cls2.resolution_source` (NULL en 5.401 NOAA; URL de WU en 11 NOAA Shenzhen 2026-03-29) **ni `markets.measurement_rule`** (§5 paso 0).
- **Cláusula «resolve to the lowest bracket»** («In the event that there is no data for the observation date by 11:59 PM ET on the day following the observation date»): **2.475 mercados / 225 eventos**, endDate 2026-08-31..09-04: NOAA TempColumn C 1.815 / 165; NOAA HourlyData F 594 / 54; WU DailyObs C 55 / 5 (Jinan, Taipei); HKO 11 / 1 (945943). Es una rama de settlement no meteorológica que depende de la disponibilidad de datos **en la fuente contractual** (UNKNOWN por mercado): IEM puede tener `n_obs > 0` cuando WU/NOAA no los tuvo y el label del proxy divergiría del pago. Por eso se trata en §4.2 cond. 6 y se marca `clause_lowest_bracket` en el rule-map; `no_data_clause_possible` sólo se registra cuando además `n_obs = 0`. Casos auditados con cláusula: E2 contiene 4 eventos (929767, 935131, 940515, 952455), **todos de la fila 9** (FAIL_CLOSED por otra razón); en filas 5, 7, 8: **0** casos auditados con cláusula; en HKO: 945943 está en el holdout §6.2.
- **Estados no resueltos:** 47 `proposed` + 33 sin `umaResolutionStatus` (todos WU); `winning_outcome` NULL 39; resueltos con `winning_outcome` NULL: 0.

---

## 3. Política fail-closed (literal)

1. **p_weather.** Un mercado recibe `p_weather` **si y sólo si** existe un `SettlementOperator` con `applies_to(...) == True`, `quantization != NONE` y `evidence.category ∈ {STRONGLY_SUPPORTED, DEMONSTRATED}` **end-to-end** (band_key vs winning_outcome en la misma (fuente, regla, unidad)) **y** ningún componente de `evidence.components` en {UNKNOWN, REFUTADO, INFERIDO}. Los componentes `NO_SEPARABLE_EN_MUESTRA` (ventana en EE. UU./°F) **bloquean** p_weather hasta que DP-W1 se ratifique explícitamente (declarando el riesgo: forecast de Tmax del día local vs settlement en día UTC) o exista un caso discriminante; los componentes `SUBSUMIDO_EN_FUENTE` (HKO: ventana/agregación realizadas por CLMMAXT y validadas por los 164/166) **no** bloquean. Con esta regla el universo p_weather es la fila 10 (1.859).
2. **label vía observaciones.** Un mercado recibe `settle()` **si y sólo si** existe un operador con `applies_to(...) == True` y `compat_status ∈ {DIRECT, PROXY_AUDITED}` para su estrato (incluida la condición 6 de §4.2 sobre cláusula). Un mercado que no cumpla 1 ni 2 **no recibe p_weather ni settle** y no entra en features, predictions, backtest ni entrenamiento de M2/M3 (`PHASE_2E_SETTLEMENT_OPERATOR_DESIGN.md`, paso 5).
3. **Label de entrenamiento y de pago = `winning_outcome` vía `labeling.build_label`** (gate `prediction_time < resolution_timestamp` intacto; `None` si no resuelto). `settle().band_key/settled_value` es covariable de auditoría (§6) y target de M2 (error = obs − forecast, bajo `asof` de §1.4 y preregistro R16), **nunca** sustituto del label de pago. Difieren exactamente en las excepciones y en los casos con cláusula/fallback, y esa diferencia es lo que §6 mide. Test `test_training_label_is_winning_outcome_not_band_key`. El universo de features y de labels coincide: los mercados sin operador no reciben ni feature ni label de entrenamiento.
4. **Registro de exclusiones** en `markets_excluded` **sin cambio de schema** (2D §V): `reason` = valor del enum cerrado; `stage='feature'`; `details` JSON = `{event_id, contract_source, measurement_rule_P, unit, rounding_rule, operator_id|null, spec_version, asof}`. Enum cerrado de `reason`: `no_settlement_operator:Y_undefined_by_contract`, `no_settlement_operator:by_forecast`, `proxy_not_audited_F`, `quantization_unknown_C`, `window_not_discriminated_US_F`, `series_filter_unverified`, `clause_stratum_not_audited`, `source_inaccessible`, `rule_map_missing`, `station_tz_unknown`, `unit_unknown`, `unit_mismatch`, `series_mismatch`, `no_observations_in_window`, `observations_not_available_asof`, `no_data_clause_possible`, `operator_none`. Mecanismo: `build_feature` lanza `SettlementOperatorUnavailable(reason)` (no subclase de `ValueError`) y `strategy_a` añade `except SettlementOperatorUnavailable as e: reason = e.reason` **antes** del `except ValueError` existente (`strategy_a.py:190-198`); esto toca 2D §L («banda NONE si build_feature devuelve None») y forma parte de **DP-2D** y **DP-L1**.
5. **Prohibiciones explícitas:** ningún operador por defecto (`operator=None` → `operator_none`, nunca nearest); ninguna conversión C↔F sobre observaciones; ningún filtro post-hoc (p. ej. `arch-`) para elevar la evidencia ni filtro de aplicabilidad por identidad de mercado (§1.4); ninguna lectura de `markets.winning_outcome/resolution_timestamp` por `build_feature` (`FORBIDDEN_FEATURE_FIELDS` sigue vigente).
6. **Cambiar el estado de una fila de §2** requiere: (a) preregistro §6, (b) artefacto con sha, (c) nueva `spec_version`; nunca una edición silenciosa. Los estados HABILITADO de §2 son **provisionales** (`validation_state=SELECCION_IN_SAMPLE`) hasta VALIDADO en holdout; NO_DECIDIDO no rebaja el estado (se acumula holdout), y nada se eleva sin cumplir §6.5.

---

## 4. Proxy IEM/METAR para WU/NOAA (D17) y fuente directa HKO

**4.1 Base.** D17 (ADOPTADO): labels WU/HKO/CWA vía proxy IEM/METAR «sólo bajo una auditoría de compatibilidad declarada»; cada label lleva `label_source`, `contract_source`, `compat_status`; sin operador auditado → fail-closed. **Extensión de D17 (a registrar como decisión propia, DP-D17x):** Hong Kong no tiene METAR (`STATION_COORDS_SNAPSHOT_v1.3` excluded_no_icao «settlement HKO, no METAR»; `v3.icao2` NULL en 1.859); la regla de etiquetado por fuente contractual de D17 se extiende a la **fuente contractual directa** `HKO_CLMMAXT` como `label_source` admitido con `compat_status='DIRECT'` (VHHH aparece en `STATION_TZ_v1` con `Asia/Hong_Kong` sólo por 18 mercados WU by-Forecast; el operador HKO no la usa). Nada de esto afirma que IEM sea la fuente de settlement de ningún mercado.

**4.2 Condiciones para `compat_status = PROXY_AUDITED`** (todas necesarias, por estrato (fuente, regla, unidad, con/sin cláusula)):
1. Existe **al menos una auditoría de compatibilidad preregistrada** (E2: `PREREG_E2.md` sha `c7f031ec…` → `E2_RESULTS.json` sha `ec500428…`, 38 eventos) con Y del proxy comparada contra `winning_outcome`. Si se usa además la muestra de discriminación (`B_CANDIDATES.json` 618 → `E2_DISCRIMINATION_EVIDENCE.json` sha `9d925bf3…`, 57), se declara **no preregistrada** y se reporta en columna separada de la `EvidenceRef` (sin solapamiento de event_id con E2, verificado por el refutador).
2. Ventana y agregación del proxy coinciden con las declaradas en §2 (día civil local de la estación; max; serie declarada).
3. La serie es la adecuada a la unidad: `metar_body_c` en °C; `metar_tgroup_tmpf` en °F (`round(F(cuerpo))` REFUTADO 5/14).
4. La estación tiene ICAO (`v3.icao2`, 55 distintos; NULL en HKO 1.859 y CWA 77) y **tz resuelta en `STATION_TZ_v1.json`** (55/55, OBSERVADO; sha `35d68e65…`). La condición se verifica **por estación en tiempo de ejecución** con fail-closed `station_tz_unknown`; el número de mercados con `icao2` no nulo (91.285, = Σ `n_markets` de `STATION_REGION_COMPONENT_v1`) es aritmética del catálogo, no una afirmación de cobertura DEMONSTRATED.
5. Las excepciones abiertas están listadas (Taipei 322448 NEITHER) y no se eliminan.
6. **Cláusula lowest-bracket:** para mercados con `clause_lowest_bracket=True`, `PROXY_AUDITED` sólo si el estrato (regla, unidad, **con cláusula**) tiene casos auditados reportados aparte; hoy **0** en filas 5, 7, 8 → `PROXY_NOT_AUDITED`, `excluded_reason='clause_stratum_not_audited'`. Para HKO (DIRECT), el label se emite con `clause_lowest_bracket=True` y se reporta como estrato aparte en §6 (la fuente es la contractual, pero si el dato estuvo disponible antes del plazo es UNKNOWN).

**4.3 Verificación preregistrada de la fila 9 (NOAA HourlyData °F)** — precondición para pasar de FAIL_CLOSED a HABILITADO_CON_PROXY. Dos hipótesis alternativas, ambas compatibles con `NOAA_DIRECT.json`:
- **H_hourly:** Y = max sobre observaciones **rutinarias horarias** de api.weather.gov (no todas las obs).
- **H_series:** Y = `round(F(grupo T))` (= `tmpf` de IEM) sobre **todas** las observaciones; la discrepancia Houston 87,8 vs 87,0 nace de cuerpo entero (31 → 87,8) vs grupo T (30,6 → 87,08).
Datos necesarios en disco: observaciones crudas de api.weather.gov por estación-día (`nq.json` sólo contiene KLGA 2026-09-03) **o** las obs IEM con marca de rutinaria/especial. Métrica: para cada evento resuelto de la fila 9 con datos, `band_key` bajo H_hourly y bajo H_series vs `winning_outcome`; `n_disc` = eventos con `band_key` distinto; criterio §6.5. Hasta entonces `compat_status='PROXY_NOT_AUDITED'` y `excluded_reason='series_filter_unverified'` en `settle` y en `band_probability`. Qué subconjunto usó el recómputo 8/8 de E2 (`H_LOCAL_n = 25` en IEM vs `n_local = 251` en el API para Houston) es UNKNOWN.

**4.4 Qué se reporta por label.** Vía proxy: `label_source='IEM_METAR'`, `contract_source`, `measurement_rule_P`, `compat_status`, `series`, `station_icao`, `station_tz`, `window_start_utc/end_utc`, `n_obs`, `settled_value`, `band_key`, `availability`, `asof`, `max_available_at`, `max_record_version`, `clause_lowest_bracket`, `fallback_R1`, `operator_id/version`, `spec_version`, `audit_ref` (ruta + sha), `revision_status='UNKNOWN_FOR_CONTRACT_SOURCE'` (impacto de revisiones medido sólo en IEM: 0/578 station-days, cota sup. 95 % < 0,519 %; no extrapolable). Directo HKO: `label_source='HKO_CLMMAXT'`, `compat_status='DIRECT'`, `window_kind='SOURCE_DAILY_ROW'`, `n_obs=1`, `revision_status='UNKNOWN_PUBLISHED_VS_FINALIZED'` (CLMMAXT «devuelve solo el estado actual»; el contrato distingue «published» 1.078 mercados de «finalized» 781, sin timestamps; `RECORD_VERSION_ASOF_AUDIT.md`), `completeness` de la fila ('C' en 184/184 días).

**4.5 Qué NO afirma el proxy.** Que IEM sea la fuente de settlement; que WU muestre el cuerpo METAR o el grupo T; la tasa de revisión de WU; nada sobre °F en WU DailyObs (0 casos); nada sobre qué observaciones usa NOAA HourlyData (§4.3); nada sobre estaciones fuera de las auditadas.

---

## 5. Migración del código

Referencias: `PHASE_2E_SETTLEMENT_OPERATOR_DESIGN.md` «Migration sequence» (5 pasos); código actual `features.py` (§4 `quantiles_to_distribution` + `band_probability`, guarda final `FORBIDDEN_FEATURE_FIELDS`), `probability.py:57-109`, `strategy_a.py:179-203`, `database.py` (`markets_excluded(market_id, reason, excluded_at, stage, details, …)` PK `(market_id, reason, dataset_version)`; `AS_OF_COLUMNS`). Orden obligatorio; cada paso cierra con tests en verde antes del siguiente. **Todo el bloque toca ficheros protegidos por 2D §V → requiere DP-2D ratificado antes de ejecutar el paso 2.**

**Paso 0 — Rule-map: fuente única del `MarketContext`.**
- Las etiquetas `primary_source/primary_rule` (P_*) no existen en el repo: `resolution.parse_measurement_rule` (`src/weather_agent/polymarket/resolution.py:126-138`) sólo distingue por regex «Daily Observations» / «by the Forecast» / «Day High & Low» / NULL; `station_identifier` sólo se extrae de URLs wunderground (NULL para NOAA 11.528, HKO 1.859, CWA 77 en `cls2`; OBSERVADO).
- **`markets.measurement_rule` NO es clave de aplicabilidad ni de segmentación del operador.** Defecto OBSERVADO en `cls2` (mismo parser): la regex «Daily Observations» clasifica la frase de **fallback** NOAA como regla WU en **exactamente 3.333 mercados** (2.497 P_NOAA_TempColumn + 836 P_NOAA_HourlyData con `cls2.measurement_rule = "highest temperature in the 'Daily Observations' table"`). Cualquier ruta que use esa columna (2D §M, un `applies_to` provisional, una migración parcial) admitiría 3.333 mercados NOAA en el operador de la fila 5. Test `test_rule_map_disagrees_with_regex_column_on_noaa_fallback` (= 3.333 sobre el catálogo congelado). Ítem de roadmap designado **R29** (no localizado en `ROADMAP.md` sha `2448e554…`; UNKNOWN hasta que se registre). **DP-2D** incluye que la segmentación de 2D §M pase a `market_rule_map.measurement_rule_P`.
- Tabla congelada `market_rule_map(market_id, event_id, contract_source, measurement_rule_P, unit, rounding_rule, station_icao, station_tz, target_date_contractual, clause_lowest_bracket, fallback_R1, rule_map_sha)` derivada de `v3` + `STATION_TZ_v1.json` (55/55) + `v3.descr ~ 'lowest bracket'` + `rule_recuperable = 'R1_*'`; fichero de datos versionado con sha (sin migración de schema). Opcional para segmentación (no para el operador): `region`/`component` de `STATION_REGION_COMPONENT_v1.json`.
- `build_feature` lee **SOLO** esa tabla para el ctx, con lista `SELECT` explícita de columnas (nunca `markets.*`): test `test_build_feature_never_selects_markets_resolution_columns`. Ctx ausente → `rule_map_missing`. El valor `contract_source='TEST'` está **prohibido** en el rule-map de producción (test `test_rule_map_has_no_test_source`).
- Tests: `test_rule_map_counts` (las 11 filas de §2 exactas), `test_rule_map_station_tz_complete` (55/55, sin NULL en WU/NOAA), `test_rule_map_clause_counts` (2.475 / 225).

**Paso 1 — `ForecastCDF_v0` + protocolo `SettlementOperator`** (nuevo módulo `settlement/`). `ForecastCDF_v0 := clamp(cdf_legacy, 0, 1)` con soporte declarado `[values[0] − 1, values[-1] + 1]` y caso degenerado explícito (`values[0] == values[-1]` → masa 1 en ese punto, replicando `{minimum: 1.0}`). Único cambio respecto a `probability.py:66-85`: el recorte (OBSERVADO: la cola inferior `0.10·(x − (values[0] − 1))` no está acotada y da F < 0 para x < p10 − 1; la superior sí satura en 1). Registrado como **DP-CDF0**. `TestOnlyOperator` vive en `tests/support/` (no en `src/`), con `applies_to := contract_source == 'TEST'`. Tests nuevos: `test_forecast_cdf_is_proper` (F→0, F→1, monótona, recorte), `test_operator_protocol_contracts` (§1.4), `test_band_probability_partition_sums_to_one_exact` (tol 1e-12), `test_interval_floor_mapping`, `test_nearest_mapping`, `test_open_bands_*`, `test_unit_mismatch_fails_closed`, `test_operator_none_fails_closed`, `test_applies_to_is_identity_blind`, `test_settle_rejects_obs_available_after_asof`, `test_feature_json_has_no_evidence_fields`, `test_test_only_operator_not_importable_from_src`.

**Paso 2 — Retirar el nearest implícito.** `quantiles_to_distribution` deja de ser llamada por producción; se conserva como `legacy_nearest_distribution` marcada `@deprecated` y prohibida en `features.py` (test `test_features_do_not_import_legacy_nearest`). `band_probability(distribution, lo, hi)` discreta se mantiene para compatibilidad de tests, fuera de la ruta de `build_feature`.

**Paso 3 — Operador obligatorio y ctx.** `build_feature(..., operator: SettlementOperator)` y `generate_event_signals(..., operator: SettlementOperator)`: argumento posicional obligatorio sin default. `build_feature` construye el ctx desde `market_rule_map` (paso 0), llama `operator.applies_to(...)` y lanza `SettlementOperatorUnavailable(reason)` si no aplica. `feature_json` añade `operator_id`, `operator_version`, `cdf_version`, `unit_conversion`, `quantization`, `spec_version` (**DP-L1**: linaje en `feature_json`, sin columna nueva; `markets_excluded.details` como en §3.4).
- Tests que **cambian** (llamadas sin operador rompen; cada fixture debe **sembrar una fila de `market_rule_map`** con `contract_source='TEST'`, `measurement_rule_P='P_TEST'`, `unit`, `rounding_rule`, `station_tz`, `target_date_contractual`): `test_resolution_not_in_features.py` (llamadas en :82, :129, :191; aserciones `row is not None` en **:93, :140, :202**); `test_no_future_information.py` (llamadas :123, :171; aserción **:134**); `test_no_lookahead_adversarial.py` (llamadas :69, :113, :160; aserciones **:124, :171**); todas las de `test_strategy_a.py` → pasan `TestOnlyOperator`. Nota: `test_no_lookahead_adversarial.py:148-158` inserta en `markets` una fila con `winning_outcome/resolution_timestamp`; `build_feature` **no** debe leer `markets` (hoy no lo hace: «Resolution: intentionally NOT read»); la fixture del rule-map es una tabla distinta.
- Aserciones numéricas que **cambian** (recomputadas con `ForecastCDF_v0`, OBSERVADO): `test_resolution_not_in_features.py:204` 0,2777777778 (= mapeo ±0,5 renormalizado por 0,9) → **0,25** para banda (30,30) con cuantiles 28..32, idéntico bajo INTERVAL_FLOOR (F(31) − F(30)) y NEAREST (F(30,5) − F(29,5)); `test_probability.py:262-277` 0,50 para [26,27] con cuantiles 24..28 → **0,40** bajo INTERVAL_FLOOR (F(28) − F(26)) o **0,45** bajo NEAREST (F(27,5) − F(25,5)), según el operador de test declarado; `test_probability.py:26-35, 171-244` (claves enteras / colapso `{26: 1.0}`) se reescriben contra `legacy_nearest_distribution` o se eliminan; `test_strategy_a.py:14, 36-37, 148-151` (PW con funciones legacy) pasan a calcular PW con el operador de test.
- Tests que **no cambian**: `test_probability.py:83-159, 247-259` (bandas sobre diccionarios manuales), `test_resolution.py` completo.
- Tests **nuevos**: `test_build_feature_requires_operator` (TypeError sin operador), `test_build_feature_records_operator_lineage`, `test_build_feature_raises_settlement_unavailable_not_valueerror`, `test_strategy_a_excludes_without_operator` (reason = enum, no `executable_or_invalid_price`), `test_markets_excluded_reasons_enum`, `test_operator_applicability_matrix` (las 11 filas de §2 con su estado, incluida fila 9 FAIL_CLOSED y fila 8 p_weather FAIL_CLOSED), `test_training_label_is_winning_outcome_not_band_key`.

**Paso 4 — Operadores de producción**, uno por fila habilitada, cada uno con `EvidenceRef` (prereg / no-prereg / componentes) y sha: `HKO_ABSMAX_INTERVAL_FLOOR v1` (fila 10; `settle` + `band_probability`); `NOAA_TEMPCOL_F_PROXY_IEM v1` (fila 8; `settle`; `band_probability` lanza `SettlementOperatorUnavailable('window_not_discriminated_US_F')` hasta DP-W1); `WU_DAILYOBS_C_PROXY_IEM v1` y `NOAA_TEMPCOL_C_PROXY_IEM v1` (filas 5, 7; `quantization=NONE`, sólo `settle`). **No** se implementa `NOAA_HOURLY_F_PROXY_IEM` hasta cerrar §4.3. Tests: reproducir HKO 164/166, n_disc 81 (81/81 vs 4/81) y las 2 excepciones desde `HKO_OPERATOR_TEST.json` (fixture copiada con sha); reproducir E2 por estrato (7/7, 16/16, 6/6).

**Paso 5 — Guardas de entrenamiento.** M2/M3 y selección final de estrategia rechazan filas sin `operator_id` (`test_training_rejects_rows_without_operator`) y filas de M2 con `availability != 'ASOF_VERIFIED'` salvo bajo el preregistro R16 explícito.

**5.5 LOCKED / desbloqueo (declaración explícita, pendiente de ratificación por ambos — DP-2D):**
- Sigue LOCKED de 2D §F: forecast as-of `available_at ≤ T`; precio as-of `observation_time ≤ T`; guardas finales de `build_feature`; `Σ_bandas p_weather = 1` sobre partición válida; `p_model = p_weather` en V1; `weather_sum_tolerance = 1e-6`; interfaz `(lo, hi)` con `None` = abierta; `is_partition` como guarda.
- Se DESBLOQUEA únicamente y de forma enumerada: (i) 2D §F: la expresión `p_weather = band_probability(quantiles_to_distribution(p10..p90), lo, hi)` → `p_weather = operator.band_probability(ForecastCDF_v0(p10..p90), lo, hi)`; la cita de `test_full_partition_sums_to_one` como matemática autoritativa se sustituye por `test_band_probability_partition_sums_to_one_exact`; (ii) 2D §L: nuevo `except SettlementOperatorUnavailable` en `strategy_a` y `reason` del enum §3.4 con `stage='feature'`; (iii) 2D §M: segmentación por `market_rule_map.measurement_rule_P` en lugar de `markets.measurement_rule`; (iv) 2D §V: autorización expresa para modificar `features.py`, `probability.py` y sus tests en los pasos 1-3, y `labeling.py`/`database.py` **no se modifican** (label = `build_label`; sin cambio de schema).
- No se desbloquea la forma de la CDF más allá del recorte (§0.1, DP-CDF0).

---

## 6. Preregistro de la validación del operador

**6.1 Objetivo.** Medir que `operator.settle(obs, ctx, asof=None).band_key` reproduce `winning_outcome` del catálogo (93.182 no nulos; 39 NULL excluidos por construcción) por estrato (contract_source, measurement_rule_P, unit, con/sin cláusula).

**6.2 Muestra (congelada antes de ejecutar).**
- Universo: `umaResolutionStatus='resolved'`, `winning_outcome` no nulo, partición válida, `target_date_contractual`, observaciones obtenibles para la serie declarada. Sin exclusión post-hoc: los eventos `arch-` **se incluyen** y se reportan como sensibilidad (149 eventos / 1.639 mercados; HKO: 486838, 490245, 493669).
- HKO: los 166 eventos de `HKO_OPERATOR_TEST.json` (target_date 2026-03-16..08-31) son **muestra de selección** (in-sample). Holdout preregistrado: eventos con target_date ≥ 2026-09-01 — hoy **934576, 939963, 945943 (resueltos, 11 mercados cada uno; 945943 con cláusula lowest-bracket)** y los que se acumulen — hasta que 6.5 sea decidible.
- WU DailyObs C / NOAA TempColumn C-F: E2 (38, preregistrada) y discriminación (57, no preregistrada) son muestra de selección; holdout = mercados resueltos de esas reglas **no** incluidos en `SAMPLE_E2.json` ni en `B_CANDIDATES.json`, muestreados por estrato con semilla fija declarada en el artefacto; el estrato «con cláusula» se muestrea aparte.
- NOAA HourlyData F: sólo tras cerrar §4.3; el diseño de §4.3 es su preregistro.
- Excepciones conocidas (490245, 493669, 322448) permanecen en la muestra de selección y se reportan; no se reasignan.

**6.3 Métrica exacta.** Para cada estrato s: `tasa_s = #{m ∈ s : band_key(m) ∈ banda(winning_outcome(m))} / |s|`, con banda cerrada `[lo, hi]` y abiertas `(None, hi]` / `[lo, None)` en enteros (`parse_band`). Se reporta `k/n`, IC Wilson 95 % (z = 1,96), y la misma tasa para **cada operador alternativo de `settle`** sobre la **misma** muestra y la misma serie: para tenths {INTERVAL_FLOOR, ceil, half-up, half-even}; para whole-degree °F {tmpf NEAREST, `round(F(cuerpo))`, `floor(F(tg))`, `ceil(F(tg))`}; para ventana {LOCAL_CIVIL_DAY, UTC_DAY, LOCAL±1} sobre los casos donde difieren. **`n_disc` := casos con `band_key` distinto entre candidato y alternativa** (HKO floor vs half-up: 81); se reporta `k_disc` de cada uno (81 vs 4) y, como descriptivo, el subconjunto con **veredicto** de compatibilidad distinto (77, 77 vs 0).

**6.4 Q-test (cuantización °C, filas 5 y 7) — NOT_TESTABLE con los artefactos existentes.** Requeriría una serie en décimas para estaciones °C; OBSERVADO en `E2_RESULTS.json`: `H_LOCAL_tg = None` en 24/24 filas °C (P_NOAA_TempColumn A/B y P_WU_DailyObservations). Por tanto, con IEM no existe vía de desbloqueo de p_weather para las filas 5 y 7 (16.962 mercados) y quedan FAIL_CLOSED **sin sustituir por convención** (DP-Q). Cualquier fuente alternativa en décimas (no IEM) deberá preregistrarse aparte con nueva `spec_version`; hoy ninguna está identificada (§7).

**6.5 Criterio de aceptación (congelado, sin umbral arbitrario).** El operador candidato de un estrato se declara VALIDADO si, en el holdout:
1. el límite inferior del IC Wilson del candidato es **estrictamente mayor** que el límite superior del IC Wilson de cada operador alternativo de `settle` sobre la misma muestra (ICs disjuntos), y
2. sobre los `n_disc` casos, `k_disc(candidato) > k_disc(alternativa)` para toda alternativa, reportando el p exacto binomial de signo como descriptivo, y
3. toda excepción del candidato está listada por event_id con su valor fuente y banda ganadora, sin exclusión.
La alternativa obligatoria cuando no exista otra es un **operador de `settle`** sobre la misma serie (p. ej. `round_half_up(valor)`), nunca `legacy_nearest_distribution` (que es un mapeo CDF→bandas, no un operador de observaciones). **Para series ya enteras (`metar_body_c`, filas 5 y 7) INTERVAL_FLOOR y NEAREST son indistinguibles en `settle` (n_disc = 0, ICs idénticos): el criterio es NO DECIDIBLE por construcción**, lo que es coherente con su FAIL_CLOSED en p_weather y se declara. Si los ICs solapan, el estado es NO_DECIDIDO (no «rechazado»): se acumula holdout; nunca se rebaja el estado de evidencia por edición. Al alcanzar VALIDADO, la fila cambia `validation_state` (nueva `spec_version`); ningún otro estado cambia.

**6.6 Artefacto.** `docs/research/SETTLEMENT_OPERATOR_AUDIT.md` (exigido por ROADMAP R12, hoy inexistente) + JSON con sha, semilla, lista de market_ids, tabla por estrato (prereg / no-prereg / cláusula), ICs y excepciones. Debe **reproducir con cálculo y sha** toda cifra hoy citada sin artefacto versionado en `pmw-e2` (2.894/2.913; «timeline 99»; «ronda 13»; «B-7 19/647»), o retirarla. Se aclara (no se «corrige») la lectura de `WF_inventario_results.json` («81 casos discriminantes floor 81/81»): 81 es `n_disc` por `band_key`; 77 (`evidence/HKO_77_discriminating_floor_vs_round.csv`) es el subconjunto con veredicto distinto (bandas cerradas). Ambas cifras son reproducibles y la definición de §6.3 fija 81.

---

## 7. Incógnitas y límites

UNKNOWN (bloquean estado; no se resuelven por convención):
1. **Y_source_value desde la fuente contractual** en WU (DailyObs, genérico, byForecast) y NOAA (TempColumn, HourlyData): 55.803 mercados validados sólo contra proxy IEM; ningún caso donde el valor publicado por WU o wrh/timeseries se haya comparado con el bracket.
2. **Cuantización continuo→entero °C** del observador (filas 5, 7): no reportada y **NOT_TESTABLE con IEM** (grupo T ausente 24/24). **Fuente alternativa en décimas para estaciones °C: ninguna identificada.**
3. **WU DailyObs °F** (2.057): 0 casos.
4. **NOAA TempColumn ≡ HourlyData** (11.528 mercados): UNKNOWN; **subconjunto de observaciones de HourlyData** (H_hourly vs H_series, §4.3): no separado; N = 4 con datos directos.
5. **Ventana en EE. UU./°F, NOAA HourlyData, HKO y CWA**: no separable en la muestra (H_LOCAL = H_UTC en 14/14 °F); transferencia desde 7 ciudades Asia/Pacífico (°C, muestra no preregistrada) es INFERIDO (DP-W1).
6. **HKO**: escalar (floor(Y) vs [N,N+1)); 490245 sin explicación; 3 eventos de septiembre en holdout sin contrastar; «published» vs «finalized» sin timestamps; alcance 1 ciudad / 1 estación.
7. **CWA**: fuente, estación, timezone, precisión y operador UNKNOWN; prohibido extrapolar desde HKO.
8. **`record_version_asof(T)`** y política de revisiones de WU/HKO/CWA: UNKNOWN (sólo IEM 0/578). `available_at` es `None` para todo el histórico IEM procesado → `settle(asof=T)` sobre histórico es siempre `observations_not_available_asof`; sólo la captura prospectiva (D17-C) lo cambia.
9. **Excepción Taipei 322448** (NOAA TempColumn, NEITHER) y eventos NOAA TempColumn resueltos antes del fin de ventana («B-7 19/647», citado sin artefacto): sin investigar.
10. **Provenance de las etiquetas P_*/R*/flags de CATALOG_V2** (no en el repo; verificadas sólo por regex): prerrequisito §5 paso 0.
11. **Unidad de `weather_forecasts`** (sin columna unit; ingestión R15 PENDIENTE): `ForecastCDF` debe recibir unidad explícita o fail-closed (`unit_mismatch`).
12. **Activación efectiva del fallback R1 (3.333) y de la cláusula lowest-bracket (2.475)** por mercado: UNKNOWN; ningún operador reproduce esas ramas.
13. **Ítem R29**: no localizado en `ROADMAP.md` (sha `2448e554…`); su registro es prerrequisito documental del paso 0.

Límites de alcance (no son incógnitas del operador, pero acotan su uso):
- Forecast Tmax continua vs. máximo de observaciones muestreadas: el máximo real entre observaciones no es observable; límite de modelado, no de settlement.
- Las categorías de este documento son las de los informes fuente más los recómputos OBSERVADOS aquí declarados; cualquier reclasificación exige artefacto nuevo y `spec_version` nueva.
- `STATION_REGION_COMPONENT_v1` (24 estaciones `in_modelsel`, resto `INFERIDA`) acota la transferencia de M1, no el operador.

---

## 8. Decisiones pendientes de ratificación explícita (no evidencia)

- **DP-U1** — conversión afín de la CDF continua a °F, sólo en `ForecastCDF` (§1.4).
- **DP-L1** — linaje en `feature_json` y en `markets_excluded.details`, sin columna nueva ni cambio de schema (§3.4, §5 paso 3).
- **DP-2D** — desbloqueo enumerado de 2D §F, §L, §M y §V (§5.5).
- **DP-Q** — cuantización °C FAIL_CLOSED en p_weather (NOT_TESTABLE) en lugar de convención (§6.4).
- **DP-CDF0** — `ForecastCDF_v0 = clamp(cdf_legacy, 0, 1)` con soporte y caso degenerado declarados (§5 paso 1).
- **DP-W1** — transferencia de la ventana «día civil local» a estaciones EE. UU./°F (fila 8): mientras no se ratifique, p_weather de la fila 8 es FAIL_CLOSED; ratificarla exige declarar el riesgo (Tmax local vs settlement UTC) y no eleva la categoría del componente (queda INFERIDO_POR_TRANSFERENCIA en `components`).
- **DP-D17x** — extensión de D17 a la fuente contractual directa HKO_CLMMAXT con `compat_status='DIRECT'` (§4.1).

---

## Changelog v2 (hallazgo → estado + motivo)

**Refutador 1**
- **H0.0 (BLOQUEANTE, fila 9 / §4.3 / totales)** → **APLICADO.** «Y es el valor horario» reclasificado INFERIDO (N=4, 1 caso, H_hourly vs H_series no separadas); fila 9 FAIL_CLOSED en ambas columnas (`PROXY_NOT_AUDITED`, `series_filter_unverified`); §4.3 reescrito como verificación preregistrada de dos hipótesis; totales recalculados: settle 18.942 (20,3 %), pendientes 1.441 aparte. p_weather queda en 1.859 (no 1.980) porque además se aplica H0.2/H1.0 sobre la fila 8.
- **H0.1 (IMPORTANTE, 81 vs 77)** → **APLICADO.** Recómputo propio confirma n_disc = 81 (floor 81/81, half-up 4/81), half-even 73 (73/73 vs 4/73), ceil 145 (143/145 vs 13/145); 77 mantenido sólo como sensibilidad «veredicto distinto / bandas cerradas»; la «corrección» de §6.6 invertida en aclaración.
- **H0.2 (IMPORTANTE, ventana EE. UU./fila 8)** → **APLICADO (opción a + estructura de b).** Fila 8 `band_probability` FAIL_CLOSED (`window_not_discriminated_US_F`); §3.1 reescrito con evidencia end-to-end + `components` y categoría `NO_SEPARABLE_EN_MUESTRA`; DP-W1 registrada; `settle` de fila 8 se mantiene (end-to-end 6/6 compatible bajo ambas ventanas).
- **H0.3 (IMPORTANTE, preregistrado vs no)** → **APLICADO.** Columnas prereg/no-prereg en tabla y `EvidenceRef`; §4.2 cond. 1 reformulada.
- **H0.4 (IMPORTANTE, tz 91.285 DEMONSTRATED)** → **APLICADO con evidencia nueva.** Se retira la afirmación; `STATION_TZ_v1.json` (55/55, IEM tzname, sha `35d68e65…`) sustituye a `STATIONS_TZ.json` (28, sin conflictos entre ambos); verificación por estación en ejecución con `station_tz_unknown`; 91.285 queda como aritmética de `icao2`.
- **H0.5 (MENOR, Q-test)** → **APLICADO.** §6.4 declarado NOT_TESTABLE (24/24 `H_LOCAL_tg = None`, OBSERVADO); filas 5/7 FAIL_CLOSED sin vía con IEM.
- **H0.6 (MENOR, ForecastCDF_v0 colas)** → **APLICADO.** `clamp(cdf_legacy, 0, 1)` como único cambio; frase «sin cambiar sus colas» eliminada; DP-CDF0.
- **H0.7 (MENOR, 2.894/2.913 y 14–36 %)** → **APLICADO.** 2.894/2.913 marcado «citado del informe, sin artefacto» y excluido como evidencia; controles sustituidos por 10/37 = 27 % y 6/37 = 16 % (recómputo propio).
- **H0.8 (MENOR, HKO ventana vs §3.1)** → **APLICADO.** `window_kind='SOURCE_DAILY_ROW'`, componentes `SUBSUMIDO_EN_FUENTE` validados por 164/166, escrito en fila 10 y §3.1.
- **H0.9 (MENOR, NEAREST °F)** → **APLICADO_PARCIAL.** Se indica que `tmpf` es derivación IEM (PROXY) y se cuantifica la discriminación, pero con cifras del recómputo propio sobre las 14 filas °F: floor(F(tg)) incompatible en 4 (940515, 888238, 888245, 888240) y ceil en 3 (935131, 929767, 888235), no 2 y 1; ICs de las alternativas solapan con 14/14.
- **H0.10 (MENOR, sha DECISIONS)** → **APLICADO.** `DECISIONS.sha256` regenerado (OBSERVADO 19:48) y coincide con `DECISIONS.md` (`d36749bf…`); D17/D19 citados por identificador con ese sha.
- **H0.11 (MENOR, 0,953 → 0,952)** → **APLICADO.** 77/77 = (0,952–1,0); el IC principal pasa a 81/81 = (0,955–1,0).

**Refutador 2**
- **H1.0 (BLOQUEANTE, §3.1 vs filas 8/9/10)** → **APLICADO (opción b para el estado + `components` de la opción a).** Filas 8 y 9 FAIL_CLOSED en p_weather; universo p_weather = fila 10 (1.859, 1,99 %); HKO justificado (ventana/agregación realizadas por la fuente, 164/166 end-to-end); `EvidenceRef.components` añadido para que la regla sea implementable; DP-W1 para elevar la fila 8.
- **H1.1 (BLOQUEANTE, fila 9 inconsistente en 4 sitios; enum)** → **APLICADO.** Estado único FAIL_CLOSED; `PROXY_AUDITED_PENDING_SERIES_FILTER` eliminado del vocabulario (no se conserva el valor PENDING); `series_filter_unverified` en el enum; §4.3 con H_hourly/H_series y criterio 6.5; totales recalculados.
- **H1.2 (BLOQUEANTE, fuente del MarketContext)** → **APLICADO.** `market_rule_map` con las columnas exigidas + `station_tz` de `STATION_TZ_v1`; `build_feature` lee sólo esa tabla con SELECT explícito (test); `rule_map_missing`; seis aserciones listadas (:93, :140, :202; :134; :124, :171) con fixture mínima; `TestOnlyOperator.applies_to := contract_source == 'TEST'` y `'TEST'` prohibido en producción.
- **H1.3 (IMPORTANTE, mecanismo de exclusión / schema)** → **APLICADO.** `SettlementOperatorUnavailable` (no `ValueError`), `except` propio en `strategy_a`, `markets_excluded.reason` = enum y resto en `details`, sin cambio de schema; incluido en DP-L1 y DP-2D (§L, §V).
- **H1.4 (IMPORTANTE, Observation sin available_at; settle sin asof)** → **APLICADO.** `available_at`/`record_version` en `Observation`; `settle(obs, ctx, asof)`; `observations_not_available_asof`; `availability='Y_FINAL_UNKNOWN_ASOF'`; §0.2 restringe Y_final a evaluación y a M2 bajo R16; test nuevo.
- **H1.5 (IMPORTANTE, applies_to por identidad)** → **APLICADO.** `applies_to(contract_source, measurement_rule, unit, rounding_rule)` puro; test identity-blind; excepciones dentro del universo.
- **H1.6 (IMPORTANTE, cláusula lowest bracket)** → **APLICADO.** Recuentos corregidos y verificados (2.475 / 225; NOAA TempColumn 1.815/165, HourlyData 594/54, WU 55/5, HKO 11/1; endDate 08-31..09-04); `clause_lowest_bracket` en rule-map; §4.2 cond. 6; casos auditados con cláusula en E2: 4, todos de la fila 9 (929767 incluido); 0 en filas 5/7/8 → `PROXY_NOT_AUDITED` para esos 1.870 mercados; totales de settle efectivo recalculados.
- **H1.7 (IMPORTANTE, `markets.measurement_rule` como clave)** → **APLICADO.** Declarada NO apta; defecto de 3.333 desacuerdos verificado en `cls2` vs `v3` (2.497 + 836); test exacto; DP-2D §M → `measurement_rule_P`; R29 citado y marcado como no localizado en ROADMAP.
- **H1.8 (IMPORTANTE, Q-test NOT_TESTABLE)** → **APLICADO.** Igual que H0.5; incógnita «fuente alternativa en décimas: ninguna identificada» añadida a §7.
- **H1.9 (IMPORTANTE, definición de n_disc)** → **APLICADO.** `n_disc` := `band_key` distinto (81); 77 como descriptivo; §6.6 reescrito como aclaración.
- **H1.10 (IMPORTANTE, D17 y 2D LOCKED no declarados)** → **APLICADO.** Extensión de D17 para HKO directo (DP-D17x); `revision_status='UNKNOWN_PUBLISHED_VS_FINALIZED'` (1.078 / 781); §5.5 incluye 2D §L, §M y §V en DP-2D.
- **H1.11 (IMPORTANTE, ForecastCDF_v0 impropia; valores esperados)** → **APLICADO.** Definición con clamp, soporte y caso degenerado (DP-CDF0); valores recalculados y verificados: `test_resolution_not_in_features.py:204` 0,2777… → 0,25 (ambos mapeos); `test_probability.py:262` 0,50 → 0,40 (INTERVAL_FLOOR) / 0,45 (NEAREST).
- **H1.12 (IMPORTANTE, label de entrenamiento)** → **APLICADO.** Label de entrenamiento y de pago = `winning_outcome` vía `build_label`; `settle()` = covariable de auditoría y target de M2 con guarda as-of; test nuevo; §0.9 y §3.3.
- **H1.13 (MENOR, alternativa legacy; suma exacta)** → **APLICADO.** Alternativa obligatoria = operador de `settle` (`round_half_up`); NO DECIDIBLE declarado para series enteras; tolerancia 1e-12 en el test de partición; `weather_sum_tolerance` conservado como guarda.
- **H1.14 (MENOR, HKO aggregation; arch-)** → **APLICADO.** `aggregation='SOURCE_DAILY'`, `n_obs=1`; ambas excepciones marcadas `arch-` (y 486838 como tercer evento arch- HKO); prohibición de filtrarlas mantenida.
- **H1.15 (MENOR, provenance de citas; STATIONS_TZ v2)** → **APLICADO.** Citas de timeline marcadas «sin artefacto versionado» y exigida su reproducción en §6.6; `STATION_TZ_v1.json` (55/55) cubre el requisito de tz antes de habilitar settle en filas 5-8.
- **H1.16 (MENOR, unit UNKNOWN; tmpf; TestOnlyOperator)** → **APLICADO.** `unit_unknown` en enum y `MarketContext.unit` admite `'UNKNOWN'`; `metar_tgroup_tmpf` declarada serie IEM-derivada con fórmula a preregistrar como parte de la serie; `TestOnlyOperator` en `tests/support/`; `test_feature_json_has_no_evidence_fields`.
- **H1.17 (MENOR, HABILITADO vs VALIDADO)** → **APLICADO.** Columna `Val.` (SELECCION_IN_SAMPLE / VALIDADO / NO_DECIDIDO); HABILITADO declarado provisional; holdout HKO actualizado a 3 eventos / 33 mercados resueltos (934576, 939963, 945943 con cláusula); regla «nada se rebaja, sólo se eleva por §6.5».

**Sin hallazgo rechazado.** Único ajuste sobre una corrección propuesta: H0.9 (cifras 2/1 sustituidas por 4/3 del recómputo propio) y H0.0/H1.1 (p_weather 1.859 en lugar de 1.980, porque H0.2/H1.0 se aplican simultáneamente sobre la fila 8).