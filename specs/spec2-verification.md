# Verificación — Backend v2

Plan de verificación de [spec2.md](spec2.md). Métodos y etiquetas según [docs/validators.md](../docs/validators.md). Las filas de [spec1-verification.md](spec1-verification.md) siguen vigentes; aquí solo están las propiedades que spec2 añade o endurece.

Actualizado el 23 de septiembre de 2026. Las rutas de evidencia son relativas a `src/backend/`.

## Cómo leer la tabla

**Punto ciego** es lo que ese método no ve aunque pase (regla 1 de validators.md). **¿Solitario?** dice si la propiedad descansa en un solo método; si lo hace, se revisa antes que ninguna otra aunque esté en verde (regla 2). **Estado** es `implementado`, `pendiente` o `fallando`. Una fila cuya evidencia es un test marcado `xfail` está `pendiente`: el test existe y falla, que es justo lo que tiene que hacer hasta que la fase lo arregle.

## Propiedades verificadas

| # | Propiedad | Fase | Método | Tag | Punto ciego | ¿Solitario? | Evidencia | Estado |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Ninguna salida del bucle de capítulo deja estado del capítulo sin cerrar | 1 | Integration testing, una prueba por tipo de salida | `T` | Solo las salidas que el test enumera; una excepción nueva en otro sitio no está cubierta | No: la regla de integridad lo ve después | `tests/test_capitulo_a_medias.py` (salida inválida del juez, agente interrumpido, reanudación), `tests/test_auditoria.py::test_hallazgo_05_…` (`parar`) | implementado |
| 2 | El worker caído deja el grafo en el último capítulo íntegro | 1 | Integration testing con una caída real del proceso | `T` | Una caída a mitad de una transacción la cubre SQLite, no este test; solo prueba la caída durante el oficio | No: la regla `estado_en_capitulo_no_completado` lo ve también | `tests/test_auditoria.py::test_hallazgo_06_…` | implementado |
| 3 | Ningún capítulo se genera sin las puertas 1 y 2 vigentes | 2 | Model checking de estados + `avanzar`: recorrido por anchura de los estados alcanzables con cada suceso y cada combinación de puertas, más una mutación que comprueba que el recorrido detecta el `avanzar` de spec1 | `A` | Solo ve el orden, con puertas falsas; se fía de que `resultado_puerta` sea veraz (la puerta 4 lo arregla la fase 6). Solo las caídas que enumera | No: guardarraíl de la fila 4 | `tests/test_estados_exhaustivo.py`, `tests/test_auditoria.py::test_hallazgo_01_…`, `tests/test_reanudacion.py::test_una_caida_entre_la_estructura_y_la_puerta_1_no_salta_la_puerta` | implementado |
| 4 | Lo mismo, en ejecución | 2 | Guardarraíl en `generar_capitulo` | `D` | El mismo: la vigencia se lee de `resultado_puerta` | No: model checking de la fila 3 | `orquestador/pipeline.py::generar_capitulo` (`PuertasNoVigentes`); `tests/test_reanudacion.py::test_generar_un_capitulo_sin_puertas_vigentes_acaba_en_error` | implementado |
| 5 | Resolver una parada rehace lo que la puerta rechazó | 2 | Integration testing | `T` | Comprueba que se rehace, no que la segunda versión sea mejor | **Sí** | `tests/test_reanudacion.py` (rehacer escaleta y estructura, tabla de acciones, retcon), `tests/test_auditoria.py::test_hallazgo_02_…`, `::test_hallazgo_12_…` | implementado |
| 6 | Dos workers no escriben a la vez | 3 | Integration testing con dos procesos reales + robo del cerrojo a mitad del pipeline | `T` | Un proceso congelado más tiempo que la gracia puede terminar la transacción que ya tenía abierta; el fencing lo acota a esa transacción. Una base de datos en red, donde el cerrojo de SQLite no es fiable | No: fencing + latido, con un test cada uno | `tests/test_cerrojo.py`, `tests/test_auditoria.py::test_hallazgo_03_…`; los tests del fencing fallan si la guarda se anula | implementado |
| 7 | Ningún elemento obligatorio se pierde; ningún recorte es silencioso | 4 | Property-based testing | `T` | Lo marcado opcional puede ser lo que el capítulo necesitaba: la relevancia es una heurística. La estimación de tokens es la de spec1 (U2-1) | **Sí** | `tests/test_paquete.py::test_lo_obligatorio_nunca_se_pierde_y_ningun_recorte_es_silencioso`, `::test_un_techo_bajo_llega_al_paquete_y_el_recorte_queda_en_la_traza`; `tests/test_auditoria.py::test_hallazgo_04_…`, `::test_hallazgo_10_…` | implementado |
| 8 | Una cadena de supersesiones no produce contradicciones | 5 | Mutation testing | `T` | Supersesiones que el extractor no declaró siguen siendo contradicción: correcto, pero es falso positivo si el extractor olvida marcar | No: la cadena y el par único tienen test cada uno | `tests/test_puerta_continuidad.py::test_una_cadena_de_tres_supersesiones_no_es_contradiccion`, `::test_cada_par_contradictorio_se_informa_una_vez`; `tests/test_auditoria.py::test_hallazgo_07_…` | implementado |
| 9 | Dos valores que solo difieren en mayúsculas o tildes son el mismo | 5 | Unit testing | `T` | Sinónimos («castaño» y «marrón»): sigue siendo U7 de spec1. La ene se conserva a propósito | — | `tests/test_puerta_continuidad.py::test_mayusculas_tildes_y_espacios_no_cambian_el_valor`, `::test_la_ene_es_una_letra_y_si_distingue`; `tests/test_auditoria.py::test_hallazgo_08_…` | implementado |
| 10 | `condicion = muerto` impide reaparecer | 5 | Mutation testing | `T` | **Dato autodeclarado por el extractor** (regla 3): una muerte que no registró como `muerto` no para | No, con la fila 13 (fase 6) | `tests/test_puerta_continuidad.py::test_detecta_personaje_muerto_que_reaparece`, `::test_la_ultima_condicion_manda`, `::test_la_muerte_no_impide_una_analepsis`; `tests/test_auditoria.py::test_hallazgo_16_…` | implementado |
| 11 | `resultado_puerta` refleja las dos partes de la puerta 4 | 6 | Contract testing | `T` | No dice si el juez acierta (fila 39 de spec1) | No | `tests/test_auditoria.py::test_hallazgo_09_…` (xfail) | pendiente |
| 12 | El extractor no descarta en silencio | 6 | Integration testing sobre el recuento | `T` | Lo que el extractor ni siquiera emitió | No, con la fila 13 | — | pendiente |
| 13 | Cobertura del extractor desde el texto | 6 | Búsquedas dirigidas | `T` | Rasgos sin nombre propio ni cifra; alias y pronombres | No: complementa las evals del extractor | — | pendiente |
| 14 | El agente no usa herramientas | 6 | Guardarraíl en el puerto | `D` | Depende de que el CLI siga devolviendo esos metadatos | **Sí** | — | pendiente |
| 15 | El filtro admite antes de que la similitud ordene | 7 | Unit testing | `T` | — | No | — | pendiente |
| 16 | Lo recuperado es relevante | 7 | Golden set, recall@k, sin juez | `T` | Golden set pequeño y escrito por el equipo; U8 sigue abierto | **Sí** | — | pendiente |
| 17 | Toda respuesta de la API tiene esquema | 8 | Contract testing | `T` | Forma, no semántica | No | — | pendiente |
| 18 | Tipos consistentes | 8 | Type checking (pyright strict) | `A` | No ve el contenido real de las filas de SQLite | No | — | pendiente |
| 19 | La demo ejercita todas las comprobaciones de la puerta 3 | 10 | Integration testing con cobertura por comprobación | `T` | Los datos los fabrica el propio equipo: prueba el mecanismo, no el extractor real | No | — | pendiente |
| 20 | Pipeline completo con Claude Code real | 10 | Demonstration | `D` | Una novela corta no enseña lo que pasa hacia el capítulo 30 | **Sí** | — | pendiente |
| 21 | Un hecho no se modifica; revocarlo es un registro y relanzar desde antes lo deshace | 5 | Integration testing sobre los triggers y la reversión | `T` | Un `UPDATE` sobre las columnas muertas `parada_id` y `supersede_a` sigue permitido para que sus cascadas actúen | No: trigger + test de reversión | `tests/test_migraciones.py`, `tests/test_reanudacion.py::test_el_retcon_es_un_registro_y_relanzar_desde_antes_lo_deshace`, `tests/test_auditoria.py::test_hallazgo_21_…` | implementado |
| 22 | Dos entidades de una novela no comparten nombre normalizado | 5 | Integration testing (índice único) + unit testing de los esquemas | `T` | Nombres distintos para la misma entidad («la doctora» y «Kowalski») | No: índice + esquema | `tests/test_auditoria.py::test_hallazgo_20_…`, `tests/test_migraciones.py::test_con_nombres_duplicados_la_migracion_aborta_con_la_lista_y_no_toca_nada` | implementado |
| 23 | Una base del esquema 1 migra a la 2 sin perder datos, y con nombres duplicados aborta sin tocar nada | 5 | Integration testing | `T` | Solo los datos que el test fabrica; una base real con formas no previstas | **Sí** | `tests/test_migraciones.py` | implementado |

## Riesgos aceptados

| # | Propiedad | Por qué no se verifica | Qué lo hace tolerable |
| --- | --- | --- | --- |
| U2-1 | La estimación de tokens no se desvía del recuento real | Sigue sin tokenizador de referencia | Es U4 de spec1, con su mismo atenuante |
| U2-2 | El desempate por similitud de RF-CTX-08 mejora algo | No hay golden set que lo mida | El orden determinista con desempate por `id` es reproducible; se revisa cuando exista el golden set de la fase 7 |

## Validadores solitarios

Las filas 5, 7, 14, 16, 20 y 23 descansan en un solo método. Son las primeras que se revisan al cerrar cada fase, aunque estén en verde.
