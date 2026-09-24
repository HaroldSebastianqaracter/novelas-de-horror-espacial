/**
 * «Aparece en» de la ficha (RF-FE-LEE-04), por id de entidad, desde `GET /apariciones` (la vista
 * `presencia` y el lugar de cada escena). Vale también para una versión anterior: un cambio del
 * lector renombra o cambia un hecho, pero no mueve a nadie de capítulo. Lo que sí cambia es el
 * nombre, y ese sale del registro de cambios. Un relanzamiento, en cambio, regenera capítulos: en
 * los que reescribió después de la versión que se lee, la presencia de ahora no vale.
 */
import type { Cambio } from "../../compartido/api/cambios";
import type { EntidadLectura } from "../../compartido/api/consultas";
import type { Apariciones as AparicionesApi, VersionResumen } from "../../compartido/api/tipos";
import { contieneTermino } from "./texto";

export interface Apariciones {
  personajes: Map<number, number[]>;
  lugares: Map<number, number[]>;
}

/**
 * Lo de la API, solo con los capítulos que existen en la versión que se lee. En los `reescritos`
 * por un relanzamiento posterior, se busca en cambio el nombre que la entidad tenía en esa versión
 * en su propia prosa, por palabras completas.
 */
export function aparicionesDeApi(
  api: AparicionesApi,
  capitulos: readonly { numero: number; texto: string }[],
  reescritos: ReadonlySet<number> = new Set(),
  nombreEnVersion: (entidad: "personajes" | "lugares", id: number, actual: string) => string = (_e, _i, actual) => actual,
): Apariciones {
  const enVersion = new Set(capitulos.map((c) => c.numero));
  const porId = (entidad: "personajes" | "lugares") =>
    new Map(
      api[entidad].map((a) => {
        const nombre = nombreEnVersion(entidad, a.id, a.nombre);
        const deLaApi = a.capitulos.filter((n) => enVersion.has(n) && !reescritos.has(n));
        const deLaProsa = capitulos.filter((c) => reescritos.has(c.numero) && contieneTermino(c.texto, nombre)).map((c) => c.numero);
        return [a.id, [...new Set([...deLaApi, ...deLaProsa])].sort((x, y) => x - y)] as const;
      }),
    );
  return { personajes: porId("personajes"), lugares: porId("lugares") };
}

/** Los capítulos que un relanzamiento publicado después de la versión `numero` reescribió. */
export function reescritosDespues(versiones: readonly VersionResumen[], numero: number): Set<number> {
  return new Set(
    versiones.filter((v) => v.numero > numero && v.motivo !== "cambio_lector").flatMap((v) => v.capitulos_cambiados),
  );
}

export const capitulosDe = (apariciones: Map<number, number[]>, id: number) => apariciones.get(id) ?? [];

const ENTIDAD_DE_TABLA: Record<string, EntidadLectura> = { personaje: "personajes", lugar: "lugares", objeto: "objetos" };

/**
 * El nombre que tenía cada entidad en la versión `numero`, para las que un cambio del lector
 * renombró después: el `antes` del primer cambio aplicado con una versión posterior. La clave es
 * `entidad-id` (`personajes-4`).
 */
export function nombresEnVersion(cambios: readonly Cambio[], numero: number): Map<string, string> {
  const nombres = new Map<string, string>();
  const posteriores = cambios
    .filter((c) => c.estado === "aplicado" && c.version !== null && c.version !== undefined && c.version > numero)
    .sort((a, b) => (a.version ?? 0) - (b.version ?? 0));
  for (const { cambio } of posteriores) {
    if (cambio?.tipo !== "renombrar" || !cambio.antes || !cambio.tabla || typeof cambio.entidad_id !== "number") continue;
    const entidad = ENTIDAD_DE_TABLA[cambio.tabla];
    const clave = `${entidad ?? cambio.tabla}-${cambio.entidad_id}`;
    if (entidad && !nombres.has(clave)) nombres.set(clave, cambio.antes);
  }
  return nombres;
}
