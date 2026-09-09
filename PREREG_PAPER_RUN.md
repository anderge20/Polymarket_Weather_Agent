# PREREGISTRO — Corrida de modo papel (R24) · **v4**

**Estado:** BORRADOR v4, **NO CONGELADO**. Por A-29.4 no se congela hasta pasar refutación hostil
sin bloqueantes abiertos.
**v1 REFUTADA** (2/2 refutadores, 25 hallazgos) → v2. **v2 REFUTADA** (3 bloqueantes: el fill no aplicaba
predicado as-of sobre el libro; el replay usaba un predicado distinto del ciclo que audita; y §0
invertía el signo del efecto de la correlación) → **v3**, que es esta.
**v3 → v4 (2026-09-09):** los cuantiles de M2 dejan de ajustarse dentro del ciclo y pasan a ser un
**artefacto versionado** (R30/A-55). Eso crea un parámetro congelable que v3 no contemplaba y una
pregunta que **hay que responder antes de la corrida, no después**: si el artefacto se reajusta a
mitad, ¿sigue siendo una sola corrida? §4bis la responde congelando la REGLA, no el valor.
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

> ### AVISO ANTEPUESTO, 2026-09-09: R21 MIDIÓ LA ESTRATEGIA Y NO ES OPERABLE
>
> Este preregistro se escribió esperando que R21 entregara un `tau`. **R21 se ejecutó y el
> veredicto, preregistrado por adelantado y publicado tal cual, es NO OPERABLE:**
>
>     candidatos 10 000 · pasan ejecución 1 139 · tomadas 468
>     §4.1 n>=100        CUMPLE   ← EVALUABLE, no vacío
>     §4.2 mediana>0     FALLA    −0,0236 por operación
>     §4.3 LOO estación  FALLA    negativa en las 47
>     §4.4 sin mes mayor FALLA    −0,0184
>     sensibilidad: con x_exec = 0 sigue en −0,0131 · H2 −0,0253 · H3 −0,0258
>     acierto 0,0556 frente a una tasa base de 0,0744
>
> **No existe umbral operable.** El walk-forward eligió el techo de la rejilla congelada
> (`tau_signal` = 0,20, máximo de §3) en **239 de 271 decisiones** y aun así perdió; y ni con
> ejecución gratuita cambia el signo, de modo que el resultado **no** es un artefacto del supuesto
> adverso de deslizamiento.
>
> **Y la causa NO es que el modelo esté roto.** Medida la calibración sobre los 10 000 candidatos —no
> sólo sobre lo tomado, que es donde la primera lectura se equivocó— `p_model` está **bien
> calibrada** (razón real/predicha 1,0–1,4× en todos los cubos por encima de 0,1). Brier:
> **`p_model` 0,05191 · mercado 0,04215 · tasa base 0,06801**. Los dos baten a la base —el modelo
> **tiene** habilidad— pero **el mercado tiene más**. Y de ahí sale todo:
>
> > La regla opera **donde `p_model` más se separa de `p_mid`**. Si el mercado está mejor calibrado
> > que el modelo, el sitio donde más discrepan es el sitio **donde el modelo se equivoca**. El
> > «edge» que la estrategia mide es, sistemáticamente, **su propio error**.
>
> Selección adversa contra una contraparte mejor informada. Explica el factor 22 en el cubo
> `[0,2 · 0,3)` (0,2215 sobre todos los candidatos frente a 0,010 sobre los tomados), explica el
> acierto por debajo del azar, y explica por qué **ningún umbral lo arregla**: subir `tau` aprieta con
> más fuerza sobre el mismo criterio equivocado.
>
> **Y R22 lo cierra midiendo dónde, si en algún sitio, el modelo bate al mercado.** Ocho ejes
> declarados antes de mirar, 1.308 eventos, 17 celdas evaluables: **ninguna favorece al modelo**, y en
> quince el `|Δ|` supera `2·SE` de la propia celda. La permutación sobre el máximo ni siquiera tuvo
> trabajo — el mejor Δ ya era negativo. *(Cobertura honesta: **diez** celdas estratifican de verdad;
> `completitud` degenera en una sola celda que es la muestra entera, el eje de precio pone el 79 % de
> las filas en un bin, la estación sólo llega a mínimo en EGLC y ahí es **no concluyente**, y los ejes
> de spread y antigüedad **no son evaluables** — `orderbook_snapshots` está vacía y `discovered_at` es
> NULL en 10.000 de 10.000.)*
>
> **Y dentro de los datos de R22 está la descomposición que lo explica todo.** El BSS del modelo
> contra la tasa base **de cada bin de precio**:
>
>     precio_decil 0  −0,547 · 1  −0,117 · 2  −0,023 · 3  −0,091 · 4  −0,234
>     muestra entera  +0,238
>
> **Dentro de cualquier régimen de precio el modelo es PEOR que predecir la tasa base de ese régimen.
> Su habilidad global positiva es enteramente un efecto ENTRE bins.** Lo único que aporta es «las
> bandas baratas son improbables», y eso el mercado ya lo tiene en el precio **porque el precio es el
> bin**. No es que el modelo sea algo peor que el mercado: **condicionado al precio no aporta
> información, y la que parecía aportar era la que el precio ya contenía.**
>
> **Es un problema de DISEÑO, no de estimación.** «Opera donde más discrepas del mercado» sólo
> funciona si eres mejor que el mercado. Haría falta un criterio que identifique **dónde** el modelo
> supera al mercado, no **cuánto** discrepa de él, y ese criterio no existe todavía.
>
> **QUÉ SIGNIFICA ESTO PARA ESTA CORRIDA, declarado ANTES de arrancar.** La corrida es **prueba de la
> CADENA y, además, el ÚNICO test PROSPECTIVO fuera de muestra del proyecto.** *(Corregido el
> 2026-09-09 a instancias de la sesión B: una redacción anterior decía «no prueba la estrategia», y
> **eso es falso por defecto**.)* Un ciclo en vivo abrió **27 posiciones**; a dos ciclos diarios
> durante 21 días son del orden de **mil posiciones**, más del doble de las 468 de R21 y sobre datos
> que R21 no puede tener: **prospectivos**.
>
> **Con un matiz que cambia el peso y que no está en el recuento de posiciones.** Esas ~1.000
> posiciones salen de unos ~7 eventos elegibles por ciclo × 42 ciclos ≈ **294 decisiones de evento**,
> y el evento es la unidad: sus bandas son una partición que suma 1 y sus errores están acoplados.
> Contra los **211 bloques de evento** de R21 eso no es «el doble de evidencia», es **~1,4×**. El
> techo de 294 ya estaba medido en §0 como propiedad del venue. **Se dobla el número de posiciones y
> se multiplica por 1,4 la muestra efectiva**, y cualquier intervalo se calcula por bloques de evento
> (la corrección que la sesión A planteó contra R21 y que allí ensanchó el intervalo a
> [−0,0288 · −0,0205] sin cambiar el signo).
>
> **Y HAY DOS PREGUNTAS QUE SÓLO ESTA CORRIDA PUEDE CONTESTAR**, porque su sustrato no se recupera
> hacia atrás. Verificado en el almacén prospectivo el 2026-09-09: los shards de
> `orderbook_snapshots` llevan `best_bid`, `best_ask`, `spread`, `mid`, `imbalance` y profundidad a 1,
> 5 y 10 niveles, con la escalera completa y su bandera de truncamiento.
> 1. **R21 tuvo que SUPONER el deslizamiento.** No había libro histórico —tabla vacía, los 16.165.636
>    precios `MIDPOINT_ESTIMATED`— así que `x_exec` se fijó en el peldaño más adverso de D19 **por
>    disciplina, no por medida**. Aquí se recorre el libro de verdad: el precio alcanzable deja de ser
>    un supuesto, y **cuánto se equivocaba el supuesto es un resultado en sí mismo**.
> 2. **R22 no pudo evaluar el eje de SPREAD** — el que la propia hipótesis señalaba como el más
>    informativo, y cuya ausencia quedó declarada como *«la rama negativa es más débil de lo que podría
>    haber sido»*. **Aquí sí hay spread.**
>
> Por eso **cada ranura de libro perdida es una de esas dos respuestas que no se podrá dar**, y por eso
> la fiabilidad del host (§5) no es una molestia operativa sino una pérdida de evidencia.
>
> **No se espera beneficio**, y decirlo ahora es lo que hace informativo cualquier resultado: si la
> corrida arrancara prometiendo PnL y diera cero, el resultado sería ambiguo entre «la cadena falla» y
> «la estrategia no vale». Declarado así, cada cosa se lee por separado — y el PnL se lee bajo §6bis,
> que se congela **antes** de que exista `PAPER_TAU`.
>
> **Lo que NO se hace:** no se amplía la rejilla de `tau`, no se toca el margen, no se cambia el
> constructor de colas y no se prueba otra regla de selección **hasta publicar por qué falló ésta**.
> Cualquiera de esas cosas después de ver el resultado es elegir el criterio a posteriori, que es lo
> que este documento existe para impedir. Una R21.2 necesita su propio preregistro.
>
> **Y la decisión de gastar 21 días en validar una cadena cuya señal ya se sabe negativa NO es de las
> sesiones: es del usuario.** Se le plantea con estos números delante.

Gobierna la corrida de N días que decide si el sistema está **listo para operar**, que aquí
significa exactamente una cosa: *que sólo falte el permiso explícito del usuario para levantar D0*.
No significa rentable — y desde R21 se sabe, medido, que **no lo es**.

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
| **P8** | **El artefacto de cuantiles existe, y la INESTABILIDAD del estimador está medida y declarada** (R30). *(revisada 2026-09-09, ver §4bis.8: la redacción anterior exigía derivar `max_age_hours` de una tasa de deriva, y esa tasa no existe.)* No basta con que el fichero esté: hay que citar la medida del movimiento de los cuantiles entre reajustes, **para los dos leads**, y decir con qué base se fija `max_age_hours` | un ciclo manual deja `forecasts` en OK con `quantiles > 0`, `quantile_artifact_id` no nulo y `quantile_artifact_age_h` dentro del límite, **y** `DECISIONS.md` cita la medida de movimiento por lead y la base declarada de `max_age_hours` |
| P2 | **`tau` fijado por calibración fuera de muestra (R21)** | el informe de R21 nombra `tau` y su procedimiento. **Si R21 no existe, la corrida no arranca**: no hay tau por defecto (§4) |
| P3 | **Etapa `forecasts` implementada.** Hoy `stage_forecasts` **no tiene ninguna rama OK** y no escribe nada; el cableado es pista de B | un ciclo manual deja `forecasts` en OK con `written > 0` |
| P4 | **Liquidación cableada** con la etiqueta real bajo el SettlementOperator del mercado. *(revisada 2026-09-09, A-60: se había dado por cerrada contra un FIXTURE. El único sitio donde `metar_body_c` —la serie que el núcleo congelado exige— había aparecido fuera del núcleo era un test de este repo, así que la liquidación no había tocado nunca una fila producida por ningún ingestor.)* | `settle` en OK con `settled > 0` **sobre una observación ingerida por `stage_observations` en el propio ciclo**, no sembrada por un test. Se cita el `paper_trade_id`, la estación, el día y el valor observado |
| **P9** | **La etiqueta la ingiere el ciclo** (`stage_observations`). Sin esto `settle` no lee nada: `weather_observations` la puebla el backfill bajo OTRO `dataset_version` y las fechas objetivo están en el futuro cuando se abre la posición, así que **toda posición quedaría abierta los 21 días y el libro reportaría PnL cero por no haber resuelto nada, no por no haber ganado nada** | un ciclo manual deja `observations` en OK con `ingested > 0`, y la fila lleva `available_at` = instante de descarga (D17) |
| **P12** | **El criterio de lectura del PnL está congelado ANTES de que exista `vars.PAPER_TAU`** (§6bis y la enmienda de §0). Poner la variable **es** lo que hace operativos los ciclos, así que el orden no es una recomendación: una tau puesta antes del criterio invalida la corrida igual que un cambio de parámetro a mitad | `DECISIONS.md` cita el sha de la enmienda y su fecha es anterior a la creación de la variable |
| **P11** | **La ruta de decisión completa ha corrido AL MENOS UNA VEZ EN EL HOST**, no sólo en una máquina de desarrollo. Medido en el almacén real el 2026-09-09: `weather_forecasts` **0 shards**, `signals` **0**, `paper_trades` **0** — todos los ciclos programados corrieron `--collect-only` porque `vars.PAPER_TAU` no está puesta, que es el fallo cerrado correcto **y significa que forecasts → signals → paper → observations → settle nunca se ha ejecutado en Actions.** Está verificado de extremo a extremo, pero en el Mac, y el día entero ha consistido en descubrir que verificar donde no corre no es verificar | un ciclo de decisión en Actions deja `forecasts`, `signals` y `paper_trades` con shards, y su `replay` da REPRODUCIBLE. **No se hace escribiendo en `ds_paper_v1`**: el `dataset_version` está fijado en el workflow y un ciclo de prueba contaminaría el libro de la corrida preregistrada. Requiere un `dataset_version` de ensayo, y por tanto un cambio de workflow ANTES de arrancar |
| **P10** | **La correspondencia de series está declarada para la población que va a operar.** *(CERRADA 2026-09-09 por evidencia del audit, A-61.)* `IEM_ASOS_METAR_1C → metar_body_c` y `IEM_ASOS_TMPF_1F → metar_tgroup_tmpf`; sobre las 14 filas en °F del audit sólo `H_LOCAL_tmpf` cae dentro de la banda ganadora, **14/14 y en grados enteros**, frente a 0/14 de las otras tres columnas. `IEM_ASOS_TMPF_0.1F` queda sin declarar y **no cuesta ningún mercado**: su única estación es KBKF, cuyo estrato (9, `P_NOAA_HourlyData`) el núcleo ya cierra por `series_filter_unverified` | el test fija las dos correspondencias contra `observations`, no contra literales |
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

| **`quantile_artifact_id`** | **el sha del artefacto vigente**, fijado al arrancar la corrida | R30. Es un sha del contenido canónico: dos ajustes con los mismos números tienen el mismo id, y un cuantil retocado a mano cambia el id y se rechaza |
| **`max_artifact_age_h`** del ciclo | **igual a la del artefacto**, o menor | R30. La línea de comandos sólo puede ENDURECER; un valor mayor se ignora |
| **`max_age_hours`** del artefacto | **120 h**, base operativa | §4bis.9. NO acota la estabilidad numérica: §4bis.8 |
| **cadencia de reajuste** | **48 h**, terminando antes de las 03:00Z | §4bis.7 y §4bis.9 |

**Auditabilidad del congelado.** El workflow lee estos valores de variables de repositorio, que se
editan sin dejar traza. Por eso cada ciclo **escribe sus parámetros efectivos** en el almacén
(`stage_params` → shard `cycle_params`), en un registro append-only y fechado por commit. Un cambio
a mitad de corrida es entonces un diff visible, y §8.3 pasa a ser auditable en vez de declarativa.

---

## §4bis. El reajuste del artefacto a mitad de corrida

El artefacto de cuantiles (R30) es un parámetro de §4, y §8.3 anula la corrida si un parámetro de §4
cambia durante ella. Pero un artefacto **tiene** que envejecer: pasada su `max_age_hours` el ciclo se
niega y deja de producir señales, así que «no reajustar nunca» no es una opción neutra — es elegir
que la corrida se apague sola. La pregunta se responde **aquí y ahora**, antes de ver un solo
resultado.

**Se congela la REGLA, no el valor** (mismo patrón que §0 con el PnL):

1. **El reajuste está PERMITIDO y programado**, no improvisado. La cadencia se declara antes de
   arrancar, en horas, y **sale de la medida de deriva de P8**, no de la comodidad. Una vez
   arrancada la corrida la cadencia no se toca.
2. **Un reajuste fuera de esa cadencia anula la corrida** (§8.3, punto 3). Reajustar porque los
   resultados no gustan es cambiar un parámetro después de ver resultados.
3. **Cada reajuste usa sólo lo disponible en su instante de ajuste.** Lo garantiza el código, no la
   buena intención: `fit_instant` es un corte sobre `label_available_at`, y el ciclo **se niega** si
   `fit_instant > prediction_time` (fuga) o si la antigüedad supera el límite (rancio).
4. **Un reajuste NO segmenta la corrida.** Los criterios de §6 se evalúan sobre los 42 ciclos
   completos. Declararlo ahora es lo que impide elegir después el corte que más favorezca: cada
   ciclo registra su `quantile_artifact_id`, así que **una partición por artefacto es computable a
   posteriori y por eso mismo no es criterio** — se reporta en §7, nunca decide.
5. **Un reajuste que empeore el ajuste no se publica.** El ajustador se niega ante un estrato
   perdido, un `POOLED` que pasa a `INSUFFICIENT` o una `n` menor, salvo `--allow-regression`
   explícito, que en corrida **no se usa**: usarlo es el punto 2.
6. **Ciclos perdidos por artefacto rancio cuentan contra C1**, como cualquier otro ciclo perdido.
   No hay categoría de excusa: si la cadencia se eligió mal, el coste se ve.

7. **La ventana de reajuste no es «cuando dé tiempo»: es ANTES DEL ANCLA.** Como
   `prediction_time = min(now, T_asof)` (§1), un artefacto ajustado después de `T_asof` cae en la
   negativa por fuga aunque se haya ajustado «antes del ciclo». En la práctica: el reajuste debe
   **terminar antes de las 12:00Z** para el ciclo de lead 24 h y **antes de las 03:00Z** para el de
   lead 9 h. No es una recomendación: verificado en vivo, la primera ejecución con un artefacto
   ajustado a las 12:39Z fue rechazada por un ciclo cuyo `prediction_time` era 12:00Z.

8. **`max_age_hours` es frescura OPERATIVA y NO acota la estabilidad numérica. Y esto es un
   resultado medido, no una renuncia.** La versión anterior de §4bis y de P8 daba por hecho que el
   número saldría de una tasa de deriva. **Esa tasa no existe.** Medido por la sesión B sobre los dos
   leads, |q(d) − q(d−Δ)| máximo sobre los cinco cuantiles:

       lead  Δ(días)   n    p50     p95     MÁX
          9        1  134  0,011   0,100   0,236
          9        4  130  0,050   0,206   0,268
          9       14  125  0,100   0,400   0,480
         24        1  134  0,010   0,100   0,393
         24        4  130  0,050   0,200   0,350
         24        7  129  0,100   0,250   0,313
         24       14  125  0,100   0,393   0,561

   Los cuantiles **no derivan: saltan**, en escalones de 0,1 °C, porque el dato subyacente está
   cuantizado y el percentil empírico cruza puntos discretos. Dividir un escalón por días inventa una
   tasa que no existe y con la que se puede «derivar» cualquier cifra eligiendo el intervalo.
   **El MÁXIMO no crece con Δ** (lead 24: 0,393 a un día, 0,313 a siete): firma de escalón, no de
   deriva. Reajustar más a menudo **no acota el peor caso**.
   Lo que sí controla la antigüedad es el **grueso** del movimiento —a lead 24 la mediana pasa de
   0,010 a 0,100 entre Δ=1 y Δ=14, factor 10, y el p95 de 0,100 a 0,393— y ése es todo el beneficio
   que un reajuste frecuente compra. No es el que se pretendía comprar, y se declara como es.
   **Elegir ahora el estadístico (máximo, p95 o mediana) que hiciera pasar un umbral sería escoger
   el criterio después de ver los resultados**, que es justo lo que este documento prohíbe. Por eso
   no se deriva ningún número de esta tabla: se declara la base y se reporta la medida.

9. **Los valores, fijados sobre base operativa y con la aritmética explícita:** cadencia de reajuste
   **48 h**, `max_age_hours` **120 h**. La vida útil debe ser **≥ 2 × cadencia** para sobrevivir a
   un reajuste perdido: con cadencia 48 y vida 84 —la primera propuesta— un reajuste fallido deja el
   siguiente en t+96 mientras el artefacto expira en t+84, y **doce horas de ciclos se niegan**.
   120 h da 24 h de margen sobre el mínimo. Es una decisión de operación, no de modelo, y se declara
   como tal.

10. **La inestabilidad medida, con el estadístico que corresponde a cada pregunta.** *(corregido
    2026-09-09: la primera redacción comparaba un MÁXIMO de valores absolutos con una dispersión, que
    son cosas distintas.)*
    - **Como dispersión**, que es lo que entra en cuadratura con `tau`: desplazamiento **signado** de
      la mediana a Δ = 5 días —justo la `max_age_hours` fijada— **σ_inst = 0,0373 °C** (lead 9) y
      **0,0548 °C** (lead 24). Contra `τ_est = 0,545` mueve el margen un **0,5 %**. Es pequeño, y el
      motivo importa: M2 v2 **agrupa entre estaciones**, así que su localización se estima con ~2.000
      pares y cinco días apenas la mueven. **La estabilidad es una propiedad de v2 por ser agrupado,
      no del fenómeno**, y NO se transporta a un M2 por estación.
    - **Como peor caso de una decisión concreta**, que es otra pregunta y no desaparece: el máximo
      observado entre dos ajustes consecutivos llega a **0,39 °C**, el 70 % de la rejilla fina. Una
      decisión individual puede verlo.
    `tau_exec` cubre la dispersión; el peor caso queda declarado en §9 junto a la descalibración por
    estación de B-12.

11. **El reajuste necesita un HOST, y hoy no lo tiene. Punto abierto, y la decisión no es mía.**
    El ajuste lee `data/pmw.duckdb` —el sustrato de entrenamiento, 578 MB— que **no existe dentro de
    GitHub Actions**: el ciclo reconstruye allí su DuckDB desde los shards prospectivos, que no
    contienen ni una observación histórica. Así que el reajuste cada 48 h sólo puede correr donde
    vive esa base, y hoy eso es **el Mac**.
    Y hay una consecuencia que conviene decir sin adornos: **si nadie extiende el sustrato, reajustar
    no cambia nada salvo el `fit_instant`.** El artefacto se ajusta sobre el backfill; si el backfill
    no crece, el reajuste produce los mismos cuantiles con una fecha nueva — frescura de sello, no de
    contenido. Un reajuste con ese efecto es teatro, y el preregistro no debe programar teatro.
    Por tanto el trabajo de reajuste son **dos pasos, no uno**: extender el backfill con los días
    cerrados desde el reajuste anterior, y después ajustar. Ambos en la máquina que tiene la base.
    **El orden de hosts (Actions → Hetzner → Mac) es decisión del usuario (A-29.2), así que esto se
    le plantea y no se resuelve por dentro.** Mientras no haya host asignado, la corrida no puede
    declarar que cumple la cadencia de §4bis.9, y decirlo aquí es preferible a arrancar y descubrirlo
    el tercer día.

**Lo que este preregistro sigue SIN poder fijar:** `tau` (P2). Sigue siendo hueco explícito: **si la
calibración de R21 no existe, la corrida no arranca**; no hay `tau` por defecto.

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
- **COLA DE LIQUIDACIÓN: dos días más, y no cuentan como ciclos de decisión.** Una posición abierta el
  día N se liquida cuando termina el día local de su objetivo, que es el día N+1 como pronto; y la
  etiqueta la ingiere el ciclo siguiente (P9). Si la corrida parase en seco en el ciclo 42, **las
  posiciones de los últimos dos días quedarían abiertas y su PnL no existiría** — el libro cerraría
  con una cola sin resolver y cualquier cifra agregada estaría tomada sobre una muestra truncada
  **por el calendario, no por el mercado**. Así que tras el ciclo 42 se ejecutan **dos días más de
  ciclos en modo sólo-liquidación** (`observations` + `settle`, sin abrir posiciones nuevas). Esos
  ciclos **no entran en el denominador de 42** ni en C1: no deciden nada. Lo que quede abierto al
  final de la cola se reporta como `unsettled` con su razón del enum, nunca como PnL cero.
- **MEDIDO 2026-09-09, y cambia lo que hay que esperar de §5.** El cron de Actions **entrega, pero
  tarde**: el disparo de las 11:40Z llegó a las **15:15Z**, con `drift_h = 3,292`,
  `late_firing = True` y `own_prices_usable = False` — el clamp llevó `prediction_time` a `T_asof` y
  el ciclo cayó, correctamente, al último precio recogido antes del ancla. Con retrasos de ese orden
  **casi todos los ciclos serán LATE_FIRING**, así que ese indicador dejará de discriminar y lo que
  importa pasa a ser **cuán viejo es el precio que se usa**, no si el ciclo llegó tarde. Se reporta
  por ciclo (§7) la antigüedad del precio empleado respecto de `T_asof`.
- **El registro completo del primer día, corregido a las 16:51Z** (una lectura anterior decía «cero de
  dos» y **era prematura**: la ranura de las 15:07Z llegó después de mirarla):

      colector  12:07Z  →  NUNCA entregada
      colector  15:07Z  →  entregada a las 16:33:54Z   (+86 min)
      colector  18:07Z  →  pendiente
      ciclo     11:40Z  →  entregada a las 15:15:30Z   (+215 min)

  **Dos de tres entregadas, las dos muy tarde, una perdida del todo.** El cron de Actions no está
  muerto: **entrega tarde y con pérdidas**, con retrasos de 1,5 a 3,6 h en la muestra.
  Y las dos formas duelen distinto: **el retraso le cuesta DENSIDAD al colector** —el book se captura
  cuando el job corre, sea a la hora o no— mientras que **una ranura perdida es una ventana de tres
  horas de historia de libro que no vuelve**. Para el ciclo, el retraso hace que muerda el clamp y que
  la decisión use la última captura del colector anterior al ancla, que con un colector también
  retrasado puede ser de varias horas antes: por eso lo que se reporta por ciclo (§7) es **la
  antigüedad del precio empleado respecto de `T_asof`**, no si el ciclo llegó tarde.
  El criterio de A-29.2 sigue siendo la tasa del colector, y **la decisión de cambiar de host es del
  usuario**. Con una muestra de tres ranuras no se decide nada: se sigue midiendo.
- **Y lo que los puentes manuales están tapando, medido.** Las capturas reales del primer día fueron
  10:31 · 12:29 · 13:10 · 14:39 · 15:15 · 16:14 · 16:33Z, con un hueco máximo de **118 min**, por
  debajo de la cadencia de diseño de 180. **Pero cinco de esas siete las disparé a mano.** Dejado
  solo, el almacén tendría un hueco de **284 minutos** (10:31 → 15:15), 1,6 veces la cadencia. Lo que
  la corrida vería sin vigilancia **no es lo que hay hoy en el almacén**, y la diferencia se reporta
  aparte: cada shard lleva su `event`, que distingue `schedule` de `workflow_dispatch`.

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

## §6bis. `PAPER_TAU`, y cómo se leerá el PnL — congelado ANTES de poner la variable

*(Añadido 2026-09-09. La sesión B lo pidió y el argumento es suyo: si la corrida va a producir un PnL
sobre ~1.000 posiciones, su lectura tiene que estar fijada antes, o en 21 días tendremos un número y
elegiremos después qué significa.)*

**1. `PAPER_TAU` es un PARÁMETRO DE EJERCICIO, no un umbral con una afirmación detrás.** R21 barrió la
rejilla congelada `{0,02k}`, k = 1…10, y el walk-forward se pegó al **máximo** en **239 de 271**
decisiones y aun así perdió. **No existe un tau operable con este sustrato.** Cualquier valor que se
ponga en la variable se declara aquí como de ejercicio, y el informe lo repite: quien lea el libro no
debe entender «operaban con tau = X» como si X tuviera respaldo.

**2. La regla para elegirlo es de COBERTURA, no de beneficio:** *el tau más alto que aún abre
posiciones en la mayoría de los ciclos*, medido sobre ciclos previos a la corrida y declarado con su
valor antes de poner la variable. Elegirlo para maximizar operaciones sería montar un escaparate;
elegirlo mirando qué PnL sale es exactamente lo que este documento existe para impedir.

**3. EL ORDEN ES UNA PRECONDICIÓN, no una recomendación.** Poner `vars.PAPER_TAU` **es** lo que
convierte los ciclos en operativos, así que la enmienda de §0 —el `n_requerido(tau)` y su umbral— y
esta sección quedan **hasheadas y congeladas antes de que la variable exista**. Una tau puesta antes
del criterio invalida la corrida igual que un cambio de parámetro a mitad (§8.3).

**4. Cómo se lee el resultado, fijado ahora:**
- **PnL negativo** → **coherente** con R21, y *no lo confirma automáticamente*: el tau es de ejercicio
  y una regla peor que la calibrada pierde por construcción. Añade evidencia prospectiva, no una
  réplica.
- **PnL positivo** → **no refuta R21 por sí solo.** El intervalo de R21 por bloques de evento es
  **[−0,0288 · −0,0205]**; refutarlo exige que el IC prospectivo, también por bloques de evento,
  **excluya ese rango**, no que la mediana salga por encima de cero.
- **`n` por debajo del mínimo** → **`NO EVALUABLE`**, nunca «no hubo beneficio». Es la cláusula de no
  vacuidad de §6.0 aplicada al PnL: el mínimo se fija en la misma enmienda que el umbral, con la
  regla de §4.1 de R21 (n ≥ 100 **decisiones de evento**, no posiciones).

**4bis. Los umbrales, en la forma directamente comprobable que propuso la sesión B:**
- **Coherente con R21:** mediana ≤ 0, **o** intervalo (por bloques de evento) que incluya el cero.
- **Contradictorio con R21:** mediana > 0 **y** intervalo por bloques que **no** incluya el cero,
  sobre **≥ 100 operaciones LIQUIDADAS**. *(Esta condición implica la formulación anterior —un
  intervalo positivo que excluye el cero excluye por fuerza el [−0,0288 · −0,0205] de R21, que es
  enteramente negativo— y es preferible porque se comprueba directamente.)*
- **`n` < 100 liquidadas → `NO EVALUABLE`**, ni APTA ni NO APTA. No «no hubo beneficio».
- **La etiqueta es `winning_outcome` del venue**, la misma que R21 §A.5, para que las dos corridas se
  midan contra la misma vara. El sesgo de la etiqueta por observación (§9) se reporta aparte y **no**
  sustituye a ésta.

**4ter. `PAPER_TAU` NO SE TOCA A MITAD. Si se cambia, la corrida SE PARTE.** Los tramos se reportan
**por separado y no se agregan**: un PnL agregado sobre dos taus distintas no es el PnL de ninguna
regla. Aportación de la sesión B, y cierra el hueco que dejaba §8.3 —que anula por cambio de
parámetro— para el caso en que alguien decida partir en vez de anular.

**5. Lo que esta sección NO autoriza:** ni ampliar la rejilla de tau, ni cambiar la regla de
selección, ni reajustar el constructor de colas, ni volver a correr con otra tau si la primera no
gusta. Cualquiera de esas cosas es una corrida nueva con su propio preregistro.

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
   `cycle_params`** (§4). Incluye `quantile_artifact_id`: un cambio de artefacto **fuera de la
   cadencia declarada en §4bis** anula la corrida; dentro de ella, no (§4bis.1).
4. Escritura en `main` desde un workflow.

**Parada con corrida conservada y declarada corta:**

5. 429 sostenido que impida ≥ 3 ciclos consecutivos.
6. **Crecimiento del almacén > 200 MB.** *(actualizado 2026-09-09)* El volcado del catálogo pasa a
   hacerse en **cada ciclo que decide**, no una vez al día: restringirlo al disparo de las 11:40Z
   dejaba al de las 02:40Z reproduciéndose contra un catálogo hasta **15 h más antiguo** que el
   universo sobre el que decidió, y **C3 daba NOT REPRODUCIBLE para media corrida por una razón que
   no es reproducibilidad** (verificado: 21 operaciones persistidas, 0 recomputadas, 21
   `only_persisted` espurias).
   **Volumen del almacén, ahora MEDIDO y no estimado** (2026-09-09, 7 recolecciones + 1 ciclo):
   **2,0 MiB en total**, ≈ **0,25 MiB por recolección**, con 7.854 capturas de libro sobre 2.244
   tokens. Proyectado a 8 recolecciones/día × 21 días ≈ **42 MiB**, más 42 ciclos con catálogo
   ≈ **8,7 MiB**, más pronósticos y señales: del orden de **55 MiB**, no los ~134 MB que estimé por
   fila. La anterior era una cuenta; ésta es una medida, y sobra margen contra el umbral de 200 MB.
   Coste **medido** del volcado: **206 KiB** comprimidos por instantánea
   (markets 83 + outcomes 123 + fees 0,3, sobre 1.100 / 2.200 / 1 filas) → **8,5 MiB en los 42
   ciclos**. Los ocho ciclos diarios de sólo-recolección lo siguen omitiendo: no deciden nada y no
   dejan nada que reproducir. El presupuesto de volumen sube de ~125 MB a ~134 MB, holgadamente
   por debajo del umbral.
   El umbral original: v1 fijaba 50 MB sin cuenta alguna y **la corrida lo
   rebasaba hacia el día 9**, haciendo C1 inalcanzable: el volumen medido es ≈ 271 B/fila
   comprimida × ~20 200 filas/día ≈ **5,5 MB/día ≈ 115 MB en 21 días**, más ~10 MB de catálogo — un
   volcado diario: el workflow pasaba `--dump-catalogue` en **los dos** disparos (~21 MB), y se ha
   corregido en el código para que sólo lo pase el de las 11:40Z. El
   umbral se fija por encima del volumen previsto, no por debajo.
7. Petición del usuario.

---

## §9. Limitaciones declaradas ANTES

- **El operador en °F está auditado sobre SEIS filas y seis estaciones** (estrato 8: KATL, KAUS,
  KHOU, KORD, KSEA, KSFO; `tmpf` dentro de la banda 6/6). Los 121 mercados y 11 eventos que la tabla
  del núcleo asocia al estrato son su **población**, no la muestra del audit. Es cobertura muestral
  estrecha, no ausencia de validación: validación hay y es 6/6.
- **Etiquetar desde observaciones falla, con signo, y el número que importa NO es el agregado.**
  Cruzando la resolución del venue contra las observaciones IEM en los 410 eventos donde el sustrato
  tiene la banda ganadora: 382 concuerdan, 28 no (**6,8 % agregado**). Medido como distancia FUERA de
  `[lo, hi]` —el único estadístico válido; usar el `lo` como «centro» da 47/72 y no significa nada—:
  **25 con la observación por debajo, 3 por encima, y 22 de las 25 fallan por exactamente un paso de
  rejilla.** No es una cola, es un escalón: la firma del muestreo horario, que no ve el máximo.
  - **El 6,8 % no es una tasa de error del instrumento: es la tasa a la que un error de un paso cruza
    el borde de la banda, y eso depende de la ANCHURA DE LA BANDA tanto como del sensor.** Una banda
    en °C es un entero único; una en °F abarca dos, y es aproximadamente el doble de tolerante.
    Por anchura: **entero único (°C) 9,7 %** (n=268) · **dos enteros (°F) 2,0 %** (n=51) · **banda
    abierta de cola 1,1 %** (n=91). Decir «las estaciones en °F observan mejor» sería escribir una
    propiedad del CONTRATO como si fuera del sensor.
  - **Y el universo en vivo está dominado por el caso malo.** Medido sobre los 1.100 mercados
    abiertos del 2026-09-09: **63,8 % banda de entero único en °C**, 18,0 % dos enteros en °F, 18,2 %
    banda abierta. Ponderando las tres tasas por esa mezcla sale **≈ 6,8 %**, pero la cifra que va
    pegada a una decisión concreta en °C es **9,7 %**, no la agregada.
  - **El sesgo NO es homogéneo y por tanto es acotable por estrato.** De 45 estaciones con ≥5
    eventos, **32 no fallan ni una vez**; cinco cargan el 71 % (EGLC 8/44, ZGSZ 5/8, RKSI 3/9,
    WSSS 2/8, EPWA 2/9). ZGSZ con 5 de 8 no es compatible con una tasa base del 6,8 % por azar.
  - **Cobertura: 399 de los 410 eventos son de abril y mayo**; junio a septiembre aportan 11 entre los
    cuatro. Es una muestra del primer tercio del periodo, no del periodo. **No se puede afirmar que la
    tasa sea estable en verano**, que es cuando la corrida ocurre.
  - **Y NO contamina el PnL en la magnitud que el 6,8 % sugiere. Corregido 2026-09-09.** Sobre las
    468 operaciones que R21 tomó, la discrepancia entre etiquetas es del **0,85 %**, la **mediana del
    PnL es idéntica** con una y con otra (−0,023600 las dos), y el total difiere en **2,00 USDC**, en
    la dirección de hacer la estrategia parecer **mejor**. La razón es estructural y no casual: el
    6,8 % se mide sobre bandas **ganadoras**, pegadas al valor realizado, donde un error de un grado
    decide; **las bandas que la estrategia compra están lejos del valor realizado, y ahí las dos
    etiquetas coinciden en que perdieron.** El 6,8 % es la fragilidad de la etiqueta **donde se juega
    la resolución**, no la contaminación de un PnL, y §7 tiene que decir las dos cosas o parecerá lo
    segundo.
  `stage_observations` hereda este sesgo; se reporta pegado a cada cifra (§7) con la tasa de la
  anchura de banda que corresponda, y junto al 0,85 % medido sobre operaciones tomadas.
- **La estimación de cuantiles se mueve entre reajustes.** Como dispersión es pequeña —σ_inst
  0,037 °C (lead 9) y 0,055 °C (lead 24) a Δ = 5 días, un 0,5 % del margen— **porque M2 v2 agrupa
  entre estaciones y su localización se estima con ~2.000 pares; es una propiedad de v2, no del
  fenómeno, y no se transporta a un M2 por estación.** Como peor caso de una decisión concreta llega
  a **0,39 °C**, el 70 % de la rejilla fina, y **no se reduce reajustando más a menudo** (§4bis.8):
  no es deriva, son escalones del percentil empírico sobre un dato cuantizado.
- **Los cuantiles vienen de un ajuste ANTERIOR a la decisión, no del instante de la decisión.** Es
  deliberado y es conservador —un ajuste en `t₀ < t` usa un subconjunto de lo permitido, y usar menos
  información de la permitida no puede crear fuga— pero significa que la distribución aplicada
  describe un pasado algo más corto que el disponible. La magnitud de esa diferencia es justamente lo
  que mide P8; por encima de `max_age_hours` deja de ser una limitación y pasa a ser una negativa.
- **El precio con el que se decide puede ser varias horas anterior a `T_asof`.** El cron llega tarde
  (§5), el clamp fija `prediction_time = T_asof`, y entonces el precio utilizable es el último que el
  COLECTOR capturó antes del ancla. Con el colector a tres horas y entregando con retraso, esa
  antigüedad puede acercarse a las tres horas. No invalida la decisión —el as-of se respeta— pero la
  información es más vieja de lo que el lead sugiere, y eso se reporta por ciclo.
- **El constructor de la distribución tiene las colas mal, y la corrida lo lleva dentro.**
  `quantiles_to_distribution` extiende linealmente sólo **un grado** más allá de p10/p90 y asigna
  **cero** después: sobrecarga la cola cercana **×1,8–2,4** (0,0968 frente a 0,0408 empírico en
  p50−2, lead 9) y **trunca a cero** la lejana, donde la realidad tiene un 2 %. Se corrigió aparte un
  error aritmético —la CDF de la cola inferior devolvía valores **negativos** y su magnitud se sumaba
  al bin más bajo, el 34 % de ese bin— pero **la forma de las colas sigue siendo la declarada aquí**,
  porque cambiarla después de ver el resultado de R21 sería elegir el modelo a posteriori. Ninguna
  cifra de esta corrida debe leerse como calidad de la señal.
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
- **`p_model` está PEOR calibrada para un mercado concreto que su cifra agregada, y NO es
  corregible** (B-12, medido). M2 calibra en agregado y, dentro de ese agregado, 43 de 45 estaciones
  están descalibradas con sesgos que **se cancelan**. La corrección por estación se intentó y falló:
  el sesgo **no es persistente** —correlación entre la primera y la segunda mitad del periodo
  **+0,080**— así que un desplazamiento aprendido del pasado se aplica al futuro como ruido, y los
  pares corregidos calibran **peor** (5 %) que los no corregidos (24 %).
  **Consecuencia operativa, y cambia una decisión:** el intervalo p10–p90 es honesto para el conjunto
  y **demasiado estrecho para cualquier estación individual**. Un edge que parezca suficiente contra
  la probabilidad agregada puede no serlo contra el mercado real. Por tanto **`tau_exec` necesita
  margen por descalibración de estación no corregible**, además del margen por costes y spread, y ese
  margen se declara en la enmienda de §0 junto con el número. El motor paper **no asume** calibración
  por mercado: no puede tenerla.
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
