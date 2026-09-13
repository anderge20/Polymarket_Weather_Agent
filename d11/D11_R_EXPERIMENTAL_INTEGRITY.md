# D11 — INTEGRIDAD EXPERIMENTAL DE LA CADENA R

**Alcance estrecho, como pide el encargo.** No es una auditoría del repositorio: es la
pregunta *«¿hay algún defecto adicional que pueda alterar materialmente el experimento de
Level 1 en la cadena R?»*. Settlement sólo se audita donde R dependa de él — y **no depende**:
verificado por grafo de importaciones, el análisis importa **una** cosa de la librería,
`resolution.parse_band`.

No se modela, no se seleccionan modelos, no se calcula poder predictivo, edge ni PnL, no se
activa nada. Producción sin tocar.

Guion: `d11_cadena_r.py` · salida íntegra: `D11_SALIDA_CADENA_R.txt` · **22 comprobaciones,
todas verdes, 0 defectos de alto impacto.**

---

## 1 · FRONTERA POR FRONTERA

### F · FORECAST

| campo | contenido |
|---|---|
| **fuente** | `weather_forecasts`, modelo **`icon_seamless` — el único**, 2 727 filas |
| **función** | `n075_poblacion.pronosticos(con, station, leads)` |
| **input** | `(station, target_date, issue_time, available_at, forecast_tmax)` |
| **output** | `{(target_date, lead): (available_at, forecast_tmax)}` — el **último** disponible |
| **unidad** | Celsius; `exige_celsius()` se niega fuera de ella |
| **timestamp** | `prediction_time = t_asof = end_date(12:00 UTC) − lead` |
| **transformación** | selección por `available_at ≤ t_asof`; ninguna de unidad |
| **guard** | `forecast_tmax IS NOT NULL`; sólo los leads declarados (24, 9) |
| **NULL** | fila sin `forecast_tmax` excluida; par sin pronóstico → evento fuera |
| **test** | `d11_cadena_r.py` F1–F6 |
| **fila real** | **SÍ**, 236 filas de EGLC |

**Sin look-ahead, verificado:**

* `available_at ≥ issue_time` en **236 de 236**.
* `available_at ≠ fetched_at` en **236 de 236** — `fetched_at` es 2026-09-09, el instante de
  descarga; **no es lo que filtra**.
* El pronóstico elegido cumple `available_at ≤ t_asof` en **los 236 pares**, cero violaciones.
* Un solo modelo: **no hay selección de modelo con retrovisión**.

**El target del pronóstico es el máximo diario relevante:** `target_date` es la fecha del
evento (`CAST(end_date AS DATE)`, verificada contra el slug en 2 804 de 2 804 filas, A-278) y
`forecast_tmax` es el máximo previsto de ese día.

> ### LA ÚNICA SUPOSICIÓN QUE SOSTIENE EL «SIN LOOK-AHEAD», MEDIDA Y ACOTADA
>
>     retardos distintos entre available_at e issue_time:  1
>     valor:  4:45:36  en las 236 filas
>
> **`available_at` es una CONVENCIÓN, no una medición**: `issue_time + 4 h 45 min 36 s`,
> constante. El margen que deja:
>
>     lead 24 h   margen min = mediana = max = 1,24 h
>     lead  9 h   margen min = mediana = max = 4,24 h
>
> **Si el retardo real de publicación fuera más de 1,24 h mayor que el declarado, TODOS los
> pronósticos de lead 24 serían look-ahead.** No es un defecto de la cadena —es un hecho
> externo sobre el proveedor— pero es **la única cosa cuya falsedad invalidaría Level 1
> entero**, y no se puede comprobar con este corpus: las 2 727 filas son backfill
> (`fetched_at` 2026-09-09). **Se comprueba hacia delante**, con el colector en vivo, que sí
> registra el instante real de disponibilidad.

### O · OBSERVATION — las dos semánticas, separadas

| | **A · pertenencia a banda** | **B · error de pronóstico** |
|---|---|---|
| **fuente** | `weather_observations.observed_value` + `observed_unit` | `weather_observations.tmax_observed` |
| **unidad** | **la rejilla de la fuente** (= la unidad contractual del mercado) | **Celsius siempre** |
| **por qué** | la banda está en la unidad del contrato (A-41) | `forecast_tmax` es Celsius en las 49 estaciones |
| **demostrado** | `d10_dos_semanticas.py`: KHOU 78,0 F → `78-79°F`, **la ganadora declarada** | mismo día: `tmax_observed` 25,56 C → error −0,24 C |
| **si se confunden** | `tmax_observed` 25,56 C → `67°F or below`, **otra banda** | `observed_value − forecast` = **+52,20**, sin excepción |

**No se mezclan: son dos variables, no una** (A-283).

* **Ventana diaria**: una fila por `(estación, serie, DÍA LOCAL)` — **256 pares, 0 duplicados**.
* **Zona horaria**: **arreglada en este ciclo**. `observaciones()` llevaba `Europe/London`
  **fijo** con un parámetro `station` que prometía una generalidad que el cuerpo no tenía;
  `exige_celsius` deja pasar CYYZ y **2 de sus 27 días caían en una fecha distinta**. Ahora
  toma la zona de `stations.timezone_of`, la función de producción que ya resolvía esto.
  **En EGLC no cambia nada — su zona ES `Europe/London`—, que es exactamente por lo que el
  defecto era invisible.**
* **Sin observación futura en las features**: verificado para los **dos leads y todos los
  eventos**: el día objetivo nunca está en el entrenamiento, y ninguna etiqueta con
  `label_av(d) > t_asof` entra.

      ejemplo 2026-06-07 lead 24: t_asof 2026-06-06 12:00Z · ultimo dia entrenable 2026-06-04
      ejemplo 2026-06-07 lead  9: t_asof 2026-06-07 03:00Z · ultimo dia entrenable 2026-06-05

### T · TARGET — `winning_outcome`

| campo | contenido |
|---|---|
| **fuente** | `markets.winning_outcome = 'Yes'` — **el resultado contractual del lado YES** |
| **output** | una ganadora por evento; `{1: 185}` en los 185 eventos elegidos |
| **guard** | regla A-275: `resolved` + partición completa + exactamente una ganadora + desempate por `close_time` |
| **NULL** | `winning_outcome` NULL en 17 de 79 735 filas globales; esos eventos no pasan la regla |
| **test** | `d11_cadena_r.py` T1–T8, `n075_identidades.py` (18 comprobaciones) |
| **fila real** | **SÍ** |

Verificado por lectura del código **y** por ejecución:

* **NO se usa `is_winner`** (además es NULL en 3 994 de 3 994).
* **NO se usa `outcome_index`.**
* **La población no toca ninguna observación**: el target **no** se infiere del proxy IEM.
* **Una fecha → un evento**: sin duplicación; sin `event_id` repetido.
* **`won` sólo se escribe como `y`**: no entra en ninguna probabilidad — verificado sobre el
  código de `filas()`.

### P · PROBABILITY

| campo | contenido |
|---|---|
| **fuente** | `n075_metricas.filas(pob, obs, FC, lead)` |
| **output** | filas `(event_id, lead, banda, y, {control: p})` |
| **transformación** | `REF_uniforme = 1/n` (estructura pura) · `B0`…`B4` desde `tr`, ya filtrado por disponibilidad |
| **guard** | `len(tr) ≥ 20`; `label_av(d) ≤ t_asof` |
| **clipping** | `min(max(p, 1e-6), 1 − 1e-6)`, simétrico e idéntico en los dos brazos |

* **Suman 1 dentro de cada evento en los seis controles**, error máximo **1,11·10⁻¹⁶**.
* **Exactamente un `y = 1` por evento.**
* **Toda `p ∈ [0,1]` ANTES del recorte**: el recorte no está tapando nada.
* **Correspondencia probabilidad ↔ contrato, probada por PERTURBACIÓN**: mover la banda
  ganadora 100 grados cambia **su** probabilidad (`0,35000 → 0,00000`). *La `p` va con el
  contrato, no con la posición en la lista.*

### S · SCORING

* **Un solo estrato** en la población puntuada: `{11}`.
* El control estructural coincide con su fórmula cerrada: Brier `0,08264463` y Log Loss
  `0,30463610`, ambos a `1e-12`.
* **Estratificar por `n` siempre; prohibido agregar entre escaleras** (H4 = INVALIDADA, A-280).

---

## 2 · DEFECTOS DE ALTO IMPACTO

| condición buscada | resultado |
|---|---|
| target incorrecto | **no** |
| forecast futuro | **no** — 0 violaciones de `available_at ≤ t_asof` |
| observación futura | **no** — verificado en los dos leads |
| timestamp incorrecto | **no** |
| timezone incorrecta | **encontrada y ARREGLADA** (categoría C) |
| mezcla de unidades | **no** — guardia `exige_celsius` + estación de unidad única |
| duplicación de eventos | **no** — biyección fecha↔evento |
| probabilidad mal asociada | **no** — probado por perturbación |
| scoring incorrecto | **no** — fórmulas verificadas a `1e-12` |

**Y una bandera que resultó ser de mi propia comprobación, no de los datos.** La primera
versión marcó «4 días con más de una fila» agrupando por `CAST(observation_time AS DATE)` —
**día UTC**— cuando `observaciones()` agrupa por **día local**. Las filas de las 23:20/23:50
UTC pertenecen al día local siguiente (00:20/00:50 BST). Por día local: **256 pares, 0
duplicados**. *Medido antes de publicarlo.*

---

## 3 · D10-7 — PROCEDENCIA DE LOS METADATOS DE LIQUIDACIÓN

**1. ¿De dónde deberían proceder?** De `resolution.classify_measurement_rule(description)` —
el clasificador R29 que `discovery.ingest_event` ya llama— sobre la **descripción del propio
mercado**.

**2. ¿Existen en la fuente original?** **SÍ.** `CATALOG_V2.duckdb` tiene la tabla `dsc` con
`desc` no NULL en **93 221 de 93 221** mercados (`desc_from = 'market'` en todos).
`mk.measurement_rule` también existe, pero es un **resumen** y alimentarlo al clasificador da
`P_UNKNOWN`: **la descripción completa es la única entrada válida.**

**3. ¿Recuperables sin inferencia post-hoc?** **SÍ, y la distinción importa.** Re-ejecutar un
clasificador determinista sobre **texto primario preservado** es reconstrucción desde la
evidencia. **No** usa escalera, **no** usa `winning_outcome`, **no** usa observación, **no**
usa el resultado. Ejecutado sobre los 1 997 mercados de EGLC:

    ('WU', 'P_byForecast')                  1 018
    ('WU', 'P_WU_GENERIC_sin_calificador')    792
    ('WU', 'P_WU_DailyObservations')          187      source_confidence = VERIFIED

**4. ¿Debe `backfill_markets` incorporarlos?** **SÍ**, uniendo `dsc` y llamando al mismo
clasificador — la misma función que la otra ruta de ingesta ya usa. Es **D10-7, categoría B**,
y espera §34.

**5. ¿Hay forma segura de reparar el histórico?** **SÍ**: bajo un `dataset_version` **nuevo**,
sin mutar ninguna fila existente, persistiendo `source_confidence` junto al código para que
una clasificación dudosa sea distinguible de una verificada.

> ### Y EL RESULTADO QUE CAMBIA LA LECTURA: RECUPERARLOS **NO** HARÍA LIQUIDABLE EL ALMACÉN
>
> Las tres ternas, contra el núcleo congelado:
>
>     P_byForecast                   1 018 mercados  ->  no_settlement_operator:by_forecast
>     P_WU_GENERIC_sin_calificador     792 mercados  ->  no_settlement_operator:Y_undefined_by_contract
>     P_WU_DailyObservations           187 mercados  ->  ACEPTA
>
> **Sólo 187 de 1 997 son liquidables, y los 1 810 restantes caen en estratos fail-closed
> DECLARADOS**: el núcleo los rechaza **por diseño**, no por accidente. Los 187 son
> **17 eventos × 11 bandas** — comprobado, porque «187 mercados» y «187 eventos» son números
> iguales y cosas distintas.
>
> Recuperar los metadatos convertiría *«todo NULL, causa desconocida»* en *«el 91 % de los
> contratos de EGLC son de un tipo que el núcleo rechaza a propósito»*. **Eso es exactamente
> lo que el diseño fail-closed existe para decir**, y es un resultado, no un arreglo.

**No se rellena ningún campo por deducción.** Si para alguna estación la descripción no
permitiera clasificar, la declaración correcta es
**`historical settlement metadata unavailable`**, no una reconstrucción.

---

## 4 · LOS DOS GATES, SEPARADOS

### `D0-R` — INTEGRIDAD EXPERIMENTAL → **READY**

¿Puede la cadena R producir un experimento histórico válido de poder predictivo?
**Sí**, sobre EGLC, con las 22 comprobaciones en verde, **bajo la suposición declarada del
retardo de publicación** (margen 1,24 h al lead 24).

### `D0-P` — INTEGRIDAD DE PRODUCCIÓN / LIQUIDACIÓN → **BLOCKED**

Sin cambios: dos falsos READY, la prosa por el código, el `NaT`, la traducción de series fuera
de la librería, y `backfill_markets` sin contrato ni test. Cinco de categoría B esperando §34.

> **`D0-R = READY` NO autoriza a tocar producción.** Son gates independientes y el segundo
> sigue cerrado. El gate de dinero real sigue siendo exclusivamente del usuario.

---

## 5 · CRITERIO DE CIERRE

| condición | estado |
|---|---|
| no existe otro defecto de alto impacto en R | **SÍ** — 0 tras corregir la zona horaria |
| target validado | **SÍ** |
| forecast validado | **SÍ** |
| observation validada | **SÍ** |
| timestamps validados | **SÍ**, con la suposición del retardo **declarada y acotada** |
| probability validada | **SÍ**, incluida la correspondencia por perturbación |
| scoring validado | **SÍ**, fórmulas a `1e-12` |
| sin look-ahead | **SÍ** |
| sin mezcla de unidades | **SÍ** |
| sin duplicados | **SÍ** |
| escaleras estratificadas | **SÍ** — un solo estrato, `{11}` |

# `D11-R = CLOSED`

**Con una condición que va pegada al veredicto y no se puede separar de él:** la validez de
Level 1 descansa sobre que el retardo de publicación declarado (4 h 45 min 36 s) no sea más de
**1,24 h** menor que el real. **No es comprobable con el corpus actual** y sí lo es hacia
delante con el colector en vivo. *Si esa suposición cae, cae el experimento entero, no una
parte.*

**Level 1 queda formalmente abierto como INVESTIGACIÓN HISTÓRICA y nada más.** Prohibidos
producción, settlement, ejecución, paper trading, PnL operativo y activación del bot. El
objetivo es exclusivamente determinar si el pronóstico disponible en `prediction_time` contiene
poder predictivo **fuera de muestra** sobre `P(YES)`. **No se buscan estrategias hasta haber
demostrado primero poder predictivo.**
