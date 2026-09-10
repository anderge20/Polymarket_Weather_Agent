# M2 v3 — RESULTADO NEGATIVO: la calibración por estación no es alcanzable con este sustrato

**Fecha:** 2026-09-09 · **Sesión:** B · **Preregistro:** `PREREG_M2_ERROR_v3.md`
sha `11c2c69f8cc73b49e9caebdfde61c2cd7f48227d7842c0ddf3359aef32627251`, congelado antes de
calcular nada.

**VEREDICTO: v3 NO VÁLIDO.** Se publica el fallo, como el propio preregistro §4 exige, en vez
de intentar una v4 con otro estimador.

---

## 1. Lo que exigía el criterio y lo que salió

```
§4.1  calibración por estación en >= 70 % de las estaciones con n >= 15
      resultado: 6 de 46  →  13 %      *** FALLA ***
§4.2  calibración agregada:  lead 9h 0,067/0,879 · lead 24h 0,057/0,866   (roza fuera)
§4.3  monotonía del horizonte: MAE 1,157 → 1,223   ok
```

## 2. No es falta de cobertura: el desplazamiento EMPEORA

Primera hipótesis: el walk-forward deja al 69 % de los pares sin desplazamiento
(`NONE 1 865` frente a `STATION 752`), así que quizá fallaba por falta de historia.
**Medido, y es al revés:**

| subconjunto | pares | estaciones evaluables | calibradas |
|---|---:|---:|---:|
| **con** desplazamiento | 752 | 21 | **1 (5 %)** |
| **sin** desplazamiento | 1 865 | 46 | **11 (24 %)** |

Los pares que reciben corrección calibran **peor** que los que no. El método no está limitado
por los datos: hace daño.

## 3. La causa, medida: el sesgo por estación NO es persistente

Partiendo el periodo por la mitad (2026-04-08 → 06-18 → 09-04), sobre las 45 estaciones con
≥ 10 pares en ambas mitades:

```
correlación  sesgo(1ª mitad)  vs  sesgo(2ª mitad):   +0,080
|Δ| mediano entre mitades: 0,50 °C   ·   máximo: 4,35 °C   ·   desviación de los Δ: 1,16 °C
CYYZ +1,00 → +0,00 · EHAM +0,40 → −0,05 · KATL +0,96 → +0,40 · EPWA −0,15 → −0,60
```

**Una correlación de +0,08 significa que el sesgo de una estación en primavera no dice
prácticamente nada sobre su sesgo en verano.** Un desplazamiento aprendido del pasado se
aplica al futuro como ruido, y por eso degrada la calibración en vez de mejorarla.

## 4. Qué significa esto para B-11, con precisión

B-11 midió 43 de 45 estaciones descalibradas y una dispersión entre estaciones de
τ = 0,545 °C. **Ese hallazgo sigue siendo correcto como descripción de la muestra.** Lo que
v3 añade es que **esa dispersión no es una propiedad estable de la estación**: es en buena
parte un estado transitorio —estacional, o de régimen sinóptico— que no se transporta hacia
adelante.

Es decir: la heterogeneidad es **real y no corregible** con este sustrato. No es un defecto
que se arregle con más parámetros; es una limitación de lo que se puede saber con cinco meses
de datos.

## 5. Consecuencia operativa — la que importa para operar

**M2 se queda en v2: agrupado por lead, calibrado en agregado.** Es lo mejor disponible y su
calibración agregada está verificada fuera de muestra.

Pero hay que declararlo sin adornos: **la probabilidad que M2 da para un mercado concreto
está peor calibrada que su cifra agregada sugiere**, y esa diferencia **no se puede corregir**
con los datos actuales. El intervalo p10–p90 es honesto para el conjunto y demasiado estrecho
para cualquier estación individual.

Para quien fije `tau` (R21) esto no es un matiz: **el umbral de edge debe llevar margen por
descalibración de estación no corregible**, no sólo por costes y spread. Un edge que parezca
suficiente contra la distribución agregada puede no serlo contra la del mercado concreto.

## 6. Qué haría falta para cerrar esto (no se hace ahora)

- **Más periodo.** Con un año se podría comprobar si el sesgo tiene estructura estacional
  estable en vez de transitoria. Bloqueado por el archivo deslizante de Single Runs (B-1):
  el histórico no es recuperable hacia atrás, sólo acumulable hacia adelante.
- **Agrupar por región o por componente ICON** en vez de por estación: menos parámetros, más
  datos por grupo. Exige su propio preregistro y no se intenta aquí para no repetir el ciclo
  de probar estimadores hasta que uno pase.

## 7. Integridad

| Comprobación | Estado |
|---|---|
| Preregistro congelado y hasheado antes de calcular | **SÍ** |
| Umbrales cambiados tras ver el resultado | **NO** |
| Cuantiles de v3 escritos en la base | **NO** — no pasa §4 |
| v4 intentada tras el fallo | **NO** — §5 lo prohíbe hasta publicar este resultado |
| Desplazamiento estimado con pares no admisibles | **NO** — walk-forward por disponibilidad |

**Artefacto:** `M2_V3_ACCEPTANCE.json`. **En producción sigue v2**, con la limitación de §5
declarada en todo informe que la use.
