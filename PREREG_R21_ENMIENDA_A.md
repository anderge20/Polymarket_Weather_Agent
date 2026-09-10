# ENMIENDA A a PREREG_R21_BACKTEST_TAU — constantes que §1–§4 dejaron sin cuantificar

**Sesión:** B (Claude) · **Congelada:** 2026-09-09, **antes de calcular ningún PnL.**
**Enmienda a:** `PREREG_R21_BACKTEST_TAU.md`, sha `464226a3…`, que **sigue vigente**: esta
enmienda no cambia ninguno de sus umbrales, ni la rejilla de §3, ni los cuatro criterios de §4.

## 0. Prueba de que no se ha calculado ningún resultado

`PREREG_R21 §6` prohíbe cambiar nada «tras ver resultados». Estado del sustrato al congelar:

```
backtest_results   0 filas      signals       0 filas
predictions        0 filas      paper_trades  0 filas
```

Nada que ver todavía. Lo que esta enmienda hace **no es cambiar** una constante fijada: es
**fijar constantes que el preregistro dejó en prosa** y sin las cuales el backtest no se puede
ejecutar de una sola manera. Cada una se elige aquí, por escrito, antes de la primera corrida.

---

## A.1 La segunda fuente de incertidumbre: MEDIDA, y NO se añade al margen

La sesión A endureció P2 tras mi propio aviso: `tau_exec` no debe calibrarse como si la única
incertidumbre fuera la del modelo de error, porque el estimador de cuantiles también se mueve.
**Avisé bien y cuantifiqué mal.** Lo que llevé a A fue «saltos de hasta 0,39 °C, el 70 % de la
rejilla fina». Eso era un **máximo de valores absolutos sobre los cinco cuantiles**. `τ_est` es
una **dispersión**. No se pueden sumar magnitudes de distinto tipo, así que he medido la del
mismo tipo: desviación típica del desplazamiento **signado** de la mediana del error entre dos
reajustes separados por la **vida útil del artefacto** (Δ = 5 días = `max_age_hours` 120 h).

```
 lead     n     media     sigma    p95|·|    max|·|
    9   128   -0.0084    0.0373    0.1000    0.1000
   24   128   -0.0238    0.0548    0.1000    0.3000

 sigma_inst = 0,0548 °C   (máximo sobre los dos leads)
 tau_est    = 0,5450 °C   (B-11, dispersión entre estaciones)
 cuadratura = 0,5478 °C   →  +0,5 % sobre tau_est
```

**Decisión: §2 queda intacto, `τ_est = 0,545 °C`.** Añadir un término que mueve el margen un
0,5 % —menos que las tres cifras con que el propio §2 escribe τ— sería tocar un preregistro
congelado para no cambiar nada. La exigencia de A queda satisfecha **por medición, no por
término**: la segunda fuente existe, se ha medido, y es un orden de magnitud menor que la
primera.

**Por qué es pequeña, que es la parte que hay que entender y no celebrar:** M2 v2 agrupa entre
estaciones, así que su localización se estima con ~2 000 pares y cinco días más apenas la
mueven. **La estabilidad es una propiedad de v2 por ser agrupado, no del fenómeno.** Un M2 por
estación —el v3 retirado— tendría una inestabilidad mucho mayor, y esta cifra no se transporta
a él.

**Se declara también lo que no queda cubierto:** el `max|·|` de 0,300 °C a lead 24 es real. La
dispersión lo absorbe en el margen; el caso peor individual no. Va a limitaciones (§A.6).

## A.2 `x_exec` — CONGELADO en el peldaño MÁS adverso, y por qué

§1 exige evaluar «al precio alcanzable, nunca al cotizado» y **no da un número**. No lo puedo
medir: `orderbook_snapshots` tiene **0 filas** y las 16 165 636 de `price_history` son todas
`MIDPOINT_ESTIMATED`. No hay book en el histórico y no se puede reconstruir hacia atrás.

Por tanto el deslizamiento es un **supuesto declarado, no una medición**. Elijo el peldaño más
adverso de la escalera de D19:

```
x_exec primario   = 0,01  USDC/share  (1 punto)   ← métrica de decisión
sensibilidad      = 0,005 · 0,001 (1 tick) · 0
```

**El criterio de elección es que un supuesto sobre lo que no se ha medido no puede ser el que
fabrique un resultado positivo.** Si la estrategia pasa a 1 punto, pasa. Si sólo pasa con
`x_exec = 0`, no se ha demostrado que pase: se ha demostrado que pasaría si ejecutar fuese
gratis, y §1 llama a eso inventar rendimiento. `x_exec = 0` se reporta como columna y **no
puede ser la métrica de decisión**, ni siquiera si las demás fallan.

`tick_size` medido: 0,001 en 6 136 mercados y 0,01 en 7.

## A.3 Doble conteo del coste — la trampa que A ya encontró una vez

§2 escribe `tau_exec = tau_costes + margen_calibracion` como umbral sobre el edge **bruto**.
El backtest calcula un edge **neto**, que ya lleva los costes restados. Aplicar las dos cosas
restaría el coste dos veces — exactamente el defecto que A encontró en su R24 v2. Se fija:

```
p_exec    = p_mid + x_exec                       (compra: adverso)
edge_net  = p_model − p_exec − c_taker(p_exec)   (USDC/share, 1 share)
se opera si   edge_net > margen_calibracion(mercado)
```

`tau_exec` **es** el margen, porque `tau_costes` ya vive dentro de `edge_net`. Es el mismo
umbral de §2, no uno más laxo: se ha movido el coste de un lado al otro de la desigualdad.

## A.4 El margen, en la unidad correcta

`τ_est = 0,545 °C` es una **diferencia**, no una temperatura: al pasarla a Fahrenheit se
multiplica por 9/5 y **no** se le suma 32. `0,545 °C → 0,981 °F`. Añadir el 32 desplazaría la
distribución 18 grados y el margen saldría ≈ 1 para toda banda estrecha. Es la misma familia
que B-7 y por eso se escribe aquí.

```
margen(m) = max sobre s ∈ {+τ, −τ} de  |P(banda_m | dist desplazada s) − P(banda_m | dist)|
```

## A.5 La etiqueta de liquidación — CONGELADA: la resolución del VENUE

§4 habla de PnL y **no dice de dónde sale el resultado realizado**. Se fija: `winning_outcome`
del catálogo, restringido a `umaResolutionStatus = 'resolved'`. Es lo que **pagó**, que es la
única definición de PnL que no es una opinión.

**Auditada contra mis observaciones IEM, que son una fuente independiente**, sobre los 410
eventos en los que el sustrato contiene la banda ganadora:

```
CONCUERDA 382 · DISCREPA 28   →  tasa de acuerdo 0,932
de las 28:  25 con la observación POR DEBAJO de la banda ganadora
             3 con la observación POR ENCIMA
```

Las 25 son **exactamente la limitación ya declarada**: `y` es cota inferior porque el METAR
muestrea por horas y la máxima real puede caer entre muestras. Las 3 restantes (ZGSZ ×2,
RKSI ×1) **no** las explica el muestreo y quedan sin causa: se declaran.

**Consecuencia que excede R21 y va a la sesión A:** etiquetar desde las observaciones —la ruta
de R14— se habría equivocado en el **6,8 %** de los casos, y de forma **asimétrica**, siempre
subestimando la máxima y por tanto favoreciendo las bandas bajas. Un sesgo con signo, no ruido.

## A.6 Universo, lado y tamaño — CONGELADOS

- **`target_date` lo aporta el caller** (2D §C). El backtest itera fechas; no la deriva de
  `endDate`, `close_time`, la pregunta ni el slug. El filtro de universo `endDate = D 12:00Z`
  es un filtro, no una derivación (R8).
- **Se incluye** un mercado si: tiene ICAO real, `rounding_rule ≠ 'tenths'`, está `resolved`,
  hay cuantiles M2 para (estación, `target_date`) disponibles en el instante de decisión, y hay
  precio con `observation_time ≤` ese instante.
- **Sólo LARGO en YES.** El token con precio es el YES en los 6 143 mercados y de la pata NO
  no existe serie. D19 ya avisó de que `1 − p` es una identidad de precios y **no** un plan de
  ejecución: son dos books. Operar el lado corto exigiría un precio que no he observado.
  **Esto descarta la mitad de las señales y se declara como límite, no como diseño.**
- **Tamaño: 1 share.** D19. Nada de sizing por Kelly: con una probabilidad cuya calibración por
  mercado B-12 declaró no corregible, dimensionar por confianza sería apostar sobre el número
  que sé que está mal.
- `c_taker(p) = rate · (p(1−p))^exponent`, sólo taker, salida por redención sin fee (D19).
  `feesEnabled = false` → 0. `exponent ≠ 1` o esquema desconocido → `edge_net = None`,
  **fail-closed**, la operación no se hace y se cuenta.

**Limitaciones que esta enmienda añade a §7:** deslizamiento supuesto y no medido (no hay book
histórico) · sólo lado largo · el caso peor del estimador (0,300 °C a lead 24) no está en el
margen, sólo su dispersión · 3 resoluciones del venue sin explicación por observación.

## A.7 Lo que esta enmienda NO toca

`tau_signal` y su rejilla `{0,02k}` k = 1…10 · el criterio de selección por mediana · los
cuatro criterios de §4 (n ≥ 100, mediana > 0, leave-one-station-out, excluir el mes mayor) ·
`τ_est = 0,545` · el desenlace declarado de §5 · las prohibiciones de §6 · **el gate D0.**
