# TAREA #63 — RESULTADO: LA CONDICIONAL DE A-259 ESTÁ REFUTADA, Y EL NÚCLEO CONGELADO TENÍA RAZÓN

Ejecuta `PREREG_N063_CONFLICTOS_VENTANA.md`, espejado a las 18:58:11Z **antes** de correr
nada (commit `b188267`). Guion: `n63_conflictos_ventana.py`. Salida íntegra:
`N063_SALIDA.txt`. Cero peticiones.

---

## 1. La reproducción, y por qué vale como verificación independiente

| | A-259 (desde `CATALOG_V2`) | #63 (desde `markets_v2` + regla A-275) |
|---|---|---|
| días etiquetables | 7 979 | **7 979** |
| estrictos | — | 62 |
| banda distinta | **39** (0,489 %) | **39** (0,489 %) |
| misma banda | 9 (inferido) | **9** |
| sin evento | **14** | **14** |

**El desglose coincide caso por caso desde dos fuentes distintas de escalera.** A-259 leyó
`CATALOG_V2`; esto lee `markets_v2` con la regla de población de A-275. Que den 39/9/14 por
separado es la comprobación más fuerte disponible de que la exposición está bien medida.

*Y para llegar ahí hubo que arreglar mi propio instrumento*: `n075_poblacion.particion()`
exige bandas de **enteros sueltos**, que es la forma de la escalera en Celsius. Las
estadounidenses son de **2 °F** (`'54-55°F'`), así que la prueba las rechazaba todas y las
12 estaciones en Fahrenheit salían `SIN_EVENTO_ELEGIBLE`. `particion_general` tesela
intervalos de anchura arbitraria y está **demostrada conservadora**: sobre los 7 331 eventos
de `markets_v2`, acepta 1 852 más y **rechaza 0** de los que la vieja aceptaba; y en EGLC las
dos poblaciones son **idénticas**, verificado antes de usarla. El primer resultado que
escribí decía 34/1/27 y era el instrumento, no los datos.

---

## 2. EL RESULTADO

    de los 39 dias con banda distinta y evento elegible:

      A_FAVOR_DE_CIVIL        38     la ganadora es la banda del maximo del DIA CIVIL COMPLETO
      A_FAVOR_DE_ESTRICTO      1     la ganadora es la banda del maximo del RESTO DEL DIA
      NINGUNA                  0

**38 de 39.** Y el único caso a favor del estricto es **EGLC 2026-05-27** — exactamente el
caso sobre el que construí toda la conjetura.

### La regla de decisión preinscrita, aplicada

> *«Al menos uno `A_FAVOR_DE_CIVIL` → la condicional queda REFUTADA.»*

No es uno: son **38**. **`WINDOW_LOCAL_CIVIL_DAY` del núcleo congelado —hora 00 INCLUIDA— es
la ventana que la fuente contractual usa, en 38 de 39 conflictos medibles.** El núcleo tenía
razón y yo llevaba cuatro entradas de decisiones sugiriendo lo contrario.

### La vía de escape también está cerrada

El preregistro contemplaba «mezcla → estratificar por `resolution_source`». Estratificado:

    www.wunderground.com   C   A_FAVOR_DE_CIVIL      33
    www.wunderground.com   C   A_FAVOR_DE_ESTRICTO    1
    www.wunderground.com   F   A_FAVOR_DE_CIVIL       5

**Los 39 son de la MISMA fuente**, y dentro de la misma fuente y la misma unidad el marcador
es 33 a 1. No hay estratificación que salve la conjetura.

---

## 3. Y ENTONCES ¿QUÉ ES EGLC 2026-05-27? NO ES LA VENTANA: ES LA SERIE

Recalculado desde el tarball, las dos series del mismo día:

    rt3   (METAR de cuerpo)   24 obs   max dia civil 24   a las 00:50, 13:50 y 14:50 (EMPATE)
                                       max h0 24   max resto 24
    rt34  (+ grupo T, produccion)  48 obs   max dia civil 25   a las 00:20 (UNICO)
                                       max h0 25   max resto 24

    banda ganadora declarada: 24 C

* **Con la serie tipo 3 el día resuelve BIEN bajo la ventana civil completa** — y ni siquiera
  está expuesto, porque el máximo empata a las 00:50, 13:50 y 14:50.
* **Con la serie de producción (RT34) aparece un 25 a las 00:20** que no existe en la otra
  serie y que la fuente contractual no recoge.

> **La causa es la SERIE, no la VENTANA.** El instante ofensivo cae en la hora 00, y eso es
> lo que me hizo mirar la ventana; pero la ventana es incidental — con la misma ventana y la
> otra serie el día resuelve correctamente, y con la misma serie y otros 38 días la ventana
> acierta.

**Conflictos atribuibles a la VENTANA: 0 de 39.** Conflictos de etiqueta: 1 de 39, y su causa
está medida y es otra.

---

## 4. Qué queda en pie y qué se retira

| afirmación | estado |
|---|---|
| A-257 · 3,56 % de exposición | ya corregida por A-258 |
| A-258 · 0,80 % | ya corregida por A-259 |
| A-259 · **0,489–0,664 % de días etiquetables** | **EN PIE como cota de EXPOSICIÓN**, reproducida caso por caso desde otra fuente |
| A-259 · *«condicionada a que la fuente contractual excluya la primera hora»* | **REFUTADA**, 38 contraejemplos de la misma fuente |
| A-247 · *«lo que refuta A-246 no es el arreglo: es la VENTANA»* | **RETIRADA la atribución.** Lo que produce el desajuste del 2026-05-27 es el arreglo de serie del #49, en un instante que está en la hora 00 |
| `WINDOW_LOCAL_CIVIL_DAY` del núcleo congelado | **VALIDADO contra resoluciones reales, 38 de 39.** No se toca — y ahora por evidencia, no por estar congelado |

**La cota que importa para liquidar ya no es 0,489 %.** Es:

    conflictos de etiqueta contra la resolucion   1 de 7 979 dias etiquetables = 0,0125 %
    de ellos, atribuibles a la ventana                             0
    de ellos, atribuibles a la serie                               1  (medido, §3)

---

## 5. Lo que este resultado NO dice

* **No mide la fuente contractual directamente.** Compara nuestra reconstrucción con lo que
  UMA liquidó. Un acuerdo en 38 casos es evidencia fuerte de que la ventana coincide; no es
  una lectura del reglamento de Wunderground.
* **No cubre nada fuera de 2026-04-09 → 2026-09-05** ni las 14 combinaciones
  estación-día sin evento elegible.
* **n = 1 para la rama estricta.** Si mañana aparecieran más casos como el 05-27, lo que
  cambiaría es la magnitud del problema de SERIE, no la conclusión sobre la ventana.
* **No dice que la serie RT34 sea peor.** A-246/A-247 midieron que el cambio del #49 corrige
  19 días y falla 1. Sigue siendo el cambio correcto; lo que se retira es la explicación que
  di del fallo restante.
