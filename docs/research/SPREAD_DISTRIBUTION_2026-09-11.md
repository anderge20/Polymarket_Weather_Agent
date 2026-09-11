# El spread no es un número, y los dos que teníamos eran estadísticos distintos

**Sesión A, 2026-09-11.** Medido sobre los 36 850 libros reales commiteados en la rama
`paper-state` (09-09 a 09-11, `source = clob_books_poll`). Reproducible offline con
`scripts/research/spread_distribution.py`, que lee los shards por `git show` y no necesita ni
red ni base de datos.

## El defecto que esto resuelve

El proyecto venía arrastrando **dos números para una magnitud**:

- **0,0168** como «semidiferencial medido» — la mitad de una **media** de 0,0336 tomada sobre
  una muestra temprana. **§6.2 del preregistro R30 apoya en él su desenlace *a priori* más
  probable**, y se usó para declarar que R21 había subestimado el coste en un 68 %.
- **0,0100** como spread **mediano** — la mitad, 0,0050, es tres veces menor.

**Ninguno está mal.** Son estadísticos distintos de una distribución cuya media es **1,93 veces
su mediana**. Es la cuarta vez en un día que dos contabilidades de una misma magnitud se hacen
pasar por una — y la tercera en la que el error tiene la forma *«un resumen puesto donde hacía
falta una distribución»*.

## La distribución

    libros: 36.850    dos lados 25.736    UN SOLO LADO 11.114 (30,2 %)

    media    0,0193    -> semidiferencial 0,0096
    mediana  0,0100    -> semidiferencial 0,0050

    p10 0,0020 · p25 0,0080 · p75 0,0200 · p90 0,0400 · p99 0,1200 · max 0,8100

La cola es larga: el p99 es **doce veces** la mediana. Una media sobre esto no describe el
libro típico, describe el libro típico **más** la cola.

**Y el 30 % de los libros está cotizado por un solo lado.** No tienen spread — ni cero ni
ancho. Se cuentan aparte porque promediarlos en cualquier dirección inventa un número, y
porque un mercado que no se puede operar en los dos sentidos es un hecho sobre la liquidez
por derecho propio.

## Lo que hay que leer en vez de un número

| bin | n | mediana | media | p90 |
|---:|---:|---:|---:|---:|
| 0 | 8 037 | **0,0100** | 0,0130 | 0,0300 |
| 1 | 1 484 | 0,0200 | 0,0294 | 0,0500 |
| 2 | 1 258 | 0,0200 | 0,0399 | 0,0500 |
| 3 | 1 080 | 0,0200 | 0,0253 | 0,0400 |
| 4 | 987 | 0,0200 | 0,0219 | 0,0300 |
| 5 | 1 004 | 0,0200 | 0,0203 | 0,0300 |
| 6 | 1 055 | 0,0200 | 0,0252 | 0,0400 |
| 7 | 1 251 | 0,0200 | **0,0410** | 0,0500 |
| 8 | 1 478 | 0,0200 | 0,0293 | 0,0500 |
| 9 | 8 102 | **0,0100** | 0,0132 | 0,0300 |

*(bins de precio según §0 de R30: `min(int(p_mid*10), 9)`)*

**El spread depende del precio, y el patrón tiene forma de U invertida.** Los extremos —bins
0 y 9, que son el **63 % de los libros**— cotizan a **la mitad** de spread que el centro. Las
bandas «casi seguro que no» y «casi seguro que sí» son las baratas; la zona de duda genuina
cuesta el doble, y en el bin 7 la media llega a **0,0410**.

## Por qué esto importa y no es estadística descriptiva

**Cuál estadístico es el correcto depende de DÓNDE opera la estrategia**, y eso convierte
«¿cuánto cuesta un trade?» en dos preguntas que estaban fundidas en una:

1. Si operases **uniformemente al azar** sobre los libros, pagarías la media.
2. Operas **donde tu señal dispara**, que no es al azar.

Y ahí está lo incómodo: Strategy A compra donde más se separan `p_model` y `p_mid`. **La
separación grande vive en la zona de duda**, no en los extremos donde el precio está pegado a
0 o a 1. O sea que **la estrategia selecciona precisamente los bins caros** — mientras que el
63 % de los libros baratos son los que menos la interesan.

**Esto no rescata ni condena nada por sí solo**, y no lo presento como si lo hiciera: R22 ya
midió que el modelo pierde *dentro de cada bin de precio*, así que el coste no es lo que mata
a Strategy A. Lo que este documento cambia es que **cualquier modelo de coste futuro —el de
E1, el de market making, el de §6.2 de R30— tiene que condicionar por bin**, porque la
diferencia entre el bin 0 y el bin 7 es un factor de tres en la media.

## Lo que NO afirmo

- **No digo que 0,0168 esté mal.** Digo que es la mitad de una media de una muestra anterior,
  y que la media de hoy es 0,0193 sobre 25 736 libros. Si la muestra temprana daba 0,0336 de
  media, o la población cambió o eran poblaciones distintas — **eso está sin resolver y no lo
  resuelvo aquí.**
- **No digo cuál usar.** Digo que la pregunta «¿cuál es el spread?» no tiene respuesta hasta
  que se diga **sobre qué población** y **con qué peso**.
- **No mido lo que se paga de verdad**, que es el spread de los libros donde una orden
  *rellena*. Eso requiere ejecución simulada contra el libro, que existe (`R23`) pero no se ha
  corrido sobre esta serie.
