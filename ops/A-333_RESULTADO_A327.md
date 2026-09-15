# A-333 — Resultado de A-327: `ALARMA`, y qué se sigue y qué no se sigue de ella

**Fecha:** 2026-09-15 · **Autor:** Claude (sesión A, perfiles desarrollador y validador)
**Predecesores:** A-327 (predicción, inmutable), A-330/A-331 (auditorías), A-332 (merge y freeze)

```
A-327 = ALARMA          #61 BLOCKED       D0-P BLOCKED       L2 BLOCKED
ESTADO OPERATIVO = ALARM / ACTION REQUIRED (preparar, no desplegar)
```

---

## 1 · RESULTADO DE A-327

| Variable | Predicción congelada | Observado | Error |
|---|---|---|---|
| duración del `decide` | ~2144 s | **2219,4 s** | +75,4 s (+3,5 %) |
| espera del `collect` | ~524 s | **612 s** | +88 s (+16,8 %) |
| cruza 300 (WARNING) | sí | **sí** | acertado |
| cruza 600 (ALARM) | **no** | **sí** | **fallado** |
| **clasificación** | banda CONFIRMADA | **`ALARMA`** | **no acertó** |

**A-327 no acertó.** La espera real superó el umbral de `ALARMA` por **12 segundos**. El
criterio se aplicó literalmente y el resultado es final.

Conviene separar dos cosas que es tentador mezclar: la predicción de **duración** fue
buena (+3,5 %); la de **espera** falló un +16,8 % y ese error cayó a caballo del umbral.
Cuando la clase se decide en 600, un error de 88 s sobre ~550 basta para cambiarla. Eso
dice algo sobre la fragilidad del criterio tanto como sobre la puntería del modelo — y no
es excusa: la clase predicha era otra.

**No es `INDETERMINADA`.** La medición es válida, completa y sin defectos. `INDETERMINADA`
está reservada a un defecto objetivo de medición, no a un resultado incómodo.

---

## 2 · INTEGRIDAD DEL INSTRUMENTO

| | |
|---|---|
| merge SHA | `22a77200e9f4aaf17d6cb3c82f681daa9c791168` |
| `code_commit` de los dos ciclos | `22a77200e9f4…` → **`HOST_SHA_VERIFICADO`** |
| `evalua_a327.py` | sha256 `24600ba2ea3f53b4…`, **idéntico** al congelado en A-332 |
| ranura objetivo | `2026-09-15 03:07Z` — la preinscrita, no sustituida |
| shard del `collect` | legible, 36 campos, ciclo terminado, **0 duplicados** |
| zona horaria | UTC (sufijo `Z`, parseado como UTC) |
| cobertura | 54 ciclos, **0 ranuras juzgables sin fila** |
| intervención previa al dato | **ninguna** |

El SHA del host no es una inferencia mía sobre mi checkout: lo escribe el host en cada
shard. Y la predicción quedó escrita antes, el criterio antes, el evaluador antes.

---

## 3 · RECONCILIACIÓN DE DURACIÓN: **no había discrepancia**

Se pidió explicar por qué A-327 reporta 2219,4 s y el análisis de capacidad 2237,6 s «para
el mismo ciclo». **No es el mismo ciclo.** Es un error de categoría, y fabricar una
reconciliación habría sido peor que decirlo.

| | `col_20260915T024005Z_20b26f` | `col_20260915T031712Z_c29972` |
|---|---|---|
| modo | `no_paper_tau` — el **decide** 02:40 | `mode_collect` — el **collect** 03:07 |
| duración | 2219,4 s | 2237,6 s |
| filas | 136.762 | 138.502 |
| etapas | 32 | 31 |
| shard | distinto | distinto |

**Mismo campo** (`max(at_s)` del `stage_profile`, `excludes=params`), **mismo método**,
**mismo almacén**. Distinto ciclo. A-327 predice la duración del **decide**, porque es el
decide quien retiene el lock y determina la espera del collect. El 2237,6 es el último
punto de la serie de capacidad, que responde a otra pregunta.

**No se corrige A-327. No se corrige el análisis B. Ninguno estaba mal.**

### 3.1 · Y al auditarlo, el sesgo de +12,4 s deja de ser ruido

```
espera_exacta = offset_decide + duracion_decide + traspaso_lock − 1620

     612,412717 = 5,971863 + 2219,396624 + 7,044230 − 1620      ← exacto al microsegundo
```

El residuo de la relación `espera ≈ ciclo − 1620` es **exactamente** dos cosas:

- **5,97 s** — la espera propia del `decide` respecto de su ranura (el «5» que aparece en
  casi todas las filas del vigilante);
- **7,04 s** — el traspaso del lock entre el fin del decide y el arranque del collect.

Suman **13,02 s**. Con la espera truncada al segundo que usa el instrumento, **12,60 s**.
El sesgo histórico medido era **+12,4 s sobre n=3**.

**Es estructural, no estadístico.** Lo que parecía un residuo empírico a estimar es la suma
de dos latencias identificables. Esto es **diagnóstico y no recalibración**: no se toca la
relación, ni el evaluador, ni la predicción. Se anota qué es.

---

## 4 · CAPACIDAD (23 ciclos, régimen desde 2026-09-13, 51,2 h)

| | inicio | final | factor |
|---|---|---|---|
| duración | 1362,3 s | 2237,6 s | **×1,643** |
| filas cargadas | 94.130 | 138.502 | ×1,471 |
| s de ciclo / fila | 14,47 ms | 16,16 ms | ×1,116 |
| almacén | 17,0 MB | 30,7 MB | ×1,807 |

**Descomposición:** `1,471 × 1,116 = 1,642` frente a **1,643** observado. En logaritmos,
**78 % volumen · 22 % coste unitario**.

> Esto es una **factorización matemática**, no una atribución causal. Dice cómo se reparte
> el crecimiento entre dos factores medidos; **no** dice que el 22 % «sea infraestructura».

**Pendiente:** Theil–Sen **+384 s/día** · OLS +380 · dos puntos +411 (**no se usa**). Los
dos admisibles concuerdan al 1 %, sobre 23 puntos.

### 4.1 · Coste unitario: `INCONCLUSIVE` para cambio de régimen

Hay indicio de deterioro: la media de los diez últimos (15,39) supera la de los trece
primeros (14,51), y las dos mediciones más altas de toda la serie son las dos últimas
(16,23 y 16,16). **Dos puntos extremos no son un régimen.** La regla estaba escrita antes
y se aplica: `INCONCLUSIVE`. No se modifica el vigilante ni ningún umbral.

### 4.2 · Dos cautelas de unidad, dichas porque son fáciles de barrer

- `store_total_bytes` es **el almacén entero** y `store_rows_loaded` son **las filas de este
  ciclo**: no son la misma población y **no se dividen**. No hay aquí ningún «bytes por
  fila».
- «ms/fila» es duración **total** sobre filas cargadas: un coste **compuesto**, no el coste
  de cargar una fila.

### 4.3 · Medido pero no explicado

Las etapas desglosadas suman `load:markets` 98,1 + `collect:books` 42,2 + `discover` 62,4 =
**203 s**, el **9 %** del ciclo. **El 91 % restante queda fuera del desglose actual.**

No se afirma que ese 91 % sea *overhead*, *I/O*, *lock* ni ninguna otra causa concreta.
Está **medido como residuo y no explicado**, y así se queda hasta que haya evidencia
directa. Nombrarlo sería inventar una causa que encaja.

---

## 5 · DIAGNÓSTICO DEL ERROR DE PREDICCIÓN

```
error de espera            = 612 − 524     = +88,0 s
  error de duración        = 2219,4 − 2144 = +75,4 s
  residual de la relación  = 612 − (2219,4 − 1620) = +12,6 s
```

**Lo que falló fue el modelo de duración, no la relación espera↔ciclo.** La relación se
comportó fuera de muestra tal como estaba caracterizada, y su residuo resultó ser
estructural (§3.1).

Esto es un diagnóstico **post-hoc**. No se convierte en recalibración: el sesgo no se
incorporó a la puntuación de A-327 —estaba escrito antes que sólo aplicaría a predicciones
futuras— y sigue sin incorporarse a nada.

---

## 6 · ESTADO OPERATIVO

| | |
|---|---|
| `GREEN` | no |
| `WARNING` | no |
| **`ALARM / ACTION REQUIRED`** | **sí** |
| ranura perdida | **no** |
| espera observada | 612 s |
| `PMW_LOCK_WAIT` | 900 s |
| margen hasta el timeout | **288 s** de espera |

**El sistema ha entrado en `ALARM` pero no ha perdido ninguna ranura.** Son dos estados
distintos y no se confunden: la `ALARMA` se cruza en 600 s; una ranura se pierde cuando la
espera alcanza los 900 s del `PMW_LOCK_WAIT` y el lock se rinde.

---

## 7 · PROYECCIÓN DE CAPACIDAD

Holgura restante: `2520 − 2238 = 282 s` (o 288 s medidos sobre la espera). A +384 s/día,
**~0,73 días**, lo que sitúa el punto en torno a **2026-09-15 20:56Z**.

Formulado como debe formularse:

> **Bajo extrapolación lineal de la pendiente observada, la holgura hasta `PMW_LOCK_WAIT`
> se agotaría aproximadamente alrededor del 2026-09-15 por la tarde-noche.**

**No** «la ranura de las 21:07 se perderá».

### 7.1 · Intervalo: no existe, y no se inventa

El instrumento **no tiene metodología de intervalo** para esta proyección. Theil–Sen admite
un IC por Kendall, pero no está implementado, e implementarlo ahora sería modificar el
instrumento justo después de que produzca una señal incómoda. **No se hace.**

El acuerdo entre Theil–Sen (384) y OLS (380) **no es un intervalo**: los dos usan el mismo
dato y la misma hipótesis de linealidad, así que su coincidencia no mide la incertidumbre
que importa.

La única evidencia **fuera de muestra** sobre la fiabilidad de esta clase de extrapolación
es A-327 misma: a **un ciclo vista** erró **+3,5 %** en duración, y ese error bastó para
cruzar una frontera de clase. Una proyección a ~0,7 días debe leerse con al menos esa
fragilidad. El propio vigilante lo imprime: **es una cota, no una fecha — la pendiente se
estima con el mismo dato que predice.**

---

## 8 · DECISIÓN

**`ALARM / ACTION REQUIRED`, donde la acción es PREPARAR, no desplegar.**

Una `ALARMA` es una señal de capacidad. **No es una autorización de modificación**, y no se
convierte en una excepción de gobernanza porque llegue con urgencia aparente.

### 8.1 · ¿Existe una intervención ya auditada y gobernada, ejecutable sin contaminar?

Se buscó. **No existe.** Y merece detalle, porque la respuesta fácil sería decir que sí:

- **El parche de #61** está auditado (A-331, dos líneas) pero **no es una mitigación de
  capacidad**: hace observable el `PMW_LOCK_WAIT` efectivo; no reduce ni un segundo el
  ciclo. Desplegarlo aquí sería confundir el defecto que estaba abierto con el problema que
  acaba de aparecer.
- **Subir `PMW_LOCK_WAIT`** evitaría la pérdida de ranura, pero está explícitamente
  prohibido, cambiaría la `HOLGURA` de la que depende el instrumento, y es tratar el
  síntoma.
- **Las palancas de capacidad** existen como análisis (compactación por
  `ingestion_timestamp`, tarea #55; extensión del backfill, #30) pero **ninguna es una
  intervención preinscrita, revisada y con tests** lista para ejecutar. Y la revisión
  independiente que el §34 exige sigue **bloqueada**: el revisor era B, que ya no existe
  (#81).

### 8.2 · `GAP OPERATIVO` — registrado, no rellenado

**No hay runbook** para «el colector entra en ALARMA» ni para «se pierde una ranura». No lo
invento ahora: un procedimiento escrito bajo la presión de la primera alarma es un
procedimiento sin auditar con aspecto de procedimiento. Queda **registrado como gap**, que
es un problema de operación y no una razón para tocar el sistema.

**La decisión operativa es del usuario.** Lo que aporto es: la señal, su magnitud, su
descomposición, el margen restante y el hecho de que no hay una acción gobernada
disponible.

---

## 9 · QUÉ NO CAMBIA

| | |
|---|---|
| **A-327** | `ALARMA`, **final**. No se recalcula, no se reinterpreta, no pasa a INDETERMINADA |
| umbrales 300 / 600 | sin tocar |
| predicción 524 / 2144 | sin tocar |
| Theil–Sen, MAD×1,4826, 3,5×, ventana de 8 | sin tocar |
| 1620 / 2520 / `PMW_LOCK_WAIT` 900 | sin tocar |
| definición de espera, relación decide↔collect, ranura objetivo | sin tocar |
| `vigila_colector.py`, `evalua_a327.py` | sin tocar |
| **#61** | **BLOCKED** |
| **D0-P** | **BLOCKED** — dinero real sigue requiriendo permiso explícito del usuario |
| **L2** | **BLOCKED** — A-327 no aporta evidencia sobre edge, mercado, costes ni liquidez |
| **B** | congelado en `c03e2d0`, fuera del roster |
| **SettlementOperator**, **R24** | congelados |
| **D-4** (mensaje del shard dañado) | abierto, no bloqueante, **sin corregir a propósito** |

Ni un outlier eliminado. Ni un dato añadido retrospectivamente. Ni una población redefinida.

---

## 10 · PRÓXIMO PUNTO DE OBSERVACIÓN

El siguiente ciclo contratado. Hasta entonces: **freeze**, observación **read-only** con
`ops/salud_pre_medicion.sh` y `ops/vigila_colector.py`, y la `ALARMA` registrada.

Lo que se observará, sin predicción nueva escrita aquí: si la espera sigue subiendo, si
alguna ranura se pierde, y si el coste unitario confirma o refuta el indicio de §4.1. Tres
preguntas separadas, que se responden con evidencia y no con la extrapolación de §7.

---

**Lo que esta prueba demuestra:** que una predicción prospectiva escrita antes del dato,
con criterio congelado, instrumento verificado y sin intervención previa, **puede fallar y
registrarse como fallo**. Ese es el valor del ejercicio, y se habría perdido entero si
hubiera movido un umbral doce segundos.

**Lo que NO demuestra:** nada sobre la fecha de pérdida de capacidad, nada sobre el edge,
nada sobre L2, y nada que autorice tocar producción.
