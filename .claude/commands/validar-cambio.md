---
description: Lanza el subagente validador-de-codigo sobre un commit, un rango o el árbol de trabajo
argument-hint: "<commit | rango | vacío para el árbol de trabajo> [qué debía hacer]"
---

Delega en el subagente `validador-de-codigo` la validación de este cambio: $ARGUMENTS

Si no se indicó qué debía hacer el cambio, dedúcelo antes de delegar (el mensaje del commit, y la fase de [specs/spec2-plan.md](../../specs/spec2-plan.md) o el bloque de [specs/storymaker-plan.md](../../specs/storymaker-plan.md) que cite) y pásaselo al subagente junto con la referencia: sin eso no puede medir la cobertura del requisito.

Cuando termine, muestra su veredicto y sus hallazgos bloqueantes tal cual. Si el veredicto es RECHAZADO, el paso no está cerrado.

El subagente vive en el repo MyFactory y se instala en `~/.claude/agents/`. Si no está disponible en esta sesión, dilo y no hagas la validación tú mismo: su valor es que la hace un contexto que no escribió el código.
