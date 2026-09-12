# PREREG R30 — ENMIENDA L: la nula de §5.5(c) supone una partición que el sustrato no tiene

**Sesión B.** Duodécima enmienda a `PREREG_R30_PUERTA_SUSTRATO.md`
(sha `0a5b794e656390b13e33f14a40260f7a7818b13928f45db7d1a5312deb0caaaf`). Índice y shas en
`R30_PREREG_CHAIN.md`.

---

## LO QUE YA HE VISTO, declarado primero porque es lo que resta valor a esta enmienda

**Esta enmienda se escribe DESPUÉS de calcular, y las once anteriores se escribieron antes.** No
puedo presentarla como preinscripción. Lo que he visto, y que cualquiera debe poder descontar:

1. **La ejecución de §5.5 tal como está congelado, entera.** Devolvió `p = 1,0000` sobre 10 000
   réplicas — degenerado, no un resultado.
2. **La tabla de `d_b` de la población completa**, con sus IC y su veredicto de §5.5(d):

        bin  filas  eventos    f_b     p_mid_b      d_b      IC 95 %
          0   7919     1290   0,0086    0,0101    -0,0015   [-0,0039, +0,0011]
          1    573      301   0,1099    0,1460    -0,0360   [-0,0621, -0,0076]
          2    541      267   0,2292    0,2464    -0,0172   [-0,0510, +0,0176]

**Sé, al escribir esto, que el intervalo 1 tiene un `d_b` negativo cuyo IC excluye el 0.** La regla
de ámbito de abajo no se elige mirando eso —se elige por un hueco vacío en la distribución de
precios, que no depende de ningún desenlace— pero el lector no tiene por qué creerme, y por eso
**los dos cómputos se publican, el de la población completa y el de la restringida.**

---

## EL DEFECTO, y son dos

§5.5(c) (enmienda K) genera la nula así:

> «Para cada EVENTO, se sortea UNA banda ganadora con probabilidades proporcionales a los `p_mid` de
> sus bandas. Eso es exactamente «los precios son las probabilidades verdaderas» **y respeta por
> construcción que las bandas de un evento son una partición con un solo ganador**.»

**Las dos mitades de esa frase son falsas sobre el sustrato, y nadie lo comprobó antes de congelarla.**

### Defecto 1 — la partición no es el evento, es (evento, lead)

    agrupando por           grupos   0 gan.   1 gan.   2 gan.
    evento                    1308      937        8      363
    (evento, lead)            2571     1837      734        0
    (evento, lead, unidad)    2571     1837      734        0

Un evento cotizado a los dos plazos aporta **cada banda dos veces**, una por plazo, y por tanto dos
ganadores. Los «363 eventos con dos ganadores» no son un error de etiquetado: son eventos con 9 h y
24 h. **Por (evento, lead) el máximo es uno, siempre.**

### Defecto 2 — y sólo 726 de los 2 571 grupos son una partición

La suma de `p_mid` por grupo **es bimodal**, y el sustrato contiene dos cosas distintas:

    percentil de la suma de p_mid por (evento, lead), n = 2 571
      p 1   0,0005      p50   0,0025      p90   1,0325
      p10   0,0005      p75   0,9685      p99   1,1100

    mediana en grupos CON ganador (734):  1,0190
    mediana en grupos SIN ganador (1837): 0,0010

**1 837 grupos tienen todas sus bandas en el suelo de 0,0005 y ninguna gana: no son mercados con una
distribución de probabilidad, son libros sin cotizar en el instante de decisión.** Aportan 2 205 filas,
casi todas al intervalo 0. Forzarles un ganador —que es lo que la nula hace— infla `f_b` por
construcción, y de ahí el `p = 1,0000`: la nula y lo observado no describen la misma población.

*Congelé una nula cuya premisa era una afirmación sobre los datos, y la escribí sin medirla.*

---

## §5.5 enmendado por L

> **§5.5(c) (enmendado L) — unidad de la partición.** Donde K dice «para cada EVENTO», se lee **para
> cada (EVENTO, LEAD)**. Medido: por ese agrupamiento ningún grupo tiene más de un ganador, en los
> 2 571 grupos.
>
> **§5.5(f) (nuevo) — ámbito del contraste.** El contraste de §5.5 se calcula sobre los grupos
> (evento, lead) cuya **suma de `p_mid` ≥ 0,50**. Un conjunto de bandas mutuamente excluyentes y
> exhaustivas tiene precios que suman 1; un grupo cuya suma es 0,001 no es una partición bajo ninguna
> lectura, y la nula de §5.5(c) no está definida sobre él.
>
> **El 0,50 no es un umbral ajustado: cae en un hueco VACÍO de la distribución observada.** No existe
> ningún grupo con suma entre **0,4850 y 0,5360**. La regla separa dos poblaciones disjuntas en vez
> de cortar una, y por eso el valor exacto del corte no cambia nada dentro de ese hueco.
>
> **Y la regla es independiente del desenlace, que es lo que impediría que sea selección sobre la
> variable dependiente:** admite 5 grupos sin ganador y excluye 13 con ganador.
>
>   - admite: **726 grupos, 7 787 filas** (721 con un ganador, 5 sin ninguno)
>   - excluye: 1 845 grupos, 2 213 filas
>
> **§5.5(e) y la regla de ocupación de §5.4 se recalculan sobre esta población**, contando grupos
> (evento, lead) y no eventos. El bootstrap por bloques de §5.5(b) usa el mismo bloque.
>
> **SE PUBLICAN LOS DOS CÓMPUTOS** —población completa y población de partición— con todos los
> intervalos y su `n`, según §5.5(e). El de la población completa **no lleva p-valor**, porque su
> nula no está definida.

## Lo que NO cambia

§0–§4, §5.1–§5.4, §5.5(a)(b)(d), §6, §7, §8 y todo lo vigente de A–K.

> **ADVERTENCIA, la de D a K:** «no cambia» significa «esta enmienda no lo toca», **nunca «ya está
> revisado»**.

## Nota de método

**El fallo no lo encontró leer el código: lo encontró imprimir una línea.** El script imprimía
«eventos con exactamente 1 banda ganadora» antes de cualquier estadístico, y dijo **8 de 1 308**. Sin
esa línea, el `p = 1,0000` habría pasado por «el mercado está calibrado, no se rechaza» — que es la
conclusión cómoda y era un artefacto de la nula.

**La lección que sí generaliza:** una nula que «respeta por construcción» una propiedad de los datos
está afirmando esa propiedad, y una afirmación sobre los datos dentro de un preregistro hay que
medirla antes de congelarla, igual que cualquier otra.
