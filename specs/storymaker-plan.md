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

- [ ] `CLAUDE.md` cuidado y legible: el enunciado lo evalúa, y hoy es un stub.
- [ ] README raíz, `.env.example` y un brief de ejemplo reproducible.
- [ ] Renombrar el remoto a **storyMaker**.
- [ ] Commitear `.claude/commands/` y los ficheros de memoria del proyecto (hoy la memoria vive fuera del repo).
- [ ] Esqueleto de `/docs` con el formato del examen: spec inicial, trade-offs, explainers, diagramas, registro de iteraciones y red-team log. Los docs actuales (`architecture.md`, `validators.md`, `definitions.md`, `domain-knowledge.md`) se enlazan desde ahí; no se duplican.
- [ ] **Empezar el registro de iteraciones** con la auditoría del 23 de septiembre y las fases de spec2: cada hallazgo, su reproducción y el cambio que provocó ya son causa y efecto.

### 2. Personalización del terror

- [ ] **Brief** con schema: destinatario (nombre, edad, rasgos, recuerdos), intensidad del terror, tono, extensión y palabras o temas vetados por el cliente.
- [ ] **Agente entrevistador** (tarea y skill) que detecta los datos que faltan y al menos una contradicción. La natural en este género es **edad del lector frente a intensidad del terror**.
- [ ] **Texto libre no confiable** (una anécdota, una carta): se extraen hechos, nunca instrucciones.
- [ ] El brief alimenta al arquitecto y al elenco. El destinatario pasa a ser personaje, sus recuerdos se trasladan a la estación, y se genera la dedicatoria.
- [ ] Escala del examen: **10 capítulos de 1.000–1.500 palabras**.

### 3. Huecos de la story bible

- [ ] Tabla **hecho → capítulos donde se usa**: hoy solo se guarda dónde se establece. Sin ella no se puede regenerar solo lo afectado por un cambio del lector.
- [ ] Fechas de nacimiento o edades de los personajes, que el invariante de edad de Lean necesita.
- [ ] Vista de **cronología**: evento, momento, personajes y lugar.
- [ ] Entidad **versión de la novela**, con qué capítulos cambiaron respecto a la anterior.

### 4. Observabilidad con Langfuse

Va pronto porque el tuning y el coste necesitan datos acumulados.

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

> **Decisión del plan.** HTML estático exportado a PDF, sin frontend React. El frontend no existe, el HTML es lo que el browser MCP puede inspeccionar, y el PDF cubre la entrega y `/ejemplos/novela-ejemplo.pdf`. Los cambios del lector se piden desde fuera del documento (CLI o formulario mínimo), que es la variante PDF del enunciado.

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

- [ ] **Servidor MCP** de solo lectura con FastMCP sobre la API que ya existe: `list_novels`, `get_chapter`, `list_versions`, `query_story_bible` y `download_novel`.
- [ ] **Linters de prosa:** la parte mecánica de la puerta 4 ya es uno (palabras filtro, adverbios de atribución, verbos de habla); ampliarla con repeticiones, frases largas y fraseo típico de IA.
- [ ] **Security report** en `/docs/security-report.md`, partiendo de la auditoría, de bandit y del `validador-de-codigo`.
