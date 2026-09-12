# Polymarket — auditoría adversarial y mapa de edge

> ## ⚠ ESTE INFORME LLEVA UNA ADENDA QUE REFUTA SU LIMITACIÓN DECLARADA Y SU RECOMENDACIÓN CENTRAL
>
> **Léela antes que el resumen ejecutivo** — está al final, bajo *ADENDA DE VALIDACIÓN*.
> En resumen: la rama `paper-state` de este repositorio lleva **36 850 filas de libro
> reales** desde el 2026-09-09, así que la recolección que §4 (E2) propone *empezar*
> lleva tres días corriendo. El veredicto sobre Strategy A **no está afectado**.
>
> **Y ADENDA 2 (sesión B) resuelve E2 con esos datos, EN CONTRA:** el medio spread mediano
> es **0.0050–0.0100** contra el umbral de **0.036** que §4 fijó antes de medir — falla en
> todos los buckets de precio (**7,2×** en la mediana global; **1,8×** en el caso más adverso,
> la media del bin 7 — ver ADENDA 3) — y la coherencia de partición es rentable en
> **0 de 96** particiones completas. **Los edges #2 y #3 pasan de C a E.** Sobrevive uno
> solo, el #1 (calibración del precio de mercado), y es el único experimento que queda.
>
> Este puntero está aquí y no dentro del texto **a propósito**: editar el cuerpo borraría
> la distinción entre lo que se afirmó y lo que se corrigió, pero una corrección que vive
> 700 líneas más abajo no la lee nadie que entre por el título.

**Fecha:** 2026-09-11 · **Alcance:** todo el proyecto, sin compromiso con el trabajo previo
**Métrica única:** NET EXPECTED P&L AFTER REALISTIC EXECUTION AND COSTS

> **Limitación declarada por adelantado, y condiciona todo lo que sigue.** Esta sesión
> corrió con egreso de red **bloqueado por política** (403 en CONNECT a
> `gamma-api.polymarket.com`, `clob.polymarket.com`, `data-api.polymarket.com`,
> `api.open-meteo.com`). No se descargó ni un precio. El repositorio tampoco contiene
> datos: `results/`, `*.duckdb` y `paper_state/` están en `.gitignore`, y el único
> artefacto versionado es `artifacts/m2_quantiles.json`.
> **Consecuencia:** todo resultado NEGATIVO de este informe se apoya en evidencia
> preexistente reproducible (código + artefacto + mensajes de commit de corridas reales);
> toda propuesta NUEVA queda en clase **C — SPECULATIVE** hasta que se mida. No se
> fabrica ningún backtest. El §25 del encargo (investigación web) **no pudo ejecutarse**.

---

## 1. EXECUTIVE SUMMARY

**La estrategia actual debe abandonarse.** No es una opinión: el propio proyecto la
falsó con dos experimentos preregistrados y congelados antes de ver un solo número.

- **R21** (backtest walk-forward, 10 000 candidatos, 468 trades sobre 211 eventos):
  mediana de P&L neto **−0.0236 USDC/trade**, tasa de acierto **0.0556 contra una base
  rate de 0.0744**. No es que no encuentre edge: **selecciona peor que el azar.** Falla
  3 de sus 4 criterios. Sobrevive a quitar los costes (con `x_exec = 0` sigue en −0.0131)
  y a endurecer el umbral (el optimizador se clavó en el techo de la rejilla, 0.20 en
  239 de 271 decisiones, y siguió perdiendo).
- **R22** (locus de skill, 1 308 eventos, block bootstrap por evento): el modelo **no
  gana al mercado en NINGUNO** de los 10 estratos que estratifican de verdad, y en
  quince de diecisiete celdas |Δ| supera 2×SE de la propia celda.
- **La descomposición es el hallazgo real:** el BSS global del modelo es **+0.238**, pero
  **dentro de cada régimen de precio es negativo** (bin 0: **−0.547**). Es decir:
  condicionado al precio, el modelo **no aporta información**; lo que parecía aportar era
  "las bandas baratas son improbables", que el precio ya contiene porque el precio *es* el bin.

**El mecanismo, nombrado:** la regla compra donde `p_model` más se separa de `p_mid`. Si el
mercado está mejor calibrado, el lugar donde más discrepan es el lugar donde **el modelo**
se equivoca. El "edge" que la estrategia mide **es su propio error**. Adverse selection
contra una contraparte mejor informada, y ningún umbral lo arregla.

**Por qué era predecible, y por qué generaliza:** el insumo es un pronóstico público y
gratuito (ICON seamless vía Open-Meteo). Todo participante lee el mismo GFS/ECMWF/HRRR.
Una estrategia cuya señal es un dato público **no puede tener information edge sobre un
mercado que lee ese mismo dato**; sólo puede tener edge de *velocidad* o de *ejecución*.
Esto mata, de una vez, toda la familia "ML sobre features públicas para predecir el evento".

**Mi aportación independiente de esta sesión** (aritmética sobre el artefacto real del repo,
`artifacts/m2_quantiles.json`, y sobre el propio código de costes — reproducible offline):

1. **La puerta de señal casi no puede abrirse, y no por los costes.** Para que
   `edge_net > margin` se cumpla, el mercado tiene que estar infravalorando una banda entre
   un **17 % y un 83 % en términos relativos**. Descomponiendo el hueco exigido, ponderado
   por masa: **margen de calibración 74 %, slippage 17 %, fees 9 %.** El cuello de botella
   **no son los costes de transacción: es la imprecisión admitida del propio modelo.** Con
   bandas de 1 °F y una incertidumbre de localización de ±0.98 °F, la probabilidad de banda
   es incierta en 3–6 puntos sobre una magnitud de 10–15 puntos.
2. **Pasarse a maker no lo salva.** Quitando fee y cobrando medio spread, el umbral medio
   sólo mejora de 56 % a 63–72 % de `p_model`. Porque lo que domina es el margen, no el coste.
   *(Esto refuta mi propia hipótesis inicial de que el problema era de ejecución. Lo es sólo
   en un 26 %.)*
3. **Defecto nuevo, no listado en R21/R22:** `backtest.select_tau` optimiza la **mediana**
   del P&L neto. Con bandas de 5–30 % de probabilidad la tasa de acierto está **siempre por
   debajo del 50 %**, así que la mediana es *siempre* el P&L de un perdedor, `−(p_exec+fee)`.
   Maximizarla equivale a **ordenar por precio del billete, no por valor esperado**.
   Demostrado: elige τ=0.04 (media +0.077/trade) sobre τ=0.15 (media **+0.125**/trade).
   *Honestidad sobre su alcance:* en la corrida R21 real el optimizador se pinchó arriba
   de la rejilla, así que **este defecto no fue la causa operante allí** — pero invalida el
   objetivo para cualquier reuso.
4. **El truncamiento de colas se reproduce exacto.** `quantiles_to_distribution` extiende
   las colas linealmente **un solo grado** más allá de p10/p90 y asigna **cero** más lejos.
   Sobre el artefacto real, el bin inferior sale 0.0968 a lead 9 — el mismo número que R21
   reportó como ×2.37 de sobre-asignación. Corroboración independiente, no hallazgo nuevo.
5. **Ningún punto de decisión dentro del día objetivo fue jamás evaluado.** Los dos únicos
   leads son 9 h y 24 h antes de `endDate`, y `endDate` es `target_date 12:00Z`. La ventana
   donde la incertidumbre se colapsa de verdad —mientras y después de que ocurra el máximo
   local— **no se ha mirado nunca.**

**Dónde está probablemente el edge, si está en algún sitio.** No en predecir. Las tres
direcciones que sobreviven al argumento de R22 son: **(a) sesgos de precio del propio
mercado** (calibración del mercado, no del modelo) — *medible hoy, sin recolectar nada*;
**(b) provisión de liquidez** en libros finos donde el venue paga al maker; **(c) coherencia
entre mercados** (Σ bandas ≠ 1), que es model-free. Las tres comparten una condición
vinculante única: **el spread y la profundidad del libro**, que es exactamente el eje que
R22 declaró imposible de evaluar — `orderbook_snapshots` está vacía y las 16 165 636 filas
de precio son **todas `MIDPOINT_ESTIMATED`**. Los propios autores escribieron que ese era
"el eje al que apuntaba el mecanismo".

**Recomendación en una frase:** dejar de modelar el tiempo, empezar a medir el libro; y
antes de eso, correr el único experimento que ya se puede correr con los datos que existen
—la curva de calibración del **precio de mercado**— porque es el que puede dar un edge
model-free sin recolectar un solo dato nuevo.

---

## 2. VERDICT SOBRE LA ESTRATEGIA ACTUAL

# **La estrategia actual debe abandonarse.**

Strategy A (`p_weather` de un forecast público → `edge = p_model − p_market` → BUY long-only
sobre el token YES de bandas de temperatura) es **clase D — FALSE EDGE**.

| qué estaba mal | evidencia |
|---|---|
| No tiene skill sobre el mercado en ningún estrato | R22: Δ<0 en 10/10 estratos reales; 15/17 celdas con \|Δ\|>2×SE |
| Condicionado al precio, no aporta información | R22: BSS del modelo dentro de cada bin de precio es **negativo** (bin 0: −0.547); su BSS global +0.238 es un efecto **entre** bins que el precio ya contiene |
| Pierde dinero y selecciona peor que el azar | R21: mediana −0.0236/trade; acierto 0.0556 vs base 0.0744; negativo al quitar **cualquiera** de las 47 estaciones |
| El mecanismo es adverse selection, no ruido | R21: `p_model` está **bien calibrado** globalmente (ratios 1.0–1.4× en todo bucket >0.1); el bucket [0.2,0.3) realiza 0.2215 sobre los 10 000 candidatos y 0.010 sobre los 468 elegidos — factor 22 **dentro de una sola celda de calibración**. No falla el modelo: falla la regla que elige dentro de él |
| La puerta exige una dislocación irreal | esta sesión: el mercado debe estar 17–83 % barato en relativo; 74 % del hueco es el margen del propio modelo |
| El objetivo del walk-forward está mal planteado | esta sesión: la mediana ordena por precio del billete, no por EV, siempre que el acierto <50 % |
| La distribución no es una distribución en las colas | R21 + esta sesión: masa ×2.37 en la cola cercana, **cero** donde la realidad tiene 1.7–2.3 % |

**Por qué parecía funcionar antes de medirlo:** porque `p_model` *sí* tiene skill contra la
base rate (Brier 0.05191 vs 0.06801). El error fue confundir **tener skill** con **tener más
skill que el precio**. Son cosas distintas y sólo la segunda produce P&L.

**Qué se conserva.** El veredicto es sobre la *estrategia*, no sobre la *infraestructura*.
Se conserva y se reutiliza: el esquema as-of y las garantías no-look-ahead de 2C
(`test_no_lookahead_adversarial`), el operador de settlement, el modelo de coste D19
(`costs.py`), el motor walk-forward de `backtest.py` (cambiando el objetivo), el catálogo
Gamma y la disciplina de preregistro. Eso es el activo real del proyecto y cuesta meses
reconstruirlo. Lo que se tira es la **hipótesis**: que un pronóstico público vence a un
precio que lee ese mismo pronóstico.

**Qué NO se puede concluir, y el propio R22 lo dejó escrito antes de medir:** esto **no**
licencia "ninguna regla long puede funcionar". Brier es un promedio; el beneficio vive en un
subconjunto elegido. Licencia exactamente esto: *el skill que una regla long necesitaría no
aparece en los estratos declarados, y quien afirme lo contrario debe nombrar el estrato.*

---

## 3. TOP 10 EDGES

Escala 0–10. **Confidence** = confianza en que el edge exista *y sea explotable neto*, no en
que la idea sea interesante. Clase según §28 del encargo.

| # | Estrategia | Edge | Robustez | Scalability | Complexity | Confidence | Clase |
|---|---|---|---|---|---|---|---|
| 1 | **Calibración del PRECIO de mercado** (favourite–longshot bias): medir frecuencia realizada por bucket de `p_mid` y fadear el sesgo | 6 | ? | 5 | **2** | 5 | **C** — *medible hoy, sin recolectar nada* |
| 2 | **Provisión de liquidez / market making** en libros finos: cotizar dos lados en torno al fair público, cobrar el spread, fee 0 para el maker | 7 | ? | 4 | 7 | 4 | C |
| 3 | **Coherencia de partición** (Σ bandas ≠ 1) por el lado **maker** | 6 | 8 | 3 | 6 | 4 | C |
| 4 | **Nowcast intradía**: decidir *dentro* del día local, cuando el máximo ya ocurrió o casi | 6 | ? | 5 | 4 | 4 | C |
| 5 | **Coherencia YES+NO** dentro de un mismo mercado (p_yes + p_no ≠ 1) | 5 | 9 | 3 | **2** | 4 | C |
| 6 | **Latencia de actualización de forecast** (runs 00/06/12/18Z): edge de *velocidad*, no de juicio | 5 | ? | 4 | 6 | 3 | C |
| 7 | **Mercados estancados / baja participación**: precio sin actualizar durante horas | 4 | ? | 3 | 5 | 3 | C |
| 8 | **Relative value entre estaciones/fechas** correlacionadas | 4 | ? | 4 | 7 | 2 | C |
| 9 | **Ambigüedad de resolución** (`rounding_rule='tenths'`, 1 936 mercados; estrato HKO) | 4 | 3 | 2 | 8 | 2 | C con **riesgo de resolución alto** |
| 10 | **Coherencia de partición por el lado taker** | 2 | 9 | 2 | 4 | 7 | **E** — el hurdle es 13.4 % con 9 bandas; no ocurre |
| — | **Strategy A (actual): forecast público vs precio** | 0 | 0 | — | — | 9 | **D — FALSE EDGE** |
| — | **ML (LGBM/XGB/NN) sobre features meteorológicas públicas** | 0 | 0 | — | — | 8 | **E — NO EDGE**. R22 mata la familia entera: el problema no es la capacidad del modelo, es que el insumo es público. Un modelo mejor sobre el mismo dato público sigue perdiendo contra un precio que lee ese dato |

**Ninguna entrada es clase A ni B.** Es el resultado honesto: lo único con evidencia
*sólida* en este proyecto son los negativos. Marcar algo como A exigiría datos que esta
sesión no pudo obtener.

**Nota sobre §20 (control de overfitting):** este ranking es *discovery*, no *evidence*. Las
10 hipótesis se enumeraron antes de medir ninguna. Cuando se midan, el corte debe aplicar
corrección por multiplicidad sobre **10 familias**, no sobre la que sobreviva.

---

## 4. WINNING STRATEGY

**No puedo nombrar una estrategia ganadora, y decirlo es el resultado.** El §34 del encargo
autoriza explícitamente esta respuesta y es la que corresponde:

> **No tenemos evidencia suficiente de edge explotable.** Lo que sí tenemos es evidencia
> sólida de dónde **no** está (predicción meteorológica sobre datos públicos) y una
> identificación precisa del dato que falta para decidir sobre el resto (el libro de órdenes).

Fabricar aquí una "estrategia ganadora" sería exactamente el error que este informe
documenta. Lo que sigue es el **árbol de decisión** que la determina, con dos experimentos
que lo resuelven.

### E1 — Calibración del precio de mercado *(corre hoy, sobre datos existentes, coste ≈ 0)*

La pregunta: **¿está el precio de Polymarket sistemáticamente sesgado en algún tramo?**
No requiere ningún pronóstico, ningún modelo y ningún dato nuevo. R21/R22 ya tienen los
ingredientes cargados (10 000 filas con `p_mid` y `won`, y 16.1 M filas de precio en la base
completa) y **nunca publicaron la curva de calibración del mercado** — sólo su Brier agregado.

- Para cada bucket de `p_mid`: frecuencia realizada, n, CI bootstrap **por evento** (nunca por
  fila: 468 trades eran 211 eventos).
- Contraste: frecuencia realizada vs `p_mid` medio del bucket.
- **Falsable ex ante:** el edge existe sólo si algún bucket muestra un sesgo que (i) supera
  2×SE por block bootstrap, (ii) **mantiene el signo** en las dos mitades del periodo, y
  (iii) supera el hurdle de coste de su propio tramo (`x_exec + 0.05·p(1−p)`).
- **Dirección esperada por la literatura:** favourite–longshot bias — las colas baratas
  cotizan **caras**. Si se confirma, la operativa es **vender** bandas baratas, es decir
  **comprar el token NO** — que es justo el lado que el colector nunca guardó.
- **Por qué es inmune al argumento de R22:** no compites en información. Explotas un sesgo de
  *precio*. No necesitas saber más que nadie sobre el tiempo.

### E2 — Medición del libro *(recolección nueva, barata, 4–6 semanas)*

La pregunta: **¿es el medio spread mayor que la incertidumbre del fair value?** Ese único
número decide simultáneamente los edges #2, #3, #4 y #7.

- Snapshots de `/book` cada 60 s sobre el universo de mercados meteorológicos abiertos
  (el feed prospectivo R26 ya existe: `docs/DISCOVERY_OPEN_MARKETS.md`), **ambos tokens**.
- Métricas: medio spread, profundidad a 1/5/10 ticks, vida de las órdenes, tasa de
  cancelación, frecuencia de actualización, hora del día.
- **Condición de viabilidad, fijada aquí antes de ver el dato:** el market making es viable
  si `medio_spread_mediano > margen_fair_value`. El margen medido sobre el artefacto real
  está en **0.010–0.100, mediana ≈ 0.036** (tabla en §11). Así que **el umbral es un medio
  spread mediano > ~3.6 puntos de probabilidad, sostenido**. Por debajo de eso, #2 y #3
  mueren y se publican como D/E.

### El árbol

```
E1 (hoy) ──► ¿sesgo de precio estable, >2xSE, signo constante en ambas mitades,
             y por encima del hurdle de su tramo?
             SÍ ──► edge model-free. Es la estrategia. Requiere precios del token NO
                    (recolección nueva, pero trivial). Pasar a §31 paper trading.
             NO ──► no hay sesgo de precio explotable. Seguir a E2.

E2 (4-6 sem) ► ¿medio spread mediano > 3.6 puntos?
             SÍ ──► market making + cesta de partición por el lado maker (#2, #3).
                    Preregistrar antes de tocar un solo P&L.
             NO ──► el libro es demasiado fino o demasiado ajustado. Conclusión:
                    los mercados meteorológicos de Polymarket no son explotables
                    con este substrato. Abandonar la categoría y reevaluar el
                    universo (§15 del encargo) fuera del tiempo meteorológico.
```

**Si ambos fallan, la conclusión correcta es abandonar la categoría, y debe publicarse.**

---

## 5. WHY SHOULD THIS EDGE EXIST? *(sección obligatoria)*

Un edge sin mecanismo es un artefacto esperando ser descubierto. Para cada candidato:

### #1 Calibración del precio (favourite–longshot bias)
- **Quién está al otro lado:** participantes recreacionales que compran bandas baratas por el
  payoff asimétrico (pagar 3¢ para cobrar 1$). Es el sesgo mejor documentado de los mercados
  de apuestas desde los años 40 (Griffith 1949; Thaler & Ziemba 1988) y aparece en casi todo
  venue con participación minorista.
- **Por qué no ha sido arbitrado:** para explotarlo hay que **vender** el longshot, lo que
  requiere capital inmovilizado hasta resolución, tolerancia a rachas de pérdida gordas
  (vendes a 3¢ y pierdes 97¢ el 3 % de las veces) y un venue donde el lado corto sea
  ejecutable. Es un trade de *capacidad limitada y varianza alta*, no un almuerzo gratis.
- **Cuánto dura:** es estructural mientras haya flujo minorista direccional. Décadas en
  mercados de apuestas. Decae si el venue institucionaliza.
- **Cómo desaparece:** entrada de market makers profesionales con capital barato.
- **Por qué podría ser falso aquí:** con base rate 0.068 y bin 0 cubriendo el 79.2 % de las
  filas, el ruido es enorme; y el sesgo puede ir en la dirección contraria en un venue de
  crypto-nativos. **Por eso E1 exige signo constante en las dos mitades del periodo.**

### #2 Provisión de liquidez
- **Quién está al otro lado:** quien quiere inmediatez — alguien que ve el forecast y quiere
  posición *ahora*. Paga el spread por eso. Es la renta más antigua del oficio.
- **Por qué existe:** el venue **cobra sólo al taker** (`takerOnly=true`) y devuelve
  `rebateRate=0.25`. **La casa está pagando por la liquidez.** Eso no es una anomalía a
  arbitrar: es un subsidio declarado, y cobrarlo es el negocio previsto.
- **Por qué no está arbitrado en *estos* mercados:** los mercados meteorológicos son finos y
  numerosos (miles de band-markets, cada uno con volumen bajo). El coste fijo de cubrir
  miles de libros minúsculos es alto respecto al ingreso de cada uno. Ahí queda hueco.
- **Cuándo desaparece:** cuando el spread comprima por debajo de la incertidumbre del fair
  value. **Es exactamente la condición que E2 mide.**
- **El riesgo que lo mata:** adverse selection en la actualización del forecast. Tu cotización
  queda obsoleta en el instante en que sale el run de las 12Z y te barren el lado malo. La
  mitigación es estructural, no opcional: **retirar cotizaciones alrededor de los instantes
  de publicación** (00/06/12/18Z + margen), que son conocidos y programados.

### #3 y #5 Coherencia (Σ bandas ≠ 1 ; p_yes + p_no ≠ 1)
- **Por qué existe:** las bandas de un evento son mercados *separados*. Nadie tiene el mandato
  de mantener su suma en 1. Un participante que compra "82–83 °F" no mira las otras ocho
  bandas. La incoherencia es el estado por defecto de un conjunto de libros independientes
  con flujo desagregado.
- **Por qué no se arbitra:** ejecutar la cesta completa exige N fills simultáneos en N libros
  finos. Un fill parcial deja una posición direccional desnuda. **Es riesgo de ejecución, no
  riesgo de modelo**, y por eso el hurdle taker es prohibitivo (13.4 % con 9 bandas, §11)
  mientras el maker cobra por el mismo servicio.
- **Es model-free:** no hay que predecir nada. Una partición válida paga exactamente 1.
  Inmune por construcción a todo el argumento de R22.

### #4 Nowcast intradía
- **Por qué existe:** a las 18:00 hora local, el máximo diario **ya ocurrió** casi siempre. La
  incertidumbre no es meteorológica: es de *lectura del dato*. Quien lee el METAR horario
  antes que el precio, sabe el resultado, no lo pronostica.
- **Por qué no está arbitrado:** requiere infraestructura de ingesta en vivo y presencia en
  mercados de volumen bajo a horas concretas. Es trabajo, no genialidad.
- **Por qué es el hueco más grande de este proyecto:** los dos únicos leads evaluados (9 h y
  24 h antes de `endDate = target_date 12:00Z`) **caen ambos antes de que empiece el día local
  objetivo** para las estaciones del hemisferio occidental. La ventana donde la información
  se vuelve barata **jamás se miró**.
- **El caveat honesto:** si el mercado **cierra** antes de esa ventana, el edge no es
  operable. Determinarlo es la primera comprobación de §6, no un supuesto.

---

## 6. DATA REQUIRED

| dato | para qué | ¿lo tenemos? |
|---|---|---|
| `p_mid` + `won` por token (10 000 filas ya construidas; 16.1 M en bruto) | **E1** | **SÍ** — corre hoy |
| Precio del token **NO** | E1 (operar el lado corto), #5 | **NO.** El colector guardó sólo el YES en los 6 143 mercados. Gap de recolección, no del venue |
| Snapshots de `/book`: bid/ask, profundidad, timestamps | **E2**, #2, #3, #4, #7 | **NO.** `orderbook_snapshots` vacía; **las 16 165 636 filas son `MIDPOINT_ESTIMATED`**. Es *el* dato que falta |
| Trades ejecutados (precio, tamaño, lado agresor) | #2 (adverse selection), #6 | **NO** |
| Horario real de apertura/cierre por mercado | #4 — viabilidad | Parcial (`close_time`); **verificar contra el cierre real** |
| Observaciones METAR intradía en vivo con `available_at` **medido** | #4 | Parcial. El repo asume 24 h de lag y lo declara supuesto, no medición (B-4/D17) |
| Instantes de publicación de runs de modelo | #6 | Parcial (`issue_time`, `available_at`) |
| `discovered_at` | edad de mercado | **NULL en 10 000/10 000.** Eje inutilizable |

**Lo primero que hay que arreglar de la instrumentación**, independientemente de la
estrategia elegida: guardar **los dos tokens**, guardar **book snapshots**, y **medir**
`available_at` en vez de suponerlo. Sin eso ninguna simulación de ejecución es honesta —
y el propio `costs.py` lo dice: *"slippage es una ASUNCIÓN, no una medición"*.

---

## 7. MODEL

**La arquitectura meta-modelo del §13 del encargo se recomienda explícitamente, con una
corrección de fondo: el Modelo 1 (predecir el evento) se ELIMINA.** R21/R22 demuestran que
sobre datos públicos ese bloque no aporta nada condicionado al precio, y su presencia es
exactamente lo que produjo la adverse selection.

```
   [ELIMINADO]  M1: P(evento) a partir de datos públicos
                    -> R22: BSS negativo dentro de todo régimen de precio

   M_fair    fair value = precio de mercado, NO el modelo.
             El mercado es el mejor estimador disponible de P(evento) (Brier
             0.04215 vs 0.05191 del modelo). Se usa el precio como ancla y el
             forecast SÓLO como cota de incertidumbre, nunca como pronóstico rival.

   M_bias    sesgo de precio estimado por bucket, de E1. La ÚNICA fuente de
             alpha direccional admitida, y sólo si E1 sobrevive.

   M_unc     incertidumbre del fair value = `calibration_margin` (ya implementado).
             Define la anchura mínima de cotización. Ya NO es un umbral de veto:
             pasa a ser el semiancho del quote.

   M_exec    P(fill | quote, spread, profundidad, hora)  <- requiere E2

   M_risk    tamaño = f(edge, incertidumbre, liquidez, inventario)
```

**El cambio conceptual que importa:** `calibration_margin` deja de ser una **puerta** que
casi nunca se abre y pasa a ser el **semiancho del spread que cotizas**. Un taker necesita
que su punto estimado sea mejor que el precio. Un maker sólo necesita cotizar más ancho que
su propia incertidumbre y esperar a que le vengan. **El mismo número, 0.036, que hacía
imposible el trade direccional, es un spread perfectamente cotizable si el libro es más
ancho.** Ese es el giro de "prediction edge" a "trading edge" que pedía el §6 del encargo.

**Sobre ML:** ningún modelo complejo se justifica aquí. La baseline (el precio de mercado)
gana al modelo actual en todos los estratos. **El modelo más simple que genere edge tiene
preferencia, y ahora mismo el más simple es "el precio"**. ML sólo volvería a ser candidato
en `M_exec` (predecir fills), que es un problema de microestructura con etiquetas propias —
y sólo cuando existan los datos de E2.

---

## 8. SIGNAL

Reglas exactas, condicionadas al resultado de E1/E2. Se escriben ahora, antes de ver
ningún número, para que sean preregistrables.

### Si E1 sobrevive — fade del sesgo de precio
```
UNIVERSO   tokens con p_mid en un bucket B cuyo sesgo sobrevivió E1
ENTRADA    |freq_realizada(B) - p_mid| > 2*SE_bucket  Y  signo estable en ambas mitades
FAIR       freq_realizada(B)   (NO el forecast)
EDGE       edge = fair - p_exec - fee
UMBRAL     edge > 2*SE_bucket          <- el umbral ES la incertidumbre de la estimación
LADO       si p_mid > fair: comprar NO. Si p_mid < fair: comprar YES.
SALIDA     hold to resolution (sin salida intermedia: no hay libro para salir)
```

### Si E2 sobrevive — market making
```
UNIVERSO   band-markets con medio spread mediano > 3.6 pts y profundidad > tamaño minimo
FAIR       mid del libro, anclado y acotado por el forecast (el forecast VETA, no dirige)
QUOTE      bid = fair - max(margin, medio_spread_minimo)
           ask = fair + max(margin, medio_spread_minimo)
INVENTARIO sesgar ambas patas contra el inventario acumulado
BLACKOUT   retirar TODA cotizacion en [-15min, +45min] de 00/06/12/18Z
           y en [-10min, +10min] de cada METAR horario   <- anti adverse selection
KILL       si el inventario neto supera el limite, solo se cotiza el lado reductor
```

### Siempre, en toda variante
```
VETO   fee no legible            -> no operar (fail-closed, ya implementado)
VETO   band_integrity != partition -> evento excluido (ya implementado)
VETO   estacion sin huso conocido  -> excluido (ya implementado)
VETO   rounding_rule = 'tenths'    -> excluido (1 936 mercados no convertibles)
```

**Cambio obligatorio en `backtest.select_tau`:** sustituir la mediana por la **media
recortada al 10 %** con CI bootstrap **por evento**. La mediana ordena por precio del
billete siempre que el acierto sea <50 %, que es el régimen de todas estas bandas
(demostrado en §11).

---

## 9. EXECUTION ENGINE

**Estado actual: no existe, y no debe existir todavía.** La puerta D0 ("nada aquí puede
firmar ni colocar una orden") está intacta y **debe seguir intacta** hasta completar §14.

Cuando llegue el momento, los requisitos no negociables, cada uno derivado de un defecto
ya medido en este proyecto:

1. **Órdenes límite por defecto.** La cadena entera de este informe dice que el taker paga
   demasiado. Un motor que cruce el spread anula el edge que pretende capturar.
2. **Nunca evaluar al mid.** `costs.exec_price` ya lo impone en backtest; el motor en vivo
   debe registrar el precio **ejecutable** y el **fill real**, no el indicativo. Las 16.1 M
   filas `MIDPOINT_ESTIMATED` son la razón por la que hoy no se puede simular nada.
3. **Fills parciales de primera clase.** Para la cesta de partición un fill parcial es una
   posición direccional desnuda. El motor debe tratar la cesta como una unidad y **cancelar
   las patas restantes** si la cesta no se completa en un plazo fijado.
4. **Blackout programado** alrededor de las publicaciones de modelo. Conocidas y periódicas:
   es una regla de calendario, no una predicción.
5. **Fail-closed en todo dato ausente.** Ya es la norma de la casa (`taker_fee` → `None`) y
   se conserva verbatim.
6. **Registro de degradación:** cada orden guarda señal, precio teórico, precio ejecutable,
   precio disponible, fill hipotético, fill real, slippage, latencia. Es el insumo del
   *degradation factor* de §14.

---

## 10. RISK MANAGEMENT

Límites propuestos. Los números se justifican abajo; **ninguno es arbitrario**, pero todos
son provisionales hasta que E1/E2 den varianzas reales.

| límite | valor | justificación |
|---|---|---|
| Capital inicial en vivo | **≤ 2 %** del capital destinado | §32: empezar con una fracción pequeña. El degradation factor backtest→paper→live es desconocido en este venue |
| Tamaño por trade | Kelly fraccionario **≤ 0.25×**, con cota de liquidez | Kelly pleno es óptimo sólo con `p` conocida. Aquí `p` es estimada y B-12 midió que está **peor calibrada por mercado que en agregado** y que **no es corregible con este substrato** |
| Tamaño máximo vs libro | **≤ 10 %** de la profundidad visible al mejor precio | Por encima, el price impact anula el edge y el backtest deja de describir la ejecución |
| Exposición por evento | **≤ 1 %** | Las bandas de un evento son una partición: **no son posiciones independientes.** Si el forecast falla para el evento, falla para todas a la vez |
| Exposición por estación | **≤ 5 %** | R21: el signo era negativo al quitar **cualquiera** de las 47 estaciones. La concentración por estación es un riesgo demostrado |
| Exposición por día objetivo | **≤ 10 %** | Un frente meteorológico correlaciona estaciones enteras el mismo día |
| Drawdown de cartera | **kill a −15 %** | ≈3× la desviación típica esperada de una cartera de edges pequeños. Debe recalibrarse con la varianza medida de E1/E2 |
| Sizing bajo incertidumbre | si `SE(edge) > edge/2` → **no operar** | §22: limitar el tamaño cuando la estimación es incierta. Con esta regla, `SIZE_SHARES=1` deja de ser un parche y pasa a ser el caso degenerado |

**Kill switches (§29):**
- P&L acumulado negativo en paper trading tras N trades preregistrados → parar y publicar.
- Degradation factor (paper/backtest) **< 0.5** → parar: la simulación no describe el mundo.
- Un cambio de régimen de fees en el venue → parar hasta re-derivar el modelo de coste.
- Cualquier fila con fee no legible → esa fila no opera (ya implementado, fail-closed).
- **Discrepancia entre nuestra etiqueta y la del venue > 1 %** → parar. R21 la midió en
  0.85 % sobre 468 trades; por encima del 1 % el riesgo de resolución deja de ser residual.

---

## 11. BACKTEST RESULTS

**No se produjo ningún backtest nuevo en esta sesión y no debe fabricarse uno.** Sin red y
sin datos en el repositorio, cualquier número de P&L sería inventado. Lo que sigue son
(a) los resultados **reales** de las corridas preregistradas previas y (b) aritmética
**reproducible offline** sobre el artefacto versionado.

### (a) Corridas reales previas — reproducibles desde `R21_REPORT.md` / `R22` JSON

**R21 — `PREREG_R21_BACKTEST_TAU.md` + Enmienda A, congelados antes de existir un solo P&L**

```
candidatos           10 000   (5 719 mercados x 2 leads - 1 438 sin insumo as-of)
trades tomados          468   sobre 211 eventos   C1 (n>=100) PASA
mediana P&L/trade   -0.0236   C2 (mediana>0) FALLA
tasa de acierto      0.0556   contra base rate 0.0744
leave-one-station   negativo en las 47          C3 FALLA
sin el mes mayor    -0.0184                     C4 FALLA
Brier: modelo 0.05191 · mercado 0.04215 · base 0.06801
VEREDICTO: NO OPERABLE CON ESTE SUBSTRATO
```

**R22 — `PREREG_R22_SKILL_LOCUS.md` v4, congelado antes de existir un solo Brier**

```
10 000 filas · 1 308 eventos · 70 celdas · 17 evaluables (>=100 eventos)
tras retirar celdas degeneradas: 10 estratos reales (lead x2, unidad x2,
                                 posicion de banda x3, anchura de forecast x3)
TODOS con Delta < 0 · 15/17 con |Delta| > 2 x SE de su celda
mejor celda T_obs = -0.00252 · p_familia = 1.0000
BSS global del modelo +0.238 · DENTRO de cada bin de precio: -0.547, -0.117,
                                -0.023, -0.091, -0.234
VEREDICTO: EL MODELO NO GANA AL MERCADO EN NINGUN ESTRATO DECLARADO
```

### (b) Aritmética de esta sesión — reproducible offline

Artefacto: `artifacts/m2_quantiles.json` (`icon_seamless`, POOLED, n=1347/1348).
Script: `scripts/research/gate_arithmetic.py`. Mercado en °F, forecast 25 °C, bandas de 1 °F.

**Lead 24 h — ¿a qué precio podríamos comprar cada banda?**

| banda | p_model | margin | mid máx. operable | mid/p_model |
|---|---|---|---|---|
| 74 | 0.1001 | 0.1001 | **nunca** | — |
| 75 | 0.0928 | 0.0233 | 0.0563 | 60.7 % |
| 76 | 0.1175 | 0.0368 | 0.0671 | 57.1 % |
| 77 | 0.1546 | 0.0357 | 0.1039 | 67.2 % |
| 78 | 0.1546 | 0.0103 | 0.1284 | 83.0 % |
| 79 | 0.1432 | 0.0599 | 0.0697 | 48.6 % |
| 80 | 0.0835 | 0.0587 | 0.0137 | **16.4 %** |
| 81 | 0.0895 | 0.0236 | 0.0530 | 59.2 % |
| 82 | 0.0641 | 0.0641 | **nunca** | — |

**El mercado tiene que estar entre un 17 % y un 83 % barato en relativo para que la puerta
se abra.** Descomposición del hueco exigido, ponderada por masa:

```
margen de calibracion  74 %      <- la imprecision del propio modelo
slippage (x_exec 0.01) 17 %
fees (0.05*p*(1-p))     9 %
```

**El contrafactual maker** (fee 0, cobrando medio spread) mejora el umbral medio sólo de
**56 % → 63–72 %** de `p_model`. Refuta la hipótesis de que el problema fuera de ejecución:
lo es en un 26 %. El problema es la precisión del fair value.

**Hurdle de la cesta de partición** (comprar las N bandas → paga exactamente 1):

| N bandas | S máx. taker (x=0.01) | S máx. maker (h=0.01) |
|---|---|---|
| 5 | 0.9100 | 1.0500 |
| **9** | **0.8656** | **1.0900** |
| 15 | 0.8033 | 1.1500 |

Con 9 bandas el taker necesita la partición a ≤0.866 —una infravaloración del **13.4 %** de
un conjunto que paga 1—; el maker cobra por hacerlo en casi cualquier libro. La componente
de fee del hurdle es `0.05·(1−1/N)`, **independiente de los precios**.

**Defecto del objetivo del walk-forward** (`scripts/research/tau_objective.py`):

```
tau=0.04  n=2000  MEDIANA -0.0315  MEDIA +0.0769   <- select_tau ELIGE este
tau=0.15  n=1000  MEDIANA -0.1667  MEDIA +0.1253   <- 63% mejor por trade
```
Un perdedor de 2 céntimos (−0.031) supera en la mediana a uno de 16 (−0.167) aunque el
segundo gane 5× más en esperanza. **La media recortada habría ordenado bien.**

---

## 12. ROBUSTNESS

Los 12 tests del §19 aplicados al **resultado negativo** (es lo que hay que atacar: si el
negativo es frágil, la estrategia merecía otra oportunidad). El resultado negativo
**sobrevive a todos los que se pudieron correr**:

| test | resultado |
|---|---|
| 1. Distintos periodos | R21 C4: quitando el mes mayor, sigue negativo (−0.0184) |
| 2. Distintas categorías | R22: 10/10 estratos negativos (lead ×2, unidad ×2, posición ×3, anchura ×3) |
| 3. Distintos niveles de liquidez | **NO EJECUTABLE** — `orderbook_snapshots` vacía. *El eje al que apuntaba el mecanismo* |
| 4. Distintos tamaños de posición | No ejecutable sin libro. `SIZE_SHARES=1` es un supuesto |
| 5. Distintos supuestos de ejecución | R21: con `x_exec=0` (ejecución gratis) sigue negativo, −0.0131 |
| 6. Costes mayores | R21: H2/H3 peores. La conclusión se endurece |
| 7. Información retrasada | Implícito en el corte por disponibilidad de etiqueta (v2 §3) |
| 8. Inyección de ruido | No ejecutado |
| 9. Perturbación de parámetros | R21: la rejilla completa de τ; el optimizador quiso ser **más** estricto y siguió perdiendo |
| 10. Out-of-sample | Walk-forward expansivo por disponibilidad de etiqueta (no por `target_date`, que fugaba en 8/8) |
| 11. Placebo | R22: test de permutación, 2 000 réplicas, p_familia=1.0000 |
| 12. Entrada aleatoria | Implícito: el acierto (0.0556) es **peor** que la base rate (0.0744) |

**Controles de leakage verificados en código** (§3, preguntas 9–12 del encargo):
- `test_no_lookahead_adversarial.py`, `test_no_future_information.py`, `test_resolution_not_in_features.py` existen y son adversariales.
- `FORBIDDEN_FEATURE_FIELDS` bloquea `winning_outcome`, `resolution_timestamp`, `settlement_timestamp`, `is_winner`.
- El corte de entrenamiento usa **disponibilidad de etiqueta**, tras descubrir que `target_date < D` fugaba en 8/8 estaciones (−9 h a −43 h).
- `local_day` prohíbe `observation_time::date` tras descubrir que el tamaño de muestra dependía de la variable de sesión de DuckDB (2 599 filas en UTC, 1 881 en Asia/Shanghai).

**Esto es trabajo de primera calidad y es la razón por la que confío en el negativo.** El
proyecto invirtió su esfuerzo en no engañarse, y funcionó: se falsó a sí mismo.

### Defectos abiertos que este informe añade

| # | defecto | severidad | evidencia |
|---|---|---|---|
| A1 | `select_tau` maximiza la mediana → ordena por precio del billete cuando el acierto <50 % (siempre aquí) | **alta** (invalida el objetivo; **no** fue la causa operante en R21) | `scripts/research/tau_objective.py` |
| A2 | Colas de `quantiles_to_distribution` truncadas a ±1 grado; masa **cero** donde la realidad tiene 1.7–2.3 % | **alta**, ya publicado por R21; **sigue sin corregir** y afecta a todo consumidor de `weather_prob`, incluido el paper run | reproducido: bin inferior 0.0968 a lead 9 |
| A3 | Sólo se guardó el token **YES** en los 6 143 mercados | **alta** — impide el lado corto y el test de coherencia YES+NO | `backtest.py`: *"no NO series exists"* |
| A4 | Ningún punto de decisión **dentro** del día local objetivo fue evaluado | **alta** — es donde la información se abarata | `decision_time()`: leads 9 y 24 sobre `endDate = target_date 12:00Z` |
| A5 | **Verificar:** `endDate = target_date 12:00Z` (R8) vs ventana de settlement `LOCAL_CIVIL_DAY` — para estaciones al oeste de Greenwich el fin declarado del mercado **precede** al cierre de su propia ventana de medición | **a determinar** — si se confirma afecta a toda fila de R21/R22 | `backtest.universe()` vs `settlement.local_civil_day_window()`. **No verificable sin la base de datos; es la primera comprobación de integridad a correr** |
| A6 | `available_at` de las observaciones es el instante de descarga, no la publicación; el lag de 24 h es **supuesto, no medido** | media, **ya declarado** por el proyecto | `error_model.ASSUMED_LABEL_LAG` |
| A7 | `discovered_at` NULL en 10 000/10 000 → eje de edad de mercado inutilizable | media, ya detectado | `run_r22.py` |

---

## 13. FAILURE MODES

**De la estrategia actual — ya falló, y así fue:** adverse selection. Compra donde su
desacuerdo con el mercado es máximo, que es donde ella se equivoca. Ningún umbral lo arregla
porque endurecer el umbral aprieta más sobre el mismo criterio equivocado.

**De cada candidato nuevo, cuándo dejará de funcionar:**

- **#1 Calibración del precio.** Muere si entran market makers profesionales, si el mix de
  participantes se institucionaliza, o si el sesgo medido era ruido de un periodo (abril–
  septiembre 2026, una sola estación del año). **Señal temprana:** el sesgo cambia de signo
  entre mitades del periodo. Por eso está en el criterio de aceptación.
- **#2 Market making.** Muere cuando el spread comprima por debajo de la incertidumbre del
  fair value. **Muere más rápido por adverse selection**: si te barren sistemáticamente en
  las publicaciones de modelo, pagas el edge de otro. **Señal temprana:** el P&L por fill se
  vuelve negativo en la ventana ±30 min de 00/06/12/18Z.
- **#3/#5 Coherencia.** Muere cuando alguien ponga un bot de coherencia en estos libros —es
  el edge más fácil de copiar de la lista. **Señal temprana:** la frecuencia de
  incoherencias por encima del hurdle cae mes a mes.
- **#4 Nowcast intradía.** Muere si el mercado cierra antes de la ventana informativa, o si
  el venue añade un feed de observaciones. **Riesgo de resolución:** la etiqueta IEM discrepa
  de la del venue en 0.85 % de los casos, medido — y ese 0.85 % se concentra en las bandas
  **ganadoras**, que son exactamente las que esta estrategia compraría. **El riesgo de
  resolución del nowcast es estructuralmente mayor que el de Strategy A.** Hay que
  cuantificarlo antes, no después.

**Del proyecto entero:** el modo de fallo más probable no es que una estrategia pierda
dinero. Es **seguir invirtiendo en infraestructura de pronóstico meteorológico** porque ya
está construida. R22 cerró esa vía. El coste hundido no es un argumento.

---

## 14. LIVE TEST

Paper / shadow trading, antes de un solo dólar. Lo que debe registrar cada señal (§31):

```
señal · instante de decision · precio teorico (fair) · precio EJECUTABLE al decidir
precio realmente disponible · fill hipotetico · fill real · tamaño · slippage
latencia decision->orden · P&L al cierre · resultado de resolucion · benchmark
```

**Benchmark obligatorio:** "comprar al precio de mercado y mantener" sobre el mismo universo.
Una estrategia que no bate a su propio universo comprado a ciegas no tiene edge, tiene beta.

**Degradation factor**, medido explícitamente:
```
D1 = P&L_paper / P&L_backtest       <- si < 0.5, la simulacion no describe el mundo: PARAR
D2 = P&L_live  / P&L_paper          <- si < 0.5, la ejecucion no es la simulada: PARAR
```

**Puertas para pasar a capital real** (§32), todas necesarias:
1. Evidencia fuera de muestra en un periodo **no usado** para elegir nada.
2. Edge económicamente significativo tras costes (no estadísticamente significativo: **económicamente**).
3. Costes incluidos con fee **leído por mercado** y slippage **medido**, no supuesto.
4. Ejecución simulada contra libro **real**, no contra el mid.
5. Paper trading confirmando el comportamiento con D1 ≥ 0.5.
6. Sin señales graves de overfitting: corrección por multiplicidad sobre **las 10 familias**, no sobre la superviviente.
7. Mecanismo económico nombrado que explique **quién** está al otro lado y **por qué** pierde.

La puerta D0 (nada puede firmar ni colocar una orden) **permanece cerrada** hasta que las
siete se cumplan.

---

## 15. ROADMAP

Ordenado por `valor esperado / coste`, no por dificultad.

**Semana 1 — barato, y puede matar o validar una hipótesis entera**
1. **Correr E1** (curva de calibración del precio de mercado) sobre las 10 000 filas de R21
   que ya existen. Preregistrar el criterio **antes** de mirar: >2×SE por block bootstrap de
   evento, signo estable en ambas mitades, y por encima del hurdle de su tramo. *Coste: horas.
   Puede producir el primer edge model-free del proyecto — o cerrar la vía.*
2. **Verificar A5** (`endDate` vs ventana `LOCAL_CIVIL_DAY`). Si el fin de mercado precede al
   cierre de la ventana de medición, hay un defecto semántico bajo cada fila de R21/R22 y hay
   que saberlo antes de reutilizar ese substrato. *Coste: una consulta.*
3. **Corregir A1** (media recortada en lugar de mediana) y **A2** (colas de la distribución).
   A2 sigue afectando al paper run en producción. *Coste: horas.*

**Semanas 2–6 — la recolección que desbloquea todo lo demás**

4. **Lanzar el colector de libro (E2).** Snapshots de `/book` cada 60 s sobre mercados
   meteorológicos abiertos, **ambos tokens**, guardando bid/ask/profundidad/timestamps. El
   feed prospectivo R26 ya existe. *Este es el punto de inflexión del proyecto:* es el eje
   que R22 declaró imposible de evaluar y el que el mecanismo señalaba.
5. **En paralelo, recolectar el token NO.** Desbloquea el lado corto (necesario para #1 si el
   sesgo es longshot) y el test de coherencia #5, que es casi gratis una vez hay ambos lados.
6. **Medir `available_at` de verdad** en vez de suponer 24 h.

**Semanas 7–10 — decidir con datos**

7. Evaluar la condición de E2: `medio_spread_mediano > 3.6 puntos`. Fijada **ahora**, antes
   de ver el dato.
8. Según el árbol de §4: preregistrar market making + cesta de partición maker, **o** declarar
   la categoría no explotable y publicarlo.
9. Medir #4 (nowcast intradía) con los datos de libro, incluyendo si el mercado sigue abierto
   en la ventana informativa y cuantificando el riesgo de resolución **antes** del P&L.

**Lo que NO hay que construir:** ningún modelo meteorológico nuevo, ninguna calibración de
`p_weather`, ningún ensemble, ningún ML sobre features públicas. R22 cerró esa familia. Si
alguien quiere reabrirla, la carga de la prueba es nombrar el estrato donde el modelo gana
al mercado — y R22 midió diez y no hay ninguno.

---

## Reproducibilidad (§36)

| experimento | script | insumo | periodo | resultado |
|---|---|---|---|---|
| Aritmética de la puerta | `scripts/research/gate_arithmetic.py` | `artifacts/m2_quantiles.json` | fit abr–sep 2026 | mid/p_model 16.4–83.0 %; hueco = 74 % margen / 17 % slippage / 9 % fee |
| Hurdle de la cesta | `scripts/research/partition_arb.py` | ninguno (aritmética cerrada) | — | taker N=9: S≤0.8656; maker N=9: S≤1.0900 |
| Objetivo del walk-forward | `scripts/research/tau_objective.py` | sintético, semilla 11 | — | la mediana invierte el orden frente a la media |

Los tres corren offline, sin red y sin base de datos:
`python3 scripts/research/<script>.py`

**Supuestos que atraviesan todo lo anterior, declarados:** mercado en °F con bandas de 1 °F y
forecast de 25 °C como caso representativo (la conclusión cualitativa no depende del nivel,
sí la tabla exacta); fee `0.05·p·(1−p)` taker-only según D19; `x_exec = 0.01` según
`PREREG_R21_ENMIENDA_A §A.2`; cuantiles POOLED por lead del artefacto versionado.
**Limitación principal, repetida porque condiciona el informe entero: sin acceso a red no se
verificó ni un solo precio vivo, y toda propuesta nueva es clase C hasta que se mida.**

---

# ADENDA DE VALIDACIÓN — sesión A, 2026-09-11 15:35Z

*Escrita al final y no dentro del texto anterior, a propósito: el informe queda como se
entregó, y esta adenda dice qué sigue en pie y qué no. Editar el cuerpo borraría la
distinción entre lo que se afirmó y lo que se corrigió.*

## LA RECOMENDACIÓN CENTRAL ESTÁ CADUCADA POR TRES DÍAS

El informe cierra con *«dejar de modelar el tiempo, empezar a medir el libro»*, y lo apoya en:

> `orderbook_snapshots` está vacía y las 16 165 636 filas de precio son **todas
> `MIDPOINT_ESTIMATED`**

**Eso es cierto del backfill histórico y falso del proyecto a día de hoy.** Medido sobre la
rama `paper-state` de este mismo repositorio:

| | |
|---|---|
| Shards de `orderbook_snapshots` commiteados | **33** |
| Filas de libro **reales** | **36 850** |
| `source` | `clob_books_poll` — ni una `MIDPOINT_ESTIMATED` |
| Cobertura | 2026-09-09 … 2026-09-11, **10 ranuras/día**, ninguna perdida |
| Campos por fila | `best_bid`, `best_ask`, `spread`, `imbalance`, `bid_depth_1/5/10`, `ask_depth_1/5/10` y el `book_snapshot` con sus niveles |

**Spread observado** sobre los 25 736 libros de dos lados: mediana **0,0100**, p25 0,0080,
p75 0,0200.

### Qué le hace esto al árbol de decisión

**E2 —«medición del libro: recolección nueva, barata, 4–6 semanas»— ya está corriendo y
lleva tres días.** No hay que empezarla: hay que esperarla. Las 4–6 semanas caen entre el
**2026-10-07 y el 2026-10-21** contando desde el 09-09.

**Y E1 cambia de naturaleza.** El informe lo propone *«sobre datos existentes, coste ≈ 0»*
usando costes **supuestos**. Con el libro recogido, el coste de E1 puede **medirse**. Eso
importa porque el propio informe concluye que el cuello de botella es el margen y no el
coste — una conclusión construida sobre un coste que ya no hace falta suponer.

### Por qué se coló, dicho sin reproche porque la clase es conocida

**Primera versión de esta adenda, corregida:** dije que era *«una afirmación sobre el alcance
del corpus hecha sin usar el instrumento»*. **Eso era injusto y, peor, inexacto.**

Comprobado: **`/paper_state/` SÍ está en `.gitignore`** (línea 59), igual que `results/` y
`*.duckdb`. **La limitación declarada era literalmente cierta.** No se dejó de mirar nada.

Lo que falla es la inferencia. **`.gitignore` dice qué haría una ruta NO RASTREADA en el árbol
de trabajo; no dice nada de lo que ya está rastreado en otra rama** — y `git` no ignora
ficheros que ya sigue. En la rama `paper-state` hay **149 ficheros de `paper_state/`
commiteados**. La comprobación fue real y respondió **otra pregunta**.

Así que la clase no es «no comprobó»: es la que este proyecto catalogó el mismo día — **un
dato bien medido prestado a una conclusión que no lo soporta.** El dato resiste cualquier
verificación, porque es verdadero; sólo se caza leyendo la implicación. Un
`git ls-tree -r origin/paper-state` la habría deshecho, y el egreso bloqueado no era el
obstáculo: la rama estaba en el clon local.

## UNA DISCREPANCIA QUE ALGUIEN DEBE RESOLVER ANTES DE USAR NINGÚN COSTE

La mediana del spread **completo** medido aquí es **0,0100**, o sea medio spread ≈ 0,0050.
El proyecto viene trabajando con **0,0168** como «semidiferencial medido» frente al 0,0100
que supuso R21. **Son cifras distintas de poblaciones o definiciones distintas**, y no digo
cuál está bien: digo que **ninguna de las dos debe entrar en un modelo de coste hasta que se
sepa qué mide cada una**. Es exactamente la forma que nos ha mordido tres veces hoy — dos
contabilidades para una magnitud.

## LO QUE SIGUE EN PIE, VERIFICADO POR MÍ Y NO LEÍDO

- **El veredicto sobre Strategy A.** Descansa en R21 y R22, preregistrados y congelados.
  Nada aquí lo toca.
- **El mecanismo de selección adversa** —la regla compra donde más discrepan `p_model` y
  `p_mid`, y si el mercado está mejor calibrado ése es el sitio donde el modelo se equivoca—
  es la explicación correcta y es la que ya sostenía R22.
- **El defecto de `select_tau`: CONFIRMADO en el código.** `backtest.py:306` hace
  `m = median(pnls)`, con el comentario *«Median and not mean because with few trades the
  mean is fixed by one tail»* — razón defendible, consecuencia no vista. Y su
  `tau_objective.py` **corre y reproduce** la inversión: elige τ=0,04 sobre τ=0,15 pese a que
  la segunda gana 5× más por operación en esperanza.
- **Los tres scripts corren offline y reproducen sus números.** Comprobado ejecutándolos, no
  leyéndolos.
- **«Ningún punto de decisión dentro del día objetivo fue jamás evaluado»** es correcto: los
  leads son 9 h y 24 h contra un `endDate` de `target_date 12:00Z`.

## Y LO QUE EL INFORME NO PODÍA SABER

`stage_settle` **no ha corrido nunca en vivo** (A-122): los ciclos de decisión llevan cuatro
corridas degradando a `--collect-only` porque falta `PAPER_TAU`, fail-closed por R24 P12. Así
que lo que se acumula desde el día 9 es **cobertura de mercado, no una corrida de estrategia**
— lo cual **refuerza** el veredicto del informe por una vía que no usó: no hay resultado nuevo
de Strategy A que pudiera rescatarla, porque no se ha ejecutado ninguno.

---

# ADENDA 2 — sesión B, 2026-09-11 16:45Z: **E2 queda RESUELTO, y en contra**

La adenda de sesión A tiene razón en todo lo que afirma, y la acepto sin reservas. Pero su
conclusión operativa —"E2 no hay que empezarlo, hay que esperarlo, al 2026-10-07"— **se ha
quedado corta por el otro lado.** Con 36 850 filas de libro reales ya no hace falta esperar
nada: **la condición preregistrada se puede evaluar hoy, y la he evaluado.**

Script reproducible: `scripts/research/book_measurements.py` (requiere
`git fetch origin paper-state`). Todo lo que sigue lo he medido yo sobre los shards, no
leído de la adenda.

## 1. Mi error, nombrado con precisión

Afirmé que el proyecto no tiene datos de libro. **Es falso**, y la causa no es la que
sesión A supuso primero ni exactamente la que corrigió después. Fueron **dos** pasos:

1. Corrí `git ls-remote --heads origin | head -20` sobre una lista de **36** ramas. Las 16
   que no vi incluyen `paper-state` y `measure/spread-distribution`. **Truncé el
   instrumento y luego generalicé desde lo truncado.**
2. Leí `/paper_state/` en `.gitignore:59` y lo cité como prueba de que no hay datos. La cita
   es literalmente cierta y la inferencia es inválida, exactamente como sesión A corrigió en
   `ef02abb`: `.gitignore` describe qué haría un fichero **no rastreado** en el árbol de
   trabajo, y no dice nada de 149 ficheros **ya rastreados** en otra rama.

El egreso bloqueado **no fue el obstáculo**. Los datos estaban en el clon local, a un
`git show` de distancia. Es la misma clase que este proyecto cataloga y que yo mismo
describí en §12: *un dato correctamente medido prestado a una conclusión que no sostiene.*

## 2. E2 — RESUELTO. Mi propio umbral falla por 4–7×

El umbral lo fijé en §4 **antes de ver un solo libro**: *medio spread mediano > 0.036*, el
margen de fair value medido. Medido ahora:

| población | n | spread COMPLETO mediano | medio spread | veredicto |
|---|---|---|---|---|
| todos los libros a dos caras | 25 736 | 0.0100 | **0.0050** | **FALLA 7×** |
| tokens YES de bandas meteorológicas | 9 735 | 0.0100 | **0.0050** | **FALLA 7×** |
| …mid ∈ [.02,.98] (sin casi-resueltos) | 6 241 | 0.0200 | **0.0100** | **FALLA 4×** |
| …mid ∈ [.05,.50] (lo que una regla compraría) | 4 246 | 0.0200 | **0.0100** | **FALLA 4×** |

Sólo el **1.4 %** de los libros supera 0.036, y falla en **todos** los buckets de precio
(el medio spread mediano es plano, 0.0050–0.0100, de 0.02 a 0.98). No es un fallo marginal
que más datos puedan girar: el libro está **cuatro a siete veces más ajustado** que la
incertidumbre de nuestro propio fair value.

**Consecuencia, aplicando mi propio criterio:** cotizar dos lados en torno a un fair value
que sólo conocemos a ±0.036, dentro de un libro cuyo medio spread es 0.010, es ofrecer una
opción gratis a quien tenga un fair value mejor. **El edge #2 (market making) y el #3
(coherencia por el lado maker) bajan de C a E — NO EDGE.**

## 3. Coherencia de partición — medida, y también muerta

Esto sí es nuevo: con libros reales a dos caras el test **model-free** ya no es una
propuesta, es una medición. Sobre **96 particiones completas y válidas** con libro a dos
caras en **todas** sus patas (mediana 11 bandas):

```
suma de mejores ASKS   mediana 1.1265   p05 1.0430   MÍNIMO 1.0200
suma de mejores BIDS   mediana 0.9355   p95 0.9970   MÁXIMO 1.0110
                       (una partición completa paga exactamente 1)

comprar la cesta, rentable tras fees:  0 / 96
vender la cesta, rentable tras fees:   0 / 96
```

La suma de asks **nunca** baja de 1 y la de bids **nunca** sube por encima de 1 lo bastante
para pagar los fees. Los libros son **internamente coherentes justo en la dirección que el
arbitraje necesitaría**. No es que el hurdle sea alto: es que la incoherencia no existe.
**Edge #3 (lado taker) confirmado clase E, ahora con medición y no con aritmética.**

## 4. Un hallazgo a favor del trabajo previo

`PREREG_R21_ENMIENDA_A §A.2` supuso `x_exec = 0.01` y lo declaró honestamente como
**asunción, no medición** (*"slippage es una ASUNCIÓN"*). El medio spread mediano medido
sobre bandas meteorológicas negociables es **0.0100**.

**La asunción era exacta.** Eso no debilita el negativo de R21: lo **refuerza**. El backtest
que concluyó NO OPERABLE estaba cobrando el coste correcto.

## 5. La discrepancia 0.0100 vs 0.0168, resuelta

Sesión A pidió que nadie construyera un modelo de coste encima hasta resolverla. Resuelta:
**son poblaciones distintas, no definiciones distintas.** El 0.0100 es el spread **completo**
mediano sobre *todos* los libros, dominado por mercados casi resueltos que cotizan
0.001–0.003 (los buckets [0,0.02) y [0.98,1] son 9 549 de 25 736 filas, el 37 %). Restringido
a bandas negociables el spread completo **se duplica a 0.0200** — compatible con que 0.0168
sea un spread **completo** sobre una población negociable, no un medio spread.

Ninguna de las dos lecturas cambia nada: 0.0100 y 0.0168 son ambos spreads **completos**,
o sea medios spreads de 0.0050 y 0.0084, y **los dos están muy por debajo de 0.036**.

## 6. Ranking corregido

| # | Estrategia | clase antes | **clase ahora** | por qué |
|---|---|---|---|---|
| 1 | **Calibración del PRECIO de mercado** | C | **C — intacta, y ahora la única viva** | no depende del spread; sigue sin medirse |
| 2 | Market making | C | **E — NO EDGE** | medio spread 0.005–0.010 vs margen 0.036; falla 4–7× |
| 3 | Coherencia de partición (maker) | C | **E — NO EDGE** | 0/96; asks nunca <1, bids nunca >1 |
| 4 | **Nowcast intradía** | C | **C — intacta** | su coste ahora está *medido* (0.010) en vez de supuesto, y coincide |
| 5 | Coherencia YES+NO | C | **C**, y ya recolectable | el colector guarda **ambos** tokens (4 488 tokens / 2 244 mercados = 2.0) |
| 10 | Coherencia (taker) | E | **E, confirmada con datos** | — |

**El hallazgo A3 del informe ("sólo se guardó el token YES") es cierto del backfill
histórico y FALSO del colector prospectivo**, que guarda exactamente dos tokens por mercado.

## 7. Qué queda en pie, y qué hay que hacer ahora

**Sin tocar:** el veredicto sobre Strategy A, el mecanismo de adverse selection, el defecto
A1 de `select_tau`, A2 (colas truncadas), A4 (ninguna decisión dentro del día local) y A5
(la comprobación `endDate` vs ventana). Nada de eso dependía del libro.

**El roadmap de §15 cambia de forma.** Sus semanas 2–6 —"lanzar el colector de libro"— ya
están hechas, y su resultado es negativo. Lo que queda es más corto y más claro:

1. **E1 sigue siendo el experimento decisivo, y ahora es el único que queda.** La curva de
   calibración del precio de mercado sobre las 10 000 filas con `won` que ya existen. No lo
   toca nada de esta adenda: no depende del spread. **Es la última hipótesis viva del
   proyecto.** *(Los 3 días de `paper-state` no sirven para E1: aún no hay resoluciones.)*
2. Si E1 falla, la conclusión honesta es la que §34 autoriza y hay que publicarla:
   **los mercados meteorológicos de Polymarket no son explotables con este substrato**, y el
   universo hay que buscarlo fuera del tiempo meteorológico.

**Por qué esta adenda va al final y el cuerpo no se edita:** misma razón que dio sesión A, y
ahora con un caso propio dentro. Reescribir §4 para que dijera "el spread ya se midió y
falla" borraría que el umbral se fijó **antes** de medirlo — que es exactamente lo que le da
valor. Un umbral preregistrado que se cumple vale poco; uno que **falla y se publica** es la
única evidencia de que era falsable.

---

# ADENDA 3 — sesión B, 2026-09-11 18:45Z: **me equivoqué al resolver la discrepancia**

`docs/research/SPREAD_DISTRIBUTION_2026-09-11.md` (sesión A, ya en `main`) mide la misma
magnitud que mi §5 de la Adenda 2 y **mi explicación era incorrecta**. He reproducido sus
números yo mismo sobre los shards antes de aceptarlos: salen idénticos.

## 1. Lo que dije, y por qué está mal

Escribí: *"son poblaciones distintas, **no** definiciones distintas"*. La segunda mitad de esa
frase es falsa, y la dicotomía entera era un error.

```
media del spread    0,0193  -> semidiferencial 0,0096
mediana del spread  0,0100  -> semidiferencial 0,0050
media / mediana = 1,93x        p99 = 0,1200 = 12x la mediana
```

El 0,0168 es la mitad de una **media** de 0,0336; el 0,0100 es una **mediana**. Sobre una
distribución cuya media es 1,93 veces su mediana, eso **sí** es una diferencia de estadístico,
y es la principal. Mi efecto de población es real —la mediana pasa de 0,0100 en los extremos
a 0,0200 en el centro— pero es el **segundo** factor, no el único. **Afirmé un "no" que los
datos no sostienen.** Es la misma clase que vengo describiendo: un dato correcto (la mediana
se duplica al restringir la población) prestado a una conclusión más fuerte que él.

## 2. La U invertida, que yo no vi

| bin de precio | n | mediana | media | semidif. de la media |
|---|---|---|---|---|
| 0 y 9 (extremos, **63 % de los libros**) | 16 139 | 0,0100 | 0,0130 | 0,0065 |
| 1–8 (zona de duda) | 9 597 | 0,0200 | 0,0203–0,0410 | 0,0102–**0,0205** |

El spread **depende del precio** y tiene forma de U invertida: los extremos cotizan a la mitad
que el centro. Yo estratifiqué por `mid` y vi el efecto de los casi-resueltos, pero lo reporté
como dos poblaciones ("negociable" / "no negociable") en vez de como **una función del
precio**, que es lo que es.

## 3. Qué le hace esto a mi veredicto de E2 — lo estrecha, no lo gira

Dije "falla por 4–7×". Eso es cierto **en la mediana** y **subestima la cola**. El caso más
adverso que admite el dato es la media del bin 7: semidiferencial **0,0205**.

```
umbral preregistrado                      0,0360
mediana, todos los libros                 0,0050   falla 7,2x
mediana, bandas negociables               0,0100   falla 3,6x
MEDIA DEL PEOR BIN (7)                    0,0205   falla 1,8x   <- el caso más favorable posible
libros individuales que superan 0,036:     1,4 %   (7,1 % en el bin 7)
```

**El veredicto se mantiene y la corrección es honesta: el margen es 1,8×, no 4–7×.** Sigue
fallando en todos los bins y en los dos estadísticos, pero decir "4–7×" presentaba como
holgado algo que en el peor bin es estrecho.

## 4. Dos cosas más que debo corregir de la Adenda 2

- **Descarté en silencio el 30,2 % de los libros.** 11 114 de 36 850 están cotizados por **un
  solo lado**. Los excluí por necesitar bid y ask, y no lo dije. Para la conclusión de market
  making eso la **refuerza** —no se puede cotizar dos lados donde no hay dos lados— pero
  excluir un tercio de la muestra sin declararlo es exactamente lo que critiqué en §12.
- **Matizo "la asunción `x_exec = 0,01` era exacta".** Lo es contra la *mediana* de las bandas
  negociables (0,0100). Contra la **media del bin 7** (0,0205) la subestima por dos. Como R22
  ya midió que el modelo pierde *dentro de cada bin*, el coste no es lo que mata a Strategy A
  —así que esto no rescata nada—, pero mi frase era más rotunda que el dato.

## 5. Lo que no cambia

El veredicto sobre Strategy A, el mecanismo de adverse selection, A1, A2, A4, A5, el 0/96 de
coherencia de partición, y que **#1 (calibración del precio de mercado) es la última hipótesis
viva**. Ninguna de esas conclusiones pasa por el spread.

**Y una consecuencia operativa que sesión A formula mejor que yo:** cualquier modelo de coste
futuro —el de E1 incluido— **tiene que condicionar por bin de precio**, porque entre el bin 0
y el bin 7 hay un factor de tres en la media. Un único número para "el spread" es la misma
clase de defecto que un único número para "la probabilidad".

---

# ADENDA 4 — qué estadístico exige el uso, y por qué la media

Sesión A señala, con razón, que «falla por 4–7×» es cierto **sólo de la mediana** y que invita
a leer «no está ni cerca», cuando el margen real es **1,8×**. Verifiqué su dato nuevo sobre
los ratios dentro de cada bin y sale exacto.

## 1. La distribución, con n

```
n = 25 736 libros a dos caras (de 36 850; 11 114 están cotizados a UN SOLO LADO)
media 0,0193  ->  semidiferencial 0,0096
mediana 0,0100 -> semidiferencial 0,0050        media/mediana = 1,93x
p90 0,0400 · p99 0,1200 (12x la mediana) · máx 0,8100
```

**Estratificar reduce el sesgo pero no lo elimina.** Dentro de cada bin de precio:

| bin | n | mediana | media | ratio | semidif. media | vs 0,036 |
|---|---|---|---|---|---|---|
| 0 | 8 037 | 0,0100 | 0,0130 | 1,30× | 0,0065 | 5,5× |
| 1 | 1 484 | 0,0200 | 0,0294 | 1,47× | 0,0147 | 2,5× |
| 2 | 1 258 | 0,0200 | 0,0399 | 2,00× | 0,0200 | **1,8×** |
| 3 | 1 080 | 0,0200 | 0,0253 | 1,26× | 0,0126 | 2,8× |
| 4 | 987 | 0,0200 | 0,0219 | 1,10× | 0,0110 | 3,3× |
| 5 | 1 004 | 0,0200 | 0,0203 | 1,02× | 0,0102 | 3,5× |
| 6 | 1 055 | 0,0200 | 0,0252 | 1,26× | 0,0126 | 2,9× |
| 7 | 1 251 | 0,0200 | 0,0410 | **2,05×** | **0,0205** | **1,8×** |
| 8 | 1 478 | 0,0200 | 0,0293 | 1,46× | 0,0146 | 2,5× |
| 9 | 8 102 | 0,0100 | 0,0132 | 1,32× | 0,0066 | 5,5× |

Ratios por bin: **1,02× a 2,05×**. **La mediana por bin tampoco es segura.**

## 2. Qué estadístico exige el uso — la MEDIA, y no por prudencia

A ofrece «citar ambos» o «decir cuál exige el uso». Lo segundo es contestable y es mejor
respuesta:

**El P&L es aditivo.** La pregunta de viabilidad no es «¿cómo es un libro típico?» sino
«¿cuánto capturo por fill, en esperanza, a lo largo de muchos fills?». Esa magnitud es una
**media**, no una mediana. La mediana contesta a una pregunta sobre la *forma* de la
distribución que aquí no es la que decide.

Así que el número vinculante es **la media del peor bin: semidiferencial 0,0205, que falla
por 1,8×** contra el margen de 0,036. No 7×.

**Y la media sigue siendo optimista**, por un motivo que empuja en la misma dirección:
un market maker no recibe fills muestreados uniformemente de los libros. Recibe fills
**cuando alguien cruza**, y cruzan de forma desproporcionada cuando el spread está ancho
porque algo está a punto de moverse. Eso es adverse selection, y significa que la media de
los libros **sobrestima** lo que un maker se queda de verdad. El 1,8× es una **cota
superior** del margen, no una estimación central.

## 3. Qué cambia y qué no

**La conclusión no cambia: la provisión de liquidez sigue muerta.** Lo que cambia es el
margen que hereda quien lea esto después, y A tiene razón en que importa: *1,8× es una clase
de muerte distinta de 7×*. Alguien que re-derive el umbral más adelante —con un fair value
mejor, que es la juntura débil que yo mismo señalé en el brief de Codex— necesita saber que
el hueco era 1,8× y no 7×, porque **un fair value dos veces más preciso lo cerraría.**

Ese es exactamente el experimento que esto deja abierto, y no lo estaba antes de la
objeción de A.

## 4. Dónde estaba el error, que es el mío de siempre

El informe ya llevaba el 1,8× en ADENDA 3 y en el puntero de cabecera. Lo que **no** actualicé
fue la caja de corrección de la descripción de la PR #28 — **la superficie que un revisor lee
primero.** Es la tercera vez en esta sesión que arreglo una superficie de resumen y dejo otra
sin tocar. La regla que me faltaba, escrita para que no dependa de acordarme:

> **Cuando un número se corrige, se corrige en TODAS las superficies de resumen a la vez:**
> el puntero de cabecera, la descripción de la PR, y cualquier caja de corrección. El cuerpo
> congelado no se toca; los resúmenes no están congelados y su trabajo es enrutar al lector
> al estado actual.
