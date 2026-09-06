# SETTLEMENT_OPERATORS_SPEC.md

**Estado del documento:** BORRADOR PARA REFUTAR Y CONGELAR (v0.1, 2026-09-06).
**Fuentes:** informe 1 (código origin/main y diseño origin/codex/prices-ingestion-wip@6ed85ad), informe 2 (artefactos /Users/mariaaleu/pmw-e2 y rondas 11-13), informe 3 (inventario CATALOG_V2.duckdb, read_only). Nada de este documento consulta Open-Meteo ni fuentes contractuales en vivo.
**Convención de evidencia (heredada de los informes, sin reclasificar):** OBSERVADO · DEMONSTRATED · STRONGLY SUPPORTED · REFUTADO · INFERIDO · UNKNOWN. Donde la evidencia sea UNKNOWN, el operador es FAIL_CLOSED. Este documento no eleva ninguna categoría respecto a sus fuentes.

---

## 0. Objeto y qué NO decide

**Objeto.** Definir el `SettlementOperator`: la función que, dada una serie de observaciones (o de forecast, para las reglas by-the-Forecast) con timestamps y unidad, produce el valor/banda que liquida un mercado Polymarket de temperatura máxima, y la función dual que mapea una CDF continua de forecast a probabilidades por banda. Fija por (contract_source, measurement_rule) qué operador existe, con qué evidencia, y cuál es su estado (HABILITADO / HABILITADO_CON_PROXY / FAIL_CLOSED). Sustituye el operador nearest-integer implícito de `probability.quantiles_to_distribution` (origin/main `src/weather_agent/probability.py:89-98`), declarado "unsafe" en `PHASE_2E_SETTLEMENT_OPERATOR_DESIGN.md:12-17` ("That is an implicit round-to-nearest operator. It is not established by the market rules").

**Qué NO decide este documento:**
1. **No decide la forma de la distribución continua de forecast** (colas ±1 al 10 % de `probability.py:66-85`, soporte, interpolación). Esa CDF es un componente aparte (`ForecastCDF`, §1.3) con versión propia; este documento sólo exige que sea una CDF propia (F→0, F→1) y que declare unidad.
2. **No decide `record_version_asof(T)` ni `source_available_at`**: UNKNOWN en 93.221/93.221 mercados (informe 2; RECORD_VERSION_ASOF_AUDIT.md:55-66). El operador produce un valor retrospectivo (`Y_final`); no afirma cuándo estuvo disponible.
3. **No decide la reconciliación target_date / día civil en Wellington** (PHASE_2E_LEAD_HOURS_ANCHOR.md:135-137) ni los 40 eventos con endDate = target_date + 1 (marzo 2026; ROADMAP R8 pendiente). El operador consume `target_date` contractual como entrada y no lo deriva de endDate (DEMONSTRATED, ronda 13).
4. **No decide la política de revisiones de WU/HKO/CWA** (REVISION_IMPACT_AUDIT.md:87-96: "NO DEMUESTRA NADA sobre Wunderground").
5. **No afirma que IEM/METAR sea la fuente de settlement** de ningún mercado (informe 2: "explícitamente NO afirmado"). El proxy se usa bajo D17 (DECISIONS.md:354-358) y con `compat_status` declarado (§4).
6. **No infiere el operador de CWA desde HKO** ("son proveedores, estaciones y países distintos").
7. **No decide el desbloqueo de p_weather LOCKED de 2D §F** (PHASE_2D_STRATEGY_A_DESIGN.md:84-95); §5.5 declara qué debería desbloquearse y lo deja como decisión explícita de ambos (ROADMAP.md:145, :255).

---

## 1. Definición formal del operador

### 1.1 Entrada

Una **serie de observaciones** `S = {(t_i, y_i, u, serie)}` donde:
- `t_i` timestamp con zona (UTC canónico);
- `y_i` valor numérico;
- `u ∈ {C, F}` unidad de toda la serie (una serie no mezcla unidades);
- `serie` identifica el producto: `hko_clmmaxt` (valor diario en décimas), `metar_body_c` (entero °C del cuerpo METAR), `metar_tgroup_tmpf` (°F derivado del grupo T, rejilla 1 °F), `noaa_hourly_f` (valor horario), etc.

Más el **contexto del mercado**: `contract_source`, `measurement_rule`, `unit` del mercado (`markets.unit`, `database.py:159,182`), `rounding_rule` (`'whole degree'|'tenths'`), `station_tz`, `target_date` (DATE contractual extraída del texto, PREREG_E2.md), y para la dual, las bandas `(lo, hi)` enteras con `None` = banda abierta (`resolution.parse_band`, `resolution.py:92-112`).

Para reglas **by-the-Forecast** la entrada sería una serie de forecast, no de observación. No existe operador con evidencia para ellas (§2); la interfaz acepta el tipo pero ningún operador lo implementa.

### 1.2 Salida

```
SettlementResult:
  band_key:          int | None       # entero N que indexa la banda liquidada (N ≡ [N, N+1) en HKO; N ≡ Y entero en whole-degree)
  settled_value:     float | None     # Y_source_value tal como lo publica la fuente/proxy (décimas en HKO, entero en METAR)
  window_start_utc:  datetime         # ventana efectivamente usada
  window_end_utc:    datetime
  window_kind:       'LOCAL_CIVIL_DAY'   # única ventana con evidencia (§2)
  n_obs:             int
  aggregation:       'MAX'
  quantization:      'INTERVAL_FLOOR' | 'NEAREST' | 'NONE'
  unit:              'C' | 'F'
  evidence_category: 'STRONGLY_SUPPORTED' | 'DEMONSTRATED' | 'UNKNOWN' ...
  label_source:      'HKO_CLMMAXT' | 'IEM_METAR' | ...
  contract_source:   'HKO' | 'WU' | 'NOAA' | 'CWA'
  compat_status:     'DIRECT' | 'PROXY_AUDITED' | 'PROXY_NOT_AUDITED' | 'NONE'   (D17)
  operator_id, operator_version
  excluded_reason:   str | None       # si el operador no aplica → fail-closed
```

Nota HKO: `band_key = floor(Y)` es una clave de banda, **no** una afirmación de que el escalar liquidado sea `floor(Y)`: "floor(Y) y pertenencia a [N, N+1) son observacionalmente indistinguibles" (ronda 13, UNKNOWN escalar). Para construir p_weather ambas lecturas convergen.

### 1.3 Interfaz Python propuesta (protocolo; sin implementar)

Coherente con `PHASE_2E_SETTLEMENT_OPERATOR_DESIGN.md:19-33` (operator_id + versión inmutable; predicados de aplicabilidad; política de unidades; mapeo CDF→outcomes; tests bandas cerradas/abiertas; referencia de evidencia).

```python
from typing import Protocol, Sequence, Callable, Literal, NamedTuple
from datetime import datetime, date

Unit = Literal["C", "F"]

class Observation(NamedTuple):
    ts_utc: datetime
    value: float
    unit: Unit
    series: str            # 'hko_clmmaxt' | 'metar_body_c' | 'metar_tgroup_tmpf' | 'noaa_hourly_f' | ...

class MarketContext(NamedTuple):
    market_id: str
    contract_source: str   # 'WU' | 'NOAA' | 'HKO' | 'CWA'  (v3.primary_source; ver §7 provenance)
    measurement_rule: str  # 'P_WU_DailyObservations' | 'P_NOAA_TempColumn' | 'P_NOAA_HourlyData' | 'P_HKO_AbsDailyMax' | 'P_byForecast' | 'P_WU_GENERIC_sin_calificador' | 'P_UNKNOWN'
    unit: Unit
    rounding_rule: Literal["whole degree", "tenths"]
    station_tz: str        # IANA
    target_date: date      # contractual, del texto; NO derivada de endDate

class EvidenceRef(NamedTuple):
    category: str          # 'STRONGLY_SUPPORTED' | 'DEMONSTRATED' | 'UNKNOWN' | ...
    n_agree: int
    n_total: int
    wilson95: tuple[float, float]
    artifacts: tuple[str, ...]   # rutas + sha de los artefactos
    exceptions: tuple[str, ...]  # event_ids abiertos

class ForecastCDF(Protocol):
    """CDF continua PROPIA de la Tmax prevista: F(-inf)=0, F(+inf)=1, no decreciente."""
    unit: Unit
    version: str
    def cdf(self, x: float) -> float: ...

class SettlementOperator(Protocol):
    operator_id: str
    version: str                      # inmutable; cambio de comportamiento => nueva versión
    unit: Unit                        # unidad en la que opera; NO convierte observaciones
    window_kind: Literal["LOCAL_CIVIL_DAY"]
    aggregation: Literal["MAX"]
    quantization: Literal["INTERVAL_FLOOR", "NEAREST", "NONE"]
    required_series: str              # serie de observación admisible
    evidence: EvidenceRef
    compat_status: str                # 'DIRECT' | 'PROXY_AUDITED'

    def applies_to(self, ctx: MarketContext) -> bool: ...
    def settle(self, obs: Sequence[Observation], ctx: MarketContext) -> SettlementResult: ...
    def band_probability(self, F: ForecastCDF, lo: int | None, hi: int | None) -> float: ...
```

**Contratos del protocolo (a testear):**
- `settle` falla cerrado (`excluded_reason`) si: `not applies_to(ctx)`; `obs` vacía en la ventana; alguna `obs.unit != self.unit`; `obs.series != required_series`.
- `band_probability` con `lo > hi` → `ValueError` (conserva `probability.py:112-147`).
- **Suma exacta sobre partición**: para toda partición válida de bandas (`band_integrity`, `resolution.py:223-266`), `Σ band_probability = 1.0` sin renormalización, porque `F` es propia (esto elimina el descarte del 10 % y la renormalización de `probability.py:95-109`).
- Mapeo por cuantización (único paso que depende de evidencia por fuente):
  - `INTERVAL_FLOOR` (HKO, bandas N ≡ [N, N+1)): `P([lo,hi]) = F(hi+1) − F(lo)`; `(None,hi] → F(hi+1)`; `[lo,None) → 1 − F(lo)`.
  - `NEAREST` (whole-degree con Y = round(valor en décimas), sólo donde OBSERVADO): `P([lo,hi]) = F(hi+0.5) − F(lo−0.5)`; abiertas análogas. Los empates exactos en .5 tienen medida cero bajo una CDF continua; la regla de empate del observador queda UNKNOWN y se declara como tal.
  - `NONE`: no definido para forecast → `band_probability` lanza `NotImplementedError` (operador sólo-label).
- **Política de unidades**: el operador NO convierte observaciones (PREREG_E2.md: "NO se aplica round(), floor(), ceil() ni conversión C<->F para forzar coincidencia"). La conversión **de la CDF continua** de forecast a la unidad del mercado es una transformación afín exacta (`x·1.8+32`) sobre una variable continua, no una regla de settlement; se permite **sólo** en `ForecastCDF` y se registra en linaje (`unit_conversion='C_to_F_affine'`). Esto es una decisión de diseño (INFERIDO), no evidencia: **DP-U1, a ratificar**.

---

## 2. Tabla por (contract_source, measurement_rule)

Recuentos exactos: CATALOG_V2.duckdb tabla v3 (93.221 mercados, 8.557 eventos; informe 3). Evidencia: informe 2. IC = Wilson 95 % calculado sobre los recuentos citados.

**Componentes transversales del operador (vía proxy IEM/METAR, no vía fuente contractual):**
- Ventana W(m) = **día civil local de la estación**: STRONGLY SUPPORTED 54/57 (IC 0,856–0,982) (E2_DISCRIMINATION_EVIDENCE: LOCAL_ONLY 54, BOTH 2, NEITHER 1, UTC_ONLY 0). Día UTC: REFUTADO 0/57 (compat_utc 2/57, IC 0,010–0,119). Límite: los 57 son 7 ciudades Asia/Pacífico (Wellington 35), 41/57 de la regla P_WU_GENERIC; **0 casos discriminantes para NOAA HourlyData, HKO, CWA ni estaciones EE. UU./Europa** (en la muestra E2 H_UTC y H_LOCAL fueron idénticas 37/37). Corroboración indirecta: 2.894/2.913 eventos resuelven tras cerrar la ventana local (timeline 108 §4.3).
- Agregación **Y = max(observaciones sobre target_date)**: STRONGLY SUPPORTED 37/37 (E2), identidad exacta 22/22 en °C; controles ±1 día caen a 14–36 %.
- Cuantización en whole degree °C: "no hace falta operador de cuantización" DEMONSTRATED **para el proxy** (cuerpo METAR ya entero). Cómo el observador produce ese entero a partir del valor continuo: **UNKNOWN** (no reportado en ninguna ronda) → afecta sólo a la dual `band_probability`, no a `settle`.
- Cuantización en °F: rejilla nativa 1 °F vía grupo T, `tmpf = round(T_grupo→F)` 14/14 (IC 0,785–1,0); `round(cuerpo→F)` incompatible con el bracket en 5/14 → STRONGLY SUPPORTED que la serie relevante es `metar_tgroup_tmpf` con cuantización NEAREST sobre el valor en décimas.

| # | contract_source / measurement_rule | unit / rounding | Operador (ventana; agregación; cuantización; serie) | Evidencia (categoría, n, IC Wilson 95 %) | Mercados / eventos | Estado `settle` (label) | Estado `band_probability` (p_weather) |
|---|---|---|---|---|---|---|---|
| 1 | WU / P_WU_GENERIC_sin_calificador | C / whole degree | ninguno: Y indefinida por contrato ("el contrato no nombra tabla ni agregación", E-6) | UNKNOWN (Y contractual). Compat proxy local 41/41 (IC 0,914–1,0) es OBSERVADO pero no define el operador; regla excluida en PREREG_E2.md:7 | 26.763 / 2.433 | FAIL_CLOSED (`no_settlement_operator:Y_undefined_by_contract`) | FAIL_CLOSED |
| 2 | WU / P_WU_GENERIC_sin_calificador | F / whole degree | ninguno | UNKNOWN | 8.459 / 769 | FAIL_CLOSED | FAIL_CLOSED |
| 3 | WU / P_byForecast | C / whole degree | ninguno: "liquida un pronóstico, no es observación"; excluida por diseño (PREREG_E2.md:7); 0 casos | UNKNOWN | 25.982 / 2.412 | FAIL_CLOSED (`no_settlement_operator:by_forecast`) | FAIL_CLOSED |
| 4 | WU / P_byForecast | F / whole degree | ninguno | UNKNOWN | 9.500 / 896 | FAIL_CLOSED | FAIL_CLOSED |
| 5 | WU / P_WU_DailyObservations | C / whole degree | `WU_DAILYOBS_C_PROXY_IEM v1`: día civil local; max; cuantización NONE (Y entero del proxy); serie `metar_body_c` | Fuente WU: UNKNOWN (no reconstruida; matriz 6/8 falla R5, R8). Proxy IEM: STRONGLY SUPPORTED, E2 7/7 + discriminación 7/7 LOCAL_ONLY = 14/14 (IC 0,785–1,0). Cuantización continuo→entero °C: UNKNOWN | 6.996 / 636 | HABILITADO_CON_PROXY (`compat_status=PROXY_AUDITED`, n=14) | FAIL_CLOSED (`quantization_unknown_C`) hasta Q-test §6.4 |
| 6 | WU / P_WU_DailyObservations | F / whole degree | ninguno auditado: 0 casos °F en E2 (los 8 WU DailyObs muestreados son °C) | UNKNOWN | 2.057 / 187 | FAIL_CLOSED (`proxy_not_audited_F`) | FAIL_CLOSED |
| 7 | NOAA / P_NOAA_TempColumn | C / whole degree | `NOAA_TEMPCOL_C_PROXY_IEM v1`: día civil local; max; NONE; serie `metar_body_c` | Vista contractual wrh/timeseries: UNKNOWN (sin backend JSON; api.weather.gov retiene ~7 días → 0/6 validables). Proxy IEM: STRONGLY SUPPORTED, E2 16/16 (A-C 8/8, B-C 8/8) + discriminación 8/9 = 24/25 (IC 0,805–0,993); excepción Taipei 322448 NEITHER abierta. Cuantización °C: UNKNOWN | 9.966 / 906 | HABILITADO_CON_PROXY (`PROXY_AUDITED`, n=25, 1 excepción abierta) | FAIL_CLOSED (`quantization_unknown_C`) hasta Q-test §6.4 |
| 8 | NOAA / P_NOAA_TempColumn | F / whole degree | `NOAA_TEMPCOL_F_PROXY_IEM v1`: día civil local; max; NEAREST sobre décimas del grupo T; serie `metar_tgroup_tmpf` | Proxy IEM: STRONGLY SUPPORTED, E2 A-F 6/6 (IC 0,610–1,0); NEAREST apoyado en 14/14 °F transversal. 0 casos discriminantes local/UTC en EE. UU. | 121 / 11 | HABILITADO_CON_PROXY (`PROXY_AUDITED`, n=6) | HABILITADO_CON_PROXY (NEAREST) |
| 9 | NOAA / P_NOAA_HourlyData | F / whole degree | `NOAA_HOURLY_F_PROXY_IEM v1`: día civil local; max **sobre los valores horarios** (no todas las obs); NEAREST; serie `noaa_hourly_f` / `metar_tgroup_tmpf` restringida a horarias | Proxy IEM tmpf: 8/8 (IC 0,676–1,0). Directo api.weather.gov 4/8 reconstruibles: "Y es el valor horario, no el máximo de todas las observaciones" STRONGLY SUPPORTED N=4 (IC 0,510–1,0), 1 caso decisivo (Houston KHOU 2026-09-01: 87,80 °F fuera de 86–87 vs 87 °F horario dentro). 0 casos discriminantes de ventana | 1.441 / 131 | HABILITADO_CON_PROXY (`PROXY_AUDITED`, n=8+4) con precondición §4.3 (filtro de serie horaria) | HABILITADO_CON_PROXY (NEAREST) |
| 10 | HKO / P_HKO_AbsDailyMax | C / tenths | `HKO_ABSMAX_INTERVAL_FLOOR v1`: día civil Asia/Hong_Kong (target_date−1 16:00Z → target_date 16:00Z); valor diario CLMMAXT (agregación MAX ya realizada por la fuente); INTERVAL_FLOOR (banda N ≡ [N, N+1)); serie `hko_clmmaxt` | **Desde la fuente contractual**: [N, N+1) STRONGLY SUPPORTED 164/166 (IC 0,957–0,997); ceil 34/166 (IC 0,150–0,273), half-up 87/166 (IC 0,448–0,599), half-even 95/166 (IC 0,496–0,645) REFUTADOS; 77 discriminantes floor 77/77 (IC 0,953–1,0) vs half-up 0/77 (IC 0–0,048). Excepciones abiertas: 490245 (26,3 → '27°C', sólo ceil), 493669 (26,4 → '≤22°C', ningún operador; duplicado arch- del 503637 que liquidó 26 °C = floor). Escalar: UNKNOWN. Ventana: construida y consistente (closedTime − window_end ≥ +10,79 h en 168/168) pero NO probada por discriminación (0 casos HKO) | 1.859 / 169 | HABILITADO (`compat_status=DIRECT`) | HABILITADO (INTERVAL_FLOOR) |
| 11 | SIN_CLAUSULA (CWA Taipei) / P_UNKNOWN | C / tenths | ninguno: fuente inaccesible (401 / 404 / JS), 0/7 con valor fuente; estación e identidad UNKNOWN | UNKNOWN (BLOCKED 2/8) | 77 / 7 | FAIL_CLOSED (`source_inaccessible`) | FAIL_CLOSED |

**Totales derivados (INFERIDO aritméticamente del catálogo):**
- `settle` habilitado (directo + proxy auditado): filas 5, 7, 8, 9, 10 = **20.383 mercados (21,9 %)**; FAIL_CLOSED: 72.838 (78,1 %).
- `band_probability` habilitado (p_weather): filas 8, 9, 10 = **3.421 mercados (3,67 %)**; sin p_weather: 89.800 (96,3 %).
- El nearest-integer actual coincide con la evidencia únicamente en las filas 8-9 (°F, 1.562 mercados); en HKO (fila 10) está REFUTADO (half-up 87/166) y en el resto es UNKNOWN.

**Subcasos que la tabla no separa (OBSERVADO, informe 3):**
- 2.497 P_NOAA_TempColumn y 836 P_NOAA_HourlyData llevan `rule_recuperable = R1` por la cláusula de fallback ("If NOAA data … unavailable by 11:59 PM ET … the Weather Underground Daily Observations table will be used"). El operador aplica a la fuente **primaria**; si el fallback se activó en un mercado concreto es UNKNOWN por mercado. `applies_to` usa `primary_source/primary_rule` (v3), nunca `cls2.resolution_source` (que es NULL en 5.401 NOAA y URL de WU en 11 NOAA Shenzhen 2026-03-29).
- 55 WU DailyObs (Jinan 33, Taipei 22, sep-26) y 11 HKO sep-26 llevan la cláusula "resolve to the lowest bracket" sin datos: caso de settlement no meteorológico que ningún operador reproduce; se registra como `excluded_reason=no_data_clause_possible` sólo si `n_obs = 0`.

---

## 3. Política fail-closed (literal)

1. Un mercado recibe `p_weather` **si y sólo si** existe un `SettlementOperator` con `applies_to(ctx) == True`, `quantization != NONE` y `evidence.category ∈ {STRONGLY_SUPPORTED, DEMONSTRATED}` para **cada** componente (ventana, agregación, cuantización, serie) en la unidad del mercado.
2. Un mercado recibe `label` derivado de observaciones **si y sólo si** existe un operador con `applies_to(ctx) == True` y `compat_status ∈ {DIRECT, PROXY_AUDITED}`. Un mercado que no cumpla 1 ni 2 **no recibe p_weather ni label** y no entra en features, predictions, backtest ni entrenamiento de M2/M3 (`PHASE_2E_SETTLEMENT_OPERATOR_DESIGN.md:50`).
3. `winning_outcome` del catálogo (labeling.build_label, `labeling.py:31-63`) sigue siendo la **verdad de validación** (§6); no se usa como label de entrenamiento para mercados sin operador, para que el universo de features y de labels coincida.
4. Toda exclusión se registra en `markets_excluded(market_id, event_id, contract_source, measurement_rule, unit, operator_id | NULL, excluded_reason, spec_version, excluded_at)` con `excluded_reason` de un enum cerrado: `no_settlement_operator:Y_undefined_by_contract`, `no_settlement_operator:by_forecast`, `proxy_not_audited_F`, `quantization_unknown_C`, `source_inaccessible`, `unit_mismatch`, `series_mismatch`, `no_observations_in_window`, `no_data_clause_possible`, `operator_none`. Strategy A registra la exclusión como la fail-closed normal (`strategy_a.py:229-235`, mismo mecanismo que `is_partition`).
5. Prohibiciones explícitas: ningún operador por defecto (`operator=None` → exclusión, nunca nearest); ninguna conversión C↔F sobre observaciones; ningún filtro post-hoc (p. ej. `arch-`) para elevar la evidencia (timeline 99: "si se usa, se pre-registre antes y se valide sobre datos distintos").
6. Cambiar el estado de una fila de la tabla §2 requiere: (a) preregistro §6, (b) artefacto con sha, (c) nueva `spec_version`; nunca una edición silenciosa.

---

## 4. Proxy IEM/METAR para WU/NOAA (D17)

**4.1 Base.** DECISIONS.md D17 (:354-358, ADOPTADO 2026-09-06): labels WU/HKO/CWA vía proxy IEM/METAR "sólo bajo una auditoría de compatibilidad declarada (E2: 54/57 …; HKO floor [N, N+1) STRONGLY SUPPORTED)"; cada label lleva `label_source`, `contract_source`, `compat_status`; sin operador auditado → fail-closed.

**4.2 Condiciones para `compat_status = PROXY_AUDITED`** (todas necesarias):
1. Existe al menos una auditoría de compatibilidad preregistrada para la (fuente, regla, unidad) con Y del proxy comparada contra `winning_outcome` del catálogo (E2_RESULTS.json sha ec500428…, E2_DISCRIMINATION_EVIDENCE sha 9d925bf3…).
2. Ventana y agregación del proxy coinciden con las declaradas en §2 (día civil local de la estación; max; serie declarada).
3. La serie es la adecuada a la unidad: `metar_body_c` en °C; `metar_tgroup_tmpf` en °F (round(cuerpo→F) REFUTADO 5/14).
4. La estación tiene ICAO y timezone resueltos (timezone por estación DEMONSTRATED 91.285; UNKNOWN 1.936 = HKO + CWA, que no usan proxy).
5. Las excepciones abiertas están listadas (Taipei 322448 NEITHER) y no se eliminan.

**4.3 Precondición específica NOAA HourlyData.** El operador debe filtrar la serie a observaciones horarias (routine) y **verificar antes de habilitar** la coherencia entre "8/8 compatibles con tmpf en E2" y "Houston 87,80 °F (todas las observaciones) fuera del bracket": qué subconjunto de observaciones usó el recómputo IEM 8/8 es UNKNOWN en los informes. Hasta esa verificación, `compat_status = PROXY_AUDITED_PENDING_SERIES_FILTER` y la fila 9 se comporta como FAIL_CLOSED.

**4.4 Qué se reporta por label vía proxy:** `label_source='IEM_METAR'`, `contract_source`, `measurement_rule`, `compat_status`, `series`, `station_icao`, `station_tz`, `window_start_utc/end_utc`, `n_obs`, `settled_value`, `band_key`, `operator_id/version`, `audit_ref` (ruta + sha del artefacto de compatibilidad), `revision_status='UNKNOWN_FOR_CONTRACT_SOURCE'` (impacto de revisiones medido sólo en IEM: 0/578, REVISION_IMPACT_AUDIT.md:24-31; no extrapolable a WU).

**4.5 Qué NO afirma el proxy.** Que IEM sea la fuente de settlement; que WU muestre el cuerpo METAR o el grupo T; la tasa de revisión de WU; nada sobre °F en WU DailyObs (0 casos).

---

## 5. Migración del código

Referencias: diseño :43-50 (5 pasos); código actual `features.py:137-156,179-187`, `probability.py:57-109`, `strategy_a.py:180-203`. Orden obligatorio; cada paso cierra con tests en verde antes del siguiente.

**Paso 0 — Prerrequisito de clasificación.** Las etiquetas `primary_source/primary_rule` (P_*) no existen en el repo (`resolution.parse_measurement_rule` sólo distingue 'by the Forecast' / 'Daily Observations' / NULL, `resolution.py:126-139`; provenance de v3 UNKNOWN). `applies_to` necesita esas etiquetas → incorporar al repo un clasificador reproducible o una tabla congelada `market_rule_map(market_id, contract_source, measurement_rule, unit, rounding_rule, sha)` derivada de v3. Tests nuevos: `test_rule_map_counts` (los 11 recuentos de §2 exactos).

**Paso 1 — `ForecastCDF` + protocolo `SettlementOperator`** (nuevo módulo `settlement/`). Extraer la CDF de `quantiles_to_distribution` (`probability.py:65-85`) a `ForecastCDF_v0` **sin cambiar** sus colas (aislar el efecto del operador). Añadir `TestOnlyOperator` (id `TEST_ONLY`, `applies_to` sólo a fixtures) para tests. Tests nuevos: `test_forecast_cdf_is_proper` (F→0, F→1, monótona), `test_operator_protocol_contracts` (§1.3), `test_band_probability_partition_sums_to_one_exact` (sin renormalización), `test_interval_floor_mapping`, `test_nearest_mapping`, `test_open_bands_*`, `test_unit_mismatch_fails_closed`, `test_operator_none_fails_closed`.

**Paso 2 — Retirar el nearest implícito.** `quantiles_to_distribution` deja de ser llamada por producción; se conserva sólo como `legacy_nearest_distribution` marcada `@deprecated` y prohibida en `features.py` (test `test_features_do_not_import_legacy_nearest`). `band_probability(distribution, lo, hi)` sobre diccionarios discretos se mantiene para compatibilidad de tests, pero deja de estar en la ruta de `build_feature`.

**Paso 3 — Operador obligatorio.** `build_feature(..., operator: SettlementOperator)` y `generate_event_signals(..., operator: SettlementOperator)`: argumento posicional obligatorio sin default. `feature_json` añade `operator_id`, `operator_version`, `cdf_version`, `unit_conversion`, `quantization`; **decisión de linaje:** se registra en `feature_json` (sin migración de schema, respetando 2D:10-12 "Strategy A V1 no toca schema"); columna nueva sólo si se decide después (§7). Strategy A registra `no_settlement_operator` como motivo de exclusión (ROADMAP R12).
- Tests que **cambian** (llamadas sin operador rompen): `test_resolution_not_in_features.py:82,129,191-200`; `test_no_future_information.py:123,171`; `test_no_lookahead_adversarial.py:69,113,160`; todas las de `test_strategy_a.py` → pasan `TestOnlyOperator`.
- Aserciones numéricas que **cambian**: `test_resolution_not_in_features.py:204` (0.2777777778 es el mapeo ±0,5 renormalizado; con `ForecastCDF_v0` + INTERVAL_FLOOR el valor esperado se recalcula y se documenta en el test); `test_probability.py:262-277` (0.50); `test_probability.py:26-35, 171-244` (claves enteras / colapso `{26:1.0}`) se reescriben contra `legacy_nearest_distribution` o se eliminan; `test_strategy_a.py:14,36-37,148-151` (PW calculado con las funciones legacy) pasan a calcular PW con el operador de test.
- Tests que **no cambian**: `test_probability.py:83-159, 247-259` (bandas sobre diccionarios manuales; `test_full_partition_sums_to_one` sigue válido para la interfaz discreta), `test_resolution.py` completo (parseo de unit/rounding_rule/measurement_rule/band_integrity; sólo cambiaría si `measurement_rule` pasa a enum).
- Tests **nuevos**: `test_build_feature_requires_operator` (TypeError sin operador), `test_build_feature_records_operator_lineage`, `test_strategy_a_excludes_without_operator`, `test_markets_excluded_reasons_enum`, `test_operator_applicability_matrix` (las 11 filas de §2 con su estado).

**Paso 4 — Operadores de producción**, uno por fila habilitada, cada uno con `EvidenceRef` y sha: `HKO_ABSMAX_INTERVAL_FLOOR v1` (fila 10); `NOAA_TEMPCOL_F_PROXY_IEM v1` (8); `NOAA_HOURLY_F_PROXY_IEM v1` (9, tras §4.3); `WU_DAILYOBS_C_PROXY_IEM v1` y `NOAA_TEMPCOL_C_PROXY_IEM v1` (5, 7) con `quantization=NONE` (sólo `settle`). Tests: reproducir HKO 164/166 desde `HKO_OPERATOR_TEST.json` (fixture copiada con sha) y las 2 excepciones listadas; reproducir E2 por estrato.

**Paso 5 — Guardas de entrenamiento.** M2/M3 y selección final de estrategia rechazan filas sin `operator_id` (test `test_training_rejects_rows_without_operator`).

**5.5 LOCKED / desbloqueo (declaración explícita, pendiente de ratificación por ambos, ROADMAP.md:145,:255):**
- Sigue LOCKED de 2D §F: forecast as-of `available_at ≤ T` (`features.py:97-105`); precio as-of `observation_time ≤ T` (`:74-82`); guardas finales `:199-203`; `Σ_bandas p_weather = 1` exactamente sobre partición válida; `p_model = p_weather` en V1; `weather_sum_tolerance = 1e-6`; interfaz `(lo, hi)` con `None` = abierta; `is_partition` como guarda.
- Se DESBLOQUEA únicamente: la expresión `p_weather = band_probability(quantiles_to_distribution(p10..p90), lo, hi)` (2D:84-95) → `p_weather = operator.band_probability(ForecastCDF_v0(p10..p90), lo, hi)`. La cita de `test_full_partition_sums_to_one` como matemática autoritativa se sustituye por `test_band_probability_partition_sums_to_one_exact`.
- No se desbloquea la forma de la CDF (§0.1).

---

## 6. Preregistro de la validación del operador

**6.1 Objetivo.** Medir que `operator.settle(obs, ctx).band_key` reproduce `winning_outcome` del catálogo (`v3/cls2.winning_outcome`, 93.182 no nulos; 39 NULL excluidos por construcción) por (contract_source, measurement_rule, unit).

**6.2 Muestra (congelada antes de ejecutar).**
- Universo: mercados con `umaResolutionStatus='resolved'`, `winning_outcome` no nulo, partición válida, target_date contractual, y observaciones obtenibles para la serie declarada. Sin exclusión post-hoc: los eventos `arch-` **se incluyen** y se reportan aparte como sensibilidad (149 en el catálogo; 3 HKO).
- HKO: los 166 eventos de HKO_OPERATOR_TEST.json (sha 093e5891…) son **muestra de selección** (in-sample: sirvieron para elegir floor). Holdout preregistrado: eventos con target_date ≥ 2026-09-01 (934576, 939963, 945943 y los que se acumulen) hasta que el criterio 6.5 sea decidible.
- WU DailyObs C / NOAA TempColumn C-F / NOAA HourlyData F: E2 (38) y discriminación (57) son muestra de selección; holdout = mercados resueltos de esas reglas **no** incluidos en SAMPLE_E2.json ni en B_CANDIDATES.json, muestreados por estrato (fuente, regla, unidad) con semilla fija declarada en el artefacto.
- Excepciones conocidas (490245, 493669, 322448) permanecen en la muestra de selección y se reportan; no se reasignan.

**6.3 Métrica exacta.** Para cada estrato s: `tasa_s = #{m ∈ s : band_key(m) ∈ banda(winning_outcome(m))} / |s|`, con banda cerrada `[lo, hi]` y abiertas `(None, hi]` / `[lo, None)` en enteros (`parse_band`). Se reporta `k/n`, IC Wilson 95 % (fórmula fija, z = 1,96), y la misma tasa para **cada operador alternativo** sobre la **misma** muestra: para tenths {INTERVAL_FLOOR, ceil, half-up, half-even}; para whole-degree °F {serie tmpf NEAREST, serie cuerpo→F}; para ventana {LOCAL_CIVIL_DAY, UTC_DAY, LOCAL±1} sobre los casos donde difieren. Se reporta también `n_disc` (casos donde el candidato y la alternativa difieren) y `k_disc` del candidato.

**6.4 Q-test (cuantización °C, filas 5 y 7).** Sólo si existe una serie en décimas para estaciones °C (grupo T en IEM): comparar `cuerpo_entero` vs `round_half_up(décimas)`, `round_half_even(décimas)`, `floor(décimas)` por observación; métrica = tasa de identidad por regla con IC Wilson. Si no existe serie en décimas, el resultado es `NOT_TESTABLE` y las filas 5/7 siguen FAIL_CLOSED en p_weather (no se sustituye por convención).

**6.5 Criterio de aceptación (congelado, sin umbral arbitrario).** El operador candidato de un estrato se declara VALIDADO si, en el holdout:
1. el límite inferior del IC Wilson del candidato es **estrictamente mayor** que el límite superior del IC Wilson de cada operador alternativo sobre la misma muestra (ICs disjuntos), y
2. sobre los `n_disc` casos discriminantes, `k_disc(candidato) > k_disc(alternativa)` para toda alternativa, reportando el p exacto binomial de signo como descriptivo (no como umbral), y
3. toda excepción del candidato está listada por event_id con su valor fuente y banda ganadora, sin exclusión.
Si ninguna alternativa existe (p. ej. serie única), el criterio 1 se aplica contra el operador nearest legacy (`legacy_nearest_distribution` con ±0,5) como alternativa obligatoria.
Si los ICs solapan, el estado es NO_DECIDIDO (no "rechazado"): se acumula holdout; **nunca** se rebaja el estado de evidencia por edición.

**6.6 Artefacto.** `docs/research/SETTLEMENT_OPERATOR_AUDIT.md` (exigido por ROADMAP R12, hoy inexistente) + JSON con sha, semilla, lista de market_ids, tabla por estrato, ICs y excepciones. Se corrige antes la discrepancia documental WF_inventario_results.json:290 ("81 casos discriminantes") frente a los 77 reproducibles (`evidence/HKO_77_discriminating_floor_vs_round.csv`).

---

## 7. Incógnitas y límites

UNKNOWN (bloquean estado; no se resuelven por convención):
1. **Y_source_value desde la fuente contractual** en WU (DailyObs, genérico, byForecast) y NOAA (TempColumn, HourlyData): 55.803 mercados validados sólo contra proxy IEM; ningún caso donde el valor publicado por WU o wrh/timeseries se haya comparado con el bracket.
2. **Cuantización continuo→entero °C** del observador (filas 5, 7): no reportada; determina si p_weather en °C sería INTERVAL_FLOOR o NEAREST (diferencia de 0,5 °C en el mapeo).
3. **WU DailyObs °F** (2.057): 0 casos; se desconoce si WU muestra grupo T, cuerpo convertido u otra cosa.
4. **NOAA TempColumn ≡ HourlyData** (E-3/U-6, 11.528 mercados): UNKNOWN; "Y es el valor horario" descansa en N = 4.
5. **Serie usada en el recómputo IEM 8/8 de HourlyData** vs caso Houston 87,80 °F (§4.3).
6. **HKO**: escalar (floor(Y) vs [N,N+1)); 490245 sin explicación (B-6); ventana Asia/Hong_Kong no discriminada; 3 eventos de septiembre sin contrastar; alcance 1 ciudad / 1 estación.
7. **CWA**: fuente, estación, timezone, precisión y operador UNKNOWN; prohibido extrapolar desde HKO.
8. **record_version_asof(T)** y política de revisiones de WU/HKO/CWA: UNKNOWN (sólo IEM 0/578).
9. **Excepción Taipei 322448** (NOAA TempColumn, NEITHER) y 19/647 eventos NOAA TempColumn resueltos antes del fin de ventana (B-7): sin investigar.
10. **Provenance de las etiquetas P_*/R*/flags de CATALOG_V2** (no en el repo; verificadas sólo por regex): prerrequisito §5 paso 0.
11. **Unidad de `weather_forecasts`** (sin columna unit, `database.py:289-310`; ingestión R15 PENDING): `ForecastCDF` debe recibir unidad explícita o fail-closed (`unit_mismatch`).

Límites de alcance (no son incógnitas del operador, pero acotan su uso):
- La ventana "día civil local" sólo se ha discriminado en 7 ciudades Asia/Pacífico; su extensión a EE. UU./Europa es INFERIDA (no separable en E2).
- Forecast Tmax continua vs. max de observaciones muestreadas cada hora (HourlyData): el máximo real entre observaciones no es observable; es un límite de modelado, no de settlement.
- La cláusula "lowest bracket sin datos" (66 mercados sep-26) y el fallback NOAA→WU (3.333) son ramas de settlement no meteorológicas que ningún operador reproduce; sólo se registran.
- Las categorías de este documento son las de los informes fuente; cualquier reclasificación exige artefacto nuevo y `spec_version` nueva.

Decisiones pendientes de ratificación explícita (no evidencia): **DP-U1** conversión afín de la CDF continua a °F (§1.3); **DP-L1** linaje en `feature_json` sin columna nueva (§5 paso 3); **DP-2D** desbloqueo limitado de p_weather (§5.5); **DP-Q** que la cuantización °C quede FAIL_CLOSED hasta el Q-test en lugar de adoptar una convención.