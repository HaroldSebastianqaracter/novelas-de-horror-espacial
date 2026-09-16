---
name: escribir-tanda
description: Fases 5-7 (spec técnica §6). Escribe capítulos en tanda invocando a escritor, extractor y qa como subagentes, avanzando el loop tramo a tramo con los verbos internos del CLI (§8.2). Uso: /escribir-tanda [N | --hasta-el-final].
argument-hint: "[N | --hasta-el-final]"
allowed-tools: Read, Write, Agent, Bash(.venv/Scripts/python.exe -m harness:*)
disable-model-invocation: true
---

Estado antes de empezar:
!`.venv/Scripts/python.exe -m harness status`

# /escribir-tanda $ARGUMENTS

Sos el orquestador. No escribís prosa, no leés `05_manuscrito/`, no editás estado a mano (INV-08). Cada decisión la toma el CLI: vos ejecutás verbos, invocás subagentes y copiás retornos. Leé la línea `RESULTADO:` de cada verbo y seguí la tabla. Si un verbo devuelve `ERROR`, detenete y mostrale al usuario el error textual.

## 0. Iniciar
- Sin argumento: `.venv/Scripts/python.exe -m harness tanda iniciar`
- Con número N: `... tanda iniciar --capitulos N` (pisa el archivo, RF-CFG-03)
- Con `--hasta-el-final`: `... tanda iniciar --hasta-el-final`
`RESULTADO: seguir siguiente=N` → ir a 1 con ese N. Cualquier otro motivo (`completo`, `tope_de_tanda`...) → reportarlo y terminar. Si el verbo falla por pausa de QA o EX-06, reportarlo y terminar.

## 1. Preparar el capítulo N
`.venv/Scripts/python.exe -m harness preparar-capitulo N` (con `--feedback "<texto>"` solo en el reintento de EX-07).
`RESULTADO: contexto_listo prompt=04_estado/prompts/escritor_cap_N.md` → leé ese archivo con Read (es estado ensamblado, no manuscrito) y pasá su contenido **completo y sin modificar** como prompt al subagente.

## 2. Invocar al escritor
`Agent(subagent_type="escritor", prompt=<contenido de escritor_cap_N.md>)`. No agregues rutas ni instrucciones propias.
Guardá textualmente su mensaje final y validalo:
`.venv/Scripts/python.exe -m harness registrar-escritor N "<mensaje final>"`
- `RESULTADO: borrador_aceptado` → ir a 3.
- `RESULTADO: reintentar_longitud feedback="..."` → volver a 1 con `--feedback` y ese texto (único reintento, EX-07).
- `ERROR ContratoRetornoError` → reenviá al mismo escritor, una sola vez, el error textual pidiendo solo la línea de retorno; si repite, detenete y reportá.

## 3. Invocar al extractor
`preparar-capitulo` ya dejó su prompt en `04_estado/prompts/extractor_cap_N.md` (si hace falta regenerarlo: `.venv/Scripts/python.exe -m harness preparar-extractor N`). Leé ese archivo con Read y pasalo completo: `Agent(subagent_type="extractor", prompt=<contenido>)`. No le pases el texto del capítulo: él lo lee con Read (única ruta permitida por H-05).
Guardá su mensaje final (solo JSON) con Write en `04_estado/deltas/delta_cap_N.json` (H-02 lo valida al escribirse) y aplicalo:
`.venv/Scripts/python.exe -m harness aplicar-delta N`
- `RESULTADO: capitulo_cerrado toca_qa=false` → ir a 5.
- `RESULTADO: capitulo_cerrado toca_qa=true` → ir a 4.
- `RESULTADO: regenerar_capitulo` (EX-08, primer fallo) → `... descartar-borrador N` y volver a 1 sin feedback.
- `ERROR EstadoInvalidoError` (JSON inválido, sujeto mal formado, tope de hechos) → reenviá al extractor el error textual y pedile el JSON corregido; hasta 3 intentos en total (§3.4); luego detenete y reportá EX-01.
- `ERROR PersonajeNoPrevistoError` → detenete y reportá EX-08: la entrada de outline es sospechosa.

## 4. Corte de QA (N múltiplo de cadencia_qa)
`.venv/Scripts/python.exe -m harness preparar-qa N` → `RESULTADO: qa_listo prompt=04_estado/prompts/qa_cap_N.md`. Leé ese prompt y `Agent(subagent_type="qa", prompt=<contenido>)`. Guardá su mensaje final (hasta cinco líneas). Después:
`.venv/Scripts/python.exe -m harness cerrar-qa N`
- `RESULTADO: qa_sin_contradicciones` → ir a 5.
- `RESULTADO: pausado_por_qa reporte=qa_cap_N` → **detenete**. Mostrale al usuario la ruta `06_qa/reportes/qa_cap_N.md` y que la tanda queda pausada hasta `resolver`. No intentes resolverlo.
- `ERROR` (QA no escribió el JSON o recursos_usados.json) → reenviá a QA el error textual una vez; si repite, detenete y reportá.

## 5. Siguiente
`.venv/Scripts/python.exe -m harness tanda siguiente`
- `RESULTADO: seguir siguiente=M` → volver a 1 con M.
- `RESULTADO: tope_de_tanda | tope_de_llamadas | novela_completa` → terminar y reportar.

## Al terminar (por cualquier motivo)
Reportá al usuario: motivo de salida, capítulos cerrados en esta tanda, el mensaje final textual de cada subagente por invocación, cada bloqueo de hook que hayas visto (id, agente, acción) y los avisos EX-07/EX-08. Sugerí `python -m harness ensamblar --salida <archivo>` para leer lo escrito. Nunca pegues prosa del manuscrito.
