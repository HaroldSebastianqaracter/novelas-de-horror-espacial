-- Migracion 010 (specs/spec3.md, bloque 5: RF3-GRD-01 y RF3-GRD-04).
--
-- Los terminos que la prosa no puede usar y el registro de lo que se decidio con ellos. Los
-- vetados del brief no se copian aqui: el brief ya esta en SQLite y se leen de el.

CREATE TABLE termino_vetado (
    id          INTEGER PRIMARY KEY,
    -- Vacio: global. Con valor: solo esa novela.
    novela_id   INTEGER REFERENCES novela(id) ON DELETE CASCADE,
    termino     TEXT NOT NULL,
    -- En los globales, la intensidad mas fuerte en la que el termino sigue vetado.
    hasta_nivel TEXT NOT NULL DEFAULT 'intenso',
    -- Expresiones, en JSON, dentro de las cuales el termino no cuenta.
    excepciones TEXT NOT NULL DEFAULT '[]',
    CHECK (hasta_nivel IN ('atmosferico', 'tension', 'intenso')),
    CHECK (json_valid(excepciones) AND json_type(excepciones) = 'array')
);

CREATE UNIQUE INDEX ux_termino_vetado ON termino_vetado (COALESCE(novela_id, 0), termino);

-- Append-only y fuera de toda reversion: es lo que el sistema decidio (RF3-GRD-04).
CREATE TABLE decision_politica (
    id              INTEGER PRIMARY KEY,
    novela_id       INTEGER NOT NULL REFERENCES novela(id) ON DELETE CASCADE,
    capitulo        INTEGER NOT NULL,
    intento         INTEGER NOT NULL,
    termino         TEXT NOT NULL,
    origen          TEXT NOT NULL,
    forma           TEXT NOT NULL,
    fragmento       TEXT NOT NULL,
    inicio          INTEGER NOT NULL,
    fin             INTEGER NOT NULL,
    accion          TEXT NOT NULL,
    huella_politica TEXT NOT NULL,
    huella_texto    TEXT NOT NULL,
    creado_en       TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (origen IN ('global', 'novela', 'brief')),
    CHECK (accion IN ('reintentar', 'parar'))
);

CREATE INDEX ix_decision_politica_novela ON decision_politica (novela_id, capitulo);

-- La lista global prudente (decision sin entrevistar, spec3 3.5): palabras que casi nunca
-- tienen otro sentido. Cada forma que importa es su fila: la busqueda solo trata el plural.
INSERT INTO termino_vetado (termino, hasta_nivel, excepciones) VALUES
    -- Contenido sexual: ningun nivel lo admite.
    ('sexo', 'intenso', '["sexo del embrion", "sexo del feto", "sexo de la criatura"]'),
    ('sexual', 'intenso', '[]'),
    ('sexuales', 'intenso', '[]'),
    ('orgasmo', 'intenso', '[]'),
    ('erotico', 'intenso', '[]'),
    ('erotica', 'intenso', '[]'),
    ('pornografia', 'intenso', '[]'),
    ('pornografico', 'intenso', '[]'),
    -- Atmosferico: sin sangre, sin cadaveres, sin heridas descritas.
    ('sangre', 'atmosferico', '["a sangre fria", "sangre fria", "de sangre caliente", "helo la sangre", "helaba la sangre", "hiela la sangre", "helada la sangre", "sangre se le helo", "sangre se le helaba", "sangre se le hiela", "banco de sangre", "hermanos de sangre", "en la sangre", "analisis de sangre", "transfusion de sangre", "muestra de sangre", "misma sangre", "sangre se le subio", "grupo de sangre"]'),
    ('sangrar', 'atmosferico', '[]'),
    ('sangraba', 'atmosferico', '[]'),
    ('sangraban', 'atmosferico', '[]'),
    ('sangrando', 'atmosferico', '[]'),
    ('sangro', 'atmosferico', '[]'),
    ('sangraron', 'atmosferico', '[]'),
    ('desangro', 'atmosferico', '[]'),
    ('desangrar', 'atmosferico', '[]'),
    ('desangraba', 'atmosferico', '[]'),
    ('desangrando', 'atmosferico', '[]'),
    ('sangrante', 'atmosferico', '[]'),
    ('desangraron', 'atmosferico', '[]'),
    ('desangrandose', 'atmosferico', '[]'),
    ('desangrado', 'atmosferico', '[]'),
    ('desangrada', 'atmosferico', '[]'),
    ('sanguinolento', 'atmosferico', '[]'),
    ('sanguinolenta', 'atmosferico', '[]'),
    ('sangrienta', 'atmosferico', '[]'),
    ('sangriento', 'atmosferico', '[]'),
    ('ensangrentado', 'atmosferico', '[]'),
    ('ensangrentada', 'atmosferico', '[]'),
    ('cadaver', 'atmosferico', '[]'),
    ('degollado', 'atmosferico', '[]'),
    ('degollada', 'atmosferico', '[]'),
    ('degollar', 'atmosferico', '[]'),
    ('degollo', 'atmosferico', '[]'),
    ('degollaron', 'atmosferico', '[]'),
    ('degollaban', 'atmosferico', '[]'),
    ('degollando', 'atmosferico', '[]'),
    -- Tension: sin tortura, sin mutilacion, sin visceras.
    ('tortura', 'tension', '["es una tortura", "era una tortura", "fue una tortura", "sera una tortura", "una tortura de espera", "tortura china", "autentica tortura", "la tortura de no"]'),
    ('torturar', 'tension', '[]'),
    ('torturado', 'tension', '[]'),
    ('torturada', 'tension', '[]'),
    ('torturaba', 'tension', '[]'),
    ('torturo', 'tension', '[]'),
    ('torturaron', 'tension', '[]'),
    ('torturando', 'tension', '[]'),
    ('torturaban', 'tension', '[]'),
    ('torturador', 'tension', '[]'),
    ('torturadores', 'tension', '[]'),
    ('mutilado', 'tension', '[]'),
    ('mutilada', 'tension', '[]'),
    ('mutilacion', 'tension', '[]'),
    ('mutilar', 'tension', '[]'),
    ('mutilo', 'tension', '[]'),
    ('mutilaron', 'tension', '[]'),
    ('mutilaban', 'tension', '[]'),
    ('mutilando', 'tension', '[]'),
    ('desmembrado', 'tension', '[]'),
    ('desmembrada', 'tension', '[]'),
    ('desmembrar', 'tension', '[]'),
    ('desmembro', 'tension', '[]'),
    ('desmembraron', 'tension', '[]'),
    ('desmembraban', 'tension', '[]'),
    ('descuartizar', 'tension', '[]'),
    ('descuartizado', 'tension', '[]'),
    ('descuartizada', 'tension', '[]'),
    ('descuartizo', 'tension', '[]'),
    ('descuartizaron', 'tension', '[]'),
    ('descuartizaba', 'tension', '[]'),
    ('decapitado', 'tension', '[]'),
    ('decapitada', 'tension', '[]'),
    ('decapitar', 'tension', '[]'),
    ('decapito', 'tension', '[]'),
    ('decapitaron', 'tension', '[]'),
    ('decapitaban', 'tension', '[]'),
    ('decapitando', 'tension', '[]'),
    ('visceras', 'tension', '[]'),
    ('destripado', 'tension', '[]'),
    ('destripada', 'tension', '[]'),
    ('destripar', 'tension', '[]'),
    ('destripo', 'tension', '[]'),
    ('destriparon', 'tension', '[]'),
    ('destripaban', 'tension', '[]'),
    ('entrañas', 'tension', '[]'),
    ('evisceracion', 'tension', '[]');
