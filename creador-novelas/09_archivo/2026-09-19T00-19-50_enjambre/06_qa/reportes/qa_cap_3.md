# Corte de QA — capítulo 3

Muestra leída: `05_manuscrito/cap_3.md`.
Voz verificada: es-ES, tercera limitada, pasado. Sin desviación.

## Contradicciones

Ninguna. Los hechos que el narrador establece en el capítulo 3 (la muerte de Renke con la rueda girable solo desde dentro, la muerte de Domas Feller en el hangar convertido en señuelo, la clausura del hangar desde el núcleo, el regreso de las criaturas al restablecerse la calefacción) son compatibles con los hechos vigentes del log. Comprobaciones puntuales:

- El muñón vendado de la mano derecha de Renke concuerda con la amputación de tres dedos (`cap_origen: 2`).
- El módulo C sigue sellado y a temperatura exterior hasta que Renke lo abre desde el lado interior (`cap_origen: 2`).
- El hangar como peor aislado del complejo y con motores de exterior concuerda con su descripción (`cap_origen: 0`).
- El relevo al sexto día concuerda con el relevo previsto a seis días (`cap_origen: 0`).
- Tres supervivientes y dos cuerpos no recuperados cierran con la dotación de cinco operarios (`cap_origen: 0`).

## Repeticiones estilísticas

Umbral: 3 o más apariciones acumuladas y presencia en esta muestra.

1. **[repeticion]** `cap_origen: null` — El silencio o la omisión de un personaje como respuesta significativa: en el capítulo 3, Ivet que dice "Registro de turno" y no escribe, Renke que no contesta a la tercera llamada y Tobi que no dice cuántos días han pasado. 6 apariciones acumuladas, capítulos 1, 2 y 3.
2. **[repeticion]** `cap_origen: null` — Párrafo de una sola frase corta aislada como golpe de tensión: en el capítulo 3, "Entonces la temperatura del hangar empezó a bajar por el suelo." y el cierre con Tobi junto a la escotilla. 5 apariciones acumuladas, capítulos 1, 2 y 3.
3. **[repeticion]** `cap_origen: null` — El arrastre de las criaturas en los conductos comparado con grava: reaparece literalmente en el cierre del capítulo 3 ("había vuelto a sonar la grava"). 3 apariciones acumuladas, capítulos 1 y 3.
4. **[repeticion]** `cap_origen: null` — Estructura de negación y corrección del tipo "No fue X. Fue Y.": en el capítulo 3, "No hacia los motores: hacia lo que respiraba entre ellos." 3 apariciones acumuladas, capítulos 1, 2 y 3.

## Recursos por debajo del umbral

Registrados en `06_qa/recursos_usados.json` sin enumerarse como hallazgo: la repetición triple de una palabra para marcar monotonía, el frío como agente que desactiva un cuerpo, la repetición de una misma cifra medida, el símil con "como quien"/"como si" para animar un objeto, el símil de paisaje abierto para el calor de la estación y el cuerpo humano descrito por su temperatura en grados.

## Veredicto

`tiene_contradicciones: false` — 0 contradicciones, 4 repeticiones.
