import { describe, expect, it } from "vitest";
import { ESTADOS_EJECUCION } from "../../compartido/api/reglas";
import { COLUMNAS, ESTADOS_ATENCION, grupoDe } from "./columnas";

describe("columnas del tablero (RF-FE-TAB-01)", () => {
  it.each([
    ["configurada", "espera"],
    ["detenida", "espera"],
    ["planificando", "planificando"],
    ["escaletando", "planificando"],
    ["generando", "escribiendo"],
    ["completada", "terminada"],
    ["completada_con_avisos", "terminada"],
    ["parada", "atencion"],
    ["error", "atencion"],
  ])("%s cae en %s", (estado, grupo) => {
    expect(grupoDe(estado)).toBe(grupo);
  });

  it("una novela sin ejecución cae en «En espera»", () => {
    expect(grupoDe(null)).toBe("espera");
    expect(grupoDe(undefined)).toBe("espera");
  });

  it("un estado desconocido no se esconde: cae en «En espera»", () => {
    expect(grupoDe("revisando")).toBe("espera");
  });

  it("cada estado está en una sola columna o en el carril, y ninguno se queda fuera", () => {
    const repartidos = [...COLUMNAS.flatMap((c) => c.estados), ...ESTADOS_ATENCION];
    expect([...repartidos].sort()).toEqual([...ESTADOS_EJECUCION].sort());
  });

  it("los estados que declara cada columna coinciden con los que agrupa", () => {
    for (const columna of COLUMNAS) {
      for (const estado of columna.estados) expect(grupoDe(estado)).toBe(columna.id);
    }
  });
});
