# M2 — ÍNDICE DE LA CADENA DE PREREGISTROS: qué versión gobierna hoy

**Sesión:** B · **2026-09-10** · **No sustituye ni modifica ningún preregistro.** Ninguno de los
documentos citados aquí cambia un byte: sus sha siguen siendo los que son. **Esto es el eslabón
que faltaba**, no una enmienda.

## Por qué existe

Lo encontró la sesión A auditando la capa de referencias (A-105), y es un defecto **mío**:

> `PREREG_M2_ERROR_v3.md` dice en su cabecera: *«Sustituye a v2 (`b2b168d4…`), que queda
> **RETIRADO por NO APTO**»*. Y `fit_quantile_artifact.py:152` escribe **ese mismo `b2b168d4…`**
> como procedencia del artefacto que usa producción.

Un auditor verifica el artefacto, abre la cadena, lee que v2 está retirado, y concluye —**con
toda la razón dada la cadena**— que producción corre sobre un preregistro retirado.

**No es así, y la decisión es correcta: v3 falló su propio criterio y se retiró.** Pero eso vive
en `M2_V3_REPORT.md` y en un comentario de `error_model.py:231`, **no en la cadena**. La
afirmación de v3 sobre v2 **era cierta cuando se escribió y dejó de serlo**, y un documento
congelado no puede enterarse.

## Estado de cada versión, hoy

| versión | sha | estado | por qué |
|---|---|---|---|
| **v1** | `16b729e1…` | **RETIRADA** | el tamaño de muestra dependía del `TimeZone` de la sesión DuckDB (2 599 frente a 1 881) y el corte `target_date < D` filtraba etiqueta futura en 8 de 8 estaciones. Sustituida por v2 |
| **v2** | `b2b168d4…` | **VIGENTE — GOBIERNA PRODUCCIÓN** | es la que produce los cuantiles del artefacto en uso |
| **v3** | `11c2c69f…` | **RETIRADA POR SU PROPIO §4/§5** | calibración por estación en **6 de 46** estaciones contra un listón de 70 %, y los pares con desplazamiento calibraban **peor** (5 %) que los sin él (24 %). Publicada como `M2_V3_REPORT.md`. **Nunca escribió cuantiles en la base** |

**La frase de v3 sobre v2 NO ESTÁ OPERATIVA.** Era el paso siguiente propuesto y ese paso falló;
al fallar, v2 vuelve a ser lo mejor disponible, que es exactamente lo que `M2_V3_REPORT.md` §5
concluye: *«M2 se queda en v2: agrupado por lead, calibrado en agregado.»*

## Lo que un lector necesita y la cadena no le da

- **Las prohibiciones vigentes de v2 son las de v1 §10.** La §6 de v2 las cita como «§10» sin
  cualificar, y v2 no tiene §10 — B-24.
- **La limitación que v3 estableció SIGUE EN PIE aunque v3 esté retirada**, y es la más
  importante de M2: la probabilidad que v2 da para **un mercado concreto** está peor calibrada
  que su cifra agregada, y **no es corregible con este sustrato** — el sesgo por estación no es
  persistente (correlación entre mitades del periodo **+0,080**). Una versión retirada puede
  dejar un resultado válido: **lo que se retiró fue el método, no la medición que lo tumbó.**
- **El repositorio sólo contiene `prereg/PREREG_M2_ERROR_v2.md`**: v1 y v3 viven fuera, así que
  desde el repo no se puede resolver ninguna de las citas de arriba.

## La regla que sale, y es general

> **Un preregistro retirado necesita un puntero HACIA ADELANTE a lo que lo retiró.**

Sin él gana **la última afirmación de la cadena** — y la última afirmación puede venir de un
documento que fue retirado a su vez. Es la categoría de B-24 (*una referencia que resuelve a algo
que ya no es cierto*) subida un nivel: allí era **dentro** de un documento, aquí es **entre**
documentos, y aquí es peor, porque cada documento por separado es correcto y sólo la cadena
miente.

**Y no se arregla editando:** editar v3 para decir que se retiró rompería su sha y con él la
prueba de que se congeló antes de calcular nada. **Se arregla con un índice fechado que se
actualiza**, que es lo que es esto.
