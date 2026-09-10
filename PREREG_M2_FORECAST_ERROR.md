> **RETIRADO el 2026-09-09 por A-30.** Refutación hostil (A-29.4): 4 hallazgos bloqueantes
> —gate as-of vacío (0/1.348 observaciones admisibles), un OBSERVADO falso sobre `available_at`,
> fórmula walk-forward autocontradictoria (`ceil` da D−3, no D−2) y doble definición de `T`—,
> más colisión con `PREREG_M2_ERROR.md` (sesión B), que es el que rige. **No citar como vigente.**

# PREREG_M2 — Distribución empírica del error de pronóstico

**Congelado el 2026-09-09, ANTES de calcular ningún cuantil que vaya a `weather_forecasts`.**
Sesión A (reclamado en A-28 tras la cesión de B-2). Un solo propósito: convertir el pronóstico
determinista `forecast_tmax` de M1 en la distribución `forecast_p10..p90` que `build_feature` necesita.
**Anclas:** `DECISIONS.md` sha en `DECISIONS.sha256`; D12 (M1 = `icon_seamless`), D17 (Y_final),
D19 (fees, independiente), A-24 (un propósito, una refutación), A-28 (ventana del archivo),
A-29 (nada VALIDADO sin refutación hostil). Convención de evidencia: OBSERVADO / INFERIDO / UNKNOWN.

## 0. Qué decide y qué NO

**Decide:** la definición del error, su estratificación, la regla walk-forward, la derivación de los
cinco cuantiles, la política fail-closed y el criterio de calibración con el que M2 se juzgará.
**NO decide:** M1 (D12, cerrado); el operador de settlement (`SETTLEMENT_OPERATOR_CORE`); `p_model`
ni la mezcla de M3; el backtest (pospuesto, A-24); los fees (D19). **No fija umbrales de aceptación
del backtest**: sólo los de calibración de M2.

## 1. Sustrato observado (recomputado 2026-09-09 sobre `data/pmw.duckdb`, `read_only=True`)

```
weather_forecasts   2.727 filas · icon_seamless · 50 estaciones · 2026-04-08 → 2026-09-04
                    forecast_p10..p90 = NULL en 2.727/2.727   (es lo que M2 viene a poblar)
weather_observations 1.348 filas · 49 estaciones
pares (pronóstico, observación) emparejados por (station, día civil):  2.545 · 49 estaciones
grupos (estación, lead):  98        n mediana = 26   min = 2   max = 118
                                    n ≥ 20 en 88/98 grupos ·  n ≥ 30 en sólo 4/98
```
**Ventana irrecuperable (A-28/B-1):** el archivo de Single Runs retiene ~159 días y avanza a diario;
el borde medido el 2026-09-08 fue **2026-04-02**. La ventana de entrenamiento de M2 queda acotada por
el archivo, **no** por el catálogo de precios (que llega a 2025-12-28). Esto **no** es una elección
metodológica: es una restricción física declarada.

## 2. Definición del error

Para cada par: **`e = forecast_tmax − Y`**, con `Y` = máximo observado del día civil local de la
estación (D17: `Y_final` desde IEM/METAR, con su limitación declarada; zona horaria de
`STATION_TZ_v1.json`). Unidad: °C. Signo fijado aquí y no revisable: **`e > 0` ⇒ el pronóstico
sobreestimó**.
`lead` se deriva de `issue_time` frente a `T = target_date 12:00:00Z`: `lead = 9 h` si
`T − issue_time ≤ 18 h`, `24 h` en caso contrario (los dos leads primarios de
`PREREG_LEAD_HOURS_RANGE`; hay exactamente 2 runs por (estación, fecha) en 1.363/1.364 casos).

## 3. Estratificación — decidida por tamaño muestral, no por resultado

Con **mediana de 26 pares por (estación, lead)**, un `p10`/`p90` por estación se estima con ~3
observaciones en cada cola: inservible. Se preregistra por tanto una **descomposición
localización–forma**, y su escalera de repliegue, **antes de ver ningún resultado**:

- **Forma (los cuantiles del error centrado):** se estima **agrupando todas las estaciones del mismo
  `lead`**. Justificación a priori: n por lead ≈ 1.272, suficiente para colas; y el régimen espacial
  ya está controlado por M1 (V5 mostró que la resolución de celda, no la estación, gobierna el error).
- **Localización (el sesgo):** **por (estación, lead)** si `n ≥ 20`; si no, por `lead`. Se estima con
  la **mediana** del error, no la media: robusta a la cola larga observada.
- **Escalera de repliegue, en este orden y sin excepciones:**
  1. `n(estación, lead) ≥ 20` → sesgo propio + forma del lead.
  2. `n(estación, lead) < 20` **y** `n(componente ICON, lead) ≥ 20` → sesgo del componente
     (`STATION_REGION_COMPONENT_v1.json`) + forma del lead.
  3. En otro caso → **fail-closed**, sin cuantiles (§6). **No se imputa.**

**Lo que esta regla renuncia a capturar, declarado:** la forma del error puede variar por estación
(climatología local) y este diseño la asume común dentro del lead. Es una simplificación forzada por
n, no una afirmación empírica. Queda como limitación en cualquier informe que use M2.

## 4. Regla walk-forward (as-of estricta)

Para un pronóstico con fecha objetivo `D` y ancla `T = endDate − lead`:
- **Historia admisible:** pares de la misma estación (o del mismo estrato de repliegue) con
  `target_date ≤ D − 2` **y** cuya observación tenga `available_at ≤ T`.
- El desfase de 2 días replica la convención congelada en V2/V3. **Corrección heredada de la
  refutación de R18:** a leads de 36 h/48 h ese desfase no garantiza disponibilidad, por lo que el
  corte es `target_date ≤ D − 2 − ceil(lead/24)`. Con los leads primarios (9 h, 24 h) equivale a `D−2`.
- **Mínimo:** `n ≥ 20` en el estrato elegido (§3). Sin imputación, sin relleno, sin ventana móvil que
  cruce hacia el futuro.
- **`quantiles_available_at`** = `max(available_at)` de las observaciones usadas. Se persiste. Toda
  lectura as-of de los cuantiles usa esa columna, no `ingestion_timestamp`.
- **OBSERVADO y declarado:** hoy `weather_observations.available_at` procede de captura propia; para
  el histórico de IEM anterior a la captura prospectiva es `NULL`, y una fila con `available_at NULL`
  **no es historia admisible** cuando se exige as-of. Esto acota M2 al periodo con captura real.

## 5. Derivación de los cinco cuantiles

Sea `b` el sesgo del estrato (mediana de `e`) y `q_p` el cuantil `p` de la **forma** `e − b` del lead.
Como `Y = f − e`:

```
forecast_p10 = f − b − q_90        forecast_p25 = f − b − q_75
forecast_p50 = f − b − q_50        forecast_p75 = f − b − q_25
forecast_p90 = f − b − q_10
```
**La inversión de índice es deliberada** (el cuantil alto del error da el cuantil bajo de `Y`) y es
el punto donde un error de signo pasaría desapercibido: **test obligatorio** que verifique
`forecast_p10 ≤ p25 ≤ p50 ≤ p75 ≤ p90` y que, con `e` simulado de media 0 y forma conocida, los
cuantiles recuperan la distribución de `Y`.
Cuantiles empíricos por interpolación lineal (`numpy`-`linear` / método 7); sin suavizado, sin
ajuste paramétrico, sin recorte de colas. Se persisten en las cinco columnas de `weather_forecasts`
junto a `quantiles_available_at`, `n_history`, `stratum` y `m2_version`.

## 6. Política fail-closed

Sin cuantiles no hay `weather_prob`: el mercado **no entra** en features, señal ni backtest, y se
registra en `markets_excluded`. Motivos, enum cerrado:
`m2_history_insufficient` (`n < 20` tras la escalera) · `m2_no_observation` (sin `Y` para el estrato)
· `m2_observations_not_asof` (`available_at NULL` o `> T` exigiendo as-of) ·
`m2_quantiles_not_monotonic` (violación de orden: es un fallo del cálculo, nunca se corrige *in situ*).

## 7. Criterio de calibración — congelado antes de ver resultados

M2 no se juzga por su MAE (eso es M1, ya decidido) sino por **calibración**:
- **PIT:** `u = F̂(Y)` con `F̂` la CDF implícita en los cinco cuantiles (interpolación lineal a trozos,
  la misma de `probability.quantiles_to_distribution`). Bajo calibración perfecta `u ~ U(0,1)`.
- **Cobertura empírica** de los intervalos [p10,p90] (nominal 80 %) y [p25,p75] (nominal 50 %),
  con IC de Wilson al 95 %, **calculada sólo sobre predicciones out-of-sample** por la regla §4.
- **Segmentación obligatoria:** por lead, por componente ICON y por estación usada / no usada en
  MODELSEL (`STATION_REGION_COMPONENT_v1.json`, campo `in_modelsel`: 24 vs 31).
- **Veredicto congelado:** M2 se declara **CALIBRADO** si el IC95 de la cobertura de [p10,p90]
  contiene 0,80 **y** el de [p25,p75] contiene 0,50, **en ambos leads**. Si alguno lo excluye →
  **NO CALIBRADO**, y M2 no se usa para generar señal hasta revisarlo con un preregistro nuevo.
  **No se ajusta el modelo para pasar el criterio**: eso sería cambiar la regla tras ver el resultado.

## 8. Lo que ya se sabe del error y que NO se usa para diseñar (transparencia)

Al medir el sustrato (§1) se observó el error global: `n = 2.545`, media **−0,451 °C**, mediana
−0,400, sd 1,542; `p10 = −2,20`, `p50 = −0,40`, `p90 = +1,30`; por lead, sd 1,486 (9 h) y 1,596 (24 h).
Es decir: **M1 subestima el máximo diario en ~0,45 °C y el error es asimétrico**, con cola larga por
abajo. Se declara aquí **porque ya lo he visto** y la honestidad del preregistro lo exige — pero
ninguna decisión de §2–§7 se ha tomado a partir de ello: la estratificación sale del tamaño muestral,
el estadístico de localización (mediana) de la robustez a colas, y el criterio de §7 es el nominal de
cobertura. Si alguna de esas elecciones pareciera favorecida por estas cifras, la refutación debe
señalarlo.

## 9. Artefactos y dependencias

Producirá `M2_ERROR_QUANTILES.json` (forma por lead, sesgo por estrato, `n`) y poblará las cinco
columnas. Depende de: B para `weather_forecasts` y `weather_observations` sobre la ventana
recuperable (A-28); no depende del operador de settlement (§0).
**Sujeto a A-29.4:** este preregistro no se considera vigente hasta pasar una refutación hostil sin
hallazgos bloqueantes abiertos.
