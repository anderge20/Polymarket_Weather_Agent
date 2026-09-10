# MODELSEL V5 — ESTADO DE EJECUCIÓN

**Actualizado:** 2026-09-05 (tarde) · **Preregistro vigente:** V5.3 — `PREREG_MODELSEL_V5.sha256`
(`e8302dc169e99b3aee44ff0b5570ad730139cd7c39b2006784a89f7789cb6264`); versiones anteriores v1
`ed062a1d…`, v1.1 `8777577c…`, v1.2 `260481c2…` apiladas en el mismo fichero (no se reescribe historia).
**Estado:** preregistro CONGELADO · extracción **NO iniciada** (HTTP 429) · contrastes **NO
calculados** · M1 **NO seleccionado**.

## Diseño vigente (V5.2 + V5.3)
- Muestra: la de V3 (400 eventos, 16 estaciones, mismos `run`, mismos `Y_final`). Hash canónico de
  disco de la muestra: `6e253e38c730fda8…` (ver D8: el hash declarado `7a57ce0a…` no es reproducible).
- Coordenadas: `STATION_COORDS_SNAPSHOT_v1.json` **v1.1** (`071b142c…`); v1.0 restaurada (`ebe21014…`).
- Re-extracción de `f` con Single Runs API, mismo `run` que V3: ICON (seamless + d2 + eu + global) en
  los 800 runs de ICON, ECMWF en sus 800 runs → **4 000 peticiones** (`v5extract.py`, reanudable).
- Identificación de componente sobre la ventana `W(m)` que produce `f` (regla V5.1 §4 bis).
- Universo §14 con el snapshot (`v5uni.py`, ~440 peticiones).
- Desbiasing `v5debias.py` = convención V2/V3 reproducida bit a bit (2330/2330, Δ=0).
- Evaluación `v5eval.py` (contrastes A/B/C, leads, regiones, LOSO, same-run, régimen, sensibilidad
  OPKC pre-declarada, categorías §15, opciones §16). Probado con datos sintéticos; resultado eliminado.

## Ejecución
```
cd /Users/mariaaleu/pmw-e2 && ./v5run.sh
```
1. `v5extract.py --smoke 3` (≈15 peticiones): aborta si la identificación o `f` fallan.
2. `v5extract.py` completa → 3. `v5uni.py` → 4. `v5eval.py`.
El 429 se trata como guardar-y-salir; relanzar el mismo comando continúa donde quedó.
Vigilante: `quota_watch.sh` (1 petición/15 min) — la sesión lanza `v5run.sh` al ver `CUOTA_RESTABLECIDA`.

## Bloqueos
- Open-Meteo `single-runs-api` / `historical-forecast-api`: HTTP 429 desde 2026-09-05 ~15:40 UTC.
- Codex: sin cuota hasta 2026-10-05 (D3/D5). Claude decide en solitario con refutación adversarial.

## Artefactos que existirán al terminar
`V5_EXTRACT.json` → `V5_DATASET.json` → `V5_EVAL.json` → `MODELSEL_V5_REPORT.md` (+ `.sha256`).
Ninguno existe hoy.
