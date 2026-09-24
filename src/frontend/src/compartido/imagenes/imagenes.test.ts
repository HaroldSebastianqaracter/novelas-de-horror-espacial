import { describe, expect, it } from "vitest";
import { SUBGENEROS } from "../api/brief";
import { PORTADA_GENERICA, portadaDe } from ".";

describe("portada por subgénero (RF-FE-IMG-01)", () => {
  it("cada subgénero del brief tiene su portada, distinta de la genérica, en los dos tamaños", () => {
    const vistas = new Set<string>();
    for (const s of SUBGENEROS) {
      const p = portadaDe(s);
      expect(p, s).not.toBe(PORTADA_GENERICA);
      expect(p.web).toContain(`portada-${s}-web`);
      expect(p.impresion).toContain(`portada-${s}.`);
      vistas.add(p.web);
    }
    expect(vistas.size).toBe(SUBGENEROS.length);
  });

  it("sin subgénero, o con uno que no se conoce, la genérica", () => {
    expect(portadaDe(null)).toBe(PORTADA_GENERICA);
    expect(portadaDe(undefined)).toBe(PORTADA_GENERICA);
    expect(portadaDe("terror_submarino")).toBe(PORTADA_GENERICA);
  });
});
