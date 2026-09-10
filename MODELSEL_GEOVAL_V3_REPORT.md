# MODELSEL_GEOVAL_V3 — validacion confirmatoria de generalizacion geografica
Pre-registro: PREREG_MODELSEL_GEOVAL_V3.md sha256
  135d46f91a0e519212fcb5221cf8e395a5384f5853bee98285120050b856d5d1 (congelado 2026-09-05T12:18:27Z)
Muestra: MODELSEL_GEOVAL_V3_SAMPLE.json hash
  7a57ce0a040a237bae8db0e518f0194d22efc41a5a993b81df3525eb5a53e2ae
V2 NO se modifica ni se reinterpreta. Esta ronda es CONFIRMATORIA.

## MUESTRA
400 eventos, 16 estaciones, 6 regiones, 2026-06-03 -> 2026-09-04.
Solapamiento con V1+V2: 0 eventos. Ninguna estacion de V2 reutilizada.
Cuotas: EUROPA 4 (>=3 OK) | ASIA este 4 + sur 2 = 6 (>=3 OK) | ORIENTE_MEDIO 2 (OK) |
HEM_SUR 2 (OK) | LATAM_NORTE 2.
ZSJN queda fuera del analisis: 192 filas sin Y (IEM sin observaciones). Quedan 15 estaciones.

## COBERTURA
forecast+Y usable: 2966/3200 = 92.7%
walk-forward evaluable: 2330/3200 = 72.8%  (V2 fue 90.0%)

## A) MAE RESIDUAL GLOBAL (leads 9h+24h)
  icon_seamless   1.058   (MAE bruto 1.127, bias -0.349, RMSE 1.537, r 0.961)  n=586
  ecmwf_ifs025    1.095   (1.459, -0.758, 1.844, 0.949)                        n=586
  ukmo            1.276   (1.658, -0.797, 2.205, 0.933)                        n=572
  gfs             1.451   (1.830, +0.081, 2.454, 0.910)                        n=586
Delta icon-ecmwf = -0.0376 C   (en V2 fue -0.4015 C -> 10x menor)

## B/C) POR LEAD
            9h      24h
icon     1.032    1.083
ecmwf    1.057    1.133
icon menor en AMBOS leads primarios. Margenes 0.025 y 0.050 C.

## D) POR ESTACION — icon gana 8/15 (53%)   [en V2 fue 8/8]
icon: RKSI OPKC EFHK LIMC UUWW MMMX MPMG LLBG
ecmwf: ZGSZ ZSQD VILK EGLC(empate 0.000) FACT SBGR LTFM

## E/F) POR REGION — icon 3, ecmwf 3
                icon_9h ecmwf_9h icon_24h ecmwf_24h  gana
ASIA_ESTE         1.220   1.151    1.334    1.275    ecmwf  <- ecmwf en AMBOS leads
ASIA_SUR          0.955   0.825    1.020    0.950    ecmwf  <- ecmwf en AMBOS leads
HEM_SUR           1.326   1.214    1.422    1.127    ecmwf  <- ecmwf en AMBOS leads
EUROPA            0.963   0.992    0.998    1.260    icon
LATAM_NORTE       1.140   1.522    1.128    1.289    icon
ORIENTE_MEDIO     0.565   0.671    0.563    0.694    icon
EXISTEN 3 REGIONES donde ecmwf gana en los dos leads.

## G) LEAVE-ONE-STATION-OUT
Excluyendo cada una de las 15 estaciones, el signo NUNCA se invierte.
Delta va de -0.0087 (excl. MMMX) a -0.0669 (excl. VILK). Ninguna estacion sostiene sola
la ventaja.

## H) IGUALDAD DE RUN
586 pares: 293 con MISMO run (todos a lead 9h), 293 con run distinto.
  MISMO run     n=293  icon 1.0317  ecmwf 1.0573  Delta -0.0256  -> icon
  run distinto  n=293  icon 1.0835  ecmwf 1.1331  Delta -0.0496  -> icon
La ventaja persiste a igualdad de frescura, pero es pequena.

## BOOTSTRAP PAREADO (bloques de estacion, 4000, semilla 20260905)
n=586  Delta medio -0.0376 C
IC95% = [-0.1477, +0.0761]  -> INCLUYE 0
En V2 el IC era [-0.5820, -0.2383] y EXCLUIA 0.

## FRESCURA (edad media del run en T)
              9h    24h
icon         9.0    6.0
ecmwf        9.0   12.0
A lead 24h icon dispone de una pasada 6 h mas fresca. A lead 9h son la misma pasada.

## ESPACIAL
icon  dist media 4.73 km (max 18.15) | ecmwf 9.70 km (max 21.71). Confundido persiste.

## CATEGORIA (evaluada contra el pre-registro, no elegida por conveniencia)
A CONFIRMACION FUERTE: NO. Falla >=75% estaciones (53%), >=75% regiones (50%), y existen
  3 regiones donde ecmwf gana en ambos leads.
C NO CONFIRMADO: NO. Ninguna exclusion de estacion invierte el signo, y gana en 53% > 50%.
D REFUTADO: NO. icon mantiene menor MAE residual global.
=> B. CONFIRMACION PARCIAL

## MATIZ SUSTANTIVO (obligatorio reportarlo)
La ventaja global cae de -0.4015 C (V2) a -0.0376 C (V3): factor 10.
El IC95% pareado pasa de excluir 0 a INCLUIRLO.
Bajo la definicion de "practicamente empatados" que se congelo en V2
(|delta| < 0.10 C O el IC incluye 0), icon y ecmwf estarian EMPATADOS en esta muestra.
Eso NO altera el veredicto de V2 sobre su propia muestra; describe esta.
Las 3 regiones donde gana ecmwf (Asia este, Asia sur, hemisferio sur) son precisamente
regiones AUSENTES de V2. La concentracion en EE.UU. de V2 inflo la ventaja aparente.
