# RECORD_VERSION_ASOF(T) — AUDITORIA READ-ONLY
Artefacto de investigacion. NO forma parte del repositorio. 2026-09-05.

## 1. Definicion formal de Y_asof_T
Y_asof_T(D) := el valor de maximo diario de la fecha D que la fuente contractual
habria reportado si se hubiera consultado en el instante T, considerando unicamente
mensajes/registros recibidos y publicados en o antes de T.

## 2. Definicion de Y_final
Y_final(D) := el valor que efectivamente liquido el mercado, incorporando las revisiones
admitidas por el contrato (hasta la publicacion del dato del dia siguiente, o hasta
"finalized"/"published" segun familia).

## 3. Diferencia
Y_final es por construccion POSTERIOR: el contrato admite revisiones dentro de una
ventana explicita. Y_asof_T es una version anterior, posiblemente distinta.
Descargar hoy un valor NO demuestra que ese valor existiera en T.
Y_final es el LABEL correcto. Y_asof_T es lo que haria falta para ENTRENAR sin look-ahead.

## 4-6. Auditoria por proveedor (A=pub ts, B=rev ts, C=historial, D=recuperable,
E=reconstruir asof, F=cota, G=valido como LABEL)

### IEM ASOS - archivo procesado (asos.py)
A NO | B NO | C NO | D NO | E NO | F NO | G SI
Evidencia: 806 METAR de KLGA agosto 2026 -> 0 timestamps duplicados (una sola version
por observation_time); 22/806 (2.7%) llevan COR; 2/30 dias (6.7%) tienen su maximo
diario en una observacion COR. obhistory.json no expone ningun campo de version,
recepcion o ingesta. report_type solo distingue 1/3/4, no version.
ESTADO: UNKNOWN

### IEM mtarchive - boletines WMO crudos (text/sao/)
A SI (granularidad HORARIA: el nombre del fichero es la hora de recepcion)
B implicito (mensajes COR presentes) | C SI | D SI | E PARCIAL | F PARCIAL | G SI
Evidencia decisiva: en 2026080323_sao.txt aparecen AMBAS versiones de KLGA 032351Z:
  "KLGA 032351Z 32012KT ... 27/17 A2987"        (original)
  "KLGA 032351Z COR 32012KT ... 27/17"          (correccion)
Profundidad verificada: 2025-12-30, 2026-04-02, 2026-06-03, 2026-08-03 -> HTTP 200.
LIMITACION CRITICA de cobertura (fichero 2026080312_sao.txt, 8.224 METAR, 60 COR):
  presentes: KLGA(4) EGLC(4) LLBG(2) OPKC(8) VHHH(4)
  AUSENTES : LIMC RKSI UUWW LTFM VILK ZGSZ ZSQD FACT EFHK RCTP NZWN RJTT ZBAA
  -> 13 de 18 estaciones sin cobertura en la hora probada.
ESTADO: PARTIAL

### NOAA api.weather.gov
A NO | B NO | C NO | D NO | E NO | F NO | G SI
Retencion ~7 dias (medido en ronda previa). qualityControl = 'V' en 300/300 obs.
Sin campos de version en properties.
ESTADO: UNKNOWN

### Wunderground Daily Observations
A NO | B NO | C NO | D NO | E NO | F NO | G SI (es la fuente contractual de 85.6%)
Pagina servida por JS contra api.weather.com con apiKey embebida. No reconstruida.
ESTADO: UNKNOWN

### HKO
A NO | B NO | C NO | D NO | E NO | F NO | G SI
CLMMAXT devuelve solo el estado actual. Campo "data Completeness" con leyenda
{*** unavailable, # data incomplete, C data Complete}; 184/184 dias = 'C'.
Es indicador de calidad, NO de version ni de provisionalidad.
El contrato distingue "published" (1.078 mercados) de "finalized" (781): dos estados
contractuales distintos, sin timestamps publicados.
ESTADO: UNKNOWN

### CWA
A-F NO (fuente inaccesible: opendata 401, pagina JS) | G no verificable
ESTADO: UNKNOWN

## 7. Podemos reconstruir Y_asof_T?
NO con el archivo procesado de IEM ni con ningun otro proveedor.
PARCIALMENTE con mtarchive: granularidad horaria, cobertura de estaciones parcial,
verificado en 1 caso. No demostrado para estaciones internacionales.

## 8. Dataset prospectivo
SI es construible desde ahora: registrar cada mensaje con su hora de recepcion
observada. Es la unica via para cobertura completa. No implementado.

## 9. Impacto sobre M2/M3
M2/M3 ajustan la distribucion de error sobre pares (forecast, observacion) de dias
PASADOS. Esos pares requieren Y_asof_T(D') para el D' de entrenamiento, no Y_final.
Usar Y_final introduce look-ahead de magnitud acotable pero no nula:
COR en 2.7% de mensajes y 6.7% de maximos diarios en la muestra KLGA.

## 10. Impacto sobre MODEL-SELECTION
El benchmark uso Y de IEM procesado = Y_final. Como TODOS los modelos se evaluaron
contra el mismo Y, el sesgo es comun y la comparacion RELATIVA no se invalida.
Pero ninguna cifra absoluta de MAE es as-of.

## 11. Impacto sobre backtesting
Y_final es admisible como LABEL de settlement (disponible tras el cierre).
Y_final NO es admisible como observacion de entrenamiento ni como feature.
Mientras Y_asof_T no sea reconstruible, un backtest que ajuste parametros sobre
observaciones pasadas NO es estrictamente as-of.

## 12. Periodo realmente utilizable
Como LABEL: todo el catalogo con evento resuelto.
Como observacion de ENTRENAMIENTO estrictamente as-of: NINGUNO demostrado.
Via mtarchive: potencialmente 2025-12-30 -> hoy, solo para estaciones cubiertas,
pendiente de verificar cobertura y completitud.

## 13. Recomendacion
1. Separar formalmente Y_final (label) de Y_asof_T (entrenamiento). No usar el primero
   como el segundo.
2. Cuantificar el impacto de las revisiones antes de decidir: medir tasa de COR y su
   efecto sobre el maximo diario en las 53 estaciones, no solo KLGA.
3. Evaluar mtarchive como via de reconstruccion, empezando por verificar cobertura
   por estacion y hora.
4. Poner en marcha la captura prospectiva.
5. NO cerrar RECORD_VERSION_ASOF como RESOLVED.
