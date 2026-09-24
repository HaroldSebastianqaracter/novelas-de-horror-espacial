import { describe, expect, it } from "vitest";
import { compararCapitulo, compararPalabras, partirEnParrafos, reconstruir } from "./comparar";

/** Un generador con semilla: los casos salen siempre iguales. */
function conSemilla(semilla: number) {
  return () => {
    semilla = (semilla * 1103515245 + 12345) % 2 ** 31;
    return semilla / 2 ** 31;
  };
}

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
    const antes = ["Uno.", "Dos con Toby.", "Tres.", "Cuatro."].join("\n\n");
    const despues = ["Uno.", "Dos con Nala.", "Cuatro.", "Cinco nuevo."].join("\n\n");
    expect(compararCapitulo(antes, despues).map((p) => p.tipo)).toEqual(["igual", "cambiado", "quitado", "igual", "nuevo"]);
  });

  it("sin versión anterior, todo el capítulo es nuevo", () => {
    expect(compararCapitulo(undefined, "A.\n\nB.").map((p) => p.tipo)).toEqual(["nuevo", "nuevo"]);
  });

  it("casos límite: vacíos y párrafos repetidos", () => {
    expect(compararCapitulo("", "")).toEqual([]);
    expect(compararCapitulo("A.", "").map((p) => p.tipo)).toEqual(["quitado"]);
    expect(compararCapitulo("", "A.").map((p) => p.tipo)).toEqual(["nuevo"]);
    const antes = ["X", "X", "Y", "X"].join("\n\n");
    const despues = ["X", "Y", "X", "X", "X"].join("\n\n");
    const c = compararCapitulo(antes, despues);
    expect(c.filter((p) => p.tipo === "igual")).toHaveLength(3);
    expect(reconstruir(c, "antes")).toBe(antes);
    expect(reconstruir(c, "despues")).toBe(despues);
  });

  it("por encima del tope compara solo por párrafos, y la reconstrucción sigue exacta", () => {
    const antes = ["Uno dos tres.", "Cuatro cinco seis."].join("\n\n");
    const despues = ["Uno dos tres.", "Cuatro CINCO seis."].join("\n\n");
    const conTope = compararCapitulo(antes, despues, 10);
    expect(conTope.map((p) => p.tipo)).toEqual(["igual", "cambiado"]);
    expect(conTope[1]?.trozos).toEqual([
      { tipo: "quitado", texto: "Cuatro cinco seis." },
      { tipo: "nuevo", texto: "Cuatro CINCO seis." },
    ]);
    expect(compararCapitulo(antes, despues)[1]?.trozos.filter((t) => t.tipo !== "igual")).toEqual([
      { tipo: "quitado", texto: "cinco" },
      { tipo: "nuevo", texto: "CINCO" },
    ]);
    expect(reconstruir(conTope, "antes")).toBe(antes);
    expect(reconstruir(conTope, "despues")).toBe(despues);
  });

  it("aplicar la comparación da exactamente las dos versiones (propiedad, 300 casos)", () => {
    const azar = conSemilla(7);
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

  it("cambiar una palabra marca esa palabra y nada más (propiedad, 300 casos)", () => {
    const azar = conSemilla(11);
    for (let k = 0; k < 300; k++) {
      const parrafos = Array.from({ length: 1 + Math.floor(azar() * 5) }, (_, i) =>
        Array.from({ length: 3 + Math.floor(azar() * 6) }, (_, j) => `p${i}w${j}`).join(" "),
      );
      const i = Math.floor(azar() * parrafos.length);
      const palabras = (parrafos[i] as string).split(" ");
      const j = Math.floor(azar() * palabras.length);
      const vieja = palabras[j] as string;
      palabras[j] = "NUEVA";
      const despues = parrafos.map((p, n) => (n === i ? palabras.join(" ") : p)).join("\n\n");
      const c = compararCapitulo(parrafos.join("\n\n"), despues);
      expect(c.filter((p) => p.tipo !== "igual")).toHaveLength(1);
      expect(c.flatMap((p) => p.trozos).filter((t) => t.tipo !== "igual")).toEqual([
        { tipo: "quitado", texto: vieja },
        { tipo: "nuevo", texto: "NUEVA" },
      ]);
    }
  });
});
