# Spec-X 01 · El reintento del escritor cuesta el 22 % de la tirada

**Estado:** X-01.1 y X-01.2 implementadas (commit pendiente). X-01.3 sigue abierta.
**Alcance:** una sola mejora. No toca el bucle, ni las fases, ni el QA.
**Base:** `especificacion-tecnica-harness-novela-terror.md` v1.9, §17 (antirrepetición) y RF-08.4 (validación)
**Evidencia:** traza Langfuse de `tanda_2026-09-16T19-30-34` (capítulos 4, 5 y 6) y `07_registro/` de esa tanda

---

## 1. Qué se midió

Una tanda real de tres capítulos, publicada en Langfuse. Siete invocaciones de subagente,
1,47 M de tokens, 23 minutos de reloj, 2,56 $.

| Agente | Turnos | Validaciones | Salida | Caché leída | Total | Coste |
|---|---:|---:|---:|---:|---:|---:|
| `escritor:cap_4` | 6 | 2 | 7.591 | 134.789 | 173.267 | 0,450 $ |
| `escritor:cap_5` | 6 | 2 | 7.118 | 141.773 | 175.874 | 0,417 $ |
| `escritor:cap_6` | 8 | **3** | 12.095 | 220.856 | 265.636 | **0,617 $** |
| `extractor:cap_4` | 7 | 1 | 3.691 | 116.302 | 139.881 | 0,055 $ |
| `extractor:cap_5` | 7 | 1 | 4.336 | 117.983 | 142.101 | 0,058 $ |
| `extractor:cap_6` | 6 | 1 | 4.492 | 96.330 | 120.927 | 0,057 $ |
| `qa:cap_6` | 10 | 1 | 15.751 | 382.355 | 449.958 | 0,909 $ |

## 2. El hallazgo

La secuencia de escrituras y validaciones, reconstruida del registro:

```
19:33:41  WRITE    cap_4.md
19:33:46  VALIDAR  cap 4  -> codigo 1
19:34:32  WRITE    cap_4.md          <- el capítulo entero, otra vez
19:34:35  VALIDAR  cap 4  -> ok
19:39:24  WRITE    cap_5.md
19:39:29  VALIDAR  cap 5  -> codigo 1
19:40:16  WRITE    cap_5.md          <- otra vez
19:40:19  VALIDAR  cap 5  -> ok
19:45:33  WRITE    cap_6.md
19:45:38  VALIDAR  cap 6  -> codigo 1
19:46:28  WRITE    cap_6.md          <- otra vez
19:46:31  VALIDAR  cap 6  -> codigo 1
19:47:16  WRITE    cap_6.md          <- y otra
19:47:19  VALIDAR  cap 6  -> ok
```

**La primera validación falla en los tres capítulos.** No es mala suerte: es el
comportamiento por defecto. Cada fallo obliga a reescribir el capítulo **completo**.

Los spans de capítulo de la traza lo cuentan por su cuenta, y coinciden:

| Span | `validaciones_invalidas` | `invocaciones_escritor` |
|---|---:|---:|
| `cap_4` | 1 | 1 |
| `cap_5` | 1 | 1 |
| `cap_6` | **2** | 1 |

El escritor se invoca **una sola vez** por capítulo: los reintentos ocurren dentro de
esa invocación, y por eso cada uno arrastra una lectura de contexto completa.

El coste de un reintento sale de restar dos filas de la tabla, que solo se
diferencian en eso:

| | cap. 5 (1 fallo) | cap. 6 (2 fallos) | diferencia |
|---|---:|---:|---:|
| Turnos | 6 | 8 | **+2** |
| Tokens de salida | 7.118 | 12.095 | **+4.977** |
| Tokens totales | 175.874 | 265.636 | **+89.762** |
| Coste | 0,417 $ | 0,617 $ | **+0,200 $** |
| Duración | 4m 23s | 5m 19s | **+56 s** |

**Un reintento cuesta ~90.000 tokens, 0,20 $ y casi un minuto.**

Proyectado a los 30 capítulos, con un solo fallo por capítulo —que es el mínimo
observado—: **2,7 M de tokens, unos 6 $ y 25 minutos**, sobre una tirada estimada en
27 $. **El 22 % de la tirada se gasta en reescribir capítulos que ya estaban escritos.**

## 3. La causa

No es que el escritor escriba mal. Es la combinación de tres cosas:

**a) El validador aplica una regla que el escritor no puede cumplir a ciegas.**
RF-05.5 prohíbe repetir literalmente 4 o más palabras con contenido de un capítulo
anterior. Pero INV-01 le impide leer los capítulos anteriores. No puede evitar la
coincidencia por construcción: solo puede descubrirla fallando.

El registro lo confirma: los eventos `validacion` de la tanda guardan la lista de
errores de cada intento fallido, y **los cuatro fallos son RF-05.5 y solo RF-05.5**.

| Fallo | Pasajes repetidos | Palabras del borrador | Regla |
|---|---:|---:|---|
| cap. 4, intento 1 | 5 | 1.386 | RF-05.5 |
| cap. 5, intento 1 | 4 | 1.247 | RF-05.5 |
| cap. 6, intento 1 | 11 | 1.474 | RF-05.5 |
| cap. 6, intento 2 | 2 | 1.386 | RF-05.5 |

Los cuatro borradores estaban **dentro de la tolerancia de longitud**. Ni una sola vez
falló por extensión ni por encabezados: es siempre la antirrepetición.

Los capítulos 2 y 3, escritos antes de que la comprobación estuviera activa, conservan
**4 y 9** repeticiones literales en su versión final. Los capítulos 4, 5 y 6 tienen
**0** — a cambio de una reescritura entera cada uno.

**b) El validador ya sabe exactamente qué sobra, y ese dato se tira.**
`validar-capitulo` devuelve los pasajes y su capítulo de origen:

```
RF-05.5: 9 pasaje(s) repiten literalmente 4 o más palabras con contenido de un
capítulo anterior; reescribilos con otras palabras: «El metal estaba frío» (cap. 1,
4 palabras); «la mano en el hombro» (cap. 2, 5 palabras); «Aviso de mantenimiento
—dijo» (cap. 2, 4 palabras); ...
```

Son tres frases de cinco palabras. El arreglo real son unos 40 tokens.

**c) El prompt del escritor le ordena la reescritura total.** Literalmente:

> «Si devuelve errores, **corregí el archivo completo con Write** y volvé a ejecutar el
> mismo comando, hasta tres veces en total.»

Ahí está el desperdicio: se paga la regeneración de 1.400 palabras para cambiar tres.

## 4. La propuesta

Tres cambios, del más barato al más discutible.

### X-01.1 · El reintento se hace con `Edit`, no con `Write`

Cambiar esa frase del prompt del escritor por una que le diga que corrija **solo los
pasajes señalados** con `Edit`, y que reserve `Write` para cuando el error sea de
longitud o de encabezados, que sí son del archivo entero.

Hizo falta además **darle la herramienta `Edit`**, que no tenía (`tools: Write, Bash`).
Eso amplía su superficie, así que la comprobación obligada era si el hook la vigila: la
vigila. `H-06` filtra por `HERRAMIENTAS_ESCRITURA = ("Write", "Edit", "MultiEdit",
"NotebookEdit")`, de modo que `Edit` queda acotado al único archivo del capítulo,
exactamente igual que `Write`. INV-01 no se toca: sigue sin `Read`.

Sin cambios de esquema ni del bucle.

Ahorro esperado: los ~5.000 tokens de salida por reintento bajan a unos 200. El turno
sigue costando su lectura de caché, así que la estimación prudente es **la mitad del
coste del reintento**, unos **3 $ y 12 minutos** en los 30 capítulos.

### X-01.2 · El registro anota por qué falló la validación

**Corrección sobre la primera versión de esta spec.** Decía que el registro no guarda
el motivo del fallo. Es falso: sí lo guarda, en un evento `validacion` con la lista
completa de errores. El agujero estaba un paso más allá — ese evento **no llegaba a
Langfuse**, que publicaba `0 eventos`. El dato existía y nadie lo veía.

El cambio, por tanto, es en el exportador: cada validación fallida viaja como un evento
de la traza. Y viaja **solo con el código de regla y los recuentos**, porque los
mensajes de error citan pasajes literales del manuscrito y §16.6 prohíbe que la prosa
de la novela salga de la máquina.

```json
{"name": "validacion:escritor", "statusMessage": "RF-05.5",
 "metadata": {"reglas": ["RF-05.5"], "errores": 1,
              "palabras": 1386, "repeticiones_literales": 5}}
```

No ahorra un solo token. Es lo que permite comprobar si X-01.1 funciona, y lo que evita
que el próximo diagnóstico vuelva a ser una conjetura.

### X-01.3 · Revisar el umbral de 4 palabras

Los pasajes que la regla marca son, en buena parte, español corriente: «El metal estaba
frío», «la mano en el hombro», «El aire de dentro». Una novela de 30 capítulos con los
mismos seis personajes en la misma nave va a repetir sintagmas de cuatro palabras sin
que eso sea un defecto de estilo.

La regla hace falta —los capítulos 2 y 3 demuestran qué pasa sin ella—, pero el umbral
es discutible. Subirlo a 5 palabras con contenido, o exigir 3 palabras léxicas en vez
de 2, reduciría los falsos positivos.

**Esto sí cambia el resultado literario, no solo el coste.** Va aquí como pregunta
abierta, no como recomendación: hay que medirlo con una tanda antes de decidir.

## 5. Cómo se comprueba

Con X-01.2 puesto, una tanda de tres capítulos da la respuesta directamente:

1. Número de validaciones fallidas por capítulo. Hoy: 1, 1, 2.
2. Tokens de salida por capítulo. Hoy: 7.591, 7.118, 12.095.
3. Reglas incumplidas, por código. Hoy: RF-05.5 en los cuatro fallos, ninguna otra.

Si (1) no baja pero (2) sí, X-01.1 funciona y la causa sigue viva. Si (1) baja, es que
el umbral era el problema y la conversación se traslada a X-01.3.

## 6. Qué NO propone esta Spec-X

- **No toca INV-01.** El escritor sigue sin poder leer el manuscrito. Se podría pensar
  en pasarle por adelantado la lista de n-gramas prohibidos, pero eso es filtrar texto
  de capítulos anteriores al escritor, y esa discusión es otra spec.
- **No toca la cadencia del QA**, que es el paso más caro de la tanda (36 % del gasto).
  Merece su propio análisis.
- **No toca el bucle ni el estado.** Un cambio de prompt y un campo más en el registro.

## 7. Nota sobre los datos

La traza de la que salen estos números tenía tres defectos de instrumentación,
corregidos en el commit `70b3448`: un `agente_fin` duplicado, el capítulo tomado del
cursor en vez del agente, y la latencia de los extractores en cero. Las cifras de esta
spec son las de la traza ya corregida.


## 8. Un margen que conviene vigilar

El escritor tiene `maxTurns: 8`. El capítulo 6, con dos reintentos, usó **exactamente
8**. Un tercer reintento lo habría cortado a media corrección. Si X-01.1 funciona los
turnos bajan y el margen se recupera solo; si no funciona, este techo es lo próximo que
va a fallar, y fallará de una forma fea: un capítulo a medio validar.

No se toca ahora porque subirlo sin arreglar la causa solo hace más caro el mismo error.
