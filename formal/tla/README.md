# La máquina de estados en TLA+

`StoryMaker.tla` modela el flujo de generación de storyMaker: configuración, planificación, escritura de capítulos, validación y publicación de versión, con los reintentos, las paradas, `parar`, la caída del worker y la reanudación, y el cambio del lector. TLC lo recorre entero en un modelo pequeño. Requisitos en [specs/spec-tla.md](../../specs/spec-tla.md), verificación en [specs/spec-tla-verification.md](../../specs/spec-tla-verification.md) y diagrama en [docs/proceso/diagramas.md](../../docs/proceso/diagramas.md), sección 2.

| Fichero | Qué es |
| --- | --- |
| `StoryMaker.tla` | La especificación: el código de hoy más el cambio del lector de spec3 3.8 |
| `StoryMaker.cfg` | El modelo del enunciado: 5 capítulos y 2 reintentos, con el cambio del lector |
| `CodigoActual.cfg` | El mismo modelo sin el cambio del lector, que todavía no está en `pruebas` |
| `Terminacion.cfg` | Puertas y agentes que fallan sin límite, para comprobar que toda ejecución termina |
| `CambioSinRevalidar.cfg` | El contraejemplo que cambió el diseño del cambio del lector |
| `Hallazgo1.tla`, `Hallazgo1.cfg` | La máquina anterior a la fase 2 de spec2 y el contraejemplo del hallazgo 1 |
| `comprobar_tablas.py` | Comprueba que las tablas del modelo son las de `orquestador/estados.py` |
| `mutaciones.py` | Rompe el modelo a propósito y comprueba que TLC lo detecta |
| `salidas/` | La salida de TLC de cada configuración |

## Cómo se ejecuta

Hace falta Java 11 o superior y `tla2tools.jar`, que no se commitea. Se probó con Temurin 21 y TLC 2.19. Sin permisos de administrador basta con esto (desde Git Bash):

```sh
mkdir -p ~/tools && cd ~/tools
curl -L -o jdk.zip "https://api.adoptium.net/v3/binary/latest/21/ga/windows/x64/jdk/hotspot/normal/eclipse"
unzip -q jdk.zip && rm jdk.zip
curl -L -o tla2tools.jar https://github.com/tlaplus/tlaplus/releases/latest/download/tla2tools.jar
```

Cada configuración se lanza desde esta carpeta:

```sh
JAVA=$(ls -d ~/tools/jdk-21*)/bin/java
$JAVA -XX:+UseParallelGC -cp ~/tools/tla2tools.jar tlc2.TLC -workers auto -deadlock \
      -config StoryMaker.cfg StoryMaker.tla
```

`-deadlock` desactiva la comprobación de deadlocks. Un comportamiento termina de forma legítima en un estado sin sucesores: la novela completada, cuando el autor ya no pide más cambios. `Hallazgo1.cfg` se lanza sobre `Hallazgo1.tla`, y las demás configuraciones sobre `StoryMaker.tla`.

Los dos scripts se lanzan desde la raíz del repo, con el entorno del backend:

```powershell
src\backend\.venv\Scripts\python.exe formal\tla\comprobar_tablas.py
src\backend\.venv\Scripts\python.exe formal\tla\mutaciones.py RUTA\java.exe RUTA\tla2tools.jar
```

## Resultados

Salida completa de cada configuración en `salidas/`. Cifras del 24 de septiembre de 2026, con 12 workers:

| Configuración | Estados distintos | Profundidad | Tiempo | Resultado |
| --- | --- | --- | --- | --- |
| `StoryMaker.cfg` | 1.132.973 | 89 | 6 min 26 s | Sin errores: S1 a S11, L1 y L2 |
| `CodigoActual.cfg` | 61.637 | 89 | 25 s | Sin errores: S1 a S11, L1 y L2 |
| `Terminacion.cfg` | 1.664.731 | 72 | 7 min 50 s | Sin errores: seguridad y L1 |
| `CambioSinRevalidar.cfg` | 207 | 29 | 2 s | Viola `CompletadaConNovela` en 29 estados |
| `Hallazgo1.cfg` | 27 | 11 | 1 s | Viola `CompletadaConNovela` en 11 estados |

`comprobar_tablas.py` da las 21 transiciones y las 7 resoluciones iguales. Las 2 transiciones del cambio del lector salen como pendientes en el backend.

## Qué se comprueba

Las propiedades se definen al final de `StoryMaker.tla`, cada una con su comentario. [spec-tla.md](../../specs/spec-tla.md) (RF-TLA-04 y RF-TLA-05) las explica, y dice cómo se modelan las paradas que esperan al autor.

- **Seguridad.**
  - S1 `PublicacionConPuertas`: nunca se publica una versión con un capítulo que no pasó todas las puertas.
  - S1b `CompletadaConNovela`: una novela completada tiene todos sus capítulos.
  - S2 `SinCapituloAMedias` y S2b `AMediasSoloElActual`: la reanudación no deja capítulos a medias.
  - S3 `ReintentosAcotados`: los reintentos nunca pasan del límite.
  - S4 `CapituloConPuertas`: no se genera un capítulo sin las puertas 1 y 2.
  - S5 `SinTransicionInvalida`: no se pide nunca una transición que no existe.
  - S6 `ParadaCoherente`: una parada abierta si y solo si el estado es `parada`.
  - S7 `SoloElAlcance`: el cambio del lector solo toca su alcance.
  - S8 `CambioFallidoNoAplica`: un cambio fallido no aplica nada.
  - S9 `VersionesInmutables`: la versión anterior se conserva siempre.
  - S10 `ReanudarNoPierde`: reanudar no pierde capítulos.
  - S11 `CierreUnico`: reanudar tampoco los duplica.
- **Liveness.**
  - L1 `EjecucionTermina`: toda ejecución termina, publicando o deteniéndose (parada, detenida o error), y nunca en bucle.
  - L2 `AcabaPublicada`: con fallos finitos y un autor que responde, la novela acaba publicada.

### Mutaciones

`mutaciones.py` aplica cada una a una copia del modelo, con 2 capítulos, en dos modos:

- **A**: fallos acotados y todas las propiedades;
- **T**: fallos de puerta ilimitados, con terminación y seguridad.

Todas tienen que hacer saltar alguna propiedad. El 24 de septiembre saltaron las 11:

| Mutación | Lo que salta |
| --- | --- |
| La recuperación no revierte el capítulo a medias | `SinCapituloAMedias` |
| El oficio reintenta sin límite | `ReintentosAcotados` |
| El cambio del lector reintenta sin límite | `ReintentosAcotados` |
| La escaleta se repite sin límite | `EjecucionTermina`, solo en el modo T |
| Un capítulo se cierra sin pasar la puerta 3 | `PublicacionConPuertas` |
| Un cambio fracasado se aplica igual | `PublicacionConPuertas` |
| El cambio reescribe un capítulo fuera del alcance | `SoloElAlcance` |
| El cambio no vuelve a evaluar las puertas 1 y 2 | `CompletadaConNovela` |
| Publicar sobrescribe la última versión | `VersionesInmutables` |
| Relanzar no comprueba las puertas 1 y 2 | `SinTransicionInvalida` |
| `avanzar` no mira la vigencia de la puerta 1 (la mitad del hallazgo 1) | `SinTransicionInvalida` |

Hay dos mutaciones que enseñaron algo del propio modelo:

- **«Un capítulo se cierra sin pasar la puerta 3»** sobrevivió a la primera versión. En ella, «completado» y «aprobado» eran lo mismo por construcción. De ahí sale la variable fantasma `aprobado`: solo la pone a verdadero la rama que pasa las puertas.
- **«La escaleta se repite sin límite»** sobrevivía con fallos acotados, porque la terminación venía de ese límite y no de los topes de reintentos. De ahí sale `Terminacion.cfg`.

## Correspondencia con el código

Todas las rutas son de `src/backend/`. Las filas del cambio del lector apuntan a la rama `cambio-lector`, que todavía no está en `pruebas`.

| Acción del modelo | Estado o transición del código | Fichero y función |
| --- | --- | --- |
| `Transiciones`, `Resoluciones`, `AdmitenRelanzar`, `AdmitenArrancar`, `Activos` | Las tablas de la máquina | `orquestador/estados.py`: `TRANSICIONES`, `RESOLUCIONES`, `ESTADOS_QUE_ADMITEN_*`, `ESTADOS_ACTIVOS` (lo comprueba `comprobar_tablas.py`) |
| `Siguiente` | Destino de un suceso, o `TransicionInvalida` | `orquestador/estados.py::siguiente` |
| `Asegurar`, `EntrarFase` | Poner la ejecución en el estado de la fase | `orquestador/pipeline.py::_asegurar_activa` |
| `MarcaError`, `FallarRun` | Una excepción sale de `avanzar` y la ejecución pasa a `error` | `worker.py::Worker._correr` y `Worker._marcar_error` |
| `DetenerRun` | `except Detenido` / `except AgenteInterrumpido`: transición `parar` | `orquestador/pipeline.py::_avanzar` |
| `AbrirParada` | Abrir la parada y hacer la transición `conflicto`, en una transacción | `orquestador/pipeline.py::_abrir_parada`, `orquestador/fallo.py::abrir_parada` |
| `Derivar` | Qué toca, derivado del grafo (RF2-PIPE-00) | `orquestador/pipeline.py::_avanzar`, primera condición; `orquestador/vigencia.py::puerta_vigente` |
| `PlanAgentes` | Arquitecto, mundo, elenco y estructura, los que falten | `orquestador/pipeline.py::planificar` (el bucle), `::_fase_ya_hecha` |
| `PlanP1` | Puerta 1: `puerta_1_ok` o parada de estructura | `orquestador/pipeline.py::planificar` (final) |
| `ChkEsc` | Sin escaleta o sin puerta 2 vigente, escaletar | `orquestador/pipeline.py::_avanzar`, segunda condición |
| `EscAgente` | El escaletador escribe la escaleta | `orquestador/pipeline.py::escaletar` (primera mitad del bucle) |
| `EscP2` | Puerta 2: `puerta_2_ok`, borrar y repetir, o parada con la escaleta borrada | `orquestador/pipeline.py::escaletar` (segunda mitad), `::_borrar_escaleta` |
| `ChkGen` | `_asegurar_activa("arrancar_generacion")` antes del bucle | `orquestador/pipeline.py::_avanzar` |
| `Bucle` | `siguiente = ultimo_capitulo_completado + 1` y el guardarraíl de puertas | `orquestador/pipeline.py::_avanzar` (el `while`), `::generar_capitulo` (`PuertasNoVigentes`), `compartido/grafo/lectura.py::ultimo_capitulo_completado` |
| `Tramo12` | Tramos 1 y 2: redacción y extracción fuera de transacción; texto, hechos y puerta 3 en una | `orquestador/pipeline.py::generar_capitulo`, hasta `a_medias = True` |
| `Tramo3` | Tramo 3: oficio, y cierre, reintento, parada de oficio o reversión en el `finally` | `orquestador/pipeline.py::generar_capitulo` (resto), `::_cerrar_capitulo`, `::_revertir_a_medias`, `orquestador/fallo.py::revertir_grafo` |
| `P5` | Puerta 5, `terminado_*` y versión, en una transacción | `orquestador/pipeline.py::_avanzar` (final), `orquestador/versiones.py::publicar` |
| `AtenderParar` | El worker coge la intención `parar` | `worker.py::Worker._parar` |
| `PedirParar` | La API encola `parar`; el pipeline la ve en cada llamada | `orquestador/cola.py::hay_parada_pendiente`, `orquestador/pipeline.py::_comprobar_parada` |
| `Caida` | El proceso muere entre dos transacciones | (entorno) |
| `Recuperar` | Revertir el capítulo a medias y dejar la ejecución `detenida` | `worker.py::Worker.recuperar` |
| `Arrancar` | Intención `arrancar` | `worker.py::Worker._arrancar` |
| `Relanzar(d)` | Intención `relanzar` o `resolver_parada` con `relanzar` | `worker.py::Worker._relanzar`, `::_motivo_para_no_relanzar`, `::_resolver_parada`; `orquestador/fallo.py::relanzar` |
| `ResolverContinuidad` | `resolver_parada` con `aceptar_retcon` o `dar_por_sabido` | `worker.py::Worker._resolver_parada`; `orquestador/fallo.py::aceptar_retcon`, `::dar_por_sabido`, `::relanzar` |
| `Rehacer` | `resolver_parada` con `rehacer` | `worker.py::Worker._resolver_parada`; `orquestador/fallo.py::rehacer_estructura`, `::rehacer_escaleta` |
| `TransicionesDelLector` | `(completada\|completada_con_avisos, cambio_lector) → generando` | Rama `cambio-lector`: `orquestador/estados.py::TRANSICIONES` |
| `CambioDelLector` | Interpretar, validar, calcular el alcance y hacer la transición | Rama `cambio-lector`: `worker.py::Worker._cambio_lector` |
| `LectorRevisar` | Reescritura por capítulo con reintentos, y fracaso sin parada | Rama `cambio-lector`: `orquestador/pipeline.py::_revisar_capitulo`, `::_fracasar` → `::_completar` sin aplicar; `parar`: `::_aplicar_cambio`, rama `except (Detenido, AgenteInterrumpido)` |
| `LectorAplicar`, `AplicarCambio` | Una transacción: canon, textos, puertas 1 y 2 otra vez, puerta 5, `terminado_*` y versión; si las puertas fallan, se deshace (`CambioImposible`) | Rama `cambio-lector`: `orquestador/pipeline.py::_completar(aplicar=_confirmar_cambio)`, `::_planificacion_sin_vigencia`, `::_registrar_puerta_en`; `orquestador/cambios.py::aplicar_canon`, `::guardar_textos`; `orquestador/versiones.py::publicar` |
| `Recuperar` con un cambio en curso | El cambio queda `interrumpido` y la ejecución `detenida` | Rama `cambio-lector`: `worker.py::Worker.recuperar` |

## Lo que encontró TLC

### El hallazgo 1, en la máquina anterior

`Hallazgo1.tla` es la máquina del padre de `68d9e7e`. Tenía dos características:

- `avanzar` decidía por el **estado** qué tocaba, no por el grafo;
- una parada de cualquier tipo se resolvía hacia `generando`.

TLC encuentra esta traza (`salidas/Hallazgo1.txt`):

| # | Acción | Lo que cambia |
| --- | --- | --- |
| 1 | Estado inicial | `configurada` |
| 2 | `Arrancar` | Empieza la ejecución |
| 3 | `Derivar` | Falta la planificación: `planificando` |
| 4 | `PlanAgentes` | El canon queda escrito |
| 5 | `PlanP1` | La puerta 1 **falla**: `parada` de estructura |
| 6 | `Resolver` | El autor relanza desde el capítulo 1: `generando`, porque la máquina lo permitía sobre cualquier parada |
| 7 | `Derivar` | El estado es `generando`, así que no planifica, aunque la puerta 1 está rechazada |
| 8 | `ChkEsc` | Como es `generando`, tampoco escaleta |
| 9 | `ChkGen` | Ya estaba en `generando` |
| 10 | `Bucle` | Hay 0 capítulos: el bucle no da ninguna vuelta |
| 11 | `P5` | **`completada`, sin escaleta y con la puerta 1 rechazada** |

Se viola `CompletadaConNovela`.

**El cambio que la cerró** es `68d9e7e`, «Fase 2 de spec2: reanudar nunca se salta una puerta». Es la entrada 4 del [registro de iteraciones](../../docs/proceso/registro-iteraciones.md). Hizo dos cosas, y el modelo actual tiene las dos:

- **`RESOLUCIONES`.** Desde `parada`, la salida depende del tipo, y una parada de estructura solo se resuelve con `rehacer`. En el modelo, `Resoluciones` y `Rehacer`.
- **`avanzar` deriva del grafo** qué toca, con la vigencia de cada puerta por huella. En el modelo, la condición de `Derivar`, `~planificado \/ ~p1`.

Quitar la segunda del modelo actual es la última mutación de la tabla, y TLC la detecta.

### El renombrado que dejaba las puertas sin vigencia

TLC encontró este al modelar el cambio del lector de spec3 3.8, antes de implementarlo, y cambió el diseño.

- **Por qué pasaba.** Un renombrado reescribe filas que leen las huellas de las puertas 1 y 2 (`orquestador/vigencia.py`): los textos de la escaleta y, con brief, `nombre_clave`, el brief y la dedicatoria. Y lo hace aunque su alcance salga vacío. El paso final aplicaba el cambio sin volver a registrar esas puertas.
- **Traza** (`salidas/CambioSinRevalidar.txt`, 29 estados y ningún fallo inyectado): la generación normal de los 5 capítulos llega a `completada` con la versión 1. Luego vienen `CambioDelLector`, un renombrado con el alcance vacío; `LectorRevisar`, que no tiene nada que revisar; y `LectorAplicar`, que deja la novela en `completada` con `p1 = FALSE` y `p2 = FALSE`. Se viola `CompletadaConNovela`.
- **Consecuencias en el código.** Relanzar esa novela quedaba bloqueado, porque `_motivo_para_no_relanzar` exige las puertas vigentes. Y si un cambio posterior se interrumpía, `arrancar` volvía a evaluar las puertas 1 y 2 sobre una novela ya publicada. Si la 1 fallaba, la única salida de su parada es `rehacer`, que borra la escaleta.
- **El cambio.** RF3-CAM-11, paso 3: la transacción final vuelve a evaluar las puertas 1 y 2 sobre el canon cambiado. Si alguna falla, se deshace entera y el cambio fracasa con las puertas intactas. En el modelo, `CambioRevalidaPuertas = TRUE` y la primera rama de `LectorAplicar`. `CambioSinRevalidar.cfg` conserva el diseño anterior para enseñar la traza.

Sobre el código actual de `pruebas`, sin el cambio del lector, TLC no encontró nada nuevo.
