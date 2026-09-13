# F3-CLOSURE-REPORT
Artefacto de investigacion. NO forma parte del repositorio del proyecto.
Generado 2026-09-05. READ-ONLY. Muestra: 307 pasadas, 20 fechas, 4 modelos, 4 ciclos.

## 1. Semantica de created_at
EVIDENCIA B (fuerte indirecta): README de open-meteo/open-data, verbatim:
  "Upon completion, metadata is written to data_run/<model>/<run>/meta.json."
EVIDENCIA D (desconocida): el campo `created_at` NO esta documentado en ninguna parte.
  El README no dice que representa, ni la relacion con la disponibilidad en la API.
REFUTACION EMPIRICA de "created_at = fin de todas las escrituras":
  101/230 objetos temperature_2m.om tienen Last-Modified POSTERIOR a created_at.
  Retraso maximo observado: 93.7 min (ukmo 2026-06-28 1800Z).
  Por tanto created_at NO marca el instante en que todos los datos estan escritos.

## 2. Evidencia S3 (categoria A: observada directamente)
Latencia created_at - init, horas:
  dwd_icon                         n=78   min=3.44 p05=3.58 med=3.83 p95=4.17 MAX=4.76
  ncep_gfs025                      n=77   min=5.55 p05=5.60 med=6.24 p95=6.78 MAX=6.93
  ukmo_global_deterministic_10km   n=77   min=6.89 p05=6.89 med=7.19 p95=8.21 MAX=10.01
  ecmwf_ifs025                     n=75   min=7.06 p05=7.07 med=7.67 p95=7.98 MAX=8.68

## 3. Evidencia API
n=1. Unica observacion: ecmwf_ifs025 2026-09-05 00z, S3 created_at=07:40:22Z,
API last_run_availability_time=07:42:21Z, delta=+2.0 min.
La API expone SOLO la ultima pasada -> la disponibilidad historica de la API NO es recuperable.
No se simula la serie. Categoria D.

## 4. Delta S3 -> API
No calculable historicamente (n=1). Se reporta la unica observacion y nada mas.
Delta Last-Modified - created_at (proxy interno, NO es el delta a la API):
  n=230 min=-16.45 p05=-10.68 med=-0.74 p95=+17.18 max=+93.70 minutos
  128/230 negativos (objeto escrito ANTES del meta).

## 5. Robustez temporal
Latencias estables jun-sep; junio ligeramente mas alto en los 4 modelos.
Outliers: ukmo 2026-06-13 0600Z = 10.01 h; ecmwf 2026-06-28 1800Z = 8.68 h.
AVISO: al pasar de 20 a 307 observaciones, el MAXIMO subio en los 4 modelos.
La cola de la distribucion NO esta caracterizada.

## 6. Robustez por modelo/ciclo
Orden ICON < GFS < UKMO < ECMWF se cumple en 61/75 slots completos (81.3%).
Violaciones: ukmo supera a ecmwf, concentradas en 2026-06-03 y 2026-06-08.
ICON es el mas rapido en el 100% de los slots. El resto del orden NO es invariante.
Patron por ciclo estable en ecmwf: 00z/12z ~7.75 h vs 06z/18z ~7.11 h.

## 7. Politica available_at recomendada
NO se puede afirmar available_at = created_at (refutado, seccion 1).
NO se puede afirmar created_at <= available_at (mismo motivo).
Construccion defendible:
  availability_safe_at := max(created_at, LastModified(variable)) + DELTA_API
DELTA_API NO esta demostrado (n=1). Cota compuesta maxima observada, horas:
  dwd_icon                         med=3.84 p95=4.22 MAX=4.76
  ncep_gfs025                      med=6.24 p95=6.78 MAX=6.93
  ukmo_global_deterministic_10km   med=7.20 p95=8.37 MAX=10.48
  ecmwf_ifs025                     med=7.67 p95=7.98 MAX=8.78

## 8. Estado por periodo
2026-06-03 -> actualidad : PARTIAL
2026-04-02 -> 2026-06-02 : UNKNOWN

## 9-12
Ver informe en la conversacion: impacto sobre leads, MODEL-SELECTION, diseno prospectivo,
limitaciones.
