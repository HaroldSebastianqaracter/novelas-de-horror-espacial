---
name: corte-qa
description: Fase 7 (RF-07.1 a RF-07.5) fuera de cadencia, sobre el último capítulo cerrado. Invoca al subagente qa y cierra el corte con el CLI.
allowed-tools: Read, Write, Agent, Bash(.venv/Scripts/python.exe -m app:*)
disable-model-invocation: true
---

Estado:
!`.venv/Scripts/python.exe -m app status`

# /corte-qa

Condición de entrada: hay al menos un capítulo cerrado y el manifiesto está en `en_progreso`. Si está `pausado_por_qa`, no hay nada que cortar: el usuario debe resolver primero.

Pasos (N = `ultimo_capitulo_cerrado`):
1. `.venv/Scripts/python.exe -m app preparar-qa N` → `RESULTADO: qa_listo prompt=04_estado/prompts/qa_cap_N.md`.
2. Leé ese prompt con Read y pasalo completo: `Agent(subagent_type="qa", prompt=<contenido>)`. QA escribe sus tres archivos, los valida con `validar-reporte N` (RF-08.4) y devuelve hasta cinco líneas que incluyen `validado`. Guardá su mensaje final.
3. `.venv/Scripts/python.exe -m app cerrar-qa N --retorno "<mensaje final de QA>"` (el harness vuelve a validar los archivos).
   - `RESULTADO: qa_sin_contradicciones` → reportá los conteos.
   - `RESULTADO: pausado_por_qa` → detenete y mostrale al usuario `06_qa/reportes/qa_cap_N.md`; la tanda queda pausada hasta `resolver`.
   - `ERROR` (contrato de retorno, EX-10 o archivos que no validan) → reenviá a QA el error textual una vez; si repite, detenete y reportá.

Retorno: motivo, conteos por tipo, ruta del reporte y el mensaje final textual de QA. Sin citar el manuscrito.
