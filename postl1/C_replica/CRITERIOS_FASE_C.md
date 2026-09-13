# POST-L1.8 · FASE C — CRITERIOS DE ELEGIBILIDAD Y REGLA DE SELECCIÓN

**Escrito y espejado ANTES de medir nada sobre el universo.** Ningún criterio usa Brier, top-1,
correlación, MAE, `B4`, `B4−S3`, PnL, precios, volumen, liquidez, rentabilidad ni «parece
prometedora». **Cero resultados de poder predictivo entran en la selección.**

Prohibido y no realizado en toda la fase: precios, EV, PnL, fills, order book, spreads,
liquidez, umbrales, entradas, salidas, stake, ejecución. `D0-P` = BLOCKED · `L2` = BLOCKED.

---

## CRITERIOS DE ELEGIBILIDAD — todos ex-ante, todos verificables sin mirar el resultado

### A · SETTLEMENT
* **A1** `resolution_source` identificable y única para la estación.
* **A2** `uma_resolution_status = 'resolved'` en todos los mercados del evento.
* **A3** exactamente **una** ganadora por evento (`winning_outcome = 'Yes'`).
* **A4** **partición completa** por `resolution.band_integrity`.
* **A5** ≥ 30 eventos que cumplan A2+A3+A4 **y** tengan observación y pronóstico.

### B · FORECAST
* **B1** **mismo proveedor y mismo modelo que Londres**: `icon_seamless`. *(No se cambia de
  modelo: la réplica usa exactamente el mismo `B4`.)*
* **B2** `issue_time` presente y `forecast_tmax` no nulo.
* **B3** las **dos** ejecuciones diarias (06z y 18z) presentes, para poder ejecutar **los dos
  leads**.
* **B4** ≥ 60 filas de pronóstico (≥ 30 días × 2 ejecuciones).

### C · OBSERVACIÓN
* **C1** observación independiente presente en `weather_observations`.
* **C2** **unidad `C`**. *(Motivo metodológico declarado ANTES de mirar: el guion de Londres
  lleva la puerta `exige_celsius()` y la versión multiunidad **no existe** — tarea #72. Una
  ciudad en Fahrenheit exigiría código nuevo, y el encargo prohíbe cambiar la metodología para
  la réplica.)*
* **C3** timezone de la estación resuelta por `stations.timezone_of`.
* **C4** ≥ 40 días locales con observación.

### D · TEMPORALIDAD
* **D1** ≥ 30 eventos puntuables tras la puerta de `MIN_TRAIN = 20` — el mismo mínimo que
  Londres, sin tocarlo.
* **D2** periodo continuo suficiente para una ventana expansiva.

### E · DISPONIBILIDAD
* **E1** el modelo es `icon_seamless`, cuyo `L_MAX = 4,76 h` está auditado (F-3, n = 78 pasadas
  ICON). **La latencia es del MODELO, no de la ciudad**, así que la cota aplica igual.
* **E2** se reporta qué fracción de los eventos de la ciudad cae dentro de la ventana con
  evidencia (**2026-06-03 → 2026-09-04**) y cuánta en periodo `UNKNOWN`.

### F · LADDER
* **F1** `band_integrity` da partición en todos los eventos elegibles.
* **F2** tamaño de escalera conocido, y **al menos un estrato con ≥ 30 eventos puntuables**
  (nunca se agregan escaleras distintas: H4 = INVALIDADA).
* **F3** `parse_band` determinista en la unidad del mercado.

---

## REGLA DE SELECCIÓN — determinista, escrita antes de aplicarla

1. Se aplican **A–F** a las **52 estaciones** de `markets_v2`. La lista de las que pasan es el
   **universo elegible**, y se publica entera.
2. Si el universo tiene **una** ciudad → ésa es la réplica.
3. Si tiene **más de una** → se elige la de **mayor número de eventos puntuables (D1)**, porque
   es el criterio que maximiza la **potencia estadística** de la prueba, que es lo que la fase C
   necesita. *Es un criterio de potencia, no de resultado.*
4. **Empate en D1** → orden **alfabético ascendente por ICAO**. Determinista y sin juicio.
5. Si el universo está **vacío** → **se declara así**, se documenta exactamente qué falta, y
   **no se relajan los criterios para que entre alguien**. Un universo vacío es un resultado de
   fase C, no un fallo del procedimiento.

**Prohibido**: elegir a mano, elegir «la que parezca mejor», o ejecutar modelos sobre varias y
quedarse con una.

---

## LO QUE NO SE TOCA EN LA RÉPLICA

`B0`…`B4` **idénticos** · `S3` **idéntico** · `t_asof = end_date(12:00Z) − lead` · leads **24 y
9, los dos** · `MIN_TRAIN = 20` · `epsilon = 1e-6` · walk-forward expansivo por evento ·
bootstrap **clusterizado por evento**, 10 000, semilla **20260913** · unidad de inferencia
**EVENTO** · métrica primaria **`B4 − S3` apareado**, con `B4 − uniforme` y `B4 − B0`
reportados · **nunca** se agregan escaleras distintas.

**Si la metodología no funciona en la ciudad nueva, eso es el resultado. No se corrige después.**

---

## CRITERIO DE VEREDICTO DE LA RÉPLICA

| | condición |
|---|---|
| **REPLICATED** | `B4 − S3 < 0` con IC95 que excluye el cero, **mismo signo** que Londres, magnitud material, controles superados y potencia suficiente |
| **NOT REPLICATED** | `S3` gana con IC que excluye el cero **y** potencia suficiente |
| **INCONCLUSIVE** | IC que incluye el cero, **o** potencia insuficiente (razón efecto/MDE < 1) |

**Un resultado negativo con potencia insuficiente es `INCONCLUSIVE`, nunca `NOT REPLICATED`.**
Y **una réplica negativa no se compensa buscando otra ciudad**: si falla con potencia
suficiente, se para y se analiza.
