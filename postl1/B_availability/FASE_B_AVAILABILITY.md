# POST-L1.8 · FASE B — VALIDACIÓN INDEPENDIENTE DE AVAILABILITY

# 1 · STATUS

## `POST-L1.8 · FASE B = CONDITIONALLY VALIDATED`

---

# 0 · CORRECCIÓN QUE VA ANTES DE TODO LO DEMÁS

En `L1.8` (A-293) escribí, y lo repetí en la tarea #75:

> *«`available_at = issue_time + 4:45:36` es una **convención del backfill**. 236 forecasts,
> **0 observaciones reales de publicación**.»*

**Es falso, y el error es mío por no haber mirado.** El `4:45:36` es **`L_MAX['icon_seamless']
= 4,76 h`**, y su procedencia está escrita en el docstring del módulo que yo llevo toda la
noche leyendo:

    weather.py:15    available_at(run) = issue_time(run) + L_MAX[model]
    weather.py:17-19 "L_MAX the MAXIMUM publication latency observed per model, not the
                      median: fail-closed. Values from the F-3 availability audit
                      (n=307 passes, 20 dates, Jun-Sep 2026), preregistered in
                      PREREG_MODELSEL_ASOF_V2.md §2."

**No es una convención inventada: es una cota empírica fail-closed sobre 307 pasadas, con su
preinscripción, su informe de cierre y sus datos crudos en el corpus.** La limitación **L1** de
`L1.8` estaba mal caracterizada — no «sin evidencia», sino **«con evidencia de nivel 1 y una
cobertura incompleta»**, que es una cosa distinta y mucho menos grave.

*Quinta vez esta noche que el proyecto ya había hecho el trabajo y yo no miré
(`band_integrity`, `tmax_observed`, la terna de `discovery`, `resolution.py`… y ahora la
auditoría F-3). Esta es la peor de las cinco: **emití un veredicto formal cuya limitación
central se apoyaba en no haber mirado.***

# 2 · LOCK

| | |
|---|---|
| evidencia primaria | `PREREG_MODELSEL_ASOF_V2.md` (congelado ANTES de consultar la muestra) + `F3-CLOSURE-REPORT.md`, generado **2026-09-05** |
| crudo | `MODELSEL_ASOF_V2_RAW.json` — 3 840 filas · `f3sample.py` |
| **fecha de congelación: 2026-09-05, ocho días ANTES de cualquier análisis de L1** | ninguna elección de esta fase puede haber mirado el resultado |
| artefactos | `postl1/B_availability/` — no se toca nada de L1 ni de la fase A |

# 3 · EVIDENCIA

| source | evidencia | qué mide | nivel | n |
|---|---|---|---|---|
| `data_run/<model>/<run>/meta.json` → `created_at` | escrita **por el proveedor** al completar la pasada (README de `open-meteo/open-data`, verbatim) | instante en que el proveedor declara la pasada completa | **NIVEL 1** | 307 pasadas, 4 modelos |
| `Last-Modified` del objeto `temperature_2m.om` | cabecera HTTP **del almacén del proveedor** | última escritura del fichero de la variable | **NIVEL 1** | 230 objetos |
| `last_run_availability_time` de la API | timestamp de la propia API | disponibilidad en la API | **NIVEL 1 pero n = 1** | **1** |

**ICON (`dwd_icon`), latencia `created_at − init`, n = 78:**

    min 3,44 · p05 3,58 · mediana 3,83 · p95 4,17 · MAX 4,76 horas
    cota compuesta max(created_at, LastModified):  med 3,84 · p95 4,22 · MAX 4,76

**El proyecto adoptó el MÁXIMO (4,76 h), no la mediana. Fail-closed por diseño.**

# 4 · COVERAGE

    auditoria F-3:  2026-06-03 -> 2026-09-04     (su §8: 2026-04-02..2026-06-02 = UNKNOWN)
    ventana puntuada de L1 (lead 9): 2026-05-01 -> 2026-08-23

    eventos lead 9 DENTRO de la auditoria:   64 de 96   (66,7 %)
    eventos lead 9 en periodo UNKNOWN:       32 de 96   (33,3 %)

**Un tercio de la evidencia superviviente vive en un periodo que la propia auditoría clasifica
como `UNKNOWN`.** *Éste es el hallazgo nuevo de la fase B y no estaba en `L1.8`.*

**Restricción a la ventana con evidencia** — declarada por su motivo, no por su resultado: la
auditoría se congeló el **2026-09-05**, antes de todo L1, y su §8 fija el corte:

    lead 9   TODOS                 n=96  B4-S3  -0,01181 [-0,01608, -0,00770]  excluye el cero
             con evidencia F-3     n=64  B4-S3  -0,01292 [-0,01815, -0,00757]  excluye el cero
             periodo UNKNOWN       n=32  B4-S3  -0,00958 [-0,01649, -0,00363]  excluye el cero

**El resultado del lead 9 no depende del periodo sin evidencia**: restringido a los 64 eventos
con evidencia es **ligeramente más fuerte**, y el subconjunto sin evidencia también excluye el
cero por su cuenta.

*(lead 24, que ya está descartado: con evidencia −0,00914; en el periodo UNKNOWN **+0,00034**,
IC que incluye el cero. Se reporta y no se usa.)*

# 5 · LATENCY Y MARGEN

    lead 9   issue 18z de td-1  ->  t_asof = init + 9,00 h

    margen sobre la mediana medida (3,83 h)  +5,17 h
    margen sobre el p95 medido    (4,17 h)   +4,83 h
    margen sobre el MAXIMO medido (4,76 h)   +4,24 h

> **Para que hubiera look-ahead en el lead 9, la latencia real de publicación tendría que
> superar 9,00 h: 2,35 veces la mediana medida y 1,89 veces el máximo observado en 78
> pasadas.**

*(lead 24: `t_asof = init + 6,00 h`, sólo 1,26× el máximo medido. **Por eso era el frágil**, y
ya estaba descartado por otras razones en la fase A.)*

# 6 · RED TEAM — los doce ataques del encargo

| # | ataque | resultado |
|---|---|---|
| 1 | ¿el timestamp representa publicación pública? | **NO del todo.** La auditoría lo **refuta** ella misma: 101 de 230 objetos tienen `Last-Modified` **posterior** a `created_at`, con retraso máximo **93,7 min**. Por eso el proyecto usa `max(created_at, LastModified)` |
| 2 | ¿caché? | **no descartada.** No hay evidencia ni a favor ni en contra |
| 3 | ¿retraso regional? | **no medido.** Limitación documentada |
| 4 | ¿API y almacén se actualizan a la vez? | **n = 1.** Única observación: `delta = +2,0 min`. La API expone **sólo la última pasada**, así que la disponibilidad histórica de la API **no es recuperable**. El informe lo clasifica como categoría D |
| 5 | ¿reconstruible antes de `t_asof`? | irrelevante: la evidencia es del lado del proveedor, no nuestra |
| 6 | ¿pudo cambiar el contenido sin cambiar `issue_time`? | **sí, y está medido**: `Last-Modified − created_at` va de −16,45 a **+93,70 min**, con 128 de 230 negativos |
| 7 | ¿revisiones? | el producto usa la pasada por `init_time`; las revisiones dentro de una pasada son el punto 6 |
| 8 | **¿`first_seen_at` = primera disponibilidad?** | **no aplica, y eso es lo bueno:** la evidencia **no** es nuestro polling, son **timestamps del proveedor**. No hay un `first_seen_at` nuestro que confundir con la publicación |
| 9 | ¿frecuencia de polling suficiente? | no aplica por lo mismo |
| 10 | ¿cubre el producto que usa `B4`? | **sí** para el modelo (`icon_seamless`/`dwd_icon`) y **parcialmente** para el periodo: **66,7 %** |
| 11 | ¿diferencia entre emisión y publicación? | **es exactamente lo que se midió**: 3,44–4,76 h para ICON |
| 12 | ¿días con latencia anormalmente alta? | **sí, y es el aviso registrado**: el máximo **creció** al pasar de 20 a 307 observaciones. **La cola NO está caracterizada** |

# 7 · LIMITACIONES

1. **`DELTA_API` no está demostrado** (`n = 1`, +2,0 min). El informe es explícito: *«NO se puede
   afirmar `available_at = created_at`»* ni *«`created_at ≤ available_at`»*. La cota adoptada
   (4,76 h) **no** añade `DELTA_API`.
2. **La cola no está caracterizada.** El máximo creció con la muestra.
3. **Cobertura del 66,7 %.** Un tercio de los eventos del lead 9 está en periodo `UNKNOWN`.
4. **Caché y variación regional**: no medidas.
5. **La evidencia es del ALMACÉN del proveedor, no de la API pública.** Que un fichero esté
   escrito en S3 no demuestra que la API lo sirviera en ese instante.

# 8 · IMPACTO SOBRE L1

**Parcialmente resuelta.** La limitación `L1` de `L1.8` —*«`available_at` es una convención sin
validar»*— queda **reclasificada**: hay evidencia de **nivel 1**, preregistrada, fail-closed, y
el margen del lead 9 es de **4,24 h sobre el máximo observado**. Lo que queda abierto es
`DELTA_API`, la cola y **un tercio de cobertura temporal**.

**`L1` NO se reabre y no se recalcula nada.** Los números de L1 quedan como están; lo que cambia
es **cómo se describe su limitación**.

# 9 · DISEÑO PROSPECTIVO MÍNIMO — lo que falta y cómo cerrarlo

Para pasar de `CONDITIONALLY` a `VALIDATED` hace falta medir **`DELTA_API`**, que es la única
pieza con `n = 1`:

    QUE OBSERVAR   para cada pasada de icon_seamless (00/06/12/18z):
                     run_init · created_at (meta.json) · LastModified (temperature_2m.om)
                     poll_time · content_hash · http_status
                     api_last_run_availability_time
    CADA CUANTO    polling cada 5 min desde init+3,0 h hasta init+6,0 h
                   (la mediana medida es 3,83 h y el maximo 4,76 h)
    CUANTO TIEMPO  minimo 30 dias -> ~120 pasadas, cubriendo los cuatro ciclos
    QUE SE GUARDA  las dos cotas: ultimo poll SIN el dato y primer poll CON el dato
                   -> first_available ∈ (t_sin, t_con],  NUNCA "= t_con"
    CRITERIO       VALIDATED si, sobre >= 100 pasadas de icon_seamless,
                   el percentil 100 de (t_con - init) se mantiene por debajo de 9,00 h
                   con margen >= 2 h, y ninguna pasada lo supera.

**No se implementa aquí.** Es el diseño; su ejecución requiere su propio lock y **no puede
tocar producción sin la revisión de §34**.

# 10 · DECISIÓN

## **CONTINUAR A FASE C**

**Por qué no `NOT VALIDATED`:** existe evidencia independiente de nivel 1 — timestamps del
**proveedor**, no nuestros —, preregistrada antes de mirar nada, con la cota adoptada en su
**máximo** y un margen de **4,24 h sobre ese máximo** para el lead 9. Y el resultado **no
depende del periodo sin cobertura**: restringido a los 64 eventos con evidencia es ligeramente
más fuerte.

**Por qué no `VALIDATED`:** `DELTA_API` tiene `n = 1`, la cola no está caracterizada, y un
**tercio** de los eventos vive en un periodo que la propia auditoría llama `UNKNOWN`. *No
tenemos evidencia suficiente para afirmar disponibilidad en todo el histórico; la tenemos para
dos tercios de él, y el tercio restante no sostiene el resultado por sí solo ni lo contradice.*

**La condición se nombra y viaja con el candidato:** *el lead 9 de Londres es un candidato cuya
validez de disponibilidad está evidenciada en el 66,7 % de su muestra y acotada —no
demostrada— en el resto.*

Sigue prohibido y no realizado: L2, precios, EV, PnL, trading, ejecución, order book, umbrales,
estrategia, dinero real, paper trading, bot, producción. `D0-P` = BLOCKED · `L2` = BLOCKED.
