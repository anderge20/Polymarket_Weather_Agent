# POST-L1.8 · FASE A — BENCHMARK ESTRUCTURAL COMPLETO · LOCK

**Escrito y espejado ANTES de ejecutar nada.** No se toca L2, precios, EV, PnL, trading,
ejecución, order book, umbrales, estrategia, stake, selección de oportunidades, optimización
económica, dinero real, paper trading, bot ni producción. `D0-P` = BLOCKED. `L2` = BLOCKED.
**Los artefactos de L1 no se sobrescriben**: esto vive en `postl1/A_benchmark_estructural/`.

---

## 0 · UN DEFECTO DEL BENCHMARK ANTERIOR QUE HAY QUE DECIR PRIMERO

`CTRL_escalera` (L1.7) repartía masa sobre **«las 7 bandas centrales»**, y ese 7 salió de la
**dispersión media de `B4`**:

```python
disp = stx.mean(sum(1 for a in x["p"]["B4_fc_prob"] if a > 0) for x in f)
semi = max(1, int(round((disp - 1) / 2)))
```

> **El benchmark tomaba prestado un parámetro del modelo que estaba juzgando.** No es
> catastrófico —no usa el pronóstico ni el resultado— pero **no es un benchmark limpio**: su
> anchura la fija `B4`. Cualquier familia estructural nueva debe fijar su forma **sólo con la
> geometría del contrato**, y el `CTRL_escalera` de L1.7 queda reclasificado como *control
> preliminar*, no como benchmark estructural.

---

## 1 · CUÁL ES LA REPRESENTACIÓN ESTRUCTURAL CORRECTA

Una escalera es `(≤ L)`, singletons `L+1 … U−1`, `(≥ U)`. Los únicos grados de libertad son
**`L` y `U`** — y con ellos `n = U − L + 1`. **Todo lo demás es consecuencia.**

Al elegir `L` y `U` el mercado **revela dónde cree que va a caer la temperatura**: pone el
interior sobre el rango plausible y deja que los extremos abiertos absorban las colas.

Así que la pregunta *«¿qué sabe el contrato por su propia forma?»* tiene una respuesta natural
y **no ajustable**:

> **¿Dónde, históricamente, ha caído la ganadora RESPECTO A LA ESCALERA?**

Eso es una distribución empírica sobre **posiciones relativas**, estimable **walk-forward** con
exactamente la misma disciplina que la distribución de error de `B4` — y **sin tocar el
pronóstico**. Es el análogo estructural exacto de `B4`:

    B4  : distribucion empirica del ERROR DE PRONOSTICO      -> necesita el forecast
    S3  : distribucion empirica de la POSICION DE LA GANADORA -> necesita solo la escalera

**Por eso `S3` es el benchmark estructural primario**: es el único de la familia que usa la
geometría **completa** (a través del mapa posición→banda) y que **no tiene ningún parámetro
libre que se pueda ajustar mirando el resultado**.

---

## 2 · LA FAMILIA, PRE-REGISTRADA ENTERA ANTES DE VER NINGÚN RESULTADO

Las tres se ejecutan y **las tres se reportan**, salga lo que salga.

### `S1` — uniforme sobre el INTERIOR *(corrige el `CTRL_escalera` de L1.7)*

Masa uniforme sobre las **bandas cerradas** (todas menos las dos abiertas); cero en las
abiertas. **La anchura la fija la escalera, no `B4`.** Es la lectura mínima de «el mercado puso
el interior donde esperaba el resultado».

### `S2` — uniforme sobre TODAS las bandas

`p = 1/n`. Es el control estructural ya usado en L1.4–L1.7. Ignora la forma salvo por `n`. Se
mantiene por continuidad y para que las cifras sean comparables con el histórico.

### `S3` — POSICIÓN EMPÍRICA, walk-forward **— PRIMARIO**

Para cada evento pasado con etiqueta disponible en `t_asof`, se calcula la posición de la
ganadora en el orden frío→caliente **relativa al centro** de su escalera. La distribución
empírica de esas posiciones, aplicada a la escalera del evento de test, da `p_i`. Las
posiciones que caen fuera de la escalera del test se acumulan en la banda abierta
correspondiente — **que es exactamente lo que las bandas abiertas significan**.

**Condiciones idénticas a las de `B4`**: sólo eventos con `label_av(d) ≤ t_asof`, mínimo 20,
ventana expansiva, cero información posterior a `t_asof`.

### Lo que NO se hace

**No se prueban veinte fórmulas para quedarse con la que peor deje a `B4`.** La familia es de
tres, está escrita aquí, y **la comparación de registro es `B4 − S3`**. `S1` y `S2` acompañan.

---

## 3 · REGLAS DE INFORMACIÓN

El benchmark puede usar: número de bandas, límites, anchura, posición, simetría, huecos,
cobertura, centro y la estructura completa — **más el histórico de resultados disponible en
`t_asof`**, con la misma regla walk-forward que todo lo demás.

**No puede usar**: pronóstico meteorológico, observación futura, ganadora del test, settlement,
precio, order book, nada posterior al cierre, ni parámetros ajustados con el test.

---

## 4 · UNA TENSIÓN QUE HAY QUE DECLARAR ANTES, NO DESPUÉS

`S3` no usa el pronóstico, **pero la escalera sí embebe el pronóstico DEL MERCADO**: el mercado
eligió `L` y `U` mirando su propia previsión. Por tanto:

> **`B4 − S3` no mide «poder predictivo contra ruido». Mide «qué añade nuestro pronóstico sobre
> lo que la geometría del contrato ya implica».** Es un listón **más alto** que el de Level 1 y
> roza la frontera con L2 — con la diferencia esencial de que **no mira precios**.

Se declara ahora para que el resultado no se pueda reinterpretar después: si `B4` sobrevive a
`S3`, la afirmación defendible es *«nuestro pronóstico añade sobre la información estructural
del contrato»*, **no** *«hay mispricing»*.

---

## 5 · MÉTRICA, INFERENCIA Y CRITERIO

Unidad **EVENTO**; escalera **11**; leads **24 y 9 por separado, los dos**; `epsilon = 1e-6`;
bootstrap clusterizado por evento, **10 000**, semilla **20260913**. Brier por evento como
métrica primaria; Log Loss sólo donde es interpretable.

    CASO A   B4 pierde frente a S3        -> Londres = NO-GO, senal explicada por la estructura
    CASO B   B4 conserva ventaja material -> Londres sigue siendo CANDIDATO (pendiente de B y C)
    CASO C   ambiguo                       -> INCONCLUSIVE

**No se busca otra transformación para salvar el caso A.** Y ni siquiera el caso B abre L2:
faltan availability (fase B) y réplica ex-ante (fase C).

---

## 6 · RED-TEAM DECLARADO DE LA FASE A

1. **¿`S3` se come señal meteorológica legítima?** Se mide cuánta información sobre la
   observación lleva la escalera **por sí sola** y se compara con la del pronóstico.
2. **¿`S3` está bien construido?** Suma 1, ex-ante, sin fuga: prueba ejecutable de alterar el
   futuro, igual que en L1.2.
3. **¿Depende del mínimo de entrenamiento?** Se reportan 20/30/40/50.
4. **¿La ventaja restante vive en unos pocos eventos?** Análisis de influencia, igual que L1.5.
