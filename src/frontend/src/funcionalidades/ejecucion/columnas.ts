/** Agrupación de los nueve estados en las columnas del tablero general (RF-FE-TAB-01). */
import { comoEstadoEjecucion, type EstadoEjecucion } from "../../compartido/api/reglas";

export type ColumnaId = "espera" | "planificando" | "escribiendo" | "terminada";
export type GrupoId = ColumnaId | "atencion";

export interface Columna {
  id: ColumnaId;
  nombre: string;
  estados: readonly EstadoEjecucion[];
  vacio: string;
}

export const COLUMNAS: readonly Columna[] = [
  { id: "espera", nombre: "En espera", estados: ["configurada", "detenida"], vacio: "Sin novelas en espera." },
  {
    id: "planificando",
    nombre: "Planificando",
    estados: ["planificando", "escaletando"],
    vacio: "Sin ejecución. Suelta aquí una novela en espera para arrancarla.",
  },
  { id: "escribiendo", nombre: "Escribiendo", estados: ["generando"], vacio: "Ninguna novela escribiendo." },
  {
    id: "terminada",
    nombre: "Terminada",
    estados: ["completada", "completada_con_avisos"],
    vacio: "Aún no hay novelas terminadas.",
  },
];

export const ESTADOS_ATENCION: readonly EstadoEjecucion[] = ["parada", "error"];

const GRUPO_DE_ESTADO: Record<EstadoEjecucion, GrupoId> = {
  configurada: "espera",
  detenida: "espera",
  planificando: "planificando",
  escaletando: "planificando",
  generando: "escribiendo",
  completada: "terminada",
  completada_con_avisos: "terminada",
  parada: "atencion",
  error: "atencion",
};

/**
 * Sin ejecución o con un estado que el cliente no conoce, la novela cae en «En espera»:
 * no se esconde, y su chip dice el estado tal cual.
 */
export function grupoDe(estado: string | null | undefined): GrupoId {
  const conocido = comoEstadoEjecucion(estado);
  return conocido ? GRUPO_DE_ESTADO[conocido] : "espera";
}
