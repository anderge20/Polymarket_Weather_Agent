# SETTLEMENT_OPERATOR_CORE.md

**Propósito único:** decir a quien implemente labels (R14) y features (R17) **qué operador de settlement aplicar a cada mercado y cuándo fallar cerrado**. Nada más. Núcleo extraído por **A-24** de `SETTLEMENT_OPERATORS_SPEC.v3.md` (sha `f6fcd2e4…`); no eleva ninguna categoría de evidencia respecto a v3.
**Anclas:** `DECISIONS.md` sha `b002e920…` (= `DECISIONS.sha256`; v3 citaba `4ca2cf76…`); rango **D0…D22, A-23, A-24**, con `D21 (sesión A)`/`D21 (sesión B)` desambiguados.
**Cifras:** recómputo propio 2026-09-07: `CATALOG_V2.duckdb` (`read_only=True`; `v3`, `ev`), `HKO_OPERATOR_TEST.json` `093e5891…`, `SAMPLE_E2.json` `28af1b79…`, `STATION_TZ_v1.json` `35d68e65…`.

---

## 1. Objeto y alcance

Decide, para cada uno de los **93.221 mercados / 8.557 eventos**: a qué estrato pertenece, qué `SettlementOperator` (ventana; agregación; cuantización; serie) aplica y con qué `reason` falla cerrado.
**NO decide:** la CDF de forecast ni `band_probability`/p_weather (v3 §1.4, §3.1); el desbloqueo de 2D §F/§L/§V; los fees (D19, intacto); el **preregistro de validación (pospuesto, A-24)**; la migración del código (v3 §5). **Ni sustituye el label de pago:** sigue siendo `winning_outcome` vía `labeling.build_label` (D17); `settle()` es covariable de auditoría y, bajo R16, target de M2.

## 2. Interfaz (sin implementar)

```python
from typing import Protocol, Sequence, Literal, NamedTuple
from datetime import datetime, date

Unit = Literal["C", "F"]
Series = Literal["hko_clmmaxt", "metar_body_c", "metar_tgroup_tmpf"]

class Observation(NamedTuple):
    ts_utc: datetime; value: float; unit: Unit; series: Series
    available_at: datetime | None  # D17-C; None = desconocido (todo el histórico IEM)
    record_version: int  # D17-C; las revisiones COR/AMD no sobrescriben

class MarketContext(NamedTuple):
    market_id: str; event_id: str  # SOLO linaje; applies_to NO los lee
    contract_source: str  # 'WU'|'NOAA'|'HKO'|'SIN_CLAUSULA' (v3.primary_source)
    measurement_rule_code: str  # v3.primary_rule (= parser de D21 sesión A)
    unit: Unit; rounding_rule: str  # 'whole degree'|'tenths'
    station_icao: str | None; station_tz: str | None  # tz IANA, STATION_TZ_v1.json
    target_date: date | None  # contractual, del TEXTO; NUNCA derivado de endDate
    clause_lowest_bracket: bool
    fail_closed_reason: str | None  # enum §4, fijado por estrato

class SettlementResult(NamedTuple):
    band_key: int | None  # N ≡ [N,N+1) con INTERVAL_FLOOR; N ≡ Y entero con NEAREST
    settled_value: float | None  # Y_source_value tal como lo publica la fuente
    window_start_utc: datetime | None; window_end_utc: datetime | None; n_obs: int; unit: Unit
    window_kind: Literal["LOCAL_CIVIL_DAY", "SOURCE_DAILY_ROW"]
    aggregation: Literal["MAX", "SOURCE_DAILY"]
    quantization: Literal["INTERVAL_FLOOR", "NEAREST", "NONE"]
    availability: Literal["ASOF_VERIFIED", "Y_FINAL_UNKNOWN_ASOF"]; asof: datetime | None
    max_available_at: datetime | None; max_record_version: int
    label_source: Literal["HKO_CLMMAXT", "IEM_METAR"]
    compat_status: Literal["DIRECT", "PROXY_AUDITED"]
    clause_lowest_bracket: bool; evidence_category: str  # el operador NO ejecuta la cláusula
    operator_id: str; operator_version: str; spec_version: str

class SettlementOperatorUnavailable(Exception):
    """NO hereda de ValueError (strategy_a captura ValueError como otra cosa)."""
    reason: str  # enum cerrado §4

class SettlementOperator(Protocol):
    operator_id: str; version: str  # otro comportamiento => otra version
    unit: Unit  # NO convierte observaciones
    window_kind: str; aggregation: str; quantization: str; required_series: Series  # §3

    def applies_to(self, contract_source: str, measurement_rule_code: str,
                   unit: str, rounding_rule: str) -> bool:
        """PURA en esos cuatro campos. NUNCA lee market_id, event_id ni target_date."""

    def settle(self, obs: Sequence[Observation], ctx: MarketContext,
               asof: datetime | None) -> SettlementResult:
        """Lanza SettlementOperatorUnavailable(reason) si no puede liquidar (§4)."""
```

**Contrato de pureza (test):** misma tupla con `market_id` distinto ⇒ mismo `applies_to`, incluidas las excepciones conocidas (322448, 490245, 493669), que **permanecen en el universo**: excluirlas por identidad sería selección condicionada al resultado.

## 3. Tabla de habilitación

Partición real de los **93.221** mercados por `(contract_source, measurement_rule_code, unit)`: 11 clases excluyentes y exhaustivas (`GROUP BY` sobre `v3.primary_source, primary_rule, unit`, sin nulos; `rounding_rule` queda determinado por la terna: *tenths* en 10 y 11, *whole degree* en el resto). **La cláusula lowest-bracket NO es elemento de la partición**: es transversal y vive en §4 como `reason`. Los eventos tampoco cruzan estratos (1.722 + 6.835 = 8.557).

| # | contract_source / measurement_rule_code / unit | Operador (ventana; agregación; cuantización; serie) | Cat. e2e | Merc. | Ev. | Estado |
|---|---|---|---|---|---|---|
| 1 | WU / P_WU_GENERIC_sin_calificador / C | — (Y indefinida por contrato) | UNKNOWN | 26.763 | 2.433 | FAIL_CLOSED |
| 2 | WU / P_WU_GENERIC_sin_calificador / F | — | UNKNOWN | 8.459 | 769 | FAIL_CLOSED |
| 3 | WU / P_byForecast / C | — (liquida un pronóstico) | UNKNOWN | 25.982 | 2.412 | FAIL_CLOSED |
| 4 | WU / P_byForecast / F | — | UNKNOWN | 9.500 | 896 | FAIL_CLOSED |
| 5 | WU / P_WU_DailyObservations / C | `WU_DAILYOBS_C_PROXY_IEM v1`: LOCAL_CIVIL_DAY; MAX; NONE; `metar_body_c` | STRONGLY_SUPPORTED* | 6.996 | 636 | HABILITADO_CON_PROXY |
| 6 | WU / P_WU_DailyObservations / F | — (0 casos auditados) | UNKNOWN | 2.057 | 187 | FAIL_CLOSED |
| 7 | NOAA / P_NOAA_TempColumn / C | `NOAA_TEMPCOL_C_PROXY_IEM v1`: LOCAL_CIVIL_DAY; MAX; NONE; `metar_body_c` | STRONGLY_SUPPORTED* | 9.966 | 906 | HABILITADO_CON_PROXY |
| 8 | NOAA / P_NOAA_TempColumn / F | `NOAA_TEMPCOL_F_PROXY_IEM v1`: LOCAL_CIVIL_DAY; MAX; NEAREST; `metar_tgroup_tmpf` | STRONGLY_SUPPORTED* | 121 | 11 | HABILITADO_CON_PROXY |
| 9 | NOAA / P_NOAA_HourlyData / F | — (subconjunto de obs UNKNOWN: 0/4 filas separan H_hourly de H_series) | UNKNOWN | 1.441 | 131 | FAIL_CLOSED |
| 10 | HKO / P_HKO_AbsDailyMax / C | `HKO_ABSMAX_INTERVAL_FLOOR v1`: SOURCE_DAILY_ROW; SOURCE_DAILY; INTERVAL_FLOOR; `hko_clmmaxt` | STRONGLY_SUPPORTED | 1.859 | 169 | HABILITADO |
| 11 | SIN_CLAUSULA (CWA Taipei) / P_UNKNOWN / C | — (fuente inaccesible; estación UNKNOWN) | UNKNOWN | 77 | 7 | FAIL_CLOSED |
| | **Σ (DuckDB `read_only`)** | | | **93.221** | **8.557** | |

\* categoría del **proxy** IEM/METAR, no de la fuente contractual (`'IEM_METAR'`/`'PROXY_AUDITED'`); el 10 es fuente directa (`'HKO_CLMMAXT'`/`'DIRECT'`).

## 4. Política fail-closed

**Regla única:** un mercado recibe `settle()` **si y sólo si** su estrato de §3 está HABILITADO o HABILITADO_CON_PROXY **y** no dispara condición de ejecución; si no, `settle` lanza `SettlementOperatorUnavailable(reason)`, se registra en `markets_excluded` (`stage='feature'`, sin cambio de schema) y el mercado **no entra en features, labels de M2, backtest ni entrenamiento**. No hay operador por defecto: el nearest-integer de `probability.quantiles_to_distribution` queda prohibido. Orden: (a) `fail_closed_reason` del estrato, (b) `target_date is None`, (c) cláusula en 5 y 7, (d) serie.

**Enum cerrado de `reason`** — sólo los alcanzables desde §3, con sus estratos:
`no_settlement_operator:Y_undefined_by_contract` (1, 2) · `no_settlement_operator:by_forecast` (3, 4) · `proxy_not_audited_F` (6) · `series_filter_unverified` (9) · `source_inaccessible` (11) · `clause_stratum_not_audited` (5, 7: 0 casos auditados con cláusula; el 8 no tiene mercados con cláusula y el 10 sí emite label, flagueado) · `target_date_unresolvable` (5, 7, 8, 10) · `unit_mismatch`, `series_mismatch`, `no_observations_in_window`, `observations_not_available_asof` (5, 7, 8, 10, por la serie).

**Eliminados de v3 por inalcanzables desde §3:** `station_tz_unknown` (51/51 ICAO de 5-8 con tz en `STATION_TZ_v1.json`, `missing=[]`; el 10 no usa tz), `unit_unknown` (ningún estrato con unidad UNKNOWN), `operator_none` y `rule_map_missing` (§3 es exhaustiva: todo estrato sin operador tiene `reason` propio; un `applies_to` falso sin `reason` sería un bug, no un estado de mercado), `no_data_clause_possible` (flag, no `reason`) y las dos puertas de p_weather (fuera de §1).

## 5. Cobertura resultante

| Corte | Mercados | % 93.221 | Eventos |
|---|---|---|---|
| Estratos con operador (5, 7, 8, 10) | 18.942 | 20,32 % | 1.722 (20,12 %) |
| — de ellos, bloqueados por cláusula (5, 7) | 1.870 | 2,01 % | 170 |
| **= elegibles a label (estrato + cláusula)** | **17.072** | **18,31 %** | — |
| Estratos FAIL_CLOSED (1-4, 6, 9, 11) | 74.279 | 79,68 % | 6.835 (79,88 %) |
| Cota superior emitible **hoy** (`target_date` resoluble) | 2.167 | 2,32 % | 197 |

La última fila mide el hueco del extractor (§6), no el universo.

**Periodo as-of (`target_date ≥ 2026-06-03`)**, acotado con `date(ev.endDate)` (a 12:00:00Z en 8.557/8.557 eventos; su fecha vale `target_date` o `target_date+1`): cohorte **51.051 mercados / 4.641 eventos**; con operador **15.796 (30,94 %) / 1.436**; fail-closed **35.255 (69,06 %)**. No contiene `P_byForecast` ni `SIN_CLAUSULA`; los estratos 5, 6, 8 y 9 entran enteros.

## 6. Holdout

**Elección (resuelve D-i): la puerta `target_date_unresolvable` es una condición de `settle`, NO un criterio de elegibilidad del universo ni de la tabla §3.**
Justificación: (a) lo exige la pureza de `applies_to` (§2): como puerta de universo, la elegibilidad sería función de un campo por mercado y, de hecho, de qué artefacto ya se ha construido; (b) `target_date_contractual` sólo es resoluble hoy para los 206 eventos / 2.266 mercados que **son** la muestra de selección, así que convertiría el universo operativo en esa muestra y dejaría el holdout vacío; (c) con la puerta en `settle`, los estratos dependen sólo del texto del contrato y el universo sigue siendo 93.221 con independencia del extractor.

**Regla de holdout, a priori e independiente de la puerta:** está en el holdout todo mercado de un estrato con operador cuyo **`target_date_contractual` ≥ 2026-09-01**, día siguiente al último `target_date` de la muestra de selección (`HKO_OPERATOR_TEST.json`, 2026-03-16…2026-08-31; OBSERVADO). El corte es temporal y **no** exige que `target_date` esté resuelto hoy: resolverlo ahí es trabajo del extractor (R14), no requisito de pertenencia. La muestra de selección (E2, discriminación, 166 HKO) queda entera antes del corte y no se reutiliza.
Tamaño, acotado con `date(ev.endDate)` (cotas `≥ 2026-09-02` y `≥ 2026-09-01`): **1.298–1.738 mercados / 118–158 eventos** con operador (cota superior: estrato 7 → 1.617/147, 5 → 88/8, 10 → 33/3). Solape con la muestra de selección: **11 mercados / 1 evento** (945943, HKO, con cláusula), reportado aparte y fuera del holdout. El **criterio de aceptación** para promover a VALIDADO queda **pospuesto (A-24)**: hasta entonces todo operador de §3 es provisional y ninguna fila se promueve por edición.

## 7. Lo que este documento NO congela

Sigue en el borrador vivo `SETTLEMENT_OPERATORS_SPEC.v3.md` (sha `f6fcd2e4…`), no normativo:

1. `band_probability`, `ForecastCDF` y la puerta de p_weather (v3 §1.4, §3.1), con su conjunto bloqueante de categorías de componente y sus dos reasons.
2. El **preregistro de validación** y su criterio de aceptación (v3 §6), pospuestos por A-24, y la verificación preregistrada del estrato 9 (v3 §4.3), única vía para sacarlo de `series_filter_unverified`.
3. La **migración del código** (v3 §5), el rule-map como tabla operacional, el desbloqueo de 2D y las **decisiones pendientes** DP-2D, DP-RM1, DP-L1, DP-U1, DP-Q, DP-CDF0, DP-W1, DP-D17x/y, DP-VS1 (v3 §8).
4. Las incógnitas UNKNOWN de v3 §7 — extractor de `target_date_contractual`, `record_version_asof(T)`, revisiones de WU/HKO/CWA, activación del fallback R1 (3.333) y de la cláusula (2.475 / 225) — y el impacto en `edge_net` (v3 §0.8, a R20, sin tocar D19).