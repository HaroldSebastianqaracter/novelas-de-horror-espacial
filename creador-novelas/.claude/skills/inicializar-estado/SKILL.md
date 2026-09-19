---
name: inicializar-estado
description: Fase 4 (RF-04.1, RF-04.2, RF-04.3). Crea personajes.json, mundo.json y continuidad.json a partir del outline y la sinopsis.
allowed-tools: Read, Write, Bash(.venv/Scripts/python.exe -m app:*)
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
   Write en `.tanda/borradores/personajes.json` → `.venv/Scripts/python.exe -m app guardar personajes --desde .tanda/borradores/personajes.json`
2. **mundo.json** (RF-04.2): `{ "reglas": [...], "objetos": [...], "linea_de_tiempo": [...], "locaciones": { "<nombre canónico>": "descripción" } }`. Toda `locacion` del outline debe ser clave de `locaciones`, con la misma grafía.
   Write en `.tanda/borradores/mundo.json` → `guardar mundo --desde ...`
3. **continuidad.json** (RF-04.3): array de hechos iniciales derivados de la premisa, que ya son verdad antes del capítulo 1 (cómo funciona el soporte vital, qué hay afuera, qué se sabe y qué no). Cada uno: `{ "sujeto": "mundo" | <personaje> | <locación>, "categoria": "mundo" | "personaje" | "locacion", "hecho": "...", "cap_origen": 0 }`. `cap_origen = 0` identifica los hechos previos al capítulo 1. Los de categoría `mundo` se inyectan siempre al escritor: poné ahí solo lo que debe condicionar cada capítulo. Puede ser `[]`.
   **Un hecho inicial no niega la existencia de nada ni dice que algo no pasa nunca.** Es lo que
   más novelas ha parado: la fase 4 anota «entre la bodega y la sala de máquinas no hay ningún
   pasillo de servicio» o «el pasajero nunca pregunta nada», y el capítulo del giro tiene que
   desmentirlo, porque el susto *es* que aparezca el pasillo. QA lo marca como contradicción, con
   razón, y la novela para a mitad. Anotá lo que un registro recoge, lo que alguien sabe o lo que
   se ha medido, no lo que el mundo es: «los planos de a bordo no recogen ningún pasillo entre la
   bodega y la sala de máquinas» es cierto para siempre y no le cierra la puerta a ningún capítulo.
   Antes de escribir un hecho, mirá el outline: si algún capítulo lo desmiente, está mal escrito.
   `guardar continuidad` rechaza los que detecta.
   **Un personaje no puede estar en dos sitios a la vez.** Si un hecho sitúa a alguien en una
   locación y el capítulo en el que aparece transcurre en otra, el escritor tiene que inventarse el
   viaje, y con 400 palabras lo cuenta a saltos y se contradice. Pasó con «tiene asignada la guardia
   del puente» y un capítulo 1 que ocurría en el pasillo del nivel dos. Narrá el paso dentro del
   hecho («y baja al nivel dos al oír la alarma») o dejá al personaje donde el capítulo lo necesita.
   `guardar continuidad` también rechaza esto.
   Write en `.tanda/borradores/continuidad.json` → `guardar continuidad --desde ...`
4. Si algún `guardar` falla, corregí exactamente lo que dice y repetí ese paso.

Retorno: una línea con los tres archivos escritos y sus conteos (fichas, locaciones, hechos).
