# R22 — RESULTADO NEGATIVO LIMPIO: el modelo no supera al mercado en NINGÚN estrato declarado

**Fecha:** 2026-09-09 · **Sesión:** B · **Preregistro:** `PREREG_R22_SKILL_LOCUS.md`
sha `0508ced1213c39e17766bbc6ccf249a1071849b1fe4d2d852dc104cb00b15796` (v4), congelado antes de
calcular ningún Brier.

**VEREDICTO: `EL_MODELO_NO_SUPERA_AL_MERCADO_EN_NINGUNO_DE_LOS_ESTRATOS_DECLARADOS`.**
Por §7 del preregistro, **no se preregistra R21.2.**

---

## 1. El resultado, y no está cerca

```
filas 10 000 · eventos 1 308 · celdas construidas 70 · evaluables (>=100 eventos) 16
degenerada y fuera del recuento: completitud=baja (§1bis)
T_obs (la MEJOR celda) = −0,00252        p_familia = 1,0000

celda                         ev    %ev  %filas     delta      2*SE  BSS mod  BSS mkt
banda=cola_lejana           1296 99,1%  77,7%  −0,00252   0,00150    0,296    0,389
estacion=EGLC                115  8,8%  12,7%  −0,00442   0,00479    0,140    0,214
precio_bin_0.1=0            1290 98,6%  79,2%  −0,00484   0,00090   −0,547    0,021
precio_bin_0.1=2             267 20,4%   5,4%  −0,00608   0,00936   −0,023    0,012
unidad=F                     282 21,6%  20,6%  −0,00704   0,00426    0,417    0,517
anchura_fc=alta              526 40,2%  31,6%  −0,00731   0,00321    0,333    0,437
lead=24                     1263 96,6%  49,4%  −0,00782   0,00209    0,220    0,335
precio_bin_0.1=1             301 23,0%   5,7%  −0,01027   0,00601   −0,117   −0,012
unidad=C                    1026 78,4%  79,4%  −0,01039   0,00241    0,189    0,343
anchura_fc=media             871 66,6%  32,4%  −0,01075   0,00306    0,194    0,357
anchura_fc=baja              823 62,9%  36,0%  −0,01085   0,00346    0,188    0,348
lead=9                      1308 100,0% 50,6%  −0,01153   0,00266    0,255    0,425
precio_bin_0.1=3             249 19,0%   4,5%  −0,02296   0,01450   −0,091    0,010
banda=cola_cercana           374 28,6%  11,8%  −0,03206   0,00864    0,094    0,316
banda=centro                 343 26,2%  10,6%  −0,03757   0,00991    0,013    0,194
precio_bin_0.1=4             188 14,4%   2,7%  −0,05840   0,03098   −0,234    0,000
```

**LAS COLUMNAS DE COBERTURA SON DE LA SESIÓN A, y sin ellas este informe se lee mal.** «Dieciséis
celdas con Δ < 0» sugiere dieciséis testigos independientes, **y no lo son**: `lead=9` contiene el
**100 %** de los eventos y `estacion=EGLC` el **8,8 %**, así que sus bootstraps por bloques
descansan sobre 1 308 y 115 bloques y sus SE no son del mismo orden. `precio_bin_0.1=0` **no es
una de cinco quintas partes**: es el 98,6 % de los eventos y el 79 % de las filas. Lo que hay es
**unas pocas celdas grandes y una cola de pequeñas, todas negativas** — que sigue siendo el
resultado, dicho sin inflarlo. Es una regla de **reporte**, como la del BSS: no mueve ninguna
cifra, cambia lo que un lector concluye de ella.

**Las dieciséis celdas evaluables tienen Δ < 0.** No hay una sola en la que el modelo gane, ni
siquiera sin significación.

**PERO CONTAR CELDAS SOBREVENDE LA COBERTURA, y la sesión A tiene razón al señalarlo dos veces.**
Descontando lo que no estratifica —ver §1bis— **los cortes que de verdad parten la muestra son
DIEZ**, y ésa es la cifra que debe citarse:

```
lead=9 · lead=24 · unidad=C · unidad=F · banda=centro · banda=cola_cercana ·
banda=cola_lejana · anchura_fc=baja · anchura_fc=media · anchura_fc=alta

las DIEZ con Δ < 0  ·  las DIEZ con |Δ| > 2·SE de su propia celda
```
Más los cinco cortes de precio evaluables, también todos negativos. El negativo sigue siendo
fuerte —**diez de diez, todos por encima de su propio ruido**— pero se dice con diez. La prueba de permutación **no tuvo trabajo que hacer**: `T_obs` —el
máximo sobre todas las celdas— ya es negativo, así que `p_familia = 1` es trivial y no un
resultado ajustado. El control de multiplicidad que tanto costó fijar acabó siendo innecesario,
y eso es la forma más limpia que puede tomar un negativo.

Y en **quince de las diecisiete**, `|Δ| > 2·SE`: la derrota no sólo existe, es **mayor que el
ruido de la propia celda**.

## 1bis. Dos celdas que no son estratos, señaladas por la sesión A y verificadas por mí

**`completitud=baja` es la muestra entera con otro nombre.** Verificado sobre el JSON crudo:
**1 308 eventos de 1 308 y 10 000 filas de 10 000.** Su Δ *es* el Δ global. Es un eje degenerado
por la misma razón que `antiguedad` —una celda con aspecto de eje— y **no debe contar entre los
estratos**. Pasa a la tabla de §4. Que se colara es un fallo del runner y no de la medida: la
guarda de degeneración sólo miraba los NULL, no la cobertura.

**`precio_decil` NO son deciles.** Son cortes de **anchura fija** sobre `p_mid`, y el reparto es:

```
7 919 · 573 · 541 · 450 · 268 · 81 · 23 · 26 · 31 · 88
la celda 0 sola es el 79,2 % de la muestra; las 5–9 no llegan a MIN_EVENTOS
```
El nombre induce a error y se corrige aquí. No invalida nada —los cortes son ex ante y no
dependen del resultado— pero el eje aporta **una celda dominante y cuatro pequeñas**, no diez.

## 1ter. EL HALLAZGO MÁS FUERTE, y no es ninguna celda: la habilidad del modelo es ENTERA entre bins

Lo encontró la sesión A dentro de mis propios datos y lo he verificado sobre el JSON:

```
BSS del modelo sobre la MUESTRA ENTERA          +0,238      (mercado +0,380)

BSS del modelo DENTRO de cada régimen de precio:
   bin 0   −0,547        bin 1   −0,117        bin 2   −0,023
   bin 3   −0,091        bin 4   −0,234
```

**Sobre el conjunto el modelo tiene habilidad positiva. Dentro de cada régimen de precio es peor
que predecir la tasa base de ese régimen. En los cinco.** Su habilidad global es, por tanto,
**enteramente un efecto ENTRE bins**: lo único que el modelo aporta es «las bandas baratas son
improbables» — y eso el mercado ya lo tiene dentro del precio, **porque el precio es el bin**.

Esto es la selección adversa de R21 **medida y descompuesta**, y dice más que «el mercado gana
en todas las celdas»: no es que el modelo sea algo peor que el mercado, es que **condicionado al
precio no aporta información, y la que parecía aportar era la que el precio ya contenía.**

**El límite de esta lectura, que A señaló y hay que repetir:** el BSS del **mercado** dentro de
su propio bin de precio es ≈0 casi por construcción —el bin *es* su predicción—, así que la
comparación modelo-contra-mercado **dentro** de un bin es débil y no se usa. Lo que no es débil
ni tautológico es **el signo negativo del modelo**, que se mide contra la tasa base observada
del bin y no contra el mercado.

## 2. La única celda donde el resultado no es concluyente, y se dice

`estacion=EGLC`: Δ = −0,00442 con 2·SE = 0,00479. **Es la única en la que la derrota del modelo
no supera su propio ruido.** Tampoco gana —Δ sigue siendo negativo— pero honestamente ahí lo
que hay es empate dentro del error. Es además la única celda del eje de estación que llegó a
`MIN_EVENTOS = 100`.

## 3. La regla de reporte del BSS hizo exactamente lo que se esperaba de ella

La sesión A la propuso para que las celdas baratas no se leyeran como evidencia. Funcionó:

```
precio_decil=0   BSS modelo −0,547   BSS mercado +0,021
```

En el decil más barato el **modelo es activamente peor que predecir la tasa base de la celda**,
y el mercado apenas la mejora. Un «gana el mercado» ahí no dice que el mercado sepa algo: dice
que ninguno de los dos sabe nada y que el modelo además estorba. Sin el BSS al lado, esa celda
habría entrado en la tabla como una derrota más entre otras.

**Donde el modelo mejor se comporta consigo mismo, el mercado sigue por delante:** unidad F
(BSS 0,417 contra 0,517) y anchura de pronóstico alta (0,333 contra 0,437).

## 4. Ejes que no se pudieron evaluar, y por qué importa decirlo

| eje | estado | causa |
|---|---|---|
| spread del libro | **IMPOSIBLE** | `orderbook_snapshots` vacía; los 16 165 636 precios son `MIDPOINT_ESTIMATED`. No hay histórico de libro y no se reconstruye |
| antigüedad del mercado | **NO DISPONIBLE** | `discovered_at` NULL en **10 000 de 10 000** filas |
| estación | **INSUFICIENTE** en 49 de 50 | sólo EGLC alcanza 100 eventos |
| completitud del evento | **DEGENERADO** | su única celda evaluable cubre 1 308/1 308 eventos y 10 000/10 000 filas: es la muestra entera, no un estrato (§1bis) |

**El del spread es el que duele**, y se declara sin adornos: la hipótesis que explica el fallo
—el mercado está mejor informado— predice que la habilidad relativa del modelo sería máxima
**donde el mercado está menos informado**, y el proxy observable de eso es el spread. **No se ha
podido mirar ahí.** Por tanto este negativo es más débil de lo que podría haber sido, y no se
sustituyó por un proxy inventado.

**El de la antigüedad se descartó en vez de colapsarse**, que es la parte que sí funcionó: con
`discovered_at` NULL en todas las filas, los tres terciles habrían fallado todas sus
comparaciones y **cada fila habría caído en «media» — una celda con aspecto de tres**. Es la
misma familia que la cadena `'nan'` en `station_identifier`. El runner cuenta y descarta.

## 5. Lo que este resultado autoriza a decir, y lo que NO

**Autoriza:** *sobre los estratos declarados no aparece la habilidad que una regla larga
necesitaría, y quien afirme lo contrario tendrá que nombrar el estrato.* Es suficiente para no
preregistrar R21.2.

**NO autoriza** afirmar que ninguna regla larga *pueda* funcionar. El Brier es un **promedio** y
el beneficio vive en un **subconjunto elegido**; un modelo con peor Brier global podría en
principio identificar un nicho rentable. Esa asimetría se escribió en §0 del preregistro
**antes** de ver nada, precisamente para no sobreleer un negativo, y se respeta aquí.

Dicho eso, la fuerza del hallazgo no está en el recuento de celdas sino en dos cosas:
**pierde en los DIEZ cortes que de verdad estratifican, y en los diez por encima de su propio
ruido**, incluidos los que se eligieron porque la hipótesis del mecanismo los señalaba (anchura
de pronóstico, posición de la banda, nivel de precio); y sobre todo **§1ter**, que muestra que
condicionado al precio el modelo no aporta información. Eso último es más fuerte que cualquier
recuento, porque no depende de cuántos ejes se nos ocurrieran.

## 6. Integridad

| Comprobación | Estado |
|---|---|
| Preregistro congelado y hasheado antes de calcular ningún Brier | **SÍ** — v4, `0508ced1…` |
| Ejes o celdas añadidos tras ver resultados | **NO** |
| Celdas RETIRADAS del recuento tras ver resultados | **SÍ, una: `completitud=baja`** — y no por su Δ, que es negativo como el resto y no cambia nada, sino porque es la muestra entera. Retirar una celda que no favorece al modelo no puede favorecerle: el cambio **reduce** la cobertura declarada de 17 a 10 |
| `MIN_EVENTOS` relajado para conservar un eje | **NO** — el 100 vació el eje de estación y se publica |
| Remuestreo por filas en algún punto | **NO** — bloques de evento en el bootstrap y en la permutación |
| Métrica cambiada en las celdas baratas | **NO** — el BSS es regla de REPORTE, no de puntuación |
| Eje de spread sustituido por un proxy | **NO** — declarado imposible |
| PnL calculado en R22 | **NO** — §6 lo prohíbe |
| Reproducible con la semilla publicada | **SÍ** — `sorted()` en toda enumeración de eventos |
| Dinero real | **NO** — gate D0 intacto |

## 7. Limitaciones

Todas las de R21 §8, y tres propias: **los estratos son los que se nos ocurrieron**, así que un
negativo dice «ninguno de estos ocho ejes», no «ninguno posible» · **el eje que la propia
hipótesis señalaba como más informativo no era evaluable** · R22 corre sobre la CDF **con** el
arreglo de la cola inferior de la sesión A, que es **distinta** de la que produjo R21, así que
las dos corridas **no son comparables fila a fila**.
