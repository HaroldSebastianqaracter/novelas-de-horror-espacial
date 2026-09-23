import { describe, expect, it } from "vitest";
import { accionesDe, destinoPara, intencionDeArrastre, MOTIVO_OTRA_ACTIVA } from "./acciones";

describe("intenciones que admite una tarjeta (RF-FE-TAB-03)", () => {
  it.each([
    ["configurada", ["arrancar"]],
    ["detenida", ["arrancar"]],
    ["planificando", ["parar"]],
    ["escaletando", ["parar"]],
    ["generando", ["parar"]],
    ["completada", []],
    ["completada_con_avisos", []],
    // Las de «Requiere atención» se abren; arrancar una en error se pide desde su detalle.
    ["parada", []],
    ["error", []],
    ["revisando", []],
    [null, []],
  ])("%s → %j", (estado, tipos) => {
    expect(accionesDe(estado, false).map((a) => a.tipo)).toEqual(tipos);
  });

  it("con otra novela en curso, arrancar se ve pero no se puede pedir, y dice por qué (RF-FE-TAB-04)", () => {
    expect(accionesDe("configurada", true)).toEqual([{ tipo: "arrancar", noDisponible: MOTIVO_OTRA_ACTIVA }]);
  });

  it("con otra novela en curso, parar la propia sigue disponible", () => {
    expect(accionesDe("generando", true)).toEqual([{ tipo: "parar" }]);
  });
});

describe("soltar una tarjeta (RF-FE-TAB-03)", () => {
  it.each([
    ["espera", "planificando", "arrancar"],
    ["planificando", "espera", "parar"],
    ["escribiendo", "espera", "parar"],
    ["espera", "escribiendo", null],
    ["espera", "terminada", null],
    ["planificando", "escribiendo", null],
    ["escribiendo", "terminada", null],
    ["terminada", "espera", null],
    ["atencion", "planificando", null],
  ] as const)("de %s a %s pide %s", (origen, destino, intencion) => {
    expect(intencionDeArrastre(origen, destino)).toBe(intencion);
  });

  it("la columna de origen no es destino, y las demás dicen si se puede soltar y por qué", () => {
    expect(destinoPara("configurada", false, "espera")).toEqual({ tipo: "origen" });
    expect(destinoPara("configurada", false, "planificando")).toEqual({ tipo: "valido", intencion: "arrancar" });
    expect(destinoPara("configurada", true, "planificando")).toEqual({ tipo: "invalido", motivo: MOTIVO_OTRA_ACTIVA });
    expect(destinoPara("configurada", false, "terminada")).toMatchObject({ tipo: "invalido" });
    expect(destinoPara("generando", false, "espera")).toEqual({ tipo: "valido", intencion: "parar" });
  });
});
