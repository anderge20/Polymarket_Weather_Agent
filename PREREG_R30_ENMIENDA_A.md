# PREREG R30 — ENMIENDA A: §4.2 exigía una conjunción cuya viabilidad nunca medí

**Sesión B, 2026-09-11.** Enmienda a `PREREG_R30_PUERTA_SUSTRATO.md`
(sha `0a5b794e656390b13e33f14a40260f7a7818b13928f45db7d1a5312deb0caaaf`).

**No se edita el documento congelado.** Se enmienda desde fuera, con hash propio y puntero hacia
adelante, que es la regla que este proyecto sacó de `M2_PREREG_CHAIN.md`: editar un congelado rompe
su sha y con él la prueba de que se congeló antes de calcular nada.

**Nada se ha calculado contra R30.** Se congeló y se enmienda dentro de la misma jornada, antes de
tocar dato alguno, así que la enmienda no puede estar informada por ningún resultado.

---

## Lo que decía §4.2

> **≥ 150 eventos** con al menos una banda en cada uno de los intervalos de precio 1 a 4.

## Por qué está mal

**Exige que CADA EVENTO abarque los cuatro intervalos simultáneamente**, y esa conjunción **nunca la
medí**. Lo que R22 da son marginales por evento, no la conjunta:

```
precio_bin_0.1=1    301 eventos   23,0 %
precio_bin_0.1=2    267           20,4 %
precio_bin_0.1=3    249           19,0 %
precio_bin_0.1=4    188           14,4 %     <- cota superior de la conjunción
```

La conjunción está **acotada por arriba en 188 de 1.308 eventos (14,4 %)**, y eso sólo si los
eventos del intervalo 4 fueran un subconjunto de los otros tres. Si fueran independientes serían
**~1,7 eventos**. La cifra real está en algún punto de ese rango y **no la conozco**.

**El defecto no es que el listón sea alto: es que no sé si es alcanzable.** Un criterio que sólo
puede fallar no es un criterio, es una conclusión escrita de antemano — y llevaría a R30 a
declararse «NO EVALUABLE POR SUSTRATO» (§6.3) **por construcción**, dando a ese resultado la
apariencia de un hallazgo empírico.

**Y es la forma que esta semana ya me costó tres correcciones:** afirmar sobre una magnitud sin
medirla, cuando medirla era barato. Aquí ni siquiera podía medirla — la conjunta no está en ningún
artefacto publicado — que es precisamente por qué no debí escribirla como umbral.

## Lo que dice ahora §4.2

> **§4.2 (enmendado)** — **≥ 150 eventos en CADA UNO** de los intervalos de precio 1 a 4. El
> requisito es sobre la población de cada intervalo, no sobre que un evento los abarque todos.

## Por qué esta forma sí sirve al propósito

El propósito declarado de §4.2 era que **§2 fuese contrastable**: §2 exige BSS positivo **dentro de
los intervalos de precio**, y eso necesita **eventos suficientes EN cada intervalo**, no eventos que
crucen todos. La conjunción no aportaba nada al contraste; era una exigencia que se me coló por
escribir «en cada uno» pensando en la población y leyéndose como «por evento».

**Y es alcanzable, con la aritmética a la vista:** el intervalo más raro aparece en el **14,4 %** de
los eventos, así que 150 eventos en él requieren **~1.042 eventos** en total. A las ~51 fechas-evento
por día que la serie de cobertura viene midiendo, son **~20 días** — holgadamente dentro de la puerta
de 60 días de §4.1, que por tanto sigue siendo la restrictiva.

## Lo que NO cambia

- §1, §2, §3, §4.1, §4.3, §5, §6, §7 y §8 de R30 quedan **exactamente como están**.
- En particular sigue en pie §6.3 «NO EVALUABLE POR SUSTRATO» y el corte de 120 días — pero ahora
  es un resultado que el sustrato puede **evitar**, en vez de uno garantizado por la redacción.
- Y sigue en pie §3: el semidiferencial medido (**0,0168** frente al 0,0100 supuesto por R21) hace
  de §6.2 el desenlace *a priori* más probable.
