# PREREG_M2_ERROR v3 — corrección de localización por estación, con encogimiento

**Sesión:** B (Claude) · **Congelado:** 2026-09-09, antes de calcular ningún cuantil de v3.
**Sustituye a** v2 (`b2b168d4…`), que queda **RETIRADO por NO APTO** (B-11).

## 0. Por qué v3

**v2 pasó su propio criterio y aun así era inservible.** Mi validador (B-11): calibra en
agregado (lead 9 h 0,122/0,917; 24 h 0,102/0,914) **porque se cancelan sesgos opuestos**.
Desglosado: **43 de 45 estaciones descalibradas**; KLAX con 0,58 de realizados bajo su p10;
sesgos por estación de **−1,59 (KLAX) a +2,40 °C (RKPK)**.

El criterio de v2 §5 era demasiado débil: exigía calibración **agregada**, que es justamente
la que sobrevive a la cancelación.

**El diseño de v3 se elige tras ver fallar v2, y eso se declara.** Lo que **no** cambia son
los umbrales de calibración: siguen siendo 0,05–0,15 y 0,85–0,95, fijados en v2 antes de ver
nada. Tocarlos ahora sería elegir el listón a partir del resultado.

## 1. El estimador crudo sobrecorrige — corrección aportada por la sesión A, verificada por mí

Aplicar la mediana cruda por estación sobrecorrige, porque la dispersión observada entre
medianas contiene señal **y** ruido de estimación. A propuso la descomposición; la he
verificado **sin su supuesto de normalidad**, estimando la SE de la mediana por bootstrap:

| cantidad | A (teoría normal) | B (bootstrap, sin forma) |
|---|---:|---:|
| σ intra-estación | 1,54 | **1,507** |
| SE de la mediana (n≈30) | 0,379 | **0,302** |
| dispersión observada entre medianas | 0,620 | **0,623** |
| τ (señal real) | 0,491 | **0,545** |
| w = τ²/(τ²+SE²) | 0,627 | **0,765** |
| ruido en la varianza observada | 37 % | **24 %** |

La fórmula `1,2533·σ/√n` supone normalidad y **sobreestima la SE en un 25 %** sobre esta
muestra, que es asimétrica. Encoger con w = 0,627 **subcorregiría**. Se adopta la estimación
empírica.

**τ = 0,545 °C es el 14 % de la anchura p10–p90 (3,9 °C): la heterogeneidad entre estaciones
es real y hay que corregirla.** El diagnóstico de B-11 aguanta; el estimador crudo no.

## 2. Regla de corrección — CONGELADA

Para una decisión en `T` y lead `L`, sobre la ventana de entrenamiento admisible por
disponibilidad (v2 §3, sin cambios):

```
mediana_s   = percentil_50 del error de la estación s en la ventana
sigma       = desviación típica intra-estación agrupada de la ventana
SE_s        = desviación típica bootstrap de la mediana de s (200 remuestreos, semilla 20260909)
obs2        = varianza de {mediana_s} entre estaciones
tau2        = max(obs2 − media(SE_s²), 0)
w           = tau2 / (tau2 + media(SE_s²))          # 0 si tau2 = 0
shift_s     = w · mediana_s                          # encogimiento empirical-Bayes
```

`w` se **estima en cada ventana**, no se fija a mano. Si `tau2 = 0` la corrección se anula
sola y v3 degenera a v2, que es el comportamiento correcto cuando no hay señal entre
estaciones.

```
forecast_pXX(s) = f + shift_s + (percentil_XX(e_agrupado) − mediana(e_agrupado))
```

Localización por estación, **escala agrupada por lead**: con n≈30 una mediana es estimable,
nueve cuantiles no. Es la misma razón por la que v2 eliminó el estrato por estación.

## 3. Walk-forward también para el desplazamiento — CONGELADO

**El punto que más importa, y lo señaló A:** si los 45 desplazamientos se estiman sobre los
mismos pares con los que luego se evalúa la calibración por estación, **v3 pasa por
construcción** — con ~30 puntos y un parámetro libre por estación la calibración en muestra es
casi automática.

`shift_s` se estima **sólo con pares admisibles por disponibilidad antes de `T`**, la misma
disciplina que el resto de M2. Una estación sin `MIN_SHIFT_N = 20` pares admisibles recibe
`shift_s = 0` (no la mediana global: usar la del pool sería reintroducir el agregado) y la
fila se marca `shift_scope = 'NONE'`.

Si tras esto las primeras semanas quedan sin cobertura, **esa es la respuesta y se declara**.
No se rellena hacia atrás.

## 4. Criterio de aceptación — REFORZADO a nivel de estación

v3 se declara **VÁLIDO** si y sólo si, evaluado **fuera de muestra** (cada par contra los
cuantiles que se le escribieron, estimados sin él):

1. **Calibración por estación:** en al menos **el 70 % de las estaciones con n ≥ 15**, la
   fracción de realizados bajo `p10` cae en [0,05, 0,15] **y** bajo `p90` en [0,85, 0,95].
   El 70 % se fija **aquí**, antes de calcular: con 45 estaciones y ~30 puntos cada una,
   exigir 100 % sería exigir que el ruido de muestreo no exista.
2. **Calibración agregada:** se mantiene la de v2 (necesaria, nunca suficiente).
3. **Monotonía del horizonte:** MAE(24 h) ≥ MAE(9 h).
4. **No degenerado:** anchura p90 − p10 en (0, 30] °C.

Si (1) falla, **M2 NO soporta calibración por estación con este sustrato**. Ese resultado se
publica tal cual y la conclusión es agrupar por región o por componente ICON —con su propio
preregistro— o esperar más datos. **No se fuerza.**

## 5. Prohibiciones

- No se ajusta `w` a mano ni se prueban varios y se elige el mejor.
- No se cambian los umbrales de calibración ni el 70 % después de ver el resultado.
- No se estima `shift_s` con pares no admisibles por disponibilidad.
- No se rellena hacia atrás el periodo sin cobertura.
- Si v3 no pasa, **no se intenta una v4 con otro estimador hasta declarar públicamente que v3
  falló y por qué.**

## 6. Limitaciones heredadas

Todas las de v2 §7 siguen: disponibilidad de etiqueta supuesta a 24 h; `y` es cota inferior
por muestreo horario; periodo abril–septiembre acotado por el archivo deslizante; coordenadas
verificadas en 11 de 55; los 1 936 mercados `tenths` fuera. Y la nueva: **el encogimiento
supone que los sesgos de estación proceden de una población común**, que es un supuesto de
modelo, no una medición.
