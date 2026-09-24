/**
 * «Aparece en» de la ficha (RF-FE-LEE-04). Mientras la API no sirva `/apariciones` (sección 5.2),
 * se calcula desde la escaleta: el punto de vista y el reparto de cada escena para los personajes,
 * y su lugar para los lugares, casados por nombre.
 */
import type { Estructura } from "../../compartido/api/tipos";
import { contieneTermino, normalizar } from "./texto";

export interface Apariciones {
  personajes: Map<string, number[]>;
  lugares: Map<string, number[]>;
}

/** Capítulos por nombre normalizado, solo entre los que existen en la versión que se lee. */
export function aparicionesDesdeEscaleta(estructura: Estructura, capitulosDeLaVersion: readonly number[]): Apariciones {
  const enVersion = new Set(capitulosDeLaVersion);
  const personajes = new Map<string, Set<number>>();
  const lugares = new Map<string, Set<number>>();
  const anotar = (mapa: Map<string, Set<number>>, nombre: string, capitulo: number) => {
    const clave = normalizar(nombre);
    if (!clave) return;
    (mapa.get(clave) ?? mapa.set(clave, new Set()).get(clave))?.add(capitulo);
  };
  for (const capitulo of estructura.capitulos) {
    if (!enVersion.has(capitulo.numero)) continue;
    for (const escena of capitulo.escenas ?? []) {
      anotar(personajes, escena.pov, capitulo.numero);
      for (const nombre of escena.reparto ?? []) anotar(personajes, nombre, capitulo.numero);
      anotar(lugares, escena.lugar, capitulo.numero);
    }
  }
  const ordenar = (mapa: Map<string, Set<number>>) =>
    new Map([...mapa].map(([k, v]) => [k, [...v].sort((a, b) => a - b)] as const));
  return { personajes: ordenar(personajes), lugares: ordenar(lugares) };
}

/** En una versión anterior: los capítulos cuya prosa escribe el nombre, por palabras completas. */
export function aparicionesEnLaProsa(
  capitulos: readonly { numero: number; texto: string }[],
  nombres: { personajes: readonly string[]; lugares: readonly string[] },
): Apariciones {
  const buscar = (lista: readonly string[]) =>
    new Map(lista.map((n) => [normalizar(n), capitulos.filter((c) => contieneTermino(c.texto, n)).map((c) => c.numero)] as const));
  return { personajes: buscar(nombres.personajes), lugares: buscar(nombres.lugares) };
}

export const capitulosDe = (apariciones: Map<string, number[]>, nombre: string) => apariciones.get(normalizar(nombre)) ?? [];
