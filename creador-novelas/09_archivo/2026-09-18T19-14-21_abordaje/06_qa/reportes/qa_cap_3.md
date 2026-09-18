# Reporte de QA — corte en el capítulo 3

Muestra leída: `05_manuscrito/cap_3.md`
Voz verificada: es-ES, tercera persona limitada, tiempo pasado. Sin desvíos.

## Contradicciones (1)

### 1. Cronología de las transmisiones sin respuesta — `cap_origen: 0`
El narrador afirma en el capítulo 3 que Vart habla "por un canal que llevaba doce días sin devolverle nada".
El log vigente fija que al empezar la novela la nave llevaba **cuatro días de travesía** y que el plan de vuelo registra **once días hasta puerto**, y que el registro de comunicaciones recoge **cuatro días** de transmisiones enviadas sin respuesta (hechos de `cap_origen: 0`). El propio capítulo 3 refuerza esa línea temporal al decir "Puerto a siete días" (4 + 7 = 11).
Doce días de silencio exceden la travesía completa y contradicen el punto de partida establecido antes del capítulo 1.

## Repeticiones (4)

Umbral: 3 o más apariciones acumuladas, con presencia en esta muestra.

### 1. Descripción por negación — `cap_origen: null`
La escena se define por lo que no ocurre. En el capítulo 3: "una voz que no admitía consulta", "No fue hacia Vart de inmediato", "Vart no levantó la vista", "aquello se hacía una vez o ninguna", "no la compartió con Bregan", "Sorel no llegó al registro", "después dejó de decir nada".
Acumulado: 13 apariciones. Capítulos 1, 2, 3.

### 2. Símil que domestica lo monstruoso con un término cotidiano o humano — `cap_origen: null`
En el capítulo 3: la atención de la presencia sobre las manos de Vart tiene "algo insoportablemente parecido a un aprendizaje".
Acumulado: 4 apariciones. Capítulos 1, 3.

### 3. Estructura del secreto callado ("no dijo / no lo compartió") — `cap_origen: null`
En el capítulo 3: Calvo "hizo la cuenta y no la compartió con Bregan, que ya la había hecho".
Acumulado: 5 apariciones. Capítulos 1, 2, 3.

### 4. Cierre de frase con oración de relativo negativa — `cap_origen: null`
En el capítulo 3: "una voz que no admitía consulta", "un canal que llevaba doce días sin devolverle nada".
Acumulado: 4 apariciones. Capítulos 1, 2, 3.

## Recursos registrados por debajo del umbral (no son hallazgos)

- Par de adjetivos calmos pospuestos aplicados a lo siniestro: 2 apariciones, capítulo 2. No reaparece en esta muestra.
- Enumeración de gestos manuales mundanos como respiro ante el terror: 2 apariciones, capítulos 2 y 3 ("los había apretado ella, uno por uno", "fue soltándolos en el orden inverso").
- Conteo descendente en diálogo escueto por intercomunicador ("Quedan tres. Quedan dos. Queda uno."): 1 aparición, capítulo 3.

Registro acumulado actualizado en `06_qa/recursos_usados.json`.
