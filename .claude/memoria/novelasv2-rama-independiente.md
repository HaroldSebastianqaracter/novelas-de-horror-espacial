---
name: novelasv2-rama-independiente
description: La rama novelasv2 es un proyecto nuevo que vive aparte de main y nunca se fusionará con ella
metadata: 
  node_type: memory
  type: project
  originSessionId: fce89bdd-447f-4782-bcb6-ad97c49ef99a
  modified: 2026-09-21T16:45:17.218Z
---

La rama `novelasv2` arranca vacía sobre `main` (commit "Rama vacía como punto de partida limpio") y borra el proyecto anterior entero (harness, specs, diseños Falcon). El usuario confirmó el 21 de septiembre de 2026 que **novelasv2 y main viven separadas y no se unirán en ningún momento**.

**Why:** main conserva el proyecto viejo; novelasv2 es el rediseño desde cero con docs/ como base.

**How to apply:** nunca proponer PR ni merge de novelasv2 a main. Los commits van directos a novelasv2. Ignorar el aviso del entorno de que main es la rama para PRs.
