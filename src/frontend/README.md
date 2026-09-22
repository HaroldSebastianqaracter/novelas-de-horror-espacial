# Frontend

Stack: React + Three.js.

Pendiente de implementación — ver [docs/architecture.md](../../docs/architecture.md).

## Ideas guardadas

Ideas de producto todavía sin decidir ni especificar. Se apuntan aquí para no perderlas; ninguna es un compromiso. Cuando una se adopte, sale de esta lista y entra en su spec de `specs/`, y lo que afecte a la arquitectura se lleva a `docs/` con la entrevista que exige [AGENTS.md](../../AGENTS.md).

### Tablero de novelas al estilo Jira

*Apuntada el 22 de septiembre de 2026.*

Cada novela es una **cajita arrastrable**. Una vez creada, se arrastra a un bloque **creación**; de ahí pasa a **procesando** y luego a **acabado**. La referencia explícita es el tablero de Jira.

Responde a la pendiente **«qué ve el frontend»** de [docs/architecture.md](../../docs/architecture.md), que está entre panel de control de un proceso y sala de lectura: esto se inclina por el panel, con la generación como flujo de trabajo visible.

Tres cosas a resolver antes de adoptarla:

- **El frontend observa, no posee.** El estado vive en SQLite y el pipeline corre solo durante horas. Arrastrar la cajita no puede ser lo que cambia el estado: tiene que traducirse a una **intención** (`arrancar`, `parar`, `relanzar`) de las que fija [specs/spec1.md](../../specs/spec1.md), y la columna se pinta desde `GET /novelas/{id}/ejecucion`. Una cajita que se mueve sola al llegar un evento es lo correcto; una que se queda donde el usuario la soltó, no.
- **Los estados de la ejecución son nueve, no tres**: `configurada`, `planificando`, `escaletando`, `generando`, `parada`, `detenida`, `completada`, `completada_con_avisos` y `error`. Hay que decidir cómo se agrupan en las tres columnas y, sobre todo, dónde caen `parada` y `error`, que son los que piden atención del autor y no deberían quedar escondidos dentro de «procesando».
- **Una obra a la vez.** La arquitectura de ejecución asume un solo autor y una sola novela generándose, así que el tablero tendrá casi siempre una cajita en movimiento y el resto quietas. Conviene comprobar que sigue mereciendo la pena frente a una vista de una sola novela.

Encaja en `src/frontend/src/funcionalidades/ejecucion/`, la carpeta que ya prevé la arquitectura.
