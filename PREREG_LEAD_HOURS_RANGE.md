# PREREG_LEAD_HOURS_RANGE — rango operativo de `lead_hours` (R8)

**Fecha:** 2026-09-06 · **Congelado antes de que `features`/`strategy` consuman leads > 24 h** ·
**Ancla:** `T = endDate − lead_hours·3600`, `endDate = target_date 12:00:00Z` (PHASE_2E_LEAD_HOURS_ANCHOR, D1 del ancla; **no** confundir con D1-COORD).

## 1. Hecho verificado (P1 cerrada)
`event_endDate` es `12:00:00Z` en **8 557 / 8 557** eventos de `CATALOG_V2.ev` (consulta read-only 2026-09-05).

## 2. Existencia del evento en T (`createdAt ≤ T`), `R8_LEAD_EXISTENCE.json`
```
lead_h    existe en T      %
   1        8501/8557    99.3
   6        8501/8557    99.3
   9        8501/8557    99.3
  12        8495/8557    99.3
  24        8402/8557    98.2
  36        6946/8557    81.2
  48        6775/8557    79.2
  60         954/8557    11.1
  72         890/8557    10.4
```
`endDate − createdAt`: p50 = 55,9 h; 20,8 % de eventos creados < 48 h antes de `endDate`; 155 < 24 h.

## 3. Regla congelada
- **Leads primarios: {9 h, 24 h}** (los de V2–V5; existencia ≥ 98,2 %). Un evento que no exista en T
  se **excluye** de ese lead (fail-closed), nunca se imputa.
- **Leads secundarios permitidos: {36 h, 48 h}** sólo con la exclusión explícita anterior y reportando
  la fracción excluida (~19–21 %) en cualquier métrica. No entran en la selección de modelo.
- **Leads > 48 h: NO OPERATIVOS** (≥ 89 % de mercados inexistentes en T; además `icon_seamless`
  cambia de componente hacia +45 h — nada de MODELSEL se transporta).
- **Lead < 9 h:** admisible operativamente (existencia 99,3 %) pero sin evidencia de MODELSEL; si se
  usa, hereda M1 sin garantía y debe evaluarse aparte.

## 4. Lo que esta regla NO decide
Qué lead usa Strategy A por defecto (decisión de 2D/2G con backtest), ni la latencia por modelo
(`L_max`, F-3), ni el `target_date` por día civil (`weather.target_day_window` de la sesión B).
