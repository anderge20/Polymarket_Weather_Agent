# PREREG_MODELSEL_GEOVAL_V3 — validacion CONFIRMATORIA de generalizacion geografica
Congelado ANTES de consultar la muestra o calcular metrica alguna. READ-ONLY.
NO modifica ni reinterpreta PREREG_MODELSEL_ASOF_V2 (sha 2b815fcb...). V2 queda intacto.
Esta ronda NO puede cambiar la metrica ni el criterio de V2: es CONFIRMATORIA.

## 0. Pregunta unica
"Se generaliza la ventaja de icon_seamless sobre ecmwf_ifs025 fuera de la concentracion
geografica de V2 (7 de 8 estaciones en EE.UU.)?"
No se declara un ganador nuevo mediante un umbral nuevo.

## 1. Modelos
PRINCIPALES: icon_seamless, ecmwf_ifs025.
SECUNDARIOS (contexto, no deciden): gfs_seamless, ukmo_global_deterministic_10km.

## 2. Regiones (definidas ANTES de ver datos)
EUROPA        : EGLC EFHK LIMC UUWW
ASIA_ESTE     : RKSI ZSJN ZSQD ZGSZ
ASIA_SUR      : VILK OPKC
ORIENTE_MEDIO : LLBG LTFM
HEM_SUR       : FACT SBGR
LATAM_NORTE   : MMMX MPMG
Cuotas objetivo: Europa >=3, Asia (este+sur) >=3, Oriente Medio >=2, Hem. Sur >=2.
Objetivo global: >=12 estaciones y >=120 eventos.
Si el catalogo no permite cumplir una cuota, se DOCUMENTA el motivo y no se sustituye
por estaciones de otra region para "rellenar".

## 3. Muestra — determinista, input-side
Universo: primary_rule != P_byForecast; ICAO presente; timezone resuelta;
target_date en [2026-06-03, 2026-09-04];
event_id NO en MODELSEL_ASOF_V2_SAMPLE.json ni en MODELSEL_SAMPLE.json (v1);
estacion NO en {KATL,KBKF,KDAL,KHOU,KLAX,KLGA,KMIA,ZUCK} (estaciones de V2).
Seleccion: toda estacion de la lista de regiones con >=25 eventos elegibles.
Dentro de cada estacion: ordenar por target_date asc y tomar 25 equiespaciados
(indices round(i*(N-1)/24), i=0..24).
Ninguna estacion puede aportar mas del doble de eventos que la que menos aporte.

## 4. Periodo
2026-06-03 -> 2026-09-04. Fail-closed fuera de ese rango.

## 5. T y leads
T := endDate - lead_hours ; endDate = target_date 12:00:00Z. Ancla 2E D1, sin cambios.
Leads PRIMARIOS: 9h y 24h. 1h/6h NO se usan como criterio.

## 6. Disponibilidad — IDENTICA a V2, sin modificar
availability_safe_at(run) = init + L_max(model), L_max = MAXIMO observado en F-3 (n=307):
  icon 4.76h | gfs 6.93h | ukmo 10.48h | ecmwf 8.78h
run usable = el de mayor init con availability_safe_at <= T. Si no existe -> no evaluable.
PROHIBIDO usar issue_time <= T.

## 7. Forecast
f := max(hourly.temperature_2m del run usable) sobre W(m) = dia civil local de la estacion.
Identica para todos los modelos. Unidad C. Se registran coordenadas pedidas, coordenadas
devueltas, distancia, edad del run y run seleccionado.

## 8. Label
Y_final := max(cuerpo METAR, C entero) sobre W(m), via IEM ASOS.
"evaluation label available retrospectively after settlement". NO es Y_asof_T.

## 9. Desbiasing — IDENTICO a V2, sin modificar
historia(e) = eventos de la MISMA estacion y modelo con target_date <= D - 2 dias.
Si |historia| < 10 -> NO EVALUABLE, sin imputacion.
bias_hat = media(f - Y_final) sobre historia. residual = (f - bias_hat) - Y_final.
METRICA PRIMARIA = MAE(|residual|).

## 10. Metricas secundarias
MAE bruto, bias, RMSE, MedAE, correlacion, n, cobertura, por lead, por region, por estacion.

## 11. Igualdad de run
Se identifican los pares donde run_ICON == run_ECMWF y se calcula el MAE residual de
cada modelo SOLO sobre esos pares. Separa exactitud de frescura.

## 12. Frescura
Se reporta run_age_ICON y run_age_ECMWF por separado. La edad NO entra en la metrica
de exactitud.

## 13. Robustez leave-one-station-out
Se recalcula la diferencia global de MAE residual excluyendo cada estacion, una a una.

## 14. CATEGORIAS DE INTERPRETACION (congeladas)
A. CONFIRMACION FUERTE : icon menor MAE_res global Y en AMBOS leads primarios
   Y en >=75% de estaciones Y en >=75% de regiones Y ninguna region donde ecmwf gane
   en los dos leads Y la ventaja global no se anula al excluir ninguna estacion.
B. CONFIRMACION PARCIAL: icon menor global y en ambos leads, pero existe al menos una
   region donde ecmwf gana en los dos leads, o gana en <75% de estaciones.
C. NO CONFIRMADO       : icon menor global pero la ventaja se anula al excluir alguna
   estacion, o gana en <50% de estaciones.
D. REFUTADO            : ecmwf menor MAE_res global.
Se elige la categoria por los resultados, no por conveniencia.

## 15. Prohibiciones
No ejecutar M2/M3. No fijar M1 en el proyecto. No escribir weather_forecasts.
No modificar nada del proyecto. No commit/push.
