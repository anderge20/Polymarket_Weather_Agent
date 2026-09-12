# FASE 0 — Diagnóstico inicial, antes de tocar nada

**2026-09-12 · auditoría ordenada por el usuario · regla aplicada: lo que no se puede
determinar se marca `UNKNOWN — requiere verificación`, y no se rellena.**

---

## 0. Qué NO he podido auditar, y por qué. Léelo primero

Dos accesos que el encargo da por disponibles **no lo están desde esta sesión**:

| recurso | estado | evidencia |
|---|---|---|
| **Codex** | **INALCANZABLE** | sin binario `codex`/`codex-cli`; sin clave `OPENAI_*` en el entorno; `api.openai.com` responde **403 en CONNECT** (misma política de egreso que bloquea Polymarket). `registry.npmjs.org` sí responde, así que el CLI se podría *instalar* — sin nada con lo que hablar |
| **Servidor Hetzner** | **INALCANZABLE** | sin claves en `~/.ssh`, sin variables de despliegue, sin credenciales, y el egreso está bloqueado por política |

**Consecuencia directa sobre el protocolo que pides:**

| fase | qué pide | estado |
|---|---|---|
| 4 · GitHub vs Hetzner | commit, branch, cambios locales, venv, systemd, cron, .env, permisos | **NO EJECUTABLE** — todo `UNKNOWN` |
| 5 · Entorno de producción | CPU, RAM, disco, procesos, relojes, NTP, timezone del servidor | **NO EJECUTABLE** — todo `UNKNOWN` |
| 6 · Ejecución real | reconstruir señales, órdenes, fills, posiciones, PnL desde logs | **NO EJECUTABLE** — no hay logs ni base de datos alcanzables |
| 7 · Auditoría cuantitativa | win rate, expectancy, Sharpe, drawdown sobre operaciones reales | **NO EJECUTABLE** — requiere el DuckDB de producción |

**No las voy a simular ni a inferir.** Lo que sí he podido auditar —código, arquitectura,
lógica, y los datos reales de la rama `paper-state`— está abajo, y ha bastado para encontrar
lo que probablemente sea la respuesta a tu pregunta sobre Hong Kong.

---

## 1. Arquitectura (auditable: SÍ, desde código)

```
DESCUBRIMIENTO   polymarket/discovery.py    catálogo Gamma -> markets/outcomes/fees
                 polymarket/resolution.py   parsea la REGLA DE RESOLUCIÓN del texto del contrato
INGESTA          polymarket/prices.py       price_history (INDICATIVE; EXECUTABLE rechazado)
                 weather.py                 forecasts Open-Meteo, con available_at fail-closed
                 observations.py            observaciones (IEM/METAR, y otras fuentes)
MODELO           error_model.py (M2)        distribución de error del forecast -> cuantiles
                 probability.py             cuantiles -> distribución discreta -> prob. de banda
FEATURES         features.py                fila as-of; resolución PROHIBIDA como feature
SEÑAL            strategy/strategy_a.py     p_weather vs p_market -> BUY/FADE/HOLD
COSTES           costs.py                   fee = 0.05·p·(1−p) taker-only; x_exec asumido
BACKTEST         backtest.py                universe() -> candidates() -> walk_forward()
SETTLEMENT       settlement.py              4 OPERADORES por regla de contrato
                 labels.py                  etiqueta por mercado
PERSISTENCIA     database.py / store.py     DuckDB + shards ndjson.gz
ORQUESTACIÓN     scripts/paper_cycle.py     ciclo diario; .github/workflows (cron DESACTIVADO
                                            desde 2026-09-09: "ejecución movida a Hetzner")
```

**Puerta D0:** no existe wallet, signer ni `py-clob-client` en el árbol. Tests lo aseveran.
El sistema es **estructuralmente incapaz de colocar una orden**. Esto es importante para tu
pregunta «¿seguir operando?»: **hoy no se opera con dinero real desde este código.**

## 2. Estado de GitHub (auditable: SÍ)

```
main = 97e7111 · 36+ ramas · 588 tests en verde (602 con PR #33)
PRs abiertas mías: #28 (investigación) · #33 (correcciones A1/A2)
Ramas con DATOS: paper-state (149 ficheros), research/modelsel-artifacts, measure/spread-distribution
```

**Riesgo detectado:** el ciclo de producción vive en `ops/hetzner/install.sh` (cron del
servidor), **no** en los workflows de Actions, que están explícitamente desactivados. Es decir:
**lo que corre en producción está gobernado por un fichero del repo que nadie en esta sesión
puede verificar que esté aplicado.** `UNKNOWN`.

## 3. Estado de Hetzner

**`UNKNOWN` en su totalidad.** Todos los puntos de las fases 4 y 5 quedan sin verificar:
commit desplegado, rama, cambios locales, venv, dependencias, systemd, cron, `.env`, permisos,
procesos duplicados, timezone del sistema, NTP, reloj, logs, rotación, base de datos.

**No puedo afirmar que el código de GitHub sea el que corre.** La regla 2 de tu encargo
(«GitHub correcto ≠ producción correcta») se mantiene **sin comprobar**.

## 4. Estrategias que existen (auditable: SÍ)

| nombre | qué es | estado |
|---|---|---|
| **Strategy A** | `p_weather` (forecast público) vs `p_market`, long-only sobre el token YES | **la única estrategia implementada**. Veredicto previo: NO OPERABLE (R21), sin skill (R22) |
| Strategy B | microestructura / orderbook / trades | **NO EXISTE.** Declarada «non-goal» en PHASE_2D §B |
| «Hong Kong» | **no es una estrategia: es un ESTRATO DE SETTLEMENT** — ver §5 | ver §5 |

**No hay subestrategias.** Hay **una** estrategia y **cuatro operadores de settlement**.

## 5. HONG KONG — localizado exactamente, y el hallazgo

### 5.1 Qué es

**No es una estrategia ni una subestrategia. Es el estrato 10: el operador de settlement de
los mercados del Observatorio de Hong Kong.**

```
src/weather_agent/settlement.py:240   OP_HKO_ABSMAX
    operator_id       "HKO_ABSMAX_INTERVAL_FLOOR"  v1
    unit              C
    window_kind       WINDOW_SOURCE_DAILY_ROW      (no hay ventana derivable)
    aggregation       AGG_SOURCE_DAILY
    quantization      QUANT_INTERVAL_FLOOR         (ceil / half-up / half-even REFUTADOS,
                                                    164/166, Wilson 0,957–0,997)
    required_series   "hko_clmmaxt"
    contract_source   SRC_HKO
    measurement_rule  P_HKO_AbsDailyMax
    compat_status     COMPAT_DIRECT   <-- el ÚNICO estrato DIRECTO
src/weather_agent/polymarket/resolution.py:159  regex: Hong Kong Observatory | weather.gov.hk
```

El propio código lo describe como **«the only DIRECT stratum and the one that has a
holdout»** — el único cuyo settlement lee la fuente del contrato en vez de un proxy, y el
único con holdout evaluable. Es, en principio, **el estrato de mayor calidad del sistema.**

### 5.2 EL HALLAZGO: Hong Kong nunca ha entrado en ningún backtest

`backtest.universe()` filtra, entre otras cosas:

```sql
AND m.station_identifier IS NOT NULL
AND lower(coalesce(m.rounding_rule, '')) <> 'tenths'
```

Y sobre los mercados HKO reales de `paper-state`:

```
mercados HKO                                    22
con station_identifier                           0 / 22   <-- EXCLUIDOS
rounding_rule = 'tenths'                        22 / 22   <-- EXCLUIDOS OTRA VEZ
conjunto HKO == conjunto 'tenths'               SI (identicos)
unit IN ('C','F')                               22 / 22   (este sí pasa)
```

Y `settlement.py:316` lo dice de los históricos: **«Stratum 10 (HKO) has no station and no tz
— `icao2` is NULL in all 1,859, and §4 says that is NOT a defect»**.

> ### **Hong Kong está excluido del universo del backtest por DOS filtros independientes.**
> **R21 y R22 contienen exactamente CERO mercados de Hong Kong.**

**Implicación inmediata y la más importante de este diagnóstico:**

- Cualquier creencia de que Hong Kong «funciona» o «tiene edge» **no puede proceder de R21 ni
  de R22**, porque esos experimentos nunca lo miraron.
- Y simétricamente: **el veredicto NO OPERABLE de R21 no dice nada sobre Hong Kong.** Es un
  veredicto sobre 47 estaciones que no incluyen ésta.
- **De dónde procede entonces cualquier resultado de Hong Kong: `UNKNOWN — requiere que me
  indiques la fuente`** (¿un informe? ¿una corrida en Hetzner? ¿el paper cycle?). No he
  encontrado en el repositorio ningún backtest que lo incluya.

### 5.3 Y hay un defecto de settlement ya documentado, en este mismo estrato

`settlement.py:313-325` describe un bug **ya corregido** pero que revela la fragilidad:

> HKO publica en HKT (UTC+8). Una versión anterior devolvía el día civil **UTC** y filtraba con
> él, así que la fila sellada a la medianoche de la fuente para 2026-09-10 (= 2026-09-09T16:00Z)
> **caía fuera de la ventana y se descartaba**, mientras la del día siguiente caía dentro y
> liquidaba. **No falló cerrado: emitió una etiqueta del día equivocado** — y precisamente en
> el único estrato DIRECTO y el único con holdout.

Un error de ±1 día en la etiqueta de un estrato es exactamente el tipo de fallo que produce
resultados que parecen reales y no lo son. **Está corregido en el código actual; que la
corrección esté desplegada en Hetzner es `UNKNOWN`.**

## 6. Riesgos principales detectados, ordenados

| # | riesgo | severidad | estado |
|---|---|---|---|
| R1 | **Hong Kong nunca ha sido backtesteado** — excluido por dos filtros | 🔴 | **CONFIRMADO** |
| R2 | **No se puede verificar qué corre en Hetzner** | 🔴 | `UNKNOWN` por falta de acceso |
| R3 | **Universo prospectivo = 3,0 %** (33/1 100 mercados pasan los filtros) | 🔴 | **CONFIRMADO** |
| R4 | El estrato HKO tuvo un bug de ventana que emitía etiquetas del día equivocado | 🟠 | corregido en código; despliegue `UNKNOWN` |
| R5 | A5: ancla `12:00Z` vs día civil local, con 51 ciudades en 3 familias de huso | 🟠 | **INDETERMINADO**, requiere DuckDB |
| R6 | `available_at` de observaciones es el instante de descarga, no la publicación | 🟠 | declarado por el propio proyecto |
| R7 | Dependencia entre estaciones el mismo día (un frente correlaciona eventos) no tratada en el bootstrap | 🟠 | **no tratada** |
| R8 | 60 h de vida de mercado sin observar; dos instantes de decisión | 🟡 | **CONFIRMADO** |
| R9 | Heterogeneidad de regla de medición: 242 mercados resuelven sobre cota inferior | 🟡 | **CONFIRMADO** |

## 7. Lo que necesito de ti para continuar

El encargo no puede avanzar más allá de este punto sin tres cosas, y ninguna la puedo obtener:

1. **Acceso a Hetzner** (o que ejecutes tú los comandos y me pases la salida) → desbloquea
   fases 4, 5, 6.
2. **El DuckDB de producción** → desbloquea fases 3, 7, y A5.
3. **La fuente de cualquier resultado de Hong Kong que te haya hecho sospechar.** Yo no
   encuentro ninguno en el repositorio, y saber de dónde sale determina qué hay que auditar.

**Y una pregunta que cambia la naturaleza del encargo:** preguntas si «seguir operando Hong
Kong». **No he encontrado ningún camino de código capaz de colocar una orden** — no hay wallet,
ni signer, ni cliente de órdenes, y hay tests que lo aseveran. Si crees que hay capital
operando, o bien corre desde otro sitio que no está en este repositorio, o bien la premisa es
incorrecta. **`UNKNOWN`, y es urgente aclararlo antes que cualquier otra cosa.**
