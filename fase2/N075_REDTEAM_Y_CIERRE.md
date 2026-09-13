# NIVEL 0.75 · punto 7 — RED‑TEAM DE H1…H6 Y VEREDICTO DE CIERRE

Instrumento: yo mismo, por ausencia de la sesión B desde ~15:00Z. **Una autorrevisión es un
instrumento más débil que un segundo par de ojos y eso no se compensa escribiendo más.** La
petición de revisión hostil a B sigue abierta. Lo que sí se ha hecho es atacar cada hipótesis
con una medida que **podía salir en contra**, y dos salieron en contra de lo que yo creía.

---

## H1 — «Los 138 nuevos eventos son el mismo producto»

**Ataque principal: los atributos con los que se verificó no podían fallar.**
`resolution_source`, `unit` y `rounding_rule` valen lo mismo en los 187 eventos de EGLC —
son constantes de la estación, no evidencia de homogeneidad. *Un criterio que sólo puede
pasar no es un criterio.* Así que busqué los atributos que **sí varían** dentro de EGLC:

| atributo | los 49 viejos (529 mercados) | **los 138 nuevos (1 468 mercados)** |
|---|---|---|
| `tick_size` | 522 × 0,001 **+ 7 × 0,01** | **1 468 × 0,001** |
| `uma_resolution_status` | 528 `resolved` **+ 1 `proposed`** | **1 468 `resolved`** |
| prefijo `arch-` en el slug | **33 mercados, 3 eventos** | **0** |
| `unit` / `rounding_rule` / `resolution_source` | constantes | constantes |
| escaleras | `{9: 5, 11: 44}` | `{7: 2, 9: 21, 11: 115}` |

> **El ataque falla, y falla invertido: las anomalías están en los 49 VIEJOS, no en los 138
> nuevos.** Mezcla de `tick_size` dentro de un mismo evento, un mercado sin liquidar y los
> slugs `arch-` son todos del conjunto que ya teníamos. Los 138 nuevos son homogéneos en
> todos los atributos medibles.

**Y una refutación mía que estuve a punto de publicar y era falsa.** Medí que 33 slugs de
EGLC **no** empiezan por `highest-temperature-in-london`, y eso contradice literalmente el
punto 1 aceptado. Antes de escribirlo comprobé a qué conjunto pertenecen: **los 3 eventos
`arch-` están entre los 49 viejos**, no entre los 138. La afirmación del usuario es **cierta
tal como está enunciada** (sobre los 138) y **falsa si se extiende a los 187**, que es la
extensión que yo iba a hacer. Queda dicho porque el enunciado correcto importa: *«los slugs
de los 138 nuevos son exclusivamente `highest-temperature-in-london-*`; 33 mercados de 3
eventos VIEJOS llevan el prefijo `arch-` y otra gramática de slug (`-on-may-17-2026-11c`)».*

**Lo que sigue sin poder comprobarse:** `open_time`, `last_traded_time`, `daily_high_time`,
`resolution_timestamp`, `settlement_timestamp`, `available_at`, `discovered_at`, `data_start`
y `data_end` están **NULL en 1 997 de 1 997**. No se puede comparar la vida del mercado, ni
el volumen, ni cuándo se propuso la resolución. La homogeneidad está verificada en los
atributos **de contrato**; en los de **mercado** no hay datos para verificarla ni para
refutarla.

**Conclusión H1: NO REFUTADA. Confianza ALTA** para los atributos de contrato, **NULA** para
los de mercado, que no existen en el almacén.

---

## H2 — «La regla de población no introduce selección basada en el resultado»

**Ataque: la elegibilidad exige "exactamente una ganadora", que es una condición SOBRE el
resultado.** Cierto en la forma. La pregunta real es si selecciona por el VALOR del
resultado.

* Tasa de exclusión en CORRECTED: **1 de 187 = 0,53 %**. Con tan poco excluido no hay espacio
  para un sesgo material, sea cual sea su dirección.
* El único excluido (2026‑05‑20, evento 496987) se excluye porque **un mercado de los 11
  sigue `proposed`** — y el máximo observado de ese día, 20,0 °C, cae en el **percentil 32,6**
  de los 135 incluidos con observación (media 23,44; rango 12–36). **No es un día extremo.**
* El desempate del 2026‑05‑19 elige entre dos escaleras que **tienen la misma ganadora,
  18 °C**. La regla no pudo cambiar el resultado ni queriendo.
* El desempate usa `close_time`, que es **la única marca temporal poblada** de las nueve.
  Eso es una dependencia sin repuesto y va a la lista de riesgos.

**Ataque secundario, y éste sí muerde en OLD:** en `backfill_2b_v1` se excluyen **123 de 163
fechas**, el 75 %. Si alguien leyera OLD como «la población histórica», eso sería una
selección masiva. No lo es dentro de esta comparación —OLD es un brazo de contraste, no la
población final— pero **cualquier uso futuro de `backfill_2b_v1` como población hereda ese
75 %.**

**Conclusión H2: NO REFUTADA para CORRECTED. Confianza ALTA.** Para OLD la hipótesis **no
aplica** y se dice.

---

## H3 — «OLD vs CORRECTED cambia únicamente la población»

**Ataque: es falsa en la lectura natural, y está documentada como tal.** Comparar el
resultado histórico de `n1_20` con una reejecución cambia **siete** elementos
(`N075_AISLAMIENTO_CAUSAL.md` §1), ninguno de ellos la población: universo filtrado por un
backtest que mira el precio, ventana temporal, serie de observación, dos `dataset_version`
sin filtrar, número de modelos y definición de B1.

**En la comparación reparada la hipótesis es cierta en lo metodológico** —una sola
implementación, un solo parámetro, y la tabla de trece filas de §2 con **doce «idéntico»**—
**pero sigue siendo engañosa en lo sustantivo**: el tratamiento arrastra una extensión
temporal de 40 a 117 fechas que va de primavera a verano, **+9,57 °C en la media del
objetivo**. Por eso las tres comparaciones, y por eso la primaria es C1.

**Evidencia definitiva a favor, y es un número:** sobre las 40 fechas comunes los dos brazos
dan **igualdad exacta en coma flotante en cinco de seis modelos** y **+8,98·10⁻⁵** en el
sexto, `B0_clima30`, localizado en un solo evento. Y `REF_uniforme` vale 0,082645 en los
cuatro cuadrantes, lo que prueba que **el código de puntuación no depende de la población**.

**Conclusión H3: REFUTADA en la lectura ingenua, CIERTA en la reparada, y con un confusor
estacional nombrado que impide leer C2 como efecto de la corrección. Confianza ALTA.**

---

## H4 — «Las escaleras 7/9/11 pueden compararse sin mezclar contratos incompatibles»

**Ataque: la línea base depende de la escalera, y por un margen que se come el efecto.**

| escalera | `REF_uniforme` Brier | Log Loss |
|---|---|---|
| 7 bandas | **0,12245** | 0,41012 |
| 9 bandas | **0,09877** | 0,34883 |
| 11 bandas | **0,08264** | 0,30464 |

El recorrido 7→11 es **0,0398 de Brier**. El mayor delta OLD↔CORRECTED de todo el punto 1 es
**0,00991** (`B3`, lead 24, C2). **La contaminación por escalera sería cuatro veces mayor que
el efecto que se pretende medir.** H4, tal como está enunciada, **es falsa**: dos escaleras
distintas NO son comparables sin normalizar.

**Y sin embargo no rompe nada aquí, por una razón que hay que verificar y no suponer:** la
población puntuada es **100 % de once bandas en los dos brazos y en los dos leads**. Los 28
eventos de 7 y 9 bandas son de 2025‑12‑31 → 2026‑03‑15 y **no hay ni observación ni
pronóstico de EGLC antes de 2026‑04‑08**. Aportan cero.

> **H4 no está validada: está SIN EJERCITAR.** Declararla validada porque «no dio problemas»
> sería exactamente la trampa del criterio que sólo puede pasar. **Disparador escrito: en
> cuanto entre un solo evento de 7 o 9 bandas en una población puntuada, hay que fijar la
> normalización ANTES de mirar el resultado.**

**Conclusión H4: REFUTADA como enunciado general. Inocua en esta ventana por una razón
medida. Confianza ALTA en las dos mitades.**

---

## H5 — «`winning_outcome` representa correctamente la liquidación»

Cerrada en A‑276 y reatacada aquí:

* Unicidad **fuera de EGLC también**: en `markets_v2` completo, **7 329 eventos con
  exactamente una ganadora y 2 con ninguna**. Cero con más de una, en las 45 estaciones.
* EGLC: `{1: 187}`, partición completa en 187 de 187.
* **No hay portador redundante**: `is_winner` es NULL en 3 994 de 3 994. La validación interna
  sólo puede ser estructural, y ésa pasa. **Es un hueco real y se dice.**
* Comparación externa contra el proxy de observación: **136 coinciden, 1 difiere, 50 sin
  observación**. La única discrepancia es 2026‑05‑27, el caso ya caracterizado de
  `WINDOW_LOCAL_CIVIL_DAY`, con cota preinscrita **antes** de que estos datos existieran.
  **Un desacuerdo proxy↔contrato es del proxy, no de la resolución**: la fuente contractual es
  Wunderground y nuestra etiqueta es el máximo METAR de IEM.
* **Ataque nuevo:** los dos eventos del 2026‑05‑19, con escaleras desplazadas un grado y
  resueltos por separado, **coinciden en la ganadora (18 °C)**. Dos resoluciones
  independientes del mismo día que concuerdan es evidencia externa barata y salió a favor.

**Conclusión H5: NO REFUTADA. Confianza ALTA en la estructura, MEDIA en la correspondencia
con el mundo**, porque el único contraste posible es un proxy de otra fuente y hay 50 eventos
sin ninguno.

---

## H6 — «La población final no contiene duplicados económicos del mismo evento»

* `event_id` → fechas objetivo distintas: **`{1: 187}`**. Ningún evento abarca dos días.
* Fechas con más de un evento: **1** (2026‑05‑19).
* Tras deduplicar: **185 fechas, 185 `event_id` distintos** — biyección verificada, no supuesta.
* `token_id`: **3 994 filas, 3 994 distintos, 0 repetidos**.

**Ataque: el 2026‑05‑19 es un duplicado económico REAL** —dos escaleras de 11 bandas, las dos
`resolved`, simultáneas, sobre el mismo subyacente— y la regla se queda con una. Eso no lo
elimina del mundo: **elimina la doble contabilización de la muestra**, que es lo que H6
afirma. Lo que la regla **no** resuelve es cuál de las dos es «el» producto; se queda con la
que cierra antes por encima del día civil, y esa elección es **declarada, no derivada de los
datos**.

**Conclusión H6: NO REFUTADA para la población final. Confianza ALTA.** La existencia del
duplicado en el mundo queda documentada como fenómeno, no como defecto.

---

## CRITERIO DE CIERRE, punto por punto

| condición que impediría avanzar | estado |
|---|---|
| discrepancias no explicadas en `winning_outcome` | **ninguna** — la única (2026‑05‑27) es del proxy y está caracterizada |
| mezcla de productos | **ninguna en la población puntuada** — 100 % once bandas, verificado |
| duplicados económicos no resueltos | **ninguno** — biyección fecha↔evento tras deduplicar |
| cambio de metodología entre OLD y CORRECTED | **ninguno en la comparación reparada** — 12 de 13 filas «idéntico», la 13ª es el tratamiento |
| scoring incorrecto por escaleras variables | **no ocurre** — pero H4 queda SIN EJERCITAR, con disparador escrito |
| clipping / log‑loss sin resolver | **resuelto y acotado** — `EPS = 1e-6` idéntico en los dos brazos; el Log Loss de B1/B2 es aritmética del recorte y va con la advertencia pegada |
| falta de reproducibilidad | **cubierta** — `N075_REPRODUCIBILIDAD.md`, con cuatro `sha256` del contenido leído |

---

# VEREDICTO

## `LEVEL_0.75 = CLOSED`

### DATASET VALIDATION — **CERRADO**
Las diez identidades pasan (18 de 18 comprobaciones), 187 eventos con partición completa y
ganadora única, biyección fecha↔evento tras deduplicar, 0 duplicados de `token_id`, y los
138 eventos nuevos son **más** homogéneos que los 49 que ya teníamos.

### SETTLEMENT SUBSTRATE — **NO VALIDADO**
`measurement_rule_code` y `contract_source` son **NULL en 85 878 de 85 878** filas de
`markets`. El núcleo congelado rechaza la terna `(None, None, 'C')` con
`context_out_of_snapshot`. Y `settle_substrate_missing` **devuelve `[]` sobre esa misma base
de datos**, ejecutado y comprobado: un falso OK que convierte «no hay sustrato» en «el núcleo
rechazó estos mercados». Diagnóstico y cambio mínimo propuesto en
`N075_SUSTRATO_LIQUIDACION.md`; **producción sin tocar**.

### OLD vs CORRECTED — **RESULTADO**
Sobre la población compartida (C1, la única comparación causalmente limpia): **igualdad
exacta en cinco de seis modelos y +8,98·10⁻⁵ en `B0_clima30`**, localizado en un evento. *La
corrección del dataset no mueve la métrica sobre lo que ya estaba bien.* Los deltas de la
comparación completa (C2, hasta −0,0099 de Brier) **se reproducen dentro de un solo dataset**
al separar las 77 fechas nuevas (C3), y son **estacionales**: +9,57 °C de media en el
objetivo. **Esto es CORRECCIÓN DE DATASET VALIDADA. No es alfa, no es mejora predictiva y no
es ventaja económica.**

### RIESGOS QUE QUEDAN
1. **Sustrato de liquidación ausente** y guarda con falso OK. Bloquea liquidar de verdad, no
   bloquea Level 1 sobre `winning_outcome`.
2. **H4 sin ejercitar.** Disparador: el primer evento de 7 o 9 bandas en una población
   puntuada obliga a fijar la normalización antes de mirar.
3. **Nueve marcas temporales NULL de nueve**, `close_time` incluido como única superviviente
   — y el desempate de la población depende precisamente de ella, sin repuesto.
4. **Sin portador redundante de la ganadora** (`is_winner` NULL en 3 994 de 3 994): la
   validación de `winning_outcome` sólo puede ser estructural.
5. **50 eventos sin observación** (fuera de 2026‑04‑08 → 2026‑08‑23): cualquier métrica que
   necesite la etiqueta observada trabaja sobre 137, no sobre 187, y las dos cifras van juntas.
6. **La ventana puntuable es 117 fechas de una sola estación.** No hay nada aquí que
   autorice a generalizar a las otras 44.
7. **La revisión hostil la hice yo.** Encontró dos cosas —el `JOIN` sin `dataset_version` en
   mi propio `n1_40` y una refutación mía que era falsa— pero no es sustituto de B.

**Nada de esto levanta el gate D0. Ningún dinero real.**
