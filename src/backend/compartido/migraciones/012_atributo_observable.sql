-- Migracion 012 (specs/spec3.md, RF3-PAS-15).
--
-- Un atributo puede ser observable: lo percibe cualquiera que este en el lugar (una luz que
-- late, un ruido, una alarma). La puerta 3 no para por conocimiento no adquirido sobre un
-- hecho observable. Como `atributo_conducta` (migracion 007): estado append-only y con escena
-- de origen, asi que revertir un capitulo borra las marcas que ese capitulo puso.

CREATE TABLE atributo_observable (
    id             INTEGER PRIMARY KEY,
    novela_id      INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    escena_id      INTEGER NOT NULL REFERENCES escena(id) ON DELETE CASCADE,
    sujeto_clave   TEXT NOT NULL,
    atributo_clave TEXT NOT NULL,
    UNIQUE (escena_id, sujeto_clave, atributo_clave)
);

CREATE INDEX ix_atributo_observable_clave
    ON atributo_observable (novela_id, sujeto_clave, atributo_clave);
