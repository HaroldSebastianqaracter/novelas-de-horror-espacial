# Reporte de QA — corte en el capítulo 1

Muestra leída: `05_manuscrito/cap_1.md`.
Log de continuidad cruzado: 18 hechos vigentes (`cap_origen` 0 y 1).
Registro de recursos de partida: vacío (primer corte).

## Contradicciones

Ninguna.

Verificaciones hechas contra hechos vigentes del log:

- Temperatura exterior (doscientos bajo cero) y superficie de la estación (doscientos metros cuadrados, once años): coinciden con los hechos de `cap_origen: 0`.
- Dotación de cinco personas con sus roles (Irune al mando y su cuenta rayada en la litera, Tomás en térmicos con los planos, Nadia médica en su primer turno, Elvio veterano reticente, Khalil en comunicaciones): coinciden con `cap_origen: 0`.
- Relevo en seis días confirmado por Khalil cada mañana: coincide con `cap_origen: 0`.
- Rumor granulado en los conductos, tercera rejilla doblada hacia fuera con los cuatro tornillos puestos, animal blando y pálido sin ojos tibio contra el radiador, explicación de Tomás por dilatación entre sesenta y dos y dieciocho grados: coinciden con los hechos de `cap_origen: 1`.

Nota de criterio: la explicación de Tomás sobre las juntas es una hipótesis de personaje dentro de la ficción, no una afirmación del narrador, y por tanto no contradice el log aunque el texto la ponga en duda.

## Voz narrativa

Conforme: es-ES, tercera persona limitada (focalizada en Nadia Oyarce) y tiempo pasado en toda la muestra. Sin hallazgo con `cap_origen: 0`.

## Repeticiones estilísticas

Ninguna alcanza el umbral de 3 apariciones acumuladas. Los recursos detectados quedan registrados para el corte siguiente en `06_qa/recursos_usados.json`:

- Estructura de contraste por negación y corrección ("No arrancada: doblada", "No chascaba. Corría.") — 2 apariciones, cap. 1.
- Percepción por temperatura al tacto ("quemaba de frío", "está tibio") — 2 apariciones, cap. 1.
- Series de frases nominales de una sola palabra ("Blando. Pálido.") — 1 aparición, cap. 1.
- El ruido descrito como material granulado vertido despacio (gravilla) — 1 aparición, cap. 1.
- Figura de repetición léxica del verbo ("repitió lo que repetía") — 1 aparición, cap. 1.
- Cierre de escena con lo que los personajes callan ("ninguno dijo lo otro") — 1 aparición, cap. 1.

## Resumen

- Hallazgos de tipo `contradiccion`: 0
- Hallazgos de tipo `repeticion`: 0
- `tiene_contradicciones`: false
