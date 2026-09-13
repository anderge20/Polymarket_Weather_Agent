# NIVEL 0.75 · punto 3 — AISLAMIENTO CAUSAL DE `OLD` vs `CORRECTED`

**Escrito ANTES de calcular ningún Brier ni Log Loss sobre los dos brazos.** El encargo
dice: *«Si algún elemento cambia entre OLD y CORRECTED, detenerse y documentarlo antes de
comparar resultados.»* Cambian siete. Esto es la parada.

---

## 1. PARADA: la comparación «mi resultado anterior vs la reejecución» NO está aislada

La lectura natural de «OLD vs CORRECTED» era *el número que publiqué en A-239/A-240 contra el
que salga ahora*. **Esa comparación cambia siete cosas a la vez** y ninguna de las siete es
la población. Lo que sigue está medido sobre `n1_20_filtros.py` (el guion que produjo el
resultado antiguo) y `n1_40_reejecucion.py`:

| # | elemento | `n1_20` (histórico) | `n1_40` (reejecución) | ¿por qué importa |
|---|---|---|---|---|
| 1 | universo de mercados | `LONDON_CANDIDATES.json`, 638 `market_id`, 115 fechas | consulta directa a `markets` | el json es la **salida de un backtest de Strategy A**, que mira `p_mid`, `edge` y `margin`. Es un filtro que **depende del precio** |
| 2 | ventana temporal | la del json: 2026‑04‑11 → 2026‑08‑23 | la del almacén: 2025‑12‑31 → 2026‑08‑23 | corta 3,5 meses sin declararlo |
| 3 | serie de observación | `weather_observations` sin filtrar | idem, pero hoy hay **dos series** | `IEM_ASOS_METAR` (118 días) + `IEM_ASOS_METAR_RT34` (138 días). Las features B0/B1/B3/B4 salen de aquí |
| 4 | `dataset_version` de observaciones | sin filtro | parámetro | — |
| 5 | `dataset_version` de pronósticos | sin filtro | parámetro | sólo existe `backfill_2b_v1`; filtrar por `markets_v2` deja `FC` vacío |
| 6 | modelos reportados | 4 (`n1_20:43` omite `B1_persist`) | 5 | — |
| 7 | definición de `B1` | no existía en `n1_20` | última etiqueta **disponible** en `t_asof` | — |

**Conclusión del punto 1: el resultado histórico NO es el brazo OLD.** Cualquier delta entre
él y una reejecución mezcla población, ventana, serie de observación y conjunto de modelos.
Queda fuera de la comparación y se cita sólo como antecedente.

### 1 bis. Y un defecto en mi propio guion, encontrado al escribir el segundo

`n1_40_reejecucion.py:120‑125` une `markets m JOIN outcomes o ON o.market_id = m.market_id`
**sin `AND o.dataset_version = m.dataset_version`**. Los 807 `market_id` de
`backfill_2b_v1` están **también** en `markets_v2` (intersección medida: 807 de 807), y
`outcomes` guarda una fila por (`market_id`, `dataset_version`). Sin el predicado, cada
evento compartido recibe **sus bandas duplicadas**, la prueba de partición falla por bandas
repetidas y la población se vacía. Medido:

    con el join defectuoso      markets_v2: 24 fechas elegibles de 186
    con `o.dataset_version = m.dataset_version`   markets_v2: 186 de 187 eventos elegibles

Es exactamente el defecto que yo mismo le señalé a la sesión B en la tarea #16
(«`dataset_version` no filtrado en features/strategy»), cometido en mi guion catorce días
después. **Auditar X encuentra los fallos de X; escribir un segundo X encuentra los que X
daba por supuestos.**

---

## 2. La comparación REPARADA: una sola implementación, un solo parámetro

`n075_poblacion.py` construye la población para los dos brazos con **el mismo código**. Lo
único que cambia entre llamadas es `markets.dataset_version`.

| Elemento | OLD | CORRECTED | ¿idéntico? |
|---|---|---|---|
| **target** | ganadora declarada por el mercado, `markets.winning_outcome = 'Yes'`, una por evento | igual | **SÍ** |
| **fecha objetivo** | `CAST(end_date AS DATE)` | igual | **SÍ** — verificado contra la fecha del slug en 2 804 de 2 804 filas de las dos versiones; `end_date` es 12:00 UTC en las 1 997, así que no hay riesgo de zona horaria |
| **prediction_time** | `t_asof = end_date − lead` = 12:00 UTC − lead | igual | **SÍ** |
| **lead** | 24 h y 9 h, los dos siempre | igual | **SÍ** |
| **model** | B0 clima30 · B1 persistencia · B2 fc crudo · B3 fc+error · B4 fc+bias | igual | **SÍ** (mismo código, los cinco) |
| **features** | `obs` = máximo por día local sobre **todas** las series · `FC` = último pronóstico con `available_at ≤ t_asof` | igual | **SÍ** — mismas 138 filas de observación y mismos 236 pronósticos en los dos brazos |
| **price** | **no se usa** | **no se usa** | **SÍ** — ninguna de las dos métricas toca `p_mid`, book, ni precio alguno. La verdad la pone `winning_outcome` |
| **filters** | `resolved` + partición completa + ganadora única + dedup `(station, fecha)` + `len(tr) ≥ 20` + existe `FC(fecha, lead)` + existe `obs(fecha)` | igual | **SÍ** |
| **tratamiento de missing** | evento sin `FC` al lead → fuera; menos de 20 pares de entrenamiento → fuera | igual | **SÍ** |
| **clipping** | `min(max(p, 1e‑6), 1 − 1e‑6)` | igual | **SÍ** |
| **weighting** | media dentro del evento, luego media sobre eventos (primaria); media sobre contratos (secundaria) | igual | **SÍ** |
| **aggregation** | por `(event_id, lead)`; los dos leads siempre reportados | igual | **SÍ** |
| **`markets.dataset_version`** | `backfill_2b_v1` | `markets_v2` | **NO — es el tratamiento** |

**Todo idéntico salvo la línea del tratamiento.** Pero eso no basta, y el punto 3 siguiente
es la razón.

---

## 3. LA POBLACIÓN NO CAMBIA SÓLO DE TAMAÑO: CAMBIA DE ESTACIÓN DEL AÑO

| | OLD | CORRECTED |
|---|---|---|
| eventos en el almacén | 163 | 187 |
| elegibles | 40 | 186 |
| fechas elegidas | 40 | 185 |
| escaleras de las elegidas | `{11: 40}` | `{7: 2, 9: 26, 11: 157}` |
| **fechas puntuables** (obs + FC, los dos leads) | **40** | **117** |
| escaleras puntuables | `{11: 40}` | `{11: 117}` |
| **rango puntuable** | **2026‑04‑08 → 2026‑05‑19** | **2026‑04‑08 → 2026‑08‑23** |
| tasa YES por contrato | 0,09091 | 0,09091 |

Las 40 fechas de OLD son un **subconjunto estricto** de las 185 de CORRECTED
(`OLD \ CORRECTED = 0`). Las 77 fechas que CORRECTED añade dentro de la ventana puntuable
son **2026‑05‑21 → 2026‑08‑23**: no están intercaladas, son una **extensión hacia el
verano**.

    máximo observado, media    comunes (40)  16,70 °C      nuevas (77)  26,27 °C     +9,57 °C
    máximo observado, desv.    comunes        3,34 °C      nuevas        4,14 °C

> **Un delta OLD → CORRECTED sobre la muestra completa NO mide el efecto de la corrección
> del dataset: mide la corrección Y el paso de primavera a verano, y no hay forma de
> separarlas dentro de esa comparación.** Es exactamente el sesgo que el encargo pide no
> cometer, y aparece aunque todos los elementos metodológicos sean idénticos.

### Cómo se responde a eso (declarado antes de ver números)

Se reportan **tres** comparaciones, las tres con la misma métrica y el mismo código:

* **C1 — AISLADA (primaria).** OLD vs CORRECTED **restringidos a las 40 fechas comunes**.
  Aquí sí cambia sólo el dataset. Predicción escrita antes de correr: las dos ramas dan
  **números idénticos salvo por 2026‑05‑19** (ver §4), porque en 39 de las 40 fechas comunes
  el evento elegido tiene el mismo `event_id`, las mismas bandas y la misma ganadora.
* **C2 — COMPLETA (secundaria, confundida).** OLD(40) vs CORRECTED(117). Se publica porque
  el encargo la pide, **etiquetada como confundida con la estación y con el tamaño**.
* **C3 — DESCOMPOSICIÓN.** CORRECTED sobre las 40 comunes vs CORRECTED sobre las 77 nuevas.
  Aísla el efecto estacional **dentro de un solo dataset**, que es lo que permite leer C2.

---

## 4. Los tres casos que la regla de población decide, nombrados

**`2026‑05‑19` — dos escaleras reales el mismo día, y el desempate hace trabajo.**

    OLD        event 493651   close 2026‑05‑25 15:05:29Z   bandas  ≤12 · 13…21 · ≥22
    CORRECTED  event 503460   close 2026‑05‑20 01:23:18Z   bandas  ≤13 · 14…22 · ≥23   ← elegido

Las dos son particiones completas de 11 bandas, las dos `resolved`, **las dos con la misma
ganadora (18 °C)**, y están desplazadas un grado. `backfill_2b_v1` sólo contiene la primera;
`markets_v2` contiene las dos y la regla elige la que cierra **antes, por encima del día
civil local**. Es el único caso de las 40 fechas comunes en que los dos brazos puntúan
eventos distintos, y es un **duplicado económico real** — H6 — resuelto por la regla, no por
el nombre ni por la posición.

**`2026‑05‑20` — el único evento de EGLC que la regla excluye.** `event 496987`, 11 bandas,
pero `uma_resolution_status` vale `{proposed, resolved}` **dentro del mismo evento**: hay
mercados del mismo evento sin liquidar. La regla pide `resolved`, y `resolved` de todo el
evento. Se excluye, se cuenta y queda nombrado aquí. Tiene observación, así que cuesta un
día puntuable.

**`2026‑04‑16` y `2026‑04‑17` — fuera en LOS DOS brazos, y no por población.** Tienen
observación y no tienen pronóstico al lead 24. Es un hueco de `weather_forecasts`, idéntico
en ambos brazos, y por eso no rompe el aislamiento.

---

## 5. Lo que el partition test hace, y que hay que decir porque podría no haberlo hecho

De los 163 eventos de `backfill_2b_v1`, **122 no pasan**:

    1 banda   ·   5 eventos   ·  resolved
    3 bandas  · 117 eventos   ·  resolved
    11 bandas ·   1 evento    ·  no resolved

Los 117 de tres bandas son el rastro de `backfill_prices`, que se quedaba con los 3
`market_id` más bajos por fecha. **Una escalera truncada a tres bandas podría haber pasado
por partición** —un `or below`, un `or higher` y un entero en medio es formalmente una
partición— y habría metido en la muestra un contrato incompatible con los de once bandas,
que es justo lo que H4 teme. **No pasa ninguno**: el truncamiento por `market_id` más bajo
deja huecos entre los enteros, y `particion()` los rechaza por el `range` contiguo. Es un
resultado medido, no una garantía de diseño: si el truncamiento hubiera sido «los 3
consecutivos más bajos», los 117 habrían entrado.

**Y la consecuencia práctica: la población puntuable de los dos brazos es 100 % de once
bandas.** No hay mezcla de escaleras dentro de ninguna de las comparaciones C1, C2 ni C3.

---

## 6. Veredicto del punto 3

* La comparación *histórico vs reejecución* está **descartada**: siete elementos cambian.
* La comparación *reparada* tiene **todos los elementos metodológicos idénticos** y un solo
  tratamiento, `markets.dataset_version`.
* Pero el tratamiento **arrastra un cambio estacional de +9,57 °C en la media del objetivo**,
  así que la comparación completa (C2) **no es interpretable como efecto de la corrección**.
* La única comparación causalmente limpia es **C1, sobre las 40 fechas comunes**, y se
  declara **primaria** aquí, antes de verla.

