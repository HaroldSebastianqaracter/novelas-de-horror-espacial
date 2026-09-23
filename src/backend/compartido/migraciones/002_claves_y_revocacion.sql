-- Migracion 002 (specs/spec2.md, fase 5: RF2-PIPE-11, RF2-PER-06, RF2-PER-11).
--
--   * El hecho guarda claves normalizadas: la puerta 3 compara claves, nunca LOWER(), que en
--     SQLite solo pliega ASCII.
--   * Revocar un hecho es insertar una fila en hecho_revocacion; la vigencia se deriva en la
--     vista hecho_vigente. La columna hecho.vigente deja de leerse y escribirse.
--   * El estado de un personaje lleva su condicion como dato cerrado.
--   * Las entidades con nombre llevan su nombre normalizado, unico por novela.
--
-- El paso en Python del mismo numero (002_claves_y_revocacion.py) corre despues, en la misma
-- transaccion: rellena las claves de las filas que ya existen, pasa las revocaciones y crea
-- los indices unicos y los triggers.

ALTER TABLE hecho ADD COLUMN sujeto_clave TEXT;
ALTER TABLE hecho ADD COLUMN atributo_clave TEXT;
ALTER TABLE hecho ADD COLUMN valor_clave TEXT;

ALTER TABLE estado_personaje ADD COLUMN condicion TEXT
    CHECK (condicion IS NULL
           OR condicion IN ('vivo','herido','incapacitado','muerto','desaparecido'));

ALTER TABLE personaje ADD COLUMN nombre_clave TEXT;
ALTER TABLE lugar ADD COLUMN nombre_clave TEXT;
ALTER TABLE objeto ADD COLUMN nombre_clave TEXT;
ALTER TABLE faccion ADD COLUMN nombre_clave TEXT;
ALTER TABLE sistema_tecnologico ADD COLUMN nombre_clave TEXT;

CREATE TABLE hecho_revocacion (
    id        INTEGER PRIMARY KEY,
    novela_id INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    hecho_id  INTEGER NOT NULL REFERENCES hecho(id) ON DELETE CASCADE,
    parada_id INTEGER REFERENCES parada(id) ON DELETE SET NULL,
    -- Capitulo desde el que rige: revertir a N borra las revocaciones de capitulos > N.
    capitulo  INTEGER NOT NULL,
    motivo    TEXT NOT NULL,
    creado_en TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (hecho_id)
);

-- El indice parcial sobre vigente = 1 deja de servir: nadie filtra ya por esa columna.
DROP INDEX IF EXISTS ix_hecho_sujeto;
CREATE INDEX ix_hecho_claves ON hecho (novela_id, sujeto_tipo, sujeto_clave, atributo_clave);
CREATE INDEX ix_revocacion_novela ON hecho_revocacion (novela_id, capitulo);
CREATE INDEX ix_hecho_supersede ON hecho (supersede_a);

-- Hechos vigentes: los que ninguna revocacion retira. Es lo unico que leen la puerta 3, el
-- paquete de contexto, el indice y la API.
CREATE VIEW hecho_vigente AS
SELECT h.id, h.novela_id, h.escena_id, h.sujeto_tipo, h.sujeto_id, h.sujeto_nombre,
       h.atributo, h.valor, h.categoria, h.cita, h.supersede_a,
       h.sujeto_clave, h.atributo_clave, h.valor_clave, h.creado_en
FROM hecho h
WHERE NOT EXISTS (SELECT 1 FROM hecho_revocacion r WHERE r.hecho_id = h.id);
