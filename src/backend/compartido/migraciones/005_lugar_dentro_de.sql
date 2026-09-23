-- Migracion 005 (specs/spec2.md, fase 10: RF2-PER-13).
--
-- Un lugar puede estar dentro de otro: la sala de lechos del sector 4 esta dentro del anillo
-- de habitacion. Sin esta relacion, la puerta 3 veia un objeto «movido sin traslado» cuando
-- pasaba del anillo a una sala del propio anillo (RF2-PIPE-26). Nullable: un lugar sin
-- contenedor declarado es un sitio aparte, como hasta ahora.

ALTER TABLE lugar ADD COLUMN dentro_de_id INTEGER REFERENCES lugar(id) ON DELETE SET NULL;
