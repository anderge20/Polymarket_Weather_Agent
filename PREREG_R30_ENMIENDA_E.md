# PREREG R30 — ENMIENDA E: mi «semidiferencial medido» era de n=27, y una regla de selección rota que NO rescata la Estrategia A

**Sesión B, 2026-09-11.** Quinta enmienda a `PREREG_R30_PUERTA_SUSTRATO.md`. Índice y shas en
`R30_PREREG_CHAIN.md`. Sigue sin calcularse nada contra R30.

**Dos disparadores externos:** la sesión A midió el spread sobre la rama `paper-state` y no coincidía
con mi número; y el **PR #28**, de una sesión en la nube que ninguno de los dos coordinó, encontró un
defecto en `backtest.py:306`, que es código mío.

---

## DEFECTO 1 — §3 declaraba como conocimiento previo un número de n=27 sin decir su población

§3 decía:

> ya he medido el semidiferencial real en **0,0168**, frente al 0,0100 que supuso R21 — **un 68 % más
> caro**.

**Ese 0,0168 sale de un spread medio de 0,0336 medido sobre los 27 tokens de UN ciclo** (B-«×2,8»,
medición de A). Medido ahora sobre **25.736 libros de dos lados**, tres días, diez ranuras diarias:

```
spread COMPLETO      media 0,0193   mediana 0,0100   p25 0,0080   p75 0,0200   p90 0,0400
SEMIdiferencial      media 0,0096   mediana 0,0050   p25 0,0040   p75 0,0100   p90 0,0200
```

**La media del semidiferencial poblacional es 0,0096 — prácticamente idéntica al `x_exec` = 0,0100
de R21.** Presentado sobre la población, el supuesto de R21 no era optimista: era exacto.

### Pero la dirección sobrevive, y la medí en vez de suponerla

¿Es el 0,0336 un artefacto de n=27? Bootstrap de 27 extracciones sobre los 25.736 spreads, 20.000
remuestreos:

```
media de 27 extracciones:  p50 0,0177   p75 0,0211   p90 0,0270   p95 0,0303   p99 0,0402
P(media de 27 >= 0,0336) = 0,026
```

**p = 0,026: el subconjunto OPERADO es genuinamente más caro que la población.** No es sólo ruido de
muestra pequeña.

### §3 enmendado

> **§3 (enmendado E)** — Conocimiento previo declarado, **con su población en cada cifra**:
>
> - **Población completa** (25.736 libros de dos lados, 2026-09-09..11): semidiferencial **media
>   0,0096**, mediana 0,0050. Es decir, el `x_exec = 0,0100` de R21 **es acertado en media sobre la
>   población**, no optimista.
> - **Subconjunto operado** (n = 27, un ciclo): semidiferencial **0,0168**. Más caro que la
>   población con **p = 0,026** en bootstrap — dirección sostenida, **magnitud NO establecida**.
> - **Lo que se afirma:** la regla opera donde el modelo más se aparta del mercado, y esas bandas
>   tienden a ser menos líquidas; por tanto **el coste que importa es el del subconjunto operado y es
>   mayor que el poblacional**. Ese argumento es **estructural** y no depende de n=27.
> - **Lo que NO se afirma:** ninguna cifra concreta para el subconjunto operado. **0,0168 queda
>   retirado como número de referencia** y sólo se cita con su n y su p.

**Y la lección, porque es la cuarta vez hoy:** *«el semidiferencial real medido es 0,0168»* era una
magnitud sin su población, presentada como un hecho del mundo. Es la misma forma que el desfase de
+0,52 min, el 590/591 y las dos cuentas de filas del almacén: **dos contabilidades haciéndose pasar
por una.**

## DEFECTO 2 — §6.2 apoyaba su estatus en ese número

§6.2 declaraba «lo contiene pero el coste se lo come» como desenlace **a priori el más probable**,
*«por el semidiferencial medido de 0,0168»*.

> **§6.2 (enmendado E)** — Sigue siendo un resultado negativo **declarado de antemano**, y sigue
> siendo el que considero más probable, **pero apoyado en el argumento ESTRUCTURAL de §3** —la regla
> selecciona bandas menos líquidas— **y no en ninguna cifra**. La cifra que lo sostenía era de n=27.

## DEFECTO 3 — el PR #28 encuentra que mi regla de selección de τ ordena por precio del billete

`backtest.py:306`, código mío, congelado por el §3 de R21:

```python
m = median(pnls)          # select_tau maximiza la MEDIANA
```

**Con tasa de acierto por debajo del 50 % —y R21 midió mediana −0,0236, luego lo está— la mediana es
SIEMPRE el PnL de un perdedor.** Para una apuesta binaria, el PnL de un perdedor es esencialmente
**menos el precio del billete**. Así que maximizar la mediana **ordena por precio del billete y no
por valor esperado**: elige τ barato. El #28 lo demuestra eligiendo τ=0,04 sobre τ=0,15 pese a que la
segunda gana 5× más por operación en esperanza.

**Lo acepto entero. Es un defecto de diseño mío.**

### Y §1.1 de R30 SOBREVIVE — pero hay que decir por qué, o se leerá al revés

La lectura tentadora es: *«la regla de selección estaba rota, luego el veredicto NO OPERABLE de R21
es sobre un τ mal elegido y quizá otro τ funcione»*. **No, y la razón es que la evidencia de §1.1 es
independiente de τ:**

- `p_model` está bien calibrado (1,0–1,4×) **sobre los 10.000 candidatos**, no sobre los operados.
- Brier: modelo 0,05191, mercado 0,04215, base 0,06801 — **sobre todos los candidatos**.
- BSS del modelo **negativo dentro de cada intervalo de precio** (−0,547, −0,117, −0,023, −0,091,
  −0,234) — **calculado sin usar τ en ningún punto**.

**Ningún τ cambia que, condicionado al precio, el modelo no aporte información.** §1.1 se mantiene
**y se mantiene sobre esa evidencia, no sobre el resultado del barrido de τ.** Queda escrito aquí
para que el hallazgo del #28 no se lea como una puerta reabierta.

**Lo que sí cambia:** R21 §3 congeló una regla de selección **mal diseñada**, y eso hay que
registrarlo en el informe de R21 como defecto conocido — no para revocar el veredicto, sino porque
**una regla congelada mala sigue siendo mala aunque el veredicto no dependa de ella**, y la próxima
que se congele no debe copiarla. **Ninguna estrategia futura selecciona umbral maximizando una
mediana mientras la tasa de acierto esté por debajo del 50 %.**

## Lo que NO cambia

§0, §1 (salvo la nota de §1.1 arriba), §2, §4, §5, §7, §8.

> **ADVERTENCIA, la misma de D:** «no cambia» significa «esta enmienda no lo toca», **nunca «ya está
> revisado»**.
