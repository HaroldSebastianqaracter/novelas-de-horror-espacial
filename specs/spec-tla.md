# SRS — storyMaker: la máquina de estados en TLA+

La especificación formal del flujo de generación, con su comprobación en TLC. Es la parte TLA+ del bloque 9 del [plan de entrega](storymaker-plan.md); la parte Lean 4 va aparte. El código está en [formal/tla/](../formal/tla/README.md) y el plan de verificación, en [spec-tla-verification.md](spec-tla-verification.md).

Versión 0.1 · 24 de septiembre de 2026

> **Cómo leer este documento.** Los requisitos llevan el prefijo `RF-TLA-`. No cambian nada de `src/`: describen un modelo del código y cómo se mantiene fiel a él. Donde el modelo toma una decisión que el código no dicta, va con el callout **Decisión sin entrevistar**, igual que en spec3.

---

## 1. Qué se modela

El modelo es el ciclo de vida de una novela desde `configurada` hasta que se publica una versión, con todo lo que puede interrumpirlo:

- los reintentos de la puerta 4 y de la escaleta;
- las paradas y su resolución;
- `parar`, la caída del worker y la recuperación;
- relanzar desde un capítulo;
- el cambio del lector, que es el diseño de [spec3](spec3.md), sección 3.8.

El diagrama está en [docs/proceso/diagramas.md](../docs/proceso/diagramas.md), sección 2.

**RF-TLA-01 — Un paso del modelo es una transacción del código.** Cada acción de `StoryMaker.tla` es una de dos cosas:

- una transacción de `orquestador/` o de `worker.py`;
- un tramo entre dos transacciones, porque las llamadas al agente caen fuera de ellas (RF2-PIPE-08).

Así, una caída entre dos acciones es exactamente una caída entre dos `COMMIT`. Hay tres pasos que el código hace en dos transacciones y el modelo junta en uno: registrar una puerta y hacer la transición que la sigue, abrir la parada tras el último fallo de oficio, y evaluar la puerta 5 y completar. Se pueden juntar porque la recuperación no mira el estado de la ejecución, sino el grafo, así que caer entre los dos pasos da el mismo estado recuperado.

**RF-TLA-02 — Lo que el modelo no ve.**

- **Las puertas y los agentes.** Son elecciones no deterministas: una puerta pasa o falla y un agente responde o lanza una excepción. Lo que se verifica es el **orden** que impone el orquestador, no lo que juzgan. Es la misma abstracción de `tests/test_estados_exhaustivo.py`.
- **La vigencia de las puertas 1 y 2.** Se modela como un booleano por puerta. Solo la cambian cuatro cosas: evaluar la puerta, borrar la escaleta, rehacer y aplicar un renombrado del lector. Lo que invalida la huella en el código real está en `orquestador/vigencia.py`, y el modelo no lo recalcula.

**RF-TLA-03 — Variables.** Las del estado persistente:

- `estado`, que es `ejecucion.estado`;
- la parada abierta y su tipo;
- `planificado`, `escaleta`, `p1` y `p2`, lo que `avanzar` deriva del grafo;
- el estado de cada capítulo: `pendiente`, `a_medias` o `completado`;
- las revisiones de su texto;
- `versiones`, que es `novela_version`;
- el estado del cambio del lector.

Las del proceso son `vivo`, `corriendo`, `pc` (por dónde va `avanzar`) y los contadores de intentos.

Hay una variable fantasma, `aprobado`, que el código no tiene. Vale verdadero solo para un capítulo cuyo texto vigente pasó las puertas 3 y 4. Sin ella, «completado» y «aprobado» serían lo mismo por construcción, y S1 no podría fallar. La mutación «un capítulo se cierra sin pasar la puerta 3» lo demostró antes de que existiera (RF-TLA-07).

## 2. Propiedades

**RF-TLA-04 — Seguridad.** Invariantes y propiedades de acción de `StoryMaker.tla`:

| # | Nombre | Qué afirma |
| --- | --- | --- |
| S1 | `PublicacionConPuertas` | Una versión publicada tiene los N capítulos y el texto de cada uno pasó las puertas 3 y 4, o la 4 sobre la corrección en un cambio del lector. Además, las puertas 1 y 2 estaban vigentes |
| S1b | `CompletadaConNovela` | Una novela completada tiene todos los capítulos aprobados y las puertas 1 y 2 vigentes. Es la propiedad que rompía el hallazgo 1 |
| S2 | `SinCapituloAMedias` | Con el worker vivo y nada corriendo, ningún capítulo tiene texto y hechos sin cerrar (RF2-PER-07) |
| S2b | `AMediasSoloElActual` | Solo el capítulo en curso puede estar a medias, y solo entre sus tramos 2 y 3 |
| S3 | `ReintentosAcotados` | El intento de capítulo y el del cambio del lector no pasan de `MaxIntentos`; la escaleta, de 2 |
| S4 | `CapituloConPuertas` | Ningún capítulo se genera sin las puertas 1 y 2 vigentes (RF2-PIPE-00b) |
| S5 | `SinTransicionInvalida` | El orquestador nunca pide una transición que la tabla no tiene, ni choca con `PuertasNoVigentes` |
| S6 | `ParadaCoherente` | En `parada` hay una parada abierta, y fuera de `parada`, ninguna |
| S7 | `SoloElAlcance` | Un cambio del lector solo reescribe los capítulos de su alcance (RF3-CAM-05) |
| S8 | `CambioFallidoNoAplica` | Un cambio fracasado o interrumpido no deja nada aplicado: ni texto ni versión (RF3-CAM-12) |
| S9 | `VersionesInmutables` | `versiones` solo crece, y ninguna versión publicada cambia (RF3-BIB-11) |
| S10 | `ReanudarNoPierde` | La recuperación tras una caída conserva todos los capítulos completados |
| S11 | `CierreUnico` | El texto de un capítulo cambia una vez por cierre, y solo al cerrar su intento en curso o al aplicar un cambio del lector que lo incluye en el alcance. Reanudar no duplica |

**RF-TLA-05 — Liveness.**

| # | Nombre | Qué afirma |
| --- | --- | --- |
| L1 | `EjecucionTermina` | Toda ejecución de `avanzar` acaba en reposo: completada, en parada, detenida o en error. Nunca queda en un bucle |
| L2 | `AcabaPublicada` | Con fallos finitos y un autor que responde, la novela acaba completada y con una versión publicada, y se queda así |

> **Decisión sin entrevistar: cómo se modelan las paradas que esperan al autor.** Una parada no es un fallo: es el sistema esperando a una persona. Por eso L1 la cuenta como final legítimo de una ejecución, y L2 exige equidad débil al autor: `WF_vars(AutorResponde)` significa que, si una novela le espera indefinidamente (parada, detenida, en error o sin arrancar), acaba respondiendo con alguna de las acciones válidas. Lo que no tiene equidad puede no ocurrir nunca: las caídas, `parar`, los fallos de las puertas y las regeneraciones sobre una novela completada.
>
> Alternativas descartadas:
> - **Solo terminación en parada.** Sin equidad del autor, L2 no se puede enunciar, y L2 es lo que distingue una máquina que termina de una que sirve para algo.
> - **Equidad fuerte.** No hace falta, porque una novela que espera sigue esperando hasta que alguien actúa.
> - **Un autor que siempre relanza.** Esconde las resoluciones que no llevan a ningún sitio.

> **Decisión sin entrevistar: dos modos de fallo.** L2 solo es cierta con fallos finitos: una puerta que falla siempre no deja publicar nunca. Si todo se comprobara con fallos acotados, la terminación de L1 vendría de ese límite y no de los topes de reintentos. Por eso hay dos modos:
> - **Fallos acotados** (`MaxFallos`) para todas las propiedades.
> - **Fallos de puerta ilimitados** (`FallosDePuertaAcotados = FALSE`) para L1 y la seguridad. En este modo, lo que acota una ejecución son `MaxIntentos` y las dos escaletas. Es el único modo que detecta la mutación «la escaleta se repite sin límite».
>
> `MaxReinicios` acota cuántas veces el autor relanza, para que el espacio de estados sea finito. Con fallos acotados no limita nada, porque cada reinicio necesita antes un fallo.

## 3. Comprobación

**RF-TLA-06 — Modelos de TLC.** Las configuraciones están en `formal/tla/`, y la salida de cada ejecución, en `formal/tla/salidas/`:

| Configuración | Qué es | Resultado esperado |
| --- | --- | --- |
| `StoryMaker.cfg` | El modelo del enunciado: 5 capítulos, 2 reintentos, 2 fallos, con el cambio del lector | Pasan S1 a S11, L1 y L2 |
| `CodigoActual.cfg` | Lo mismo, sin el cambio del lector: el código de `pruebas` tal cual | Pasan todas |
| `Terminacion.cfg` | Fallos de puerta ilimitados, una caída o `parar` y un reinicio | Pasan la seguridad y L1 |
| `CambioSinRevalidar.cfg` | El diseño del cambio del lector antes del contraejemplo (RF-TLA-08) | S1b falla |
| `Hallazgo1.cfg` (sobre `Hallazgo1.tla`) | La máquina anterior a la fase 2 de spec2 | S1b falla |

Para comprobar deadlocks, TLC corre con `-deadlock`, que los desactiva. El final legítimo de un comportamiento es un estado sin sucesores: una novela completada cuando el autor ya no pide más cambios.

**RF-TLA-07 — El modelo tiene que poder fallar.** `formal/tla/mutaciones.py` rompe el modelo a propósito, un fallo cada vez, y exige que TLC encuentre cada uno. La mutación cambia el modelo, no el código: comprueba que los invariantes miran algo. La lista de mutaciones y lo que detecta cada una está en el [README](../formal/tla/README.md).

**RF-TLA-08 — Correspondencia comprobada.** `formal/tla/comprobar_tablas.py` lee `TRANSICIONES`, `RESOLUCIONES` y los conjuntos de estados de `orquestador/estados.py` y los compara con los del modelo, fila a fila. Si difieren en algo, sale con 1. Las transiciones del cambio del lector (RF3-CAM-06) salen como pendientes hasta que el backend las tenga. El resto de la correspondencia, cada acción del modelo con su fichero y su función, es una tabla del README que se revisa a mano (fila 5 del plan de verificación).

**RF-TLA-09 — Los contraejemplos.** El `README` enseña dos trazas de TLC, con sus pasos y el cambio que cerró cada una:

1. **El hallazgo 1 de la auditoría.** Resolver una parada de estructura acababa en `completada` sin capítulos. La máquina anterior es la del padre de `68d9e7e`, y el cambio que la cerró, la fase 2 de spec2 (entrada 4 del [registro de iteraciones](../docs/proceso/registro-iteraciones.md)).
2. **El renombrado que dejaba las puertas sin vigencia.** Lo encontró TLC al modelar spec3 3.8, antes de implementarlo, y cambió el diseño: RF3-CAM-11 vuelve a evaluar las puertas 1 y 2 en la transacción final.

**RF-TLA-10 — Herramientas.** Hacen falta un JDK 11 o superior (se probó con Temurin 21) y `tla2tools.jar` de las [releases oficiales](https://github.com/tlaplus/tlaplus/releases); se probó con TLC 2.19. El `.jar` no se commitea, y el README dice cómo conseguirlo y cómo lanzar cada configuración.

> **Decisión sin entrevistar: TLA+ directo y no PlusCal.** Con PlusCal, cada etiqueta es un paso atómico, y habría que escribir tantas etiquetas como transacciones tiene el código: la correspondencia saldría igual, pero pasando por la traducción. Con TLA+ directo, cada acción lleva el nombre de lo que hace en el código (`Tramo12`, `Recuperar`, `LectorAplicar`), y las trazas de TLC se leen contra el código sin traducir nada.

> **Decisión sin entrevistar: cómo se integra con el flujo real.** Tres opciones:
> - Especificar a mano y comprobar la correspondencia con un script.
> - Generar la especificación desde `estados.py`.
> - Solo el test exhaustivo en Python.
>
> Se eligió la primera. Generar la especificación solo daría la tabla, que es lo fácil. Lo que TLC aporta está en `avanzar` y en el worker, que no son una tabla. El test exhaustivo de Python sigue: ejecuta el código real, pero con profundidad 4. TLC explora el modelo entero, pero el modelo puede apartarse del código. Cada uno cubre el punto ciego del otro. El trade-off completo está en [docs/proceso/trade-offs.md](../docs/proceso/trade-offs.md).
