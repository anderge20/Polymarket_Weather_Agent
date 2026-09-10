# MODELSEL V5 — INFORME FINAL · Categoría §15 y recomendación M1 §16

**Fecha:** 2026-09-06 · **Preregistro vigente:** V5.3 (`e8302dc1…`), congelado antes de ejecutar
**Ejecución:** `v5run2.sh`, 07:22–07:37 UTC · 1 200/1 200 claves · 4 000 respuestas
(2 779 `ok` + 1 221 `out_of_domain`, estas últimas por diseño: ICON-D2/EU fuera de su dominio)
**Coordenadas:** `STATION_COORDS_SNAPSHOT_v1.json` v1.1 (D1, alcance acotado por D6)

> ⚠️ **CORREGIDO POR `MODELSEL_V5_CORRECTION_01.md` (2026-09-06).** Las secciones §4 y §9
> de este informe son incorrectas: la diferencia de edad del run NO es un confusor sino la
> latencia de diseminación de cada producto, y el experimento `same_run` a 24 h que §9
> proponía usaría información del futuro. La recomendación M1 pasa de la opción 5 a la
> **opción 1 (`M1 = icon_seamless`)**. §1, §2, §3, §5, §6, §7 y §8 (contrastes, categoría **B**,
> universo operativo) se mantienen íntegros.


Ninguna métrica fue calculada antes de congelar los criterios. Nada de lo que sigue cambia
métricas ni umbrales a posteriori (§18).

---

## 1. Contrastes principales — ΔMAE_res = MAE_ICON − MAE_ECMWF (negativo ⇒ ICON mejor)

| Componente | est | obs | ΔMAE_res | IC95 % | LOSO | §13 |
|---|---:|---:|---:|---|---|---|
| `icon_d2` | 2 | 80 | −0.111 | no calculable | — | **INCONCLUSO_POR_DISEÑO** (iii: <3 est) |
| `icon_eu` | 4 | 156 | −0.150 | **[−0.246, −0.037]** excluye 0 | sin cambio de signo | **CONCLUYENTE EN SU ESTRATO** |
| `icon_global` | 9 | 350 | −0.043 | [−0.198, +0.121] incluye 0 | **cambia de signo** (MMMX) | **INCONCLUSO** (i **y** ii) |

Clasificaciones verificadas una a una contra §13 de forma independiente. Correctas.

## 2. Desglose por lead — el resultado concluyente vive en un solo estrato

| Estrato | ΔMAE_res | IC95 % | §13 |
|---|---:|---|---|
| `icon_eu` **9 h** | −0.060 | [−0.170, +0.015] incluye 0 | INCONCLUSO |
| `icon_eu` **24 h** | **−0.240** | **[−0.393, −0.053]** excluye 0 | **CONCLUYENTE** |
| `icon_global` 9 h | −0.060 | [−0.241, +0.125] | INCONCLUSO |
| `icon_global` 24 h | −0.025 | [−0.191, +0.154] | INCONCLUSO |

La conclusividad del agregado `icon_eu` procede **íntegramente del lead de 24 h**.

## 3. Universo operativo §14 — dónde está el producto

| Componente | estaciones | mercados | % | contraste V5 |
|---|---:|---:|---:|---|
| `icon_global` | 42 | 68 515 | **75.1 %** | INCONCLUSO |
| `icon_eu` | 7 | 12 971 | 14.2 % | CONCLUYENTE (ICON) |
| `icon_d2` | 6 | 9 799 | 10.7 % | INCONCLUSO_POR_DISEÑO |

**Tres cuartas partes del universo del producto caen en el componente donde la evidencia es
inconcluyente, y además con inversión de signo bajo LOSO.** El único estrato concluyente cubre
el 14.2 % de los mercados.

## 4. Hallazgo crítico — la ventaja concluyente coincide con una ventaja de frescura

§17 exige reportar `run_age` por separado. Los datos:

| Lead | edad del run ICON | edad del run ECMWF |
|---|---:|---:|
| 9 h | 9 h | 9 h |
| 24 h | **6 h** | **12 h** |

A 9 h ambos modelos parten del mismo run: la comparación es limpia, y ahí `icon_eu` es
**INCONCLUSO** (Δ = −0.060, IC incluye 0). A 24 h ICON usa un run **6 horas más fresco** que
ECMWF, y es exactamente ahí donde aparece el único resultado **CONCLUYENTE** (Δ = −0.240).

> Cuando la edad del run se iguala, la ventaja de ICON desaparece. Cuando ICON recibe un run
> más fresco, aparece.

El control `same_run` del preregistro sólo produjo estratos de **9 h** — a 24 h los modelos usan
runs estructuralmente distintos, así que ese control no existe donde haría falta.

**Esto NO reclasifica nada.** §18 prohíbe cambiar criterios tras ver resultados: `icon_eu` sigue
siendo CONCLUYENTE por §13. Pero al elegir la recomendación §16 —que es un juicio, no una
clasificación— esta coincidencia es determinante: no se puede atribuir a "ICON como familia de
modelo" una ventaja que sólo aparece donde ICON parte con 6 horas de ventaja informativa.

§17 prohíbe usar la frescura para *tapar* una diferencia de precisión. Aquí opera en la dirección
contraria y el preregistro no la previó; se declara como limitación, no como criterio.

## 5. Heterogeneidad regional en `icon_global`

Los signos no son consistentes dentro del componente dominante:

```
LATAM_NORTE  9h  Δ = −0.391   (ICON mejor)
ASIA_ESTE    9h  Δ = −0.090   (ICON mejor)
ASIA_SUR     9h  Δ = +0.141   (ECMWF mejor)
HEM_SUR      9h  Δ = +0.112   (ECMWF mejor)
HEM_SUR     24h  Δ = +0.294   (ECMWF mejor)
```

Coherente con el LOSO: excluir MMMX invierte el signo del agregado (−0.043 → +0.007).

## 6. Régimen de resolución — el confusor que V5 venía a desacoplar

Distancia media estación→celda, por componente:

```
icon_d2       0.02°    0.92 km
icon_eu       0.0625°  2.12 km
icon_global   0.125°   6.87 km
ecmwf_ifs025  0.25°    9.64 km
```

La ventaja de ICON en el agregado de V2/V3 es **monótona en la resolución**: máxima donde ICON
tiene celda fina (EU) y desaparece donde ICON opera a 0.125° frente a los 0.25° de ECMWF —
que es el 75 % del universo. Esto es exactamente lo que V5 se diseñó para separar, y lo separa.

## 7. Sensibilidad OPKC (pre-declarada en V5.2)

```
icon_global  con OPKC: Δ = −0.0427     sin OPKC: Δ = −0.0139
```

Ambos inconcluyentes; la exclusión no cambia el signo. La excepción abierta de coordenadas de
OPKC (D1/D6) **no altera ninguna conclusión** de este informe.

---

## 8. CATEGORÍA §15 — **B**

- **A** exigiría CONCLUYENTE en *todos* los componentes con ≥3 estaciones y en *ambos* leads.
  `icon_global` (9 est) es INCONCLUSO → **A descartada**.
- **C** exigiría que *ningún* componente alcanzara contraste concluyente. `icon_eu` lo alcanza
  → **C descartada**.
- **D** exigiría ΔMAE_res ≥ 0 en el componente que domina el universo, o inversión de signo
  respecto al agregado V3. `icon_global` da −0.043 (< 0) y mantiene el signo de V3
  → **D descartada**.
- **B** — *"ICON mantiene ventaja en algunos regímenes pero no en otros"*: se cumple
  exactamente. Ventaja concluyente en `icon_eu`; ausente en `icon_global` y `icon_d2`;
  inversión de signo por región dentro de `icon_global`.

> **Respuesta a la pregunta central de §15:** la ventaja de ICON observada en V2/V3 **no
> procede de ICON como familia de modelo**. Está concentrada en el régimen de resolución fina
> (ICON-EU a 0.0625° frente a ECMWF a 0.25°) y, dentro de él, en el lead donde ICON además
> dispone de un run 6 horas más fresco.

## 9. RECOMENDACIÓN M1 §16 — opción **5: continuar investigación**

Descartadas las demás, y por qué:

1. **`M1 = icon_seamless`** — extendería al 75 % del universo (`icon_global`, INCONCLUSO con
   inversión de signo bajo LOSO) una conclusión probada sólo en el 14.2 %. No sostenible.
2. **`M1 = ecmwf_ifs025`** — ninguna estimación puntual favorece a ECMWF en el agregado; el
   signo global es negativo en los tres componentes. Sin apoyo.
3. **`M1` por componente/región** — es lo que la evidencia respalda *para el 14.2 %*, pero
   dejaría indefinido el componente que cubre tres cuartas partes del producto. Un M1
   indefinido para el 75 % del universo no es un M1.
4. **`M1` por lead** — el único estrato concluyente es `icon_eu|24 h`, y es precisamente el que
   está confundido con la frescura del run (§4). Fijar M1 por lead sobre esa base sería
   consagrar un artefacto de edad de run como criterio de modelo.
5. **Continuar investigación.** ✅

### Experimento decisivo, ya especificado

Una sola pregunta separa la categoría B de una decisión sobre M1:

> ¿Sobrevive la ventaja de `icon_eu` a 24 h cuando ambos modelos parten **del mismo run**?

Requiere extraer ECMWF en los runs de ICON (o ICON en los de ECMWF) para los 78 pares de
`icon_eu` a 24 h — un control `same_run` a 24 h, que el preregistro sólo construyó a 9 h.
Coste estimado: **~156 peticiones**, tres órdenes de magnitud por debajo de esta ejecución.
Exige **enmienda V5.4 congelada y hasheada antes de ejecutar** (§18 prohíbe extracciones
ajenas al preregistro vigente).

Resultado esperado y su lectura, declarados **antes** de ejecutar:
- Si la ventaja **persiste** con run igualado → sostiene `M1` dependiente del componente
  (ICON en régimen de resolución fina).
- Si la ventaja **desaparece** → categoría **D** de facto, y la recomendación pasa a
  `M1 = ecmwf_ifs025` por simplicidad operativa, al no haber ventaja de ICON en ningún
  régimen con comparación limpia.

## 10. INTEGRIDAD

| Comprobación | Estado |
|---|---|
| M1 seleccionado | **NO** — recomendación §16 opción 5 |
| M1 escrito en el proyecto | **NO** |
| M2/M3 ejecutados | **NO** |
| `weather_forecasts` escrita | **NO** |
| código / schema / DB / pipeline modificados | **NO** |
| git commit / push | **NO** |
| criterios o métricas cambiados tras ver resultados | **NO** |
| coordenadas modificadas | **NO** |

**Artefactos:** `V5_EXTRACT.json` (3.0 MB) · `V5_DATASET.json` (972 KB) ·
`V5_UNIVERSE_COMPONENTS.json` · `V5_EVAL.json` · este informe.
**Limitación heredada:** D1 está verificada en 11/55 estaciones (D6); en las 43 restantes la
convención de coordenadas es inferencia declarada, no verificación individual.
**Limitación de transportabilidad:** `icon_seamless` cambia de componente con el lead (D2 sólo
hasta ~+45 h); nada de esto se transporta a leads largos.
