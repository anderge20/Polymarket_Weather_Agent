# A-328 — VALIDACIÓN PROSPECTIVA DEL COLECTOR Y DIAGNÓSTICO DE CAPACIDAD

**Auditor técnico independiente · 2026-09-14T16:30Z**

> Regla que gobierna este documento: *primero comprueba si acertó; después intenta explicar
> por qué.* Ningún umbral, pendiente, ventana ni definición se ha tocado.

---

## 1 · ESTADO INICIAL — verificado, no copiado

    main                1584045   (merge del PR #57)
    suite               754 passed, verificada sobre el arbol 19cd611 (A-315)
    PRs accionables     0         (solo el #28, borrador antiguo)
    B                   inexistente: la sesion no figura en el roster
    D0-P                BLOCKED   ·   §34   BLOCKED   ·   #68  gateado por el usuario
    colector            operativo ·   vigilante operativo
    A-327               53b8642

**La investigación de edge NO se toca.** Fase C / pooled lead 9 permanece intacta:
`θ ≈ −0,01051`, `IC95 [−0,01369, −0,00732]`, `Q p ≈ 0,372`, `I² = 0 %`. Es evidencia
**predictiva/estructural**, no de edge económico ejecutable, y **no se mezcla** con el
problema de capacidad del colector.

---

## 2 · PREDICCIÓN CONGELADA DE A-327 — citada, no recalculada

Escrita el 2026-09-14T15:55Z, antes de que el ciclo existiera:

    Theil-Sen 362 s/dia   ·   espera ≈ ciclo − 1620
    decide 02:40 (09-15)     duracion proyectada ≈ 2.144 s
    collect 03:07 siguiente  espera proyectada  ≈   524 s
    AVISO  300 s   CRUZA
    ALARMA 600 s   NO CRUZA

---

## 3 · DATO OBSERVADO — **NO EXISTE TODAVÍA**

El ciclo al que apunta la predicción es el `decide 02:40` del **2026-09-15** y el `collect
03:07` que le sigue. **Son las 16:30Z del 09-14: faltan ~11 horas.**

Último estado real de la serie:

    09-14 15:07:05Z   ranura 15:07   espera 5 s   ciclo 1970,2 s   27,5 MB   mode_collect
    paper-state       2b13ae5

**No se fuerza ninguna medición sustitutiva.** El `collect` de las 12:07 de HOY ya se midió
(A-326, espera 239 s) y **no es el ciclo predicho**: usarlo para puntuar A-327 sería mover el
objetivo después de lanzar.

---

## 4 · COMPARACIÓN PREDICCIÓN vs REALIDAD — **PENDIENTE**

Se emitirá cuando el shard exista, con el tiempo canónico derivado del identificador contra
la ranura (A-326), nunca de una estimación verbal.

## 5 · CLASIFICACIÓN — **NO CLASIFICABLE TODAVÍA**

No es `CASE D / INDETERMINADO`: ese caso es para cuando la instrumentación existe y produce
un valor no comparable. **Aquí el instrumento está sano y el dato no ha ocurrido.** Confundir
las dos cosas metería un `INDETERMINADO` falso en el registro.

## 6 · ERROR DE PREDICCIÓN — **PENDIENTE** (§4 y §5 del encargo)

---

## 7 · RELACIÓN ESPERA / CICLO — medible YA, y se mide

`r = espera − (ciclo_del_decide − 1620)`, sobre las **tres** esperas reales de toda la era del cron:

    09-12 12:09:19Z   espera 139 s · ciclo previo 1747,4 · predicho 127,4 · residuo +11,6
    09-14 03:08:34Z   espera  94 s · ciclo previo 1701,8 · predicho  81,8 · residuo +12,2
    09-14 12:10:59Z   espera 239 s · ciclo previo 1845,7 · predicho 225,7 · residuo +13,3

**La relación NO es exacta: tiene un sesgo sistemático de +12,4 s (rango 11,6-13,3).** Es el
arranque del launcher (~5 s) más la fluctuación del cron (~5 s) más la adquisición del lock.

> **No corrijo la relación.** A-327 predijo con `ciclo − 1620` y así se puntuará. El sesgo se
> registra como propiedad medida, y **si se incorpora, será a partir de la siguiente
> predicción, no de ésta.**

---

## 8 · EVOLUCIÓN DE THEIL-SEN — y la razón por la que la fecha es de baja confianza

    ventana   Theil-Sen   MAD-escala   atipicos (3,5×MAD)
      n= 6     265,8 s/d     29,0 s        0
      n= 9     217,3         22,0          0
      n=12     265,5         33,9          0
      n=15     348,9         42,0          0
      n=18     361,6         40,4          0

**La pendiente no es estable frente al tamaño de ventana: va de 217 a 362 s/día.** Eso, y no
el ajuste puntual, es lo que limita la confianza de cualquier fecha.

**Y un efecto que hay que decir:** con n=18 el detector marca **0 atípicos**, incluida la
excursión de las 06:07/09:07 que con n=15 sí destacaba. **La excursión ha entrado en la
escala que debía detectarla.** No cambio el multiplicador —está prohibido y sería exactamente
la ingeniería retrospectiva que el encargo veta—, pero queda anotado que la sensibilidad del
detector decae al absorber sus propios atípicos.

## 9 · EVOLUCIÓN DE MAD

Ver la tabla de §8: 29,0 → 22,0 → 33,9 → 42,0 → 40,4 s. **Casi se duplica**, en paralelo al
crecimiento de la pendiente.

---

## 10-13 · SERIE COMPLETA DEL RÉGIMEN (desde el escalón del 09-13)

    ciclo          dur   filas   MB  ms/fila   disc     mk    cb
    09-13 00:07  1362,3  94130 17,0   13,45   56,2   60,9  38,3
    09-13 02:40  1429,6  95988 17,5   13,90   55,8   60,9  37,8
    09-13 03:07  1425,0  97750 18,0   13,59   56,1   61,4  38,7
    09-13 06:07  1507,5  99600 18,4   14,08   61,5   61,4  42,0
    09-13 09:07  1501,1 101594 19,2   13,78   58,0   62,9  41,2
    09-13 11:40  1468,0 103530 19,7   13,51   27,9   61,8  39,5   <- discover a la MITAD
    09-13 12:07  1490,2 105474 20,2   13,46   29,4   59,9  39,9   <- idem
    09-13 15:07  1528,0 107408 20,5   13,57   28,6   62,0  39,9   <- idem
    09-13 18:07  1559,4 109282 21,0   13,41   53,7   60,4  38,4
    09-13 21:07  1622,4 112690 21,9   13,54   56,0   74,2  38,1
    09-14 00:07  1649,8 114496 22,4   13,61   52,9   73,6  37,2
    09-14 02:40  1701,8 116320 22,9   13,82   55,3   74,8  37,0
    09-14 03:08  1718,9 118042 23,4   13,75   56,5   75,1  37,8
    09-14 06:07  1883,3 119896 23,9   14,62   87,7   77,2  41,0   <- discover x1,5
    09-14 09:07  1927,4 122989 24,9   14,65   83,9   86,8  39,3   <- idem
    09-14 11:40  1845,7 125187 25,9   14,00   52,8   85,2  38,8
    09-14 12:10  1862,6 127172 26,9   13,90   53,7   86,9  38,7
    09-14 15:07  1970,2 129056 27,5   14,49   58,5   92,8  39,8

    variable        Theil-Sen        OLS     2 puntos     (por dia)
      duracion         361,58     352,72       374,09
      filas          21.139,75  21.150,94    21.493,08
      MB                  5,81       6,08         6,44
      ms/fila             0,38       0,43         0,64
      discover            1,57       9,78         1,40
      load:markets       18,63      19,70        19,64
      collect:books      −0,18      −0,33         0,94

---

## 14 · ANÁLISIS DE RÉGIMEN — **y aquí se corrige a A-323/A-324**

**TAMAÑO** (explicable por crecimiento del almacén):
`filas` +21.140/día · `MB` +5,81/día · `load:markets` **+18,63/día** con los tres estimadores
de acuerdo (18,63 / 19,70 / 19,64) — **éste sí es una tendencia limpia y monótona**, de 60,9
a 92,8 s (+52 %). `ms/fila` deriva **+0,38/día**: A-317 la midió constante a 13,54 ± 0,25 en
una ventana donde la deriva quedaba dentro del ruido; en ventana más larga la deriva se ve.
**No contradice A-317; la refina.**

**MÁQUINA / INFRAESTRUCTURA:**
`collect:books` **−0,18/día** — plano. Control perfecto.
`discover` **Theil-Sen +1,57/día** (plano) contra **OLS +9,78** — la divergencia entre robusto
y no robusto **es la firma de una serie con atípicos, no de una tendencia**.

> **CORRECCIÓN A A-323.** Usé la subida de `discover` (~85 s) como una de las dos condiciones
> del «nivel nuevo». La serie completa muestra que `discover` **también bajó a la mitad**
> (27,9 · 29,4 · 28,6 s) el 09-13 entre las 11:40 y las 15:07, y yo no lo vi. **Oscila en las
> dos direcciones y su pendiente robusta es esencialmente cero.** No es una variable de
> régimen: es una variable ruidosa que usé como si lo fuera.

**RÉGIMEN:** hay **un solo cambio sostenido** en la serie y es el del 09-13 (`_newest_first`,
A-320, hecho establecido). Lo del 09-14 06:07-09:07 fue una **excursión de dos ciclos**, ya
refutada como régimen por el tercer punto (A-325). **Correlación ≠ mecanismo:** que `discover`
y `ms/fila` subieran a la vez no prueba causa común, y `collect:books` —misma API— no se movió.

---

## 15 · AUDITORÍA DEL VIGILANTE

    sha256  3c97c5db4c5c8a62   ·   157 lineas   ·   identico al espejado en research

| comprobación | resultado |
|---|---|
| ¿Theil-Sen de verdad? | **SÍ** — mediana de todas las pendientes por pares |
| ¿MAD? | **SÍ** — `median(\|r − median(r)\|) × 1,4826`, residuos contra la recta **robusta** |
| ¿parámetros del lock? | **NO** — `HOLGURA = 27*60 + 900` está **duplicado a mano**. `PMW_LOCK_WAIT` vive en `launcher.sh` |
| ¿constantes duplicadas? | **SÍ, tres**: `RANURAS` duplica el crontab, `900` duplica `PMW_LOCK_WAIT`, `1620` se escribe como `27*60` |
| ¿misma serie medida? | SÍ — 49 ciclos, 09-09 21:07Z → 09-14 15:07Z |
| ¿timezone? | SÍ — todos `tz-aware` UTC; sin conversión local |
| ¿ranura correcta? | SÍ — `minute=7/40, second=0`; la línea base de 4-7 s es la fluctuación del cron, documentada |
| ¿mezcla ramas? | NO — lee `paper_state` de `wt-paper`, `diff` contra `origin/paper-state` = **0 líneas** |
| ¿usa datos posteriores? | NO — el ajuste es un ajuste; la proyección parte del último nivel hacia delante |
| ¿exit code? | SÍ — 1 con ALARMA (verificado), 1 sin datos, 0 en el resto |
| ¿fallo de extracción → falso verde? | NO — sin `try/except`; un shard corrupto aborta con traza |
| **¿dato ausente → falso «sin alarma»?** | **SÍ. Es el punto ciego, y es el que importa.** |

### 15.1 · EL PUNTO CIEGO

**El vigilante detecta ESPERAS, no AUSENCIAS.** Una ranura perdida no deja fila: no hay espera
que derivar, y el informe sale verde. **Justo el suceso que el instrumento existe para
anticipar es el único que no puede ver.** Verificado por mutación (M5).

---

## 16 · MUTACIONES EJECUTADAS

Sobre **copia** de los 70 shards de producción; el worktree real no se tocó.

| # | mutación | esperado | observado | |
|---|---|---|---|---|
| M1 | duración 1970 → 2400 s | cambia holgura y plazo | holgura 550 → **120 s**, plazo 09-16 03:36 → **09-14 22:53** | ✓ |
| M2 | `discover` 58 → 900 s | **nada** (no se lee) | **nada cambió** | ✓ confirma que no lo lee |
| M3 | espera → **301 s** | AVISO | **AVISO**, exit 0 | ✓ |
| M3b | espera → **299 s** | sin aviso | sin aviso | ✓ frontera exacta, sin off-by-one |
| M4 | espera → **601 s** | ALARMA + exit 1 | **ALARMA**, **exit=1** | ✓ |
| M5 | **borrar el shard** | ¿detecta la ranura perdida? | **exit=0, silencio** | ✗ **CIEGO** |

---

## 17 · AUDITORÍA DEL AUDITOR

    1  sha del vigilante ejecutado   3c97c5db4c5c8a62 (identico al espejado, d12dc97)
    2  main                          1584045
    3  suite                         754 passed (arbol 19cd611, A-315)
    4  rama de datos                 origin/paper-state 2b13ae5; diff en paper_state/ = 0 lineas
    5  procedencia                   paper_state/cycle_params/*/*/*/*.ndjson.gz, escritos por el
                                     ciclo en Hetzner. NO hay almacen alternativo de tiempos de
                                     ciclo: el consumidor de este dato es el propio vigilante y
                                     no existe otra fuente. (Leccion de A-316 aplicada: se
                                     comprueba QUE ALMACEN antes de medir severidad.)
    6  shards                        70        ·  7  ciclos en la serie  49
    8  timezone                      100 % tz-aware UTC
    9  ranuras                       10 (8 collect + 2 decide) · ERA_CRON 09-09T21:07:05Z
    10 umbrales                      AVISO 300 · ALARMA 600 · HOLGURA 2520
    11 regimen (>=09-13)             18 ciclos con stage_profile
    12 sin stage_profile             18 (no entran en la pendiente; SI en las esperas)
    13 fixtures                      0 — todo de produccion
    14 silenciamiento                ninguno
    15 exit codes                    reales y verificados por mutacion

**Nota de método:** en una comprobación anterior leí `$?` detrás de una tubería a `tail` y
obtuve el código de `tail`. Aquí los códigos se capturan sin tubería.

---

## 18 · CONCLUSIÓN

**PREDICCIÓN:** no evaluable todavía. El ciclo objetivo es del 09-15 y hoy es 09-14.
A-327 queda **congelado y sin puntuar**.

**DIAGNÓSTICO** (independiente de lo anterior):

1. **Hay una sola tendencia sostenida** y es de tamaño: el almacén crece ~21.140 filas/día y
   la carga crece con él; `load:markets` sube +18,6 s/día con los tres estimadores de acuerdo.
2. **`discover` no es una variable de régimen.** Pendiente robusta ≈ 0, con excursiones en las
   dos direcciones. **Esto corrige A-323**, que la usó como condición decisoria.
3. **El plazo es de BAJA-MEDIA confianza**: la pendiente va de 217 a 362 s/día según la
   ventana, y quitar un solo ciclo mueve la fecha ~5,5 h.
4. **El vigilante es correcto en lo que mide y ciego en lo que más importa**: no ve una ranura
   perdida.
5. **`discover` no lo lee el instrumento** — el criterio de A-322/A-323 vivía en prosa, no en
   el código.

## 18.1 · PLAZO (§11) — estimación central, rango y supuestos

    nivel actual 1970,2 s (09-14 15:07Z)   ·   holgura 2520 − 1970 = 550 s

    Theil-Sen (principal)   361,6 s/dia   1,52 d   ->  2026-09-16 03:36Z
    minimos cuadrados       352,7         1,56     ->  2026-09-16 04:31Z
    dos puntos (diagnostico)374,1         1,47     ->  2026-09-16 02:23Z

    RANGO por eleccion de estimador      09-16 02:23Z .. 09-16 04:31Z
    SENSIBILIDAD quitando el ultimo ciclo                09-16 09:04Z

**CONFIANZA: BAJA-MEDIA.** El rango entre estimadores es estrecho (2 h) pero engañoso: la
sensibilidad real —quitar un punto, o cambiar la ventana— es de 5-6 h, y la pendiente ha
crecido monótonamente con cada ventana nueva.

**Supuestos:** (1) la relación `espera ≈ ciclo − 1620` se mantiene (medida con sesgo +12,4 s);
(2) `PMW_LOCK_WAIT` sigue en 900 s; (3) el crecimiento de filas sigue lineal; (4) no aterriza
ninguna optimización — el 09-13 aterrizó una y bajó el nivel de golpe.

---

## 19 · SIGUIENTE OBSERVACIÓN NECESARIA

**El `decide 02:40` del 2026-09-15 y el `collect 03:07` que le sigue** (empuje esperado
~03:40Z). Extraer, del identificador y la ranura: duración, espera derivada, `discover`,
`load:markets`, `collect:books`, filas, MB, ms/fila, veredicto del vigilante, `lock_timeout`
si lo hubiera, y `code_commit`. Clasificar con §4 **sin retocarlo**.

## 20 · DECISIÓN OPERATIVA

> ### `GAP OPERATIVO`

**No existe procedimiento escrito** para AVISO (>300 s), ALARMA (>600 s), ranura perdida ni
riesgo de solapamiento. Lo único que hay es la **emisión** del evento `lock_timeout` en
`launcher.sh:88` — un registro, no una acción.

**No lo invento retrospectivamente.** Queda registrado como hueco, y la decisión de qué hacer
al cruzar un umbral corresponde al usuario.

**Nada de este análisis autoriza L2, paper trading, trading real ni cambio alguno de
estrategia, ciudad, modelo o umbral.** Es exclusivamente capacidad y operación del sistema de
investigación.
