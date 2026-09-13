# L1.7 — FINAL RED TEAM · DECLARACIÓN DE ATAQUES

**Escrita y espejada ANTES de ejecutarlos.** Se declaran **cinco** ataques, se ejecutan **los
cinco** y se reportan **todos**, salgan como salgan. No se ejecutan ataques adicionales buscando
uno que pase. No se busca edge, precio ni PnL; producción sin tocar; `D0-P` = BLOCKED. **No se
emite el veredicto**: eso es L1.8.

Los diez riesgos de `PREREG_LEVEL1.md` §19 ya cubiertos en L1.4–L1.6 (look-ahead, leakage,
estacionalidad, escalera, dependencia intra-evento, calibración sobre el test, selección
post-hoc, revisiones, múltiples comparaciones) **se resumen**; lo que sigue son ataques
**nuevos**, a canales que nadie ha mirado todavía.

## A1 — GEOMETRÍA DE LA ESCALERA (el ataque más serio que se me ocurre)

**La escalera la elige el mercado**, presumiblemente centrada en SU expectativa de temperatura.
Si la ganadora tiende a caer cerca del centro de la escalera, **un modelo que concentre masa en
el centro bate al uniforme SIN NINGUNA habilidad meteorológica propia**.

**Control declarado `CTRL_escalera`**: distribución que **ignora por completo el pronóstico** y
sólo usa la geometría — masa concentrada en la banda central de la escalera, con la misma
dispersión media que `B4`. **Es un CONTROL, no un modelo**: no compite, sólo atribuye.

*Si `CTRL_escalera` bate al uniforme por un margen comparable al de `B4`, la ventaja de `B4` es
en parte geometría de la escalera y hay que descontarla.*

## A2 — BANDAS ABIERTAS CONTRA INTERIORES

Las bandas `≤ k` y `≥ m` son **abiertas** y absorben toda la cola. Si la ventaja de `B4` vive en
acertar la banda abierta, es un efecto de partición, no de pronóstico. Se separa el resultado
según **dónde cayó la ganadora**: abierta inferior · interior · abierta superior.

## A3 — MÚLTIPLES COMPARACIONES, contadas de verdad

Se enumeran **todas** las comparaciones con IC hechas en L1.4–L1.6 y se aplica una corrección
de Bonferroni sobre la primaria. **Se cuenta todo lo ejecutado, no lo reportado.**

## A4 — FUGA POR LA ESCALERA HACIA EL TARGET

¿Sabe la escalera algo del resultado que el pronóstico no sepa? Se mide la correlación entre el
**centro de la escalera** y la **temperatura observada**, y se compara con la del pronóstico.
Si la escalera predice mejor que nuestro pronóstico, el mercado lleva información que nosotros
no tenemos — **relevante para L2, y aquí sólo se mide**.

## A5 — ROBUSTEZ AL MÍNIMO DE ENTRENAMIENTO

`MIN_TRAIN = 20` es un parámetro preinscrito. Se recalcula el resultado con **20, 30, 40 y 50**
y **se reportan los cuatro**. *No se elige ninguno: es una comprobación de robustez, y si el
resultado depende del valor, eso es el hallazgo.*

## Gate

Si un ataque revela un defecto que invalide el resultado: **`LEVEL 1 = BLOCKED`**. Si sólo
acota o matiza: se documenta y `L1.7 = CLOSED` con la limitación pegada.
