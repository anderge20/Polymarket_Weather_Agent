# LEVEL 1 · L1.7 — FINAL RED TEAM

Cinco ataques **declarados y espejados antes de ejecutarlos** (`LOCK_L1_7.md`, `d3207b3`,
21:22:12Z). **Se ejecutaron los cinco y se reportan los cinco.** No se buscan precios, EV ni
PnL; producción sin tocar; `D0-P` = BLOCKED. **No se emite el veredicto: eso es L1.8.**

---

# A1 · GEOMETRÍA DE LA ESCALERA — **el ataque que más muerde**

La escalera la elige el mercado. Si la ganadora tiende a caer cerca de su centro, **un modelo
que concentre masa en el centro bate al uniforme sin ninguna habilidad meteorológica**.

`CTRL_escalera` **ignora el pronóstico por completo**: reparte masa uniformemente sobre las 7
bandas centrales (la dispersión media de `B4`).

| | lead 24 | lead 9 |
|---|---|---|
| `CTRL_escalera − uniforme` | **−0,00390 [−0,00472, −0,00281]** | **−0,00391 [−0,00472, −0,00283]** |
| `B4 − uniforme` | −0,01151 | −0,01731 |
| **fracción atribuible a la geometría** | **33,9 %** | **22,6 %** |
| `B4 − CTRL_escalera` | **−0,00761 [−0,01224, −0,00286]** | **−0,01340 [−0,01760, −0,00891]** |

**La geometría sola ya bate al uniforme**, y explica entre un quinto y un tercio de la ventaja
de `B4`. El mercado centra su escalera cerca de la verdad:

    posicion de la ganadora respecto al centro   |desviacion| media 1,23 bandas
    lo que daria el uniforme                                       2,73 bandas

> ## LA CIFRA HONESTA SE DEFLACTA TRES VECES, Y LAS TRES SON MÍAS
>
>     B4 - B0            -0,0304 / -0,0359    comparacion PRE-REGISTRADA
>                                             ...pero B0 es peor que el azar (A-289)
>     B4 - uniforme      -0,0115 / -0,0173    tras descontar lo malo que es B0
>     B4 - CTRL_escalera -0,0076 / -0,0134    tras descontar el centrado de la escalera
>
> **El titular pre-registrado sobrestima la señal por un factor de ~4 (lead 24) y ~2,7
> (lead 9).** `B4` sobrevive a las tres deflaciones —el IC sigue excluyendo el cero— pero el
> tamaño real del efecto es **la tercera cifra, no la primera**.

*Nota sobre el control, para no venderlo mejor de lo que es:* usa la dispersión de `B4` como
anchura. Otra anchura daría otra fracción. Es **una** operacionalización razonable de «la
geometría explica el resultado», no la única.

---

# A2 · BANDAS ABIERTAS CONTRA INTERIORES

| grupo | lead 24 | lead 9 |
|---|---|---|
| abierta INFERIOR | n=2, −0,03647 | n=2, −0,02461 |
| **INTERIOR** | **n=92, −0,01042 [−0,01440, −0,00637]** | **n=93, −0,01676 [−0,02069, −0,01282]** |
| abierta SUPERIOR | n=1, −0,06245 | n=1, −0,05408 |

**La ventaja NO vive en las bandas abiertas**: el grupo interior —92 y 93 de los eventos— la
conserva entera con el IC excluyendo el cero. Las abiertas tienen `n` de 1 y 2: se muestran y
**no se interpretan**.

---

# A3 · MÚLTIPLES COMPARACIONES, contadas de verdad

    L1.4 primaria, B1..B4 contra B0, dos leads              8
    L1.4 control uniforme, cinco modelos, dos leads        10
    L1.5 mitades temporales, dos leads                      4
    L1.6 placebo A, seis desplazamientos, dos leads        12
    L1.6 placebo B, dos leads                               2
    L1.6 test de heterogeneidad, dos leads                  2
    L1.7 A1/A2/A5, dos leads                               18
    ------------------------------------------------------ --
    TOTAL de comparaciones con IC EJECUTADAS               56

Bonferroni sobre la primaria: `α = 0,05 / 56 = 0,00089`. El bootstrap de `B4 − uniforme` a
lead 9 dio **0 de 10 000** remuestreos con signo contrario → `p < 1e-4`. **La primaria sobrevive
a Bonferroni contando las 56 comparaciones ejecutadas, no sólo las reportadas.**

---

# A4 · ¿SABE LA ESCALERA ALGO QUE EL PRONÓSTICO NO SEPA?

| | lead 24 | lead 9 |
|---|---|---|
| corr(centro de la escalera, observación) | +0,957 | +0,957 |
| corr(pronóstico, observación) | **+0,973** | **+0,979** |
| MAE del centro de la escalera | 1,263 °C | 1,271 °C |
| **MAE del pronóstico** | **1,014 °C** | **0,885 °C** |

**Nuestro pronóstico es mejor que el centro de la escalera, pero por poco**: 0,25 °C a lead 24 y
0,39 °C a lead 9. *El mercado publica, en la geometría de su propia escalera, un punto casi tan
bueno como el nuestro.*

> Esto es **exactamente el hallazgo de R21 reapareciendo una capa más arriba** —*«el mercado
> está mejor calibrado que el modelo»*— y es la pregunta central de la fase económica. **Aquí
> sólo se mide. No se toca.**

---

# A5 · ROBUSTEZ AL MÍNIMO DE ENTRENAMIENTO — los cuatro valores, reportados

    lead 24   MIN_TRAIN 20  n=95  -0,01151 [-0,01577,-0,00726]
              MIN_TRAIN 30  n=85  -0,01316 [-0,01768,-0,00882]
              MIN_TRAIN 40  n=76  -0,01381 [-0,01837,-0,00925]
              MIN_TRAIN 50  n=66  -0,01355 [-0,01866,-0,00875]

    lead  9   20: -0,01731 · 30: -0,01752 · 40: -0,01743 · 50: -0,01718   los cuatro excluyen el cero

**El resultado no depende del parámetro.** Y la ligera mejora al subir el mínimo va en la
dirección esperada —más entrenamiento, mejor distribución de error— sin que se elija ningún
valor: **el preinscrito sigue siendo 20**.

---

# LOS DIEZ RIESGOS DE §19, RESUMIDOS

| riesgo | dónde se atacó | resultado |
|---|---|---|
| look-ahead | L1.3 §9, L1.6 placebo A | `available_at ≤ t_asof` 95/95 y 96/96; un día de desfase borra la ventaja |
| leakage | L1.2, prueba ejecutable | alterar el futuro no mueve nada anterior, y sí lo posterior |
| estacionalidad | L1.4 §7, L1.6 test temporal | presente y nombrada; **lead 24 heterogéneo entre mitades** |
| efectos de escalera | **L1.7 A1 y A2** | **explican 23–34 % de la ventaja**; el resto sobrevive |
| dependencia intra-evento | L1.4–L1.7 | clúster por evento; `r = +0,595` entre leads → n efectivo 119, no 190 |
| calibración sobre el test | L1.5 | declarada **diagnóstico**, no calibración OOS entrenada |
| selección post-hoc | locks de L1.4–L1.7 | todo declarado antes; el control uniforme, **declarado ex-post** |
| revisiones | L1.1, L1.3 §9 | dos ejecuciones distintas, 06z y 18z; la 18z es información nueva |
| target leakage | **L1.7 A4** | la escalera lleva información, **pero nuestro pronóstico es mejor** |
| múltiples comparaciones | **L1.7 A3** | 56 contadas; la primaria sobrevive a Bonferroni |

---

# DEFECTOS

| severidad | hallazgo |
|---|---|
| **A — bloqueante** | **ninguno** |
| **B — requiere corrección** | **ninguno** |
| **C — documentable** | (1) **el titular pre-registrado sobrestima la señal ×4 / ×2,7**; (2) **lead 24 heterogéneo** entre mitades; (3) el centro de la escalera es casi tan buen pronóstico como el nuestro; (4) `available_at` sin validar externamente; (5) el test **no cubre abril**; (6) la calibración de `B4` es casi tautológica; (7) una ciudad, una estación, cuatro meses; (8) `n` efectivo 119, no 190 |

# `L1.7 = CLOSED`

**Ningún ataque invalidó el resultado; dos lo acotaron sustancialmente.** `B4` conserva ventaja
sobre el uniforme **y** sobre la geometría de la escalera, en los dos leads, con IC que excluyen
el cero, robusta al mínimo de entrenamiento, con los doce placebos de desfase yendo al otro lado
y `p = 0,0010` en permutación.

**Lo que no se dice aquí:** ni «hay edge» ni «no hay edge». Eso es `L1.8`, y llegará con las
ocho limitaciones pegadas.
