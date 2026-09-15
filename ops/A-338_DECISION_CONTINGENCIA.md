# A-338 — Decisión de contingencia antes del `decide` 02:40Z del 16-09

**Fecha:** 2026-09-15 · **Autor:** Claude (sesión A) · **Naturaleza:** auditoría de palancas
reales. **No se ejecuta nada.**

```
NO EXISTE MITIGACIÓN AUDITADA DISPONIBLE
```

La respuesta a la pregunta final del encargo es negativa, y este documento demuestra por qué
en vez de afirmarlo. Por el camino aparece **dónde está realmente el coste**, que hasta hoy
figuraba en mis propios informes como «medido pero no explicado».

---

## 1 · Estado actual

| ciclo | duración | espera del collect posterior |
|---|---|---|
| 09-15 02:40 (decide) | 2219,4 s | 612 s → **1ª ALARMA** (A-327 = ALARMA) |
| 09-15 06:07 | 2366,8 s | 5 s |
| 09-15 09:07 | 2489,1 s | 5 s |
| 09-15 11:40 (decide) | 2385,4 s | 778 s → **2ª ALARMA** |
| 09-15 12:19 | 2439,2 s | — |
| **09-15 15:07** | **2612,8 s** | — |

**0 ranuras perdidas.** Cobertura completa, 57 ciclos.

---

## 2 · Umbral exacto de pérdida — derivado, no recordado

Reconstruido **sólo** con `cycle_started_at` y `recorded_at` de los shards:

```
espera(collect) = (decide_ini − ranura_decide) + duracion(decide) + traspaso − HUECO
pérdida ⟺ espera ≥ ESPERA_MAX
        ⟺ duracion(decide) ≥ ESPERA_MAX + HUECO − offset_decide − traspaso
```

Los ocho pares `decide → collect` reales del régimen:

| ranura | decide inicio | decide fin | dur | collect inicio | espera | traspaso |
|---|---|---|---|---|---|---|
| 02:40 | 09-12 02:40:05,954 | 03:01:03,294 | 1257,3 | 03:07:05,114 | 5,1 | (ocioso 361,8) |
| 11:40 | 09-12 11:40:05,406 | 12:09:12,836 | 1747,4 | 12:09:19,587 | 139,6 | **6,75** |
| 02:40 | 09-13 02:40:05,907 | 03:03:55,528 | 1429,6 | 03:07:05,654 | 5,7 | (ocioso 190,1) |
| 11:40 | 09-13 11:40:06,765 | 12:04:34,732 | 1468,0 | 12:07:05,866 | 5,9 | (ocioso 151,1) |
| 02:40 | 09-14 02:40:06,255 | 03:08:28,007 | 1701,8 | 03:08:34,880 | 94,9 | **6,87** |
| 11:40 | 09-14 11:40:05,942 | 12:10:51,651 | 1845,7 | 12:10:59,157 | 239,2 | **7,51** |
| 02:40 | 09-15 02:40:05,971 | 03:17:05,368 | 2219,4 | 03:17:12,412 | 612,4 | **7,04** |
| 11:40 | 09-15 11:40:05,492 | 12:19:50,917 | 2385,4 | 12:19:58,044 | 778,0 | **7,13** |

`traspaso` sólo existe como magnitud cuando el decide invade la ranura: **cinco
observaciones, 6,75–7,51 s**. Cuando no la invade, el hueco es ocio, no traspaso — y
confundir ambos sería medir otra cosa.

`offset_decide` (arranque menos ranura): **5,41–6,77 s** en los ocho.

    umbral = 900 + 1620 − offset − traspaso
           ∈ [900+1620−6,77−7,51 ,  900+1620−5,41−6,75]
           = [2505,7 ; 2507,8] s

**UMBRAL = 2506–2508 s.** Toda la incertidumbre del umbral son 2 segundos.

---

## 3 · Evidencia observada: hecho, condición necesaria, incertidumbre

**HECHO.** El último ciclo medido duró **2612,8 s**, es decir **105 s por encima del
umbral**. El último *decide* duró 2385,4 s, 122 s por debajo. Entre ambos hay 3,5 h.

**CONDICIÓN NECESARIA para NO perder la ranura.** Que `duracion(decide 02:40Z) < ~2507 s`.
Eso exige que un decide que hace 15 h duraba 2385,4 s **no crezca más de 122 s**, cuando el
crecimiento medido entre los dos últimos decides (02:40 → 11:40, 9 h) fue de **+166 s**. No
basta con que la tendencia se aplane: tiene que **invertirse**.

**INCERTIDUMBRE.** La serie no es monótona. La mayor excursión a la baja observada en el
régimen es **−104 s** (09:07 → 11:40). Para salvar la ranura haría falta que el decide de
las 02:40 quede ~155 s por debajo de su propia tendencia — **~1,5 veces la mayor excursión
a la baja jamás observada**, y sostenida hasta esa hora concreta.

Formulación exacta, sin predicción: **el sistema está en una zona en la que un `decide` de
duración comparable al último observado agotaría el presupuesto del `collect` post-decide.**

**La pendiente NO es el argumento.** Se menciona sólo como contexto (Theil-Sen +401 s/día,
OLS +418). El argumento es que **el nivel ya medido supera el umbral**.

---

## 4 · Dónde está el coste — lo que esta auditoría encontró

Mis informes anteriores decían «las etapas conocidas suman 203 s, el 9 % del ciclo; el 91 %
restante queda sin explicar». **Eso era falso, y la culpa es mía**: no estaba sin explicar,
es que yo sólo había listado tres etapas de las treinta y dos. El perfil completo del ciclo
de las 15:07:

| etapa | s | % |
|---|---|---|
| **`load:orderbook_snapshots`** | **1495,8** | **57,2 %** |
| **`load:price_history`** | **768,7** | **29,4 %** |
| `load:markets` | 126,4 | 4,8 % |
| `load:outcomes` | 106,0 | 4,1 % |
| `discover` | 66,9 | 2,6 % |
| `collect:books` | 45,8 | 1,8 % |
| las otras 26 etapas juntas | 3,2 | 0,1 % |

**Dos cargas son el 86,6 % del ciclo. El trabajo útil —descubrir mercados y capturar el
book— es el 4,4 %.**

### La causa, y está escrita en el propio código

`paper_cycle.py:2386` abre `db.connect(args.db or ":memory:")`, y el host **no pasa `--db`**
(`run_cycle.sh` no lo incluye en `ARGS`). Así que cada ciclo reconstruye **toda** la base en
RAM desde todos los shards. El docstring de `store.load_shards` lo dice sin rodeos:

> «It is also the HOT path: `paper_cycle` opens `:memory:`, so every cycle rebuilds the
> entire store from scratch before it can do anything, **and the store only grows**.»

Y `rebuild()` recorre `STATE_TABLES` entero, incondicionalmente: sin filtro, sin `since`, sin
depender de `--collect-only`.

La razón original está documentada y era correcta: «an Actions runner starts with an empty
disk, so this is where continuity actually comes from». **Pero ese host ya no existe.** El
sistema corre desde el 09-09 en un Hetzner con disco persistente. Es un diseño que sobrevivió
a la máquina para la que se escribió — el mismo patrón que D-4, D-5 y D-6.

**Esto es un diagnóstico, no una palanca.** Ver §5.

---

## 5 · Palancas disponibles — tabla completa

| Intervención | ¿Reduce duración? | ¿Reduce espera? | ¿Evita la pérdida? | ¿Auditada? | ¿Gobernada? | ¿Requiere deploy? | ¿Contamina evidencia? |
|---|---|---|---|---|---|---|---|
| **`--db <ruta>` persistente** | **NO por sí sola** | no | no | no | no | sí | sí |
| **Carga incremental** (pasar sólo shards nuevos a `load_shards`) | sí, potencialmente mucho | sí, por consecuencia | probablemente | **NO** | **NO** | sí | sí |
| **#61 (parche de 2 líneas)** | **no** | **no** | **no** | sí (A-331) | sí | sí | sí |
| **subir `PMW_LOCK_WAIT`** | no | **no** | «evita el timeout», no la contención | n/a | **prohibido** | sí | sí |
| **cambiar el cron** | no | sí, moviendo la contención | sí, trivialmente | no | **prohibido** | sí | sí |
| **`--horizon-days` / `--max-pages`** | sólo sobre `discover` (2,6 %) | no | **no** | no | no | sí | sí |
| **#55 compactación** | sí en teoría | — | desconocido | **NO** | **NO** | sí | sí |
| **#30 backfill** | **no** (es de datos, no de coste) | no | no | n/a | n/a | — | — |

### Por qué `--db` persistente **no** es la palanca que parece

Es la primera idea al leer §4, y es incorrecta. `load_shards` es **idempotente** —
«replaying the whole store over a populated database changes nothing» — pero idempotente
**no es gratis**: sigue **leyendo todos los shards**. Una base persistente ahorraría el
`upsert`, no la lectura, y la lectura es el coste. Su firma acepta `paths`, así que un
llamante *podría* pasar sólo los shards nuevos — pero **nadie calcula ese conjunto hoy**.
Esa lógica no existe.

Detectar esto es lo que separa una auditoría de una corazonada: la opción existe en el
argparse, es tentadora, y **no resuelve el problema**.

---

## 6 · Palancas descartadas, con su razón

**#61 — FUERA DE LAS MITIGACIONES, EXPLÍCITAMENTE.** Su parche (dos líneas, §6 de A-331)
exporta `PMW_LOCK_WAIT` y lo registra en `cycle_params`. **No acorta el ciclo ni un
segundo.** Mejora la observabilidad de una configuración; no toca el coste. Presentarlo como
mitigación de capacidad sería confundir el defecto que estaba abierto con el problema que
acaba de aparecer. **No hay ninguna parte de #61 que reduzca este riesgo.**

**`PMW_LOCK_WAIT` — NO ES UNA MITIGACIÓN DE CAPACIDAD.** Subirlo evitaría el `lock_timeout`,
sí. Pero **no hace que el `collect` llegue antes**: convierte una pérdida explícita —
registrada, con evento `lock_timeout` y `TURNO PERDIDO` en el vigilante— en una espera más
larga y silenciosa, y el book se captura igualmente tarde. Cambia la *contabilidad* del
fallo, no el fallo. Además viola el freeze. **No se toca.**

**CRON — qué pasaría, y por qué no.** Separar el `decide` del `collect` (p. ej. mover el
decide a 02:00, o el collect a 03:37) eliminaría la contención de inmediato, porque el
problema es geométrico: `HUECO = 1620 s` y el ciclo dura más que eso. Dependencias: el
`decide` a 02:40 y 11:40 está atado a `t_asof` 03:00/12:00 y por tanto a `lead_effective_h`
y a la ventana de mercado; moverlo cambia **qué pronóstico se usa para decidir**, que es
materia de R24 y de preinscripción, no de operación. Gobernanza: cambiar el cron durante la
prueba requiere **autorización explícita del usuario**. **No se hace.**

**#55 y #30 — no se presenta estimación de ahorro.** #55 (compactación / `ingestion_timestamp`)
apunta a la zona correcta según §4, pero **no tiene benchmark, ni test, ni revisor
independiente** (§34 bloqueado por #81), y su nota dice que `newest_first` ya redujo el
*upsert* sin saltarse la *lectura* — es decir, ataca la mitad que no cuesta. #30 es de
cobertura de datos, no de coste. **Sin evidencia suficiente, no doy una cifra de ahorro**,
que es exactamente lo que pide el §8 del encargo.

---

## 7 · Riesgos de intervenir

A-327 **ya terminó**, así que una intervención ahora no puede contaminarla. Pero sí
contaminaría:

- **la observación de la degradación natural** — la serie de 26 puntos desde el 09-13
  perdería su continuidad justo en el punto donde por fin es informativa;
- **la estimación de capacidad** — cualquier ahorro se confundiría con la tendencia;
- **la interpretación de los siguientes ciclos** — un ciclo más corto mañana no se podría
  atribuir.

Cualquier intervención debe etiquetarse **`POST-A-327 INTERVENTION`** y su serie posterior
**no debe mezclarse** con la anterior. Es una costura declarada, igual que las dos que
`load_shards` ya documenta en `rows_written`.

Y el riesgo específico de intervenir **esta noche**: un cambio en la ruta caliente,
desplegado sin test ni revisor, a pocas horas de la ranura, sobre el código que el host
reinstala con `git reset --hard origin/main` en cada ciclo. Un fallo ahí no pierde una
ranura: las pierde **todas**.

---

## 8 · Opciones

### OPCIÓN A — NO INTERVENIR *(recomendada)*

Mantener el freeze y observar el `decide` de las 02:40Z.

**Consecuencia esperada:** riesgo elevado de perder el `collect` de las 03:07Z. Se perdería
una instantánea del book, irrecuperable. Quedaría **registrada**: `lock_timeout` con el
`waited_s` efectivo (primera vez que D-3 sería observable), `TURNO PERDIDO` en el vigilante,
y `ranuras juzgables sin fila = 1`.

**Lo que se gana:** la serie sigue limpia, el diagnóstico de §4 queda confirmado o refutado
por el dato, y la primera pérdida real documenta el modo de fallo completo — que es
justamente lo que ningún runbook inventado esta noche podría darnos.

### OPCIÓN B — MITIGACIÓN AUDITADA

**NO EXISTE.** Ninguna fila de la tabla del §5 tiene «auditada = sí» y «reduce duración =
sí» a la vez. La única palanca con potencial real —carga incremental— no está implementada,
no tiene tests, no tiene benchmark y no tiene revisor. **No la invento.**

### OPCIÓN C — CAMBIO DE EMERGENCIA *(descrito, no ejecutado)*

- **Qué se cambia:** lo más pequeño con efecto geométrico cierto sería mover la ranura del
  `collect` post-decide, o el `decide`, para separarlos más de 1620 s.
- **Por qué:** elimina la contención sin tocar el coste, y su efecto es aritmético, no
  estimado.
- **Qué evidencia se pierde:** la serie de espera post-decide —11 puntos, la única que mide
  la contención— queda cortada; y con ella la posibilidad de observar el modo de fallo.
- **Qué riesgo introduce:** mover el `decide` cambia `t_asof` y por tanto **qué pronóstico
  decide**, materia de R24 y de preinscripción. Mover el `collect` desalinea la rejilla de
  3 h del book. Un cambio de cron sin test aplicado de noche puede detener el horario entero
  — el modo de fallo que `launcher.sh` documenta como el peor.
- **Quién debe autorizarlo:** el usuario, explícitamente. No yo.

---

## 9 · Recomendación técnica

**OPCIÓN A.** Y no por inercia ni por obediencia al freeze, sino porque las otras dos son
peores esta noche:

1. **No hay nada auditado que desplegar.** Todo lo que reduciría la duración es código que
   habría que escribir ahora, sobre la ruta caliente, sin revisor.
2. **El coste de la pérdida es una instantánea del book; el coste de un despliegue fallido
   es el horario completo.** Los dos son irrecuperables, pero no del mismo tamaño.
3. **La pérdida es informativa.** Confirmaría o refutaría la geometría del §2 con un dato,
   revelaría el `PMW_LOCK_WAIT` efectivo (D-3) y ejercitaría por primera vez la ruta de
   `lock_timeout` — que hasta hoy sólo está probada en tests.

Lo que **sí** recomiendo preparar, para cuando el usuario levante el freeze y con revisión:
atacar `load:orderbook_snapshots` + `load:price_history` (86,6 %) por carga incremental. Ahí
está el problema, y es estructural: un diseño correcto para un runner efímero, ejecutándose
en un host persistente.

---

## 10 · Decisión que requiere Ander

> **¿Opción A (no intervenir y observar), o autorización explícita para un cambio de
> emergencia bajo Opción C?**

No ejecuto ninguna de las dos sin que lo digas. Si no hay respuesta antes de las 02:40Z, se
aplica **A por omisión**, que es el estado actual del sistema: freeze y observación.

---

## 11 · Qué permanece congelado

`A-327 = ALARMA` (final) · umbrales 300/600 · predicción 524/2144 · Theil-Sen, MAD×1,4826,
3,5×, ventana de 8 · 1620 / 2520 / `PMW_LOCK_WAIT` 900 · el cron · `vigila_colector.py` ·
`evalua_a327.py` · `install.sh`, `launcher.sh`, `paper_cycle.py` · **#61 BLOCKED** ·
**D0-P BLOCKED** · **L2 BLOCKED** · B congelado en `c03e2d0` · SettlementOperator y R24
congelados.

**Defectos abiertos, ninguno corregido:** D-3 (override de entorno de `PMW_LOCK_WAIT`),
D-4 (shard dañado → «TURNO PERDIDO»), D-5 (`salud_pre_medicion.sh` confunde alarma con
fallo), **D-6 (`OPEN / DETECTION CORRECT, PRESENTATION INCORRECT`** — con holgura negativa el
vigilante imprime una fecha en el pasado; **no se usa esa fecha para nada en este documento**,
el dato correcto es la relación del §2).

**`GAP OPERATIVO`** sigue registrado y sin rellenar: no hay runbook, y no se escribe uno bajo
la presión de la primera alarma.
