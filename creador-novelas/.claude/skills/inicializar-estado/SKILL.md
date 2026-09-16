---
name: inicializar-estado
description: Fase 4 (RF-04.1, RF-04.2, RF-04.3). Crea personajes.json, mundo.json y continuidad.json a partir del outline y la sinopsis.
allowed-tools: Read, Write, Bash(.venv/Scripts/python.exe -m harness:*)
disable-model-invocation: true
---

Outline:
!`cat 04_estado/capitulos.json 2>/dev/null || echo "(falta capitulos.json: corré /generar-escaleta)"`

Sinopsis:
!`cat 04_estado/tres_actos.md 2>/dev/null || echo "(falta tres_actos.md)"`

# Fase 4: bases de estado

Condición de entrada: `capitulos.json` y `tres_actos.md` existen y el manifiesto tiene `ultimo_capitulo_cerrado = 0`.

Pasos, en este orden (cada `guardar` valida contra la anterior):
1. **personajes.json** (RF-04.1): un objeto `{ "<nombre canónico>": { "estado_fisico", "estado_psicologico", "secretos_que_conoce": [], "ultima_aparicion": 0 } }` con una ficha por cada nombre que aparezca en `personajes` del outline, con la misma grafía. `ultima_aparicion = 0` significa que todavía no apareció. Estados iniciales al comienzo de la novela.
   Write en `.tanda/borradores/personajes.json` → `.venv/Scripts/python.exe -m harness guardar personajes --desde .tanda/borradores/personajes.json`
2. **mundo.json** (RF-04.2): `{ "reglas": [...], "objetos": [...], "linea_de_tiempo": [...], "locaciones": { "<nombre canónico>": "descripción" } }`. Toda `locacion` del outline debe ser clave de `locaciones`, con la misma grafía.
   Write en `.tanda/borradores/mundo.json` → `guardar mundo --desde ...`
3. **continuidad.json** (RF-04.3): array de hechos iniciales derivados de la premisa, que ya son verdad antes del capítulo 1 (cómo funciona el soporte vital, qué hay afuera, qué se sabe y qué no). Cada uno: `{ "sujeto": "mundo" | <personaje> | <locación>, "categoria": "mundo" | "personaje" | "locacion", "hecho": "...", "cap_origen": 0 }`. `cap_origen = 0` identifica los hechos previos al capítulo 1. Los de categoría `mundo` se inyectan siempre al escritor: poné ahí solo lo que debe condicionar cada capítulo. Puede ser `[]`.
   Write en `.tanda/borradores/continuidad.json` → `guardar continuidad --desde ...`
4. Si algún `guardar` falla, corregí exactamente lo que dice y repetí ese paso.

Retorno: una línea con los tres archivos escritos y sus conteos (fichas, locaciones, hechos).
