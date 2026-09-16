---
name: criterios-qa
description: Qué cuenta como contradicción y qué no, umbral de repetición, cómo citar cap_origen y formato de recursos_usados.json, para el agente qa (spec técnica §11.8; RF-07.2 a RF-07.5).
user-invocable: false
---

# Criterios del corte de QA

## Qué ES una contradicción (tipo `contradiccion`)
El narrador establece como cierto algo incompatible con un hecho **vigente** del log (`superado_por: null`):
- Un personaje muerto, ausente o incapacitado actúa como si no lo estuviera.
- Un lugar sellado, destruido o venteado se usa sin que nadie lo reabra ni se explique.
- Un objeto perdido o destruido reaparece; una herida desaparece; un secreto que nadie reveló es conocido por quien no podía saberlo.
- Cambios de voz: capítulo en otra persona narrativa, tiempo verbal o idioma que los configurados (`cap_origen = 0`).
Cada contradicción cita el `cap_origen` del hecho contradicho, tal como figura en el log. Si contradice varios, uno por hallazgo.

## Qué NO es una contradicción
- Un personaje que miente, se equivoca, alucina o recuerda mal **dentro de la ficción**. El log registra lo que el narrador establece, no lo que los personajes dicen.
- Una ambigüedad deliberada o una hipótesis que el texto no confirma.
- Un hecho con `superado_por` distinto de null: fue reemplazado por una corrección; ignoralo.
- Información nueva que no niega nada previo: eso es avance, no contradicción.
- Un hecho repetido dos veces en el log con distinta redacción: eso es, a lo sumo, un hallazgo de tipo `repeticion` si molesta; nunca lo corregís.

## Repetición estilística (tipo `repeticion`)
- Recurso: una metáfora o imagen concreta ("el pasillo como una garganta"), una estructura de frase recurrente ("No era X. Era Y."), un tic léxico.
- Contá las apariciones de esta muestra y sumalas a `veces` del registro anterior. El umbral es **3 o más acumuladas**: a partir de ahí, hallazgo de tipo `repeticion` con `cap_origen: null` y la lista de capítulos en la descripción.
- Registrá también lo que quedó por debajo del umbral: el corte siguiente lo necesita.

## Formato de `06_qa/recursos_usados.json`
Array de objetos, uno por recurso, acumulativo entre cortes:
```json
[
  { "recurso": "el pasillo comparado con una garganta", "veces": 3, "caps": [2, 5, 9] },
  { "recurso": "estructura 'No era X. Era Y.'", "veces": 2, "caps": [4, 9] }
]
```
Partí del archivo anterior tal como está; nunca borres entradas ni bajes conteos. Es obligatorio escribirlo en cada corte, aunque no haya novedades.

## Formato del reporte
- `qa_cap_N.md`: legible, un ítem por hallazgo con tipo, `cap_origen` y descripción breve que cite el capítulo de la muestra donde ocurre.
- `qa_cap_N.json`: `{ "cap_corte": N, "hallazgos": [ { "tipo", "descripcion", "cap_origen" } ], "tiene_contradicciones": bool }`. La bandera debe coincidir con la presencia de hallazgos de tipo `contradiccion`.
- Mensaje final: hasta cinco líneas con la bandera, los conteos por tipo y la ruta del reporte.
