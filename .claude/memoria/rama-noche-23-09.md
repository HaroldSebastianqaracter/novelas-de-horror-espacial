---
name: rama-noche-23-09
description: "Rama noche-23-09 (worktree ../novelasv2-noche) con el trabajo nocturno del 23-24/09, integrada el 24-09 en pruebas y novelasv2; resumen en docs/proceso/noche-23-09.md"
metadata:
  node_type: memory
  type: project
  originSessionId: 2175183d-e372-4e0c-8322-620c27cab89c
  modified: 2026-09-23T22:02:25.264Z
---

La noche del 23 al 24 de septiembre de 2026 se trabajó sin el autor en la rama `noche-23-09` (worktree `../novelasv2-noche`, sale de `pruebas` en 134e453). Contenido: banco de contraejemplos, ficha del redactor, juez de cuentas (`cuentas_cuadran`), validadores de la prosa (nombres, allegados, longitud), guardrails (migración 010), segunda opinión en la parada y voto del juez con k=3. Todo está validado y medido en parte con Claude real sobre una copia de novela_real.db (unos 5,90 $).

**Why:** el autor pidió trabajo autónomo nocturno con el objetivo [[objetivo-novela-con-menos-fallos]] y sin integrar nada en pruebas.

**How to apply:** el 24-09 el autor pidió integrarla: `pruebas` y `novelasv2` avanzaron por fast-forward a e6d9bd2 (606 tests verdes), sin push. La migración 010 es la de guardrails; la siguiente será la 011. RF3-PAS-11 (muerte y ubicuidad leyendo presencias) se revirtió porque revocaba una decisión entrevistada: no reintroducirlo sin el autor. El resumen está en docs/proceso/noche-23-09.md.
