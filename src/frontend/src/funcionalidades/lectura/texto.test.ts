import { describe, expect, it } from "vitest";
import { contieneTermino, normalizar } from "./texto";

describe("términos por palabras completas, sin tildes ni mayúsculas", () => {
  it("normaliza tildes, mayúsculas y espacios", () => {
    expect(normalizar("  Módulo   de CULTIVOS ")).toBe("modulo de cultivos");
  });

  it("encuentra el término entero y no dentro de otra palabra", () => {
    expect(contieneTermino("Oda se agachó junto a Nala y le puso la mano", "Nala")).toBe(true);
    expect(contieneTermino("Las nalas no existen", "Nala")).toBe(false);
    expect(contieneTermino("—Nala, quieta.", "nala")).toBe(true);
    expect(contieneTermino("En el módulo de cultivos", "Modulo de cultivos")).toBe(true);
    expect(contieneTermino("cualquier texto", "   ")).toBe(false);
    expect(contieneTermino("vale 3.5 (aprox.)", "3.5 (aprox.)")).toBe(true);
  });
});
