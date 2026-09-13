# LEVEL 1 · L1.4 — WALK-FORWARD OOS

Ejecuta `LOCK_L1_4.md`, espejado a las **20:38:43Z** (`cee4255`) **antes** de correr nada.
**No se busca edge, precio ni PnL, no se optimizan umbrales, no se activa trading, no se toca
producción.** `D0-P` = BLOCKED. **No se emite el veredicto de Level 1**: requiere L1.5–L1.7.

    expanding window POR EVENTO · escalera 11 · epsilon 1e-6 · semilla 20260913
    bootstrap clusterizado por EVENTO, 10 000 remuestreos

---

## RESULTADOS

### lead 24 h — 95 eventos de test, 1 045 contratos

| modelo | Brier/evento | Log Loss | rango ganadora | top-1 | `p_max` | sharpness |
|---|---|---|---|---|---|---|
| `B0_clima` | 0,10154 | 0,57396 | 5,789 | 0,032 | 0,418 | 0,2936 |
| `B1_persist` | 0,15502 | *2,14174* | 5,689 | 0,147 | 1,000 | 1,0000 |
| `B2_fc_crudo` | 0,12440 | *1,71868* | 4,763 | **0,316** | 1,000 | 1,0000 |
| `B3_fc_sesgo` | 0,12057 | *1,66579* | 4,647 | **0,337** | 1,000 | 1,0000 |
| **`B4_fc_prob`** | **0,07113** | **0,27215** | **2,711** | 0,316 | 0,344 | 0,2373 |
| *control uniforme* | *0,08264* | *0,30464* | *6,000* | *0,091* | *0,091* | *0,0909* |

### lead 9 h — 96 eventos de test, 1 056 contratos

| modelo | Brier/evento | Log Loss | rango ganadora | top-1 |
|---|---|---|---|---|
| `B0_clima` | 0,10119 | 0,56902 | 5,802 | 0,031 |
| `B1_persist` | 0,15909 | *2,19792* | 5,812 | 0,125 |
| `B2_fc_crudo` | 0,11553 | *1,59611* | 4,495 | **0,365** |
| `B3_fc_sesgo` | 0,12121 | *1,67461* | 4,667 | 0,333 |
| **`B4_fc_prob`** | **0,06534** | **0,23792** | **2,344** | 0,302 |
| *control uniforme* | *0,08264* | *0,30464* | *6,000* | *0,091* |

*(Log Loss en cursiva = **no interpretable**: es aritmética del recorte, A-288. Sólo el de `B4`
es genuino.)*

### MÉTRICA PRIMARIA — Brier por evento, apareado contra `B0_clima`

| | lead 24 | lead 9 |
|---|---|---|
| `B1 − B0` | +0,05348 [+0,04071, +0,06548] **PEOR** | +0,05790 [+0,04592, +0,06873] **PEOR** |
| `B2 − B0` | +0,02286 [+0,00507, +0,04046] **PEOR** | +0,01434 [−0,00407, +0,03317] **IC incluye el cero** |
| `B3 − B0` | +0,01903 [+0,00030, +0,03713] **PEOR** | +0,02003 [+0,00141, +0,03804] **PEOR** |
| **`B4 − B0`** | **−0,03041 [−0,03732, −0,02349] MEJORA** | **−0,03585 [−0,04259, −0,02899] MEJORA** |

---

# EL CAVEAT QUE DOMINA LA LECTURA: **`B0` ES PEOR QUE NO MIRAR NADA**

El control estructural `p = 1/11` vale **0,08264** y no mira ni un dato. La climatología, que es
el *benchmark primario que yo mismo bloqueé*, vale **0,10154 / 0,10119**.

    delta contra el control uniforme (diagnostico anadido DESPUES de ver esto, y se declara)

                   lead 24                                lead 9
    B0_clima   +0,01890 [+0,01316,+0,02455] PEOR      +0,01854 [+0,01287,+0,02414] PEOR
    B1_persist +0,07238 [+0,05898,+0,08386] PEOR      +0,07645 [+0,06319,+0,08781] PEOR
    B2_fc_crudo+0,04176 [+0,02453,+0,05898] PEOR      +0,03289 [+0,01584,+0,04993] PEOR
    B3_fc_sesgo+0,03793 [+0,02070,+0,05515] PEOR      +0,03857 [+0,02152,+0,05561] PEOR
    B4_fc_prob -0,01151 [-0,01592,-0,00707] MEJORA    -0,01731 [-0,02139,-0,01312] MEJORA

> **De los cinco modelos, sólo `B4` bate a un control que no mira datos.** Y eso descompone el
> titular: del `−0,030` de `B4` frente a `B0`, **+0,019 son `B0` siendo peor que el azar** y
> sólo **−0,0115** es margen genuino de `B4` sobre el nulo estructural. **El margen honesto es
> entre un tercio y la mitad del que sugiere la comparación preinscrita.**

**Declarado sin adornos: el diagnóstico contra el uniforme se añadió DESPUÉS de ver que `B0`
quedaba por debajo de él.** No es un modelo nuevo —`REF_uniforme` es `(n−1)/n²`, aritmética
pura, ya en el corpus desde A-280— pero **sí es una comparación que no estaba en el lock**, y
el lector debe poder descontarla. Lo que **no** se ha hecho: cambiar `B0`, cambiar su ventana,
ni sustituir el benchmark preinscrito. `B0` se reporta tal cual, con su resultado.

**Por qué `B0` falla, y es meteorología, no un bug**: la climatología de 30 días **va por detrás
de la estación** en una ventana que sube de abril a agosto. Se ve en su calibración: donde más
confía, más se equivoca.

    B0_clima   p en [0,30, 0,50)  n= 37   predicho 0,3623   observado 0,0000
               p en [0,50, 1,01)  n= 27   predicho 0,7353   observado 0,0741
    B4_fc_prob p en [0,20, 0,30)  n=110   predicho 0,2534   observado 0,2727
               p en [0,30, 0,50)  n= 85   predicho 0,3416   observado 0,3059

---

## RANKING ≠ CALIBRACIÓN, y aquí se ve con toda claridad

| | `B2` / `B3` (deterministas) | `B4` (probabilístico) |
|---|---|---|
| **top-1** | **0,316–0,365** (azar 0,091) | 0,302–0,316 |
| **rango medio de la ganadora** | 4,50–4,76 (azar 6,0) | **2,34–2,71** |
| **Brier** | 0,115–0,124 — **peor que el uniforme** | **0,065–0,071** |

> **Los deterministas ACIERTAN la banda ganadora entre 3,3 y 4 veces más que el azar y aun así
> puntúan peor que no saber nada.** No es falta de señal: es **exceso de confianza**. Poner 1,0
> en una banda y fallar cuesta 2/11 de Brier; el azar nunca paga eso. *El pronóstico tiene
> ranking skill; lo que los deterministas no tienen es calibración.*
>
> `B4` es el único que convierte esa misma señal en probabilidades pagables por una regla de
> puntuación propia — y su ventaja de ranking (rango 2,34 contra 4,50) es mayor que su ventaja
> de top-1 (0,302 contra 0,365, **donde pierde**). **Se registra el split sin elegir**: L1.5
> separa formalmente calibración de ranking.

---

## DIAGNÓSTICO TEMPORAL (corte 2026-06-23; diagnóstico, **no** selección)

    lead 24   1a mitad (47)  B0 0,11187  B1 0,15861  B2 0,13153  B3 0,12766  B4 0,07647
              2a mitad (48)  B0 0,09143  B1 0,15151  B2 0,11742  B3 0,11364  B4 0,06591
    lead  9   1a mitad (48)  B0 0,11115  B1 0,15530  B2 0,12500  B3 0,13636  B4 0,06791
              2a mitad (48)  B0 0,09122  B1 0,16288  B2 0,10606  B3 0,10606  B4 0,06276

**`B4` es mejor en la segunda mitad en los dos leads, y también lo es `B0`.** Que mejoren los
dos a la vez apunta a que la segunda mitad es *más fácil*, no a que el modelo aprenda. **No se
selecciona periodo.**

---

## RED-TEAM (§15), ejecutado antes de interpretar

| riesgo | estado |
|---|---|
| **leakage** | prueba **ejecutable** en L1.2: alterar el futuro +25 °C no mueve ninguna probabilidad anterior, y sí mueve las posteriores (la prueba tiene poder) |
| **look-ahead** | `available_at ≤ t_asof` en 95/95 y 96/96; `target_date` nunca en su train; **pero** la convención `issue + 4:45:36` sigue **no validada externamente** (tarea #75) |
| **errores de timestamp** | registro `issue → available_at → prediction_time → train cutoff` verificado evento a evento (L1.3 §9) |
| **dependencia intra-evento** | bootstrap **clusterizado por evento**; los leads **nunca** se agregan |
| **efectos de escalera** | un solo estrato, `{11}`. 7 y 9 tienen **cero** eventos puntuables: se dice, no se ocultan |
| **confusión estacional** | **presente y nombrada**: es la causa del fallo de `B0`, y la mejora conjunta en la 2ª mitad |
| **artefactos de clipping / epsilon** | Brier varía ≤3e-3 entre 1e-8 y 1e-2; el Log Loss de los deterministas varía hasta 2,13 y **no se usa** |
| **calibración contaminada** | la curva se mide **sobre el propio test**. Los pronósticos son OOS, pero **la curva de calibración no está validada fuera de muestra**: es diagnóstico |
| **diferencias de población** | misma población en los cinco modelos, mismo `n`, mismos eventos |
| **missingness selectiva** | **comprobada**: los 22/21 excluidos son **contiguos desde el inicio** (2026-04-08 → 05-01), el arranque de la ventana expansiva. Son más fríos (17,3 contra 24,3 °C) y su banda ganadora está más arriba (5,8 contra 4,8) — **es estacionalidad del calendario, no selección por resultado**, pero significa que el test **no cubre abril** |

---

## GATE

**Ningún defecto metodológico.** Las comprobaciones de buena forma, no-fuga, temporalidad,
estratificación y dependencia pasan; el único hallazgo de esta etapa es que **el benchmark
preinscrito es más débil que el control estructural**, y eso es un resultado, no un fallo del
procedimiento.

# `L1.4 = CLOSED`

**No se emite el veredicto de Level 1.** Lo registrado, sin retocar nada: `B4` mejora sobre
`B0` en los dos leads con IC95 que excluye el cero, **y también sobre el control uniforme**, con
un margen de **−0,0115 / −0,0173** que es la cifra honesta. `B1`, `B2` y `B3` son **peores que
no mirar datos** en Brier pese a tener ranking skill. **Nada se ha cambiado tras ver estos
números.**

Siguiente: **`L1.5` — CALIBRACIÓN + RANKING**.
