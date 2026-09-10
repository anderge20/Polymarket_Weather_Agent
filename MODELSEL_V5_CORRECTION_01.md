# MODELSEL V5 — CORRECCIÓN 01 · La frescura no es un confusor: es disponibilidad operativa

**Fecha:** 2026-09-06 · **Autor:** Claude en rol de revisor adversarial, sobre su propio informe
**Corrige:** `MODELSEL_V5_REPORT.md` §4 y §9 (sha del original: `6c3c2a66…`, se conserva)
**No corrige:** §1, §2, §3, §5, §6, §7, §8 — los contrastes, la categoría **B** y el universo
operativo se mantienen íntegros. Ninguna métrica se ha recalculado.

---

## 1. El error

`MODELSEL_V5_REPORT.md` §4 trató la diferencia de edad del run a 24 h (ICON 6 h, ECMWF 12 h)
como un **confusor** que impedía atribuir la ventaja a ICON, y §9 recomendó por ello la opción 5
(continuar investigación) con un experimento `same_run` a 24 h.

Ambas cosas son incorrectas. La comprobación que faltaba:

```
T = 2026-06-21T12:00Z   (lead 24 h, EFHK)
  ICON  run 2026-06-21T06:00Z  →  availability_safe_at 10:45Z   age 6 h
  ECMWF run 2026-06-21T00:00Z  →  availability_safe_at 08:46Z   age 12 h
```

Idéntico en los 69 eventos del estrato. La razón no es el muestreo: es la **latencia de
diseminación**. ICON publica ~4 h 45 min después de su run; ECMWF IFS025, ~8 h 46 min. A las
12:00Z el run de ECMWF de 06Z **todavía no existe** — llega hacia las 14:46Z.

A 9 h ambos modelos parten del run de 18:00Z con 9 h de edad: ahí la comparación ya es limpia,
y no hay nada que corregir.

## 2. Por qué el experimento V5.4 propuesto era inadmisible

Extraer ECMWF en el run de ICON (06Z) para decidir en T=12:00Z sería usar un pronóstico **no
publicado aún en el momento de la decisión**. Es exactamente la fuga que este proyecto verifica
con `test_no_future_information.py` y `test_no_lookahead_adversarial.py`, y que la disciplina
as-of de V2 existe para impedir.

**V5.4 queda retirada antes de redactarse.** No se ejecuta, no se gasta cuota.

Nota: la pregunta *física* —"¿es ICON mejor que ECMWF a igualdad de información?"— sigue siendo
legítima como ciencia, pero **no es la pregunta de M1**. M1 elige qué usar en producción, y en
producción no se dispone del run que no existe.

## 3. Consecuencia sobre §15 — la categoría B **no cambia**

La pregunta de §15 es si la ventaja procede de "ICON como familia de modelo". La respuesta sigue
siendo que no: parte de la ventaja a 24 h es **latencia**, no física del modelo, y la ventaja de
precisión sólo es concluyente en el régimen de resolución fina. **Categoría B confirmada.**

Lo que cambia es la recomendación §16, que es una decisión operativa y no una clasificación
científica: para el producto, la latencia **cuenta**. No se puede descontar una ventaja que el
sistema recibe realmente cada día.

## 4. Recomendación M1 rehecha — aplicando §17 tal como está congelado

§17 dice, literalmente y desde antes de ver ningún resultado:

> `run_age` se reporta por separado […] Sólo puede invocarse como criterio operacional
> **secundario** si la precisión queda prácticamente empatada — definido aquí como: el IC95 %
> de ΔMAE_res incluye 0 **y** |ΔMAE_res| < 0.05 °C.

Comprobación de la condición sobre el componente que domina el universo:

```
icon_global   IC95 = [−0.1982, +0.1214]   incluye 0      ✓
              |ΔMAE_res| = 0.0427  <  0.05 °C            ✓
```

**Las dos condiciones se cumplen exactamente.** El preregistro previó este caso y autoriza el
desempate por frescura. Aplicarlo no es cambiar criterios tras ver resultados (§18): es ejecutar
una regla congelada cuyo antecedente se ha verificado.

Decisión por componente, ponderada por el universo §14:

| Componente | % mercados | Precisión | Criterio aplicado | M1 |
|---|---:|---|---|---|
| `icon_eu` | 14.2 % | ICON mejor, CONCLUYENTE (IC excluye 0, LOSO estable) | §13 | **ICON** |
| `icon_global` | 75.1 % | empate estadístico (§17 se cumple) | §17 desempate por frescura: 6 h vs 12 h a 24 h; empate a 9 h | **ICON** |
| `icon_d2` | 10.7 % | INCONCLUSO_POR_DISEÑO (2 est); Δ = −0.111 a favor de ICON | coherencia + signo | **ICON** |

Los tres componentes apuntan a ICON, por vías distintas y declaradas. Y `icon_seamless` es
precisamente el producto que entrega D2/EU/GLOBAL por dominio de forma automática.

> ## **RECOMENDACIÓN M1 §16 — opción 1: `M1 = icon_seamless`**

Sustituye a la opción 5 del informe original.

### Qué NO afirma esta recomendación

- **No** afirma que ICON sea más preciso que ECMWF en el 75 % del universo. Ahí la precisión está
  empatada (IC incluye 0) y la elección se apoya en la regla §17, no en una ventaja medida.
- **No** afirma que la ventaja sea de la física del modelo. En `icon_eu` a 24 h es inseparable de
  la latencia; a 9 h, con runs iguales, el contraste es INCONCLUSO (Δ=−0.060).
- **No** se transporta a leads largos: `icon_seamless` cambia de componente con el horizonte
  (D2 sólo hasta ~+45 h).
- **No** cubre la heterogeneidad regional: dentro de `icon_global`, ASIA_SUR (Δ=+0.141) y HEM_SUR
  (Δ=+0.112 a 9 h, +0.294 a 24 h) tienen estimación puntual a favor de ECMWF, ninguna concluyente.
  Queda **declarado para vigilancia** y es candidato natural a un override por región en M2/M3.

### Reversibilidad y condición de revisión

Alta: M1 es una elección de configuración, no un cambio estructural. Se revisa si (a) alguna
región acumula evidencia concluyente a favor de ECMWF, o (b) cambian las latencias de
diseminación de cualquiera de los dos productos — es decir, si el antecedente de §17 deja de
cumplirse.

## 5. Lección de método

El error se produjo por tratar una propiedad del producto como un artefacto estadístico sin haber
comprobado antes `availability_safe_at`, que estaba en el propio dataset. La comprobación cuesta
una consulta. Regla que queda: **antes de declarar confusor una diferencia sistemática entre dos
fuentes, verificar si es una restricción operativa real del sistema.**
