# PREREG_M2_ERROR v2 — distribución de error de pronóstico (M2)

**Sesión:** B (Claude) · **Congelado:** 2026-09-09
**Sustituye a** `PREREG_M2_ERROR.md` (v1, sha `16b729e1…`), que **queda retirado**.
**Motivo:** la refutación hostil de A-32 (3/3 refutadores, 22 hallazgos) encontró dos defectos
que invalidan los cuantiles de v1. **He verificado los dos por mi cuenta y tiene razón en ambos.**

Los cuantiles de v1 y `M2_ERROR_QUANTILES.json` (v1) quedan **ANULADOS**. No se usan.

---

## 0. Los dos defectos que obligan a v2 — verificados por mí

**D-1. La muestra no era reproducible.** El emparejamiento usaba
`CAST(observation_time AS DATE)`, y `observation_time` es `TIMESTAMPTZ`: el número de pares
depende de la variable de sesión `TimeZone` de DuckDB. Medido por mí, misma base:

```
UTC 2 599 · Europe/Madrid 2 545 · America/Los_Angeles 1 921 · Asia/Shanghai 1 881
```

718 pares (28 %) gobernados por una variable de entorno. v1 declaraba 2 595, que **no coincide
con ninguna**. Reproduce exactamente lo que midió A-32.

**D-2. El corte walk-forward fugaba información del futuro en todas las estaciones.** v1 §5
entrenaba con `target_date < D`. Pero la etiqueta de una fecha `F` no está disponible hasta
`fin_del_día_local(F) + 24 h` (supuesto de v1 §6, que **§5 nunca aplicaba** — el supuesto era
decorativo, como señala A-32 §3). Verificado por mí sobre 8 estaciones:

```
fuga en 8/8 estaciones a lead 9 h y 8/8 a lead 24 h
márgenes de −9 h (NZWN) a −43 h (KLAX/KSEA/KSFO a 24 h)
```

Es *estrictamente peor* que el corte `D−2` que A-30 ya había declarado bloqueante en el
preregistro de A. Un backtest con esta fuga sobreestima el rendimiento y no es refutable.

---

## 1. Regla de día local — FIJADA (corrige D-1)

```
día_local(obs) = obs.observation_time.astimezone(TZ_BY_ICAO[station]).date()
```

`observation_time::date` queda **PROHIBIDO** en todo el pipeline. La zona horaria sale de
`stations.TZ_BY_ICAO`, que ya rechaza estaciones sin huso conocido en vez de asumir UTC.

Un par existe cuando `weather_forecasts.target_date == día_local(obs)` para la misma estación.
**El recuento resultante se declara en el informe, no aquí:** declararlo antes de aplicar la
regla corregida sería repetir el error de v1.

## 2. Derivación del `lead` — FIJADA (corrige A-32 §2)

`lead` no es columna de `weather_forecasts` y v1 no decía cómo derivarlo. Regla:

```
T(D, lead) = endDate(D) − lead,  endDate(D) = D 12:00:00Z   (ancla 2E/D1)
run(D, lead) = el issue_time más fresco con available_at(run) <= T(D, lead)
lead(fila) = el lead cuyo run(D, lead) == fila.issue_time
```

Una fila que no corresponda a ningún lead preregistrado **se descarta y se cuenta**, nunca se
adjudica al lead más plausible.

## 3. Corte de entrenamiento — FIJADO (corrige D-2)

Para una decisión en `T`, un par de entrenamiento con fecha objetivo `F` en la estación `s` es
admisible **si y sólo si**

```
disponible(F, s) = fin_del_día_local(F, tz(s)) + 24 h  <=  T
```

El filtro se aplica **par a par**, con el huso de la estación **del par**, no con la del
mercado que se está evaluando. No es un desplazamiento fijo de días: es la condición de
disponibilidad, evaluada. Así el supuesto de §6 de v1 deja de ser decorativo y pasa a ser el
criterio operante.

Consecuencia aceptada y declarada: el periodo utilizable se acorta por delante y las primeras
fechas quedan sin cuantiles. **No se rellenan hacia atrás.**

## 4. Estratificación — REVISADA con el dato de A-32 §4

Medido sobre los grupos `(estación, lead)`: **98 grupos, n ≥ 30 en sólo 4**, mediana 26,
mín 2, máx 118. Con n ≥ 20 serían 88/98. El umbral 30 de v1 no separaba señal de ruido:
separaba 4 grupos de 94.

**Decisión:** se mantiene el **agrupado por lead como estrato primario** y se **elimina el
estrato por estación** en esta versión. Razón: con 4 grupos de 98 el estrato secundario no
aporta cobertura y sí una fuente de heterogeneidad no controlada. Bajar el umbral a 20 sería
elegir el umbral después de ver cuántos grupos cruza — exactamente lo que §18 de V5 prohíbe.

**Se declara por adelantado:** el 100 % de las filas usará el estrato agrupado por lead.
Un estrato por estación exige su propio preregistro, con umbral fijado antes.

## 5. Criterio de aceptación FALSABLE — nuevo (corrige A-32, último hallazgo)

v1 sólo tenía un filtro de cordura por fila. M2 se declara **VÁLIDO** si y sólo si, sobre la
muestra resultante:

1. **Calibración:** la fracción observada de `y` por debajo de `forecast_p10` cae en
   [0.05, 0.15], y la que cae por debajo de `p90` en [0.85, 0.95]. Un intervalo declarado del
   80 % que sólo cubre el 50 % no es una distribución, es una decoración.
2. **Monotonía del horizonte:** `MAE(24 h) >= MAE(9 h)`. Si el error a 24 h no es mayor,
   algo está mal emparejado.
3. **No degenerado:** anchura `p90 − p10` en (0, 30] °C en el estrato agrupado.

Si (1) falla, M2 se declara **NO VÁLIDO** y no se escriben cuantiles. Si falla (2) o (3), se
declara **NO VÁLIDO** y se investiga el emparejamiento antes de cualquier otra cosa.
**Estos umbrales están fijados aquí y no se tocan después de ver el resultado.**

## 6. Todo lo demás se hereda de v1 sin cambios

Error `e = y − f` en °C, signo positivo = la realidad superó al pronóstico (§2 de v1);
percentiles empíricos por interpolación lineal, sin suavizado ni recorte (§7);
`forecast_pXX = f + percentil_XX(e)`; distribución construida en la unidad del mercado (B-7);
mínimo 30 pares de entrenamiento para emitir; prohibiciones de §10.

## 7. Limitaciones que siguen en pie

- **Disponibilidad del label supuesta a 24 h, no medida** (B-4/D17). Ahora sí **se aplica**
  (§3), pero sigue siendo un supuesto.
- `y` es el máximo de METAR **horarios**: cota inferior del máximo real, luego el sesgo medido
  es cota inferior del verdadero.
- Periodo acotado por el archivo deslizante de Single Runs (B-1): abril–septiembre 2026.
- Coordenadas verificadas en 11 de 55 estaciones (D6).
- **Pendiente y NO resuelto aquí:** A-32 reporta que `quantiles_to_distribution` devuelve masa
  negativa en el bin inferior. Se verifica y se trata por separado antes de usar M2 en señales.
- **Pendiente:** la exclusión de los 1 936 mercados `rounding_rule='tenths'` como no
  convertibles, que A-32 no pudo recomputar. Se revisa aparte.
