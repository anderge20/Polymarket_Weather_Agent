# PREREG_MODELSEL_ASOF_V2 — benchmark AS-OF de modelos forecast (M1)
Congelado ANTES de consultar la muestra o calcular metrica alguna. READ-ONLY.
El benchmark anterior (MODELSEL v1) queda marcado INVALID_AS_OF y NO se reutiliza.

## 0. Etiqueta del resultado
FORECAST_ACCURACY_BENCHMARK_ASOF_V2 — availability bound = empirical, not guaranteed.
La politica de disponibilidad es una COTA EMPIRICA, no una verdad demostrada.

## 1. Modelos
ecmwf_ifs025 · icon_seamless · gfs_seamless · ukmo_global_deterministic_10km
EXCLUIDO jma_gsm: no dispongo de cota de latencia con muestra suficiente (n=5 en F-3);
sin cota defendible no puede seleccionarse su run. Se documenta la exclusion.
EXCLUIDO era5 (reanalisis). EXCLUIDOS modelos sin archivo de runs comparable.

## 2. Politica de disponibilidad  (availability_safe_at)
availability_safe_at(run) := init_time(run) + L_max(model)
L_max = MAXIMO observado de max(created_at, LastModified(variable)) - init
        en la auditoria F-3 (n=307 pasadas, 20 fechas, jun-sep 2026):
  icon_seamless (dwd_icon global)          L_max = 4.76 h
  gfs_seamless  (ncep_gfs025 global)       L_max = 6.93 h
  ukmo_global_deterministic_10km           L_max = 10.48 h
  ecmwf_ifs025                             L_max = 8.78 h
Se usa el MAXIMO por modelo (no la mediana): fail-closed.
ADVERTENCIA REGISTRADA: es una cota empirica sobre 307 observaciones; el maximo
crecio al ampliar la muestra de 20 a 307, luego la cola NO esta caracterizada.
NO se usa issue_time <= T en ningun punto.
La disponibilidad NO se iguala entre modelos: la publicacion mas rapida es una
ventaja operativa real y forma parte de la comparacion.

## 3. Seleccion de run
run usable(modelo, T) := el run de mayor init_time de la rejilla {00,06,12,18} tal que
                         availability_safe_at(run) <= T
Si no existe ninguno -> evento no evaluable para ese modelo (no se imputa).

## 4. T y leads
T := endDate - lead_hours ; endDate = target_date 12:00:00Z  (ancla 2E D1 ratificada)
PROHIBIDO usar daily_high_time o last_meaningful_market_time.
Leads PRINCIPALES : 9 h, 24 h
Leads SECUNDARIOS : 1 h, 6 h
Si dos leads seleccionan el MISMO run, NO se cuentan como informacion independiente:
se reporta la coincidencia y solo uno entra en los agregados principales.

## 5. Periodo
2026-06-03 -> 2026-09-04 exclusivamente (inicio del archivo data_run de disponibilidad).
Fail-closed: cualquier fecha fuera queda excluida. No se usan datos anteriores.

## 6. Muestra — determinista, input-side, INDEPENDIENTE de MODELSEL v1
Universo: eventos con primary_rule != P_byForecast, ICAO presente, timezone de estacion
resuelta desde metadatos IEM, target_date en [2026-06-03, 2026-09-04],
y event_id NO presente en MODELSEL_SAMPLE.json (v1).
1. Estaciones: las 8 con mayor numero de eventos elegibles; desempate por ICAO ascendente.
2. Dentro de cada estacion: ordenar por target_date ascendente y tomar 30 eventos
   equiespaciados (indices round(i*(N-1)/29), i=0..29).
3. Muestra = 8 estaciones x 30 eventos = 240 eventos.
Ningun criterio usa Y, el forecast, ni ninguna metrica.

## 7. Target y definicion de f
f := max(hourly.temperature_2m del run usable) restringido a
     W(m) = [medianoche local(target_date), medianoche local(target_date+1))
     con timezone de la ESTACION. Identica para los 4 modelos. Unidad °C.
Se documentan: coordenadas solicitadas, coordenadas devueltas, distancia, timezone,
variable y resolucion temporal.

## 8. Label
Y_final := max(grupo de cuerpo METAR, °C entero) sobre W(m), via IEM ASOS.
ETIQUETA OBLIGATORIA: "evaluation label available retrospectively after settlement".
NO se afirma que Y_final sea Y_asof_T. No se usa como feature ni para elegir el run.

## 9. METRICA PRIMARIA — MAE residual WALK-FORWARD
Para cada evento e de estacion s con target_date D:
  historia(e) := eventos de la MISMA estacion y modelo con target_date <= D - 2 dias
  si |historia(e)| < 10  -> evento NO EVALUABLE (no se imputa)
  bias_hat(s, e) := media de (f - Y_final) sobre historia(e)
  residual(e)    := (f(e) - bias_hat(s,e)) - Y_final(e)
  METRICA PRIMARIA := MAE(|residual|)
El desfase de 2 dias garantiza que la observacion historica ya estaba disponible en T
(latencia de settlement observada ~1,3 h tras el fin de la ventana).
PROHIBIDO estimar el bias con toda la muestra y evaluar sobre la misma muestra.

## 10. Metricas secundarias
MAE bruto · bias · RMSE · MedAE · correlacion · n · cobertura ·
error por lead · por estacion · por mes · edad del run en T.

## 11. Comparacion pareada ICON vs ECMWF
Solo eventos donde AMBOS tienen forecast usable. Diferencia de |residual|.
Bootstrap por BLOQUES DE ESTACION (respeta la dependencia temporal/estacional intra-estacion).
IC95%. 4000 remuestreos, semilla 20260905.

## 12. CRITERIO DE DECISION  (congelado)
Primario: menor MAE residual walk-forward.
Condiciones minimas para declarar un ganador distinto de ecmwf_ifs025:
  (a) cobertura >= 80% de los eventos elegibles;
  (b) la ventaja no puede apoyarse en menos de 3 estaciones;
  (c) menor MAE residual en LOS DOS leads principales (9h y 24h);
  (d) ninguna estacion individual aporta > 50% de la ventaja agregada.
"PRACTICAMENTE EMPATADOS" := |diferencia de MAE residual| < 0.10 °C
                             O el IC95% del bootstrap pareado incluye 0.
Si empatan: prioridad 1) mayor cobertura, 2) mayor frescura (menor edad del run en T),
            3) menor complejidad operativa.
Si NO se cumplen todas las condiciones -> se CONSERVA ecmwf_ifs025, PROVISIONAL.
No se cambia la metrica primaria despues de ver resultados.

## 13. Parada sin seleccion
Se informa y se PARA sin seleccionar modelo si: cobertura < 80%, o < 3 estaciones con
datos, o el walk-forward deja < 50% de eventos evaluables, o la cota de disponibilidad
resulta inaplicable en el periodo.
