# NIVEL 1 — RESULTADO

**Pregunta única, y la única que este documento contesta:**

> ¿Existe poder predictivo meteorológico real en los datos disponibles **antes** de
> `prediction_time`?

**Fecha: 2026-09-13. Autor: Claude (sesión A). Estado: RESULTADO PROVISIONAL — ver §7.**

> **No se usa aquí el lenguaje de EDGE ni de ventaja económica.** Este nivel no habla de
> rentabilidad, de mercado ni de ejecución. **El veredicto anterior de fase — `LONDRES =
> NO EDGE MEDIDO` — no se modifica y no se comenta.**

---

## 1. CLASIFICACIÓN: **D — INCONCLUSO**

**No por falta de señal, sino por falta de sustrato: el corpus sobre el que se puede
evaluar tiene n = 19 eventos, y el criterio preregistrado exige el resultado en LOS DOS
leads.** Con 19 eventos lo cumple en uno y no en el otro.

No es A (sin poder): los indicios apuntan en la dirección contraria. No es B ni C: el
criterio preregistrado **no se cumple**, y no se cambia un criterio después de ver el
resultado.

## 2. Lo que SÍ está medido y se sostiene

Todo esto es descriptivo, ex-ante y reproducible; no depende del corpus roto:

| magnitud | lead 24 h | lead 9 h |
|---|---|---|
| MAE del pronóstico contra el máximo observado | **0,953 °C** | **0,839 °C** |
| sesgo | +0,042 | −0,015 |
| cobertura del intervalo declarado (nominal 80 %) | 83,5 % | 85,2 % |

- **El error es homoscedástico en temperatura**: `corr(pronóstico, |error|) ≈ −0,02`. No
  hay tramo térmico donde el modelo sea sistemáticamente peor.
- **La incertidumbre declarada es casi una constante** (desviación típica de la anchura
  0,200 sobre una media de 3,818) y **apenas predice el error**. Y `forecast_p10..p90`
  **son nuestro propio modelo M2**, no la incertidumbre nativa del proveedor.
- **La corrección de sesgo no ayuda**: B4 no mejora a B3 de forma consistente.
- **Temporalidad**: con `L_MAX = 4,76 h` el margen es de 1,24 h en lead 24 y 4,24 h en
  lead 9; el acantilado está en `L_MAX = 6,00 h` (118/236 → 0/236). **Ningún pronóstico
  usado se publicó después de su `prediction_time`.**

## 3. El criterio preregistrado, y qué dio

> CONFIRMA (nivel B): B3 o B4 mejoran a B0 en Brier por evento con IC95 bootstrap por
> evento que **EXCLUYE el cero**, **EN LOS DOS LEADS**. REFUTA: el intervalo incluye el
> cero en cualquiera de los dos.

    lead 24 h   n=19   B3 - B0  -0,01432   IC95 [-0,02988, +0,00109]   incluye el cero
    lead  9 h   n=20   B3 - B0  -0,03060   IC95 [-0,04629, -0,01535]   EXCLUYE el cero

**No se cumple.** La dirección es la buena en los dos leads —B3 y B4 baten a B0 en media—
pero en lead 24 el intervalo toca el cero.

Y las líneas base se comportan como tienen que comportarse, que es la única señal barata
de que la maquinaria discrimina: **B1 (persistencia) sale claramente PEOR que la
climatología** (+0,079 y +0,076, los dos excluyendo el cero).

## 4. Por qué n = 19 y no 119

**La primera respuesta a esta pregunta fue `C — PODER FUERTE`, y la retracté.** La ventaja
entera venía de eventos **cuya banda ganadora no está en los datos**: el Brier por evento
promediado sobre bandas lejanas, todas con verdad 0, omite el único término que importa,
`(q_verdadera − 1)²`. Restringido a eventos completos, **el criterio refuta**.

**La causa está localizada y no es de Polymarket.** Los mercados existen en Polymarket y
existen en nuestro propio catálogo en disco; el corte está **entre el catálogo y la tabla
`markets`**, en el backfill histórico de precios, que seleccionaba **los 3 mercados de
menor `market_id` por fecha** y arrastró esa selección a `markets` y `outcomes` a través
de una puerta que exigía precio. Verificado: **el conjunto guardado es exactamente el
prefijo de menor id de la escalera en 160 de 160 eventos**.

## 5. Un resultado propio que salió por el camino

De los 119 eventos con escalera completa y ganadora declarada, **15 (12,6 %) tienen hoy
una etiqueta nuestra que contradice la banda que el mercado pagó — las 15 por debajo y las
15 por exactamente 1,0 °C, ninguna por encima.**

No es un desajuste de fuente: unilateral y cuantizado en un grado entero es **un máximo
que se quedó bajo**. La causa está identificada (el filtro de tipo de reporte tiraba los
METAR rutinarios de :20) y arreglada en un PR pendiente de fusionar.

**Y hay un caso en sentido contrario, uno solo de 147**: el 2026-05-27, donde el máximo
del día civil local es el calor sobrante del día anterior —25 °C a las 00:20 locales tras
un día de 34— y el mercado resolvió por el máximo diurno. Ese no es un problema de la
serie: **es la ventana**, y queda registrado como la primera observación que separa
`WINDOW_LOCAL_CIVIL_DAY` de una resolución real.

## 6. Bloqueos de sustrato que este nivel NO puede resolver

- **No hay libro en el periodo del backtest**: el libro va del 09-09 al 09-13 y el
  backtest del 04-11 al 08-23. **Solapamiento cero.**
- **Un solo modelo meteorológico.**
- **La revisión sólo es utilizable en lead 9.**
- **No hay observaciones intradía.**
- **No hay lado corto ejecutable.**

Los cinco afectan a niveles posteriores, no a la pregunta de este documento.

## 7. Por qué es PROVISIONAL, y qué lo cerraría

La reparación del corpus está especificada, preinscrita y **no cuesta ni una petición de
red para los mercados**: `fase2/PREREG_NIVEL1_REEJECUCION.md` (población y criterio, sin
tocar el criterio) y `fase2/PREREG_PRESUPUESTO_IEM.md` (techo de 200 peticiones, sólo
EGLC, parada dura ante 429).

**Tras la reparación, n pasa de 19 a 119**, con escalera completa y ganadora declarada por
el mercado en los 119. El criterio se reejecuta **sin modificarlo** y con la misma semilla.

**Si con 119 eventos el intervalo de lead 24 sigue tocando el cero, la respuesta es A o D
y se dirá así.** No se cambiará el criterio, ni la población, ni el lead, ni el
estadístico. *El objetivo no es que salga B.*
