# L1.6 — INFERENCE · LOCK

**Escrito y espejado ANTES de ejecutar.** Integridad del lock previo verificada por `sha256`
inmediatamente antes (ver salida del guion). No se buscan precios, EV, PnL, umbrales,
estrategias ni ciudades; no se toca producción; `D0-P` = BLOCKED. **No se emite el veredicto de
Level 1**: eso es L1.8.

## Lo que NO cambia

Cinco modelos cerrados. Unidad de inferencia **EVENTO**. Bootstrap clusterizado por evento,
**10 000**, semilla **20260913**. Escalera **11**. `epsilon = 1e-6`. Leads separados.
Benchmark primario pre-registrado `B0`; uniforme 1/11 = control estructural ex-post.

## Comparaciones autorizadas — LAS MISMAS, ninguna nueva

    B1-B0, B2-B0, B3-B0, B4-B0        pre-registradas (LOCK_L1_4)
    modelo - uniforme                  control estructural, declarado ex-post en A-289

**No se añade ninguna comparación modelo-contra-modelo nueva.** En particular **no** se compara
`B4` contra `B2`/`B3` como contraste formal: sería una comparación no declarada y §16 del
preregistro existe justo para impedirlo.

## PLACEBOS — número y forma DECLARADOS AHORA, antes de ver ninguno

**Placebo A — desalineamiento temporal.** Se empareja el pronóstico del día `t` con el evento
del día `t + k`, conservando toda la estructura temporal y el walk-forward.

    k ∈ { -7, -3, -1, +1, +3, +7 }      SEIS desplazamientos, conjunto FIJO

**Placebo B — permutación dentro del evento.** Se permuta cuál de las 11 bandas es la ganadora,
uniformemente, conservando la escalera y las probabilidades.

    1 000 permutaciones, semilla 20260913

**Se ejecutan los siete experimentos completos y se reportan TODOS**, salgan como salgan. No se
ejecutan placebos adicionales buscando uno que falle.

**Expectativa escrita antes de correr**: en los dos placebos la ventaja de `B4` sobre el
uniforme debe **desaparecer** (IC95 que contenga el cero). *Si NO desaparece, el resultado de
L1.4/L1.5 es un artefacto de estructura y `L1.6 = BLOCKED`.*

## Test temporal

Diferencia entre el delta de la 1ª mitad y el de la 2ª mitad (corte **2026-06-23**,
pre-registrado), con IC95 bootstrap clusterizado por evento. **Diagnóstico de estabilidad, no
selección de periodo.**

## Potencia

* **Efecto mínimo detectable** al 80 % de potencia y α = 0,05 bilateral, con el `n` de clusters
  y la desviación observada del delta apareado.
* **Correlación entre leads** del delta por evento: los dos leads comparten evento, así que
  `191 = 95 + 96` **no son 191 clusters independientes**. Se mide y se dice.
* Si el efecto observado queda por debajo del mínimo detectable, o el IC es compatible con cero,
  **`INCONCLUSIVE` es un resultado válido** y se emite.

## Cierre

`L1.6 = CLOSED` si los placebos se comportan como deben, el IC95 primario es reproducible, la
potencia está cuantificada y no aparece ningún defecto. `L1.6 = BLOCKED` si un placebo
sobrevive o aparece un defecto metodológico.
