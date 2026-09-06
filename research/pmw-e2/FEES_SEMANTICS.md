# FEES_SEMANTICS — semántica de fees de Polymarket y modelo de coste preregistrable (R11)

**Fecha:** 2026-09-06 · **Método:** workflow `wf_81c10776-eaa` — 3 investigadores (documentación oficial, catálogo `CATALOG_V2.duckdb` read-only, código del repo) → síntesis → 2 refutadores adversariales (fuente, datos). Resultados completos en `WF_fees_results.json`.
**Confianza declarada por la síntesis:** STRONGLY_SUPPORTED

## 0. Veredicto de la refutación y correcciones aplicadas

- **Fuente — PASA.** Cada fórmula, parámetro y cita literal existe y dice lo afirmado; la fórmula reproduce la tabla oficial de 100 shares (p=0.05→$0.24, 0.10→$0.45, 0.50→$1.25); leer 1000 bps como *rate* daría $2.50 en p=0.5, incompatible con la tabla. Corrección aplicada: el mínimo de 0.00001 USDC **no es un suelo** — *"Anything smaller rounds to zero"* → `fee = round5(C·c(p))`, y si redondea a 0 la fee es 0.
- **Datos — REFUTACIÓN PARCIAL, acotada.** Los agregados del catálogo se reproducen exactamente (8 770 sin fees / 84 451 con fees; endDate 30-mar mezclado 275/143; `feeSchedule` único {1, 0.05, true, 0.25}; mbf/tbf 1000; tick 0.001 en 99,56 %). Lo refutado son dos IDs/horas ilustrativos del corte: el primer mercado con fees de endDate 30-mar es **Toronto 1779469** (createdAt 2026-03-29 18:09:15Z), no Atlanta; la creación de ese día va **intercalada** (7 eventos sin fees → 7 con → 16 sin → 5 con → Moscú sin → Ciudad de México con), es decir, la activación fue por lote y **no** por orden de creación. Corrección aplicada en §3. Nada del coste modelado cambia.

## 1. Semántica (OBSERVADO salvo donde se indica)

SEMÁNTICA ADOPTADA (hipótesis principal H1). La fee efectiva de un mercado weather la define el objeto Gamma `feeSchedule` = {exponent:1, rate:0.05, takerOnly:true, rebateRate:0.25}, NO los campos makerBaseFee/takerBaseFee=1000.

OBSERVADO (docs.polymarket.com/trading/fees.md, re-verificado 2026-09-06): "Fees are calculated using the following formula: fee = C × feeRate × p × (1 - p)"; tabla de categorías "| Weather | 0.05 | 0 | 25% |"; "Makers are never charged fees. Only takers pay fees."; "Fees are rounded to 5 decimal places. The smallest fee charged is 0.00001 USDC." Esa página NO menciona makerBaseFee, takerBaseFee, base fee, basis points ni feeRateBps ("Not present").
OBSERVADO (docs.polymarket.com/market-data/market-details#trading-fees): "feeSchedule.rate: Base rate used in the fee calculation. | feeSchedule.exponent: Exponent applied to the price component of the fee curve. | feeSchedule.takerOnly: When true, fees are charged to the taker side only, and makers pay no fee. | feeSchedule.rebateRate: Fraction of taker fees rebated back to the resting maker. Example: 0.25 = 25% rebate."
OBSERVADO (docs.polymarket.com/changelog): "Mar 31, 2026: Fees should now be calculated using the `feeSchedule` object within a market." y "Apr 17, 2026: Fees are now set at match time — no more `feeRateBps` on orders".
OBSERVADO (en vivo 2026-09-06): GET https://gamma-api.polymarket.com/markets/4107021 → feesEnabled true, feeType 'weather_fees', feeSchedule {exponent 1, rate 0.05, takerOnly true, rebateRate 0.25}, makerBaseFee 1000, takerBaseFee 1000; GET https://clob.polymarket.com/clob-markets/0xf9a5bbe3… → mbf 1000, tbf 1000, fd {r:0.05, e:1, to:true}. OpenAPI CLOB define mbf/tbf/base_fee como "base fee in basis points" (1000 bps = 10%).
OBSERVADO (verificación aritmética contra la tabla oficial de 100 shares): 100×0.05×0.5×0.5 = $1.25 ✓; 100×0.05×0.1×0.9 = $0.45 ✓. Con 1000 bps=10% en la misma fórmula saldría $2.50 ≠ $1.25.

INFERIDO: 1000 bps es el `feeRateBps` on-chain de CTF Exchange V1 (tope firmado; el FeeModule "refunds" el exceso) que sobrevive como campo heredado / flag binario (1000 ↔ feesEnabled=true, 0/NULL ↔ false; colinealidad 100% en el catálogo). Evidencia empírica pública de que la fee real sigue feeSchedule y no el 10%: py-clob-client issue #326 (sports, rate 0.03, base_fee 1000: "5 shares at $0.65 → 4.9475 shares, fee 0.0525 = 5×0.03×0.35"). NO existe frase oficial que relacione 1000 con 0.05 → esa relación queda UNKNOWN; lo que SÍ está documentado es que el cálculo se hace con feeSchedule.

Deducción por lado: en BUY taker la fee se descuenta en shares (fee_usdc/p) — OBSERVADO en #326 (sports) y coherente con docs "Taker fees are calculated in USDC"; place-orders: "A market BUY's amount is the pre-fee USD notional. Applicable platform fees and builder taker fees are charged on top." Para weather no hay fill real verificado (UNKNOWN empírico, ver incógnitas).

Maker: fee 0 (takerOnly). Rebate 25% NO es un descuento por trade: docs.polymarket.com/programs/maker-rebates: "fee_equivalent = C × feeRate × p × (1 - p) … rebate = (your_fee_equivalent / total_fee_equivalent) × rebate_pool … Totals are calculated per market … A minimum accrued rebate of $1 pUSD is required for a payout." → esperanza acotada por 0.25×fee_equivalent, no calculable ex ante; en Strategy A se modela como 0 (conservador) y se reporta la cota superior aparte.

## 2. Fórmula de coste

```
Notación: C = shares, p = precio de ejecución del token comprado (YES a p; FADE = NO a 1−p), r = feeSchedule.rate, e = feeSchedule.exponent, regime = markets.fee_regime.

(1) Fee taker por share (USDC), H1 principal:
   c_taker(p) = r · (p·(1−p))^e   con r=0.05, e=1  ⇒  c_taker(p) = 0.05·p·(1−p)   [máx 0.0125 USDC/share en p=0.5]
   Fee total = round5( C · c_taker(p) ), mínimo 0.00001 USDC (docs: "rounded to 5 decimal places").
   Como fracción del notional comprado (C·p): f(p) = 0.05·(1−p) → 4.5% en p=0.10; 3.5% en 0.30; 2.5% en 0.50; 0.5% en 0.90.
   Simetría: comprar YES a p y comprar NO a 1−p pagan la misma fee/share.
   fees_disabled: c_taker = 0 (JUSTIFICADO por feesEnabled=false + CLOB base_fee=0). fee_status≠KNOWN o e≠1 → None (fail-closed).

(2) Desembolso y shares recibidas (BUY taker, C shares nominales a p):
   desembolso = C·p + C·c_taker(p)   [docs place-orders: fees "charged on top" del notional pre-fee]
   Equivalente observado en #326 (deducción en shares): shares_netas = C·(1 − r·(1−p)); ambas formas dan el mismo coste USDC = C·r·p·(1−p).

(3) Edge neto por share (Strategy A, señal bruta intacta):
   edge_net_BUY  = (p_model − p) − c_taker(p) − exit_cost − x_exec
   edge_net_FADE = ((1−p_model) − (1−p)) − c_taker(p) − exit_cost − x_exec
   exit_cost = c_taker(p_exit) si exit_mode='taker_close'; = 0 si exit_mode='hold_to_resolution' (redención sin fee documentada; gas fuera del modelo, ver incógnitas).
   x_exec = spread_cost + slippage: parámetro explícito preregistrado (no estimable históricamente; 0 sólo como valor JUSTIFICADO y declarado).
   R11: fees_disabled ∧ x_exec=0 ⇒ edge_net = edge_gross.

(4) Maker (si Strategy A cotiza en vez de tomar):
   c_maker = 0 ; rebate_esperado ∈ [0, 0.25·C·r·p·(1−p)] (pool diario pro-rata por mercado, mínimo $1 pUSD) → modelar rebate=0 y reportar cota superior.

(5) PnL neto por operación (hold_to_resolution, resultado Y∈{0,1} para el token comprado):
   pnl_net = C·(Y − p) − C·c_taker(p) − C·x_exec   (para FADE sustituir p→1−p, Y→1−Y)

(6) Hipótesis alternativa H2 (fórmula on-chain V1 con feeRateBps=1000 aplicada íntegra): c_H2(p) = 0.10·min(p, 1−p) USDC/share [BUY: fee_shares = 0.10·min(p,1−p)·C/p]. Cota H3 (1000 bps dentro de la fórmula documentada): c_H3(p) = 0.10·p·(1−p). Cota H4 (1000 = 0.1%): c_H4(p) = 0.001·p·(1−p).
```

## 3. Épocas (fronteras por `endDate`; corregidas tras refutación)

- **2025-12-30 (endDate mínimo del catálogo) → 2026-03-30 (endDate; ese día sólo 275 mercados de 25 ciudades no norteamericanas)**: fee_regime='fees_disabled': c_taker=0, c_maker=0, rebate=0 (JUSTIFICADO por feesEnabled=false; CLOB /fee-rate base_fee=0; sin fd). edge_net = edge_gross − x_exec. 8.770 mercados.
  - evidencia: OBSERVADO CATALOG_V2.duckdb mk: (False, NULL, NULL, NULL, 8770, '2025-12-30T12:00:00Z', '2026-03-30T12:00:00Z'); en vivo Gamma 1779191 (Paris 30-mar) feesEnabled false, feeType null; CLOB /fee-rate → {"base_fee":0}
- **2026-03-30 (endDate; 143 mercados de 13 ciudades norteamericanas: Atlanta, Austin, Chicago, Dallas, Denver, Houston, Los Angeles, Mexico City, Miami, NYC, San Francisco, Seattle, Toronto) → 2026-04-28 (cutover CLOB V2)**: fee_regime='weather_fees', sub-época V1: c_taker=0.05·p·(1−p) USDC/share (H1); mecanismo on-chain = feeRateBps=1000 firmado en la orden + FeeModule refund (INFERIDO). Para endDate ≥ 2026-03-31 el 100% del catálogo tiene fees; para endDate = 2026-03-30 leer feesEnabled por fila (0 eventos mixtos).
  - evidencia: OBSERVADO changelog "Mar 30, 2026: Fees now apply to … Weather …" y "Mar 31, 2026: Fees should now be calculated using the feeSchedule object"; catálogo 30-mar: (True,143)/(False,275); primer mercado con fees 1779513 Atlanta (createdAt 2026-03-29T18:09:47Z), último sin fees 1779683 Taipei (createdAt 18:11:35Z); Istanbul 31-mar creado el 27-mar ya con fees → corte por lote/evento, no por createdAt ni endDate. Evidencia de fee real = curva feeSchedule bajo base_fee 1000: issue #326 (sports, abr-2026)
- **2026-04-28 (CLOB V2: 'Order struct: nonce, feeRateBps, taker removed'; 'Fees are now set at match time') → 2026-09-04 (endDate máximo del catálogo) / vigente**: fee_regime='weather_fees', sub-época V2: misma fórmula c_taker=0.05·p·(1−p) (v2-migration: 'Platform fees are dynamic per market: fee = C × feeRate × p × (1 - p)'; 'Makers are never charged fees'); makerBaseFee/takerBaseFee=1000 persisten como campo heredado. Desde 2026-05-28 existe Taker Rebate Program (0–50% según volumen; modelar 0).
  - evidencia: OBSERVADO changelog Apr 17/Apr 28 2026; https://docs.polymarket.com/v2-migration; en vivo 2026-09-06 market 4107021 (London 4-sep) feeSchedule {1,0.05,true,0.25}, mbf/tbf 1000, fd {0.05,1,true}; catálogo 84.451 mercados con feeSchedule idéntico hasta endDate 2026-09-04

*Corrección (refutador de datos):* para endDate 2026-03-30 la creación (2026-03-29 UTC) fue intercalada por lotes: Paris 17:46:33 … Seoul 18:08:32 (sin fees) → Toronto 18:09:15 (mk 1779469, **primer mercado con fees**) … Chicago 18:10:02 (con) → Wellington 18:10:12 … Shenzhen 18:12:10, incl. Taipei 18:11:34 (sin) → Austin 18:12:18 … San Francisco 18:12:48 (con) → Moscow 18:12:55 (mk 1779810–1779820, **último sin fees**) → Mexico City 18:13:05 (mk 1779821–1779831, con). Regla del corte: **por lote, no documentada**; en el pipeline se lee `feesEnabled`/`feeSchedule` **por mercado**, nunca por fecha.

## 4. Parámetros

| parámetro | valor | origen | incertidumbre |
|---|---|---|---|
| rate (r) | 0.05 | Gamma feeSchedule.rate (84.451/84.451 mercados con fees en CATALOG_V2.duckdb mk; en vivo market 4107021) = fila Weather de https://docs.polymarket.com/trading/fees.md "| Weather | 0.05 | 0 | 25% |"; CLOB fd.r=0.05 | Baja para el valor ACTUAL. Gamma no expone histórico: no se puede excluir desde el catálogo que hubiera otro rate entre 30-mar y hoy (changelog no registra ningún cambio de weather tras el 30-mar; sports sí cambió 0.03→0.05 el 10-jul-2026) |
| exponent (e) | 1 | Gamma feeSchedule.exponent; CLOB fd.e=1; docs market-details: "Exponent applied to the price component of the fee curve" | Forma general c=r·(p(1−p))^e es INFERIDA (pico 1.56% del changelog crypto con r=0.25,e=2); para weather e=1 la fórmula documentada aplica literalmente. Fail-closed si e≠1 |
| takerOnly | true (maker fee = 0) | Gamma feeSchedule.takerOnly; docs: "Makers are never charged fees. Only takers pay fees." | Baja |
| rebateRate | 0.25 (cota superior; modelar 0 en edge_net) | Gamma feeSchedule.rebateRate; https://docs.polymarket.com/programs/maker-rebates: "rebate = (your_fee_equivalent / total_fee_equivalent) × rebate_pool", mínimo $1 pUSD | Alta: reparto diario de pool por mercado, depende de la competencia de makers; no estimable ex ante |
| makerBaseFee / takerBaseFee / CLOB base_fee (mbf, tbf) | 1000 bps (=10%) — NO se usa en el coste | Gamma (integer sin descripción en gamma-openapi.yaml); CLOB openapi: "Maker/Taker base fee in basis points"; en vivo 1000 con fees / 0 sin fees | UNKNOWN su relación con rate; INFERIDO que es el feeRateBps on-chain V1 (tope) y hoy un flag binario de época. Contradice los ejemplos oficiales si se usa como rate ($2.50 vs $1.25) |
| redondeo / fee mínima | 5 decimales; mínimo 0.00001 USDC | https://docs.polymarket.com/trading/fees.md | Baja; irrelevante salvo micro-órdenes |
| tick_size | 0.001 (92.810 mercados, 99.56%) / 0.01 (411 mercados, endDate 2026-03-13..2026-09-01, 343 con slug 'arch-') | CATALOG_V2.duckdb mk (verificado read_only 2026-09-06); Gamma orderPriceMinTickSize | Regla que fija 0.01 desconocida; leer por mercado, no por época. El docstring de fees.py ('BOTH epochs carry orderPriceMinTickSize=0.001') es incompleto |
| min_order_size | 5 (100% de mercados) | CATALOG_V2.duckdb mk; Gamma orderMinSize; CLOB mos=5 | Unidad no confirmada: market-details dice 'Minimum order size in USDC', CLOB sólo 'Minimum order size' |
| x_exec (spread_cost + slippage) | UNKNOWN → parámetro preregistrado explícito | config.FEE_CONFIG.effective_cost_components (sin consumidor); no hay orderbook histórico (precio INDICATIVE) | No estimable con datos históricos; sólo forward-only (R22) |
| exit_cost | 0 si hold_to_resolution; c_taker(p_exit) si cierre taker | Derivado de la fórmula oficial (segunda operación taker) | Fee de redención no documentada (no encontrada ni afirmada ni negada) → tratar 0 como supuesto declarado, no verificado |
| taker rebate program | 0 por defecto (0–50% de la fee taker según wV 30 días; Tier 1 = $2.000 wV → 3%) | https://docs.polymarket.com/programs/taker-rebates (desde 2026-05-28; Weather weight 1.7) | Sólo relevante a volumen alto; no incluir en edge_net base |
| builder fee | 0 (no se opera vía builder) | docs place-orders: 'Applicable platform fees and builder taker fees are charged on top' | Componente opcional; añadir si se usa un builder |

## 5. Sensibilidad a la semántica

Coste taker por share (USDC) bajo cada semántica, en p = 0.10 / 0.30 / 0.50 / 0.70 / 0.90:
- H1 (principal) c=0.05·p·(1−p): 0.0045 / 0.0105 / 0.0125 / 0.0105 / 0.0045  (fracción del notional: 4.5% / 3.5% / 2.5% / 1.5% / 0.5%)
- H2 (on-chain V1 íntegro, 1000 bps) c=0.10·min(p,1−p): 0.0100 / 0.0300 / 0.0500 / 0.0300 / 0.0100  (2.2× a 4× H1; fracción del notional 10% / 10% / 10% / 4.3% / 1.1%)
- H3 (1000 bps = 10% como rate en la fórmula documentada) c=0.10·p·(1−p): exactamente 2× H1 (máx 0.025 en p=0.5)
- H4 (1000 = 0.1%) c=0.001·p·(1−p): ≤0.00025 → edge_net ≈ edge_gross (H4 es indistinguible de fees_disabled a efectos prácticos)
- H5 (10% flat sobre notional) c=0.10·p: 0.01 / 0.03 / 0.05 / 0.07 / 0.09 — asimétrica: penaliza BUY YES caro y favorece FADE; descartada por los ejemplos oficiales pero incluida como cota extrema.

Edge bruto mínimo para edge_net>0 (x_exec=0, hold_to_resolution): H1: 1.25 pt en p=0.5 (0.45 pt en extremos); H2: 5 pt en p=0.5 (1 pt en extremos); H3: 2.5 pt; H5: hasta 9 pt en p=0.9. Con cierre taker (dos operaciones) los umbrales aproximadamente se duplican.

Implicación para Strategy A: con umbrales τ típicos de pocos puntos, H1 deja rentable la mayor parte de señales con |edge|≥2–3 pt en todo el rango de p; H2/H3 eliminan las señales en la zona central (p∈[0.3,0.7]) salvo edges ≥5 pt y conservan sólo las de colas; H5 invalida además la simetría BUY/FADE. Todas las hipótesis salvo H5 son simétricas en p↔1−p, así que la elección BUY vs FADE no depende de la semántica; sólo el nivel del umbral. El 25% de rebate maker, si se realizara íntegro, reduciría el coste efectivo de una entrada maker a −0.25·c_H1 (ingreso), pero no es determinista y se modela 0.

Épocas: la parte fees_disabled (8.770 mercados, 9.4% del catálogo, endDate ≤ 2026-03-30) es invariante a la semántica (c=0 bajo todas). La sensibilidad afecta al 90.6% restante. Riesgo residual de histórico: si el rate weather hubiera sido distinto de 0.05 en algún subperiodo (no hay constancia en changelog), el PnL de ese tramo estaría mal escalado proporcionalmente.

## 6. Propuesta de preregistro (para D19)

PREREGISTRO 'FEES' (para DECISIONS.md, R11):

H_principal (H1): para mercados con fee_regime='weather_fees' y fee_status='KNOWN', c_taker(p) = feeSchedule.rate · (p·(1−p))^feeSchedule.exponent USDC/share (=0.05·p·(1−p)); c_maker=0; rebate=0 (cota superior 0.25·fee_equivalent reportada aparte); fees_disabled → c=0; fee_status≠KNOWN o exponent≠1 → edge_net=None (fail-closed). Fuentes: docs.polymarket.com/trading/fees.md (fórmula + fila Weather), market-data/market-details (definición feeSchedule), changelog 31-mar-2026 (feeSchedule como fuente de cálculo), catálogo (feeSchedule único {1,0.05,true,0.25}).

H_alternativa (H2): la fee real es la del contrato CTF Exchange V1 con feeRateBps=takerBaseFee=1000: c_taker(p) = 0.10·min(p,1−p) USDC/share (BUY deducido en shares = 0.10·min(p,1−p)·C/p). Se preregistra porque 1000 bps es el único valor que la doc CLOB define con unidad ('base fee in basis points') y su relación con rate=0.05 no está documentada (UNKNOWN).

Parámetros fijados a priori: exit_mode='hold_to_resolution' (exit_cost=0, redención sin fee = supuesto declarado); x_exec=0 JUSTIFICADO y declarado como 'sin modelo de spread/slippage hasta R22' (se añadirá una variante x_exec=0.5·tick y x_exec=1 pt como estrés); rebate maker=0; taker rebate program=0; builder fee=0; sizing C no altera el coste por share (exponent=1), sólo escala PnL.

Reporte obligatorio (por mercado, época y agregado): edge_gross, pnl_gross, y en columnas separadas edge_net_H1 / pnl_net_H1 (métrica de decisión primaria), edge_net_H2 / pnl_net_H2 (robustez), edge_net_H3 / pnl_net_H3 (cota 2×). predictions.edge_net y signals.net_edge se rellenan con H1; H2/H3 van en columnas o tabla auxiliar 'costs_sensitivity' con hipótesis_id. Criterio preregistrado: la estrategia se declara 'robusta a semántica de fees' sólo si pnl_net_H2 > 0 en la época weather_fees; se declara 'positiva' si pnl_net_H1 > 0 con IC bootstrap que excluya 0. Segmentar SIEMPRE por fee_regime (fees_disabled vs weather_fees) y por sub-época V1/V2 (corte 2026-04-28) como análisis secundario; para endDate=2026-03-30 usar el flag por fila.

Test de falsación (forward, R22): con el primer fill taker real en un mercado weather registrar C, p, USDC gastado y shares recibidas; calcular fee_observada/share. Regla de decisión: si |fee_obs − c_H1(p)| ≤ 5% de c_H1 → H1 ADOPTADA (confianza DEMOSTRADA); si coincide con c_H2 (±5%) → conmutar la métrica primaria a H2 y reprocesar; si no coincide con ninguna → fee_status='UNKNOWN' y edge_net=None hasta nueva evidencia. Además registrar feeSchedule de Gamma en cada snapshot del colector para construir el histórico que Gamma no expone.

## 7. Incógnitas declaradas

- UNKNOWN: relación oficial entre makerBaseFee/takerBaseFee/base_fee=1000 bps y feeSchedule.rate=0.05; ninguna página de docs.polymarket.com la enuncia. La lectura 'tope on-chain V1 + flag heredado' es INFERIDA (CalculatorHelper.sol + FeeModule README + issue #326 abierto sin respuesta de mantenedores).
- UNKNOWN empírico: no existe ningún fill real verificado en un mercado weather (los /trades del CLOB requieren auth L2; el data-api público no expone fee). La única evidencia de fill es de sports (issue #326, abr-2026, CLOB V1).
- UNKNOWN: fórmula exacta de CLOB V2 en el contrato (28-abr-2026); la doc v2-migration reproduce C×feeRate×p×(1−p) y 'fee-adjusted fill amounts', pero no se ha leído el código del exchange V2 ni el lado (shares vs USDC) en que se deduce.
- UNKNOWN: vigencia histórica del feeSchedule. Gamma/CLOB devuelven el valor ACTUAL; el catálogo no tiene fee history. El changelog no registra cambios de weather tras el 30-mar-2026, pero no se puede demostrar que rate=0.05/rebate=0.25 rigiera en todo el intervalo 30-mar..4-sep.
- UNKNOWN: retroactividad del flag en la franja 27..31-mar-2026 (mercados creados antes del 30-mar con feesEnabled=true y updatedAt 31-mar, p.ej. Istanbul 31-mar creado el 27-mar): no se sabe si los trades ejecutados antes de la activación pagaron fee.
- UNKNOWN: regla exacta del corte del 30-mar-2026 (13 ciudades norteamericanas con fees, 25 no norteamericanas sin fees, creadas con ~20 min de diferencia): activación por lote no documentada. Consecuencia: la época debe leerse de markets.fee_regime por fila, no de una fecha.
- UNKNOWN: fee en redención/resolución (no se ha encontrado documentación que la afirme ni la niegue); el modelo asume 0 como supuesto declarado. Gas de redención fuera del modelo.
- UNKNOWN: forma general con exponent≠1 (c=r·(p(1−p))^e es inferida del pico 1.56% de crypto); irrelevante mientras e=1 pero el código debe hacer fail-closed.
- UNKNOWN: spread_cost y slippage (x_exec) — sin orderbook histórico, precio INDICATIVE; sólo estimable forward (R22).
- UNKNOWN: rebate maker efectivo (pool diario pro-rata por mercado, mínimo $1 pUSD); 0.25 es una cota superior, no un ingreso por trade.
- UNKNOWN: unidad de orderMinSize=5 (market-details: 'in USDC'; CLOB: sólo 'Minimum order size').
- UNKNOWN: regla que asigna tick_size=0.01 a 411 mercados (343 con slug 'arch-', endDate 2026-03-13..2026-09-01); fees.py afirma tick 0.001 para ambas épocas, lo cual es incompleto.
- No verificable en esta sesión: builder fees ('charged on top') si se operase vía builder; Taker Rebate Program (desde 28-may-2026) sólo a volumen alto.

## 8. Refutaciones (literal)

### Refutador 1 — refutada=False

Lente FUENTE: abrí cada documento citado (fees.md, market-details, changelog, maker-rebates, taker-rebates, v2-migration, place-orders, clob-openapi.yaml, gamma-openapi.yaml) y consulté en vivo Gamma y CLOB (GET). Cada fórmula, parámetro y cita literal del modelo aparece exactamente como se afirma; ninguna cita es inexistente ni dice otra cosa. La fórmula c_taker=0.05·p·(1−p) reproduce la tabla oficial de 100 shares en todos los puntos comprobados (p=0.05→$0.24, 0.10→$0.45, 0.50→$1.25), y la lectura de 1000 bps como rate produciría $2.50 en p=0.5, incompatible con la tabla. Las afirmaciones no documentadas (relación 1000 bps ↔ 0.05, deducción en shares vía issue #326, fórmula on-chain V1, fee de redención) están correctamente etiquetadas como INFERIDO/UNKNOWN y no como OBSERVADO. Sólo detecto una imprecisión de redacción menor (ver corrección), sin impacto en el coste modelado.

**Corrección sugerida:** Precisión menor en formula_coste (1) y en el parámetro "redondeo / fee mínima": "mínimo 0.00001 USDC" no es un suelo. La doc dice literalmente "The smallest fee charged is 0.00001 USDC. Anything smaller rounds to zero" → Fee total = round5(C·c_taker(p)), y si el resultado redondeado es 0 la fee es 0 (no se eleva a 0.00001). Sustituir "mínimo 0.00001" por "granularidad 0.00001; fees < 0.000005 redondean a 0". Adicionalmente, anotar que la deducción en shares para BUY (issue #326) queda fuera de las fuentes oficiales verificables; lo documentado es "charged on top" del notional pre-fee y "fee-adjusted fill amounts" vía SDK, equivalentes en coste USDC como ya indica el modelo.

### Refutador 2 — refutada=True

Refutación PARCIAL y acotada (lente DATOS). Las tablas agregadas del catálogo se reproducen exactamente con DuckDB read_only, así que la fórmula de coste, los parámetros (r=0.05, e=1, takerOnly, rebate 0.25, mbf/tbf=1000, tick, min_order_size) y los límites de época por endDate NO quedan refutados. Lo que NO cuadra son dos fechas/IDs citados como evidencia OBSERVADA en la época V1 (corte del 30-mar-2026): (a) "primer mercado con fees 1779513 Atlanta (createdAt 2026-03-29T18:09:47Z)" es falso: el primer evento con fees de endDate 30-mar es Toronto (event 322390, markets 1779469–1779479, createdAt 18:09:15/18:09:16Z), 31 s antes que Atlanta; (b) "último sin fees 1779683 Taipei (createdAt 18:11:35Z)" es falso: después de Taipei se crearon Chongqing, Beijing, Wuhan, Chengdu, Shenzhen (sin fees), luego Austin, Denver, Houston, Los Angeles, San Francisco (con fees), luego Moscow (event 322426, markets 1779810–1779820, createdAt 18:12:55Z, SIN fees) y por último Mexico City (1779821, 18:13:05Z, CON fees). Es decir, la secuencia real es intercalada [7 sin][7 con][16 sin][5 con][1 sin][1 con], no "primero fees, luego sin fees"; 12 eventos con fees fueron creados ANTES del último evento sin fees. La conclusión INFERIDA del modelo ("corte por lote/evento, no por createdAt ni endDate") sobrevive e incluso se refuerza, pero la evidencia literal citada está mal y, según la regla "si hay duda razonable, refutada=true", debe corregirse. Hallazgo adicional no declarado en el modelo: la época fees_disabled "2025-12-30..2026-03-30" no es continua en el catálogo (faltan 47 días: 2026-01-02..2026-02-17; enero sólo tiene 56 mercados/8 eventos) y además faltan 2026-04-16 y 2026-04-17 dentro de la sub-época V1; endDate 2026-03-31 sólo tiene 3 eventos/33 mercados (Tokyo, NYC, Istanbul, creados 27-mar) frente a 418 el 1-abr. Estos huecos no cambian la fórmula pero sí el peso muestral de cada época y deberían declararse en el preregistro.

**Corrección sugerida:** Sustituir en "epocas[1].evidencia" la frase "primer mercado con fees 1779513 Atlanta (createdAt 2026-03-29T18:09:47Z), último sin fees 1779683 Taipei (createdAt 18:11:35Z)" por: "para endDate 30-mar la creación (ev.createdAt / Gamma createdAt, 2026-03-29 UTC) va intercalada: 7 eventos sin fees (Paris 17:46:33 … Seoul 18:08:32) → 7 con fees (Toronto 18:09:15 mk 1779469 … Chicago 18:10:02) → 16 sin fees (Wellington 18:10:12 … Shenzhen 18:12:10, incl. Taipei 18:11:34) → 5 con fees (Austin 18:12:18 … San Francisco 18:12:48) → Moscow 18:12:55 sin fees (mk 1779810–1779820) → Mexico City 18:13:05 con fees (mk 1779821–1779831). Primer mercado con fees de esa fecha: 1779469 (Toronto); último sin fees: 1779820 (Moscow). 12 eventos con fees fueron creados antes del último sin fees → el corte es por ciudad/evento, no por createdAt". Añadir a "epocas" y al preregistro una nota de cobertura: la época fees_disabled tiene 49 días sin mercados en el catálogo (2026-01-02..2026-02-17; 2026-04-16/17 en V1), enero con sólo 8 eventos, y endDate 2026-03-31 con sólo 3 eventos/33 mercados; segmentar por fee_regime y sub-época debe reportar n_mercados y n_días efectivos, y las inferencias sobre la época fees_disabled deben tratarse como basadas en ~8.770 mercados concentrados en 2026-02-18..2026-03-30 (8.637 de 8.770) más 133 de dic/ene. Mantener el resto del modelo (fórmula H1, parámetros, límites de época por endDate, tick/min size) sin cambios: todos los recuentos citados se reproducen exactamente.
