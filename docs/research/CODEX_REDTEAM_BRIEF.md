# Encargo para Codex — red team cuantitativo independiente

**Preparado por:** Claude (sesión B), 2026-09-11
**Para:** una sesión de Codex con acceso a este repositorio
**Por qué existe este fichero:** la sesión de Claude que lo escribe tiene el egreso de red
bloqueado por política (403 en CONNECT a `api.openai.com`, igual que a Polymarket), así que
**no puede invocar a Codex**. Este documento es el paquete de contexto para que lo lances tú.

**Cómo usarlo:** abre Codex en la raíz de este repositorio y pégale las secciones 0–3.
Las secciones 4–6 son el material que §4 del encargo pide entregarle y que **no vive en el
repositorio** — resultados negativos, números medidos y dónde falló el proceso.

---

## 0. Tu misión, y tu libertad

Eres un **red team cuantitativo independiente**. Tu trabajo no es revisar código: es
responder a una pregunta.

> **¿Existe alguna fuente de edge explotable en Polymarket que este proyecto no haya
> estudiado, modelado o probado?**

El objetivo único es **P&L neto positivo y sostenible después de costes, slippage, liquidez
y riesgo de ejecución.** No accuracy, no AUC, no Sharpe de un backtest ingenuo.

**No tienes ninguna obligación de defender, mejorar ni preservar nada de lo hecho aquí.**
Puedes concluir que la estrategia es mala, que el modelo es incorrecto, que los features son
irrelevantes, que el ML sobra, que el universo de mercados está mal elegido, que el horizonte
es incorrecto, que el backtest está mal planteado, que los datos son insuficientes, o que hay
que abandonarlo todo. Si crees que Claude está mirando en la dirección equivocada, **dilo
con esas palabras**.

Prohibido: inventar datos o resultados; llamar significativo a algo sin test; confundir
accuracy con rentabilidad; ignorar costes, liquidez o ejecución; usar información futura;
optimizar sobre el test set; presentar un único backtest como evidencia; defender el trabajo
previo por inercia.

## 1. Lo que tienes que producir

La estructura completa está en el encargo del usuario (PARTS I–X y las preguntas Q1–Q10).
Lo esencial, en orden de valor:

* **PART II — BLIND SPOTS:** las 10 áreas que Claude no ha explorado bien. *Esta es la parte
  por la que existe este encargo.*
* **PART III — 30+ hipótesis nuevas**, con mecanismo, datos, test y criterio de falsación.
* **PART VI/VII — qué construirías desde cero**, y la alternativa más radical que merezca la
  pena.
* **PART X — veredicto:** KEEP / MODIFY / DELETE / INVESTIGATE / BUILD NEXT.

Termina en **una decisión**, no en "hay ideas interesantes": evidencia suficiente → paper
trading; hipótesis prometedora → experimento X; sin evidencia → cambiar de dirección;
cuello de botella en datos → obtener dato X.

## 2. Verifícalo tú, no te fíes de este documento

Todo lo que sigue es lo que Claude cree haber establecido. **Compruébalo en código y datos.**
Dos afirmaciones de Claude ya han resultado falsas esta misma sesión (§6). Asume que hay más.

## 3. El repositorio, y dónde está de verdad cada cosa

```
src/weather_agent/        modelo, costes, backtest, settlement, as-of
scripts/run_r21.py        el backtest que produjo el veredicto NO OPERABLE
scripts/run_r22.py        el test de skill contra el mercado
scripts/research/         mis scripts reproducibles offline (ver abajo)
prereg/                   preregistros congelados
docs/research/            el informe de auditoría y el estudio de spread
artifacts/m2_quantiles.json   el ÚNICO artefacto de modelo versionado
```

**Ramas con datos — esto es lo que Claude tardó en encontrar y casi le invalida el informe:**

| rama | contenido |
|---|---|
| `paper-state` | **149 ficheros de datos reales.** 36 850 libros L2 (`clob_books_poll`, 09-09 a 09-11), 26 440 filas de precio, 1 100 mercados, 2 200 outcomes. **Cero resoluciones** (`winning_outcome` NULL en los 1 100) |
| `research/modelsel-artifacts` | `M2_PREREG_CHAIN.md` — el estado real de las versiones v1/v2/v3 del modelo de error |
| `measure/spread-distribution` | el estudio de distribución de spread |

**Lo que NO está en el repositorio y necesitarás:** el DuckDB de producción en la máquina
Hetzner. Contiene 16 165 636 filas de precio, 84 451 mercados con schedule de fees, 6 143
mercados meteorológicos con token priceado, y **las ~10 000 filas con resultado realizado**
que son el único substrato con el que se puede medir calibración. **Sin él no puedes
reproducir R21 ni R22 ni correr E1.** Pídeselo al usuario.

---

## 4. Qué se construyó y qué se midió — incluidos TODOS los negativos

### La estrategia (Strategy A)
Mercados de temperatura máxima diaria en ~55 estaciones. Bandas de 1 °F o 1 °C que forman
una partición exhaustiva. Se toma un pronóstico público (ICON seamless vía Open-Meteo), se
le añade una distribución de error empírica (M2), se obtiene `p_weather` por banda, y se
compra el token YES cuando `p_weather − p_market` supera un umbral. Long-only. Hold to
resolution. Tamaño: 1 acción.

### Los dos resultados preregistrados — ambos negativos

**R21** (backtest walk-forward, congelado antes de existir un P&L):
```
candidatos 10 000 · trades 468 sobre 211 eventos
mediana P&L/trade  -0.0236        criterio: >0     FALLA
tasa de acierto     0.0556  contra base rate 0.0744
leave-one-station  negativo en las 47             FALLA
sin el mes mayor   -0.0184                        FALLA
con x_exec = 0 (ejecución gratis)  sigue -0.0131
Brier: modelo 0.05191 · mercado 0.04215 · base 0.06801
VEREDICTO: NO OPERABLE CON ESTE SUBSTRATO
```

**R22** (locus de skill, block bootstrap por evento):
```
10 000 filas · 1 308 eventos · 10 estratos que estratifican de verdad
TODOS con Delta < 0 · 15/17 celdas con |Delta| > 2 x SE
BSS global del modelo +0.238
BSS DENTRO de cada bin de precio: -0.547, -0.117, -0.023, -0.091, -0.234
VEREDICTO: EL MODELO NO GANA AL MERCADO EN NINGÚN ESTRATO
```

**La descomposición es el hallazgo:** condicionado al precio, el modelo **no aporta
información**. Su skill global es un efecto *entre* bins que el precio ya contiene, porque el
precio *es* el bin. El mecanismo es **adverse selection**: la regla compra donde más discrepa
del mercado, y si el mercado está mejor calibrado, ahí es donde el modelo se equivoca.

### Modelo de error M2 — tres versiones, dos retiradas
* **v1** RETIRADA: la muestra dependía de la variable de sesión `TimeZone` de DuckDB (2 599
  filas en UTC, 1 881 en Asia/Shanghai) y el corte walk-forward **fugaba en 8/8 estaciones**,
  de −9 h a −43 h.
* **v2** en producción, pero marcada NO APTA por B-11.
* **v3** (shift por estación con shrinkage) **falló su propio criterio preregistrado**: 6 de
  46 estaciones contra un umbral del 70 %. **La correlación del sesgo por estación entre
  mitades del periodo es +0,080** — un shift aprendido del pasado se aplica al futuro como
  ruido. Código conservado en `error_model.py` bajo `WITHDRAWN`.

### Lo que midió esta sesión (todo reproducible offline)
```
scripts/research/gate_arithmetic.py    la puerta de señal casi no abre, y NO por los costes:
                                       hueco exigido = 74 % margen del modelo, 17 % slippage,
                                       9 % fees. El mercado debe estar 17-83 % barato.
scripts/research/partition_arb.py      hurdle de la cesta de partición (taker N=9: S<=0.8656)
scripts/research/tau_objective.py      el objetivo del walk-forward ordenaba por precio del
                                       billete, no por valor esperado
scripts/research/book_measurements.py  SOBRE LIBROS REALES: medio spread mediano 0.0050
                                       (0.0100 en bandas negociables, 0.0205 en la media del
                                       peor bin) contra un margen de fair value de 0.036.
                                       Falla por 1.8x en el mejor caso. Y coherencia de
                                       partición rentable en 0 de 96.
scripts/research/run_e1.py             la última hipótesis viva, congelada y con self-test
docs/research/SPREAD_DISTRIBUTION_2026-09-11.md
                                       el spread es una U invertida en el precio; media/mediana
                                       = 1.93x; 30.2 % de los libros están cotizados a UN LADO
```

### Costes, medidos y confirmados
`fee = 0.05 · p · (1−p)`, **sólo taker**, `rebateRate = 0.25` (el venue **paga al maker**).
`PREREG_R21` supuso `x_exec = 0.01` declarándolo asunción; el medio spread mediano medido en
bandas negociables es **0.0100**. **La asunción era correcta** — refuerza el negativo de R21.

## 5. Lo que Claude ya descartó, con medición, para que no repitas trabajo

| hipótesis | clase | por qué |
|---|---|---|
| Strategy A (pronóstico público vs precio) | **D — FALSE EDGE** | R21 + R22 |
| ML sobre features meteorológicas públicas | **E — NO EDGE** | R22 mata la familia: el insumo es público |
| Market making sobre este fair value | **E** | medio spread 0.005–0.0205 vs margen 0.036 |
| Coherencia de partición, lado maker | **E** | idem |
| Coherencia de partición, lado taker | **E** | 0 de 96 particiones rentables |
| Calibración del PRECIO de mercado | **C — la única viva** | `prereg/PREREG_E1_MARKET_CALIBRATION.md`, sin correr |
| Nowcast intradía | **C — sin estudiar** | ningún punto de decisión dentro del día local fue evaluado nunca |
| Latencia de actualización de forecast | **C — sin estudiar** | |
| Coherencia YES+NO | **C — ahora recolectable** | el colector prospectivo guarda ambos tokens |

**Ataca esta tabla.** En particular: los descartes de market making y coherencia se apoyan en
**3 días** de libros (09-09 a 09-11) y en un umbral (0.036) que es el margen del modelo
*retirado*. Si el fair value viniera de otro sitio, el umbral sería otro y la conclusión
podría cambiar. Claude no exploró esa vía.

## 6. Dónde falló el proceso — dos veces, esta misma sesión

Te lo doy porque es donde más probable es que haya más:

1. **Claude afirmó que el proyecto no tenía datos de libro de órdenes. Era falso.** Corrió
   `git ls-remote --heads origin | head -20` sobre una lista de **36** ramas, y luego
   generalizó desde la lista truncada. Además citó `/paper_state/` en `.gitignore` como
   prueba: literalmente cierto e inferencia inválida — `.gitignore` gobierna ficheros **no
   rastreados**, y había 149 ficheros **ya rastreados** en otra rama.
2. **Al medir esos datos, explicó mal una discrepancia.** Dijo "poblaciones distintas, **no**
   definiciones distintas". Era sobre todo media contra mediana (1,93×). Afirmó un "no" que
   los datos no sostenían.

**La clase de error es la misma en ambos: un dato correcto prestado a una conclusión más
fuerte que él.** Búscala por todo el repositorio, incluidos los informes de auditoría.

## 7. Defectos conocidos y su estado

| id | defecto | estado |
|---|---|---|
| A1 | `select_tau` optimizaba la mediana → ordenaba por precio del billete | **corregido** en PR #33 (media recortada; la mediana sigue seleccionable para reproducir R21) |
| A2 | las colas de la distribución se truncaban a ±1 grado, masa cero más allá | **corregido** en PR #33 (cola exponencial con escala tomada de los datos) |
| A3 | el backfill histórico sólo guardó el token YES en los 6 143 mercados | **abierto** — impide el lado corto y el test YES+NO |
| A4 | ningún punto de decisión **dentro** del día local objetivo fue evaluado | **abierto** — es el hueco más grande |
| A5 | `endDate = target_date 12:00Z` vs ventana `LOCAL_CIVIL_DAY`: para estaciones al oeste el fin declarado del mercado **precede** al cierre de su ventana de medición | **SIN VERIFICAR** — si se confirma, afecta a toda fila de R21/R22. Necesita el DuckDB. **Empieza por aquí.** |
| A6 | `available_at` de observaciones es el instante de descarga; el lag de 24 h es supuesto | abierto, declarado |
| A7 | `discovered_at` NULL en 10 000/10 000 → eje de edad de mercado inutilizable | abierto |

## 8. Las preguntas donde Claude cree que está el hueco

No son instrucciones: son las direcciones donde Claude **sabe que no ha mirado**. Ignóralas
si ves otras mejores.

1. **Predecir el error del mercado en vez del resultado.** Todo el proyecto modela
   `P(evento)`. Nadie ha intentado `P(el mercado está mal valorado)` ni `retorno futuro`.
   R22 dice que lo primero no funciona; **no dice nada de lo segundo**.
2. **El ciclo de vida del mercado.** `discovered_at` está NULL en todo, así que la edad de
   mercado nunca se pudo evaluar. Los primeros minutos tras la creación son un agujero total.
3. **Order flow y microestructura dinámica.** Hay 36 850 libros pero **nadie ha mirado
   series temporales** de imbalance, reposición, cancelaciones o impacto.
4. **El grafo cross-market.** Sólo se probó la coherencia *dentro* de un evento (las bandas de
   una ciudad-día). Entre ciudades, entre fechas, y contra mercados no meteorológicos: nada.
5. **Fuera del tiempo meteorológico.** Todo el proyecto asume mercados de temperatura. El
   universo de Polymarket es mucho mayor y **nunca se comparó la eficiencia por categoría**.
