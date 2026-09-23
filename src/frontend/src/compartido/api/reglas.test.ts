import { describe, expect, it } from "vitest";
import { haceTanto } from "../ui/Hace";
import { capituloEnCurso, instanteDeApi } from "./reglas";

describe("formato de la API", () => {
  it("una fecha sin zona es UTC, como la guarda SQLite", () => {
    expect(instanteDeApi("2026-09-23 15:44:20").toISOString()).toBe("2026-09-23T15:44:20.000Z");
    expect(instanteDeApi("2026-09-23T15:44:20").toISOString()).toBe("2026-09-23T15:44:20.000Z");
    expect(instanteDeApi("2026-09-23T15:44:20+02:00").toISOString()).toBe("2026-09-23T13:44:20.000Z");
    // Con la hora local por delante de UTC, leerla como local daría «hace 2 h».
    expect(haceTanto("2026-09-23 15:44:20", Date.parse("2026-09-23T15:44:30Z"))).toBe("hace 10 s");
  });

  it("el cursor más allá del último capítulo no es un capítulo en curso", () => {
    expect(capituloEnCurso({ capitulo_actual: 11, total_capitulos: 10 })).toBeNull();
    expect(capituloEnCurso({ capitulo_actual: 10, total_capitulos: 10 })).toBe(10);
    expect(capituloEnCurso({ capitulo_actual: null, total_capitulos: 10 })).toBeNull();
    expect(capituloEnCurso({ capitulo_actual: 3, total_capitulos: null })).toBe(3);
  });
});
