# NIVEL 0.5 — DATASET VALIDATION · CRITERIO DE COMPLETITUD

**Escrito el 2026-09-13 a las 16:45Z, CON LA REINGESTA TODAVÍA CORRIENDO y antes de mirar
un solo recuento suyo.** Autor: Claude (sesión A). Encargo: NIVEL 0.5 del usuario.

> **Una tabla con 79.735 mercados no demuestra que esté completa.** Este documento fija,
> antes de ver el resultado, qué significa «completa» y qué hace que el dataset quede
> **INVALID / INCOMPLETE** y no se use para investigación.

---

## 0. Qué NO es este nivel

Este nivel es **DATA QUALITY** y sólo eso. No se mide poder predictivo, no se habla de
edge, alpha ni ventaja, y **una mejora de calidad de datos NO es evidencia de poder
predictivo**. El resultado de la corrección de observaciones se nombra
**`DATASET CORRECTION VALIDATED`** y nada más.

---

## 1. Las tres poblaciones, y de dónde sale «lo esperado»

| población | fuente de verdad | por qué esa y no otra |
|---|---|---|
| **eventos y mercados** | `CATALOG_V2.duckdb`, tabla `mk` | es lo que Polymarket sirvió, descargado el 2026-09-05; el `--dry-run` es una PROYECCIÓN de él, no una fuente |
| **observaciones** | IEM, más el tarball de B-133 como oráculo | 137 días con respuesta guardada **antes** de preguntar |
| **selección** | salida del `--dry-run` de `backfill_markets` | es la afirmación del código sobre lo que va a escribir |

**Se compara contra las DOS**: contra el `--dry-run` (¿escribió lo que dijo que escribiría?)
y contra el catálogo (¿dijo que escribiría todo lo que había?). *Comparar sólo contra el
dry-run valida el código contra sí mismo.*

## 2. Números FIJADOS AHORA, antes de mirar

Del `--dry-run` ejecutado a las 16:02Z sobre el catálogo entero:

    events_writable                              7 331
    markets_writable                            79 735
    excluidos: no_station_identifier             1 224
    excluidos: market_without_token_ids...           2

De mediciones previas ya registradas (A-244, A-259):

    eventos EGLC en el catalogo por station_identifier            187
    mercados EGLC en el catalogo                                1 997
    escaleras EGLC completas en el catalogo, por tamano   {7:2, 9:26, 11:159}
    observaciones EGLC tras la reingesta        118 viejas + 138 nuevas = 256 filas EGLC

## 3. IDENTIDADES QUE DEBEN CUMPLIRSE. Cualquiera que falle ⇒ INVALID

**I1 — conservación del universo.**
`eventos del catalogo con station_identifier` = `eventos escritos` + `eventos excluidos`
y lo mismo por mercados. **No puede haber un evento que no esté ni escrito ni excluido**:
un evento que desaparece sin motivo es exactamente el defecto que este nivel existe para
cazar.

**I2 — el dry-run no mintió.**
`eventos escritos en markets_v2` == `events_writable` (7 331)
`mercados escritos en markets_v2` == `markets_writable` (79 735)

**I3 — atomicidad por evento.** Para todo evento escrito, **todos** sus mercados del
catálogo están escritos. Cero eventos a medias. *(Es la propiedad que el #50 introdujo; si
falla, el arreglo no funcionó o la escritura se truncó.)*

**I4 — outcomes completos.** `outcomes` en `markets_v2` = 2 × `mercados escritos`, y cada
mercado tiene exactamente un token `Yes` y uno `No`.

**I5 — sin duplicados.** Cero `market_id` con más de una fila por `(dataset_version,
record_version)`; cero `token_id` duplicado.

**I6 — bandas.** Todo mercado escrito tiene `band_label` no nulo en su token `Yes`, y
`lo`/`hi` coherentes con la etiqueta.

**I7 — el dataset viejo intacto.** `backfill_2b_v1` conserva **exactamente** sus 6 143
mercados y 12 286 outcomes. La reingesta es aditiva: si tocó la versión vieja, INVALID.

**I8 — particiones.** Para EGLC: los eventos con escalera completa deben ser **187**, con la
distribución de tamaños `{7:2, 9:26, 11:159}` ya medida en el catálogo. Cualquier otra cosa
significa que la escritura perdió bandas.

**I9 — observaciones.** 256 filas EGLC (118 + 138), 118 días con las dos series, cero días
con dos filas de la MISMA serie, y el máximo de la serie nueva coincide con el oráculo en
los 137 días que el tarball cubre.

**I10 — sin leakage temporal.** Ninguna observación con `available_at` anterior a su
`observation_time`; ningún pronóstico con `available_at` posterior al `t_asof` que se le
aplique.

## 4. Qué se reporta, con estos nombres

    eventos esperados / escritos / completos
    mercados esperados / escritos / completos / excluidos + razones
    tokens esperados / presentes
    particiones incompletas
    duplicados
    inconsistencias

Y las dos tablas ANTES/DESPUÉS que pide el encargo: una de agregados y otra de
entradas/salidas con su motivo.

## 5. Regla de parada

**Si `expected != actual` en cualquiera de I1-I10, el dataset queda `INVALID /
INCOMPLETE`**, se dice cuál falló y con qué números, y **no se usa para investigación**. No
se «ajusta el criterio a lo que salió»: el criterio está escrito arriba, con la reingesta
todavía corriendo.

## 6. Lo que NO se hace en este nivel

Ni un modelo, ni un threshold, ni un lead, ni una banda, ni una estación nueva, ni una
segmentación. **Ninguna conclusión de edge.** La reejecución del criterio antiguo —sin
tocarlo— es el paso 5 del encargo y va **después** de que este nivel cierre.
