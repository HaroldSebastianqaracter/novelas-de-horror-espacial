# Qué aprendimos midiendo la velocidad del harness

Veintinueve novelas escritas de punta a punta entre el 18 y el 19 de septiembre de 2026, sin
intervención humana, en la rama `specs/velocidad`. Cada una deja una fila en `09_archivo/corridas.csv`
con 47 columnas: reloj, trabajo y tokens por agente, guardarraíles de calidad y los ajustes con los
que se escribió. Todo lo que sigue sale de ahí.

Condiciones iguales en todas: 3 capítulos de 400 palabras, premisas fijas con la amenaza a la vista
desde el capítulo 1, tres novelas por variante.

## El resultado

La medición que vale es la última, porque es la única **emparejada**: las mismas tres premisas
escritas por las dos variantes. Comparar medias entre juegos de premisas distintos no dice nada, por
la razón que explica la sección siguiente.

| premisa | base | dos-agentes-sonnet | Δ reloj | contradicciones | correcciones | coste |
|---|---|---|---|---|---|---|
| nido | 25,7 min | 13,2 min | −49 % | 2 → 0 | 1 → 0 | 6,83 → 3,17 $ |
| carga | 26,1 min | 13,1 min | −50 % | 1 → 0 | 1 → 0 | 5,83 → 2,92 $ |
| sombra | 23,9 min | 12,9 min | −46 % | 1 → 0 | 1 → 0 | 6,33 → 4,00 $ |
| **media** | **25,2** | **13,1** | **−48 %** | 4 → 0 | 3 → 0 | −47 % |

Buscábamos un 20 % de reloj. Sale un 48 %, con 0,2 minutos de dispersión, sin una sola excepción en
tres pares, y con el coste a poco más de la mitad. `dos-agentes-sonnet` es el escritor emitiendo su
propio delta (Spec-X 04, sin agente extractor) con el orquestador en sonnet.

**No es solo que haya menos agentes: es que se equivoca menos.** La base gastó una corrección en cada
una de las tres novelas y `dos-agentes-sonnet` ninguna. Con las cifras de las premisas 1–3, donde la
base no corrigió nada y tardó 18,6 minutos, una corrección cuesta unos 6,6 minutos: rehacer el
capítulo y volver a auditarlo, los dos en serie y los dos en el camino crítico. De los doce minutos
de ventaja, la mitad es no tener que corregir y la otra mitad es la arquitectura.

Se comprobó que los ceros no son ausencia de trabajo: QA corrió sus tres cortes en las seis novelas,
con 10.000–15.000 tokens de salida en las dos variantes.

**Aviso sobre la columna de coste.** `claude-sonnet-5` no estaba en `config/precios.json`, y el coste
se calcula con esa tabla, así que el orquestador de las novelas sonnet entró a 0,00 $ y el CSV marcó
2,54 $ de media cuando eran 3,36 $. El ahorro es del 47 %, no del 61 % que dijo este documento
durante unas horas. **El reloj no está afectado**, porque el tiempo se mide, no se tarifa. La entrada
ya está puesta, con la advertencia de que es tarifa publicada y no derivada de una traza como las
otras dos.

## La premisa pesa más que la arquitectura

El hallazgo incómodo, y el que obliga a rehacer cómo leemos el CSV.

La misma variante `base` tardó **18,6 minutos sobre las premisas 1–3 y 25,2 sobre las 4–6**. Son 6,6
minutos de diferencia sin cambiar una línea del harness: más de lo que movió cualquier cambio de
arquitectura que probamos antes de esto. La dificultad de lo que se pide a escribir domina el reloj.

De ahí la regla: **una variante solo se compara con otra sobre el mismo juego de premisas.** Las
tablas por medias que llenaron este documento hasta el 19/09 mezclaban juegos y por eso daban
diferencias del 1 al 9 %, indistinguibles del ruido. Emparejando, la misma diferencia salta al 48 %.

## El «cero contradicciones» de la base era suerte

Durante un día entero este documento dijo que la base era la variante limpia: cero contradicciones.
Eran **dos novelas, seis cortes**. Con la tasa que mostraban las otras variantes, 0,22 por corte, seis
cortes limpios seguidos salen por azar una de cada cuatro veces.

Con tres novelas más, la base dio contradicción en **las tres**, una corrección en cada una. No era
una propiedad de la variante. Era el tamaño de la muestra.

## La regla que explica las variantes intermedias

**Lo que está solapado es casi gratis, y quitarlo no ahorra: empeora.**

El extractor parecía el culpable evidente: se lleva 12 de los 18 minutos de trabajo de una novela y
emite entre 6.000 y 11.000 tokens para dejar un archivo de 1.200. Pero corre **mientras** el escritor
redacta el capítulo siguiente. En la novela base los agentes suman 25,3 minutos de trabajo y el reloj
marca 20,0: seis minutos regalados por solapar.

Lo mismo, y más claro, con la auditoría: **revisar cada capítulo no es un coste, es un ahorro.** Pasar
a un corte cada tres capítulos salió un 21 % más lento y con tres contradicciones por novela en vez de
una. El corte por capítulo va solapado con el siguiente; el corte único al final no tiene con qué
solaparse, y encima encuentra de golpe contradicciones que llevaban dos capítulos acumulándose, cada
una obligando a rehacer un capítulo en serie. Los tokens del escritor se doblaron, de 4.333 a 8.685,
reescribiendo lo que se había roto hacía rato.

**El camino crítico es escritor + QA**, porque la auditoría necesita el capítulo terminado. El
orquestador no lo es: medido, 0,8 minutos de 20, el 8 %. Todo lo demás ya está escondido detrás, y
acelerar lo que está escondido no se nota.

Esto convive con el resultado de arriba sin contradecirlo: quitar el extractor por sí solo daba un
9 % que caía dentro del error. Lo que rinde es quitarlo **y** que el escritor, que ya tiene el
capítulo en la cabeza, anote los hechos él mismo, que es donde se van las contradicciones.

## Lo que se arregló por el camino

Ninguno de estos fallos se buscaba; todos salieron de mirar por qué una novela no terminaba.

**El escritor no podía corregirse.** Cuando la auditoría encontraba una contradicción, el harness
mandaba rehacer el capítulo, pero el escritor no tiene herramienta de lectura por diseño y el cliente
exige haber leído un archivo antes de sobrescribirlo. Su escritura se rechazaba, y —esto es lo
grave— su validación daba «válido» sobre el archivo viejo e intacto. Una corrección que no ocurrió se
anotaba como éxito. Tres novelas la dieron por buena sin cambiar una coma.

**El preludio anotaba leyes que la trama tenía que desmentir.** «Entre la bodega y la sala de
máquinas no hay ningún pasillo de servicio» es exactamente lo que el capítulo 2 necesita negar para
que haya novela. Ahora esos hechos se rechazan al guardarlos, con un mensaje que enseña a
reformularlos: lo que dice un registro, no lo que el mundo es.

**Un personaje en dos sitios a la vez.** El hecho decía que estaba de guardia en el puente y el
capítulo la mataba en otra cubierta. Las dos cosas pueden ser ciertas, pero alguien tiene que narrar
el viaje, y en 400 palabras no cabía: el escritor lo contaba a saltos y se contradecía. También se
rechaza al guardar.

**Un CSV que se descuadraba en silencio.** Al añadir columnas, las filas nuevas se escribían bajo la
cabecera vieja y los valores quedaban corridos un sitio. Nada avisa, porque un CSV mal alineado se
lee igual de bien. Era el peor de todos: iba directo contra los datos con los que decidimos.

## Lo que no hay que hacer

**No montar un grafo de eventos.** El estado completo de una novela de 30 capítulos son unos 138
hechos, medidos sobre 385 hechos reales: unos 5.400 tokens, que caben cuatro veces en el presupuesto
del escritor. Las herramientas de grafo existen para corpus que no caben. Lo que sí falta es que el
filtro vea relaciones, y eso se arregla con un campo más en cada hecho, no con un grafo (Spec-X 05).

**No reordenar los prompts por la caché.** Ya entra el 80 % por caché en el escritor y en QA, y el
98 % en el orquestador; la entrada fresca del escritor son ocho tokens por invocación. Ver el detalle
en `PROXIMOS-PASOS.md`.

**No sacar conclusiones de medias entre juegos de premisas distintos.** Ver más arriba.

## QA no aprueba por vago: comprobado

La explicación alternativa que habría tumbado el titular era que el verificador fuese blando. Si QA
aprobara sin mirar, el «cero contradicciones» de `dos-agentes-sonnet` no significaría nada y la mitad
de la ventaja de reloj sería contable, no real.

`herramientas/contradiccion-inyectada.py` corre el corte de verdad --subagente `qa` en opus, con
hooks-- dos veces sobre la misma novela: intacta, y con un párrafo que niega a la cara un hecho de
canon del preludio. Resultado:

| vuelta | `tiene_contradicciones` | manifiesto | hallazgos |
|---|---|---|---|
| control | `false` | `en_progreso` | 3 repeticiones de estilo, ninguna contradicción |
| inyectado | `true` | `pausado_por_qa` | la contradicción inyectada, la primera de la lista |

Cazó el párrafo, lo identificó como afirmación en voz del narrador --no un personaje equivocándose,
que es la distinción que importa-- y pausó la novela. Y en el control calló sobre continuidad
mientras seguía marcando estilo, así que tampoco marca por sistema.

## Lo que se encontró montando ese test

**`corte-qa` estaba rota y nadie podía saberlo.** Su `allowed-tools` no declaraba `Write`, mientras
que las otras dos skills que despachan subagentes que escriben sí lo hacen. Su subagente `qa` leía la
muestra, producía el análisis completo --`0 contradicciones · 3 repeticiones`, con acumulados por
capítulo-- y después no podía persistir ni uno de los tres archivos. La skill no ha funcionado nunca.
No se veía porque en producción el corte va dentro de `escribir-tanda`, que sí lo declara.

Es el mismo patrón que el fallo del escritor de ayer: **trabajo hecho de verdad que se pierde en el
último paso, el de escribir.** Dos en dos días sugiere mirar si hay más.

**H-06 compara rutas como texto.** Corriendo el harness desde otra raíz, la forma corta de Windows
(`HAROLD~1.ROD`) y la larga del mismo directorio le parecen sitios distintos, y bloquea escrituras
que están dentro de `06_qa/`. En una corrida normal no aparece, porque el árbol siempre se nombra
igual; para cualquier herramienta que corra sobre una copia, es una mina.

## Lo siguiente

El objetivo del loop está cumplido con margen y verificado, así que lo que queda ya no es velocidad.
Spec-X 05, que no es velocidad sino coherencia a partir del capítulo 10.
