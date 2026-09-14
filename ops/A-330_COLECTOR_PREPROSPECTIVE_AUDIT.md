# A-330 — AUDITORÍA PREVIA A LA PRUEBA PROSPECTIVA: #61, VALIDACIÓN DE A-329 Y PREPARACIÓN DE A-327

**Auditor técnico independiente · 2026-09-14T17:10Z**

> *Dejar el instrumento preparado para observar el futuro sin tocar la predicción que se hizo
> sobre ese futuro.* Ningún parámetro de A-327 se ha modificado.

---

## 1 · ESTADO CONGELADO

    main 1584045 · suite 754 verdes · PRs accionables 0 · B inexistente
    D0-P BLOCKED · §34 BLOCKED · #68 gateado por el usuario
    colector operativo · vigilante operativo (sha fa274d57…)
    A-327 prospectiva pendiente · A-328 auditoria · A-329 detector de ranuras

**A-327 sigue INMUTABLE** y no se evalúa con ningún ciclo anterior.

---

## 2 · AUDITORÍA DE #61

### 2A · `HOLGURA` vs `PMW_LOCK_WAIT`

| | |
|---|---|
| **dónde se define `PMW_LOCK_WAIT`** | **en ningún sitio como definición.** Es un *default de shell* `${PMW_LOCK_WAIT:-900}` repetido **tres veces** en `ops/hetzner/launcher.sh` (líneas 61, 62, 89) |
| **quién lo consume** | `flock -w` (el comportamiento **real**), el mensaje de log, y la carga útil del evento `lock_timeout` |
| **dónde está `HOLGURA`** | `ops/vigila_colector.py:67` → `HOLGURA = (27 * 60) + 900` |
| **¿mismo concepto?** | El `900` **sí**: es la misma espera máxima. El `27*60` es **otra cosa** — la separación `decide`→`collect`, derivada de `RANURAS`, escrita como una **tercera** representación |
| **¿uno deriva del otro?** | **No.** Los dos se escriben a mano, en ficheros distintos, en lenguajes distintos |
| **riesgo de divergencia** | **Alto y silencioso.** `PMW_LOCK_WAIT` es una variable de entorno: exportarla en el host cambia el comportamiento real **sin tocar ningún fichero**, y el vigilante seguiría calculando con 900 |

### 2B · `RANURAS` vs el crontab

| | |
|---|---|
| **dónde está el crontab** | `ops/hetzner/install.sh:71-73` — `7 */3`, `40 2`, `40 11` |
| **dónde está `RANURAS`** | `vigila_colector.py:63` — `[(h,7) for h in range(0,24,3)] + [(2,40),(11,40)]` |
| **quién consume cada uno** | cron ejecuta el primero; el vigilante deriva esperas y cobertura del segundo |
| **timezone** | **UTC en los dos, y verificado**: `install.sh:85-92` comprueba `timedatectl` y **se niega a instalar** si el host no es `Etc/UTC` |
| **DST** | `Etc/UTC` no tiene DST. Ni el cron ni el vigilante pueden desplazarse |
| **si se añade/quita un slot del crontab** | el vigilante **no se entera**: seguiría esperando el viejo (falsa ALARMA de ranura perdida) o ignorando el nuevo (ceguera) |
| **¿puede el vigilante creer en una ranura que cron no ejecuta?** | **SÍ** |
| **¿puede cron ejecutar una que el vigilante no conoce?** | **SÍ** — y entonces su fila se asignaría a la ranura anterior, inflando la «espera» |

---

## 3 · FUENTE ÚNICA DE VERDAD — cuál debería ser, y por qué hoy no la hay

| magnitud | fuente de verdad conceptual | estado hoy |
|---|---|---|
| slots | **las líneas del crontab de `install.sh`** — son lo que cron ejecuta | duplicada a mano en el vigilante |
| espera máxima | **el entorno del host**, no el fichero: `flock -w "${PMW_LOCK_WAIT:-900}"` | duplicada, y el entorno puede ganarle al default sin dejar rastro |
| duración del ciclo | **medida**, nunca configurada | correcto: sale de `stage_profile` |
| timezone | **`install.sh`**, que verifica y se niega | correcto — pero **sólo en la instalación** |
| ventana de evaluación de una ranura | **derivada del dato** (`HOLGURA + 2 × último ciclo`) | correcto: A-329 la deriva, no la fija |

> **La pregunta no es si hoy coinciden.** Es si pueden divergir mañana sin que nada lo
> detecte. **Para slots y espera máxima: sí.**

---

## 4 · MUTACIONES DE #61

| | mutación | esperado | observado |
|---|---|---|---|
| **R1** | cambiar sólo `RANURAS` | debería fallar algún guard | **no hay guard que pueda fallar**: `grep -rln "vigila_colector\|RANURAS\|HOLGURA" tests/` no devuelve nada. El vigilante **no está en la suite** |
| **R2** | cambiar sólo el crontab (`7 */3` → `9 */4`) | debería fallar algún test | **3 tests seleccionados, 3 pasan** |
| **H1** | cambiar sólo `HOLGURA` | el consumidor debería detectarlo | mismo caso que R1: **ningún test lo mira** |
| **H2** | cambiar sólo `PMW_LOCK_WAIT` (900 → 1800) | debería existir guarda contra divergencia | **13 tests seleccionados, 13 pasan** |

> ### **#61 NO se cierra. Las cuatro mutaciones confirman que la duplicación es real y no la detecta nada.**
>
> Que los valores coincidan hoy es una coincidencia mantenida a mano, no una invariante.

---

## 5 · VALIDACIÓN DE A-329

| caso | resultado |
|---|---|
| **1 · ranura recién iniciada** | `EN VUELO`, exit 0 — verificado borrando el shard de las 15:07 a las 16:23 |
| **2 · ranura pasada del margen sin fila** | `ALARMA: TURNO PERDIDO`, **exit 1**, nombra la ranura |
| **3 · dos ranuras antiguas ausentes** | identifica **las dos** (09-13 18:07Z y 09-14 06:07Z), exit 1 |
| **4 · todos los slots presentes** | exit 0, 0 alarmas |
| **5 · última ranura presente pero con datos incompletos** | **se comporta como AUSENTE y alarma** (D4) |

**Contrato del caso 5, buscado y no inventado:** la unidad del vigilante no es «existe el
fichero» sino **«existe una fila parseable cuyo id mapea a una ranura»**. Un shard vacío o
ilegible no produce ninguna fila, así que su ranura queda sin cubrir. **El comportamiento es
el correcto y no hubo que decidirlo: ya estaba determinado por el diseño.**

---

## 6 · «FILA EXISTE» ≠ «CICLO VÁLIDO»

El detector **nunca comprueba `shard exists`**. Comprueba fila parseable + id válido + ranura.
Consecuencia medida:

    shard vacio (gzip valido, 0 lineas)   -> ninguna fila -> ranura sin cubrir -> ALARMA
    shard ilegible (gzip corrupto)        -> excepcion    -> exit 1 con traza
    id corrupto en shard ANTIGUO          -> fila descartada -> ranura sin cubrir -> ALARMA
    id corrupto en shard EN VUELO         -> exit 0, "en vuelo"  (correcto: no juzgable)
    shard duplicado / de otra ranura      -> se asigna a su ranura por el id, no por el fichero

**Ninguno produce verde falso.**

### 6.1 · DEFECTO NUEVO (menor): el diagnóstico miente aunque la detección acierte

Un shard **presente pero dañado** se reporta como **`PERDIDA — TURNO PERDIDO`**, es decir
«el ciclo no corrió», cuando la verdad puede ser «el ciclo corrió y su registro está roto».
**La alarma es correcta; el texto que la acompaña manda a buscar en el sitio equivocado.**
Documentado, **no corregido** — corregirlo ahora tocaría el instrumento en vísperas de la
prueba.

---

## 7 · TEMPORALIDAD Y TIMEZONE — la única parte que sale limpia de esta auditoría

    cron            campos UTC, y `install.sh:85-92` VERIFICA `Etc/UTC` y SE NIEGA si no
    launcher        todos los sellos con `date -u`
    session_id      `collector.new_session_id()` -> `_utcnow().strftime("%Y%m%dT%H%M%SZ")`
    vigilante       parsea con `%Y%m%dT%H%M%SZ` + `tzinfo=utc`; slots con `.replace()` sobre UTC
    produccion      `paper_cycle.py:2008` usa el MISMO patron `col_(\d{8}T\d{6}Z)_`

**Una sola interpretación de «ranura 03:07 del 15-09».** Sin mezcla de `Europe/London`,
`Asia/Seoul` ni hora del host. `Etc/UTC` no tiene DST, así que ni el cron ni los slots pueden
desplazarse.

**Riesgo residual declarado:** la verificación de `Etc/UTC` corre **en la instalación**. Si
alguien cambia la zona del host después, nada la vuelve a comprobar. Es la familia de
*«los instrumentos sobreviven a la máquina para la que se escribieron»*.

---

## 8 · RELACIÓN ESPERA / CICLO

**No es una identidad, y la mayoría de los ciclos no son aplicables.** De 30 ciclos con ciclo
previo medido, **sólo 3 tuvieron contención real** (el anterior seguía corriendo cuando el
cron disparó). En los otros 27 la «espera» de 5-6 s es el arranque del launcher, **no** una
espera de lock: meterlos en el estadístico daría residuos enormes y falsos.

    ciclo             ranura  espera  ciclo previo  predicho      r
    09-12 12:09:19    12:07      139       1747,4     127,4   +11,6
    09-14 03:08:34    03:07       94       1701,8      81,8   +12,2
    09-14 12:10:59    12:07      239       1845,7     225,7   +13,3

    media +12,37 · mediana +12,25 · min +11,57 · max +13,29 · rango 1,72 s · desv 0,71
    p95 = maximo (n = 3)

**Sesgo sistemático de +12,4 s**, muy estable (rango 1,7 s) — **sobre n = 3**. Suficiente como
diagnóstico, insuficiente para tratarlo como constante física. **No se toca el 1620.**

---

## 9 · CAPACIDAD — y el hallazgo que cambia la lectura

**La ventana acumulada oculta que la pendiente NO se estabiliza.** La acumulada sube por
construcción si los últimos puntos son altos; la pregunta se responde con ventana deslizante.

    DESLIZANTE de 8 ciclos:
      212,7 · 181,7 · 228,8 · 246,9 · 341,7 · 369,7 · 382,8 · 518,2 · 456,6 · 406,4 · 496,3

    ACUMULADA: 265,8 · 217,3 · 265,5 · 348,9 · 361,6

**Las últimas cinco ventanas deslizantes están por encima de la acumulada.** La tasa local
(~400-500 s/día) supera a la global (362) de forma consistente, aunque las tres últimas
(456,6 · 406,4 · 496,3) rebotan y **no permiten declarar aceleración**.

    nivel 1970,2 s · holgura 550 s
      acumulada Theil-Sen   361,6 s/dia  ->  2026-09-16 03:36Z
      acumulada OLS         352,7        ->  2026-09-16 04:31Z
      dos puntos            374,1        ->  2026-09-16 02:23Z
      deslizante, ULTIMA    496,3        ->  2026-09-15 17:42Z
      deslizante, mediana   341,7        ->  2026-09-16 05:44Z
      deslizante, minima    181,7        ->  2026-09-17 15:44Z

> **ESTIMACIÓN DE CAPACIDAD, no fecha de ejecución: la pérdida de una ranura es plausible
> desde la tarde del 2026-09-15, con centro el 09-16 de madrugada y cola hasta el 09-17.**
> **Confianza BAJA.** Bajó desde «baja-media» en A-328 precisamente porque la ventana
> deslizante enseña lo que la acumulada tapaba.

---

## 10 · ESTADO DE A-327

**INTACTA.** No se ha recalculado, reinterpretado ni sustituido. Sigue siendo **la predicción
prospectiva vigente**: `duración ≈ 2.144 s`, `espera ≈ 524 s`, cruza 300, no cruza 600, sobre
el `decide 02:40Z` + `collect 03:07Z` del **2026-09-15**.

**No se ha generado ninguna predicción nueva.**

---

## 11 · PROCEDIMIENTO DE EVALUACIÓN — preparado y probado en seco

`ops/evalua_a327.py`. **No requiere editar ningún parámetro**: la predicción y el criterio
están congelados dentro. Extrae los 14 campos exigidos del identificador y la ranura
(A-326), nunca de una estimación verbal ni del instante de fin del ciclo anterior.

    ejecutado hoy  ->  "EL CICLO AUN NO EXISTE: falta el decide de las 02:40 del 2026-09-15.
                        NO es INDETERMINADA: es que todavia no ha ocurrido."   exit=2

Códigos: **0** evaluado · **2** aún no ocurrido · **1** el instrumento falla.
Separa explícitamente la **Pregunta A** (¿acertó?) de la **B** (¿sigue la tendencia?) y la
**C** (¿cuándo se pierde una ranura?), y no responde B ni C.

---

## 12 · GAP OPERATIVO → **RUNBOOK NECESARIO** (no implementado)

Hoy sólo existe la **emisión** del evento `lock_timeout` (`launcher.sh:88`). Para cerrar el
hueco haría falta declarar:

    1. responsable            quien recibe el aviso y quien decide
    2. canal de aviso         hoy no hay ninguno: el vigilante lo corre una sesion a mano
    3. accion ante AVISO >300 s
    4. accion ante ALARMA >600 s
    5. accion ante RANURA PERDIDA (irreversible: el libro de ese instante no existe)
    6. escalado               cuando deja de ser observacion y pasa a intervencion
    7. recuperacion           que se hace con la ranura perdida (nada se recupera; que se anota)
    8. criterio de cierre     cuando se considera resuelto un episodio
    9. evidencia requerida    shards, log del launcher, evento lock_timeout, salida del vigilante

**No lo invento.** Queda como especificación de lo que falta.

---

## 13 · AUDITORÍA DEL AUDITOR

    sha ejecutado       vigila_colector.py  fa274d57db926550   ·  evalua_a327.py (nuevo)
    branch / parent     main 1584045 (merge #57, segundo padre 3d95fc7)
    suite               754 verdes, verificada sobre el arbol 19cd611 (A-315)
    datos               origin/paper-state 2b13ae5 · 70 shards · 49 ciclos en la era del cron
    timezone            100 % UTC, verificada en los cinco puntos de la cadena (§7)
    ciclos del regimen  18 con stage_profile
    exit codes          reales, capturados SIN tuberia (la leccion de A-314)
    fixtures            0 — todo de produccion; las mutaciones sobre COPIA, nunca el worktree
    lectura fallida     ninguna produce verde: D1/D2 exit 1, D3 traza, D4 alarma, D5b alarma
    errores de shell    `set -euo pipefail` donde hay encadenamiento; `$?` leido directo

**Comprobación de consumidor (lección de A-316):** el vigilante lee
`paper_state/cycle_params`, que es **el único registro de tiempos de ciclo que existe**. No
hay almacén alternativo cuyo consumidor pudiera diferir.

---

## 14 · DEFECTOS ENCONTRADOS

| # | defecto | estado |
|---|---|---|
| D-1 | **#61 confirmado**: `HOLGURA`/`PMW_LOCK_WAIT` y `RANURAS`/crontab duplicados, **ninguna mutación los detecta** | **abierto**, documentado, no corregido |
| D-2 | **El vigilante no está en la suite.** Ningún test lo referencia: R1 y H1 no tienen guard que pueda fallar | **abierto** |
| D-3 | **`PMW_LOCK_WAIT` es una variable de entorno**: el host puede cambiar el comportamiento real sin tocar un fichero, y nada lo reflejaría | **abierto** |
| D-4 | **NUEVO (menor):** un shard presente pero dañado se diagnostica como «TURNO PERDIDO». Detección correcta, mensaje engañoso | **abierto**, no corregido a propósito |
| D-5 | La verificación de `Etc/UTC` corre **sólo en la instalación** | **abierto** |

**Ninguno impide evaluar A-327**: su evaluación depende de la espera derivada del id contra
la ranura, que §6, §7 y §13 muestran sana.

---

## 15 · DECISIÓN FINAL

> ## `READY_FOR_PROSPECTIVE_TEST`
> ## con `NEW_DEFECT` (D-4, menor y no bloqueante)

Se cumplen las siete condiciones del §19 del encargo:

    #61 resuelto o formalmente documentado      -> DOCUMENTADO con mutaciones que prueban el riesgo
    A-329 pasa las mutaciones                   -> los 5 casos, en las dos direcciones
    ausencia de shard no produce falso verde    -> ALARMA + exit 1
    errores de lectura no producen falso verde  -> D1/D2/D3/D4/D5b, ninguno verde
    timezone validada                           -> cadena completa UTC, verificada en instalacion
    A-327 intacta                                -> byte a byte, sin recalcular
    procedimiento de evaluacion preparado        -> ops/evalua_a327.py, probado en seco

**Doy los dos rótulos y no uno**: forzar uno solo escondería información. El que decide si se
puede observar es `READY`; D-4 es real y va nombrado para que no se pierda.

**No se abre PR.** #61 no se arregla en esta tarea: el arreglo correcto —leer el crontab y
`PMW_LOCK_WAIT` del host en vez de duplicarlos— toca configuración de producción, y hacerlo
en vísperas de la prueba contaminaría el instrumento con el que se mide.

**Nada de esto autoriza L2, edge económico, paper trading, trading real ni cambio alguno de
estrategia, ciudad, modelo, umbral, escalera o settlement.**

**Siguiente paso:** ejecutar `ops/evalua_a327.py` cuando exista el ciclo del 2026-09-15
(empuje esperado ~03:40Z).
