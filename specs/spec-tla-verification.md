# Verificación — storyMaker: la máquina de estados en TLA+

Plan de verificación de [spec-tla.md](spec-tla.md). Los métodos y las etiquetas siguen [docs/validators.md](../docs/validators.md), y las rutas de evidencia son relativas a `formal/tla/`.

Actualizado el 24 de septiembre de 2026.

## Cómo leer la tabla

- **Punto ciego:** lo que el método no ve aunque pase (regla 1 de validators.md).
- **¿Solitario?:** si la propiedad descansa en un solo método (regla 2).
- **Estado:** `implementado`, `pendiente` o `fallando`.

El alcance es enteramente **determinista**: un modelo del orquestador y del worker, sin agentes. Los agentes y las puertas son elecciones no deterministas dentro del modelo.

## Propiedades verificadas

| # | Propiedad | Requisito | Método | Tag | Punto ciego | ¿Solitario? | Evidencia | Estado |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Se cumplen los invariantes S1 a S11 en todos los estados alcanzables del modelo del diseño: 5 capítulos, 3 intentos (2 reintentos), 2 fallos, el cambio del lector y los dos arreglos del presupuesto | RF-TLA-04, RF-TLA-06 | Model checking con TLC | `A` | Verifica el modelo, no el código: una diferencia entre los dos pasa en verde. La primera versión juntaba dos transacciones y S2 daba un verde falso. Además, solo vale dentro de los límites de la configuración (hipótesis del alcance pequeño) | No: `src/backend/tests/test_estados_exhaustivo.py` recorre el código real (T), con profundidad 4 | `salidas/StoryMaker.txt` | implementado |
| 1b | El código de `pruebas` cumple S2: una caída nunca deja un capítulo a medias fuera de una ejecución activa | RF-TLA-04, RF-TLA-09 | Model checking con TLC sobre `CodigoActual.cfg` | `A` | El de la fila 1 | No: el `validador-de-codigo` lo reprodujo contra el código real, con una caída simulada | `salidas/CodigoActual.txt` (traza de 14 estados); `salidas/ArregloA.txt` y `salidas/ArregloB.txt` pasan | fallando: lo cierra el backend con los dos arreglos |
| 2 | Toda ejecución termina aunque las puertas y los agentes fallen sin límite | RF-TLA-05 (L1) | Model checking con TLC, con fallos de puerta ilimitados | `A` | La equidad débil del sistema da por hecho que el worker sigue dando pasos. Una llamada al agente que no vuelve nunca no está en el modelo: la cubre el `timeout` del puerto | Sí | `salidas/Terminacion.txt` | implementado |
| 3 | Con fallos finitos y un autor que responde, la novela acaba publicada | RF-TLA-05 (L2) | Model checking con TLC | `A` | Supone un autor que responde y fallos finitos. Una puerta real que rechaza siempre el mismo capítulo no se publica nunca, y el modelo no dice nada de eso | Sí | `salidas/StoryMaker.txt` | implementado |
| 4 | Las tablas del modelo son las de `estados.py` | RF-TLA-08 | Unit / integration testing: `comprobar_tablas.py` lee las dos y las compara fila a fila | `T` | Solo las tablas y los conjuntos de estados. La lógica de `avanzar`, del worker y de la recuperación se copió a mano y no la compara ningún programa | No: la fila 5 cubre el resto | `comprobar_tablas.py` | implementado |
| 5 | Cada acción del modelo corresponde a la transacción o al tramo del código que nombra | RF-TLA-01, RF-TLA-08 | Multi-agent verification: el `validador-de-codigo` lee la tabla de correspondencia del README contra el código | `I` | La lectura es de un momento: un cambio posterior en `pipeline.py` no avisa a nadie. La fila 4 solo protege las tablas | No: la fila 4 cubre las tablas | `README.md`, «Correspondencia con el código» | implementado |
| 6 | Los invariantes detectan los fallos que el código podría tener | RF-TLA-07 | Mutation testing: 13 mutaciones del modelo, y cada una tiene que hacer saltar justo la propiedad que se espera | `T` | Solo las trece mutaciones de la lista. S2b, S4, S6, S8, S10 y S11 no tienen una mutación propia | Sí | `mutaciones.py` | implementado |
| 7 | La máquina anterior a la fase 2 de spec2 viola S1b con la traza del hallazgo 1 | RF-TLA-09 | Model checking con TLC sobre `Hallazgo1.tla` | `A` | `Hallazgo1.tla` solo modela lo que el hallazgo necesita: sin caídas, sin `parar` y sin versiones | No: `src/backend/tests/test_auditoria.py::test_hallazgo_01_…` lo reproduce contra el código | `salidas/Hallazgo1.txt` | implementado |
| 8 | Un renombrado del lector que no vuelve a evaluar las puertas 1 y 2 deja la novela completada con las puertas sin vigencia, y con la nueva evaluación ya no | RF-TLA-09 | Model checking con TLC: `CambioSinRevalidar.cfg` frente a `StoryMaker.cfg` | `A` | El modelo de la vigencia es un booleano. Qué filas cambia de verdad un renombrado lo dice `vigencia.py` y lo comprueban sus tests, no TLC | No, cuando existan los tests del bloque 8 en la rama `cambio-lector` | `salidas/CambioSinRevalidar.txt` | implementado |
| 9 | Las acciones del cambio del lector corresponden al código del bloque 8 | RF-TLA-08 | Multi-agent verification, como la fila 5 | `I` | Se modeló sobre la spec (spec3, 3.8) antes de que existiera el código. Hasta integrar la rama `cambio-lector`, la tabla apunta a funciones que no están en `pruebas` | Sí | `README.md`, filas del cambio del lector | pendiente |

## Riesgos aceptados

| # | Propiedad | Por qué no se verifica | Qué lo hace tolerable |
| --- | --- | --- | --- |
| 10 | Las propiedades valen para 6 capítulos o más, 4 intentos o más, o 3 fallos | TLC explora un modelo finito, y con 5 capítulos y 2 fallos ya son un millón de estados | Ninguna acción del modelo depende del número de capítulo más allá de «siguiente» y «desde d». Los fallos que encuentran los modelos de este tipo suelen salir con muy pocos pasos: la traza del hallazgo 1 tiene 11 estados, y la del renombrado, 29 |
| 11 | La huella de las puertas 1 y 2 cambia exactamente cuando el modelo dice | El modelo no recalcula el SHA-256 de `vigencia.py` | Lo cubren los tests de vigencia de spec2 y spec3 (spec3-verification, fila 16) |
| 12 | Una intención del autor que falla a mitad (una excepción en `_resolver_parada`) deja el sistema coherente | El modelo trata las intenciones como atómicas e infalibles. En el código, esa excepción lleva a `_marcar_error` y deja la ejecución en `error` con la parada todavía abierta en su tabla, lo que rompería S6 | La parada abierta no bloquea nada: desde `error`, arrancar o relanzar la cierran (`fallo.relanzar` cierra todas las abiertas). La transición `(parada, error)` existe en la tabla para ese caso |
