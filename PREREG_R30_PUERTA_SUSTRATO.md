# PREREG R30 — La puerta de sustrato: qué tendría que cumplir una hipótesis candidata

**Sesión B. Redactado 2026-09-11, ANTES de mirar ningún dato de libro con intención
evaluativa.** Se congela y se hashea antes de calcular nada, según D0.

**Esto NO es el preregistro de una estrategia.** Es la puerta que cualquier candidata tiene que
pasar para que merezca la pena escribirle un preregistro propio. Existe porque el ROADMAP §8 deja
el paso 2 —*«decidir si existe una hipótesis con sustrato»*— sin criterio, y sin criterio ese paso
se resuelve por intuición después de mirar.

---

## §1. Lo que R21 y R22 DEJAN DESCARTADO, y no se vuelve a intentar

**1.1 — Toda regla cuya señal sea la discrepancia `|p_model − p_mid|`.** R21: mediana −0,0236 sobre
468 operaciones, **37 de 37 fechas con mediana negativa** (signo p = 7,3e-12), IC bootstrap por
bloques [−0,0288, −0,0205]. La causa **no es el umbral**: recalibrar τ no la toca, porque el fallo
es que la regla opera justo donde el modelo más se aparta del mercado y **el mercado es el mejor
calibrado de los dos** (Brier: modelo 0,05191, mercado 0,04215, base 0,06801).

**1.2 — Todo argumento que descanse en el BSS AGREGADO.** El BSS del modelo es **+0,238 sobre la
muestra entera** y **negativo dentro de cada intervalo de precio**: −0,547 · −0,117 · −0,023 ·
−0,091 · −0,234. El agregado es paradoja de Simpson, no habilidad. **Un número global favorable ya
no se acepta como evidencia en este proyecto.**

**1.3 — Y el descarte es más fuerte de lo que parece por dónde está la masa:** el intervalo
`precio_bin_0.1=0` concentra el **79,2 % de las filas** y el **98,6 % de los eventos**, y es donde
el modelo es PEOR (−0,547). No es una cola: es el cuerpo de la muestra.

## §2. La restricción dura que hereda cualquier candidata

> **Tiene que demostrar información CONDICIONADA AL PRECIO.**

Concretamente: **BSS positivo dentro de los intervalos de precio**, con el intervalo `0` incluido y
no exceptuado. Una candidata que sólo mejore en agregado se declara **refutada sin más análisis**,
porque es exactamente el patrón que §1.2 ya midió como espurio.

## §3. El único sustrato que R21 y R22 NO pudieron usar

**El libro.** R21 **tuvo que suponerlo** (`x_exec` = 0,01, el escalón más adverso de D19) y R22 **no
pudo medirlo en absoluto**. Desde 2026-09-09 hay instantáneas L2 reales.

**Conocimiento previo que declaro aquí para que no cuente como hallazgo después:** ya he medido el
semidiferencial real en **0,0168**, frente al 0,0100 que supuso R21 — **un 68 % más caro**. Eso
**refuerza** el veredicto de R21 y, para R30, significa que **cualquier candidata parte de un coste
mayor del que R21 ya no pudo superar**. Lo digo ahora porque descubrirlo «después» sería presentar
como resultado algo que ya sabía.

## §4. Puerta de tamaño, fijada ANTES de tener los datos

Hoy hay **3 días** de libro. Ninguna evaluación se ejecuta antes de cumplir **las tres**:

- **§4.1** — **≥ 60 días naturales** de cobertura de libro con ≥ 8 de las 10 ranuras diarias
  entregadas. *Razón:* R21 necesitó 37 fechas para que el signo fuera concluyente; una hipótesis de
  microestructura se evalúa por evento y necesita al menos ese orden con estratificación por precio.
- **§4.2** — **≥ 150 eventos** con al menos una banda en cada uno de los intervalos de precio
  1 a 4. *Razón:* el intervalo `0` domina la masa; sin los otros cuatro poblados, §2 no es
  contrastable y la evaluación mediría otra vez el agregado.
- **§4.3** — **≥ 100 eventos liquidados** con etiqueta final. Sin esto no hay Brier que calcular.

**Si a los 120 días naturales no se cumplen las tres, R30 se declara NO EVALUABLE POR SUSTRATO** y
se publica como tal. Declararlo de antemano es lo que impide que «esperamos un poco más» se
convierta en la conclusión.

## §5. Criterios de aceptación, falsables

Una candidata **PASA la puerta** sólo si cumple **todas**:

- **§5.1** — BSS > 0 **en cada uno de los cinco intervalos de precio**, con IC bootstrap por
  bloques **sobre eventos** (los bloques son eventos, no filas: las bandas de un evento son una
  partición que suma 1) cuyo límite inferior sea > 0 en **al menos tres** de los cinco.
- **§5.2** — Mediana de PnL neto > 0 **con el coste medido**, no supuesto: semidiferencial
  observado en el libro del instante de decisión, más las fees de D19.
- **§5.3** — Robustez: el signo se mantiene **dejando fuera la estación de mayor peso** y
  **dejando fuera el mes de mayor peso** — los dos criterios que R21 falló.
- **§5.4** — El estadístico del contraste es el **MÁXIMO** sobre la familia de estratos declarados,
  con permutación pareada por evento completo. Nada de elegir el estrato ganador después.

**Cualquier fallo de §5.1 a §5.4 es una REFUTACIÓN y se publica como tal.**

## §6. Resultados negativos declarados de antemano

Se publican con el mismo rango que uno positivo:

- **§6.1** — «El libro no contiene información condicionada al precio a estos plazos.»
- **§6.2** — «La contiene, pero el coste medido se la come» — que es el resultado que el 0,0168 de
  §3 hace **a priori el más probable**, y lo escribo antes para no poder presentarlo luego como
  sorpresa.
- **§6.3** — «No evaluable por sustrato» (§4).

## §7. Lo que este documento NO afirma

- No afirma que exista una candidata. Afirma qué tendría que cumplir.
- No afirma que M2 sea mejorable: su limitación sigue siendo la de `M2_PREREG_CHAIN.md` — la
  probabilidad para **un mercado concreto** está peor calibrada que la agregada y **no es corregible
  con este sustrato** (correlación del sesgo por estación entre mitades del periodo: **+0,080**).
- No autoriza operar con dinero real. El gate D0 sigue entero: sin wallet, sin firma, sin ruta de
  orden.

## §8. Prohibiciones vigentes

Las de **PREREG_M2_ERROR v1 §10**, citadas con su documento porque v2 las referencia como «§10» sin
cualificar y v2 no tiene §10 (B-24). Y las de D0, íntegras.
