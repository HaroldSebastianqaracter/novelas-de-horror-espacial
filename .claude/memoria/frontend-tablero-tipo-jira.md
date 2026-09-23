---
name: frontend-tablero-tipo-jira
description: "Idea guardada para el frontend: la novela es una cajita que se arrastra por columnas tipo Jira (creación → procesando → acabado)"
metadata:
  type: project
---

Idea que el usuario pidió guardar el 22 de septiembre de 2026, **sin implementar todavía**: el frontend presenta cada novela como una **cajita arrastrable**. Una vez creada la novela, se arrastra a un bloque o columna llamado **creación**; de ahí pasa a **procesando** y luego a **acabado**. La referencia explícita es **el tablero de Jira**.

**Why:** responde a la pendiente «qué ve el frontend» de [docs/architecture.md](docs/architecture.md), que estaba entre panel de control de un proceso y sala de lectura. Esto se inclina claramente por el panel de control, con la generación como flujo de trabajo visible.

**How to apply:** no tocar el frontend ni `docs/` por esto hasta que el usuario lo pida. Cuando llegue el momento:

- Contrastarlo con la arquitectura ya escrita: el frontend **observa, no posee**, y el estado vive en SQLite. Arrastrar la cajita no puede ser el que cambia el estado; tiene que traducirse a una **intención** (`arrancar`, `parar`, `relanzar`) de las que fija `specs/spec1.md`, y la columna se pinta desde `GET /novelas/{id}/ejecucion`.
- Los estados reales de `ejecucion` en la spec son nueve (`configurada`, `planificando`, `escaletando`, `generando`, `parada`, `detenida`, `completada`, `completada_con_avisos`, `error`), no tres. Hay que decidir cómo se agrupan en las tres columnas y dónde caen `parada` y `error`, que son los que piden atención del autor.
- Encaja con `src/frontend/src/funcionalidades/ejecucion/`, la carpeta que ya prevé la arquitectura.

Ver [[huecos-de-diseno-con-criterio-propio]] para el estilo de decisión que el usuario prefiere.
