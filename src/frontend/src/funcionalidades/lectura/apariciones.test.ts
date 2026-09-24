import { describe, expect, it } from "vitest";
import type { Cambio } from "../../compartido/api/cambios";
import { aparicionesDeApi, mencionesEnLaProsa, nombresEnVersion, reescritosDespues } from "./apariciones";

const renombre = (version: number, antes: string, despues: string, estado = "aplicado"): Cambio => ({
  id: version,
  estado,
  peticion: `Que se llame ${despues}`,
  objetivo: { tipo: "entidad", entidad: "personajes", id: 2 },
  cita: null,
  cambio: { tipo: "renombrar", antes, despues, tabla: "personaje", entidad_id: 2 },
  capitulos: [1],
  version,
  creado_en: "2026-09-24 13:37:04",
});

describe("los nombres de una versión anterior (RF-FE-LEE-04)", () => {
  it("con dos renombres seguidos, cada versión lleva el nombre que tenía entonces", () => {
    // El orden de la lista no importa: manda la versión que publicó cada cambio.
    const cambios = [renombre(3, "Brann", "Corvo"), renombre(2, "Vaan", "Brann")];
    expect(nombresEnVersion(cambios, 1).get("personajes-2")).toBe("Vaan");
    expect(nombresEnVersion(cambios, 2).get("personajes-2")).toBe("Brann");
    expect(nombresEnVersion(cambios, 3).size).toBe(0);
  });

  it("no cuenta los cambios que no se aplicaron ni los que no renombran", () => {
    const fallido = { ...renombre(2, "Vaan", "Brann", "fallido"), version: null };
    const hecho: Cambio = { ...renombre(2, "doce metros", "cuarenta metros"), cambio: { tipo: "cambiar_hecho", antes: "doce metros", despues: "cuarenta metros" } };
    expect(nombresEnVersion([fallido, hecho], 1).size).toBe(0);
  });
});

const capitulos = [
  { numero: 1, texto: "Idris abrió la compuerta." },
  { numero: 2, texto: "Vaan esperaba en la esclusa." },
  { numero: 3, texto: "Nadie habló." },
];

describe("menciones en la prosa, sin apariciones en la story bible (RF-FE-LEE-04)", () => {
  const prosa = [
    { numero: 1, texto: "La estación Roldán dormía." },
    { numero: 2, texto: "Nadie habló del nodo." },
    { numero: 3, texto: "En el Nodo de Retransmisión Roldán hacía frío." },
    { numero: 4, texto: "Rolda sin tilde no cuenta; roldán en minúscula tampoco." },
  ];
  it("cuenta el nombre entero o una palabra suya con mayúscula de tres letras o más, sin mirar tildes", () => {
    expect(mencionesEnLaProsa(prosa, "Nodo de Retransmisión Roldán")).toEqual([1, 3]);
    expect(mencionesEnLaProsa(prosa, "el eje")).toEqual([]);
  });
});

describe("apariciones de la API (RF-FE-LEE-04)", () => {
  it("se quedan con los capítulos que existen en la versión", () => {
    const a = aparicionesDeApi({ personajes: [{ id: 1, nombre: "Idris", capitulos: [1, 3, 11] }], lugares: [] }, capitulos);
    expect(a.personajes.get(1)).toEqual([1, 3]);
  });

  it("en los capítulos que un relanzamiento reescribió después, buscan el nombre de entonces en la prosa", () => {
    // Ahora «Brann» está en el 3 (prosa nueva); en esta versión, el 2 lo nombra como Vaan y el 3 no.
    const api = { personajes: [{ id: 2, nombre: "Brann", capitulos: [1, 3] }], lugares: [] };
    const a = aparicionesDeApi(api, capitulos, new Set([2, 3]), (_e, _id, actual) => (actual === "Brann" ? "Vaan" : actual));
    expect(a.personajes.get(2)).toEqual([1, 2]);
  });

  it("solo los relanzamientos posteriores reescriben: los cambios del lector no", () => {
    const v = (numero: number, motivo: string, capitulos_cambiados: number[]) =>
      ({ numero, motivo, capitulos_cambiados, titulo: "", dedicatoria: null, detalle: null, creado_en: "" }) as never;
    const versiones = [v(1, "primera", [1, 2, 3]), v(2, "relanzamiento", [3]), v(3, "cambio_lector", [1, 2]), v(4, "relanzamiento", [2])];
    expect([...reescritosDespues(versiones, 1)].sort()).toEqual([2, 3]);
    expect([...reescritosDespues(versiones, 2)]).toEqual([2]);
    expect(reescritosDespues(versiones, 4).size).toBe(0);
  });
});
