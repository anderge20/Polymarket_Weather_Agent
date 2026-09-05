# PHASE 2E — `lead_hours`: ancla de mercado (decisión D1)

**Estado: RATIFIED / DOCUMENTED** · Ratificada 2026-09-04 · Baseline de repo: `5287122`

Este documento cierra **D1**, la decisión sobre el ancla temporal de `lead_hours`.
No introduce cambios de esquema, de código ni de datos.

---

## 1. Definición ratificada

```
T = endDate - lead_hours * 3600
```

| Término | Definición |
|---|---|
| `endDate` | **Cierre programado del mercado** (*scheduled market end*) |
| `T` | **Instante de decisión/predicción de mercado** |
| `lead_hours` | Número de horas antes de `endDate` en que se evalúa la estrategia |
| `issue_time` | Hora nominal de inicialización del forecast ECMWF |

**`lead_hours` NO es un horizonte meteorológico medido desde `issue_time`.**
Es un desplazamiento hacia atrás desde el cierre programado del mercado, y define
el instante en que la estrategia habría tomado la decisión.

## 2. Prohibiciones explícitas

1. NO usar `target_start`, `target_midpoint`, `target_end` ni `expected_max_time`
   como ancla de `lead_hours`.
2. NO usar `daily_high_time` como ancla.
3. NO usar `last_meaningful_market_time` como ancla.
4. NO redefinir `lead_hours` como diferencia entre `issue_time` y `target_date`.

## 3. Separación de relojes

Estos cuatro instantes se mantienen **completamente separados**. Ninguno se deriva
de otro ni se sustituye por otro:

| Reloj | Qué es |
|---|---|
| **Market decision time `T`** | Cuándo la estrategia decide. Derivado de `endDate` y `lead_hours` |
| **Forecast `issue_time`** | Inicialización nominal de la pasada del modelo |
| **Forecast availability time** | Cuándo el forecast fue obtenible en la fuente |
| **Observation availability time** | Cuándo la observación fue obtenible en la fuente |

Relación temporal que debe quedar explícita:

```
issue_time < T
```

para que un forecast se considere válido para la decisión tomada en `T`.

Esta condición es **necesaria pero no suficiente**: la admisibilidad as-of del
forecast se rige además por su disponibilidad, no por su `issue_time`.

## 4. Justificación

### 4.1 Precedente histórico

`endDate` fue el ancla **implementada en Fase 4**, sustituyendo a la medianoche de
la fecha objetivo, y quedó validada en las fases 4-5.

### 4.2 Alcance real de la crítica de Fase 1.5B

La objeción de Fase 1.5B sobre *leads* terminales se refería a
**`closedTime` / resolución formal**, **NO a `endDate`**.

`endDate` es siempre anterior a `closedTime` — medido entre **+0,38 h y +15,33 h**
antes, según ciudad — de modo que un lead anclado a `endDate` cae siempre **más
lejos** de la zona terminal sin cotizaciones, no más cerca. La crítica de 1.5B no
aplica a este ancla.

### 4.3 Motivo de exclusión de las alternativas

`daily_high_time` y `last_meaningful_market_time` quedan excluidos como anclas
porque **requieren información posterior para determinar el instante de decisión y
pueden introducir look-ahead**.

Ambos son conocibles solo *ex post*: `daily_high_time` exige haber observado el día
completo; `last_meaningful_market_time` exige haber observado la vida entera del
mercado. Anclar `T` a cualquiera de ellos haría que el backtest eligiera *cuándo*
decidir usando información que en `T` no existía.

Es una fuga en la **selección del instante de decisión**, no en las features. Las
guardas as-of vigentes verifican que los inputs tengan timestamp <= T y **la
cumplirían**, porque el problema no está en los inputs sino en cómo se escogió `T`.
Ninguna comprobación existente la detectaría.

`endDate`, en cambio, es metadato publicado al crear el mercado: conocible en tiempo
real y disponible antes de `T`.

## 5. Lo que esta decisión NO afirma

**Esta ratificación es metodológica. NO constituye una afirmación de disponibilidad
empírica de precios en `T`.**

No está verificado que existieran cotizaciones CLOB en los instantes `T` derivados
de esta definición. La ausencia de cotización en `T` debe tratarse como **exclusión
fail-closed registrada**, nunca desplazando el ancla para encontrar datos: mover el
ancla en busca de cobertura reintroduce exactamente el look-ahead descartado en §4.3.

## 6. Verificaciones pendientes

| | Sonda | Qué debe verificar |
|---|---|---|
| **P1** | Catálogo Gamma | Generalización de `endDate` fuera del catálogo actual |
| **P3** | CLOB `prices-history` | Disponibilidad real de cotizaciones en `T` |

Ambas siguen **abiertas**. La identidad del ancla queda cerrada; su adecuación
empírica no.

## 7. Evidencia

| Ref | Fuente | Contenido |
|---|---|---|
| E1 | `backtest.py:26` (proyecto original) | `make_dataset(city, lead_hours=24, ...)` |
| E2 | `backtest.py:57` | `ts = int(end_dt.timestamp()) - lead_hours*3600`, con `end_dt` = `endDate` |
| E3 | `backtest.py:50-54` | Comentario del *lead anchor fix*: anclar a medianoche de la fecha objetivo se probó y se rechazó |
| E4 | `validation_oos.md:23` | "precio Yes a 24 h antes del cierre, anclado a `endDate` (mediodía UTC) — el fix de la fase 4" |
| E5 | `validation_results.md:19` | "24 h antes del cierre (`endDate-24 h`)" |
| E6 | `PHASE_1_5B_FETCH_SUMMARY.md:100` | "Do NOT define leads solely relative to the UMA `closedTime`" |
| E7 | `PHASE_1_5B_FETCH_SUMMARY.md:104-105` | Definiciones de `last_meaningful_market_time` y `daily_high_time` |
| E8 | `PHASE_2B_MARKET_DISCOVERY.md` §11 · `discovery.py:151` | `close_time` = `closedTime`; `resolution_timestamp` = `umaEndDate`; `endDate` en `source_timestamps` |
| E9 | Medición read-only sobre el catálogo (2026-09-04) | `endDate` presente en 110/110 y exactamente `12:00:00Z` en 110/110, 9 ciudades, ambos hemisferios |
| E10 | Medición read-only sobre el catálogo (2026-09-04) | `daily_high_time` 0/110 · `last_meaningful_market_time` 0/110 |

## 8. Alcance

Esta decisión **no** modifica esquema, código, datos ni ningún artefacto de 2A/2B/2C/2D.
`weather_errors.lead_hours` conserva su definición de columna; que herede esta misma
semántica de ancla sigue siendo **INFERRED** y se documentará por separado.

Cuestión adyacente abierta, fuera del alcance de D1: en Wellington `endDate` 12:00 UTC
cae en la medianoche civil local, lo que debe reconciliarse con la definición de
`target_date`.
