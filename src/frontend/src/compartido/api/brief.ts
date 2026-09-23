/**
 * DEUDA (RF-FE-API-04). El payload de `crear_novela` es un `object` sin esquema en el OpenAPI,
 * así que el brief no se puede generar: esto es una copia a mano de `src/backend/compartido/brief.py`
 * (RF3-BRF-01 y RF3-BRF-02), con sus mismos límites. Se borra cuando la API tipe el payload
 * (sección 5 de specs/spec-frontend.md).
 *
 * Aquí solo hay forma. Qué falta y qué se contradice lo decide la API (RF-FE-BRF-04): el cliente
 * no reimplementa `analizar`.
 */
import { ErrorApi } from "./cliente";

export type Pronombres = "el" | "ella" | "neutro";
export type Ocasion = "cumpleanos" | "aniversario" | "boda" | "jubilacion" | "navidad" | "otra";
export type Intensidad = "atmosferico" | "tension" | "intenso";
export type Tono = "sobrio" | "emotivo" | "humor_negro" | "aventura";
export type Subgenero =
  | "terror_corporal"
  | "infeccion"
  | "horror_cosmico"
  | "slasher_espacial"
  | "ia_hostil"
  | "supervivencia";

export const PRONOMBRES: readonly Pronombres[] = ["el", "ella", "neutro"];
export const OCASIONES: readonly Ocasion[] = ["cumpleanos", "aniversario", "boda", "jubilacion", "navidad", "otra"];
export const TONOS: readonly Tono[] = ["sobrio", "emotivo", "humor_negro", "aventura"];
export const SUBGENEROS: readonly Subgenero[] = [
  "terror_corporal",
  "infeccion",
  "horror_cosmico",
  "slasher_espacial",
  "ia_hostil",
  "supervivencia",
];

/** Un rasgo o un recuerdo. Sin `codigo` ni `cita`: los pone el backend o no aplican (RF-FE-BRF-03). */
export interface ElementoPersonal {
  texto: string;
  obligatorio: boolean;
}

export interface Allegado {
  nombre: string;
  relacion: string;
  rasgos: string[];
  obligatorio: boolean;
}

/** Lo que el formulario envía. Sin `texto_libre` (RF-FE-BRF-02). */
export interface Brief {
  destinatario: {
    nombre?: string;
    edad?: number;
    pronombres?: Pronombres;
    rasgos: ElementoPersonal[];
  };
  recuerdos: ElementoPersonal[];
  allegados: Allegado[];
  ocasion?: Ocasion;
  ocasion_detalle?: string;
  quien_regala?: string;
  mensaje_dedicatoria?: string;
  intensidad?: Intensidad;
  tono?: Tono;
  subgenero?: Subgenero;
  capitulos: number;
  vetados: string[];
}

/** Límites de forma de `brief.py`. */
export const LIMITES = {
  nombre: 60,
  edad: { min: 1, max: 110 },
  rasgos: 8,
  recuerdos: 10,
  allegados: 6,
  textoElemento: 500,
  nombreAllegado: 60,
  relacion: 60,
  rasgosAllegado: 5,
  ocasionDetalle: 120,
  quienRegala: 80,
  mensajeDedicatoria: 300,
  capitulos: { min: 3, max: 10, defecto: 10 },
  vetados: 30,
} as const;

export interface NivelIntensidad {
  edadMinima: number;
  publico: string;
  admite: string;
  noAdmite: string;
}

/** Copia de `INTENSIDADES` (RF3-BRF-02). */
export const INTENSIDADES: Record<Intensidad, NivelIntensidad> = {
  atmosferico: {
    edadMinima: 10,
    publico: "juvenil, desde 10 años",
    admite: "inquietud, amenaza sugerida, peligro que se resuelve, pérdidas sin descripción",
    noAdmite: "muertes en escena, sangre, heridas descritas, crueldad",
  },
  tension: {
    edadMinima: 14,
    publico: "adolescente, desde 14 años",
    admite: "peligro real, muertes fuera de plano, heridas sin detalle anatómico",
    noAdmite: "violencia gráfica, tortura, terror corporal explícito",
  },
  intenso: {
    edadMinima: 18,
    publico: "adulto",
    admite: "violencia explícita al servicio de la historia",
    noAdmite: "contenido sexual",
  },
};

export interface Contradiccion {
  codigo: string;
  campos: string[];
  mensaje: string;
}

export interface AnalisisBrief {
  faltantes: string[];
  contradicciones: Contradiccion[];
}

/**
 * El análisis de un `422` con código `brief_incompleto` (RF3-PER-05): viene como JSON dentro de
 * `detalle`. Cualquier otro error devuelve `null`.
 */
export function analisisDeError(error: unknown): AnalisisBrief | null {
  if (!(error instanceof ErrorApi) || error.estado !== 422) return null;
  const cuerpo = error.cuerpo as { codigo?: unknown; detalle?: unknown } | null;
  if (cuerpo?.codigo !== "brief_incompleto" || typeof cuerpo.detalle !== "string") return null;
  try {
    const datos = JSON.parse(cuerpo.detalle) as Partial<AnalisisBrief>;
    return {
      faltantes: Array.isArray(datos.faltantes) ? datos.faltantes : [],
      contradicciones: Array.isArray(datos.contradicciones) ? datos.contradicciones : [],
    };
  } catch {
    return null;
  }
}
