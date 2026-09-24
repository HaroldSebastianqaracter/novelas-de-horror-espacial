---
name: novela-10cap-final
description: La novela de 10 capítulos de la entrega (24-09-2026) y sus copias; el original y los respaldos no se tocan nunca
metadata:
  node_type: memory
  type: project
  originSessionId: 2175183d-e372-4e0c-8322-620c27cab89c
  modified: 2026-09-24T17:46:41.180Z
---

La novela de 10 capítulos de la entrega terminó el 24-09-2026 a las 19:44 (completada_con_avisos, 41,47 $, 97 llamadas, Opus 5.5, brief de ejemplo). El autor pidió guardarla «con tu alma».

- Original: `novelasv2/src/backend/novela_10cap_seudo.db`. No se escribe nunca en ella: solo lectura o copia con la API de backup.
- Respaldos de solo lectura, verificados con integrity_check (sha256 fc056bcb4807d585…): `novelasv2/src/backend/novela_10cap_final.db` y `Nueva carpeta/RESPALDO_NOVELA_10CAP/novela_10cap_final.db`.
- Copias de trabajo: `novela_10cap_pdf.db` (para a1: PDF y vídeo) y `novela_10cap_lean.db` (para 1d: Lean).
- Avisos de la puerta 5: 5 elementos «ausentes», que son falsos porque los capítulos 1-4 se generaron antes de la migración 013; 20 siembras sin pagar, pendientes de revisar; los 10 capítulos pasan de 1.500 palabras (1.510-1.930).

**Why:** es la evidencia de la entrega (/ejemplos/novela-ejemplo.pdf, el vídeo, la tabla de evals, Lean y la revisión humana), y repetirla cuesta unos 40 $ y 4 horas.
**How to apply:** toda prueba, cambio del lector o regeneración sobre esta novela se hace en una copia nueva hecha con backup. Relacionado: [[objetivo-novela-con-menos-fallos]].
