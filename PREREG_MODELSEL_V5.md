# PREREG_MODELSEL_V5 — DESACOPLAMIENTO MODELO × RÉGIMEN DE RESOLUCIÓN

Congelado **ANTES** de calcular ninguna métrica estratificada por componente.
READ-ONLY. No modifica ni reinterpreta PREREG_MODELSEL_ASOF_V2 (sha `2b815fcb…`) ni
PREREG_MODELSEL_GEOVAL_V3 (sha `135d46f9…`). Ambos quedan intactos.

---

## 0. PREGUNTA ÚNICA

> ¿La ventaja aparente de `icon_seamless` sobre `ecmwf_ifs025` observada en V2/V3 se
> mantiene **dentro de cada régimen espacial real de ICON**, o está explicada
> principalmente por el régimen de resolución y/o la geografía?

El V5 originalmente planteado (igualar distancias estación→celda) queda **CANCELADO**
por la auditoría arquitectónica `ARCH_AUDIT_OPENMETEO.md` (sha `47a7cbe264b506e0…`):
la distancia es consecuencia intrínseca de la arquitectura de cada modelo y no debe
neutralizarse. Este V5 sustituye aquel diseño.

---

## 1. LIMITACIÓN INFERENCIAL DECLARADA POR ADELANTADO

**Este análisis es una RE-ANÁLISIS ESTRATIFICADO de un conjunto de datos ya observado,
no una confirmación fuera de muestra.**

- Los resultados agregados de V3 ya son conocidos por el analista.
- La variable de estratificación (componente ICON) es **nueva**: se midió de forma
  independiente en la auditoría arquitectónica y **no** intervino en la construcción de
  la muestra V3 ni en su análisis.
- Aun así, V5 **no puede** reclamar el estatus inferencial de un test confirmatorio
  independiente. Sus conclusiones son **exploratorias-estructurales**: sirven para
  detectar si la ventaja está confundida con el régimen, no para certificar una ventaja.
- **Consecuencia congelada:** ningún resultado de V5 puede, por sí solo, elevar la
  evidencia a "confirmada". V5 sólo puede **rebajar** la confianza en la ventaja agregada
  o mostrar que ésta es homogénea entre regímenes. Se declara aquí para impedir su uso
  posterior como confirmación.

---

## 2. MODELOS

- **Contraste principal:** `icon_seamless` (descompuesto en sus componentes) vs `ecmwf_ifs025`.
- `gfs_seamless` y `ukmo_global_deterministic_10km`: **excluidos** de V5. No participan en
  ningún contraste ni en ninguna decisión. No se reportan sus métricas.

---

## 3. MUESTRA — REUTILIZACIÓN ESTRICTA DE V3

Fuente: `MODELSEL_GEOVAL_V3_RAW.json` (3 200 filas) y `MODELSEL_GEOVAL_V3_SAMPLE.json`
(hash `7a57ce0a040a237bae8db0e518f0194d22efc41a5a993b81df3525eb5a53e2ae`).

- **No se añade ningún evento nuevo.** No se amplía el periodo, ni las estaciones, ni las regiones.
- Se retienen únicamente las filas con `model ∈ {icon_seamless, ecmwf_ifs025}` y `lead ∈ {9, 24}`.
- **Exclusiones (a documentar con recuento exacto en el informe):**
  - `f` nulo (run no disponible con `availability_safe_at ≤ T`);
  - `y` nulo (sin observación METAR válida en la ventana);
  - historia de desbiasing insuficiente (< 10, ver §7);
  - `COMPONENT = UNKNOWN` (sólo para los contrastes por componente; ver §5).

**Ninguna exclusión depende del resultado.** Todas son input-side o de identificabilidad.

### 3.1 Campos registrados por observación

`region`, `icao`, `req_lat`, `req_lon`, `model`, `component`, `resolution_deg`,
`cell_lat`, `cell_lon`, `dist_km`, `lead`, `run`, `T`, `availability_safe_at`,
`f`, `Y_final`, `residual_bruto`, `residual_debiased`, `cell_selection`.

- `T := endDate − lead_hours`, `endDate = target_date 12:00:00Z` (ancla 2E D1, sin cambios).
- `availability_safe_at := run + L_max(model)`, con `L_max` **idéntico a V2/V3**:
  `icon 4.76 h · ecmwf 8.78 h`. Prohibido usar `issue_time ≤ T`.
- `cell_selection`: **`land` (valor por defecto, no declarado en la petición)** — es la
  configuración operacional real. **No se modifica en V5.**
- `dist_km`: haversine entre coordenada solicitada y centro de celda devuelto.
  **Descriptivo. No se usa para ajustar, igualar ni ponderar.**

---

## 4. IDENTIFICACIÓN DEL COMPONENTE ICON — REGLA CONGELADA

**No se infiere el componente por resolución aproximada ni por región.**

Para cada par único `(estación, run)` presente en las filas `icon_seamless`, se consulta la
**Single Runs API** con el **mismo parámetro `run`** y las **mismas coordenadas solicitadas**
para `icon_d2`, `icon_eu` e `icon_global`, y se compara contra la respuesta de `icon_seamless`
para ese mismo `run`:

1. **Criterio de coincidencia (ambas condiciones):**
   - centro de celda idéntico: `round(lat,5) == round(lat,5)` y `round(lon,5) == round(lon,5)`; **y**
   - serie horaria idéntica: la tupla completa de `temperature_2m` coincide valor a valor,
     incluidos los `null` en las mismas posiciones.
2. **Asignación:**
   - **exactamente un** componente coincide → `COMPONENT` = ese componente;
   - **cero** componentes coinciden → `COMPONENT = UNKNOWN`;
   - **dos o más** componentes coinciden → **`COMPONENT = UNKNOWN`** (no es asignación
     inequívoca; se registra aparte como `UNKNOWN_AMBIGUO`).
3. Un componente que devuelve **HTTP 400** en esa coordenada se interpreta como
   **fuera de dominio** y no compite en la comparación. Se registra.
4. Las observaciones `UNKNOWN` se **excluyen de los contrastes por componente** y su número
   se reporta explícitamente, desglosado en `UNKNOWN_SIN_COINCIDENCIA` y `UNKNOWN_AMBIGUO`.
5. **El componente se determina por `(estación, run)`, no por estación.** Si una misma
   estación presenta componentes distintos en runs distintos, se registra y se reporta como
   **inestabilidad de composición**, y cada observación conserva su propio componente.

Resoluciones asociadas (inferidas y documentadas en la auditoría arquitectónica, §6):
`icon_d2 ≈ 0.02° (~2.2 km)` · `icon_eu ≈ 0.0625° (~7 km)` · `icon_global ≈ 0.125° (~13 km)` ·
`ecmwf_ifs025 = 0.25° (~28 km)`.

---

## 5. CONTRASTES PRINCIPALES

Tres contrastes **separados**, nunca agregados entre sí:

- **A)** ICON-D2 vs ECMWF
- **B)** ICON-EU vs ECMWF
- **C)** ICON-GLOBAL vs ECMWF

**Regla de emparejamiento (congelada):** cada contraste se calcula **sólo sobre las
observaciones `(event_id, icao, lead)` en las que el componente ICON correspondiente está
activo**, y ECMWF se restringe a **exactamente ese mismo conjunto de `(event_id, icao, lead)`**.
Esto implementa literalmente la prohibición de comparar un componente ICON con ECMWF en
regiones donde ese componente no existe: ECMWF nunca aporta observaciones que ICON no tenga
en ese estrato, ni al revés.

Métricas por contraste (todas reportadas):
n eventos · n estaciones · regiones · MAE bruto · **MAE residual (primaria)** · RMSE ·
bias · ΔMAE_res (ICON − ECMWF) · IC95 % bootstrap por bloques · MAE a 9 h · MAE a 24 h.

---

## 6. ANÁLISIS POR LEAD

Para cada componente se reportan **9 h y 24 h por separado, y se muestran antes de
cualquier agregado**. No se promedia 9 h y 24 h hasta haber presentado ambos.

---

## 7. DESBIASING — IDÉNTICO A V2/V3, SIN MODIFICAR

`historia(e)` = eventos de la **misma estación y mismo modelo** con `target_date ≤ D − 2 días`.
Si `|historia| < 10` → **NO EVALUABLE**, sin imputación.
`bias_hat = media(f − Y_final)` sobre la historia. `residual = (f − bias_hat) − Y_final`.
**MÉTRICA PRIMARIA = MAE(|residual|).**

**Nota congelada:** la historia de desbiasing se computa sobre `icon_seamless` como serie
única (tal como opera el pipeline), **no** por componente. Estratificar la historia por
componente cambiaría la definición de V2/V3 y está prohibido en esta ronda.

---

## 8. BOOTSTRAP — IDÉNTICO A V3/V4

Bootstrap por bloques con la **estación** como unidad de remuestreo.
**4 000 remuestreos, semilla 20260905.** IC95 % percentil (2.5 / 97.5).

Se reporta CI para ΔMAE_res sólo cuando el estrato tiene **≥ 3 estaciones**; con menos, la
unidad de remuestreo no admite un IC interpretable y el contraste se declara
`INCONCLUSO_POR_DISEÑO` con estadística únicamente descriptiva. Éste no es un umbral de
tamaño muestral: es el mínimo estructural para que exista el estadístico.

---

## 9. IGUALDAD DE RUN

Se repite el análisis restringido a los pares en que `run_ICON == run_ECMWF`,
**por componente y por lead**. Se reporta n, lead, componente, ΔMAE y IC95 %.
**No se extrapola** el resultado de igualdad de run a leads o componentes donde no exista.

---

## 10. DESCRIPCIÓN DEL RÉGIMEN (NO CONTROL)

Por componente se reportan de forma **puramente descriptiva**: distancia media, mediana,
p25, p75, y resolución. **La distancia no se iguala, no se ajusta y no se usa como
covariable en ningún estimador.** El objetivo es describir el régimen, no eliminarlo.

---

## 11. CONTRASTE DENTRO DE REGIÓN

Para cada región con cobertura suficiente (≥ 2 estaciones en el estrato) se reporta
ICON-componente vs ECMWF a 9 h y 24 h. Sirve para separar
*"ICON-EU gana en Europa"* de *"ICON gana porque Europa es más fácil"*.

---

## 12. LEAVE-ONE-STATION-OUT

Se recalcula ΔMAE_res excluyendo cada estación, una a una, en todo estrato con
≥ 3 estaciones. Se reporta si **el signo cambia** al retirar alguna.
**LOSO no se interpreta como evidencia de significación por sí solo.**

---

## 13. CRITERIO DE SUFICIENCIA — CONGELADO

No se fija ningún umbral arbitrario de n. Para cada contraste se reportan:
n estaciones · n eventos · anchura del IC95 % · estabilidad del signo bajo LOSO ·
heterogeneidad regional.

Un contraste se clasifica **INCONCLUSO** si se cumple **cualquiera** de:
- (i) el IC95 % de ΔMAE_res **incluye 0**;
- (ii) el **signo de ΔMAE_res cambia** bajo alguna exclusión leave-one-station-out;
- (iii) el estrato tiene **< 3 estaciones** (`INCONCLUSO_POR_DISEÑO`, §8).

En caso contrario se clasifica **CONCLUYENTE EN SU ESTRATO**, con la limitación §1 vigente.

---

## 14. UNIVERSO OPERATIVO (§11 del encargo)

Sobre el universo real del proyecto (`CATALOG_V2.duckdb`, tabla `v3`, 93 221 mercados,
57 filas ciudad/ICAO) se determina, para **cada estación**, el componente `icon_seamless`
realmente utilizado.

- Coordenadas: **OurAirports** (`airports.csv`, fuente pública), validadas contra las
  `req_lat`/`req_lon` de las 16 estaciones de V3; se reporta la discrepancia máxima.
  Cualquier estación sin coordenada resoluble se marca `UNKNOWN` y se cuenta.
- Identificación de componente: **misma regla del §4** (celda + serie horaria).
- Entregable: tabla `station | region | ICON component | resolution | ECMWF resolution`,
  ponderada por número de mercados y de eventos del catálogo.
- Sirve para determinar **qué contraste es realmente relevante para el producto**.

---

## 15. PREGUNTA CENTRAL — CATEGORÍAS CONGELADAS

> "¿La ventaja observada de ICON en V2/V3 procede de ICON como familia de modelo, o está
> explicada principalmente por determinados regímenes de resolución/geografía?"

- **A** — ICON mantiene ventaja consistente dentro de los principales componentes/regímenes.
  *Requiere:* ΔMAE_res < 0 y contraste CONCLUYENTE (§13) en **todos** los componentes con
  ≥ 3 estaciones, y en **ambos** leads.
- **B** — ICON mantiene ventaja en algunos regímenes pero no en otros.
  *Requiere:* al menos un componente CONCLUYENTE a favor de ICON y al menos otro
  componente o lead donde no lo esté o donde el signo se invierta.
- **C** — no hay evidencia suficiente para atribuir ventaja a ICON como familia.
  *Requiere:* ningún componente alcanza contraste CONCLUYENTE.
- **D** — la ventaja desaparece una vez desacoplamos resolución/geografía.
  *Requiere:* ΔMAE_res ≥ 0 (ECMWF igual o mejor) en el/los componentes que dominan el
  universo operativo (§14), o inversión de signo respecto al agregado V3.

La categoría se elige por los resultados, no por conveniencia.

---

## 16. DECISIÓN M1 — OPCIONES CONGELADAS

**No se selecciona M1 automáticamente.** Al final se recomienda **exactamente una**:

1. `M1 = icon_seamless`
2. `M1 = ecmwf_ifs025`
3. `M1` dependiente del componente/región
4. `M1` dependiente del lead
5. continuar investigación: la evidencia no permite decidir

Si se propone (4), debe justificarse **separando explícitamente 9 h y 24 h**.
La recomendación es una **recomendación**, no una fijación: M1 no se escribe en el proyecto.

---

## 17. FRESCURA

`run_age` se reporta **por separado**, por modelo, componente y lead.
**NO se usa para tapar una diferencia de precisión.** Sólo puede invocarse como criterio
operacional **secundario** si la precisión queda prácticamente empatada — definido aquí
como: el IC95 % de ΔMAE_res incluye 0 **y** |ΔMAE_res| < 0.05 °C.

---

## 18. PROHIBICIONES

No ejecutar M2/M3. No fijar M1 en el proyecto. No escribir `weather_forecasts`.
No modificar código, schema, DB, pipeline ni configuración. No commit. No push.
No modificar coordenadas. No igualar distancias. No cambiar `cell_selection`.
No introducir ninguna transformación ajena a la extracción operacional.
No cambiar métricas ni criterios después de ver resultados.

---

# ENMIENDA V5.1 — CORRECCIÓN DE LA REGLA DE IDENTIFICACIÓN (§4)

**Momento:** durante la ejecución de la identificación de componente, **antes de calcular
ninguna métrica de resultado**. No se había computado ningún MAE, ningún ΔMAE, ningún IC,
ningún contraste. El fichero `V5_EVAL.json` no existía. La enmienda **no puede estar
motivada por resultados porque no había resultados**.

## Defecto detectado

La regla §4 exigía coincidencia de la **serie horaria completa** (168 valores). Esa regla es
**mecánicamente incapaz de identificar `icon_d2`**, por una razón que la auditoría
arquitectónica no había detectado:

> **`icon_seamless` es "seamless" también en el TIEMPO, no sólo en el espacio.**

Evidencia (EGLC 51.5053/0.0553, run `2026-06-02T18:00`):

```
icon_seamless   celda=51.5000,0.0600   no-nulos=121   último = +120 h
icon_d2         celda=51.5000,0.0600   no-nulos= 49   último = + 48 h
icon_eu         celda=51.5000,0.0625   no-nulos=121   último = +120 h
icon_global     celda=51.5000,0.0000   no-nulos=121   último = +120 h

seamless vs icon_d2     : celda IDÉNTICA, coincidencia exacta en idx 0..45,
                          primera discrepancia en idx 46 (+46 h)
seamless vs icon_eu     : celda distinta, discrepancia desde idx 1
seamless vs icon_global : celda distinta, discrepancia desde idx 0
```

`icon_seamless` reproduce exactamente `icon_d2` mientras D2 tiene alcance (~48 h) y
después transiciona a un componente más grueso. La comparación sobre 168 h falla siempre
para D2, produciendo `UNKNOWN` de forma sistemática **precisamente en el componente de
mayor resolución** — es decir, el sesgo de identificación apuntaba justo contra la
hipótesis que V5 debe contrastar.

Efecto observado de la regla defectuosa: 6 de 55 estaciones del universo operativo
(EGLC, EDDM, LIMC, EHAM, LFPB, LFPG — todas del dominio D2) devolvían `UNKNOWN`.

## Regla corregida (§4 bis) — sustituye a §4.1

La identificación se realiza **sobre la ventana horaria que efectivamente produce `f`**,
es decir `W(m)` = **día civil local de la estación en `target_date`**, que es la misma
ventana con la que V2/V3 calculan `f = max(temperature_2m)`. Criterio:

1. **Centro de celda idéntico** (`round(lat,5)`, `round(lon,5)`); **y**
2. **coincidencia exacta valor a valor en todas las marcas de tiempo `t ∈ W(m)` para las
   que `icon_seamless` tiene valor no nulo**; el componente debe tener valor no nulo en
   todas ellas. Se exige al menos 1 hora comparable; si hay 0, `COMPONENT = UNKNOWN`.

El resto de §4 (cero coincidencias → `UNKNOWN`; dos o más → `UNKNOWN_AMBIGUO`;
HTTP 400 → fuera de dominio; asignación por `(estación, run)`) **se mantiene sin cambios**.

## Justificación

La regla corregida es **más fiel al objetivo declarado**, no más laxa: identifica qué
componente generó **el pronóstico que realmente se evalúa**, en lugar de exigir identidad
en horas que no intervienen en `f` y que pertenecen a otro régimen de la mezcla temporal.
Es además **más estricta en lo relevante**: exige coincidencia exacta, sin tolerancia, en
todas las horas que producen `f`.

## Consecuencias declaradas

- El mapa de componentes generado con la regla defectuosa se conserva como
  `V5_COMPONENT_MAP_ABANDONADO_REGLA_V1.json` y **no se usa** en ningún cálculo.
- Se recalcula íntegramente la identificación, y también la tabla del universo operativo (§14).
- **Nuevo hallazgo a reportar en el informe:** la composición de `icon_seamless` depende
  del **lead**, no sólo de la estación. Para los leads primarios de esta investigación
  (9 h y 24 h) la ventana cae dentro del alcance de D2, pero a leads mayores la
  composición cambiaría. Esto debe declararse como limitación de transportabilidad.

El preregistro V5 original (sha `ed062a1d9c676aaee79847fc19b9ff9fadf78b14728cbfacd8d26b6258dcdb24`)
queda superado por este documento enmendado. Ambos hashes se reportan.

---

# ENMIENDA V5.2 — ADOPCIÓN DE LA CONVENCIÓN CANÓNICA DE COORDENADAS (D1)

**Momento:** 2026-09-05, antes de cualquier ejecución de V5 y sin haber calculado ninguna métrica.
`V5_EVAL.json` no existe. La identificación de componente con la regla V5.1 no llegó a
completarse (bloqueo HTTP 429) y **no se ha usado**.

**Autoridad:** mandato del usuario de 2026-09-05 delegando las decisiones a Claude y Codex.
Decisión registrada como **D1** en `DECISIONS.md`. Pendiente de objeción de Codex; si la
hubiera, se emitirá V5.3.

## Qué cambia

§3 decía: *"Se retienen únicamente las filas [de V3 RAW]… No se añade ningún evento nuevo."*
Se mantiene la muestra (400 eventos, 16 estaciones, mismos `run`, mismos leads, mismos `Y_final`)
pero **los pronósticos `f` se RE-EXTRAEN** con las coordenadas canónicas:

- **Coordenadas:** `STATION_COORDS_SNAPSHOT_v1.json`
  (sha256 `ebe21014519eb725143e486a88567e468661fb2ad860e7528d15f501a02d02a6`), regla de
  `COORDINATE_UNIVERSE_AUDIT.md` §10. Sustituye a `req_lat`/`req_lon` de
  `MODELSEL_GEOVAL_V3_SAMPLE.json` (que eran IEM).
- **Modelos re-extraídos:** `icon_seamless`, `icon_d2`, `icon_eu`, `icon_global`, `ecmwf_ifs025`
  — 800 pares `(estación, run)` × 5 = **4 000 peticiones** a Single Runs API, con el **mismo
  parámetro `run`** que V3. Ejecución reanudable; puede repartirse en dos días de cuota.
- **Todo lo demás permanece idéntico:** `availability_safe_at`, ventana `W(m)`, `Y_final` desde
  IEM METAR, desbiasing (§7), bootstrap (§8), contrastes (§5), categorías (§15–§16).

## Por qué re-extraer las 16 y no sólo las 3 que cambian de celda

El impacto de D1 sobre las 16 estaciones de V3 (`COORD_UNIGEOM.json`) es:
```
cambian celda: OPKC (ECMWF), ZGSZ (ECMWF+ICON), ZSQD (ECMWF+ICON)   -> 3/16
resto: misma celda en ambos modelos, componente ICON idéntico       -> 13/16
```
Pero el downscaling vertical usa el DEM **en la coordenada solicitada** (auditoría §5): mover la
coordenada 0,05–4,6 km cambia la elevación de referencia y por tanto `f` en fracciones de grado
aunque la celda sea la misma. Re-extraer sólo 3 estaciones produciría un dataset de convención
mixta. Se re-extraen las 16 para que **una única convención** gobierne todo V5.

## Consecuencia inferencial (actualiza §1)

V5.2 deja de ser un puro re-análisis: los `f` son extracciones nuevas. Los `Y_final`, la
muestra y los `run` siguen siendo los de V3, y los resultados agregados de V3 siguen siendo
conocidos por el analista. **La limitación §1 se mantiene**: V5.2 no adquiere estatus
confirmatorio independiente.

## Consecuencia sobre la identificación de componente (§4 bis)

Se recalcula íntegramente con las coordenadas canónicas. El mapa parcial de la regla V5.1 se
descarta. Se espera (por `COORD_UNIGEOM.json`) que el componente no cambie en ninguna de las 16,
pero **se identifica de nuevo, no se hereda**.

## Excepciones abiertas heredadas de D1

OPKC está en la muestra V5 y es una excepción abierta de D1 (NOAA a 2,51 km del ARP). Se usa la
coordenada NOAA por la regla general y **se marca**: en el informe V5 se reportará el contraste
con y sin OPKC como análisis de sensibilidad **pre-declarado aquí**, no post-hoc.

---

# ENMIENDA V5.3 — §14 ALINEADO CON D1 (corrección de omisión)

**Momento:** 2026-09-05, antes de cualquier ejecución; ninguna métrica calculada.
V5.2 decía *"todo lo demás permanece idéntico"* pero **§14 seguía indicando "Coordenadas:
OurAirports"** para el universo operativo, en contradicción con D1. Se corrige: **§14 usa
`STATION_COORDS_SNAPSHOT_v1.json` (v1.1, sha en `STATION_COORDS_SNAPSHOT_v1.sha256`)**; OurAirports
sólo como control. `v5uni.py` ha sido alineado en consecuencia. Nada más cambia.
