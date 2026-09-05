# MODELSEL_ASOF_V2 — informe
FORECAST_ACCURACY_BENCHMARK_ASOF_V2 — availability bound = empirical, not guaranteed.
Pre-registro: PREREG_MODELSEL_ASOF_V2.md sha256
  2b815fcb6b43051b4422a879f3ff0ba53d32b8fe9dd15f1d34c5f6a85af3af46  (congelado 2026-09-05T11:39:45Z)
Muestra:      MODELSEL_ASOF_V2_SAMPLE.json hash
  a0157ed780eccfec7455116585bb349300a3c45025664ad324da79b2e083bf87

## MUESTRA
240 eventos, 8 estaciones, 2026-06-03 -> 2026-09-04, 4 meses.
Solapamiento con MODELSEL v1: 0 eventos.
Estaciones: KATL KBKF KDAL KHOU KLAX KLGA KMIA (US) + ZUCK (Chongqing).
LIMITACION: 7 de 8 estaciones en EE.UU.; todas en hemisferio norte. Es consecuencia
de la regla de seleccion congelada (8 estaciones con mas eventos elegibles). NO se
corrige a posteriori.

## DISPONIBILIDAD (politica declarada)
availability_safe_at(run) = init + L_max(model), L_max = MAXIMO observado en F-3 (n=307):
  icon 4.76h | gfs 6.93h | ukmo 10.48h | ecmwf 8.78h
Cota EMPIRICA, no garantia. El maximo crecio al ampliar la muestra de 20 a 307 pasadas.
jma_gsm EXCLUIDO: sin cota con muestra suficiente.

## COBERTURA
forecast usable: 3840/3840 = 100.0%
walk-forward evaluable: 3456/3840 = 90.0% (identico en los 4 modelos)

## METRICA PRIMARIA — MAE residual walk-forward, leads 9h+24h
  icon_seamless                   1.017   (MAE bruto 1.248, bias +0.203, RMSE 1.569, r 0.942)
  ukmo_global_deterministic_10km  1.153   (1.205, +0.355, 1.599, 0.944)
  gfs_seamless                    1.282   (1.256, +0.122, 1.569, 0.946)
  ecmwf_ifs025                    1.418   (2.129, +0.502, 2.917, 0.787)

## POR LEAD (MAE residual)
              1h      6h      9h     24h
ecmwf      1.286   1.315   1.315   1.521
gfs        1.198   1.317   1.317   1.247
icon       0.895   0.927   0.905   1.129
ukmo       1.160   1.124   1.121   1.184
Leads con run IDENTICO: ecmwf (6h=9h), gfs (6h=9h). icon y ukmo: ninguno.

## POR ESTACION (leads 9h+24h) — mejor modelo
KATL icon | KBKF icon | KDAL icon | KHOU ukmo | KLAX icon | KLGA icon | KMIA ukmo | ZUCK icon
icon 6/8, ukmo 2/8, ecmwf 0/8. icon < ecmwf en 8/8 estaciones.

## POR MES (MAE residual)
              06      07      08      09
ecmwf      1.356   1.521   1.381   1.261
gfs        1.237   1.377   1.251   1.088
icon       1.086   0.971   0.984   1.187
ukmo       1.298   1.139   0.994   1.504
icon es el mejor en 3 de 4 meses; en 2026-09 gana gfs.

## CONTRASTE PAREADO icon vs ecmwf (mismos eventos)
n=432 pares. Delta|residual| medio = -0.4015 C
IC95% bootstrap por bloques de estacion (4000, semilla 20260905): [-0.5820, -0.2383] EXCLUYE 0

## EDAD DEL RUN EN T (horas)
              1h      6h      9h     24h
ecmwf       11.0    12.0     9.0    12.0
gfs         11.0    12.0     9.0    12.0
icon         5.0     6.0     9.0     6.0
ukmo        11.0    12.0    15.0    12.0
NOTA CLAVE: a lead 9h icon y ecmwf usan LA MISMA pasada (edad 9h). La ventaja de icon
alli (0.905 vs 1.315) NO es frescura: es exactitud a igualdad de antiguedad.

## ANALISIS ESPACIAL
  icon  dist media 4.80 km (max 7.19)  MAE_res 1.017
  ukmo             4.33      (6.83)            1.153
  gfs              2.11      (7.60)            1.282
  ecmwf           10.36     (14.39)            1.418
correlacion distancia<->MAE_res: r=+0.536 (n=4). MAS DEBIL que en v1 (+0.836): gfs es
el mas cercano y solo 3o, luego la distancia ya no explica bien el ranking.

## CRITERIO DE DECISION (congelado, evaluado despues)
(a) cobertura >=80%                : CUMPLE (100.0%)
(b) ventaja sobre >=3 estaciones   : CUMPLE (8)
(c) mejor en AMBOS leads principales: CUMPLE (9h y 24h)
(d) ninguna estacion aporta >50%   : CUMPLE (max KLAX 26.2%)
practicamente empatados?           : NO (|delta|=0.401 > 0.10; IC excluye 0)
--> VEREDICTO: SUSTITUIR ecmwf_ifs025 POR icon_seamless

## LIMITACIONES
7/8 estaciones en EE.UU.; hemisferio norte unicamente; 4 meses; 8 estaciones.
Cota de disponibilidad empirica con cola no caracterizada.
Y_final es "evaluation label available retrospectively after settlement", NO Y_asof_T.
Instrumento de label = IEM/METAR, que NO es la fuente contractual de settlement.
