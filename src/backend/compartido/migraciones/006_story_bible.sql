-- Migracion 006 (specs/spec3.md, bloque 3: RF3-BIB-01 a RF3-BIB-14).
--
-- Los huecos de la story bible que necesitan el cambio del lector, Lean y la lectura: donde se
-- USA cada hecho (hasta ahora solo donde se establece), la edad de los personajes, un dia
-- numerico en la cronologia y las versiones que lee el lector.

-- Donde se usa un hecho sin establecerlo (RF3-BIB-01). Es estado: append-only y con escena de
-- origen, asi que la reversion de un capitulo lo borra con el resto.
CREATE TABLE hecho_uso (
    id        INTEGER PRIMARY KEY,
    novela_id INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    hecho_id  INTEGER NOT NULL REFERENCES hecho(id) ON DELETE CASCADE,
    escena_id INTEGER NOT NULL REFERENCES escena(id) ON DELETE CASCADE,
    via       TEXT NOT NULL,
    cita      TEXT,
    UNIQUE (hecho_id, escena_id, via),
    CHECK (via IN ('reafirma','menciona'))
);

CREATE INDEX ix_hecho_uso_hecho  ON hecho_uso (hecho_id);
CREATE INDEX ix_hecho_uso_escena ON hecho_uso (escena_id);

-- Las cuatro fuentes juntas (RF3-BIB-02): lo que el bloque 8 consulta para saber que regenerar.
CREATE VIEW hecho_escena AS
SELECT x.novela_id, x.hecho_id, x.escena_id, eo.capitulo_numero, eo.escena_orden, x.via, x.cita
FROM (
    SELECT novela_id, id AS hecho_id, escena_id, 'establece' AS via, cita FROM hecho
    UNION ALL SELECT novela_id, hecho_id, escena_id, via, cita FROM hecho_uso
    UNION ALL SELECT novela_id, hecho_id, escena_id, 'conoce', NULL FROM estado_conocimiento
    UNION ALL SELECT novela_id, hecho_id, escena_id, 'usa', NULL FROM uso_conocimiento
) x
JOIN escena_ordinal eo ON eo.escena_id = x.escena_id;

-- Edad el dia 0 de la historia (RF3-BIB-04). Nula solo en las novelas anteriores al bloque 3.
ALTER TABLE personaje ADD COLUMN edad INTEGER;

-- El nacimiento se deriva, y la formula vive solo aqui (RF3-BIB-05): a mitad de ano, para que
-- una analepsis de una semana no le quite un ano a nadie.
CREATE VIEW personaje_nacimiento AS
SELECT id AS personaje_id, novela_id, nombre, edad, -(edad * 365) - 182 AS nacimiento_dia
FROM personaje
WHERE edad IS NOT NULL;

-- Dias desde el comienzo de la historia; negativos antes (RF3-BIB-08).
ALTER TABLE evento ADD COLUMN dia INTEGER;

-- Un evento por fila con su lugar (RF3-BIB-10). Los previos del mundo no tienen escena.
CREATE VIEW cronologia AS
SELECT ev.novela_id, ev.id AS evento_id, ev.dia, ev.orden_interno, ev.fecha_interna,
       ev.descripcion, ev.tipo, ev.dramatizado, ev.escena_id,
       eo.capitulo_numero, eo.escena_orden, e.lugar_id, l.nombre AS lugar
FROM evento ev
LEFT JOIN escena e          ON e.id = ev.escena_id
LEFT JOIN escena_ordinal eo ON eo.escena_id = ev.escena_id
LEFT JOIN lugar l           ON l.id = e.lugar_id;

-- Los personajes de un evento son los de su escena: reparto y punto de vista.
CREATE VIEW cronologia_personaje AS
SELECT ev.id AS evento_id, p.id AS personaje_id, p.nombre
FROM evento ev
JOIN escena e    ON e.id = ev.escena_id
JOIN personaje p ON p.id = e.pov_id
UNION
SELECT ev.id, p.id, p.nombre
FROM evento ev
JOIN escena_personaje sp ON sp.escena_id = ev.escena_id
JOIN personaje p         ON p.id = sp.personaje_id;

-- Lo que leyo el lector (RF3-BIB-11). Canon: ninguna reversion lo toca, y el texto se copia
-- porque rehacer la escaleta borra los capitulos y sus compilados en cascada.
CREATE TABLE novela_version (
    id          INTEGER PRIMARY KEY,
    novela_id   INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    numero      INTEGER NOT NULL,
    motivo      TEXT NOT NULL,
    detalle     TEXT,
    titulo      TEXT NOT NULL,
    dedicatoria TEXT,
    creado_en   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (novela_id, numero),
    CHECK (motivo IN ('primera','relanzamiento','cambio_lector'))
);

CREATE TABLE novela_version_capitulo (
    id         INTEGER PRIMARY KEY,
    version_id INTEGER NOT NULL REFERENCES novela_version(id) ON DELETE CASCADE,
    numero     INTEGER NOT NULL,
    texto      TEXT NOT NULL,
    palabras   INTEGER NOT NULL DEFAULT 0,
    cambiado   INTEGER NOT NULL,
    UNIQUE (version_id, numero),
    CHECK (cambiado IN (0, 1))
);

-- Las novelas que ya estaban completadas nacen con su version 1 (RF3-BIB-13).
INSERT INTO novela_version (novela_id, numero, motivo, titulo, dedicatoria)
SELECT n.id, 1, 'primera', n.titulo, n.dedicatoria
FROM novela n
JOIN ejecucion x ON x.novela_id = n.id
WHERE x.estado IN ('completada', 'completada_con_avisos');

INSERT INTO novela_version_capitulo (version_id, numero, texto, palabras, cambiado)
SELECT v.id, c.numero, cc.texto, cc.palabras, 1
FROM novela_version v
JOIN capitulo c           ON c.novela_id = v.novela_id
JOIN capitulo_compilado cc ON cc.capitulo_id = c.id AND cc.estado = 'vigente';
