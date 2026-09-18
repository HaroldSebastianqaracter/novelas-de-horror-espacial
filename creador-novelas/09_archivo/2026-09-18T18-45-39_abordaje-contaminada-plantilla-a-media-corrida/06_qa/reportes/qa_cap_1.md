# Reporte de QA — corte en el capítulo 1

Muestra revisada: `05_manuscrito/cap_1.md`.
Voz configurada: es-ES, tercera limitada, pasado. El capítulo la respeta (foco en Sossa, pasado, español de España).

## Hallazgos

### 1. Contradicción — `cap_origen: 1`
El capítulo narra la muerte de Marek Sundh **en la bodega**: se lo ve por la cámara de bodega con la linterna comprobando eslingas, la presencia cruza la bodega y lo mata allí mismo, y al final "la bodega volvía a estar vacía". El log registra como vigente que "Marek Sundh fue asesinado en la Sala de máquinas por la presencia en menos de dos segundos sin que él pudiera retroceder" (`cap_origen` 1). La duración (menos de dos segundos) y la imposibilidad de retroceder coinciden; la locación no. El narrador establece la bodega como cierta, de modo que el hecho vigente sobre la Sala de máquinas queda contradicho.

### 2. Repetición — `cap_origen: null`
Estructura de negación seguida de afirmación ("No A, no B: C" / "X, no Y" / "no hubo A, ni B. Hubo C"): 3 apariciones acumuladas, todas en el capítulo 1 (apertura del panel de esclusas, el giro de Sundh y la descripción del método de la presencia). El recurso sostiene casi todos los momentos de tensión del capítulo.

### 3. Repetición — `cap_origen: null`
"Nada" como sustantivo del vacío exterior o como respuesta: 3 apariciones acumuladas en el capítulo 1 ("Afuera no había nada, y por ese nada entró algo grande", "Nada contestó", "Alrededor, nada"). Es el cierre de tres párrafos distintos.

### 4. Repetición — `cap_origen: null`
Enumeración en tríada como recurso rítmico: 3 apariciones acumuladas en el capítulo 1 (la secuencia del ciclo de esclusa, la descripción del monitor de bodega y los tres adjetivos de la alarma de presión).

## Sin hallazgo
- Cronología: "el cuarto día de once" y "siete días hasta puerto" son coherentes con el hecho de `cap_origen` 0 sobre el trayecto de once días.
- Los tres protocolos de contacto (radio, luces, saludo grabado), el plano incompleto que corrige Kes, la alarma de presión tardía y el rol de Arens concuerdan con el log.
- Que la rejilla de ventilación de proa quede abierta no se enuncia como negación del hecho "abandonó la nave": el texto no lo confirma ni lo desmiente, es ambigüedad deliberada y no se contabiliza.
