# Reporte de QA — corte en el capítulo 2

Muestra leída: `05_manuscrito/cap_2.md`
Voz verificada: es-ES, tercera persona limitada, tiempo pasado. Conforme.

## Hallazgos

### 1. Contradicción (cap_origen: 0)
El narrador cierra el capítulo 2 afirmando como cierto que la pregunta de Adalid en la cocina
("¿Quién quiere volver a casa?") era **la primera pregunta que hacía**. En el mismo capítulo, unos
párrafos antes, el narrador ya había establecido que Adalid **le preguntó a Vidal si su hermano
seguía escribiendo**. No es un personaje que miente: ambas afirmaciones están en voz narrativa.
Contradice el hecho vigente de `cap_origen: 0`: "El pasajero contesta con exactitud a todo lo que
se le pregunta y nunca pregunta nada".

### 2. Repetición (cap_origen: null)
Estructura de negación anafórica en oración corta ("No pidió X. No preguntó Y."). Tres apariciones
en el capítulo 2 ("Nadie recordaba esas horas. Nadie las echaba de menos"; "No había soporte vital.
No había raciones, ni asiento, ni anclajes"). Acumulado: 7 apariciones, capítulos 1 y 2.

### 3. Repetición (cap_origen: null)
Enumeración ternaria asindética como cierre descriptivo. Dos apariciones en el capítulo 2
("pisadas, consumos, puertas"; "ni bulto, ni huella, ni rastro"). Acumulado: 5 apariciones,
capítulos 1 y 2.

### 4. Repetición (cap_origen: null)
Símil introducido por "como quien" / "como si" ("marcaban como si hubieran respirado dieciocho").
Una aparición en el capítulo 2. Acumulado: 3 apariciones, capítulos 1 y 2.

### 5. Repetición (cap_origen: null)
Cierre de escena con frase corta lapidaria ("que era lo peor"; "Era la primera pregunta que hacía").
Dos apariciones en el capítulo 2. Acumulado: 4 apariciones, capítulos 1 y 2.

### 6. Repetición (cap_origen: null)
El registro o archivo de la nave invocado como única prueba (registro de presencia, huecos del
registro de a bordo, barridos antiguos). Tres apariciones en el capítulo 2. Acumulado:
5 apariciones, capítulos 1 y 2.

## Verificaciones sin hallazgo
- Filtros que marcan dieciocho meses tras catorce: información nueva que no niega el hecho de
  `cap_origen: 0` sobre el desgaste medible; es avance, no contradicción.
- Bodega vacía sin rastro de Adalid: no contradice su alojamiento allí (`cap_origen: 1`); el texto
  no afirma que nunca estuvo.
- "Los filtros mienten" (Eyer): diálogo de personaje, no establece hecho narrativo.

## Resumen
- Contradicciones: 1
- Repeticiones: 5
