-- Esquema de la base de datos (seccion 4 de specs/spec1.md).
--
-- Reglas que este fichero materializa:
--   * Traduccion directa de docs/definitions.md, camelCase -> snake_case (RF-PER-03).
--   * Todo el ESTADO es append-only y lleva escena de origen (RF-PER-06): lo que en la
--     ontologia son atributos que cambian durante la redaccion (Siembra.estado,
--     HiloNarrativo.estado, Amenaza.nivelRevelacion, Lugar.presenciaActual) NO son columnas
--     mutables, se derivan de su tabla de estado. Eso es lo que hace que revertir al
--     capitulo N sea borrar por escena de origen (RF-FALLO-04).
--   * El Hecho es un triple sujeto/atributo/valor (RF-PIPE-11), no un enunciado libre:
--     sin eso la puerta 3 no puede ser una consulta exacta.
--   * El texto se versiona, nunca se hace UPDATE sobre el (RF-PER-05).
--
-- Las tablas van en orden de dependencia: SQLite comprueba las claves ajenas al vuelo.

-- =========================================================================================
-- Infraestructura
-- =========================================================================================

CREATE TABLE IF NOT EXISTS esquema_version (
    version     INTEGER PRIMARY KEY,
    aplicado_en TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS worker_lock (
    id        INTEGER PRIMARY KEY CHECK (id = 1),
    pid       INTEGER NOT NULL,
    arrancado_en TEXT NOT NULL DEFAULT (datetime('now')),
    latido_en TEXT NOT NULL DEFAULT (datetime('now'))
);

-- =========================================================================================
-- Canon
-- =========================================================================================

CREATE TABLE IF NOT EXISTS novela (
    id                  INTEGER PRIMARY KEY,
    titulo              TEXT NOT NULL,
    genero              TEXT NOT NULL DEFAULT 'terror_espacial',
    subgenero_dominante TEXT,
    premisa             TEXT,
    logline             TEXT,
    pregunta_dramatica  TEXT,
    tema_central        TEXT,
    tipo_final          TEXT,
    longitud_objetivo   INTEGER,
    pov_por_defecto     TEXT,
    tiempo_verbal       TEXT,
    semilla_premisa     TEXT,
    creado_en           TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ejecucion (
    id                    INTEGER PRIMARY KEY,
    novela_id             INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    estado                TEXT NOT NULL DEFAULT 'configurada',
    fase                  TEXT,
    capitulo_actual       INTEGER,
    intento_actual        INTEGER NOT NULL DEFAULT 1,
    capitulos_completados INTEGER NOT NULL DEFAULT 0,
    -- Sin clave ajena a propoisto: parada.ejecucion_id ya apunta aqui y seria un ciclo.
    parada_abierta_id     INTEGER,
    ultimo_error          TEXT,
    actualizado_en        TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (novela_id),
    CHECK (estado IN ('configurada','planificando','escaletando','generando','parada',
                      'detenida','completada','completada_con_avisos','error'))
);

CREATE TABLE IF NOT EXISTS parada (
    id           INTEGER PRIMARY KEY,
    ejecucion_id INTEGER NOT NULL REFERENCES ejecucion(id) ON DELETE CASCADE,
    tipo         TEXT NOT NULL,
    capitulo     INTEGER,
    intento      INTEGER,
    informe      TEXT NOT NULL,
    estado       TEXT NOT NULL DEFAULT 'abierta',
    resolucion   TEXT,
    creado_en    TEXT NOT NULL DEFAULT (datetime('now')),
    resuelto_en  TEXT,
    -- La migracion 014 anade 'formal' (spec-lean, RF-LEAN-06).
    CHECK (tipo IN ('estructura','escaleta','continuidad','oficio','presupuesto')),
    CHECK (estado IN ('abierta','resuelta'))
);

CREATE TABLE IF NOT EXISTS llamada_modelo (
    id                        INTEGER PRIMARY KEY,
    novela_id                 INTEGER REFERENCES novela(id) ON DELETE CASCADE,
    agente                    TEXT NOT NULL,
    capitulo                  INTEGER,
    intento                   INTEGER,
    sistema                   TEXT NOT NULL,
    entrada                   TEXT NOT NULL,
    esquema                   TEXT,
    salida_cruda              TEXT,
    tokens_entrada_por_bloque TEXT,
    tokens_entrada            INTEGER,
    tokens_salida             INTEGER,
    duracion_ms               INTEGER,
    exit_code                 INTEGER,
    estado                    TEXT NOT NULL DEFAULT 'en_curso',
    metadatos                 TEXT,
    creado_en                 TEXT NOT NULL DEFAULT (datetime('now')),
    terminado_en              TEXT,
    CHECK (estado IN ('en_curso','ok','salida_invalida','timeout','interrumpida','error'))
);

CREATE TABLE IF NOT EXISTS restriccion (
    id        INTEGER PRIMARY KEY,
    novela_id INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    tipo      TEXT NOT NULL,
    valor     TEXT NOT NULL,
    UNIQUE (novela_id, tipo)
);

CREATE TABLE IF NOT EXISTS tema (
    id              INTEGER PRIMARY KEY,
    novela_id       INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    pregunta_central TEXT NOT NULL,
    verdad_tematica  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS motivo (
    id                 INTEGER PRIMARY KEY,
    novela_id          INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    tema_id            INTEGER REFERENCES tema(id) ON DELETE SET NULL,
    simbolo            TEXT NOT NULL,
    significado_inicial TEXT,
    significado_final   TEXT
);

CREATE TABLE IF NOT EXISTS estilo_narrativo (
    id                   INTEGER PRIMARY KEY,
    novela_id            INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    registro             TEXT NOT NULL,
    ritmo_prosa          TEXT NOT NULL,
    densidad_sensorial   TEXT NOT NULL,
    distancia_psiquica   TEXT NOT NULL,
    tics_prohibidos      TEXT NOT NULL,   -- JSON: lista no vacia (RF-PIPE-04)
    convenciones_formato TEXT,
    UNIQUE (novela_id)
);

CREATE TABLE IF NOT EXISTS mundo (
    id             INTEGER PRIMARY KEY,
    novela_id      INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    nombre         TEXT NOT NULL,
    geografia      TEXT,
    historia       TEXT,
    culturas       TEXT,
    reglas_fisicas TEXT,
    UNIQUE (novela_id)
);

CREATE TABLE IF NOT EXISTS sistema_tecnologico (
    id          INTEGER PRIMARY KEY,
    novela_id   INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    mundo_id    INTEGER NOT NULL REFERENCES mundo(id) ON DELETE CASCADE,
    nombre      TEXT NOT NULL,
    capacidades TEXT NOT NULL,
    costes      TEXT NOT NULL,
    limites     TEXT NOT NULL,
    acceso      TEXT,
    dureza      TEXT NOT NULL DEFAULT 'duro',
    CHECK (dureza IN ('duro','blando'))
);

CREATE TABLE IF NOT EXISTS lugar (
    id                INTEGER PRIMARY KEY,
    novela_id         INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    mundo_id          INTEGER NOT NULL REFERENCES mundo(id) ON DELETE CASCADE,
    nombre            TEXT NOT NULL,
    tipo              TEXT,
    descripcion       TEXT,
    sistemas_criticos TEXT             -- JSON: lista de sistema_tecnologico.id
    -- presencia_actual NO es columna: se deriva del reparto de la ultima escena alli.
);

CREATE TABLE IF NOT EXISTS linea_de_tiempo (
    id        INTEGER PRIMARY KEY,
    novela_id INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    origen    TEXT NOT NULL,
    unidad    TEXT NOT NULL,
    UNIQUE (novela_id)
);

CREATE TABLE IF NOT EXISTS faccion (
    id        INTEGER PRIMARY KEY,
    novela_id INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    nombre    TEXT NOT NULL,
    proposito TEXT,
    objetivos TEXT,
    recursos  TEXT
);

CREATE TABLE IF NOT EXISTS personaje (
    id                INTEGER PRIMARY KEY,
    novela_id         INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    faccion_id        INTEGER REFERENCES faccion(id) ON DELETE SET NULL,
    nombre            TEXT NOT NULL,
    rol               TEXT,
    rol_narrativo     TEXT NOT NULL,
    deseo             TEXT,
    necesidad_interna TEXT,
    fantasma          TEXT,
    herida            TEXT,
    mentira           TEXT,
    defecto           TEXT,
    tipo_arco         TEXT,
    subtipo_arco      TEXT,
    idiolecto         TEXT,
    secreto           TEXT,
    posicion_tematica TEXT,
    CHECK (rol_narrativo IN ('protagonista','oponente','aliado','falso_aliado','mentor',
                             'heraldo','guardian_del_umbral','espejo')),
    CHECK (tipo_arco IS NULL OR tipo_arco IN ('positivo','plano','negativo')),
    CHECK (subtipo_arco IS NULL OR subtipo_arco IN ('desilusion','caida','corrupcion'))
);

CREATE TABLE IF NOT EXISTS personaje_relacion (
    id        INTEGER PRIMARY KEY,
    origen_id  INTEGER NOT NULL REFERENCES personaje(id) ON DELETE CASCADE,
    destino_id INTEGER NOT NULL REFERENCES personaje(id) ON DELETE CASCADE,
    tipo       TEXT NOT NULL,
    UNIQUE (origen_id, destino_id, tipo),
    CHECK (tipo IN ('se_opone_a','aliado_con'))
);

CREATE TABLE IF NOT EXISTS faccion_relacion (
    id        INTEGER PRIMARY KEY,
    origen_id  INTEGER NOT NULL REFERENCES faccion(id) ON DELETE CASCADE,
    destino_id INTEGER NOT NULL REFERENCES faccion(id) ON DELETE CASCADE,
    tipo       TEXT NOT NULL DEFAULT 'se_opone_a',
    UNIQUE (origen_id, destino_id, tipo)
);

CREATE TABLE IF NOT EXISTS amenaza (
    id        INTEGER PRIMARY KEY,
    novela_id INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    tema_id   INTEGER REFERENCES tema(id) ON DELETE SET NULL,
    naturaleza TEXT NOT NULL,
    reglas     TEXT NOT NULL,  -- JSON: [{capacidad, limite, activacion}], minimo 3
    origen     TEXT,
    UNIQUE (novela_id)
    -- nivel_revelacion NO es columna: se deriva de amenaza_revelacion.
);

CREATE TABLE IF NOT EXISTS objeto (
    id               INTEGER PRIMARY KEY,
    novela_id        INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    nombre           TEXT NOT NULL,
    funcion_narrativa TEXT
);

-- =========================================================================================
-- Estructura
-- =========================================================================================

CREATE TABLE IF NOT EXISTS acto (
    id                INTEGER PRIMARY KEY,
    novela_id         INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    numero            INTEGER NOT NULL,
    funcion_narrativa TEXT,
    UNIQUE (novela_id, numero)
);

CREATE TABLE IF NOT EXISTS hilo (
    id               INTEGER PRIMARY KEY,
    novela_id        INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    tema_id          INTEGER REFERENCES tema(id) ON DELETE SET NULL,
    tipo             TEXT NOT NULL,
    conflicto_central TEXT NOT NULL,
    CHECK (tipo IN ('principal','subtrama'))
    -- estado NO es columna: se deriva de hilo_estado.
);

CREATE TABLE IF NOT EXISTS punto_de_giro (
    id       INTEGER PRIMARY KEY,
    hilo_id  INTEGER NOT NULL REFERENCES hilo(id) ON DELETE CASCADE,
    tipo     TEXT NOT NULL,
    posicion REAL NOT NULL,
    CHECK (tipo IN ('gancho','incidente_incitador','primer_umbral','punto_de_pellizco',
                    'punto_medio','segundo_pellizco','todo_esta_perdido','entrada_tercer_acto',
                    'crisis','climax','resolucion')),
    CHECK (posicion >= 0.0 AND posicion <= 100.0)
);

CREATE TABLE IF NOT EXISTS hilo_personaje (
    id          INTEGER PRIMARY KEY,
    hilo_id     INTEGER NOT NULL REFERENCES hilo(id) ON DELETE CASCADE,
    personaje_id INTEGER NOT NULL REFERENCES personaje(id) ON DELETE CASCADE,
    UNIQUE (hilo_id, personaje_id)
);

CREATE TABLE IF NOT EXISTS capitulo (
    id                INTEGER PRIMARY KEY,
    novela_id         INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    acto_id           INTEGER NOT NULL REFERENCES acto(id) ON DELETE CASCADE,
    numero            INTEGER NOT NULL,
    objetivo          TEXT,
    pov_id            INTEGER REFERENCES personaje(id) ON DELETE SET NULL,
    gancho_apertura   TEXT,
    gancho_cierre     TEXT,
    longitud_prevista INTEGER,
    estado            TEXT NOT NULL DEFAULT 'planificado',
    resumen           TEXT,
    resumen_breve     TEXT,
    UNIQUE (novela_id, numero),
    CHECK (estado IN ('planificado','completado'))
);

CREATE TABLE IF NOT EXISTS secuencia (
    id                  INTEGER PRIMARY KEY,
    novela_id           INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    acto_id             INTEGER NOT NULL REFERENCES acto(id) ON DELETE CASCADE,
    objetivo_intermedio TEXT,
    orden               INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS escena (
    id                INTEGER PRIMARY KEY,
    novela_id         INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    capitulo_id       INTEGER NOT NULL REFERENCES capitulo(id) ON DELETE CASCADE,
    secuencia_id      INTEGER REFERENCES secuencia(id) ON DELETE SET NULL,
    punto_de_giro_id  INTEGER REFERENCES punto_de_giro(id) ON DELETE SET NULL,
    pov_id            INTEGER NOT NULL REFERENCES personaje(id) ON DELETE RESTRICT,
    lugar_id          INTEGER NOT NULL REFERENCES lugar(id) ON DELETE RESTRICT,
    orden             INTEGER NOT NULL,
    objetivo          TEXT NOT NULL,
    conflicto         TEXT NOT NULL,
    resultado         TEXT,
    valor_inicial     TEXT NOT NULL,
    valor_final       TEXT NOT NULL,
    tension           INTEGER,
    gancho_salida     TEXT,
    longitud_prevista INTEGER,
    analepsis         INTEGER NOT NULL DEFAULT 0,   -- RF-PIPE-12: marca de flashback
    UNIQUE (capitulo_id, orden)
);

CREATE TABLE IF NOT EXISTS escena_personaje (
    id          INTEGER PRIMARY KEY,
    escena_id    INTEGER NOT NULL REFERENCES escena(id) ON DELETE CASCADE,
    personaje_id INTEGER NOT NULL REFERENCES personaje(id) ON DELETE CASCADE,
    UNIQUE (escena_id, personaje_id)
);

CREATE TABLE IF NOT EXISTS escena_objeto (
    id        INTEGER PRIMARY KEY,
    escena_id INTEGER NOT NULL REFERENCES escena(id) ON DELETE CASCADE,
    objeto_id INTEGER NOT NULL REFERENCES objeto(id) ON DELETE CASCADE,
    UNIQUE (escena_id, objeto_id)
);

CREATE TABLE IF NOT EXISTS escena_motivo (
    id        INTEGER PRIMARY KEY,
    escena_id INTEGER NOT NULL REFERENCES escena(id) ON DELETE CASCADE,
    motivo_id INTEGER NOT NULL REFERENCES motivo(id) ON DELETE CASCADE,
    UNIQUE (escena_id, motivo_id)
);

CREATE TABLE IF NOT EXISTS secuela (
    id               INTEGER PRIMARY KEY,
    escena_id        INTEGER NOT NULL REFERENCES escena(id) ON DELETE CASCADE,
    reaccion         TEXT,
    dilema           TEXT,
    decision         TEXT,
    motiva_escena_id INTEGER REFERENCES escena(id) ON DELETE SET NULL,
    UNIQUE (escena_id)
);

CREATE TABLE IF NOT EXISTS beat (
    id        INTEGER PRIMARY KEY,
    escena_id INTEGER NOT NULL REFERENCES escena(id) ON DELETE CASCADE,
    orden     INTEGER NOT NULL,
    tipo      TEXT,
    cambio    TEXT,
    UNIQUE (escena_id, orden)
);

CREATE TABLE IF NOT EXISTS siembra (
    id                     INTEGER PRIMARY KEY,
    novela_id              INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    hilo_id                INTEGER REFERENCES hilo(id) ON DELETE SET NULL,
    sembrada_en_escena_id  INTEGER REFERENCES escena(id) ON DELETE CASCADE,
    elemento               TEXT NOT NULL,
    capitulo_pago_previsto INTEGER,
    origen                 TEXT NOT NULL DEFAULT 'estructura',
    CHECK (origen IN ('estructura','extraccion'))
    -- estado NO es columna: se deriva de siembra_estado.
);

-- =========================================================================================
-- Estado (append-only, siempre con escena de origen)
-- =========================================================================================

CREATE TABLE IF NOT EXISTS hecho (
    id                 INTEGER PRIMARY KEY,
    novela_id          INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    escena_id          INTEGER NOT NULL REFERENCES escena(id) ON DELETE CASCADE,
    sujeto_tipo        TEXT NOT NULL,
    sujeto_id          INTEGER,
    sujeto_nombre      TEXT,
    atributo           TEXT NOT NULL,
    valor              TEXT NOT NULL,
    categoria          TEXT NOT NULL DEFAULT 'otro',
    cita               TEXT,
    supersede_a        INTEGER REFERENCES hecho(id) ON DELETE SET NULL,
    vigente            INTEGER NOT NULL DEFAULT 1,
    motivo_no_vigente  TEXT,
    parada_id          INTEGER REFERENCES parada(id) ON DELETE SET NULL,
    creado_en          TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (sujeto_tipo IN ('personaje','lugar','objeto','amenaza','sistema_tecnologico',
                           'faccion','mundo','novela','otro')),
    CHECK (categoria IN ('nombre','fisico','fecha','distancia','regla','relacion',
                         'ubicacion','otro'))
);

CREATE TABLE IF NOT EXISTS estado_conocimiento (
    id           INTEGER PRIMARY KEY,
    novela_id    INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    personaje_id INTEGER NOT NULL REFERENCES personaje(id) ON DELETE CASCADE,
    hecho_id     INTEGER NOT NULL REFERENCES hecho(id) ON DELETE CASCADE,
    escena_id    INTEGER NOT NULL REFERENCES escena(id) ON DELETE CASCADE,
    postura      TEXT NOT NULL,
    via          TEXT NOT NULL,
    CHECK (postura IN ('sabe','cree','sospecha','ignora','cree_version_falsa')),
    CHECK (via IN ('presencio','se_lo_contaron','dedujo','le_mintieron'))
);

CREATE TABLE IF NOT EXISTS uso_conocimiento (
    id           INTEGER PRIMARY KEY,
    novela_id    INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    personaje_id INTEGER NOT NULL REFERENCES personaje(id) ON DELETE CASCADE,
    hecho_id     INTEGER NOT NULL REFERENCES hecho(id) ON DELETE CASCADE,
    escena_id    INTEGER NOT NULL REFERENCES escena(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS estado_personaje (
    id                 INTEGER PRIMARY KEY,
    novela_id          INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    personaje_id       INTEGER NOT NULL REFERENCES personaje(id) ON DELETE CASCADE,
    escena_id          INTEGER NOT NULL REFERENCES escena(id) ON DELETE CASCADE,
    salud_fisica       TEXT,
    estado_psicologico TEXT,
    nivel_confianza    TEXT           -- JSON: {personaje_id: nivel}
);

CREATE TABLE IF NOT EXISTS estado_objeto (
    id                 INTEGER PRIMARY KEY,
    novela_id          INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    objeto_id          INTEGER NOT NULL REFERENCES objeto(id) ON DELETE CASCADE,
    escena_id          INTEGER NOT NULL REFERENCES escena(id) ON DELETE CASCADE,
    poseedor_id        INTEGER REFERENCES personaje(id) ON DELETE SET NULL,
    ubicacion_lugar_id INTEGER REFERENCES lugar(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS evento (
    id                 INTEGER PRIMARY KEY,
    novela_id          INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    linea_de_tiempo_id INTEGER NOT NULL REFERENCES linea_de_tiempo(id) ON DELETE CASCADE,
    escena_id          INTEGER REFERENCES escena(id) ON DELETE CASCADE,
    fecha_interna      TEXT NOT NULL,
    orden_interno      INTEGER,
    descripcion        TEXT NOT NULL,
    tipo               TEXT,
    dramatizado        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS siembra_estado (
    id         INTEGER PRIMARY KEY,
    novela_id  INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    siembra_id INTEGER NOT NULL REFERENCES siembra(id) ON DELETE CASCADE,
    escena_id  INTEGER NOT NULL REFERENCES escena(id) ON DELETE CASCADE,
    estado     TEXT NOT NULL,
    CHECK (estado IN ('sembrada','regada','pagada','abandonada'))
);

CREATE TABLE IF NOT EXISTS hilo_estado (
    id        INTEGER PRIMARY KEY,
    novela_id INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    hilo_id   INTEGER NOT NULL REFERENCES hilo(id) ON DELETE CASCADE,
    escena_id INTEGER NOT NULL REFERENCES escena(id) ON DELETE CASCADE,
    estado    TEXT NOT NULL,
    CHECK (estado IN ('abierto','complicando','latente','resuelto','abierto_deliberado'))
);

CREATE TABLE IF NOT EXISTS amenaza_revelacion (
    id         INTEGER PRIMARY KEY,
    novela_id  INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    amenaza_id INTEGER NOT NULL REFERENCES amenaza(id) ON DELETE CASCADE,
    escena_id  INTEGER NOT NULL REFERENCES escena(id) ON DELETE CASCADE,
    nivel      TEXT NOT NULL,
    CHECK (nivel IN ('rastro','efecto','vislumbre','encuentro','confrontacion'))
);

CREATE TABLE IF NOT EXISTS entidad_no_reconocida (
    id        INTEGER PRIMARY KEY,
    novela_id INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    escena_id INTEGER NOT NULL REFERENCES escena(id) ON DELETE CASCADE,
    nombre    TEXT NOT NULL,
    contexto  TEXT,
    parada_id INTEGER REFERENCES parada(id) ON DELETE SET NULL
);

-- =========================================================================================
-- Texto (versionado; nunca UPDATE sobre el texto)
-- =========================================================================================

CREATE TABLE IF NOT EXISTS escena_texto (
    id                INTEGER PRIMARY KEY,
    novela_id         INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    escena_id         INTEGER NOT NULL REFERENCES escena(id) ON DELETE CASCADE,
    version           INTEGER NOT NULL,
    texto             TEXT NOT NULL,
    palabras          INTEGER NOT NULL DEFAULT 0,
    origen            TEXT NOT NULL DEFAULT 'redaccion',
    intento           INTEGER,
    estado            TEXT NOT NULL DEFAULT 'vigente',
    llamada_modelo_id INTEGER REFERENCES llamada_modelo(id) ON DELETE SET NULL,
    creado_en         TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (escena_id, version),
    CHECK (origen IN ('redaccion','retcon','revision')),
    CHECK (estado IN ('vigente','descartada'))
);

CREATE TABLE IF NOT EXISTS capitulo_compilado (
    id          INTEGER PRIMARY KEY,
    novela_id   INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    capitulo_id INTEGER NOT NULL REFERENCES capitulo(id) ON DELETE CASCADE,
    version     INTEGER NOT NULL,
    texto       TEXT NOT NULL,
    palabras    INTEGER NOT NULL DEFAULT 0,
    estado      TEXT NOT NULL DEFAULT 'vigente',
    creado_en   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (capitulo_id, version),
    CHECK (estado IN ('vigente','descartada'))
);

-- =========================================================================================
-- Cola y traza
-- =========================================================================================

CREATE TABLE IF NOT EXISTS intencion (
    id            INTEGER PRIMARY KEY,
    tipo          TEXT NOT NULL,
    novela_id     INTEGER REFERENCES novela(id) ON DELETE CASCADE,
    payload       TEXT NOT NULL DEFAULT '{}',
    estado        TEXT NOT NULL DEFAULT 'pendiente',
    motivo        TEXT,
    resultado     TEXT,
    creado_en     TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (tipo IN ('crear_novela','arrancar','parar','relanzar','resolver_parada')),
    CHECK (estado IN ('pendiente','en_curso','hecha','rechazada','interrumpida'))
);

CREATE TABLE IF NOT EXISTS resultado_puerta (
    id        INTEGER PRIMARY KEY,
    novela_id INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    puerta    INTEGER NOT NULL,
    capitulo  INTEGER,
    intento   INTEGER,
    veredicto TEXT NOT NULL,
    detalle   TEXT,
    creado_en TEXT NOT NULL DEFAULT (datetime('now')),
    -- La migracion 014 lo lleva a 6: la verificacion formal (spec-lean, RF-LEAN-06).
    CHECK (puerta BETWEEN 1 AND 5),
    CHECK (veredicto IN ('pasa','falla','aviso'))
);

CREATE TABLE IF NOT EXISTS traza_evento (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    novela_id INTEGER REFERENCES novela(id) ON DELETE CASCADE,
    tipo      TEXT NOT NULL,
    payload   TEXT NOT NULL DEFAULT '{}',
    creado_en TEXT NOT NULL DEFAULT (datetime('now'))
);

-- =========================================================================================
-- Indice vectorial (derivado y reconstruible; las tablas vec0 se crean aparte si carga
-- sqlite-vec — RF-PER-10). Aqui solo va el registro de su estado.
-- =========================================================================================

CREATE TABLE IF NOT EXISTS indice_estado (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    modelo          TEXT,
    dimension       INTEGER,
    disponible      INTEGER NOT NULL DEFAULT 0,
    reconstruido_en TEXT
);

-- =========================================================================================
-- Vistas derivadas
-- =========================================================================================

-- Orden global de escenas: (capitulo.numero, escena.orden). Es lo que convierte "antes" y
-- "despues" en una comparacion exacta, que es lo que necesitan la puerta 3 y la integridad.
CREATE VIEW IF NOT EXISTS escena_ordinal AS
SELECT e.id            AS escena_id,
       e.novela_id     AS novela_id,
       e.capitulo_id   AS capitulo_id,
       c.numero        AS capitulo_numero,
       e.orden         AS escena_orden,
       (c.numero * 1000 + e.orden) AS ordinal
FROM escena e
JOIN capitulo c ON c.id = e.capitulo_id;

-- Estado vigente de cada siembra: la ultima fila por orden de escena.
CREATE VIEW IF NOT EXISTS siembra_vigente AS
SELECT s.id AS siembra_id,
       s.novela_id,
       s.elemento,
       s.hilo_id,
       s.capitulo_pago_previsto,
       COALESCE((SELECT se.estado
                 FROM siembra_estado se
                 JOIN escena_ordinal eo ON eo.escena_id = se.escena_id
                 WHERE se.siembra_id = s.id
                 ORDER BY eo.ordinal DESC, se.id DESC
                 LIMIT 1), 'sembrada') AS estado
FROM siembra s;

-- Estado vigente de cada hilo.
CREATE VIEW IF NOT EXISTS hilo_vigente AS
SELECT h.id AS hilo_id,
       h.novela_id,
       h.tipo,
       h.conflicto_central,
       COALESCE((SELECT he.estado
                 FROM hilo_estado he
                 JOIN escena_ordinal eo ON eo.escena_id = he.escena_id
                 WHERE he.hilo_id = h.id
                 ORDER BY eo.ordinal DESC, he.id DESC
                 LIMIT 1), 'abierto') AS estado
FROM hilo h;

-- =========================================================================================
-- Indices (RF-PER-08)
-- =========================================================================================

CREATE INDEX IF NOT EXISTS ix_hecho_sujeto
    ON hecho (novela_id, sujeto_tipo, sujeto_id, atributo) WHERE vigente = 1;
CREATE INDEX IF NOT EXISTS ix_hecho_escena        ON hecho (escena_id);
CREATE INDEX IF NOT EXISTS ix_conocimiento_ph     ON estado_conocimiento (personaje_id, hecho_id);
CREATE INDEX IF NOT EXISTS ix_conocimiento_escena ON estado_conocimiento (escena_id);
CREATE INDEX IF NOT EXISTS ix_uso_ph              ON uso_conocimiento (personaje_id, hecho_id);
CREATE INDEX IF NOT EXISTS ix_escena_texto_ev     ON escena_texto (escena_id, version);
CREATE INDEX IF NOT EXISTS ix_traza_novela        ON traza_evento (novela_id, id);
CREATE INDEX IF NOT EXISTS ix_intencion_cola      ON intencion (estado, creado_en);
CREATE INDEX IF NOT EXISTS ix_escena_capitulo     ON escena (capitulo_id, orden);
CREATE INDEX IF NOT EXISTS ix_escena_lugar        ON escena (lugar_id);
CREATE INDEX IF NOT EXISTS ix_estado_obj          ON estado_objeto (objeto_id, escena_id);
CREATE INDEX IF NOT EXISTS ix_estado_pers         ON estado_personaje (personaje_id, escena_id);
CREATE INDEX IF NOT EXISTS ix_siembra_estado      ON siembra_estado (siembra_id, escena_id);
CREATE INDEX IF NOT EXISTS ix_hilo_estado         ON hilo_estado (hilo_id, escena_id);
CREATE INDEX IF NOT EXISTS ix_llamada_novela      ON llamada_modelo (novela_id, creado_en);
