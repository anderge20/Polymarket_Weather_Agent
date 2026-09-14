# A-332 — Merge de #58, verificación y congelación hasta A-327

**Fecha:** 2026-09-14 · **Autor:** Claude (sesión A, perfiles desarrollador y validador)
**Encargo:** «D16 → MERGE #58 → FREEZE → EVALUACIÓN PROSPECTIVA A-327»
**Predecesores:** A-329 (punto ciego), A-330 (auditoría), A-331 (`#61 BLOCKED`)

```
#58 MERGED — VERIFIED     A-327 FROZEN     #61 BLOCKED
A-327 PENDING             SYSTEM FROZEN
```

---

## 1 · A-112 — las tres resoluciones, tomadas AL DISPARO

Recomprobadas a las **20:08:12Z**, con la ventana D16 ya abierta (la entrada A-331 se
escribió a las 18:07:21Z; ventana ≥ 2 h ⇒ 20:07:21Z).

| resolución | valor |
|---|---|
| `isDraft` | `false` |
| `headRefOid` | `1f8a8e38a275574affbcade18b89f26ca7281904` |
| SHA revisado | `1f8a8e38…` — **el mismo** |
| SHA que corrió la suite | `1f8a8e38…` — **el mismo** |
| `mergeable` | `MERGEABLE / CLEAN` |
| working tree | limpio |
| alcance | `tests/test_configuracion_operacional.py`, y nada más |
| `origin/main` | `1584045826fa…`, **sin moverse** desde la predicción |

Las tres resoluciones son la misma pregunta hecha tres veces: *¿lo que voy a fusionar es lo
que verifiqué?* Mover la rama habría reiniciado la ventana; no se movió.

---

## 2 · Padres reales

| | |
|---|---|
| **padre 1** | `1584045826fa6db64ca7ae4f9b022f081394fd7c` |
| **padre 2** | `1f8a8e38a275574affbcade18b89f26ca7281904` |
| **merge SHA** | `22a77200e9f4aaf17d6cb3c82f681daa9c791168` |
| **árbol de fusión** | `3cc7269608553f4f14cc7687b8e5445a2892e80f` |

El árbol de fusión coincide **byte a byte** con el árbol probado localmente antes de
fusionar (`c427aaa`, construido con `git merge --no-ff`). Es decir: la suite que corrí
antes del merge cubría exactamente el contenido que aterrizó.

Método: **commit de fusión**. Ni squash, ni rebase, ni cherry-pick, ni retoque posterior.

---

## 3 · A-119 — la predicción, derivada de los padres

```
EXPECTED_TESTS = 754  (padre 1, MEDIDO en ese árbol exacto)
               +   4  (colectados con `pytest --collect-only` del fichero que añade el padre 2)
               −   0  (el diff es `1 file changed, 129 insertions(+)`: cero borrados)
               = 758
```

El 754 **no se copió de la rama ni de la memoria**: se midió corriendo la suite completa
sobre `1584045` a las 18:14Z. Eso es lo que A-119 exige y es la diferencia entre predecir y
recordar. Se comprobó además que ningún test enumera el directorio `tests/`, así que la
cuenta es aditiva.

---

## 4 · Suite post-merge sobre el SHA REAL

```
pytest sobre HEAD = 22a77200e9f4aaf17d6cb3c82f681daa9c791168
758 passed in 133.05s
```

**MEDIDO 758 = EXPECTED 758.** Sin discrepancia, y por tanto sin nada que reinterpretar.

### La afirmación, reconstruible sólo con estos datos

> Sobre el commit `22a7720`, cuyo padre 1 es `1584045` (754 tests medidos) y cuyo padre 2 es
> `1f8a8e3` (+4, −0), se predijo 758 antes de ejecutar y se midieron 758.

---

## 5 · Integridad de A-327

`ops/instantanea_a327.sh` genera **el «antes» y el «después» con el mismo código**: si los
produjeran dos textos escritos a mano, el diff compararía mi memoria conmigo mismo.

```
diff A327_ANTES.txt A327_DESPUES.txt   →   sin diferencias
```

| elemento | sha / valor |
|---|---|
| entrada A-327 en `DECISIONS.md` (37 líneas) | `a3a50b2a8a115ecb…` |
| `evalua_a327.py` | `24600ba2ea3f53b4…` |
| `vigila_colector.py` | `de08f738fd57e9fb…` |
| `install.sh` / `launcher.sh` | `69e36585…` / `966069aa…` |
| predicción | duración ~2144 s · espera ~524 s |
| objetivo | decide **2026-09-15 02:40Z** → collect **03:07Z** |
| criterio | AVISO 300 · ALARMA 600 |
| derivados | RANURAS(10) · HUECO 1620 · ESPERA_MAX 900 · HOLGURA 2520 |

**`A-327 UNCHANGED`.** El diff se tomó *después* de sincronizar `wt-main` a `origin/main`
post-merge, así que la igualdad no se debe a mirar un checkout viejo.

---

## 6 · El host: qué está verificado y qué no

`ops/salud_pre_medicion.sh` → **SANO** (exit 0). Pero conviene decir exactamente qué prueba
y qué no, porque la tentación es leerlo como más de lo que es: ese script compara **mi
checkout** con `origin/main`. Eso no es evidencia del host.

**La evidencia del host existe, y la escribe el host.** `cycle_params` lleva un campo
`code_commit`:

| ciclo | `code_commit` |
|---|---|
| `col_20260914T121059Z` | `1584045826fa` |
| `col_20260914T150705Z` | `1584045826fa` |
| `col_20260914T180705Z` | `1584045826fa` |

`1584045826fa` era `origin/main` en ese momento. Clasificación del §6:

| afirmación | clasificación |
|---|---|
| «el host ejecutaba `1584045` hasta el merge» | **`HOST_SHA_VERIFICADO`** — por evidencia producida por el host |
| «el host ejecutará `22a7720`» | **`HOST_SHA_NO_VERIFICABLE`** — todavía no existe el ciclo que lo probaría |

No se promueve la segunda a la primera. La evidencia llegará sola en el `collect` de las
**21:07Z**, que será el primer ciclo posterior al merge: su `code_commit` debe decir
`22a77200e9f4`. Si dijera otra cosa → `HOST_SHA_INCONSISTENTE` y hay que pararse.

La ausencia de evidencia **no bloquea**: el ciclo sigue siendo observable por el resto de
mecanismos (shards, ranuras, esperas), que es lo que A-327 necesita.

### Por qué esto importa: la tercera puerta de #61

El vigilante deriva sus constantes de un **checkout local** (`PMW_REPO`), y el host ejecuta
`origin/main`. Nada garantizaba que coincidieran — `wt-main` estaba **6 commits por
detrás**, y sus `ops/hetzner/*` resultaron idénticos **por suerte, no por construcción**.
No es duplicación (A-331 la cerró) ni override de entorno (D-3): es una **ref rancia**, y
es la única de las tres que se puede neutralizar sin tocar nada, comprobándola. Hecho:
`wt-main` sincronizado a `22a7720`, y la comprobación vive en el script de salud.

---

## 7 · Mutaciones post-merge — los dos bancos

Reconstruidos **como código**, no como anécdota: los dos se habían corrido a mano y se
volvían a montar cada vez. Un banco que hay que remontar no es reproducible.

### `ops/mutaciones_61.py` — **7/7 como se predijo**

| mutación | suite | vigilante |
|---|---|---|
| control | pasa | pasa |
| R2 · `7 */3` → `9 */4` | **falla** | **levanta** |
| H2a · uno de tres a 1800 | **falla** | **levanta** |
| H2b · los tres a 1800 | **falla** | pasa |
| TZ-a · borrar la guarda | **falla** | pasa |
| TZ-b · renombrar el binario | **falla** | pasa |
| TZ-c · degradar `exit 1` → `true` | **falla** | pasa |

La predicción está escrita **dentro del banco**, antes de correrlo.

### `ops/regresion_a329.py` — **10/10**

shard presente · shard antiguo ausente (+ `main()` exit 1) · dos ausentes · ranura reciente
**en vuelo, no perdida** · almacén inexistente · almacén vacío · shard ilegible por permisos
· gzip corrupto · **id corrupto en shard antiguo = D-4 reproducido intacto**.

### Regla que ahora es del banco, no de mi atención

> **Toda mutación tiene que demostrar primero que muta.** Una mutación no-op produce
> exactamente la misma salida que un arreglo.

Nació de un error mío: muté `"session_id": "col_` **con espacio** y el JSON real no lo
lleva. Cero sustituciones, exit 0, y estuve a punto de anotar «D-4 ya no reproduce». Es la
tercera vez en esta sesión que una mutación no muerde (las otras: el marcador del crontab y
el `in` de subcadena sobre `timedatectl`). Ahora `_muta_gz` levanta si el patrón no aparece.

### Y el otro error, del mismo tipo

El caso 4 «falló» porque congelé el `ahora` **a mano** a las 18:00Z: con el último ciclo a
las 15:07 y un margen de ~7.000 s, esa ranura ya estaba perdida — el instrumento tenía
razón y mi fixture había envejecido. Es el mismo fallo que ya cometí en A-330, por otra
puerta. Ahora el `ahora` **se deriva del banco** (último ciclo + 600 s), y se ha visto
funcionar: en la corrida post-merge se movió solo a 18:17Z.

---

## 8 · Estado de #61: **BLOCKED**

El merge **no** cierra #61. Lo que #58 aporta son las guardas del **repositorio**:
detectan divergencia de `RANURAS` y de `PMW_LOCK_WAIT` **en el fichero**.

Lo que sigue abierto: `launcher.sh` usa `${PMW_LOCK_WAIT:-900}` sin exportarlo, y
`cycle_params` (**36 campos** — ninguno lleva `lock` ni `wait` en el nombre) no registra el
valor efectivo. Un `export PMW_LOCK_WAIT=1800` en el host cambia el comportamiento real y
no queda garantizado de forma prospectiva **antes de que ocurra un timeout**.

El parche está escrito entero en el §6 de A-331 (dos líneas) y **no se despliega ahora**:
`launcher.sh:98-104` hace `git reset --hard origin/main` al principio de cada ciclo, así
que fusionar algo que el host *ejecuta* es desplegarlo antes de la medición.

### Corrección de una cifra que publiqué mal

En A-331, en el docstring del test, en el commit y en el PR escribí que `cycle_params`
tiene **35** campos. Tiene **36**. La conclusión no cambia —ninguno es el valor efectivo
del lock— pero el número citado no cuadraba con el dato, que es justo lo que llevo toda la
sesión señalando en otros sitios. **No se corrige el fichero ahora**: tocarlo movería
`headRefOid` y reiniciaría la ventana D16 la víspera de la medición. Un error de un campo
no justifica eso. Queda aquí y se arregla al levantar el freeze.

---

## 9 · H2b — dos garantías distintas, no una contradicción

| | cambiar los tres `PMW_LOCK_WAIT` a 1800 coherentemente |
|---|---|
| **vigilante** | **pasa**. Es fuente única: relee, recalcula `HOLGURA = 1620+1800 = 3420` y sigue midiendo bien |
| **suite** | **falla**. La guarda fija el valor contratado en 900 |

El encargo esperaba que H2b pasara; pasa en el instrumento y falla en la suite, **a
propósito**. No se tocó el test para que encajara con la expectativa.

Son dos garantías que viven en sitios distintos:

- **coherencia interna de la configuración** — la ejerce el vigilante: que las tres copias
  digan lo mismo y que lo derivado siga a lo declarado;
- **invariancia del contrato operacional** — la ejerce la suite: que el horario contratado
  no se desplace **en silencio**.

La palabra que decide es *silencio*. Un cambio coherente sigue siendo un cambio de
configuración operacional, y tiene que aparecer en el diff de alguien: la forma de hacerlo
es actualizar `ESPERA_LOCK_ESPERADA` a la vez, que es precisamente el rastro deliberado que
la guarda existe para forzar. Si la suite lo dejara pasar, el criterio 2 del §17 de A-331
quedaría vacío.

**No se resuelve ahora.** Es una decisión de gobernanza, no un defecto.

---

## 10 · FREEZE

Desde este documento y hasta que `ops/evalua_a327.py` devuelva `exit 0`:

**Congelado:** `A-327` · `evalua_a327.py` · `vigila_colector.py` · Theil–Sen · MAD×1,4826 ·
3,5× · la ventana de 8 · los umbrales 300/600 · 1620 · 2520 · el cron · `PMW_LOCK_WAIT` ·
`install.sh` · `launcher.sh` · `paper_cycle.py` · settlement · R24 · L2 · estrategia.

**No se abre** ningún PR. **No se arregla** el mensaje engañoso del shard dañado (D-4). No
se «aprovecha la espera» para nada.

**Única actividad permitida:** `ops/salud_pre_medicion.sh`, que es read-only — no modifica
código, configuración ni datos, no reinicia nada, no toca el cron ni el entorno y no ejecuta
el ciclo a mano. Si devolviera `FAIL`: registrar el motivo y **parar**, sin corregir.

---

## 11 · El dato que importa

**A-327 = `PENDING`.** No `INDETERMINADA`: *pendiente* y *indeterminado* no son lo mismo, y
`evalua_a327.py` los distingue con `exit 2` frente a `exit 1`.

El objetivo es **exactamente** `decide 2026-09-15 02:40Z → collect ~03:07Z`. No se sustituye
por el ciclo de las 18:07 del 14, ni por el de las 21:07, ni por ningún otro.

Cuando exista, y sólo entonces:

```
python3 ~/pmw-e2/ops/evalua_a327.py
```

sin tocar argumentos ni código, guardando la salida completa. Criterio congelado:
`300 ≤ espera < 600` **CONFIRMADA** · `< 300` **FALLIDA** · `≥ 600` **ALARMA** ·
**INDETERMINADA** sólo si hay un defecto real de medición — nunca porque el resultado
incomode.

Y en tres bloques separados, en este orden y sin mezclarlos:
**A** ¿acertó la predicción? · **B** ¿sigue la tendencia de capacidad? · **C** ¿qué implica
operativamente? B no reinterpreta A. C no reinterpreta A. Acertar A **no** valida la fecha
de pérdida de capacidad: eso necesita evidencia independiente.

---

## 12 · Lo que aprendí en esta ventana

1. **Una mutación puede no mutar**, y entonces se parece mucho a un arreglo. El banco lo
   comprueba ahora; mi atención no bastaba, tres veces seguidas.
2. **Una fixture escrita a mano caduca sola.** La fecha del banco sale del dato.
3. **Un checkout puede quedarse atrás**, y que los ficheros coincidan puede ser suerte.
4. **El campo que ya se escribe vale más que el instrumento que ibas a construir**:
   `code_commit` convirtió «no puedo verificar el host» en evidencia del propio host.
5. **Una cifra citada que no se recalcula no es un dato, es una cita** — 35 campos frente a
   36, otra vez, y esta vez en algo que yo mismo había publicado.

---

**Estado final:** `#58 MERGED — VERIFIED` (`22a7720`, 758 verdes) · `A-327 UNCHANGED` ·
`A-327 PENDING` · `#61 BLOCKED` · `HOST_SHA_VERIFICADO` hasta el merge, `NO_VERIFICABLE`
para `22a7720` hasta las 21:07Z · **SYSTEM FROZEN**.
