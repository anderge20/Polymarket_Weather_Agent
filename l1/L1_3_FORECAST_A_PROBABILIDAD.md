# LEVEL 1 · L1.3 — FORECAST → P(YES)

**No se evalúa edge, precio, mispricing, PnL, umbrales, estrategia ni ejecución.** No se calcula
el veredicto de poder predictivo, no se compara contra precios de mercado y no se seleccionan
modelos. Las métricas que aparecen aquí son **instrumento** —sensibilidad al recorte— y **no se
ordenan**. `D0-P` sigue BLOCKED.

Guiones: `l1_3_intervalos.py` (19 verdes) y `l1_3_probabilidades.py` (11 verdes). Salidas
íntegras junto a ellos.

---

## 1 · DEFINICIÓN EXACTA

Para cada `(evento, lead)`:

    informacion en t_asof            el ultimo pronostico con available_at <= t_asof
                                     + el historico con label_av(d) <= t_asof
      -> distribucion predictiva     T = f + e,  e ~ distribucion EMPIRICA de los errores del train
      -> probabilidad por intervalo  P_i = #{e : round(f + e) en banda_i} / #e
      -> P(YES) de cada contrato     P_i, con sum_i P_i = 1 por construccion

`sum(P_i) = 1` verificado con tolerancia **≤ 1e-12**: máximo **0,00e+00** a lead 24 y
**1,11e-16** a lead 9.

---

## 2 · TRES OBJETOS, SEPARADOS Y ETIQUETADOS

| | qué es | disponibilidad |
|---|---|---|
| **A · `T_WU`** | la temperatura contractual real, la que publica Wunderground | **NO existe serie histórica independiente en el almacén** |
| **B · `T_IEM`** | el proxy observado: máximo METAR de IEM | 138 días, es lo que tenemos |
| **C · `winning_outcome`** | el resultado contractual almacenado | **LA ETIQUETA** |

> **Declaración explícita, como pide el encargo:** no existe `T_WU` histórica independiente, así
> que **la validación de forecast skill usa `B` como proxy de `C`** — y **`C` NO se sustituye
> por `B`** en ningún punto: el target de todos los baselines es `winning_outcome`, verificado
> en D11 (`is_winner` no usado, `outcome_index` no usado, ninguna observación entra en la
> construcción del target). **La discrepancia conocida del 2026-05-27 se conserva**, no se
> corrige.

---

## 3 · INTERVALOS CONTRACTUALES — PROBADOS POR ESCALERA, SIN ASUMIR EQUIVALENCIA

| escalera | eventos | tramo cerrado | sin solapes | sin huecos | todo entero en **exactamente una** banda |
|---|---|---|---|---|---|
| **7 bandas** | 2 | enteros 3…7 | ✔ 0 | ✔ 0 | ✔ (probado de −60 a +80) |
| **9 bandas** | 26 | enteros 2…20 | ✔ 0 | ✔ 0 | ✔ |
| **11 bandas** | 159 | enteros 4…44 | ✔ 0 | ✔ 0 | ✔ |

Estructura, con límites e inclusión explícitos (ejemplo de 11 bandas):

    5°C or below     ->  (-inf, 5]        inclusiva por arriba
    6°C .. 14°C      ->  [k, k]           nueve singletons
    15°C or higher   ->  [15, +inf)       inclusiva por abajo

**Cada una de las tres se probó por separado**, con todos sus eventos, no sólo con un ejemplo.

---

## 4-5 · DISTRIBUCIÓN PREDICTIVA Y SESGO

Sólo las transformaciones preinscritas (`PREREG_LEVEL1.md` §7, con la enmienda de A-287).
La distribución empírica de error se estima **exclusivamente con el train**, con el día objetivo
excluido y sin nada posterior a `t_asof` — verificado en L1.2 con una **prueba ejecutable de
no-fuga** (alterar el futuro no mueve ninguna probabilidad anterior; las posteriores sí).

`f_corregido = f + bias`, con `bias = E[obs − forecast]` estimado **sólo con train**. **No se
introduce corrección condicional por temperatura, ni por mes, ni ningún modelo nuevo de sesgo.**

> **Y una propiedad de `B4` que salió de una prueba mía mal escrita y merece quedar dicha:**
> `B4` es **invariante a un sesgo constante de TODOS los pronósticos**. Si se desplazan train y
> objetivo por igual, `round((f+d) + (e−d)) = round(f+e)`: la distribución empírica de error lo
> absorbe exacto. *Por eso la corrección global de sesgo mueve tan poco — lo que `B3` corrige a
> mano, `B4` ya lo tiene dentro.*

---

## 6 · DETERMINISTAS COMO CONTROLES, Y LA SENSIBILIDAD A `epsilon`

`epsilon` **declarado antes de este guion**: `1e-6`, el de A-280. **No se elige por el número.**

**lead 24 h · 95 eventos**

| control | Brier | LL@1e-8 | LL@1e-6 | LL@1e-4 | LL@1e-3 | LL@1e-2 | LL varía | Brier varía |
|---|---|---|---|---|---|---|---|---|
| `B0_clima` | 0,10154 | 0,67091 | 0,57396 | 0,47703 | 0,42878 | 0,38252 | 0,288 | 3,9e-04 |
| `B1_persist` | 0,15502 | 2,85565 | 2,14174 | 1,42791 | 1,07171 | 0,72240 | **2,133** | 3,0e-03 |
| `B2_fc_crudo` | 0,12440 | 2,29157 | 1,71868 | 1,14587 | 0,86021 | 0,58169 | **1,710** | 2,4e-03 |
| `B3_fc_sesgo` | 0,12057 | 2,22106 | 1,66579 | 1,11062 | 0,83378 | 0,56410 | **1,657** | 2,3e-03 |
| `B4_fc_prob` | 0,07113 | 0,28978 | 0,27215 | 0,25456 | 0,24606 | 0,24036 | 0,049 | 4,2e-05 |

**El Brier es prácticamente insensible al recorte; el Log Loss no.** Y en los tres deterministas
el Log Loss **es aritmética del recorte**, demostrado con la fórmula cerrada:

    LL = [ k·(2·(-ln eps) + (n-2)·(-ln(1-eps)))  +  (N-k)·n·(-ln(1-eps)) ] / (N·n)
         k = eventos fallados,  n = bandas,  N = eventos

    B1  fallos 81/95   formula 2,14173550   medido 2,14173550   IDENTICO (delta 2,2e-12)
    B2  fallos 65/95   formula 1,71867683   medido 1,71867683   IDENTICO (delta 1,8e-12)
    B3  fallos 63/95   formula 1,66579450   medido 1,66579450   IDENTICO (delta 1,7e-12)

*(El delta de 2e-12 es acumulación en coma flotante sobre 1 045 términos; se midió antes de
fijar la tolerancia, no se aflojó el umbral hasta que pasara.)*

> **DICHO EXPLÍCITAMENTE, como pide el encargo: el Log Loss de `B1`, `B2` y `B3` es
> artificialmente DESFAVORABLE, y su magnitud la fija `epsilon`, no el modelo.** Con
> `eps = 1e-2` el Log Loss de `B1` cae de 2,14 a 0,72 sin que cambie ni un dato. **Se reportan
> como controles; no se comparan con los probabilísticos en Log Loss.**

---

## 7 · PROBABILIDADES: RANGO, SUMA Y **DIRECCIÓN**

* `sum(P_i) = 1` con tolerancia ≤ 1e-12 en los dos leads y los cinco controles.
* `0 ≤ P_i ≤ 1` **antes** del recorte: 0 fuera. **Después** del recorte: 0 fuera.
* **Prueba de dirección**, perturbando **sólo el pronóstico del día objetivo**:

      forecast +3,0 C  ->  el centro de masa de B4 se mueve  +2,820 bandas   mismo signo en 95 de 95
      forecast -3,0 C  ->                                     -2,779 bandas   mismo signo en 95 de 95

**La primera versión de esta prueba estaba mal y medía cero.** Desplazaba *todos* los
pronósticos, incluidos los del train, y el desplazamiento se cancela exacto (§4-5). **El defecto
estaba en la prueba, no en el modelo** — y arreglarla es lo que reveló la propiedad de
invariancia de `B4`.

---

## 8 · FRONTERAS

Ocho casos enteros, todos con **exactamente una** banda: límite inferior exacto, límite inferior
+1, límite superior exacto, límite superior −1, muy por debajo, muy por encima, cero y negativo.

> **Y el hallazgo formal de esta sección: la partición es sobre los ENTEROS, no sobre los
> reales.** Medido: `12,50`, `13,40` y `13,50` caen en **cero** bandas. La pertenencia se evalúa
> sobre `round(valor)`, así que **`round()` es parte de la interpretación del contrato, no un
> detalle de implementación**, y hay que decirlo antes de que alguien lo trate como un intervalo
> real.

    13,49 -> 13   13,50 -> 14   13,51 -> 14      14,49 -> 14   14,50 -> 14   14,51 -> 15

**El empate exacto usa redondeo BANCARIO (a par)**, no «medio arriba»: `round(13,5) = 14` pero
`round(14,5) = 14`. Queda **declarado**; no se cambia en L1.3 porque cambiarlo sería una
decisión de modelado y el encargo prohíbe introducir transformaciones nuevas aquí. Las
observaciones del almacén son grados enteros, así que el empate sólo puede aparecer en
`round(f + e)`, donde `f` y `e` son flotantes y el empate exacto es de medida nula.

**Unidades**: EGLC es enteramente Celsius (verificado), así que aquí no hay conversión C/F que
probar; la guarda `exige_celsius()` impide que una estación en Fahrenheit entre por accidente.

---

## 9 · REGISTRO TEMPORAL

    lead  issue_time      available_at       prediction_time   margen   train cutoff
      24  06-22 06:00Z    06-22 10:45:36Z    06-22 12:00Z       1,24 h   2026-06-20
       9  06-22 18:00Z    06-22 22:45:36Z    06-23 03:00Z       4,24 h   2026-06-21
    (ejemplo: target 2026-06-23)

* `available_at ≤ t_asof` en los **95** eventos del lead 24 y los **96** del lead 9.
* train cutoff con etiqueta **disponible** en `t_asof`, en los dos leads.

> **ADVERTENCIA MANTENIDA, sin modificar retrospectivamente:**
> `available_at = issue_time + 4:45:36` es una **hipótesis operacional no validada
> externamente**. Validación en tarea #75.

---

## 10 · SENSIBILIDAD AL PROXY — medición, no modelo

    acuerdo proxy <-> resolucion (A-276):   136 coinciden · 1 discrepa · 50 sin observacion
    tasa medida de discrepancia:            1/137 = 0,73 %

**Impacto máximo de una discrepancia de ±1 °C:** con bandas de **1 °C**, un error de 1 °C
**mueve la banda siempre**. El impacto por evento afectado es **total**; lo que acota el daño es
**la tasa, no la magnitud**.

    si la tasa fuese la medida (0,73 %):   ~0,7 de 95 eventos
    si fuese diez veces peor (7,3 %):      ~6,9 de 95 eventos

    efecto sobre la distribucion empirica de error (la que alimenta B4):
      bias actual  +0,1863 C sobre 117 pares
      1 par mal por +1 C  ->  el bias se mueve +0,0085 C  (4,6 % del bias)
      10 pares mal        ->                   +0,0855 C  (46 % del bias)

**No se corrige el desacuerdo IEM/Wunderground.** Queda cuantificado.

---

## 11 · CRITERIO DE CIERRE

| condición | estado |
|---|---|
| probabilidades matemáticamente bien construidas | **SÍ** |
| suman 1 (≤ 1e-12) | **SÍ** — 0,00e+00 y 1,11e-16 |
| escaleras correctamente interpretadas | **SÍ** — las tres, por separado, exhaustivo |
| sin leakage | **SÍ** — prueba ejecutable con poder verificado |
| la distribución usa exclusivamente train | **SÍ** |
| `B3` con el signo correcto | **SÍ** — `f + bias` (A-287) |
| deterministas tratados como controles | **SÍ** — con la aritmética del recorte demostrada |
| proxy contractual correctamente etiquetado | **SÍ** — A/B/C separados, `C` no sustituido |
| hipótesis de `available_at` registrada | **SÍ** |

# `L1.3 = CLOSED`

**No se calcula el veredicto de poder predictivo.** No se compara contra precios. No se
selecciona ningún modelo. Siguiente etapa: **`L1.4` — WALK-FORWARD OOS**.
