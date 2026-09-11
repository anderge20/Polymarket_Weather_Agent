# Cadena de preregistro R30 — índice fechado

**Actualizado 2026-09-11.** Este fichero **se actualiza**; los documentos que indexa **no se tocan
jamás**. Editar un congelado rompe su sha y con él la única prueba de que se congeló antes de
calcular nada.

**Existe porque un congelado no puede apuntar hacia adelante.** Quien llegue a
`PREREG_R30_PUERTA_SUSTRATO.md` por su sha —que es cómo se llega a un congelado— leería la versión
con §4.2, §4.3, §5.2, §5.3 y §5.4 rotos y **nada se lo advertiría**. Es el defecto 4 de
`reference-layer-audit`: *cada documento es correcto por separado; sólo la cadena miente.*

> ## SI VAS A USAR R30, LÉELO CON LAS ENMIENDAS A, B, C, D, E, F, G, H, I Y J.
> El documento base **por sí solo no describe ningún criterio vigente de §4.2, §4.3, §5.2, §5.3 ni
> §5.4.**

## Estado, hoy

| documento | sha256 | estado |
|---|---|---|
| `PREREG_R30_PUERTA_SUSTRATO.md` | `0a5b794e656390b13e33f14a40260f7a7818b13928f45db7d1a5312deb0caaaf` | **BASE — VIGENTE con A+B+C+D** |
| `PREREG_R30_ENMIENDA_A.md` | `b2ecac699fa097cc5d23ff0513ced1a05d683aff89c92a92312705961d9aec33` | **VIGENTE** |
| `PREREG_R30_ENMIENDA_B.md` | `116b78b06f82b0bcc9b2be2083390f0d5169577b3806ad5fe9152debd9dd9a0a` | **VIGENTE** (su §5.4 lo refina C) |
| `PREREG_R30_ENMIENDA_C.md` | `2fecf29200624cd5f440a656941a0f4ef2a44279d36c806dc2d6d81408c99534` | **VIGENTE** |
| `PREREG_R30_ENMIENDA_D.md` | `d2ae02d2712a9be75f9a0716f8f0b154257573a91c798780dbcdd768c989ac4f` | **VIGENTE** |
| `PREREG_R30_ENMIENDA_E.md` | `34906daa3117486b012f0a532775efed5d9eeb616a6e5f632f8808cd397bd00b` | **VIGENTE** (su §3 y §6.2 los sustituye F) |
| `PREREG_R30_ENMIENDA_F.md` | `2fd946b53cc9e05cf528f959718918888a78a03df60133f65b725148e5ba14d1` | **VIGENTE** (su párrafo de sustrato lo sustituye G) |
| `PREREG_R30_ENMIENDA_G.md` | `ee5949a06975268547a6a84a102dc23f8835ed1704ef6f018d567768bf252ce5` | **VIGENTE** |
| `PREREG_R30_ENMIENDA_H.md` | `42bead6798d79a248c6c55f55a897be4a8dd37550eb4ed8965c3911e41523f4c` | **VIGENTE** (su «obligación más dura» la RETIRA I) |
| `PREREG_R30_ENMIENDA_I.md` | `03f0b5a292425d7f6c50c08feca6a4d6cc429b0e8d537183a7c3fc97e61e71fb` | **VIGENTE** (su §5.5(d) lo sustituye J) |
| `PREREG_R30_ENMIENDA_J.md` | `bbac91ffecf0183711ab18ff020cbb0b819340ddc451aceefa8547d64c86ab31` | **VIGENTE** |

**Nada se ha calculado todavía contra R30.** Base y cuatro enmiendas son del mismo día,
2026-09-11, todas anteriores a tocar un solo dato.

## Qué cláusula gobierna qué, y dónde leerla

| cláusula | dónde está la versión VIGENTE | qué pasó |
|---|---|---|
| §0 `precio_bin` | **C** | no existía; el eje sólo estaba definido en `run_r22.py:129`. Congelado por valor |
| §1.1 | base, **nota en E** | sobrevive al defecto de `select_tau` del PR #28: su evidencia es independiente de τ |
| §2 | base, precisado por C | |
| §3 | **E, luego F** | E: 0,0168 era de n=27 sin población. **F: magnitud ESTABLECIDA** — en la zona operada la mediana es 0,0100, exactamente el `x_exec` de R21; la media 0,0148. Más el 30,2 % de libros de un solo lado |
| §6.2 | **E, luego F** | **F lo DEGRADA**: pierde el rango de «a priori el más probable». El coste en la zona operada es en mediana el que R21 ya suponía, así que no explica nada nuevo; sigue vivo por la COLA (media 1,48×) |
| §4.1 | base, **acotado por H** | 60 días de LIBRO, **sólo para candidatas que requieran libro**. Las que usen el sustrato que R21/R22 ya tenían quedan fuera — a cambio de declarar qué midieron aquéllas y por qué no responden ya la pregunta |
| §4.2 | **A, B, precisado en G** | A: «en cada uno» era conjunción por evento, inviable. B: se cuenta **post-borrado** |
| §4.3 | **D, precisado en G** | «liquidado» sin definir; fijado como **resuelto por el mercado**, sin depender de `stage_settle` |
| §5.1 | base, ajustado por C | el umbral del IC pasa a «≥60 % de la familia» |
| §5.2 | **D** | no declaraba unidad; **mediana SOBRE EVENTOS** + IC bootstrap por eventos |
| §5.3 | **D** | decía sólo «el signo se mantiene»: sin estadístico ni incertidumbre. Ahora ambos nombrados |
| §5.5(d) | **I, sustituido por J** | el umbral de explotabilidad usaba la MEDIANA del intervalo; el coste de una serie es la MEDIA (hasta 2,05x dentro del bin). Ahora el estadístico se calcula **sobre la población que la candidata opera**, y el filtro —si lo hay— se declara antes |
| §5.5 | **I** (nuevo) | contraste de calibración del mercado: estadístico, IC, criterio de mal calibrado, umbral de explotabilidad y regla de potencia — todo fijado ANTES de calcular la curva |
| §5.4 | **B, luego C** | B: familia enumerada y cerrada. C: la parte de precio pasa a **regla de ocupación** |
| §6.1, §6.3, §7, §8 | base | sin cambios |

## Cómo se encontró cada cosa, porque importa para el método

- **§4.2 (A)** — B, revisando su propio documento. Fallaba en dirección **restrictiva**: sólo podía
  fallar, y habría dado a «no evaluable por sustrato» apariencia de hallazgo empírico.
- **§5.4 y §4.2 post-borrado (B)** — **A**, revisando el de B. §5.4 fallaba en dirección
  **permisiva**: sin familia fija, «el máximo sobre la familia declarada» **legitima justo lo que
  prohíbe**.
- **§0 y la regla de ocupación (C)** — B, aplicando al resto de su documento la lección que A
  acababa de enseñarle sobre **una** línea. Y descubriendo que **la Enmienda B había abierto un
  hueco permisivo dentro de la enmienda escrita para cerrar uno**: enumeró cinco intervalos de
  precio cuando la variable tiene diez niveles.
- **§5.2, §5.3, §4.3 y esta cadena (D)** — **A**, en una cuarta pasada pedida expresamente en
  dirección permisiva.
- **§3, §6.2 y la nota de §1.1 (E)** — dos disparadores externos: **A** midiendo el spread sobre
  `paper-state` y no coincidiendo con la cifra de B; y el **PR #28**, de una sesión en la nube que no
  coordinó ninguno de los dos, encontrando que `select_tau` maximiza una mediana que —con acierto
  bajo el 50 %— es siempre el PnL de un perdedor, o sea **el precio del billete**.
- **§5.5(d) (J)** — **A** encontró que el umbral de explotabilidad usaba la **mediana** del intervalo
  mientras el coste esperado de una serie es la **media**: dentro del bin el sesgo va de 1,02x a
  **2,05x**, así que una candidata pasaba en los intervalos 2 y 7 **con la mitad del sesgo necesario**.
  A **no propuso arreglo** porque dependía de una decisión sin tomar —¿opera todas las apariciones o
  filtra por spread?—, y B la tomó en general: **el estadístico de coste se calcula sobre la misma
  población que se opera**, por defecto la media del intervalo entero. *Cuarta vez del día: un resumen
  donde hacía falta una distribución.*
- **§5.5 y las correcciones a H (I)** — A atacó la H a petición de B y **los dos puntos que B pidió
  atacar cedieron**: (a) la H decía que su obligación era «más dura» que la puerta, **falso** —una
  declaración cuesta una tarde y la puerta sesenta días—, y el criterio correcto no es *¿es más cara?*
  sino ***¿filtra lo que la puerta filtraba?***; (b) la H **no fijaba el criterio de decisión** de la
  curva de fiabilidad, que habría quedado para después del dato. Y A señaló lo que la H implicaba y no
  decía: **la explicación de R21 descansa sobre una premisa no medida**, así que esta vía **es el test
  de esa premisa**.
- **§4.1 acotado (H)** — una TERCERA sesión (la de la nube) mató dos de las tres vías de edge contra
  un umbral preinscrito **1h09m antes del dato** (verificado en el historial: `b95564a` 15:24:18Z
  frente a `a0eeb11` 16:33:34Z). La superviviente —**calibración del precio**— **no necesita libro**,
  y §4.1 la habría bloqueado dos meses. Verificado además que **ninguna medición de R21/R22 toca la
  calibración del MERCADO**: todas son sobre `p_model`, y el Brier del mercado mide que es informativo,
  no que esté calibrado.
- **§3 sustrato y §4 conteo (G)** — A rehizo por MERCADO el «~70 % de filas» de F: **47 % siempre /
  26 % NUNCA / 27 % intermitente**, y la liquidez resultó ser propiedad del mercado (100 % de
  acoplamiento). B midió entonces **dónde** vive la iliquidez: en los **extremos** de precio (41,6 %)
  y casi no en la zona de duda (2,7 %) — un mercado intermitente **sólo cotiza los dos lados cuando
  el desenlace ya está decidido**.
- **§3 y §6.2 (F)** — A midió el spread **por bin de precio** y salió una U invertida; B lo reprodujo
  sobre la definición congelada del §0. La zona de duda cuesta el doble que los extremos, **lo que
  convierte el argumento estructural de §3 en una medición**. Y de paso deshizo el «a priori más
  probable» de §6.2, que era una declaración que **favorecía a quien la escribió**.

**La regla que sale, y es de A:** *una sección que enmiendas sucesivas declaran intacta deja de
mirarse.* Tres enmiendas listaron §5.2 y §5.3 en «lo que NO cambia», y eso los protegió de la
revisión. **«No cambia» significa «esta enmienda no lo toca», nunca «ya está revisado».**

**Y la otra:** *una enmienda es un cambio de código con otro nombre y puede introducir la clase de
defecto que viene a corregir.* Se revisa igual que un parche.
