# R21 — RESULTADO NEGATIVO: no existe umbral de edge operable con este sustrato

**Fecha:** 2026-09-09 · **Sesión:** B · **Preregistro:** `PREREG_R21_BACKTEST_TAU.md`
sha `464226a3…` + `PREREG_R21_ENMIENDA_A.md` sha
`3c7d9b1301798783bb3259e2dc1cc96a8856493cfb12efc41855d895d50fae2f`, **los dos congelados antes
de calcular ningún PnL.**

**VEREDICTO: LA ESTRATEGIA NO ES OPERABLE CON ESTE SUSTRATO.** §5 declaró este desenlace por
adelantado y se publica tal cual. No se han probado umbrales alternativos, no se ha relajado el
margen, no se ha ampliado la rejilla.

---

## 0. Que el preregistro se congeló antes, y cómo se comprueba

La enmienda §0 registró el estado del sustrato en el instante del hash:

```
backtest_results  0 filas      signals       0 filas
predictions       0 filas      paper_trades  0 filas
```

Nada que ver. La enmienda **no cambió ningún umbral**: fijó las cuatro constantes que §1–§4
habían dejado en prosa y sin las cuales el backtest no se puede ejecutar de una sola manera.
Las cuatro, y el criterio con el que se eligieron:

| constante | valor | por qué ése |
|---|---|---|
| `x_exec` | **1 punto**, el peldaño más adverso de D19 | no hay book histórico: `orderbook_snapshots` vacía y los 16 165 636 precios son `MIDPOINT_ESTIMATED`. El deslizamiento es un **supuesto**, y un supuesto sobre lo no medido no puede ser lo que fabrique un resultado positivo |
| el coste | **dentro** de `edge_net`; el umbral se compara sólo contra el margen | aplicar además `tau_costes` restaría el coste dos veces — el defecto que la sesión A encontró en su R24 v2 |
| τ en °F | **×9/5, sin +32** | es una **diferencia**. Sumar el desplazamiento movería la distribución 18 grados y llevaría el margen a ≈1 en toda banda estrecha. Misma familia que B-7 |
| la etiqueta | `winning_outcome` del venue, sólo `resolved` | es lo que **pagó**. Auditada contra IEM: 382/410 concuerdan (0,932) |

## 1. Los cuatro criterios de §4

```
candidatos            10 000    5 719 mercados × 2 leads − 1 438 sin insumo as-of
pasan ejecución        1 139    edge_net > margen de calibración
operaciones tomadas      468

§4.1  n >= 100                        468       CUMPLE
§4.2  mediana del PnL neto > 0     −0,0236      FALLA
§4.3  signo sobrevive LOO estación negativo en las 47   FALLA
§4.4  signo sobrevive sin el mes mayor  −0,0184  FALLA
```

**§4.1 se cumple, y eso importa:** el resultado es **EVALUABLE**, no vacío. Un backtest con
cero operaciones habría cumplido §4.2, §4.3 y §4.4 por cuantificación sobre el vacío, que es el
defecto que la sesión A encontró en su propia R24 v1 y que §4.1 existe para bloquear.

## 2. No es que no haya ventaja: hay selección negativa

```
tasa de acierto de lo tomado          0,0556
tasa base de los 10 000 candidatos    0,0734
tasa base del universo de mercados    0,0744     (457 ganadores de 6 143)
```

La comparación que decide es la primera contra la segunda: **la tasa base del conjunto de
candidatos**, porque es el conjunto del que la regla podía elegir. Contra el universo entero de
mercados sería comparar con oportunidades que la regla nunca tuvo delante.

**La estrategia acierta menos que elegir al azar dentro de su propio conjunto de
oportunidades.** Eso no es ausencia de señal: es señal con el signo cambiado en el régimen en
el que opera.

## 3. La causa, medida — y no es la que parecía

### 3.1 Sobre lo TOMADO, `p_model` parece catastrófica

```
p_model ∈ [0,1 · 0,2)   n=105   predice ~0,15   REAL 0,019
p_model ∈ [0,2 · 0,3)   n=199   predice ~0,25   REAL 0,010
p_model ∈ [0,3 · 0,4)   n=119   predice ~0,35   REAL 0,084
```

Esos tres cubos son el 90 % de lo tomado. Es la lectura fácil, y **es la lectura equivocada.**

### 3.2 Sobre los 10 000 candidatos, `p_model` está BIEN calibrada

```
             TODOS los candidatos            de ellos, los TOMADOS
cubo          n     real                      n     real
[0,1 · 0,2)  1439   0,1209                   105   0,019
[0,2 · 0,3)   930   0,2215                   199   0,010
[0,3 · 0,4)   390   0,3026                   119   0,084
[0,4 · 0,5)    48   0,3125                    23   0,130
[0,5 · 0,6)    25   0,5200                     9   0,111
[0,9 · 1,0)    81   0,9877                     3   1,000
```

**En el mismo cubo `[0,2 · 0,3)`, el universo entero realiza 0,2215 y lo que la estrategia
eligió realiza 0,010: un factor de 22 dentro de una sola celda de calibración.**

El modelo no está roto. **Lo que está roto es la regla que elige dentro de él.**

### 3.3 Y el mercado es mejor que el modelo, que es la razón de fondo

```
Brier  p_model   0,05191
Brier  mercado   0,04215     ← mejor
Brier  tasa base 0,06801     (0,0734)
```

Los dos baten a la tasa base, así que `p_model` **tiene** habilidad. Pero **el mercado tiene
más.** Y ahí está el mecanismo completo, en una frase:

> La regla opera donde `p_model` más se separa de `p_mid`. Si el mercado está mejor calibrado
> que el modelo, el sitio donde más discrepan es el sitio donde **el modelo** se equivoca. El
> «edge» que la estrategia mide es, sistemáticamente, su propio error.

Eso es selección adversa contra una contraparte mejor informada, y explica el factor 22 y la
tasa de acierto por debajo del azar. Ningún umbral lo arregla: **subir `tau` selecciona con más
fuerza sobre el mismo criterio equivocado**, que es exactamente lo que se observa cuando el
walk-forward se pega al techo de la rejilla (§4) y aun así pierde.

*(Los cubos `[0 · 0,1)` dan ratios de 3,5x y 5,8x en las dos tablas. Es un artefacto de comparar
contra el centro del cubo 0,05 cuando la masa está en 0,001–0,02, y no se usa como evidencia.
La comparación sólida es el Brier y el contraste tomado/todos.)*

### 3.4 Un defecto real, localizado, pero secundario

Al perseguir la hipótesis equivocada apareció algo que sí hay que arreglar.
`quantiles_to_distribution` extiende las colas **linealmente a lo largo de un grado** más allá
de p10/p90 y asigna cero después. Contra la distribución empírica del error de M2:

```
                       constructor   empírico   ratio
entero p50−1  lead  9     0,1585      0,1767    0,90x
entero p50−2  lead  9     0,0968      0,0408    2,37x
entero p50−3  lead  9     0,0000      0,0171    truncada
entero p50−2  lead 24     0,0990      0,0564    1,76x
entero p50−3  lead 24     0,0000      0,0230    truncada
```

**Sobrecarga la cola cercana ×1,8–2,4 y trunca a cero la lejana**, donde la realidad tiene un
2 %. Es la fuente de la discrepancia con el mercado en la región barata, así que **alimenta** la
selección adversa; pero explica un factor 2 y el fenómeno es de 22. Se declara como defecto a
corregir y **no** como la causa del fallo.

### 3.5 Adenda tras refutación de la sesión A: el `n` efectivo es de EVENTOS, no de filas

A objetó, con razón, que las bandas de un mismo evento **no son independientes**: forman una
partición que suma 1, así que si el pronóstico se equivoca en un evento se equivoca en todas sus
bandas a la vez y en direcciones acopladas. Tratar 468 filas como 468 observaciones
independientes **sobreestima la precisión**. Medido:

```
operaciones                468
eventos distintos          211        ← el n efectivo
pares (evento, lead)       301
operaciones por evento     mediana 2 · máximo 8

mediana observada                        −0,0236
IC 95 % bootstrap por BLOQUES de evento  [−0,0288 · −0,0205]
IC 95 % ingenuo por fila                 [−0,0275 · −0,0210]   ← demasiado estrecho
```

**El intervalo correcto es más ancho, y NO cruza cero.** La objeción era válida, la corrección
era necesaria y **el signo de §1 sobrevive**. Se registra así, con el intervalo agrupado, y no
como si el `n` fuera 468.

### 3.6 Adenda: `x_exec = 0,01` NO era el peldaño más adverso, y R21 perdió con un coste OPTIMISTA

§A.2 fijó `x_exec` en «el peldaño más adverso de la escalera de D19» y lo justificó como el
supuesto que no puede fabricar un resultado positivo. **Medido después por la sesión A sobre el
book real de 27 tokens operados en vivo** —el book que R21 no tenía—:

```
spread observado   medio 0,0336   (mín 0,003 · máx 0,09)   →   medio spread ≈ 0,0168
x_exec de R21                                                                0,0100
```

**El coste real de cruzar es un 68 % mayor que el que este backtest aplicó.** El veredicto no
cambia y de hecho se refuerza: **la estrategia perdió con un supuesto de coste optimista**, y con
el spread medido perdería más. Pero la **afirmación** de §A.2 —que 0,01 era lo más adverso—
**era falsa de hecho**, y se corrige aquí en vez de dejarla en pie porque la conclusión no
dependía de ella. Lo que sí queda intacto es el razonamiento: elegir el peldaño más adverso
*disponible* seguía siendo lo correcto sin book, y la escalera de sensibilidad (§4) muestra que
ni siquiera con ejecución gratuita cambia el signo.

### 3.7 Adenda: la evidencia está CONCENTRADA en pocas fechas — declarado, y el signo aguanta

Persiguiendo un hallazgo de la sesión A sobre el agrupamiento de bandas, medí la concentración
temporal de este backtest y es mayor de lo que ninguno de los dos suponía:

```
468 operaciones · 211 eventos · sólo 37 FECHAS
las 5 fechas mayores acumulan 356 de 468 operaciones = 76,1 %
```

**Y la causa es mi propio backfill, no el mercado.** La fracción de bandas cotizadas por evento
es netamente **bimodal**: de 1 464 eventos, **869 tienen ~10 % de sus bandas y 436 las tienen
todas**; sólo 159 quedan en medio, y **el 89,1 % está en un extremo o en el otro**. Con huecos
repartidos al azar y 11 bandas por evento, la fracción de eventos completos sería
`0,383¹¹ ≈ 0,003 %`, y es **29,8 %**. Eso no es una propiedad del venue: es la firma de un
backfill hecho en dos pasadas, una que muestreó mercados y otra `--complete-events` que completó
un subconjunto. **Mis regímenes «completo» e «incompleto» son esas dos pasadas, no dos muestras
de una misma población**, y ninguna de sus tasas se generaliza.

**Comprobado qué le hace eso al resultado**, porque eventos de una misma fecha comparten régimen
sinóptico y por tanto **no son bloques independientes**:

```
bootstrap por bloques de EVENTO (el publicado, 211 bloques)   [−0,0288 · −0,0205]
bootstrap por bloques de FECHA  (más conservador, 37 bloques) [−0,0270 · −0,0205]
leave-one-DATE-out sobre las 37 fechas: mediana máxima −0,0231
```

**Ninguno cruza cero y el signo sobrevive a excluir cualquier fecha.**

**Pero la sesión A objetó, con razón, que el leave-one-date-out es débil cuando cinco fechas
dominan:** quitar la mayor elimina ~15 % del dato, así que el estimador apenas puede moverse y el
resultado dice poco. Y añadió el matiz que lo cierra: *la estabilidad de la mediana es también lo
que se esperaría si el `n` efectivo fuera 5*, así que **no distingue las dos hipótesis**. El
estadístico que sí las distingue es la **mediana por fecha, las 37**:

```
fechas con mediana NEGATIVA   37 / 37
fechas con mediana POSITIVA    0 / 37
test de signo, H0 simétrica en 0:   p = 7,3 × 10⁻¹²

las 5 grandes (n=356)   medianas −0,0273 · −0,0262 · −0,0168 · −0,0309 · −0,0178
las otras 32 (n=112)    32 negativas, 0 positivas · mediana de las medianas −0,0350
```

**R21 no descansa en cinco días: pierde en los treinta y siete que miró, de abril a julio.** La
concentración afecta a la **anchura del intervalo**, no al **signo**, y con esto la limitación se
escribe en su versión fuerte en vez de la débil.

**RETIRADO por una segunda objeción de A, y con razón:** una versión anterior de este párrafo
decía que las fechas pequeñas pierden *más* (−0,0350 frente a −0,0262) y que por tanto «la
concentración, si acaso, diluye el resultado». **Eso es más de lo que el dato aguanta.** Medido:

```
fechas grandes (n > 5)   7 fechas, 409 operaciones · dispersión de sus medianas 0,0056
fechas pequeñas (n <= 5) 30 fechas,  59 operaciones · dispersión de sus medianas 0,0270
                                     media 2,0 operaciones por fecha ·  4,8× más ruidosas
```
Una mediana sobre **dos** operaciones no se compara en nivel con una sobre setenta. **Lo que
aguanta es el SIGNO unánime** —`0,5³⁰ = 9,3 × 10⁻¹⁰` sólo entre las pequeñas— y no la comparación
de magnitudes. La conclusión no cambia; la frase que la sobrepasaba, sí.

#### Y una decisión preregistrada que se valida sola — no es anécdota, es el método funcionando

**Siete de las 37 fechas tienen PnL TOTAL positivo y las 37 tienen mediana negativa.**

La media la fijan unos pocos ganadores grandes. §3 del preregistro eligió la **mediana** y no la
media con esta justificación exacta —*«con pocas operaciones la media la fija una cola»*—
**escrita antes de ver un solo resultado**. Si esta corrida se hubiera evaluado por la media, siete
días habrían parecido rentables y el agregado habría sido discutible. **Es el único punto de todo
el proyecto en el que una elección congelada a ciegas se demuestra necesaria a posteriori**, y por
eso se registra aquí como validación del procedimiento y no como curiosidad.

**Se declara igualmente la concentración**, porque un lector merece saber que **el 76 % de las
operaciones viene de cinco días** —exactamente los que el backfill completó— aunque ahora sepamos
que el signo no depende de ellos.

## 4. Dos pretextos cerrados por adelantado

**No es el deslizamiento.** La escalera de sensibilidad, que §A.2 prohíbe como métrica de
decisión y aquí sólo describe:

```
x_exec = 0,01 (primario)  n=468  mediana −0,0236
x_exec = 0,005            n=460  mediana −0,0184
x_exec = 0,001            n=463  mediana −0,0142
x_exec = 0     (gratis)   n=463  mediana −0,0131
H2_1000bps_full           n=549  mediana −0,0253
H3_double_H1              n=508  mediana −0,0258
```

**Ni siquiera con ejecución gratuita el signo cambia.** El resultado negativo no es un artefacto
de mi supuesto adverso.

**Tampoco es «un tau mayor».** El walk-forward eligió `tau_signal = 0,20` —**el máximo de la
rejilla congelada de §3**— en **239 de 271** decisiones. El optimizador quería ser más estricto
de lo que el preregistro le permitía y aun así perdió. **No se amplía la rejilla ahora**: §6 lo
prohíbe y hacerlo tras ver el resultado sería elegir el criterio a partir del resultado.

## 5. El sesgo de la etiqueta, acotado en dinero

La sesión A preguntó cuánto vale en PnL el 6,8 % de discrepancia entre la etiqueta del venue y
la derivada de observaciones. Sobre las **mismas 468 operaciones**, al mismo coste:

```
etiquetas discrepantes      4 de 468 = 0,85 %
mediana con venue     −0,023600
mediana con IEM       −0,023600      IDÉNTICA
total venue −2,805 · total IEM −0,805 · diferencia +2,00 USDC (+0,0043/op)
dirección: 3 «IEM gana / venue pierde» · 1 al revés
```

**El sesgo habría hecho parecer la estrategia mejor y no habría cambiado el veredicto.**

Y el matiz que hay que declarar junto al 6,8 %: **es una cota superior medida donde la etiqueta
es más frágil.** Se midió sobre las bandas **ganadoras**, que están pegadas al valor realizado
y donde un error de un grado decide. Las bandas que la estrategia compra están lejos, así que
las dos etiquetas coinciden en que perdieron. El 6,8 % describe la fragilidad de la
resolución; **no es la tasa que contamina un PnL**.

## 6. Integridad

| Comprobación | Estado |
|---|---|
| Preregistro y enmienda congelados y hasheados antes de calcular | **SÍ** |
| Sustrato de resultados vacío en el momento del hash | **SÍ** — cuatro tablas a 0 |
| Umbrales, margen o rejilla cambiados tras ver el resultado | **NO** |
| `tau_exec` evaluado al precio cotizado | **NO** — `x_exec` adverso, y el 0 sólo como columna |
| Coste restado dos veces | **NO** — vive dentro de `edge_net`, y hay test |
| Calibración agregada usada para el margen | **NO** — dispersión entre estaciones, §2 |
| Entrenamiento con etiquetas no disponibles aún | **NO** — filtro por `label_available_at`, con test |
| R21.2 intentada tras el fallo | **NO** — §5 lo prohíbe hasta publicar esto |
| Dinero real | **NO** — gate D0 intacto |

## 7. Qué haría falta, y que no se hace ahora

Cada una exige su propio preregistro y ninguna se intenta antes de publicar este resultado:

- **Una regla de selección que no sea «operar donde más discrepo del mercado».** Es el factor
  dominante (§3.3) y es un problema de **diseño**, no de estimación. Mientras el Brier del
  mercado sea mejor que el del modelo, esa regla compra el error propio, y **ningún umbral la
  arregla porque el umbral aprieta sobre el mismo criterio.** Lo que haría falta es un criterio
  que identifique *dónde* el modelo es mejor que el mercado, no *cuánto* discrepa de él — y eso
  es una pregunta que este sustrato aún no ha contestado.
- **Un constructor de distribución con colas ajustadas al error empírico** en vez de lineales a
  un grado (§3.4). Defecto real y localizado; afecta a todo lo que consuma `weather_prob`,
  incluida la corrida en papel de la sesión A.
- **Más periodo.** El archivo deslizante de Single Runs no se recupera hacia atrás (B-1).

## 8. Limitaciones heredadas que este informe repite

`p_model` peor calibrada por mercado que en agregado y **no corregible** (B-12) · disponibilidad
de etiqueta **supuesta** a 24 h (B-4/D17) · `y` es cota inferior por muestreo horario, y el
sesgo está **concentrado**: 32 de 45 estaciones no fallan ninguna vez y cinco cargan el 71 % ·
la tasa de discrepancia depende de la **anchura de la banda** tanto como del sensor (9,7 % en
bandas de un entero en °C, 2,0 % en dos enteros en °F) · 399 de los 410 eventos auditables son
de abril y mayo, así que la tasa está medida **fuera de la estación** en la que se aplicaría ·
**evidencia concentrada: 37 fechas, con el 76 % de las operaciones en cinco (§3.7), y una
completitud de eventos bimodal por construcción del backfill** · periodo abril–septiembre 2026
acotado por el archivo deslizante · coordenadas verificadas en 11
de 55 (D6) · 1 936 mercados en décimas fuera del universo · **sólo lado largo en YES**: el token
con precio es el YES en los 6 143 mercados y de la pata NO no existe serie · no transportable a
leads > ~45 h (D2).
