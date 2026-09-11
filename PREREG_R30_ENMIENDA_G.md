# PREREG R30 — ENMIENDA G: el sustrato operable, contado por mercado, y dónde se concentra la iliquidez

**Sesión B, 2026-09-11.** Séptima enmienda a `PREREG_R30_PUERTA_SUSTRATO.md`. Índice y shas en
`R30_PREREG_CHAIN.md`. **Sigue sin calcularse nada contra R30.**

**Por qué existe:** §3 (enmienda F) declaró *«el 30,2 % de los libros están cotizados por un solo
lado, la población operable es ~70 % de la observada»*. **La dirección es correcta y la forma es
floja** — lo señaló la sesión A: eso es cierto **por filas** y engaña **por sujeto**. El 30 % no es un
recorte repartido.

---

## 1. El sustrato operable, contado por MERCADO

Sobre 2.244 mercados / 4.488 tokens, 3 días, 30 pasadas:

```
SIEMPRE de dos lados   1.055   47,0 %
NUNCA  de dos lados      583   26,0 %   <- no operables JAMAS
mixtos                   606   27,0 %
```

**Un cuarto del universo no se puede operar nunca.** No es «a veces ilíquido»: son 583 mercados que
en 30 pasadas no cotizaron los dos lados ni una sola vez.

## 2. La liquidez es propiedad del MERCADO, no del lado — comprobado, no supuesto

**En 2.244 de 2.244 mercados (100 %) los dos tokens comparten estado de liquidez.** Tiene sentido —un
bid en `Yes` es un ask en `No`— pero estaba sin comprobar. **Consecuencia práctica: cualquier conteo
de sustrato puede hacerse por mercado sin perder nada.**

## 3. Y la pregunta que decide cuánto muerde: DÓNDE se concentra la iliquidez

Observaciones de dos lados por `precio_bin` del §0, según la clase del mercado:

```
                         siempre    mixto    % mixto
zona de duda (bins 1-8)    9.335      262       2,7 %
extremos    (bins 0 y 9)   9.431    6.708      41,6 %
```

**La iliquidez intermitente se concentra en los EXTREMOS de precio, no en la zona de duda.** La zona
donde la regla opera está servida en un **97,3 %** por mercados siempre líquidos.

**Y el hecho que eso revela, que ninguno de los dos había escrito:** un mercado intermitente **sólo
cotiza los dos lados cuando el desenlace ya está casi decidido** (p cerca de 0 o de 1) — es decir,
cuando menos hay que operar. Su liquidez aparece justo donde no sirve.

## §3 enmendado — el párrafo de sustrato, cuarta redacción

> **§3, párrafo de sustrato (enmendado G)** — sustituye a la frase «la población operable es ~70 % de
> la observada» de F:
>
> - Por mercado: **47,0 % siempre operable · 26,0 % NUNCA · 27,0 % intermitente.**
> - **La liquidez es propiedad del mercado** (100 % de acoplamiento entre sus dos tokens), así que el
>   conteo de sustrato se hace **por mercado y por evento**, nunca descontando un porcentaje de filas.
> - **La iliquidez intermitente vive en los extremos de precio** (41,6 % de las observaciones
>   extremas contra 2,7 % de las de la zona de duda). La zona operada la sirven los mercados siempre
>   líquidos.
> - **Todas las cifras de spread de §3 y de la tabla de F son SEMIdiferenciales, `(ask − bid)/2`.**
>   F lo dice en el texto que introduce su tabla, pero **no en las cabeceras de columna**, y un
>   fragmento citado pierde la unidad. Queda dicho aquí sin depender del contexto.

## §4.2 y §4.3 precisados — la puerta se cuenta sobre lo operable, por sujeto

> **§4.2 y §4.3 (precisados G)** — Los conteos de eventos se hacen **sobre la población operable,
> identificada por MERCADO**: un evento cuyos mercados caen en el cuarto que nunca cotiza dos lados
> **aporta cobertura que jamás podrá convertirse en una operación**, y no cuenta para la puerta.
>
> **No se descuenta un porcentaje de filas.** Esa fue la forma floja de F y produce el número
> correcto por casualidad y el razonamiento equivocado siempre.

**Nota sobre la dirección del efecto, para que nadie lo lea como alarma:** esta corrección **endurece
§4 en los extremos y casi no lo toca en la zona de duda** (donde sólo el 2,7 % viene de mercados
intermitentes). El sustrato que §2 necesita —bins 1 a 4— está mejor servido de lo que la cifra del
30 % sugería. **La corrección es de forma y de conteo; no cambia la viabilidad de la puerta.**

## Lo que NO cambia

§0, §1, §2, §4.1, §5, §6 (con la degradación de F), §7, §8.

> **ADVERTENCIA, la misma de D, E y F:** «no cambia» significa «esta enmienda no lo toca», **nunca
> «ya está revisado»**.
