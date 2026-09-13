# PREINSCRIPCIÓN · tarea #63 — CONTAR CONFLICTOS REALES DE VENTANA CONTRA RESOLUCIONES

**Escrito y espejado ANTES de ejecutar nada.** Esto es el paso que A-259 dejó declarado y
bloqueado: *«la siguiente cifra que vale la pena no sale de afinar la definición sino de
contar conflictos reales contra resoluciones, y eso necesita el corpus reparado»*, y
`s01_ventana_hora_cero.py` lo repite en su docstring: *«NO MIDE: si el mercado resolvió
distinto. Eso necesita las escaleras completas, que hoy están truncadas (A-244), y se hará
tras la reingesta»*. **La reingesta está hecha y `markets_v2` cubre 52 estaciones y 79 735
mercados**, así que el bloqueo se levanta hoy.

## 0. Lo primero, porque es un riesgo y no una medición

El tarball del que depende toda la cota vivía en
`/Users/mariaaleu/.claude/jobs/43deec01/tmp/raw_b133.tgz` —**el directorio temporal de OTRO
trabajo**— y `s02_ventana_estricta.py` apuntaba a una ruta que ya no existe
(`wt-research/evidence/B-133/…`). El instrumento habría fallado ruidosamente; la evidencia
habría desaparecido en silencio con el trabajo que la alojaba.

Copiado a `~/pmw-e2/evidence/B-133/raw_iem_55_estaciones.tgz`, con la misma suma:

    sha256  be91a0096627ad2edafd32008eea35757b50094558b8027a4182b41991b81322

Cobertura del tarball: **2026-04-09 → 2026-09-05, 55 estaciones, series `rt3` y `rt34`.**

## 1. La definición, copiada de A-259 sin tocar una palabra

Un día-estación **cuenta en el denominador** si y sólo si pasa (a). Está **EXPUESTO** si
además cumple (b) y (c):

* **(a) cobertura** — las horas de `weather.PEAK_LOCAL_HOURS` están todas presentes en el día
  civil local.
* **(b)** el máximo del día civil local se alcanza en la **hora 00 local**.
* **(c)** ese máximo es **estrictamente mayor**, en la **rejilla de la estación** y con la
  **serie que esa estación pide en producción** (`observations.station_series`), que el
  máximo del resto del día.
* **(d) banda distinta** — los dos valores caen en bandas distintas de la escalera del evento.

Cota preinscrita de A-259/A-260, que NO se toca:

    dias etiquetables                                7 979
      banda distinta                                    39   (0,489 %)
      + los 14 estrictos sin evento en el catalogo      53   (0,664 %)

## 2. Lo que se mide AHORA y no se pudo medir entonces

Para cada día **expuesto con banda distinta**, se busca el evento de ese `(station,
target_date)` en **`markets_v2`** con la **regla de población de A-275** (resuelto +
partición completa + ganadora única; desempate por `close_time` por encima del día civil
local) y se compara la **banda ganadora declarada** con las dos candidatas:

| clasificación | significado |
|---|---|
| `A_FAVOR_DE_ESTRICTO` | la banda del máximo **del resto del día** es la ganadora → la fuente contractual **excluye** la hora 00 |
| `A_FAVOR_DE_CIVIL` | la banda del máximo **del día civil completo** es la ganadora → la fuente **incluye** la hora 00, como hace el núcleo congelado |
| `NINGUNA` | la ganadora no es ninguna de las dos → hay una tercera explicación y la cota no mide lo que dice |
| `SIN_EVENTO_ELEGIBLE` | no hay evento que cumpla A-275 para ese día |

## 3. REGLA DE DECISIÓN, escrita antes de ver un solo número

* **Todos los resueltos `A_FAVOR_DE_ESTRICTO`** → la condicional de A-259 queda **sostenida**,
  y la cota 0,489–0,664 % pasa de ser exposición a ser **conflicto real**. Es un hallazgo
  sobre el núcleo congelado y **se escala, no se arregla**: `SETTLEMENT_OPERATOR_CORE.v3`
  está congelado por sha y no se toca desde aquí.
* **Al menos uno `A_FAVOR_DE_CIVIL`** → la condicional queda **REFUTADA**. La cota mide
  exposición y no conflicto, y hay que decirlo en A-259 con un puntero.
* **Mezcla** → la ventana **no es una regla única entre fuentes**, y hay que estratificar por
  `resolution_source` antes de decir nada.
* **Cero resueltos** (todo `SIN_EVENTO_ELEGIBLE` o `NINGUNA`) → la cota **sigue sin poder
  contrastarse**, se dice así, y la tarea #63 se cierra como *no medible con este corpus* en
  lugar de inventar una cifra.

**No se elegirá la estratificación, ni la serie, ni la ventana temporal después de ver el
resultado.** La serie es la de producción por estación, la ventana es la intersección del
tarball (2026-04-09 → 2026-09-05) con `markets_v2`, y el denominador es el de A-259.

## 4. Lo que este instrumento NO puede decidir

* **No mide la fuente contractual directamente.** Compara nuestra reconstrucción con la
  ganadora que UMA liquidó. Un desacuerdo señala la ventana como **explicación compatible**,
  no como causa probada: la fuente es Wunderground y nuestra serie es METAR de IEM.
* **No mide nada fuera de 2026-04-09 → 2026-09-05.**
* **n será pequeño.** Con 39 días de banda distinta en 55 estaciones y una intersección más
  corta que el catálogo, el número de conflictos resueltos puede quedarse en un dígito. Se
  reportará el intervalo binomial exacto junto al recuento, y **un `n` de un dígito no
  valida nada**: como mucho refuta.
