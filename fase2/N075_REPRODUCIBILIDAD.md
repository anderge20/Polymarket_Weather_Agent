# NIVEL 0.75 · punto 6 — REGISTRO DE REPRODUCIBILIDAD

Objetivo declarado en el encargo: *«que otra ejecución pueda reconstruir exactamente OLD y
CORRECTED»*. Lo que sigue es todo lo que hace falta para eso, y nada más.

## Código

| qué | valor |
|---|---|
| repositorio | `anderge20/Polymarket_Weather_Agent` |
| `main` en el momento del análisis | `b523a8f31ad8f669737492dac771748266bd2861` (fusión de #53) |
| árbol del que los guiones importan `src` | `/Users/mariaaleu/.claude/jobs/324ffe40/tmp/wt-main`, en `22ba210d96491ee591934179309188c1271177e7` (fusión de #52) |
| ¿importa la diferencia? | **no**, y está verificado: `git diff 22ba210 b523a8f -- src/` es **vacío**, y `src/weather_agent/polymarket/resolution.py` —la única cosa que los guiones importan— da el mismo `sha256 9e5d3e8c…` en los dos árboles. #53 sólo tocó `scripts/paper_cycle.py` y su test. |
| import concreto | `weather_agent.polymarket.resolution.parse_band` |
| entorno | Python 3.14.3 · duckdb 1.5.5 · macOS (darwin 21.6.0) |

## Datos

| qué | valor |
|---|---|
| base | `/Users/mariaaleu/workspace/Polymarket_Weather_Agent/data/pmw.duckdb` |
| tamaño / mtime | 2 476 224 512 B · 2026‑09‑13 17:28 UTC |
| **brazo OLD** | `markets.dataset_version = 'backfill_2b_v1'` |
| **brazo CORRECTED** | `markets.dataset_version = 'markets_v2'` |
| observaciones | **las mismas en los dos brazos**, sin filtrar por `dataset_version` (sólo existe `backfill_2b_v1`, con dos `source`: `IEM_ASOS_METAR` 118 filas y `IEM_ASOS_METAR_RT34` 138) |
| pronósticos | **los mismos en los dos brazos**, `backfill_2b_v1`, 236 filas, `forecast_tmax IS NOT NULL` |
| estación | `station_identifier = 'EGLC'` |

Huellas criptográficas de **las filas exactas que entran en el análisis**, ordenadas
canónicamente (guion y salida íntegra en `N075_HUELLA_DATASET.txt`):

    markets+outcomes EGLC backfill_2b_v1   47f60af01e0b9bd33f3e0ed140218d1032b27b7ae6ae33e23cf766f35aef5fbd
    markets+outcomes EGLC markets_v2       59e3caa5ac372549816ba868dd0c2c88509eca9e1a900c07b0f9a6553d2050a7
    weather_observations EGLC              f323903ee8576ee457edc836eb49119ba69d6ab0be53031491b44e22b19079d8
    weather_forecasts EGLC                 0574207e43467c2e23b7095ba14f9caad82789530bda4b6985392b22bf9b6c30

**No se hace hash del fichero `.duckdb`**: son 2,4 GB y su suma cambia con cualquier
escritura ajena al análisis, incluidas las de otras estaciones. Las cuatro huellas de arriba
son sobre el **contenido leído**, que es la condición que de verdad hay que reproducir.

## Parámetros, todos, con su valor

| parámetro | valor | dónde se fija |
|---|---|---|
| estación | `EGLC` | `n075_poblacion.py` |
| leads | `(24, 9)` — los dos siempre | `n075_metricas.py:LEADS` |
| `t_asof` | `end_date(12:00 UTC) − lead` | `tasof()` |
| disponibilidad de la etiqueta | `medianoche local del día siguiente + 24 h` | `label_av()` |
| mínimo de entrenamiento | **20 pares** | `filas()` |
| ventana de climatología B0 | **últimos 30** de `tr` | `filas()` |
| clipping | `EPS = 1e-6` | `n075_metricas.py:EPS` |
| elegibilidad | `resolved` **de todo el evento** + partición completa + exactamente una ganadora | `poblacion()` |
| deduplicación | `(station, target_date)` | `poblacion()` |
| desempate | menor `close_time` **por encima del fin del día civil local**; si ninguno está por encima, el menor de los elegibles | `poblacion()` |
| fecha objetivo | `CAST(end_date AS DATE)` | `poblacion()` |
| regla de observación | máximo por día local sobre todas las `source` | `observaciones()` |
| aleatoriedad | **ninguna** — no hay bootstrap en este nivel | — |

## Guiones y salidas, con hash

```
da1d2cbbb20d1805b35ed25697d43d7ec01adc5a7ec46ac6c8b7ababf290dbba  n075_poblacion.py
2e15cb14cab1544dc9d1f09a3f989df236c72bcbe0132778c7534fd4c5683ee0  n075_metricas.py
ceac8158bf612731c38382ed5b41b5e186aad1a00e97c7de539b6990ddefbfcb  N075_METRICAS_SALIDA.txt
5787852e77b038d4abb9cbbab92495b32a9e9a6c21562d908460c4189a747908  N075_HUELLA_DATASET.txt
91344b14e59ce50c12f79cac4b2a0adaf6ea2ef8b0a269d350e8a1ec5cabd6d2  N075_AISLAMIENTO_CAUSAL.md
59cc060dcc52f4c9d9e664a1c068aa76a52d07a0c5b62167bd7398256a7c9848  N075_OLD_VS_CORRECTED.md
15afdfeb4b44021682665814a4258824b9b4c71f895c4ceec344457b81b67883  N075_SUSTRATO_LIQUIDACION.md
```

Todo bajo `~/pmw-e2/fase2/`, espejado en la rama `research/modelsel-artifacts`.

## Orden de ejecución

    python3 n075_poblacion.py          # poblacion de los dos brazos + diagnostico
    python3 n075_metricas.py           # Brier y Log Loss, C1 / C2 / C3, auditoria de p

**Timestamp de la ejecución que produjo estos números: 2026‑09‑13 18:40–18:46 UTC.**

## Lo que NO queda reproducible, y hay que decirlo

El **resultado histórico** de `n1_20_filtros.py` (A‑239/A‑240) depende de
`LONDON_CANDIDATES.json`, que es la salida de un backtest de Strategy A con su propio
estado. Ese artefacto sigue en `~/pmw-e2/`, pero **el resultado histórico no forma parte de
esta comparación** (§1 de `N075_AISLAMIENTO_CAUSAL.md`) y su reproducción no se garantiza
aquí. Lo que se garantiza es OLD y CORRECTED tal como se definen arriba.
