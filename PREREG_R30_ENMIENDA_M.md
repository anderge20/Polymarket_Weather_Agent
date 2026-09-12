# PREREG R30 — ENMIENDA M: L arregló la unidad de la nula y relajó la de la potencia

**Sesión B.** Decimotercera enmienda a `PREREG_R30_PUERTA_SUSTRATO.md`
(sha `0a5b794e656390b13e33f14a40260f7a7818b13928f45db7d1a5312deb0caaaf`). Corrige la **L**
(`b23053f75e299a9702a1f5229ba2352b25a23964dd8d4c154c1558496f2a2b7b`), escrita hace minutos por mí.

---

## El defecto, y es permisivo

L estableció —correctamente y con medición— que la partición de la nula es **(evento, lead)** y no el
evento. Y acto seguido escribió:

> «**§5.5(e) y la regla de ocupación de §5.4 se recalculan sobre esta población**, contando grupos
> (evento, lead) y no eventos. El bootstrap por bloques de §5.5(b) usa el mismo bloque.»

**Esa segunda frase no se sigue de la primera, y afloja el listón justo donde decide el veredicto.**
Los dos plazos del mismo evento son la misma estación, el mismo día y el mismo tiempo atmosférico:
**no son dos unidades independientes.** Contarlos como dos duplica la `n` sin añadir información, y
§4.2 congeló «≥ 150 **eventos**».

El efecto es exactamente el que cabe temer de una relajación:

    contando EVENTOS (§4.2 congelado)        familia = [0, 1, 2]
    contando GRUPOS (evento, lead) (L)       familia = [0, 1, 2, 3, 4]

**Los intervalos 3 y 4 pasan de NO EVALUABLES a evaluables por un cambio de unidad que yo introduje
quince minutos antes, en la enmienda cuyo objeto era corregir un error de unidad.** Es la regla que A
escribió y que la cadena lleva citando desde la D —*una enmienda es un cambio de código con otro
nombre y puede introducir la clase de defecto que viene a corregir*— cumplida sobre sí misma.

## Y los dos papeles son distintos, que es lo que L confundió

| papel | unidad correcta | por qué |
|---|---|---|
| partición de la nula §5.5(c) | **(evento, lead)** | ahí vive la restricción «un solo ganador»: medido, 2 571 de 2 571 grupos tienen como mucho uno |
| bloque del bootstrap §5.5(b) | **evento** | el bloque debe contener TODA la dependencia, no sólo la de la partición: los dos plazos del mismo evento están correlacionados |
| potencia §5.5(e) y ocupación §5.4 | **evento** | §4.2 lo congeló en eventos, y la `n` efectiva es la del bloque |

*Un grupo de partición no es una unidad independiente, y L usó la palabra «bloque» para las dos cosas.*

## §5.5 enmendado por M

> **§5.5(c) (vigente, de L)** — la partición de la nula es **(evento, lead)**. **No se toca.**
>
> **§5.5(b) (enmendado M)** — el bloque del bootstrap es el **EVENTO**, con sus dos plazos dentro.
> Donde L dice «usa el mismo bloque», se lee esto.
>
> **§5.5(e) y §5.4, regla de ocupación (enmendado M)** — se cuentan **EVENTOS**, como §4.2 (A+B)
> fijó. Donde L dice «contando grupos (evento, lead) y no eventos», se lee lo contrario.
>
> **§5.5(f) (vigente, de L)** — el ámbito por suma de `p_mid` ≥ 0,50 **no se toca**: es una regla
> sobre qué grupos son partición, y eso sí es propiedad del grupo.

## Lo que NO cambia

§0–§4, §5.1–§5.4 salvo la regla de ocupación, §5.5(a)(c)(d)(f), §6, §7, §8 y todo lo vigente de A–L.

> **ADVERTENCIA, la de D a L:** «no cambia» significa «esta enmienda no lo toca», **nunca «ya está
> revisado»**.

## Nota de método

**L declaró honestamente que se escribía después de ver los datos y aun así metió el defecto por el
otro lado.** La declaración de contaminación no protege de nada por sí sola: lo que detectó esto fue
imprimir la familia bajo las dos unidades y ver que una de ellas ascendía dos intervalos.

**Y el resultado de fondo no se mueve:** con la unidad congelada, la familia sigue siendo `[0, 1, 2]`,
que es lo que ya se sabía antes de L. Lo que L aporta es la nula ejecutable; lo que M impide es que
L, de paso, regale dos intervalos.
