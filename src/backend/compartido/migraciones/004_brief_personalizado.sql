-- Migracion 004 (specs/spec3.md, bloque 2: RF3-PER-02).
--
-- El brief de una novela personalizada y lo que el pipeline saca de el. Todo es canon: lo
-- fija el comprador antes de empezar, y ninguna reversion de capitulos lo toca. La unica
-- tabla que depende de la escaleta, escena_elemento, cae con sus escenas cuando la escaleta
-- se rehace.

-- El brief validado, tal como llego en la intencion crear_novela.
CREATE TABLE brief (
    id        INTEGER PRIMARY KEY,
    novela_id INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    contenido TEXT NOT NULL,              -- JSON de compartido.brief.Brief, con codigos
    creado_en TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (novela_id)
);

-- Un rasgo, recuerdo o allegado del destinatario. El codigo (RAS1, REC1, ALL1...) es como el
-- resto del sistema dice donde aparece cada elemento.
CREATE TABLE elemento_personal (
    id          INTEGER PRIMARY KEY,
    novela_id   INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    codigo      TEXT NOT NULL,
    tipo        TEXT NOT NULL,
    texto       TEXT NOT NULL,
    obligatorio INTEGER NOT NULL DEFAULT 1,
    origen      TEXT NOT NULL DEFAULT 'entrevista',
    cita        TEXT,
    UNIQUE (novela_id, codigo),
    CHECK (tipo IN ('rasgo','recuerdo','allegado')),
    CHECK (origen IN ('entrevista','texto_libre'))
);

-- Que elementos personales planifica la escaleta en cada escena. Lo declara el escaletador:
-- es dato autodeclarado, y que la prosa lo cumpla se comprueba aparte (bloque 6).
CREATE TABLE escena_elemento (
    id          INTEGER PRIMARY KEY,
    escena_id   INTEGER NOT NULL REFERENCES escena(id) ON DELETE CASCADE,
    elemento_id INTEGER NOT NULL REFERENCES elemento_personal(id) ON DELETE CASCADE,
    UNIQUE (escena_id, elemento_id)
);

-- La transcripcion de la entrevista, con sus alertas y las llamadas al agente. La entrevista
-- no escribe en la base (RF3-ENT-06): la trae la intencion y la guarda el worker.
CREATE TABLE entrevista (
    id            INTEGER PRIMARY KEY,
    novela_id     INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    transcripcion TEXT NOT NULL,
    creado_en     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (novela_id)
);

ALTER TABLE novela ADD COLUMN dedicatoria TEXT;

CREATE INDEX ix_elemento_novela ON elemento_personal (novela_id);
CREATE INDEX ix_escena_elemento ON escena_elemento (elemento_id);
