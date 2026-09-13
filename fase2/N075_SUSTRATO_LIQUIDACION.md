# NIVEL 0.75 · punto 5 — SUSTRATO DE LIQUIDACIÓN

**Diagnóstico y propuesta. No se ha modificado producción y no se ha implementado nada.**

---

## A y B son dos conclusiones distintas y aquí no se mezclan

**A — la población histórica corregida está bien identificada por evidencia observable.**
Sostenido por los puntos 1–4: las diez identidades de `NIVEL0_5_CRITERIO_COMPLETITUD.md`
pasan (18 de 18), `winning_outcome` tiene unicidad y partición en 187 de 187 (A‑276), y la
comparación aislada C1 no mueve la métrica sobre la población compartida.

**B — el catálogo actual NO contiene la terna de liquidación.** Medido ahora mismo:

| columna | `backfill_2b_v1` (EGLC) | `markets_v2` (EGLC) | `markets` entera |
|---|---|---|---|
| `measurement_rule_code` no NULL | **0 de 807** | **0 de 1 997** | **0 de 85 878** |
| `contract_source` no NULL | **0 de 807** | **0 de 1 997** | **0 de 85 878** |
| `measurement_rule` no NULL | 0 de 807 | 0 de 1 997 | — |
| `unit` no NULL | 807 | 1 997 | — |
| `rounding_rule` no NULL | 807 | 1 997 | — |
| `station_identifier` no NULL | 807 | 1 997 | — |

> **Por tanto NO se afirma que el dataset sea «settlement‑ready» para el núcleo congelado.**
> La reingesta arregló la POBLACIÓN. No tocó el SUSTRATO, y no pretendía hacerlo.

`weather_observations` sí está poblado: `observed_value`, `observed_unit` y `series` no NULL
en 1 486 de 1 486. La carencia es exclusivamente de `markets`.

---

## El falso OK de `settle_substrate_missing`, demostrado sobre producción

`scripts/paper_cycle.py:1122`:

```python
def settle_substrate_missing(con) -> list[str]:
    """What `stage_settle` still lacks. Empty list == ready to settle."""
    missing = []
    for table, cols in _SETTLE_REQUIRED.items():
        have = set(db.column_names(con, table))
        missing += [f"{table}.{c}" for c in cols if c not in have]
    ...
```

**Sólo mira `column_names`.** Pregunta si la columna está DECLARADA; nunca si tiene un
valor. Ejecutado tal cual, sin modificarlo, contra `data/pmw.duckdb`:

    settle_substrate_missing(pmw.duckdb) -> []
    => la guarda dice: LISTO PARA LIQUIDAR
    measurement_rule_code no-NULL en markets: 0 de 85 878

Y lo que ocurre entonces, con el núcleo congelado, también ejecutado:

    select_operator(None, None, 'C', 'whole_degree')
      -> SettlementUnavailable: context_out_of_snapshot:
         terna outside the 11-class partition: (None, None, 'C')

**El docstring dice «Empty list == ready to settle» y sobre esa base de datos la lista está
vacía y no se puede liquidar ni un mercado.** El contrato de la función es falso.

### Y el modo de fallo es peor que fallar

Las dos rutas no dejan el mismo registro:

| ruta | qué queda escrito |
|---|---|
| guarda dispara (columna ausente) | `stage settle SKIPPED reason=substrate_incomplete missing=markets.contract_source,...` — **el lector sabe qué falta y por qué** |
| falso OK (columna presente, vacía) | la etapa se ejecuta, recorre las posiciones y anota N rechazos `context_out_of_snapshot` — **un diagnóstico genérico por posición, sin la causa común** |

El falso OK convierte *«el sustrato no está»* en *«el núcleo rechazó estos mercados»*. Es la
misma familia que este proyecto lleva el día entero encontrando: **el hueco que produce un
valor plausible en lugar de un error.** Y hay una ironía aprovechable: `database.py:958` ya
documenta que `discovery.ingest_event` decide **por `column_names`** si escribe
`contract_source` y `measurement_rule_code`. La misma primitiva que puede dejar de escribir
la columna es la única que la guarda usa para comprobar que está escrita.

### La segunda mitad de la ceguera, que hoy no muerde

`_SETTLE_REQUIRED` también lista `weather_observations.observed_value / observed_unit /
series`, y la guarda tiene ahí exactamente el mismo punto ciego. **Hoy no muerde** porque
están pobladas 1 486 de 1 486. Se dice para que no se descubra el día que deje de ser cierto.

---

## Cambio mínimo PROPUESTO (no implementado)

**Objetivo:** que la guarda compruebe también población, **sin cambiar su tipo de retorno**
(`list[str]`), para que ni el llamador ni el campo `missing` del shard cambien de forma.

```python
def settle_substrate_missing(con, *, dataset_version=None, market_ids=None) -> list[str]:
    missing = []
    for table, cols in _SETTLE_REQUIRED.items():
        have = set(db.column_names(con, table))
        missing += [f"{table}.{c}" for c in cols if c not in have]
    # NUEVO: poblacion, solo para la terna de `markets`, y solo sobre las filas
    # que la etapa va a leer de verdad.
    if market_ids and not any(m.startswith("markets.") for m in missing):
        for c in _SETTLE_REQUIRED["markets"]:
            r = db.query(
                con,
                f"SELECT count(*) AS n, count({c}) AS ok FROM markets "
                "WHERE market_id IN (SELECT UNNEST(?)) AND dataset_version = ?",
                [sorted(market_ids), dataset_version])[0]
            if r["n"] and not r["ok"]:
                missing.append(
                    f"markets.{c} (columna presente, 0 de {r['n']} filas pobladas)")
    ...
```

y en el llamador (`stage_settle`, línea 1461), pasarle el ámbito que ya tiene en la mano:

```python
missing = settle_substrate_missing(
    con, dataset_version=dataset_version,
    market_ids={r["market_id"] for r in open_rows})
```

**Dos comprobaciones de API, hechas y no supuestas.** `db.query_one` **no existe**: el
módulo expone `connect`, `init_db`, `column_names`, `insert`, `upsert`, `query`, `query_df`
y `query_asof`, y el snippet de arriba usa `db.query`, que devuelve `list[dict]`. Y el
repositorio no tiene **ningún** uso previo de `IN` con una lista enlazada, así que la forma
`IN (SELECT UNNEST(?))` se probó contra DuckDB en esta misma sesión antes de escribirla. La
primera versión de este documento llamaba a una función inventada; el arreglo costó un
`grep`, y el comentario de `_station_tz` en el propio `paper_cycle.py` dice por qué importa:
adivinar un nombre de API es cómo se coló la degradación silenciosa a `None` en el timezone.

### Las cuatro decisiones de diseño, dichas en voz alta

1. **El ámbito es el de las posiciones abiertas, no el de toda la tabla.** Un recuento
   global sobre 85 878 filas se dejaría engañar por una sola fila poblada en otra estación,
   y además respondería una pregunta que nadie hizo. La etapa sólo va a leer los mercados de
   `open_rows`; ésos son los que tienen que estar poblados.
2. **Sólo la terna de `markets`.** Para `weather_observations` el ámbito correcto es
   `(estación, día)` de cada posición, que es justo lo que el bucle ya comprueba fila a fila
   y rechaza con una razón nombrada. Meterlo en la guarda duplicaría la lógica sin ganar
   diagnóstico. **Queda declarado como punto ciego que NO se tapa en este cambio.**
3. **`0 de N` en el texto, no un booleano.** El shard ya guarda `missing` como cadena; que
   diga *«columna presente, 0 de 12 filas pobladas»* distingue las dos causas para el que
   lea el registro dentro de un mes, que es el único que importa.
4. **La guarda sigue devolviendo `[]` cuando no hay `market_ids`.** Es deliberado y es la
   parte discutible: conserva la firma para los llamadores que no dan ámbito. La alternativa
   —exigir ámbito siempre— es más honesta y rompe más sitios; se menciona para que la
   elección sea visible y no implícita.

### El test que esto pone en rojo, y por qué eso es el hallazgo y no el coste

`tests/test_paper_cycle.py:509 test_settle_reports_ready_on_a_complete_substrate` llama a
`_with_b_substrate(con)` —que **sólo hace `ALTER TABLE ADD COLUMN`**— y afirma
`settle_substrate_missing(con) == []`. Es decir: **hoy la suite certifica como «sustrato
completo» una base de datos con las columnas declaradas y cero filas.** Exactamente el mundo
que produce el falso OK.

Con el cambio propuesto ese test **no se pone en rojo**, porque sin `market_ids` la guarda
sigue devolviendo `[]` — y eso es precisamente lo que hay que arreglar en el test, no en la
guarda: el test tendría que pasar un ámbito y poblar la terna, como ya hace
`_settleable_market` (línea 559, que inserta `SRC_NOAA` / `P_NOAA_TEMPCOL`). **Un test que
sólo puede pasar es el defecto que este proyecto ya tiene nombrado.**

**Nada de esto se ha implementado. Es diagnóstico y propuesta, como pide el encargo.**
