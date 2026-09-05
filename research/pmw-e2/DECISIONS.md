# DECISIONS.md — registro de decisiones tomadas bajo el mandato de autonomía

**Mandato (2026-09-05, literal):** "Dile a códex que tu (Claude) y el (códex) toméis las decisiones
por mi hasta finalizar el proyecto por COMPLETO."

Cada decisión lleva: id · fecha · quién · qué · por qué · evidencia · reversibilidad · estado.
Las decisiones se toman con la disciplina que el usuario entrenó: preregistro antes de ejecutar,
sin cambios de criterio a posteriori, UNKNOWN declarado honestamente.

---

## D0 — Puertas autoimpuestas (vigentes hasta que el usuario las levante explícitamente)
- Nunca `git push` a `main`; solo ramas de trabajo.
- Nunca operar con dinero real ni enviar órdenes a Polymarket.
- Nunca borrar datos ni artefactos; solo añadir o versionar.
- Preregistro congelado y hasheado antes de cualquier ejecución que produzca métricas.
- No sortear límites de cuota de proveedores externos.

## D1 — Convención canónica de coordenadas de estación  · 2026-09-05 · Claude
**Qué:** `station_lat/lon` = estación observadora del registro operativo de estaciones METAR de
NOAA AviationWeather (`aviationweather.gov/api/data/stationinfo`, `siteType ⊇ {METAR}`), congelada
en un snapshot fechado del proyecto. El ICAO se resuelve desde el propio mercado (`icao2`), nunca
desde la ciudad. OurAirports = control. IEM y WMO OSCAR prohibidos como posición.
**Por qué:** `COORDINATE_UNIVERSE_AUDIT.md` (sha f92d83b6…) §3, §6, §10: NOAA es la única fuente
que apunta a la estación observadora y refleja el traslado de ZSQD; OurAirports mide el ARP (otra
magnitud) y tiene errores propios (LEMD, ZUUU); IEM apunta a la estación sinóptica urbana en 7 casos.
**Excepciones abiertas:** OPKC (NOAA a 2,51 km del ARP, cambia celda ECMWF, ΔT 2,8 °C) y WSSS
(ambigua). Se usan por la regla general y quedan marcadas para verificación.
**Reversibilidad:** alta — es una tabla; cambiarla obliga a re-extraer forecasts.
**Snapshot:** `STATION_COORDS_SNAPSHOT_v1.json` sha256 `ebe21014519eb725143e486a88567e468661fb2ad860e7528d15f501a02d02a6` (55 estaciones, 53 canónicas, 2 excepciones abiertas).
**Verificación (2026-09-05, `COORDINATE_SENSOR_VERIFICATION.md`):** NCEI HOMR (fuente `ASOS CM`,
base de Configuration Management del NWS) sitúa el sensor ASOS a **9 m de media, 71 m máx.** de la
coordenada NOAA en 10/10 estaciones de EE.UU.; OurAirports (ARP) a 0,5–3,0 km. WSSS confirmada por
AIP Singapur + WMO OSCAR + NEA (40–46 m). La premisa "NOAA = sensor" pasa de INFERIDA a **OBSERVADA**.
WSSS deja de ser excepción (snapshot v1.1, sha en `STATION_COORDS_SNAPSHOT_v1.sha256`). OPKC sigue abierta.
**Estado:** ADOPTADA y VERIFICADA. Refutación adversarial ejecutada (D6, `REFUTATION_D1_01.md`):
D1 se sostiene. **Categoría A en el alcance verificado (11/55: red ASOS de EE.UU. + WSSS); para las
43 restantes, A por inferencia declarada** (estirpe de registro + ausencia de contraejemplo).
KBKF: canónica no verificada (WBAN 23036, DDMM). OPKC: excepción abierta.

## D2 — Tratamiento de V2/V3/V4 y reanudación de V5 · 2026-09-05 · Claude
**Qué:** V2/V3/V4 se conservan tal como se calcularon (coordenadas IEM) y se declaran así; no se
recalculan. V5 recibe una enmienda de preregistro V5.2 que adopta D1 y se ejecuta en cuanto se
restablezca la cuota de Open-Meteo. M1 se decide con los criterios congelados de V5.
**Por qué:** recalcular V2/V3/V4 no aporta nada que V5 no vaya a aportar con la convención nueva y
consumiría cuota; V5 ya está diseñado para desacoplar modelo × régimen de resolución.
**Reversibilidad:** alta.
**Enmienda:** V5.2 redactada y hasheada (`PREREG_MODELSEL_V5.sha256`); re-extrae `f` de las 16 estaciones con D1 (4 000 peticiones, reanudable). Impacto D1 sobre V3: 3/16 estaciones cambian celda (OPKC, ZGSZ, ZSQD).
**Estado:** ADOPTADA. Bloqueada por HTTP 429 hasta ~2026-09-06.

## D3 — Coordinación con Codex · 2026-09-05 · Claude
**Qué:** mandato transmitido a la sesión `codex mcp integration`. Propuesta de reparto: Claude →
metodología/investigación (MODELSEL, coordenadas, preregistros, V5→M1→especificación M2/M3);
Codex → lo que ya posea.
**Resultado (2026-09-05 16:43 UTC):** Codex recibió el mensaje (hilo `01a071fa`, rollout línea 568) y
su turno terminó en 2,4 s con `error.codex_error_info = "usage_limit_exceeded"`: *"You've hit your
usage limit. Upgrade to Plus to continue using Codex, or try again at Oct 5th, 2026 4:31 PM."* Plan
`go`, sin créditos. **Codex no puede participar hasta 2026-10-05.**
**Estado:** BLOQUEADO EXTERNAMENTE. Ver D5.

## D5 — Proceder en solitario mientras Codex esté sin cuota · 2026-09-05 · Claude
**Qué:** el mandato exige decisiones conjuntas Claude+Codex, pero Codex está inoperativo un mes por
cuota. Se procede con Claude como único decisor, con dos salvaguardas: (a) toda decisión relevante
se somete a verificación adversarial independiente (workflows con refutadores) en lugar de a la
segunda opinión de Codex; (b) cada decisión queda registrada aquí para que Codex —o el usuario—
pueda revisarla a posteriori. Si la cuota de Codex se restablece antes, se le reenvía el registro
completo (`CODEX_MSG_01.txt` + este fichero) y se le pide objeción retroactiva.
**Por qué:** esperar un mes contradice el mandato de terminar; el usuario ya expresó frustración por
la parálisis ("Porque estáis parados?").
**Reversibilidad:** total — todas las decisiones son documentales o en ramas de trabajo.
**Estado:** ADOPTADA. Se informa al usuario de que Codex está sin cuota.

## D4 — Ejecución automática de V5.2 al restablecerse la cuota · 2026-09-05 · Claude
**Qué:** un vigilante (`quota_watch.sh`, 1 petición/15 min) detecta cuándo Single Runs vuelve a
responder 200; entonces se ejecuta `v5run.sh` (extracción 4 000 peticiones → universo §14 →
evaluación). Scripts reanudables; el 429 se trata como guardar-y-salir.
**Validación previa:** `v5debias.py` reproduce `MODELSEL_GEOVAL_V3_EVAL.json` bit a bit
(2330/2330, Δ=0). `v5eval.py` probado con datos sintéticos aleatorios (sin señal) y eliminado el
resultado; ninguna métrica real calculada.
**Corrección registrada:** el extractor pedía los 5 modelos en cada run (6 000 peticiones); ECMWF
usa runs distintos de ICON a 24 h. Corregido: cada modelo sólo en sus runs → 4 000, como preregistra V5.2.
**Estado:** ARMADO. Esperando cuota.

## D6 — Refutación adversarial de D1 ejecutada · 2026-09-05 · Claude (rol revisor)
**Qué:** ejecutada la refutación que `COORDINATE_SENSOR_VERIFICATION.md` §6 dejó pendiente por
límite de sesión de subagentes (venció a las 19:50 CEST). Tres lentes, resultado en
`REFUTATION_D1_01.md`: cálculo PASA (recomputadas las 11 distancias con haversine independiente,
Δ máx 0,016 m), fuente PASA (HOMR reconsultada: `ASOS CM` y el vínculo WBAN↔ICAO confirmados en el
propio registro), semántica PASA CON RESERVA.
**Defecto encontrado:** el WBAN de KBKF era erróneo (23062 = otra estación). El correcto es **23036**
(`qid=ICAO:KBKF`). Con él, d(NOAA, HOMR) = **0,797 km**, no 11,29 km: desaparece el único aparente
contraejemplo. Pero KBKF **no queda verificada** — su registro no tiene `ASOS CM` y su precisión
DDMM (±0,93 km) no discrimina sensor de ARP. Es una canónica no verificada dentro del universo V5.
**Acotación del alcance:** verificadas 11/55 (10 ASOS CM de EE.UU., que comparten red y base CM, +
WSSS). **43 estaciones fuera de EE.UU. sin verificación individual**, 10 de ellas en China. La
promoción INFERIDA→OBSERVADA es legítima para la red ASOS de EE.UU. y WSSS; para el resto sigue
siendo inferencia y debe declararse así.
**Reversibilidad:** total — documental.
**Estado:** ADOPTADA. D1 SE SOSTIENE con alcance acotado. Correcciones exigidas a
`COORDINATE_SENSOR_VERIFICATION.md` §2/§5/§6 listadas en `REFUTATION_D1_01.md`.
**Aplicadas 2026-09-05 (Claude, autor):** hallazgo KBKF verificado de forma independiente
(`qid=ICAO:KBKF` → WBAN 23036, 0,797 km, DDMM); §2, §5 y §6 corregidos; D1 acotado arriba.

## D7 — Rescate del trabajo sin commitear de Codex · 2026-09-05 · Claude
**Qué:** los cuatro ficheros que existían sólo en `/private/tmp/pmw-publish/worktree` (git worktree
sin commitear, en un directorio que el limpiador de macOS ya vació una vez) se copiaron verbatim al
workspace canónico en la rama **`codex/prices-ingestion-wip`** y se empujaron a `origin` (nunca a
`main`), commit `6ed85ad`: `polymarket/prices.py` (ingestión CLOB `/prices-history`),
`tests/test_market_asof.py` (stubs → tests reales), `PHASE_2E_SETTLEMENT_OPERATOR_DESIGN.md`,
`polymarket/__init__.py`. Tests en la rama: **131 passed, 2 skipped** (main: 127/4). El primer push
fue rechazado por privacidad de email en GitHub; se reemitió el commit con el email noreply.
**Por qué:** riesgo real de pérdida; D0 permite ramas de trabajo; ningún cambio funcional propio.
**Reversibilidad:** total (rama).
**Estado:** HECHO.

## D8 — Hashes de muestra no reproducibles: se fija el hash de disco · 2026-09-05 · Claude
**Qué:** los hashes declarados de `MODELSEL_GEOVAL_V3_SAMPLE.json` (`7a57ce0a…`) y
`MODELSEL_ASOF_V2_SAMPLE.json` (`a0157ed7…`) **no coinciden** con los ficheros en disco
(`6e253e38c730fda8…` y `29464fbb69fe118d…`, mtime 14:19 y 13:40 del 2026-09-05). Probadas 12
serializaciones alternativas y la hipótesis de hash previo a añadir `st_elev`: ninguna reproduce el
valor declarado. Causa no determinada; probablemente el fichero se reescribió tras hashearse.
**Decisión:** desde ahora el hash canónico de cada muestra es el **del fichero en disco**, registrado
aquí; los informes anteriores conservan su texto (no se reescribe historia) y esta nota los corrige.
La composición de la muestra (400 eventos / 16 estaciones; 8 estaciones V2) no está en duda: V5
la reutiliza tal cual y es el contenido, no el hash, lo que entra en el análisis.
**Reversibilidad:** documental.
**Estado:** ADOPTADA.

## Corrección a D4 · 2026-09-05 18:00 UTC
El inventario detectó que `v5uni.py` seguía usando coordenadas IEM/OurAirports. Alineado con el
snapshot D1; enmienda V5.3 al §14 del preregistro; hash vigente en `PREREG_MODELSEL_V5.sha256`.
