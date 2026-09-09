# PREREGISTRO — Corrida de modo papel (R24)

**Estado:** BORRADOR, **NO CONGELADO**. Por A-29.4 no se congela hasta pasar refutación hostil
sin bloqueantes abiertos.
**Fecha de redacción:** 2026-09-09 · **Autor:** Claude (sesión A) · **Pista:** A-31
**Host:** GitHub Actions (decisión del usuario, A-29.2) · **Código:** `feat/paper-actions`

---

## §0. Qué gobierna este documento, y el número que determina su forma

Gobierna la corrida de N días de `paper_cycle.py` que decide si el sistema está **listo para
operar** — que en este proyecto significa una cosa concreta y acotada: *que sólo falte el permiso
explícito del usuario para levantar D0*. No significa que el sistema sea rentable.

Esa distinción no es prudencia retórica, es aritmética. El PnL de una posición binaria comprada a
precio `p` con probabilidad verdadera `q` tiene media `C·(q−p)` y desviación típica `C·√(q(1−q))`
por operación, con `C = presupuesto/p` acciones. Con el presupuesto de §4 (200 USDC por posición),
el número de operaciones necesario para que la media acumulada alcance **2 σ** es:

| precio `p` | ventaja `q−p` | acciones | media/op | sd/op | **n para 2 σ** | días a 5 op/día |
|---:|---:|---:|---:|---:|---:|---:|
| 0,20 | 0,02 | 1 000 | 20,00 | 414,25 | **1 716** | 343 |
| 0,20 | 0,03 | 1 000 | 30,00 | 420,83 | **787** | 157 |
| 0,35 | 0,03 | 571 | 17,14 | 277,36 | **1 047** | 209 |
| 0,50 | 0,02 | 400 | 8,00 | 199,84 | **2 496** | 499 |
| 0,50 | 0,03 | 400 | 12,00 | 199,64 | **1 107** | 221 |
| 0,50 | 0,05 | 400 | 20,00 | 199,00 | **396** | 79 |

`n = (2·sd/media)²`. Aun en el caso más favorable de la tabla —una ventaja de 5 puntos, que sería
enorme— hacen falta **79 días**; con la ventaja de 3 puntos que el diseño contempla, entre **157 y
221 días**.

> **Consecuencia, declarada ANTES de ejecutar: el PnL de esta corrida NO es un criterio de éxito ni
> de fracaso.** Una corrida de dos o cuatro semanas no puede distinguir una ventaja real de tres
> puntos del ruido, y presentar su PnL como evidencia —en cualquiera de los dos signos— sería
> pseudociencia. Se reporta (§7) porque ocultarlo sería peor, y se reporta **con su intervalo**,
> que será ancho.

Lo que una corrida de N días **sí** puede establecer es que la máquina funciona sin supervisión y
que sus decisiones son las que dice tomar. Ése es el objeto de §6.

---

## §1. Símbolos y ancla temporal

Escritos aquí porque su ausencia fue el bloqueante nº 2 de la refutación de `PREREG_M2_ERROR.md`
(A-32) y una de las cuatro causas de retirada de `PREREG_M2_FORECAST_ERROR.md` (A-30). **Son dos
símbolos distintos y no se abrevian a uno.**

- **`D`** — `target_date`: el día cuya temperatura máxima liquida el contrato. **Parámetro
  obligatorio del caller** (`--target-date`), por PHASE_2D_STRATEGY_A_DESIGN.md §C. En modo papel
  el caller es el planificador de Actions, que lo fija por reloj (§5). Nunca se deriva del catálogo.
- **`T_end`** = `D 12:00:00Z` — fin de la ventana de resolución (R8: verificado en 8 557/8 557
  eventos). **Sólo sirve para derivar el lead.** No es un instante de decisión.
- **`T_asof`** = `T_end − lead_hours` — **el instante de decisión**, y el único operando de
  cualquier regla de admisibilidad. Toda fila usada en una decisión debe cumplir
  `available_at ≤ T_asof`.
- **`lead_hours` ∈ {9, 24}** — rango operativo (PREREG_LEAD_HOURS_RANGE). Cada lead tiene su
  `T_asof`: `D 03:00Z` para 9 h, `D−1 12:00Z` para 24 h.
- **`lead_efectivo`** = `T_end − instante_real_de_ejecución`. **No es igual a `lead_hours`**: el
  cron de Actions llega tarde (§5). Se **mide y se reporta** por ciclo; no se asume.

---

## §2. Precondiciones — las cinco tienen que cumplirse ANTES del día 1

La corrida **no empieza** mientras alguna falle. Fail-closed, comprobable, y el informe declara la
fecha en que cada una pasó.

| # | Precondición | Cómo se comprueba |
|---|---|---|
| P1 | **M2 produce cuantiles fiables.** Los bloqueantes de A-32 —en particular la clave de emparejamiento dependiente de la zona horaria de sesión— resueltos y re-ejecutados. | `weather_forecasts.forecast_p10..p90` no nulos para el universo de §3, y `PREREG_M2_ERROR.md` sin bloqueantes abiertos |
| P2 | **`tau` fijado por calibración fuera de muestra (R21)**, no por juicio. | El informe de R21 nombra `tau` y su procedimiento; se copia a `vars.PAPER_TAU` sin redondear |
| P3 | **Módulos de ingesta en `main`.** `weather.py`, `observations.py`, `stations.py` fusionados; la etapa `forecasts` deja de reportar SKIPPED. | Un ciclo manual con `forecasts` en OK |
| P4 | **Liquidación cableada.** La etapa `settle` cierra posiciones con la etiqueta real bajo el SettlementOperator del mercado. | `settle` en OK con `positions_settled > 0` en un ciclo de prueba |
| P5 | **Colector con ≥ 7 días continuos previos.** El book no es recuperable; empezar a decidir sin historia previa deja el primer tramo sin contexto. | `store_stats` y el historial de commits de `paper-state` |

**P3, P4 y P5 no dependen de mí** (P3/P4 son pista de la sesión B). Esta corrida no puede
programarse por decisión unilateral de A: se declara la precondición y se espera.

---

## §3. Universo

- **Mercados:** los descubiertos ABIERTOS (`discover(closed=False)`, R26) cuyo `endDate` cae en `D`,
  con `available_at` sellado en el instante del descubrimiento.
- **Filtro de universo, no derivación de `target_date`:** la selección usa `endDate` del catálogo
  (§C de 2D prohíbe *derivar el parámetro*, no *filtrar candidatos*; la distinción se registra en
  A-31 y no se difumina en el código).
- **Excluidos, declarado antes:**
  - eventos que Strategy A excluye por sus propias puertas (partición de bandas, sumas fuera de
    tolerancia, precio ausente) → `markets_excluded`, con razón;
  - mercados con `fee_status ≠ 'KNOWN'` → sin fee no hay coste, y sin coste no hay operación (D19);
  - mercados cuyo `book_snapshot` del ciclo falte → no se opera contra un precio no observado.
- **NO se excluye por `rounding_rule`.** La refutación de A-32 pone en duda la exclusión de los
  1 936 mercados `tenths` de B y **yo no he podido recomputarla**; hasta que se resuelva, este
  documento no hereda una exclusión que no ha verificado. Si al ejecutar resulta que esos mercados
  no son representables, caerán por la puerta de Strategy A y quedarán contados en
  `markets_excluded` — visibles, no silenciados.

---

## §4. Parámetros congelados

| Parámetro | Valor | Origen |
|---|---|---|
| `bankroll` | 10 000 USDC nocionales | `config.DEFAULTS` |
| `fixed_fraction` | 0,02 | `config.DEFAULTS` |
| `size_cap` | 0,02 | `config.DEFAULTS` (presupuesto efectivo: 200 USDC/posición) |
| `tau` | **de R21 (P2)** — no fijado aquí | preregistro del backtest |
| `exit_mode` | `hold_to_resolution` | redención sin fee de venue (D19); evita modelar una salida que no se observa |
| `x_exec` | **0,0, declarado como tal** | D19: «0 sólo como valor JUSTIFICADO y declarado». Con `hold_to_resolution` y fill simulado contra el book observado, el coste de spread ya está dentro del VWAP; `x_exec` cubriría deslizamiento adicional que aquí no aplica |
| `price_layer` | `SIMULATED_EXECUTABLE` | R23 |
| `model` (M1) | `icon_seamless` | D12 |
| `rebate` de maker | **0** | D19: pool pro-rata no calculable ex ante; se reporta la cota superior aparte |

Ningún parámetro se toca durante la corrida. Cambiar uno **termina la corrida** y abre otra
(§8), con su propio preregistro.

---

## §5. Duración, calendario y el desfase del cron

- **N = 21 días naturales consecutivos**, contados desde el primer ciclo en que las cinco
  precondiciones se cumplen. Tres semanas cubren ambos leads en todos los días de la semana y
  suficientes ventanas de pronóstico; no se eligen por potencia estadística, que §0 ya declara
  inalcanzable a cualquier N razonable.
- **Dos decisiones al día**, una por lead: `40 11 * * *` (lead 24 h, `D` = mañana) y `40 2 * * *`
  (lead 9 h, `D` = hoy). Disparan ~20 min antes de `T_asof` porque el cron de Actions se retrasa.
- **El desfase se mide, no se asume.** Retrasarse **acorta** el lead efectivo, nunca lo alarga, así
  que no puede fabricar información — pero cambia el lead, y el lead es la clave de estratificación
  de M2. Se registra `lead_efectivo` por ciclo y el informe publica su distribución.
- **Regla pre-declarada:** un ciclo con `lead_efectivo` fuera de `lead_hours ± 1 h` se marca
  `LEAD_DRIFT` y **se excluye del criterio C5**, pero se conserva y se reporta.
- **Un día perdido no se recupera.** No se rellena hacia atrás ni se desplaza el calendario;
  se cuenta contra C1.

---

## §6. Criterios de éxito — PRIMARIOS, binarios, comprobables

La corrida se declara **APTA** si y sólo si **los seis** se cumplen. Cualquier fallo → **NO APTA**,
con la causa nombrada. No hay categoría intermedia y no se renegocian después de ver los datos.

| # | Criterio | Umbral | Cómo se comprueba |
|---|---|---|---|
| **C1** | **Continuidad.** Ciclos de decisión completados. | **≥ 90 %** de los 42 programados (≥ 38), y **ningún hueco de más de 48 h** | commits de `paper-state` + resúmenes por ciclo |
| **C2** | **Integridad as-of.** Decisiones que usan una fila con `available_at > T_asof`. | **exactamente 0** | auditoría sobre las filas persistidas; una sola violación tumba la corrida |
| **C3** | **Reproducibilidad.** Reconstruir la DuckDB desde los shards y re-evaluar cada decisión reproduce señal, precio de fill y tamaño. | **100 %** de las operaciones | `store.load_shards` + re-ejecución determinista |
| **C4** | **Coste aplicado.** Fills con fee calculada por el modelo de D19 y `fee_status='KNOWN'`. | **100 %**; 0 fills con fee nula no justificada | `paper_trades.fees` frente a `market_fee_schedule` |
| **C5** | **Coherencia con el backtest.** Sobre los ciclos sin `LEAD_DRIFT`: tasa de señales accionables y reparto de razones de rechazo dentro del envolvente del backtest de R21. | ambas tasas dentro de **±10 puntos porcentuales** del valor de R21 | comparación tabulada |
| **C6** | **Calibración.** Cobertura empírica de los intervalos de `p_model` sobre las posiciones liquidadas. | el IC95 de la cobertura observada **contiene** el nominal | Wilson sobre las liquidadas |

**C6 se declara con su límite por delante:** con las posiciones que 21 días producen, el IC de
cobertura será ancho y el criterio será **fácil de pasar**. Se incluye porque una calibración
groseramente rota (cobertura 0,4 donde debía ser 0,9) sí se detecta con pocas observaciones, y ése
es el fallo que importa atrapar. **No se presentará como evidencia de buena calibración.**

---

## §7. Lo que se reporta y NO es criterio

- **PnL neto y bruto, con IC bootstrap.** Por §0, sin poder para ningún signo. El informe escribe
  literalmente que el resultado es compatible con cero.
- Número de operaciones, tamaño medio, precios de fill frente a mid indicativo (cuánto cuesta el
  spread realmente).
- Fees pagadas y **cota superior del rebate de maker** (0,25 × fee equivalente, D19).
- Distribución de `lead_efectivo` y recuento de `LEAD_DRIFT`.
- Razones de rechazo del motor paper, con recuento (`net_edge_below_tau`, `below_min_order_shares`,
  `no_book_this_cycle`, `fee_unknown_fail_closed`, …).
- Tamaño del almacén de shards y su crecimiento diario.
- Incidencias de cuota: 429, ciclos parados, reanudaciones.

---

## §8. Reglas de parada

**Parada inmediata y corrida NULA** (no «parcial»):

1. Cualquier indicio de ruta de dinero real: una clave, una firma, un endpoint de orden. Gate D0.
2. Una violación de C2 (as-of).
3. Un cambio de cualquier parámetro de §4 durante la corrida.
4. Escritura en `main` desde un workflow.

**Parada con corrida conservada y declarada corta:**

5. 429 sostenido que impida ≥ 3 ciclos consecutivos.
6. Crecimiento del almacén > 50 MB (obligaría a cambiar el diseño de persistencia a mitad).
7. Petición del usuario.

---

## §9. Limitaciones declaradas ANTES

- **`SIMULATED_EXECUTABLE` no es un fill.** Se simula contra el book observado en el ciclo, que
  puede haber cambiado entre la captura y `T_asof`. Es una cota razonable, no una ejecución.
- **La escalera almacenada está truncada a 10 niveles** (`DEFAULT_KEEP_LEVELS`). Un fill que agote
  el book almacenado se marca `book_exhausted` y **se cuenta aparte**; sesga a menos ejecución,
  nunca a más.
- **`minimum_order_size` es ambiguo** (5 acciones vs 5 USDC de nocional). Se exigen ambas, que
  rechaza más de lo que el venue rechazaría.
- **Un solo `p_model`.** Es `p_weather` (Strategy A V1). Todo lo que herede de M2 hereda también sus
  limitaciones, incluida la de disponibilidad de la etiqueta a 24 h, que sigue siendo un supuesto.
- **`neg_risk: true`** en estos mercados (OBSERVADO 2026-09-09) y **no se modela**: el FADE se
  simula como compra taker del token complementario contra su propio book, que es correcto como
  ejecución pero ignora la mecánica del adaptador de riesgo negativo.
- **No hay datos de un competidor.** La corrida no dice nada sobre impacto de mercado: nuestras
  órdenes no existen y por tanto no mueven el book.

---

## §10. Integridad

- Este documento se **congela y hashea antes del primer ciclo** de la corrida, y su sha se cita en
  `DECISIONS.md`. Un documento con bloqueantes abiertos **no se congela** (A-29.4).
- Ningún umbral de §6 se calcula ni se ajusta después de ver resultados.
- Si un criterio resulta mal especificado al ejecutar, la corrida se declara **NO APTA por
  especificación** y se rehace el preregistro. No se enmienda en caliente.
- La corrida **no toca dinero real en ningún caso**. Terminarla con éxito significa exactamente
  «sólo falta que el usuario levante D0», y levantarlo es decisión suya, no nuestra.
