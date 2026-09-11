# PREREG R30 — ENMIENDA K: §5.5(c) tomaba prestada la familia de §5.4 y dejaba fuera su corrección

**Sesión B, 2026-09-11, ~20:10Z.** Undécima enmienda a `PREREG_R30_PUERTA_SUSTRATO.md`. Índice y shas
en `R30_PREREG_CHAIN.md`.

**ESTADO EN EL MOMENTO DE ESCRIBIRLA, y es lo que la hace preinscripción:** hay un proceso construyendo
el **sustrato** (`p_mid`, desenlace, evento, estación, fecha) y **no se ha calculado ninguna `d_b`, ni
ninguna curva, ni ningún conteo de potencia.** El criterio se cambia **antes** de que exista un número
al que ajustarlo. Defecto encontrado por la sesión A.

---

## El defecto, y es permisivo

§5.5(c) decía: *«mal calibrado si el IC de `d_b` **excluye el 0** en **al menos un intervalo de la
familia de §5.4**»*. **Cita la familia de §5.4 y no usa su contraste.** §5.4 prescribe el **MÁXIMO
sobre la familia** precisamente para impedir elegir el estrato ganador después; §5.5(c) se llevó la
familia y dejó la corrección.

**Suelo de falso positivo bajo la nula, con IC al 95 % independientes:**

```
k= 4 intervalos   18,5 %
k= 5              22,6 %   <- el MINIMO garantizado por §4.2 + el bin 0
k= 6              26,5 %
k=10              40,1 %
```

**Con un 22,6 % de «mal calibrado» sobre un mercado perfectamente calibrado, un positivo no
distinguiría señal de familia** — y esto decide si la única vía superviviente se declara viva.

## §5.5(c) enmendado — el contraste pasa por §5.4, como debió desde el principio

> **§5.5(c) (enmendado K)** — **Estadístico: `T = max_b |d_b|`** sobre la familia de §5.4 (enmienda C),
> restringida a los intervalos **EVALUABLES** por §5.5(e).
>
> **Distribución nula, y aquí la permutación de §5.4 NO sirve tal cual.** Permutar desenlaces
> contrasta *«no hay asociación entre `p_mid` y el resultado»*, y **un mercado calibrado SÍ tiene
> asociación** — eso es resolución, no fiabilidad. La nula que toca es **«el mercado está
> calibrado»**, y se genera así:
>
> **Para cada EVENTO, se sortea UNA banda ganadora con probabilidades proporcionales a los `p_mid` de
> sus bandas.** Eso es exactamente «los precios son las probabilidades verdaderas» **y respeta por
> construcción que las bandas de un evento son una partición con un solo ganador** — la dependencia
> intra-evento que §5.1 nombra y que una Bernoulli por banda destruiría.
>
> **p-valor familiar:** `P(T_nula ≥ T_observado)` sobre **≥ 10 000 réplicas**. **Mal calibrado si
> p < 0,05.** Nivel declarado, familiar, y no depende de cuántos intervalos tenga la muestra.
>
> **§5.3 sigue siendo condición ADICIONAL, no alternativa:** el signo de `d_b` en el intervalo que
> alcanza el máximo debe sobrevivir los dos borrados. **Es robustez, no significación**, y nunca
> sustituye al p-valor.

## Por qué esta salida y no las otras dos

A ofreció tres. **Se elige enrutar por §5.4** porque **no introduce ningún número nuevo que justificar**
y porque es lo que §5.4 ya prescribe para toda la familia: §5.5(c) era **incoherente con el propio
documento**, no un criterio distinto defendible.

**Bonferroni** habría servido y es más conservador de lo necesario con estadísticos correlacionados
—los `d_b` de intervalos vecinos no son independientes—. **Cuantificar por simulación la reducción que
aporta §5.3** es lo más honesto de las tres y **es trabajo que no cambia la decisión**: con el máximo
y su permutación, §5.3 deja de cargar peso inferencial y pasa a ser lo que siempre debió ser, una
prueba de robustez.

## Lo que A declaró NO saber, y se recoge tal cual

A dijo que la segunda condición —sobrevivir los dos borrados— **reduce los falsos positivos pero no
sabe cuánto**, porque los borrados quitan subconjuntos **correlacionados** y por tanto no es (1/2)².
**No inventó el factor.** Con esta enmienda **deja de hacer falta**: el nivel lo fija el p-valor
familiar y §5.3 no tiene que aportar significación.

## Lo que NO cambia

§0–§4, §5.1–§5.4, §5.5(a)(b)(d)(e), §6, §7, §8 y lo vigente de A–J.

> **ADVERTENCIA, la de D a J:** «no cambia» significa «esta enmienda no lo toca», **nunca «ya está
> revisado»**.

## Nota de método

**Undécima enmienda, y la cuarta que A encuentra atacando un criterio que yo acababa de congelar.** Las
cuatro en dirección **permisiva**, que es la clase que no veo. Y ésta llega **con el sustrato
construyéndose**: media hora más tarde, cualquier cambio a §5.5(c) habría sido indistinguible de un
ajuste al resultado — **no porque lo fuera, sino porque nadie podría demostrar que no.**
