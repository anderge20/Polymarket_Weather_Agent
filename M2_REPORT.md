# M2_REPORT — distribución de error de pronóstico

**Fecha:** 2026-09-09 · **Sesión:** B (Claude)
**Preregistro:** `PREREG_M2_ERROR.md` sha `16b729e1d28f3cbab8a102ab7ebd67a451471a961a299726714e987d8223e55d`,
congelado **antes** de calcular ningún cuantil. Nada de lo que sigue cambió una regla.

## 1. Muestra ejecutada

```
pares pronóstico-observación: 2 595     lead  9 h: 1 297     lead 24 h: 1 298
estaciones: 49        fechas: 2026-04-08 → 2026-09-02
estratos: STATION 201 · POOLED 2 324 · INSUFFICIENT 70
filas con cuantiles escritos: 2 525 de 2 727
```

Las 70 `INSUFFICIENT` son las primeras fechas: el walk-forward expansivo (§5) no tiene aún
30 pares de entrenamiento. **No se rellenan hacia atrás.** Esas filas quedan sin cuantiles y
`build_feature` devolverá `None`, que es el comportamiento correcto.

`STATION` cayó de 605 a 201 al separar los leads correctamente (§4): con la mitad de datos
por estrato, menos estaciones alcanzan n ≥ 30. Es la consecuencia esperada de no mezclar.

## 2. Distribución del error `e = y − f` (°C)

| lead | n | sesgo | MAE | p10 | p25 | p50 | p75 | p90 | anchura |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 9 h | 1 297 | **+0.46** | 1.16 | −1.20 | −0.40 | +0.47 | +1.20 | +2.20 | 3.40 |
| 24 h | 1 298 | **+0.48** | 1.23 | −1.35 | −0.48 | +0.48 | +1.30 | +2.30 | 3.65 |

Coherente con la física en lo estructural: el MAE crece con el horizonte (1.16 → 1.23) y la
anchura también (3.40 → 3.65). Nada de esto se ajustó; son los percentiles empíricos crudos,
sin suavizado ni recorte de colas (§7).

## 3. Hallazgo principal — sesgo sistemático de +0,47 °C

**El modelo subestima el máximo diario en cerca de medio grado, de forma consistente en los
dos leads.** No es ruido: n = 2 595 y el sesgo es prácticamente idéntico a 9 h y a 24 h, lo
que descarta que dependa del horizonte.

Es justamente para esto que existe M2: los cuantiles lo incorporan, de modo que
`forecast_p50 = f + 0.47` en lugar de `f`. Una estrategia que usara el pronóstico crudo
estaría sesgada a la baja en todas las bandas altas.

**Advertencia sobre la interpretación.** No se afirma que sea un sesgo *del modelo ICON*. Hay
al menos tres causas candidatas no separadas por este análisis:
1. sesgo real de ICON en temperatura a 2 m;
2. diferencia entre la celda de rejilla y la ubicación del sensor (D1/D6 acotan la coordenada,
   no la representatividad);
3. **el artefacto de muestreo de la §4 de este informe**, que va en la dirección contraria.

Separarlas exige un diseño propio, con su preregistro. **No se hace aquí.**

## 4. Limitación del label que empeora el sesgo, no lo explica

`y` es el máximo sobre los **METAR de rutina horarios**. El máximo diario real es el máximo de
una serie continua, así que muestrear una vez por hora lo **subestima**. Es decir, `y` es una
cota inferior del verdadero máximo.

Como `e = y − f`, un `y` subestimado hace `e` **más negativo**. El sesgo medido de **+0,47 °C
es por tanto una cota inferior del sesgo verdadero**: corrigiendo el muestreo, el modelo
subestimaría todavía más. Esto refuerza el hallazgo de §3 en lugar de debilitarlo, y no lo
explica.

Cuantificarlo requeriría METAR especiales (SPECI) o datos de 5 minutos. Queda declarado, no
resuelto.

## 5. Limitaciones heredadas, que todo uso de estos cuantiles debe repetir

- **Disponibilidad del label supuesta, no medida** (preregistro §6): se asume que el máximo
  estaba publicado 24 h después del fin del día local. La ingesta retrospectiva no puede
  probarlo — `available_at` es el instante de descarga (B-4/D17). **Es un supuesto.**
- **Periodo acotado por el archivo** (B-1): abril–septiembre 2026 y no ampliable hacia atrás;
  la ventana de Single Runs se desplaza cada día.
- **Coordenadas verificadas en 11 de 55 estaciones** (D6). En las 43 restantes la convención
  es inferencia declarada.
- **1 936 mercados con redondeo a décimas quedan fuera** del universo operable (§9): una
  rejilla de claves enteras no puede representarlos.
- **No transportable a leads largos:** `icon_seamless` cambia de componente hacia +45 h (D2).
  Nada aquí dice nada sobre horizontes mayores que 24 h.

## 6. Integridad

| Comprobación | Estado |
|---|---|
| Preregistro congelado y hasheado antes de calcular | **SÍ** |
| Reglas cambiadas tras ver resultados | **NO** |
| Cuantiles escritos en filas que no cumplen §8 | **NO** |
| Periodo sin entrenamiento rellenado hacia atrás | **NO** |
| Estratificación añadida a posteriori (región, mes) | **NO** |
| M3 ejecutado / órdenes enviadas | **NO** — gate D0 intacto |

**Artefactos:** `M2_ERROR_QUANTILES.json` · este informe · `forecast_p10..p90` en
`weather_forecasts` (2 525 filas).
