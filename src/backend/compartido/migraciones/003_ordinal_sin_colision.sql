-- Migracion 003 (specs/spec2.md, fase 9: RF2-PER-12).
--
-- El orden global de escena era capitulo * 1000 + orden, que colisionaba en cuanto un
-- capitulo pasaba de 999 escenas: la escena 1500 del capitulo 1 quedaba DESPUES de la 1 del
-- capitulo 2. Pasa a capitulo * 1.000.000 + orden, y un trigger rechaza un orden fuera de
-- 1..999.999, de modo que la colision es imposible y no solo improbable.

DROP VIEW IF EXISTS escena_ordinal;

CREATE VIEW escena_ordinal AS
SELECT e.id            AS escena_id,
       e.novela_id     AS novela_id,
       e.capitulo_id   AS capitulo_id,
       c.numero        AS capitulo_numero,
       e.orden         AS escena_orden,
       (c.numero * 1000000 + e.orden) AS ordinal
FROM escena e
JOIN capitulo c ON c.id = e.capitulo_id;

CREATE TRIGGER escena_orden_en_rango BEFORE INSERT ON escena
WHEN NEW.orden < 1 OR NEW.orden > 999999
BEGIN
    SELECT RAISE(ABORT, 'escena.orden fuera de 1..999999: el orden global de escena colisionaria');
END;

CREATE TRIGGER escena_orden_en_rango_al_cambiar BEFORE UPDATE OF orden ON escena
WHEN NEW.orden < 1 OR NEW.orden > 999999
BEGIN
    SELECT RAISE(ABORT, 'escena.orden fuera de 1..999999: el orden global de escena colisionaria');
END;
