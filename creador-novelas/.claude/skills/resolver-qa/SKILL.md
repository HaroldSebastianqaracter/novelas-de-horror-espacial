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

**No termines hasta que `reextraccion_pendiente` esté vacío.** Rehacer el capítulo es la mitad del trabajo: si paras ahí, la resolución se queda abierta, `resolver --cerrar` se niega con «quedan capítulos por reextraer» y la novela se detiene igual que si no hubieras hecho nada. Los cinco pasos, para cada capítulo K de la lista, en orden (el CLI mantiene `capitulo_activo = K` para que H-05 deje leerlo):

1. `.venv/Scripts/python.exe -m app preparar-correccion K` → `RESULTADO: correccion_lista prompt=04_estado/prompts/escritor_cap_K.md`. Leélo con Read.
2. `Agent(subagent_type="escritor", prompt=<contenido>)`. Reescribe `05_manuscrito/cap_K.md` con el hallazgo de la revisión delante y lo valida él mismo (`validar-capitulo K`, RF-08.4). Guardá su línea; si dice `NO VALIDADO`, detenete y reportalo. **No llames a `registrar-escritor`**: ese verbo cierra un capítulo nuevo y K ya está cerrado, así que el capítulo parecería rechazado y acabarías en `descartar-borrador`, que INV-07 prohíbe sobre un capítulo cerrado. Aquí no se cierra nada, solo se reemplaza el texto.
3. Mirá `delta_del_escritor` en la línea `RESULTADO: correccion_lista` del paso 1.
   **Si es `true`, no invoques al extractor**: el escritor ya reescribió también
   `04_estado/deltas/delta_cap_K.json` junto al capítulo. Saltá al paso 5 y aplicalo sin
   `--retorno`, porque no hay línea de extractor que pasar. Si es `false`, seguí aquí:
   `.venv/Scripts/python.exe -m app preparar-extractor K` → `RESULTADO: extractor_listo prompt=04_estado/prompts/extractor_cap_K.md`. Leélo con Read.
4. `Agent(subagent_type="extractor", prompt=<contenido>)`. Escribe `04_estado/deltas/delta_cap_K.json`, lo valida (`validar-delta K`) y devuelve `delta_cap_K.json · N hechos · P personajes · validado`. El JSON no pasa por vos. Guardá su línea.
5. `.venv/Scripts/python.exe -m app aplicar-delta K --reextraccion --retorno "<línea del extractor>"`
   - `RESULTADO: reextraido pendientes=[...]` → si quedan, volvé al paso 1 con el siguiente; si está vacío, terminaste.
   - `RESULTADO: regenerar_capitulo` → el texto corregido introduce un personaje fuera del registro: detenete y reportalo.
   - `ERROR ContratoRetornoError` → reenviá al extractor el error textual una vez pidiendo solo la línea; si repite, detenete.
   - `ERROR AutovalidacionFallidaError` o `ERROR EstadoInvalidoError` → reenviá al extractor el error textual para que corrija y vuelva a validar, hasta 3 invocaciones; luego detenete.

Antes de dar por terminado, comprobá con `.venv/Scripts/python.exe -m app status` que `reextraccion_pendiente` está vacío. El cierre (`resolver --cerrar`) lo hace quien te invocó, no vos.

Retorno: capítulos reextraídos, hechos agregados por capítulo y los mensajes finales textuales del extractor.
