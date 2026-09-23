-- Migracion 008 (specs/spec3.md, bloque 4: RF3-OBS-08).
--
-- Lo que el worker ya envio a Langfuse, fila a fila. Solo lo escribe el worker, que es el
-- unico escritor. El comando exportar_langfuse.py no lo toca: abre la base en solo lectura y
-- sus identificadores deterministas hacen que reenviar no duplique.

CREATE TABLE langfuse_envio (
    tabla      TEXT NOT NULL,
    fila_id    INTEGER NOT NULL,
    novela_id  INTEGER REFERENCES novela(id) ON DELETE CASCADE,
    enviado_en TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (tabla, fila_id),
    CHECK (tabla IN ('llamada_modelo', 'resultado_puerta', 'entrevista'))
);
