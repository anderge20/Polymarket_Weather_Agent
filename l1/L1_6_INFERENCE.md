# LEVEL 1 · L1.6 — INFERENCE

`LOCK_L1_6.md` espejado a las **20:57:37Z** (`9586f5e`) **antes** de ejecutar, con los **siete
placebos declarados de antemano**. Integridad de los seis ficheros de lock verificada por
`sha256` **dentro del propio guion** antes de calcular nada. No se buscan precios, EV, PnL,
umbrales, estrategias ni ciudades; producción sin tocar; `D0-P` = BLOCKED. **No se emite el
veredicto de Level 1**: eso es L1.8.

---

## 1 · RESULTADO PRIMARIO, reproducido

| | lead 24 (95 clusters) | lead 9 (96 clusters) |
|---|---|---|
| `B4 − B0` *(pre-registrado)* | −0,03041 [−0,03726, −0,02336] | −0,03585 [−0,04260, −0,02878] |
| `B4 − uniforme` *(control ex-post)* | −0,01151 [−0,01577, −0,00706] | −0,01731 [−0,02132, −0,01296] |

---

## 2 · PLACEBO A — desalineamiento temporal · **6 desplazamientos declarados, los 6 ejecutados**

    lead 24                                    lead 9
      k    n   B4-uniforme        veredicto      k    n   B4-uniforme
     -7   74     +0,04106            peor       -7   75     +0,04632
     -3   76     +0,02607            peor       -3   77     +0,02952
     -1   81     +0,01265            peor       -1   82     +0,01664
     +1   82     +0,00819            peor       +1   83     +0,01084
     +3   79     +0,02910            peor       +3   80     +0,03092
     +7   81     +0,04106            peor       +7   82     +0,04143

**Los doce van al otro lado, y de forma monótona en `|k|`.** Un día de desfase basta para
perder toda la ventaja; siete días la convierten en un perjuicio cuatro veces mayor que la
ventaja original.

> **Mi expectativa escrita era «el IC debería contener el cero». El resultado es MÁS fuerte que
> eso y hay que decirlo, no presentarlo como si fuera lo predicho:** un pronóstico desalineado
> no es ruido, es una distribución **confiada y centrada en el día equivocado**, así que puntúa
> peor que no saber nada. La monotonía en `|k|` —+0,008 a un día, +0,041 a siete— es la firma
> de una señal que se degrada con la distancia temporal, y es difícil de fabricar con un
> artefacto de estructura.

## 3 · PLACEBO B — 1 000 permutaciones de la ganadora dentro del evento

    lead 24   observado -0,01151   nulo: media +0,01342  [+0,00916, +0,01741]   0/1000  p = 0,0010
    lead  9   observado -0,01731   nulo: media +0,01654  [+0,01162, +0,02085]   0/1000  p = 0,0010

`p = 0,0010` es **el suelo** de 1 000 permutaciones: ninguna alcanzó el valor observado.

**Y el nulo permutado es POSITIVO, no cero — eso es correcto y conviene explicarlo:** contra una
ganadora aleatoria, una distribución concentrada puntúa **peor** que la uniforme, porque la
uniforme es óptima cuando el objetivo no tiene estructura. *Un nulo permutado centrado en cero
habría sido la señal de que algo estaba mal.*

## 4 · TEST TEMPORAL — **y aquí está el hallazgo incómodo**

| | 1ª mitad | 2ª mitad | diferencia 1ª−2ª |
|---|---|---|---|
| **lead 24** | −0,00618 **[−0,01265, +0,00006]** | −0,01674 [−0,02238, −0,01100] | **+0,01056 [+0,00231, +0,01914] → INESTABLE** |
| **lead 9** | −0,01473 [−0,02078, −0,00816] | −0,01988 [−0,02508, −0,01454] | +0,00515 [−0,00307, +0,01373] → **estable** |

> **En el lead 24 la ventaja NO es estable entre mitades: el IC de la diferencia excluye el
> cero, y el IC de la primera mitad toca el cero (+0,00006).** En el lead 9 sí lo es.

**¿Heterogeneidad o falta de potencia?** Las dos cosas se separan y se miden:

    lead 24  1a mitad  n=47  efecto -0,00618  MDE 0,00885   POR DEBAJO DEL MDE -> infrapotenciada
             2a mitad  n=48  efecto -0,01674  MDE 0,00830   detectable
    lead  9  1a mitad  n=48  efecto -0,01473  MDE 0,00885   detectable
             2a mitad  n=48  efecto -0,01988  MDE 0,00777   detectable

La primera mitad del lead 24 está **infrapotenciada** por sí sola — pero **el test de
heterogeneidad no depende de eso**: compara las dos mitades directamente y su IC excluye el
cero. **La heterogeneidad del lead 24 es un hallazgo, no un artefacto de potencia.**

**No se busca otro corte.** El corte 2026-06-23 estaba pre-registrado en `LOCK_L1_4`.

## 5 · POTENCIA

    lead 24   n=95  sd 0,02176   MDE(80 %, alfa 0,05) 0,00625   observado 0,01151   razon 1,84
    lead  9   n=96  sd 0,02077   MDE               0,00593   observado 0,01731   razon 2,92

El efecto está por encima del mínimo detectable en los dos leads, con más holgura en el 9.

## 6 · LOS DOS LEADS NO SON DOS MUESTRAS

    eventos con los dos leads: 95    correlacion de Pearson del delta por evento: r = +0,595
    tamano efectivo ~ 2n/(1+r) = 119   (contra 190 si fueran independientes)

**Presentar «191 observaciones `evento × lead`» sobrestimaría la información en un ~60 %.** La
inferencia se hace por lead y nunca se agregan.

---

## 7 · GATE

| condición del lock | resultado |
|---|---|
| ningún placebo sobrevive | **cumplido** — los 12 desplazamientos van al otro lado; permutación `p = 0,0010` en los dos leads |
| IC95 primario reproducible | **cumplido** — idéntico a L1.4 |
| potencia cuantificada | **cumplido** — MDE y razón por lead y por mitad |
| ningún defecto metodológico | **ninguno encontrado** |

# `L1.6 = CLOSED`

**Con una limitación que va pegada al cierre y no se separa de él: en el lead 24 la ventaja es
heterogénea entre mitades, con el IC de la diferencia excluyendo el cero.** El criterio **C —
STRONG PREDICTIVE POWER** del preregistro exige *«consistente en varios periodos»*: **el lead 24
no lo cumple**. El lead 9 sí.

**Lo que sigue sin decirse, y no se dirá hasta L1.8:** ni «hay edge» ni «no hay edge». Y todo
sigue condicionado a la validación externa de `available_at` (tarea #75), a que el test **no
cubre abril**, y a que esto es **una ciudad, una estación, cuatro meses**.

Siguiente: **`L1.7` — FINAL RED TEAM**.
