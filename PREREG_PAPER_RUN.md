# PREREGISTRO — Corrida de modo papel (R24) · **v3**

**Estado:** BORRADOR v3, **NO CONGELADO**. Por A-29.4 no se congela hasta pasar refutación hostil
sin bloqueantes abiertos.
**v1 REFUTADA** (2/2 refutadores, 25 hallazgos) → v2. **v2 REFUTADA** (3 bloqueantes: el fill no aplicaba
predicado as-of sobre el libro; el replay usaba un predicado distinto del ciclo que audita; y §0
invertía el signo del efecto de la correlación) → **v3**, que es esta.
**Fecha:** 2026-09-09 · **Autor:** Claude (sesión A) · **Pista:** A-31
**Host:** GitHub Actions (decisión del usuario, A-29.2) · **Código:** `feat/paper-actions` (PR #3)

> **Qué cambió de v1 a v2, en una línea cada uno.** (1) El criterio de éxito era **vacuamente
> satisfacible**: una corrida con cero operaciones cumplía los seis criterios y se declaraba APTA
> — corregido con §6.0. (2) `price_history`, de donde Strategy A lee el precio de mercado, **no la
> escribía nadie**: la corrida habría producido cero señales de forma determinista — corregido en
> el código. (3) El ritmo «5 op/día» de §0 estaba **inventado**; se sustituye por un techo
> **medido**. (4) La tabla de potencia usaba edge **bruto** bajo un documento que congela el modelo
> de costes de D19 — recomputada en neto. (5) §5 afirmaba que el retraso *acorta* el lead: con el
> clamp lo *alarga*, y la regla de deriva no podía dispararse. (6) El umbral de parada de 50 MB
> abortaba la corrida hacia el día 9.

---

## §0. Qué gobierna, y cómo se decidirá si el PnL puede ser criterio

Gobierna la corrida de N días que decide si el sistema está **listo para operar**, que aquí
significa exactamente una cosa: *que sólo falte el permiso explícito del usuario para levantar D0*.
No significa rentable.

**El techo del universo, MEDIDO (no supuesto).** v1 escribía «5 op/día» sin derivarlo de nada. El
número real se mide, y lo he medido sobre el universo en vivo del 2026-09-10 (ciclo real,
`ds_p5`, 2 páginas de gamma):

| magnitud | valor |
|---|---:|
| eventos de la fecha | 51 |
| tokens | 1 122 |
| tokens con book **de dos lados** (y por tanto con precio indicativo) | 888 (79 %) |
| **eventos con TODAS sus bandas cotizadas** | **7 (13,7 %)** |

Strategy A es *fail-closed a nivel de evento*: una sola banda sin precio excluye el evento entero
(`build_feature` → None → `missing_feature` → `event_ok = False`). Por tanto el techo no es el
bankroll (50 posiciones/día a tamaño completo) sino el universo: **≤ 7 eventos elegibles por ciclo,
≤ 14 por día, ≤ 294 decisiones de evento en 21 días** — y de ésas sólo operan las bandas que crucen
tau.

> **Hallazgo de primer orden, y no era el objeto de esta medición:** el 86 % de los eventos se cae
> por no tener las dos puntas cotizadas en todas sus bandas. Eso no es una limitación del
> preregistro, es una propiedad del venue, y afecta a la viabilidad de la estrategia mucho antes que
> cualquier cuestión de calibración. Queda declarado aquí y anotado para R21.

**La potencia, recomputada en NETO.** v1 tabulaba la ventaja bruta bajo un documento que en §4
congela el modelo de costes de D19; la fee por acción es del mismo orden que la ventaja, así que
ignorarla subestima `n` entre 1,4× y 7,1×. Con `media_neta = (q−p) − 0,05·p·(1−p)` por acción:

| `p` | ventaja bruta | ventaja **neta** | n bruta | **n NETA** | factor |
|---:|---:|---:|---:|---:|---:|
| 0,20 | 0,020 | 0,0120 | 1 716 | **4 767** | 2,8× |
| 0,20 | 0,030 | 0,0220 | 787 | **1 464** | 1,9× |
| 0,20 | 0,050 | 0,0420 | 300 | **425** | 1,4× |
| 0,35 | 0,030 | 0,0186 | 1 047 | **2 717** | 2,6× |
| 0,50 | 0,020 | 0,0075 | 2 496 | **17 749** | 7,1× |
| 0,50 | 0,030 | 0,0175 | 1 107 | **3 254** | 2,9× |
| 0,50 | 0,050 | 0,0375 | 396 | **704** | 1,8× |

`n = (2·√(q(1−q)) / media_por_acción)²`. **`n` es invariante al presupuesto**: el número de acciones
`C` se cancela en el cociente, de modo que ninguna decisión de sizing de §4 cambia estas cifras —
v1 presentaba columnas de acciones y sd que sugerían lo contrario y eran decorativas.

**Y aquí v2 se equivocó de signo, no sólo de unidad.** v2 escribía que las bandas de un evento
«no son seis observaciones, es una», dando a entender que agrupar bandas **destruye** potencia. Es al
revés. Si en un evento se abren `|S|` bandas de la partición con pago `X = Σ_j C(1{gana j} − p_j)`,
la covarianza entre bandas es **negativa** (gana exactamente una), luego `Var(X) = C²·Q(1−Q)` con
`Q = Σ q_j`, que es **menor** que `|S|` veces la varianza de una banda suelta, mientras la media es
`|S|` veces mayor. El caso extremo lo deja claro: comprar **toda** la partición da un pago
determinista `C·(1 − Σp_j)` — varianza **cero**. Agrupar bandas del mismo evento **aumenta** la
potencia por evento, no la reduce.

**Lo que sí reduce el número de observaciones, y v2 no vio:** el calendario de §5 decide **la misma
fecha objetivo dos veces** — a las 11:40Z de `D−1` con lead 24 h y a las 02:40Z de `D` con lead 9 h.
Mismos eventos, mismos mercados, **un solo sorteo**: qué banda gana en `D`. Los dos pagos están
perfectamente correlacionados. El techo de **desenlaces independientes** no es 294 sino
**≈ 21 fechas × 7 eventos ≈ 147**.

Hay entonces tres magnitudes distintas, y v2 las confundía en una:

| magnitud | valor |
|---|---:|
| (i) decisiones de evento por ciclo | ≤ 7 |
| (ii) decisiones de evento en la corrida (**no** independientes) | ≤ 294 |
| (iii) **desenlaces independientes** | **≈ 147** |

### La potencia NO se puede fijar aquí, y decirlo es el resultado

`n` depende de `|S|` —cuántas bandas por evento cruzan tau— y `|S|` depende de **tau**, que no
existe hasta R21 (P2). Con `|S|` grande la varianza por evento se desploma y hacen falta muchos menos
eventos; con `|S| = 1` la tabla de arriba vale tal cual, en unidades de **posición**, y el techo
relevante es (ii). No puedo elegir la fila sin conocer tau, y elegirla a ojo sería exactamente lo que
§10 prohíbe.

> **DECISIÓN, congelada ahora:** el **método** queda fijado aquí y el **número** se calcula cuando
> tau exista, **antes** de arrancar la corrida, como enmienda preregistrada y hasheada. La regla de
> decisión también queda fijada ahora, para que no dependa del resultado:
> - Si `n_requerido(tau) ≤ 147` → **el PnL SÍ es criterio**, y su umbral se declara en esa enmienda.
> - Si `n_requerido(tau) > 147` → el PnL **se reporta con su IC y no es criterio**, y la enmienda
>   escribe cuántos días harían falta.
>
> `n_requerido(tau)` se computa con `σ = √(Q(1−Q))`, `Q = Σ_j q_j` sobre las bandas efectivamente
> abiertas, y `μ = Σ_j (q_j − p_j − 0,05·p_j(1−p_j))`, medidos sobre un ciclo real previo a la
> corrida. La tabla de arriba se conserva **sólo** como cota para el caso `|S| = 1`.

**v1 afirmó que el PnL no podía ser criterio apoyándose en un ritmo inventado. v2 lo reafirmó
apoyándose en una correlación con el signo cambiado. v3 no lo afirma: fija cómo se decidirá y cuándo,
antes de ver un solo dato.** Las dos veces anteriores la conclusión blindaba el PnL contra toda
falsación, que es justo lo que un preregistro no debe hacer.

## §1. Símbolos y ancla temporal

Explícitos porque su ausencia fue el bloqueante nº 2 de la refutación de `PREREG_M2_ERROR.md`
(A-32) y una de las cuatro causas de retirada de mi propio preregistro de M2 (A-30).

- **`D`** — `target_date`. **Parámetro obligatorio del caller** (`--target-date`), por
  PHASE_2D_STRATEGY_A_DESIGN.md §C. En modo papel el caller es el planificador. Nunca se deriva del
  catálogo; la selección de qué mercados le pertenecen es un **filtro de universo** declarado (§3).
- **`T_end`** = `D 12:00:00Z` (R8, 8 557/8 557 eventos). Sólo deriva el lead; no es instante de
  decisión.
- **`T_asof`** = `T_end − lead_hours` — la as-of declarada.
- **`prediction_time`** = **`min(now, T_asof)`** — el instante de decisión que el código usa
  realmente (`paper_cycle.decision_time`). El clamp es lo que hace verdadera la afirmación de
  as-of: disparando pronto se decide con menos información; disparando tarde, un dato llegado
  durante el retraso no puede entrar en una decisión que dice ser as-of `T_asof`.
- **`lead_efectivo`** = `(T_end − prediction_time)/3600`. Por el clamp,
  **`lead_efectivo ≥ lead_hours` siempre**: el retraso NO lo acorta, y el disparo adelantado lo
  alarga. v1 afirmaba lo contrario.
- **`lead_hours` ∈ {9, 24}** (PREREG_LEAD_HOURS_RANGE).

**Columna as-of por tabla** (v1 exigía `available_at` en tablas que no la tienen):

| tabla | columna que gobierna la admisibilidad |
|---|---|
| `price_history` | `observation_time` (instante de NUESTRA captura del book) |
| `orderbook_snapshots` | `timestamp` = `collected_at` (ídem) |
| `weather_forecasts` | `available_at` |
| `markets` | `available_at` (sellado en el descubrimiento, R26) |
| `outcomes` | **no tiene columna as-of**: no figura en `AS_OF_COLUMNS` y sus únicas columnas temporales son `source_timestamp` e `ingestion_timestamp`, que `database.py` prohíbe usar como as-of. Su admisibilidad se hereda de su `markets` (v2 la agrupó con `markets` bajo `available_at` y repetía el error que decía corregir) |

---

## §2. Precondiciones — ninguna es opcional

La corrida **no empieza** mientras alguna falle. El informe declara la fecha en que cada una pasó.

| # | Precondición | Comprobación mecánica |
|---|---|---|
| P1 | **M2 produce cuantiles fiables**; los bloqueantes de A-32 resueltos y re-ejecutados | `weather_forecasts.forecast_p10..p90` no nulos para el universo de §3 **y** una entrada en `DECISIONS.md` que declare cerrados los bloqueantes de A-32, citando el sha del preregistro corregido |
| P2 | **`tau` fijado por calibración fuera de muestra (R21)** | el informe de R21 nombra `tau` y su procedimiento. **Si R21 no existe, la corrida no arranca**: no hay tau por defecto (§4) |
| P3 | **Etapa `forecasts` implementada.** Hoy `stage_forecasts` **no tiene ninguna rama OK** y no escribe nada; el cableado es pista de B | un ciclo manual deja `forecasts` en OK con `written > 0` |
| P4 | **Liquidación cableada** con la etiqueta real bajo el SettlementOperator del mercado | `settle` en OK con `positions_settled > 0` |
| P5 | **Colector con ≥ 7 días continuos previos**, definido como: para cada uno de los 7 días naturales anteriores existe ≥ 1 shard de `orderbook_snapshots` con ≥ 1 fila | `store.iter_shards` por fecha |
| **P6** | **`price_history` poblada por el propio ciclo** (el hueco que hacía la corrida estructuralmente estéril) | un ciclo manual deja `collect:books` con `prices > 0`, y `price_history` está en `LEDGER_TABLES` |
| **P7** | **Existe la herramienta de re-ejecución que C3 invoca** (`scripts/replay_cycle.py`): reconstruye la DuckDB desde los shards y re-evalúa cada decisión con el `prediction_time` y los parámetros registrados de ese ciclo | la herramienta existe y reproduce un ciclo de prueba al 100 % |

**P1–P4 no dependen de A.** Esta corrida no puede programarse por decisión unilateral: se declara la
precondición y se espera.

---

## §3. Universo

- Mercados descubiertos **ABIERTOS** (`discover(closed=False)`, R26) cuyo `endDate` cae en `D`,
  con `available_at` sellado en el instante del descubrimiento.
- **Filtro de universo, no derivación de `target_date`** (§C de 2D prohíbe derivar el *parámetro*,
  no filtrar *candidatos*; A-31).
- **Excluidos, declarado antes:** eventos que Strategy A excluye por sus propias puertas (partición
  de bandas, sumas fuera de tolerancia, **cualquier banda sin precio** — el 86 % medido en §0);
  mercados con `fee_status ≠ 'KNOWN'`; mercados sin `book_snapshot` en el ciclo.
- **NO se excluye por `rounding_rule`.** A-34 verificó que la rejilla de bandas de los 1 936
  mercados `tenths` es **entera** (`13°C or below … 23°C or higher`, cero bandas no enteras): lo que
  `tenths` describe es la precisión de la fuente, no la rejilla. Esos mercados caen igualmente, pero
  por **no tener identificador de estación** (los 1 936 tienen `station` NULL: Hong Kong 1 859 +
  Taipei 77), y quedan contados en `markets_excluded` con esa razón.

---

## §4. Parámetros congelados

| Parámetro | Valor | Origen |
|---|---|---|
| `bankroll` inicial | 10 000 USDC nocionales | `config.DEFAULTS` |
| `fixed_fraction` | 0,02 | `config.DEFAULTS` |
| `size_cap` | 0,02 | `config.DEFAULTS` |
| **presupuesto por posición** | **200 USDC en la PRIMERA**; decae como `200·(1−0,02)^k` mientras no haya liquidación que reponga bankroll | `paper.position_cash` sobre el bankroll corriente. v1 decía «200 USDC/posición» a secas, y era falso a partir de la segunda |
| **`tau_signal`** | **de R21 (P2)** — sin valor por defecto | umbral de Strategy A, sobre el edge **BRUTO** (`fair_value − p_market`) contra el mid indicativo |
| **`tau_exec`** | **de R21 (P2)**, declarado aparte | umbral de ejecución, sobre el edge **NETO** (tras fees, contra el VWAP alcanzable). v1 y v2 declaraban **un** `tau` con **un** origen, mientras el código lo aplicaba **dos veces sobre dos magnitudes distintas**: un umbral con dos operandos, la misma clase de defecto que A-32 le reprocha al `n ≥ 30` ajeno. Pueden tomar el mismo valor; que lo tomen es una **decisión declarada**, no una identidad |
| `exit_mode` | `hold_to_resolution` | D19: redención sin fee de venue |
| `x_exec` | **0,0 como principal**, y **dos variantes de estrés obligatorias: `0,5·tick` y `1 punto`** | D19 las declara obligatorias y v1 las omitía. Las variantes se computan **sobre las mismas decisiones registradas**, no re-operando |
| `price_layer` | `SIMULATED_EXECUTABLE` | R23 |
| `model` (M1) | `icon_seamless` | D12 |
| `rebate` de maker | 0, con la cota superior reportada aparte | D19 |

**Auditabilidad del congelado.** El workflow lee estos valores de variables de repositorio, que se
editan sin dejar traza. Por eso cada ciclo **escribe sus parámetros efectivos** en el almacén
(`stage_params` → shard `cycle_params`), en un registro append-only y fechado por commit. Un cambio
a mitad de corrida es entonces un diff visible, y §8.3 pasa a ser auditable en vez de declarativa.

---

## §5. Duración, calendario y deriva

- **N = 21 días naturales consecutivos**, desde el **primer ciclo de las 02:40Z** posterior al
  cumplimiento de las precondiciones (v1 dejaba el denominador ambiguo: según el ciclo de arranque
  salían 42 o 41).
- **Dos decisiones al día:** `40 11 * * *` (lead 24 h, `D` = mañana) y `40 2 * * *` (lead 9 h,
  `D` = hoy). **Denominador de la corrida: 42 ciclos.**
- **Deriva.** Por el clamp (§1) `lead_efectivo ∈ [lead_hours, lead_hours + 0,333 h]`, así que la
  regla de v1 («fuera de ±1 h») **era inalcanzable por construcción**. Se sustituye por una que sí
  puede dispararse y mide lo que importa: **`LATE_FIRING` si `drift_h > 0`** (el runner llegó
  después de `T_asof`, luego la decisión se tomó con información recortada al clamp y no con la
  información fresca que el lead permitía). `drift_h` se registra por ciclo y **sí varía**.
- Un día perdido **no se recupera** y cuenta contra C1.

---

## §6. Criterios — evaluabilidad primero, luego éxito

### §6.0 — Cláusula de NO VACUIDAD (el fallo que hundió v1)

Los criterios de v1 eran cuantificadores universales sobre conjuntos que pueden ser vacíos
(«100 % de las operaciones», «cobertura sobre las liquidadas»). Sobre el vacío **todos son
verdaderos**: una corrida que ejecutase los 42 ciclos sin abrir una sola posición cumplía los seis y
se declaraba **APTA**, es decir «lista para operar con dinero real». Eso es exactamente lo que la
corrida existe para descartar.

**La corrida es EVALUABLE sólo si alcanza los tres mínimos:**

| | mínimo | por qué ése |
|---|---:|---|
| **ciclos con veredicto registrado en el almacén** — NO sobre `markets_excluded`, cuya clave `(market_id, reason, dataset_version)` no lleva instante ni lead y colapsa en una fila los dos ciclos de la misma fecha: ese recuento **no es recuperable** de ahí, así que el resumen del ciclo (con su mapa `reasons`) se persiste como shard | **≥ 30 de 42** | es lo que el almacén sí puede reconstruir, y queda ligado a C1 y no al techo de eventos |
| posiciones **abiertas** | **≥ 30** | por debajo, C3 y C4 son casi vacíos |
| posiciones **liquidadas** | **≥ 20** | por debajo, C6 no puede pronunciarse ni siquiera sobre un fallo grosero |

**Si alguno falla → veredicto `NO EVALUABLE POR FALTA DE SUSTRATO`,** nombrando la cifra alcanzada.
**`NO EVALUABLE` no es `APTA`** y no autoriza nada. Es el veredicto por defecto, y hay que salir de
él con datos.

Estos tres mínimos son de **evaluabilidad mecánica** (¿hay bastantes filas para que C3/C4/C6 digan
algo?), **no de potencia estadística**. No se contradicen con §0: allí la unidad es el **evento** y
30 posiciones pueden ser muchas menos observaciones independientes, porque varias bandas del mismo
evento son una sola. Nada en §6 autoriza a leer 30 posiciones como 30 observaciones.

### §6.1 — Criterios de éxito

Con la corrida ya declarada evaluable, es **APTA** si y sólo si **los seis** se cumplen. Cualquier
fallo → **NO APTA**, con la causa nombrada. No hay categoría intermedia y no se renegocian tras ver
los datos.

| # | Criterio | Umbral | Comprobación |
|---|---|---|---|
| **C1** | **Continuidad.** Un ciclo cuenta como completado si **ninguna** de sus etapas quedó en STOPPED y dejó su shard `cycle_params` | **≥ 38 de 42** (90 %) y ningún hueco > 24 h (2 ciclos consecutivos) | shards `cycle_params` + resúmenes. v1 contaba commits, que no miden esto: el ciclo devuelve 0 aunque haya etapas paradas |
| **C2** | **Integridad as-of.** Filas usadas en una decisión cuya columna as-of (§1, por tabla) sea **posterior a `prediction_time`** | **exactamente 0**, sobre **≥ 30 posiciones** (§6.0) | auditoría sobre las filas persistidas. El clamp hace esto verdadero por construcción para el precio; el criterio **sí muerde** en `weather_forecasts.available_at` y en `markets.available_at`, que el clamp no gobierna |
| **C3** | **Reproducibilidad de la CAPA DE EJECUCIÓN.** `replay_cycle.py` (P7) reconstruye desde shards y re-deriva, para cada señal persistida, el libro admisible, el precio de fill, el tamaño y la fee, con el `prediction_time` y los parámetros **registrados** de ese ciclo. **NO recomputa la señal**: toma `signal` y `fair_value` como dados. Auditar la generación de señal exigiría re-derivar `p_weather` desde los cuantiles de M2, que es pista de B | **100 %** de las ≥ 30 operaciones | la herramienta de P7. v1 invocaba un instrumento inexistente; v2 lo creó pero afirmaba auditar «cada decisión», que es más de lo que hace |
| **C4** | **Coste aplicado.** Fills con fee del modelo de D19 y `fee_status='KNOWN'` | **100 %**; **0 fills con fee 0**, sin cláusula de escape — el régimen `fees_disabled` sólo existe para `endDate` < 2026-03-30 y en modo prospectivo no puede aparecer | `paper_trades.fees` frente al `cycle_params` y a `market_fee_schedule` vía `markets.fee_regime` |
| **C5** | **Coherencia con el backtest.** Tasa de eventos elegibles y reparto de razones de exclusión frente a R21 | ambas dentro de **±10 puntos porcentuales**. **Si R21 no publicó esas tasas, C5 se declara NO APLICABLE y la corrida NO puede ser APTA** — no se sustituye por un juicio | comparación tabulada |
| **C6** | **Calibración.** Fiabilidad de `p_model`: agrupadas las posiciones en deciles de `p_model`, la frecuencia observada de aciertos frente a la predicha | ningún decil con **\|observada − predicha\| > 0,40** con IC95 de Wilson que **excluya** esa diferencia | Wilson sobre ≥ 20 liquidadas. v1 hablaba de «cobertura de los intervalos de p_model», y `p_model` es un **escalar**, no un intervalo: era un error de categoría |

**C6 declara su límite por delante:** con ≥ 20 liquidadas el IC es ancho y el criterio es **fácil de
pasar**. Está para atrapar una calibración groseramente rota (de ahí el 0,40, no 0,05), que sí se
detecta con pocas observaciones. **No se presentará como evidencia de buena calibración.**

---

## §7. Se reporta, NO es criterio

- **PnL neto y bruto, con IC bootstrap**, y la frase explícita de que a N = 21 el resultado es
  compatible con cero (§0), **más** el `n` que habría hecho falta según la fila de la tabla que
  corresponda al `tau` realmente usado.
- **Las dos variantes de estrés de `x_exec`** (§4), recomputadas sobre las mismas decisiones.
- Operaciones **por día** y por ciclo, contra el techo medido de 14 (§0).
- Precios de fill frente al mid indicativo: cuánto cuesta el spread de verdad.
- Fees pagadas y cota superior del rebate de maker.
- Distribución de `lead_efectivo`, de `drift_h` y recuento de `LATE_FIRING`.
- Razones de rechazo del motor paper y de exclusión de Strategy A, con recuento.
- **Fracción de eventos caídos por banda sin cotizar** — la magnitud de §0, medida a lo largo de la
  corrida en vez de en un solo día.
- Tamaño del almacén y crecimiento diario.
- Incidencias de cuota: 429, ciclos parados, reanudaciones.

---

## §8. Reglas de parada

**Parada inmediata y corrida NULA:**

1. Cualquier indicio de ruta de dinero real: una clave, una firma, un endpoint de orden. Gate D0.
2. Una violación de C2.
3. Un cambio de cualquier parámetro de §4 durante la corrida, **detectado como diff entre shards
   `cycle_params`** (§4).
4. Escritura en `main` desde un workflow.

**Parada con corrida conservada y declarada corta:**

5. 429 sostenido que impida ≥ 3 ciclos consecutivos.
6. **Crecimiento del almacén > 200 MB.** v1 fijaba 50 MB sin cuenta alguna y **la corrida lo
   rebasaba hacia el día 9**, haciendo C1 inalcanzable: el volumen medido es ≈ 271 B/fila
   comprimida × ~20 200 filas/día ≈ **5,5 MB/día ≈ 115 MB en 21 días**, más ~10 MB de catálogo — un
   volcado diario: el workflow pasaba `--dump-catalogue` en **los dos** disparos (~21 MB), y se ha
   corregido en el código para que sólo lo pase el de las 11:40Z. El
   umbral se fija por encima del volumen previsto, no por debajo.
7. Petición del usuario.

---

## §9. Limitaciones declaradas ANTES

- **`SIMULATED_EXECUTABLE` no es un fill.** Se simula contra el book observado en el ciclo, que pudo
  cambiar entre la captura y `prediction_time`.
- **La escalera almacenada está truncada a 10 niveles.** Un fill que la agote se marca
  `book_exhausted` y se cuenta aparte; sesga a **menos** ejecución, nunca a más.
- **`minimum_order_size` es ambiguo** (5 acciones vs 5 USDC). Se exigen ambas: rechaza más de lo que
  el venue rechazaría.
- **El 86 % de los eventos no llega a evaluarse** por falta de cotización en dos puntas (§0). La
  corrida mide la estrategia sobre el 14 % que sí cotiza, que **no es una muestra aleatoria** del
  universo: son, presumiblemente, los mercados más líquidos.
- **Un solo `p_model`** (`p_weather`, Strategy A V1). Hereda las limitaciones de M2, incluida la
  disponibilidad de la etiqueta a 24 h, que sigue siendo un supuesto.
- **`neg_risk: true`** en estos mercados (OBSERVADO 2026-09-09) y **no se modela**.
- **Sin impacto de mercado:** nuestras órdenes no existen y no mueven el book.
- **`price_history` la escribe nuestro propio colector** desde el mid del book (P6). Es mejor
  procedencia que el endpoint `prices-history`, pero **no es el mismo dato** que usó el backtest de
  R21, que sí viene de ese endpoint. C5 compara dos poblaciones con fuentes de precio distintas, y
  eso se declara aquí en vez de descubrirse al comparar.

---

## §10. Integridad

- Se **congela y hashea antes del primer ciclo**; su sha se cita en `DECISIONS.md`. Un documento con
  bloqueantes abiertos **no se congela** (A-29.4).
- Ningún umbral de §6 se calcula ni se ajusta tras ver resultados.
- Si un criterio resulta mal especificado al ejecutar, la corrida se declara **NO APTA por
  especificación** y se rehace el preregistro. No se enmienda en caliente.
- La corrida **no toca dinero real en ningún caso**. Terminarla con éxito significa exactamente
  «sólo falta que el usuario levante D0», y levantarlo es decisión suya.
