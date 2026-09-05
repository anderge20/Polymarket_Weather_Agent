# PRE-REGISTRO — impacto de revisiones METAR (READ-ONLY)
Congelado ANTES de calcular ninguna metrica.

## Instrumento
IEM mtarchive, boletines WMO crudos: mtarchive.geol.iastate.edu/YYYY/MM/DD/text/sao/YYYYMMDDHH_sao.txt
USO EXCLUSIVO: medir el impacto de las revisiones. NO es la fuente contractual de settlement.

## Estaciones (criterio input-side, fijado por la sonda de cobertura del 2026-08-03)
Las estaciones del catalogo con >= 20 mensajes en el dia de sonda. Resultado: 23 estaciones.
KLGA KORD KDAL KATL KAUS KBKF KHOU KLAX KMIA KSEA KSFO EGLC LTAC CYYZ MMMX RKPK MPMG
LLBG OEJN OPKC WMKK WSSS VHHH
Excluidas por cobertura insuficiente: RCTP (3 msg/dia), RPLL (1), y las 27 sin cobertura.

## Dias (deterministas, sin relacion con el resultado)
2025-12-30; dias 3 y 18 de cada mes de 2026-01 a 2026-08; 2026-09-01, 09-02, 09-03.
Total: 20 dias distribuidos por toda la ventana del catalogo.

## Definiciones
Para cada (estacion, observation_time) se recogen TODAS las versiones del mensaje,
con su fichero-hora de recepcion y su orden dentro del fichero.
  version_first := la de menor (hora_fichero, orden)
  version_final := la de mayor (hora_fichero, orden)
  Y_first_observed(est, dia_UTC) := max(temp del grupo de cuerpo METAR) usando version_first
  Y_final_IEM(est, dia_UTC)      := max(temp del grupo de cuerpo METAR) usando version_final
  revision_delta := Y_final_IEM - Y_first_observed
NOTA: dia UTC, no dia civil local. La eleccion de ventana es IDENTICA en ambos estados,
luego no sesga el delta. Y_first_observed NO se llama Y_asof_T.

## Tres niveles (reportados por separado)
A: cualquier revision METAR (existe COR o >1 version del mismo observation_time)
B: revision que cambia el Tmax del dia
C: revision que cambia el ENTERO del Tmax (y por tanto el bracket de 1 entero en C)

## Metricas
% station-days nivel A / B / C; distribucion de revision_delta; MAE; max; percentiles;
delay_COR = hora_fichero(COR) - hora observation_time (granularidad HORARIA).

## Prohibiciones
No extrapolar la tasa de COR de IEM a Wunderground.
No usar estos resultados para seleccionar M1.
No cerrar RECORD_VERSION_ASOF como RESOLVED.
