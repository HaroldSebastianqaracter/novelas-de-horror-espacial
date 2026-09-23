# Skills, subagentes y comandos

Las herramientas de Claude Code que se han usado o creado durante el desarrollo, con su propósito y su resultado. Hay dos familias que no conviene confundir: las **skills de ejecución**, que son el prompt de sistema de los agentes del pipeline, y las **herramientas de desarrollo**, que ayudan a construir el sistema y no forman parte de él.

## Skills de ejecución (`.claude/skills/`)

Una por agente del pipeline. El puerto lee la `SKILL.md` y se la entrega a Claude Code como prompt de sistema; cada una reparte solo el oficio de su fase (architecture.md, «Agentes y sus skills»).

| Skill | Rol | Qué produce |
| --- | --- | --- |
| `arquitecto` | Planner | Premisa, logline, pregunta dramática, tema, subgénero, tipo de final y estilo narrativo |
| `mundo` | Planner | Estación, sistemas técnicos, lugares, facciones, amenaza con sus reglas y línea de tiempo |
| `elenco` | Planner | Personajes con su cadena fantasma → herida → mentira → defecto, arco y rol |
| `estructura` | Planner | Actos, hilos, puntos de giro, siembras y objetos |
| `escaleta` | Planner | Capítulos, secuencias y escenas con POV, objetivo, conflicto y valor en juego |
| `redaccion` | Writer | La prosa de un capítulo |
| `extraccion` | Extractor | Hechos, conocimiento, estados, eventos y siembras que fija la prosa |
| `oficio` | Editor | Veredicto por criterio de oficio, con evidencia |
| `continuidad` | Editor | El informe legible de un conflicto que la puerta 3 ya detectó |

## Herramientas de desarrollo

| Herramienta | Tipo | Dónde vive | Propósito | Resultado |
| --- | --- | --- | --- | --- |
| `verificacion` | Skill | `.claude/skills/verificacion/` | Construir o revisar el plan de verificación de una spec: propiedad, método, etiqueta T/A/I/D/U y punto ciego | Los planes [spec1-verification](../../specs/spec1-verification.md) y [spec2-verification](../../specs/spec2-verification.md). El puerto rechaza invocarla como agente |
| `validador-de-codigo` | Subagente | Repo MyFactory, `.claude/agents/`; instalado en `~/.claude/agents/` | Validar el código que escribe otro agente: ejecuta tests y linters, comprueba que cada test nuevo fallaba antes del cambio y busca la picaresca del implementador | Creado el 23 de septiembre de 2026. Se lanza con `/validar-cambio` |
| `revisor-de-agentes` | Subagente | Repo MyFactory | Revisar definiciones de subagentes contra buenas prácticas documentadas | Checklist con el que se escribió `validador-de-codigo` |
| `writing-for-agents` | Skill (usuario) | `~/.claude/skills/` | Guía para escribir documentos que consume un agente | Aplicada a `validador-de-codigo` y a `CLAUDE.md` |
| `find-skills` | Skill (usuario) | `~/.claude/skills/` | Buscar skills del ecosistema para una tarea | En la auditoría del 23 de septiembre encontró candidatas para Python, SQLite y RAG (`python-code-review`, `sqlite-database-expert`, `rag-eval`). **No se instaló ninguna**: el control de permisos bloqueó instalar código de terceros sin verificar |
| `grillme` | Skill (usuario) | `~/.claude/skills/` | Entrevista corta antes de decidir en `docs/` | Las decisiones marcadas como «entrevistadas» en los documentos |

## Comandos del proyecto (`.claude/commands/`)

| Comando | Propósito |
| --- | --- |
| `/verificar` | Tests, ruff y pyright del backend, con el resultado literal de cada uno |
| `/demo-falsa` | El pipeline entero con el puerto falso sobre una base temporal, sin tocar la del autor |
| `/validar-cambio` | Lanza `validador-de-codigo` sobre un commit, un rango o el árbol de trabajo |
| `/sincronizar-memoria` | Copia la memoria de Claude Code a `.claude/memoria/` |

## Sesiones de Claude Code como implementador

spec2 la aplicó fase a fase otra sesión de Claude Code, a partir de [spec2-plan.md](../../specs/spec2-plan.md): diez fases y un commit por fase, cada una con su test rojo previo, su spec y su plan de verificación. El resultado está en el [registro de iteraciones](registro-iteraciones.md), entradas 3 a 13.
