# PREREG E1 — ¿está sesgado el PRECIO de mercado?

**Sesión:** B · **Congelado:** 2026-09-11, **antes de ver un solo dato de resultado**
**Script:** `scripts/research/run_e1.py` · **Informe:** lo escribe el script, no se edita a mano

Todo lo de este documento está fijado **ahora**. Nada se toca después de ver el resultado.
Si algo hay que cambiar, se retira este preregistro y se escribe un E1 v2 que lo diga.

---

## 0. Por qué esta hipótesis y no otra

`docs/research/EDGE_RESEARCH_2026-09-11.md` cierra, con medición, todas las demás:

* **Strategy A** (pronóstico público vs precio): R21 NO OPERABLE, R22 sin skill en 10/10
  estratos. El mecanismo es adverse selection y ningún umbral lo arregla.
* **Market making** y **coherencia de partición (maker)**: la Adenda 2 midió el libro real.
  Medio spread 0,0050–0,0205 contra un margen de fair value de 0,036. Falla por 1,8× en el
  mejor caso posible. Clase E.
* **Coherencia (taker)**: 0 de 96 particiones completas rentables tras fees. Clase E.

Queda **una** hipótesis, y es la única que **no** compite en información: en vez de intentar
saber más que el mercado sobre el tiempo, preguntamos si **el precio del propio mercado está
sistemáticamente equivocado** en algún tramo. No requiere pronóstico. No requiere ser más
listo que nadie. Sólo requiere que exista un sesgo de precio y que sobreviva a los costes.

**Mecanismo propuesto (obligatorio declararlo antes):** *favourite–longshot bias*. En
mercados con flujo minorista, las apuestas de baja probabilidad cotizan **caras** porque el
comprador paga por el payoff asimétrico (3 céntimos para cobrar 1 $). Documentado desde
Griffith (1949) y Thaler & Ziemba (1988) en hípica y deportes. **Quién está al otro lado:**
participantes recreacionales comprando cola barata. **Por qué no está arbitrado:** explotarlo
exige **vender** el longshot — capital inmovilizado hasta resolución, rachas de pérdida
grandes (vendes a 3¢ y pierdes 97¢ el 3 % de las veces) y un lado corto ejecutable.

**Dirección esperada, declarada por adelantado:** en los buckets baratos, la frecuencia
realizada debe quedar **por DEBAJO** del precio medio (el mercado paga de más por la cola).
Un sesgo del signo contrario **no** confirma esta hipótesis: la refuta y se reporta como tal.

---

## 1. Datos y universo — FIJADO

Mismo substrato y misma disciplina as-of que R21/R22, para que sea comparable:

```
filas   = backtest.candidates(con, days, dataset_version='backfill_2b_v1')
days    = mercados con uma_resolution_status='resolved' y end_date no nulo
por fila: p_mid (INDICATIVE as-of), won (resolución), event_id, target_date
```

**`p_model` NO se usa en ningún punto de E1.** No entra en el bucketing, ni en el
criterio, ni en el reporte. Si apareciera, esto dejaría de ser un test del precio.

## 2. Bucketing — FIJADO AHORA

Cortes en `p_mid`, elegidos **antes** de ver ninguna frecuencia:

```
[0, .02) [.02, .05) [.05, .10) [.10, .15) [.15, .20) [.20, .30) [.30, .50) [.50, .75) [.75, 1]
```

**Por qué éstos y no deciles:** R22 descubrió que sus «deciles» eran bins de anchura fija y
que el bin 0 contenía el **79,2 %** de las filas. Unos deciles reales sobre una distribución
tan cargada abajo darían cortes elegidos por los datos. Estos cortes son finos donde vive la
masa (abajo, que es además donde el mecanismo predice el sesgo) y gruesos arriba.
**Nueve buckets. No se añaden, ni se fusionan, ni se reparten después.**

## 3. Estadístico — FIJADO

Por bucket `b`:

```
Delta(b) = frecuencia_realizada(b) − media(p_mid en b)
```

`Delta > 0` = el mercado **infravalora** (pagó menos de lo que valía).
`Delta < 0` = el mercado **sobrevalora** — el signo que predice el longshot bias abajo.

## 4. Incertidumbre — FIJADO

**Block bootstrap POR EVENTO, 2 000 réplicas, semilla 20260911. Nunca por fila.**
Las bandas de un evento son una partición: si el evento sale de una forma, sale de esa forma
para todas sus bandas a la vez. Tratar filas como independientes exagera la precisión — es el
bloqueante de la sesión A sobre R21, donde 468 trades eran 211 eventos.

`SE(b)` = desviación típica de `Delta(b)` sobre las réplicas.

## 5. Criterios de aceptación — FIJADOS, LOS CUATRO NECESARIOS

Un bucket `b` contiene edge explotable **si y sólo si** cumple **los cuatro**:

| # | criterio | umbral |
|---|---|---|
| **C1** | cobertura mínima | `n_eventos(b) >= 100` (el número de R22, no uno nuevo) |
| **C2** | significación | `abs(Delta(b)) > 2 * SE(b)` |
| **C3** | estabilidad temporal | el **signo** de `Delta(b)` se mantiene en las **dos mitades** del periodo, partido por la mediana de `target_date`, y **C2 se cumple en el conjunto completo** |
| **C4** | significación **económica** | `abs(Delta(b)) > coste(b)`, con `coste(b) = medio_spread(b) + 0,05 * p * (1 − p)` |

**`coste(b)` se condiciona por bucket de precio**, no es una constante. Es la conclusión
operativa de la Adenda 3: entre el bin 0 y el bin 7 hay un factor de tres en la media del
spread. El medio spread por bucket sale de `scripts/research/book_measurements.py` sobre los
libros reales de `paper-state`; si un bucket no tiene libros suficientes (`< 100`), se usa el
**percentil 75** del medio spread global como cota conservadora, y el script lo declara.

## 6. Multiplicidad — FIJADO

Se prueban **9 buckets**. Corrección de **Holm–Bonferroni** sobre los 9 p-valores del
bootstrap. **El conteo de familia es 9 aunque sólo uno sobreviva** — es exactamente el punto
del §20 del encargo: distinguir *discovery* de *evidence*.

Un bucket que pase C1–C4 pero no sobreviva a Holm se reporta como **C — SPECULATIVE**, no
como hallazgo.

## 7. Resultado negativo, declarado POR ADELANTADO

**Si ningún bucket cumple C1–C4 tras la corrección de multiplicidad, la respuesta es:**

> **No existe sesgo de precio explotable en este substrato.**

Y como E1 es la última hipótesis viva, la conclusión que sigue es la del §34 del encargo:

> **No tenemos evidencia suficiente de edge explotable en los mercados meteorológicos de
> Polymarket. La categoría se abandona y el universo se busca fuera del tiempo meteorológico.**

Ese resultado **se publica tal cual**. No se prueban cortes alternativos, no se relajan los
umbrales, no se añaden buckets, no se cambia el estadístico. Si alguien quiere probar otra
cosa, es un preregistro nuevo con su propio conteo de familia.

## 8. Lo que este test NO puede contestar

* **No mide lo que se paga de verdad.** `p_mid` es INDICATIVE; el precio ejecutable exige
  simulación contra libro, que existe (R23) pero no se ha corrido sobre esta serie.
* **No prueba que el lado corto sea ejecutable.** Si el sesgo es longshot, explotarlo exige
  comprar el token NO, y el backfill histórico **sólo guardó el YES** en los 6 143 mercados.
  Un C4 positivo abre una pregunta de ejecución, no la cierra.
* **Periodo acotado** a abril–septiembre 2026 por el archivo deslizante de Single Runs. Un
  sesgo estacional es indistinguible de uno estructural en esta muestra, y C3 es una
  comprobación de estabilidad **dentro** del periodo, no fuera de él.
* **No es una estrategia.** Es la condición necesaria de una. El sizing, la ejecución y el
  riesgo son trabajo posterior y necesitan su propio preregistro.
