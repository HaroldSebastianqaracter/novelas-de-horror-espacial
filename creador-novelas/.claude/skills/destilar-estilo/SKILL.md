---
name: destilar-estilo
description: Fase 0 (RF-00.1, RF-00.2). Produce 04_estado/style_guide.md a partir de los ejemplos de terror espacial de 00_referencias/. Corre en fork para que los textos de referencia no queden en el contexto del orquestador.
context: fork
allowed-tools: Read, Glob, Write, Bash(.venv/Scripts/python.exe -m harness:*)
disable-model-invocation: true
---

Estado actual:
!`.venv/Scripts/python.exe -m harness status`

Referencias disponibles:
!`ls -1 00_referencias 2>/dev/null || echo "(00_referencias/ vacía)"`

# Fase 0: destilado de estilo

Condición de entrada: `00_referencias/` tiene al menos un texto `.md` o `.txt` de **terror espacial** (naves, estaciones, colonias aisladas). Si está vacía, detenete y decíselo al usuario: la fase no se ejecuta sin ejemplos, salvo que él autorice una excepción documentada.

Pasos:
1. Leé cada archivo de `00_referencias/` con Read.
2. Redactá la guía de estilo del subgénero, en el idioma de `config/novela.json`, con estas secciones: tropos recurrentes (aislamiento, fallas de soporte vital, presencias que se confunden con la nave), **ritmo de tensión/alivio con un vocabulario explícito para los niveles 1 a 5** (lo usa el escritor para interpretar `tension`), vocabulario sensorial, longitud y cadencia de frase típica, qué evitar.
3. Prohibido copiar oraciones de los ejemplos: describí el estilo, no lo cites. `guardar` rechaza cualquier tramo de 30+ caracteres que coincida con las referencias.
4. Escribí el borrador con Write en `.tanda/borradores/style_guide.md` y persistilo con:
   `.venv/Scripts/python.exe -m harness guardar style_guide --desde .tanda/borradores/style_guide.md`
5. Si `guardar` falla, corregí exactamente lo que dice el error y repetí el paso 4.

Retorno al orquestador: una línea con la ruta escrita y la cantidad de secciones. Sin reproducir la guía ni los ejemplos.
