# NIVEL 0.75 · puntos 1 y 2 — Brier y Log Loss, `OLD` vs `CORRECTED`

**Esto no es Nivel 1.** No hay bootstrap, no hay intervalo de confianza, no se evalúa el
criterio CONFIRMA/REFUTA, no se ordenan modelos y no se declara poder predictivo. Las
métricas se usan aquí como **instrumento de validación del dataset**: la pregunta es si la
maquinaria métrica se comporta igual sobre las dos poblaciones.

Guion: `n075_metricas.py` · salida íntegra: `N075_METRICAS_SALIDA.txt` · población:
`n075_poblacion.py` · aislamiento causal y por qué las comparaciones son tres:
`N075_AISLAMIENTO_CAUSAL.md`, escrito y espejado **antes** de calcular nada (commit
`e432837`, 18:39:13Z).

---

## 0. Una referencia que no es un modelo, y por qué está aquí

`REF_uniforme` asigna `p = 1 / n_bandas`. No mira datos: es una propiedad de la
**estructura del contrato**. Sirve de control de la maquinaria métrica.

| | OLD lead 24 | CORRECTED lead 24 | OLD lead 9 | CORRECTED lead 9 |
|---|---|---|---|---|
| Brier/contrato | 0,08264 | 0,08264 | 0,08264 | 0,08264 |
| Brier/evento | 0,08264 | 0,08264 | 0,08264 | 0,08264 |
| Log Loss/contrato | 0,30464 | 0,30464 | 0,30464 | 0,30464 |
| tasa YES | 0,09091 | 0,09091 | 0,09091 | 0,09091 |

**Idéntico hasta el último decimal en los cuatro casos.** Con una escalera de 11 bandas y
exactamente una ganadora, `REF_uniforme` vale `(10·(1/11)² + (10/11)²)/11 = 0,082645` sea
cual sea la población. *Cualquier diferencia entre brazos en las tablas siguientes viene de
las features del modelo, nunca del código de puntuación ni del tamaño de la muestra.*

---

## 1. Tamaños de población, todas las definiciones de N

El encargo pide que no se presente un N como si fuera otro. Son cinco cosas distintas:

| definición de N | OLD | CORRECTED |
|---|---|---|
| eventos en el almacén (EGLC) | 163 | 187 |
| eventos elegibles (resolved + partición + 1 ganadora) | 40 | 186 |
| **fechas** tras deduplicar por `(station, fecha)` | 40 | 185 |
| fechas con observación **y** pronóstico, lead 24 / lead 9 | 40 / 40 | 117 / 117 |
| **eventos PUNTUADOS**, lead 24 / lead 9 | **18 / 19** | **95 / 96** |
| observaciones `evento × lead` | **37** | **191** |
| contratos puntuados, lead 24 / lead 9 | 198 / 209 | 1 045 / 1 056 |

**La caída de «con obs+FC» a «puntuados» es el mínimo de 20 pares de entrenamiento**, y es
idéntica en los dos brazos: caen **las mismas 22 fechas** (2026‑04‑08 → 2026‑05‑01) al lead
24 y **las mismas 21** (2026‑04‑08 → 2026‑04‑30) al lead 9. La puerta de entrenamiento es
invariante al brazo, verificado por igualdad de conjuntos, no por igualdad de recuentos.

### Escaleras

| | eventos puntuados por escalera |
|---|---|
| OLD, los dos leads | `{11: 18}` / `{11: 19}` |
| CORRECTED, los dos leads | `{11: 95}` / `{11: 96}` |

**Las escaleras de 7 y 9 bandas aportan CERO eventos puntuados en los dos brazos**, y no
por ningún filtro de la comparación: los 28 eventos (`{7: 2, 9: 26}`) son de 2025‑12‑31 →
2026‑03‑15, y `weather_observations` y `weather_forecasts` de EGLC empiezan el 2026‑04‑08.
Quedan fuera junto con otros 40 de once bandas. *Un «Brier por escalera 7/9/11» no existe
para esta ventana; lo que existe es la razón por la que no existe.*

---

## 2. C1 — LA COMPARACIÓN AISLADA (primaria): sólo las 40 fechas comunes

Aquí lo único que cambia es `markets.dataset_version`.

**lead 24 h · 18 eventos · 198 contratos · tasa YES 0,09091 en los dos brazos**

| modelo | Brier/contrato OLD | CORRECTED | Brier/evento OLD | CORRECTED | Δ evento |
|---|---|---|---|---|---|
| REF_uniforme | 0,08264 | 0,08264 | 0,08264 | 0,08264 | **0** |
| B0_clima30 | 0,09202 | 0,09211 | 0,09201840 | 0,09210819 | **+0,00008979** |
| B1_persistencia | 0,16162 | 0,16162 | 0,16162 | 0,16162 | **0** |
| B2_fc_crudo | 0,13131 | 0,13131 | 0,13131 | 0,13131 | **0** |
| B3_fc_error | 0,08087 | 0,08087 | 0,08087 | 0,08087 | **0** |
| B4_fc_bias | 0,07442 | 0,07442 | 0,07442 | 0,07442 | **0** |

**lead 9 h · 19 eventos · 209 contratos**: idéntico salvo `B0_clima30`,
0,09486330 → 0,09494836, **Δ = +0,00008506**.

> **Resultado de C1: los dos brazos dan el mismo número en cinco de seis modelos, con
> igualdad exacta en coma flotante, y difieren en `B0_clima30` en la quinta cifra decimal.**

Y la diferencia está **localizada y explicada**: es el evento del **2026‑05‑19**, el único
de las 40 fechas comunes en que los dos brazos puntúan eventos distintos. Las dos escaleras
son de 11 bandas, las dos `resolved`, **las dos con ganadora 18 °C**, y están desplazadas un
grado (`≤12 · 13…21 · ≥22` contra `≤13 · 14…22 · ≥23`). Sólo `B0` lo nota, porque sólo `B0`
cuenta días históricos **dentro de las bandas de borde**, que son las que se mueven: los
modelos puntuales (B1, B2) resuelven al mismo singleton en las dos escaleras, y B3/B4 ponen
masa cero en los bordes.

**Lectura, dicha entera: la corrección del dataset NO cambia la métrica sobre la población
que las dos versiones comparten.** Eso es lo que uno quiere de una corrección de datos: no
mover lo que ya estaba bien. No es un resultado predictivo y no se presenta como tal.

---

## 3. C2 — LA COMPARACIÓN COMPLETA, que está CONFUNDIDA y se publica etiquetada

**lead 24 h · Brier por evento**

| modelo | OLD (18 ev) | CORRECTED (95 ev) | Δ |
|---|---|---|---|
| REF_uniforme | 0,08264 | 0,08264 | 0 |
| B0_clima30 | 0,09202 | 0,10154 | +0,00952 |
| B1_persistencia | 0,16162 | 0,15502 | −0,00660 |
| B2_fc_crudo | 0,13131 | 0,12440 | −0,00691 |
| B3_fc_error | 0,08087 | **0,07096** | **−0,00991** |
| B4_fc_bias | 0,07442 | 0,07014 | −0,00428 |

**lead 9 h · Brier por evento**

| modelo | OLD (19 ev) | CORRECTED (96 ev) | Δ |
|---|---|---|---|
| REF_uniforme | 0,08264 | 0,08264 | 0 |
| B0_clima30 | 0,09486 | 0,10119 | +0,00633 |
| B1_persistencia | 0,17225 | 0,15909 | −0,01316 |
| B2_fc_crudo | 0,12440 | 0,11553 | −0,00887 |
| B3_fc_error | 0,06583 | 0,06505 | −0,00078 |
| B4_fc_bias | 0,06978 | 0,06885 | −0,00093 |

> **Estos deltas NO miden el efecto de la corrección.** C1 acaba de demostrar que sobre la
> población compartida el efecto de la corrección es cero en cinco modelos y 9·10⁻⁵ en el
> sexto. Todo lo que se ve aquí viene de las **77 fechas nuevas**, que no están
> intercaladas: son **2026‑05‑21 → 2026‑08‑23**, con un máximo observado medio de
> **26,27 °C contra 16,70 °C** en las comunes. Es un cambio de estación, no de calidad de
> datos.

---

## 4. C3 — LA DESCOMPOSICIÓN, que es la que permite leer C2

Todo dentro de `CORRECTED`, misma versión del dataset, mismo código.

**lead 24 h · Brier por evento**

| modelo | comunes (18 ev) | nuevas (77 ev) | Δ |
|---|---|---|---|
| B0_clima30 | 0,09211 | 0,10375 | +0,01164 |
| B1_persistencia | 0,16162 | 0,15348 | −0,00814 |
| B2_fc_crudo | 0,13131 | 0,12279 | −0,00852 |
| B3_fc_error | 0,08087 | 0,06864 | −0,01223 |
| B4_fc_bias | 0,07442 | 0,06914 | −0,00528 |

**lead 9 h**: mismo patrón (`B3` 0,06583 → 0,06486; `B0` 0,09495 → 0,10273).

**El signo y el orden de magnitud de C2 se reproducen dentro de un solo dataset.** El
verano empeora la climatología y mejora todo lo que usa pronóstico. Esa es la explicación
completa de C2, y no queda residuo que atribuir a la corrección.

---

## 5. Punto 2 — AUDITORÍA DE PROBABILIDADES, `p = 0`, `p = 1` y clipping

Fórmula, **idéntica en los dos brazos y en los seis modelos**:

    clip(p) = min(max(p, 1e-6), 1 - 1e-6)          EPS = 1e-6, el mismo de n1_20 y n1_40
    LogLoss = -[ y·ln(clip(p)) + (1-y)·ln(1-clip(p)) ]     por contrato

### Recuento de extremos (lead 24 h)

| brazo | modelo | `p = 0` | de ellos con `y = 1` | `p = 1` | de ellos con `y = 0` | contratos recortados | % del LL que aportan |
|---|---|---|---|---|---|---|---|
| OLD | REF_uniforme | 0 | 0 | 0 | 0 | 0 | 0,00 % |
| OLD | B0_clima30 | 53 | 3 | 0 | 0 | 53 | 43,50 % |
| OLD | B1_persistencia | 180 | 16 | 18 | 16 | **198 = todos** | **100,00 %** |
| OLD | B2_fc_crudo | 180 | 13 | 18 | 13 | **198 = todos** | **100,00 %** |
| OLD | B3_fc_error | 84 | 3 | 0 | 0 | 84 | 49,29 % |
| OLD | B4_fc_bias | 82 | 0 | 0 | 0 | 82 | 0,00 % |
| CORRECTED | B0_clima30 | 277 | 22 | 1 | 0 | 278 | 50,67 % |
| CORRECTED | B1_persistencia | 950 | 81 | 95 | 81 | **1 045 = todos** | **100,00 %** |
| CORRECTED | B2_fc_crudo | 950 | 65 | 95 | 65 | **1 045 = todos** | **100,00 %** |
| CORRECTED | B3_fc_error | 363 | 4 | 0 | 0 | 363 | 19,50 % |
| CORRECTED | B4_fc_bias | 364 | 1 | 0 | 0 | 364 | 5,56 % |

### El hallazgo que invalida el Log Loss para dos de los modelos

`B1` y `B2` son **indicadores**: producen exactamente 0 o 1 y nada más. Su Log Loss no es una
medida de calibración, es **aritmética del recorte**:

    evento acertado  ->  ~0
    evento fallado   ->  banda ganadora  p=0, y=1   ->  -ln(EPS) = 13,8155
                         banda elegida   p=1, y=0   ->  -ln(EPS) = 13,8155
                         por contrato: 2·13,8155 / 11 = 2,51191

    LL/contrato = (fallos / eventos) · 2 · (-ln EPS) / n_bandas

Comprobado contra la salida, sin ajustar nada: OLD lead 24, `B1` falla 16 de 18 →
`16/18 · 2,51191 = 2,23281`, que es **exactamente** el número de la tabla; `B2` falla 13 de
18 → `13/18 · 2,51191 = 1,81416`, también exacto.

> **El Log Loss de `B1` y `B2` es una función determinista de la tasa de acierto y de la
> constante de recorte.** Cambiar `EPS` de `1e-6` a `1e-3` reduciría esos números a la
> mitad exacta sin que cambie ni un dato. **No es comparable entre modelos, y para estos dos
> no mide nada que el Brier no mida mejor.** Se reporta porque el encargo lo pide, y se
> reporta con esta advertencia pegada.

Para `B0`, `B3` y `B4` el recorte pesa entre el 0 % y el 51 % del Log Loss, y **ese peso
difiere entre brazos** (por ejemplo `B3`: 49,29 % en OLD, 19,50 % en CORRECTED). La
constante es la misma; lo que cambia es cuántas veces se toca. **Es una propiedad de la
población, no un cambio de tratamiento** — pero significa que un delta de Log Loss entre
brazos mezcla calibración con exposición al recorte, y por eso el Brier queda como métrica
primaria y el Log Loss como diagnóstico.

`REF_uniforme` no toca el recorte ni una vez en ninguno de los dos brazos: `p = 1/11` siempre.

---

## 6. Unidad primaria, y por qué

**La unidad primaria es el evento** (`evento × lead`), y está preinscrita desde el docstring
de `n1_14`: las 11 bandas de un evento son **11 contratos del mismo sorteo**, no 11
observaciones independientes. Ponderar por contrato daría más peso a los eventos de escalera
larga.

En esta ventana **las dos ponderaciones coinciden hasta la quinta cifra** porque todos los
eventos puntuados tienen exactamente 11 bandas — se muestran las dos en todas las tablas
precisamente para que eso se **vea** en lugar de suponerse. En cuanto entren escaleras de 7
o 9 dejarán de coincidir, y entonces la ponderación por evento será la que hay que leer.

**Ninguna unidad se ha elegido después de mirar el resultado**: las cuatro (contrato,
evento, `evento×lead`, escalera) estaban en el guion antes de la primera ejecución, y las
cuatro se imprimen siempre.
