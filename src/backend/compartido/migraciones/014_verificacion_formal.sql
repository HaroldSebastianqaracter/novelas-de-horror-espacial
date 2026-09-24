-- Migracion 014 (specs/spec-lean.md, RF-LEAN-06).
--
-- La verificacion formal en Lean queda en `resultado_puerta` como puerta 6, y su fallo abre una
-- parada de tipo `formal`. SQLite no sabe cambiar un CHECK. `resultado_puerta` no tiene hijos y
-- se rehace con el mismo contenido; `parada` si los tiene, y su CHECK se cambia en el paso de
-- Python (014_verificacion_formal.py).

CREATE TABLE resultado_puerta_nueva (
    id        INTEGER PRIMARY KEY,
    novela_id INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    puerta    INTEGER NOT NULL,
    capitulo  INTEGER,
    intento   INTEGER,
    veredicto TEXT NOT NULL,
    detalle   TEXT,
    creado_en TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (puerta BETWEEN 1 AND 6),
    CHECK (veredicto IN ('pasa','falla','aviso'))
);

INSERT INTO resultado_puerta_nueva (id, novela_id, puerta, capitulo, intento, veredicto, detalle,
                                    creado_en)
SELECT id, novela_id, puerta, capitulo, intento, veredicto, detalle, creado_en
FROM resultado_puerta;

DROP TABLE resultado_puerta;
ALTER TABLE resultado_puerta_nueva RENAME TO resultado_puerta;
