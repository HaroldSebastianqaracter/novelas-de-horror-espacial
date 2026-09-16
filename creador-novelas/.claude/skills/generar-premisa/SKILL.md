---
name: generar-premisa
description: Fase 1 (RF-01.1). A partir de 01_concepto/idea.md produce 01_concepto/premisa.md con título, logline y premisa.
allowed-tools: Read, Write, Bash(.venv/Scripts/python.exe -m harness:*)
disable-model-invocation: true
---

Idea del usuario:
!`cat 01_concepto/idea.md 2>/dev/null || echo "(no existe 01_concepto/idea.md)"`

Configuración de la novela:
!`cat config/novela.json`

# Fase 1: concepto

Condición de entrada: `01_concepto/idea.md` existe y no está vacío. Si falta, pedile la idea al usuario (o que la escriba con `python -m harness ui`) y detenete.

Pasos:
1. Escribí, en el idioma configurado, un documento con exactamente estos tres campos, ninguno vacío:
   ```
   Título: <título de la novela>
   Logline: <una oración>
   Premisa: <un párrafo>
   ```
   Es terror espacial: el escenario es una nave, estación o colonia aislada y la amenaza viene del vacío o de lo desconocido.
2. Guardá el borrador con Write en `.tanda/borradores/premisa.md` y persistilo con
   `.venv/Scripts/python.exe -m harness guardar premisa --desde .tanda/borradores/premisa.md`
3. Si `guardar` falla, corregí lo que indique y repetí.

Retorno: una línea con la ruta escrita y el título. Nada más.
