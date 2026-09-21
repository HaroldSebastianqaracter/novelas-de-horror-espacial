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

| Propiedad | Se comprueba sobre | Fallo que detecta |
| --- | --- | --- |
| Continuidad factual | `Hecho` (`enunciado`, relación `establecidoEn`) | El texto afirma algo que contradice un hecho ya establecido: un nombre, una fecha, un rasgo físico, una distancia. |
| Conocimiento no adquirido | `EstadoDeConocimiento` (`postura`, `via`, relación `desde`) | Un personaje actúa sobre información que todavía no ha recibido, o se sorprende de algo que ya sabía. Es la fuente número uno de errores en obra larga. |
| Siembras sin pago | `Siembra` (`estado`) | Elemento plantado que llega al final sin recogerse, o pago que aparece sin siembra previa. |
| Hilos sin cerrar | `HiloNarrativo` (`estado`) | Hilo que termina la novela en `abierto` sin estar marcado como abierto deliberadamente; hilo `latente` más allá del umbral fijado; cierre en orden distinto al inverso de apertura. |
| Presencia imposible | `Escena` (reparto), `Lugar` (`presenciaActual`), `EstadoObjeto` | Un personaje en dos lugares a la vez; un objeto que aparece sin traslado registrado desde su última ubicación. |
| Coherencia temporal | `LineaDeTiempo`, `Evento` (`fechaInterna`) | Duraciones incompatibles, edades que no cuadran, sucesos fuera de orden. |
| Escena sin cambio de valor | `Escena` (`valorInicial`, `valorFinal`) | La escena termina en la misma polaridad en que empezó: es relleno declarado. |
| Integridad de POV | `Escena` (`pov`), `Novela` (`povPorDefecto`) | Escena sin POV declarado, o cambio de conciencia focal dentro de una misma escena. |
| Presupuesto | `Restriccion` (`valor`) | Longitud de acto, capítulo o escena fuera del rango fijado; desviación de la longitud objetivo. |

### Comprobable ejecutando — `T`

| Método | Aplicación al dominio |
| --- | --- |
| **Búsquedas dirigidas** | Pasadas mecánicas sobre listas cerradas: palabras filtro (vio, oyó, sintió, notó), adverbios de atribución, verbos de habla expresivos, tics de `EstiloNarrativo.ticsProhibidos`, repetición de nombres, deriva ortográfica de nombres propios inventados. |
| **Property-based testing** | Invariantes que deben cumplirse sea cual sea la novela generada: todo `Hecho` tiene escena de origen; toda `Siembra` pagada tiene su escena de pago posterior a la de siembra; ningún `EstadoDeConocimiento` precede a la escena que establece su `Hecho`. Se generan estructuras sintéticas y se busca la violación. |
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

## Cómo se usan juntos

Los métodos de código (`A` y `T`) cubren el sistema que rodea a los agentes: determinista, verificable con las herramientas de siempre. Los métodos de proceso cubren la parte no determinista —lo que el agente decide hacer— donde la verificación pasa por muestreo (evals), juicio (inspección, multi-agente) y contención (sandbox, guardrails, rollout progresivo).

La salida narrativa se reparte entre los dos mundos, y esa es la decisión de diseño que este documento fija: **todo lo que la ontología modela como estado se verifica con `A`, no con un modelo juez.** Preguntarle a un modelo si hay una contradicción de continuidad es caro, lento y poco fiable cuando la respuesta está en una consulta al grafo. El juicio se reserva para lo que de verdad lo necesita: voz, subtexto, función de escena y cliché.

El orden importa. Las puertas deterministas van primero porque son baratas y su fallo invalida el trabajo posterior: no tiene sentido evaluar la prosa de una escena que contradice el canon. La secuencia concreta de puertas por etapa del pipeline vive en [architecture.md](architecture.md).

Toda propiedad que importe debe terminar con una etiqueta asignada. Si no cae en `T`, `A`, `I` ni `D`, se marca `U` y se deja escrita como riesgo aceptado.
