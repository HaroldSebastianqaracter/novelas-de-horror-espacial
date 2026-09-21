# Domain knowledge — Fundamentos de la novela de terror espacial

Principios de escritura que determinan si una novela se siente lograda o no, más allá del esquema de datos. No son entidades del modelo (ver `definitions.md`), pero cada uno se apoya en él o lo atraviesa.

### 1. Voz y estilo de prosa
Distinto del punto de vista: POV es quién cuenta, voz es cómo suena al contarlo — largo de oración, vocabulario, ritmo, cuánto describe frente a cuánto sugiere. Una prosa seca y clínica genera un tipo de miedo (distancia, informe forense); una prosa densa y sensorial genera otro (inmersión, claustrofobia). Se decide antes de escribir la primera línea.
*Se relaciona con:* `EstiloNarrativo`, definido una sola vez para toda la `Novela` y constante en cada `Escena`.

### 2. Diálogo
Casi nunca sirve solo para dar información. Cumple tres funciones a la vez: caracteriza (cómo habla alguien dice quién es), genera subtexto (lo que no se dice pesa más que lo que se dice) y avanza el conflicto. El error más común es usarlo para explicar lo que el lector ya sabe. En terror espacial, el silencio y las comunicaciones cortadas son parte del vocabulario del miedo.
*Se relaciona con:* ocurre dentro de `Escena`; el subtexto suele apoyarse en el `secreto` del `Personaje`.

### 3. Subtramas y cómo se entrelazan
Toda novela larga necesita más de un hilo argumental corriendo en paralelo al principal: una tensión entre dos personajes, un secreto de alguien del elenco, un conflicto de poder. La habilidad no es tenerlas, es que se crucen con la trama principal justo en los puntos de giro, para que se sienta una sola historia y no capítulos intercalados sin relación.
*Se relaciona con:* `HiloNarrativo` — la trama principal es un hilo más, con tipo "principal"; cada subtrama es otro hilo, compuesto de sus propios `PuntoDeGiro` e involucrando a los `Personaje` correspondientes.

### 4. Arquitectura de capítulo
Cada capítulo necesita su propio gancho de apertura y de cierre, independientes del gancho general del libro. El cierre de capítulo decide si alguien sigue leyendo o cierra el libro — en terror suele ser una revelación parcial, una pregunta nueva, o un corte justo antes de mostrar algo.
*Se relaciona con:* `Capitulo`, atributos `ganchoApertura` y `ganchoCierre`.

### 5. Mostrar vs. contar
El consejo más repetido y el más malentendido: no significa nunca resumir nada, significa que los momentos emocionales clave se transmiten por acción y detalle sensorial concreto, no nombrando la emoción. "Sintió terror" es mucho más débil que describir la mano temblando al no poder abrir una escotilla.
*Se relaciona con:* es la técnica para escribir el `estadoPsicologico` de `EstadoPersonaje` dentro de una `Escena`, en vez de solo declararlo.

### 6. Simbolismo y motivos recurrentes
Una imagen, objeto o frase que reaparece y va cambiando de significado a medida que la historia avanza (el traje de presión, una foto familiar, una alarma específica). Es lo que hace que un libro se sienta unificado y no solo una secuencia de eventos, y en terror suele ser el vehículo concreto del tema.
*Se relaciona con:* `Motivo`, contenido por la `Novela` y presente en varias `Escena`; casi siempre encarna el `temaCentral`.

### 7. Verosimilitud técnica del género
El lector perdona fantasía siempre que las reglas internas sean consistentes. No hace falta que la física sea real, hace falta que la nave no rompa sus propias reglas a mitad de libro sin explicación.
*Se relaciona con:* `Ambientacion`, atributo `reglasTecnologicas`.

### 8. Expectativas y tropos del subgénero
"Terror espacial" no es un género monolítico: terror corporal (mutación, infección), horror cósmico (lo incomprensible), slasher espacial (una amenaza física que persigue), thriller de IA hostil. Cada uno pide un tipo de final distinto, así que conviene elegir uno como dominante desde el inicio.
*Se relaciona con:* `Novela`, atributo `subgeneroDominante` — condiciona directamente el `tipoFinal` (punto 9).

### 9. Tipos de final
Cerrado (la amenaza se resuelve del todo), abierto (algo escapa o queda sin resolver), ambiguo (no se sabe si lo que pasó fue real) o de victoria pírrica (ganan pero a un costo altísimo). En terror, el final ambiguo o pírrico es mucho más común que el final limpio — que suele sentirse barato.
*Se relaciona con:* `Novela`, atributo `tipoFinal`.

### 10. Proceso de revisión
Una novela no se escribe una vez, se reescribe en pasadas con objetivos distintos: primero estructura y trama (¿funciona la historia?), después personaje y ritmo (¿se siente bien leerla?), y al final prosa a nivel de oración. Mezclar estas pasadas es la forma más común de perder tiempo escribiendo.
*Se relaciona con:* es un proceso de producción, no una clase de datos — se aplica sobre toda la ontología en pasadas sucesivas, no de una sola vez.

## Cómo se conectan entre sí

Hay tres capas. La capa de oficio (voz, diálogo, mostrar/contar) se aplica dentro de cada escena. La capa estructural (subtramas, arquitectura de capítulo) organiza cómo se agrupan los actos, capítulos y escenas. La capa temática (simbolismo, subgénero, tipo de final) le da unidad a la novela completa y es la que casi siempre se define primero, porque condiciona a las otras dos.
