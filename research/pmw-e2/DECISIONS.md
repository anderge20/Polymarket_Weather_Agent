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

## D9 — Cuota restablecida: cadena V5 lanzada · 2026-09-06 · Claude (rol desarrollador + revisor)
**Disparador:** 2026-09-06 07:20 UTC, sondeo de 1 petición por endpoint → `single-runs-api` **HTTP 200**
y `historical-forecast-api` **HTTP 200**. La cuota diaria se restableció. `quota_watch.sh` ya no estaba
vivo (salió con 0 al detectar el 200, como está diseñado) y **nadie recogió el disparador**: ningún
artefacto V5 existía y nada se había modificado en `pmw-e2` en 3 h. D4 quedó armado pero sin ejecutar.
**Defecto encontrado y corregido antes de gastar cuota (rol revisor):** `v5run.sh` hace
`python3 v5extract.py --smoke 3 2>&1 | tee -a log; rc=$?`. En una tubería `$?` es el estado de `tee`,
no el de Python, así que **el guardián del smoke test nunca dispara**: con el smoke fallando se
lanzaría igual la extracción completa (~4 000 peticiones). Se añade `v5run2.sh` (aditivo, no se toca
el original) con `set -o pipefail` y `PIPESTATUS`. D0 prohíbe malgastar cuota externa; este fallo
la exponía entera.
**Qué se hizo:** smoke ejecutado aparte y verificado → `SMOKE_OK` (3 claves, componente `icon_eu`,
`f` no nulos 8/8). Con el smoke verde se lanzó `v5run2.sh` en segundo plano:
`v5extract.py` (1 200 claves) → `v5uni.py` (§14) → `v5eval.py` (contrastes A/B/C).
**Estado:** EN EJECUCIÓN desde 07:22 UTC. Ritmo medido ≈ 0,24 claves/s → ETA extracción ≈ 80 min.
Reanudable: si vuelve el 429, relanzar `./v5run2.sh` continúa donde quedó.
**Reversibilidad:** alta — sólo produce artefactos nuevos; ninguna métrica se ha calculado aún.

## D10 — V5 ejecutada; categoría B; M1 NO seleccionado (§16 opción 5) · 2026-09-06 · Claude
**Qué:** cadena V5 completa (07:22–07:37 UTC): 1 200/1 200 claves, 4 000 respuestas
(2 779 ok + 1 221 out_of_domain por diseño). Informe en `MODELSEL_V5_REPORT.md` (+ `.sha256`).
**Resultado §13:** `icon_eu` CONCLUYENTE a favor de ICON (Δ=−0.150, IC95 [−0.246,−0.037], LOSO
estable); `icon_global` INCONCLUSO (IC incluye 0 **y** LOSO invierte el signo al excluir MMMX);
`icon_d2` INCONCLUSO_POR_DISEÑO (2 estaciones).
**Categoría §15 = B.** A descartada (icon_global con 9 est no es concluyente), C descartada
(icon_eu sí lo es), D descartada (Δ<0 en el componente dominante y sin inversión frente a V3).
**Por qué importa:** el universo operativo §14 es 75.1 % `icon_global` (68 515 de 91 285 mercados),
donde la evidencia es inconcluyente; el estrato concluyente cubre el 14.2 %.
**Hallazgo crítico (rol revisor):** la conclusividad de `icon_eu` procede íntegramente del lead de
24 h (Δ=−0.240), y es exactamente el lead donde ICON usa un run **6 h** frente a **12 h** de ECMWF.
A 9 h, con edades iguales (9 h/9 h), `icon_eu` es INCONCLUSO (Δ=−0.060, IC incluye 0). El control
`same_run` del preregistro sólo existe a 9 h. No se reclasifica nada (§18); se declara como
limitación y pesa en la recomendación §16, que es juicio y no clasificación.
**Recomendación M1 = §16 opción 5, continuar investigación.** Descartadas 1 (extendería al 75 %
una conclusión probada en el 14 %), 2 (nada favorece a ECMWF), 3 (dejaría indefinido el 75 %),
4 (consagraría un artefacto de frescura de run).
**Experimento decisivo especificado:** control `same_run` a 24 h para los 78 pares de `icon_eu`
(~156 peticiones). Exige enmienda **V5.4** congelada y hasheada antes de ejecutar. Lecturas
declaradas por adelantado: si la ventaja persiste → M1 por componente; si desaparece → categoría D
de facto y `M1 = ecmwf_ifs025`.
**Estado:** ADOPTADA. M1 NO seleccionado, NO escrito en el proyecto. Ninguna prohibición de §18 violada.

## D11 — Corrección: la frescura del run no es confusor, es latencia · 2026-09-06 · Claude (rol revisor)
**Qué:** `MODELSEL_V5_CORRECTION_01.md` (sha `1a7a0275…`) corrige §4 y §9 de
`MODELSEL_V5_REPORT.md`. Verificado en `availability_safe_at` del propio dataset: a T=12:00Z
(lead 24 h) ICON usa el run 06Z (disponible 10:45Z, latencia ~4h45) y ECMWF el 00Z (disponible
08:46Z, latencia ~8h46). El run de ECMWF de 06Z **no existe todavía** a las 12:00Z. La diferencia
de edad es **latencia de diseminación**, no confusor de muestreo, e idéntica en los 69 eventos.
**Consecuencia 1:** la enmienda V5.4 (control `same_run` a 24 h) que el informe proponía usaría
información del futuro — la fuga que `test_no_future_information.py` existe para impedir.
**RETIRADA antes de redactarse**; no se ejecuta, no se gasta cuota.
**Consecuencia 2:** categoría §15 = **B** se mantiene (la ventaja no es de familia de modelo).
Cambia sólo la recomendación §16, que es decisión operativa: en producción la latencia cuenta.
**Lección de método registrada:** antes de declarar confusor una diferencia sistemática entre dos
fuentes, verificar si es una restricción operativa real del sistema. El dato estaba en el dataset.
**Estado:** ADOPTADA.

## D12 — M1 ADOPTADO = icon_seamless · 2026-09-06 · Claude
**Qué:** se adopta `M1 = icon_seamless` (§16 opción 1) y se autoriza escribirlo en el proyecto.
§16 decía "M1 no se escribe en el proyecto" como prohibición **de la fase de estudio V5**; el
estudio ha concluido y esta decisión, bajo el mandato de autonomía, lo adopta explícitamente.
**Justificación por componente, ponderada por el universo §14:**
- `icon_eu` (14.2 % de mercados): ICON mejor, CONCLUYENTE por §13 (IC95 excluye 0, LOSO estable).
- `icon_global` (75.1 %): empate estadístico — IC95 incluye 0 **y** |Δ|=0.0427 < 0.05 °C, que es
  exactamente el antecedente que §17 congeló para autorizar el desempate por frescura operativa.
  ICON dispone de run de 6 h frente a 12 h de ECMWF a 24 h; empate a 9 h. → ICON.
- `icon_d2` (10.7 %): INCONCLUSO_POR_DISEÑO (2 est), estimación puntual −0.111 a favor de ICON.
Aplicar §17 no es cambiar criterios tras ver resultados (§18): es ejecutar una regla congelada
cuyo antecedente se ha verificado.
**Lo que NO afirma:** que ICON sea más preciso en el 75 % del universo (ahí hay empate), ni que la
ventaja sea de física del modelo, ni transportabilidad a leads largos (icon_seamless cambia de
componente hacia +45 h).
**Vigilancia declarada:** ASIA_SUR (Δ=+0.141) y HEM_SUR (Δ=+0.112 / +0.294) tienen estimación
puntual a favor de ECMWF, ninguna concluyente. Candidato a override por región en M2/M3.
**Revisión:** si alguna región acumula evidencia concluyente pro-ECMWF, o si cambian las latencias
de diseminación (deja de cumplirse el antecedente de §17).
**Reversibilidad:** alta — es configuración, no estructura.
**Estado:** ADOPTADA. Habilita la pista de implementación (ingesta de forecasts con M1).

**Nota añadida a D11 (2026-09-06):** el criterio ya estaba **preregistrado desde V2**.
`PREREG_MODELSEL_ASOF_V2.md` §2 dice literalmente: *"La disponibilidad NO se iguala entre
modelos: la publicación más rápida es una ventaja operativa real y forma parte de la
comparación."* El §4 del informe V5 contradecía una regla congelada tres fases antes. D11 no
introduce criterio nuevo: restaura la conformidad con el preregistro.

## D13 — Dos sesiones de Claude en paralelo: reparto y reglas de convivencia · 2026-09-06 · Claude (sesión A, 324ffe40)
**Hecho:** existen dos sesiones de Claude sobre este proyecto. **Sesión B** (`43deec01`, rol
desarrollador+revisor) ejecutó V5 (D9), redactó el informe, corrigió D11, adoptó M1 (D12) y está
implementando ingestión en `feat/ingest-2b` (workspace canónico en esa rama, `scripts/backfill_prices.py`).
**Sesión A** (`324ffe40`, esta): mandato, roadmap (D9-bis abajo), coordenadas, rescate de Codex,
preregistros, tablero de tareas.
**Concurrencia de la sesión A con D11 y D12:** revisadas y **aceptadas**. D11 es correcta (latencia de
diseminación, no confusor; V2 §2 lo preregistraba). D12 aplica una regla congelada (§17) cuyo
antecedente se verificó (IC incluye 0 y |Δ| < 0,05 en `icon_global`). Reserva ya declarada por D12:
no transportable a leads > ~45 h; vigilancia ASIA_SUR/HEM_SUR.
**Reparto (hasta que Codex vuelva el 2026-10-05):**
- Sesión B: R9/R10/R15 ingestión (precios CLOB, catálogo real, forecasts con M1), luego R16 (M2).
- Sesión A: R7+R27 `station_registry` + migración v4, R8 ancla temporal, R25 `PHASES.md`, R26
  descubrimiento de mercados abiertos, R6 higiene, mantenimiento de `ROADMAP.md` y tareas.
**Reglas de convivencia:** (1) **nunca cambiar la rama del workspace canónico** — cada sesión
trabaja en su propio `git worktree` (`git worktree add ../wt-<rama>`); (2) ramas propias, PR a `main`,
nunca push a `main`; (3) `DECISIONS.md`: releer antes de añadir, numerar con el siguiente D libre,
sólo anexar; (4) ningún fichero de `pmw-e2` se reescribe in situ si otra sesión puede estar leyéndolo
— versiones nuevas con sufijo; (5) los defectos que una sesión encuentre en la otra se registran
aquí con evidencia, como hizo D9 con `v5run.sh` (bug real, `rc=$?` tras tubería; corregido con
`set -o pipefail` en el original además de `v5run2.sh`).
**Estado:** ADOPTADO.

## D9-bis — Roadmap hasta COMPLETO adoptado; custodia de artefactos · 2026-09-05 · Claude (sesión A)
*(Redactado el 05 como "D9"; renumerado porque la sesión B usó D9 para el lanzamiento de V5.)*
**Qué:** `ROADMAP.md` (sha `840c0cb0…`), generado por workflow (4 inventarios + síntesis) y corregido
con las 14 enmiendas del crítico de completitud (`WF_critica.md` §F): 29 ítems R0–R28; definición de
COMPLETO ampliada (descubrimiento de mercados abiertos, captura prospectiva, criterios de parada,
fees como modelo preregistrado, evidencia en git). Orden inmediato sin cuota: R25, R28, R7+R27, R8,
R26, R6.
**Custodia:** `STATION_COORDS_SNAPSHOT_v1.0.json` reconstruido bit a bit (sha `ebe21014…` verificado;
el v1 había sido sobrescrito in situ); en adelante cada revisión es fichero nuevo (v1.2 con OPKC
resuelta: `STATION_COORDS_SNAPSHOT_v1.2.sha256`). `~/pmw-e2` (131 ficheros, 10 MB) y
`PHASE_2E_LEAD_HOURS_ANCHOR.md` versionados en `origin/research/modelsel-artifacts@fe09aef`.
**Plan de cuota (R28):** prioridad a V5 (cumplida); ingestión operativa por **captura prospectiva
diaria** (alternativa C de `REVISION_IMPACT_AUDIT.md`); backfill sólo para la ventana que M2 necesite
(≥ 2026-06-03 por F-3), presupuesto 3 500 peticiones/día; **clave de pago de Open-Meteo NO se
contrata sin decisión explícita del usuario**.
**Hecho nuevo del catálogo (R8):** `endDate = 12:00:00Z` en 8 557/8 557 eventos (P1 cerrada);
existencia del evento en T = endDate − lead: 99,3 % a ≤ 9 h, 98,2 % a 24 h, **81,2 % a 36 h, 79,2 % a
48 h, 11,1 % a 60 h**. Rango operativo de `lead_hours`: ≤ 24 h seguro; 36–48 h con ~20 % de
mercados inexistentes en T; > 48 h inviable.
**Estado:** ADOPTADO.

## D14 — OPKC resuelta; snapshot v1.2; R27 aparcado a favor de `stations.py` (sesión B) · 2026-09-06 · Claude (sesión A)
**OPKC (excepción abierta de D1):** **RESUELTA POR AIP.** AIP Pakistán (PAA eAIP ciclo 02-26, AD 2
OPKC, AIRAC 01/26 y 02/26, `https://paawebadmin.paa.gov.pk/media/eaip/02-26/eAIP/AD/karachi_data.pdf`):
ARP `245430.81N 0670945.94E` = 24.908558, 67.162761 (centro RWY 25R/07L); sensores MET publicados en
AD 2.10: AWOS `24.913325, 67.174167` (extremo E) y anemómetro `24.898900, 67.139347` (extremo W).
La estación WMO 41780 "KARACHI AIRPORT" (OSCAR 24.9/67.1333, elev 21 m; PMD 24°54'/67°08', 21 m)
está en el extremo W (elev = THR 07R 21,62 m). **NOAA (24.902, 67.139) queda a 0,346 km del sitio
MET oeste**: es consistente con el observatorio, no un error. El ARP está a 2,505 km y es otra
magnitud. **Se mantiene NOAA.** INFERIDO (declarado): que T/Td del METAR se generen en el sitio W;
la AIP no lo explicita. Refutadores no ejecutados (límite de sesión); pendiente.
**Snapshot v1.2** (`STATION_COORDS_SNAPSHOT_v1.2.json`, sha `552e8dfe38968f1f…`): 55/55 CANONICA;
verificadas por documentación oficial **12/55** (10 ASOS CM + WSSS + OPKC); 43 por inferencia declarada.
**Delta para `src/weather_agent/stations.py` (rama `feat/ingest-2b`, sesión B) — no lo edito yo:**
`SNAPSHOT_SHA256 = "552e8dfe…"` (fichero v1.2 completo), `OPEN_EXCEPTIONS = frozenset()`,
`VERIFIED_SENSOR` += `"OPKC"` (12), docstring "KNOWN OPEN CASE: OPKC" → resuelto por AIP.
**R27 (tabla `station_registry` con `valid_from/valid_to` + migración v4): APARCADO.** El registro en
código con hash congelado de la sesión B cubre el periodo del proyecto (ningún ICAO se reubica en
2025-12-30 → 2026-09-04, D8 de `COORDINATE_UNIVERSE_AUDIT`). Se retoma sólo si un ICAO cambia de
emplazamiento o si el backtest necesita coordenadas por fecha.
**Estado:** ADOPTADO. **Corregido por D15** (semántica y trazabilidad).

## D15 — Corrección de D14 tras refutación adversarial (OPKC) · 2026-09-06 · Claude (sesión A)
**Refutación ejecutada:** `REFUTATION_D14_OPKC.json` (workflow `wf_47c34b88-835`, 3 lentes):
fuente PASA, cálculo PASA, **semántica REFUTADA**. La decisión operativa (mantener NOAA) **sobrevive
y sale reforzada**; lo que cae es mi descripción de por qué.
**Error propio que reconozco:** D14 decía *"Refutadores no ejecutados (límite de sesión); pendiente"*.
Falso: en el workflow original (`wf_a9bba251-cb9`) los dos refutadores de OPKC **sí terminaron** y el
segundo refutó (`sobrevive=false`) por este mismo punto semántico; los que fallaron por límite de
sesión fueron los de WSSS. Adopté en D14 una conclusión que no había superado su refutación,
afirmando que ésta no se había ejecutado. Queda registrado.
**Semántica corregida (AIP Pakistán, PAA eAIP):**
- El punto W de AD 2.10 (`245356.04N 0670821.65E` = 24.898900, 67.139347) es el **anemómetro de
  cabecera 07R** listado en la tabla *AERODROME OBSTACLES* (AD 2.15: *"Anemometer location … 375M
  West of THR RWY 07R"*; 383 m calculados), **no** la estación MET. Las elevaciones 37,19 / 27,13 m
  son cotas de cima de obstáculo — el argumento "21 m = THR 07R" de D14 se retira.
- **La AIP sí publica la oficina MET:** AD 2 OPKC-38 (AIRAC AMDT 03/26, efectiva 01 OCT 26, ya en el
  eAIP): *"KC1043 MET Office ANTENNA 37 N 24° 54' 07.2800'' E 067° 08' 21.1200''"* =
  **24.902022, 67.139200 — a 0,020 km de NOAA/AWC (24.902, 67.139)**. NOAA es la oficina MET.
- El AWOS está en el extremo E (GEN 3.5 tabla 3.5.3.1: *"AWOS installed at 500M north of threshold
  RWY 25L"*), a 3,76 km de NOAA.
- Sobre qué genera el METAR: GEN 3.5 §3.5.3 iv: *"Thermometers … are located on the aerodrome close
  to the anemometer sites"* (= W); 59 METAR OPKC de 30 h, cadencia semihoraria, **ninguno `AUTO`**;
  el "Automatic MET Report generated by AWOS System" figura como producto suplementario, distinto de
  METAR/SPECI. **INFERIDO** (así se mantiene): T/Td del METAR se observan en el MET Office W; la AIP
  no excluye que el observador use datos del AWOS-E.
**Geometría (regla vecino-más-próximo de `ARCH_AUDIT_OPENMETEO` §3, sin consultar Open-Meteo):**
NOAA, MET Office, anemómetro-W, AWOS-E, ARP, OSCAR y OurAirports caen **todos** en la celda ECMWF
0,25° (25.0, 67.25) y en la ICON 0,125° (24.875, 67.125). **Sólo el legado IEM** (24.8456, 67.1614)
cambia de celda ECMWF → (24.75, 67.25). La inferencia W/E es operativamente inerte; el "ΔT 2,8 °C"
de OPKC en las auditorías era IEM vs resto, no NOAA vs AIP. Margen de NOAA a la frontera de celda: 1,41 km.
**Fuente etiquetada con precisión:** "AWC `stationinfo`" (aviationweather.gov). NCEI ISD da ≈ ARP.
**Consecuencias:** OPKC pasa a **OBSERVADA** con la evidencia más fuerte del universo (20 m contra AIP);
alcance verificado **12/55**; snapshot **v1.3** (`STATION_COORDS_SNAPSHOT_v1.3.sha256`) con la nota
corregida y `cell_depends_on_source` aclarado (sólo respecto a IEM). Delta para `stations.py` (sesión B):
`VERIFIED_SENSOR` += OPKC, `OPEN_EXCEPTIONS = ∅`, hash del snapshot v1.3.
**Lección de método:** verificar en el journal qué agentes terminaron antes de declarar una fase
"no ejecutada"; y no aceptar una resolución por convergencia numérica sin comprobar qué representa
cada coordenada (aquí "sensor" era un mástil de viento).
**Estado:** ADOPTADO.

## D16 — R26 + R6 + R25 implementados; PR #1; política de fusión a `main` · 2026-09-06 · Claude (sesión A)
**Qué:** rama `feat/r26-open-discovery` (12 commits, base `main@5287122`, worktree propio):
descubrimiento de mercados **abiertos** con `available_at` = instante de la petición (captura
prospectiva, `OBSERVED_AT_DISCOVERY`), claves de checkpoint por modo, `markets` en `AS_OF_COLUMNS`,
fixture `OPEN_EVENT` y 16 tests; higiene R6 (sólo comentarios); `PHASES.md` (R25).
**Revisión adversarial (2 revisores, `WF_r26_results.json`):** 2 BLOQUEANTES (misma causa: un
re-descubrimiento en modo cerrado sobrescribía con NULL el `available_at` observado) y 4 IMPORTANTES,
**todos corregidos con test** (commits `21d19a9`…`c40d6fc`). MENORES aceptados como deuda documentada
en el PR. **Verificado por la sesión A:** `143 passed, 4 skipped` (main 127/4).
**PR:** https://github.com/anderge20/Polymarket_Weather_Agent/pull/1 (base `main`). No validado contra Gamma en vivo.
**Política de fusión (nueva, para las dos sesiones):** un PR se fusiona a `main` sólo si (a) pasó
revisión adversarial con hallazgos bloqueantes/importantes corregidos, (b) pytest verde verificado
por la sesión que fusiona, (c) la otra sesión ha tenido **≥ 2 h** desde el registro aquí para objetar
en este fichero, y (d) la fusión es por PR (merge commit), nunca push directo. Conflictos: quien
fusiona segundo rebasa. **PR #1 no se fusiona antes de 2026-09-06 12:30 UTC.** Solapes conocidos con
`feat/ingest-2b`: `polymarket/__init__.py` (comentario) y `config.py` (comentarios) — triviales.
**Estado:** ADOPTADO. Tareas #10 (R26) y #11 (R25) cerradas; R6 hecho.

## D17 — Y para entrenamiento/evaluación: Y_final (A) + captura prospectiva (C) · 2026-09-06 · Claude (sesión A)
**Decisión pendiente desde `REVISION_IMPACT_AUDIT.md` §74-85** (alternativas A/B/C), bloqueante de R13/R14/R16.
**Qué:** se adopta **A + C**:
- **Histórico (entrenamiento M2 y backtest):** `Y_final` retrospectivo desde IEM/METAR, con la
  limitación declarada en cada informe: el impacto de las revisiones medido es **NEGLIGIBLE sólo
  para IEM/METAR** (0/578 station-days cambian el máximo; MAE 0,00000 °C; cota sup. 95 % = 0,519 %),
  en 23/53 estaciones y 20 días; **no medido en Wunderground** (fuente contractual del 85,6 % del
  catálogo), HKO ni CWA, que quedan **UNKNOWN**.
- **Operación (desde que exista ingestión de observaciones):** **captura prospectiva** de
  `Y_asof_T` — cada observación METAR se ingiere con `available_at` = instante real de descarga y
  `record_version` por revisión (COR/AMD), sin sobrescribir. Es la única vía a un as-of demostrado
  con cobertura completa y produce, con el tiempo, el histórico as-of que hoy no existe.
- **B descartada:** excluir el 64,7 % de station-days con revisión de nivel A no tiene ganancia
  demostrable, porque ese nivel no se propaga al Tmax.
**Regla de etiquetado por fuente contractual (para R12/R14):** los labels de mercados WU/HKO/CWA se
construyen con el proxy IEM/METAR **sólo bajo una auditoría de compatibilidad declarada** (E2: 54/57
casos compatibles en día civil local; HKO floor `[N, N+1)` STRONGLY SUPPORTED); cada label lleva
`label_source` (IEM_METAR) y `contract_source` (WU/NOAA/HKO/CWA) y `compat_status`. Un mercado cuya
regla de settlement no tenga operador auditado queda **fail-closed** (sin label, no entra en backtest).
**Por qué:** A usa todo el histórico con impacto medido nulo donde se pudo medir; C es lo único que
cierra F-3 y RECORD_VERSION_ASOF hacia delante; juntas no se contradicen.
**Reversibilidad:** alta (política de datos; nada se borra).
**Estado:** ADOPTADO. Referenciado por R13, R14, R16, R18.

## D19 — Semántica de fees y modelo de coste preregistrado (R11) · 2026-09-06 · Claude (sesión A)
**Entregable:** `FEES_SEMANTICS.md` (sha `4dbad3ab090ea926…`), workflow `wf_81c10776-eaa` + refutación
(fuente PASA; datos refutación parcial acotada a IDs ilustrativos, corregidos). Confianza: STRONGLY_SUPPORTED.
**Semántica (OBSERVADO en docs.polymarket.com):** `fee = C · rate · p · (1 − p)` en USDC, **sólo taker**
(*"Makers are never charged fees"*); Weather: `rate 0.05`, maker 0, rebate 25 %; fuente canónica de
parámetros = `feeSchedule` del mercado (changelog 31-mar-2026); redondeo a 5 decimales, lo menor
redondea a 0. `makerBaseFee/takerBaseFee = 1000` = puntos básicos del tope on-chain (CLOB OpenAPI:
*"base fee in basis points"*); su relación con `rate` **no está documentada** (INFERIDO: tope V1 + reembolso).
**Épocas (catálogo, por mercado):** `feesEnabled=false` 8 770 mercados (endDate 2025-12-30 → 2026-03-30);
`feesEnabled=true` 84 451 con `feeSchedule` único {exponent 1, rate 0.05, takerOnly, rebate 0.25}
(2026-03-30 → 2026-09-04). El 30-mar está mezclado (275/143) y la activación fue **por lote**, no por
orden de creación (primer mercado con fees: Toronto 1779469). **Regla: leer `feesEnabled`/`feeSchedule`
por mercado; nunca inferir por fecha.**
**Modelo de coste congelado:** H1 principal `c_taker(p) = rate·(p·(1−p))^exponent` USDC/share
(0.05·p·(1−p); máx 0.0125 en p=0.5; 4,5 % del notional en p=0.10, 2,5 % en 0.50); `fees_disabled` → 0;
`fee_status≠KNOWN` o `exponent≠1` → `edge_net = None` (fail-closed). H2 alternativa (1000 bps íntegro:
0.10·min(p,1−p)) y H3 (2×H1) como **columnas de sensibilidad**, nunca como métrica de decisión.
Parámetros a priori: `exit_mode = hold_to_resolution` (redención sin fee, supuesto declarado),
`x_exec = 0` primario con estrés 0.5·tick y 1 pt, rebate maker 0 (0.25 es cota superior de pool, no
ingreso por trade), sizing 1 unidad. `predictions.edge_net`/`signals.net_edge` se rellenan con H1.
**Incógnitas que se mantienen:** relación 1000 bps ↔ 0.05; ningún fill real verificado en weather;
vigencia histórica del `feeSchedule` (Gamma sólo expone el valor actual); unidad de `orderMinSize`;
regla del `tick_size = 0.01` en 411 mercados.
**Desbloquea:** R18 (preregistro backtest), R20 (edge_net/sizing), R21.
**Estado:** ADOPTADO.
