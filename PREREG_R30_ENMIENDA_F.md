# PREREG R30 — ENMIENDA F: la magnitud que E declaró «no establecida» ya está establecida, y es menos favorable a §6.2

**Sesión B, 2026-09-11.** Sexta enmienda a `PREREG_R30_PUERTA_SUSTRATO.md`. Índice y shas en
`R30_PREREG_CHAIN.md`. **Sigue sin calcularse nada contra R30.**

**Por qué existe:** la Enmienda E cerró §3 diciendo *«dirección sostenida, magnitud NO establecida»*.
Con la tabla por bin de la sesión A y mi medición sobre la definición congelada del §0, **la magnitud
sí está establecida**. Dejar en pie un «no establecido» que ya no lo es sería exactamente la clase de
afirmación caduca que este proyecto lleva el día entero persiguiendo.

---

## Lo medido

Semidiferencial (`(ask − bid)/2`) por `precio_bin` del §0, sobre **25.736 libros de dos lados**,
2026-09-09..11:

```
bin      n     mediana    media     p75     media/x_exec
  0   8037     0,0050   0,0065   0,0100        0,65x
  1   1484     0,0100   0,0147   0,0200        1,47x
  2   1258     0,0100   0,0200   0,0150        2,00x
  3   1080     0,0100   0,0126   0,0150        1,26x
  4    987     0,0100   0,0110   0,0100        1,10x
  5   1004     0,0100   0,0102   0,0100        1,02x
  6   1055     0,0100   0,0126   0,0150        1,26x
  7   1251     0,0100   0,0205   0,0150        2,05x
  8   1478     0,0100   0,0146   0,0150        1,46x
  9   8102     0,0050   0,0066   0,0100        0,66x

zona de duda (1-8)   n= 9.597   mediana 0,0100   media 0,0148
extremos   (0 y 9)   n=16.139   mediana 0,0050   media 0,0066
poblacion            n=25.736   mediana 0,0050   media 0,0096
```

**U invertida:** los extremos de precio son baratos, la zona de duda cuesta el doble en mediana y
más del doble en media. **Y la regla opera en la zona de duda por construcción** —es donde `p_model`
y `p_mid` más se separan—, así que el mecanismo del argumento estructural de §3 **queda medido y no
argumentado.**

**Y mi 0,0168 de n=27 encaja como lo que era:** una muestra pequeña de la zona de duda, entre la
media de la zona (0,0148) y las de los bins 2 y 7 (0,0200 y 0,0205).

## §3 enmendado — tercera y previsiblemente última redacción

> **§3 (enmendado F)** — Conocimiento previo declarado, con población y estadístico en cada cifra:
>
> - **En la zona donde la regla opera (bins 1–8, n = 9.597): semidiferencial mediano = 0,0100, que
>   es EXACTAMENTE el `x_exec` que supuso R21.** Su media es 0,0148 (**1,48×**), porque la
>   distribución está sesgada a la derecha.
> - **R21 no fue optimista en la mediana; lo fue en la cola.** Un `x_exec` constante de 0,0100 acierta
>   en el centro de la distribución que enfrentaba y se queda corto en su cola derecha.
> - **Queda RETIRADO «un 68 % más caro»** en todas sus formas. Era 0,0168 de n=27 contra un supuesto,
>   sin población.
> - **Dato de sustrato, declarado aquí porque afecta a §4:** **11.114 de 36.850 libros (30,2 %) están
>   cotizados por un solo lado.** No tienen semidiferencial —ni ancho ni cero— y no son operables en
>   dos sentidos. La población operable es ~70 % de la observada, y las puertas de §4 deben contarse
>   sobre la operable.

## §6.2 DEGRADADO — y es lo que más cambia

§6.2 declaraba «lo contiene pero el coste se lo come» como **el desenlace a priori más probable**,
apoyado primero en 0,0168 (Enmienda E lo retiró) y después en el argumento estructural.

**Ese argumento ya no sostiene «el más probable».** El coste en la zona operada es, en mediana,
**exactamente el que R21 ya asumía** — y R21 perdió con ese coste **por calibración, no por coste**:
§1.1 lo mide sin usar τ y sin usar el libro. Un coste que resulta ser el que ya se suponía no puede
ser la explicación principal de nada nuevo.

> **§6.2 (enmendado F)** — Sigue siendo un resultado negativo **declarado de antemano** y plenamente
> publicable, pero **pierde el rango de «a priori el más probable»**. Los tres desenlaces de §6
> quedan **sin orden de probabilidad declarado**, porque ninguna medición disponible lo justifica.
>
> **Lo que sí se declara:** el coste en la zona operada **excede al supuesto en la cola** (media
> 1,48×, bins 2 y 7 por encima de 2×), así que §6.2 sigue siendo un desenlace **vivo** — pero por la
> cola de la distribución, no por su centro.

**Y esto va contra mí, que es la razón de escribirlo.** Declarar de antemano cuál es el desenlace más
probable era una forma de blindarme: si salía §6.2, podía decir «lo dije». **Retirar esa declaración
cuando la medición deja de sostenerla es lo que la hacía valer algo.**

## Lo que NO cambia

§0, §1, §2, §4.1, §4.2, §4.3, §5, §6.1, §6.3, §7, §8.

> **ADVERTENCIA, la misma de D y E:** «no cambia» significa «esta enmienda no lo toca», **nunca «ya
> está revisado»**.
