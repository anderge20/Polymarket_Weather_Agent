# PREREG_R22 — ¿dónde, si en algún sitio, bate el modelo al mercado?

**Sesión:** B · **Congelado:** 2026-09-09, **antes de calcular ningún Brier.**
**v4.** v1 la refutó A (tres bloqueantes). v2 la congelé yo demasiado pronto y **queda RETIRADA
por incompleta**: A encontró después un umbral mejor derivado, un `MIN` mal dimensionado, tres
ejes que faltaban y una regla de reporte. Se adoptan todos. **v3 queda RETIRADA por INEJECUTABLE**, y el motivo es mío y no de A: su §5
decía «se baraja la asignación de EVENTOS A CELDAS», y con ejes **marginales** eso no está
definido — la celda a la que pertenece un evento la determinan sus propios atributos (lead,
unidad, posición de banda…), así que reasignar eventos a celdas cambiaría lo que las celdas
*son*. Lo descubrí al implementarlo, no al ver resultados. **Sigue sin haberse calculado ningún
Brier**, así que retirar y recongelar no contamina nada — es la misma disciplina con la que M2
v1 dio paso a v2, y se hace explícita en vez de editar v2 en silencio.

**Tres premisas verificadas ANTES de rediseñar, como A exigió:**
1. **El eje de spread del libro es IMPOSIBLE con este sustrato.** `orderbook_snapshots` tiene
   **0 filas** y los 16 165 636 precios son `MIDPOINT_ESTIMATED`. Era la mejor idea de A —mirar
   donde la hipótesis dice que el modelo tendría más posibilidades— y **no se puede evaluar**.
   Queda declarado como el hueco que impide fortalecer la rama negativa, no omitido.
2. **Mi preocupación por el desbalance temporal era INFUNDADA, y A tenía razón en mandarme
   medirla.** Por eventos el periodo está repartido: abril 245 · mayo 300 · junio 294 · julio
   293 · agosto 236. El 399/410 era del sustrato de *sesgo de etiqueta*, no de éste. Por filas
   sí hay desbalance (2 629 mercados en abril contra 354 en junio), pero **la unidad de R22 es
   el evento** (§1), así que la partición temporal es legítima.
3. **`MIN_EVENTOS = 100` deja el eje de ESTACIÓN con una sola celda** (EGLC, 163 eventos; sólo
   4 estaciones llegan a 30). Se mantiene el 100 —es el número del adversario, no uno elegido
   por mí para que sobreviva algo— y **el eje de estación se declarará INSUFICIENTE casi
   entero**. Que un eje resulte no evaluable es un resultado, no un fallo, y se publica.

## 0. La pregunta, y lo que su respuesta autoriza a decir

R21 midió que la regla «operar donde `p_model` más se separa de `p_mid`» pierde, y por qué: el
Brier del mercado (0,04215) bate al del modelo (0,05191), así que donde más discrepan es donde
el modelo se equivoca. La tentación es proponer otra regla. **Sería el ciclo de probar
estimadores hasta que uno pase**, prohibido desde M2 v3. Aquí **no se propone ninguna regla:**

> **¿Existe algún estrato identificable EX ANTE en el que `p_model` bata a `p_mid` en Brier,
> fuera de muestra y de forma estable?**

**LA ASIMETRÍA ES DELIBERADA Y SE ESCRIBE ANTES (bloqueante 3 de A):**

- **Un resultado NEGATIVO es fuerte** y basta para no preregistrar R21.2.
- **Un resultado POSITIVO NO es un hallazgo.** Es sólo un **candidato** sobre el que
  preregistrar otra cosa. Brier mide calibración y resolución sobre **toda** la distribución; el
  beneficio depende del signo y el tamaño del error de precio **en las bandas que se operan**,
  neto de la fee D19 y del recorrido del book. Un estrato puede tener mejor Brier y perder
  dinero. **Condición necesaria, nunca suficiente**, y el día que una celda salga positiva esta
  frase es la que hay que releer.

**Y lo que un negativo NO autoriza a decir** (auto-refutación de B, anterior a la de A): mi
primera redacción afirmaba que ningún método largo *podría* funcionar. **Falso.** El Brier es un
promedio y el beneficio vive en un subconjunto elegido; un modelo con peor Brier global puede
identificar un nicho rentable. Un negativo autoriza exactamente esto: *sobre los estratos
declarados no aparece la habilidad que una regla larga necesitaría, y quien afirme lo contrario
tendrá que nombrar el estrato.*

## 1. La unidad de observación es el EVENTO — bloqueante 2 de A

Las bandas de un evento forman **una partición que suma 1**: si el pronóstico falla en un
evento, falla en todas sus bandas a la vez y en direcciones acopladas. Tratar filas como
observaciones independientes sobreestima la precisión.

- Todo intervalo, test y remuestreo va **agrupado por evento** (bootstrap por bloques sobre
  eventos, jamás sobre filas).
- El `n` que se reporta en cada celda es **de eventos**, y también se reporta el de filas.
- Ya verificado sobre R21: 468 operaciones eran **211 eventos**, y el intervalo agrupado
  ([−0,0288 · −0,0205]) es más ancho que el ingenuo y no cruza cero.

## 2. Estratos — SE FIJAN AQUÍ, MARGINALES, y no se amplían

**Marginales, no cruzados**, y se declara aquí para que nadie elija después el cruce que gana:

| eje | celdas |
|---|---|
| lead | 9 h · 24 h |
| unidad del contrato | C · F |
| posición de la banda respecto a p50 | centro (p25–p75) · cola cercana (p10–p25 o p75–p90) · cola lejana (fuera de p10–p90) |
| nivel de precio | deciles de `p_mid` |
| estación | todas las que cumplan §3 (**se anticipa que casi todas serán INSUFICIENTE**) |
| anchura del pronóstico `p90 − p10` de ese día | terciles — estratifica por RÉGIMEN, no por sitio |
| completitud del evento | bandas cotizadas del evento: terciles |
| antigüedad del mercado desde su descubrimiento | terciles |
| ~~amplitud del spread bid-ask~~ | **NO EVALUABLE**: no hay book histórico (§0, premisa 1) |

Todos observables en el instante de decidir. Ninguno usa el resultado. **No se evalúa ningún
cruce de ejes en R22.**

## 3. Umbral de evaluabilidad — en EVENTOS, bloqueante menor 4 de A

`MIN_EVENTOS = 100` por celda, **fijado aquí** y tomado de la propuesta de A, no de la mía
—elegir el 30 después de ver que el 100 vacía el eje de estación habría sido elegir el umbral
para conservar una hipótesis—. Por debajo la celda se reporta `INSUFICIENTE`:
**ni empate, ni derrota, ni victoria**. Sin esto, la celda con menos datos es la de más varianza
y la más fácil de «ganar».

**Sesgo conocido y declarado:** en los deciles de precio bajo casi todo pierde y predecir ≈0 da
un Brier excelente sin habilidad ninguna; el mercado cotiza ahí 0,001–0,02 y **ganará esas
celdas casi por construcción**. No se corrige —la comparación es justa, los dos se puntúan sobre
los mismos resultados— pero un «el mercado gana» en el decil más barato **no es informativo** y
el informe lo dirá en vez de contarlo como evidencia.

## 4. `p_model` se RECOMPUTA con disciplina as-of — bloqueante menor 5 de A

No se reutilizan los `p_model` de R21. Se recomputan con el artefacto **vigente en cada
`prediction_time`**, con la guarda `fit_instant > prediction_time`, para no puntuar un modelo
ajustado después contra un mercado que sí operaba en tiempo real.

**Versión de la CDF, congelada aquí para que no parezca continuidad:** se usa
`quantiles_to_distribution` **CON el arreglo de la cola inferior de la sesión A** (la rama
inferior devolvía valores negativos por debajo de `p10 − 1` y el bin sumaba su magnitud). **Es
una CDF distinta de la que produjo R21**, y por eso R22 **no es comparable fila a fila con R21**
y no se presentará como si lo fuera.

## 5. El control de multiplicidad — bloqueante 1 de A, el que rompía v1

v1 exigía «ganar en las dos mitades del periodo». **A demostró que no controla nada:** bajo la
hipótesis nula ganar una mitad es una moneda, ganar las dos es **P ≈ 0,25**, y con ~65 celdas
marginales eso deja pasar **≈ 16 ganadoras espurias**. Retirado.

**Se adopta un test de PERMUTACIÓN sobre el estadístico MÁXIMO:**

```
Δ(celda) = Brier(p_mid | celda) − Brier(p_model | celda)      (positivo = gana el modelo)
T_obs    = max Δ sobre las celdas evaluables

B = 2 000 permutaciones, semilla 20260909.
En cada una, para CADA EVENTO y con probabilidad 1/2, se INTERCAMBIAN `p_model` y `p_mid`
en todas las filas de ese evento a la vez. Se recalcula Δ en cada celda y T* = max Δ.
p_familia = (1 + #{T* >= T_obs}) / (1 + B)
```

**Por qué este esquema y no otro.** Es una prueba **pareada**: la hipótesis nula es que los dos
predictores son intercambiables, y bajo ella la distribución de Δ es simétrica en cero. El
intercambio se hace **por evento entero**, así que los bloques de §1 quedan intactos por
construcción y la dependencia entre las bandas de un evento se conserva exactamente. No exige
emparejar eventos de igual tamaño, no toca la pertenencia a celdas, y controla la familia sobre
el **máximo** sin suponer independencia entre ejes — que era el objetivo de A al pedir
permutación en vez de «ganar las dos mitades» (P ≈ 0,25 bajo la nula, ≈ 16 espurias sobre 65
celdas).

Es el único control que acota la familia **sin suponer independencia entre ejes**, y con
clústeres por evento el supuesto de independencia de Bonferroni tampoco se sostiene.

**Segundo criterio, y sustituye al umbral absoluto de v2 — propuesto por A:** el listón se fija
como múltiplo del error estándar **de la propia celda**, no como una cifra a ojo:

```
gana(celda)  ⇔  Δ(celda) >= 2 · SE(celda)
SE(celda) = desviación típica de Δ por bootstrap por BLOQUES DE EVENTO, 2 000 remuestreos
```

Es **derivado**, adimensional, y **se adapta al tamaño de cada celda**, que es exactamente lo
que un umbral absoluto no hace. El `0,002` de v2 era el 20 % del hueco global elegido a ojo, y
podía estar por debajo del suelo de ruido de las celdas pequeñas. El SE se puede calcular sin
mirar quién gana: no depende del signo.

**Criterio final, congelado:** una celda se declara ganadora si y sólo si `Δ(celda) > 0` **y**
`Δ(celda) >= 2 · SE(celda)` **y** `p_familia < 0,05`. Se reporta siempre el número de celdas evaluadas y el de `INSUFICIENTE`.

## 5bis. Regla de REPORTE para las celdas baratas — propuesta de A, adoptada

En los deciles de precio bajo predecir ≈0 da un Brier excelente sin habilidad ninguna. **No se
cambia la puntuación** —hacerlo tras ver el problema sería elegir la métrica a partir de él—
pero junto al Brier se reporta el **Brier Skill Score de cada uno contra la tasa base de la
propia celda**. No altera el orden dentro de la celda, así que no puede hacer pasar a nadie;
sólo hace **visible** que los dos tienen habilidad ≈ 0 ahí, y entonces «el mercado gana» en esa
celda se lee como lo que es: no informativo.

## 6. Prohibiciones

- No se calcula ningún Brier antes de que este documento esté hasheado.
- No se añaden ejes, cruces ni celdas tras ver resultados.
- No se relajan `MIN_EVENTOS`, el 0,05 de familia ni la agrupación por evento.
- **No se calcula ningún PnL en R22.** Un PnL exige R21.2 y su propio preregistro.
- No se remuestrea por filas en ningún punto.
- No se sustituye el eje de spread por un proxy inventado: no hay book y se dice.
- Gate D0 intacto.

## 7. Desenlace declarado por adelantado

Si ninguna celda cumple §5, el resultado es **EL MODELO NO SUPERA AL MERCADO EN NINGUNO DE LOS
ESTRATOS DECLARADOS**, se publica con esas palabras y no con otras más amplias (§0), y **no se
preregistra R21.2**. No se buscan más ejes: buscar hasta encontrar uno que gane es exactamente
el ciclo que este documento existe para no repetir.

## 8. Limitaciones que heredará el informe

Todas las de R21 §8, y tres propias: **el eje que la propia hipótesis señalaba como el más
informativo —dónde el mercado está menos informado, medido por el spread— no se puede evaluar
porque no hay book histórico, así que la rama negativa es más débil de lo que podría haber
sido** · **los estratos son los que se nos ocurrieron**, así que un
negativo dice «ninguno de estos», no «ninguno posible» · el periodo está desbalanceado hacia
abril y mayo, así que la partición temporal tiene mitades de composición distinta y el contraste
entre ellas hereda ese desbalance.
