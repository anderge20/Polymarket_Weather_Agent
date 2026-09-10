# PREREG_M2_ERROR — distribución de error de pronóstico (M2)

**Sesión:** B (Claude) · **Fecha de congelación:** 2026-09-09
**Estado:** CONGELADO antes de calcular ninguna métrica. Ningún cuantil, sesgo, MAE ni
error se ha computado sobre estos datos. La comprobación de integridad de B-5 fue
deliberadamente gruesa (sólo detección de sustrato roto) y **no** caracterizó el error.

**Por qué lo escribe B y no A:** A reclamó M2 en su respuesta a B-2 y aceptó el reparto,
pero lleva 7 h inactiva y la ventana de objeción de D13 expiró sin respuesta. El mandato
es terminar. Se congela y hashea **antes** de ejecutar precisamente para que A pueda
objetar sobre un documento y no sobre resultados ya vistos. Si A objeta, se revierte:
todo lo que produce este preregistro son artefactos nuevos.

---

## 0. Pregunta única

> Dado un pronóstico determinista de máxima diaria `f` (M1 = `icon_seamless`, D12) para una
> estación y un lead, ¿cuál es la distribución del error `e = y − f`, y qué cuantiles
> `p10, p25, p50, p75, p90` deben escribirse para que `quantiles_to_distribution` produzca
> una distribución de probabilidad utilizable por `band_probability`?

M2 **no** decide qué modelo usar (eso fue M1) ni cómo apostar (eso será M3).

## 1. Muestra — declarada antes de mirar

`weather_forecasts` × `weather_observations`, emparejados por `(station, target_date)`:

```
pares:      2 595        (1 298 station-days × 2 leads, menos huecos)
estaciones: 49
fechas:     136          2026-04-08 → 2026-09-02
estaciones con >= 20 pronósticos: 45
```

Cota superior fijada por B-1: el archivo de Single Runs es una ventana deslizante de ~5
meses. Este periodo **no es ampliable hacia atrás**.

## 2. Definición del error

`e = y − f`, en **grados Celsius**, ambos ya canónicos:
- `f` = `weather_forecasts.forecast_tmax`, Open-Meteo nativo en °C.
- `y` = máximo METAR sobre la **misma ventana de día local** que produjo `f` (B-4).

El signo se fija aquí: **positivo = la realidad superó al pronóstico**. No se cambia después.

## 3. Unidad de la distribución — regla de B-7, congelada

La distribución se construye **en la unidad contractual del mercado**, no en °C:
- mercado en °C → cuantiles en °C, directos;
- mercado en °F → cuantiles convertidos a °F **después** de sumarse al pronóstico, con
  `°F = °C × 9/5 + 32` para el nivel y `× 9/5` para el error (que es una diferencia).

**Razón, medida:** `quantiles_to_distribution` indexa por enteros y la rejilla de resolución
del contrato es de grado entero en su propia unidad (bandas de anchura 0 en °C, 1 en °F).
Convertir las bandas a °C las dejaría de 0,56 °C, desalineadas con los enteros. Las bandas
**no se tocan**.

## 4. Estratificación — congelada, con umbral declarado ANTES

Con ~26 station-days por (estación, lead), estimar nueve cuantiles por estación es
sobreajustar. Regla:

- **Primario:** distribución agrupada **por lead** (9 h y 24 h por separado). Los leads no
  se mezclan: el error crece con el horizonte y mezclarlos produciría una distribución que
  no describe ninguno de los dos.
- **Secundario:** por `(estación, lead)` **sólo si n ≥ 30** en la ventana de entrenamiento.
  Por debajo, se usa el agrupado y se marca `error_scope='POOLED'` en la fila.
- **No** se estratifica por región, mes ni componente ICON en esta versión. Añadirlo tras
  ver resultados sería exactamente lo que §18 de V5 prohíbe. Queda para M2.1 con su propio
  preregistro.

## 5. Walk-forward — sin mirar al futuro

Para una fecha objetivo `D`, la distribución de error usa **únicamente** pares con
`target_date < D`. Ventana expansiva, no deslizante. Mínimo 30 pares para emitir cuantiles;
por debajo, la fila queda **sin cuantiles** y `build_feature` devolverá `None`, que es el
comportamiento correcto: sin error caracterizado no hay probabilidad honesta.

Consecuencia aceptada: las primeras semanas de abril quedan sin cobertura. No se rellenan
hacia atrás.

## 6. Disponibilidad de la etiqueta — LIMITACIÓN DECLARADA, no resuelta

`weather_observations.available_at` es el instante de descarga (B-4), no la publicación
real, que la ingesta retrospectiva **no puede probar**. Un filtro as-of estricto no
devolvería nada y el backtest sería imposible.

Se asume, **declarándolo**, que el máximo diario de una estación estaba disponible **24 h
después del fin de su día local**. Es cierto en la práctica para METAR y es la misma
limitación que D17 ya registró al adoptar `Y_final`. **Es un supuesto, no una medición.**
La captura prospectiva de D17 es lo que producirá un as-of demostrado; hasta entonces todo
informe que use estos cuantiles debe repetir esta frase.

## 7. Cómo se obtienen los cuantiles

Cuantiles empíricos de `e` sobre la ventana de entrenamiento, por interpolación lineal
(`numpy.percentile`, método por defecto), en los niveles 10, 25, 50, 75, 90.

`forecast_pXX = f + percentil_XX(e)`.

Sin suavizado, sin ajuste paramétrico, sin recorte de colas. Si la distribución resulta
sesgada o de colas gruesas, se **reporta**; no se corrige a posteriori.

## 8. Criterio de suficiencia — congelado

Una fila recibe cuantiles sólo si:
1. n ≥ 30 en su ventana de entrenamiento;
2. los cinco cuantiles son finitos y monótonos (`p10 ≤ p25 ≤ p50 ≤ p75 ≤ p90`);
3. la anchura `p90 − p10` es > 0 y < 30 °C — fuera de ese rango se declara
   `error_scope='REJECTED'` y no se escribe nada. Una anchura de 0 significa muestra
   degenerada; una de 30 °C significa que algo está roto, no que el clima sea incierto.

## 9. Universo excluido — declarado ANTES

- **1 936 mercados con `rounding_rule='tenths'`** (2,1 % del catálogo): una distribución de
  claves enteras no puede representarlos. **No es convertible.** Quedan fuera del universo
  operable de esta versión y se cuentan como `UNSUPPORTED_ROUNDING`.
- Estaciones sin huso horario conocido: ya rechazadas en la ingesta (B-4).
- Estaciones sin observación suficiente: rechazadas por la guarda de horas de máximo (B-4).

## 10. Prohibiciones

- No se calcula ningún cuantil antes de que este documento esté hasheado.
- No se cambia la estratificación, el umbral n ≥ 30, los niveles de cuantil ni el criterio
  de suficiencia después de ver resultados.
- No se escriben cuantiles en filas que no cumplan §8.
- No se rellena hacia atrás el periodo sin entrenamiento.
- No se toca `outcomes.lo/hi`: las bandas se escriben en la unidad contractual (B-7).
- No se ejecuta M3 ni se envía ninguna orden. Gate D0 intacto.

## 11. Entregables

`M2_ERROR_QUANTILES.json` (los cuantiles por estrato y ventana) · `M2_REPORT.md` con la
caracterización del error y las limitaciones de §6 y §9 · escritura de
`forecast_p10..p90` en `weather_forecasts` · `.sha256` de todo.
