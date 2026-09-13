# POST-L1.8 · FASE A — BENCHMARK ESTRUCTURAL COMPLETO · RESULTADO

# STATUS

## `POST-L1.8 · FASE A = CASO B`, **pero sólo en lead 9**

    lead  9   CASO B   B4 conserva ventaja MATERIAL y ROBUSTA sobre el benchmark completo
    lead 24   CASO A/C la ventaja residual NO queda establecida: infrapotenciada y
                       sostenida por unos cinco eventos

# LOCK

| | |
|---|---|
| lock | `LOCK_FASE_A.md`, commit **`668b944`**, **2026-09-13T21:36:55Z**, espejado **antes** de ejecutar |
| familia | **tres benchmarks pre-registrados enteros**, con `S3` declarado **primario** antes de verlos |
| hashes | ver `FASE_A_HASHES.txt` |
| artefactos | `postl1/A_benchmark_estructural/` — **no se sobrescribe nada de L1** |

# HIPÓTESIS

> ¿Cuánto del supuesto predictive power de `B4` permanece cuando el benchmark conoce **toda** la
> geometría de la escalera —y el historial de dónde cayó la ganadora dentro de ella— pero **no**
> conoce el pronóstico ni ninguna información futura?

# MÉTODO

**`S3` — posición empírica**, el análogo estructural exacto de `B4`:

    B4  distribucion empirica del ERROR DE PRONOSTICO       -> necesita el forecast
    S3  distribucion empirica de la POSICION DE LA GANADORA -> necesita solo la escalera

Para cada evento de test se toma la posición de la ganadora respecto al centro de su escalera en
**todos** los eventos con etiqueta disponible en `t_asof` (mediana 121–122 eventos de historial),
y esa distribución se aplica a la escalera del test. Walk-forward, expansivo, sin nada posterior
a `t_asof`. Las posiciones que caen fuera de la escalera del test se acumulan en la banda abierta
correspondiente — *que es lo que una banda abierta significa*.

`S1` (uniforme sobre el interior) y `S2` (uniforme) acompañan. **Y el `CTRL_escalera` de L1.7
queda reclasificado**: su anchura la fijaba la dispersión de `B4`, o sea que el benchmark tomaba
prestado un parámetro del modelo que juzgaba.

# RESULTADOS

## La escalera sola sabe bastante más de lo que creíamos

    posicion de la ganadora respecto al centro
      {-5: 2, -3: 2, -2: 12, -1: 27, 0: 25, 1: 13, 2: 7, 3: 6, 5: 1}
      |desviacion| media 1,23 bandas   (el uniforme daria 2,73)
      entropia 1,82                    (el uniforme sobre 11 daria 2,40)

| benchmark | Brier lead 24 | contra uniforme | Brier lead 9 | contra uniforme |
|---|---|---|---|---|
| `S2` uniforme | 0,08264 | — | 0,08264 | — |
| `S1` interior | 0,08145 | −0,00120 | 0,08144 | −0,00121 |
| **`S3` posición empírica** | **0,07718** | **−0,00547** | **0,07714** | **−0,00550** |
| `B4` | 0,07113 | −0,01151 | 0,06534 | −0,01731 |

**`S3` captura el 47,5 % (lead 24) y el 31,8 % (lead 9) de toda la ventaja de `B4` sobre el
uniforme — sin mirar el tiempo ni una vez.** `S1` apenas aporta (−0,0012): lo que importa no es
«el interior», es **dónde cae históricamente la ganadora dentro de la escalera**.

## La comparación de registro

| | lead 24 | lead 9 |
|---|---|---|
| `B4 − S2` | −0,01151 [−0,01589, −0,00700] | −0,01731 [−0,02131, −0,01296] |
| `B4 − S1` | −0,01031 [−0,01494, −0,00566] | −0,01610 [−0,02032, −0,01177] |
| **`B4 − S3`** *(primario)* | **−0,00605 [−0,01092, −0,00125]** | **−0,01181 [−0,01607, −0,00771]** |
| **razón efecto/MDE** | **0,87 — POR DEBAJO DEL MÍNIMO DETECTABLE** | **1,95** |
| eventos ganados | **58/95 (61 %)** | **73/96 (76 %)** |
| mediana contra media | −0,00442 contra −0,00605 → **la media la tira la cola** | −0,01306 contra −0,01181 → **la mediana es MÁS favorable** |

## LA CUARTA DEFLACIÓN

    benchmark                    lead 24     lead 9
    B4 - B0                      -0,0304    -0,0359
    B4 - uniforme                -0,0115    -0,0173
    B4 - CTRL_escalera (L1.7)    -0,0076    -0,0134
    B4 - S3  (estructural completo) -0,0061 -0,0118

**Cada vez que hemos construido un benchmark mejor, el efecto ha vuelto a encogerse.** Ahora el
benchmark es **no ajustable** —una frecuencia empírica walk-forward, sin un solo parámetro
libre— y **aun así el efecto siguió bajando**. Del titular pre-registrado al actual:
**×5,0 en lead 24 y ×3,0 en lead 9.**

# RED TEAM

### 1 · ¿`S3` se come señal legítima?

`S3` no usa el pronóstico, pero **la escalera embebe el pronóstico DEL MERCADO**. Por eso
`B4 − S3` **no** mide «poder predictivo contra ruido»: mide **qué añade nuestro pronóstico sobre
lo que la geometría del contrato ya implica**. Es un listón más alto que el de Level 1 y se
declaró como tal **en el lock, antes de ver el resultado**.

### 2 · ¿Tiene `S3` fuga del futuro?

**No.** Prohibiendo además todo lo posterior al corte, `S3` sale **idéntico en 47 de 47** eventos
anteriores: el historial ya estaba limitado a `t_asof` por construcción.

### 3 · Robustez al mínimo de entrenamiento — los cuatro valores

    lead 24   20: -0,00605 · 30: -0,00732 · 40: -0,00859 · 50: -0,00870   los cuatro excluyen el cero
    lead  9   20: -0,01181 · 30: -0,01146 · 40: -0,01197 · 50: -0,01208   los cuatro excluyen el cero

### 4 · INFLUENCIA — **y aquí es donde el lead 24 se cae**

    lead 24   quitando los  5 mas favorables:  -0,00292  [-0,00686, +0,00105]   YA NO excluye el cero
              quitando los 10:                 -0,00110  [-0,00491, +0,00302]   YA NO
              quitando los 20:                 +0,00243  [-0,00132, +0,00634]   CAMBIA DE SIGNO

    lead  9   quitando los  5:  -0,00910 [-0,01256,-0,00545]   sigue
              quitando los 10:  -0,00737 [-0,01075,-0,00383]   sigue
              quitando los 20:  -0,00418 [-0,00740,-0,00074]   SIGUE excluyendo el cero

> **En el lead 24 la ventaja sobre el benchmark estructural completo descansa sobre unos CINCO
> eventos.** Contra el uniforme (L1.5) hacían falta veinte para tumbarla; contra `S3` bastan
> cinco. **El benchmark más fuerte no sólo redujo el efecto: destapó que era frágil.**
>
> **En el lead 9 no.** Sobrevive a quitar los veinte más favorables, gana en el 76 % de los
> eventos y su mediana es más favorable que su media.

# DEFECTOS

| severidad | hallazgo |
|---|---|
| **A — bloqueante** | **ninguno** en el método |
| **B — requiere corrección** | **el `CTRL_escalera` de L1.7 tomaba su anchura de `B4`.** Corregido: reclasificado a control preliminar y sustituido por la familia `S1`/`S2`/`S3`. **Los números de L1.7 no se reescriben**; se contextualizan |
| **C — documentable** | (1) `B4 − S3` en lead 24 está **infrapotenciado** (razón 0,87); (2) `S3` embebe el pronóstico del mercado, así que el listón es más alto que el de L1 y roza L2; (3) todo sigue sobre un corpus único; (4) `available_at` sin validar (fase B); (5) la escalera sola ya lleva entropía 1,82 contra 2,40 del uniforme |

# DECISIÓN

## **CONTINUAR a la FASE B — con el caso reducido a un solo lead**

**Qué sobrevive:** `lead 9`. Contra el benchmark estructural más exigente que sabemos construir
—no ajustable, walk-forward, sin pronóstico— `B4` conserva **−0,01181 [−0,01607, −0,00771]**,
con razón efecto/MDE **1,95**, ganando en el **76 %** de los eventos, robusto al mínimo de
entrenamiento y **resistiendo la eliminación de los veinte eventos más favorables**.

**Qué no sobrevive:** `lead 24`. Infrapotenciado (0,87), gana sólo en el 61 %, y **cinco eventos
bastan para que el IC deje de excluir el cero**. Sumado a su heterogeneidad temporal (L1.6) y a
su margen de disponibilidad de 1,24 h, **el lead 24 deja de ser parte del caso**. *No se busca
otra transformación para salvarlo.*

**Una nota que va a favor y hay que decir igual que las que van en contra:** el lead que
sobrevive es **el que tiene mayor margen de disponibilidad** (4,24 h contra 1,24 h). La fase B
es, por tanto, **menos peligrosa para el caso superviviente de lo que habría sido para el lead
24** — pero sigue siendo decisiva, porque ahora el caso entero descansa sobre un solo lead.

**Sigue prohibido y no realizado:** L2, precios, EV, PnL, trading, ejecución, order book,
umbrales, estrategia, stake, optimización económica, dinero real, paper trading, bot,
producción. `D0-P` = BLOCKED · `L2` = BLOCKED.
