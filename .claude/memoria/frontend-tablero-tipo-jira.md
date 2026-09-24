---
name: frontend-tablero-tipo-jira
description: "Frontend de novelasv2: tablero Jira + estética B; desde el 24-09-2026 la web ES la lectura de la entrega (sustituye al HTML+PDF del bloque 7)"
metadata:
  node_type: memory
  type: project
  originSessionId: bf5487d1-d438-4793-88d5-dc7afdfe2eac
  modified: 2026-09-24T08:40:11.222Z
---

La idea del tablero tipo Jira se **adoptó el 23-09-2026** como extra. Requisitos en `specs/spec-frontend.md` y verificación en `specs/spec-frontend-verification.md`. La v1 (tablero, novela, parada, lector y brief por pasos) se probó contra el backend real el 23-09.

**Cambio de alcance del 24-09-2026, confirmado por el usuario:** la web pasa a ser **la lectura de la entrega** (la variante «web» del enunciado) y sustituye al HTML+PDF del bloque 7 de storymaker-plan.md. Encargo llegado vía la sesión novelasv2-f4. Prioridades:
1. Lectura: índice, ficha de personajes y lugares desde la story bible con enlaces a los capítulos, y portada con la dedicatoria.
2. Cambio del lector desde la página, con versiones y diff de capítulos. Es la demo obligatoria. El backend lo hace f4; el frontend fija el contrato y se lo manda antes de implementarlo contra el backend.
3. Exportar a PDF (ejemplos/novela-ejemplo.pdf).
4. Playwright MCP en `.mcp.json`, usado de verdad, con la evidencia en docs/.
5. `segunda_opinion` legible en la parada.

Decisiones que siguen del 23-09:
- **Dos niveles**: una tarjeta por novela y, dentro, sus capítulos.
- Estética **B, «papel técnico»**. El prototipo está en `src/frontend/prototipo-b/`.
- Alta con **formulario del brief por pasos**.
- Se trabaja en el **mismo árbol** de `pruebas` y se commitea directo en `pruebas` (el usuario lo reconfirmó el 24-09-2026, aunque f4 pidió una rama propia).

**Estado al 24-09-2026 (commit f2bf83a, paso 13):** el backend del bloque 8 está integrado en `pruebas` y el frontend ya va contra él. Tipos regenerados, `/apariciones`, línea del regalo y alcance del worker, probados contra la API real con el puerto falso. Pendiente: el PDF de ejemplo, sacado de una copia de `novela_10cap_opus55.db` (con la API de backup de SQLite) cuando termine; la inspección con el browser MCP (hay que reabrir Claude Code); el vídeo del cambio del lector con Claude real.

**Why:** entrega del examen. El autor quiere que la lectura y la demo del cambio del lector vivan en la web.

**How to apply:** tocar `src/frontend/`, `specs/spec-frontend*.md` y ahora también el bloque 7 de `specs/storymaker-plan.md`. Los contratos con el backend están cerrados; no se escribe a otras sesiones (ver [[no-comunicarse-con-otros-chats]]). Los tipos salen de `src/backend/tests/openapi.json`, y los huecos van a ficheros de deuda (RF-FE-API-04).

Ver [[huecos-de-diseno-con-criterio-propio]] y [[worker-vivo-del-usuario]].
