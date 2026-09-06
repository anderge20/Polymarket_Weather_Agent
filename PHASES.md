# PHASES — índice de fases del repositorio (2A → 2H)

Fuente de estado: `scripts/HARNESS_CHANGELOG.md` ("Master status rule": IMPLEMENTED = escrito,
no ejecutado; TESTED = ejecutado y en verde con pytest / fixtures / stubs offline; VALIDATED =
comportamiento demostrado sobre datos reales con informe de evidencia). Un PASS de pytest
nunca es VALIDATED. Este índice sólo refleja evidencia que vive en git: los informes de
`results/` están ignorados (`.gitignore`) y, mientras no se versionen en `docs/validation/`
(ROADMAP §0, enmienda 14), ninguna fase se marca VALIDATED aquí.

| fase | qué es | documento | estado |
|---|---|---|---|
| 2A | Modelo de datos DuckDB (esquema, provenance, as-of, migraciones v1→v3) | `PHASE_2A_DATA_MODEL.md`, `src/weather_agent/database.py` | IMPLEMENTED · TESTED (`tests/test_database.py`, `test_integrity.py`, `test_weather_asof.py`) |
| 2B | Descubrimiento del catálogo Gamma: markets/outcomes/fees/resolución, checkpoint | `PHASE_2B_MARKET_DISCOVERY.md`, `PHASE_2B_FINAL_BUNDLE.txt`, `scripts/validate_2b.py` | IMPLEMENTED · TESTED (`test_discovery.py`, `test_resolution.py`, `test_fees_*.py`, `test_ingest_atomic.py`); harness real (`validate_2b.py`) sin informe versionado → no VALIDATED en git |
| 2C | Checkpoint/resume persistente (Blocker 1) y no-look-ahead adversarial (Blocker 2), features/labels base | `PHASE_2C_DESIGN.md`, `scripts/validate_2c.py` | IMPLEMENTED · TESTED (`test_checkpoint_resume.py` con SIGKILL real, `test_no_lookahead_adversarial.py`, `test_no_future_information.py`); informe `validate_2c.py` no versionado |
| 2D | Strategy A V1 (p_market/p_weather/edge_gross/señal) y contrato `outcome_label` | `PHASE_2D_STRATEGY_A_DESIGN.md`, `scripts/validate_2d.py` | IMPLEMENTED · TESTED (`test_strategy_a.py`, `test_outcome_label.py`, `test_probability.py`); `validate_2d.py` fija `validated=False` (requiere catálogo real) |
| 2E | Ancla temporal `T = endDate − lead_hours` (decisión D1 de 2E) + registro de estaciones (coordenadas D1-COORD, ICAO variable en el tiempo, tz) | ancla: `PHASE_2E_LEAD_HOURS_ANCHOR.md` — **borrador fuera de git** (ratificado 2026-09-04 sobre baseline `5287122`, aún sin commit en este repo; sin código) · registro de estaciones: R7/R27 | DOCUMENTED fuera de git (ancla; pendiente de versionar) · PENDING (registro de estaciones) |
| 2F | Ingestión: precios CLOB `price_history` (R9), forecasts Open-Meteo `weather_forecasts` con `available_at` fail-closed (R15), observaciones IEM `weather_observations` (R13); descubrimiento de mercados abiertos como feed prospectivo (R26, `docs/DISCOVERY_OPEN_MARKETS.md`) | `docs/DISCOVERY_OPEN_MARKETS.md`; resto sin documento aún | R26 IMPLEMENTED · TESTED (`test_discovery_open.py`); R9/R13/R15 PENDING |
| 2G | M2: `weather_errors` → cuantiles p10..p90 por estación/modelo/lead/mes (R16) + backtest walk-forward que escribe `backtest_results` (R18–R21) | sin documento aún (preregistro pendiente) | PENDING |
| 2H | Paper: colector forward-only (R22), `paper_trades` con `SIMULATED_EXECUTABLE` (R23), corrida preregistrada de N días (R24) | sin documento aún | PENDING |

Los identificadores R\* remiten a `~/pmw-e2/ROADMAP.md` §2–§3 (orden topológico y criterios
de hecho).

### R6 (higiene de comentarios) — hecho y diferido

Corregido (solo texto, sin cambio de comportamiento): `SCHEMA_VERSION stays 2` en `database.py`;
rutas `phase1_5/...` inexistentes en `config.py`, `polymarket/__init__.py`, `resolution.py`;
docstring de `validate_2c.py` (Blocker 2 se valida en §5b); cabeceras `STATUS: ... authored
without Python execution — NOT tested` de `discovery.py`, `resolution.py`, `fees.py`, `config.py`,
`polymarket/__init__.py`, `strategy_a.py` y `tests/conftest.py` → `IMPLEMENTED + TESTED
(<tests>)`, `NOT VALIDATED` contra Gamma en vivo.

**Diferido, deliberadamente:**

* `scripts/validate_2b.py:1094-1095` (BLOCKER "checkpoint/resume only stub-tested", anterior a
  2C): el harness 2B se trata como **congelado** (PHASE_2C_DESIGN.md §4, Alt A); el texto es
  histórico del informe 2B y su superación queda registrada en 2C (`test_checkpoint_resume.py`,
  `validate_2c.py`). No se edita para no alterar un harness ya ejecutado.
* `PHASE_2B_FINAL_BUNDLE.txt` (checksums `PENDING-compute-post-reconstruction`): el bundle es un
  **snapshot histórico** de la Rev 3 de 2B (nº de líneas de entonces); calcular sha256 sobre el
  árbol actual no reproduciría aquel estado. Se conserva tal cual como documento histórico; no
  se recalcula.

## Nomenclatura

Fijada por R25 (ROADMAP) para deshacer dos ambigüedades:

1. **Fases**
   * **2E = ancla temporal + registro de estaciones.** El único documento que describe 2E
     es `PHASE_2E_LEAD_HOURS_ANCHOR.md`; a fecha de este índice **no está versionado**
     (borrador fuera de git, pendiente de commit), por lo que la fila 2E no puede apoyarse en
     evidencia en git y se marca "DOCUMENTED fuera de git". El borrador
     `PHASE_2E_SETTLEMENT_OPERATOR_DESIGN.md` (también fuera de git) NO es 2E: el
     `SettlementOperator` pertenece a R12 y se renombrará al integrarse (no a 2E).
   * **2F = ingestión** (precios, forecasts, observaciones; y el feed de mercados abiertos).
   * **2G = M2** (`weather_errors` / cuantiles) **+ backtest**.
   * **2H = paper.**
2. **"D1" (colisión de nombres)**
   * En `PHASE_2E_LEAD_HOURS_ANCHOR.md`, **D1 significa la decisión del ancla temporal**
     (`T = endDate − lead_hours·3600`; prohibiciones sobre `daily_high_time`,
     `last_meaningful_market_time`, `closedTime`).
   * La **convención canónica de coordenadas de estación** (NOAA AviationWeather stationinfo,
     snapshot fechado; OurAirports = control; IEM/OSCAR prohibidos como posición) se cita
     como **`D1-COORD`**. Su registro es la entrada "D1" de `DECISIONS.md` en `~/pmw-e2`
     (2026-09-05); en los documentos nuevos de este repo se escribe siempre `D1-COORD`, nunca
     `D1` a secas.
3. **Estados**: IMPLEMENTED / TESTED / VALIDATED con la definición literal de
   `scripts/HARNESS_CHANGELOG.md`; "DOCUMENTED / RATIFIED" se reserva para decisiones sin
   código (2E ancla) y sólo se aplica a documentos versionados; mientras el documento viva
   fuera de git se escribe "DOCUMENTED fuera de git".
