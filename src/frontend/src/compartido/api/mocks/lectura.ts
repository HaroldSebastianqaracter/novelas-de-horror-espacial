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
    const reparto = conPerro ? ["Oda Varga", nombreDelPerro()] : [...(REPARTO[i % 2] ?? [])];
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

const canonInicial = structuredClone(canonDe);

/** El perro cambia de nombre con un cambio del lector: la escaleta lo sigue. */
function nombreDelPerro(): string {
  return canonDe[6]?.personajes?.find((p) => p.id === 4)?.nombre ?? "Nala";
}

export const escenasDeNovela: Record<number, (numero: number) => Escena[]> = { 6: escenasDe };

/** Hechos del canon de la novela 6, con dónde se establecen y se usan (`hecho_escena`). */
export const hechosDe: Record<number, { id: number; sujeto_tipo: string; sujeto_nombre: string; atributo: string; valor: string; categoria: string; capitulo_origen: number; vigente: boolean }[]> = {
  6: [
    { id: 31, sujeto_tipo: "objeto", sujeto_nombre: "contenedor once", atributo: "estado", valor: "abierto desde dentro", categoria: "estado", capitulo_origen: 1, vigente: true },
    { id: 32, sujeto_tipo: "lugar", sujeto_nombre: "Bodega once", atributo: "olor", valor: "óxido", categoria: "rasgo", capitulo_origen: 1, vigente: true },
  ],
};
export const usosDe: Record<number, Record<number, { capitulo: number; escena_orden: number; via: string; cita: string | null }[]>> = {
  6: {
    31: [1, 2, 4, 6, 7, 8, 9, 10].map((capitulo) => ({ capitulo, escena_orden: 3, via: capitulo === 1 ? "establece" : "reafirma", cita: "el contenedor once estaba abierto desde dentro" })),
    32: Array.from({ length: 10 }, (_, i) => ({ capitulo: i + 1, escena_orden: 1, via: i === 0 ? "establece" : "menciona", cita: "olía a óxido" })),
  },
};

export interface CambioSimulado {
  id: number;
  estado: string;
  peticion: string;
  objetivo: Record<string, unknown>;
  cita: { capitulo: number; texto: string } | null;
  cambio: { tipo: string; antes: string | null; despues: string | null } | null;
  capitulos: number[];
  informe: unknown;
  version: number | null;
  creado_en: string;
}
export const cambiosDe: Record<number, CambioSimulado[]> = {};
let siguienteCambio = 1;

const escapar = (texto: string) => texto.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const palabrasCompletas = (termino: string) =>
  new RegExp(String.raw`(^|[^\p{L}\p{N}])` + escapar(termino) + String.raw`(?=$|[^\p{L}\p{N}])`, "gu");

/** La regla del worker, simplificada: una entidad, los capítulos cuya prosa la nombra; un hecho, sus usos. */
export function alcanceDe(novelaId: number, objetivo: Record<string, unknown>, cita?: { capitulo: number } | null): number[] | null {
  const ultima = versionesDe[novelaId]?.at(-1);
  if (!ultima) return null;
  if (objetivo.tipo === "entidad") {
    const entidad = canonDe[novelaId]?.[String(objetivo.entidad)]?.find((e) => e.id === Number(objetivo.id));
    if (!entidad) return null;
    return ultima.capitulos.filter((c) => palabrasCompletas(entidad.nombre).test(c.texto)).map((c) => c.numero);
  }
  if (objetivo.tipo === "hecho") {
    const usos = usosDe[novelaId]?.[Number(objetivo.hecho_id)];
    if (!usos) return null;
    return [...new Set(usos.map((u) => u.capitulo))].sort((a, b) => a - b);
  }
  return cita ? [cita.capitulo] : [];
}

/** Registra un cambio aceptado, en `reescribiendo`. */
export function registrarCambio(novelaId: number, payload: Record<string, unknown>, capitulos: number[]): CambioSimulado {
  const objetivo = payload.objetivo as Record<string, unknown>;
  let cambio: CambioSimulado["cambio"] = null;
  const nuevoNombre = /se llam[ae]\s+([\p{L}]+)/u.exec(String(payload.peticion))?.[1];
  if (objetivo.tipo === "entidad" && nuevoNombre) {
    const entidad = canonDe[novelaId]?.[String(objetivo.entidad)]?.find((e) => e.id === Number(objetivo.id));
    cambio = { tipo: "renombrar", antes: entidad?.nombre ?? null, despues: nuevoNombre };
  } else {
    cambio = { tipo: "cambiar_hecho", antes: null, despues: String(payload.peticion) };
  }
  const registro: CambioSimulado = {
    id: siguienteCambio++,
    estado: "reescribiendo",
    peticion: String(payload.peticion),
    objetivo,
    cita: (payload.cita as CambioSimulado["cita"]) ?? null,
    cambio,
    capitulos,
    informe: null,
    version: null,
    creado_en: fecha(0),
  };
  (cambiosDe[novelaId] ??= []).push(registro);
  return registro;
}

/** Aplica el cambio y publica la versión siguiente, motivo `cambio_lector` (RF3-BIB-12). */
export function publicarCambio(novelaId: number, registro: CambioSimulado): number | null {
  const lista = versionesDe[novelaId];
  const ultima = lista?.at(-1);
  if (!lista || !ultima) return null;
  const capitulos = ultima.capitulos.map((c) => {
    if (!registro.capitulos.includes(c.numero)) return { ...c, cambiado: false };
    let texto = c.texto;
    const { cambio } = registro;
    if (cambio?.tipo === "renombrar" && cambio.antes && cambio.despues) {
      texto = texto.replace(palabrasCompletas(cambio.antes), (_, antes: string) => `${antes}${cambio.despues}`);
    } else {
      const peticion = registro.peticion.replace(/\.$/, "");
      texto = `${texto}\n\n(Reescrito para que ${peticion.charAt(0).toLowerCase()}${peticion.slice(1)}.)`;
    }
    return { ...c, texto, palabras: texto.split(/\s+/).filter(Boolean).length, cambiado: texto !== c.texto };
  });
  const numero = ultima.numero + 1;
  lista.push({
    ...ultima,
    numero,
    motivo: "cambio_lector",
    detalle: registro.peticion,
    creado_en: fecha(0),
    capitulos,
    capitulos_cambiados: capitulos.filter((c) => c.cambiado).map((c) => c.numero),
  });
  if (registro.cambio?.tipo === "renombrar" && registro.cambio.despues) {
    const entidad = canonDe[novelaId]?.[String(registro.objetivo.entidad)]?.find((e) => e.id === Number(registro.objetivo.id));
    if (entidad) entidad.nombre = registro.cambio.despues;
  }
  Object.assign(registro, { estado: "aplicado", version: numero });
  return numero;
}

export function restaurarLectura() {
  for (const id of Object.keys(versionesDe)) delete versionesDe[Number(id)];
  Object.assign(versionesDe, structuredClone(versionesIniciales));
  for (const id of Object.keys(canonDe)) delete canonDe[Number(id)];
  Object.assign(canonDe, structuredClone(canonInicial));
  for (const id of Object.keys(cambiosDe)) delete cambiosDe[Number(id)];
  siguienteCambio = 1;
}
