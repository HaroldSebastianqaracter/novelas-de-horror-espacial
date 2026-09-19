# Medir Spec-X 05: qué se compara y qué se ha visto

En curso desde el 19/09/2026, rama `specs/aristas`. Este documento se escribe mientras corre, así que
las secciones marcadas **(provisional)** cambiarán.

## El diseño

Seis novelas de **15 capítulos** × 400 palabras, tres premisas escritas por las dos variantes:

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

## Lo que ya enseñó el brazo de control (provisional, n=1)

`esclusas`: 15 capítulos, **105 min**, 22,67 $, **5 contradicciones**, 3 correcciones automáticas.

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

Cuidado al leerlo: **esto demuestra que el brazo de control falla, no que el otro lo arregle.** Eso
depende de que el escritor rellene bien `relacionados`, que es lo único del cambio que no se puede
cubrir con pruebas.

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

Una novela de 15 capítulos: **105 minutos y 22,67 $**. Las seis: unas diez horas y media y ~136 $.
La estimación previa era de una hora y 17 $ por novela; se quedó corta en las dos cosas.
