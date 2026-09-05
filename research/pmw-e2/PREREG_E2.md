# PRE-REGISTRO E2 — identificación empírica de Y
Congelado ANTES de cualquier comparación con observaciones.

## Universo
CATALOG_V2, eventos con: primary_rule ∈ {P_WU_DailyObservations, P_NOAA_TempColumn,
P_NOAA_HourlyData, P_HKO_AbsDailyMax, P_UNKNOWN(CWA)}; partición válida (1 open-low + 1 open-high);
exactamente 1 bracket ganador. EXCLUIDOS: P_byForecast, P_WU_GENERIC_sin_calificador.

## Estratos
S = (primary_rule, unit, rounding_rule)

## Regla de selección — determinista, input-side
1. Dentro de cada estrato, ordenar por md5(event_id) hex ASCENDENTE.
2. Restricción de diversidad: como máximo 1 evento por (city, año-mes).
3. Tomar los primeros k=8 por estrato (todos si hay menos).
Ningún criterio usa el resultado, el ganador, ni concordancia con observaciones.

## target_date
Se extrae del TEXTO de la descripción ("on 29 Aug '26"), NO se asume = date(endDate).
La igualdad target_date == date(endDate) es una hipótesis a verificar, no un supuesto.

## Series candidatas de Y (independientes)
- Y_IEM_body   : máx del grupo de cuerpo METAR (°C entero) vía IEM ASOS
- Y_IEM_tgroup : máx del grupo T del METAR (°C décimas) vía IEM ASOS
- Y_IEM_tmpf   : máx de IEM tmpf (°F entero)
- Y_IEM_tmpc   : máx de IEM tmpc (derivado)
- Y_NWSAPI     : máx de api.weather.gov (PROXY de NOAA Temp column; NO es la misma vista)

## Hipótesis de ventana
- H_UTC        : [00:00Z, 24:00Z) de target_date
- H_LOCAL      : día civil local (IANA tz de la estación)
- H_LOCAL_M1   : día civil local de target_date - 1  (control off-by-one)
- H_LOCAL_P1   : día civil local de target_date + 1  (control off-by-one)

## Métricas (todas, no solo accuracy)
N; coincidencias exactas; discrepancias; error absoluto medio y máx;
distribución completa de diferencias; % brackets compatibles; casos incompatibles listados uno a uno.

## Compatibilidad de bracket
Y compatible si lo <= Y <= hi (extremos abiertos: NULL = sin cota).
NO se aplica round(), floor(), ceil() ni conversión C<->F para forzar coincidencia.
Cualquier operador de ese tipo debe demostrarse por separado.

## Clasificación de conclusiones
DEMONSTRATED / STRONGLY SUPPORTED / UNKNOWN. Alta correlación != identidad.
