# Diagrama de flujo — Harness Generador de Novelas de Terror Espacial

Fuente: `especificacion-funcional-harness-novela-terror.md` v1.0 y `especificacion-tecnica-harness-novela-terror.md` v1.0.

El **0** es el resumen para explicar el sistema a alguien de cero. Los otros cuatro se reparten el detalle: el **1** es el flujo de control (qué corre y en qué orden), el **2** el flujo de datos (quién lee qué — el invariante central del diseño), el **3** el detalle de una iteración y el **4** la máquina de estados que sostiene la reanudación.

## 0. Resumen — el flujo en tres etapas

```mermaid
flowchart LR
    IDEA(["Una idea<br/>+ ejemplos del género"]) --> PREP

    PREP["<b>1 · PREPARAR</b><br/>Convierte la idea en premisa,<br/>sinopsis, escaleta de capítulos<br/>y fichas de personajes"]
    PREP --> CAP

    CAP["<b>2 · ESCRIBIR UN CAPÍTULO</b><br/>Un agente redacta.<br/>Otro lo lee y anota qué cambió:<br/>quién sabe qué, qué pasó, dónde"]

    CAP --> TOCA{"¿toca revisión?<br/>cada 8 capítulos"}
    TOCA -->|"no"| MAS
    TOCA -->|"sí"| QA

    QA["<b>3 · REVISAR</b><br/>Busca contradicciones<br/>y recursos ya repetidos"]
    QA --> HALL{"¿hay<br/>contradicciones?"}
    HALL -->|"no"| MAS
    HALL -->|"sí"| HUMANO["Se detiene.<br/>Un humano revisa"]
    HUMANO --> MAS

    MAS{"¿faltan<br/>capítulos?"}
    MAS -->|"sí, siguiente capítulo"| CAP
    MAS -->|"no"| FIN(["Novela completa"])

    NOTA["<b>La clave del diseño</b><br/>El que escribe nunca relee los capítulos anteriores:<br/>solo mira las fichas y un resumen corto.<br/>Por eso el costo no crece con la novela."]
    CAP -.- NOTA

    classDef etapa fill:#3a2350,stroke:#b07cc6,stroke-width:2px,color:#f2e9f7
    classDef borde fill:#1f4030,stroke:#66c08a,stroke-width:2px,color:#e6f7ee
    classDef humano fill:#4a3a1c,stroke:#d4b05c,stroke-width:2px,color:#faf3e2
    classDef nota fill:#14243a,stroke:#4f7ea8,stroke-width:1.5px,color:#cfe3f2

    class PREP,CAP,QA etapa
    class IDEA,FIN borde
    class HUMANO humano
    class NOTA nota
```

## 1. Flujo de control — pipeline de 8 fases

```mermaid
flowchart TD
    subgraph SETUP["Preparación · fases 0 a 4 — una sola vez por novela"]
        direction LR
        EJEMPLOS["Ejemplos de referencia<br/>space horror"] --> F0["Fase 0<br/>Destilado de estilo<br/>RF-00.1 · RF-00.2"]
        F0 --> STYLE[/"style_guide.md"/]
        IDEA["Idea del usuario<br/>texto libre"] --> F1["Fase 1<br/>Concepto<br/>RF-01.1"]
        F1 --> PREMISA[/"premisa.md<br/>título · logline · premisa"/]
        PREMISA --> F2["Fase 2<br/>Sinopsis 3 actos<br/>RF-02.1 · RF-02.2"]
        F2 --> ACTOS[/"tres_actos.md<br/>gancho · medio · clímax"/]
        ACTOS --> F3["Fase 3<br/>Escaleta<br/>RF-03.1 · RF-03.2"]
        PREMISA --> F3
        F3 --> OUTLINE[/"capitulos.json<br/>30-50 entradas · tensión 1-5"/]
        OUTLINE --> F4["Fase 4<br/>Bases de estado<br/>RF-04.1 · 04.2 · 04.3"]
        ACTOS --> F4
        F4 --> BASES[/"personajes.json<br/>mundo.json<br/>continuidad.json"/]
    end

    SETUP --> CKPT{"checkpoint · manifest.json<br/>¿dónde quedó la tanda?"}
    CKPT -->|"pausado_por_qa"| ESPERA["Espera resolución humana<br/>EX-02"]
    CKPT -->|"en_progreso"| E0

    subgraph LOOP["Loop por capítulo N · fases 5 a 7"]
        direction TB
        E0{"¿existe<br/>capitulos[N]?"}
        E0 -->|no| EX03["EX-03 · OutlineFaltanteError<br/>no se gasta generación"]
        E0 -->|sí| F51["Fase 5.1 — Ensamblar contexto<br/>RF-05.1"]

        F51 --> TOK{"¿excede<br/>max_tokens_contexto_escritor?"}
        TOK -->|sí| RECORTE["Recortar resumen_rodante · EX-04<br/>nunca continuidad ni personajes"]
        RECORTE --> TOK2{"¿aún excede?"}
        TOK2 -->|sí| EX04["EX-04 · ContextoExcedidoError<br/>detiene y reporta"]
        TOK2 -->|no| ESCRITOR
        TOK -->|no| ESCRITOR["Fase 5.2 — Agente ESCRITOR<br/>modelo capaz · RF-05.2<br/>SIN acceso a 05_manuscrito/"]

        ESCRITOR --> CAPN[/"05_manuscrito/cap_N.md<br/>RF-05.4"/]
        CAPN --> EXTRACTOR["Fase 6 — Agente EXTRACTOR<br/>modelo económico · RF-06.1<br/>lee SOLO cap_N.md"]
        EXTRACTOR --> DELTA[/"delta<br/>personajes · hechos_nuevos<br/>resumen_corto"/]

        DELTA --> VALID{"¿valida contra<br/>esquema Pydantic?"}
        VALID -->|no| EX01["EX-01 · EstadoInvalidoError<br/>no persiste artefacto corrupto"]
        VALID -->|sí| APLICA["Aplicar deltas al estado<br/>RF-06.2 · 06.3 · 06.4"]

        APLICA --> CIERRE["marcar_capitulo_cerrado(N)"]
        CIERRE --> QACAD{"¿N múltiplo<br/>de cadencia_qa?"}
        QACAD -->|no| SIG["N = N + 1"]
        QACAD -->|sí| QA["Fase 7 — Agente QA<br/>RF-07.1 · 07.2 · 07.3<br/>único con lectura amplia del manuscrito"]

        QA --> REPORTE[/"06_qa/reportes/qa_cap_N.md"/]
        REPORTE --> CONTRA{"¿tiene_contradicciones?"}
        CONTRA -->|sí| PAUSA["pausar_por_qa<br/>RF-07.4 · EX-02"]
        CONTRA -->|no| SIG
        SIG --> FIN{"¿N > total_capitulos?"}
        FIN -->|no| E0
    end

    FIN -->|sí| DONE(["Novela completa<br/>estado = completo"])
    PAUSA --> HUMANO["Usuario humano revisa<br/>y marca el reporte resuelto"]
    ESPERA --> HUMANO
    HUMANO --> CKPT

    classDef agente fill:#3a2350,stroke:#b07cc6,stroke-width:2px,color:#f2e9f7
    classDef estado fill:#1e3247,stroke:#6ca6c6,stroke-width:1.5px,color:#e8f2f8
    classDef error fill:#4a1f1f,stroke:#d97777,stroke-width:2px,color:#fbeaea
    classDef humano fill:#4a3a1c,stroke:#d4b05c,stroke-width:2px,color:#faf3e2
    classDef ok fill:#1f4030,stroke:#66c08a,stroke-width:2px,color:#e6f7ee

    class F0,F1,F2,F3,F4,ESCRITOR,EXTRACTOR,QA agente
    class STYLE,PREMISA,ACTOS,OUTLINE,BASES,CAPN,DELTA,REPORTE estado
    class EX01,EX03,EX04,PAUSA error
    class IDEA,EJEMPLOS,HUMANO,ESPERA humano
    class DONE ok
```

## 2. Flujo de datos — quién lee qué

El punto del harness es que el manuscrito acumulado nunca vuelve a entrar al contexto de generación. Este diagrama muestra las fronteras de lectura (INV-01 a INV-05): es lo que hay que poder auditar en el código.

```mermaid
flowchart LR
    subgraph ESTADO["Estado persistente · crece poco, se relee siempre"]
        direction TB
        S1[/"style_guide.md"/]
        S2[/"tres_actos.md"/]
        S3[/"capitulos.json[N]"/]
        S4[/"personajes.json"/]
        S5[/"continuidad.json<br/>append-only · INV-03"/]
        S6[/"resumen_rodante.md<br/>ventana deslizante 2-3 caps"/]
    end

    ESC["ESCRITOR<br/>RF-05.2"]
    EXT["EXTRACTOR<br/>RF-06.1"]
    AQA["QA<br/>RF-07.1"]
    RECURSOS[/"recursos_usados.json"/]

    subgraph MANUSCRITO["05_manuscrito/ · crece linealmente, casi nunca se relee"]
        direction TB
        M1["cap_1.md"]
        M2["cap_2.md … cap_N-1.md"]
        MN["cap_N.md"]
    end

    S1 --> ESC
    S2 --> ESC
    S3 --> ESC
    S4 --> ESC
    S5 --> ESC
    S6 --> ESC
    ESC -->|"escribe"| MN

    MN -->|"un solo capítulo<br/>INV-02"| EXT
    EXT --> D[/"delta"/]
    D -->|"personajes"| S4
    D -->|"hechos_nuevos"| S5
    D -->|"resumen_corto"| S6

    S5 --> AQA
    RECURSOS --> AQA
    M1 -.->|"muestra: últimos<br/>cadencia_qa capítulos<br/>INV-05"| AQA
    M2 -.-> AQA
    MN -.-> AQA

    M1 -. "INV-01 · prohibido" .-x ESC
    M2 -.-x ESC

    classDef agente fill:#3a2350,stroke:#b07cc6,stroke-width:2px,color:#f2e9f7
    classDef estado fill:#1e3247,stroke:#6ca6c6,stroke-width:1.5px,color:#e8f2f8
    classDef texto fill:#33261a,stroke:#c08a5c,stroke-width:1.5px,color:#f7ece2

    class ESC,EXT,AQA agente
    class S1,S2,S3,S4,S5,S6,RECURSOS,D estado
    class M1,M2,MN texto
```

## 3. Secuencia de un capítulo (fases 5-6-7)

```mermaid
sequenceDiagram
    autonumber
    participant O as Orquestador
    participant R as Repository
    participant E as Agente Escritor
    participant X as Agente Extractor
    participant Q as Agente QA
    participant H as Usuario humano

    O->>R: leer_outline_entry(N)
    alt entrada faltante
        R-->>O: None
        O->>O: OutlineFaltanteError (EX-03)
    else entrada válida
        R-->>O: capitulos[N]
        O->>O: ensamblar_contexto(N) — RF-05.1
        Note over O: verifica max_tokens_contexto_escritor,<br/>recorta el resumen rodante si hace falta (EX-04)
        O->>E: generar_capitulo(contexto)
        E-->>O: borrador (palabras_por_capitulo ±20%)
        O->>R: guardar_capitulo(N) — RF-05.4
        O->>X: extraer(cap_N.md) — RF-06.1
        X-->>O: delta
        O->>R: validar contra esquema Pydantic
        alt validación falla
            R-->>O: EstadoInvalidoError (EX-01)
            O->>O: detiene el loop, capítulo N queda pendiente
        else validación ok
            O->>R: aplicar deltas (RF-06.2 / 06.3 / 06.4)
            O->>R: marcar_capitulo_cerrado(N)
            opt N múltiplo de cadencia_qa
                O->>Q: ejecutar_corte(N) — RF-07.1
                Q-->>O: ReporteQA
                alt tiene_contradicciones
                    O->>R: pausar_por_qa (estado = pausado_por_qa)
                    O->>H: reporte qa_cap_N.md
                    H-->>O: marca resuelto y el harness reanuda
                end
            end
        end
    end
```

## 4. Estados del manifiesto de ejecución

`04_estado/manifest.json` es lo que permite reanudar una tanda interrumpida sin repetir capítulos ya cerrados.

```mermaid
stateDiagram-v2
    direction TB
    [*] --> en_progreso: inicio de tanda
    en_progreso --> en_progreso: capítulo cerrado · N++
    en_progreso --> pausado_por_qa: contradicción · RF-07.4
    pausado_por_qa --> en_progreso: usuario resuelve
    en_progreso --> completo: N > total
    en_progreso --> abortado: EX-01 / 03 / 04
    completo --> [*]
    abortado --> [*]

    note right of pausado_por_qa
        El harness no reanuda solo (EX-02)
    end note

    note right of abortado
        Aborta sin cerrar el capítulo N,
        el manifiesto queda consistente
    end note
```
