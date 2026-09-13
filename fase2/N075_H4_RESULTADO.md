# H4 — COMPARABILIDAD DEL SCORING ENTRE ESCALERAS 7/9/11

**REFERENCE / SANITY CONTROLS — NOT LEVEL 1.** Nada de lo que hay aquí entrena un modelo,
hace walk-forward, busca edge, calcula PnL, selecciona bandas ni ejecuta CONFIRMA/REFUTA. El
gate D0 sigue abajo y Level 1 sigue cerrado.

Unidades, ponderación y regla de veredicto: `N075_H4_DECLARACION.md`, espejado a las
**19:11:08Z** (`391c5f3`) **antes** de calcular las partes B–F. Guion: `n75_h4.py`. Salida
íntegra: `N075_H4_SALIDA.txt`.

---

## B. LA LÍNEA BASE MATEMÁTICA

### B.1 Brier — derivación

Un evento de `n` bandas, exactamente una ganadora, control uniforme `p_i = 1/n`:

    banda ganadora      (1/n - 1)^2  =  ((n-1)/n)^2
    n-1 perdedoras      (n-1) · (1/n)^2  =  (n-1)/n^2
    ---------------------------------------------------------------
    SUMA por evento     [(n-1)^2 + (n-1)] / n^2
                      =  (n-1)·[(n-1) + 1] / n^2
                      =  (n-1)·n / n^2
                      =  (n-1)/n                          <- CRECE con n

    MEDIA por contrato  (n-1)/n^2                          <- DECRECE con n

**Monotonía, derivada:** `d/dn [(n-1)/n^2] = [n^2 - (n-1)·2n]/n^4 = (2-n)/n^3 < 0` para
`n > 2`. Estrictamente decreciente.

### B.2 Log Loss — derivación

    banda ganadora      -ln(1/n)  =  ln n
    n-1 perdedoras      (n-1) · -ln(1 - 1/n)  =  (n-1)·ln(n/(n-1))
    ---------------------------------------------------------------
    SUMA por evento     ln n + (n-1)·ln(n/(n-1))
    MEDIA por contrato  [ln n + (n-1)·ln(n/(n-1))] / n

(El término `(n-1)·ln(n/(n-1)) → 1` cuando `n → ∞`, así que la media `≈ (ln n + 1)/n`.)

### B.3 Verificación

Las dos fórmulas se comprueban contra el cálculo directo, contrato a contrato, para
`n = 2…15`. **Coinciden a `1e-12` en los catorce casos** (`N075_H4_SALIDA.txt`, parte B).

| n | Brier/contrato | Log Loss/contrato | Brier suma por evento |
|---|---|---|---|
| **7** | **0,12244898** | **0,41011632** | 0,85714286 |
| **9** | **0,09876543** | **0,34883210** | 0,88888889 |
| **11** | **0,08264463** | **0,30463610** | 0,90909091 |

    recorrido 7 -> 11    Brier   +0,039804   =  48,2 % del valor de 11 bandas
                         LogLoss +0,105480   =  34,6 % del valor de 11 bandas

**Sí: la línea base cambia mecánicamente con `n`, en las dos métricas, y por un margen
enorme.** Para comparar: el mayor delta OLD↔CORRECTED de todo el nivel 0.75 fue **0,00991**.
El salto de escalera es **cuatro veces mayor que el efecto que se pretendía medir**.

### B.4 Y NO ES SÓLO LA LÍNEA BASE — lo importante de esta sección

Se puede objetar que un nulo que se mueve no impide comparar *modelos*. Se puede, y es
falso. Tómese una **familia de calidad fija**: probabilidad `c` a la banda ganadora, el resto
repartido uniformemente entre las `n-1` restantes.

    media por contrato = (1/n)[ (1-c)^2 + (n-1)·((1-c)/(n-1))^2 ]
                       = (1/n)(1-c)^2 [ 1 + 1/(n-1) ]
                       = (1-c)^2 / (n-1)

(Comprobación: `c = 1/n` devuelve `(n-1)/n^2`, la línea base. ✓)

| c | Brier n=7 | n=9 | n=11 | LL n=7 | n=9 | n=11 | **−ln c** |
|---|---|---|---|---|---|---|---|
| 0,20 | 0,106667 | 0,080000 | 0,064000 | 0,35258 | 0,27248 | 0,22211 | **1,60944** |
| 0,35 | 0,070417 | 0,052813 | 0,042250 | 0,24826 | 0,19197 | 0,15654 | **1,04982** |
| 0,50 | 0,041667 | 0,031250 | 0,025000 | 0,17360 | 0,13438 | 0,10964 | **0,69315** |
| 0,70 | 0,015000 | 0,011250 | 0,009000 | 0,09492 | 0,07360 | 0,06012 | **0,35667** |
| 0,90 | 0,001667 | 0,001250 | 0,001000 | 0,02946 | 0,02289 | 0,01871 | **0,10536** |

> **A CALIDAD IDÉNTICA, más bandas dan mejor Brier y mejor Log Loss por contrato.** Un modelo
> que pone exactamente la misma probabilidad sobre la verdad puntúa un 37 % «mejor» en Brier
> sólo por pasar de 7 a 11 bandas. El problema no es que el nulo se mueva: es que **toda la
> escala se comprime con `n`**.

**La única columna que no se mueve es `−ln(q_ganadora)`**, porque es función de un solo
número y `n` no aparece en ella.

---

## C. PONDERACIÓN — peso efectivo, con la muestra real

Muestra elegible de EGLC: `7 bandas × 2 · 9 bandas × 26 · 11 bandas × 158` = 1 986 contratos,
186 eventos.

| n | eventos | W1 por contrato | W2 por evento | W3 evento×lead | W1/W2 |
|---|---|---|---|---|---|
| 7 | 2 | 0,003525 | 0,005376 | 0,005376 | **0,656** |
| 9 | 26 | 0,004532 | 0,005376 | 0,005376 | **0,843** |
| 11 | 158 | 0,005539 | 0,005376 | 0,005376 | **1,030** |

* **W1 (por contrato)** da a un evento de 11 bandas **11/7 = 1,571 veces** el peso de uno de 7.
* **W2 y W3** igualan el peso del evento, y ahí acaba lo que arreglan.

> **Igualar pesos NO iguala escalas.** W2 y W3 promedian una cantidad que **ya depende de
> `n`** —`(n-1)/n²` en el nulo, `(1-c)²/(n-1)` a calidad fija—. Dar el mismo peso a dos
> eventos no sirve de nada si lo que se promedia de cada uno está en unidades distintas.

**Ninguno de los tres esquemas declarados neutraliza la dependencia de `n`.** Es la condición
exacta que la regla de veredicto exigía para `INVALIDADA`.

---

## D. COMPARABILIDAD TEMPORAL — la confusión es TOTAL, no parcial

    escalera  7 :  [2025-12-30 .. 2026-01-01]
    escalera  9 :  [2026-02-18 .. 2026-03-15]
    escalera 11 :  [2026-03-16 .. 2026-09-04]

**No es una peculiaridad de EGLC: es un calendario global.** De las 52 estaciones de
`markets_v2`, 20 tienen más de una escalera, y **el corte cae en las mismas fechas en todas**.

> **Fechas del catálogo entero con más de un tamaño de escalera: UNA.** El 2026-05-19, con
> `{1, 3, 11}` — y es el caso degenerado del duplicado `arch`/vivo ya caracterizado en A-278,
> no una coexistencia real de escaleras.

Y el dato que cierra la puerta empírica:

    primera observacion de TODO el almacen   2026-04-07 16:00 UTC
    observaciones en o antes del 2026-01-01  (fin de la escalera 7)     0
    observaciones en o antes del 2026-03-15  (fin de la escalera 9)     0

**Las escaleras de 7 y 9 bandas tienen CERO días etiquetables en las 52 estaciones.** No es
que la comparación salga mal: es que no existe ni un solo par comparable.

Confusores que **no se pueden separar** de la escalera con este corpus, porque cambian
exactamente en las mismas fechas:

| confusor | separable |
|---|---|
| cambio de escalera | — (es el tratamiento) |
| estación del año (invierno → primavera → verano) | **NO** |
| distribución de temperatura | **NO** |
| régimen de mercado (`tick_size`, liquidez, número de mercados) | **NO** |
| calidad del pronóstico (horizonte, modelo, sesgo estacional) | **NO** |

**Cualquier diferencia de puntuación entre escaleras es, en este corpus, inseparable de
cuatro cambios simultáneos.** No se interpreta ninguna diferencia temporal como evidencia
predictiva.

---

## E. EL CONTROL DECISIVO, Y UNA PRECISIÓN SOBRE LO QUE DEMUESTRA

`p = 1/n_bandas`. Medido en los cuatro cuadrantes:

| | eventos | escaleras | Brier | teórico | Log Loss | teórico |
|---|---|---|---|---|---|---|
| CORRECTED lead 24 | 95 | `{11}` | 0,082645 | 0,082645 | 0,304636 | 0,304636 |
| CORRECTED lead 9 | 96 | `{11}` | 0,082645 | 0,082645 | 0,304636 | 0,304636 |
| OLD lead 24 | 18 | `{11}` | 0,082645 | 0,082645 | 0,304636 | 0,304636 |
| OLD lead 9 | 19 | `{11}` | 0,082645 | 0,082645 | 0,304636 | 0,304636 |

**El valor medido coincide con `(n-1)/n²` con `n = 11` hasta el último decimal impreso.**

> **Y aquí hay que afinar lo que dije en A-278.** Escribí que la constancia del control «prueba
> que el código de puntuación no depende de la población». Eso es cierto para lo que
> comprobaba —invariancia al brazo y al tamaño de muestra— pero **el control es constante
> también porque `n` es constante**. Si `n` variara, el control variaría con él, y esa
> variación sería **correcta**, no un fallo. Un control estructural sólo certifica
> invariancia *dentro de una `n` fija*. No es una retractación: es el límite de lo que ese
> control puede certificar, y no estaba escrito.

**Si la línea base cambia por escalera, es una propiedad matemática del scoring, no una
señal.** Queda documentada como tal en B.1–B.2.

---

## ¿Y SI SE NORMALIZA? Medido, porque era la objeción obvia

Skill score contra el nulo uniforme **de su propia escalera**:
`BSS_n = 1 − B/B_unif(n)`, `LSS_n = 1 − LL/LL_unif(n)`. Valen 0 en el nulo para toda `n`
**por construcción**. La pregunta es si valen lo mismo a calidad fija.

| c | BSS n=7 | n=9 | n=11 | **rango** | LSS n=7 | n=9 | n=11 | **rango** |
|---|---|---|---|---|---|---|---|---|
| 0,20 | 0,12889 | 0,19000 | 0,22560 | **0,0967** | 0,14030 | 0,21888 | 0,27089 | **0,1306** |
| 0,35 | 0,42493 | 0,46527 | 0,48877 | **0,0638** | 0,39467 | 0,44967 | 0,48615 | **0,0915** |
| 0,50 | 0,65972 | 0,68359 | 0,69750 | **0,0378** | 0,57670 | 0,61476 | 0,64008 | **0,0634** |
| 0,70 | 0,87750 | 0,88609 | 0,89110 | **0,0136** | 0,76856 | 0,78900 | 0,80267 | **0,0341** |
| 0,90 | 0,98639 | 0,98734 | 0,98790 | **0,0015** | 0,92817 | 0,93439 | 0,93857 | **0,0104** |

    BSS(c, n) = 1 - (1-c)^2 · n^2/(n-1)^2        sigue siendo funcion de n

**Normalizar reduce la dependencia, no la elimina** — y el residuo es **mayor donde viven los
modelos reales**: a `c ≈ 0,2–0,35`, que es el rango plausible sobre once bandas a 24 h, el
rango de BSS entre escaleras es de 0,064 a 0,097. Sólo se hace despreciable cuando el modelo
ya es casi perfecto.

`−ln(q_ganadora)` es exactamente invariante en `n`… **pero su nulo, `ln n`, no lo es**
(1,9459 · 2,1972 · 2,3979). Invariante como estadístico del pronóstico; no comparable como
evidencia de skill.

---

## F. TABLA DE RESULTADO

| Pregunta | Resultado | Evidencia | Implicación |
|---|---|---|---|
| **¿Brier comparable entre 7/9/11?** | **NO** | `B_unif(n) = (n-1)/n²`, derivada y verificada a 1e-12 para n=2…15. Recorrido 7→11 = **0,0398 = 48,2 %**, cuatro veces el mayor efecto medido en 0.75. A calidad fija `c`, `B = (1-c)²/(n-1)` | Nunca agregar Brier crudo entre escaleras distintas. Estratificar por `n` siempre |
| **¿Log Loss comparable?** | **NO, y peor** | `LL_unif(n) = [ln n + (n-1)ln(n/(n-1))]/n`. Recorrido 7→11 = **0,1055 = 34,6 %**. Además el Log Loss de los controles indicadores (B1, B2) es **aritmética del recorte** `EPS` (A-278) | Igual que Brier, más la advertencia del recorte. No es métrica primaria |
| **¿Contrato es unidad adecuada?** | **NO para puntuar; SÍ para el libro** | Las `n` filas de un evento no son independientes (`Σ y = 1`). W1 da a un evento de 11 bandas **1,571×** el peso de uno de 7 | Es la unidad económica real. Como unidad estadística infla `N` por un factor `n` |
| **¿Evento es unidad adecuada?** | **NECESARIA pero NO SUFICIENTE** | Iguala el peso (W2), pero promedia `(n-1)/n²`, que depende de `n` | Correcta para contar `N`. No arregla la comparabilidad |
| **¿Event×lead es necesaria?** | **SÍ** | El lead cambia la información en `t_asof`; los dos leads dan controles distintos (p. ej. B3: 0,07096 a 24 h, 0,06505 a 9 h) | Reportar leads por separado, nunca agregarlos. **Es la unidad primaria declarada** |
| **¿Hay ponderación recomendada?** | **SÍ, con una condición que la hace insuficiente por sí sola** | W3 (igual por evento×lead) es la primaria. Pero ningún esquema neutraliza `n`: hay que **estratificar por escalera y no agregar entre escaleras** | La ponderación NO es el remedio. El remedio es la estratificación |

---

# VEREDICTO

## `H4 = INVALIDADA`

La regla escrita antes de medir decía: *`INVALIDADA` si la línea base —o la puntuación de una
familia de pronósticos de calidad fija— depende de `n` y ninguno de los tres esquemas de
ponderación lo neutraliza.* **Las dos condiciones se cumplen, y con margen:**

1. La línea base depende de `n` por derivación cerrada, verificada a `1e-12`.
2. La dependencia sobrevive a calidad fija: `(1-c)²/(n-1)`.
3. Ninguno de W1, W2, W3 la neutraliza, porque los tres promedian una cantidad `n`-dependiente.
4. Ni siquiera la normalización por skill score la elimina (residuo de 0,0015 a 0,097 de BSS).
5. Y empíricamente **no podría comprobarse aunque se quisiera**: cero días etiquetables en las
   escaleras de 7 y 9 bandas, en las 52 estaciones, y una sola fecha en todo el catálogo con
   más de un tamaño — degenerada.

**La declaración ya preveía el intento de rescate:** *«si la respuesta resulta ser “no en
crudo, sí tras normalizar”, eso NO es VALIDADA»*. Y además resulta que ni siquiera tras
normalizar.

---

## METODOLOGÍA DE SCORING CORREGIDA

Conforme al cierre pedido —*si H4 queda invalidada, corregir primero la metodología y repetir
exclusivamente los sanity controls*—:

1. **Unidad primaria `evento × lead`.** Leads siempre separados, nunca agregados.
2. **Estratificar por `n` SIEMPRE.** Está prohibido agregar puntuaciones crudas de eventos con
   distinto número de bandas, con cualquier ponderación.
3. **Publicar el nulo de cada estrato junto a cada número**: `(n-1)/n²` para Brier,
   `[ln n + (n-1)ln(n/(n-1))]/n` para Log Loss.
4. **Acompañar con `BSS_n` y `LSS_n`**, que anclan el cero para toda `n` — declarando que
   igualan el **ancla**, no la **escala**.
5. **Reportar `−ln(q_ganadora)`** como la única cantidad `n`-invariante, con su nulo `ln n` al lado.
6. **La ponderación no es el remedio.** Si alguna vez entra una escalera distinta, se reportan
   estratos separados; no se busca el peso que «arregle» la mezcla.
7. Todo esto son **REFERENCE / SANITY CONTROLS**. `p = 1/n` es un **control estructural**, no
   un modelo predictivo.

### Sanity controls re-ejecutados bajo esa metodología

**REFERENCE / SANITY CONTROLS — NOT LEVEL 1.** Comprobado antes de puntuar: las
probabilidades suman 1 dentro de cada evento con error máximo **2,22·10⁻¹⁶**, así que la
lectura categórica de `−ln q_ganadora` es legítima.

**lead 24 h · 95 eventos · escaleras `{11}`**

| control | Brier/evento | BSS₁₁ | LL/evento | LSS₁₁ | −ln q_gan |
|---|---|---|---|---|---|
| `REF_uniforme` *(control estructural)* | 0,08264 | **0,00000** | 0,30464 | **0,00000** | 2,39790 |
| `B0_clima30` | 0,10154 | −0,22868 | 0,57396 | −0,88408 | 5,12760 |
| `B1_persistencia` | 0,15502 | −0,87579 | 2,14174 | −6,03047 | 11,77954 |
| `B2_fc_crudo` | 0,12440 | −0,50526 | 1,71868 | −4,64174 | 9,45272 |
| `B3_fc_error` | 0,07096 | 0,14141 | 0,27125 | 0,10960 | 2,10878 |
| `B4_fc_bias` | 0,07014 | 0,15131 | 0,23773 | 0,21963 | 1,74452 |

**lead 9 h · 96 eventos · escaleras `{11}`**

| control | Brier/evento | BSS₁₁ | LL/evento | LSS₁₁ | −ln q_gan |
|---|---|---|---|---|---|
| `REF_uniforme` *(control estructural)* | 0,08264 | **0,00000** | 0,30464 | **0,00000** | 2,39790 |
| `B0_clima30` | 0,10119 | −0,22436 | 0,56902 | −0,86786 | 5,09302 |
| `B1_persistencia` | 0,15909 | −0,92500 | 2,19792 | −6,21491 | 12,08857 |
| `B2_fc_crudo` | 0,11553 | −0,39791 | 1,59611 | −4,23940 | 8,77861 |
| `B3_fc_error` | 0,06505 | 0,21287 | 0,23716 | 0,22151 | 1,77308 |
| `B4_fc_bias` | 0,06885 | 0,16697 | 0,22869 | 0,24930 | 1,65150 |

**Todas las filas son de once bandas, así que `BSS₁₁`/`LSS₁₁` son el nulo correcto para todas
y la estratificación es trivial: un solo estrato.** En cuanto entre otra `n`, hay que separar
y no agregar.

**Estos números NO son evidencia de poder predictivo, no ordenan modelos y no autorizan
ninguna conclusión de Level 1.** Son controles de cordura del instrumento.

---

## CIERRE

La condición que puso el encargo era: *«si H4 queda validada, el siguiente paso será abrir
Level 1; si queda invalidada o inconclusiva, corregir primero la metodología de scoring y
repetir exclusivamente los sanity controls»*.

**H4 = INVALIDADA. La metodología corregida está arriba y los sanity controls están
re-ejecutados bajo ella. Level 1 NO se abre.** El gate D0 sigue abajo; producción sin tocar.

**La buena noticia operativa, dicha sin convertirla en permiso:** la población puntuable
actual es **100 % de once bandas**, así que la corrección **no cambia ni uno** de los números
de A-278 — sólo les pone al lado el nulo de su estrato. Lo que cambia es que ahora hay una
regla escrita para el día en que eso deje de ser cierto, y ese día es exactamente el
disparador de la tarea #69.
