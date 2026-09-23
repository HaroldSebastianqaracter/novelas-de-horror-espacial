---
name: repo-my-factory
description: "El repo My-factory (\"myfactory\") es donde el usuario guarda sus agentes y skills reutilizables de Claude Code"
metadata: 
  node_type: memory
  type: reference
  originSessionId: fce89bdd-447f-4782-bcb6-ad97c49ef99a
  modified: 2026-09-21T16:58:15.014Z
---

Repo de herramientas del usuario: https://github.com/HaroldSebastianqaracter/My-factory, clon local en `C:\Users\harold.rodriguez\Desktop\Nueva carpeta\My-factory`, rama `main`, sin `gh` instalado (se empuja con `git push` directo).

Layout: `.claude/agents/<nombre>.md` para subagentes y `.claude/skills/<nombre>/SKILL.md` para skills, con una tabla por tipo en `README.md` (skill, qué hace, cómo invocarla). Mensajes de commit en castellano sin tildes, estilo "Anade la skill X".

**How to apply:** cuando el usuario diga "súbela a myfactory" o pida guardar una skill/agente reutilizable, copiar ahí, añadir la fila al README y hacer commit y push. Las skills genéricas también se instalan en `~/.claude/skills/` para que le funcionen en todos los proyectos.
