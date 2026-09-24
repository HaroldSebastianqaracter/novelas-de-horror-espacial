# Notas del orador — storyMaker (SpaceMaker)

Castellano, con los términos técnicos en inglés. Tiempo total de las 15 diapositivas principales: 10:00.

## 01 · Una novela en la que el protagonista eres tú

[0:00–0:20 · 20 s] Buenos días. Soy [TU NOMBRE], de SpaceMaker. Presento storyMaker a Faro Regalos: una novela de regalo en la que el protagonista es la persona que la recibe. En diez minutos verán el producto, el harness que lo sostiene, cómo lo validamos y lo que cuesta.

## 02 · Personalización y calidad narrativa, a la vez

[0:20–1:00 · 40 s] Nuestro comprador quiere regalar una novela a alguien concreto: un hijo, la pareja, una boda, un aniversario, un cumpleaños o una jubilación. Hoy tiene tres opciones y ninguna le sirve. El libro de plantilla solo cambia el nombre. Un escritor por encargo es caro y tarda semanas. Y un LLM a pelo pierde la continuidad a los pocos capítulos. Lo que falta es tener personalización y calidad narrativa a la vez, y eso es lo que resuelve storyMaker.

## 03 · Un brief que valida el código, no el modelo

[1:00–1:40 · 40 s] La configuración empieza con un agente entrevistador que recoge nombre, edad, rasgos, recuerdos, tono, intensidad y palabras prohibidas. Lo importante: los huecos y las contradicciones, por ejemplo una edad baja con intensidad alta, los detecta el código, no el modelo. La carta libre del comprador se trata como contenido no confiable, porque es la puerta de entrada de una inyección. El resultado es un brief validado con schema.

## 04 · El lector corrige desde la página

[1:40–2:20 · 40 s] La novela se lee en una web: portada y dedicatoria, índice, una ficha de personajes y lugares que sale directamente de la story bible, y exportación a PDF. Y el lector puede corregir desde la propia página. Si escribe «la bahía huele a ozono», solo se regeneran los capítulos afectados, se marcan como cambiados y la versión anterior se conserva. [Señalar las capturas: portada e índice con la marca «cambió en la versión 2».]

## 05 · El harness: un bucle con seis puertas

[2:20–3:20 · 60 s] Este es el corazón: el harness. Del brief pasa al planner, que hace de arquitecto, mundo, elenco y estructura. Puerta 1. Luego la escaleta y la puerta 2. Entonces entra el bucle por capítulo: el writer escribe, el extractor vuelca los hechos a la story bible en SQLite, la puerta 3 comprueba la continuidad con SQL y la puerta 4 es el editor, un LLM-as-judge. Si pasa, siguiente capítulo. Al terminar, la puerta 5 evalúa la novela entera y la puerta 6 verifica la cronología con Lean. Solo entonces se publica. Y si el lector pide un cambio, vuelve al writer. Cuatro roles: planner, writer, editor/critic y extractor. El motor es Claude Code sin tools, con cada skill como prompt de sistema.

## 06 · Contexto acotado, memoria persistente

[3:20–4:05 · 45 s] Cada llamada tiene un tope de 100.000 tokens, y se respetó en las 97 llamadas de la novela real: la mayor fue de 90.764. La memoria no vive en el prompt sino en una story bible en SQLite, con cronología e índice vectorial para recuperar solo lo relevante. Hay checkpoint por capítulo, retries con límite de tres, y los datos personales se seudonimizan antes de llegar al modelo. El harness tiene dos hooks: validación del capítulo, que son las puertas 3 y 4, y policy, el guardrail de palabras prohibidas con audit log.

## 07 · Cuatro tipos de validators

[4:05–4:55 · 50 s] Validamos con cuatro tipos de validators. Programáticos: schema, nombres exactos, longitud, elementos personales, palabras prohibidas y validación visual de la web con browser MCP; actúan en las puertas 1 a 3, el guardrail y la web. Semánticos: un LLM-as-judge de oficio en cada capítulo, una rúbrica de la novela entera y la revisión humana. Y dos formales: Lean 4 sobre la historia y TLA+ con TLC sobre el sistema. Todos envían su score a Langfuse. Un ejemplo de por qué hacen falta varios: la rúbrica encontró una incoherencia de fechas que las puertas deterministas no vieron.

## 08 · Evals: cinco briefs

[4:55–5:45 · 50 s] La evidencia: cinco briefs contra cada puerta, con Claude real. El de ejemplo, con Opus 5.5, llega a la novela completa: diez de diez capítulos, rúbrica media 4,5 y Lean pasa con 115 eventos; el juez rechazó 6 de 16 intentos. 41,47 dólares. En el adversarial, el entrevistador detecta las tres inyecciones, el canario no aparece y la continuidad para el capítulo 3 por un fallo real. Jubilación se para en el capítulo 3 en el juez, con 4 rechazos de 6. Boda e incoherencia las repetimos con Sonnet 5: la puerta 1 obligó a rehacer la estructura y el juez rechazó 5 de 6 intentos, 4 por clichés. El editor no rebaja el listón por usar un modelo más barato. Total de las evals: 86,92 dólares.

## 09 · Verificación formal del sistema y de la historia

[5:45–6:30 · 45 s] Dos validadores formales. Con TLA+ modelamos el flujo como máquina de estados y TLC exploró 15,8 millones de estados sin errores. Hay 11 invariantes de seguridad: por ejemplo, nunca se publica un capítulo sin todas sus puertas, la reanudación no pierde ni duplica capítulos, los reintentos no pasan del límite y la versión anterior se conserva. Y liveness: toda generación termina publicando o deteniéndose. Lo valioso es que TLC encontró contraejemplos reales durante el desarrollo, y cada uno cambió el código. Con Lean 4 verificamos la cronología que sale de SQLite. No encontró ningún caso real en las tres novelas, y es coherente: no hay analepsis, solo hay una muerte y las edades vienen en letra.

## 10 · Tuning del prompt del redactor: v5 → v6

[6:30–7:10 · 40 s] La observabilidad está en Langfuse, y ahí versionamos los prompts. Un ejemplo de tuning: el prompt del redactor, de la v5 a la v6. Los intentos rechazados por cuentas bajaron del 44 al 14 %. Los capítulos aprobados a la primera pasaron de 3 de 5 a 5 de 6. Las paradas, de una a cero. Y el coste de los intentos rechazados, de 11,44 a 2,87 dólares. [Señalar la captura de la trace: cada puerta deja su score en la misma traza.]

## 11 · Guardrails: lo que nunca llega a la página

[7:10–7:40 · 30 s] Los guardrails. Palabras prohibidas en tres niveles: globales, de la novela y del cliente, normalizando tildes y plurales; si aparece una, el capítulo se reescribe. Los datos personales se seudonimizan antes de llegar al modelo. De los tres intentos de inyección, detectamos los tres. Y cada decisión del policy engine queda en un audit log.

## 12 · Cada novela deja 90,55 € de margen

[7:40–8:20 · 40 s] Vamos a los números. El coste unitario de una novela es de 58,45 euros: 38,15 de tokens, que son los 41,47 dólares medidos en Langfuse; 13,80 de tres revisiones incluidas; 1,50 de infraestructura y 5 de operación. La vendemos a 149 euros, así que el margen es de 90,55 euros, un 61 %. La fórmula es simple: margen igual a precio menos tokens, revisiones, infraestructura y operación.

## 13 · Se recupera en 9 meses con 50 novelas al mes

[8:20–9:05 · 45 s] El proyecto cuesta 440 horas: 80 de diseño, 220 de desarrollo, 100 de validación y 40 de despliegue; a 60 euros la hora, 26.400 euros. Con 1.500 euros al mes de costes fijos, 50 novelas al mes dejan 3.027,50 euros al mes y se recupera en 9 meses; con 200, 16.610 euros al mes y menos de dos meses; con 1.000, 89.050 euros al mes. Y es robusto: si los tokens suben un 50 %, el margen baja a 64,57 euros, un 43 %; con seis revisiones en vez de tres, a 76,75, un 52 %; y con las dos cosas a la vez, a 43,87, un 29 %. Sigue siendo positivo.

## 14 · Demo: el cambio llega solo donde toca

[9:05–9:50 · 45 s] Para cerrar, la demo. [Vídeo: AUTOR; si no, la captura.] El lector pide un cambio y se propaga solo a los capítulos 1 y 2; vemos lo añadido y lo quitado, y la versión 1 sigue ahí. Los riesgos que vemos: el coste de los reintentos, que el juez es probabilístico y que los capítulos salen algo largos. Por eso los siguientes pasos son una comprobación determinista de cifras, el control de longitud y la revisión humana a escala.

## 15 · Gracias

[9:50–10:00 · 10 s] Gracias. storyMaker convierte a quien recibe el regalo en el protagonista, con un harness que se puede medir. Quedo a su disposición para preguntas; en los anexos tienen la especificación TLA+, las evals completas, el esquema de la story bible, el red-team log y la comparación de modelos.

## 16 · A1 · Especificación TLA+ comentada (1/2)

Anexo de respaldo (0 s en la exposición). El modelo TLA+ comprueba el flujo con 5 capítulos, 3 intentos por capítulo (2 reintentos) y cambio del lector. TLC recorrió 15.815.224 estados, con profundidad 110, en 1 h 07 min y sin errores. Las 17 variables recogen el estado de la ejecución, las puertas, las versiones, el cambio del lector y los fallos inyectados. Next combina el sistema, las paradas pedidas, las caídas, la respuesta del autor, el relanzamiento y el cambio del lector. Hay 11 invariantes.

## 17 · A1 · Propiedades y contraejemplos (2/2)

Anexo de respaldo (0 s en la exposición). Propiedades temporales: la versión anterior es inmutable, reanudar no pierde ni duplica capítulos, el cierre es único, toda ejecución termina (L1) y, con fallos finitos y un autor que responde, acaba publicada (L2). TLC encontró tres contraejemplos reales: una novela «completada» sin capítulos, un cambio del lector que no revalidaba las puertas y un capítulo a medias en el código actual; los tres cambiaron el código. comprobar_tablas.py mantiene el modelo alineado con orquestador/estados.py.

## 18 · A2 · Tabla de evals completa (1/2)

Anexo de respaldo (0 s en la exposición). Primera mitad de la tabla completa: modelo, capítulos y puertas hasta la continuidad. Con Sonnet 5, la puerta 1 obligó a rehacer la estructura en boda e incoherencia; la escaleta pasa en los cinco briefs; la continuidad paró el adversarial en el capítulo 3 y la incoherencia temporal en el capítulo 2.

## 19 · A2 · Tabla de evals completa (2/2)

Anexo de respaldo (0 s en la exposición). Segunda mitad de la tabla completa: personalización, palabras prohibidas, juez de oficio, rúbrica global, Lean, browser MCP y coste. La personalización falló una vez de tres en la incoherencia temporal; las palabras prohibidas pasan en los cinco briefs; browser MCP hizo 11 comprobaciones sobre la web del ejemplo y el único fallo, el favicon, se corrigió. Coste total de las evals: 86,92 dólares.

## 20 · A3 · Esquema SQLite de la story bible

Anexo de respaldo (0 s en la exposición). El esquema real de la story bible. Personajes y lugares alimentan la ficha de la web; los eventos, con su línea de tiempo, forman la cronología que se exporta a Lean. La pieza clave para el cambio del lector es hecho_uso: sabe en qué escenas se usa cada hecho y así decide qué capítulos regenerar. Las versiones conservan la anterior, resultado_puerta guarda cada veredicto y lo envía a Langfuse, termino_vetado y decision_politica son el guardrail y su audit log, y vec_escena y vec_hecho, el índice vectorial.

## 21 · A4 · Red-team log

Anexo de respaldo (0 s en la exposición). Ocho ataques. Los seis primeros los paró el sistema: inyecciones en la carta, petición del prompt de sistema, término vetado, canario, un intento de cambiar la intensidad y una inyección disfrazada de cambio del lector, que se rechaza antes de llegar a ningún agente. Los dos últimos no los vio ninguna defensa al principio: una etiqueta anidada que cerraba el bloque de datos y un entrevistador que inventaba datos. Los encontró el subagente validador-de-codigo; ahora el primero está corregido en el código y el segundo exige cita literal.

## 22 · A5 · Opus 5.5 frente a Sonnet 5

Anexo de respaldo (0 s en la exposición). Opus 5.5 pasa la puerta 1 a la primera en las cinco novelas; Sonnet 5 paró las dos por una dedicatoria sin el nombre completo. El juez rechaza el 44 % de los intentos de Opus (un 14 % por cuentas tras el tuning) y el 83 % de los de Sonnet, 4 de ellos por clichés. Opus cuesta 41,47 dólares por novela de 10 capítulos; Sonnet gastó 14,84 en dos evals y solo aprobó un capítulo, y además es más lento por intento. Conclusión: más barato no sale más barato; Opus queda en producción para redacción y juez.

## 23 · A6 · Langfuse y browser MCP

Anexo de respaldo (0 s en la exposición). Evidencia de observabilidad: una trace completa en Langfuse con el score de cada puerta, las versiones v5 y v6 del prompt del redactor y la validación visual de la web con browser MCP (la ficha de personajes y lugares). [AUTOR: capturas de la trace y de las versiones del prompt.]

## 24 · A7 · Rúbrica del LLM frente a revisión humana

Anexo de respaldo (0 s en la exposición). La rúbrica del LLM-as-judge sobre la novela de ejemplo: continuidad 4, tono 4, arco 5, coherencia de personajes 5, ritmo 4 y personalización natural 5; media 4,5. El 4 en continuidad es el caso que vale la pena contar: el juez vio que una videollamada del día −6 no encaja con once días sin respuesta, y ninguna puerta determinista lo detectó. [AUTOR: revisión humana y diferencia.]
