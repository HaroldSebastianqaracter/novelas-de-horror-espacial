# Verificación — storyMaker

Plan de verificación de [spec3.md](spec3.md). Métodos y etiquetas según [docs/validators.md](../docs/validators.md). Las filas de [spec1-verification.md](spec1-verification.md) y [spec2-verification.md](spec2-verification.md) siguen vigentes; aquí solo están las propiedades que spec3 añade.

Actualizado el 23 de septiembre de 2026. Las rutas de evidencia son relativas a `src/backend/`.

## Cómo leer la tabla

**Punto ciego** es lo que ese método no ve aunque pase (regla 1 de validators.md). **¿Solitario?** dice si la propiedad descansa en un solo método; si lo hace, se revisa antes que ninguna otra aunque esté en verde (regla 2). Cuando la propiedad se comprueba sobre un dato que declara el propio agente, la fila nombra el segundo método que mira el texto (regla 3). **Estado** es `implementado`, `pendiente` o `fallando`.

## Bloque 2 — Personalización del terror

| # | Propiedad | Requisito | Método | Tag | Punto ciego | ¿Solitario? | Evidencia | Estado |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | El análisis del brief detecta cada faltante y cada contradicción, sin falsos positivos sobre un brief correcto | RF3-BRF-03 | Unit testing: una prueba por contradicción con su caso mínimo, más el brief de ejemplo como caso limpio | `T` | Solo las contradicciones que el código conoce; una incoherencia nueva (por ejemplo, un recuerdo imposible para la edad) no es ninguna de las tres | **Sí**: señalarlo | `tests/test_brief.py` | implementado |
| 2 | Un término vetado se reconoce con mayúsculas, sin tildes y en plural simple, y respeta palabras completas y la eñe | RF3-BRF-03 | Unit testing parametrizado | `T` | Sinónimos y perífrasis («el animal de ocho patas» por «araña»), y plurales irregulares | Sí; el guardrail del bloque 5 reutiliza la función y añade sus propios tests | `tests/test_brief.py::test_contiene_termino` | implementado |
| 3 | Un brief incompleto o contradictorio no llega al worker, y si llega por otra vía el worker lo rechaza | RF3-BRF-04, RF3-PER-05 | Integration testing sobre la API y sobre el worker | `T` | — | No: dos barreras, cada una con su test | `tests/test_brief.py::test_la_api_rechaza_…`, `::test_el_worker_rechaza_…` | implementado |
| 4 | Las restricciones de la novela salen del brief (escala y política de contenido), y el brief, sus elementos y la entrevista quedan guardados | RF3-PER-01, RF3-PER-02 | Integration testing | `T` | Que el agente respete de verdad la política de contenido: eso es del guardrail (bloque 5) y del juez (bloque 6) | No | `tests/test_brief.py::test_el_worker_guarda_…`, `::test_restricciones_derivadas_…` | implementado |
| 5 | El brief de ejemplo del README es válido y la API lo acepta | RF3-PER-06 | Integration testing | `T` | — | No | `tests/test_brief.py::test_la_api_acepta_…`, `::test_el_brief_de_ejemplo_esta_completo` | implementado |
| 6 | El entrevistador no puede meter en el brief un dato que el comprador no dio | RF3-ENT-02 | Unit testing del filtro de citas literales | `T` | Una cita literal sacada de contexto («no tengo perro» → cita «perro») | Sí | — | pendiente |
| 7 | El texto libre no cambia la configuración ni da instrucciones | RF3-ENT-05 | Red-teaming con inyección en el texto libre + unit testing de los campos permitidos | `T` | Inyecciones que no usan ningún patrón conocido: la búsqueda es una lista cerrada. El filtro de campos no depende de ella | No: filtro de campos + alerta | — | pendiente |
| 8 | La entrevista termina en 25 turnos como máximo | RF3-ENT-03 | Unit testing con el puerto falso | `T` | — | Sí | — | pendiente |
| 9 | La entrevista no escribe en la base salvo la intención | RF3-ENT-06 | Integration testing | `T` | — | Sí | — | pendiente |
| 10 | El destinatario es el protagonista con su nombre exacto, y cada allegado obligatorio está en el elenco | RF3-PER-04 (puerta 1) | Mutation testing sobre la puerta 1 | `A` | Que la prosa lo trate como protagonista: el punto de vista declarado no es el ejercido | No: la fila 12 lo refuerza en la escaleta | — | pendiente |
| 11 | La dedicatoria nombra al destinatario tal cual, y el subgénero fijado en el brief se respeta | RF3-PER-04 (puerta 1) | Mutation testing | `A` | Que la dedicatoria sea buena: es juicio | Sí | — | pendiente |
| 12 | El destinatario es el punto de vista de más de la mitad de las escenas, y la escaleta tiene los capítulos del brief | RF3-PER-04 (puerta 2) | Mutation testing | `A` | El POV lo declara el escaletador (regla 3); que la prosa lo ejerza lo juzga el oficio | No | — | pendiente |
| 13 | Todo elemento personal obligatorio está planificado en alguna escena | RF3-PER-04 (puerta 2) | Mutation testing | `A` | **Dato autodeclarado** (regla 3): el escaletador dice dónde va cada elemento. El segundo método, que el elemento aparezca en la prosa, es del bloque 6 | No, cuando exista el del bloque 6; hasta entonces, **sí** | — | pendiente |
| 14 | El destinatario nunca muere | RF3-PER-04 (puerta 3) | Mutation testing | `A` | La condición la registra el extractor: una muerte que no extrajo no se ve. La búsqueda dirigida `muerto_nombrado` de la puerta 3 no aplica al protagonista vivo | Sí | — | pendiente |
| 15 | El pipeline completo corre con un brief y el puerto falso | RF3-PER-03, RF3-PER-06 | Integration testing | `T` | Los agentes de demostración leen el brief del paquete, pero no escriben como el agente real | No | — | pendiente |

## Riesgos aceptados

| # | Propiedad | Por qué no se verifica todavía | Qué lo hace tolerable |
| --- | --- | --- | --- |
| U3-1 | La prosa respeta la intensidad elegida | Exige el guardrail por nivel (bloque 5) y la rúbrica del juez (bloque 6) | La tabla de intensidad llega al arquitecto y al redactor en cada paquete |
| U3-2 | La personalización se integra con naturalidad y no forzada | Es juicio: lo mide el LLM-as-judge del bloque 6 contra una revisión humana | La escaleta reparte los elementos por escenas en lugar de acumularlos |
