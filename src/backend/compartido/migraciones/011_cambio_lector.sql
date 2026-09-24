-- Migracion 011 (specs/spec3.md, bloque 8: RF3-CAM-01 y RF3-CAM-13).
--
-- El tipo de intencion nuevo, `cambio_lector`, y el registro de cada cambio que pide el lector.
-- SQLite no sabe cambiar un CHECK: la tabla de intenciones se rehace con el mismo contenido.

CREATE TABLE intencion_nueva (
    id            INTEGER PRIMARY KEY,
    tipo          TEXT NOT NULL,
    novela_id     INTEGER REFERENCES novela(id) ON DELETE CASCADE,
    payload       TEXT NOT NULL DEFAULT '{}',
    estado        TEXT NOT NULL DEFAULT 'pendiente',
    motivo        TEXT,
    resultado     TEXT,
    creado_en     TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (tipo IN ('crear_novela','arrancar','parar','relanzar','resolver_parada',
                    'cambio_lector')),
    CHECK (estado IN ('pendiente','en_curso','hecha','rechazada','interrumpida'))
);

INSERT INTO intencion_nueva (id, tipo, novela_id, payload, estado, motivo, resultado,
                             creado_en, actualizado_en)
SELECT id, tipo, novela_id, payload, estado, motivo, resultado, creado_en, actualizado_en
FROM intencion;

DROP TABLE intencion;
ALTER TABLE intencion_nueva RENAME TO intencion;
CREATE INDEX ix_intencion_cola ON intencion (estado, creado_en);

-- Canon y fuera de toda reversion: lo que pidio el lector y lo que se hizo con ello.
CREATE TABLE cambio_lector (
    id             INTEGER PRIMARY KEY,
    novela_id      INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    intencion_id   INTEGER REFERENCES intencion(id) ON DELETE SET NULL,
    version_base   INTEGER NOT NULL,
    peticion       TEXT NOT NULL,
    objetivo       TEXT NOT NULL,                 -- JSON, como llego en el payload
    cita           TEXT,                          -- JSON {capitulo, texto}, o nulo
    -- JSON: lo que devolvio el interprete y, si se admitio, el cambio que se aplica.
    interpretacion TEXT,
    cambio         TEXT,
    alertas        TEXT NOT NULL DEFAULT '[]',    -- JSON: patrones de inyeccion encontrados
    capitulos      TEXT NOT NULL DEFAULT '[]',    -- JSON: el alcance
    estado         TEXT NOT NULL DEFAULT 'interpretando',
    informe        TEXT,                          -- JSON: por que se rechazo o fracaso
    version        INTEGER,                       -- la version que publico, si publico
    creado_en      TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (estado IN ('interpretando','rechazado','reescribiendo','aplicado','fallido',
                      'interrumpido')),
    CHECK (json_valid(objetivo) AND json_valid(alertas) AND json_valid(capitulos))
);

CREATE INDEX ix_cambio_lector_novela ON cambio_lector (novela_id, id);
