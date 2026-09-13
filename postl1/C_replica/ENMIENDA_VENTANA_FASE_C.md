# FASE C · ENMIENDA — ESTRECHAMIENTO DE VENTANA POR PRESUPUESTO

**Escrita ANTES de emitir una sola petición y ANTES de puntuar nada sobre RKSI.**

## Qué ha pasado

El lock (`LOCK_FASE_C.md`, `aed9482`) preinscribió **techo de 100 peticiones de observación**
y estimó **~72** necesarias. Al construir la ingesta, la guarda del propio guion **se negó**:

    ventana 2026-04-08 -> 2026-08-23 · dias a pedir 138 · techo 100
    NEGADO: 138 dias contra un techo de 100. El techo esta preinscrito;
            se estrecha la ventana, no el techo.

**La estimación de ~72 estaba mal.** Contaba los días que le faltan a RKSI **respecto a su
`dataset_version` actual**, pero el lock exige un **`dataset_version` NUEVO sin tocar ninguna
fila existente** — así que hay que reingerir **los 138 días**, no los 90 que faltaban.

## La regla, y por qué no toca el techo

**El techo NO se sube.** Era la regla explícita del lock y del encargo: *«no aumentar el
presupuesto retrospectivamente»*. Se estrecha la ventana.

**Regla de estrechamiento, declarada aquí:** se conserva **el tramo MÁS RECIENTE** que quepa en
el presupuesto con holgura.

*Motivo, e independiente de cualquier resultado:* el walk-forward consume los primeros días en
el arranque (`MIN_TRAIN = 20`; en Londres se perdieron 21). Conservar el tramo reciente
**maximiza los eventos puntuables por petición gastada**. **No se ha puntuado nada sobre RKSI**,
así que la elección no puede estar mirando un resultado.

## Ventana elegida: `W = 95`, **2026-05-21 → 2026-08-23**

| W | desde | peticiones obs | peticiones fc | puntuables aprox. |
|---|---|---|---|---|
| 138 | 2026-04-08 | **138 > techo** | 185 | 115 |
| 110 | 2026-05-06 | **110 > techo** | 141 | 89 |
| 100 | 2026-05-16 | 100 = techo, **sin holgura** | 125 | 79 |
| **95** | **2026-05-21** | **95** (holgura 5) | **117** (holgura 83) | **~74** |
| 90 | 2026-05-26 | 90 | 109 | 69 |

Se elige **95** por ser el mayor valor que deja holgura en el techo que muerde. Los **~74
eventos puntuables** superan con margen el umbral de **30** preinscrito en los criterios.

## Diferencia con Londres, documentada y no disimulada

    Londres  ventana puntuada  2026-05-01 -> 2026-08-23   (96 eventos, lead 9)
    RKSI     ventana prevista  ~2026-06-11 -> 2026-08-23  (~74 eventos, tras arranque)

**Solapan pero no son idénticas.** RKSI empieza más tarde y tiene ~23 % menos eventos. Es una
diferencia de **cobertura**, no de metodología: `B0`–`B4`, `S3`, leads, `t_asof`, `MIN_TRAIN`,
`epsilon`, bootstrap y unidad de inferencia siguen **exactamente congelados**.

**Consecuencia sobre la potencia, dicha antes de medir:** con ~74 eventos en vez de 96, el
mínimo detectable sube en torno a `sqrt(96/74) ≈ 1,14`, un **14 % peor**. Si el efecto de RKSI
fuese del mismo tamaño que el de Londres, seguiría siendo detectable; si fuese la mitad,
probablemente no. **Eso se evaluará con la razón efecto/MDE, no con el signo.**
