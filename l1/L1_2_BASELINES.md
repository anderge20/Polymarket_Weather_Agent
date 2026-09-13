# LEVEL 1 · L1.2 — BASELINES

Ejecuta la §7 de `PREREG_LEVEL1.md`. **No se puntúa contra el target en esta etapa** —
deliberadamente: puntuar aquí invitaría a retocar las definiciones después de ver el número, y
el orden por etapas existe para impedirlo. El scoring es `L1.4`/`L1.5`. `D0-P` sigue BLOCKED.

---

# PARADA DE ETAPA — DOS DEFECTOS EN MI PROPIA PREINSCRIPCIÓN

El encargo dice *«detenerse si aparece un defecto metodológico»*. Aparecieron dos, **los dos en
la §7 que yo escribí**, y los dos se ven **sin mirar el target ni una vez**.

## Defecto 1 — EL SIGNO DE LA CORRECCIÓN DE SESGO

El error se define `e = obs − fc`. Si `E[e] = b > 0`, el pronóstico va **bajo**, y corregirlo
es **`f + b`**. La preinscripción decía `round(f − sesgo)`: **empuja al mismo lado que el
error.**

Medido sobre los pares pronóstico/observación (esto es L1.1, no scoring contra el contrato):

    lead 24, n = 95
      sin corregir     f        bias +0,0789   MAE 1,0137
      PREINSCRITO      f - b    bias +0,2867   MAE 1,0362     <- empeora las dos
      CORREGIDO        f + b    bias -0,1288   MAE 1,0303

Heredado de `n1_14.B4_fc_bias`, que hacía `masa(f - bias, [e - bias ...])`. **Llevaba ahí desde
la primera preinscripción y nadie lo miró, yo incluido.**

## Defecto 2 — `B4` Y `B4'` SON EL MISMO MODELO

«Corregir el punto y recentrar los residuos» es:

    f + b + (e − b)  =  f + e        identidad algebraica, no una eleccion

Comprobado numéricamente: **60 de 60** idénticos. **El pronóstico probabilístico ya lleva el
sesgo dentro, porque los errores empíricos lo llevan.** La distinción `B4` / `B4'` que declaré
era vacua; sólo parecía real *por culpa del defecto 1*.

## ENMIENDA, y por qué no es optimizar después de ver resultados

    B3   round(f + sesgo)                         <- signo corregido
    B4   masa empirica de round(f + e)            <- el probabilistico, sesgo incluido
    B4'  RETIRADO: es identico a B4

**El conjunto declarado pasa de SEIS modelos a CINCO.** Cuatro razones por las que esto no es
selección:

1. **No se ha puntuado nada contra `winning_outcome`** en ningún momento — ni antes ni después.
2. El defecto es **un signo**, visible desde la definición sola.
3. La corrección **empeora** a `B3` en MAE frente a no corregir (1,0303 contra 1,0137): si
   estuviera buscando favorecerme, iría en la otra dirección.
4. El número de comparaciones **baja**, no sube.

*Y una lectura que sale gratis y hay que registrar antes de puntuar: la corrección de sesgo
global no ayuda ni siquiera contra la observación. Es lo que L1.1 anticipó — el sesgo es
CONDICIONAL a la temperatura y una corrección global no lo captura.*

---

## VERIFICACIÓN DE BUENA FORMA (§8) — 16 comprobaciones, todas verdes

| | lead 24 | lead 9 |
|---|---|---|
| eventos · escaleras | 95 · `{11}` | 96 · `{11}` |
| toda `p ∈ [0,1]` | **0 fuera** | **0 fuera** |
| suman 1 dentro del evento, en los cinco | **0,00e+00** | **1,11e-16** |
| exactamente un `y = 1` por evento | ✔ | ✔ |
| un componente por banda del contrato | ✔ | ✔ |
| **el día objetivo nunca está en el entrenamiento** | ✔ (el más cercano es `td−3`) | ✔ (`td−2`) |
| última etiqueta de train **disponible** en `t_asof` | ✔ | ✔ |
| mínimo 20 pares de entrenamiento | ✔ (mín. real 20) | ✔ (mín. real 20) |

### PRUEBA EJECUTABLE DE NO-FUGA

No es una lectura del código: **se altera el futuro y se exige que nada cambie.** Se suman
+25 °C a **todas** las observaciones desde el 2026-06-23.

    47 eventos anteriores al corte:  NINGUNA probabilidad cambia          -> no hay fuga
    47 eventos posteriores:          SI cambian                            -> la prueba tiene poder

La segunda mitad importa tanto como la primera: **una prueba de no-fuga que pasa porque no
puede fallar no prueba nada.**

---

## CARACTERIZACIÓN, sin tocar el target

| modelo | lead | `p_max` medio | entropía | bandas con masa | `p=0` exactos | `p=1` exactos |
|---|---|---|---|---|---|---|
| `B0_clima` | 24 | 0,4184 | 1,6543 | 8,08 | 277 | 1 |
| `B1_persist` | 24 | **1,0000** | **0,0000** | **1,00** | 950 | 95 |
| `B2_fc_crudo` | 24 | **1,0000** | **0,0000** | **1,00** | 950 | 95 |
| `B3_fc_sesgo` | 24 | **1,0000** | **0,0000** | **1,00** | 950 | 95 |
| `B4_fc_prob` | 24 | 0,3444 | 1,6313 | 7,18 | 363 | 0 |
| `B0_clima` | 9 | 0,4143 | 1,6641 | 8,12 | 276 | 1 |
| `B4_fc_prob` | 9 | 0,3620 | **1,4678** | **6,33** | 448 | 0 |

*(entropía máxima de una escalera de 11 bandas: 2,3979)*

**Tres cosas que quedan registradas antes de puntuar:**

1. **`B1`, `B2` y `B3` son indicadores puros**: entropía 0, una sola banda con masa, 950 ceros
   y 95 unos exactos por lead. **Su Log Loss será aritmética de la constante de recorte**, no
   una medida de calibración — ya demostrado en A-280 y ahora visible en su estructura.
2. **`B4` se afila con el lead corto**: de lead 24 a lead 9, las bandas con masa bajan de
   **7,18 a 6,33** y la entropía de **1,631 a 1,468**. Es la mejor precisión del pronóstico a
   9 h propagándose a la distribución predictiva — **una comprobación interna coherente**, no
   un resultado.
3. **`B3` se separa de `B2`** en el **20,0 %** de los eventos a lead 24 y el **14,6 %** a
   lead 9. No son el mismo modelo, aunque la corrección sea pequeña.

---

## VEREDICTO DE ETAPA

**Buena forma verificada en las 16 comprobaciones, con la prueba de no-fuga ejecutada y con
poder.** La etapa se detuvo por dos defectos de mi propia preinscripción, **los dos corregidos
antes de puntuar nada**, y el conjunto de modelos queda en **cinco**.

Se puede pasar a **`L1.3` — FORECAST → P(YES)**.
