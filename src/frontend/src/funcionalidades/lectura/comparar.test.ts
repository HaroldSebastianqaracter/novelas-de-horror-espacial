import { describe, expect, it } from "vitest";
import { compararCapitulo, compararPalabras, partirEnParrafos, reconstruir } from "./comparar";

describe("qué cambió entre dos versiones (RF-FE-LEE-07)", () => {
  it("marca por palabras lo que cambió dentro de un párrafo", () => {
    expect(compararPalabras("El perro se llamaba Toby y ladraba.", "El perro se llamaba Nala y ladraba.")).toEqual([
      { tipo: "igual", texto: "El perro se llamaba " },
      { tipo: "quitado", texto: "Toby" },
      { tipo: "nuevo", texto: "Nala" },
      { tipo: "igual", texto: " y ladraba." },
    ]);
  });

  it("distingue párrafos iguales, cambiados, añadidos y quitados", () => {
    const antes = "Uno.\n\nDos con Toby.\n\nTres.\n\nCuatro.";
    const despues = "Uno.\n\nDos con Nala.\n\nCuatro.\n\nCinco nuevo.";
    expect(compararCapitulo(antes, despues).map((p) => p.tipo)).toEqual(["igual", "cambiado", "quitado", "igual", "nuevo"]);
  });

  it("sin versión anterior, todo el capítulo es nuevo", () => {
    expect(compararCapitulo(undefined, "A.\n\nB.").map((p) => p.tipo)).toEqual(["nuevo", "nuevo"]);
  });

  it("aplicar la comparación da exactamente las dos versiones (propiedad, 300 casos)", () => {
    let semilla = 7;
    const azar = () => {
      semilla = (semilla * 1103515245 + 12345) % 2 ** 31;
      return semilla / 2 ** 31;
    };
    const palabras = ["el", "perro", "Toby", "Nala", "ladró", "en", "la", "bodega", "once", "—dijo", "ella."];
    const parrafo = () =>
      Array.from({ length: 1 + Math.floor(azar() * 8) }, () => palabras[Math.floor(azar() * palabras.length)]).join(" ");
    const capitulo = () => Array.from({ length: 1 + Math.floor(azar() * 6) }, parrafo).join("\n\n");
    for (let k = 0; k < 300; k++) {
      const a = capitulo();
      const b = azar() < 0.3 ? a : capitulo();
      const c = compararCapitulo(a, b);
      expect(reconstruir(c, "antes")).toBe(partirEnParrafos(a).join("\n\n"));
      expect(reconstruir(c, "despues")).toBe(partirEnParrafos(b).join("\n\n"));
      if (a === b) expect(c.every((p) => p.tipo === "igual")).toBe(true);
    }
  });
});
