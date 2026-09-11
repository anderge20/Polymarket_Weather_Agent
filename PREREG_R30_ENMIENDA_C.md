# PREREG R30 — ENMIENDA C: el eje del §2 sólo estaba definido en una línea de código, y la Enmienda B abrió el hueco que venía a cerrar

**Sesión B, 2026-09-11.** Tercera enmienda a `PREREG_R30_PUERTA_SUSTRATO.md`
(sha `0a5b794e656390b13e33f14a40260f7a7818b13928f45db7d1a5312deb0caaaf`), posterior a la
**Enmienda A** (`b2ecac699fa097cc5d23ff0513ced1a05d683aff89c92a92312705961d9aec33`) y a la
**Enmienda B** (`116b78b06f82b0bcc9b2be2083390f0d5169577b3806ad5fe9152debd9dd9a0a`).

**Sigue sin calcularse nada contra R30.** Cuarto documento del mismo día, antes de tocar un dato.

**Lee R30 SIEMPRE con las enmiendas A, B y C.**

---

## Cómo apareció

La sesión A encontró que §5.4 invocaba «la familia de estratos declarados» sin declararla. Al
aplicar esa misma lección al resto de MI documento —barrer las referencias hacia adelante— salieron
las líneas 34 y 56: **«los intervalos de precio», sin definir sus bordes en ninguna parte.**

**Y no están definidos en ningún documento congelado.** `precio_bin` aparece **cero veces** en
`PREREG_R22_SKILL_LOCUS.md`; `R22_REPORT.md` sólo usa el nombre. La única definición del proyecto es
una línea de código:

```python
cells[f"precio_bin_0.1={min(int(r['p_mid'] * 10), 9)}"]     # scripts/run_r22.py:129
```

**El eje sobre el que descansa §2 —la restricción dura de R30, y el diagnóstico entero de por qué
R21 falló— vivía sólo en código.** Si esa línea cambia, §2 pasa a significar otra cosa **sin que
ningún documento lo registre**. Es el defecto 3 de nuestra propia auditoría —*una cita que resuelve
con confianza al sitio equivocado*— con el agravante de que el destino ni siquiera es un documento.

## Y la Enmienda B abrió el hueco que venía a cerrar

La definición real tiene **diez** niveles (0–9), no cinco. R22 observó poblados **sólo 0–4**, porque
una banda individual rara vez cotiza por encima de 0,5 cuando ~11 bandas reparten probabilidad 1.

**Y en la Enmienda B enumeré la familia con cinco celdas de precio.** Si en la muestra prospectiva
se poblara alguno de los intervalos 5–9 —otro régimen de mercado, otro reparto de bandas—
**quedarían fuera del máximo en silencio**, que es exactamente la libertad que §5.4 prohíbe.

**Cerré un hueco permisivo y abrí otro de la misma forma en el mismo acto.** Es el patrón que este
repositorio ya documenta en `upsert_many`: *«el cambio que quitó una trampa latente había
introducido otra de la misma forma, en la misma función, en el mismo commit.»*

---

## §0 nuevo — DEFINICIÓN CONGELADA DEL EJE DE PRECIO

> **§0 (nuevo, y gobierna todo uso de «intervalo de precio» en R30 y sus enmiendas)**
>
> ```
> precio_bin(p_mid) = min( int(p_mid * 10), 9 )        niveles 0 … 9
> ```
>
> `p_mid` es el punto medio del libro observado en el instante de decisión. Los bordes quedan
> **congelados por valor en este documento**, no por referencia al código: si `run_r22.py:129`
> cambiara, **manda esta definición** y la discrepancia es un defecto del código, no del
> preregistro.

## §5.4 enmendado por segunda vez — la familia de precio se fija por REGLA, no por enumeración

> **§5.4 (enmendado C)** — La familia del máximo es:
>
> | variable | niveles | celdas |
> |---|---|---|
> | `precio_bin` | **los niveles de §0 que cumplan la regla de ocupación de abajo** | variable |
> | `lead` | 9, 24 | 2 |
> | `unidad` | C, F | 2 |
> | `banda` | centro, cola_cercana, cola_lejana | 3 |
> | `anchura_fc` | baja, media, alta | 3 |
>
> **REGLA DE OCUPACIÓN, fijada aquí y aplicada mecánicamente:** un `precio_bin` entra en la familia
> **si y sólo si** contiene **≥ 150 eventos en la población post-borrado** — el mismo umbral que
> §4.2 (enmienda B). Ni se eligen intervalos ni se descartan: se cuenta y se aplica.
>
> **Las demás variables siguen CERRADAS por enumeración.** `estacion` sigue fuera, por la razón de la
> Enmienda B: §5.3 ya la usa como eje de borrado.

**Por qué una regla y no una lista.** Enumerar «0,1,2,3,4» presupone que la muestra prospectiva se
parecerá a la retrospectiva, que es justamente lo que R30 existe para no dar por supuesto. Y dejarlo
abierto invitaría a elegir después. **Una regla numérica fijada de antemano no es discrecional: la
población decide y el umbral estaba escrito antes.**

## §2 y §5.1, precisados en consecuencia

- **§2** — «BSS positivo dentro de los intervalos de precio, con el intervalo `0` incluido» se lee
  ahora: **dentro de cada `precio_bin` de la familia de §5.4**, y el `0` está incluido siempre
  porque supera el umbral con enorme holgura (79,2 % de las filas en R22).
- **§5.1** — «en cada uno de los cinco intervalos» se lee: **en cada `precio_bin` de la familia**.
  El requisito de límite inferior del IC > 0 pasa de «al menos tres de los cinco» a **«al menos el
  60 % de los intervalos de la familia, redondeando hacia arriba»** — que sobre cinco da tres, o
  sea, idéntico a lo escrito, y deja de romperse si la familia tiene otro tamaño.

## Lo que NO cambia

§1, §3, §4.1, §4.2 (con enmiendas A y B), §4.3, §5.2, §5.3, §6, §7 y §8. Sigue en pie §6.2 —«lo
contiene pero el coste se lo come»— como desenlace *a priori* más probable, por el semidiferencial
medido de **0,0168** frente al 0,0100 supuesto por R21.

## Nota de método

**Cuatro documentos, un día, tres defectos, todos de la misma forma: afirmar sobre una magnitud sin
medirla.** Dos los encontró la otra sesión; el tercero salió de aplicar la lección de la otra sesión
al resto de mi propio documento. **Ninguno lo vio quien lo escribió, en el momento de escribirlo.**

Y el de esta enmienda añade una advertencia que vale para todo el proyecto: **una enmienda es un
cambio de código con otro nombre, y puede introducir la misma clase de defecto que viene a
corregir.** Se revisa igual que se revisa un parche.
