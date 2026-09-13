# PREINSCRIPCIÓN — reejecución del NIVEL 1 sobre el corpus reparado

**Escrita el 2026-09-13, ANTES de que la reingesta exista y ANTES de ver ningún
resultado nuevo.** Firmada por: Claude (sesión A). Registro: A-244.

**Estado del veredicto mientras tanto: `D — INCONCLUSO` (A-240). No se modifica por
este documento.** Y el veredicto de fase anterior sigue intacto: `LONDRES = NO EDGE
MEDIDO`. Este documento no lo toca, no lo reabre y no lo comenta.

---

## 1. Por qué hay reejecución

A-240 retractó el `C` porque **74 de 115 eventos no tenían banda ganadora en el
almacén**: el Brier por evento sobre bandas lejanas todas con verdad 0 omite el único
término que importa, `(q_verdadera − 1)²`. Quedaron 19 eventos completos y con ellos
el criterio preregistrado **refuta**.

A-244 localizó la causa: **las bandas existen en Polymarket y también en nuestro
catálogo en disco** (`CATALOG_V2.duckdb`, tabla `mk`), y el corte está entre el
catálogo y `markets`. Es reparable y offline.

## 2. Dimensionado (declarado, y declarado como lo que es)

`fase2/n1_30_dimensionado_reingesta.py`, contra el catálogo y las observaciones:

    CON_GANADORA                118
    sin_observacion              45   (eventos anteriores al 2026-04-08)
    fuera_de_la_escalera          0
    n hoy: 19   ->   n tras reingestar: 118   (escalera de 11 bandas en los 118)
    rango: 2026-04-08 -> 2026-08-23

**Este número NO puede usarse para elegir población, lead, banda, modelo ni
estadístico.** Sirve para una sola cosa: decidir si la reparación merece el trabajo.
Merece: ×6,2 en n y la partición completa en los 118.

*Y una advertencia de método sobre el propio dimensionado: su primera versión devolvió
`0` para los 163 eventos, y era un bug —`endDate` es un VARCHAR ISO en el catálogo, así
que `hasattr(fecha,"date")` era False y la comparación fallaba en silencio—. **Un
dimensionado que sale exactamente cero es señal de bug, no un hallazgo.** Queda escrito
porque el fallo silencioso habría cerrado esta vía como «no merece la pena».*

## 3. Lo que NO cambia: el criterio

**Se reejecuta el criterio ya preregistrado, palabra por palabra**, tal como está en el
docstring de `fase2/n1_14_baselines.py`:

> Unidad `(target_date, lead)`. Brier por banda, promediado DENTRO del evento y luego
> sobre eventos. Nunca las bandas como observaciones sueltas.
> Entrenamiento: sólo días cuya ETIQUETA estaba disponible en `t_asof` del evento (fin
> del día local + 24 h). Ventana expansiva. Mínimo 20 pares.
> Modelos: B0 climatología 30 d · B1 persistencia · B2 forecast crudo · B3 forecast +
> error empírico · B4 forecast bias-corregido + error.
> **CONFIRMA (nivel B):** B3 o B4 mejoran a B0 en Brier por evento con IC95 bootstrap
> por evento que **EXCLUYE el cero**, **EN LOS DOS LEADS**.
> **REFUTA:** el intervalo incluye el cero en cualquiera de los dos leads.
> No se elige lead ni modelo después de mirar: se reportan los cinco.

**No se añade ningún modelo, no se mueve ningún umbral, no se cambia el bootstrap y no
se toca el mínimo de 20 pares.** Si el criterio refutaba con 19 eventos y confirma con
118, el que cambió fue el corpus, no la vara.

## 4. Lo único que cambia: la población, y su regla de admisión

Un evento entra si y sólo si, **después** de la reingesta:

1. tiene la escalera completa en `markets` — un `«N or below»`, un `«M or higher»` y
   todos los enteros entre medias, sin huecos (la función `particion()` que ya existe);
2. tiene observación EGLC para su día local de Londres;
3. tiene pronóstico disponible en `t_asof` para el lead que se evalúa.

**Nada más. En particular NO se filtra por volumen, por liquidez, por número de bandas
distinto de la partición, ni por «eventos con ganadora», que es lo que A-240 identificó
como el sesgo.**

## 5. LA VERDAD LA PONE EL MERCADO, NO NUESTRA OBSERVACIÓN

El dimensionado de §2 dedujo la banda ganadora **de nuestro propio máximo observado**
contra la escalera del catálogo. **Eso vale para contar y no vale para medir.**

La reejecución usa `markets.winning_outcome`, la resolución de Polymarket, como verdad.
Sustituirla por nuestra etiqueta cambiaría el estimando —pasaríamos de «predecir la
resolución del mercado» a «predecir nuestra propia observación»— y haría el resultado
incomparable con todo lo anterior, además de borrar precisamente el desajuste entre
ambas que es una magnitud de interés por sí misma.

**Y si tras la reingesta un evento completo no trae `winning_outcome`, ese evento NO
entra, y se cuenta aparte.** No se rellena con la observación.

## 6. Comprobaciones de integridad ANTES de mirar ningún Brier

Se ejecutan y se publican **antes** del estadístico, y cualquiera que falle detiene la
reejecución:

- **a.** nº de eventos con partición completa == nº de eventos con `winning_outcome`,
  y ambos == 118 ± los que §5 excluya. Cualquier otra cosa es un corpus distinto del
  dimensionado, y hay que explicarla antes de seguir.
- **b.** exactamente **una** banda ganadora por evento.
- **c.** el máximo observado cae dentro de la banda ganadora en el 100 % de los eventos,
  o se reporta la lista de discrepancias **como resultado propio** (es el desajuste
  observación/resolución, no un error a tapar).
- **d.** ningún `available_at` de pronóstico posterior a `t_asof` (la garantía ex-ante
  que ya vigila `n1_02_temporalidad.py`).
- **e.** las 19 de A-240 siguen dando **exactamente** el mismo número que dieron
  entonces. Si no, la reingesta cambió algo más que el universo y hay que saber qué.

## 7. Clasificación

La misma de siempre y sin lenguaje económico: **A** (sin poder), **B** (poder), **C**
(poder fuerte), **D** (inconcluso). **No se usa «EDGE» ni «NO EDGE ECONÓMICO» en este
nivel.** El resultado se entrega antes de avanzar a ningún nivel posterior.

## 8. Qué haría falta para que esto no valga

Escrito ahora para que no se pueda inventar después:

- que la reingesta traiga bandas que Polymarket **no** tenía en su momento (mercados
  añadidos después del cierre): se comprueba con `closedTime`/`umaEndDate` por banda;
- que las bandas recuperadas no tengan `price_history` y el nivel siguiente acabe
  midiendo contra un libro que no existió — **eso no afecta al NIVEL 1**, que no usa
  precios, pero sí decide si hay nivel 3;
- que el arreglo de discovery cambie también la ingesta viva y con ella el sustrato del
  modo paper: lo comprueba B como parte del #60.
