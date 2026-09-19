# Spec-X 06 — El escritor se contradice con el hecho delante

**Estado:** propuesta, sin implementar. Salió midiendo X-05, no buscándola.

## El dato

De las 6 contradicciones del brazo de control de X-05 (dos novelas de 15 capítulos, 29 cortes de QA),
clasificadas con `herramientas/ceguera_del_filtro.py`:

| clase | cuántas |
|---|---|
| **el hecho estaba en su prompt y lo contradijo igual** | **4** |
| el hecho no le llegó (ceguera del filtro, lo que ataca X-05) | 1 |
| no se pudo atar a un hecho | 1 |

El caso más claro, en `esclusas`. En el prompt del capítulo 14 iba, literal:

> «Ilya Prost ha perdido toda comunicación con el puente; ni el canal principal ni el técnico de
> emergencia responden.»

Y el capítulo 14 pone a Prost respondiendo por el canal técnico, recibiendo una orden y cerrando una
válvula. El mismo fallo se repite en el 15.

**Cuatro de cada seis contradicciones no son un problema de información, son de atención.** Ningún
filtro las arregla: mejorar lo que el escritor recibe no sirve de nada si no respeta lo que ya tiene.

## Por qué pasa, probablemente

Son hipótesis; ninguna está medida todavía.

**Los hechos son una lista plana de cincuenta líneas.** En el capítulo 14 el prompt lleva 50 hechos
con el mismo formato y el mismo peso visual. Un hecho que prohíbe algo --«no hay comunicación»-- se
lee igual que uno que solo informa. Lo que la escena pide a gritos (que dos personajes hablen) compite
con una línea entre cincuenta.

**Nada distingue lo que el capítulo no puede hacer.** El prompt dice qué ha pasado, no qué está
vedado. Un hecho negativo --una avería, una puerta sellada, una muerte-- es una restricción dura, y
va mezclado con los descriptivos.

**El objetivo narrativo empuja en contra.** La escaleta pide una escena concreta, y si esa escena
necesita una conversación, el escritor la escribe. La restricción está en el prompt, pero el encargo
es lo último que lee y lo que manda.

## Qué se podría probar, de más barato a más caro

**1. Separar las restricciones del resto.** Que el extractor marque los hechos que prohíben algo
(categoría o campo nuevo) y que el prompt los saque de la lista general a un bloque propio, corto,
titulado como lo que es: lo que este capítulo no puede contradecir. Cambia el prompt, no la
arquitectura.

**2. Ponerlas al final, pegadas al encargo.** Hoy los hechos van antes del objetivo narrativo. Lo
último que se lee pesa más, y hoy lo último es la petición de escribir la escena.

**3. Que el escritor declare qué restricciones respetó.** Una línea en su retorno, como ya declara
palabras y personajes. No garantiza nada, pero obliga a mirarlas, y deja medir si las vio.

**4. Un paso de comprobación antes de cerrar el capítulo.** Lo más caro: otra pasada que cruce el
texto contra las restricciones. Es lo que ya hace QA, así que probablemente no compense --duplicaría
el corte-- salvo que resulte mucho más barato por ser más estrecho.

## Cómo se mide

Con la herramienta que ya existe: `ceguera_del_filtro.py` separa las dos clases. El número a mover es
**«con el hecho delante»**, que hoy es 4 de 6.

Y con la misma cautela que X-05: la variación entre novelas del mismo brazo es de 5 contradicciones a
1, así que hará falta emparejar por premisa y mirar la clase, no el total.

## Por qué esto puede importar más que X-05

X-05 ataca 1 de cada 6 contradicciones; esto ataca 4. Si la proporción aguanta en más novelas --son
seis casos, muy pocos-- el margen de calidad está aquí y no en el filtro.
