# Verificación — Backend v1

Plan de verificación de [spec1.md](spec1.md). Métodos y etiquetas según [docs/validators.md](../docs/validators.md).

Actualizado el 23 de septiembre de 2026. Suite: 325 tests en verde, 1 marcado `modelo` y 3 marcados `agente`; `ruff` limpio y `pyright` estricto en cero sobre `src/backend` sin los tests. Las rutas de evidencia son relativas a `src/backend/`.

> **Filas degradadas el 23 de septiembre de 2026.** La auditoría de ese día reprodujo fallos en siete filas que estaban en `implementado`: 11, 16, 17, 21, 25, 27 y 35. Pasan a `fallando` ya, y no cuando se arreglen, porque un plan que dice «implementado» sobre un fallo reproducido es justo lo que la sección siguiente llama la forma más común de mentir. Cada una vuelve a `implementado` en la fase de [spec2-plan.md](spec2-plan.md) que la corrige, y su propiedad endurecida vive en [spec2-verification.md](spec2-verification.md).

## Cómo leer la tabla

**Evidencia** apunta a dónde vive la comprobación. **Estado** es `implementado`, `pendiente` o `fallando`. Una fila sin evidencia lleva `pendiente` aunque la propiedad se cumpla hoy: cumplirse y estar comprobado no son lo mismo, y confundirlos es la forma más común de que un plan de verificación mienta.

## Propiedades verificadas

| # | Propiedad | Método | Tag | Evidencia | Estado |
| --- | --- | --- | --- | --- | --- |
| 1 | Ninguna tarea importa de otra tarea | Static analysis sobre el árbol de imports | `A` | `tests/test_arquitectura.py::test_una_tarea_no_importa_de_otra` | implementado |
| 2 | FastAPI solo aparece en el borde HTTP | Static analysis | `A` | `tests/test_arquitectura.py::test_fastapi_solo_en_los_router` | implementado |
| 3 | La API no alcanza el puerto ni el orquestador | Static analysis | `A` | `tests/test_arquitectura.py::test_los_router_no_invocan_al_modelo_ni_orquestan` | implementado |
| 4 | La lista de carpetas es la lista de agentes | Static analysis | `A` | `tests/test_arquitectura.py::test_la_lista_de_carpetas_es_la_lista_de_agentes` | implementado |
| 5 | Cada agente tiene su skill, con las secciones que la spec exige | Unit testing | `T` | `tests/test_arquitectura.py::test_cada_agente_de_la_v1_tiene_su_skill`, `::test_las_skills_tienen_la_forma_que_pide_la_spec` | implementado |
| 6 | Toda respuesta de la API está en OpenAPI, con esquema | Contract testing | `T` | `tests/test_api.py::test_openapi_declara_todas_las_rutas`, `::test_ninguna_respuesta_es_un_objeto_sin_esquema`, `::test_el_contrato_no_cambia_sin_revisarlo` (snapshot `tests/openapi.json`). Reforzada por spec2, fase 8 | implementado |
| 7 | La API no escribe salvo en `intencion` | Integration testing | `T` | `tests/test_api.py::test_la_api_solo_escribe_intenciones` | implementado |
| 8 | La conexión de lectura rechaza escrituras en el motor | Integration testing | `T` | `tests/test_api.py::test_la_conexion_de_lectura_rechaza_escrituras`, `tests/test_arquitectura.py::test_la_api_no_puede_escribir` | implementado |
| 9 | Encolar una intención no ejecuta nada | Integration testing | `T` | `tests/test_api.py::test_encolar_una_intencion_no_ejecuta_nada` | implementado |
| 10 | El `GET` de ejecución refleja el estado real | Integration testing | `T` | `tests/test_api.py::test_el_get_es_la_verdad` | implementado |
| 11 | Un lector nunca ve un capítulo sin sus hechos ni hechos sin texto | Property-based sobre `verificar_integridad()` + integration testing por tipo de salida | `T` | Regla `estado_en_capitulo_no_completado` (RF2-PER-07) en `compartido/db.py`; `tests/test_capitulo_a_medias.py`; `tests/test_auditoria.py::test_hallazgo_05_…`, `::test_hallazgo_06_…`. Corregida por spec2, fase 1 | implementado |
| 12 | Invariantes del grafo: hecho con escena, pago posterior a siembra, conocimiento no anterior a su hecho | Property-based testing | `T` | `compartido/db.py::verificar_integridad` + aserciones en `tests/test_pipeline.py` | implementado |
| 13 | La puerta 1 para si una subtrama cierra tras el clímax | Unit testing | `T` | `tests/test_puerta_estructura.py::test_subtrama_que_cierra_tras_el_climax_para` | implementado |
| 14 | La puerta 1 solo avisa del anidamiento imperfecto y del final incompatible | Unit testing | `T` | `tests/test_puerta_estructura.py::test_anidamiento_imperfecto_solo_avisa`, `::test_final_incompatible_con_el_subgenero_avisa` | implementado |
| 15 | La puerta 2 detecta escena sin cambio de valor, sin POV, sin conflicto y sin lugar | Unit + mutation testing | `T` | `tareas/escaleta/puerta.py`; mutación en `tests/test_pipeline.py` | implementado |
| 16 | La puerta 3 detecta los siete tipos de conflicto | Mutation testing | `T` | `tests/test_puerta_continuidad.py` (una prueba por tipo; la muerte, por `condicion`; y la última condición manda); `tests/test_auditoria.py::test_hallazgo_15_…` (sin `orden_interno` no se valida). Corregida por spec2, fase 5 | implementado |
| 17 | La puerta 3 no produce falsos positivos con `supersede_a`, `analepsis` ni misma fecha en distinto momento | Unit testing | `T` | `tests/test_puerta_continuidad.py` (cadena de tres supersesiones, tildes y mayúsculas, la ene sí distingue, cada par una vez, muerte en analepsis); `tests/test_auditoria.py::test_hallazgo_07_…`, `::test_hallazgo_08_…`, `::test_hallazgo_16_…`. Corregida por spec2, fase 5 | implementado |
| 18 | Un conflicto de continuidad para el pipeline y no deja texto vigente | Integration testing | `T` | `tests/test_pipeline.py::test_un_conflicto_de_continuidad_para_y_no_deja_rastro` | implementado |
| 19 | La puerta 4 reintenta tres veces y escala a parada, con el criterio en el paquete | Integration testing | `T` | `tests/test_pipeline.py::test_la_puerta_4_reintenta_y_escala_a_parada` | implementado |
| 20 | La máquina de estados no admite transiciones fuera de la tabla | Model checking + unit testing | `A` + `T` | `orquestador/estados.py::TRANSICIONES` y `::RESOLUCIONES`; recorrido exhaustivo en `tests/test_estados_exhaustivo.py`; rechazos en `tests/test_reanudacion.py`. Ampliada por spec2, fase 2 | implementado |
| 21 | Ningún paquete supera el presupuesto; si no cabe, parada y no truncado | Property-based testing | `T` | `compartido/contexto/paquete.py::ajustar`; `tests/test_paquete.py` (hypothesis, 300 ejemplos, y una mutación que la propiedad detecta); `tests/test_auditoria.py::test_hallazgo_04_…`, `::test_hallazgo_10_…`. Corregida por spec2, fase 4 | implementado |
| 22 | El orden de recorte es el que fija la arquitectura y los bloques fijos no se tocan | Unit testing | `T` | `tests/test_arquitectura.py::test_los_bloques_fijos_no_estan_en_el_orden_de_recorte`, `::test_el_capitulo_anterior_cae_antes_que_el_canon` | implementado |
| 23 | Revertir a N deja el grafo como al terminar N-1 | Property-based testing | `T` | `tests/test_pipeline.py::test_revertir_deja_el_grafo_como_estaba` | implementado |
| 24 | Tras revertir se puede reanudar y la novela termina | Integration testing | `T` | `tests/test_pipeline.py::test_se_puede_reanudar_y_termina` | implementado |
| 25 | `parar` detiene sin dejar un capítulo a medias | Integration testing | `T` | `tests/test_pipeline.py::test_parar_detiene_sin_dejar_capitulo_a_medias` (antes de generar) y `tests/test_auditoria.py::test_hallazgo_05_…` (durante el oficio). Corregida por spec2, fase 1 | implementado |
| 26 | El pipeline completo corre sin Claude Code instalado | Integration testing | `T` | `tests/test_pipeline.py::test_pipeline_completo_sin_claude_code` | implementado |
| 27 | Las cinco puertas quedan registradas en `resultado_puerta` | Integration testing + contract testing | `T` | `tests/test_pipeline.py::test_las_puertas_quedan_registradas`; la puerta 4 con mecánica y juicio en un registro: `tests/test_traza.py::test_toda_parada_de_oficio_tiene_la_puerta_4_en_falla`, `tests/test_auditoria.py::test_hallazgo_09_…`. Corregida por spec2, fase 6 | implementado |
| 28 | Toda llamada se reconstruye desde `llamada_modelo` | Integration testing | `T` | `tests/test_api.py::test_la_traza_no_devuelve_el_prompt_salvo_que_se_pida` | implementado |
| 29 | Ningún veredicto de puerta cambia según el índice vectorial esté o no | Integration testing | `T` | `tests/test_puerta_continuidad.py::test_puerta_no_depende_del_indice`; con el índice activo y el modelo sin cargar, el pipeline termina y la traza avisa: `tests/test_indice.py::test_si_el_modelo_no_carga_el_pipeline_sigue_y_la_traza_lo_avisa` | implementado |
| 30 | El estado es append-only con escena de origen, y lo mutable se deriva | Static analysis sobre el esquema + integration testing de los triggers | `A` + `T` | `tests/test_arquitectura.py::test_el_estado_es_append_only_con_escena_de_origen`, `::test_lo_que_cambia_durante_la_redaccion_no_es_columna_mutable`; `tests/test_migraciones.py::test_un_hecho_no_se_modifica` (el trigger `hecho_inmutable`), `tests/test_auditoria.py::test_hallazgo_21_…` | implementado |
| 31 | El texto se versiona y nunca se hace `UPDATE` sobre él | Static analysis | `A` | `tests/test_arquitectura.py::test_el_texto_se_versiona_y_no_se_actualiza` | implementado |
| 32 | WAL, `busy_timeout` y claves ajenas activas en toda conexión | Unit testing | `T` | `tests/test_arquitectura.py::test_wal_y_busy_timeout` | implementado |
| 33 | El agente no puede leer el repositorio ni buscar canon por su cuenta | Guardrail | `D` | Parte automática (spec2, fase 6): `--tools ""`, `--allowedTools ""`, `--strict-mcp-config` y directorio vacío; una respuesta con permisos denegados o más de dos turnos es error. `tests/test_traza.py` contra un binario falso. Falta observarlo contra el CLI real, que es la evidencia de la etiqueta `D`: va con la fila 41 | **pendiente** |
| 34 | Dos workers no escriben a la vez | Integration testing con dos procesos reales | `T` | `tests/test_cerrojo.py`: latido en un hilo propio, fencing dentro de `BEGIN IMMEDIATE`, robo del cerrojo a mitad del pipeline sin ninguna escritura posterior. Corregida por spec2, fase 3 | implementado |
| 35 | El worker caído a mitad de capítulo reanuda desde el último capítulo íntegro | Integration testing con una caída real del proceso (antes `D`) | `T` | `tests/test_auditoria.py::test_hallazgo_06_…`: el subproceso sale con `os._exit` durante el oficio y `recuperar()` revierte. Corregida por spec2, fase 1 | implementado |
| 36 | El SSE recupera con `Last-Event-ID` sin huecos ni duplicados | Integration testing | `T` | `main.py::stream_eventos`. Sin prueba | **pendiente** |
| 37 | La salida de cada agente cumple sus criterios de terminación | Evals por skill | `T`, `I` con juez | Sin conjunto de referencia | **pendiente** |
| 38 | El extractor captura los hechos que un manuscrito de referencia fija | Evals con golden dataset | `I` | Capítulo anotado a mano y puntuador determinista de recall por tipo de registro en `tests/test_evals_extraccion.py` (fila 32 de spec2). Pasada contra el extractor real (marcada `agente`) ejecutada el 23-09-2026: recall 15/15. Un solo capítulo de dos escenas: el dataset tiene que crecer antes de fiarse del número | implementado |
| 39 | El juez de oficio acierta contra escenas con veredicto conocido | Evals | `I` | Sin conjunto de referencia | **pendiente** |
| 40 | Ningún secreto en el repositorio ni en la base de datos | SAST | `A` | Sin escaneo automático | **pendiente** |
| 41 | Pipeline completo con Claude Code real sobre una novela corta | Demonstration | `D` | Pasada del 23-09-2026: 2 de 4 capítulos completos con Claude Code real; parada en el capítulo 3 por tres huecos de diseño (fila 20 y riesgos U2-4 a U2-6 de spec2-verification) | **pendiente** |

## Riesgos aceptados

| # | Propiedad | Por qué no se verifica | Qué lo hace tolerable |
| --- | --- | --- | --- |
| U1 | El clímax responde la pregunta dramática | Exige un agente juez sobre estructura, fuera de la v1 | La parte determinista de la puerta 1 sí corre, y el autor puede leer la estructura por la API antes de que baje a capítulos |
| U2 | La prosa respeta las reglas de la amenaza y los límites técnicos | Exige interpretar el texto, y no hay juez de canon en la v1 | Las reglas van en el paquete del redactor y en el del juez de oficio; el revisor humano las coteja en las paradas |
| U3 | Curva de tensión en lectura continua | Solo se manifiesta leyendo seguido | Es el mismo riesgo que validators.md ya declara para «si da miedo» |
| U4 | La estimación de tokens se desvía del recuento real | Sin tokenizador de referencia en la v1 | Margen del 10 % y 26.000 tokens de reserva; la traza guarda los tokens por bloque para medir la desviación |
| U5 | Claude Code compacta o trunca dentro de una llamada | No es observable desde fuera salvo por sus metadatos | Sin herramientas y con el paquete bajo presupuesto no debería ocurrir; el puerto lo registra si ocurre |
| U6 | Un hecho mal extraído degrada la coherencia sin que ninguna puerta lo note | Es la pieza frágil declarada en la arquitectura: una puerta no puede echar de menos un hecho que nadie registró | Las evals del extractor van antes que las de cualquier otro agente (fila 38); las paradas hacen visible la fricción pronto |
| U7 | La normalización de atributos produce sinónimos que la puerta 3 no compara | Sin ontología cerrada de atributos | El paquete entrega al extractor los atributos existentes por sujeto; la eval del extractor medirá la tasa de sinónimos |
| U8 | Los fragmentos recuperados son los que el redactor necesitaba | La relevancia semántica no tiene respuesta correcta única | El bloque es pequeño y llega como referencia, no como instrucción; la selección obligatoria de canon sigue siendo determinista |
| U9 | Calidad literaria del manuscrito | Un manuscrito puede pasar las cinco puertas y ser mediocre | Ninguna puerta sustituye a la lectura de un editor. Declarado ya en validators.md |

## Qué falta y en qué orden

Las filas en `fallando` las cierra [spec2-plan.md](spec2-plan.md), fase por fase. Las nueve pendientes no pesan lo mismo. Por orden de lo que más riesgo retira:

1. **Fila 41**, la pasada completa con Claude Code real. Es la única que puede destapar que el sistema no funciona de verdad; todo lo demás está probado contra el puerto falso.
2. **Fila 38**, las evals del extractor. La arquitectura lo señala como la pieza frágil y pide sus evals antes que ninguna otra.
3. **Filas 34, 35 y 36**: cerrojo, recuperación y reconexión. Son caminos de fallo que hoy solo están escritos.
4. **Filas 37 y 39**, evals del resto de agentes y del juez.
5. **Filas 33 y 40**, guardarraíl y escaneo de secretos.
