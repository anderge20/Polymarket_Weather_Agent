# POST-FASE C · D — PREREGISTRO DEL ANÁLISIS CONJUNTO LONDRES + RKSI

**Escrito y espejado ANTES de calcular un solo número conjunto.** Sesión A, 2026-09-13.

`D0` abajo · `D0-P = BLOCKED` · `L2 = BLOCKED`. Cero precios, cero EV, cero PnL, cero
order book, cero ejecución, cero dinero real. **Presupuesto de ingesta: 0 peticiones.**
Todos los datos ya están en el almacén; este análisis no toca ningún proveedor.

---

## 1 · POR QUÉ EXISTE ESTE DOCUMENTO

§18-A del encargo de la Fase C: *"una réplica positiva no abre L2 automáticamente.
Primero hay que combinar la evidencia de Londres + RKSI mediante un análisis previamente
justificado."* Y §21: *"No utilizar pooling para convertir una réplica negativa en
resultado positivo."*

Con **k = 2 ciudades**, un meta-análisis no es gran cosa: τ² no es estimable con dos
estudios y cualquier «efectos aleatorios» sería teatro. **Lo que se puede hacer
honestamente es una media ponderada por precisión, declarada de antemano, con una
comprobación de heterogeneidad que sólo puede invalidarla, nunca confirmarla.** Se dice
aquí para que nadie lo lea como más de lo que es.

---

## 2 · LO QUE YA ESTÁ MEDIDO Y NO SE VUELVE A TOCAR

    lead 9    EGLC   B4-S3 = -0,01181   n=96   efecto/MDE 1,95   [A-293, Fase A]
              RKSI   B4-S3 = -0,00892   n=74   efecto/MDE 1,33   [A-298, Fase C]
    lead 24   EGLC   B4-S3 = -0,00605   n=95   efecto/MDE 0,87   INCONCLUSIVE
              RKSI   B4-S3 = -0,00485   n=73   efecto/MDE 0,74   INCONCLUSIVE

Los cuatro son del mismo estrato de escalera (**n = 11**), la misma métrica (Brier por
evento), el mismo benchmark (`S3`), la misma semilla y el mismo bootstrap clusterizado
por evento. **Ninguno se recalcula.**

---

## 3 · LA ASIMETRÍA QUE HAY QUE MIRAR ANTES DE JUNTAR NADA

Medido hoy, y es lo que motiva la mitad de este preregistro:

| | historial de `S3` (mediana) | entrenamiento de `B4`, `n_train` (mediana) |
|---|---|---|
| **EGLC** lead 9 | 122 eventos | **68 días** |
| **RKSI** lead 9 | **148 eventos** | **56 días** |

En RKSI el **benchmark está mejor entrenado** (+21 %) y el **modelo peor entrenado**
(−18 %) que en Londres. **Las dos asimetrías empujan `B4 − S3` hacia cero en RKSI.**

> Es decir: el 0,76× de magnitud **no es evidencia de que el fenómeno sea más débil en
> Seúl.** Es compatible con eso y es igual de compatible con que la ventana de RKSI sea
> 95 días en vez de 138. **No sé cuál de las dos es, y no lo voy a saber sin medirlo.**

Ésa es la razón por la que la comparabilidad se comprueba **antes** del pooling y no
después: si se mira el número conjunto primero, cualquier diagnóstico posterior se
convierte en una explicación elegida.

---

## 4 · GATE DE COMPARABILIDAD — se ejecuta ANTES del pooling y puede bloquearlo

### C1 · Ventana equiparada (el diagnóstico que decide si el 0,76× significa algo)

Recortar **Londres** a una ventana de **95 días** y recalcular `B4 − S3` en lead 9, con
TODO lo demás idéntico. Dos recortes, los dos declarados aquí:

* **C1a — misma longitud, tramo más reciente**: los 95 días finales de la ventana de
  EGLC. Es la misma regla de recorte que la `ENMIENDA_VENTANA_FASE_C` aplicó a RKSI.
* **C1b — mismo calendario**: EGLC restringido a `2026-05-21 … 2026-08-23`, las fechas
  exactas de RKSI. Controla estación del año además de longitud.

**Regla de interpretación, escrita ahora:**

| resultado de C1 | lectura |
|---|---|
| Londres recortado cae hacia ≈ −0,009 | la diferencia entre ciudades es en buena parte **de ventana**, no de ciudad. El pooling gana sentido. |
| Londres recortado se queda en ≈ −0,012 | la diferencia **sí** es de ciudad. El pooling sigue permitido pero el informe tiene que decir que las dos ciudades no rinden igual. |
| Londres recortado cambia de signo o se dispara | **BLOQUEA el pooling**: si el efecto de Londres depende tanto de la ventana, no es una cantidad que se pueda promediar. |

**C1 no sustituye ni modifica el resultado publicado de Londres** (`-0,01181`, n=96).
Es un diagnóstico; el número de registro sigue siendo el de la ventana completa.

### C2 · Estrato de escalera
Los dos corpus puntuables son **exclusivamente n = 11**. Ya verificado. Si al reejecutar
apareciera otro tamaño, **se para**: A-280 prohíbe agregar entre escaleras.

### C3 · Availability
EGLC lo sirve **ICON-D2**; RKSI, **ICON-GLOBAL**. La cota `L_MAX = 4,76 h` es una
medición de `dwd_icon` (GLOBAL): **directa para RKSI, trasladada para Londres** (tarea
#75). La dirección es conservadora en los dos casos — retrasa `available_at`, hace perder
información, nunca filtrarla — pero **no es la misma calidad de evidencia y el informe
conjunto tiene que decirlo en el cuerpo, no en una nota al pie.**

### C4 · Régimen climático
No se puede equiparar y **no se intenta**. Londres marítimo templado, Seúl monzónico
continental. Queda como limitación declarada. *Que dos climas distintos den el mismo
signo es precisamente el interés del ejercicio; fingir que son comparables sería
destruirlo.*

### C5 · Independencia
Las dos ciudades comparten **modelo de proveedor** (ICON) y **plataforma** (Polymarket).
No son replicaciones independientes en el sentido fuerte: comparten un modo de fallo. Se
declara aquí y se repite en el veredicto.

---

## 5 · EL ESTIMADOR CONJUNTO — declarado, no elegido después

**Primario — media ponderada por precisión (efectos fijos), sólo `lead 9`:**

    w_c   = 1 / se_c^2          se_c = sd_c / sqrt(n_c)   (sd sobre las diferencias por evento)
    theta = sum(w_c * d_c) / sum(w_c)
    se    = sqrt(1 / sum(w_c))
    IC95  = theta -+ 1,96 * se

**Secundario — bootstrap jerárquico**, 10 000, semilla `20260913`: en cada réplica se
remuestrean **los eventos dentro de cada ciudad** (cluster por evento, como siempre) y se
recombina con los mismos pesos. Es el que manda si discrepa del analítico, porque no
supone normalidad.

**Control — pool ingenuo**: concatenar los 170 eventos y tratarlos como uno solo. **Se
reporta y NO se usa para decidir**: deja que la ciudad con más eventos pese más por
tamaño en vez de por precisión.

**Heterogeneidad**: `Q` de Cochran con 1 grado de libertad e `I²`. Con k = 2 esto **sólo
puede invalidar**, nunca confirmar: si `Q` es grande, el promedio no representa a ninguna
de las dos y el veredicto conjunto pasa a `NO AGREGABLE`.

---

## 6 · `lead 24` NO ENTRA EN EL PRIMARIO, Y LA RAZÓN IMPORTA

Los dos leads 24 son **INCONCLUSIVE por potencia** (0,87 y 0,74), del mismo signo.
Juntarlos daría casi con seguridad un IC que excluye el cero.

**Eso es exactamente la maniobra que §21 prohíbe**: dos resultados que no alcanzaron su
criterio preinscrito no se convierten en uno que sí, cambiando la unidad de análisis.
Que la maniobra sea estadísticamente legítima en general no la hace legítima **aquí**,
donde el criterio de potencia se escribió antes y se aplicó a los dos.

`lead 24` se calcula, se reporta **etiquetado como SECUNDARIO EXPLORATORIO**, y
**no puede desbloquear nada por sí solo**. Se escribe ahora para que no parezca una
decisión tomada al ver el número.

---

## 7 · EL POOLING TIENE QUE PASAR LAS MISMAS PRUEBAS QUE PASARON LAS PARTES

Un promedio no arregla fragilidad. Sobre el conjunto de eventos de las dos ciudades:

* **influencia** — quitar el 5 %, 10 % y 20 % de eventos más favorables (del conjunto,
  proporcionalmente por ciudad) y rehacer el estimador;
* **estabilidad temporal** — mitades por fecha dentro de cada ciudad;
* **una ciudad fuera** — el *leave-one-city-out* con k = 2 es simplemente cada ciudad
  sola: se reporta como recordatorio de que el conjunto no añade una tercera observación.

---

## 8 · VEREDICTO — escrito antes, no se retoca al ver el número

| | condición |
|---|---|
| **`POOLED CONFIRMED`** | `theta < 0` · IC95 excluye el cero · **las dos** ciudades con `d_c < 0` individualmente · `Q` no significativo · sobrevive quitar el 10 % más favorable |
| **`NO AGREGABLE`** | `Q` significativo o C1 dispara el bloqueo: el promedio no representa a ninguna |
| **`POOLED INCONCLUSIVE`** | IC95 incluye el cero, o cae al quitar el 10 %, o una ciudad tiene signo contrario |

### Y lo que `POOLED CONFIRMED` NO significa

**No abre `L2`.** `L2` es *economic edge* y necesita precios, spreads, fees y
ejecutabilidad: nada de eso está en este análisis, y `D0-P` sigue `BLOCKED`. Lo máximo
que `POOLED CONFIRMED` puede producir es **la autorización para especificar `L2`**, que a
su vez tendrá su propio preregistro y su propio gate. **`D0` sólo lo levanta el usuario.**

---

## 9 · LO QUE ESTÁ PROHIBIDO EN ESTE ANÁLISIS

* buscar una tercera ciudad (§23 de la Fase C: la réplica no falló, buscarla sería *city
  shopping*);
* recalcular `B4`, `S3`, `MIN_TRAIN`, `epsilon`, la ventana de RKSI o la de Londres;
* meter los 9 días de observación de RKSI que quedaron fuera de la ventana congelada;
* cambiar el estimador después de ver el resultado del primario;
* quitar eventos porque empeoren el resultado;
* presentar `lead 24` conjunto como si fuera el primario.
