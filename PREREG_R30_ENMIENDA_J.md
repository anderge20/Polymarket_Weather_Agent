# PREREG R30 — ENMIENDA J: §5.5(d) ponía una MEDIANA donde el coste de una serie es la MEDIA

**Sesión B, 2026-09-11.** Décima enmienda a `PREREG_R30_PUERTA_SUSTRATO.md`. Índice y shas en
`R30_PREREG_CHAIN.md`. **Sigue sin calcularse la curva de fiabilidad.** Defecto encontrado por la
sesión A sobre el §5.5 que congelé hace minutos.

---

## El defecto, y es permisivo

§5.5(d) exige `|d_b| > semidiferencial **mediano** del intervalo + fees`. **Estratificar por precio
reduce el sesgo de la distribución pero no lo elimina:**

```
bin      n   mediana    media   media/mediana
  2   1.258   0,0100   0,0200      2,00x   <-
  7   1.251   0,0100   0,0205      2,05x   <-
  5   1.004   0,0100   0,0102      1,02x
```

De 1,93× global a entre **1,02× y 2,05× dentro del intervalo**.

**Por qué es permisivo:** si existe un sesgo `d_b` y la candidata **opera cada vez que aparece**, se
enfrenta a la **distribución** del intervalo, no a su mediana — y **el coste esperado de una serie de
operaciones es la MEDIA**. Con la mediana como umbral, **una candidata pasa §5.5(d) en los intervalos
2 y 7 con la mitad del sesgo que haría falta**. Y son dos de la zona de duda.

**Cuarta vez hoy de la misma forma:** un **resumen** puesto donde hacía falta una **distribución** —el
0,0168 de n=27, la k de dos puntos, `store_rows_loaded` contando copias, y esto.

## La decisión que faltaba, tomada aquí

A no propuso arreglo porque **depende de algo que nadie había decidido**: ¿la candidata opera **todas**
las apariciones del sesgo, o **filtra** por spread observado? Se decide ahora, y en general, porque
R30 es una puerta y no una candidata:

> **§5.5(d) (enmendado J) — EL ESTADÍSTICO DE COSTE SE CALCULA SOBRE LA MISMA POBLACIÓN QUE LA
> CANDIDATA OPERA.**
>
> 1. **Por defecto —ninguna candidata declara filtro— la población es el intervalo entero y el umbral
>    es la MEDIA** del semidiferencial de ese intervalo, más las fees de D19. La media, porque el
>    coste esperado de una serie de operaciones es la media, no la mediana.
> 2. **Si la candidata declara un filtro de ejecución** —por ejemplo cotizar sólo con el libro por
>    debajo de cierto spread— **entonces opera un SUBCONJUNTO del intervalo, y todo se recalcula sobre
>    ese subconjunto**: el umbral de coste **y los conteos de §4.2**. No vale medir el coste en el
>    subconjunto y la potencia en el intervalo entero.
> 3. **El filtro, si existe, se declara ANTES** en el preregistro de la candidata, con su predicado
>    exacto. Un filtro añadido después de ver la curva es exactamente lo que §5.4 prohíbe.
> 4. **Se reportan SIEMPRE las dos cifras** —mediana y media del semidiferencial de la población
>    operada— **con su n**, para que el sesgo de la distribución quede a la vista en vez de resumido.

**Lo que esto cierra:** el umbral deja de depender de un estadístico elegido y pasa a depender de **qué
se opera**, que es una decisión de diseño que la candidata tiene que declarar de todos modos. **Y lo
que no puede quedarse es la mediana sin decir cuál de las dos cosas se hace** — eso deja la elección
para después del resultado.

## Lo que NO cambia

§0–§4, §5.1–§5.4, §5.5(a)(b)(c)(e), §6, §7, §8 y todo lo vigente de A–I.

> **ADVERTENCIA, la de D a I:** «no cambia» significa «esta enmienda no lo toca», **nunca «ya está
> revisado»**.

## Nota de método

**El número que hizo permisivo mi criterio —la mediana por intervalo— lo publicó A en su tabla del
#29, y lo encontró A.** Ninguno de los dos lo vio al escribir la Enmienda F, donde esa tabla entró por
primera vez, ni al escribir la I, que la usó como umbral. **Una tabla correcta usada como si fuera un
resumen suficiente: el dato no falló, falló lo que se le pidió.**
