# PREREG R30 — ENMIENDA I: lo que la H implicaba y no decía, un criterio mío que era falso, y el umbral del contraste ANTES de calcularlo

**Sesión B, 2026-09-11.** Novena enmienda a `PREREG_R30_PUERTA_SUSTRATO.md`. Índice y shas en
`R30_PREREG_CHAIN.md`. **Sigue sin calcularse la curva de fiabilidad del mercado.**

Las tres correcciones vienen de la sesión A atacando la H a petición mía.

---

## 1. LO QUE LA H IMPLICABA Y NO DECÍA, y es más grande que la H

La H establece que **nadie ha medido la calibración del MERCADO**. De ahí se sigue algo que no escribí:

> **La explicación que R21 da de por qué falló la Estrategia A descansa sobre una premisa no medida.**

R21 línea 108: *«La regla opera donde `p_model` más se separa de `p_mid`. **Si el mercado está mejor
calibrado**, el lugar donde más discrepan es donde el modelo se equivoca»*. **Eso es una hipótesis
enunciada como explicación.** El Brier del mercado (0,04215 contra 0,06801 de base) mide
**resolución**, no **fiabilidad**.

**Así que la vía superviviente no es sólo una candidata nueva: es el test de la premisa explicativa que
el proyecto da por buena desde R21.** Los dos desenlaces, declarados ahora:

- **Si el mercado SÍ está bien calibrado:** confirma la explicación de R21 **y mata la vía**. El
  veredicto NO OPERABLE de R21 se queda intacto y además queda explicado por la razón que decía.
- **Si NO lo está en algún régimen:** la vía vive, **y R21 acertó en el resultado por una razón que no
  era la que dio**. El veredicto no cambia —lo sostienen §1.1 y la descomposición por intervalo, que no
  usan esta premisa— pero su **explicación** sí.

**Ninguno de los dos desenlaces es un fracaso, y los dos se publican.**

## 2. UN CRITERIO MÍO QUE ERA FALSO, retirado

La H dice: *«la obligación que impone a cambio es más dura que la puerta que levanta»*. **Es falso, y
por mi propio test.** Escribir la declaración cuesta **una tarde**; la puerta costaba **sesenta días**.

**Pero el criterio equivocado era el mío, no la enmienda.** El propósito de una puerta **no es costar:
es filtrar**. Sustituido:

> **No preguntes «¿es más cara?». Pregunta «¿filtra lo que la puerta filtraba?».**
>
> La puerta de 60 días filtraba *«no tienes sustrato»*. La declaración escrita, sometida a revisión
> adversarial, filtra *«tu pregunta ya está respondida»* — que es **el riesgo real cuando el sustrato
> es compartido**. **Sesenta días de espera no filtran nada de eso: el tiempo no distingue una
> hipótesis nueva de una reciclada.**

## 3. EL UMBRAL DEL CONTRASTE, fijado antes de calcular la curva

Sin esto, quien ejecute mira la curva y **después** decide qué cuenta como sesgo. Se fija aquí.

> **§5.5 (nuevo)** — Contraste de calibración del mercado.
>
> **(a) Estadístico.** Por cada `precio_bin` del §0: `d_b = f_b − media(p_mid)_b`, donde `f_b` es la
> frecuencia realizada del desenlace en ese intervalo. **Unidad de análisis: el EVENTO** (§5.2
> enmienda D).
>
> **(b) Incertidumbre.** IC bootstrap **por bloques sobre eventos**, idéntico a §5.1.
>
> **(c) El mercado está MAL CALIBRADO** si el IC de `d_b` **excluye el 0** en **al menos un intervalo
> de la familia** de §5.4 (enmienda C), **y** el signo de `d_b` en ese intervalo **sobrevive los dos
> borrados de §5.3** — fuera la estación de mayor peso, fuera el mes de mayor peso.
>
> **(d) Y MAL CALIBRADO NO ES EXPLOTABLE.** Para que la vía pase hace falta además
> **`|d_b| > semidiferencial mediano del intervalo b` + fees de D19**, con el semidiferencial **medido**
> de la tabla de la Enmienda F —0,0100 en la zona de duda, 0,0050 en los extremos—. **Un sesgo real
> menor que el coste de tocarlo es §6.2**, y se publica como tal.
>
> **(e) Potencia.** §4.2 (enmiendas A y B) aplica: **≥150 eventos por intervalo 1–4 sobre la población
> post-borrado**. Un intervalo que no lo cumpla **se reporta como NO EVALUABLE POR POTENCIA, con su n
> a la vista** — nunca se descarta en silencio ni se agrega con otro. Es previsible que el intervalo 4
> lo incumpla en la muestra retrospectiva: R22 le daba 188 eventos **antes** de borrar el mes mayor.

## Lo que NO cambia

§0, §1, §2, §3, §4, §5.1–§5.4, §6, §7, §8, y todo lo vigente de A–H salvo lo corregido en el punto 2.

> **ADVERTENCIA, la de D a H:** «no cambia» significa «esta enmienda no lo toca», **nunca «ya está
> revisado»**.

## Nota de método

La H **abría** una vía y yo mismo señalé que eso invierte el incentivo. **A atacó los dos puntos que
pedí que atacara y los dos cedieron**: uno era una afirmación falsa y el otro un hueco que habría
dejado el criterio de decisión para después del dato. **Pedir que ataquen no sirve si no se corrige lo
que encuentran** — y el que encontró el hueco es quien no ganaba nada con él.
