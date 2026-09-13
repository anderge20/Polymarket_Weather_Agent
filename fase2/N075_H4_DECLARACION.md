# H4 · PARTE A y C — UNIDADES, PONDERACIÓN Y REGLA DE VEREDICTO

**Espejado antes de calcular nada de la parte D/E.** Lo que va aquí es lo único que podría
elegirse para que el resultado salga favorable: la unidad primaria, el esquema de
ponderación y la regla que convierte números en veredicto. Por eso se fija primero.

## 0. Lo que YA he visto, dicho antes de declarar nada

No puedo afirmar que llego ciego, y fingirlo sería peor que el sesgo. **Ya he visto**, del
ciclo anterior (A-278):

* que la población puntuada es **100 % de once bandas** en los dos brazos;
* que `REF_uniforme` vale **0,082645 / 0,30464** en los cuatro cuadrantes de once bandas;
* que la línea base por escalera es **7 → 0,12245 · 9 → 0,09877 · 11 → 0,08264** de Brier, y
  **0,41012 · 0,34883 · 0,30464** de Log Loss;
* que el recorrido 7→11 (0,0398) es **cuatro veces** el mayor delta OLD↔CORRECTED (0,00991).

**Esos cuatro hechos son el motivo de esta tarea, no su resultado.** La declaración de
abajo no puede «elegirse» para favorecerlos porque ya apuntan todos en la misma dirección:
la línea base se mueve con la escalera. Lo que aún no he mirado, y lo que decide el
veredicto, es **si alguna unidad o ponderación lo neutraliza** y **si los datos permiten
distinguir escalera de calendario**.

---

## A. Las tres unidades, formalizadas

Notación: un evento `e` tiene `n_e` bandas, exactamente una ganadora. `q_{e,i}` es la
probabilidad asignada a la banda `i`; `y_{e,i} ∈ {0,1}` con `Σ_i y_{e,i} = 1`.

### A.1 CONTRATO

* **Definición.** La fila es `(event_id, lead, banda)`. Hay `n_e` filas por evento y lead.
  La puntuación es `s(q_{e,i}, y_{e,i})` con `s` = Brier o Log Loss binarios.
* **Peso.** Cada contrato pesa `1` en la media global. Un evento de `n` bandas aporta `n`
  filas, luego **pesa proporcionalmente a `n`**.
* **Ventaja.** Es la unidad en la que el contrato **se negocia y se liquida**: cada banda es
  un token con su propio libro. Si la pregunta es económica, ésta es la unidad real.
* **Inconveniente.** Las `n` filas de un evento **no son independientes**: son `n` contratos
  del mismo sorteo, con `Σ y = 1` impuesto. Tratarlas como observaciones sueltas infla `N`
  por un factor `n` y da más peso a las escaleras largas.
* **Qué hipótesis responde.** «¿Cuánto cuesta/vale cada contrato?» — no «¿acierta el
  modelo?».

### A.2 EVENTO

* **Definición.** La fila es `event_id`. La puntuación es la **media dentro del evento**,
  `(1/n_e) Σ_i s(q_{e,i}, y_{e,i})`, y luego la media sobre eventos.
* **Peso.** Cada evento pesa `1`, sea cual sea `n_e`.
* **Ventaja.** Un sorteo, una observación. Es la unidad estadísticamente honesta para contar
  `N`.
* **Inconveniente.** **La media dentro del evento sigue dependiendo de `n`** (se demuestra en
  B). Igualar el peso entre eventos **no** iguala la escala de lo que se promedia.
* **Qué hipótesis responde.** «¿Cuántos sorteos ha acertado el modelo?»

### A.3 EVENTO × LEAD

* **Definición.** La fila es `(event_id, lead)`. El mismo evento puntuado a 24 h y a 9 h son
  **dos** filas, nunca promediadas entre sí.
* **Peso.** Cada par pesa `1` **dentro de su lead**; los leads se reportan **siempre por
  separado** y no se agregan.
* **Ventaja.** El lead cambia la información disponible en `t_asof`. Mezclar leads mezcla dos
  problemas de predicción distintos bajo un mismo número.
* **Inconveniente.** Duplica la superficie de reporte y no arregla nada de la escalera.
* **Qué hipótesis responde.** «¿Cuánto acierta el modelo **con la información que tenía a esa
  hora**?»

### A.4 UNIDAD PRIMARIA — DECLARADA

> **La unidad primaria es `evento × lead`**, con los dos leads reportados por separado y
> nunca agregados entre sí.

**No es una elección nueva:** está en el docstring de `n1_14_baselines.py` desde antes de que
existiera cualquiera de estos números —*«Unidad (target_date, lead). Brier por banda,
promediado DENTRO del evento y luego sobre eventos. Nunca las bandas como observaciones
sueltas»*— y aquí sólo se reescribe con `event_id` en lugar de `target_date`, que es la
corrección de A-275. **Se mantiene aunque B demuestre que no basta**, precisamente para que
nadie pueda decir que la unidad se movió al ver el resultado.

Las otras dos se reportan **siempre**, en todas las tablas, para que la diferencia se vea en
lugar de suponerse.

---

## C. Los tres esquemas de ponderación, declarados antes de compararlos

Sea `E_n` el número de eventos con `n` bandas en la muestra.

| esquema | peso de UN evento de `n` bandas en la media global |
|---|---|
| **W1 — por contrato** | `n / Σ_m (m · E_m)` — **proporcional a `n`** |
| **W2 — igual por evento** | `1 / Σ_m E_m` — **independiente de `n`** |
| **W3 — igual por evento × lead** | `1 / Σ_m E_m` **dentro de cada lead**, sin agregar leads |

**Los tres se calculan y se publican.** No se elegirá uno después de ver cuál sale mejor; W3
es el primario por la declaración A.4 y los otros dos acompañan.

---

## F. REGLA DE VEREDICTO, escrita antes de los números

H4 afirma: *«las escaleras 7/9/11 pueden compararse y agregarse sin que el cambio de escalera
genere diferencias mecánicas de línea base»*.

* **`H4 = INVALIDADA`** si se demuestra que la línea base —o la puntuación de una familia de
  pronósticos de calidad fija— **depende de `n`** y **ninguno** de los tres esquemas de
  ponderación lo neutraliza.
* **`H4 = VALIDADA`** si existe una unidad o ponderación, entre las tres declaradas, bajo la
  cual la línea base es **invariante en `n`**.
* **`H4 = INCONCLUSIVA`** si la matemática no decide y **los datos tampoco pueden decidirlo**.

**Precisión que importa para no hacer trampa con las palabras:** si la respuesta resulta ser
«no en crudo, sí tras normalizar contra la línea base de su propia escalera», eso **NO es
`VALIDADA`**. H4 pregunta por las métricas tal como se están calculando. Una corrección que
haya que introducir es la prueba de que la hipótesis, como está enunciada, era falsa.
