# REVISION_IMPACT_AUDIT — cuantificacion del impacto de revisiones sobre M2/M3
Artefacto de investigacion. NO forma parte del repositorio. 2026-09-05. READ-ONLY.
Pre-registro: PREREG_REVISION.md sha256 8d6efcba5c515a54419f7701a6ff38b523ca9be22f843c823f1a4a13648f1d1a
Muestra:      REVISION_SAMPLE.json hash ad508647a3fb7184  (congelada antes de medir)

## MUESTRA
23 estaciones x 20 dias = 460 station-days planificados; 578 reconstruidos
(incluye station-days adyacentes que aparecen en los ficheros horarios descargados).
Periodo 2025-12-30 -> 2026-09-03. 480 ficheros de boletines WMO, ~19 MB/dia.
Estaciones: KLGA KORD KDAL KATL KAUS KBKF KHOU KLAX KMIA KSEA KSFO EGLC LTAC CYYZ
MMMX RKPK MPMG LLBG OEJN OPKC WMKK WSSS VHHH
Criterio: estaciones del catalogo con >=20 mensajes en la sonda de cobertura del 2026-08-03.
Cobertura mtarchive real: 25 de 52 estaciones del catalogo.

## RESULTADOS
Mensajes parseados            : 34.387  (33.403 con temperatura)
Observaciones unicas          : 15.853
Mensajes marcados COR         : 296
Observaciones con COR         : 214  (1,35%)
Observaciones con >1 version  : 9.813 (61,90%)  <- mayoritariamente retransmision verbatim
Observaciones con TEMPERATURA distinta entre 1a y ultima version: 5 (0,0315%)
                                IC95% Wilson [0,0135% , 0,0738%]

### TRES NIVELES
A. station-days con alguna revision (COR o >1 version) : 374/578  (64,71%)
   station-days con algun COR                          : 126/578  (21,80%)
B. station-days donde cambia el Tmax                   :   0/578  (0,000%)
C. station-days donde cambia el ENTERO / bracket       :   0/578  (0,000%)
   (el grupo de cuerpo METAR ya es entero -> B y C coinciden por construccion)

Cota superior con 0 eventos en 578 (regla de tres, 95% unilateral): < 0,519%

### LAS 5 OBSERVACIONES CON CAMBIO DE TEMPERATURA
MPMG 2025-12-30 0100Z  [27,27,26,26]  COR=ninguno  -> no afecta al maximo
LLBG 2025-12-30 1920Z  [13,14]        COR=ninguno  -> no afecta al maximo
OPKC 2026-01-03 0630Z  [12,22,12,22,22,22,22] COR=ninguno -> no afecta al maximo
MMMX 2026-02-18 1827Z  [25,25,26,26]  COR=si       -> no afecta al maximo
MMMX 2026-06-03 2051Z  [24,25,24,25]  COR=si       -> no afecta al maximo
NOTA: 3 de los 5 no llevan COR en ninguna version. Los valores alternantes
(p.ej. OPKC 12/22/12/22) sugieren artefacto de parseo o de boletin, no revision
genuina. La tasa real de revision es por tanto MENOR o igual a la reportada.

### revision_delta
MAE(Y_first_observed, Y_final_IEM) = 0,00000 C sobre 578 station-days
bias medio = +0,00000 C ; max |delta| = 0 ; distribucion = {0: 578}

### TIMING (granularidad HORARIA)
delay_COR = hora_fichero(COR) - hora de observacion, n=214
p50=0h  p75=1h  p90=1h  p95=1h  p99=1h  max=1h
Distribucion: {0h: 140, 1h: 74}
LIMITACION: la granularidad es horaria. No se puede afirmar el instante exacto.

## IMPACTO SOBRE M2/M3  (derivado, sin construir nada)
Como revision_delta = 0 en 578/578, se sigue por identidad:
  error_first = Y_first - f  ==  error_final = Y_final - f
MAE, bias, RMSE, MedAE, percentiles y colas: DIFERENCIA EXACTAMENTE CERO.
No hace falta recalcular sobre los forecasts historicos: el resultado es identico
por construccion, no por estimacion.

## IMPACTO SOBRE PROBABILIDADES / BRACKETS
0 station-days cambian el entero -> 0 cambios de bracket en mercados en C (bandas de 1 entero).
P(bracket compatible | Y_first) == P(bracket compatible | Y_final) en esta muestra.

## CLASIFICACION: NEGLIGIBLE  (solo para IEM/METAR, solo en esta muestra)
Justificacion (sin umbrales arbitrarios):
- Frecuencia: 0 de 578 station-days. Cota superior 95% = 0,519%.
- Magnitud:   MAE exactamente 0,00000 C. No es "pequeno": es nulo en la muestra.
- Distribucion: diferencia identicamente cero, no aproximadamente cero.
- Bracket:    0 cambios.
- Timing:     correcciones en 0-1 h, muy dentro de la ventana contractual de revisiones.
El nivel A es alto (64,71%) pero NO se propaga a B ni a C: las revisiones existen
y son frecuentes, pero casi nunca tocan la temperatura y nunca tocaron el maximo.

## DECISION METODOLOGICA — tres alternativas
A) Usar Y_final con limitacion explicita.
   VENTAJA: inmediato; el impacto medido es nulo; usa todo el historico.
   RIESGO: medido solo en IEM/METAR y en 23 de 53 estaciones; NO medido en Wunderground,
   que es la fuente contractual del 85,6% del catalogo.
B) Usar solo station-days sin evidencia de revision relevante.
   VENTAJA: conservador.
   RIESGO: excluiria el 64,71% (nivel A) sin ganancia demostrable, porque el nivel A
   no se propaga al Tmax. Seria una perdida de datos sin justificacion empirica.
C) Reconstruccion prospectiva de Y_asof_T + historico solo para calibracion limitada.
   VENTAJA: unica via a un as-of demostrado y con cobertura completa.
   RIESGO: no resuelve el historico; coste de operacion continuada.

## QUE DEMUESTRA IEM Y QUE NO DEMUESTRA RESPECTO A WUNDERGROUND
DEMUESTRA: en la cadena METAR, las correcciones son frecuentes a nivel de mensaje
pero casi nunca alteran la temperatura, y en 578 station-days no alteraron el maximo diario.
NO DEMUESTRA NADA sobre Wunderground:
- WU no publica METAR crudo; su tabla Daily Observations es un producto derivado.
- El contrato distingue explicitamente la tabla Daily Observations de Day High & Low
  y admite que pueden discrepar -> WU aplica su propio procesamiento.
- WU tiene su propia politica de revisiones, no observable.
- La tasa de revision de WU NO es extrapolable desde la de METAR. Categoria UNKNOWN.
Lo mismo aplica a HKO y CWA.

## LIMITACIONES
Muestra de 20 dias (no continua). 23 de 53 estaciones. Granularidad horaria del receipt.
3 de los 5 casos de cambio pueden ser artefactos de parseo. Dia UTC, no dia civil local
(no sesga el delta, que usa la misma ventana en ambos estados).
RECORD_VERSION_ASOF(T) NO queda RESOLVED.
