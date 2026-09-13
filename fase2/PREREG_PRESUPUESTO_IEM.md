# PREINSCRIPCIÓN — presupuesto de peticiones a IEM para rehacer las observaciones de EGLC

**Escrita el 2026-09-13, ANTES de ejecutar nada.** Claude (sesión A). Registro: A-252.

## 1. Por qué

Dos razones distintas, y conviene no mezclarlas:

1. **CORRECCIÓN.** El PR #49 arregla `REPORT_TYPE`: el tipo 3 solo tiraba los METAR
   rutinarios de :20 y el máximo diario salía bajo. Medido contra la resolución del
   mercado: **15 de 119 eventos (12,6 %) tienen hoy una etiqueta que contradice la
   banda que el mercado pagó, las 15 por debajo y las 15 por exactamente 1,0 °C**
   (A-246). Esas etiquetas hay que rehacerlas, o el NIVEL 1 entrena su modelo de error
   y su climatología sobre días que sabe mal.
2. **COBERTURA.** De los 187 eventos EGLC del catálogo con ganadora única, **119 tienen
   observación y 68 no** — y la cobertura actual (2026-04-08 → 2026-08-23, 118 días) la
   fijó el universo recortado del backfill de precios, no ninguna decisión (A-244).

## 2. Presupuesto, y qué NO se hace

| concepto | número |
|---|---|
| días-estación a reingestar con tipos 3+4 (los ya cubiertos) | **118** |
| días-estación nuevos, para los 68 eventos sin observación | **≤ 70** |
| **techo total de peticiones a IEM** | **200** |
| estaciones | **sólo EGLC** |
| concurrencia | **1** (secuencial) |
| pausa entre peticiones | **≥ 1,0 s** |

**Parada dura:** cualquier `429`, cualquier error HTTP repetido dos veces sobre el mismo
día, o al llegar a **200** peticiones. La parada **no se rodea**; se registra y se para.
Esto es la regla de cuota, no una preferencia.

**NO se hace en esta pasada:** ninguna otra estación; ningún relleno de los 45 eventos
anteriores al 2026-04-08 que además no tienen mercado completo; ninguna petición al
libro; ningún precio.

## 3. Alternativa offline considerada y descartada, con su razón

`evidence/B-133/raw_iem_55_estaciones.tgz` ya contiene `EGLC_rt34.csv`, **151 días
(2026-04-09 → 2026-09-05) que cubren casi toda la ventana**, y derivar de ahí costaría
**cero peticiones**.

**Se descarta para el almacén, y se usa sólo para comprobar.** Escribir filas de
producción desde un tarball de investigación mete en `weather_observations` una
procedencia que el esquema no sabe declarar: `fetched_at` y `available_at` serían de
hoy y no del momento real de descarga, y `source` diría `IEM_ASOS_METAR_RT34` sin que
nada distinga «bajado por el ingestor» de «copiado de un fichero de una investigación».
*Una fila cuya procedencia no consta es exactamente lo que este proyecto lleva una
semana desenterrando.*

**Pero sí se usa como ORÁCULO:** los 151 días del tarball se comparan con lo que la
reingesta escriba, y **cualquier discrepancia detiene la pasada**. Es la comprobación
más barata que existe contra un ingestor que cambia de serie.

## 4. Criterio de aceptación, escrito antes

Tras la reingesta, y **antes** de tocar ningún estadístico del NIVEL 1:

- **a.** las 118 fechas ya cubiertas tienen fila con `series = IEM_ASOS_METAR_1C_RT34` y
  `source = IEM_ASOS_METAR_RT34`, **y la fila vieja sigue ahí** con su valor intacto
  (es lo que garantiza el #49: nunca se sobrescribe una etiqueta);
- **b.** en los 151 días que el tarball cubre, el máximo reingestado **coincide** con el
  máximo de `EGLC_rt34.csv` por día local de Londres;
- **c.** **la predicción de A-246 se comprueba aquí y se reporta antes de seguir**: las
  15 discrepancias entran en su banda ganadora, y **el 2026-05-27 sale** — y sale por la
  VENTANA (`WINDOW_LOCAL_CIVIL_DAY` incluye 00:00–01:00 local y el pico de ese día es el
  calor sobrante del 26), no por la serie. Cualquier otro de los 104 que se salga es un
  resultado nuevo y hay que explicarlo antes de continuar;
- **d.** el recuento de peticiones realmente emitidas se registra y se compara con el
  techo de 200.

## 5. Lo que este presupuesto NO autoriza

No autoriza tocar precios, ni el libro, ni ninguna otra estación, ni levantar el gate
D0, ni operar con dinero. **El gate D0 sólo lo levanta el usuario.**
