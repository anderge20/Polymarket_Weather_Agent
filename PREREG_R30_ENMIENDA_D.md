# PREREG R30 — ENMIENDA D: los criterios de aceptación que tres enmiendas declararon intactos

**Sesión B, 2026-09-11.** Cuarta enmienda a `PREREG_R30_PUERTA_SUSTRATO.md`
(sha `0a5b794e656390b13e33f14a40260f7a7818b13928f45db7d1a5312deb0caaaf`), posterior a
**A** (`b2ecac699fa097cc5d23ff0513ced1a05d683aff89c92a92312705961d9aec33`),
**B** (`116b78b06f82b0bcc9b2be2083390f0d5169577b3806ad5fe9152debd9dd9a0a`) y
**C** (`2fecf29200624cd5f440a656941a0f4ef2a44279d36c806dc2d6d81408c99534`).

**Los cuatro defectos los encontró la sesión A**, en una pasada pedida expresamente **en dirección
permisiva**. Sigue sin calcularse nada contra R30.

**Y la observación de método que los explica, que es de A y es la mejor de la jornada:**

> Ninguna de las tres enmiendas anteriores toca §5.2 ni §5.3: **las tres los listan en «lo que NO
> cambia», y eso es lo que los ha protegido de la revisión. Una sección que tres enmiendas seguidas
> declaran intacta deja de mirarse.**

Es mi propia regla —*una enmienda es un parche y se revisa igual*— aplicada a **lo que la enmienda
declara que no toca**. La lista de «no cambia» se leía como garantía y era lo contrario: un permiso
para no mirar.

---

## DEFECTO 1 (el grave) — §5.3 no puede fallar por la razón para la que existe

Decía, entero:

> **§5.3** — Robustez: el signo se mantiene dejando fuera la estación de mayor peso y dejando fuera
> el mes de mayor peso.

**«El signo se mantiene»: estimador puntual, sin IC, sin bootstrap, y sin nombrar de qué
estadístico.** Mientras §5.1 —dos líneas arriba— exige límite inferior del IC bootstrap > 0.

**Y se aplica sobre el 48 % de los datos** en el mínimo de §4.1, o sea donde los IC son más anchos:
**exactamente cuando una prueba de sólo-signo es más permisiva.** Un estimador de puro ruido
conserva el signo la mitad de las veces. *La prueba de robustez es lo más débil del documento y
parece lo más estricto.*

### §5.3 enmendado

> **§5.3 (enmendado D)** — Robustez sobre las dos poblaciones de borrado (fuera la estación de mayor
> peso; fuera el mes natural de mayor peso), evaluadas **por separado**, y **con los estadísticos
> nombrados**:
>
> 1. **Mediana de PnL neto por evento** (la de §5.2, tal como la define el DEFECTO 2 de abajo):
>    **IC bootstrap por bloques sobre eventos, límite inferior > 0.** El mismo listón inferencial que
>    §5.1, no uno más flojo.
> 2. **BSS por `precio_bin`**: **estimador puntual > 0 en TODOS los intervalos de la familia** de
>    §5.4 (enmienda C).
>
> El punto 2 se queda en signo **a propósito y con la razón escrita**: exigir IC por celda sobre el
> 48 % de la muestra sería una prueba que la potencia decide, no los datos. Pero el signo se exige
> **simultáneamente en todos los intervalos**, lo que bajo ruido es 2^−k con k = tamaño de la
> familia (k ≥ 5 por §4.2 A+B, o sea p ≤ 0,031). **La fuerza inferencial viene de la conjunción, no
> de cada celda** — y queda dicho aquí para que nadie lo relaje después leyéndolo como «sólo signo».

## DEFECTO 2 — §5.2 no declaraba unidad de análisis, dos líneas después de que §5.1 la declarase

§5.1 es explícito: *«los bloques son eventos, no filas: las bandas de un evento son una partición que
suma 1»*. **§5.2 dice sólo «mediana de PnL neto > 0».** ¿Mediana sobre qué? Si la unidad fuesen filas
u operaciones, un evento con 11 bandas cotizadas aporta 11 observaciones y la mediana la dominan los
eventos más activos — **la dependencia que §5.1 nombra y §5.2 heredaba sin decirlo.**

Es el **defecto 3 de nuestra auditoría** (*el calificador decae a lo largo de una enumeración*), un
documento después de haberlo escrito.

### §5.2 enmendado

> **§5.2 (enmendado D)** — **Mediana SOBRE EVENTOS** del PnL neto del evento, donde el PnL de un
> evento es la **suma** del de sus bandas. Con el coste medido y no supuesto: semidiferencial
> observado en el libro del instante de decisión, más las fees de D19. **IC bootstrap por bloques
> sobre eventos, límite inferior > 0.**
>
> **El evento es la unidad de análisis en TODO R30**, §5.1, §5.2 y §5.3 incluidos. Donde un criterio
> no lo repita, se lee aquí.

## DEFECTO 3 — §4.3 apoyaba una puerta en «liquidado», que R30 no define

*«≥ 100 eventos liquidados con etiqueta final»*. **R30 no define el término**, y las dos lecturas
**difieren en si la puerta es alcanzable**:

- **Lectura A — liquidados por nosotros** (posiciones paper cerradas por `stage_settle`).
  **Imposible hoy**: `stage_settle` no ha corrido nunca en vivo porque no existe `PAPER_TAU`
  (A-122). §4.3 dependería de una puerta **fuera del documento y fuera de nuestra decisión**.
- **Lectura B — resueltos por el mercado**, desenlace conocido. **Alcanzable sólo con observaciones.**

**Quien ejecutara elegiría la alcanzable**, que es la misma forma que la familia sin declarar: un
término que soporta peso sin definición.

### §4.3 enmendado

> **§4.3 (enmendado D)** — **≥ 100 eventos RESUELTOS**: aquellos cuyo desenlace es conocido a partir
> de `weather_observations` bajo el operador de liquidación que R29/R12 declaren para su terna,
> **con independencia de que exista o no una posición paper y de que `stage_settle` haya corrido.**
>
> Es la **lectura B**, elegida **por el propósito declarado** del propio §4.3 —*«sin esto no hay
> Brier que calcular»*—: el Brier necesita el **desenlace**, no nuestra liquidación. Y así R30 **no
> depende de que se levante ningún gate**: D0 sigue entero y R30 sigue siendo evaluable.

## DEFECTO 4 — el congelado no tiene puntero hacia adelante y no había cadena

Verificado: `grep -ci enmienda` sobre el congelado = **0**, y no existía ningún índice para R30.

**Y es permisivo:** el artefacto que los resultados van a citar por su sha es
`PREREG_R30_PUERTA_SUSTRATO.md`. Quien llegue por ese nombre —que es *cómo se llega a un congelado*—
lee **§5.4 con la familia sin declarar**, la versión rota, y **nada se lo advierte**. Es el defecto 4
de nuestra auditoría con su forma exacta: *cada documento es correcto por separado; sólo la cadena
miente.*

El remedio de aquella auditoría era **un índice fechado, nunca editar el congelado**. El ROADMAP no
es ese índice: es un fichero grande donde nadie busca la procedencia de un sha.

### Remedio

> **`R30_PREREG_CHAIN.md`**, índice fechado y actualizable, con el estado de R30 y de cada enmienda,
> sus shas y qué cláusula cambia cada una. **Se actualiza; nunca se edita un congelado.**

## Lo que NO cambia — y esta vez la lista lleva advertencia

§1, §2, §3, §4.1, §4.2 (A+B), §5.1, §5.4 (B+C), §6, §7, §8 y el §0 de C.

> **ADVERTENCIA, por lo aprendido hoy:** esta lista **no es una certificación**. Tres enmiendas
> seguidas declararon intactos §5.2 y §5.3 y eso es precisamente lo que impidió que se mirasen.
> **«No cambia» significa «esta enmienda no lo toca», nunca «ya está revisado».**
