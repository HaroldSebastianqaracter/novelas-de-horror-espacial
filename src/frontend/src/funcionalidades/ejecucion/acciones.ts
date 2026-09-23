/**
 * Qué intenciones puede pedir una tarjeta del tablero general y adónde se puede soltar
 * (RF-FE-TAB-03, RF-FE-TAB-04). Es un filtro de cortesía: quien decide es el worker.
 */
import { comoEstadoEjecucion, ESTADOS_ACTIVOS, ESTADOS_QUE_ADMITEN_ARRANCAR } from "../../compartido/api/reglas";
import { type GrupoId, grupoDe } from "./columnas";

export type IntencionDeTablero = "arrancar" | "parar";

export interface AccionDeTarjeta {
  tipo: IntencionDeTablero;
  /** Por qué no se puede pedir ahora; sin él, se puede. */
  noDisponible?: string;
}

export const MOTIVO_OTRA_ACTIVA = "Ya hay una novela en curso: solo se genera una a la vez.";

/** Las intenciones que admite una novela del tablero, dado su estado y si otra está en curso. */
export function accionesDe(estado: string | null | undefined, hayOtraActiva: boolean): AccionDeTarjeta[] {
  const conocido = comoEstadoEjecucion(estado);
  if (!conocido) return [];
  // Las de «Requiere atención» no se piden desde el tablero: se abren (RF-FE-TAB-03).
  if (grupoDe(conocido) === "espera" && ESTADOS_QUE_ADMITEN_ARRANCAR.has(conocido)) {
    return [{ tipo: "arrancar", ...(hayOtraActiva ? { noDisponible: MOTIVO_OTRA_ACTIVA } : {}) }];
  }
  if (ESTADOS_ACTIVOS.has(conocido)) return [{ tipo: "parar" }];
  return [];
}

/** La intención que pide soltar una tarjeta de `origen` en `destino`, o `null` si no pide ninguna. */
export function intencionDeArrastre(origen: GrupoId, destino: GrupoId): IntencionDeTablero | null {
  if (origen === "espera" && destino === "planificando") return "arrancar";
  if ((origen === "planificando" || origen === "escribiendo") && destino === "espera") return "parar";
  return null;
}

export type Destino = { tipo: "origen" } | { tipo: "valido"; intencion: IntencionDeTablero } | { tipo: "invalido"; motivo: string };

/** Cómo se ve cada columna mientras se arrastra una tarjeta con este estado. */
export function destinoPara(
  estado: string | null | undefined,
  hayOtraActiva: boolean,
  columna: GrupoId,
): Destino {
  const origen = grupoDe(estado);
  if (columna === origen) return { tipo: "origen" };
  const intencion = intencionDeArrastre(origen, columna);
  if (!intencion) return { tipo: "invalido", motivo: "Aquí no se puede soltar" };
  const accion = accionesDe(estado, hayOtraActiva).find((a) => a.tipo === intencion);
  if (!accion) return { tipo: "invalido", motivo: "Aquí no se puede soltar" };
  if (accion.noDisponible) return { tipo: "invalido", motivo: accion.noDisponible };
  return { tipo: "valido", intencion };
}
