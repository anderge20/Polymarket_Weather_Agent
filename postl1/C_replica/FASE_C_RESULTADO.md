# POST-L1.8 · FASE C — RÉPLICA EX-ANTE EN RKSI · RESULTADO

**`FASE C = CLOSED`** · escrito 2026-09-13T22:35Z · sesión A

`D0` sigue abajo · `D0-P = BLOCKED` · `L2 = BLOCKED` · cero precios, cero EV, cero PnL,
cero order book, cero ejecución, cero dinero real.

---

## 1 · LOCK

| | |
|---|---|
| ciudad congelada | **`RKSI`** — Incheon/Seúl · `Asia/Seoul` |
| commit del lock | `aed9482` (criterios, 21:58:56Z) → `LOCK_FASE_C.md` |
| enmienda 1 (ventana) | `9912761`, 22:09:30Z — **antes** de la primera petición |
| enmienda 2 (pasada ausente) | `e290106`, 22:2xZ — **antes** de reanudar, **después** de 44 peticiones |
| ventana congelada | 2026-05-21 → 2026-08-23 · **95 días** |

    LOCK_FASE_C.md               a7258b1af1ded933      n075_poblacion.py    ed86e4e104591f83
    CRITERIOS_FASE_C.md          16f1ab31caf75d7f      l1_2_baselines.py    463c86d9223e7ddb
    ENMIENDA_VENTANA_FASE_C.md   8409600376dd2c7b      l1_5_calibracion.py  2df7bf4c2b491903
    ENMIENDA_FALLO_DE_PASADA.md  5a6dc7b1b07edd06      faseA_benchmark.py   1b52691ae9853c1b
    faseC_ingesta_obs.py         52dea254d194c7b6      faseC_gate_timezone  75be80a4fd67c303
    faseC_ingesta_fc.py          134a1c59c9a7b128      faseC_gate_integrid  4b9523b7d61f9972
    faseC_datos.py               8aaf67bd144edd9d      faseC_scoring.py     3669b7e261a51a0e

**Ningún criterio miró un resultado.** Las dos enmiendas se escribieron y se espejaron
antes de la petición que motivaba cada una, y ninguna de las dos toca un techo ni una
regla de puntuación.

---

## 2 · INGESTA

| | peticiones | techo | 429 | fallos | cobertura |
|---|---|---|---|---|---|
| observaciones (IEM) | **95** | 100 | 0 | 0 | **95 de 95 días** |
| pronósticos (Open-Meteo single-runs) | **191** (44 + 147) | 200 | 0 | **1** | **189 filas** de 190 planeadas |

    dataset_version   replica_rksi_v1     0 filas existentes tocadas
    estacion          RKSI                timezone   Asia/Seoul
    fuente pronostico OPEN_METEO_SINGLE_RUNS   modelo  icon_seamless (= dwd_icon aqui)
    fuente observacion IEM_ASOS_METAR_RT34     unidad  C

**El único fallo, con nombre y fecha:**

    2026-06-10T18:00Z  ·  "The requested model run is not available. Model: dwd_icon"

No es cuota, es un hueco del archivo. Tratado como lo trata producción
(`backfill_weather.py`): se cuenta y se sigue, sin retroceder a otra pasada y sin
rellenar nada. Consecuencia medida: `(2026-06-11, lead 9)` se sirve con la pasada 06z
en vez de la 18z, y el §17.6 mide el resultado quitando esa fecha.

**Oráculos independientes, los dos con cero discrepancias:**

* observaciones — tarball `B-133` (serie horaria IEM), 95 de 95 días;
* pronósticos — las **73 pasadas** que la ingesta de **producción** (`backfill_2b_v1`)
  ya tenía para RKSI: mismo `(model, issue_time, target_date)`, mismo `forecast_tmax`,
  **0 discrepancias**. El archivo Single-Runs es reproducible y las dos rutas tomaron la
  misma ventana local.

---

## 3 · AUDITORÍA DE TIMEZONE (§6)

`faseC_gate_timezone.py` → **PASA**, nueve bloques. Lo que importa de cada uno:

| | resultado |
|---|---|
| T1 | `Asia/Seoul` = UTC+09:00 **todo el año** (sin horario de verano) |
| T2 | agrupación por fecha **local**: 95 días locales frente a 91 días UTC |
| T3 | la serie **horaria** tiene 380 lecturas a ±1 h de medianoche UTC y **190 cambian de fecha** al pasar a Seúl |
| T4 | 0 discrepancias contra el oráculo por día local; el **mismo** oráculo agrupado por `Europe/London` discrepa en **2 de 95** |
| T5 | 190 pares (fecha, lead) sobre 95 fechas; 0 fechas sin observación; 0 fuera de ventana |
| T6 | `t_asof` lead 24 = **21:00 KST** del día anterior · lead 9 = **12:00 KST** del día objetivo |
| T7 | pasadas 06z y 18z · `available_at <= t_asof` en **190 de 190** · margen mínimo **1,240 h** |
| T8 | **MUTACIÓN**: forzando `Europe/London` y `UTC`, las lecturas **cambian**. Si la zona estuviera clavada, este bloque fallaría |
| T9 | `tmax_from_series` depende de la zona sobre filas reales; y las 73 pasadas comunes con producción coinciden |

### Y el gate encontró un defecto real, antes de puntuar

`n075_poblacion.poblacion()` calculaba el corte del día civil del desempate en
**`Europe/London` fijo**, para cualquier estación. Es el **hermano** del defecto que
D11/A-285 arregló doce líneas más arriba, en `observaciones()`: arreglar uno dejó el
otro en pie, en la misma función.

Con `LON`, el corte de RKSI caía **8 h tarde** (23:00Z en vez de 15:00Z).

**Impacto medido, y es cero:** RKSI tiene **0 fechas con desempate** y EGLC tiene 1, que
resuelve igual con las dos zonas. `eventos distintos = 0` en las dos estaciones. Un
defecto real, latente, corregido — que no movió ni un número. Se dice así y no más.

---

## 4 · POBLACIÓN (§11) — la unidad es el EVENTO

| | n |
|---|---|
| A · fechas elegibles en el catálogo (A-275) | 186 |
| B · dentro de la ventana congelada | 95 |
| C · con observación (día local) | 95 |
| D · con pronóstico lead 24 / lead 9 | 95 / 95 |
| E · con observación **y** pronóstico | 95 / 95 |
| **F · PUNTUABLE (MIN_TRAIN = 20)** | **73 (lead 24) · 74 (lead 9)** |

    contratos: 803 (lead 24) y 814 (lead 9). NO son observaciones independientes.
    escaleras puntuables: {11: 73} y {11: 74} — un solo estrato, A-280 satisfecho.

---

## 5 · AUDITORÍA DE ESCALERAS (§10)

    186 eventos elegibles · escaleras {7: 2, 9: 26, 11: 158}
    particion completa, sin huecos ni solapes ......... 186 de 186
    exactamente una banda ganadora ................... 186 de 186
    resolution.band_integrity (PRODUCCION) ........... 186 de 186, 0 desacuerdos

La segunda opinión es la de **producción**, sobre las etiquetas crudas, y coincide
evento a evento con `particion()`. Para RKSI eso cierra la duda abierta de la tarea #70.
Todo lo puntuable es escalera de **11**: no se agrega entre tamaños.

---

## 6 · AVAILABILITY (§12) — y aquí la réplica está MEJOR servida que Londres

El encargo prohíbe trasladar la cota de Londres sin evidencia. No hace falta trasladarla:

    ARCH_AUDIT_SEAMLESS.json     RKSI -> ICON-GLOBAL ~13km     EGLC -> ICON-D2 ~2.2km
    F3-CLOSURE-REPORT.md         dwd_icon  n=78  MAX = 4,76 h
    el proveedor, en RKSI        "Model: dwd_icon"   (mensaje del run ausente)

`L_MAX['icon_seamless'] = 4,76 h` **es una medición de `dwd_icon`**, que es exactamente
el modelo que sirve a RKSI. Para RKSI la cota es **directa**.

> **Y el corolario incomoda al otro lado:** para **Londres** sí estaba trasladada.
> EGLC lo sirve **ICON-D2**, y la cota que L1 le aplicó es un número de ICON-GLOBAL. La
> dirección es conservadora — ICON-D2 publica antes, así que 4,76 h retrasa el
> `available_at` y hace *perder* información, nunca filtrarla — pero es una traslación
> no declarada y queda anotada contra la tarea #75 y contra la Fase B.

Margen mínimo `t_asof − available_at` sobre las 190 lecturas: **1,240 h**. Cero
look-ahead.

### Y la evidencia de las dos ciudades no es de la misma calidad — hay que decirlo

`ARCH_AUDIT_OPENMETEO.md` §7.1-2 declara un UNKNOWN que esta afirmación hereda:

> *"Estabilidad temporal de la composición. La asignación estación→componente se midió
> para una única fecha (2026-07-15). Si D2/EU cambian de dominio, resolución o
> disponibilidad a lo largo del histórico, la composición podría no ser constante.
> **No verificado.**"*

La identificación en sí es inequívoca — se consultaron `icon_d2`, `icon_eu` e
`icon_global` por separado y se buscó cuál reproduce a la vez el centro de celda exacto
**y** los 24 valores horarios. Pero es de **un día**.

| | evidencia del dominio | fechas |
|---|---|---|
| **RKSI → ICON-GLOBAL** | auditoría 2026-07-15 **+ el proveedor lo nombra** (`Model: dwd_icon`) en un run de **2026-06-10** | **dos**, por dos canales distintos |
| **EGLC → ICON-D2** | auditoría 2026-07-15 | **una** |

Así que la afirmación *"a Londres se le aplicó la latencia de otro modelo"* descansa sobre
una sola medición de dominio. La dirección del sesgo no cambia — ICON-D2 publica antes que
GLOBAL, así que 4,76 h **retrasa** `available_at` y hace perder información, nunca
filtrarla — pero la fuerza de la evidencia sí, y va anotada en la tarea #75 en vez de
viajar sin ella.

---

## 7 · RESULTADOS (§14)

**Brier por evento · bootstrap clusterizado por evento · 10 000 · semilla 20260913**

| lead | serie | Brier | B4 − S3 | IC95 | B4 − uniforme | B4 − B0 | n |
|---|---|---|---|---|---|---|---|
| **24** | B4 0,07327 · S3 0,07813 · unif 0,08264 · B0 0,08856 | | **−0,00485** | [−0,00940, −0,00042] | −0,00937 | −0,01528 | 73 |
| **9** | B4 0,06919 · S3 0,07811 · unif 0,08264 · B0 0,08803 | | **−0,00892** | [−0,01378, −0,00438] | −0,01346 | −0,01884 | 74 |

Los dos IC excluyen el cero. `S2` da 0,08264 = `10/121` exacto: el control uniforme está
donde tiene que estar.

---

## 8 · POTENCIA (§19)

| lead | efecto | sd | MDE(80 %) | **efecto/MDE** | gana en |
|---|---|---|---|---|---|
| 24 | −0,00485 | 0,01988 | 0,00652 | **0,74** | 41/73 |
| 9 | −0,00892 | 0,02068 | 0,00673 | **1,33** | 47/74 |

**Lead 24 no llega a 1.** Por el criterio escrito en el LOCK antes de ver nada, eso es
`INCONCLUSIVE`, no una réplica. **Lead 9 sí llega.**

---

## 9 · ROBUSTEZ (§17) — sólo las pruebas predefinidas, y la fea se cuenta primero

### 9.1 Influencia de eventos — **es la debilidad de la réplica**

    lead  9   quitando  5 mejores  -0,00565  [-0,00962, -0,00167]  sigue
              quitando 10 mejores  -0,00305  [-0,00653, +0,00069]  YA NO
              quitando 20 mejores  +0,00090  [-0,00254, +0,00442]  YA NO

    lead 24   quitando  5 mejores  -0,00168  [-0,00548, +0,00219]  YA NO

**Londres lead 9 aguantaba quitando 20.** RKSI lead 9 muere quitando 10. El efecto es
real por el criterio preinscrito y es **más frágil que el de Londres**.

### 9.2 Estabilidad temporal — el efecto vive en la segunda mitad

|  | 1.ª mitad | 2.ª mitad |
|---|---|---|
| **RKSI** lead 9 | −0,00302 [−0,00834, +0,00215] | −0,01482 [−0,02229, −0,00782] |
| **RKSI** lead 24 | −0,00052 [−0,00602, +0,00469] | −0,00907 [−0,01615, −0,00224] |
| **EGLC** lead 9 | −0,01089 [−0,01717, −0,00482] | −0,01272 [−0,01876, −0,00693] |
| **EGLC** lead 24 | −0,00242 [−0,00933, +0,00442] | −0,00959 [−0,01665, −0,00276] |

Londres lead 9 es **estable en las dos mitades**. RKSI lead 9 **no**: su primera mitad
incluye el cero. En estabilidad, RKSI lead 9 se parece más al **lead 24 de Londres** —
que fue descartado en la Fase A — que al lead 9 de Londres.

### 9.3 MIN_TRAIN — y por qué NO es una confirmación independiente

    lead 9   MIN_TRAIN 20  n=74  -0,00892      40  n=54  -0,01152
                       30  n=64  -0,00931      50  n=44  -0,01314

El efecto crece con `MIN_TRAIN` en los cuatro valores y en los dos leads. Suena a
confirmación y **no lo es del todo**: subir `MIN_TRAIN` **elimina los eventos más
tempranos**, que son justo los de la primera mitad floja. 9.3 y 9.2 están midiendo en
buena parte lo mismo, y presentarlos como dos pruebas independientes sería inflar la
evidencia. Se cuentan como **una**.

### 9.4 Fuga de S3 · 9.5 missingness

    S3 identico prohibiendo todo lo posterior al corte: 36/36  ->  NO hay fuga
    observacion: 0 dias ausentes de 95
    pronostico : 1 pasada ausente; quitando esa fecha, lead 9 = -0,00916 [-0,01405, -0,00457]

### 9.6 Información que lleva la escalera sola

    posicion de la ganadora  {-2:3, -1:5, 0:10, 1:13, 2:25, 3:8, 4:7, 5:3}
    |desviacion| media 1,91 bandas (uniforme daria 2,73) · entropia 1,848 (uniforme 2,398)

La escalera de RKSI está **descentrada hacia +2**: el mercado coloca la escalera algo por
debajo de donde cae el máximo. `S3` captura eso, y por eso `S3` vale 0,0781 frente al
0,0826 del uniforme. Lo que `B4` tiene que superar es `S3`, no el uniforme — y es lo que
se mide arriba.

---

## 10 · RED TEAM (§22)

| ataque | resultado |
|---|---|
| ¿RKSI se eligió antes de ver resultados? | **Sí.** Dos criterios ex-ante independientes, espejados en `aed9482` antes de medir el universo. |
| ¿La ingesta está completa? | 95/95 observaciones, 189/190 pronósticos. El hueco está nombrado y medido. |
| ¿Sesgo de missingness? | El único hueco es una pasada del proveedor, no una fecha; quitarla no mueve el resultado. |
| ¿Duplicados? | 0 por `(station, model, issue_time, target_date)`; 1 registro por día local. |
| ¿Timezone correcta en todos los eventos? | Sí, y demostrado por **mutación**, no por inspección. Y el gate encontró un defecto latente de zona fija en el desempate. |
| ¿La pasada correcta? ¿`t_asof` correcto? | 06z y 18z; `available_at <= t_asof` 190/190; margen mínimo 1,24 h. |
| ¿Estaba realmente disponible el pronóstico? | La cota es de `dwd_icon`, el modelo que sirve a RKSI. Evidencia directa, no trasladada. |
| ¿Settlement y escalera equivalentes? | 186/186 partición completa y una ganadora, confirmado por `resolution.band_integrity` de producción. Todo lo puntuable es escalera 11, igual que Londres. |
| ¿`B4` es el mismo? ¿`S3` es el mismo? | Se **importan**, no se reescriben. `faseC_datos.equivalencia()` demuestra sobre EGLC que la capa de lectura devuelve exactamente lo que devuelven las funciones congeladas. |
| ¿Cluster por evento? ¿n correcto? | Sí: cada dato del bootstrap es el Brier de un evento. n = 73 y 74. |
| ¿Depende de pocos eventos? | **Sí, más que en Londres.** Muere quitando 10. Es la limitación principal. |
| ¿Depende de un periodo? | **Sí.** La primera mitad incluye el cero. |

**Ataque que NO pude montar y lo digo:** la ventana de RKSI (95 días) es más corta que la
de Londres (138) y arranca más tarde, así que no puedo separar *"efecto más débil"* de
*"ventana peor"*. Y los 9 días de observación que RKSI tiene fuera de la ventana no se
usaron: entran en `backfill_2b_v1`, y meterlos después de ver el resultado sería
exactamente lo que §15 prohíbe.

---

## 11 · VEREDICTO

> ### `lead 9` = **REPLICATED**
> ### `lead 24` = **INCONCLUSIVE** (potencia: efecto/MDE 0,74 < 1)

Contra el criterio escrito en `LOCK_FASE_C.md` §6 **antes** de ver un número:

| condición (lead 9) | |
|---|---|
| `B4 − S3 < 0` | ✔ −0,00892 |
| IC95 excluye el cero | ✔ [−0,01378, −0,00438] |
| mismo signo que Londres | ✔ |
| magnitud material | ✔ 0,76× la de Londres |
| controles superados | ✔ uniforme, S3 sin fuga, MIN_TRAIN, escalera |
| **efecto/MDE ≥ 1** | ✔ **1,33** |

**No relajo el criterio y tampoco lo endurezco al ver el resultado.** La fragilidad
medida (§9.1, §9.2) es una **limitación reportada**, no un criterio nuevo: añadir ahora
un umbral de influencia sería cambiar la regla después de ver el número, que está
prohibido en las dos direcciones.

> **Corrección de una cifra mía, 22:50Z.** El `B4 − S3` de Londres en lead 24 es
> **−0,00605**, no −0,00614: transcribí el −0,0061 de una tabla redondeada y **me inventé
> el quinto decimal**. El cociente de magnitudes pasa de 0,79× a 0,80× y ninguna
> conclusión se mueve. Lo detectó la guarda `REPRODUCE / NO REPRODUCE` del análisis
> conjunto, que exige que cada número de partida se recalcule desde los datos antes de
> usarlo. El lead 9 (−0,01181) siempre estuvo bien.

**Y el eco estructural es lo más informativo del experimento:** el lead que sobrevive y
el lead que cae son **los mismos en las dos ciudades**. Londres descartó el lead 24 en la
Fase A por potencia (0,87) y RKSI lo descarta por lo mismo (0,74). Eso no estaba
garantizado por nada.

---

## 12 · DECISIÓN

> ## `PREPARAR ANÁLISIS CONJUNTO`
> ## `L2` sigue **BLOCKED** · `D0` sigue abajo · `D0-P` sigue **BLOCKED**

Por §18-A: una réplica positiva **no abre L2 automáticamente**. Lo que se abre es el
diseño de un análisis combinado Londres + RKSI, **justificado y declarado antes de
ejecutarlo**, y que tendrá que explicar por qué dos ventanas distintas, dos modelos ICON
distintos (D2 y GLOBAL) y dos regímenes climáticos distintos pueden juntarse.

**No se busca una tercera ciudad** (§23). No hace falta y estaría prohibido: la réplica
no falló.

**Lo que hay que llevarse escrito al análisis conjunto, antes de diseñarlo:**

1. la fragilidad de RKSI a la influencia (muere quitando 10) y su primera mitad floja;
2. que la cota de availability de **Londres** está trasladada de ICON-GLOBAL a ICON-D2 —
   conservadora, pero no declarada hasta hoy;
3. que las ventanas no coinciden y que el pooling no puede fingir que sí.
