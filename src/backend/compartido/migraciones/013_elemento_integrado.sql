-- Migracion 013 (specs/spec3.md, RF3-ELE-01).
--
-- Que elemento personal del encargo integra la prosa de cada escena, con la cita literal que
-- lo muestra. Lo registra el extractor y el codigo comprueba la cita. Estado append-only y con
-- escena de origen: revertir un capitulo borra lo que ese capitulo registro.

CREATE TABLE elemento_integrado (
    id          INTEGER PRIMARY KEY,
    novela_id   INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    escena_id   INTEGER NOT NULL REFERENCES escena(id) ON DELETE CASCADE,
    elemento_id INTEGER NOT NULL REFERENCES elemento_personal(id) ON DELETE CASCADE,
    cita        TEXT NOT NULL,
    UNIQUE (escena_id, elemento_id)
);

CREATE INDEX ix_elemento_integrado_elemento ON elemento_integrado (novela_id, elemento_id);
