# PREREG_MODELSEL_SPATIAL_V4 — control del confusor espacial (ICON vs ECMWF)
Congelado ANTES de mirar ningun resultado del contraste. READ-ONLY.
NO modifica V2 ni V3. NO selecciona M1.

## 0. Pregunta
"Permanece la pequena ventaja de ICON sobre ECMWF al controlar explicitamente la
distancia/representacion espacial del punto meteorologico respecto a la estacion?"

## 1. HECHO ARQUITECTONICO ESTABLECIDO ANTES DEL ANALISIS (sonda read-only)
Peticiones a la misma zona (Londres, 4 coordenadas dentro de ~4 km):
  ecmwf_ifs025 : devuelve SIEMPRE la celda 51.50,0.00 ; T12 = 26.6/26.6/26.6/26.5 ;
                 elevacion devuelta VARIABLE (4/2/10/31 m) -> rejilla 0.25 deg (~28 km)
                 CON ajuste dependiente de la elevacion del punto pedido.
  icon_seamless: devuelve celdas DISTINTAS (51.50,0.06 / 51.54,0.10 / 51.48,0.02) con
                 T distintas (26.1/26.3/26.0) -> rejilla efectiva mucho mas fina.
                 'seamless' es un COMPUESTO: la resolucion efectiva VARIA POR REGION
                 (ICON-D2 / ICON-EU / ICON global segun cobertura).
  cell_selection (nearest|land|sea) no altera el resultado en la sonda.
CONCLUSION §7: ICON y ECMWF NO se evaluan en el mismo punto espacial. Son REJILLAS
NATIVAS DISTINTAS con resoluciones efectivas distintas, y al menos ECMWF aplica un
ajuste por elevacion. La 'distancia a la celda devuelta' es un PROXY IMPERFECTO de la
representatividad espacial: no captura la diferencia de resolucion.
LIMITACION DECLARADA: Open-Meteo no documenta si el valor devuelto es el bruto de celda
o uno interpolado/downscaled. Ese punto queda UNKNOWN y no se inventa.

## 2. Muestra
EXACTAMENTE los eventos de V3 (MODELSEL_GEOVAL_V3_SAMPLE.json,
hash 7a57ce0a040a237bae8db0e518f0194d22efc41a5a993b81df3525eb5a53e2ae).
Se reutiliza MODELSEL_GEOVAL_V3_RAW/EVAL.json. NO se refetchan datos ni se cambia la muestra.
Exclusion previa ya aplicada en V3 y documentada: ZSJN (192 filas sin Y en IEM) -> 15 estaciones.
No se excluye ningun evento adicional.

## 3. Reglas heredadas SIN CAMBIO de V3
T = endDate - lead_hours ; availability_safe_at = init + L_max(model) con
icon 4.76h / ecmwf 8.78h ; seleccion as-of del ultimo run con avail <= T ;
leads 9h y 24h ; walk-forward (historia misma estacion+modelo, target_date <= D-2d,
minimo 10, sin imputacion) ; Y_final como LABEL retrospectivo, no Y_asof_T.

## 4. Modelos
Solo icon_seamless vs ecmwf_ifs025.

## 5. Analisis (todos read-only, sobre los datos de V3)
A) Distribucion de distancia estacion->punto por modelo: media, mediana, p25, p75, p90;
   por region; por estacion.
B) Relacion distancia vs abs(residual), bruto y debiased, por modelo: Pearson y Spearman.
   NO se interpreta como causal.
C) Subconjunto de distancias comparables: |dist_ICON - dist_ECMWF| <= U, con
   UMBRALES FIJADOS AQUI: U in {1 km, 2 km, 5 km}. Se reportan LOS TRES.
   Prohibido elegir a posteriori el umbral que favorezca a un modelo.
D) Matching: emparejamiento 1:1 sin reutilizacion, por evento (mismo event_id y lead),
   admitiendo el par solo si |dist_ICON - dist_ECMWF| <= 2 km (umbral central de C).
   Algoritmo documentado. Delta MAE + bootstrap pareado por bloques de estacion.
E) Control estadistico: regresion lineal de abs(residual) sobre
   [modelo (indicador ICON), distancia_km, lead(indicador 24h)] y, como sensibilidad,
   la misma con efectos fijos de estacion (dummies). Se reporta el coeficiente de
   MODELO y su IC95%. Objetivo: estimar el efecto de modelo controlando distancia,
   NO construir un predictor.
F) Por estacion: dist_ICON, dist_ECMWF, MAE_ICON, MAE_ECMWF, delta, n. Se comprueba la
   correlacion entre (delta de distancia) y (delta de MAE) entre estaciones.
G) Pares con run identico: se mantiene el analisis de V3 y se CONFIRMA que corresponden
   a lead 9h. NO se presenta como evidencia de igualdad de run a 24h.
H) 24h por separado, con el mismo control de distancia. Prioritario porque a 24h los
   runs difieren.

## 6. Bootstrap
Pareado, por BLOQUES DE ESTACION, 4000 remuestreos, semilla 20260905 (igual que V2/V3).

## 7. CATEGORIAS (congeladas)
A — ventaja de ICON ROBUSTA al control espacial: el signo se mantiene y el IC95% excluye
    0 en el subconjunto de distancias comparables (U=2km) Y el coeficiente de modelo en
    E) favorece a ICON con IC que excluye 0.
B — persiste pero pequena/no concluyente: signo se mantiene en la mayoria de controles
    pero al menos un IC95% relevante incluye 0.
C — empate/no confirmado: el signo cambia o los deltas son ~0 en los controles.
D — la ventaja estaba explicada en buena medida por el confusor: al igualar distancias
    la ventaja desaparece o se invierte, y/o el coeficiente de distancia absorbe el efecto.
Se elige por resultados, no por conveniencia.

## 8. Prohibiciones
La FRESCURA se reporta aparte y NO se usa como desempate en esta ronda.
No se selecciona M1. No se modifica nada del proyecto. No commit/push.
