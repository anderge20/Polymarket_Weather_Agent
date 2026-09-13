# L1.5 — CALIBRACIÓN + RANKING · LOCK

**Integridad del lock previo verificada antes de escribir esto:** `LOCK_L1_4.md`,
`PREREG_LEVEL1.md`, `l1_2_baselines.py` y `l1_4_walkforward.py` tienen el **mismo `sha256`** en
el corpus local y en `research/modelsel-artifacts` (`cee4255` / `53eb8e6`). **Nada se ha
tocado.**

## Lo que NO cambia

Cinco modelos cerrados (`B0`…`B4`). **Prohibido**: `B5`, modelos nuevos, correcciones
condicionales, cambiar la ventana climatológica, cambiar el método de `B4`, hiperparámetros,
optimizar probabilidades, distribución alternativa, elegir modelo o lead, ensembles, `B2+B4`,
recalibrar y repuntuar sobre los mismos datos, o elegir una transformación porque mejore L1.4.
**Cualquier mejora que aparezca se registra como HIPÓTESIS PARA VALIDACIÓN FUTURA.**

Unidad de inferencia: **EVENTO**. Bootstrap clusterizado por evento, 10 000, semilla
**20260913**. Escalera **11** para inferencia; 7 y 9 sólo descriptivas. `epsilon = 1e-6`. Leads
separados, nunca agregados. `D0-P` = BLOCKED.

## Jerarquía metodológica, intacta

    benchmark PRIMARIO PRE-REGISTRADO     B0_clima
    control estructural (ex-post)          uniforme 1/11 = 0,0826446

**El uniforme NO se convierte en benchmark primario y `B0` no se modifica.** L1.4 no se
reescribe.

## Métricas: qué estaba predefinido y qué NO

| métrica | estado |
|---|---|
| Brier por evento / contrato | **predefinida** (LOCK_L1_4 §4) |
| Log Loss (sólo `B4` interpretable) | **predefinida** |
| rango medio de la banda ganadora | **predefinida** |
| top-1 | **predefinida** |
| bins de calibración `[0, .05, .1, .2, .3, .5, 1.01]` | **predefinida** |
| mitades temporales, corte 2026-06-23 | **predefinida** |
| entropía, sharpness | **predefinidas** (caracterización de L1.2) |
| **top-2, top-3** | **DIAGNÓSTICO DESCRIPTIVO — no estaba predefinido** |
| **intercepto y pendiente de calibración** | **DIAGNÓSTICO DESCRIPTIVO — no estaba predefinido** |
| **frecuencia de probabilidades extremas** | **DIAGNÓSTICO DESCRIPTIVO** |
| **bloques mensuales** | **DIAGNÓSTICO DESCRIPTIVO** |
| **análisis de influencia (dejar fuera los k eventos más influyentes)** | **DIAGNÓSTICO DESCRIPTIVO** |
| **binning alternativo** (red-team) | **DIAGNÓSTICO DESCRIPTIVO** |

**Ninguna métrica marcada como descriptiva puede usarse para modificar un modelo, elegir un
modelo, elegir un lead ni elegir un periodo.** Sólo describen.

## Calibración: qué se calcula y con qué advertencia

* **Curva de fiabilidad** sobre contratos, con la advertencia permanente de que los contratos de
  un evento **no son independientes**: sirve para ver la forma, no para inferir.
* **Intercepto y pendiente** por regresión logística de `y` sobre `logit(clip(p))`, con IC
  bootstrap **clusterizado por evento**. Se reportan **dos versiones**: con todos los contratos
  (el recorte de `1e-6` domina los extremos) y **restringida a `p > 0`**. Las dos se publican;
  ninguna se elige.
* **NO se entrena Platt, isotónica ni temperature scaling.** Si procediera, sería una hipótesis
  futura con procedimiento OOS propio, nunca entrenada sobre este test.

> **`OOS prediction` ≠ `OOS calibrated prediction`.** Los pronósticos son OOS por walk-forward;
> **la curva de calibración se mide sobre el mismo conjunto de test y NO es una calibración
> validada fuera de muestra.** Es diagnóstico.

## Caveats que siguen vigentes y no se resuelven aquí

1. **`available_at = issue_time + 4:45:36` es una convención NO validada externamente.**
   `available_at ≤ t_asof` no demuestra disponibilidad pública real. **Toda señal positiva queda
   condicionada** a esa validación (tarea #75). No se inventa otra latencia.
2. **`T_IEM` es el proxy de observación; `winning_outcome` es el target contractual.** 136
   acuerdo · 1 discrepancia · 50 sin observación. **No se sustituye el target por el proxy.**
3. **Missingness**: 22 (lead 24) y 21 (lead 9) eventos excluidos, contiguos desde el inicio, por
   arranque de la ventana expansiva. **El test NO cubre abril** y no se dirá «representativo de
   abril–agosto».

## Cierre

`L1.5 = CLOSED` sólo si las métricas se reproducen, la calibración está bien calculada, ranking
y calibración quedan separados, no hay selección post-hoc, no hay defectos bloqueantes, los
resultados son reproducibles y todas las limitaciones están documentadas. **No se emite «hay
edge» ni «no hay edge».**
