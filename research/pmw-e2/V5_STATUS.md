# MODELSEL V5 — ESTADO DE EJECUCIÓN (BLOQUEADO POR CUOTA EXTERNA)

**Fecha:** 2026-09-05
**Estado:** preregistro CONGELADO · identificación de componente **INCOMPLETA** ·
contrastes A/B/C **NO CALCULADOS** · M1 **NO SELECCIONADO**

---

## 1. QUÉ ESTÁ TERMINADO

| Artefacto | Estado | Hash / n |
|---|---|---|
| `PREREG_MODELSEL_V5.md` (v1) | congelado | `ed062a1d9c676aaee79847fc19b9ff9fadf78b14728cbfacd8d26b6258dcdb24` |
| `PREREG_MODELSEL_V5.md` (v1.1, enmendado) | congelado | `8777577ca418ba8851161c6d6f303ca74c7de22c21da7f471e3dce23dbf8ed61` |
| `MODELSEL_GEOVAL_V3_SAMPLE.json` (muestra reutilizada) | sin cambios | `7a57ce0a040a237bae8db0e518f0194d22efc41a5a993b81df3525eb5a53e2ae` |
| `V5_UNIVERSE_STATIONS.json` | completo | 55 estaciones resolubles / 91 285 mercados |
| `v5comp.py`, `v5uni.py`, `v5eval.py`, `v5run.sh` | listos y reanudables | — |

## 2. QUÉ ESTÁ BLOQUEADO

```
single-runs-api        HTTP 429 {"reason":"Daily API request limit exceeded. Please try again tomorrow."}
historical-forecast    HTTP 429 (misma cuota compartida)
api.open-meteo.com     DISPONIBLE (cuota distinta, pero NO sirve: V2/V3 usan Single Runs)
```

La identificación de componente **exige** Single Runs API con el parámetro `run` idéntico
al que usó V3. No existe sustituto: usar otro endpoint cambiaría la extracción y violaría
el preregistro (§18: "no introducir ninguna transformación ajena a la extracción operacional").

**Trabajo pendiente:** 800 pares `(estación, run)` × 4 modelos = **3 200 peticiones**,
más ~440 para el universo operativo (§14).

## 3. CAUSA DEL AGOTAMIENTO — RESPONSABILIDAD

La cuota se consumió en tres bloques, el segundo de los cuales fue **desperdicio atribuible
a un error mío**:

| Bloque | Peticiones aprox. | ¿Útil? |
|---|---|---|
| Auditoría arquitectónica (§2–§6) | ~250 | SÍ — produjo `ARCH_AUDIT_OPENMETEO.md` |
| **Identificación con la regla §4 defectuosa (abandonada a 350/800)** | **~1 400** | **NO — descartado íntegro** |
| Universo operativo con la regla defectuosa | ~440 | NO — descartado |
| Reejecución con la regla corregida | ~150 antes del 429 | parcial, no guardada |

La regla §4 original exigía coincidencia sobre las 168 horas de la serie. Esa regla es
mecánicamente incapaz de identificar `icon_d2`, porque `icon_seamless` **cambia de
componente a lo largo del horizonte temporal** (reproduce D2 hasta ~+45 h y después
transiciona). Detecté el defecto sólo después de ejecutar ~1 400 peticiones con ella.

Una prueba de validación sobre 2 o 3 pares antes de lanzar las 800 habría revelado el
defecto a coste casi nulo. No la hice.

## 4. NO HAY ARTEFACTO CORRUPTO

- `V5_COMPONENT_MAP.json` **no existe**: el proceso se detuvo antes del primer checkpoint.
- `V5_COMPONENT_MAP_ABANDONADO_REGLA_V1.json` se conserva sólo como registro; **no se usa**.
- `V5_UNIVERSE_COMPONENTS.json` construido con la regla defectuosa fue **eliminado**.
- `V5_EVAL.json` **no existe**. **Ninguna métrica de resultado ha sido calculada.**

## 5. REANUDACIÓN

Ambos scripts son ahora **reanudables** (retoman desde el mapa parcial guardado) y tratan
el `429` como **fatal** (guardan y salen con `SystemExit(3)` en lugar de marcar
silenciosamente los pares como error).

```sh
cd /Users/mariaaleu/pmw-e2 && ./v5run.sh
```

Ejecuta en orden: `v5comp.py` (identificación) → `v5uni.py` (universo §14) →
`v5eval.py` (contrastes A/B/C, leads, regiones, LOSO, same-run, bootstrap).
Si vuelve a agotarse la cuota, se puede relanzar el mismo comando: continúa donde quedó.

## 6. HALLAZGOS YA FIRMES (no dependen de lo bloqueado)

### 6.1 `icon_seamless` es "seamless" también en el TIEMPO

Evidencia (EGLC, run `2026-06-02T18:00`):

```
icon_seamless   celda=51.5000,0.0600   no-nulos=121   último = +120 h
icon_d2         celda=51.5000,0.0600   no-nulos= 49   último = + 48 h
seamless vs icon_d2:  celda IDÉNTICA, coincidencia EXACTA en idx 0..45,
                      primera discrepancia en idx 46 (+46 h)
```

**Consecuencia para MODELSEL:** la composición de `icon_seamless` depende del **lead**,
no sólo de la estación. Para 9 h y 24 h la ventana cae dentro del alcance de D2, pero a
leads mayores la entidad evaluada cambia. Debe declararse como límite de transportabilidad
de cualquier decisión sobre M1 basada en leads cortos.

### 6.2 El proyecto NO define coordenadas de estación

Árbol completo del commit `5287122e141f972eaca9b7c62e88496343931457` recuperado del
almacén de objetos local **en copia aislada** (`$CLAUDE_JOB_DIR/tmp/pmwgit`), sin tocar
el repositorio. Resultado de la búsqueda en `src/` y `scripts/`:

```
src/weather_agent/config.py:103:  "params": "latitude, longitude, start_date, end_date, hourly=temperature_2m, "
```

Es la **única** aparición. No existe tabla de coordenadas ni resolución estación→lat/lon.
Las `req_lat`/`req_lon` de V3 proceden del artefacto de muestra, no del repositorio, y su
origen no es reproducible desde el código actual.

**Esto importa** porque la coordenada determina la celda: comparadas con OurAirports,
las coordenadas de V3 difieren hasta **39,5 km** (ZSQD) y **32,0 km** (ZGSZ).

Prueba de sensibilidad ya ejecutada (3 estaciones):

```
ZGSZ  V3           celda=22.5000,114.1250   componente=icon_global
ZGSZ  OurAirports  celda=22.6250,113.8750   componente=icon_global
ZSQD  V3           celda=36.1250,120.3750   componente=icon_global
ZSQD  OurAirports  celda=36.3750,120.1250   componente=icon_global
OPKC  V3           celda=24.8750, 67.1250   componente=icon_global
OPKC  OurAirports  celda=24.8750, 67.1250   componente=icon_global
```

El **componente** resiste el cambio de convención en estos 3 casos; la **celda** no, y por
tanto el pronóstico tampoco. La convención de coordenadas es un grado de libertad no fijado
y no preregistrado del pipeline. **No probado** en estaciones próximas a fronteras de
dominio (Europa), donde sí podría cambiar el componente.

### 6.3 Universo operativo enumerado

`CATALOG_V2.duckdb` tabla `v3`: 93 221 mercados en **57 filas ciudad/ICAO**.
55 con ICAO resoluble (91 285 mercados); 2 sin ICAO: **Hong Kong** (1 859 mercados,
169 eventos) y **Taipei** (77 mercados, 7 eventos) → se marcarán `UNKNOWN` en §14.

## 7. INTEGRIDAD (§15 del encargo)

| Comprobación | Estado |
|---|---|
| project files modificados | **NO** |
| DB modificada | **NO** (DuckDB abierto con `read_only=True`) |
| schema modificado | **NO** |
| pipeline modificado | **NO** |
| `weather_forecasts` modificada | **NO** (no existe; no se ha creado) |
| Git commit | **NO** |
| Git push | **NO** |
| M1 seleccionado | **NO** |
| Métricas de resultado calculadas | **NINGUNA** |

El árbol del proyecto se recuperó en **copia aislada** fuera de `/private/tmp/pmw-publish`.
El `.git` original no fue escrito. Todos los artefactos V5 residen en `/Users/mariaaleu/pmw-e2/`.
