# SETTLEMENT_OPERATORS_SPEC.md

**Estado del documento:** v3 — BORRADOR REVISADO TRAS RONDA 2 DE REFUTACIÓN, PENDIENTE DE CONGELAR (2026-09-07).
**Sustituye a:** v2 (2026-09-06), que a su vez sustituyó a `SETTLEMENT_OPERATORS_SPEC.draft.md` (v0.1). v2 aplicó los 30 hallazgos de `WF_r12_refutations.json`; v3 aplica los **17 hallazgos adicionales de la ronda 2** (2 BLOQUEANTES + 1 BLOQUEANTE de partición aritmética, 14 IMPORTANTES) más **dos autocorrecciones OBSERVADAS en esta ronda** (§6.6, §2.1). El detalle hallazgo → estado está en «Changelog v3».
**Fuentes:** código `origin/main` = `dfdc73e` (OBSERVADO; worktree read-only `/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-main`; `src/weather_agent/{probability,features,labeling,database}.py`, `src/weather_agent/polymarket/resolution.py`, `src/weather_agent/strategy/strategy_a.py`), `PHASE_2D_STRATEGY_A_DESIGN.md`, `PHASE_2E_SETTLEMENT_OPERATOR_DESIGN.md`, `PHASE_2E_LEAD_HOURS_ANCHOR.md`; artefactos de `/Users/mariaaleu/pmw-e2` (recómputo propio read-only 2026-09-07 sobre `HKO_OPERATOR_TEST.json` sha `093e5891…`, `E2_RESULTS.json` sha `ec500428…`, `E2_DISCRIMINATION_EVIDENCE.json` sha `9d925bf3…`, `NOAA_DIRECT.json` sha `bdcb7127…`, `NOAA_DIRECT_EXACT.json`, `STATION_TZ_v1.json` sha `35d68e65…`, `STATION_REGION_COMPONENT_v1.json` sha `b6aeeacb…`, `STATION_COORDS_SNAPSHOT_v1.3.json` sha `c1617939…`, `PREREG_E2.md` sha `c7f031ec…`, `PREREG_LEAD_HOURS_RANGE.md` sha `1d4161e8…`, `FEES_SEMANTICS.md` sha `4dbad3ab…`, `ROADMAP.md` sha `2448e554…`); `CATALOG_V2.duckdb` (`/Users/mariaaleu/pmw-catalog-v2/`, `read_only=True`, tablas `v3`, `cls2`, `ev`).
**Ancla de decisiones (OBSERVADO 2026-09-07):** `shasum -a 256 DECISIONS.md` = `4ca2cf76a21251e4df7b5ab03d0f2ddabdaadd8a459d2cbbe5a188cac156a1a7`, **coincide** con `DECISIONS.sha256` (regenerado 2026-09-07 21:41). El rango vigente es **D0…D22 más `A-23`** (no D0…D19, como decía v2). **Colisión de identificador:** existen **dos** entradas `D21` (sesión A: «R29 — clasificación de la fuente de settlement»; sesión B: «prices.py reconciliado»); `A-23` resuelve la colisión hacia delante con prefijos `A-n`/`B-n` y deja lo escrito sin renumerar, desambiguado por el sufijo «· Claude (sesión X)». **Este documento cita siempre `D21 (sesión A)` o `D21 (sesión B)`, nunca `D21` a secas**, y nunca por número de línea.
**Nada de este documento consulta Open-Meteo ni fuentes contractuales en vivo.** Todo el trabajo sobre el repo y sobre `pmw-e2` fue read-only; DuckDB abierto con `read_only=True`.

---

## Convención de evidencia (cerrada)

**Categorías end-to-end y de componente admisibles** (no se usa ninguna otra; ningún valor de `compat_status` puede aparecer como categoría de evidencia):

| Categoría | Significado | ¿Bloquea p_weather (§3.1)? |
|---|---|---|
| `DEMONSTRATED` | Reproducible por cálculo sobre artefacto en disco, sin hipótesis alternativa viva | **No** |
| `STRONGLY_SUPPORTED` | Compatible en muestra con IC Wilson 95 % y alternativas refutadas o dominadas | **No** |
| `SUBSUMIDO_EN_FUENTE` | El componente no lo ejecuta el operador: lo realiza la fuente contractual y queda validado end-to-end (caso HKO: ventana y agregación dentro de la fila CLMMAXT) | **No** |
| `NO_SEPARABLE_EN_MUESTRA` | La muestra es compatible con el componente y con su alternativa; no hay caso discriminante | **Sí** |
| `INFERIDO` | Razonamiento sin artefacto que lo separe de alternativas | **Sí** |
| `INFERIDO_POR_TRANSFERENCIA` | `INFERIDO` cuya única base es transferir evidencia de otro estrato (otra unidad, región o fuente). **Subcategoría de `INFERIDO`; bloquea igual, y su ratificación como decisión (DP-*) NO lo desbloquea** | **Sí** |
| `REFUTADO` | Incompatible con la muestra | **Sí** |
| `UNKNOWN` | Sin evidencia | **Sí** |

`OBSERVADO` se reserva para lecturas/recómputos propios sobre artefacto o catálogo en disco y **no** es una categoría de `EvidenceRef`: es el sello de procedencia de una cifra. `DEMONSTRATED` / `STRONGLY SUPPORTED` / `REFUTADO` se heredan de los informes con n e IC Wilson 95 %; en `EvidenceRef` se escriben con guion bajo (`STRONGLY_SUPPORTED`) por ser identificadores de código, y ese es el mismo conjunto que el de esta tabla.

**Regla maestra:** donde la evidencia de un componente sea `UNKNOWN`, el operador es **FAIL_CLOSED**. Este documento no eleva ninguna categoría respecto a sus fuentes; las cifras «citadas del informe» sin artefacto versionado se marcan como tales y no cuentan como evidencia.

---

## 0. Objeto y qué NO decide

**Objeto.** Definir el `SettlementOperator`: la función que, dada una serie de observaciones (o de forecast, para las reglas by-the-Forecast) con timestamps, disponibilidad y unidad, produce el valor/banda que liquida un mercado Polymarket de temperatura máxima, y la función dual que mapea una CDF continua de forecast a probabilidades por banda. Fija por `(contract_source, measurement_rule, unit, rounding_rule)` qué operador existe, con qué evidencia (end-to-end **y** por componente, ambas con categoría explícita), cuál es su estado (HABILITADO / HABILITADO_CON_PROXY / FAIL_CLOSED) y su estado de validación (SELECCION_IN_SAMPLE / VALIDADO / NO_DECIDIDO / NO_DECIDIBLE). Sustituye el operador nearest-integer implícito de `probability.quantiles_to_distribution`, declarado «unsafe» en `PHASE_2E_SETTLEMENT_OPERATOR_DESIGN.md` («That is an implicit round-to-nearest operator. It is not established by the market rules»).

**Qué NO decide este documento:**

1. **No decide la forma de la distribución continua de forecast** (colas ±1 al 10 %, soporte, interpolación). `ForecastCDF_v0` (§1.3, §5 paso 1) es la CDF legada **recortada a [0,1]** — ese recorte y el caso degenerado son las dos únicas decisiones que se toman sobre ella (**DP-CDF0**, §8).
2. **No decide `record_version_asof(T)` ni `source_available_at`** para el histórico: UNKNOWN en 93.221/93.221 mercados (`RECORD_VERSION_ASOF_AUDIT.md`). El operador produce `Y_final` retrospectivo cuando `asof=None` y lo declara (`availability='Y_FINAL_UNKNOWN_ASOF'`). El estrechamiento de D17-A que hace este documento (`Y_final` como target de M2 sólo bajo preregistro R16) **no es cita de D17: es decisión propia DP-D17y** (§8).
3. **No decide la reconciliación target_date / día civil en Wellington** (`PHASE_2E_LEAD_HOURS_ANCHOR.md` §8) ni los eventos con `endDate = target_date + 1` (ROADMAP R8, PARCIAL). El operador consume `target_date_contractual` del rule-map (§5 paso 0) y **no lo deriva de `endDate`**; §6.6 documenta un caso OBSERVADO (evento 276889) en el que derivarlo de `endDate` produce una ventana desplazada un día. El ancla `T = endDate − lead_hours·3600` con `endDate = target_date 12:00:00Z` en **8.557/8.557 eventos** (OBSERVADO en `ev`, recómputo propio 2026-09-07) fija el `asof` de `settle` cuando se use en M2 o backtest; leads operativos {9 h, 24 h} primarios, {36 h, 48 h} secundarios, > 48 h no operativos (`PREREG_LEAD_HOURS_RANGE.md` §3).
4. **No decide la política de revisiones de WU/HKO/CWA** (`REVISION_IMPACT_AUDIT.md`: «NO DEMUESTRA NADA sobre Wunderground»; «Lo mismo aplica a HKO y CWA»).
5. **No afirma que IEM/METAR sea la fuente de settlement** de ningún mercado. El proxy se usa bajo D17 con `compat_status` declarado (§4).
6. **No infiere el operador de CWA desde HKO** (proveedores, estaciones y países distintos).
7. **No decide el desbloqueo de p_weather LOCKED de 2D §F**, ni la modificación de `features.py`/`probability.py`/`labeling.py`/`database.py` prohibida por 2D §V, ni el mecanismo de exclusión de 2D §L; §5.5 declara exactamente qué habría que desbloquear (**DP-2D**) y lo deja como decisión explícita de ambos.
8. **No decide la semántica de fees ni el modelo de coste.** D19 (`FEES_SEMANTICS.md`, ADOPTADO) es independiente y **no se toca**: ninguna fórmula suya se modifica aquí. **Pero sí impacta la COBERTURA de `edge_gross`/`edge_net`**, y v2 lo negaba: por la cadena que 2D y D19 ya fijan (2D §W.1 `p_model = p_weather` en V1; §W.2 `fair_value = p_model`; §W.3 `edge_gross = fair_value − p_market`; D19: «`predictions.edge_net`/`signals.net_edge` se rellenan con H1»), `band_probability` es el productor de `p_weather` y, por tanto, de `fair_value`. Al restringir p_weather a la fila 10 (§3.1), **sólo 1.859 mercados (1,99 % del catálogo) podrán tener `fair_value` y `edge_net` bajo H1 de D19**. Este efecto se declara y se reporta a **R20**; no modifica ninguna fórmula de D19 ni su semántica.
9. **No define el label de entrenamiento ni el de pago**: ambos son `winning_outcome` vía `labeling.build_label` (gate temporal `prediction_time < resolution_timestamp` intacto). `settle()` produce `Y_source_value`/`band_key` como **covariable de auditoría (§6) y target de M2**, nunca como sustituto del label de pago (§3.3).
10. **No fija el valor de `weather_sum_tolerance`** ni promueve `p_model = p_weather` de DECIDED-V1 a LOCKED (§5.5).

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

Más el **contexto del mercado** `MarketContext`, cuya **fuente única** es la tabla operacional congelada `market_rule_map` (§5 paso 0): `contract_source`, `measurement_rule_P`, `unit`, `rounding_rule`, `station_icao`, `station_tz` (de `STATION_TZ_v1.json`), `target_date_contractual`, `clause_lowest_bracket`, `fallback_R1`, `fail_closed_reason`; y para la dual, las bandas `(lo, hi)` enteras con `None` = banda abierta (`resolution.parse_band`).

Más el **corte temporal** `asof: datetime | None` (§1.4): con `asof` dado, toda observación con `available_at` `None` o `> asof` invalida el cálculo (fail-closed `observations_not_available_asof`); con `asof=None` el resultado es `Y_final` retrospectivo y así se declara.

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
  evidence_category: str              # categoría END-TO-END de la EvidenceRef (tabla de la Convención)
  validation_state:  'SELECCION_IN_SAMPLE' | 'VALIDADO' | 'NO_DECIDIDO' | 'NO_DECIDIBLE'
  provisional:       bool             # True salvo validation_state == 'VALIDADO'  (§3.7)
  label_source:      'HKO_CLMMAXT' | 'IEM_METAR'
  contract_source:   'HKO' | 'WU' | 'NOAA' | 'CWA' | 'SIN_CLAUSULA'
  compat_status:     'DIRECT' | 'PROXY_AUDITED' | 'PROXY_NOT_AUDITED' | 'NONE'   # resuelto POR MERCADO (§1.3)
  revision_status:   'UNKNOWN_FOR_CONTRACT_SOURCE' | 'UNKNOWN_PUBLISHED_VS_FINALIZED'
  clause_lowest_bracket: bool         # copiado del rule-map; el operador NO reproduce esa rama
  operator_id, operator_version, spec_version
  excluded_reason:   str | None       # enum cerrado §3.4; si no es None, todo lo anterior es None/inaplicable
```

Nota HKO: `band_key = floor(Y)` es una clave de banda, **no** una afirmación de que el escalar liquidado sea `floor(Y)`: `floor(Y)` y pertenencia a `[N, N+1)` son observacionalmente indistinguibles (escalar UNKNOWN). Para construir p_weather ambas lecturas convergen.

### 1.3 Interfaz Python (protocolo; sin implementar)

Coherente con `PHASE_2E_SETTLEMENT_OPERATOR_DESIGN.md` «Required interface». **Cambio v3 (H-ronda2-G):** `compat_status` deja de ser atributo estático y pasa a método `compat_status_for(ctx)`, porque la condición 6 de §4.2 lo hace dependiente del mercado (estrato con/sin cláusula).

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
    measurement_rule: str            # 'P_WU_DailyObservations' | 'P_NOAA_TempColumn' | 'P_NOAA_HourlyData' |
                                     # 'P_HKO_AbsDailyMax' | 'P_byForecast' | 'P_WU_GENERIC_sin_calificador' | 'P_UNKNOWN'
    unit: Literal["C", "F", "UNKNOWN"]
    rounding_rule: str               # 'whole degree' | 'tenths' | otro
    station_icao: str | None         # v3.icao2; None en HKO (1.859) y CWA (77)
    station_tz: str | None           # IANA, de STATION_TZ_v1.json; None => fail-closed station_tz_unknown
    target_date: date | None         # contractual, del TEXTO; None => fail-closed target_date_unresolvable
    clause_lowest_bracket: bool
    fallback_R1: bool
    fail_closed_reason: str | None   # §5 paso 0: reason del enum §3.4 previo a resolver operador

class EvidenceRef(NamedTuple):
    category: str                    # categoría END-TO-END (band_key vs winning_outcome, misma (fuente, regla, unidad))
    n_agree_prereg: int              # muestra preregistrada (PREREG_E2 / HKO_OPERATOR_TEST)
    n_total_prereg: int
    n_agree_nonprereg: int           # muestra NO preregistrada (E2_DISCRIMINATION_EVIDENCE), declarada como tal
    n_total_nonprereg: int
    wilson95_prereg: tuple[float, float]
    components: dict[str, str]       # {'window','aggregation','quantization','series'} -> categoría de la Convención
    validation_state: Literal["SELECCION_IN_SAMPLE", "VALIDADO", "NO_DECIDIDO", "NO_DECIDIBLE"]
    validation_axes: dict[str, str]  # eje -> mismo enum; el peor eje domina validation_state
    risk_declared: tuple[str, ...]   # riesgos que una DP ratificada obliga a declarar (p. ej. DP-W1)
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

    def applies_to(self, contract_source: str, measurement_rule: str, unit: str, rounding_rule: str) -> bool: ...
    def compat_status_for(self, ctx: MarketContext) -> Literal["DIRECT", "PROXY_AUDITED", "PROXY_NOT_AUDITED"]: ...
    def settle(self, obs: Sequence[Observation], ctx: MarketContext, asof: datetime | None) -> SettlementResult: ...
    def band_probability(self, F: ForecastCDF, lo: int | None, hi: int | None) -> float: ...
```

### 1.4 Contratos del protocolo (a testear)

- **`applies_to` es función pura de `(contract_source, measurement_rule, unit, rounding_rule)`** y nunca de `market_id`, `event_id`, `target_date`, `station_icao` ni de ningún campo derivado del resultado. Motivo: las excepciones conocidas (322448, 490245, 493669) se identificaron por su `winning_outcome`; excluirlas por identidad sería una selección del universo condicionada al resultado — la misma clase de fuga que `PHASE_2E_LEAD_HOURS_ANCHOR.md` §4 describe («fuga en la selección…, no en las features», invisible a las guardas as-of). Test `test_applies_to_is_identity_blind`: mismo `(fuente, regla, unidad, redondeo)` con `market_id` distinto → mismo resultado, incluidos los tres event_ids de excepción. Las excepciones permanecen en el universo y se reportan en §6.
- **`compat_status_for(ctx)` sí depende del mercado** y sólo de `(estrato del operador, ctx.clause_lowest_bracket)`. No lee `winning_outcome`, `market_id` ni ningún campo de resultado. Test `test_compat_status_depends_only_on_stratum_and_clause`.
- **`settle` falla cerrado** (`SettlementResult.excluded_reason`) si, en este orden:
  1. `ctx.fail_closed_reason is not None` → ese reason (§5 paso 0);
  2. `not applies_to(...)` → `operator_none`;
  3. `ctx.unit == 'UNKNOWN'` → `unit_unknown`;
  4. `ctx.target_date is None` → **`target_date_unresolvable`** (nuevo en v3);
  5. `ctx.station_tz is None` y `window_kind == LOCAL_CIVIL_DAY` → `station_tz_unknown`;
  6. `ctx.clause_lowest_bracket` y `compat_status_for(ctx) == 'PROXY_NOT_AUDITED'` → **`clause_stratum_not_audited`** (nuevo en v3: sin esta cláusula el reason del enum era inalcanzable y los 1.870 mercados de §2.3 no tenían camino de exclusión);
  7. alguna `obs.unit != self.unit` → `unit_mismatch`; `obs.series != required_series` → `series_mismatch`;
  8. `obs` vacía en la ventana → `no_observations_in_window`; si además `ctx.clause_lowest_bracket` → se registra también `no_data_clause_possible`;
  9. `asof` dado y alguna obs con `available_at is None` o `available_at > asof` → `observations_not_available_asof`.
- `settle(asof=None)` devuelve `availability='Y_FINAL_UNKNOWN_ASOF'`; `settle(asof=T)` devuelve `availability='ASOF_VERIFIED'` y `max_available_at ≤ T`. Test `test_settle_rejects_obs_available_after_asof`.
- **`band_probability` nunca lanza `NotImplementedError`** (corrección v3). Contratos:
  - `lo > hi` → `ValueError` (única supervivencia del contrato heredado de `probability.band_probability`);
  - `quantization == 'NONE'` → `SettlementOperatorUnavailable('quantization_unknown_C')`;
  - componente bloqueante según §3.1 → `SettlementOperatorUnavailable(<reason del enum>)` (p. ej. `window_not_discriminated_US_F` en la fila 8).
  Motivo: `strategy_a` sólo tiene `except ValueError` (OBSERVADO en `strategy_a.py`, con el comentario que declara que `AssertionError` propaga a propósito); un `NotImplementedError` no lo captura nadie y abortaría la generación de señales de los 16.962 mercados de las filas 5 y 7 en lugar de registrarlos en `markets_excluded`. Test `test_band_probability_none_quantization_raises_unavailable_not_notimplemented`.
- **Suma sobre partición**: para toda partición válida (`band_integrity(...)['is_partition']`), `|Σ band_probability − 1.0| ≤ 1e-12` sin renormalización, porque `F` es propia y la suma es telescópica (test `test_band_probability_partition_sums_to_one_exact`, tolerancia 1e-12). `weather_sum_tolerance` es un parámetro obligatorio de Strategy A, **sin valor fijado por este documento** (§5.5).
- **Mapeo por cuantización** (único paso que depende de evidencia por fuente):
  - `INTERVAL_FLOOR` (HKO, bandas `N ≡ [N, N+1)`): `P([lo,hi]) = F(hi+1) − F(lo)`; `(None,hi] → F(hi+1)`; `[lo,None) → 1 − F(lo)`.
  - `NEAREST` (whole-degree con `Y = round(valor en décimas)`, sólo donde OBSERVADO en la serie): `P([lo,hi]) = F(hi+0.5) − F(lo−0.5)`; abiertas análogas. Empates exactos en .5 tienen medida cero bajo una CDF continua; la regla de empate del observador es UNKNOWN y se declara.
  - `NONE`: no definido para forecast → `SettlementOperatorUnavailable('quantization_unknown_C')` (operador sólo-`settle`).
- **Política de unidades**: el operador NO convierte observaciones (`PREREG_E2.md`: «NO se aplica round(), floor(), ceil() ni conversión C<->F para forzar coincidencia»). `metar_tgroup_tmpf` es una serie **derivada por IEM**; si la ingestión prospectiva (D17-C) parte del METAR crudo, la fórmula `tmpf = round(F(T_grupo))` se preregistra como **definición de la serie** (no como paso del operador), con test de identidad contra la columna `tmpf` de IEM. La conversión **de la CDF continua** de forecast a la unidad del mercado es una transformación afín exacta (`x·1.8+32`) sobre variable continua; se permite **sólo** en `ForecastCDF` y se registra en linaje (`unit_conversion='C_to_F_affine'`). Decisión de diseño (INFERIDO), **DP-U1**.
- `feature_json` **no** contiene campos de evidencia (`evidence`, `exceptions`, `n_agree*`, `wilson*`): test `test_feature_json_has_no_evidence_fields`. Sí contiene `provisional` (§3.7).

---

## 2. Tabla por (contract_source, measurement_rule, unit, rounding_rule)

Recuentos exactos: `CATALOG_V2.duckdb` tabla `v3` (**93.221 mercados, 8.557 eventos**), OBSERVADO por recómputo read-only 2026-09-07; las 11 filas suman exactamente el universo. IC = Wilson 95 % (z = 1,96) recomputado.

### 2.1 Componentes transversales (vía proxy IEM/METAR, no vía fuente contractual)

**Ventana W(m) = día civil local de la estación** (tz de `STATION_TZ_v1.json`, `tzname` del registro ASOS de IEM, 55/55 estaciones, `missing=[]`, `conflicts=[]`; OBSERVADO). Recómputo propio sobre `E2_DISCRIMINATION_EVIDENCE.json` (sha `9d925bf3…`, n = 57), **desagregando las dos magnitudes que v2 confundía**:

- **Compatibilidad con el día civil local: 56/57**, IC Wilson (0,907–0,997) — categoría `STRONGLY_SUPPORTED`.
- **Casos que además EXCLUYEN el día UTC (LOCAL_ONLY): 54/57**, IC (0,856–0,982).
- **Compatibilidad con el día UTC: 2/57**, IC (0,010–0,119) → **día UTC REFUTADO**.
- Desglose de compatibilidad: LOCAL_ONLY 54, BOTH 2, NEITHER 1 (Taipei 322448).
- Coherencia interna: las celdas de la tabla §2.2 usan `compat_local`, no LOCAL_ONLY — fila 1 «41/41», fila 5 «7/7», fila 7 «8/9»; 41+7+8 = **56** aciertos sobre 41+7+9 = **57**. El titular 54/57 de v2 no cuadraba con su propio desglose.
- **Nota sobre D17:** D17 cita «E2: 54/57 casos compatibles en día civil local». Esa cifra es LOCAL_ONLY, no la tasa de compatibilidad. Este documento **desagrega sin elevar ni corregir D17**: la categoría del componente no cambia (`STRONGLY_SUPPORTED` en el estrato auditado).

**Alcance de esa muestra (limitaciones que no se pueden transferir):** **NO está preregistrada** (PREREG_E2 cubre sólo los 38 eventos de E2; ningún preregistro menciona `B_CANDIDATES`/discriminación) y **es toda °C y toda Asia/Pacífico**: Wellington 35 (NZWN), Tokyo 10 (RJTT), Chengdu 5 (ZUUU), Beijing 3 (ZBAA), Seoul 2 (RKSI), Taipei 1 (RCTP), Guangzhou 1 (ZGGG); por regla P_WU_GENERIC 41, P_NOAA_TempColumn 9, P_WU_DailyObservations 7 (OBSERVADO). En E2 (preregistrada) `H_UTC` y `H_LOCAL` son **idénticas en 37/37 filas con datos** (OBSERVADO), incluidas las 14 filas °F de EE. UU. → **para EE. UU./°F, NOAA HourlyData, HKO y CWA la ventana está NO SEPARADA en la muestra**: categoría de componente `NO_SEPARABLE_EN_MUESTRA`, que **bloquea** (Convención). Su extensión a EE. UU./Europa sería `INFERIDO_POR_TRANSFERENCIA` (**DP-W1**, §8), que **también bloquea y no se desbloquea por ratificación**. La corroboración «2.894/2.913 eventos resuelven tras cerrar la ventana local» es **citada del informe de timeline, sin artefacto en `pmw-e2`**; no se usa como evidencia hasta reproducirse en el artefacto §6.6.

**Agregación Y = max(observaciones sobre target_date)**: `STRONGLY_SUPPORTED`, 37/37 (E2 con datos), identidad exacta 22/22 en °C con banda cerrada (OBSERVADO). Controles ±1 día recomputados sobre `E2_RESULTS.json`: `H_LOCAL_M1` 10/37 = 27 % (IC 0,154–0,430), `H_LOCAL_P1` 6/37 = 16 % (IC 0,077–0,311).

**Cuantización whole degree °C**: «no hace falta operador de cuantización» `DEMONSTRATED` **para el proxy** (el cuerpo METAR ya es entero). Cómo el observador/fuente produce ese entero desde el valor continuo: **UNKNOWN**, y **NOT_TESTABLE con los artefactos existentes** (`H_LOCAL_tg` es `None` en 24/24 filas °C de E2; OBSERVADO) → afecta a `band_probability`, no a `settle` (§6.4).

**Cuantización °F** (serie `metar_tgroup_tmpf`, derivación IEM, PROXY): `tmpf == round(F(tg))` en 14/14 filas °F (IC 0,785–1,0); compatibilidad con el bracket: `tmpf` 14/14 (0,785–1,0); `round(F(cuerpo))` 9/14 (IC 0,388–**0,837**; 5 incompatibles: 935131 Houston 87,08; 940515 NYC 73,94; 888238 Atlanta 91,94; 888245 SF 75,92; 888240 Chicago 75,92); `floor(F(tg))` 10/14 (0,454–0,883; 4 incompatibles: 940515, 888238, 888245, 888240); `ceil(F(tg))` 11/14 (0,524–0,924; 3 incompatibles: 935131 Houston 87,08; 929767 Miami 91,04; 888235 Seattle 75,02) — OBSERVADO, recómputo propio 2026-09-07. Los ICs de las alternativas **solapan** con 14/14: la discriminación NEAREST vs floor/ceil descansa en 4 y 3 casos. Ningún caso está cerca de un empate .5. Lo evidenciado es la derivación de IEM, no el proceso del observador ni de NOAA.

### 2.2 Tabla

Columnas: **Cat. e2e** = `EvidenceRef.category` end-to-end (Convención); **Ev. prereg** = muestra preregistrada; **Ev. no-prereg** = discriminación (no preregistrada); **Val.** = `validation_state` (§6.5). El estado se desdobla en dos celdas por estrato: **sin cláusula** / **con cláusula lowest-bracket**.

| # | contract_source / measurement_rule | unit / rounding | Operador (ventana; agregación; cuantización; serie) | Cat. e2e | Evidencia (prereg · no-prereg) y `components` | Mercados / eventos (de ellos, con cláusula) | `settle` sin cláusula | `settle` con cláusula | `band_probability` (p_weather) | Val. |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | WU / P_WU_GENERIC_sin_calificador | C / whole degree | ninguno: Y indefinida por contrato (no nombra tabla ni agregación) | **UNKNOWN** | Y contractual UNKNOWN. Compat proxy local 41/41 (IC 0,914–1,0) OBSERVADO en muestra no preregistrada, no define el operador; regla excluida en PREREG_E2 | 26.763 / 2.433 (0) | FAIL_CLOSED (`no_settlement_operator:Y_undefined_by_contract`) | — | FAIL_CLOSED | — |
| 2 | WU / P_WU_GENERIC_sin_calificador | F / whole degree | ninguno | **UNKNOWN** | — | 8.459 / 769 (0) | FAIL_CLOSED (ídem) | — | FAIL_CLOSED | — |
| 3 | WU / P_byForecast | C / whole degree | ninguno: liquida un pronóstico; excluida por diseño (PREREG_E2); 0 casos | **UNKNOWN** | — | 25.982 / 2.412 (0) | FAIL_CLOSED (`no_settlement_operator:by_forecast`) | — | FAIL_CLOSED | — |
| 4 | WU / P_byForecast | F / whole degree | ninguno | **UNKNOWN** | — | 9.500 / 896 (0) | FAIL_CLOSED (ídem) | — | FAIL_CLOSED | — |
| 5 | WU / P_WU_DailyObservations | C / whole degree | `WU_DAILYOBS_C_PROXY_IEM v1`: LOCAL_CIVIL_DAY; MAX; NONE; `metar_body_c` | **STRONGLY_SUPPORTED** (proxy; fuente WU UNKNOWN, no reconstruida) | prereg E2 **7/7** (IC 0,646–1,0) · no-prereg 7/7 compat_local. `components`: window `STRONGLY_SUPPORTED` (Asia/Pac., °C), aggregation `STRONGLY_SUPPORTED`, series `DEMONSTRATED`, quantization **`UNKNOWN`** | 6.996 / 636 (**55** / 5) | HABILITADO_CON_PROXY (`PROXY_AUDITED`; n_prereg = 7) | **FAIL_CLOSED** `clause_stratum_not_audited` (`PROXY_NOT_AUDITED`, §4.2 cond. 6; 0 casos auditados con cláusula) | **FAIL_CLOSED** (`quantization_unknown_C`; Q-test NOT_TESTABLE) | **NO_DECIDIBLE** (eje cuantización) |
| 6 | WU / P_WU_DailyObservations | F / whole degree | ninguno auditado: 0 casos °F en E2 | **UNKNOWN** | — | 2.057 / 187 (0) | FAIL_CLOSED (`proxy_not_audited_F`) | — | FAIL_CLOSED | — |
| 7 | NOAA / P_NOAA_TempColumn | C / whole degree | `NOAA_TEMPCOL_C_PROXY_IEM v1`: LOCAL_CIVIL_DAY; MAX; NONE; `metar_body_c` | **STRONGLY_SUPPORTED** (proxy; vista contractual wrh/timeseries UNKNOWN) | prereg E2 **16/16** (A-C 8/8, B-C 8/8; IC 0,806–1,0) · no-prereg 8/9 (IC 0,565–0,980; excepción Taipei 322448 NEITHER, abierta). `components` como fila 5 | 9.966 / 906 (**1.815** / 165) | HABILITADO_CON_PROXY (`PROXY_AUDITED`; n_prereg = 16; 1 excepción abierta) | **FAIL_CLOSED** `clause_stratum_not_audited` | **FAIL_CLOSED** (`quantization_unknown_C`) | **NO_DECIDIBLE** (eje cuantización) |
| 8 | NOAA / P_NOAA_TempColumn | F / whole degree | `NOAA_TEMPCOL_F_PROXY_IEM v1`: LOCAL_CIVIL_DAY; MAX; NEAREST (vía serie IEM); `metar_tgroup_tmpf` | **STRONGLY_SUPPORTED** (proxy) | prereg E2 A-F **6/6** (IC 0,610–1,0; KHOU, KATL, KSFO, KORD, KAUS, KSEA) · no-prereg 0. `components`: window **`NO_SEPARABLE_EN_MUESTRA`** (H_LOCAL = H_UTC 6/6; 0 discriminantes EE. UU./°F), aggregation `STRONGLY_SUPPORTED`, series `STRONGLY_SUPPORTED`, quantization `STRONGLY_SUPPORTED` (14/14 transversal, derivación IEM) | 121 / 11 (**0**) | HABILITADO_CON_PROXY (`PROXY_AUDITED`; n_prereg = 6; end-to-end compatible bajo ambas ventanas) | n/a (0 mercados) | **FAIL_CLOSED** (`window_not_discriminated_US_F`) — **sólo** un caso discriminante local/UTC en estación EE. UU./°F lo abre; DP-W1 **no** lo abre (§3.1, §8) | SELECCION_IN_SAMPLE (eje ventana `NO_DECIDIDO`) |
| 9 | NOAA / P_NOAA_HourlyData | F / whole degree | **ninguno habilitado.** Candidato `NOAA_HOURLY_F_PROXY_IEM v1` pendiente de §4.3; sin operador, no hay `compat_status` que portar | **UNKNOWN** | Proxy IEM tmpf: prereg E2 8/8 (IC 0,676–1,0), **pero el subconjunto de observaciones usado es UNKNOWN**. Directo api.weather.gov: 4/8 filas con datos; **3/4 discriminan** contra «máximo sobre TODAS las obs del API» (Houston KHOU 2026-09-01: `nws_maxF_local` 87,8 fuera de 86–87 vs `iem_tmpf` 87,0 dentro; NYC KLGA 2026-09-02: 73,94 fuera de 74–75 vs 74,0 dentro; Miami KMIA 2026-08-31: 91,04 fuera de 90–91 vs 91,0 dentro); **Dallas KDAL 2026-09-04 no discrimina** (98,96 y 99,0 ambos dentro de 98–99). **0/4 separan H_hourly de H_series**: ninguna fila del artefacto lleva la marca rutinaria/especial. «Y es el valor horario» = **INFERIDO**. Ningún artefacto en disco calcula un máximo sólo-horario de api.weather.gov | 1.441 / 131 (**594** / 54) | **FAIL_CLOSED** (`fail_closed_reason = 'series_filter_unverified'` en el rule-map, §5 paso 0); reportados aparte como «pendientes §4.3» | ídem | FAIL_CLOSED (`series_filter_unverified`) | — |
| 10 | HKO / P_HKO_AbsDailyMax | C / tenths | `HKO_ABSMAX_INTERVAL_FLOOR v1`: **SOURCE_DAILY_ROW** (fila CLMMAXT de `target_date`, día civil Asia/Hong_Kong = target_date−1 16:00Z → target_date 16:00Z, ventana realizada por la fuente); **SOURCE_DAILY**; INTERVAL_FLOOR (`N ≡ [N, N+1)`); `hko_clmmaxt` | **STRONGLY_SUPPORTED** (categoría heredada de D17; este documento no la eleva) | **Desde la fuente contractual** (`HKO_OPERATOR_TEST.json`, 166 resueltos, recómputo propio 2026-09-07): floor 164/166 (IC 0,957–0,997); ceil 34/166 (0,150–0,273), half-up 87/166 (0,448–0,599), half-even 95/166 (0,496–0,645) **REFUTADOS**. Discriminación por `band_key` distinto: **floor vs half-up n_disc = 81: floor 81/81 (0,955–1,0) vs half-up 4/81 (0,019–0,120)**; floor vs half-even n_disc = 73: 73/73 (0,950–1,0) vs 4/73 (0,022–0,133); floor vs ceil n_disc = 145: 143/145 (0,951–0,996) vs 13/145 (0,053–0,147). Sensibilidad «veredicto distinto» (bandas cerradas): 77 casos, floor 77/77 (0,952–1,0) vs half-up 0/77. 16 mitades exactas: floor 16/16 (0,806–1,0). Excepciones abiertas, **ambas `arch-`**: 490245 (26,3 → '27°C', sólo ceil) y 493669 (26,4 → '≤22°C', ningún operador; duplicado del 503637 que liquidó 26 °C = floor). Escalar: UNKNOWN. `components`: window **`SUBSUMIDO_EN_FUENTE`**, aggregation **`SUBSUMIDO_EN_FUENTE`** (ambas realizadas dentro de la fila CLMMAXT y validadas end-to-end por los 164/166), quantization `STRONGLY_SUPPORTED`, series **`DEMONSTRATED`** (fuente contractual directa; `completeness = 'C'` en 166/166) | 1.859 / 169 (**11** / 1) | HABILITADO (`compat_status = DIRECT`; `revision_status = 'UNKNOWN_PUBLISHED_VS_FINALIZED'`) | HABILITADO **DIRECT flagueado** (945943, 11 mercados): label emitido con `clause_lowest_bracket = True` y reportado como estrato aparte (§4.2 cond. 6, rama DIRECT) | **HABILITADO** (INTERVAL_FLOOR) | SELECCION_IN_SAMPLE (holdout: 3 eventos / 33 mercados resueltos, §6.2) |
| 11 | SIN_CLAUSULA (CWA Taipei) / P_UNKNOWN | C / tenths | ninguno: fuente inaccesible (401/404/JS), 0/7 con valor fuente; estación e identidad UNKNOWN | **UNKNOWN** | — | 77 / 7 (0) | FAIL_CLOSED (`source_inaccessible`) | — | FAIL_CLOSED | — |

**Verificación de cierre (OBSERVADO):** Σ mercados = 93.221; Σ eventos distintos = 8.557; Σ con cláusula = 55 + 1.815 + 594 + 11 = **2.475** en **225** eventos (`descr ilike '%lowest bracket%'`, endDate 2026-08-31…09-04).

### 2.3 Totales derivados — **una sola partición cerrada sobre 93.221**

v2 publicaba dos lecturas incompatibles (18.942 «habilitado» y 74.279 «resto») cuyos porcentajes sumaban 99,5 %: los 1.870 mercados con cláusula de las filas 5/7/8 se contaban a la vez como habilitados y como excluidos. v3 publica **una única partición**, recomputada sobre las filas:

| Estado (excluyente y exhaustivo) | Mercados | % de 93.221 | `excluded_reason` |
|---|---|---|---|
| **`settle` emitido** (label producido) — filas 5, 7, 8, 10 sin cláusula + fila 10 con cláusula | **17.072** | **18,31 %** | — |
| **Cláusula lowest-bracket no auditada** — filas 5 (55) + 7 (1.815) + 8 (0) | **1.870** | **2,01 %** | `clause_stratum_not_audited` |
| **Pendientes §4.3** — fila 9 | **1.441** | **1,55 %** | `series_filter_unverified` |
| **Sin operador** — filas 1, 2, 3, 4, 6, 11 | **72.838** | **78,13 %** | `no_settlement_operator:*`, `proxy_not_audited_F`, `source_inaccessible` |
| **Total** | **93.221** | **100,00 %** | |

- **Cobertura teórica del operador antes de la condición 6** (filas 5+7+8+10 = 6.996 + 9.966 + 121 + 1.859) = **18.942 (20,32 %)**. **NO es cobertura de label**: 1.870 de esos mercados no reciben label por §4.2 cond. 6. Se conserva únicamente como magnitud descriptiva y así etiquetada.
- **Total que NO recibe label** = 1.870 + 1.441 + 72.838 = **76.149 (81,69 %)**. La cifra 74.279 (79,68 %) de v2 es sólo el complemento de la cobertura teórica y no debe leerse como «sin label».
- **`band_probability` habilitado (p_weather)**: fila 10 = **1.859 mercados (1,99 %)**; sin p_weather **91.362 (98,01 %)**. **No existe la línea «si se ratifica DP-W1 → 1.980»**: DP-W1 no desbloquea p_weather (§3.1, §8). La única vía para la fila 8 es ≥ 1 caso discriminante local/UTC en estación EE. UU./°F.
- El nearest-integer legado coincide con la serie evidenciada únicamente en la fila 8 (121 mercados, y sólo por la serie `tmpf` derivada de IEM); en HKO (fila 10) está **REFUTADO** (half-up 87/166; 4/81 en discriminantes) y en el resto es UNKNOWN.

### 2.4 Subcasos que la tabla no separa (OBSERVADO en `v3`/`cls2`)

- **Fallback NOAA→WU (R1):** `rule_recuperable = 'R1_WU_DailyObservations'` en 12.386 mercados, de los cuales **2.497 P_NOAA_TempColumn + 836 P_NOAA_HourlyData = 3.333** son NOAA (el resto, 9.053, son P_WU_DailyObservations, donde la frase es la cláusula primaria). La cláusula es «If NOAA data … unavailable by 11:59 PM ET … the Weather Underground Daily Observations table will be used». El operador aplica a la fuente **primaria** (`v3.primary_source/primary_rule`); si el fallback se activó en un mercado concreto es UNKNOWN por mercado. `applies_to` nunca usa `cls2.resolution_source` (NULL en 5.401 NOAA; URL de WU en 11 NOAA Shenzhen 2026-03-29) **ni `markets.measurement_rule`** (§5 paso 0).
- **Cláusula «resolve to the lowest bracket»** («In the event that there is no data for the observation date by 11:59 PM ET on the day following the observation date»): **2.475 mercados / 225 eventos**, endDate 2026-08-31…09-04: NOAA TempColumn C 1.815/165; NOAA HourlyData F 594/54; WU DailyObs C 55/5 (Jinan, Taipei); HKO 11/1 (945943). Es una rama de settlement **no meteorológica** que depende de la disponibilidad del dato **en la fuente contractual** (UNKNOWN por mercado): IEM puede tener `n_obs > 0` cuando WU/NOAA no los tuvo, y el label del proxy divergiría del pago. De ahí §4.2 cond. 6 y el flag `clause_lowest_bracket` en el rule-map; `no_data_clause_possible` sólo se registra cuando además `n_obs = 0`. **Casos auditados con cláusula:** E2 contiene 4 eventos (929767, 935131, 940515, 952455), **todos P_NOAA_HourlyData °F = fila 9** (FAIL_CLOSED por otra razón) — verificado por recómputo sobre `v3` cruzando los 38 event_ids de E2; en filas 5, 7, 8: **0** casos auditados con cláusula; en HKO: 945943 está en el holdout §6.2.
- **Estados no resueltos:** `umaResolutionStatus` = `resolved` 93.141, `proposed` 47, NULL 33 (todos WU); `winning_outcome` NULL 39; resueltos con `winning_outcome` NULL: 0.

---

## 3. Política fail-closed (literal)

1. **p_weather.** Un mercado recibe `p_weather` **si y sólo si** existe un `SettlementOperator` con `applies_to(...) == True`, `quantization != 'NONE'`, `evidence.category ∈ {DEMONSTRATED, STRONGLY_SUPPORTED}` **end-to-end** (band_key vs winning_outcome en la misma (fuente, regla, unidad)) **y** ningún valor de `evidence.components` pertenece al **conjunto bloqueante literal**:

   ```
   BLOQUEAN = {NO_SEPARABLE_EN_MUESTRA, INFERIDO, INFERIDO_POR_TRANSFERENCIA, UNKNOWN, REFUTADO}
   NO_BLOQUEAN = {DEMONSTRATED, STRONGLY_SUPPORTED, SUBSUMIDO_EN_FUENTE}
   ```

   No hay excepción nominada ni desbloqueo por ratificación de una DP: **ratificar DP-W1 no cambia la categoría del componente ni abre p_weather**. La única vía para que `window` de la fila 8 deje de bloquear es que su categoría pase a `STRONGLY_SUPPORTED` por evidencia nueva (≥ 1 caso discriminante local/UTC en estación EE. UU./°F, §6.3), lo que exige artefacto + `spec_version` nueva (§3.6).
   **Aplicación de la regla, fila por fila (derivable de la tabla §2.2):** filas 1-4, 6, 9, 11 fallan por `category = UNKNOWN`; filas 5 y 7 fallan por `components['quantization'] = UNKNOWN`; fila 8 falla por `components['window'] = NO_SEPARABLE_EN_MUESTRA`; **fila 10 pasa** (`category = STRONGLY_SUPPORTED`; components = {`SUBSUMIDO_EN_FUENTE`, `SUBSUMIDO_EN_FUENTE`, `STRONGLY_SUPPORTED`, `DEMONSTRATED`}, ninguno bloqueante). **Universo p_weather = fila 10 = 1.859 mercados.**

2. **label vía observaciones.** Un mercado recibe `settle()` **si y sólo si** existe un operador con `applies_to(...) == True`, `compat_status_for(ctx) ∈ {DIRECT, PROXY_AUDITED}` (lo que incorpora la condición 6 de §4.2 sobre cláusula) y `evidence.validation_state ∈ {SELECCION_IN_SAMPLE, VALIDADO, NO_DECIDIBLE}` (§3.7). Un mercado que no cumpla 1 ni 2 **no recibe p_weather ni settle** y no entra en features, predictions, backtest ni entrenamiento de M2/M3.

3. **Label de entrenamiento y de pago = `winning_outcome` vía `labeling.build_label`** (gate `prediction_time < resolution_timestamp` intacto; `None` si no resuelto). `settle().band_key/settled_value` es covariable de auditoría (§6) y target de M2 (error = obs − forecast, bajo el `asof` de §1.4 y el preregistro R16, **DP-D17y**), **nunca** sustituto del label de pago. Difieren exactamente en las excepciones y en los casos con cláusula/fallback, y esa diferencia es lo que §6 mide. Test `test_training_label_is_winning_outcome_not_band_key`. El universo de features y el de labels coincide: los mercados sin operador no reciben ni feature ni label de entrenamiento.

4. **Registro de exclusiones** en `markets_excluded` **sin cambio de schema** (2D §V): `reason` = valor del enum cerrado; `stage='feature'`; `details` JSON = `{event_id, contract_source, measurement_rule_P, unit, rounding_rule, operator_id|null, spec_version, asof, clause_lowest_bracket}`.
   **Enum cerrado de `reason`:** `no_settlement_operator:Y_undefined_by_contract`, `no_settlement_operator:by_forecast`, `proxy_not_audited_F`, `quantization_unknown_C`, `window_not_discriminated_US_F`, `series_filter_unverified`, `clause_stratum_not_audited`, `source_inaccessible`, `rule_map_missing`, `station_tz_unknown`, **`target_date_unresolvable`** (nuevo v3), `unit_unknown`, `unit_mismatch`, `series_mismatch`, `no_observations_in_window`, `observations_not_available_asof`, `no_data_clause_possible`, `operator_none`.
   **Mecanismo:** `build_feature` lanza `SettlementOperatorUnavailable(reason)` (no subclase de `ValueError`) y `strategy_a` añade `except SettlementOperatorUnavailable as e: reason = e.reason` **antes** del `except ValueError` existente; esto toca 2D §L y forma parte de **DP-2D** y **DP-L1**. Los reasons de filas sin operador (1-4, 6, 9, 11) son alcanzables porque `build_feature` consulta `market_rule_map.fail_closed_reason` **antes** de resolver operador (§5 paso 0).

5. **Prohibiciones explícitas:** ningún operador por defecto (`operator=None` → `operator_none`, nunca nearest); ninguna conversión C↔F sobre observaciones; ningún filtro post-hoc (p. ej. `arch-`) para elevar la evidencia ni filtro de aplicabilidad por identidad de mercado (§1.4); ninguna lectura de `markets.winning_outcome/resolution_timestamp` por `build_feature` (`FORBIDDEN_FEATURE_FIELDS` sigue vigente); `band_probability` nunca lanza `NotImplementedError` (§1.4).

6. **Cambiar el estado de una fila de §2** requiere: (a) preregistro §6, (b) artefacto con sha, (c) nueva `spec_version`; nunca una edición silenciosa. Nada se rebaja por edición; sólo se eleva cumpliendo §6.5.

7. **Puerta de validación (nueva en v3, DP-VS1).** Los estados HABILITADO de §2 son **provisionales**. Se emite `settle`/`p_weather` con `validation_state ∈ {SELECCION_IN_SAMPLE, VALIDADO, NO_DECIDIBLE}`, pero:
   - toda fila con `validation_state != 'VALIDADO'` marca **`provisional = True`** en `feature_json` y queda **fuera de la selección final de estrategia** hasta alcanzar VALIDADO;
   - **la fila 10 (única con p_weather) es hoy `SELECCION_IN_SAMPLE`**: floor se eligió entre {floor, ceil, half-up, half-even} sobre los mismos 166 eventos que lo miden. Que alimente p_weather → p_model → fair_value → señales está permitido **sólo** con `provisional = True` y excluido de la selección final; su promoción depende del holdout §6.2;
   - `NO_DECIDIBLE` (filas 5 y 7, eje cuantización) significa **settle permanente, p_weather permanentemente cerrado y no promocionable**: con series ya enteras (`metar_body_c`) INTERVAL_FLOOR y NEAREST son indistinguibles en `settle` (n_disc = 0) y el Q-test es NOT_TESTABLE con IEM (§6.4). Sus otros ejes (ventana, agregación) sí pueden validarse en holdout y se reportan por separado en `validation_axes`, pero el eje NO_DECIDIBLE domina el estado de la fila.

---

## 4. Proxy IEM/METAR para WU/NOAA (D17) y fuente directa HKO

**4.1 Base.** D17 (ADOPTADO): labels WU/HKO/CWA vía proxy IEM/METAR «sólo bajo una auditoría de compatibilidad declarada»; cada label lleva `label_source`, `contract_source`, `compat_status`; sin operador auditado → fail-closed.
**Extensión de D17 (decisión propia, DP-D17x):** Hong Kong no tiene METAR (`STATION_COORDS_SNAPSHOT_v1.3` excluded_no_icao «settlement HKO, no METAR»; `v3.icao2` NULL en 1.859). La regla de etiquetado por fuente contractual de D17 se extiende a la **fuente contractual directa** `HKO_CLMMAXT` como `label_source` admitido con `compat_status='DIRECT'` (VHHH aparece en `STATION_TZ_v1` con `Asia/Hong_Kong` sólo por 18 mercados WU by-Forecast; el operador HKO no la usa). Nada de esto afirma que IEM sea la fuente de settlement de ningún mercado.
**Restricción de D17-A (decisión propia, DP-D17y):** D17-A admite `Y_final` retrospectivo para entrenamiento M2 y backtest sin condición. Este documento lo estrecha: `Y_final` es admisible como label de **evaluación/auditoría sin condiciones**, y como **target de M2 sólo bajo preregistro R16**; hasta que R16 exista, **M2 no consume `settle`**. Se registra como decisión propia, no como cita de D17, porque combinada con §7.8 (`available_at` es `None` en todo el histórico IEM procesado → `settle(asof=T)` es siempre `observations_not_available_asof`) deja D17-A inoperante al 100 % en la ruta M2 hasta R16.

**4.2 Condiciones para `compat_status_for(ctx) = PROXY_AUDITED`** (todas necesarias, por estrato `(fuente, regla, unidad, con/sin cláusula)`):

1. Existe **al menos una auditoría de compatibilidad preregistrada** (E2: `PREREG_E2.md` sha `c7f031ec…` → `E2_RESULTS.json` sha `ec500428…`, 38 eventos) con Y del proxy comparada contra `winning_outcome`. Si se usa además la muestra de discriminación (`B_CANDIDATES.json` 618 → `E2_DISCRIMINATION_EVIDENCE.json` sha `9d925bf3…`, 57), se declara **no preregistrada** y se reporta en columna separada de la `EvidenceRef` (sin solapamiento de event_id con E2: **0 eventos comunes**, OBSERVADO).
2. Ventana y agregación del proxy coinciden con las declaradas en §2 (día civil local de la estación; max; serie declarada).
3. La serie es la adecuada a la unidad: `metar_body_c` en °C; `metar_tgroup_tmpf` en °F (`round(F(cuerpo))` REFUTADO, 5/14 incompatibles).
4. La estación tiene ICAO (`v3.icao2`, **55 distintos**; NULL en HKO 1.859 y CWA 77) y **tz resuelta en `STATION_TZ_v1.json`** (55/55, OBSERVADO; sha `35d68e65…`). La condición se verifica **por estación en tiempo de ejecución** con fail-closed `station_tz_unknown`; el número de mercados con `icao2` no nulo (**91.285**) es aritmética del catálogo, no una afirmación de cobertura DEMONSTRATED.
5. Las excepciones abiertas están listadas (Taipei 322448 NEITHER) y no se eliminan del universo.
6. **Cláusula lowest-bracket:** para mercados con `clause_lowest_bracket = True`, `PROXY_AUDITED` sólo si el estrato (regla, unidad, **con cláusula**) tiene casos auditados reportados aparte; hoy **0** en filas 5, 7 y 8 → `compat_status_for(ctx) = 'PROXY_NOT_AUDITED'` y `settle` falla cerrado con `clause_stratum_not_audited` (§1.4, punto 6). Para HKO (rama DIRECT) el label **sí** se emite, con `clause_lowest_bracket = True`, y se reporta como estrato aparte en §6 (la fuente es la contractual; si el dato estuvo disponible antes del plazo es UNKNOWN).
7. **Cobertura de `target_date_contractual`** (nuevo v3): el mercado tiene `target_date` no nulo en el rule-map; si no, `target_date_unresolvable` (§5 paso 0).

**4.3 Verificación preregistrada de la fila 9 (NOAA HourlyData °F)** — precondición para pasar de FAIL_CLOSED a HABILITADO_CON_PROXY.
Estado actual de la evidencia (recómputo propio sobre `NOAA_DIRECT.json`, sha `bdcb7127…`, OBSERVADO 2026-09-07): de las 4 filas P_NOAA_HourlyData con datos del API, **3 discriminan** contra la hipótesis «Y = máximo sobre todas las observaciones de api.weather.gov» (Houston, NYC, Miami; Dallas no), y **0 separan** las dos hipótesis vivas, porque ninguna fila del artefacto lleva la marca rutinaria/especial:

- **H_hourly:** Y = max sobre observaciones **rutinarias horarias** de api.weather.gov (no todas las obs).
- **H_series:** Y = `round(F(grupo T))` (= `tmpf` de IEM) sobre **todas** las observaciones; la discrepancia de Houston (87,8 vs 87,0) nace de cuerpo entero (31 → 87,8) frente a grupo T (30,6 → 87,08).

**Datos necesarios en disco:** observaciones crudas de api.weather.gov por estación-día (`nq.json` sólo contiene KLGA 2026-09-03) **o** las obs IEM con marca de rutinaria/especial.
**Métrica:** para cada evento resuelto de la fila 9 con datos, `band_key` bajo H_hourly y bajo H_series vs `winning_outcome`; `n_disc` según §6.3; criterio §6.5.
Hasta entonces, `market_rule_map.fail_closed_reason = 'series_filter_unverified'` para los 1.441 mercados, en `settle` y en `band_probability`. Qué subconjunto usó el recómputo 8/8 de E2 (`H_LOCAL_n = 25` en IEM vs `n_local = 251` en el API para Houston) es UNKNOWN.

**4.4 Qué se reporta por label.** Vía proxy: `label_source='IEM_METAR'`, `contract_source`, `measurement_rule_P`, `compat_status`, `series`, `station_icao`, `station_tz`, `window_start_utc/end_utc`, `n_obs`, `settled_value`, `band_key`, `availability`, `asof`, `max_available_at`, `max_record_version`, `clause_lowest_bracket`, `fallback_R1`, `provisional`, `validation_state`, `operator_id/version`, `spec_version`, `audit_ref` (ruta + sha), `revision_status='UNKNOWN_FOR_CONTRACT_SOURCE'` (impacto de revisiones medido sólo en IEM: 0/578 station-days, cota sup. 95 % < 0,519 %; no extrapolable).
Directo HKO: `label_source='HKO_CLMMAXT'`, `compat_status='DIRECT'`, `window_kind='SOURCE_DAILY_ROW'`, `n_obs=1`, `revision_status='UNKNOWN_PUBLISHED_VS_FINALIZED'` (CLMMAXT «devuelve solo el estado actual»; el contrato distingue «published» 1.078 mercados de «finalized» 781, sin timestamps), `completeness` de la fila (`'C'` en 166/166 filas del test).

**4.5 Qué NO afirma el proxy.** Que IEM sea la fuente de settlement; que WU muestre el cuerpo METAR o el grupo T; la tasa de revisión de WU; nada sobre °F en WU DailyObs (0 casos); nada sobre qué observaciones usa NOAA HourlyData (§4.3); nada sobre estaciones fuera de las auditadas.

---

## 5. Migración del código

Referencias: `PHASE_2E_SETTLEMENT_OPERATOR_DESIGN.md` «Migration sequence»; código actual `features.py`, `probability.py`, `strategy_a.py`, `database.py` (`markets_excluded(market_id, reason, excluded_at, stage, details, …)`; `AS_OF_COLUMNS`). Orden obligatorio; cada paso cierra con tests en verde antes del siguiente. **Todo el bloque toca ficheros protegidos por 2D §V → requiere DP-2D ratificado antes de ejecutar el paso 2.**

### Paso 0 — Rule-map: fuente única del `MarketContext`

**0.a — `markets.measurement_rule` NO es clave de aplicabilidad ni de segmentación.**
`resolution.parse_measurement_rule` en `origin/main@dfdc73e` sólo distingue por regex «Daily Observations» / «by the Forecast» / «Day High & Low» / NULL; `station_identifier` sólo se extrae de URLs wunderground (NULL para NOAA 11.528, HKO 1.859, CWA 77 en `cls2`; OBSERVADO). **Defecto OBSERVADO** (recómputo propio 2026-09-07, cruce `cls2 × v3`): la regex «Daily Observations» clasifica la frase de **fallback** NOAA como regla WU en **exactamente 3.333 mercados** (2.497 `P_NOAA_TempColumn` + 836 `P_NOAA_HourlyData` con `cls2.measurement_rule = "highest temperature in the 'Daily Observations' table (not Day High & Low)"`). Cualquier ruta que use esa columna (2D §M, un `applies_to` provisional, una migración parcial) admitiría 3.333 mercados NOAA en el operador de la fila 5. Test `test_rule_map_disagrees_with_regex_column_on_noaa_fallback` (= 3.333 sobre el catálogo congelado).
**Estado de R29 (corregido en v3):** R29 **no** figura en `ROADMAP.md` (sha `2448e554…`, verificado), pero **sí está registrado y ADOPTADO como decisión: `D21 (sesión A)` — «R29: la clasificación de la fuente de settlement se corrige en el código»**, con `contract_source`, `fallback_source`, `measurement_rule_code` (P_*, byte-idéntico a `v3.primary_rule`), `primary_clause` y `contract_source_confidence` en el parser, validador read-only sobre las 93.221 descripciones (0 desacuerdos inexplicados, 3.333 correcciones, 77 residuales CWA) y **PR #2 abierto sobre `main@dfdc73e`**. Consecuencias: (i) la afirmación «las etiquetas `primary_source/primary_rule` (P_*) no existen en el repo» **sólo vale para `origin/main@dfdc73e`**, no para la rama del PR #2; (ii) §7 ya no lista «registro de R29» como incógnita; (iii) el punto (iii) de DP-2D (segmentación por `measurement_rule_P` en vez de `markets.measurement_rule`) **ya está decidido** y sale de la lista de pendientes (§8).

**0.b — `target_date_contractual`: hueco declarado y fail-closed.**
La derivación que v2 escribía («`v3` + `STATION_TZ_v1.json` + `v3.descr ~ 'lowest bracket'` + `rule_recuperable = 'R1_*'`») **no produce `target_date_contractual`**: OBSERVADO (`describe v3`, read_only), las columnas de `v3` son `market_id, event_id, city, unit, rounding_rule, source_recuperable, rule_recuperable, icao2, descr, m_R7_HKO, m_R3_BYF, m_R1_DOBS, m_R5_HOURLY, m_R6_TEMPCOL, m_R4_ALLT, primary_source, primary_rule, has_secondary_WU, menciona_1159_ET, event_endDate, winning_outcome, lo, hi` — **ninguna columna de target_date**. §0.3 prohíbe derivarlo de `endDate`; `PREREG_E2.md` (sha `c7f031ec…`) exige extraerlo «del TEXTO de la descripción ("on 29 Aug '26"), NO se asume = date(endDate)». **Cobertura OBSERVADA hoy: 204 eventos / 2.244 mercados** (166 de `HKO_OPERATOR_TEST.json` + 38 de `E2_RESULTS.json`, **0 solape**) sobre 8.557 eventos / 93.221 mercados = **2,4 % de los mercados**. No existe extractor ni artefacto versionado que lo produzca para el resto.
**Regla:** mientras no exista ese artefacto, `market_rule_map.target_date_contractual` es NULL fuera de esos 204 eventos y `settle` falla cerrado con **`target_date_unresolvable`** (§1.4, punto 4). Esto afecta a las tres filas con `window_kind='LOCAL_CIVIL_DAY'` (5, 7, 8 = 17.083 mercados), que son precisamente las que definen la ventana sobre ese campo; la fila 10 lo necesita igualmente para mapear `target_date → fila CLMMAXT`. Cuando el extractor exista, se nombra aquí con su sha y su cobertura k/n, igual que se hizo con `STATION_TZ_v1.json` para tz. Test **`test_rule_map_target_date_coverage`** (análogo a `test_rule_map_station_tz_complete`): la cobertura declarada coincide con la del artefacto y todo mercado sin `target_date` lleva `fail_closed_reason='target_date_unresolvable'`.

**0.c — Naturaleza de `market_rule_map` (decisión, DP-RM1).**
v2 la describía a la vez como tabla que `build_feature` consulta con SELECT y como «fichero de datos versionado sin migración de schema», con `database.py` intacto. Se resuelve por la **opción A**, amparada en el precedente que el propio `database.py` documenta (`discovery_checkpoint`, Fase 2C: «Operational table, NOT a numbered migration, NOT in ALL_TABLES; it does not bump SCHEMA_VERSION»; OBSERVADO):
> `market_rule_map` es una **tabla operacional**, fuera de `ALL_TABLES` y del contador de migraciones, creada por un script de datos versionado; `database.py` **no se modifica**; se declara expresamente que la prohibición de 2D §V («cualquier migración/cambio de schema en Strategy A») **no la alcanza**, por no ser schema de Strategy A ni bumpear `SCHEMA_VERSION`.

Esquema: `market_rule_map(market_id, event_id, contract_source, measurement_rule_P, unit, rounding_rule, station_icao, station_tz, target_date_contractual, clause_lowest_bracket, fallback_R1, fail_closed_reason, rule_map_sha)`, derivada de `v3` + `STATION_TZ_v1.json` (55/55) + `v3.descr ilike '%lowest bracket%'` + `rule_recuperable = 'R1_*'` + el futuro extractor de target_date. Opcional para segmentación (nunca para el operador): `region`/`component` de `STATION_REGION_COMPONENT_v1.json`.

**0.d — `fail_closed_reason`: hace alcanzables los reasons de las filas sin operador.**
`build_feature` consulta esta columna **antes** de resolver operador:
```python
if ctx.fail_closed_reason:
    raise SettlementOperatorUnavailable(ctx.fail_closed_reason)
```
Así `series_filter_unverified` (fila 9), `no_settlement_operator:Y_undefined_by_contract` (filas 1-2), `no_settlement_operator:by_forecast` (filas 3-4), `proxy_not_audited_F` (fila 6), `source_inaccessible` (fila 11) y `target_date_unresolvable` son producibles; sin esta columna el único camino era `applies_to == False → operator_none`, y esos reasons eran letra muerta. **La fila 9 deja de portar `compat_status`**: no hay operador que lo porte (§2.2).

**0.e — Lectura y tests.**
`build_feature` lee **SOLO** `market_rule_map` para el ctx, con lista `SELECT` explícita de columnas (nunca `markets.*`): test `test_build_feature_never_selects_markets_resolution_columns` (nombre ajustado a la opción A de DP-RM1: verifica que la consulta del ctx nombra `market_rule_map` y ninguna columna de `markets`). Ctx ausente → `rule_map_missing`. El valor `contract_source='TEST'` está **prohibido** en el rule-map de producción (test `test_rule_map_has_no_test_source`).
Tests: `test_rule_map_counts` (las 11 filas de §2 exactas), `test_rule_map_station_tz_complete` (55/55, sin NULL en WU/NOAA), `test_rule_map_clause_counts` (2.475 / 225), `test_rule_map_target_date_coverage`, `test_rule_map_fail_closed_reason_enum` (todo valor pertenece al enum §3.4), `test_rule_map_disagrees_with_regex_column_on_noaa_fallback` (3.333).

### Paso 1 — `ForecastCDF_v0` + protocolo `SettlementOperator`

Nuevo módulo `settlement/`. `ForecastCDF_v0 := clamp(cdf_legacy, 0, 1)` con soporte declarado `[values[0] − 1, values[-1] + 1]` y caso degenerado explícito (`floor(values[0]) == ceil(values[-1])` → masa 1 en ese punto, replicando `{minimum: 1.0}`). Único cambio respecto a la CDF de `probability.py`: el recorte (OBSERVADO: la cola inferior `0.10·(x − (values[0] − 1))` no está acotada y da `F < 0` para `x < p10 − 1`; la superior sí satura en 1). Registrado como **DP-CDF0**. `TestOnlyOperator` vive en `tests/support/` (no en `src/`), con `applies_to := contract_source == 'TEST'`.
Tests nuevos: `test_forecast_cdf_is_proper` (F→0, F→1, monótona, recorte), `test_operator_protocol_contracts` (§1.4), `test_band_probability_partition_sums_to_one_exact` (tol 1e-12), `test_interval_floor_mapping`, `test_nearest_mapping`, `test_open_bands_*`, `test_unit_mismatch_fails_closed`, `test_operator_none_fails_closed`, `test_applies_to_is_identity_blind`, `test_compat_status_depends_only_on_stratum_and_clause`, `test_settle_rejects_obs_available_after_asof`, `test_feature_json_has_no_evidence_fields`, `test_test_only_operator_not_importable_from_src`, **`test_band_probability_none_quantization_raises_unavailable_not_notimplemented`**, **`test_clause_stratum_fails_closed`**, **`test_target_date_unresolvable_fails_closed`**.

### Paso 2 — Retirar el nearest implícito

`quantiles_to_distribution` deja de ser llamada por producción; se conserva como `legacy_nearest_distribution` marcada `@deprecated` y prohibida en `features.py` (test `test_features_do_not_import_legacy_nearest`). `band_probability(distribution, lo, hi)` discreta se mantiene para compatibilidad de tests, fuera de la ruta de `build_feature`.

### Paso 3 — Operador obligatorio y ctx

`build_feature(..., operator: SettlementOperator)` y `generate_event_signals(..., operator: SettlementOperator)`: argumento posicional obligatorio sin default. `build_feature` construye el ctx desde `market_rule_map` (paso 0), aplica `fail_closed_reason`, llama `operator.applies_to(...)` y `operator.compat_status_for(ctx)`, y lanza `SettlementOperatorUnavailable(reason)` si procede. `feature_json` añade `operator_id`, `operator_version`, `cdf_version`, `unit_conversion`, `quantization`, `validation_state`, `provisional`, `spec_version` (**DP-L1**: linaje en `feature_json`, sin columna nueva; `markets_excluded.details` como en §3.4).

- **Tests que cambian** (llamadas sin operador rompen; cada fixture debe **sembrar una fila de `market_rule_map`** con `contract_source='TEST'`, `measurement_rule_P='P_TEST'`, `unit`, `rounding_rule`, `station_tz`, `target_date_contractual`, `fail_closed_reason=NULL`): `test_resolution_not_in_features.py` (llamadas en :82, :129, :191; aserciones `row is not None` en :93, :140, :202); `test_no_future_information.py` (llamadas :123, :171; aserción :134); `test_no_lookahead_adversarial.py` (llamadas :69, :113, :160; aserciones :124, :171); todas las de `test_strategy_a.py` → pasan `TestOnlyOperator`. Nota: `test_no_lookahead_adversarial.py:148-158` inserta en `markets` una fila con `winning_outcome/resolution_timestamp`; `build_feature` **no** debe leer `markets` (hoy no lo hace: «Resolution: intentionally NOT read»); la fixture del rule-map es una tabla distinta.
- **Aserciones numéricas que cambian** (recomputadas con `ForecastCDF_v0`, OBSERVADO): `test_resolution_not_in_features.py:204` 0,2777777778 (mapeo ±0,5 renormalizado por 0,9) → **0,25** para banda (30,30) con cuantiles 28..32, idéntico bajo INTERVAL_FLOOR (`F(31) − F(30)`) y NEAREST (`F(30,5) − F(29,5)`); `test_probability.py:262-277` 0,50 para [26,27] con cuantiles 24..28 → **0,40** bajo INTERVAL_FLOOR (`F(28) − F(26)`) o **0,45** bajo NEAREST (`F(27,5) − F(25,5)`), según el operador de test declarado; `test_probability.py:26-35, 171-244` (claves enteras / colapso `{26: 1.0}`) se reescriben contra `legacy_nearest_distribution` o se eliminan; `test_strategy_a.py:14, 36-37, 148-151` (PW con funciones legacy) pasan a calcular PW con el operador de test.
- **Tests que no cambian**: `test_probability.py:83-159, 247-259` (bandas sobre diccionarios manuales), `test_resolution.py` completo.
- **Tests nuevos**: `test_build_feature_requires_operator` (TypeError sin operador), `test_build_feature_records_operator_lineage`, `test_build_feature_raises_settlement_unavailable_not_valueerror`, `test_strategy_a_excludes_without_operator` (reason = enum, no `executable_or_invalid_price`), `test_markets_excluded_reasons_enum`, `test_operator_applicability_matrix` (las 11 filas de §2 con su estado por estrato con/sin cláusula, incluidas fila 9 FAIL_CLOSED y fila 8 p_weather FAIL_CLOSED), `test_training_label_is_winning_outcome_not_band_key`, `test_provisional_flag_in_feature_json`, `test_provisional_rows_excluded_from_final_selection`.

### Paso 4 — Operadores de producción

Uno por fila habilitada, cada uno con `EvidenceRef` (categoría end-to-end, prereg / no-prereg, `components`, `validation_axes`) y sha:

- `HKO_ABSMAX_INTERVAL_FLOOR v1` (fila 10; `settle` + `band_probability`);
- `NOAA_TEMPCOL_F_PROXY_IEM v1` (fila 8; `settle`; `band_probability` lanza `SettlementOperatorUnavailable('window_not_discriminated_US_F')` hasta que exista caso discriminante);
- `WU_DAILYOBS_C_PROXY_IEM v1` y `NOAA_TEMPCOL_C_PROXY_IEM v1` (filas 5 y 7; `quantization='NONE'`, sólo `settle`; `band_probability` lanza `SettlementOperatorUnavailable('quantization_unknown_C')`).

**No** se implementa `NOAA_HOURLY_F_PROXY_IEM` hasta cerrar §4.3.
Tests: reproducir HKO 164/166, `n_disc` 81 (81/81 vs 4/81), 73 (73/73 vs 4/73), 145 (143/145 vs 13/145) y las 2 excepciones desde `HKO_OPERATOR_TEST.json` (fixture copiada con sha); reproducir E2 por estrato (7/7, 16/16, 6/6) y las alternativas °F (14/14, 9/14, 10/14, 11/14).

### Paso 5 — Guardas de entrenamiento

M2/M3 y la selección final de estrategia rechazan filas sin `operator_id` (`test_training_rejects_rows_without_operator`); la selección final rechaza además filas con `provisional = True` (§3.7). **M2 no consume `settle` hasta que exista el preregistro R16** (DP-D17y); cuando exista, rechaza filas con `availability != 'ASOF_VERIFIED'` salvo bajo ese preregistro explícito. M3 y la selección final de estrategia mantienen la guarda de `provisional` con independencia de R16.

### 5.5 LOCKED / desbloqueo — **lista corregida contra 2D** (OBSERVADO en `PHASE_2D_STRATEGY_A_DESIGN.md`, worktree `wt-main@dfdc73e`)

v2 listaba como «LOCKED de 2D §F» dos ítems que 2D no bloquea y colocaba uno en la sección equivocada. Lista corregida:

- **LOCKED de 2D §F:** forecast as-of `available_at ≤ T`; `Σ_bandas p_weather = 1` sobre partición válida; interfaz `(lo, hi)` con `None` = abierta; `is_partition` como guarda de evento; falta de forecast ⇒ banda NONE.
- **LOCKED de 2D §E** (no §F): precio as-of `observation_time ≤ T` (INDICATIVE; EXECUTABLE rechazado en `build_feature`).
- **LOCKED de 2D §L (parte):** banda NONE si `build_feature` devuelve None; forecast `available_at > T` excluido.
- **LOCKED de 2D §V:** prohibición de tocar `features.py`/`probability.py`/`labeling.py`/`database.py` y sus tests, y de migrar schema en Strategy A.
- **DECIDED-V1 de 2D §W — reemplazable, NO LOCKED:** `p_model = p_weather` (§W.1; 2D §G es **OPEN** y dice literalmente «**NO asumir `p_model = p_weather`**»); `weather_sum_tolerance` es «DECIDED-V1 (mecanismo) / valores OPEN; parámetros obligatorios, SIN default; fail-closed si faltan» (tabla final de 2D), y `1e-6` aparece sólo como fixture en `tests/test_strategy_a.py:52` y `scripts/validate_2d.py:66`. **Este documento no fija el valor de `weather_sum_tolerance`** ni promueve `p_model = p_weather` a LOCKED.

**Se DESBLOQUEA únicamente y de forma enumerada (DP-2D):**
(i) 2D §F: la expresión `p_weather = band_probability(quantiles_to_distribution(p10..p90), lo, hi)` → `p_weather = operator.band_probability(ForecastCDF_v0(p10..p90), lo, hi)`; la cita de `test_full_partition_sums_to_one` como matemática autoritativa se sustituye por `test_band_probability_partition_sums_to_one_exact`;
(ii) 2D §L: nuevo `except SettlementOperatorUnavailable` en `strategy_a` y `reason` del enum §3.4 con `stage='feature'`;
(iii) **2D §M: YA DECIDIDO** por `D21 (sesión A)` (R29, ADOPTADO, PR #2): la segmentación pasa a `measurement_rule_code`/`market_rule_map.measurement_rule_P` en lugar de `markets.measurement_rule`. Sale de la lista de pendientes de ratificación; se cita como decisión existente;
(iv) 2D §V: autorización expresa para modificar `features.py`, `probability.py` y sus tests en los pasos 1-3; `labeling.py` y `database.py` **no se modifican** (label = `build_label`; `market_rule_map` es tabla operacional fuera de `ALL_TABLES`, DP-RM1).
No se desbloquea la forma de la CDF más allá del recorte (§0.1, DP-CDF0), ni `p_model`, ni tolerancias.

---

## 6. Preregistro de la validación del operador

**6.1 Objetivo.** Medir que `operator.settle(obs, ctx, asof=None).band_key` reproduce `winning_outcome` del catálogo (93.182 no nulos; 39 NULL excluidos por construcción) por estrato `(contract_source, measurement_rule_P, unit, con/sin cláusula)`.

**6.2 Muestra (congelada antes de ejecutar).**
- Universo: `umaResolutionStatus='resolved'` (93.141), `winning_outcome` no nulo, partición válida, `target_date_contractual` presente, observaciones obtenibles para la serie declarada. Sin exclusión post-hoc: los eventos `arch-` **se incluyen** y se reportan como sensibilidad (**149 eventos / 1.639 mercados**, OBSERVADO en `ev`; HKO: 486838, 490245, 493669).
- **HKO:** los 166 eventos de `HKO_OPERATOR_TEST.json` (target_date 2026-03-16…08-31) son **muestra de selección** (in-sample) — floor se eligió entre {floor, ceil, half-up, half-even} sobre ellos. **Holdout preregistrado:** eventos con target_date ≥ 2026-09-01 — hoy **934576, 939963, 945943** (resueltos, 11 mercados cada uno = 33; 945943 con cláusula lowest-bracket) y los que se acumulen — hasta que 6.5 sea decidible.
- **WU DailyObs C / NOAA TempColumn C-F:** E2 (38, preregistrada) y discriminación (57, no preregistrada) son muestra de selección; holdout = mercados resueltos de esas reglas **no** incluidos en `SAMPLE_E2.json` ni en `B_CANDIDATES.json`, muestreados por estrato con semilla fija declarada en el artefacto; el estrato «con cláusula» se muestrea aparte y es el que puede levantar §4.2 cond. 6.
- **NOAA HourlyData F:** sólo tras cerrar §4.3; el diseño de §4.3 es su preregistro.
- Excepciones conocidas (490245, 493669, 322448) permanecen en la muestra de selección y se reportan; no se reasignan.

**6.3 Métrica exacta.** Para cada estrato *s*: `tasa_s = #{m ∈ s : band_key(m) ∈ banda(winning_outcome(m))} / |s|`, con banda cerrada `[lo, hi]` y abiertas `(None, hi]` / `[lo, None)` en enteros (`parse_band`). Se reporta `k/n`, IC Wilson 95 % (z = 1,96), y la misma tasa para **cada operador alternativo de `settle`** sobre la **misma** muestra y la misma serie: para *tenths* {INTERVAL_FLOOR, ceil, half-up, half-even}; para whole-degree °F {tmpf NEAREST, `round(F(cuerpo))`, `floor(F(tg))`, `ceil(F(tg))`}; para ventana {LOCAL_CIVIL_DAY, UTC_DAY, LOCAL±1} sobre los casos donde difieren. **`n_disc` := casos con `band_key` distinto entre candidato y alternativa** (HKO floor vs half-up: 81); se reporta `k_disc` de cada uno (81 vs 4) y, como descriptivo, el subconjunto con **veredicto** de compatibilidad distinto (77; 77 vs 0). Un **caso discriminante de ventana** para la fila 8 es un evento EE. UU./°F donde `band_key(LOCAL) ≠ band_key(UTC)`; hoy `n_disc = 0` (14/14 filas °F con `H_LOCAL = H_UTC`).

**6.4 Q-test (cuantización °C, filas 5 y 7) — NOT_TESTABLE con los artefactos existentes.** Requeriría una serie en décimas para estaciones °C; OBSERVADO en `E2_RESULTS.json`: `H_LOCAL_tg = None` en **24/24** filas °C (P_NOAA_TempColumn A/B y P_WU_DailyObservations). Por tanto, con IEM **no existe vía de desbloqueo de p_weather** para las filas 5 y 7 (16.962 mercados), que quedan FAIL_CLOSED **sin sustituir por convención** (**DP-Q**), con `validation_state = NO_DECIDIBLE` en el eje de cuantización (§3.7). Cualquier fuente alternativa en décimas (no IEM) deberá preregistrarse aparte con nueva `spec_version`; hoy ninguna está identificada (§7).

**6.5 Criterio de aceptación (congelado, sin umbral arbitrario).** El operador candidato de un estrato se declara **VALIDADO** si, en el holdout:
1. el límite inferior del IC Wilson del candidato es **estrictamente mayor** que el límite superior del IC Wilson de cada operador alternativo de `settle` sobre la misma muestra (ICs disjuntos), **y**
2. sobre los `n_disc` casos, `k_disc(candidato) > k_disc(alternativa)` para toda alternativa, reportando el p exacto binomial de signo como descriptivo, **y**
3. toda excepción del candidato está listada por event_id con su valor fuente y banda ganadora, sin exclusión.

La alternativa obligatoria cuando no exista otra es un **operador de `settle`** sobre la misma serie (p. ej. `round_half_up(valor)`), nunca `legacy_nearest_distribution` (que es un mapeo CDF→bandas, no un operador de observaciones).
**Estados posibles del resultado:** VALIDADO (cumple 1-3); **NO_DECIDIDO** si los ICs solapan (no «rechazado»: se acumula holdout); **NO_DECIDIBLE** si el criterio no puede separar *por construcción* — caso de las filas 5 y 7 en el eje de cuantización, donde con series ya enteras (`metar_body_c`) INTERVAL_FLOOR y NEAREST coinciden siempre (`n_disc = 0`, ICs idénticos). NO_DECIDIBLE es permanente para ese eje: `settle` permanece habilitado, `p_weather` permanentemente cerrado, y la fila no es promocionable a VALIDADO ni entra en la selección final de estrategia (§3.7). Nunca se rebaja el estado de evidencia por edición. Al alcanzar VALIDADO, la fila cambia `validation_state` y `provisional` (nueva `spec_version`); ningún otro estado cambia.

**6.6 Artefacto.** `docs/research/SETTLEMENT_OPERATOR_AUDIT.md` (exigido por ROADMAP R12, hoy inexistente) + JSON con sha, semilla, lista de market_ids, tabla por estrato (prereg / no-prereg / con cláusula), ICs, `validation_axes` y excepciones. Debe **reproducir con cálculo y sha** toda cifra hoy citada sin artefacto versionado en `pmw-e2` («2.894/2.913»; «timeline 99»; «ronda 13»; «B-7 19/647»), o retirarla.

Aclaraciones que el artefacto debe conservar:
- **81 vs 77:** 81 es `n_disc` por `band_key` (definición de §6.3); 77 (`evidence/HKO_77_discriminating_floor_vs_round.csv`) es el subconjunto con **veredicto** de compatibilidad distinto (bandas cerradas). Ambas cifras son reproducibles; §6.3 fija 81 como la magnitud del criterio.
- **Autocorrección v3 sobre el margen de cierre HKO (OBSERVADO 2026-09-07, recómputo propio sobre `ev` + `HKO_OPERATOR_TEST.json`):** v2 afirmaba «`closedTime − window_end ≥ 10,795 h` en 168/168». La cifra correcta es **165/165** de los 166 eventos de la muestra que tienen `closedTime` (**493669 no tiene `closedTime`**), con mínimo **10,795 h** y máximo 135,859 h; los 3 eventos del holdout dan 17,033 h (934576), 14,575 h (939963) y 11,216 h (945943). El «168» de v2 mezclaba los 169 eventos HKO del catálogo con los 166 de la muestra. **Además**, calcular `window_end` desde `date(endDate)` en vez de desde `target_date_contractual` produce un margen **negativo (−10,21 h) en el evento 276889** (`highest-temperature-in-hong-kong-on-march-19-2026`, `endDate = 2026-03-20T12:00Z`): es un caso concreto de `endDate = target_date + 1` (ROADMAP R8, PARCIAL) y la justificación empírica de la prohibición de §0.3.
- **Desagregación de la ventana:** compat_local 56/57 vs LOCAL_ONLY 54/57 (§2.1), con la nota sobre la lectura de D17.

---

## 7. Incógnitas y límites

UNKNOWN (bloquean estado; no se resuelven por convención):

1. **`Y_source_value` desde la fuente contractual** en WU (DailyObs, genérico, byForecast) y NOAA (TempColumn, HourlyData): 55.803 mercados validados sólo contra proxy IEM; ningún caso donde el valor publicado por WU o wrh/timeseries se haya comparado con el bracket.
2. **Cuantización continuo→entero °C** del observador (filas 5, 7): no reportada y **NOT_TESTABLE con IEM** (grupo T ausente 24/24). **Fuente alternativa en décimas para estaciones °C: ninguna identificada.**
3. **WU DailyObs °F** (2.057 mercados): 0 casos auditados.
4. **NOAA TempColumn ≡ HourlyData** (11.528 mercados): UNKNOWN; **subconjunto de observaciones de HourlyData** (H_hourly vs H_series, §4.3): **0/4 filas con datos lo separan** (falta la marca rutinaria/especial), aunque **3/4 sí refutan** el máximo sobre todas las obs del API.
5. **Ventana en EE. UU./°F, NOAA HourlyData, HKO y CWA**: `NO_SEPARABLE_EN_MUESTRA` (`H_LOCAL = H_UTC` en 14/14 filas °F); la transferencia desde 7 ciudades Asia/Pacífico (°C, muestra no preregistrada) sería `INFERIDO_POR_TRANSFERENCIA` (DP-W1) y **bloquea igualmente**.
6. **`target_date_contractual`** para 8.353 de 8.557 eventos (90.977 de 93.221 mercados): sin extractor ni artefacto versionado → `target_date_unresolvable`, fail-closed (§5 paso 0.b). **Es hoy el hueco de mayor alcance del documento.**
7. **HKO**: escalar (`floor(Y)` vs `[N,N+1)`); 490245 sin explicación; 3 eventos de septiembre en holdout sin contrastar; «published» (1.078) vs «finalized» (781) sin timestamps; alcance 1 ciudad / 1 estación.
8. **CWA**: fuente, estación, timezone, precisión y operador UNKNOWN; prohibido extrapolar desde HKO.
9. **`record_version_asof(T)`** y política de revisiones de WU/HKO/CWA: UNKNOWN (sólo IEM 0/578). `available_at` es `None` para todo el histórico IEM procesado → `settle(asof=T)` sobre histórico es siempre `observations_not_available_asof`; sólo la captura prospectiva (D17-C) lo cambia. Consecuencia registrada en DP-D17y.
10. **Excepción Taipei 322448** (NOAA TempColumn, NEITHER) y eventos NOAA TempColumn resueltos antes del fin de ventana («B-7 19/647», citado sin artefacto): sin investigar.
11. **Provenance de las etiquetas P_*/R*/flags de `CATALOG_V2`** (verificadas sólo por regex): prerrequisito de §5 paso 0. Nota: `D21 (sesión A)` afirma que `measurement_rule_code` del parser corregido es byte-idéntico a `v3.primary_rule` sobre las 93.221 descripciones, lo que cierra parcialmente esta incógnita en la rama del PR #2, no en `origin/main@dfdc73e`.
12. **Unidad de `weather_forecasts`** (sin columna unit; ingestión R15 PENDIENTE): `ForecastCDF` debe recibir unidad explícita o fail-closed (`unit_mismatch`).
13. **Activación efectiva del fallback R1 (3.333) y de la cláusula lowest-bracket (2.475)** por mercado: UNKNOWN; ningún operador reproduce esas ramas.

*(La incógnita «R29 no registrado» de v2 queda RESUELTA: R29 está registrado y ADOPTADO en `D21 (sesión A)`, con PR #2 abierto; sigue sin figurar en `ROADMAP.md` sha `2448e554…`, lo que es un desfase documental del roadmap, no una incógnita del operador.)*

**Límites de alcance** (no son incógnitas del operador, pero acotan su uso):
- Forecast Tmax continua vs. máximo de observaciones muestreadas: el máximo real entre observaciones no es observable; límite de modelado, no de settlement.
- Las categorías de este documento son las de los informes fuente más los recómputos OBSERVADOS aquí declarados; cualquier reclasificación exige artefacto nuevo y `spec_version` nueva.
- `STATION_REGION_COMPONENT_v1` (24 estaciones `in_modelsel`, resto INFERIDA) acota la transferencia de M1, no el operador.
- **Cobertura de `edge_net`**: al restringir p_weather a 1.859 mercados, la cadena 2D §W → D19 H1 sólo puede producir `fair_value`/`edge_net` para ese 1,99 % del catálogo (§0.8); se reporta a R20.

---

## 8. Decisiones pendientes de ratificación explícita (no evidencia)

- **DP-U1** — conversión afín de la CDF continua a °F, sólo en `ForecastCDF` (§1.4).
- **DP-L1** — linaje en `feature_json` y en `markets_excluded.details`, sin columna nueva ni cambio de schema (§3.4, §5 paso 3).
- **DP-2D** — desbloqueo enumerado de 2D §F(i), §L(ii) y §V(iv) (§5.5). **El punto (iii) (segmentación por `measurement_rule_P`) ya NO es pendiente: está decidido por `D21 (sesión A)`, ADOPTADO, PR #2 sobre `main@dfdc73e`.**
- **DP-RM1** — `market_rule_map` como **tabla operacional** fuera de `ALL_TABLES`, sin bump de `SCHEMA_VERSION`, por el precedente `discovery_checkpoint`; se declara que 2D §V no la alcanza (§5 paso 0.c).
- **DP-Q** — cuantización °C FAIL_CLOSED en p_weather (NOT_TESTABLE) en lugar de convención; `validation_state = NO_DECIDIBLE` para las filas 5 y 7 (§6.4, §6.5).
- **DP-CDF0** — `ForecastCDF_v0 = clamp(cdf_legacy, 0, 1)` con soporte y caso degenerado declarados (§5 paso 1).
- **DP-W1 (alcance reducido en v3)** — declarar `LOCAL_CIVIL_DAY` como ventana del operador de `settle` de la fila 8 pese a que la muestra no separa local de UTC (end-to-end 6/6 compatible bajo ambas). **DP-W1 NO desbloquea p_weather**: el componente `window` queda `NO_SEPARABLE_EN_MUESTRA` hoy, y su transferencia sería `INFERIDO_POR_TRANSFERENCIA`, que bloquea por §3.1 con o sin ratificación. Ratificarla obliga a declarar el riesgo (Tmax del día local vs settlement en día UTC) en `EvidenceRef.risk_declared`. La única vía de desbloqueo de p_weather en la fila 8 es ≥ 1 caso discriminante EE. UU./°F.
- **DP-D17x** — extensión de D17 a la fuente contractual directa `HKO_CLMMAXT` con `compat_status='DIRECT'` (§4.1).
- **DP-D17y** — restricción de D17-A: `Y_final` admisible como label de evaluación/auditoría sin condiciones y como **target de M2 sólo bajo preregistro R16**; hasta R16, M2 no consume `settle` (§0.2, §3.3, §4.1, §5 paso 5).
- **DP-VS1** — puerta de validación: emisión con `validation_state ∈ {SELECCION_IN_SAMPLE, VALIDADO, NO_DECIDIBLE}`, flag `provisional=True` mientras no sea VALIDADO, y exclusión de las filas provisionales de la selección final de estrategia (§3.7).

---

## Changelog v3 (hallazgo de la ronda 2 → estado + motivo)

**H2.1 (IMPORTANTE) — §3.1 / EvidenceRef / columna «Evidencia» / DP-W1: trazabilidad incompleta de H1.0 y H0.2** → **APLICADO.** (1) Cada fila de §2.2 lleva ahora columna **«Cat. e2e»** con el valor explícito de `EvidenceRef.category` (UNKNOWN en filas 1-4, 6, 9, 11; STRONGLY_SUPPORTED en 5, 7, 8, 10), además de k/n e IC, de modo que «el universo p_weather es la fila 10» es derivable de la tabla. (2) Las categorías de componente están declaradas en la **Convención de evidencia** del preámbulo con su efecto binario. (3) §3.1 enumera literalmente el conjunto bloqueante y aplica la regla fila por fila. (4) La contradicción DP-W1 se resuelve en H2.5.

**H2.2 (IMPORTANTE) — `target_date_contractual` no derivable de `v3`** → **APLICADO.** Verificado por `describe v3` (read_only): no existe columna de target_date. §5 paso 0.b declara el hueco, la cobertura OBSERVADA (**204 eventos / 2.244 mercados** de 8.557 / 93.221; 166 HKO + 38 E2, 0 solape) y el fail-closed **`target_date_unresolvable`**, añadido al enum §3.4 y a la lista de fallos de §1.4; test `test_rule_map_target_date_coverage`. Añadido como incógnita §7.6 y como condición 7 de §4.2.

**H2.3 (IMPORTANTE) — los cuatro estados de §2.3 no suman 93.221** → **APLICADO.** §2.3 publica ahora **una sola partición cerrada** (17.072 + 1.870 + 1.441 + 72.838 = 93.221, 100,00 %), recomputada read-only; «18.942 (20,32 %)» se conserva sólo etiquetado como **cobertura teórica antes de la cond. 6, NO cobertura de label**; se declara **76.149 (81,69 %)** como el total sin label y se retira la lectura «74.279 = resto».

**H2.4 (IMPORTANTE) — ancla de DECISIONES caducada; D20-D22; doble D21; R29 ya resuelto** → **APLICADO.** `DECISIONS.sha256` regenerado y **verificado coincidente** (OBSERVADO 2026-09-07: `4ca2cf76a212…` en ambos); rango ampliado a **D0…D22 + A-23**; la colisión de los dos `D21` se cita siempre con sufijo de sesión, conforme a la regla de prefijos de `A-23`; §5 paso 0.a sustituye «R29 no localizado / UNKNOWN» por la cita de **`D21 (sesión A)`, ADOPTADO, PR #2 sobre `main@dfdc73e`**, aclarando que «P_* no existe en el repo» sólo vale para `origin/main@dfdc73e`; la incógnita §7.13 de v2 se retira; el punto (iii) de DP-2D pasa a «ya decidido».

**H2.5 (BLOQUEANTE) — §3.1 vs DP-W1 vs §2.3 (fila 8)** → **APLICADO, opción (a).** Se elige la vía estricta: **DP-W1 no desbloquea p_weather**. Se **borra** de §2.3 la línea «Si se ratifica DP-W1 (fila 8): 1.980 (2,12 %)»; §3.1 deja «≥ 1 caso discriminante EE. UU./°F» como única vía; DP-W1 se reduce a autorizar la declaración de ventana del operador de `settle` de la fila 8 y a exigir la declaración del riesgo en `risk_declared`. Motivo de preferir (a) sobre (b): la regla maestra del documento es fail-closed ante ausencia de evidencia, y `NO_SEPARABLE_EN_MUESTRA`/`INFERIDO_POR_TRANSFERENCIA` son ausencia de separación, no conocimiento; una excepción nominada por ratificación convertiría una decisión administrativa en evidencia.

**H2.6 (BLOQUEANTE) — §2.3 dejó de particionar el universo tras H1.6** → **APLICADO.** Misma corrección que H2.3: partición única de cuatro estados con sus cuatro porcentajes; los 1.870 aparecen exactamente una vez, con `reason = clause_stratum_not_audited`.

**H2.7 (BLOQUEANTE) — `compat_status` estático vs dependiente del mercado; `clause_stratum_not_audited` inalcanzable** → **APLICADO.** El atributo estático se sustituye por **`compat_status_for(ctx)`** en el protocolo (§1.3); §1.4 añade el fallo cerrado «`ctx.clause_lowest_bracket` y `compat_status_for(ctx) == PROXY_NOT_AUDITED` → `clause_stratum_not_audited`»; §2.2 **desdobla el estado en dos celdas** (sin cláusula / con cláusula) para las 11 filas, con la columna de recuento «(de ellos, con cláusula)»; test `test_clause_stratum_fails_closed` en §5 paso 1 y `test_compat_status_depends_only_on_stratum_and_clause`.

**H2.8 (IMPORTANTE) — 54/57 (LOCAL_ONLY) presentado como tasa de compatibilidad** → **APLICADO.** §2.1 separa las tres magnitudes con recómputo propio: **compat_local 56/57 (0,907–0,997)**, LOCAL_ONLY 54/57 (0,856–0,982), compat_utc 2/57 (0,010–0,119) → UTC REFUTADO; se anota que D17 cita 54/57 como «casos compatibles» y que este documento **desagrega sin elevar ni corregir D17**; se verifica la coherencia con las celdas de la tabla (41+7+8 = 56 sobre 57).

**H2.9 (IMPORTANTE) — fila 9: «1 caso decisivo» no reconstruible** → **APLICADO.** Recómputo sobre `NOAA_DIRECT.json`: **3/4 filas con datos discriminan** contra «máximo sobre todas las obs del API» (Houston 87,8 fuera de 86–87; NYC 73,94 fuera de 74–75; Miami 91,04 fuera de 90–91; Dallas 98,96 dentro, no discrimina) y **0/4 separan H_hourly de H_series**. La fila 9 y §4.3 se reescriben con esas cifras y con la definición de `n_disc` de §6.3; el FAIL_CLOSED no cambia pero deja de apoyarse en una cifra que el artefacto contradice.

**H2.10 (IMPORTANTE) — tres mecanismos incompatibles para `quantization = NONE`** → **APLICADO.** §1.4 unifica: `band_probability` **nunca** lanza `NotImplementedError`; con `NONE` lanza `SettlementOperatorUnavailable('quantization_unknown_C')`; `ValueError` queda reservado a `lo > hi`. Test `test_band_probability_none_quantization_raises_unavailable_not_notimplemented`. Motivo verificado: `strategy_a` sólo tiene `except ValueError` y deja propagar a propósito lo demás.

**H2.11 (IMPORTANTE) — reasons de filas sin operador no producibles** → **APLICADO.** §5 paso 0.d añade la columna **`fail_closed_reason`** a `market_rule_map`, consultada por `build_feature` antes de resolver operador (`raise SettlementOperatorUnavailable(ctx.fail_closed_reason or 'operator_none')`); `compat_status` **desaparece de la fila 9** (no hay operador que lo porte); test `test_rule_map_fail_closed_reason_enum`.

**H2.12 (IMPORTANTE) — §5.5 lista como LOCKED lo que 2D deja abierto** → **APLICADO.** Verificado en `PHASE_2D_STRATEGY_A_DESIGN.md` (worktree `dfdc73e`): §G es OPEN y dice «NO asumir `p_model = p_weather`»; §W.1 es DECIDED-V1 «explícitamente reemplazable»; `weather_sum_tolerance` es «DECIDED-V1 (mecanismo) / valores OPEN, sin default» y `1e-6` sólo aparece en `tests/test_strategy_a.py:52` y `scripts/validate_2d.py:66`; el precio as-of es §E, no §F. §5.5 se reescribe con las cuatro categorías (LOCKED §F, LOCKED §E, LOCKED §L parcial, DECIDED-V1 §W) y §0.10 declara que este documento no fija `weather_sum_tolerance` ni promueve `p_model = p_weather`.

**H2.13 (IMPORTANTE) — §0.8 «ninguna salida alimenta edge_net» es falso** → **APLICADO.** §0.8 reescrito con la redacción propuesta: no decide semántica de fees ni modelo de coste (D19 intacto), **sí** impacta la cobertura: sólo 1.859 mercados (1,99 %) podrán tener `fair_value`/`edge_net` bajo H1 de D19; efecto declarado y reportado a **R20**; añadido también a «Límites de alcance» (§7).

**H2.14 (IMPORTANTE) — `market_rule_map`: ¿tabla o fichero?** → **APLICADO, opción A.** **DP-RM1** (§5 paso 0.c): tabla **operacional** fuera de `ALL_TABLES`, sin bump de `SCHEMA_VERSION`, creada por script de datos versionado, `database.py` sin tocar, amparada en el precedente documentado en el propio `database.py` (`discovery_checkpoint`, Fase 2C, verificado); se declara expresamente que 2D §V no la alcanza. Nombre del test ajustado a esa opción.

**H2.15 (IMPORTANTE) — estrechamiento de D17-A presentado como cita** → **APLICADO.** Registrado como decisión propia **DP-D17y** (§4.1, §8), citada desde §0.2, §3.3 y §5 paso 5, con la consecuencia explícita (combinada con §7.9, D17-A queda inoperante en la ruta M2 hasta R16). Se conserva la restricción en lugar de la alternativa «limitar §5 paso 5 a M3», porque la guarda as-of es la única defensa frente a `available_at = None` en el 100 % del histórico.

**H2.16 (IMPORTANTE) — `validation_state` ausente de las puertas; `NO DECIDIBLE` fuera del enum** → **APLICADO.** Nuevo §3.7 (**DP-VS1**): las puertas de §3.1 y §3.2 incorporan `validation_state`; toda fila no VALIDADA marca **`provisional=True`** en `feature_json` y queda fuera de la selección final de estrategia; se añade **`NO_DECIDIBLE`** como cuarto valor del enum, asignado a las filas 5 y 7 (settle permanente, p_weather permanentemente cerrado, no promocionable), con `validation_axes` para no ocultar que sus ejes de ventana y agregación sí son validables. Se declara explícitamente que la fila 10 —única con p_weather— es hoy in-sample y sólo puede alimentar señales como provisional.

**H2.17 (IMPORTANTE) — vocabulario de `components` fuera de la Convención; «series DIRECT»** → **APLICADO.** El preámbulo incorpora la **tabla cerrada de categorías** con su efecto binario sobre §3.1; la fila 10 corrige `series DIRECT` → **`series: DEMONSTRATED`** (fuente contractual directa, `completeness='C'` en 166/166), quedando `DIRECT` sólo como `compat_status`; los identificadores se escriben con guion bajo en `EvidenceRef` y la Convención lo declara.

**Autocorrecciones propias de esta ronda (no provenían de ningún hallazgo):**
- **§6.6 — margen de cierre HKO.** v2 afirmaba «`closedTime − window_end ≥ 10,795 h` en 168/168». Recómputo propio: **165/165** de los 166 eventos de la muestra con `closedTime` (493669 no lo tiene), mínimo 10,795 h; holdout 17,033 / 14,575 / 11,216 h. Además, calcular `window_end` desde `date(endDate)` da **−10,21 h** en el evento 276889 (`endDate = target_date + 1`), lo que se incorpora como justificación empírica de §0.3.
- **§2.1 — IC de `round(F(cuerpo))`.** 9/14 → IC (0,388–**0,837**), no (0,388–0,836).

**Ningún hallazgo de la ronda 2 se rechaza.** Los dos únicos puntos donde se elige entre alternativas ofrecidas por el refutador son **H2.5 (opción a)** y **H2.14 (opción A)**, ambos con motivo escrito arriba.