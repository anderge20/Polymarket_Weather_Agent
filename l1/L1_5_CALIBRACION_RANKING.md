# LEVEL 1 · L1.5 — CALIBRACIÓN + RANKING

# 1 · STATUS

## `L1.5 = CLOSED`

**No se emite «hay edge» ni «no hay edge».** Prohibido y no realizado: precios, EV, PnL,
entradas/salidas, umbrales, bandas óptimas, stake, liquidez, ejecución, elección de ciudades,
ampliación del dataset, producción, bot, paper trading, dinero real. `D0-P` = BLOCKED.

# 2 · LOCK

| | |
|---|---|
| lock de esta etapa | `LOCK_L1_5.md`, commit **`5c87024`**, **2026-09-13T20:50:03Z**, espejado **antes** de ejecutar |
| lock previo | `LOCK_L1_4.md` (`cee4255`) y `PREREG_LEVEL1.md` — **integridad verificada por `sha256`**: idénticos en local y en `research/modelsel-artifacts` |
| metodología | 5 modelos cerrados · unidad de inferencia **EVENTO** · bootstrap clusterizado por evento, 10 000, semilla 20260913 · escalera **11** · `epsilon = 1e-6` · leads separados |
| **cambios respecto al lock previo** | **NINGUNO en modelos ni en metodología.** Se añaden métricas **marcadas como diagnóstico descriptivo**: top-2/top-3, intercepto/pendiente, frecuencia de extremos, bloques mensuales, influencia, binning alternativo. **Ninguna se usa para modificar, elegir ni seleccionar nada.** |

**Jerarquía intacta:** benchmark primario pre-registrado = **`B0`**; control estructural
ex-post = **uniforme 1/11**. L1.4 no se reescribe y `B0` no se modifica.

# 3 · RESULTADOS

| model | lead | calibración (int·pend, `p>0`) | ranking (rango·top1) | Brier | LogLoss | entropía | top1 | rango gan. |
|---|---|---|---|---|---|---|---|---|
| `B0_clima` | 24 | −2,070 · **+0,081 [−0,261, +0,216]** | pobre | 0,10154 | 0,57396 | 1,6543 | 0,032 | 5,789 |
| `B1_persist` | 24 | *determinista* | pobre | 0,15502 | *2,14174* † | 0,0000 | 0,147 | 5,689 |
| `B2_fc_crudo` | 24 | *determinista* | **buena** | 0,12440 | *1,71868* † | 0,0000 | **0,316** | 4,763 |
| `B3_fc_sesgo` | 24 | *determinista* | **buena** | 0,12057 | *1,66579* † | 0,0000 | **0,337** | 4,647 |
| **`B4_fc_prob`** | 24 | **+0,003 · +1,040 [+0,801, +1,359]** | **muy buena** | **0,07113** | **0,27215** | 1,6313 | 0,316 | **2,711** |
| *uniforme* | 24 | *ideal trivial* | *azar* | *0,08264* | *0,30464* | *2,3979* | *0,091* | *6,000* |
| `B0_clima` | 9 | −2,055 · **+0,089 [−0,280, +0,207]** | pobre | 0,10119 | 0,56902 | 1,6641 | 0,031 | 5,802 |
| `B1_persist` | 9 | *determinista* | pobre | 0,15909 | *2,19792* † | 0,0000 | 0,125 | 5,812 |
| `B2_fc_crudo` | 9 | *determinista* | **buena** | 0,11553 | *1,59611* † | 0,0000 | **0,365** | 4,495 |
| `B3_fc_sesgo` | 9 | *determinista* | **buena** | 0,12121 | *1,67461* † | 0,0000 | 0,333 | 4,667 |
| **`B4_fc_prob`** | 9 | **+0,171 · +1,177 [+0,891, +1,550]** | **muy buena** | **0,06534** | **0,23792** | 1,4678 | 0,302 | **2,344** |
| *uniforme* | 9 | — | *azar* | *0,08264* | *0,30464* | *2,3979* | *0,091* | *6,000* |

† **LogLoss NO interpretable**: aritmética del recorte (A-288). **No se usa para seleccionar.**

# 4 · `B4`

**Calibración.** Con la versión restringida a `p > 0` —la única honesta, porque el recorte de
`1e-6` domina los logits de los ceros— el ajuste logístico da **intercepto +0,003 y pendiente
+1,040** a lead 24, y **+0,171 / +1,177** a lead 9. **Los cuatro IC95 contienen el ideal
(0, 1).** La curva de fiabilidad lo confirma: desvíos de **+0,0045 · −0,0006 · −0,0135 ·
+0,0194 · −0,0357** en los cinco bins con `n` suficiente. *(El bin superior tiene `n = 2`: se
ignora.)*

**Concentración y sharpness.** `p_max` medio 0,344 / 0,362; sharpness 0,2373 / 0,2717; entropía
1,631 / 1,468 contra 2,398 del uniforme. **No está sobreconcentrado**: `p > 0,5` ocurre en
**2 contratos de 1 045**, y **nunca** asigna `p = 1`.

**La propiedad que más importa para el ranking:** `B4` pone `p = 0` a la banda ganadora en sólo
**4 de 95 (4,2 %)** y **3 de 96 (3,1 %)** eventos. `B0` lo hace en el 23 %; `B2`/`B3` en el
63–68 %.

**Diferencia lead 24 → lead 9.** Se afila —entropía 1,631 → 1,468, rango medio 2,711 → 2,344,
top-3 0,716 → 0,844— y el Brier mejora de 0,07113 a 0,06534. **Coherente con L1.1**, donde el
pronóstico de 9 h (revisión 18z) era mejor en las cuatro medidas. La calibración se mantiene en
los dos leads.

# 5 · `B2` / `B3`

**Ranking bueno, confianza ruinosa.** Aciertan la banda ganadora en **0,316–0,365** contra
**0,091** del azar: entre **3,5 y 4 veces** mejor. Y su Brier (0,115–0,124) es **peor que el
uniforme** (0,0826).

**Por qué:** poner 1,0 en una banda y fallar cuesta `2/11 = 0,182` de Brier. Con una tasa de
acierto de ~1/3, el coste esperado supera al del azar. **No es falta de señal: es exceso de
confianza.**

> **Y una advertencia sobre top-2/top-3 que impide una comparación falsa:** un determinista pone
> 1,0 en una banda y 0,0 en las otras diez. Si falla, la ganadora **empata con los diez ceros** y
> su rango es `1 + (10+1)/2 = 6,5`. **Nunca puede caer en rango 2 ni 3**, así que
> `top-1 = top-2 = top-3` por construcción. **Comparar top-k (k>1) entre deterministas y
> probabilísticos no mide nada**: los primeros son estructuralmente incapaces de expresarlo.

**Y `B4` no es «`B2` con dispersión»:** su argmax coincide con la banda de `B2` sólo en el
**69,5 %** (lead 24) y **65,6 %** (lead 9), y con la de `B3` en el 76,8 % y **52,1 %**. La
distribución empírica de error desplaza la moda respecto al pronóstico puntual.

# 6 · `B0` VS UNIFORME

    benchmark PRIMARIO PRE-REGISTRADO   B0_clima     0,10154 / 0,10119
    control estructural (ex-post)        uniforme     0,0826446

**`B0` es peor que no mirar datos**, y la calibración explica por qué: su **pendiente es
+0,081 [−0,261, +0,216]** y **+0,089 [−0,280, +0,207]** — **el IC contiene el cero en los dos
leads**. *Las probabilidades de `B0` casi no llevan información sobre el resultado.* Su
fiabilidad lo enseña sin ambigüedad: `p ∈ [0,50, 1,01)` predicho **0,7353**, observado
**0,0741**.

**La jerarquía se mantiene y no se reescribe L1.4**: la comparación pre-registrada era
`B4 − B0` (−0,0304 / −0,0359); la comparación contra el uniforme (−0,0115 / −0,0173) es un
**control estructural añadido ex-post** y así se etiqueta. **`B0` no se modifica.**

# 7 · TEMPORALIDAD

    mes        n    B4        B0        B4-B0      B4-unif        (lead 24)
    2026-05   29  0,07577   0,11337   -0,03761   -0,00688
    2026-06   22  0,07284   0,09823   -0,02539   -0,00981
    2026-07   25  0,06730   0,09784   -0,03054   -0,01535
    2026-08   19  0,06712   0,09220   -0,02507   -0,01552

    lead 9:   -0,01766 · -0,01235 · -0,01657 · -0,02346   contra el uniforme

**`B4` bate al uniforme en 4 de 4 meses, en los dos leads.** La ventaja **crece** hacia agosto
en los dos (de −0,0069 a −0,0155 y de −0,0177 a −0,0235), y `B0` también mejora con el tiempo:
**la segunda mitad es más fácil**, y eso está dicho, no seleccionado. **No se elige periodo.**

# 8 · MISSINGNESS

    poblacion objetivo (target)          187 eventos EGLC
    poblacion observacional              137 (nivel evento) · 135 (nivel fecha)
    poblacion PUNTUADA (fc+obs+>=20)      95 (lead 24) · 96 (lead 9)

Los **22 / 21** excluidos son **contiguos desde el inicio** (2026-04-08 → 05-01): arranque de la
ventana expansiva. Son más fríos (17,3 contra 24,3 °C) y su banda ganadora está más arriba
(5,8 contra 4,8) — **estacionalidad del calendario, no selección por resultado**.

> **Limitación que se declara y no se suaviza: el test NO cubre abril.** No se dirá
> «representativo de abril–agosto». La ventana puntuada es **mayo–agosto de 2026, una estación,
> una ciudad**.

# 9 · RED TEAM — pruebas ejecutadas

| prueba | resultado |
|---|---|
| **leakage** (alterar el futuro +25 °C) | ninguna probabilidad anterior cambia; las posteriores sí → **la prueba tiene poder** |
| **look-ahead** | `available_at ≤ t_asof` en 95/95 y 96/96; `target_date` nunca en su train |
| **unidad estadística** | bootstrap **clusterizado por evento**; leads nunca agregados |
| **binning arbitrario** | ECE de `B4`: 0,00970 (predefinido) · 0,00953 (deciles) · 0,00498 (grueso) → **estable** |
| **dependencia del nº de bandas** | un solo estrato `{11}`; nulo del estrato publicado |
| **pocos eventos** | quitando los **20 más favorables**: delta −0,00446, IC95 [−0,00850, −0,00078], **sigue excluyendo el cero**. Quitando los más DESfavorables el delta **empeora** (−0,0120 → −0,0139): el resultado no vive de una cola |
| **reparto evento a evento** | `B4` mejor en **65**, peor en **30**. **Mediana −0,01551, media −0,01151**: la mediana es *más* favorable → efecto **amplio**, no de unos pocos casos |
| **efecto estacional** | presente y nombrado; `B0` mejora a la vez que `B4` |
| **clipping / epsilon** | Brier varía ≤3e-3 entre 1e-8 y 1e-2; el LogLoss de los deterministas **no se usa** |
| **redondeo** | la partición es sobre enteros; el empate exacto usa redondeo bancario, **declarado** (A-288) |
| **calibración contaminada** | la curva se mide **sobre el mismo test**: los pronósticos son OOS, **la curva no es una calibración OOS entrenada**. Declarado como diagnóstico |

## LA OBJECIÓN MÁS FUERTE CONTRA `B4`, Y ES ESTRUCTURAL

> `B4` asigna a cada banda la **frecuencia empírica** de `round(f + e)` sobre los errores del
> train. **Si la distribución de error es estacionaria, `B4` está calibrado POR CONSTRUCCIÓN**:
> es un estimador de frecuencia de la misma cantidad que luego se mide.
>
> **Que `B4` salga bien calibrado NO es evidencia independiente de habilidad predictiva.** Es
> evidencia de que la distribución de error es **estable** entre train y test.
>
> Lo que **no** es tautológico —y es donde vive la señal— es que el **pronóstico puntual** esté
> centrado cerca de la banda ganadora. Eso se mide en el **ranking** (rango medio 2,34–2,71
> contra 6,0 del azar) y en el **Brier contra el uniforme** (−0,0115 / −0,0173), no en la
> calibración.

# 10 · DEFECTOS

| severidad | hallazgo |
|---|---|
| **A — bloqueante** | **ninguno** |
| **B — requiere corrección** | **ninguno** |
| **C — documentable** | (1) `available_at` sigue **sin validar externamente** (tarea #75); (2) la curva de calibración **no es OOS entrenada**; (3) el test **no cubre abril**; (4) `B0` es peor que el uniforme y era el benchmark pre-registrado; (5) la calibración de `B4` es **casi tautológica** por construcción; (6) una estación, una ciudad, cuatro meses |

**Defecto encontrado y corregido DURANTE la etapa, en mi propio instrumento:** el ajuste
logístico reventaba con `OverflowError` sobre `B0` (logits de ±13,8 por el recorte). Era del
**ajuste**, no de los datos: sigmoide estabilizada y paso de Newton amortiguado. **No cambia
ningún modelo.**

# 11 · HIPÓTESIS PARA VALIDACIÓN FUTURA — **no implementadas, no son resultados**

1. **Corrección de sesgo condicional a la temperatura.** L1.1 midió sesgo −0,55 °C bajo 15 °C y
   +0,37 entre 25 y 30: encogimiento hacia la media. `B3` corrige un sesgo global y por eso no
   ayuda. *Requiere preinscripción propia y walk-forward propio.*
2. **Calibración OOS entrenada** (Platt / isotónica) con procedimiento walk-forward propio.
   **Nunca entrenada sobre este test.**
3. **Usar los cuantiles del proveedor** (`p10…p90`, poblados en 230 de 236) como distribución
   predictiva alternativa. Cobertura medida 84,3 %/87,8 % contra 80 % nominal.
4. **El lead 9 domina al 24 en todo.** Si eso se sostiene, la pregunta operativa es cuánta señal
   se pierde por decidir antes — **pregunta de fase económica, no de Level 1**.

# 12 · RECOMENDACIÓN

## **CONTINUAR A `L1.6` — INFERENCE**

Las métricas se reproducen, la calibración está correctamente calculada, **ranking y calibración
quedan separados** (y su divergencia documentada: `B2` gana en top-1 a lead 9 y pierde de largo
en rango medio), no se ha introducido selección post-hoc, no hay defectos bloqueantes y todas
las limitaciones están escritas.

**Lo que NO se declara:** ni «hay edge» ni «no hay edge». El veredicto de Level 1 requiere
L1.6 → L1.7 → L1.8. **Toda señal positiva sigue condicionada a la validación externa de
`available_at`.**
