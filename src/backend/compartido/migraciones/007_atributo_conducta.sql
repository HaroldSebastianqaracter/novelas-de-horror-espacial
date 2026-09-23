-- Migracion 007 (specs/spec2.md, fase 10: RF2-PIPE-29).
--
-- Un atributo puede ser una conducta del sujeto (un habito, un ritual): cambiar su valor es
-- aviso en la puerta 3, no conflicto. Es estado: append-only y con escena de origen, asi que
-- revertir un capitulo borra las marcas que ese capitulo puso. No se toca `hecho.categoria`:
-- su CHECK obligaria a reconstruir la tabla (ver la migracion 002).

CREATE TABLE atributo_conducta (
    id             INTEGER PRIMARY KEY,
    novela_id      INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    escena_id      INTEGER NOT NULL REFERENCES escena(id) ON DELETE CASCADE,
    sujeto_clave   TEXT NOT NULL,
    atributo_clave TEXT NOT NULL,
    UNIQUE (escena_id, sujeto_clave, atributo_clave)
);

CREATE INDEX ix_atributo_conducta_clave ON atributo_conducta (novela_id, sujeto_clave, atributo_clave);
