# Reporte de QA — corte en el capítulo 3

Muestra leída: `05_manuscrito/cap_3.md`.
Voz narrativa: es-ES, tercera limitada (focalizada en Mirén), tiempo pasado. Conforme; sin hallazgo de voz.

## Contradicciones

Ninguna. Todo lo que el narrador establece como cierto en el capítulo 3 es compatible con los hechos vigentes del log:

- El mamparo del puente cede cuando Sein deja de sostenerlo desde dentro: coherente con el hecho de `cap_origen` 0 sobre el sellado manual.
- El retardo de seis horas con Halcón y el acuse del atraque prioritario: coherentes con los hechos de `cap_origen` 0 (sin comunicación en tiempo real) y 2 (solicitud de atraque ya en cola).
- La voz de Mirén multiplicada por las credenciales de Vasari, Sein, Dovan, Okonjo y Reder: coherente con los hechos de `cap_origen` 0 (el sistema no distingue quién habla sino qué credencial habla) y 2 (la presencia ya usaba el array con la credencial de Vasari).
- La identidad del único ocupante del módulo de escape queda deliberadamente ambigua en el texto; una ambigüedad no confirmada por el narrador no es contradicción.

## Repeticiones estilísticas (umbral: 3 o más acumuladas y presencia en esta muestra)

1. **tipo: repeticion** · `cap_origen: null` — Estructura de corrección "no X, sino/debajo de Y". Reaparece dos veces en el capítulo 3 ("No la silenciaba. La acompañaba."; "no devorando el canal, sino ocupándolo entero"). Acumulado: 9 apariciones en los capítulos 1, 2 y 3.
2. **tipo: repeticion** · `cap_origen: null` — Marca horaria exacta para escandir la escena. Tres apariciones en el capítulo 3 ("catorce minutos antes", "seis horas de retardo", "sostuvo un minuto más"). Acumulado: 9 apariciones en los capítulos 1, 2 y 3.
3. **tipo: repeticion** · `cap_origen: null` — Enumeración de negaciones absolutas como remate. Una aparición en el capítulo 3 ("Ningún remolcador... ninguna maniobra la deshacía"). Acumulado: 5 apariciones en los capítulos 1, 2 y 3.
4. **tipo: repeticion** · `cap_origen: null` — Personaje que anota, mide o lleva un registro en lugar de reaccionar. Una aparición en el capítulo 3 (la respiración de Sein "midiéndose sola, como si todavía llevara un registro"). Acumulado: 4 apariciones en los capítulos 1, 2 y 3.

## Recursos por debajo del umbral o sin aparición en esta muestra

Registrados en `06_qa/recursos_usados.json` con su conteo intacto y no enumerados como hallazgo: tic léxico de la rutina, detalle olfativo como indicio, anáfora triple con "siempre", testigo que se niega a contar lo que vio, y los dos recursos nuevos del capítulo 3 (voz propia multiplicada por credenciales ajenas; pantalla que trae la noticia antes que la voz humana).

## Resumen

- Contradicciones: 0
- Repeticiones: 4
