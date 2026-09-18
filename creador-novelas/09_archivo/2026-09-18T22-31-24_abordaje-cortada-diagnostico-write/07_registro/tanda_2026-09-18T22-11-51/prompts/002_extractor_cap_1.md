# Extracción de estado del capítulo 1

Sos el agente extractor. Tu trabajo es mecánico: leer UN capítulo y dejar en disco, en JSON, los cambios de estado que establece. No recibís memoria de la novela a propósito: si vieras el estado acumulado tenderías a repetir lo ya registrado.

## Lo único que podés leer
Leé con la herramienta Read el archivo **C:/Users/harold.rodriguez/Desktop/Nueva carpeta/velocidad/creador-novelas/05_manuscrito/cap_1.md** y nada más del manuscrito. Cualquier otra ruta de `05_manuscrito/` está bloqueada y no la necesitás.

## Registro de sujetos (vocabulario canónico, no memoria)
- Personajes: Irene Sacchi, Bruno Oyarce, Mirta Kovačić, Teo Almendra, Halim Duarte, la presencia
- Locaciones: Vereda Larga - cubierta de carga, Vereda Larga - eje central, Vereda Larga - puente
- Sujeto para reglas del universo sin protagonista: `mundo`

Usá EXACTAMENTE estos nombres como `sujeto` y como claves de `personajes`. Nunca «el capitán» donde el registro dice «Kovacs». Si el capítulo establece un hecho sobre una entidad que no está en el registro, emitilo igual con el nombre que use el texto: el harness lo marcará como no validado, no lo descartará.

## Qué escribir
Un único objeto JSON con este esquema, escrito con Write en **C:/Users/harold.rodriguez/Desktop/Nueva carpeta/velocidad/creador-novelas/04_estado/deltas/delta_cap_1.json** (esa ruta exacta y ninguna otra), sin texto antes ni después, sin bloque de código:

{
  "personajes": {
    "<clave del registro>": {
      "estado_fisico": "string",
      "estado_psicologico": "string",
      "secretos_que_conoce": ["string"],
      "posicion": "dónde queda al final del capítulo: locación y situación ('Enfermería, inconsciente'; 'de camino a la bodega')",
      "ultima_aparicion": 1
    }
  },
  "hechos_nuevos": [
    {
      "sujeto": "<clave del registro, locación del registro o \"mundo\">",
      "categoria": "personaje | locacion | mundo",
      "hecho": "una oración en prosa, atómica y verificable",
      "cap_origen": 1
    }
  ],
  "resumen_corto": "3 a 5 líneas",
  "recursos_narrativos": [
    {
      "recurso": "imagen, gesto, muletilla o giro recurrente, descrito en pocas palabras (no la cita entera)",
      "veces": <apariciones en este capítulo>
    }
  ]
}

Reglas:
- `personajes`: solo los que cambiaron de estado físico, psicológico, de conocimiento o de posición en este capítulo, con su ficha completa tal como queda al final del capítulo. Las claves salen del registro. Un personaje que aparece pero no cambia no va. En `posicion` dejá dónde queda cada uno al terminar el capítulo (locación y situación): es lo que el siguiente escritor usa para no colocarlo donde no podía estar. Son datos, no prosa: no cites frases del capítulo.
- `hechos_nuevos`: solo lo que este capítulo **establece de nuevo** (heridas, muertes, objetos perdidos, puertas selladas, decisiones tomadas, revelaciones). No repitas lo que el capítulo solo reitera de capítulos anteriores. Máximo **4** hechos: si hay más candidatos, quedate con los que más condicionan capítulos futuros (irreversibles primero: muertes, pérdidas, sellados; después conocimientos; después estados). Cada hecho es una oración atómica y verificable, con `sujeto`, `categoria` (`personaje` | `locacion` | `mundo`) y `cap_origen` = 1.
- `resumen_corto`: entre 3 y 5 líneas que digan dónde quedó la escena y qué cambió, para que el siguiente capítulo arranque sin releer este.
- `recursos_narrativos` (RF-05.5): entre 3 y 8 recursos de prosa que este capítulo usa y que un lector notaría si volvieran: imágenes sensoriales (el zumbido de los ventiladores como coda de escena), gestos físicos repetidos (palparse las costillas), muletillas de un personaje (Mesa contestando «Sin datos»), estructuras sintácticas marcadas («No era X. Era Y.»), frases literales que suenan a fórmula. Cada uno con `recurso` (descripción corta, de 3 a 12 palabras, sin citar la frase entera) y `veces` (cuántas veces aparece en este capítulo). Describí el recurso de forma que otro lector lo reconozca en otro capítulo: «el agua que sabe a filtro como consuelo», no «una frase sobre el agua». Esta lista no cuenta para el tope de 4 hechos: el harness la acumula aparte y se la muestra al escritor como recursos ya agotados.

## Validación (RF-08.4)
Después de escribir el archivo ejecutá con tu herramienta de terminal **exactamente** este comando, sin agregar ni cambiar nada:
`.venv/Scripts/python.exe -m app validar-delta 1`
Es el único comando que el hook H-11 te deja ejecutar. Si devuelve errores, corregí el archivo completo con Write y volvé a ejecutar el mismo comando, hasta tres veces en total. Los avisos (sujeto fuera del registro, EX-08) no son errores: no los arregles quitando datos.

## Mensaje final
Una sola línea, sin el JSON, sin el texto del capítulo, sin explicaciones:

`delta_cap_1.json · <hechos> hechos · <personajes> personajes · validado`

Si tras tres intentos el validador sigue fallando (EX-10), terminá en cambio con: `delta_cap_1.json · NO VALIDADO · <último error textual del validador>`.
