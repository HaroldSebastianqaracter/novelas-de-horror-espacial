# Reporte de QA — corte del capítulo 1

Muestra leída: `05_manuscrito/cap_1.md`
Voz configurada: es-ES · tercera limitada · pasado. La muestra la respeta (sin hallazgo de voz).

## Hallazgos

### 1. Contradicción — `cap_origen: 0`
El narrador afirma en el capítulo 1 que al detectarse la apertura de la esclusa "bajaron al nivel dos los cinco",
es decir, la tripulación completa incluida Duna Oyarzo. Pocas líneas después el mismo narrador establece que
Oyarzo llegó por separado, "venía del puente por el otro extremo". Ambas afirmaciones son del narrador, no de un
personaje, y no pueden ser ciertas a la vez: contradice el hecho vigente de `cap_origen` 0 según el cual
Duna Oyarzo tiene asignada la guardia del puente en la noche del cuarto día (y el puente está en el extremo
opuesto al que se baja). No es error de un personaje ni ambigüedad deliberada: es un conteo del narrador.

### 2. Repetición — `cap_origen: null`
Motivo del registro que "anota": tres apariciones del mismo verbo y gesto en el capítulo 1 — "el sistema anotó
la apertura", "el registro anotó el cierre con su hora exacta" y "Keth anotó la hora". Acumuladas: 3 (umbral
alcanzado en este mismo corte). Capítulos: 1.

### 3. Repetición — `cap_origen: null`
Insistencia en el número doce como marcador: "doce contenedores" / "Doce, siempre doce" y "doce años
cruzándolo". Acumuladas: 3. Capítulos: 1. El dato es correcto respecto del log; lo que se señala es el efecto
de eco del mismo número en posiciones de énfasis dentro de un capítulo corto.

## Registrado por debajo del umbral (sin hallazgo)
- Series anafóricas de frases negativas breves ("No había alarma... No había orden...", "No se detuvo. No
  respondió. No pidió nada."): 2 apariciones.
- Imagen de la luz plana que no hace sombras: 1 aparición.
- La entidad que pasa por un espacio demasiado angosto para su tamaño: 2 apariciones.

## Verificaciones sin hallazgo
- Esclusa de carga abierta y cerrada sin alarma de presión ni orden en la cola: coherente con el log (cap 1).
- Sellado del nivel dos mamparo por mamparo en catorce minutos: coherente (cap 1).
- Conductos de servicio, boca de registro en el techo del pasillo del nivel dos y conocimiento de Solé del
  circuito completo: coherente (cap 0).
- Once días de travesía, ausencia de nave a distancia de rescate y retardo de señal: coherente (cap 0).
- Procedimiento de contacto de diecinueve fases recitado por Marrec: coherente (cap 0).
