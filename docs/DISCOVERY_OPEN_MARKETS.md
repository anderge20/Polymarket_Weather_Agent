# Descubrimiento de mercados ABIERTOS y `markets.available_at` (R26)

**Estado:** IMPLEMENTED + TESTED (`tests/test_discovery_open.py`, stub offline). NO VALIDATED:
no se ha ejecutado contra Gamma en vivo. Prerrequisito del modo paper (2H / R23).

## 1. Dos poblaciones, un mismo `discover()`

| modo | llamada | consulta Gamma | población | clave de checkpoint | `markets.available_at` |
|---|---|---|---|---|---|
| histórico (por defecto) | `discover(con, dsv)` / `closed=True` | `/events?...&closed=true` | mercados cerrados/resueltos | `dsv` (idéntica a pre-R26) | `NULL`, `available_at_confidence='UNKNOWN'` |
| abierto (paper) | `discover(con, dsv, closed=False)` | `/events?...&closed=false` | mercados con `endDate` futuro | `dsv + ':open'` (`discovery.checkpoint_key`) | instante UTC de la petición, `available_at_confidence='OBSERVED_AT_DISCOVERY'` |

`closed` se escribe también en `dataset_versions.query_parameters`. Como `ensure_dataset_version`
hace upsert en cada run, `query_parameters.closed` es el valor del **último** run; la constancia
de todas las poblaciones que han alimentado un `dataset_version` está en
`query_parameters.closed_modes_seen` (`discovery.CLOSED_MODES_SEEN`), unión ordenada de todos los
`closed` ejecutados bajo ese dsv (p.ej. `["false", "true"]` tras abierto→cerrado). La población
de cada **fila** se lee en `markets.available_at_confidence` (`OBSERVED_AT_DISCOVERY` = vino del
feed abierto). El resumen de `discover()` devuelve `closed` y `checkpoint_key`.

## 2. Semántica de `available_at`

`available_at` responde a "¿desde cuándo podía un agente externo saber que este mercado
existía?". Es la columna as-of canónica de `markets` (`database.AS_OF_COLUMNS['markets']`).

* **Modo histórico (`closed=True`)**: se mantiene `NULL`. Los metadatos de Gamma
  (`createdAt`, `updatedAt`, `startDate`) NO son una garantía de disponibilidad hacia
  fuera y NO se equiparan a ella (política 2B, #1). No se inventa disponibilidad
  retrospectiva. Consecuencia deliberada: una lectura as-of sobre `markets` **nunca**
  devuelve estas filas (`NULL <= T` no es verdadero).
* **Modo abierto (`closed=False`)**: captura **prospectiva**. `available_at` = instante UTC
  inmediatamente anterior al envío de la petición HTTP `/events` cuya respuesta contenía el
  mercado (`fetch_events_page(..., meta=)` → `meta['requested_at']`). Se estampa **por
  página**: la página N+1 se pide más tarde que la N y sus mercados llevan su propio
  instante. Es la única evidencia de disponibilidad que tenemos de primera mano.
* **Re-descubrimiento**: si la misma fila `(market_id, dataset_version, record_version)` ya
  tenía `available_at` no nulo, se conserva el instante **más temprano**. Disponibilidad =
  "primera vez que pudimos saberlo", nunca "última vez que miramos".
* `ingestion_timestamp` sigue siendo un reloj distinto (momento de escritura). Nunca se
  copia a `available_at`.
* La fila `data_quality.market_data_quality` documenta la política aplicada
  (`available_at_policy`, `observed_fields`, `observed_at`) y saca `available_at` de
  `unknown_fields` en modo abierto.

## 3. Checkpoints separados

Un mismo `event_id` puede verse ABIERTO hoy y CERRADO dentro de días. Con una única clave,
el checkpoint del modo abierto haría que el modo histórico se lo saltase (o al revés). Por
eso `discovery_checkpoint.dataset_version` almacena `dsv` (histórico) o `dsv:open`
(abierto). La atomicidad 2C no cambia: la marca sigue siendo la última escritura de la
transacción por evento.

## 4. Lo que NO hace

* No toca precios, forecasts ni observaciones (2F). No decide `T` (2E). No etiqueta.
* No infiere `winning_outcome` en mercados abiertos (`outcomePrices` no resueltos → `None`).
* No modifica el esquema (`available_at` existe desde la migración v2); `SCHEMA_VERSION = 3`.

## 5. Tests (offline, fixtures)

`tests/gamma_fixtures.py::OPEN_EVENT` deriva de `ANKARA_EVENT` (deepcopy) con `endDate`
2030-08-20T12:00Z, `closed=false`, precios 0.5/0.5, sin campos UMA, ids sintéticos.
`tests/test_discovery_open.py` cubre: (a) `available_at` no nulo dentro de la ventana de la
petición y `OBSERVED_AT_DISCOVERY`; (b) `closed=True` deja `NULL`/`UNKNOWN`; (c) claves de
checkpoint separadas, sin contaminación cruzada, reanudación; (d) `latest_asof`/`query_asof`
sobre `markets` no devuelven un mercado observado después de `T`.
