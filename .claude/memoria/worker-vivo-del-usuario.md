---
name: worker-vivo-del-usuario
description: El usuario suele tener un worker propio corriendo sobre src/backend/novela.db; nunca detener procesos python por patron de linea de comandos
metadata:
  node_type: memory
  type: project
  originSessionId: fbf54757-2b05-44b4-bfe3-9ca8f8603190
  modified: 2026-09-23T09:33:56.193Z
---

El usuario deja a menudo un `python -m worker` suyo vivo sobre `src/backend/novela.db` (visto el 23-09-2026, pid 22468, puerto falso). En Windows cada `.venv\Scripts\python.exe -m worker` son **dos** procesos (lanzador + hijo) con la misma linea de comandos.

**Why:** el 23-09-2026, al parar un worker de prueba filtrando por `-m worker`, detuve tambien el del usuario (estaba inactivo, sin perdida, pero hubo que avisarle).

**How to apply:** para pruebas de humo del worker, usa una base temporal propia y captura el pid del proceso que lances (`Start-Process -PassThru` o `$!`); detén solo ese pid y su hijo. Nunca `Stop-Process` por patron de CommandLine.
