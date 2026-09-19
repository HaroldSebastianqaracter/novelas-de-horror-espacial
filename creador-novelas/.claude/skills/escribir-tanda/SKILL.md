---
name: escribir-tanda
description: Fases 5-7 (spec técnica §6). Escribe capítulos en tanda invocando a escritor, extractor y qa como subagentes, avanzando el loop tramo a tramo con los verbos internos del CLI (§8.2). Uso: /escribir-tanda [N | --hasta-el-final].
argument-hint: "[N | --hasta-el-final]"
allowed-tools: Read, Write, Edit, Agent, Bash(.venv/Scripts/python.exe -m app:*)
disable-model-invocation: true
---

Estado antes de empezar:
!`.venv/Scripts/python.exe -m app status`

# /escribir-tanda $ARGUMENTS

Sos el orquestador. No escribís prosa, no leés `05_manuscrito/`, no editás estado a mano (INV-08). Cada decisión la toma el CLI: vos ejecutás verbos, invocás subagentes y copiás retornos. Leé la línea `RESULTADO:` de cada verbo y seguí la tabla. Si un verbo devuelve `ERROR`, detenete y mostrale al usuario el error textual.

## 0. Iniciar
- Sin argumento: `.venv/Scripts/python.exe -m app tanda iniciar`
- Con número N: `... tanda iniciar --capitulos N` (pisa el archivo, RF-CFG-03)
- Con `--hasta-el-final`: `... tanda iniciar --hasta-el-final`
`RESULTADO: seguir siguiente=N` → ir a 1 con ese N. Cualquier otro motivo (`completo`, `tope_de_tanda`...) → reportarlo y terminar. Si el verbo falla por pausa de QA o EX-06, reportarlo y terminar.

## 1. Preparar el capítulo N
`.venv/Scripts/python.exe -m app preparar-capitulo N` (con `--feedback "<texto>"` solo en el reintento de EX-07).
`RESULTADO: contexto_listo prompt=04_estado/prompts/escritor_cap_N.md` → leé ese archivo con Read (es estado ensamblado, no manuscrito) y pasá su contenido **completo y sin modificar** como prompt al subagente.

## 2. Invocar al escritor
`Agent(subagent_type="escritor", prompt=<contenido de escritor_cap_N.md>)`. No agregues rutas ni instrucciones propias. El escritor escribe `cap_N.md`, corre su validador (`validar-capitulo N`, RF-08.4) y devuelve una línea que termina en `· validado`.
Guardá textualmente su mensaje final y validalo (el harness vuelve a validar el archivo, §8.2):
`.venv/Scripts/python.exe -m app registrar-escritor N "<mensaje final>"`
- `RESULTADO: borrador_aceptado` → ir a 3.
- `RESULTADO: reintentar_longitud feedback="..."` → volver a 1 con `--feedback` y ese texto (único reintento, EX-07).
- `ERROR ContratoRetornoError` → reenviá al mismo escritor, una sola vez, el error textual pidiendo solo la línea de retorno; si repite, detenete y reportá.
- `ERROR AutovalidacionFallidaError` (EX-10: el escritor agotó sus intentos) → `... descartar-borrador N` y volver a 1 con `--feedback "<detalle del error>"`, una sola vez; si repite, detenete y reportá EX-07/EX-08 con el error textual.
- `ERROR EstadoInvalidoError` (el borrador no valida por algo distinto de la longitud) → detenete y reportá el error textual.

## 3. El delta

Mirá `delta_del_escritor` en la línea `RESULTADO: contexto_listo` del paso anterior.

**`delta_del_escritor=true` (X-04): no invoques al extractor.** El escritor ya dejó
`04_estado/deltas/delta_cap_N.json` junto al capítulo y lo validó con el mismo comando. Aplicá
el delta directamente, sin `--retorno`, porque no hay línea de extractor que pasar:
`.venv/Scripts/python.exe -m app aplicar-delta N`
Si eso devuelve `ERROR` porque el delta no está o no vale, entonces sí despachá al extractor
como abajo: ese capítulo pierde la ventaja de velocidad, pero la novela sigue.

**`delta_del_escritor=false`: invocá al extractor.**
`preparar-capitulo` ya dejó su prompt en `04_estado/prompts/extractor_cap_N.md` (si hace falta regenerarlo: `.venv/Scripts/python.exe -m app preparar-extractor N`). Leé ese archivo con Read y pasalo completo: `Agent(subagent_type="extractor", prompt=<contenido>)`. No le pases el texto del capítulo: él lo lee con Read (única ruta permitida por H-05).
El extractor escribe él mismo `04_estado/deltas/delta_cap_N.json`, lo valida (`validar-delta N`, RF-08.4) y devuelve **una línea** `delta_cap_N.json · K hechos · P personajes · validado`. El JSON no pasa por vos: no lo pidas, no lo escribas. Guardá su línea y aplicá el delta (el harness vuelve a validar el archivo):
`.venv/Scripts/python.exe -m app aplicar-delta N --retorno "<línea del extractor>"`
- `RESULTADO: capitulo_cerrado toca_qa=false` → ir a 5.
- `RESULTADO: capitulo_cerrado toca_qa=true` → ir a 4.
- `RESULTADO: regenerar_capitulo` (EX-08, primer fallo) → `... descartar-borrador N` y volver a 1 sin feedback.
- `ERROR ContratoRetornoError` → reenviá al mismo extractor, una sola vez, el error textual pidiendo solo la línea de retorno; si repite, detenete y reportá.
- `ERROR AutovalidacionFallidaError` o `ERROR EstadoInvalidoError` (EX-10 / EX-01: el delta no valida) → reenviá al extractor el error textual y pedile que corrija el archivo y vuelva a validar; hasta 3 invocaciones en total (§3.4); luego detenete y reportá EX-01.
- `ERROR PersonajeNoPrevistoError` → detenete y reportá EX-08: la entrada de outline es sospechosa.

## 4. Corte de QA (N múltiplo de cadencia_qa), en paralelo con el capítulo siguiente

QA audita capítulos **ya cerrados**, así que no necesita nada del capítulo que viene: los dos pueden trabajar a la vez y ahí se ahorra el tiempo entero del corte. Se hace así, en este orden:

**a)** `.venv/Scripts/python.exe -m app preparar-qa N` → `RESULTADO: qa_listo prompt=04_estado/prompts/qa_cap_N.md`. Leé ese prompt con Read.

**b)** `.venv/Scripts/python.exe -m app tanda siguiente`
- `RESULTADO: seguir siguiente=M` → `... preparar-capitulo M` y leé `04_estado/prompts/escritor_cap_M.md`. Seguí en (c) con los dos prompts en la mano.
- Cualquier otro motivo (`tope_de_tanda`, `novela_completa`...) → no hay capítulo que solapar: invocá solo a QA, seguí en (d) y al terminar reportá ese motivo.

**c)** En **un solo mensaje**, invocá los dos subagentes a la vez, para que corran en paralelo:
`Agent(subagent_type="qa", prompt=<qa_cap_N.md>)` y `Agent(subagent_type="escritor", prompt=<escritor_cap_M.md>)`.
Cada uno escribe y valida lo suyo, y no se pisan: QA solo toca `06_qa/` y el escritor solo su `cap_M.md` (H-06).

**d)** Cerrá **primero el corte**, siempre, antes de tocar el capítulo M:
`.venv/Scripts/python.exe -m app cerrar-qa N --retorno "<mensaje final de QA>"`
- `RESULTADO: qa_sin_contradicciones` → recién ahora seguí con M: `... registrar-escritor M "<mensaje final del escritor>"`, y tratá lo que devuelva con **la misma tabla del paso 2** (reintento de longitud, contrato de retorno, EX-10...). Si acepta el borrador, seguí al **paso 3** con M.
- `RESULTADO: pausado_por_qa reporte=qa_cap_N` → `... descartar-borrador M` y **detenete**. El capítulo M se escribió mientras QA auditaba y no se cierra: se descarta. Mostrale al usuario la ruta `06_qa/reportes/qa_cap_N.md` y que la tanda queda pausada hasta `resolver`. No intentes resolverlo.
- `ERROR` (contrato de retorno, EX-10, o QA no escribió el JSON o recursos_usados.json) → reenviá a QA el error textual una vez; si repite, detenete y reportá.

**No cierres el capítulo M antes que el corte.** `aplicar-delta M` mueve `ultimo_capitulo_cerrado`, y de ahí sale el capítulo con el que los hooks resuelven a QA (§13.3): su `validar-reporte N` dejaría de casar con H-11 a media auditoría. El harness lo rechaza si lo intentás, pero el orden correcto es este.

## 5. Siguiente
`.venv/Scripts/python.exe -m app tanda siguiente`
- `RESULTADO: seguir siguiente=M` → volver a 1 con M.
- `RESULTADO: tope_de_tanda | tope_de_llamadas | novela_completa` → terminar y reportar.

## Al terminar (por cualquier motivo)
Reportá al usuario: motivo de salida, capítulos cerrados en esta tanda, el mensaje final textual de cada subagente por invocación, cada bloqueo de hook que hayas visto (id, agente, acción) y los avisos EX-07/EX-08. Sugerí `python -m app ensamblar --salida <archivo>` para leer lo escrito. Nunca pegues prosa del manuscrito.
