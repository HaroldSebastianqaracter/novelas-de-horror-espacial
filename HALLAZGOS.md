# Qué aprendimos midiendo la velocidad del harness

Veinte novelas escritas de punta a punta entre el 18 y el 19 de septiembre de 2026, sin intervención
humana, en la rama `specs/velocidad`. Cada una deja una fila en `09_archivo/corridas.csv` con 47
columnas: reloj, trabajo y tokens por agente, guardarraíles de calidad y los ajustes con los que se
escribió. Todo lo que sigue sale de ahí.

Condiciones iguales en todas: 3 capítulos de 400 palabras, diez premisas fijas con la amenaza a la
vista desde el capítulo 1, tres novelas por variante.

## El resultado

| variante | reloj | contradicciones | coste |
|---|---|---|---|
| **dos-agentes** (el escritor emite su delta) | **16,8 ±2,4 min** | 0,7 | 5,8 $ |
| orquestador en sonnet | 18,3 ±2,7 min | 0,7 | **2,7 $** |
| base (3 agentes, opus, QA cada capítulo) | 18,6 ±2,0 min | **0,0** | 5,4 $ |
| QA cada 3 capítulos | 22,5 ±1,2 min | 3,0 | 5,5 $ |

Buscábamos un 20 % menos de reloj. **Lo mejor que encontramos es un 9 %, y cae dentro de una
desviación típica.** No es un resultado que se pueda defender todavía.

## La regla que explica las cuatro filas

**Lo que está solapado es casi gratis, y quitarlo no ahorra: empeora.**

El extractor parecía el culpable evidente: se lleva 12 de los 18 minutos de trabajo de una novela y
emite entre 6.000 y 11.000 tokens para dejar un archivo de 1.200. Pero corre **mientras** el escritor
redacta el capítulo siguiente. En la novela base los agentes suman 25,3 minutos de trabajo y el reloj
marca 20,0: seis minutos regalados por solapar.

Quitarlo del todo quitó 7,4 minutos de trabajo y 0,4 de reloj. El solapamiento pasó de +5,4 minutos
ganados a −1,7 perdidos, porque un solo agente haciendo las dos cosas las hace en serie.

Lo mismo, y más claro, con la auditoría: **revisar cada capítulo no es un coste, es un ahorro.**
Pasar a un corte cada tres capítulos salió un 21 % más lento y con tres contradicciones por novela en
vez de cero. El corte por capítulo va solapado con el siguiente; el corte único al final no tiene con
qué solaparse, y encima encuentra de golpe contradicciones que llevaban dos capítulos acumulándose,
cada una obligando a rehacer un capítulo en serie. Los tokens del escritor se doblaron, de 4.333 a
8.685, reescribiendo lo que se había roto hacía rato.

**El camino crítico es escritor + QA + orquestador**, porque la auditoría necesita el capítulo
terminado. Todo lo demás ya está escondido detrás, y acelerar lo que está escondido no se nota.

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
filtro vea relaciones, y eso se arregla con un campo más en cada hecho, no con un grafo.

**No tocar el extractor.** Está fuera del camino crítico.

## Lo siguiente

Combinar las dos variantes que no se pisan: el escritor emitiendo su delta y el orquestador en
sonnet. En teoría, el 9 % de reloj con la mitad del coste.

Y si el 20 % sigue haciendo falta, hay que atacar el camino crítico de verdad, que es el escritor y
la auditoría. Nada de lo que hemos probado los toca.
