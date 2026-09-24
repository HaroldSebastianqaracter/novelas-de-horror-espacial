/**
 * Datos ficticios de la lectura (RF-FE-LEE) para la novela 6, que está completada: dos versiones
 * publicadas (la segunda, un cambio del lector que renombra al perro), su canon y el reparto de
 * cada escena. Nombres inventados; ningún nombre de persona real.
 */
import type { components } from "../esquema.gen";

type Esquemas = components["schemas"];
type VersionNovela = Esquemas["VersionNovela"];
type Escena = Esquemas["Escena"];
type EntidadCanon = Esquemas["PersonajeCanon"] | Esquemas["LugarCanon"] | Esquemas["ObjetoCanon"];

const fecha = (minutosAtras: number) =>
  new Date(Date.now() - minutosAtras * 60_000).toISOString().slice(0, 19).replace("T", " ");

const LUGARES = ["Bodega once", "Puente de mando", "Módulo de cultivos"] as const;
const REPARTO = [["Oda Varga", "Ciro Lenz"], ["Oda Varga", "Maura Quiles", "Ciro Lenz"], ["Oda Varga", "Toby"]] as const;

/** Tres escenas por capítulo. El perro solo sale en los capítulos 3 y 5. */
function escenasDe(numero: number): Escena[] {
  return [0, 1, 2].map((i) => {
    const conPerro = (numero === 3 || numero === 5) && i === 2;
    const reparto = conPerro ? ["Oda Varga", "Nala"] : [...(REPARTO[i % 2] ?? [])];
    return {
      orden: i + 1,
      pov: "Oda Varga",
      lugar: LUGARES[(numero + i) % LUGARES.length] ?? "Bodega once",
      reparto,
      objetivo: `Objetivo de la escena ${i + 1}`,
      conflicto: "La nave no responde como debería.",
      valor_inicial: "calma",
      valor_final: "miedo",
      tension: 5,
      analepsis: false,
    };
  });
}

function textoCapitulo(numero: number, perro: string): string {
  const escenas = [
    [
      `La bodega olía a óxido y a algo más dulce. Oda Varga se detuvo junto al contenedor once y escuchó durante el turno ${numero}.`,
      "Nada. Solo el zumbido del soporte vital y, debajo, muy debajo, un ritmo que no era el de las bombas.",
    ],
    [
      "En el puente, Ciro Lenz repasaba el registro por tercera vez. Las horas no cuadraban.",
      "—El ordenador no se equivoca —dijo Maura Quiles, sin apartar la vista del casco.",
      "—Entonces alguien le ha enseñado a mentir.",
    ],
    numero === 3 || numero === 5
      ? [
          `${perro} ladró dos veces hacia el conducto y se negó a dar un paso más.`,
          `Oda se agachó junto a ${perro} y le puso la mano en el lomo. Temblaba.`,
        ]
      : ["Cuando volvieron a la bodega, el contenedor once estaba abierto desde dentro."],
  ];
  return escenas.map((p) => p.join("\n\n")).join("\n\n* * *\n\n");
}

const palabras = (texto: string) => texto.split(/\s+/).filter(Boolean).length;
const TOTAL = 10;
const DEDICATORIA = "Para Oda, que nunca deja un problema a medias.";

function version(numero: number, perro: string, cambiados: number[], extra: Partial<VersionNovela>): VersionNovela {
  return {
    numero,
    motivo: "primera",
    titulo: "Deriva en el anillo Tántalo",
    dedicatoria: DEDICATORIA,
    detalle: null,
    creado_en: fecha(100 - numero * 30),
    capitulos_cambiados: cambiados,
    capitulos: Array.from({ length: TOTAL }, (_, i) => {
      const texto = textoCapitulo(i + 1, perro);
      return { numero: i + 1, texto, palabras: palabras(texto), cambiado: cambiados.includes(i + 1) };
    }),
    ...extra,
  };
}

const versionesIniciales: Record<number, VersionNovela[]> = {
  6: [
    version(1, "Toby", Array.from({ length: TOTAL }, (_, i) => i + 1), {}),
    version(2, "Nala", [3, 5], { motivo: "cambio_lector", detalle: "El perro se llama Nala" }),
  ],
};

export const versionesDe: Record<number, VersionNovela[]> = structuredClone(versionesIniciales);

export const canonDe: Record<number, Record<string, EntidadCanon[]>> = {
  6: {
    personajes: [
      { entidad: "personajes", id: 1, nombre: "Oda Varga", rol: "Ingeniera de a bordo", rol_narrativo: "protagonista", edad: 34, secreto: "No debería leerse en la ficha" },
      { entidad: "personajes", id: 2, nombre: "Ciro Lenz", rol: "Piloto", rol_narrativo: "aliado", edad: 41 },
      { entidad: "personajes", id: 3, nombre: "Maura Quiles", rol: "Capitana", rol_narrativo: "mentor", edad: 52 },
      { entidad: "personajes", id: 4, nombre: "Nala", rol: "Perra de la ingeniera", rol_narrativo: "aliado", edad: 6 },
      { entidad: "personajes", id: 5, nombre: "Eco", rol: "Lo que respira en el conducto", rol_narrativo: "antagonista", edad: null },
    ],
    lugares: LUGARES.map((nombre, i) => ({
      entidad: "lugares" as const,
      id: i + 1,
      nombre,
      tipo: i === 1 ? "sala de control" : "módulo",
      descripcion: ["Almacén de carga, frío y a oscuras.", "Donde se gobierna la nave.", "Invernadero de a bordo."][i] ?? null,
      sistemas_criticos: [],
    })),
    objetos: [{ entidad: "objetos", id: 1, nombre: "baliza de socorro", funcion_narrativa: "detonante" }],
  },
};

export const escenasDeNovela: Record<number, (numero: number) => Escena[]> = { 6: escenasDe };

export function restaurarLectura() {
  for (const id of Object.keys(versionesDe)) delete versionesDe[Number(id)];
  Object.assign(versionesDe, structuredClone(versionesIniciales));
}
