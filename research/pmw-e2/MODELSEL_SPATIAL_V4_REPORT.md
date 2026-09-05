# MODELSEL_SPATIAL_V4 — control del confusor espacial (ICON vs ECMWF)
Pre-registro: PREREG_MODELSEL_SPATIAL_V4.md sha256
  65e1e7079efe9c9241f6f23bc47e839a9337268b070490ff494fe07d1813bcec (congelado 2026-09-05T12:50:30Z)
Muestra: la de V3, hash 7a57ce0a040a237bae8db0e518f0194d22efc41a5a993b81df3525eb5a53e2ae
Sin refetch. 586 pares icon/ecmwf, 15 estaciones, leads 9h y 24h.

## §7 ARQUITECTURA ESPACIAL — establecido antes del analisis
ecmwf_ifs025 : 4 coordenadas en ~4 km -> MISMA celda 51.50,0.00 ; T casi identica
               (26.6/26.6/26.6/26.5) ; elevacion devuelta VARIABLE (4/2/10/31 m)
               => rejilla 0.25 deg CON ajuste dependiente de la elevacion del punto pedido.
icon_seamless: las mismas 4 coordenadas -> celdas DISTINTAS con T distintas
               => rejilla efectiva mucho mas fina; 'seamless' es COMPUESTO y su
               resolucion efectiva VARIA POR REGION.
cell_selection (nearest|land|sea) no altera el resultado.
RESPUESTA: NO se evaluan en el mismo punto espacial. Son REJILLAS NATIVAS DISTINTAS con
RESOLUCIONES EFECTIVAS DISTINTAS y, al menos ECMWF, con ajuste por elevacion.
UNKNOWN declarado: Open-Meteo no documenta si el valor es bruto de celda o downscaled.
La 'distancia a la celda' es un PROXY IMPERFECTO: no captura la diferencia de resolucion.
La celda es CONSTANTE por (estacion,modelo): 0/64 pares con mas de una celda.
=> los subconjuntos de distancia comparable seleccionan ESTACIONES, no eventos.

## A) DISTANCIA (km)
                 n_est  media mediana   p25   p75   p90   max
icon_seamless       16   4.73    3.83  1.61  6.12  7.49 18.15
ecmwf_ifs025        16   9.70   10.28  5.76 11.68 13.51 21.71
Por region (icon / ecmwf): ASIA_ESTE 9.06/12.88 · ASIA_SUR 3.38/12.47 · EUROPA 1.66/8.83
HEM_SUR 5.72/9.05 · LATAM_NORTE 5.70/6.48 · ORIENTE_MEDIO 1.64/6.18
ICON esta mas cerca en TODAS las regiones.

## B) DISTANCIA vs |RESIDUAL| (dentro de cada modelo)
icon  bruto Pearson +0.097 Spearman +0.156 | debiased +0.064 / +0.077
ecmwf bruto Pearson +0.113 Spearman +0.154 | debiased +0.056 / +0.009
Relacion positiva pero DEBIL. No se interpreta como causal.

## F) POR ESTACION — el hallazgo central
Pearson(delta_distancia, delta_MAE) = -0.087 ; Spearman = +0.040  (n=15)
=> ICON **NO** gana sistematicamente donde esta mas cerca.
Contraejemplos directos:
  RKSI: icon esta 12.4 km MAS LEJOS y aun asi GANA (dMAE -0.147)
  ZSQD: icon esta 14.2 km MAS CERCA y PIERDE (+0.071)
  VILK: icon 9.2 km mas cerca y PIERDE (+0.362)
  LTFM y MPMG: distancia IDENTICA (delta=0.00) -> LTFM gana ecmwf (+0.038),
               MPMG gana icon (-0.090)

## C) DISTANCIAS COMPARABLES (umbrales prefijados)
                        n   est    ICON   ECMWF     delta        IC95%          
TODOS                 586    15  1.0576  1.0952   -0.0376  [-0.148,+0.076] incluye 0
U = 1 km               78     2  1.0038  1.0281   -0.0243  [-0.090,+0.038] incluye 0
U = 2 km              154     4  1.0635  1.1380   -0.0746  [-0.326,+0.129] incluye 0
U = 5 km              194     5  1.0722  1.1314   -0.0592  [-0.267,+0.102] incluye 0
El SIGNO se mantiene a favor de ICON en los tres umbrales; ningun IC excluye 0.
AVISO: 2-5 bloques de estacion. Un bootstrap por bloques con 2 bloques carece de
resolucion; sus IC no son fiables.

## D) MATCHING
Emparejamiento por identidad de (event_id, lead): cada evento aporta exactamente una
observacion por modelo, luego NO hay reutilizacion posible. Admitido si |delta d| <= 2 km.
Resultado identico a C con U=2 km: n=154, 4 estaciones, delta -0.0746, IC [-0.326,+0.129].

## E) CONTROL ESTADISTICO  |residual| ~ modelo + distancia + lead
Sin efectos de estacion:
  MODELO(icon=1)  +0.0214  SE 0.0634  IC95% [-0.1028,+0.1457]   <- signo POSITIVO (icon peor)
  distancia_km    +0.0124  SE 0.0061  IC95% [+0.0005,+0.0243]   <- EXCLUYE 0
  lead24h         +0.0638  SE 0.0564  IC95% [-0.0467,+0.1743]
Con efectos fijos de estacion:
  MODELO(icon=1)  -0.0531  SE 0.0691  IC95% [-0.1885,+0.0823]   <- signo NEGATIVO (icon mejor)
  distancia_km    -0.0032  (colineal con estacion; no interpretable)
El coeficiente de MODELO CAMBIA DE SIGNO segun la especificacion y su IC INCLUYE 0 en ambas.
Aritmetica relevante: distancia estimada en +0.0124 C/km; ICON esta 4.97 km mas cerca de
media -> ventaja predicha SOLO por distancia = 0.062 C. La ventaja observada global es
0.0376 C, MENOR que la que la distancia por si sola predeciria.

## G) RUN IDENTICO
n=293, leads presentes = [9]. CONFIRMADO: todos a 9h. NO es evidencia sobre 24h.
ICON 1.0317 vs ECMWF 1.0573 ; delta -0.0256 ; IC [-0.139,+0.089] incluye 0.

## H) LEAD 24h CON CONTROL DE DISTANCIA (prioritario)
24h todos     n=293 est=15  ICON 1.0835 ECMWF 1.1331  delta -0.0496 [-0.184,+0.091] incluye 0
24h U=1 km    n= 39 est= 2  ICON 1.0040 ECMWF 0.9647  delta +0.0393 [+0.010,+0.067] EXCLUYE 0
24h U=2 km    n= 77 est= 4  ICON 1.0870 ECMWF 1.0433  delta +0.0437 [-0.229,+0.325] incluye 0
24h U=5 km    n= 97 est= 5  ICON 1.1251 ECMWF 1.0790  delta +0.0461 [-0.173,+0.269] incluye 0
=> A 24h, al igualar distancias, el SIGNO SE INVIERTE a favor de ECMWF en los TRES umbrales.

## 9h para contraste
9h todos      n=293 est=15  delta -0.0256 [-0.139,+0.089] incluye 0
9h U=1 km     n= 39 est= 2  delta -0.0878 [-0.190,+0.009] incluye 0
9h U=2 km     n= 77 est= 4  delta -0.1928 [-0.438,-0.008] EXCLUYE 0  (ICON mejor)
9h U=5 km     n= 97 est= 5  delta -0.1645 [-0.377,-0.017] EXCLUYE 0  (ICON mejor)
=> A 9h (MISMO run) y con distancias comparables, la ventaja de ICON se REFUERZA.

## FRESCURA (reportada, NO usada como desempate)
edad media del run en T: 9h -> icon 9.0 / ecmwf 9.0 ; 24h -> icon 6.0 / ecmwf 12.0.

## VEREDICTO
B — la ventaja de ICON persiste pero es pequena y NO concluyente.
Justificacion: el signo global se mantiene bajo los tres controles de distancia
(-0.024/-0.075/-0.059) luego NO es D; pero ningun IC global excluye 0, el coeficiente de
MODELO cambia de signo segun especificacion y su IC incluye 0 en ambas, y el efecto es
HETEROGENEO POR LEAD: favorable a ICON a 9h (significativo con U=2 y U=5) y favorable a
ECMWF a 24h en los tres umbrales.

## LIMITACIONES
Los subconjuntos de distancia comparable tienen 2-5 estaciones: los IC por bloques son
fragiles. La 'distancia' no captura la diferencia de RESOLUCION EFECTIVA, que es la
diferencia arquitectonica real entre los dos modelos. No se puede separar 'modelo' de
'resolucion del producto' con estos datos. Y_final sigue siendo label retrospectivo,
no Y_asof_T.
