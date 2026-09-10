# PREREG_R25 (BORRADOR — NO CONGELADO) — la corrida prospectiva de 21 días

> # SUPERADO — NO ES UN CONTRATO VIGENTE
> Su contenido vive en **`PREREG_PAPER_RUN.md` §6bis** (sesión A), donde debe estar: partir el
> criterio de aceptación en dos documentos lo fragmenta justo donde hace falta que sea uno solo.
> Se conserva **sólo como registro** de qué se propuso y cuándo. **No se congeló, no tiene sha, y
> nada debe citarlo como preregistro.**

**Sesión:** B · **Estado: SUPERADO por R24 §6bis.** Ofrecido a la sesión A, que decide si va aquí o dentro de
R24. **Nada se congela hasta que A responda, y NADA de esto se ejecuta antes de que
`vars.PAPER_TAU` exista** — que es precisamente el orden que este documento existe para imponer.

## 0. Por qué hace falta un preregistro y por qué AHORA

`vars.PAPER_TAU` no está puesta, así que todos los ciclos programados corrieron `--collect-only`
y la cadena de decisión **nunca ha corrido en Actions** (A, P11). En cuanto se ponga, la corrida
empieza a producir un PnL.

**Y va a producir mucho más de lo que ninguno de los dos estaba reconociendo.** Un ciclo en vivo
abrió **27 posiciones**; a dos ciclos diarios durante 21 días son ~42 ciclos y del orden de **mil
posiciones**, más del doble de las 468 de R21 — y **prospectivas**, que es lo único que R21 no
puede ser.

> Si va a haber un PnL sobre ~1 000 posiciones, su criterio tiene que estar congelado **antes**
> de que la variable exista. Si no, en 21 días habrá un número y se elegirá después qué
> significa. Eso es exactamente lo que R21 §6 prohíbe, aplicado un nivel más arriba.

**Me corrijo a mí mismo:** dije que la corrida «prueba la cadena y no la estrategia». Con esos
números **es falso por defecto**: es el único test fuera de muestra **prospectivo** del proyecto.

## 1. `PAPER_TAU` es un parámetro de EJERCICIO — se declara aquí

R21 barrió la rejilla congelada `{0,02·k}` k = 1…10 y el walk-forward se pegó al **máximo** en
239 de 271 decisiones **y aun así perdió**. Por tanto:

> **No existe ninguna `PAPER_TAU` con una afirmación de beneficio detrás.** El valor que se
> ponga es un parámetro de ejercicio y así debe constar junto a él, en el workflow y en todo
> informe. Sin eso, quien lea el libro leerá «operaban con tau = X» como si X tuviera respaldo.

**Regla de elección — de cobertura, no de beneficio:** la **tau más alta** que aún abra
posiciones en la mayoría de los ciclos. Elegirla para maximizar operaciones sería optimizar el
escaparate; elegirla mirando qué PnL sale sería elegir el criterio a partir del resultado.

## 2. LO QUE ESTA CORRIDA PUEDE CONTESTAR Y R21/R22 NO PUDIERON

`orderbook_snapshots` lleva **7 854 filas y 2 244 tokens** en el almacén prospectivo, con
`best_bid`, `best_ask`, `spread` y profundidad a 1/5/10 niveles. **Eso es exactamente lo que
faltaba dos veces:**

1. **R21 tuvo que SUPONER el deslizamiento.** No había book histórico —`orderbook_snapshots`
   vacía, los 16 165 636 precios `MIDPOINT_ESTIMATED`— así que `x_exec` se fijó en el peldaño
   más adverso de D19 por disciplina, no por medida. **Aquí se puede recorrer el book de verdad**
   y el precio alcanzable deja de ser un supuesto.
2. **R22 no pudo evaluar el eje de SPREAD**, que era el que la propia hipótesis señalaba como el
   más informativo —donde el mercado está menos informado— y cuya ausencia se declaró en su §8
   como *«la rama negativa es más débil de lo que podría haber sido»*. **Aquí sí hay spread.**

**Esto cambia el valor de la corrida y hay que decírselo a la usuaria:** no son 21 días para
volver a mirar una señal ya medida; son 21 días para contestar **las dos preguntas que quedaron
abiertas por falta de sustrato**, y ese sustrato no se recupera hacia atrás — cada ranura de
libro perdida es una de esas respuestas que no se podrá dar.

## 3. Criterios — CONGELADOS antes de que exista `PAPER_TAU`

**Unidad de observación: el EVENTO** (R22 §1). Las bandas de un evento son una partición que
suma 1. Todo intervalo por **bootstrap de bloques sobre eventos**, nunca sobre filas. Se reporta
el `n` de eventos y el de filas.

**Etiqueta:** `winning_outcome` del venue, sólo `resolved` — la misma de R21 §A.5, auditada
contra IEM (382/410).

**Costes:** D19 H1 como métrica de decisión; H2 y H3 como columnas. **`x_exec` MEDIDO recorriendo
el book observado**, con el `x_exec` supuesto de R21 (1 punto) como columna de comparación —
para poder decir cuánto se equivocaba el supuesto, que es un resultado en sí mismo.

**Cláusula de no vacuidad:** con **menos de 100 operaciones liquidadas** el resultado es
`NO EVALUABLE`, nunca `APTA` ni `NO APTA`. Es la cláusula que A echó en falta en su propia R24 v1
y que R21 §4.1 aplica.

### 3.1 Qué sería COHERENTE con R21 y qué lo CONTRADIRÍA — declarado antes

- **Coherente:** mediana del PnL neto por operación ≤ 0, o un intervalo por bloques de evento que
  incluya el cero.
- **Contradictorio:** mediana **> 0** con un intervalo por bloques que **no** incluya el cero,
  sobre ≥ 100 operaciones liquidadas. Sólo entonces hay algo que explicar.
- **Y lo que NO cuenta como ninguna de las dos:** un PnL positivo sobre pocas operaciones **no
  refuta R21**, cuyo intervalo es [−0,0288 · −0,0205] sobre 211 eventos; y uno negativo **no lo
  confirma automáticamente**, porque la tau es de ejercicio y no la que R21 evaluó.

**Se declara aquí para que en 21 días nadie pueda elegir cuál de las tres lecturas aplica.**

## 4. Prohibiciones

- No se pone `vars.PAPER_TAU` antes de que este documento esté hasheado.
- No se cambia `PAPER_TAU` a mitad de la corrida. Si se cambia, la corrida **se parte** y los dos
  tramos se reportan por separado; no se agregan.
- No se cambian los criterios de §3 tras ver resultados.
- El ensayo de P11 corre bajo un `dataset_version` **de ensayo**, nunca `ds_paper_v1`: un ciclo
  de prueba en el libro preregistrado sería imposible de separar después.
- Los ciclos disparados a mano se marcan y se reportan **aparte** de los programados, por el
  `event` del shard. Un almacén lleno a base de puentes mide la atención del operador, no el host.
- No se opera con dinero real: **gate D0 intacto**, y este documento no lo levanta.

## 5. Limitaciones que heredará el informe

Todas las de R21 §8 y R22 §7, y dos propias: **la tau es de ejercicio**, así que el resultado
describe *esa* regla y no la mejor posible · **el periodo son 21 días de una sola estación del
año**, y R22 ya declaró que el sustrato retrospectivo estaba desbalanceado hacia abril-mayo, así
que las dos ventanas juntas siguen sin cubrir un año.
