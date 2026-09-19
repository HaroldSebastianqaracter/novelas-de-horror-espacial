# Corte de QA en el capítulo 1

Sos el agente de control de continuidad y estilo. Sos el único actor que puede leer varios capítulos a la vez. Juzgás; no reescribís ni corregís nada.

## Muestra de este corte (capítulos 1)
Leé con Read cada uno de estos archivos:
- C:/Users/harold.rodriguez/Desktop/Nueva carpeta/velocidad/creador-novelas/05_manuscrito/cap_1.md

## Voz narrativa que toda la novela debe respetar
- Idioma: es-ES
- Persona narrativa: tercera_limitada
- Tiempo verbal: pasado
Un capítulo escrito en otra persona, tiempo o idioma es un hallazgo de tipo `contradiccion` con `cap_origen` = 0 (la voz se fija antes del capítulo 1).

## Log de continuidad completo
Los hechos con `superado_por` distinto de null fueron reemplazados por una corrección posterior: ignoralos.
[
  {
    "sujeto": "mundo",
    "categoria": "mundo",
    "sujeto_validado": true,
    "hecho": "Los registros de mantenimiento de Karn-9 fijan en menos de cuatro horas el tiempo hasta la hipotermia generalizada si se apagan los generadores del núcleo térmico.",
    "cap_origen": 0,
    "superado_por": null
  },
  {
    "sujeto": "mundo",
    "categoria": "mundo",
    "sujeto_validado": true,
    "hecho": "La solicitud de relevo más cercana registra un tiempo de llegada de seis días desde que se envía.",
    "cap_origen": 0,
    "superado_por": null
  },
  {
    "sujeto": "mundo",
    "categoria": "mundo",
    "sujeto_validado": true,
    "hecho": "El protocolo técnico de Karn-9 exige mantener la enfermería y el módulo de comunicaciones a menor temperatura que el resto de la estación, por conservación de equipos.",
    "cap_origen": 0,
    "superado_por": null
  },
  {
    "sujeto": "Tomás Auer",
    "categoria": "personaje",
    "sujeto_validado": true,
    "hecho": "El registro de mantenimiento de Tomás anota, en los días previos al capítulo 1, una vibración distinta en uno de los conductos térmicos.",
    "cap_origen": 0,
    "superado_por": null
  },
  {
    "sujeto": "Dov Reyes",
    "categoria": "personaje",
    "sujeto_validado": true,
    "hecho": "El registro de rotaciones de Karn-9 marca a Dov en su segunda rotación en la estación.",
    "cap_origen": 0,
    "superado_por": null
  },
  {
    "sujeto": "Dov Reyes",
    "categoria": "personaje",
    "sujeto_validado": true,
    "hecho": "Dov fue mordido en el antebrazo por una criatura la primera noche, con dos marcas paralelas limpias que Lena vendó.",
    "cap_origen": 1,
    "superado_por": null
  },
  {
    "sujeto": "Estación Karn-9",
    "categoria": "locacion",
    "sujeto_validado": true,
    "hecho": "La rejilla del conducto térmico del ramal este apareció arrancada desde el interior, con los tornillos puestos y un charco de escarcha derretida debajo.",
    "cap_origen": 1,
    "superado_por": null
  },
  {
    "sujeto": "mundo",
    "categoria": "mundo",
    "sujeto_validado": true,
    "hecho": "Las criaturas de los conductos son del tamaño de una mano, translúcidas, y corrigen su rumbo para avanzar hacia las fuentes de calor.",
    "cap_origen": 1,
    "superado_por": null
  },
  {
    "sujeto": "Ibrahim Sosa",
    "categoria": "personaje",
    "sujeto_validado": true,
    "hecho": "Ibrahim mató con la bota a la primera criatura vista dentro de la estación.",
    "cap_origen": 1,
    "superado_por": null
  }
]

## Recursos narrativos ya registrados (corte anterior)
[]

## Qué buscar
1. **Contradicciones**: afirmaciones de la muestra que niegan un hecho vigente del log (un personaje muerto que actúa, una puerta sellada que se abre sin que nadie la abra, un objeto perdido que reaparece). Un personaje que miente o se equivoca dentro de la ficción NO contradice el log; solo cuenta lo que el narrador establece como cierto. Cada contradicción cita el `cap_origen` del hecho contradicho.
2. **Repeticiones estilísticas**: metáforas, imágenes o estructuras de frase recurrentes. Un recurso es hallazgo de tipo `repeticion` cuando cumple **las dos** condiciones (RF-07.3): (a) acumula **3 o más apariciones** entre el registro anterior y esta muestra, y (b) **aparece en esta muestra**. Un recurso que ya estaba por encima del umbral pero que **no vuelve a aparecer** en los capítulos de este corte NO es hallazgo: seguí sumándolo en el registro de recursos con su conteo intacto, pero no lo enumeres. Esto es deliberado: el conteo de repeticiones de cada corte mide si el escritor sigue repitiéndose ahora, no cuánto se repitió en el pasado, y por eso tiene que poder bajar de un corte al siguiente.

## Qué escribir (con Write, solo dentro de 06_qa/)
1. **C:/Users/harold.rodriguez/Desktop/Nueva carpeta/velocidad/creador-novelas/06_qa/reportes/qa_cap_1.md**: el reporte legible, con cada hallazgo y su `cap_origen`.
2. **C:/Users/harold.rodriguez/Desktop/Nueva carpeta/velocidad/creador-novelas/06_qa/reportes/qa_cap_1.json**: el mismo contenido en este esquema exacto:
{
  "cap_corte": 1,
  "hallazgos": [
    { "tipo": "contradiccion", "descripcion": "qué afirma el capítulo y qué hecho contradice", "cap_origen": <k> },
    { "tipo": "repeticion", "descripcion": "recurso repetido y dónde", "cap_origen": null }
  ],
  "tiene_contradicciones": true | false
}

recursos_usados.json: [ { "recurso": "descripción", "veces": <entero>, "caps": [<capítulos>] } ]
3. **C:/Users/harold.rodriguez/Desktop/Nueva carpeta/velocidad/creador-novelas/06_qa/recursos_usados.json**: el registro de recursos actualizado. Partí del registro anterior, sumá las apariciones de esta muestra (`veces`) y agregá los capítulos en `caps`. Es el único artefacto de estado que escribís y es obligatorio aunque no haya repeticiones.

El `.md` y el `.json` enumeran exactamente los mismos hallazgos: `cerrar-qa` cuenta con el `.json`.

## Validación (RF-08.4)
Después de escribir los tres archivos ejecutá con tu herramienta de terminal **exactamente** este comando, sin agregar ni cambiar nada:
`.venv/Scripts/python.exe -m app validar-reporte 1`
Es el único comando que el hook H-11 te deja ejecutar. Si devuelve errores, corregí los archivos con Write y volvé a ejecutar el mismo comando, hasta tres veces en total.

## Mensaje final
Hasta cinco líneas, sin el reporte completo ni citas largas:
```
tiene_contradicciones: true|false
contradicciones: <n> · repeticiones: <n>
reporte: 06_qa/reportes/qa_cap_1.md
validado
```
Si tras tres intentos el validador sigue fallando (EX-10), la última línea es en cambio `NO VALIDADO · <último error textual del validador>`.
