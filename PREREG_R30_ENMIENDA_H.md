# PREREG R30 — ENMIENDA H: §4.1 exige LIBRO para una hipótesis que no lo necesita

**Sesión B, 2026-09-11.** Octava enmienda a `PREREG_R30_PUERTA_SUSTRATO.md`. Índice y shas en
`R30_PREREG_CHAIN.md`.

**Sigue sin calcularse nada contra R30.** En particular **NO he calculado la curva de fiabilidad del
mercado** que esta enmienda hace evaluable: se enmienda y se congela primero, se mide después. Decirlo
importa porque esta enmienda **abre** una vía, y una enmienda que abre lo que su autor ya ha mirado no
vale nada.

---

## El defecto

**§4.1 exige «≥ 60 días naturales de cobertura de LIBRO».** Esa puerta viene de §3: el libro es el
único sustrato que R21 y R22 no pudieron usar. **Correcto — y de ahí no se sigue que toda candidata
necesite libro.**

Una tercera sesión (la de la nube, PR #28) ha matado hoy dos de las tres vías que quedaban, **contra un
umbral preinscrito 1h09m antes del dato** — verificado en el historial de commits, no de palabra:
provisión de liquidez (medio spread 0,005–0,010 contra un margen de `fair_value` de ~0,036: **cotizar
dentro del propio error**) y coherencia de partición (0 de 96 particiones completas rentables).

**La vía que sobrevive es la calibración del precio. Y no necesita libro: necesita precios y
desenlaces, que ya existen retrospectivamente.** Tal como está, §4.1 la bloquearía **dos meses sin
razón**.

## Y lo que la hace legítima, verificado

**Ninguna medición de R21 ni de R22 toca la calibración del MERCADO.** Todas las de calibración son
sobre `p_model`:

- R21 §3.2: *«sobre los 10 000 candidatos, `p_model` está BIEN calibrada»*.
- R21 §3.x: *«`p_model` peor calibrada por mercado que en agregado»*.
- R22: Brier del mercado **0,04215** contra base **0,06801**.

**El Brier del mercado mide que es INFORMATIVO, no que esté CALIBRADO.** Son cosas distintas: un
mercado puede batir a la base y estar sesgado de forma sistemática y explotable — el sesgo
favorito-longshot es el caso de manual. **Nadie ha calculado `P(desenlace | p_mid ∈ intervalo)` contra
`p_mid`.**

## §4.1 enmendado

> **§4.1 (enmendado H)** — La puerta de **60 días de cobertura de libro** aplica **sólo a candidatas
> cuya hipótesis requiera el LIBRO**. Una candidata que use únicamente el sustrato que R21 y R22 ya
> tenían —precios, desenlaces, previsiones— **no está sujeta a §4.1**.
>
> **Pero carga con una obligación más dura, y no es negociable:** debe **declarar por escrito qué
> midieron R21 y R22 con ese mismo sustrato y por qué su pregunta no está ya respondida ahí**. Sin esa
> declaración, la candidata se rechaza sin evaluar. El sustrato compartido es exactamente donde una
> hipótesis nueva puede ser una vieja refutada con otro nombre.

## Y §2 no se relaja: se vuelve el test

§2 exige **información condicionada al precio**. Para una candidata de calibración del mercado eso
**no es una restricción añadida: es el enunciado literal del contraste** — dentro de cada
`precio_bin` del §0, ¿la frecuencia realizada se aparta de `p_mid` de forma sistemática y con signo
estable?

**Es la misma curva de fiabilidad que §5.1 ya pide por intervalo**, aplicada al precio en vez de al
modelo. Así que §2, §5.1 y §5.4 **valen tal cual** y no hacen falta criterios nuevos: cambia el objeto
—`p_mid` en lugar de `p_model`— y no la maquinaria.

## Lo que NO cambia

§0, §1, §2, §3, §4.2, §4.3, §5, §6, §7, §8 — y §6.2 sigue degradado por la Enmienda F.

> **ADVERTENCIA, la de D, E, F y G:** «no cambia» significa «esta enmienda no lo toca», **nunca «ya
> está revisado»**.

## Nota de método

**Esta enmienda ABRE una vía, y las siete anteriores CERRABAN o endurecían.** Eso invierte el incentivo
y hay que decirlo: es la primera en la que el autor gana algo. Por eso lleva delante que **no he
mirado el dato**, y por eso la obligación de §4.1 —declarar qué midió R21/R22 y por qué no responde ya
la pregunta— **es más dura que la puerta que levanta**.
