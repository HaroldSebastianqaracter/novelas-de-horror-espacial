# Plan de entrega — storyMaker

Lista de lo que falta para la entrega final del examen de *Harness Engineering*, comparada con lo que el repo ya hace. Se va tachando a medida que se cierra. **No es una spec**: cada bloque de «Ahora» empieza escribiendo su spec en `specs/` y entra en el mismo commit que su código, como pide [AGENTS.md](../AGENTS.md).

Versión 0.1 · 23 de septiembre de 2026

> **Decisión entrevistada, 23 de septiembre de 2026.** Las novelas siguen siendo de **terror espacial**. La personalización que pide el enunciado se resuelve **dentro del género**: el terror se adapta al destinatario (su nombre, sus rasgos, sus recuerdos trasladados a la estación, la intensidad que admite su edad). Se descartó abrir el sistema a otros géneros. **storyMaker es este repositorio**, no uno nuevo.

---

## Ya cubierto

Lo que el enunciado pide y el repo ya tiene, con su evidencia en los planes de verificación:

- **Roles planner, writer y editor.** Planner = `arquitecto`, `mundo`, `elenco`, `estructura` y `escaleta`; writer = `redaccion`; editor/critic = `oficio` y `continuidad`. En la presentación se llaman así.
- **Story bible en SQLite**, con hechos como triple y escena de origen.
- **Resúmenes por capítulo** (`resumen`, `resumen_breve`) que construyen el estado rodante.
- **Checkpoint y reanudación por capítulo**, reforzados en [spec2](spec2.md) (fases 1 a 3).
- **Retries con límite** (puerta 4 ×3, puerto ×2, escaleta ×2).
- **Tools con schema validado** (JSON Schema al CLI y Pydantic).
- **Techo de 100.000 tokens** por llamada, con el presupuesto de contexto.
- **Skills** de los nueve agentes y la de `verificacion`.
- **spec2 cerrada** (fases 0 a 10) y **evals del extractor con Claude Code real** (recall 15/15, fila 38 de [spec1-verification](spec1-verification.md)).

## Ahora

En orden de dependencias: cada bloque se apoya en los anteriores.

### 1. Base del repo

- [x] `CLAUDE.md` cuidado y legible: importa `AGENTS.md` y añade solo lo propio de Claude Code (comandos, coste, datos del autor, qué son las skills, cómo se cierra un paso).
- [x] README raíz, `.env.example` y un brief de ejemplo reproducible (`ejemplos/brief-ejemplo.json`, el mismo que usa `demo.py`).
- [ ] Renombrar el remoto a **storyMaker**. Lo tiene que hacer el autor en GitHub (Settings → Repository name); después, `git remote set-url origin <url nueva>`.
- [x] `.claude/commands/` (`/verificar`, `/demo-falsa`, `/validar-cambio`, `/sincronizar-memoria`) y una copia de la memoria en `.claude/memoria/`.
- [x] `docs/proceso/` con el formato del examen: spec inicial, trade-offs, explainers, diagramas, registro de iteraciones, red-team log y herramientas. Resume y enlaza los cuatro documentos de `docs/`; no los duplica.
- [x] Registro de iteraciones al día: la auditoría, las fases de spec2, las evals del extractor y la primera llamada real.
- [x] Por qué se reinició el proyecto el 21 de septiembre (petición de la profesora), en `spec-inicial.md` y en la entrada 0 del registro.
- [ ] Hacer que el backend cargue un `.env` por su cuenta (hoy solo lee el entorno del proceso). Es un cambio en `src/` con su spec; encaja en el bloque 4, que trae las claves de Langfuse.

### 2. Personalización del terror

Requisitos en [spec3.md](spec3.md), 3.2; verificación en [spec3-verification.md](spec3-verification.md).

- [x] **Brief** con schema: destinatario (nombre, edad, pronombres, rasgos), recuerdos, allegados, ocasión, intensidad del terror, tono, subgénero, extensión (3 a 10 capítulos) y términos vetados.
- [x] **Agente entrevistador** (tarea, skill y `entrevista.py`). Qué falta y qué se contradice lo calcula el código: edad frente a intensidad, subgénero frente a intensidad y término vetado dentro de un elemento obligatorio.
- [x] **Texto libre no confiable**: solo salen rasgos, recuerdos y allegados, cada uno con cita literal comprobada, y una búsqueda de patrones de inyección deja alertas.
- [x] El brief llega a arquitecto (dedicatoria), mundo (recuerdos), elenco (destinatario protagonista y allegados), estructura, escaleta (elementos por escena) y redacción. Las puertas 1, 2 y 3 comprueban el encargo.
- [x] Escala del examen: **10 capítulos de 1.000–1.500 palabras** por defecto, derivada del brief.
- [ ] Probar la entrevista y una novela personalizada con **Claude Code real**. Cuesta dinero: pendiente de aprobación.

### 3. Huecos de la story bible

Requisitos en [spec3.md](spec3.md), 3.3; verificación en [spec3-verification.md](spec3-verification.md), filas 20 a 32.

- [x] Tabla **hecho → capítulos donde se usa** (`hecho_uso` y la vista `hecho_escena`): lo que el extractor reafirma, el valor exacto que aparece en la prosa y el conocimiento de los personajes.
- [x] Edad de cada personaje el día 0 y nacimiento derivado; el protagonista tiene la edad del destinatario (puerta 1).
- [x] Vista de **cronología** con día numérico, orden, lugar y personajes; la puerta 3 comprueba que el día y el orden no se contradigan.
- [x] Entidad **versión de la novela**, con copia del texto y qué capítulos cambiaron respecto a la anterior. Nace al completarse la novela.

### Mejoras tras la primera pasada real

Requisitos en [spec3.md](spec3.md), 3.11; verificación en [spec3-verification.md](spec3-verification.md), filas 33 a 38. Salen de la pasada del 23 de septiembre (2 de 4 capítulos, 11,57 $, seis paradas).

- [x] **Un hecho, un dato**: valor de 10 palabras como mucho. Pendiente de confirmar con la eval del extractor real (fila 34).
- [x] Resumen de unas 160 palabras con el límite duro en 250: se recortaba en 7 de 7 extracciones.
- [x] **Nombres menores**: el mundo en el inventario, variantes resueltas contra el canon, la lista de los ya usados para redactor y extractor, y un aviso por nombre nuevo.
- [ ] La puerta 4 no rechazó nada en 16 criterios: un capítulo malo conocido como eval y una comprobación mecánica de coletillas. Va con el bloque 6.
- [ ] Modelo por agente: la extracción es el 48 % del coste y todo corre con Opus. Hace falta medir el extractor con Sonnet contra el golden set (con coste).
- [ ] Los tres huecos de la parada 6: conocimiento por facción (RF2-PIPE-27), el objeto que viaja con su poseedor (RF2-PIPE-28) y los hábitos como conducta (RF2-PIPE-29). Decididos por el autor; los implementa la sesión que hizo la pasada, en spec2.

### 4. Observabilidad con Langfuse

Va pronto porque el tuning y el coste necesitan datos acumulados.

El primer harness (historial anterior al 21 de septiembre) ya tenía Langfuse integrado. Conviene mirarlo antes de empezar: commits `2280640`, `cf3ba67` y `b87775d`. Deja una lección medida: Langfuse declaraba menos de la cuarta parte del coste real porque solo anotaba a los subagentes. Aquí el coste se registra desde el puerto, llamada a llamada.

- [ ] Una traza por novela, agrupada en una sesión por novela que incluya la entrevista y las regeneraciones.
- [ ] Un span por rol y por tool, con nombre identificable.
- [ ] Tokens, coste y latencia por llamada, capítulo y novela, desde el puerto (el CLI ya devuelve `usage` y `total_cost_usd`).
- [ ] Todos los validadores como scores, a partir de `resultado_puerta`.
- [ ] Las `SKILL.md` registradas como **prompts versionados**, y cada llamada enlazada a su versión.
- [ ] Claves solo en `.env`, con su entrada en `.env.example`.

### 5. Guardrails

- [ ] Palabras prohibidas en SQLite, **globales y por novela**, con normalización de mayúsculas, acentos, plurales y variantes simples.
- [ ] Un capítulo con coincidencia vuelve al writer; con el límite agotado, la generación se detiene y se informa.
- [ ] **Audit log** de las decisiones del policy engine, también enviado a Langfuse.
- [ ] Tests: un caso por nivel y uno de variante (acento o plural).

### 6. Validadores que faltan

- [ ] Nombres escritos **exactamente** como en la story bible.
- [ ] Longitud **real** de cada capítulo dentro del rango (hoy solo se comprueba la prevista en la escaleta).
- [ ] Cada elemento personalizado obligatorio del brief aparece en al menos un capítulo, comprobado contra la tabla de hechos.
- [ ] LLM-as-judge con **puntuación y justificación por criterio** (continuidad, tono, calidad narrativa y **personalización integrada con naturalidad**). Hoy el juez de oficio da pasa/falla y no tiene criterio de personalización.
- [ ] **Dos hooks**, uno de validación del capítulo y otro de policy. Hay que decidir y justificar dónde viven: los agentes corren sin herramientas, así que los hooks de herramientas de Claude Code no se disparan nunca.

### 7. Lectura: HTML estático más PDF exportado desde él

- [ ] Índice de capítulos navegable.
- [ ] Ficha de personajes y lugares generada desde la story bible, con enlaces al capítulo donde aparece cada uno.
- [ ] Portada con dedicatoria personalizada.
- [ ] `.claude/mcp.json` con un browser MCP. El agente abre la lectura, navega y registra los errores visuales como fallos para el rol correspondiente. Su uso real se documenta en `/docs`.

> **Decisión del plan.** HTML estático exportado a PDF, sin frontend React. El frontend no existía al decidirlo, el HTML es lo que el browser MCP puede inspeccionar, y el PDF cubre la entrega y `/ejemplos/novela-ejemplo.pdf`. Los cambios del lector se piden desde fuera del documento (CLI o formulario mínimo), que es la variante PDF del enunciado. El frontend React que se decidió después (23 de septiembre) es un opcional y no cambia esta decisión.

### 8. Cambio del lector

- [ ] Pedir un cambio («el perro se llama Nala») por CLI o formulario.
- [ ] Localizar los capítulos que usan ese hecho, con la tabla del bloque 3.
- [ ] Regenerar **solo** esos capítulos sin romper la continuidad.
- [ ] Nueva versión del PDF con una página inicial de **novedades** y enlaces internos a los capítulos modificados. La versión anterior se conserva.

### 9. Validadores formales

- [ ] **Lean 4:** generar un fichero `.lean` desde SQLite con eventos, momento, personajes, lugar y fechas de nacimiento.
- [ ] Al menos dos invariantes. Candidatos directos, porque la puerta 3 ya los comprueba en SQL: orden temporal, edad coherente, nadie en dos lugares a la vez, nadie aparece tras su muerte.
- [ ] `lake build` automático como puerta antes de publicar una versión; si falla, el fallo vuelve al editor.
- [ ] **TLA+:** especificación de la máquina de estados de `orquestador/estados.py` (configuración, planificación, escritura, validación, publicación, retries, reanudación y cambio del lector).
- [ ] Al menos tres invariantes de seguridad y una propiedad de liveness.
- [ ] TLC con un modelo pequeño (5 capítulos, 2 reintentos) y su configuración en el repo.
- [ ] **Contraejemplo documentado:** el hallazgo 1 de la auditoría (resolver una parada de estructura acababa en `completada` sin capítulos). Se modela la máquina anterior a la fase 2 de spec2, se ejecuta TLC, se muestra la traza y el cambio que la cerró.
- [ ] README con la correspondencia entre cada acción de la spec y el estado o transición del código.

### 10. Infraestructura de evals

El mecanismo se construye ahora; la tabla definitiva se saca al final.

- [ ] Cinco briefs de prueba: uno **adversarial** (injection en el texto libre), uno diseñado para provocar una **incoherencia temporal** y tres normales.
- [ ] Un script que ejecuta un brief y produce la tabla de qué validadores pasaron y cuáles fallaron.
- [ ] **Medición de referencia** a mitad de camino: es el «antes» de la iteración de tuning.

## Al final

- [ ] **Pasada completa con Claude Code real** (fila 41 de spec1-verification, preparada y pendiente de aprobación) → `/ejemplos/novela-ejemplo.pdf` con el brief de ejemplo del README.
- [ ] Ejecutar los cinco briefs → **tabla de resultados** con números.
- [ ] Iteración de tuning: el **«después»**, comparado con la referencia y ligado a la versión de prompt en Langfuse.
- [ ] **Revisión humana** de una novela completa con la misma rúbrica, comparada con el LLM-as-judge.
- [ ] El caso en que **Lean detecta algo que los otros validadores no detectaron**, o la justificación de por qué no apareció.
- [ ] **Coste real por novela** desde Langfuse → slide de presupuesto: coste unitario (tokens, infraestructura y margen operativo), precio de venta y margen, coste del desarrollo en horas, tres escenarios de volumen y sensibilidad (+50 % en tokens, más de tres revisiones por novela).
- [ ] Cerrar `/docs`: diagramas finales (arquitectura del harness, máquina de estados de TLA+, esquema SQLite, tabla de validadores con su punto de ejecución), red-team log y explainers.
- [ ] Documentar en `/docs` las skills, subagentes y comandos usados (incluido el `validador-de-codigo` de MyFactory).
- [ ] **Presentación** en `/presentacion/`: marca propia (nombre, logotipo, paleta, tipografía), deck en PDF y editable, anexos como ficheros individuales, README con el contenido y el idioma, y **vídeo** de la demo del cambio del lector.
- [ ] Escaneo de secretos en el historial (fila 40) antes del commit final.
- [ ] Commit final de **MyFactory** con el README al día.
- [ ] **Email** a la dirección del enunciado, con el asunto indicado, los enlaces a los dos commits finales y la frase de diseño (máximo tres líneas).

## Opcionales (suman nota, después de lo obligatorio)

- [ ] **Frontend web** en React: un tablero de novelas al estilo Jira, la alerta de parada, un lector de capítulos y el alta desde un brief. Requisitos en [spec-frontend.md](spec-frontend.md). No sustituye al bloque 7: la lectura de la entrega sigue siendo HTML con PDF.
- [ ] **Servidor MCP** de solo lectura con FastMCP sobre la API que ya existe: `list_novels`, `get_chapter`, `list_versions`, `query_story_bible` y `download_novel`.
- [ ] **Linters de prosa:** la parte mecánica de la puerta 4 ya es uno (palabras filtro, adverbios de atribución, verbos de habla); ampliarla con repeticiones, frases largas y fraseo típico de IA.
- [ ] **Security report** en `/docs/security-report.md`, partiendo de la auditoría, de bandit y del `validador-de-codigo`.
