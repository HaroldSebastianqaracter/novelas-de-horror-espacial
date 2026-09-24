-- Migracion 015: la rubrica del LLM-as-judge y la revision humana.
--
-- Una fila por criterio y evaluacion. `origen` distingue al juez (llm) de la revision a mano
-- (humano); la comparacion la hace evals/rubrica_humana.py. Es registro, no estado: ninguna
-- reversion la toca.

CREATE TABLE evaluacion_rubrica (
    id                INTEGER PRIMARY KEY,
    novela_id         INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    version           INTEGER,                 -- la version publicada que se evaluo
    origen            TEXT NOT NULL,
    criterio          TEXT NOT NULL,
    nota              INTEGER NOT NULL,
    justificacion     TEXT NOT NULL DEFAULT '',
    evidencia         TEXT NOT NULL DEFAULT '',
    -- Solo del juez: 1 si la evidencia es una cita de la novela, 0 si no.
    evidencia_literal INTEGER,
    llamada_id        INTEGER REFERENCES llamada_modelo(id) ON DELETE SET NULL,
    creado_en         TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (origen IN ('llm', 'humano')),
    CHECK (nota BETWEEN 1 AND 5),
    CHECK (criterio IN ('continuidad', 'tono', 'arco', 'coherencia_personajes', 'ritmo',
                        'personalizacion_natural'))
);

CREATE INDEX ix_evaluacion_rubrica_novela ON evaluacion_rubrica (novela_id, origen, id);

-- Langfuse recibe la rubrica como scores: su registro de envios admite la tabla nueva.
CREATE TABLE langfuse_envio_nueva (
    tabla      TEXT NOT NULL,
    fila_id    INTEGER NOT NULL,
    novela_id  INTEGER REFERENCES novela(id) ON DELETE CASCADE,
    enviado_en TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (tabla, fila_id),
    CHECK (tabla IN ('llamada_modelo', 'resultado_puerta', 'entrevista', 'evaluacion_rubrica'))
);

INSERT INTO langfuse_envio_nueva (tabla, fila_id, novela_id, enviado_en)
SELECT tabla, fila_id, novela_id, enviado_en FROM langfuse_envio;

DROP TABLE langfuse_envio;
ALTER TABLE langfuse_envio_nueva RENAME TO langfuse_envio;
