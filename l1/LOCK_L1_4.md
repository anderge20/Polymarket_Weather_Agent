# L1.4 — WALK-FORWARD OOS · LOCK

**Escrito y espejado ANTES de ejecutar.** Nada de lo que sigue se modifica después de ver
resultados. Prohibido y no realizado: buscar edge, precio, PnL, umbrales, activar trading,
modificar producción. **`D0-P` = BLOCKED.**

## 1 · Estructura temporal — EXPANDING WINDOW POR EVENTO

**No hay un corte train/test único.** Cada evento de test lleva su propia ventana expansiva:

    train(evento) = { dias d : label_av(d) <= t_asof(evento) y existe FC(d, lead) }
    test          = el evento, cuyo target_date NUNCA esta en su propio train

Es la forma **más estricta** de walk-forward: el corte se mueve con cada evento y jamás retrocede.

| | lead 24 h | lead 9 h |
|---|---|---|
| eventos de TEST | **95** | **96** |
| primer test | 2026-05-02 (train 20, cutoff 2026-04-29) | 2026-05-01 (train 20, cutoff 2026-04-29) |
| último test | 2026-08-23 (train 115, cutoff 2026-08-20) | 2026-08-23 (train 116, cutoff 2026-08-21) |
| tamaño de train | min 20 · mediana 68 · **max 115** | min 20 · mediana 68 · **max 116** |
| candidatos (obs+FC) → puntuados | 117 → 95 (caen 22) | 117 → 96 (caen 21) |
| escaleras presentes | `{11}` | `{11}` |
| **mitad temporal** (diagnóstico) | 2026-06-23 → 47 / 48 | 2026-06-23 → 48 / 48 |

**Mínimo de train: 20 pares** (preinscrito en `PREREG_LEVEL1.md` §11). Los 22/21 eventos que
caen por debajo **no se ocultan**: se cuentan aquí.

**Prohibido y verificado ausente en L1.2/L1.3**: split aleatorio, K-fold, información del
futuro, `target_date` en train, calibración usando test, selección de parámetros usando test.

## 2 · Modelos — LOS CINCO BLOQUEADOS, NINGUNO MÁS

    B0_clima      frecuencia de cada banda en las ultimas 30 etiquetas DISPONIBLES
    B1_persist    indicador sobre la banda de la ultima etiqueta disponible
    B2_fc_crudo   indicador sobre round(f)
    B3_fc_sesgo   indicador sobre round(f + bias),  bias = mean(obs - fc) SOLO del train
    B4_fc_prob    masa empirica de round(f + e),    e = errores SOLO del train

**No se introduce**: modelo nuevo, corrección condicional (temperatura, mes, estación, lead),
suavizado, distribución alternativa ni hiperparámetro nuevo. **Si un modelo falla, se registra
el fallo**; sólo se repara un bug matemático identificable *a priori*, como el signo de A-287.

**Climatología**: ventana de **30 etiquetas disponibles**, versión preinscrita y única. No se usa
climatología completa de 2026, ni el resultado del test, ni observaciones futuras.

**B4**: la distribución de errores se estima **sólo con train**, no se recalibra con el test y no
usa la ganadora del test. Se documenta n de errores, método y evolución entre ventanas.

## 3 · Dependencia — DOS NIVELES

1. Los `n` contratos de un evento cumplen `Σ y = 1`: **no son independientes**.
2. Los dos leads del mismo evento **tampoco** lo son.

**Inferencia**: bootstrap **clusterizado por EVENTO**, 10 000 remuestreos, semilla **20260913**
(preinscrita). **Los leads se analizan por separado y nunca se agregan**, así que el clúster es
el evento dentro de cada lead.
**Reporting**: se muestran contrato, evento y `evento×lead`; la inferencia sólo respeta el evento.

## 4 · Métricas

**PRIMARIA — declarada antes de ejecutar:**

> Diferencia **apareada por evento** de Brier frente a **`B0_clima`**, dentro de la **escalera de
> 11 bandas**, unidad `evento × lead`, con IC95 por bootstrap clusterizado por evento.
> Comparaciones declaradas: **B1−B0, B2−B0, B3−B0, B4−B0**. Las cuatro se reportan siempre.

**SECUNDARIAS**: Brier por contrato y por evento · Log Loss **probabilístico (sólo B4 es
genuino)** · ranking · calibración básica · MAE del pronóstico.

**Ranking, definido ahora**: (a) **rango medio de la banda ganadora** ordenando de mayor a menor
probabilidad, empates con rango medio (1 = mejor, 11 = peor; el azar da 6,0); (b) **fracción en
que la ganadora es el argmax** (top-1; el azar da 1/11 = 9,1 %).

**Calibración básica**: bins de probabilidad predicha `[0, .05, .1, .2, .3, .5, 1]`, frecuencia
observada contra media predicha, **sobre contratos y declarada como diagnóstico** — los contratos
no son independientes.

**Clipping**: `epsilon = 1e-6`, preinscrito. Se reporta sensibilidad. **El Log Loss de B1/B2/B3
NO se usa para seleccionar** — es aritmética del recorte (A-288). **Brier sí** es referencia.

## 5 · Escaleras

    7 bandas    0 eventos puntuables   INSUFICIENTE, y se dice
    9 bandas    0 eventos puntuables   INSUFICIENTE, y se dice
   11 bandas   95 / 96 eventos          analisis principal

**Nunca se agregan Brier ni Log Loss crudos entre escaleras** (H4 = INVALIDADA, A-280). Las de 7
y 9 **no se eliminan por poco útiles**: no tienen ningún evento con observación y pronóstico, y
eso está medido desde el lock de L1.0.

## 6 · Diagnóstico temporal

Primera mitad / segunda mitad, corte **2026-06-23**. **Diagnóstico, no una nueva oportunidad de
selección**: se reporta el resultado en las dos mitades sea cual sea.

## 7 · Regla anti-selección, escrita antes de ver nada

Si sale `B4 > B3`, o cualquier otro orden, **no se cambia** la distribución, ni la ventana, ni el
bias, ni el clipping, ni se añaden features, ni se prueba otro modelo. **Se registra el
resultado.** Si el número efectivo de eventos es insuficiente, **`INCONCLUSIVE` es un resultado
válido** y se emite.

## 8 · Gate

Defecto metodológico → **`L1.4 = BLOCKED`**. Todo correcto → **`L1.4 = CLOSED`**, y **aun así NO
se emite el veredicto final de Level 1**: eso requiere L1.5–L1.7.
