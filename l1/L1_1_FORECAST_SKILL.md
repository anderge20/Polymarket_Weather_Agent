# LEVEL 1 · L1.1 — FORECAST SKILL

Ejecuta la §6 de `PREREG_LEVEL1.md`, espejado a las **20:18:35Z** (`e4db1af`) **antes** de
correr esto. **No entrena modelos, no convierte nada en probabilidad, no calcula edge ni PnL.**
`D0-P` sigue BLOCKED.

Error medido en **Celsius**: `tmax_observed − forecast_tmax`. **Nunca `observed_value`**, que es
la rejilla del mercado y sirve para pertenencia a banda, no para el error (A-283).

    pares validos              236   (118 dias objetivo x 2 ejecuciones)
    ejecuciones                06z y 18z, las dos emitidas el dia ANTERIOR al objetivo
    lead 24 = 06z  ·  lead 9 = 18z      (medido en la preinscripcion §3)

---

## Global y por lead

| | n | bias | MAE | RMSE | MedAE | p10 | p90 | sd |
|---|---|---|---|---|---|---|---|---|
| todos | 236 | **+0,15** | **0,94** | **1,22** | 0,80 | −1,40 | +1,60 | 1,21 |
| **lead 24 (06z)** | 118 | +0,18 | 1,01 | 1,30 | 0,80 | −1,49 | +1,70 | 1,29 |
| **lead 9 (18z)** | 118 | +0,12 | **0,87** | **1,13** | 0,70 | −1,13 | +1,33 | 1,12 |

**El lead 9 es mejor que el lead 24 en las cuatro medidas.** Es el orden que cabía esperar —la
18z es una revisión posterior— y sirve además como comprobación interna: *si el lead 9 no fuera
mejor, habría algo mal en la lógica de disponibilidad.*

## Por mes

    2026-04  lead24 MAE 1,03 · lead9 0,81        2026-07  lead24 0,82 · lead9 0,70
    2026-05  lead24 MAE 1,05 · lead9 0,95        2026-08  lead24 0,91 · lead9 0,75
    2026-06  lead24 MAE 1,22 · lead9 1,10   <- el peor

Ningún mes se descuelga: el recorrido es 0,70–1,22 de MAE. **No hay un periodo que sostenga
solo el resultado**, que es una de las cosas que el criterio C exige mirar.

## Por rango de temperatura observada — hay SESGO CONDICIONAL

| obs (°C) | n | bias | MAE |
|---|---|---|---|
| < 15 | 24 | **−0,55** | 1,03 |
| 15–20 | 56 | −0,08 | 1,03 |
| 20–25 | 42 | +0,30 | 0,90 |
| 25–30 | 82 | +0,37 | **0,80** |
| ≥ 30 | 32 | +0,30 | 1,12 |

> **El signo del sesgo cambia con la temperatura**: en días fríos el pronóstico va **alto**
> (obs − fc < 0) y en días cálidos va **bajo**. Es encogimiento hacia la media, el patrón
> clásico. **Importa para `B3`**: una corrección de sesgo **global** no captura un sesgo
> **condicional**, así que `B3` está estructuralmente limitado y hay que decirlo antes de ver
> su resultado, no después.
>
> **No se introduce una corrección condicional.** Sería un sexto modelo y la preinscripción lo
> prohíbe hasta que alguno de los cinco muestre señal.

## Cobertura p10/p90 — del proveedor, NO se usan como modelo

    lead 24  n=115  cobertura 84,3 %  (nominal 80 %)  anchura media 3,82 C   14 por debajo · 4 por encima
    lead  9  n=115  cobertura 87,8 %  (nominal 80 %)  anchura media 3,48 C   14 por debajo · 0 por encima

Los intervalos del proveedor están **ligeramente sobredimensionados** (cubren más de lo
nominal). Y los fallos son **asimétricos**: casi todos por abajo — la observación sale más fría
que `p10`. **Estos cuantiles no entran en Level 1**: serían un sexto modelo. Se miden aquí
porque describen la calidad del pronóstico, no porque se vayan a usar.

## Estabilidad de las revisiones 06z → 18z

    dias con las dos ejecuciones      118
    revision (18z - 06z)              MAE 0,54 C · RMSE 0,73 · identica en 12 de 118 dias
    |e06| - |e18|   (>0 = mejora)     media +0,14 C
    la 18z acierta mas en 62 dias · empata 13 · peor 43

**La revisión es información nueva de verdad** —difiere en 106 de 118 días— y **mejora en
promedio, pero no siempre**: gana en 62 y pierde en 43. Un pronóstico que mejorase siempre al
revisarse sería sospechoso.

---

## EL NÚMERO QUE GOBIERNA TODO LO QUE VIENE DESPUÉS

Las bandas del contrato son de **1 °C**. El error típico del pronóstico es de **0,94 °C**. Así
que la pregunta *«¿en qué banda cae?»* es intrínsecamente difícil, y conviene verlo en la
rejilla del contrato antes de puntuar nada:

| | lead 24 | lead 9 |
|---|---|---|
| `round(obs) = round(fc)` — **grado exacto** | **33,9 %** | **35,6 %** |
| a un grado | 40,7 % (30 arriba, 18 abajo) | 50,8 % (38 arriba, 22 abajo) |
| a dos o más | 25,4 % | 13,6 % |
| `\|e\| ≤ 0,5 °C` | 37,3 % | 38,1 % |

**Contra el nulo uniforme de una escalera de 11 bandas —1/11 = 9,1 %— acertar el grado exacto
el 34-36 % de las veces es entre 3,7 y 3,9 veces mejor que el azar.**

> **Y lo que esto NO dice.** Es *forecast skill*: pronóstico contra **observación**. El target
> de Level 1 es **`winning_outcome`**, la resolución contractual, que coincide con nuestro proxy
> observacional en **136 de 137** casos (A-276) pero **no es lo mismo**. Convertir este 34 % en
> una afirmación sobre el contrato es exactamente el paso que L1.2–L1.5 tienen que hacer con
> cuidado, y no está hecho aquí.

---

## VEREDICTO DE ETAPA

**El pronóstico contiene señal meteorológica real**: MAE 0,94 °C, sin mes que se descuelgue,
con la revisión posterior mejorando a la anterior y con el grado exacto acertado ~3,8 veces por
encima del azar.

**Ningún defecto metodológico en esta etapa.** Se puede pasar a `L1.2 — BASELINES`.

**Registrado para no olvidarlo cuando toque interpretar:** el sesgo es **condicional** a la
temperatura, así que `B3` (corrección global) está limitado por construcción; y la anchura de
banda (1 °C) es del mismo orden que el error típico (0,94 °C), así que **el techo de cualquier
modelo puntual sobre esta escalera es bajo por física, no por método**.
