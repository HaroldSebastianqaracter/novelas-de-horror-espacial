# Agent

Las definiciones del proyecto están en [docs/](docs/); cada definición nueva se añade en su respectivo .md dentro de esa carpeta. Hay 4 tipos de documentos:

- [docs/architecture.md](docs/architecture.md) — arquitectura del sistema de agentes.
- [docs/definitions.md](docs/definitions.md) — ontología narrativa: entidades y relaciones del universo de la novela.
- [docs/domain-knowledge.md](docs/domain-knowledge.md) — principios de escritura y oficio narrativo.
- [docs/validators.md](docs/validators.md) — métodos de verificación del código y de la salida de los agentes.

## Estructura del proyecto

Monorepo con [src/](src/) (todo el código: [src/backend/](src/backend/) y [src/frontend/](src/frontend/)) y [specs/](specs/) (las especificaciones del programa, una por `.md`). Detalle del stack y del sistema de agentes en [docs/architecture.md](docs/architecture.md).

## Reglas de trabajo

**El código sigue a la spec.** Todo cambio en `src/` empieza por escribir o actualizar su spec en `specs/`. Si lo que vas a tocar no tiene spec, la escribes primero. La spec actualizada entra en el mismo commit que el código.

**Los cambios en `docs/` se justifican en el propio documento.** No hace falta entrevistar antes de editar. Lo que sí hace falta es que cada cambio deje escrito, ahí mismo, qué decisión lo motiva y qué alternativas se descartaron, y que se revisen los otros documentos de `docs/` que queden afectados. Lo decidido sin consultar se marca con un callout `> **Decisión sin entrevistar.**`, como los que ya usa `architecture.md`.

**Los diagramas van en Mermaid.** Todo diagrama, en respuestas, en `docs/` o en `specs/`, se escribe como bloque ` ```mermaid `. Nada de ASCII art ni de imágenes.
