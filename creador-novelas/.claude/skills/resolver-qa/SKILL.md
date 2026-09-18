---
name: resolver-qa
description: RF-07.6 paso 2. Tras `resolver --reporte X --capitulos a,b`, hace que el escritor rehaga cada capítulo con el hallazgo de QA delante, lo reextrae y aplica cada delta con `aplicar-delta --reextraccion`. El cierre (paso 3) lo hace el usuario con `resolver --cerrar`.
allowed-tools: Read, Write, Agent, Bash(.venv/Scripts/python.exe -m app:*)
disable-model-invocation: true
---

Estado:
!`.venv/Scripts/python.exe -m app status`

# /resolver-qa

Condición de entrada: el manifiesto muestra `reextraccion_pendiente` no vacío (el usuario ya corrió `resolver --reporte qa_cap_N --capitulos a,b`). Si la lista está vacía, no hay nada que hacer: indicá `python -m app resolver --cerrar`.

Para cada capítulo K de la lista, en orden (el CLI mantiene `capitulo_activo = K` para que H-05 deje al extractor leerlo):

0. **Primero se corrige la prosa, y la corrige el escritor.** `.venv/Scripts/python.exe -m app preparar-correccion K` → `RESULTADO: correccion_lista prompt=04_estado/prompts/escritor_cap_K.md`. Leé ese archivo con Read y pasáselo a `Agent(subagent_type="escritor", prompt=<contenido>)`. El escritor reescribe `05_manuscrito/cap_K.md` con el hallazgo de la revisión delante y lo valida él mismo con `validar-capitulo K` (RF-08.4). Guardá su línea y pasá al paso 1.

   **No llames a `registrar-escritor`.** Ese verbo cierra un capítulo nuevo y K ya está cerrado: lo único que consigue es que el capítulo parezca rechazado y acabes intentando `descartar-borrador`, que INV-07 prohíbe sobre un capítulo cerrado. Aquí no se cierra nada: el capítulo sigue cerrado y solo se ha reemplazado su texto. La prueba de que el texto vale es la autovalidación del propio escritor.

   Si su línea dice `NO VALIDADO`, detenete y reportalo. Sin este paso el capítulo se reextrae con la contradicción dentro y no se arregla nada.
1. `.venv/Scripts/python.exe -m app preparar-extractor K` → `RESULTADO: extractor_listo prompt=04_estado/prompts/extractor_cap_K.md`. Leé ese archivo con Read.
2. `Agent(subagent_type="extractor", prompt=<contenido>)`. El extractor escribe él mismo `04_estado/deltas/delta_cap_K.json`, lo valida (`validar-delta K`, RF-08.4) y devuelve una línea `delta_cap_K.json · K hechos · P personajes · validado`. El JSON no pasa por vos. Guardá su línea.
3. `.venv/Scripts/python.exe -m app aplicar-delta K --reextraccion --retorno "<línea del extractor>"`
   - `RESULTADO: reextraido pendientes=[...]` → seguir con el próximo.
   - `RESULTADO: regenerar_capitulo` → el texto corregido introduce un personaje fuera del registro: detenete y reportalo; el usuario tiene que corregir el capítulo o el registro.
   - `ERROR ContratoRetornoError` → reenviá al extractor el error textual una vez pidiendo solo la línea; si repite, detenete.
   - `ERROR AutovalidacionFallidaError` o `ERROR EstadoInvalidoError` → reenviá al extractor el error textual para que corrija el archivo y vuelva a validar, hasta 3 invocaciones; luego detenete.
4. Cuando `pendientes=[]`, indicá al usuario que corra `python -m app resolver --cerrar`.

Retorno: capítulos reextraídos, hechos agregados por capítulo y los mensajes finales textuales del extractor.
