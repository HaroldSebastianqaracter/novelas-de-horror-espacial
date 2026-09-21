# Validators — Métodos de verificación

Catálogo de métodos para comprobar que el código del proyecto y la salida de los agentes son correctos. Este documento fija el vocabulario y la clasificación; qué método concreto se aplica a cada componente se decidirá junto con la arquitectura (ver `architecture.md`).

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

## Cómo se usan juntos

Los métodos de código (`A` y `T`) cubren el sistema que rodea a los agentes: determinista, verificable con las herramientas de siempre. Los métodos de proceso cubren la parte no determinista —lo que el agente decide hacer y lo que escribe— donde no hay una salida "correcta" única y la verificación pasa por muestreo (evals), juicio (inspección, multi-agente) y contención (sandbox, guardrails, rollout progresivo).

Toda propiedad que importe debe terminar con una etiqueta asignada. Si no cae en `T`, `A`, `I` ni `D`, se marca `U` y se deja escrita como riesgo aceptado.
