-- Migracion 008 (specs/spec2.md, fase 10: RF2-PIPE-31).
--
-- Quien esta fisicamente en una escena segun la prosa, aunque la escaleta no lo pusiera. La
-- registra el extractor (spec3, RF3-PAS-09). Es estado: append-only y con escena de origen,
-- asi que revertir un capitulo borra las presencias que ese capitulo registro.

CREATE TABLE presencia_escena (
    id           INTEGER PRIMARY KEY,
    novela_id    INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    escena_id    INTEGER NOT NULL REFERENCES escena(id) ON DELETE CASCADE,
    personaje_id INTEGER NOT NULL REFERENCES personaje(id) ON DELETE CASCADE,
    UNIQUE (escena_id, personaje_id)
);

CREATE INDEX ix_presencia_escena_personaje ON presencia_escena (personaje_id, escena_id);

-- Estar en una escena: el reparto y el POV que planifico la escaleta, lo que constata el
-- extractor, y actuar en ella (un uso de conocimiento o un estado registrados alli,
-- RF2-PIPE-30). Es lo que lee la puerta 3 cuando pregunta si alguien estaba.
CREATE VIEW presencia AS
    SELECT escena_id, personaje_id FROM escena_personaje
    UNION SELECT id, pov_id FROM escena WHERE pov_id IS NOT NULL
    UNION SELECT escena_id, personaje_id FROM presencia_escena
    UNION SELECT escena_id, personaje_id FROM uso_conocimiento
    UNION SELECT escena_id, personaje_id FROM estado_personaje;
