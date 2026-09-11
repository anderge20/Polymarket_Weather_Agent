# PREREG R30 — ENMIENDA B: una familia que no existía y una puerta contada antes del borrado

**Sesión B, 2026-09-11.** Segunda enmienda a `PREREG_R30_PUERTA_SUSTRATO.md`
(sha `0a5b794e656390b13e33f14a40260f7a7818b13928f45db7d1a5312deb0caaaf`), posterior a
`PREREG_R30_ENMIENDA_A.md` (sha `b2ecac699fa097cc5d23ff0513ced1a05d683aff89c92a92312705961d9aec33`).

**Los dos defectos los encontró la sesión A revisando R30.** Ninguno es mío de haberlos visto y
callado: **no los vi.** Sigue sin calcularse nada contra R30; se congeló, se enmendó dos veces y se
enmienda esta tercera dentro de la misma jornada, antes de tocar un dato.

**Lee R30 SIEMPRE con las enmiendas A y B.**

---

## DEFECTO 1 — §5.4 invocaba una familia que el documento nunca declara

§5.4 decía:

> el estadístico del contraste es el **MÁXIMO** sobre la familia de estratos declarados […] Nada de
> elegir el estrato ganador después.

**Y la familia no está declarada en ninguna parte de R30.** Es una referencia hacia adelante a una
lista que no existe.

### La dirección es lo que lo hace peor que el defecto de la Enmienda A

El §4.2 original **sólo podía fallar**: restrictivo, una conclusión escrita de antemano. **§5.4 sólo
puede pasar.** Si la familia no está fijada antes, la fija quien ejecute el análisis — y «el máximo
sobre la familia declarada», que es *la maquinaria puesta ahí precisamente para impedir elegir el
estrato ganador después*, **legitimaría exactamente lo que prohíbe**. Una corrección por
comparaciones múltiples sobre una familia escogida tras ver los datos no es una corrección: es un
adorno.

**Los dos son «un criterio que no es un criterio», en sentidos opuestos — y el permisivo es el que
no se nota**, porque no produce ningún fallo que obligue a mirarlo.

### §5.4 enmendado: la familia, enumerada y cerrada

> **§5.4 (enmendado)** — El estadístico es el **MÁXIMO** sobre **esta familia y sólo ésta**, con
> permutación pareada por evento completo:
>
> | variable | niveles | celdas |
> |---|---|---|
> | `precio_bin_0.1` | 0, 1, 2, 3, 4 | 5 |
> | `lead` | 9, 24 | 2 |
> | `unidad` | C, F | 2 |
> | `banda` | centro, cola_cercana, cola_lejana | 3 |
> | `anchura_fc` | baja, media, alta | 3 |
> | **TOTAL** | | **15** |
>
> **La familia queda CERRADA por esta enmienda.** Añadir un estrato exige un preregistro nuevo, no
> una nota. Quitarlo también.

**`estacion` queda FUERA de la familia deliberadamente**, y la razón se escribe para que nadie la
«arregle» luego: §5.3 ya usa la estación como eje de borrado (*leave-one-out*). Meterla además en la
familia del máximo la contaría dos veces —una como celda y otra como prueba de robustez— y las dos
lecturas no son independientes.

**Estos son los estratos que R22 ya declaró**, no una lista nueva: se reutilizan precisamente porque
ya están congelados en un documento hasheado, y estrenar estratos aquí sería la misma libertad que
§5.4 prohíbe.

---

## DEFECTO 2 — §4.2 cuenta la población ANTES del borrado que §5.3 exige

§4.2 (ya enmendado en A) pide ≥150 eventos en cada intervalo 1–4. **§5.3 exige después que el signo
aguante dejando fuera el mes de mayor peso.** Nadie midió la conjunción — **mi mismo defecto de la
Enmienda A, un nivel más allá.**

En el mínimo permitido por §4.1 el borrado es brutal (verificado):

```
 60 dias: Sep 23 · Oct 31 · Nov  6   mes mayor = 31/60 = 51,7 %  -> §5.3 evalua sobre el 48 %
120 dias: Sep 23 · Oct 31 · Nov 30 · Dec 31 · Jan 5
                                     mes mayor = 31/120 = 25,8 % -> evalua sobre el 74 %
```

Así que evaluando en cuanto abre la puerta, **§5.3 tira más de la mitad de los datos** y §5.1 —BSS>0
en los cinco intervalos con IC bootstrap— se calcularía sobre una población **que no ha pasado
ninguna puerta**, porque §4.2 contó la de antes.

### §4.2 enmendado por segunda vez: la puerta se cuenta DESPUÉS del borrado

> **§4.2 (enmendado B)** — **≥ 150 eventos en cada uno de los intervalos de precio 1 a 4, contados
> SOBRE LA POBLACIÓN QUE QUEDA tras aplicar los dos borrados de §5.3** (fuera la estación de mayor
> peso; fuera el mes natural de mayor peso). Si la muestra no aguanta la puerta después del borrado,
> la puerta no está abierta.

**Elegí esto y no cambiar la unidad de §5.3 —bloques rodantes de 30 días en lugar de meses— por una
razón concreta:** el borrado por mes natural es el criterio que **R21 falló**, y cambiar la unidad
rompería la comparabilidad con el único resultado medido que tenemos. Se endurece la puerta, no se
ablanda el contraste.

**Y es alcanzable, con la aritmética delante:** al 14,4 % del intervalo más raro y quitando el 51,7 %
del mes mayor, 150 eventos post-borrado exigen ~2.155 eventos totales → **~42 días** a ~51
fechas-evento/día. **Sigue dentro de los 60 días de §4.1, que por tanto continúa siendo la
restricción que manda.**

---

## Lo que NO cambia

§1, §2, §3, §4.1, §4.3, §5.1, §5.2, §5.3, §6, §7 y §8 quedan exactamente como están. En particular
sigue en pie §6.2 —«lo contiene pero el coste se lo come»— como desenlace *a priori* más probable,
por el semidiferencial medido de **0,0168** frente al 0,0100 supuesto por R21.

## Nota de método, porque es la tercera enmienda del mismo día

R30 se escribió **en una sola pasada** y ha necesitado tres correcciones en horas: una conjunción no
medida, una familia inexistente y una puerta contada en el momento equivocado. **Las tres son la
misma forma —afirmar sobre una magnitud sin medirla— y ninguna la vio quien escribió el documento.**
La única que falla en dirección permisiva la encontró la otra sesión, que es el argumento entero a
favor de que los preregistros los revise alguien distinto de quien los redacta.
