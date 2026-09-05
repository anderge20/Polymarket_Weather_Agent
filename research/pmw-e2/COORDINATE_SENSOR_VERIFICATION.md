# COORDINATE_SENSOR_VERIFICATION — ¿ES LA COORDENADA NOAA LA DEL SENSOR?

**Fecha:** 2026-09-05 · **Naturaleza:** READ-ONLY · **Pregunta:** la que dejó abierta
`COORDINATE_UNIVERSE_AUDIT.md` §3/§11 y que separaba la decisión **B** de **A**.

## 1. Fuente oficial encontrada: NCEI HOMR (Historical Observing Metadata Repository)

`https://www.ncei.noaa.gov/access/homr/services/station/search?qid=WBAN:<wban>&date=all`
Publica, por estación, la serie histórica de pares lat/lon con `source`, `precision`, `datum` y
fechas. Para las ASOS de EE.UU. el par vigente tiene **`source: "ASOS CM"`** (base de datos de
*Configuration Management* del NWS), `precision: DDddddd`, `datum_horiz: WGS84`, `beginDate
2021-11-22` (o la fecha de comisión). Remark literal (idéntico en varias): *"NCEI PERFORMED A BULK
UPDATE TO ASOS STATION LOCATIONS FOLLOWING AN UPDATE FROM NWS'S ASOS CONFIGURATION MANAGEMENT (CM)
DATABASE."* KORD: *"SITE (ASOS) MOVED 2.4 MILES S ON SAME PROPERTY"*.

## 2. Resultado (11 estaciones de EE.UU. del universo; `COORD_HOMR_US.json`)

| ICAO | WBAN | HOMR (ASOS CM) | d(NOAA avwx) | d(OurAirports) | d(IEM) |
|---|---|---|---|---|---|
| KATL | 13874 | 33.62972, −84.44224 | **0.001 km** | 1.522 | 0.059 |
| KAUS | 13904 | 30.18311, −97.67989 | **0.071** | 2.350 | 0.008 |
| KDAL | 13960 | 32.83839, −96.83583 | **0.003** | 1.313 | 1.778 |
| KHOU | 12918 | 29.64586, −95.28212 | **0.005** | 0.516 | 0.933 |
| KLAX | 23174 | 33.93816, −118.38660 | **0.001** | 2.032 | 0.006 |
| KLGA | 14732 | 40.77945, −73.88027 | **0.000** | 0.693 | 0.001 |
| KMIA | 12839 | 25.78805, −80.31694 | **0.002** | 2.862 | 0.001 |
| KORD | 94846 | 41.96017, −87.93164 | **0.002** | 3.021 | 0.005 |
| KSEA | 24233 | 47.44467, −122.31442 | **0.000** | 0.479 | 0.004 |
| KSFO | 23234 | 37.61962, −122.36562 | **0.001** | 0.811 | 0.820 |
| KBKF | **23036** | 39.71667, −104.75000 *(precisión DDMM, sin `ASOS CM`; ANGB)* | 0.797 | — | — |

*Corrección (REFUTATION_D1_01 §Defecto): la primera versión de esta tabla consultaba el WBAN 23062,
que es otra estación (par USGS 2019 a 11,29 km). El registro correcto de KBKF es el WBAN 23036
(`qid=ICAO:KBKF`, verificado de forma independiente). Con él la distancia es 0,797 km, pero la
precisión DDMM (±0,93 km lat / ±0,71 km lon) **no permite discriminar sensor de ARP**: KBKF queda
como canónica NO verificada, no como contraejemplo.*

```
estaciones con 'ASOS CM': 10/11
d(NOAA aviationweather, sensor ASOS CM):  media 0.009 km   máx 0.071 km   ≤10 m en 9/10
d(IEM, sensor):                            media 0.362 km   máx 1.778 km  (KDAL, KHOU, KSFO desviados)
d(OurAirports, sensor):                    media 1.560 km   máx 3.021 km   >1 km en 6/10
```

## 3. Confirmación fuera de EE.UU.: WSSS (Singapur) — `WF_opkc_wsss_results.json`

- **AIP Singapore (CAAS), AD 2 WSSS, vigente 19 MAR 2026:** ARP *"012133.16N 1035921.57E
  (Control Tower)"* = 1.359211, 103.989325 — **a 1.27 km del punto NOAA**.
- **AIP GEN 3.5 / AD 2.14:** la estación meteorológica está *"345m west of middle of RWY 02L/20R"*,
  no en el ARP. Con los umbrales de AD 2.12, ese punto es ≈ 1.3656, 103.9814 — a ~0.27 km de NOAA.
- **WMO OSCAR 48698 "SINGAPORE/CHANGI AIRPORT":** 1.3679, 103.9824 — **a 46 m de NOAA**.
- **NEA data.gov.sg estación S24:** 1.3678, 103.9823 — a 40 m de NOAA.
- Matiz: el viento del METAR se toma de un sensor en el extremo sur de RWY 02L (~2,2 km); la
  temperatura y presión, de la estación MET. Para nuestra variable (temperatura) NOAA es correcta.

## 4. Advertencia sobre FAA NASR

El fichero FAA NASR `AWOS.csv` (grupo ASOS/AWOS, ciclo 2026-09-03) **no** es fiable como
ubicación de sensor: en 301 de 866 filas ASOS (35 %) la coordenada es exactamente el ARP
(placeholder), y con `SURVEY_METHOD_CODE=E` lo es en 118/225 (52 %). HOMR es la fuente correcta.

## 5. Conclusión

> **La coordenada de NOAA AviationWeather ES la ubicación del sensor ASOS/estación meteorológica
> que genera el METAR**, verificada contra registro oficial (NCEI HOMR / NWS ASOS CM) en 10/10
> estaciones de EE.UU. y contra AIP + OSCAR + servicio meteorológico nacional en Singapur.
> La premisa deja de ser inferida **en el alcance verificado**: red ASOS de EE.UU. (10 estaciones,
> que comparten una única red y una única base CM, y valen por tanto como *una* evidencia sobre la
> práctica de NOAA con estaciones extranjeras) y WSSS (evidencia independiente y fuerte).
> **Verificada por documentación oficial en 11/55 estaciones. En las 43 restantes —todas fuera de
> EE.UU., 10 de ellas en China— la regla se sostiene por identidad de estirpe de registro y ausencia
> de contraejemplo, no por verificación individual.** (Acotación exigida por REFUTATION_D1_01 §Lente 3.)

Consecuencias: (a) la regla D1 queda fundada en criterio 1 (correspondencia física con el METAR)
por evidencia directa; (b) las divergencias NOAA↔OurAirports de 1–3 km son **sensor vs ARP**, no
errores; (c) WSSS deja de ser excepción → CANÓNICA; (d) OPKC sigue abierta (su investigación no
llegó a ejecutarse por límite de sesión; PCAA AIP pendiente).

## 6. Pendiente declarado

- **Refutación adversarial EJECUTADA** (`REFUTATION_D1_01.md`, 2026-09-05, revisor independiente):
  cálculo PASA (Δ máx 0,016 m), fuente PASA (HOMR reconsultada; vínculo WBAN↔ICAO en el propio
  registro), semántica PASA CON RESERVA (alcance 11/55). Un defecto encontrado y corregido (KBKF).
  Esta conclusión pasa de "pendiente de refutación" a **CONFIRMADA CON ALCANCE ACOTADO**.
- KBKF: **no verificable con HOMR** — registro WBAN 23036 sin `ASOS CM`, precisión DDMM.
  Canónica no verificada dentro del universo V5.
- Cobertura: 10 EE.UU. + 1 Singapur = 11/55 verificadas directamente. Para las 43 restantes, la
  identidad de estirpe NOAA≡registro observador (≤0,2 km respecto a IEM en 30/55) y la ausencia
  de contraejemplos sostienen la regla, pero **no hay verificación individual**; debe declararse
  como inferencia en cualquier informe que use la convención.
- OPKC: excepción abierta (PCAA AIP pendiente).
