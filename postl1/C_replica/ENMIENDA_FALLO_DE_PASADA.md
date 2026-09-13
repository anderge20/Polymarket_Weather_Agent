# FASE C · ENMIENDA 2 — QUÉ HACER CUANDO EL ARCHIVO NO TIENE UNA PASADA

**Escrita ANTES de reanudar la ingesta y ANTES de puntuar nada.** No toca la metodología
congelada: la ALINEA con la de producción, de la que mi guion se había separado.

---

## 1 · QUÉ PASÓ

La ingesta de pronósticos paró en seco a las **44 peticiones** (43 escritas, 1 fallida):

    2026-06-11 run 06-10 18z (lead 9h) ERROR WeatherIngestError:
      icon_seamless rejected at (37.469,126.451) run 2026-06-10T18:00Z:
      The requested model run is not available. Model: dwd_icon, run: 2026-06-10T18:00Z

No es cuota. No es 429. No es red. Es **una pasada que el archivo Single-Runs no tiene**.

## 2 · MI GUION SE HABÍA SEPARADO DE PRODUCCIÓN, Y HACIA EL LADO EQUIVOCADO

`scripts/backfill_weather.py` — la ruta congelada, la que construyó el corpus de Londres —
distingue **dos clases** de error y las trata distinto:

```python
except weather.WeatherIngestError as e:
    msg = str(e)
    if "429" in msg or "quota" in msg.lower():
        ...  quota_hit = True; break          # PARA
    failed += 1                                # CUENTA Y SIGUE
```

`faseC_ingesta_fc.py` colapsaba las dos en una: `except Exception` → parada dura. Eso lo
copié de `faseC_ingesta_obs.py`, donde sí es lo correcto (allí *cualquier* fallo de IEM es
un fallo de proveedor). Aplicado al pronóstico convierte **un hueco del archivo en una
parada del experimento**, que es justo lo que la metodología de Londres no hace.

**La enmienda es volver a producción, no alejarse de ella:**

| clase | regla |
|---|---|
| 429 / `quota` | **PARADA DURA**, sin reintento, sin rodeo. Regla D0, intacta. |
| pasada ausente del archivo / cualquier otro `WeatherIngestError` | **se cuenta y se sigue**, exactamente como `backfill_weather.py`. El par `(target_date, lead)` se queda **sin pronóstico** y por tanto **fuera de la población puntuable**. |

## 3 · LO QUE NO SE HACE, Y POR QUÉ IMPORTA MÁS QUE LO QUE SÍ

**NO se retrocede a una pasada anterior.** Sería lo que haría un agente en vivo si la
pasada nunca se hubiera publicado — pero `pick_run` es parte de la metodología congelada y
retroceder más allá de lo que ella devuelve **es cambiarla**. Además, a posteriori es
imposible distinguir *«nunca se publicó»* de *«se publicó y se cayó de la ventana rodante
del archivo»*, y las dos exigen respuestas opuestas. Ante esa ambigüedad, la opción que no
inventa información es **perder el evento**, no rellenarlo.

Consecuencia aceptada y declarada aquí: **la ausencia de pasada reduce N**. Se reportará
como *missingness* en la tabla de poblaciones (§11 del encargo) y se atacará en el red team
(§22, «¿hay sesgo de missingness?»).

## 4 · TECHO DE FALLOS — declarado ahora, antes de volver a ejecutar

    fallos_max = 20     (~10 % del plan de 190)

Si se superan, se **para** y se declara la ingesta incompleta. Un hueco suelto es
missingness; veinte huecos son un problema de integridad del archivo y no se puntúa encima
de eso. El umbral es más restrictivo que el de producción (que no tiene ninguno) y **no
puede favorecer ningún resultado**: sólo puede impedir que se calcule.

## 5 · PRESUPUESTO — no se mueve

    techo preinscrito        200 peticiones de pronóstico
    gastadas hasta ahora      44   (43 escritas + 1 fallida)
    plan restante            147   (190 - 43 ya escritas)
    margen                     9

`147 <= 156`. **El techo no se toca.** Si se agotara, se para con datos incompletos, tal y
como manda §3 del encargo: *«no aumentar el presupuesto retrospectivamente»*.

## 6 · Y EL ERROR TRAE UN DATO QUE EL GATE DE AVAILABILITY NECESITABA

El proveedor nombró el modelo: **`Model: dwd_icon`**. A las coordenadas de RKSI,
`icon_seamless` **es ICON-GLOBAL**, no ICON-D2. Eso se desarrolla en el gate de
availability; aquí queda anotado que la evidencia llegó de un mensaje de error, no de una
petición pagada con cuota.
