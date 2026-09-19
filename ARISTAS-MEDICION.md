# Medir Spec-X 05: qué se compara y qué se ha visto

19/09/2026, rama `specs/aristas`. Cuatro novelas de quince capítulos: tres de control y una con el
interruptor encendido. **Veredicto corto: el mecanismo de X-05 funciona y está medido; su efecto
sobre la calidad final no se puede demostrar con esta muestra, y probablemente sea pequeño, porque
solo 1 de cada 9 contradicciones es del tipo que arregla.**

## El diseño

Previsto: seis novelas de **15 capítulos** × 400 palabras, tres premisas por las dos variantes.
Ejecutado: las tres de control y **una** con aristas, por lo que explica la sección «X-05 ataca una
minoría del problema».

| brazo | `aristas_en_continuidad` | qué hace el filtro |
|---|---|---|
| `sin-aristas` | `false` | el de siempre: entra el hecho si su sujeto está en escena o es la locación |
| `con-aristas` | `true` | además, si el hecho toca (`relacionados`) a alguien en escena; y recorta por puntuación si no cabe |

Tres decisiones del diseño, cada una comprada con un error anterior:

**Quince capítulos y no tres.** Con tres cabe todo en el presupuesto del escritor y los dos brazos
darían idéntico resultado. El filtro solo puede fallar cuando deja algo fuera.

**Las mismas premisas en los dos brazos.** Medido el 19/09: la misma variante tardó 18,6 y 25,2
minutos según el juego de premisas. La dificultad de la premisa mueve los resultados más que
cualquier cambio de arquitectura, así que comparar medias de juegos distintos no mide nada.

**El campo `relacionados` solo aparece en el esquema del delta con el interruptor encendido.** Si el
brazo de control viera el mismo prompt, los dos se diferenciarían en algo más que el filtro.

**Premisas escritas para que la arista pueda existir**: tripulaciones de seis a ocho que se separan
pronto y siguen separadas. En una novela donde todos van juntos no hay ningún hecho «de alguien que
no está en escena», y no habría nada que arreglar.

## El brazo de control, completo (n=3)

| novela | reloj | contradicciones | coste |
|---|---|---|---|
| esclusas | 105,0 min | 5 | 22,67 $ |
| relevos | 88,9 min | 1 | 17,69 $ |
| descenso | 92,2 min | 3 | 17,87 $ |
| **media** | **95,4 min** | **3,0** | 19,4 $ |

Las tres corrieron con **tres agentes**, no con dos. No era lo previsto: `campos_de_encargo` solo
ponía por defecto dos interruptores, y lo que el encargo no decía llegaba al formulario como casilla
desmarcada, o sea apagado, así que el valor por defecto del harness no se respetaba por esa vía.
Está arreglado, pero estas cifras son de la configuración de tres agentes.

**El defecto existe y aparece donde la spec decía.**

| capítulos | cortes de QA | contradicciones |
|---|---|---|
| 1–11 | 11 | **0** |
| 12, 14, 15 | 4 | **5** |

Y una de ellas es el caso de la spec, aparecido solo. En el capítulo 8 quedó establecido:

> «El intercomunicador de máquinas no consigue enlace con el puente; la línea no responde.»
> — sujeto: `sala de máquinas`

Ese hecho **no llegó al escritor en los capítulos 14 ni 15**: su sujeto es una locación que no era la
de esas escenas, así que el filtro lo descartó. El escritor, que no puede leer capítulos anteriores
ni preguntar, escribió a dos personajes hablando por esa radio. QA lo marcó las dos veces.

Con `relacionados` ese hecho llevaría a los personajes a los que deja incomunicados, y el salto de
vecindad se lo entregaría al capítulo 14 aunque la escena no transcurra en máquinas.

Cuidado al leerlo: **esto demuestra que el brazo de control falla, no que el otro lo arregle.**

## Pero X-05 ataca una minoría del problema

Clasificando las 9 contradicciones de las tres novelas con `herramientas/ceguera_del_filtro.py`:

| clase | cuántas |
|---|---|
| **el hecho estaba en su prompt y lo contradijo igual** | **7** |
| ceguera del filtro (lo que X-05 arregla) | 1 |
| no se pudo atar a un hecho | 1 |

**Siete de cada nueve contradicciones no son un problema de información sino de atención**, y ningún
filtro las arregla. De ahí sale `spec-x-06`, que apunta a un margen siete veces mayor.

Esto cambió el plan. Tres novelas con aristas (5 h, ~58 $) para detectar un cambio de una
contradicción sobre nueve, con una variación entre novelas del mismo brazo que va de 1 a 5, habrían
dado «no concluyente» pasara lo que pasara. Se corrió **una sola**, y no para comparar
contradicciones sino para medir el mecanismo, que no tiene ruido.

## El brazo con aristas (n=1): el mecanismo funciona

`esclusas` con el interruptor encendido: 114,1 min, 19,68 $, 6 contradicciones.

**El campo se rellena, y bien. Lo rellena el extractor**, que es quien escribe el delta con tres
agentes; el extractor corrió 19 veces en esta novela. 51 de 84 hechos (61 %) traen `relacionados`, y
de 11 nombres distintos 8 son personajes del registro. Ejemplo real:

> `Ramiro Solís` → `["Inés Vasconcelos", "Tomás Aguirre"]`
> «Ramiro Solís desapareció en los conductos de ventilación durante la ronda…»

Los otros 3 nombres son locaciones o `mundo`. No rompen nada, pero tampoco sirven: el salto compara
contra los personajes en escena, así que una locación en `relacionados` nunca casa. Si X-05 sigue
adelante, conviene decírselo al que rellena el campo.

**Queda sin comprobar lo que más importa para producción:** con `escritor_emite_delta` encendido el
delta lo escribe el **escritor**, no el extractor, y esa es la configuración que se envía. Que el
escritor rellene `relacionados` igual de bien es una suposición, no una medida. El escritor trabaja
sin haber leído los capítulos anteriores y con el capítulo recién escrito en la cabeza, así que no
hay razón para darlo por hecho en ninguna de las dos direcciones.

**El salto tiene alcance.** Contando sobre el log y la escaleta reales, **212 de 971 inyecciones de
hecho (22 %) entran solo por la arista**: unos 14 por capítulo que el filtro viejo escondía.

**Emparejado con su control, misma premisa:**

| | sin aristas | con aristas |
|---|---|---|
| contradicciones | 5 | 6 |
| **cegueras del filtro** | **1** | **0** |
| hechos entrados por la arista | — | 212 (22 %) |

La ceguera desapareció, que es exactamente lo que el cambio promete. Pero **1 → 0 es un solo suceso**
y el total subió de 5 a 6, dentro del ruido (el control fue de 1 a 5). Lo honesto: el mecanismo está
demostrado, su efecto sobre la calidad final no.

## Hallazgo lateral: en novelas largas, QA es el actor caro

No lo buscábamos. En `esclusas`, tokens de salida:

| rol | tokens |
|---|---|
| qa | **86.305** |
| escritor | 40.538 |

**La auditoría gasta el doble que escribir la novela.** En las novelas de 3 capítulos era al revés.
La causa es estructural: hay un corte por capítulo y la muestra que el revisor cruza crece con el
libro, así que el coste de QA sube más deprisa que el del texto. No es un fallo --revisar cada
capítulo sigue siendo más rápido que revisar cada tres, medido el 19/09-- pero es la primera vez que
el revisor domina el presupuesto, y merece su propia vuelta.

## Lo que este experimento NO va a medir

**El recorte por puntuación.** Medido sobre la novela en curso: 39 hechos en el capítulo 8 ocupan
1.998 tokens, el 17 % del tope de 12.000, y el prompt entero va por 7.655. Proyectado a 15 capítulos,
los hechos no pasan del 31 % del presupuesto. **Cabe todo, así que el recorte no se activa ni una
vez.** Queda cubierto por sus pruebas unitarias y sin ejercitar en real; es un seguro para novelas de
30 capítulos. Forzarlo pediría bajar `max_tokens_contexto_escritor`, y eso mediría otra cosa: cómo se
degrada el harness con poco contexto.

## Coste

Una novela de 15 capítulos: **95 minutos y 19,4 $** de media. La estimación previa era de una hora y
17 $; se quedó corta en las dos cosas. Las cuatro corridas suman unas 6,7 horas y ~78 $. Las seis del
plan original habrían sido diez horas y media y ~136 $.

## Qué haría falta para cerrar X-05

1. **Decidir si merece la pena.** Ataca 1 de cada 9 contradicciones; `spec-x-06` ataca 7. Si hay una
   sola vuelta disponible, es la otra.
2. **Si sigue adelante**: repetir con `escritor_emite_delta` encendido, que es la configuración que
   se envía, y decirle a quien rellena `relacionados` que ponga personajes y no locaciones.
3. **Medir por cegueras, no por contradicciones totales.** El total varía de 1 a 5 entre novelas del
   mismo brazo; las cegueras son pocas y directamente atribuibles al filtro.
