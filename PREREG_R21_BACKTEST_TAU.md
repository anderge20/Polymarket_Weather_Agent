# PREREG_R21 — backtest y calibración fuera de muestra de los umbrales

**Sesión:** B (Claude) · **Congelado:** 2026-09-09, antes de calcular ninguna métrica de
resultado, ningún umbral y ningún PnL.

**Insumos ya congelados y no renegociables aquí:** M1 = `icon_seamless` (D12) · M2 = v2,
agrupado por lead, con la limitación de B-12 · D1/D6 coordenadas · D19 modelo de costes ·
B-7 unidades · v2 §3 disponibilidad.

---

## 0. Pregunta única

> Con la señal que produce M2 y el modelo de costes de D19, ¿existe un umbral de edge que
> deje operaciones con esperanza positiva **fuera de muestra**, y cuál es?

No se pregunta cuánto se ganaría. Se pregunta si **queda algo** tras costes y tras el margen
que exige la descalibración medida.

## 1. Dos umbrales, no uno — separación aportada por la sesión A

Un solo `tau` sería un umbral con dos operandos distintos, la misma clase de defecto que el
`n≥30` de M2 v1:

- **`tau_signal`** — sobre el edge **BRUTO** contra el **mid**: `|p_model − p_mid|`. Decide si
  el mercado merece siquiera mirarse.
- **`tau_exec`** — sobre el edge **NETO** contra el **VWAP alcanzable**, después de comisiones
  (D19) y de recorrer el book. Decide si se opera.

`tau_exec` se evalúa **al precio alcanzable, nunca al cotizado**: acreditar a la estrategia una
ventaja que nadie tuvo que pagar en spread es inventar rendimiento.

## 2. El margen de `tau_exec` — CONGELADO, y NO sale de la calibración agregada

B-12 midió que `p_model` está peor calibrada **por mercado** que en agregado, y que esa
diferencia **no es corregible** con este sustrato. Por tanto:

> **El margen se deriva de la dispersión ENTRE estaciones, no de la cobertura agregada.**

Usar la agregada volvería a comprar exactamente el problema diagnosticado: la agregada se ve
bien **porque** los sesgos opuestos se cancelan.

```
tau_exec  =  tau_costes  +  margen_calibracion
margen_calibracion = |P(banda | dist. desplazada ±τ_est) − P(banda | dist. sin desplazar)|
τ_est = 0,545 °C   (dispersión entre estaciones medida en B-11, en la unidad del mercado)
```

El margen se calcula **por mercado**, no como una constante: desplazar la distribución τ_est
mueve mucho la probabilidad de una banda estrecha cerca del centro y poco la de una banda ancha
en la cola. Un margen constante en puntos de probabilidad sería otro umbral con dos operandos.

`tau_signal` se calibra fuera de muestra (§3); `tau_exec` **no se calibra**: se deriva de los
costes y del margen. Calibrarlo sería elegirlo a partir del resultado.

## 3. Calibración fuera de muestra de `tau_signal` — CONGELADA

Walk-forward expansivo por fecha objetivo, la misma disciplina que M2:

- para decidir en `D`, sólo operaciones con `target_date` cuya **etiqueta ya estaba disponible**
  (fin del día local + 24 h, v2 §3);
- rejilla de candidatos: `tau_signal ∈ {0,02 · k}` para k = 1…10, **fijada aquí**;
- criterio de selección: el `tau_signal` que maximiza la **mediana** del PnL neto por
  operación en la ventana de entrenamiento. Mediana y no media: con pocas operaciones la media
  la fija una cola;
- si dos valores empatan dentro de 1e-9, gana el **mayor** (menos operaciones, más exigente).

## 4. Criterio de aceptación FALSABLE — CONGELADO

La estrategia se declara **OPERABLE** si y sólo si, sobre el conjunto fuera de muestra:

1. **n ≥ 100 operaciones** accionables. Por debajo, `NO EVALUABLE` — no `APTA`.
2. **PnL neto mediano por operación > 0** tras costes D19 y con `tau_exec` aplicado.
3. **El signo sobrevive** a excluir cualquier estación individual (leave-one-station-out).
4. **El signo sobrevive** a excluir el mes con más operaciones.

Los cuatro son necesarios. (1) es una **cláusula de no vacuidad**: un backtest con cero
operaciones cumple (2), (3) y (4) por cuantificación sobre el vacío, que es el defecto que la
sesión A encontró en su R24 v1.

## 5. Desenlace declarado por adelantado si el margen se come la ventaja

**Exigido por la sesión A, y con razón.** Es un resultado posible y hay que escribirlo antes de
verlo:

> Si `tau_exec` con su margen deja **menos de 100 operaciones accionables**, o deja el PnL
> mediano en cero o negativo, el resultado es **LA ESTRATEGIA NO ES OPERABLE CON ESTE
> SUSTRATO**, y se publica tal cual.

No es un fallo de ejecución: es el límite de cinco meses de historia con una probabilidad que
no se puede calibrar por mercado. En ese caso **no** se prueban umbrales alternativos, ni se
relaja el margen, ni se amplía la rejilla de §3. La respuesta sería acumular periodo — el
colector ya corre en cron y cada día añade historia que no se puede recuperar hacia atrás (B-1).

## 6. Prohibiciones

- No se calcula ningún PnL antes de que este documento esté hasheado.
- No se cambian `tau_costes`, el margen, la rejilla de §3 ni los cuatro criterios de §4 tras ver
  resultados.
- No se evalúa `tau_exec` al precio cotizado.
- No se usa la calibración agregada para el margen.
- No se opera con dinero real: **gate D0 intacto**, y este documento no lo levanta.
- Si §4 falla, no se intenta una R21.2 hasta publicar por qué falló R21.

## 7. Limitaciones heredadas que todo informe debe repetir

`p_model` peor calibrada por mercado que en agregado y **no corregible** (B-12) · disponibilidad
de etiqueta **supuesta** a 24 h (B-4/D17) · `y` es cota inferior por muestreo horario · periodo
abril–septiembre 2026 acotado por el archivo deslizante (B-1) · coordenadas verificadas en 11 de
55 (D6) · 1 936 mercados en décimas fuera del universo · no transportable a leads > ~45 h (D2).
