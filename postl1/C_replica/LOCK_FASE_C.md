# POST-L1.8 · FASE C — LOCK DE LA RÉPLICA

**La ciudad queda CONGELADA aquí, antes de descargar un solo dato nuevo y antes de ejecutar un
solo modelo sobre ella.** Prohibido y no realizado: precios, EV, PnL, fills, order book,
spreads, liquidez, umbrales, entradas, salidas, stake, ejecución. `D0-P` = BLOCKED ·
`L2` = BLOCKED.

---

## 1 · CIUDAD SELECCIONADA

# `RKSI` — Incheon / Seúl · `Asia/Seoul`

Seleccionada aplicando la regla de `CRITERIOS_FASE_C.md`, espejada a las **21:58:56Z**
(`aed9482`) **antes** de medir el universo. **Ningún criterio miró un resultado.**

---

## 2 · EL UNIVERSO ELEGIBLE TIENE UNA SOLA ESTACIÓN, Y ES LONDRES

    UNIVERSO ELEGIBLE HOY: 1 estacion -> EGLC, la propia Londres

    por que caen las otras 51 (causa PRIMERA):
      < 40 dias de observacion ............ 36
      unidad != C (Fahrenheit) ............ 11
      sin observacion ......................  3
      < 30 eventos puntuables ..............  1

**La réplica no se puede ejecutar hoy.** Y la causa está medida, no supuesta: **el corpus se
construyó centrado en Londres por los DOS lados a la vez.**

    dias objetivo con pronostico, por estacion
      EGLC 118 · RKSI 46 · RCSS 31 · 28 (x19) · 27 (x14) · 26 (x8) · resto menos

    dias locales con observacion
      EGLC 138 · RKSI 46 · RCSS 31 · 28 o menos el resto

> **La restricción que manda es la COBERTURA, no la calidad.** Londres tiene 118 días de
> pronóstico; la segunda estación tiene 46 y la tercera 31. Con `MIN_TRAIN = 20`, RKSI daría
> **25 eventos puntuables**, por debajo del umbral de 30 que yo mismo preinscribí.
>
> **No se relaja el umbral para que entre alguien.** Era la regla 5 de los criterios y se
> cumple.

## 3 · REGLA APLICADA AL OBJETIVO DE INGESTA

`D1` (eventos puntuables) no es evaluable sin cobertura, así que se usa **su techo**,
`A_eventos_elegibles`, que **no depende de la observación ni del pronóstico**. Adaptación
declarada y totalmente independiente del resultado.

| icao | eventos elegibles | días de pronóstico | escaleras | timezone |
|---|---|---|---|---|
| **RKSI** | **186** | **46** | `{7:2, 9:26, 11:158}` | `Asia/Seoul` |
| CYYZ | 185 | 27 | `{7:2, 9:26, 11:157}` | `America/Toronto` |
| LTAC | 185 | 28 | `{9:26, 11:159}` | `Europe/Istanbul` |
| NZWN | 185 | 28 | `{9:26, 11:159}` | `Pacific/Auckland` |
| SAEZ | 183 | 26 | `{7:2, 9:26, 11:155}` | `America/Argentina/Buenos_Aires` |

**`RKSI` gana por DOS criterios ex-ante independientes**, y ninguno mira un resultado:

1. **máximo de eventos elegibles** entre las estaciones en Celsius (186, empatado con la propia
   Londres);
2. **máxima cobertura de pronóstico** después de Londres (46 días contra 31 de la tercera).

*Que los dos apunten a la misma estación es una comprobación, no una coincidencia buscada.*

**Nota necesaria:** RKSI sólo es utilizable porque `observaciones()` toma ya la zona horaria de
`stations.timezone_of` — el arreglo de D11/A-285. Con el `Europe/London` fijo que había antes,
los días de Seúl se habrían agrupado mal **sin que nada avisara**.

---

## 4 · LO QUE QUEDA CONGELADO, PALABRA POR PALABRA

    ciudad            RKSI                          estacion      Asia/Seoul
    proveedor/modelo  Open-Meteo / icon_seamless    (el MISMO que Londres)
    leads             24 y 9, LOS DOS               t_asof        end_date(12:00Z) - lead
    availability      available_at = issue + L_MAX['icon_seamless'] = 4,76 h  (F-3, sin tocar)
    poblacion         regla A-275: resolved + particion completa + una ganadora
                      + dedup (station,target_date) + desempate por close_time
    modelos           B0 B1 B2 B3 B4  IDENTICOS  (sin recalibrar, sin cambiar ventana,
                      sin sesgo condicional, sin cuantiles, sin tocar epsilon)
    benchmark         S3 IDENTICO (posicion empirica walk-forward); ademas uniforme y B0
    metrica primaria  Brier por evento, diferencia APAREADA contra S3
    walk-forward      expansivo por evento · MIN_TRAIN = 20 · epsilon = 1e-6
    inferencia        bootstrap CLUSTERIZADO POR EVENTO · 10 000 · semilla 20260913
    unidad            EVENTO. Los contratos NO son observaciones independientes
    escaleras         estratificar SIEMPRE; nunca agregar entre tamaños distintos
    unidades          C. `exige_celsius()` activo: si la ciudad no fuera Celsius, se niega

**Si la metodología no funciona en RKSI, eso es el resultado. No se corrige después.**

---

## 5 · PRESUPUESTO DE INGESTA — preinscrito ANTES de gastar cuota

Para que RKSI llegue a una cobertura comparable a la de Londres:

    pronosticos   faltan ~72 dias objetivo x 2 ejecuciones = ~144 peticiones
                  API Open-Meteo single-runs · TECHO DECLARADO: 200 peticiones
    observaciones RKSI ya tiene observacion en los 46 dias que tienen pronostico;
                  hara falta una peticion IEM por cada dia nuevo: ~72
                  TECHO DECLARADO: 100 peticiones

    REGLAS: respetar 429 sin excepcion y sin reintento agresivo; no usar clave de pago;
            parar al llegar al techo aunque falten dias; registrar peticiones y fallos;
            dataset_version NUEVO, sin tocar ni una fila existente.

**Nada de esto se ejecuta en este turno.** El lock existe para que la ciudad esté congelada
**antes** de que se toque un dato.

---

## 6 · CRITERIO DE VEREDICTO — ya escrito, no se retoca al ver el número

| | condición |
|---|---|
| **REPLICATED** | `B4 − S3 < 0`, IC95 que excluye el cero, mismo signo que Londres, magnitud material, controles superados y **razón efecto/MDE ≥ 1** |
| **NOT REPLICATED** | `S3` gana con IC que excluye el cero **y** potencia suficiente |
| **INCONCLUSIVE** | IC que incluye el cero **o** razón efecto/MDE < 1 |

**Una réplica negativa con potencia insuficiente es `INCONCLUSIVE`, jamás `NOT REPLICATED`.**
**Y una réplica negativa no se compensa buscando otra ciudad**: si falla con potencia
suficiente, se para y se analiza.

**No se hará meta-análisis Londres + réplica para rescatar un resultado negativo.** Si procede
un pooling, será un análisis secundario con su propio diseño, declarado antes de verlo.
