# Verificación — Backend v1

Plan de verificación de [spec1.md](spec1.md). Métodos y etiquetas según [docs/validators.md](../docs/validators.md).

Actualizado el 22 de septiembre de 2026. Suite: 53 tests en verde. Las rutas de evidencia son relativas a `src/backend/`.

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
| 6 | Toda respuesta de la API está en OpenAPI | Contract testing | `T` | `tests/test_api.py::test_openapi_declara_todas_las_rutas` | implementado |
| 7 | La API no escribe salvo en `intencion` | Integration testing | `T` | `tests/test_api.py::test_la_api_solo_escribe_intenciones` | implementado |
| 8 | La conexión de lectura rechaza escrituras en el motor | Integration testing | `T` | `tests/test_api.py::test_la_conexion_de_lectura_rechaza_escrituras`, `tests/test_arquitectura.py::test_la_api_no_puede_escribir` | implementado |
| 9 | Encolar una intención no ejecuta nada | Integration testing | `T` | `tests/test_api.py::test_encolar_una_intencion_no_ejecuta_nada` | implementado |
| 10 | El `GET` de ejecución refleja el estado real | Integration testing | `T` | `tests/test_api.py::test_el_get_es_la_verdad` | implementado |
| 11 | Un lector nunca ve un capítulo sin sus hechos ni hechos sin texto | Property-based sobre `verificar_integridad()` | `T` | `tests/test_pipeline.py` (todas las pruebas la comprueban al terminar) | implementado |
| 12 | Invariantes del grafo: hecho con escena, pago posterior a siembra, conocimiento no anterior a su hecho | Property-based testing | `T` | `compartido/db.py::verificar_integridad` + aserciones en `tests/test_pipeline.py` | implementado |
| 13 | La puerta 1 para si una subtrama cierra tras el clímax | Unit testing | `T` | `tests/test_puerta_estructura.py::test_subtrama_que_cierra_tras_el_climax_para` | implementado |
| 14 | La puerta 1 solo avisa del anidamiento imperfecto y del final incompatible | Unit testing | `T` | `tests/test_puerta_estructura.py::test_anidamiento_imperfecto_solo_avisa`, `::test_final_incompatible_con_el_subgenero_avisa` | implementado |
| 15 | La puerta 2 detecta escena sin cambio de valor, sin POV, sin conflicto y sin lugar | Unit + mutation testing | `T` | `tareas/escaleta/puerta.py`; mutación en `tests/test_pipeline.py` | implementado |
| 16 | La puerta 3 detecta los siete tipos de conflicto | Mutation testing | `T` | `tests/test_puerta_continuidad.py` (una prueba por tipo) | implementado |
| 17 | La puerta 3 no produce falsos positivos con `supersede_a`, `analepsis` ni misma fecha en distinto momento | Unit testing | `T` | `tests/test_puerta_continuidad.py::test_supersede_no_es_contradiccion`, `::test_analepsis_no_es_retroceso_temporal`, `::test_misma_fecha_en_distinto_momento_no_es_ubicuidad` | implementado |
| 18 | Un conflicto de continuidad para el pipeline y no deja texto vigente | Integration testing | `T` | `tests/test_pipeline.py::test_un_conflicto_de_continuidad_para_y_no_deja_rastro` | implementado |
| 19 | La puerta 4 reintenta tres veces y escala a parada, con el criterio en el paquete | Integration testing | `T` | `tests/test_pipeline.py::test_la_puerta_4_reintenta_y_escala_a_parada` | implementado |
| 20 | La máquina de estados no admite transiciones fuera de la tabla | Model checking + unit testing | `A` + `T` | `orquestador/estados.py::TRANSICIONES`; rechazo comprobado en `tests/test_pipeline.py` | implementado |
| 21 | Ningún paquete supera el presupuesto; si no cabe, parada y no truncado | Property-based testing | `T` | `compartido/contexto/paquete.py::ajustar`; `tests/test_arquitectura.py::test_el_paquete_cabe_en_el_techo_de_contexto` | implementado |
| 22 | El orden de recorte es el que fija la arquitectura y los bloques fijos no se tocan | Unit testing | `T` | `tests/test_arquitectura.py::test_los_bloques_fijos_no_estan_en_el_orden_de_recorte`, `::test_el_capitulo_anterior_cae_antes_que_el_canon` | implementado |
| 23 | Revertir a N deja el grafo como al terminar N-1 | Property-based testing | `T` | `tests/test_pipeline.py::test_revertir_deja_el_grafo_como_estaba` | implementado |
| 24 | Tras revertir se puede reanudar y la novela termina | Integration testing | `T` | `tests/test_pipeline.py::test_se_puede_reanudar_y_termina` | implementado |
| 25 | `parar` detiene sin dejar un capítulo a medias | Integration testing | `T` | `tests/test_pipeline.py::test_parar_detiene_sin_dejar_capitulo_a_medias` | implementado |
| 26 | El pipeline completo corre sin Claude Code instalado | Integration testing | `T` | `tests/test_pipeline.py::test_pipeline_completo_sin_claude_code` | implementado |
| 27 | Las cinco puertas quedan registradas en `resultado_puerta` | Integration testing | `T` | `tests/test_pipeline.py::test_las_puertas_quedan_registradas` | implementado |
| 28 | Toda llamada se reconstruye desde `llamada_modelo` | Integration testing | `T` | `tests/test_api.py::test_la_traza_no_devuelve_el_prompt_salvo_que_se_pida` | implementado |
| 29 | Ningún veredicto de puerta cambia según el índice vectorial esté o no | Integration testing | `T` | `tests/test_puerta_continuidad.py::test_puerta_no_depende_del_indice` | implementado |
| 30 | El estado es append-only con escena de origen, y lo mutable se deriva | Static analysis sobre el esquema | `A` | `tests/test_arquitectura.py::test_el_estado_es_append_only_con_escena_de_origen`, `::test_lo_que_cambia_durante_la_redaccion_no_es_columna_mutable` | implementado |
| 31 | El texto se versiona y nunca se hace `UPDATE` sobre él | Static analysis | `A` | `tests/test_arquitectura.py::test_el_texto_se_versiona_y_no_se_actualiza` | implementado |
| 32 | WAL, `busy_timeout` y claves ajenas activas en toda conexión | Unit testing | `T` | `tests/test_arquitectura.py::test_wal_y_busy_timeout` | implementado |
| 33 | El agente no puede leer el repositorio ni buscar canon por su cuenta | Guardrail | `D` | Verificado a mano contra el CLI: `--allowedTools ""` y directorio de trabajo vacío. Sin prueba automática | **pendiente** |
| 34 | Dos workers no escriben a la vez | Integration testing | `T` | `orquestador/cola.py::tomar_cerrojo`. Sin prueba | **pendiente** |
| 35 | El worker caído a mitad de capítulo reanuda desde el último capítulo íntegro | Demonstration | `D` | `worker.py::recuperar`. Sin prueba | **pendiente** |
| 36 | El SSE recupera con `Last-Event-ID` sin huecos ni duplicados | Integration testing | `T` | `main.py::stream_eventos`. Sin prueba | **pendiente** |
| 37 | La salida de cada agente cumple sus criterios de terminación | Evals por skill | `T`, `I` con juez | Sin conjunto de referencia | **pendiente** |
| 38 | El extractor captura los hechos que un manuscrito de referencia fija | Evals con golden dataset | `I` | Sin dataset anotado | **pendiente** |
| 39 | El juez de oficio acierta contra escenas con veredicto conocido | Evals | `I` | Sin conjunto de referencia | **pendiente** |
| 40 | Ningún secreto en el repositorio ni en la base de datos | SAST | `A` | Sin escaneo automático | **pendiente** |
| 41 | Pipeline completo con Claude Code real sobre una novela corta | Demonstration | `D` | Probados por separado el puerto y el arquitecto. Falta la pasada entera | **pendiente** |

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

Las nueve filas pendientes no pesan lo mismo. Por orden de lo que más riesgo retira:

1. **Fila 41**, la pasada completa con Claude Code real. Es la única que puede destapar que el sistema no funciona de verdad; todo lo demás está probado contra el puerto falso.
2. **Fila 38**, las evals del extractor. La arquitectura lo señala como la pieza frágil y pide sus evals antes que ninguna otra.
3. **Filas 34, 35 y 36**: cerrojo, recuperación y reconexión. Son caminos de fallo que hoy solo están escritos.
4. **Filas 37 y 39**, evals del resto de agentes y del juez.
5. **Filas 33 y 40**, guardarraíl y escaneo de secretos.
