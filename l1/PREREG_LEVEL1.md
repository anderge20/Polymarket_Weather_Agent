# LEVEL 1 — PREDICTIVE POWER · PREINSCRIPCIÓN

**Escrito y espejado ANTES de ejecutar L1.1.** Alcance exclusivamente histórico. Prohibidos y
no realizados: producción, settlement, ejecución, paper trading, PnL operativo, activación del
bot, selección de mercados, búsqueda de estrategias, optimización de umbrales y búsqueda de
edge económico. **`D0-P` permanece BLOCKED durante todo Level 1.**

**Objetivo único:** determinar si la información meteorológica disponible en `prediction_time`
tiene poder predictivo **fuera de muestra** sobre la probabilidad de que un contrato YES
resulte ganador.

---

## 1 · LOCK DEL DATASET

Salida íntegra en `L1_LOCK.txt` (guion `l1_lock.py`).

    timestamp de ejecucion   2026-09-13T20:15:45Z
    dataset_version markets  markets_v2
    dataset_version obs/fc   backfill_2b_v1   (la unica que existe)
    estacion                 EGLC
    git SHA repo             b523a8f31ad8f669737492dac771748266bd2861
    git SHA research         72dc0ad916bd901909947be88f46bb48f75546dd
    n075_poblacion.py        sha256 f4511b9623b6d23a…

    huellas sha256 de las filas que entran
      markets+outcomes   cda1dc07fe80a20be3d356e8f35cacbb61ba4d0f42bfbf5ccc78af42444dfef5
      observaciones      0eb8a2d8374d656b158d7acf734319c861ba37b417823110f2833c86a3d3c543
      pronosticos        c9093b50b6e48b0feb1129ebccd7835b8a4ffd71721abc301a308e32043d8f08

### Población — TODAS las definiciones, y la diferencia entre dos de ellas explicada

| definición | N |
|---|---|
| `population_total` — eventos EGLC en el almacén | **187** |
| mercados | 1 997 |
| eventos elegibles (resolved + partición completa + una ganadora) | 186 |
| fechas tras deduplicar `(station, target_date)` | **185** |
| **`population_with_observation`** — **a nivel EVENTO** | **137** |
| **`population_without_observation`** | **50** |
| `population_with_observation` — **a nivel FECHA, tras deduplicar** | **135** |
| con observación **y** pronóstico, lead 24 / lead 9 | **117 / 117** |

> **137 y 135 son las dos correctas y hay que dar las dos.** La diferencia son exactamente dos
> eventos, ambos con observación, nombrados:
>
>     2026-05-19  event 493651  11 bandas  elegible  -> lo descarta el DESEMPATE (hay dos
>                                                        eventos ese dia; gana 503460)
>     2026-05-20  event 496987  11 bandas  NO elegible -> uma = {proposed, resolved}
>
> `137 − 2 = 135`. **Los 50 sin observación no se eliminan en silencio:** son eventos válidos
> de **2025-12-31 → 2026-04-07**, fuera de la ventana en que existen observaciones
> (2026-04-08 → 2026-08-23). Toda métrica que necesite la etiqueta observada trabaja sobre 135,
> y las dos cifras se reportan juntas siempre.

### Escaleras

    elegibles          {7: 2, 9: 26, 11: 157}
    con observacion    {11: 135}
    con obs + FC       {11: 117}  en los dos leads

**Las escaleras de 7 y 9 aportan CERO eventos puntuables**: son de 2025-12-31 → 2026-03-15 y no
hay observación de EGLC antes del 2026-04-08. Se declara desde ya: **7 y 9 son insuficientes
para inferencia** y no se agregan con 11 (H4 = INVALIDADA, A-280).

### Estrato aceptado por settlement — se reporta, NO se usa como filtro

**17 eventos · 187 mercados**, terna `('WU','P_WU_DailyObservations')` (A-285). Los otros 170
eventos caen en estratos *fail-closed declarados* del núcleo. **Level 1 no filtra por esto**: el
target es `winning_outcome`, la resolución contractual almacenada, no nuestra liquidación.

---

## 2 · HIPÓTESIS

* **H0** — el pronóstico disponible en `prediction_time` **no** contiene poder predictivo
  adicional respecto a líneas base simples para determinar el contrato ganador.
* **H1** — sí lo contiene, **fuera de muestra**.

No se usa lenguaje de *edge*, *profit* ni *trading* en ninguna conclusión de Level 1.

---

## 3 · RIESGO `available_at`

    availability_assumption = issue_plus_4h45m36s
    LOOKAHEAD ASSUMPTION    = UNVERIFIED EXTERNALLY

**Demostrado:** el código no usa datos posteriores a `available_at` (D11, 0 violaciones en 236
pares). **No demostrado:** que el proveedor publicara con ese retardo exacto. La convención
**no se cambia retrospectivamente**; los resultados se reportan bajo ella.

**Estructura real, medida (no supuesta):** dos ejecuciones por `target_date`, **06z y 18z**,
ambas emitidas el día ANTERIOR al objetivo.

    lead 24   t_asof 12:00Z de td-1   -> elige la 06z de td-1   margen 1,24 h
    lead  9   t_asof 03:00Z de td     -> elige la 18z de td-1   margen 4,24 h

**Los dos leads usan ejecuciones DISTINTAS**, y la del lead 9 es una revisión posterior: no es
el mismo pronóstico leído dos veces. **Si aparece poder predictivo no se declarará definitivo
sin evaluar la sensibilidad a esta hipótesis** — en particular, el lead 24 tiene sólo 1,24 h de
margen. Validación operacional: tarea #75.

---

## 4 · UNIDAD DE ANÁLISIS

* **PRIMARIA: `event × lead`.** Cada par es una previsión disponible independientemente: los dos
  leads usan ejecuciones distintas emitidas en momentos distintos con información distinta. Los
  leads **se reportan por separado y nunca se agregan entre sí**.
* **Secundaria: evento.** Un sorteo, una observación. Es la unidad honesta para contar `N`.
* **Secundaria: contrato.** Es la unidad en que el mercado existe, y **no** es una observación
  independiente: las `n` bandas de un evento cumplen `Σ y = 1` por construcción.

**Pseudorreplicación explícitamente evitada:** tratar los contratos como independientes
multiplica `N` por `n` y da más peso a las escaleras largas. **El remuestreo estadístico se hace
por EVENTO** (§14).

**Se reportan las tres siempre.** No se elige después de ver el resultado.

---

## 5 · TARGET

`markets.winning_outcome = 'Yes'` — **el contrato YES ganó según la resolución contractual
almacenada**. Prohibido y verificado ausente (D11): `is_winner`, `outcome_index`, cualquier
observación para construir el target, y el proxy IEM como sustituto.

La observación entra **sólo** como feature o como variable de evaluación meteorológica.

---

## 6 · L1.1 — FORECAST SKILL (antes de convertir nada en probabilidad)

Sobre pares `(pronóstico, observación)` válidos, con **`tmax_observed` (Celsius)** contra
`forecast_tmax` (Celsius) — **nunca `observed_value`**, que es la rejilla del mercado (A-283):

bias · MAE · RMSE · error absoluto mediano · distribución de errores · error por lead · por mes
· por rango de temperatura · cobertura p10/p90 · anchura p10-p90 · estabilidad de las revisiones
(06z → 18z).

**No se entrena ningún modelo en esta fase.**

---

## 7 · LOS CINCO BASELINES, DEFINIDOS EX ANTE

Todos usan **exclusivamente** información con `label_av(d) ≤ t_asof`.

| id | definición |
|---|---|
| **B0** climatología | frecuencia histórica de cada banda con las últimas 30 etiquetas disponibles |
| **B1** persistencia | última etiqueta **disponible** en `t_asof`; indicador sobre la banda que la contiene |
| **B2** forecast crudo | indicador sobre la banda que contiene `round(f)` |
| **B3** forecast corregido de sesgo | indicador sobre la banda que contiene `round(f − sesgo)`, sesgo = media de los errores del train |
| **B4** forecast probabilístico | masa empírica: fracción de `round(f − sesgo + e)` que cae en cada banda, con `e` los errores del train |

**Variante declarada ANTES de correr, para que no parezca elegida después:** `B4'` = igual que
B4 **sin** corrección de sesgo (era `B3_fc_error` en la preinscripción de `n1_14`). Se reporta
siempre; no sustituye a ninguna.

**No se introduce ningún modelo adicional** hasta que alguno de éstos muestre señal. Los
cuantiles del proveedor (`forecast_p10…p90`, poblados en 230 de 236) **no se usan en Level 1**:
serían un sexto modelo.

---

## 8 · FORECAST → P(YES)

Para cada `prediction_time`: tomar el pronóstico disponible, obtener la distribución predictiva,
integrarla sobre cada intervalo contractual y obtener `P(contrato_i gana | información en
prediction_time)`. Las probabilidades deben estar en `[0,1]`, **sumar 1 dentro del evento**,
usar sólo información anterior y respetar unidad y escalera contractual. **Nunca se calibra una
observación con su propio resultado.**

---

## 9 · CALIBRACIÓN

Brier · Log Loss · diagrama de fiabilidad · intercepto y pendiente de calibración · sharpness ·
ECE **sólo como secundaria**.

**Estratificación obligatoria por escalera (7 / 9 / 11), con el nulo de cada estrato**
`(n−1)/n²` y `[ln n + (n−1)ln(n/(n−1))]/n`. **Prohibido agregar entre escaleras.** Ya declarado:
7 y 9 tienen 0 eventos puntuables → **insuficientes para inferencia**.

---

## 10 · RANKING, SEPARADO DE CALIBRACIÓN

*Calibración*: ¿son correctas las probabilidades? *Ranking*: ¿el ganador recibe más probabilidad
que los demás **dentro de su evento**? Se evalúan por separado y **un ranking fuerte con
calibración débil se documenta como tal**, no como éxito.

---

## 11 · WALK-FORWARD

**Obligatorio, ventana expansiva, sin train/test aleatorio.** Bloques temporales consecutivos;
todo lo aprendido —climatología, corrección de sesgo, distribución de error, calibración,
cualquier hiperparámetro— sale **exclusivamente** del train anterior al bloque de test.

Bloques declarados **antes de ver resultados**: **mensuales** sobre la ventana puntuable
(2026-04 → 2026-08), con mínimo de 20 pares de entrenamiento (el mismo que ya usa el corpus).

---

## 12 · REVISIONES

Leads por separado. Registrado en §3: `issue_time → available_at → prediction_time` con las dos
ejecuciones (06z, 18z) y la demostración de que **cada lead usa una revisión distinta y nueva**
en el momento en que la usa.

---

## 13 · INFORMACIÓN DE MERCADO

**No se usa en L1.1–L1.5.** Orden declarado: *weather-only* → *market-only* → *weather+market*,
para medir información **incremental**. Ninguna combinación se elige por su resultado ni se
reprueba retrospectivamente.

---

## 14 · TEST ESTADÍSTICO

Bootstrap **por evento** (cluster), IC 95 %, test temporal, placebo, comparación contra baseline
y análisis de potencia. **Los contratos de un mismo evento nunca se remuestrean como
independientes.** Semilla declarada: **20260913**.

---

## 15 · PLACEBO

Al menos: **placebo temporal** (desalinear pronóstico y target conservando la estructura
temporal) y **permutación dentro del evento**. Número de placebos **declarado de antemano** — no
se ejecutan hasta encontrar uno que falle.

---

## 16 · MULTIPLE TESTING

**Registro de variantes**: todo lo que se pruebe queda anotado antes de usarse para concluir.
Registro abierto en este documento: los cinco baselines, `B4'`, dos leads, tres unidades. Nada
más está autorizado sin añadirlo aquí primero.

---

## 17 · CRITERIOS DE VEREDICTO

* **A — NO PREDICTIVE POWER**: sin evidencia robusta de mejora OOS sobre los baselines.
* **B — PREDICTIVE POWER**: mejora OOS consistente y defendible estadísticamente.
* **C — STRONG**: consistente en varios periodos, frente a baselines, con calibración y ranking
  coherentes, resistente a placebo, IC compatible con mejora y **sin depender de una sola
  escalera o periodo**.
* **D — INCONCLUSIVE**: datos o potencia insuficientes para distinguir A de B.

---

## 18 · PODER PREDICTIVO ≠ EDGE ECONÓMICO

Son dos gates distintos. Precio, ejecución, spread, slippage, fees, liquidez, sizing, EV y PnL
**no forman parte de Level 1** y no se calculan.

---

## 19 · RED TEAM OBLIGATORIO antes del veredicto

look-ahead · leakage · estacionalidad · efectos de escalera · dependencia intra-evento ·
calibración sobre el propio test · selección post-hoc · revisiones · target leakage · múltiples
comparaciones. **Si aparece un defecto: `LEVEL 1 = BLOCKED` hasta resolverlo.**

---

## 20 · ORDEN DE EJECUCIÓN

`L1.1` forecast skill → `L1.2` baselines → `L1.3` forecast→probabilidad → `L1.4` walk-forward
OOS → `L1.5` calibración + ranking → `L1.6` inferencia → `L1.7` red-team → `L1.8` veredicto.

**Parada tras cada etapa si aparece un defecto metodológico. No se optimiza después de ver
resultados. No se introducen modelos nuevos para rescatar resultados negativos.**
