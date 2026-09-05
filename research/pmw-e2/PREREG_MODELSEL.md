# PRE-REGISTRO — benchmark de modelos forecast (M1)
Congelado ANTES de calcular ninguna métrica.
ETIQUETA OBLIGATORIA DEL RESULTADO: FORECAST_ACCURACY_BENCHMARK — availability unresolved.
NO es evidencia OOS. NO valida ninguna estrategia.

## Modelos candidatos (pasadas históricas explícitas en Single Runs API, verificado)
ecmwf_ifs025 · gfs_seamless · icon_seamless · ukmo_global_deterministic_10km · jma_gsm
EXCLUIDOS: era5 (reanálisis, no pasada operativa); ecmwf_ifs04, ecmwf_aifs025, gem_global
(sin pasadas históricas); meteofrance_arpege_world (cobertura parcial 103/168 -> sesgaría).
gfs_global / icon_global excluidos por duplicar la celda de las variantes _seamless.

## Universo
Eventos de CATALOG_V2 con: primary_rule != P_byForecast; ICAO presente; timezone de estación
resuelta desde metadatos IEM; target_date >= 2026-04-02 (inicio del archivo de pasadas).

## Regla de selección de muestra — determinista, input-side
1. Estaciones: las 12 con mayor número de eventos elegibles, desempate por ICAO ascendente.
2. Dentro de cada estación: ordenar eventos por md5(event_id) ascendente; tomar los 4 primeros.
3. Muestra = 12 estaciones x 4 eventos = 48 eventos.
Ningún criterio usa Y, el forecast, ni ninguna métrica.

## Y (verdad de contraste)
Y := max(grupo de cuerpo METAR, °C entero) sobre W(m) = día civil local de la estación,
     vía IEM ASOS. Es Y_validation (fuente independiente), NO la fuente de settlement.

## Definición de f — IDÉNTICA para los 5 modelos
f := max(hourly.temperature_2m del run seleccionado) restringido a W(m),
     mismo W(m), misma unidad (°C), mismo target_date, misma regla de run.
Se verificará por separado la equivalencia con daily.temperature_2m_max.

## Leads y selección de run  (T = endDate - lead_hours; endDate = target_date 12:00Z)
lead  1h -> T = td 11:00Z -> run = td 06:00Z
lead  6h -> T = td 06:00Z -> run = td 06:00Z
lead  9h -> T = td 03:00Z -> run = td 00:00Z
lead 24h -> T = (td-1) 12:00Z -> run = (td-1) 12:00Z
Regla: pasada más reciente con issue_time <= T, sobre la rejilla {00,06,12,18}.
ADVERTENCIA REGISTRADA: issue_time <= T NO es available_at <= T. No se afirma validez as-of.

## Métricas
MAE (PRIMARIA); RMSE; bias (f - Y); error absoluto mediano; correlación de Pearson;
n; n efectivo ajustado por autocorrelación por estación. Desglose por lead y por estación.

## Criterio de selección — fijado antes de ver resultados
Se sustituye ecmwf_ifs025 SOLO SI un modelo alternativo cumple LAS TRES:
 (a) MAE global estrictamente menor que ecmwf_ifs025;
 (b) MAE menor en >= 3 de los 4 leads;
 (c) MAE menor en >= 2/3 de las estaciones (>= 8 de 12).
Si no se cumplen las tres -> se CONSERVA ecmwf_ifs025 como baseline, DECISIÓN PROVISIONAL.
No se cambia la métrica primaria después de ver resultados.
La distancia a la estación NO penaliza por sí sola; se reporta como análisis espacial.
