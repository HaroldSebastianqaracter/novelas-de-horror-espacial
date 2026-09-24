# Explainers

Un párrafo por concepto del curso aplicado en el proyecto: qué es, en una frase, y cómo se aplica aquí. No repite la teoría; enseña dónde está en el código.

## Aplicados

**Harness.** El código que rodea al modelo y decide qué ve, qué puede hacer y cuándo se acepta lo que produce. Aquí es el orquestador de `src/backend/orquestador/`: elige la fase, monta el paquete de contexto, invoca al agente, valida su salida y aplica las puertas. El modelo escribe y juzga; nunca decide el flujo.

**Spec-driven development.** El código sigue a una spec con requisitos numerados. Aquí es la primera regla de `AGENTS.md`: todo cambio en `src/` empieza en `specs/`, y la spec entra en el mismo commit. El código cita los requisitos (`RF2-PIPE-12`) y los tests también.

**Multi-agent por fases.** Varios agentes especializados en lugar de uno generalista. Aquí hay uno por fase de la escritura (planner, writer, editor y extractor), cada uno con su skill en `.claude/skills/` y su carpeta en `src/backend/tareas/`. Una tarea no importa de otra, y un test lo comprueba.

**Context engineering.** Seleccionar qué entra en cada llamada en vez de volcarlo todo. Aquí el paquete de capítulo (`compartido/contexto/paquete.py`) se ensambla por bloques con presupuesto propio, dentro de un techo de 100.000 tokens. Cada elemento es obligatorio u opcional, y si lo obligatorio no cabe el sistema para en vez de truncar el canon.

**Memoria externa (story bible).** Lo que el modelo no puede recordar entre llamadas vive fuera de él. Aquí es la base SQLite: cada hecho que fija la prosa se guarda como triple con su escena de origen, y el extractor lo registra antes de dar el capítulo por terminado. Los resúmenes por capítulo construyen el estado rodante.

**Checkpoint y reanudación.** Poder retomar desde la última unidad completa. Aquí la unidad es el capítulo: como todo el estado es append-only con escena de origen, volver al capítulo N es borrar lo posterior (`orquestador/fallo.py::revertir_grafo`). Un worker caído se recupera así al arrancar.

**Tools con schema.** La salida del agente se valida contra un esquema antes de usarla. Aquí cada tarea tiene su `esquemas.py` (Pydantic); el esquema viaja al CLI como JSON Schema, y lo que no valida se repite una vez con el error adjunto antes de fallar.

**Retries con límite.** Reintentar lo recuperable sin entrar en bucle. Aquí la puerta 4 devuelve el capítulo al writer como máximo tres veces con el criterio incumplido; después abre una parada. El puerto repite una vez una salida inválida, y la escaleta, una vez.

**Guardrails por construcción.** Impedir la conducta indebida quitando el medio, no pidiéndola. Aquí el agente corre sin herramientas y en un directorio vacío, así que no puede leer el repo aunque quiera. Si aun así lo intenta (permisos denegados en la respuesta), el puerto lo trata como error.

**Validación determinista antes que juicio.** Lo que tiene respuesta exacta se comprueba con código. Aquí la continuidad es SQL: la puerta 3 compara hechos, conocimiento, presencia y cronología dentro de la misma transacción que los inserta, y si hay conflicto revierte.

**LLM-as-judge.** Un modelo evalúa con una rúbrica lo que no tiene respuesta única. Aquí es el agente `oficio`, que da un veredicto por criterio (voz, distancia psíquica, subtexto, cliché…) con su evidencia citada. *Pendiente para la entrega:* puntuación por criterio y un criterio de personalización.

**Trust Spec (T/A/I/D/U).** Cada comprobación se etiqueta por el origen de su evidencia: ejecutar (T), analizar (A), leer y juzgar (I), observar (D) o riesgo aceptado (U). Aquí es el vocabulario de `docs/validators.md` y de los planes de verificación; toda propiedad lleva su etiqueta.

**Puntos ciegos y validador solitario.** Cada método tiene una zona que no ve, y una propiedad con un solo método está en riesgo. Aquí es una columna obligatoria en los planes de verificación. El caso canónico: la puerta 3 solo ve los hechos que el extractor registró, así que el extractor tiene sus propias evals.

**Picaresca.** Antes de mandar algo a un juez, buscar el atajo determinista aunque cubra solo una parte. Aquí produjo las búsquedas dirigidas de la puerta 3: nombres del canon en la prosa sin registro, cifras sin hecho, un muerto nombrado.

**Property-based testing.** Afirmar una propiedad para cualquier entrada y dejar que la herramienta busque el contraejemplo. Aquí, con `hypothesis`: «ningún elemento obligatorio se pierde al recortar el paquete», en `tests/test_paquete.py`.

**Mutation testing.** Romper a propósito algo correcto para saber si el validador lo detecta. Aquí se introducen contradicciones en un grafo limpio (`tests/test_puerta_continuidad.py`) y se rompe la demo una comprobación cada vez (`tests/test_demo.py`).

**Model checking.** Explorar todos los estados alcanzables para comprobar un invariante. Aquí `tests/test_estados_exhaustivo.py` recorre la máquina de estados por anchura (19 estados abstractos, unas mil transiciones) y comprueba que ningún capítulo se genera sin las puertas 1 y 2 vigentes. Ejecuta el código real, pero solo hasta cuatro pasos de profundidad.

**Especificación con TLA+ y TLC.** Describir un sistema como estados y acciones en un lenguaje matemático, y dejar que un model checker recorra todos los comportamientos posibles de un modelo pequeño. Busca un estado que rompa un invariante (seguridad) o un comportamiento que nunca llegue a donde debe (liveness). Aquí es `formal/tla/StoryMaker.tla`:

- cada acción es una transacción del orquestador o del worker;
- las puertas son elecciones no deterministas;
- TLC comprueba, con 5 capítulos y 2 reintentos, que nunca se publica un capítulo sin sus puertas, que reanudar no pierde ni duplica capítulos, que la versión anterior se conserva y que toda ejecución termina.

Encontró el hallazgo 1 en la máquina de spec1 y dos fallos nuevos:

- uno del diseño del cambio del lector, antes de implementarlo: un renombrado dejaba la novela completada con las puertas 1 y 2 sin vigencia;
- uno del código actual: una caída justo después de una parada de presupuesto dejaba un capítulo a medias.

El segundo salió porque el validador vio que la primera versión del modelo juntaba dos transacciones en un solo paso: un modelo que simplifica de más da verdes falsos. `comprobar_tablas.py` mantiene sus tablas iguales a las del código. `mutaciones.py` rompe el modelo a propósito para comprobar que los invariantes miran algo.

**Verificación formal con Lean 4.** Demostrar una propiedad en vez de probarla con ejemplos. Aquí el generador (`src/backend/orquestador/lean.py`) escribe desde la story bible un fichero `.lean` con solo datos: eventos con su día, quién está en cada uno, nacimientos, muertes y edades que afirma la prosa. Los invariantes viven en `formal/lean/Storymaker/Cronologia.lean` (nadie antes de nacer, nadie tras morir, edad coherente y el tiempo no retrocede), y el fichero de cada novela los afirma con `decide`: si compila, la novela los cumple. La biblioteca demuestra además, para cualquier novela, que la lista de testigos de cada invariante está vacía si y solo si se cumple, así que cuando falla dice qué evento y qué personaje lo rompen sin poder discrepar de la prueba; cambiar un invariante sin cambiar sus testigos deja de compilar. Lean compara por el día, no por el orden de las escenas, y por eso ve lo que la puerta 3 salta: un recuerdo situado después de una muerte, un muerto que el extractor registra presente fuera del reparto, una analepsis a antes de que naciera quien la vive, una edad que no cuadra con el elenco. Los cinco casos están en `tests/test_formal_lean.py`, y en todos la puerta 3 da verde. En novelas reales no ha saltado, y la razón está en los datos. La de diez capítulos (24 de septiembre, completa) le dio a Lean 115 eventos con día, 300 presencias y 5 nacimientos, y pasó en 5 segundos; pero ninguna de las cuatro novelas reales tiene una sola analepsis, solo una tiene una muerte y las edades que afirma la prosa vienen en letra («treinta y cuatro años»), que Lean no lee. Tres de los cuatro invariantes apenas tenían material; el del tiempo sí (98 eventos de la línea principal y 11 antecedentes) y se cumplió. La única edad declarada, además, cuadra con el elenco. Hay una incoherencia real que ninguno de los dos vio: en la primera novela, el capítulo 4 cuenta la pérdida de Kaminski el «día tres» y el capítulo 3 la había registrado el día 2, pero el extractor no le puso día a ese recuerdo, y sin día Lean no lo compara (spec-lean, «Lo que no hace»).

**Prompt injection y contenido no confiable.** Un texto que aporta el usuario puede intentar dar órdenes al modelo. Aquí el texto libre del brief va delimitado y marcado como no confiable, pero la defensa no descansa en que el agente obedezca: de ese texto el código solo acepta rasgos, recuerdos y allegados, y cada uno con una cita literal que se comprueba contra el texto. Una búsqueda de patrones conocidos deja además una alerta (`tareas/entrevistador/servicio.py`).

**Evals con golden set.** Medir un agente contra un conjunto de referencia con resultado conocido. Aquí el extractor se mide contra un capítulo anotado a mano con un puntuador determinista de recall: 15 de 15 con Claude Code real.

**Observabilidad con Langfuse.** Ver cada llamada, su coste y cada validador de una ejecución larga en un solo sitio. Aquí la fuente es la base y no un registro aparte: el exportador (`orquestador/observabilidad.py`) lee `llamada_modelo` y `resultado_puerta` y los manda como generaciones, spans y scores, con una sesión por novela e identificadores deterministas, para que reenviar no duplique. El coste es el que declara Claude Code en cada llamada, y los nombres del encargo se seudonimizan antes de salir. La lección viene del primer harness, donde Langfuse declaraba menos de la cuarta parte del coste real.

## Pendientes para la entrega

Se escriben cuando se apliquen, con el mismo formato: **hooks** de validación y de policy, **guardrail de palabras prohibidas**, **validación visual con browser MCP** y **revisión humana** frente a LLM-as-judge.
