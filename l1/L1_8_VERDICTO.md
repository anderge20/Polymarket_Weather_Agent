# LEVEL 1 · L1.8 — VEREDICTO

    D0-R = READY     D0-P = BLOCKED
    L1.3 = CLOSED · L1.4 = CLOSED · L1.5 = CLOSED · L1.6 = CLOSED · L1.7 = CLOSED

Sigue prohibido y no realizado: producción, paper trading, dinero real, PnL, ejecución,
umbrales, estrategia, optimización de entradas/salidas, selección de precio, liquidez,
modificación del bot. **Esto es un veredicto científico, no operativo.**

---

# 1 · VERDICT

## 🟡 `L1.8 = INCONCLUSIVE`

# 2 · ONE-SENTENCE VERDICT

> **Hay una señal real, temporalmente alineada y robusta a los controles que construimos —pero
> su tamaño se ha dividido por 4 cada vez que hemos encontrado un benchmark estructural mejor,
> descansa entera sobre una convención de disponibilidad que nunca hemos verificado, y sólo
> existe en una ciudad, una estación y cuatro meses: no hemos demostrado predictive power, hemos
> demostrado un candidato a predictive power.**

# 3 · EVIDENCIA A FAVOR (5)

1. **Sobrevive al benchmark estructural más exigente que construimos.** `B4 − CTRL_escalera`
   = **−0,00761 [−0,01224, −0,00286]** (lead 24) y **−0,01340 [−0,01760, −0,00891]** (lead 9);
   los dos IC excluyen el cero contra un control que **ignora el pronóstico por completo**.
2. **Los doce placebos temporales van al otro lado y son monótonos en `|k|`**: +0,008 a un día
   de desfase, +0,041 a siete. *Una señal alineada con el día que predice, no un artefacto de
   estructura.*
3. **Permutación de la ganadora: `p = 0,0010`**, el suelo de 1 000 permutaciones, en los dos
   leads — y el nulo permutado sale **positivo**, que es lo que debe pasar.
4. **Robustez al único parámetro libre**: `MIN_TRAIN` 20/30/40/50 da ocho IC y **los ocho
   excluyen el cero**, con el efecto estable (−0,0115…−0,0138 y −0,0172…−0,0175).
5. **Ranking muy por encima del azar y no concentrado en artefactos**: rango medio de la
   ganadora **2,34–2,71** contra 6,0, y la ventaja **se conserva en el grupo interior**
   (n = 92/93), no vive en las bandas abiertas.

# 4 · EVIDENCIA EN CONTRA (8)

1. **El efecto se deflactó ×4,0 y ×2,7 al mejorar el benchmark, y la serie es monótona
   decreciente.** No tenemos ninguna razón para creer que `CTRL_escalera` sea el último
   benchmark estructural; sí tenemos tres precedentes de que el siguiente encogió el efecto.
2. **`available_at` es una convención sin validar externamente**, y es **load-bearing**: a
   lead 24 el margen es **1,24 h**. Si la latencia real del proveedor fuese ~1,3 h mayor que la
   supuesta, **todo el lead 24 sería look-ahead**.
3. **A lead 24 el efecto contra `CTRL_escalera` apenas supera el mínimo detectable**: razón
   obs/MDE = **1,13**, y `B4` gana al control en sólo **59 de 95** eventos (62 %).
4. **A lead 24 hay heterogeneidad temporal detectable**: la diferencia entre mitades es
   +0,01056 **[+0,00231, +0,01914]**, IC que excluye el cero, con la primera mitad tocando el
   cero (+0,00006). **No satisface un criterio fuerte de consistencia temporal.**
5. **Una ciudad, una estación, cuatro meses**, y **abril no está en la muestra puntuada**. No
   hay ninguna réplica independiente: los ocho IC de robustez son **el mismo corpus**.
6. **La geometría de la escalera —sin mirar el tiempo— ya bate al uniforme** y explica el
   **33,9 %** (lead 24) y **22,6 %** (lead 9) de la ventaja frente al uniforme.
7. **La calibración de `B4` no es evidencia independiente**: por construcción es un estimador de
   frecuencia de la misma cantidad que luego se mide. Prueba estabilidad de la distribución de
   error, no habilidad.
8. **Los leads no son dos muestras**: `r = +0,595`, tamaño efectivo ~**119**, no 190.

# 5 · EFECTO ESTIMADO HONESTO

| benchmark | lead 24 | lead 9 | qué descuenta |
|---|---|---|---|
| `B4 − B0` *(pre-registrado)* | **−0,0304** | **−0,0359** | nada: `B0` resultó **peor que el azar** |
| `B4 − uniforme` *(control estructural)* | **−0,0115** | **−0,0173** | lo malo que es `B0` |
| **`B4 − CTRL_escalera`** | **−0,0076** | **−0,0134** | **además, el centrado de la escalera** |
| | 9,2 % del nulo | 16,2 % del nulo | |
| razón efecto/MDE | **1,13** | **2,14** | |
| eventos en que gana | 59/95 (62 %) | 79/96 (82 %) | |

**Por qué el tercero es el benchmark más exigente:** los otros dos comparan contra rivales que
*no saben nada del contrato*. `CTRL_escalera` compara contra un rival que **sabe dónde puso el
mercado las bandas** — la única información de mercado que L1 puede usar sin mirar precios. Es
el suelo más alto que sabemos construir sin entrar en L2. **Y sigue siendo un suelo bajo**: usa
sólo el *centro* de la escalera, la lectura más pobre posible de lo que el mercado sabe.

# 6 · LEAD 24 VS LEAD 9

| | lead 24 | lead 9 |
|---|---|---|
| efecto contra `CTRL_escalera` | −0,0076 | −0,0134 |
| razón obs/MDE | 1,13 | **2,14** |
| consistencia temporal | **NO** (IC de la diferencia excluye el cero) | **sí** (incluye el cero) |
| margen de `available_at` | **1,24 h** | 4,24 h |
| cuota de la geometría | 33,9 % | 22,6 % |
| eventos ganados al control | 62 % | 82 % |
| **componente** | **🟡 INCONCLUSIVE** | **🟢 GO como componente** |

**No se selecciona lead retrospectivamente.** El lead 9 es mejor en las seis columnas, pero el
veredicto global **no** se emite sobre el lead 9 solo: los dos estaban pre-registrados, los dos
se reportan, y el global se emite sobre el conjunto.

# 7 · RIESGOS

| riesgo | severidad | impacto sobre la conclusión |
|---|---|---|
| `available_at` es una convención no verificada | **ALTA** | si falla, **invalida lead 24 entero**; lead 9 aguantaría hasta ~4,2 h de error |
| existe un benchmark estructural mejor que `CTRL_escalera` | **MEDIA-ALTA** | la serie ×4 → ×2,7 es monótona; otro control podría reducir más el efecto |
| corpus único (ciudad/estación/meses) | **ALTA** | ninguna réplica independiente; la robustez medida **no** es validación externa |
| heterogeneidad temporal del lead 24 | **MEDIA** | degrada el lead 24 a inconclusivo; no afecta al lead 9 |
| construcción de `B4` (calibración casi tautológica) | **BAJA-MEDIA** | no invalida el Brier ni el ranking, pero anula la calibración como evidencia |
| selección post-hoc | **BAJA** | todo pre-registrado; el control uniforme, declarado ex-post **y etiquetado** |
| proxy IEM/Wunderground | **BAJA** | 1 discrepancia en 137; no toca el target |
| dependencia entre leads | **BAJA** | ya contabilizada: n efectivo 119 |

## Análisis cualitativo pedido en §12

*¿Qué probabilidad hay de que `B4 − CTRL_escalera` sea consecuencia de…?*

| fuente | riesgo | razonamiento |
|---|---|---|
| **estructura de mercado** | **MEDIO** | `CTRL_escalera` sólo descuenta el *centro*. El resto de la geometría —anchura, asimetría, qué bandas abre— no está descontado |
| **selección temporal** | **BAJO-MEDIO** | corte pre-registrado y no se buscó otro; pero el lead 24 **falla** el test |
| **construcción de `B4`** | **BAJO** | los placebos rompen el efecto y la construcción no depende del alineamiento temporal: si fuese un artefacto de construcción, el desfase no lo borraría |
| **este corpus concreto** | **ALTO** | una ciudad, una estación, cuatro meses. **Es el riesgo dominante y no se puede reducir con estos datos** |

# 8 · AVAILABILITY — por qué sigue abierta

`available_at = issue_time + 4:45:36` es **constante en las 236 filas**: no es una medición, es
una **convención aplicada en el backfill**. Que `available_at ≤ t_asof` se cumpla en 95/95 y
96/96 demuestra que **el código respeta la convención**, no que el pronóstico estuviera
públicamente disponible en ese instante.

El margen es **1,24 h** (lead 24) y **4,24 h** (lead 9). Las 2 727 filas son backfill
(`fetched_at` 2026-09-09): **no hay ni una sola fila con un instante de disponibilidad
observado**. **Es comprobable hacia delante** con el colector en vivo (tarea #75) y no se
resuelve inventando otra latencia.

# 9 · MARKET INFORMATION — por qué L2 es mucho más difícil que L1

    corr(centro de la escalera, observacion) = +0,957
    corr(nuestro pronostico,    observacion) = +0,973 / +0,979
    MAE centro de la escalera = 1,26-1,27 C     MAE pronostico = 1,014 / 0,885 C

**El mercado, con sólo la geometría de sus bandas, ya alcanza correlación 0,957 con la
temperatura final.** Nuestro pronóstico gana por **0,25 °C** (lead 24) y **0,39 °C** (lead 9).

Y eso es el **suelo** de lo que el mercado sabe: los **precios** llevan mucha más información
que el centro de la escalera. L1 ha medido nuestra ventaja sobre la lectura **más pobre
posible** de la información de mercado. **L2 tendrá que medirla contra la más rica.**

*Este proyecto ya tiene un precedente directo: R21 midió Strategy A como NO OPERABLE, y la
causa era de diseño — el mercado estaba mejor calibrado que el modelo. A4 es ese mismo hallazgo
reapareciendo una capa más arriba.*

# 10 · FINAL DECISION

**`INCONCLUSIVE`, y las cuatro categorías que §11 nombra como motivo para serlo tienen todas
una objeción viva:** availability (sin verificar), temporalidad (lead 24 heterogéneo), muestra
(un corpus único) y benchmark (deflación monótona sin suelo conocido). **Cuatro de cuatro.**

**No es un fracaso y no cierra Londres.** La señal es real: doce placebos limpios, permutación
en el suelo, robustez al parámetro, supervivencia a Bonferroni sobre 56 comparaciones contadas.
Lo que falta no es más análisis del mismo corpus — **ocho IC sobre los mismos 95 eventos no son
ocho pruebas** — sino evidencia que este corpus no puede dar.

## Qué resolvería la incertidumbre, en orden de coste

1. **Validar `available_at` hacia delante** (tarea #75). El colector en vivo ya registra el
   instante real. **Coste: esperar. Resuelve el riesgo ALTO número 1.** Si la latencia real
   supera la convención en más de 1,24 h, el lead 24 cae y el veredicto empeora; si la
   confirma, sube.
2. **Réplica en una segunda ciudad y/o una segunda estación.** Es la única forma de atacar el
   riesgo dominante. Requiere extender observaciones y pronósticos, con su presupuesto de
   peticiones preinscrito. **Sin esto, ninguna cantidad de análisis adicional sobre Londres
   cambia el veredicto.**
3. **Un benchmark estructural más exigente que `CTRL_escalera`** — la geometría completa
   (anchura y asimetría de la escalera), no sólo el centro. **Coste: bajo, no necesita datos
   nuevos.** Si el efecto sobrevive a ése también, la evidencia sube un escalón.

**Sólo cuando 1 y 3 estén resueltos y 2 en marcha tendría sentido reabrir L1.8.** Abrir L2 ahora
sería estudiar si un precio está equivocado usando una señal cuyo tamaño real no conocemos con
un factor de 4 de incertidumbre.

**No se abre L2. No se cierra Londres. `D0-P` sigue BLOCKED y el gate de dinero real sigue
siendo exclusivamente del usuario.**
