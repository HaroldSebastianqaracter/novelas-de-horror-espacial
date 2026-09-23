# Validators — Métodos de verificación

Catálogo de métodos para comprobar que el código del proyecto y la salida de los agentes son correctos. Este documento fija el vocabulario y la clasificación; qué método concreto se aplica a cada componente se decidirá junto con la arquitectura (ver [architecture.md](architecture.md)).

Hay tres planos que se verifican de forma distinta y no conviene mezclarlos:

1. **Código** — el sistema determinista que rodea a los agentes. Se verifica con las herramientas de siempre.
2. **Proceso del agente** — qué decide hacer y si se comporta de forma fiable.
3. **Salida narrativa** — el manuscrito y los artefactos de planificación. Es el plano específico de este proyecto, y buena parte de él es comprobable de forma determinista porque la ontología de [definitions.md](definitions.md) lo modela como grafo: una contradicción de continuidad es una consulta, no una opinión.

## Clasificación (Trust Spec)

Cada método se etiqueta según de dónde saca su evidencia:

| Código | Tipo | Cómo se verifica |
| --- | --- | --- |
| **T** | Test | Ejecutando el sistema contra entradas concretas. |
| **A** | Analysis | Razonamiento estático: tipos, SAST, ejecución simbólica o prueba formal. |
| **I** | Inspection | Una persona o un modelo crítico lo lee y lo juzga. |
| **D** | Demonstration | Observando el funcionamiento correcto en un escenario realista (staging, sandbox). |
| **U** | Unverifiable / Accepted Risk | Ningún método aplica, o no compensa el coste. Se nombra explícitamente en vez de dejarlo como supuesto silencioso. |

`U` no es un método: es la etiqueta obligatoria para lo que decidimos no verificar.

## Verificación a nivel de código

**Type checking** — `A`
Comprobación automática de que los valores se usan de forma consistente con lo que esperan las operaciones (nunca pasar un string donde se requiere un número).

**Static analysis / SAST** — `A`
Escaneo del código fuente sin ejecutarlo, buscando coincidencias con patrones conocidos como malos: vulnerabilidades de seguridad, code smells, antipatrones.

**Symbolic execution** — `A`
Ejecutar el código con entradas simbólicas (marcadores en vez de valores) para derivar, vía un solver SMT, las condiciones exactas que lo romperían y los contraejemplos concretos.

**Formal verification / theorem proving** — `A`
Demostrar matemáticamente que el código satisface una especificación para todas las entradas posibles, no solo para las probadas o exploradas.

**Unit / integration testing** — `T`
Comprobar el comportamiento contra entradas de ejemplo elegidas y sus salidas esperadas.

**Property-based testing** — `T`
Especificar una propiedad general que debe cumplirse para cualquier entrada, y generar muchas entradas automáticamente buscando una violación.

**Mutation testing** — `T`
Introducir bugs pequeños a propósito en el código para comprobar si la suite de tests existente realmente los detecta.

**Contract testing** — `T`
Verificar que la interfaz (forma de request/response) entre dos servicios se mantiene consistente, con independencia de los internos de cada lado.

## Verificación a nivel de proceso

¿Se está comportando el agente de forma fiable?

**Runtime observability / tracing** — `D`
Instrumentar el agente para que su trayectoria real (llamadas a herramientas, tokens, latencia, errores) sea visible y consultable a posteriori.

**Evals** — `T` (`I` cuando el scorer es un modelo juez)
Tests estructurados del comportamiento de un modelo o agente contra un dataset y un método de puntuación: golden-dataset, LLM-as-judge, task-completion, adversarial, live/online.

**Sandboxed execution** — `D`
Ejecutar el código del agente en un entorno aislado (contenedor, microVM) para que una acción mala falle de forma segura en vez de llegar a producción.

**Guardrails** — `D`
Políticas o filtros que restringen qué acciones y salidas puede producir un agente, antes de que actúe. Es un control preventivo: su evidencia viene de observar que efectivamente bloquea lo que debe bloquear.

**Human-in-the-loop review** — `I`
Una persona aprueba, rechaza o edita las acciones de alta consecuencia del agente, y la decisión se realimenta como señal de entrenamiento.

**Multi-agent verification** — `I`
Crítico/verificador (un segundo modelo revisa al primero), self-consistency (voto mayoritario entre ejecuciones repetidas), debate (dos modelos discuten y un juez decide), reflection (autocrítica y revisión) y ensembles (combinación de modelos distintos).

**CI/CD integration** — `T`
Enrutar los cambios generados por el agente por el mismo pipeline, tests y revisión que el código escrito por humanos, más etiquetado de procedencia.

**Progressive rollout** — `D`
Desplegar un cambio detrás de un feature flag a un porcentaje pequeño del tráfico y monitorizarlo antes del release completo.

**Red-teaming / adversarial testing** — `T`
Sondear deliberadamente en busca de fallos bajo un modelo de amenaza adversario (prompt injection, cadenas de mal uso de herramientas, goal drift, exfiltración de datos), no solo errores ordinarios.

**Model checking** — `A`
Explorar exhaustivamente los estados y transiciones alcanzables de un agente para verificar invariantes ("nunca borrar antes de hacer backup"). Es el análogo de la ejecución simbólica para flujos multi-agente.

## Verificación de la salida narrativa

Los métodos anteriores son genéricos. Esta sección los instancia sobre el dominio: qué propiedad de una novela se comprueba con qué método, y dónde vive esa propiedad en el modelo. La regla de reparto es la altitud del error — un fallo de continuidad es un hecho, un fallo de voz es un juicio.

### Comprobable de forma determinista sobre el grafo — `A`

Son consultas sobre las entidades de estado de [definitions.md](definitions.md). No requieren modelo: o el dato contradice al registro o no lo contradice.

| Propiedad | Se comprueba sobre | Fallo que detecta | Punto ciego |
| --- | --- | --- | --- |
| Continuidad factual | `Hecho` (triple `sujeto`/`atributo`/`valor`, relación `establecidoEn`) | El texto afirma algo que contradice un hecho ya establecido: un nombre, una fecha, un rasgo físico, una distancia. | Solo ve los hechos que el extractor registró. Un dato que nadie extrajo no puede contradecir a nada, y la puerta da verde. |
| Conocimiento no adquirido | `UsoDeConocimiento` contra `EstadoDeConocimiento` (`postura`, `via`, relación `desde`) | Un personaje actúa sobre información que todavía no ha recibido, o se sorprende de algo que ya sabía. Es la fuente número uno de errores en obra larga. | Depende de que el uso quede registrado. Un personaje que actúa sobre lo que sabe sin nombrarlo no deja rastro que consultar. Estar en la escena donde se fija el hecho cuenta como haberlo presenciado, así que un personaje presente pero ajeno a lo que pasa lo «sabe» igual. Y la presencia que no planificó la escaleta la declara el extractor: si marca presente a alguien que no estaba, la comprobación calla para todo lo que se fijó en esa escena. |
| Siembras sin pago | `EstadoSiembra` (`estado`) | Elemento plantado que llega al final sin recogerse, o pago que aparece sin siembra previa. | Comprueba que el pago **existe**, no que satisfaga. Un pago trivial cierra la siembra igual que uno bueno. |
| Hilos sin cerrar | `EstadoHilo` (`estado`) | Hilo que termina la novela en `abierto` sin estar marcado como abierto deliberadamente; hilo `latente` más allá del umbral fijado; cierre en orden distinto al inverso de apertura. | El estado lo declara quien cierra el hilo. Un cierre nominal queda `cerrado` sin haber resuelto nada. |
| Presencia imposible | `Escena` (reparto), `Lugar` (`presenciaActual`), `EstadoObjeto`, `EstadoPersonaje` (`condicion`) | Un personaje en dos lugares a la vez; un muerto que reaparece; un objeto que aparece sin traslado registrado desde su última ubicación. | Solo cubre entidades con ubicación registrada: un objeto que nunca se situó no puede estar mal situado. La muerte se lee de `condicion`, que **declara el extractor** (regla 3): una muerte que no registró como `muerto` no para nada, y por eso la acompaña una búsqueda del nombre del muerto en la prosa posterior. |
| Coherencia temporal | `LineaDeTiempo`, `Evento` (`ordenInterno`, `dia`) | Sucesos fuera de orden; un suceso posterior que cae en un día anterior (`dia_contra_orden`). | Verifica el orden declarado, no la plausibilidad de lo que cabe en una duración. **El día y el orden los declara el mismo extractor** (regla 3): compararlos entre sí detecta que se contradigan, no que los dos estén mal de la misma forma. Como el orden, no mira las analepsis ni los antecedentes del mundo, cuyo orden el extractor no conoce. Las edades que no cuadran se comprueban con Lean (bloque 9 del plan), que lee `dia` y la edad de cada personaje. |
| Edad del destinatario | `Personaje` (`edad`) contra `Encargo` (edad del destinatario) | El protagonista no tiene la edad del destinatario del regalo. | Que la prosa respete esa edad (un protagonista de doce años que conduce el remolcador): eso es juicio. |
| Escena sin cambio de valor | `Escena` (`valorInicial`, `valorFinal`) | La escena termina en la misma polaridad en que empezó: es relleno declarado. | **Los dos valores los declara el mismo agente al que se juzga.** Basta escribir polaridades distintas para que una escena plana pase. Es el validador solitario más frágil del catálogo. |
| Integridad de POV | `Escena` (`pov`), `Novela` (`povPorDefecto`) | Escena sin POV declarado, o cambio de conciencia focal dentro de una misma escena. | Ve el POV **declarado**, no el ejercido. La prosa puede deslizarse a otra conciencia con el campo correcto. |
| Presupuesto | `Restriccion` (`valor`) | Longitud de acto, capítulo o escena fuera del rango fijado; desviación de la longitud objetivo. | Mide extensión, no densidad. Un capítulo en rango puede no contener nada. |
| Encargo completo y coherente | `Encargo` (destinatario, intensidad, subgénero, vetados, `ElementoPersonal`) | Falta un dato obligatorio, la edad no llega a la intensidad, el subgénero no cabe en ella o un término vetado aparece en un elemento obligatorio. | Solo las contradicciones que el código conoce. Un recuerdo imposible para la edad no es ninguna de ellas. |
| Destinatario protagonista y superviviente | `Personaje` (`rolNarrativo`), `Escena` (`pov`), `EstadoPersonaje` (`condicion`) | El destinatario no es el protagonista, no es el punto de vista de la mayoría de las escenas o muere. | El punto de vista y la condición los declaran el escaletador y el extractor: es **dato autodeclarado**, y que la prosa lo ejerza lo juzga el oficio. |
| Personalización planificada | `ElementoPersonal` y su relación `integra` con `Escena` | Un elemento personal obligatorio no está planificado en ninguna escena. | **Dato autodeclarado**: el escaletador dice dónde va cada elemento. Que aparezca en la prosa es un segundo método, sobre el texto, que todavía falta. |

> **Decisión entrevistada, 23 de septiembre de 2026.** Dónde se **usa** cada hecho (`UsoDeHecho`, [definitions.md](definitions.md)) sale de dos métodos para no depender de un dato autodeclarado: lo que el extractor reafirma y la búsqueda del valor exacto en la prosa, que hace el código. Las dos búsquedas dirigidas de la puerta 3 que miden la cobertura del extractor cuentan ahora esos usos como registro: una escena que solo reafirmaba un hecho de un personaje dejaba un falso `nombre_sin_registro`, y una cifra que ya estaba en el canon, un falso `cifra_sin_hecho`. Detalle en [specs/spec3.md](../specs/spec3.md), RF3-BIB-01 a RF3-BIB-03.

> **Decisión entrevistada, 23 de septiembre de 2026.** La primera pasada con Claude Code real paró el capítulo 1 con seis falsos «conocimiento no adquirido»: personajes que estaban en la escena donde se fijaba el dato. La presencia pasa a contar como adquisición (RF2-PIPE-21 de spec2). En la misma pasada, doce entidades menores inventadas por el redactor (un planeta, unos sectores, una enfermería) paraban el pipeline; la entidad fuera de canon pasa a aviso (RF2-PIPE-22). Se descartó convertir el conocimiento en aviso, que perdía la detección, y añadir lo inventado al canon, que queda para más adelante.

> **Decisión entrevistada, 23 de septiembre de 2026.** Con esos nombres como aviso, la pasada acabó con 50 avisos para 15 nombres, y cuatro no eran inventos: el nombre del propio mundo, una variante de un lugar del canon y dos grafías del mismo nombre. El aviso sale ahora solo la primera vez que aparece un nombre; el mundo y el título entran en el inventario del extractor; una variante de puntuación, artículos o preposiciones se resuelve contra el canon, y el redactor recibe los nombres menores ya usados para mantener su grafía. Los nombres menores siguen sin entrar en el canon. En la misma revisión, el valor de un hecho pasa a tener como mucho diez palabras: 57 de 94 pasaban de ocho, y un valor compuesto convierte cualquier reformulación en una contradicción falsa. Detalle en [specs/spec3.md](../specs/spec3.md), 3.11.

> **Decisión sin entrevistar, 23 de septiembre de 2026.** «Siembras sin pago» e «Hilos sin cerrar» se describen arriba como **fallos**, y en la v2 la puerta 5, que es donde se comprueban, **avisa y no bloquea**. No es una contradicción sino un orden: llegado a la puerta 5 el manuscrito existe, y lo que encuentra se arregla revisando, que es el trabajo del revisor, fuera de la v2. Bloquear ahí solo impediría leer un manuscrito que ya está escrito. Desde la v2 comprueba también el pago sin siembra previa, el cierre de hilos fuera de orden y la latencia como tramo continuo. Cuando exista el revisor, estas comprobaciones pasarán a condicionar su trabajo. Detalle en [specs/spec2.md](../specs/spec2.md), RF2-PIPE-15.

### Comprobable ejecutando — `T`

| Método | Aplicación al dominio |
| --- | --- |
| **Búsquedas dirigidas** | Pasadas mecánicas sobre listas cerradas: palabras filtro (vio, oyó, sintió, notó), adverbios de atribución, verbos de habla expresivos, tics de `EstiloNarrativo.ticsProhibidos`, repetición de nombres, deriva ortográfica de nombres propios inventados. |
| **Property-based testing** | Invariantes que deben cumplirse sea cual sea la novela generada: todo `Hecho` tiene escena de origen; toda `Siembra` pagada tiene su escena de pago posterior a la de siembra; ningún `EstadoDeConocimiento` ni `UsoDeHecho` precede a la escena que establece su `Hecho`; toda novela completada tiene una `VersionNovela` con su texto vigente. Se generan estructuras sintéticas y se busca la violación. |
| **Mutation testing** | Introducir contradicciones a propósito en un manuscrito correcto —cambiar una fecha, adelantar una revelación, mover un objeto— y comprobar que el validador de continuidad las detecta. Es la única forma de saber si la verificación determinista sirve de algo. |
| **Contract testing** | La forma del paquete de contexto que una etapa del pipeline entrega a la siguiente se mantiene estable con independencia de cómo cambie cada etapa por dentro. |
| **Evals** | Conjunto de escenas de referencia con su veredicto conocido, para medir si el agente juez acierta. Etiqueta `I` cuando el scorer es un modelo. |

### Requiere juicio — `I`

No hay salida correcta única; se verifica con lectura humana o con un modelo crítico, y conviene puntuarlo contra el principio concreto de [domain-knowledge.md](domain-knowledge.md) en vez de preguntar si está bien.

- **Voz y estilo constantes** — registro, ritmo y densidad sensorial iguales a `EstiloNarrativo`, escriba quien escriba la escena (principios 28-30).
- **Distancia psíquica** — la escena modula, no se queda plana a un solo nivel (29).
- **Emoción nombrada** — se construye por conducta y percepción alterada en vez de declararse (31).
- **Diálogo con subtexto** — ninguna réplica responde exactamente a la anterior; nadie explica lo que ambos ya saben (33).
- **Voces distinguibles** — al tapar las acotaciones se sigue sabiendo quién habla (25).
- **La escena se gana su lugar** — avanza trama, personaje o tema; idealmente dos de tres (10, 19).
- **Causalidad** — entre beats cabe un "pero" o un "por tanto", nunca un "y entonces" (11).
- **Argumento del antagonista** — sostiene la posición contraria del tema en su mejor versión (7).
- **Reglas de la amenaza y del sistema técnico** — lo escrito respeta `Amenaza.reglas` y `SistemaTecnologico.limites`. Detectar la violación exige interpretar el texto, no solo consultarlo (44).
- **Revelación fraccionada** — el `nivelRevelacion` avanza un peldaño y deja zona sin explicar (45).
- **Cliché y fraseo genérico** — incluido el fraseo típico de modelo, que es el riesgo propio de este proyecto (38).

### Comprobable observando — `D`

- **Lectura continua** de un acto completo en condiciones reales, no de escenas sueltas: el pavor, el ritmo y la fatiga solo se manifiestan en lectura seguida (40, 18).
- **Guardrails de canon** — el agente de redacción solo puede escribir sobre las entidades presentes en su paquete de escena; cualquier entidad inventada fuera de él se bloquea antes de llegar al manuscrito.
- **Rollout progresivo** — un cambio de estilo o de criterio se aplica primero a un capítulo y se evalúa antes de propagarlo a la obra.
- **Sandbox** — la regeneración de una escena no toca el manuscrito hasta pasar las puertas de continuidad.

### Riesgo aceptado — `U`

Se nombran explícitamente en vez de dejarlos como supuesto silencioso:

- **Si da miedo.** El efecto sobre un lector real no es medible con los métodos de este catálogo. Se aproxima con `I` y `D`, y se acepta que la aproximación es débil.
- **Calidad literaria global.** Un manuscrito puede pasar todas las puertas y ser mediocre. Ninguna puerta sustituye a la lectura de un editor.
- **Originalidad frente al corpus de entrenamiento.** Se puede detectar el cliché conocido; no se puede garantizar que una imagen no sea el lugar común estadístico del modelo.
- **Satisfacción del final.** Verificable en sus condiciones estructurales (hilos cerrados, siembras pagadas, clímax que responde la pregunta inicial), no en su efecto.

## Puntos ciegos y validadores solitarios

Ningún método es fiable por sí solo: cada uno tiene una fortaleza y una zona que no ve. Por eso un validador no se evalúa aislado, sino por lo que el conjunto deja sin cubrir.

Tres reglas:

**1. Todo método declara su punto ciego.** Un método sin punto ciego escrito no está entendido. La columna existe en la tabla determinista; en las demás secciones va como línea propia.

**2. Una propiedad con un solo validador es una propiedad en riesgo.** Se marca como *validador solitario* y se revisa antes que ninguna otra, aunque su fila esté en verde. El orden de revisión no es el orden de ejecución: se ejecuta lo barato primero, se revisa lo ciego primero.

**3. El dato autodeclarado no verifica.** Cuando la propiedad se comprueba sobre un campo que produce el mismo agente al que se juzga, el validador mide obediencia al formato, no verdad. Necesita un segundo método que mire el texto, no el metadato.

Los tres puntos ciegos estructurales de este proyecto:

| Punto ciego | Por qué | Qué lo tapa |
| --- | --- | --- |
| **Lo que el extractor no registró** | Todas las comprobaciones deterministas consultan el grafo. Una puerta no puede echar de menos un hecho que nadie escribió. El fallo entra aguas arriba y ninguna puerta lo nota. | Evals del extractor con golden dataset (`I`), antes que las de cualquier otro agente. Y, más barato, búsquedas dirigidas sobre la prosa que la comparan con lo registrado: nombres del canon sin ningún registro en la escena, cifras sin hecho de fecha o distancia, un muerto nombrado fuera de una analepsis. Avisan, no paran. |
| **El metadato autodeclarado** | `valorInicial`/`valorFinal`, `pov` y `EstadoHilo.estado` los escribe el agente evaluado. La consulta es impecable y el dato puede ser mentira. | Un segundo método sobre el texto: juicio de función de escena (`I`) en la misma escena que la consulta aprobó. |
| **La lista cerrada** | Las búsquedas dirigidas solo encuentran los tics que ya están en la lista. Un verde significa «ninguno de los conocidos», no «prosa limpia». | Muestreo humano periódico que alimente la lista, y la eval de cliché (`I`). |

## Cómo se usan juntos

Los métodos de código (`A` y `T`) cubren el sistema que rodea a los agentes: determinista, verificable con las herramientas de siempre. Los métodos de proceso cubren la parte no determinista —lo que el agente decide hacer— donde la verificación pasa por muestreo (evals), juicio (inspección, multi-agente) y contención (sandbox, guardrails, rollout progresivo).

La salida narrativa se reparte entre los dos mundos, y esa es la decisión de diseño que este documento fija: **todo lo que la ontología modela como estado se verifica con `A`, no con un modelo juez.** Preguntarle a un modelo si hay una contradicción de continuidad es caro, lento y poco fiable cuando la respuesta está en una consulta al grafo. El juicio se reserva para lo que de verdad lo necesita: voz, subtexto, función de escena y cliché.

> **Decisión sin entrevistar, 23 de septiembre de 2026** (spec3, RF3-PAS-12). **Una excepción: las cuentas.** El juez de oficio comprueba que las cifras de la prosa cuadren con los hechos y dentro del capítulo (`cuentas_cuadran`). La consulta compara cada valor con el de su mismo sujeto y atributo, y no suma ni resta entre datos distintos. Además, una cifra que el extractor no registra como hecho no llega al grafo. En la primera novela completa, tres de las cuatro contradicciones reales que pasaron las puertas eran de este tipo. Se descartó modelar la aritmética en el grafo: haría falta que el extractor guardara cada cifra con su unidad y su relación con las demás, que es justo lo que falló. El resto de la continuidad sigue siendo `A`, y el juez recibe los hechos como canon cerrado.

**Picaresca antes que juicio.** Antes de mandar una propiedad a un modelo juez, se busca el atajo determinista, aunque solo cubra una parte. Es la regla que produjo las mejores comprobaciones del catálogo: convertir la continuidad en una consulta al grafo en vez de en una pregunta; medir si una escena hace algo comparando dos campos en vez de leyéndola; cazar tics con una lista cerrada en vez de con crítica literaria; y romper un manuscrito correcto a propósito para saber si el validador sirve de algo. Una cobertura parcial y barata vale más que un juicio caro y variable, siempre que su punto ciego quede escrito.

El orden importa. Las puertas deterministas van primero porque son baratas y su fallo invalida el trabajo posterior: no tiene sentido evaluar la prosa de una escena que contradice el canon. La secuencia concreta de puertas por etapa del pipeline vive en [architecture.md](architecture.md).

Toda propiedad que importe debe terminar con una etiqueta asignada. Si no cae en `T`, `A`, `I` ni `D`, se marca `U` y se deja escrita como riesgo aceptado. Y toda propiedad que termine con un solo método debe terminar además con el punto ciego de ese método escrito al lado.

> **Decisión sin entrevistar, 22 de septiembre de 2026.** Tres filas de la tabla determinista se apoyaban en atributos que [definitions.md](definitions.md) ha dejado de tener, y se han reapuntado a los registros que los sustituyen. El cambio de fondo está en las dos primeras: la continuidad factual se comprueba sobre un **triple** y no sobre un enunciado libre, y el conocimiento no adquirido necesita **dos** registros, el de lo que un personaje adquirió y el de lo que usó. Sin esa segunda lista la comprobación no se puede escribir como consulta, y quedaría como juicio: exactamente lo que este documento dice que no debe pasar.
>
> El plan de verificación concreto del backend, con su estado fila a fila, vive en [specs/spec1-verification.md](../specs/spec1-verification.md).

> **Decisión sin entrevistar, 22 de septiembre de 2026.** Se añade la sección [Puntos ciegos y validadores solitarios](#puntos-ciegos-y-validadores-solitarios), la columna *Punto ciego* en la tabla determinista y el principio de picaresca. El catálogo nombraba lo que cada método **detecta** y nunca lo que se le **escapa**, de modo que una tabla de verificación podía quedar entera en verde con todas sus filas sostenidas por un único validador ciego: cobertura de etiquetado, no confianza. `U` no cubría este hueco, porque `U` es lo que **ningún** método ve, y un punto ciego es lo que un método concreto no ve pero otro sí podría ver.
>
> Se descartó abrir una sexta etiqueta de Trust Spec para la ceguera: la clasificación dice de dónde sale la evidencia, y el punto ciego es una propiedad del método, no una fuente distinta. Se descartó también fijar un mínimo de dos métodos por propiedad, porque obligaría a inventar verificación de relleno donde uno basta; en su lugar el segundo método solo es obligatorio cuando el dato lo declara el agente evaluado.
>
> El cambio afecta a la skill `verificacion`, que asignaba «el método más barato que dé evidencia real» sin preguntar qué se le escapa.

> **Decisión sin entrevistar, 23 de septiembre de 2026.** Tres filas nuevas en la tabla determinista, para el encargo de una novela personalizada ([specs/spec3.md](../specs/spec3.md), 3.2). La completitud y la coherencia del encargo se comprueban en código antes de llamar a ningún agente, por picaresca: qué falta y qué se contradice tiene respuesta exacta, y preguntárselo al entrevistador convertiría un brief incompleto en uno «bueno porque el agente lo dijo». Dos de las tres filas descansan en **dato autodeclarado** (el punto de vista, la condición y la escena donde va cada elemento los declara el agente evaluado), así que la regla 3 exige un segundo método sobre el texto; para la personalización, ese método es comprobar el elemento en la prosa contra la tabla de hechos, y está en el plan de entrega como pendiente.
