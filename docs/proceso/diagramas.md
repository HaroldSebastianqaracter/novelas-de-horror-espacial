# Diagramas

Los cuatro diagramas que pide la entrega. Los que ya viven en otro documento se enlazan en lugar de copiarse, para que no haya dos versiones.

## 1. Arquitectura del harness

Dos procesos sobre una sola base de datos. La API solo lee y encola intenciones; el worker es el único que escribe y en él vive el orquestador, que invoca a los agentes a través del puerto.

```mermaid
graph TD
  U["Autor / cliente HTTP"] -- "intenciones: crear, arrancar, parar, relanzar" --> API["API FastAPI<br/>solo lee"]
  API -- "INSERT en intencion" --> DB[("story bible<br/>SQLite + WAL")]
  API -- "SSE + GET" --> U
  DB -- "cola" --> O["Orquestador<br/>(worker, único escritor)"]
  O -- "paquete de contexto<br/>≤ 100.000 tokens" --> P["Puerto a Claude Code<br/>sin herramientas, skill como sistema"]
  P --> PL["Planner<br/>arquitecto · mundo · elenco · estructura · escaleta"]
  P --> WR["Writer<br/>redacción"]
  P --> EX["Extractor<br/>hechos a la story bible"]
  P --> ED["Editor<br/>oficio (juez)"]
  O -- "puertas 1, 2, 3 y 5: SQL<br/>puerta 4: mecánica + juez" --> DB
  O -- "texto, hechos, traza" --> DB
```

El bucle de capítulo, con las llamadas al agente fuera de las transacciones:

```mermaid
sequenceDiagram
  participant O as Orquestador
  participant DB as Story bible
  participant A as Agentes (Claude Code)
  O->>DB: lee el grafo y monta el paquete
  O->>A: writer (sin transacción abierta)
  A-->>O: prosa
  O->>A: extractor (sin transacción abierta)
  A-->>O: hechos, conocimiento, estados, eventos
  Note over O,DB: Tramo 2, BEGIN IMMEDIATE
  O->>DB: texto + hechos, y puerta 3 dentro
  alt conflicto de continuidad
    O->>DB: ROLLBACK y parada
  else limpio
    O->>DB: COMMIT
  end
  O->>A: editor: juicio de oficio (puerta 4)
  alt falla (máximo 3 intentos)
    O->>DB: revierte el capítulo y vuelve al writer con el criterio
  else pasa
    O->>DB: Tramo 3: capítulo completado y compilado
  end
```

El pipeline completo por fases está en [architecture.md](../architecture.md), «Fases del pipeline».

## 2. Máquina de estados

La máquina de estados que implementa el código (`orquestador/estados.py`) está dibujada en [specs/spec2.md](../../specs/spec2.md), requisito RF2-WK-06.

La máquina de la especificación TLA+ ([formal/tla/StoryMaker.tla](../../formal/tla/README.md), [spec-tla.md](../../specs/spec-tla.md)) es esa misma máquina con dos añadidos:

- lo que la mueve: las intenciones del autor, las puertas, `parar` y la caída del worker;
- las dos transiciones del cambio del lector ([spec3](../../specs/spec3.md), RF3-CAM-06).

Las etiquetas son los sucesos de `estados.py` y, entre paréntesis, la acción del modelo que los dispara. La correspondencia de cada acción con su fichero y su función está en el [README de formal/tla](../../formal/tla/README.md), «Correspondencia con el código».

```mermaid
stateDiagram-v2
  [*] --> configurada
  configurada --> planificando: arrancar (Arrancar, Derivar)
  planificando --> escaletando: puerta_1_ok (PlanP1)
  escaletando --> generando: puerta_2_ok (EscP2)
  generando --> completada: terminado_limpio (P5, LectorAplicar)
  generando --> completada_con_avisos: terminado_con_avisos (P5, LectorAplicar)

  planificando --> parada: conflicto, puerta 1 (PlanP1)
  escaletando --> parada: conflicto, puerta 2 dos veces (EscP2)
  generando --> parada: conflicto, puerta 3, oficio o presupuesto (Tramo12, Tramo3)

  parada --> planificando: rehacer, estructura (Rehacer)
  parada --> escaletando: rehacer, escaleta (Rehacer)
  parada --> generando: aceptar_retcon, dar_por_sabido o relanzar (ResolverContinuidad, Relanzar)

  planificando --> detenida: parar (DetenerRun, Recuperar)
  escaletando --> detenida: parar (DetenerRun, Recuperar)
  generando --> detenida: parar (DetenerRun, Recuperar)
  detenida --> planificando: arrancar_planificacion (Derivar)
  detenida --> escaletando: arrancar_escaleta (ChkEsc)
  detenida --> generando: arrancar_generacion o relanzar (ChkGen, Relanzar)

  planificando --> error: error (FallarRun)
  escaletando --> error: error (FallarRun)
  generando --> error: error (FallarRun)
  parada --> error: error
  error --> planificando: arrancar_planificacion (Derivar)
  error --> escaletando: arrancar_escaleta (ChkEsc)
  error --> generando: arrancar_generacion o relanzar (ChkGen, Relanzar)

  completada --> generando: relanzar (Relanzar) o cambio_lector (CambioDelLector)
  completada_con_avisos --> generando: relanzar (Relanzar) o cambio_lector (CambioDelLector)
```

Dentro de `generando` está el bucle de capítulo, que es donde viven los reintentos y la reanudación:

```mermaid
stateDiagram-v2
  [*] --> Bucle: ChkGen
  Bucle --> Tramo12: siguiente capítulo, puertas 1 y 2 vigentes
  Tramo12 --> Tramo3: texto y hechos entran y la puerta 3 pasa (capítulo a medias)
  Tramo3 --> Bucle: la puerta 4 pasa (capítulo completado y aprobado)
  Tramo3 --> Tramo12: la puerta 4 falla y quedan intentos (se revierte)
  Tramo3 --> [*]: la puerta 4 falla por última vez, parada de oficio
  Tramo3 --> RevertirTrasParada: el paquete del oficio no cabe, parada de presupuesto
  RevertirTrasParada --> [*]: el finally revierte el capítulo
  Tramo12 --> [*]: parada de continuidad o de presupuesto
  Bucle --> P5: no quedan capítulos
  P5 --> [*]: completada y versión publicada
  note right of Tramo3
    Una caída aquí deja el capítulo a medias.
    Recuperar lo revierte y deja la ejecución detenida.
  end note
  note right of RevertirTrasParada
    Una caída aquí, con la ejecución ya en parada,
    dejaba el capítulo a medias (tercer contraejemplo).
  end note
```

## 3. Esquema SQLite (núcleo de la story bible)

La base tiene cincuenta y nueve tablas y ocho vistas; esto es el núcleo que consultan las puertas. El inventario completo por grupos está en [architecture.md](../architecture.md), «Persistencia», y el DDL en `src/backend/compartido/esquema.sql` más las migraciones de `compartido/migraciones/`.

```mermaid
erDiagram
  novela ||--o{ capitulo : tiene
  novela ||--o{ personaje : tiene
  novela ||--o{ lugar : tiene
  capitulo ||--o{ escena : contiene
  escena }o--|| lugar : ocurre_en
  escena }o--|| personaje : pov
  escena ||--o{ escena_personaje : reparto
  personaje ||--o{ escena_personaje : aparece
  escena ||--o{ hecho : establece
  hecho |o--o| hecho : supersede_a
  hecho ||--o| hecho_revocacion : revocado_por
  hecho ||--o{ estado_conocimiento : sabido_por
  hecho ||--o{ uso_conocimiento : usado_por
  hecho ||--o{ hecho_uso : usado_en
  escena ||--o{ hecho_uso : usa
  personaje ||--o{ estado_personaje : evoluciona
  escena ||--o{ evento : dramatiza
  linea_de_tiempo ||--o{ evento : ordena
  escena ||--o{ escena_texto : versiones
  capitulo ||--o{ capitulo_compilado : versiones
  novela ||--o{ novela_version : publica
  novela_version ||--o{ novela_version_capitulo : copia

  hecho {
    int id
    int escena_id
    text sujeto_tipo
    text sujeto_clave
    text atributo_clave
    text valor
    text cita
    int supersede_a
  }
  estado_conocimiento {
    int personaje_id
    int hecho_id
    int escena_id
    text postura
    text via
  }
  estado_personaje {
    int personaje_id
    int escena_id
    text condicion
    text salud_fisica
  }
  hecho_uso {
    int hecho_id
    int escena_id
    text via
    text cita
  }
  evento {
    int escena_id
    text fecha_interna
    int dia
    int orden_interno
    int dramatizado
  }
  novela_version {
    int numero
    text motivo
    text titulo
    text dedicatoria
  }
  escena_texto {
    int escena_id
    int version
    text estado
    text texto
  }
```

Tres reglas sostienen el esquema: **todo el estado es append-only y lleva su escena de origen** (revertir es borrar por escena), **el texto se versiona** y nunca se actualiza, y **lo que cambia se deriva en vistas** (`hecho_vigente`, `siembra_vigente`, `hilo_vigente`, `escena_ordinal`, y desde el bloque 3 `hecho_escena`, `personaje_nacimiento`, `cronologia` y `cronologia_personaje`). Las versiones de la novela son la excepción deliberada: copian el texto, porque tienen que sobrevivir a que se rehaga la escaleta.

## 4. Validadores y su punto de ejecución

| Validador | Tipo | Dónde se ejecuta | Si falla |
| --- | --- | --- | --- |
| Salida de cada agente contra su schema | Programático | Puerto y orquestador, tras cada llamada | Una repetición con el error adjunto; después, error |
| El agente no usa herramientas | Programático | Puerto, tras cada llamada | Error de puerto (`AgenteUsoHerramientas`) |
| Puerta 1: estructura (protagonista, oponente, hilo principal, giros obligatorios en orden, subtramas que cierran antes, final compatible) | Programático | Orquestador, tras el estructurador | Parada; se rehace la estructura |
| Puerta 2: escaleta (cada escena cambia un valor, tiene conflicto y lugar, POV en el reparto, longitudes en rango) | Programático | Orquestador, tras la escaleta | Un reintento; después, parada y se rehace |
| Guarda de vigencia de las puertas 1 y 2 | Programático | Al empezar cada capítulo | Error: no se genera un capítulo sin plan aprobado |
| Puerta 3: continuidad (contradicción factual, conocimiento no adquirido, presencia imposible, objeto sin traslado, coherencia temporal, día contra orden, entidad fuera de canon) | Programático | Tramo 2, dentro de la transacción que inserta texto y hechos | ROLLBACK y parada |
| Búsquedas dirigidas sobre la prosa (nombre sin registro, cifra sin hecho, muerto nombrado) y descartes del extractor | Programático | Tramo 2, como avisos de la puerta 3 | Aviso en el informe |
| Puerta 4, mecánica (tics prohibidos; palabras filtro, adverbios de atribución y verbos de habla como avisos) | Programático | Tras la puerta 3 limpia | El capítulo vuelve al writer |
| Puerta 4, juicio de oficio (nueve criterios con evidencia; el noveno, las cuentas contra el canon) | Semántico (LLM-as-judge) | Tras la mecánica | El capítulo vuelve al writer; al tercer fallo, parada |
| Puerta 5: global (siembras sin pagar, pago sin siembra, hilos sin cerrar o fuera de orden, latencia de hilos) | Programático | Tras el último capítulo | Aviso: la novela termina `completada_con_avisos` |
| Integridad del grafo (`verificar_integridad`) | Programático | Al recuperar un worker caído, y en los tests | Se revierte el capítulo a medias |
| Evals del extractor (recall contra capítulo anotado) | Eval | Desarrollo, `pytest -m agente` | — |

*Pendientes para la entrega* (ver el plan): nombres exactos, longitud real del capítulo, cobertura de la personalización, palabras prohibidas, validación visual con browser MCP, Lean 4 y TLA+, puntuación del juez y revisión humana. Todos acaban enviando su resultado a Langfuse como score.
