# A-331 — Resolver #61 sin contaminar A-327, y congelar hasta la prueba prospectiva

**Fecha:** 2026-09-14 · **Autor:** Claude (sesión A, perfiles desarrollador y validador)
**Encargo:** «RESOLVER #61 SIN CONTAMINAR A-327 Y CONGELAR EL SISTEMA HASTA LA PRUEBA
PROSPECTIVA» · **PR:** #58 · **Predecesores:** A-328 (predicción), A-329 (punto ciego),
A-330 (auditoría pre-prospectiva, donde #61 quedó abierto)

---

## VEREDICTO

```
#61 BLOCKED
```

Una sola etiqueta, como pide el §17. Y hay que decir de qué está bloqueado, porque no es
de lo que parece: **no falta saber cómo arreglarlo, ni falta código.** El arreglo son dos
líneas y están escritas en el §6 de este documento. Lo que lo bloquea es el propio encargo:
§16 y §24 congelan la configuración operacional hasta la medición del 2026-09-15, y la
mitad que queda **sólo** se arregla tocando lo que el host ejecuta.

La regla de oro del §24 es la que decide:

> ¿Podemos eliminar la divergencia de configuración sin cambiar el instrumento que mañana
> debe medir la predicción?

- Para la mitad de **duplicación**: sí. Hecho, y con la salida byte a byte idéntica.
- Para la mitad de **override de entorno**: no. Y por tanto no se hace.

Y la segunda frase del §24, que es la que impide maquillar esto como un cierre:

> descubrirlo antes del dato es una victoria; corregirlo para que el dato salga mejor sería
> contaminar la prueba.

---

## §1 · Qué estaba roto, y cómo se demostró

A-330 no lo dedujo leyendo: lo demostró mutando. Cuatro mutaciones, cuatro veces verde.

| # | mutación | suite ANTES | vigilante ANTES |
|---|---|---|---|
| R1 | añadir una ranura al crontab | verde | ciego a la nueva |
| R2 | `7 */3` → `9 */4` | **verde** | sigue esperando las ranuras viejas |
| H1 | añadir un cuarto `PMW_LOCK_WAIT:-` con otro valor | verde | ni se entera |
| H2 | `PMW_LOCK_WAIT:-900` → `:-1800` | **verde** | sigue calculando `HOLGURA = 2520` |

La causa estructural: `ops/vigila_colector.py` llevaba `RANURAS` y `ESPERA_MAX` **copiadas**
como literales de `install.sh` y `launcher.sh`. Dos ficheros afirmando lo mismo, nada
comparándolos. Y `PMW_LOCK_WAIT` no tenía *una* definición: era un default de shell
repetido **tres veces en el mismo fichero** — tres literales iguales por costumbre no son
una definición, son tres oportunidades de divergir.

El efecto no es «un número desactualizado». Es que el instrumento mediría contra un
horario que ya no existe: **alarmaría por ranuras que cron no dispara y sería ciego a las
que sí**. Las dos direcciones del mismo agujero, y ninguna de las dos se anuncia.

---

## §2 · Remedio 1 — fuente única (corpus, fuera del repo)

`ops/vigila_colector.py` ya no lleva literales. Deriva:

```python
RANURAS   = _ranuras_del_crontab(f"{REPO}/ops/hetzner/install.sh")
ESPERA_MAX = _espera_max_del_launcher(f"{REPO}/ops/hetzner/launcher.sh")
HUECO     = _hueco_decide_collect(RANURAS)   # 1620.0
HOLGURA   = HUECO + ESPERA_MAX               # 2520.0
```

Tres decisiones que merecen justificarse:

**a) El parser de cron reconoce las líneas por lo que SON, no por dónde están.** La versión
obvia delimita por los marcadores `>>> pmw paper mode >>>`. No sirve: esas cadenas aparecen
**dos veces cada una** — al definir `BEGIN=`/`END=` y al expandirlas dentro del heredoc — y
un `re.search` no codicioso casa el **hueco vacío entre las dos definiciones**, devolviendo
cero ranuras sin quejarse. Lo descubrí porque el parser devolvió un conjunto vacío; si
hubiera devuelto algo plausible, no lo habría descubierto.

**b) Cero ranuras es un error, no un resultado.** `raise RuntimeError`. Un vigilante que
arranca sin saber qué ranuras espera no vigila nada, y lo haría en silencio.

**c) Defaults discrepantes es un error, no un promedio.** Si los tres `PMW_LOCK_WAIT:-`
no coinciden, el script **se niega a arrancar**:

```
PMW_LOCK_WAIT tiene defaults DISTINTOS: ['900', '1800']
```

No elige el primero, ni el máximo, ni el más frecuente. Cualquiera de esas tres políticas
convierte una incoherencia en un número, y un número no se puede auditar hacia atrás.

### La prueba de que esto no contamina A-327

`HOLGURA` sigue valiendo **2520 s** y la salida del vigilante es **byte a byte** la de
antes del cambio (hizo falta un `{HOLGURA:.0f}` para que lo fuera: derivarlo lo convirtió
en `float` y el formato cambió de `2520` a `2520.0`. Un dígito de diferencia habría bastado
para que «byte a byte» fuera una afirmación falsa que yo mismo había escrito).

Esto es el requisito, no un detalle de estilo: el 2026-09-15 este script mide la predicción
de A-327. Refactorizarlo la víspera **sólo** vale si no cambia lo que mide.

### Mutaciones DESPUÉS del remedio

| mutación | antes | ahora |
|---|---|---|
| `M-RANURAS` (`7 */3` → `9 */4`) | `exit=0`, silencio | `exit=1` |
| `M-PMW` (uno de los tres a 1800) | `exit=0`, silencio | `exit=1`, *"defaults DISTINTOS"* |
| `M-PMW-todos` (los tres a 1800) | `exit=0` | `exit=0` ← **correcto** |

La tercera fila es la interesante. Cambiar los tres a la vez **debe** pasar: es una fuente
única y un cambio coherente de la configuración, y el vigilante recalcula `HOLGURA = 3420`
y sigue midiendo bien. Una guarda que también prohibiera eso no sería una guarda, sería
una constante con otro nombre.

---

## §3 · Remedio 2 — las guardas que faltaban (PR #58, `tests/`)

`tests/test_configuracion_operacional.py`. Cuatro tests que **no cambian ningún valor**:
fijan el que hay, para que un cambio tenga que ser deliberado y salga en el diff de alguien.

1. **El horario contratado.** `7 */3` collect, `40 2` decide 9, `40 11` decide 24. Todo UTC.
2. **El default del lock, y que los tres sitios digan lo mismo.** Las dos mitades de H:
   el valor, y la coherencia interna.
3. **Que `install.sh` se niegue si el host no es `Etc/UTC`.**
4. **Un test de CARACTERIZACIÓN** que clava el defecto que queda vivo (§5).

### El tercero casi fue inútil, y por qué importa contarlo

Mi primera versión afirmaba `assert "timedatectl" in INSTALL`. Pasa. También pasa después
de renombrar el binario a `NOtimedatectl`, que es exactamente el cambio que rompería la
comprobación. **Un `in` de subcadena no es una aserción sobre lo que el script ejecuta.**

La versión que quedó afirma tres cosas distintas y verificables:

```python
re.search(r"(?<![\w-])timedatectl\s+show\s+-p\s+Timezone", INSTALL)   # la INVOCACIÓN
guarda = re.search(r'\[ "\$TZNAME" = "Etc/UTC" \].*?\|\| \{(.*?)\n\}', INSTALL, re.S)
re.search(r"REFUSING", guarda.group(1))    # se NIEGA
re.search(r"\bexit\s+1\b", guarda.group(1))  # y aborta: un aviso no es una negativa
```

Verificada con tres mutaciones: borrar la guarda, renombrar el binario, y degradar el
`exit 1` a un `echo`. Las tres fallan ahora; las tres pasaban antes.

(Entre medias, un `re.escape` mal puesto produjo un `SyntaxError` que tumbó la colección
entera de la suite. Un test que no compila no es un test que pasa, pero se le parece
mucho en la salida si uno lee sólo la última línea.)

### Verificación

| comprobación | resultado |
|---|---|
| mutación R2 (horario) | `1 failed` |
| mutación H2a (valor del lock) | `1 failed` |
| mutación H2b (uno de tres diverge) | `1 failed` |
| mutación M-TZ ×3 (borrar / renombrar / degradar) | `1 failed` cada una |
| control sin mutar | `4 passed` |
| **suite completa** | **758 passed** |

La cuenta se predijo **antes** de correrla: `main 754 + 4 = 758`. Salió 758.

---

## §4 · Lo que el remedio NO puede alcanzar

Las guardas leen el **fichero**. El host ejecuta un **proceso**. Entre los dos hay una
rendija: `launcher.sh` usa `${PMW_LOCK_WAIT:-900}` sin exportarlo. Un `export
PMW_LOCK_WAIT=1800` en el entorno del host cambia **cuánto espera el lock antes de saltarse
una ranura** — comportamiento real, en la ranura, el día de la medición — y ni la suite ni
el vigilante se enteran, porque los dos leen el fichero, que no ha cambiado.

Es el defecto **D-3** de A-330, y es distinto de la duplicación: la duplicación era
*dos sitios que podían divergir*; esto es *el fichero y la realidad* pudiendo divergir.

---

## §5 · Corrección a mí mismo: el valor efectivo SÍ se registra, en un caso

Escribí — en el test, en el commit y en el cuerpo del PR — que un `export PMW_LOCK_WAIT`
«no deja rastro en ningún sitio». **Es falso**, y lo encontré leyendo `launcher.sh` para
otra cosa:

```sh
# launcher.sh:88, dentro de la rama `if ! flock -w "${PMW_LOCK_WAIT:-900}" 9`
printf '{"event":"lock_timeout",...,"waited_s":%s,...}\n' ... "${PMW_LOCK_WAIT:-900}" ...
```

El valor efectivo se escribe en `lock_timeout.waited_s`, y `stage_host_events`
(`scripts/paper_cycle.py:637`) arrastra la cola hasta un shard y hasta GitHub. Existe el
campo. Existe el transporte.

**Pero sólo por la ruta de timeout.** Por la ruta feliz — el lock se coge, el ciclo corre —
el valor no queda escrito en ninguna parte, y `cycle_params` no lo lleva entre sus 35
campos.

Y al corregirme, el defecto sale **peor** de lo que yo lo había descrito, no mejor:

> El vigilante calcula la `HOLGURA` con el default del fichero y juzga con ella **todos los
> ciclos buenos**. El valor verdadero sólo aparecería en el primer salto — que es
> exactamente el evento que la holgura existe para anticipar. Se entera cuando ya no sirve.

Ésta es, otra vez, la lección que ya tenía escrita y no apliqué: **mirar el campo que ya se
escribe antes de afirmar que no existe ninguno.** La diferencia entre las dos versiones no
es cosmética: la primera describe un agujero, la segunda describe un instrumento que
aprende su propio parámetro demasiado tarde.

---

## §6 · El arreglo que no se hace hoy, escrito entero para que no haya que redescubrirlo

Dos líneas:

```sh
# ops/hetzner/launcher.sh — exportarlo, para que el hijo vea el valor EFECTIVO
export PMW_LOCK_WAIT="${PMW_LOCK_WAIT:-900}"
```
```python
# scripts/paper_cycle.py — registrarlo en cycle_params, igual que se lee PMW_GENERATOR
"lock_wait_s": float(os.environ["PMW_LOCK_WAIT"]),
```

Con el `export` delante, la segunda línea puede usar `os.environ[...]` sin default: si
falta, revienta, y eso es lo correcto — significa que el ciclo no vino por el launcher.
**Repetir el `900` en Python sería reintroducir #61 por la puerta de al lado.**

### Por qué no se hace hoy, verificado y no supuesto

```sh
# ops/hetzner/launcher.sh:98-104
git -C "$REPO" fetch -q origin
git -C "$REPO" reset -q --hard "origin/$REF"     # REF=main por defecto
```

El host hace `git reset --hard origin/main` **al principio de cada ciclo**. Fusionar a
`main` cualquier cosa que el host *ejecute* es desplegarla, y desplegarla en la ranura
siguiente — antes de la medición del 2026-09-15. El §16 lo prohíbe explícitamente.

Por eso el PR #58 toca **sólo `tests/`**: aterriza en el host como todo lo demás y no
cambia una sola línea de lo que el host corre.

### Alternativa considerada y DESCARTADA

El vigilante podría detectar la divergencia sin tocar el host: leer los eventos
`lock_timeout` ya presentes en la serie y negarse si algún `waited_s` no coincide con el
default del fichero. Cambia sólo el corpus, no producción.

**Descartada, y por la regla de oro.** Añade una ruta de negativa nueva al instrumento que
mañana mide A-327. Si esa ruta se dispara — por un evento viejo, por un formato que no
previne, por un error mío del día antes — el vigilante se niega a arrancar **justo el día
de la medición**. Cambiar el instrumento la víspera para cerrar un agujero que hoy no ha
disparado nunca (0 timeouts en 48 ciclos) es exactamente el intercambio que el §24 prohíbe.

Va a la lista de después del 09-15, no a hoy.

---

## §7 · Criterios del §17, uno por uno

| # | criterio | estado |
|---|---|---|
| 1 | La configuración vive en **un** sitio | ✅ el vigilante deriva; no copia |
| 2 | Un cambio unilateral **falla** en la suite | ✅ R2, H2a, H2b, M-TZ×3 |
| 3 | `PMW_LOCK_WAIT` no puede divergir **en silencio** | ❌ **el override de entorno sigue abierto** |
| 4 | El instrumento de A-327 no cambia | ✅ `HOLGURA=2520`, salida byte a byte |
| 5 | Nada se despliega antes de la medición | ✅ el PR toca sólo `tests/` |

Cuatro de cinco. El §17 dice `BLOCKED` si no existe una solución segura sin modificar
configuración operacional. No existe. **`#61 BLOCKED`.**

### La tensión del encargo, dicha en voz alta

El §17 exige el criterio 3 y el §16 prohíbe el único cambio que lo satisface. No es una
contradicción que haya que resolver a favor de uno: es el encargo diciendo, correctamente,
**que hay cosas que no se arreglan la víspera de una medición.** La resolución honesta no
es cumplir el criterio 3 desobedeciendo el §16, ni declarar el criterio 3 cumplido porque
molesta — es `BLOCKED` con fecha de desbloqueo y el parche ya escrito.

---

## §8 · Congelación declarada

Desde ahora y hasta que `ops/evalua_a327.py` devuelva `exit 0` (medición del `decide 02:40Z`
+ `collect 03:07Z` del 2026-09-15):

| congelado | por qué |
|---|---|
| `ops/vigila_colector.py` | es el instrumento de la medición |
| `ops/evalua_a327.py` y sus constantes (2144 / 524 / 300 / 600) | es el criterio, escrito antes del dato |
| `install.sh`, `launcher.sh`, `paper_cycle.py` | el host los ejecuta, y hace `reset --hard origin/main` cada ciclo |
| el cron real y el `PMW_LOCK_WAIT` del host | §16 |
| la predicción de A-327 | inmutable desde que se escribió |
| Theil–Sen, MAD×1.4826, 3.5×, la ventana de 8 | §16 |

Lo único que se permite tocar: documentos, `DECISIONS.md`, y tests que **fijan** lo que ya
hay sin cambiar ningún valor. El PR #58 es exactamente eso.

---

## §9 · Lo que queda abierto, con su nombre

| id | qué | cuándo |
|---|---|---|
| **#87 / D-3** | el override de entorno; parche en el §6, dos líneas | tras el 09-15 |
| **#85** | medir el 09-15 contra A-327 sin retocar la clasificación | 2026-09-15 |
| **GAP OPERATIVO** | no hay runbook para «el colector se pasa de holgura»; no me lo invento | usuario |
| **KNOWN_NONBLOCKING_DEFECT** | el mensaje del shard dañado sigue confundiendo dos causas | sin fecha |

---

## §10 · Lo que aprendí y no quiero volver a aprender

1. **Un `in` de subcadena no es una aserción sobre lo que se ejecuta.** `"timedatectl" in
   INSTALL` sobrevive a `NOtimedatectl`. Si la guarda tiene que morder un renombrado, la
   aserción va sobre la invocación.
2. **Mirar el campo que ya se escribe antes de afirmar que no hay ninguno.** Me costó una
   corrección pública en el §5, y la versión corregida describe un defecto peor.
3. **«Byte a byte» hay que comprobarlo, no declararlo.** Derivar `HOLGURA` la convirtió en
   `float` y la salida cambió en un dígito. Yo ya había escrito que no cambiaba.
4. **Una mutación que debe pasar vale tanto como una que debe fallar.** `M-PMW-todos`
   pasando es lo que distingue una fuente única de una constante disfrazada.
5. **El arreglo correcto en el momento incorrecto contamina.** Dos líneas, escritas, listas,
   y no se fusionan hasta pasado mañana.

---

**Estado final:** `#61 BLOCKED` · mitad de duplicación **cerrada** (PR #58, 758 verdes) ·
mitad de override **abierta a propósito**, parche escrito, desbloqueo tras el 2026-09-15 ·
sistema **CONGELADO** · `READY_FOR_PROSPECTIVE_TEST`.
