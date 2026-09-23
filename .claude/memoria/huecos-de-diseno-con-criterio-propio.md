---
name: huecos-de-diseno-con-criterio-propio
description: "El usuario no conoce el proyecto a fondo y prefiere que resuelva huecos de diseño con criterio propio, marcándolos como \"Decisión sin entrevistar\" en el doc"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: fce89bdd-447f-4782-bcb6-ad97c49ef99a
  modified: 2026-09-21T16:45:24.344Z
---

Al corregir inconsistencias en `docs/`, el usuario eligió "todo, con tu criterio": que resuelva los huecos de diseño con la opción más coherente con lo que los docs ya defienden, y que cada decisión quede marcada en el propio doc como "Decisión sin entrevistar" (callout `>` como los que ya usa architecture.md). Solo pidió que le pregunte lo que de verdad cambia el producto (quién fija `Restriccion`, si hay agente Revisor).

**Why:** el usuario dijo "no sé mucho del proyecto"; está preparando el arranque y no tiene contexto para decidir cada detalle. La entrevista `grillme` que exige AGENTS.md sigue siendo obligatoria, pero corta: 3-4 preguntas con opción recomendada primero.

**How to apply:** en `grillme` sobre docs/, preguntar solo las decisiones de producto; el resto decidirlo y dejarlo escrito en el doc con fecha. Ver [[novelasv2-rama-independiente]].
