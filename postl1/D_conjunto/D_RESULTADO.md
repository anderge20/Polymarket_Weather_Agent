# D — ANÁLISIS CONJUNTO LONDRES + RKSI · RESULTADO

**`POOLED CONFIRMED` (lead 9)** · 2026-09-13T22:55Z · sesión A
Preregistro `bfd7cb0`, escrito y espejado **antes** de calcular nada. 0 peticiones.

`D0` abajo · `D0-P = BLOCKED` · `L2 = BLOCKED`.

---

## 0 · LO PRIMERO: MI PROPIA HIPÓTESIS QUEDÓ REFUTADA POR MI PROPIO TEST

El §3 del preregistro decía, con los números delante:

> *"En RKSI el benchmark `S3` está mejor entrenado (+21 %) y el modelo `B4` peor (−18 %)
> que en Londres. Las dos asimetrías empujan `B4 − S3` hacia cero en RKSI. El 0,76× de
> magnitud no es evidencia de que el fenómeno sea más débil en Seúl."*

Era una conjetura cómoda: explicaba la debilidad de la réplica sin culpar a la réplica.
**C1 la refuta.**

    lead 9    EGLC completo  (138 dias)  n=96   -0,01181
              EGLC RECORTADO ( 95 dias)  n=57   -0,01257   n_train mediana 47
              RKSI           ( 95 dias)  n=74   -0,00892   n_train mediana 56

Londres recortado a la ventana exacta de RKSI **no se acerca a RKSI: se aleja.** Y lo
hace con **menos** entrenamiento que RKSI (mediana 47 frente a 56) y con **menos**
eventos (57 frente a 74). La asimetría de información no explica nada.

> **La diferencia entre las dos ciudades es DE CIUDAD.** Escrito antes de mirar, leído
> como decía la regla, y en contra de lo que yo había supuesto media hora antes.

*(C1a — los 95 días más recientes de EGLC — y C1b — el calendario exacto de RKSI —
resultaron ser **el mismo recorte**, porque las dos ventanas terminan el 2026-08-23. Se
midió una vez y responde a las dos. No son dos confirmaciones.)*

---

## 1 · REPRODUCCIÓN DE LOS CUATRO NÚMEROS DE PARTIDA

    EGLC lead 24  n= 95  -0,00605  publicado -0,00605  REPRODUCE   escaleras {11: 95}
    EGLC lead  9  n= 96  -0,01181  publicado -0,01181  REPRODUCE   escaleras {11: 96}
    RKSI lead 24  n= 73  -0,00485  publicado -0,00485  REPRODUCE   escaleras {11: 73}
    RKSI lead  9  n= 74  -0,00892  publicado -0,00892  REPRODUCE   escaleras {11: 74}

**Esta guarda ya se ganó el sueldo.** En su primera ejecución paró el análisis: el lead 24
de Londres que yo había escrito era `−0,00614` y el real es `−0,00605`. Transcribí un
`−0,0061` de una tabla redondeada y **me inventé el quinto decimal**. Corregido en
`faseC_scoring.py`, en `FASE_C_RESULTADO.md` y en A-298. Nada se mueve (0,79× → 0,80×),
pero una cifra inventada en un artefacto publicado es una cifra inventada.

*Regla que se queda: un número de partida que no se recalcula desde los datos antes de
usarlo no es un dato, es una cita.*

---

## 2 · GATE DE COMPARABILIDAD

| | resultado |
|---|---|
| **C1 ventana** | no bloquea. La diferencia es de ciudad, no de ventana (§0). |
| **C2 escalera** | los cuatro corpus son **exclusivamente n = 11**. No se agrega entre tamaños. |
| **C3 availability** | EGLC → ICON-D2, cota **trasladada** de ICON-GLOBAL y con **una** medición de dominio. RKSI → ICON-GLOBAL, cota **directa**, dos fechas por dos canales. **No es la misma calidad de evidencia.** |
| **C4 clima** | marítimo templado contra monzónico continental. **No equiparable, y no se intenta.** |
| **C5 independencia** | mismo proveedor (ICON) y misma plataforma (Polymarket). **No son réplicas independientes en sentido fuerte: comparten modo de fallo.** |

---

## 3 · ESTIMADOR CONJUNTO — `lead 9`, PRIMARIO

    pesos                        EGLC 0,552 · RKSI 0,448
    analitico (efectos fijos)    theta -0,01051   IC95 [-0,01367, -0,00736]
    bootstrap jerarquico         theta -0,01051   IC95 [-0,01369, -0,00732]   <- manda
    pool ingenuo (control)       media -0,01055   IC95 [-0,01377, -0,00737]   n=170
    heterogeneidad               Q 0,798 (gl 1, p 0,372)   I2 0,0 %   -> AGREGABLE

El bootstrap jerárquico y el analítico coinciden hasta el quinto decimal, y el pool
ingenuo también. Con `I² = 0 %` las dos ciudades son compatibles con un efecto común —
**y con k = 2 eso es lo más que se puede decir: `Q` aquí sólo podía invalidar.**

### El pooling pasa las mismas pruebas que pasaron las partes

    quitando el  5 % mas favorable de cada ciudad   n=161  -0,00790  [-0,01061, -0,00500]  sigue
    quitando el 10 % mas favorable de cada ciudad   n=153  -0,00605  [-0,00880, -0,00340]  sigue
    quitando el 20 % mas favorable de cada ciudad   n=136  -0,00282  [-0,00539, -0,00032]  sigue

    una ciudad fuera (k=2: es cada ciudad sola)
       solo EGLC  n=96  -0,01181  [-0,01597, -0,00763]
       solo RKSI  n=74  -0,00892  [-0,01382, -0,00433]

**Aquí el conjunto sí arregla algo real:** RKSI sola moría al quitar 10 eventos; el
conjunto aguanta hasta el 20 %. No es magia, es `n`: 170 eventos en vez de 74. Era el
beneficio legítimo que el preregistro autorizaba a buscar.

---

## 4 · `lead 24` — SECUNDARIO EXPLORATORIO, Y NO DESBLOQUEA NADA

    theta -0,00541   IC95 [-0,00877, -0,00199]   Q 0,124 (p 0,725)   I2 0,0 %

Ocurrió exactamente lo que el §6 del preregistro anticipó: **dos resultados que no
alcanzaron su criterio de potencia (0,87 y 0,74) se combinan en uno que excluye el cero.**

Está escrito de antemano que eso no cuenta. Cambiar la unidad de análisis hasta que el
criterio se cumpla es la maniobra que §21 de la Fase C prohíbe, y que sea estadísticamente
razonable en general no la hace admisible **aquí**, donde el umbral de potencia se escribió
antes y se aplicó a los dos. **`lead 24` sigue `INCONCLUSIVE`.**

---

## 5 · UNA REGULARIDAD QUE APARECE EN LAS DOS CIUDADES Y NO TENGO MECANISMO PARA ELLA

| | 1.ª mitad | 2.ª mitad |
|---|---|---|
| EGLC lead 9 | −0,01089 | −0,01272 |
| RKSI lead 9 | −0,00302 *(incluye el cero)* | −0,01482 |
| EGLC lead 24 | −0,00242 *(incluye el cero)* | −0,00959 |
| RKSI lead 24 | −0,00052 *(incluye el cero)* | −0,00907 |

Y en la misma dirección: EGLC recortado a los 95 días **finales** da −0,01257, más fuerte
que los 138 completos.

**En los cuatro casos el efecto es mayor en el tramo más reciente.** No propongo un
mecanismo — no tengo ninguno medido, y elegir uno ahora sería inventarlo. Queda anotado
como lo que es: una regularidad que la especificación de `L2` tendrá que mirar de frente,
porque si el efecto depende del calendario, un backtest sobre el corpus entero lo
promedia y un sistema en vivo no vive en el promedio.

---

## 6 · VEREDICTO

Contra el criterio escrito en `PREREG_ANALISIS_CONJUNTO.md` §8, **antes** de ver el número:

| condición | |
|---|---|
| `theta < 0` | ✔ −0,01051 |
| IC95 excluye el cero | ✔ [−0,01369, −0,00732] |
| **las dos** ciudades con `d_c < 0` individualmente | ✔ −0,01181 y −0,00892 |
| `Q` no significativo | ✔ p 0,372 · I² 0 % |
| sobrevive quitar el 10 % más favorable | ✔ −0,00605 [−0,00880, −0,00340] |

> # `POOLED CONFIRMED` (lead 9)

### Y lo que esto NO es

**No abre `L2`.** `L2` es *economic edge*: necesita precios, spreads, fees, profundidad y
ejecutabilidad, y **nada de eso está en este análisis**. `D0-P` sigue `BLOCKED`.

Lo único que `POOLED CONFIRMED` produce es **la autorización para ESPECIFICAR `L2`**, que
tendrá su propio preregistro y su propio gate. **`D0` sólo lo levanta el usuario.**

Y el recordatorio que el preregistro obligaba a repetir aquí: **dos ciudades no son dos
observaciones independientes.** Comparten proveedor de pronóstico (ICON) y plataforma
(Polymarket). Un fallo en cualquiera de los dos se manifestaría en las dos ciudades a la
vez y este análisis no lo distinguiría de una señal.

---

## 7 · LO QUE HAY QUE LLEVARSE A LA ESPECIFICACIÓN DE `L2`

1. **El efecto es de magnitud pequeña.** −0,0105 de Brier por evento sobre un benchmark
   estructural que ya vale 0,078. Que sea estadísticamente distinto de cero **no dice
   nada** sobre si sobrevive a fees y spread: eso es precisamente lo que `L2` mide, y R21
   ya midió una vez que Strategy A **no era operable** porque el mercado está mejor
   calibrado que el modelo.
2. **La concentración temporal (§5).**
3. **La traslación de availability en Londres (C3, tarea #75)**, que afecta a la mitad de
   mayor peso del conjunto (0,552).
4. **La no-independencia (C5).**
