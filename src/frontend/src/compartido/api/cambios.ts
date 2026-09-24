/**
 * DEUDA (RF-FE-API-04): el contrato del cambio del lector (spec-frontend 5.2, aceptado por el
 * backend en spec3 3.7 y 3.8) escrito a mano mientras no esté en `tests/openapi.json`. Cuando el
 * backend lo publique, estos tipos salen de `esquema.gen.ts` y las lecturas pasan a `api.GET`.
 */
import { ErrorApi } from "./cliente";
import type { EntidadLectura } from "./consultas";
import type { NuevaIntencion, TipoIntencion } from "./tipos";

export type TipoIntencionAmpliada = TipoIntencion | "cambio_lector";
/** `NuevaIntencion` con `cambio_lector`, que el OpenAPI todavía no declara. */
export type IntencionPedida = Omit<NuevaIntencion, "tipo"> & { tipo: TipoIntencionAmpliada };

export type ObjetivoCambio =
  | { tipo: "entidad"; entidad: EntidadLectura; id: number }
  | { tipo: "hecho"; hecho_id: number }
  | { tipo: "fragmento" };

export interface PayloadCambio {
  version_base: number;
  objetivo: ObjetivoCambio;
  peticion: string;
  cita?: { capitulo: number; texto: string };
}

export const LIMITES_CAMBIO = { peticionMin: 3, peticionMax: 300, citaMax: 500 } as const;

export const ESTADOS_CAMBIO = ["interpretando", "rechazado", "reescribiendo", "aplicado", "fallido", "interrumpido"] as const;
export type EstadoCambio = (typeof ESTADOS_CAMBIO)[number];
export const CAMBIO_TERMINADO: ReadonlySet<string> = new Set(["rechazado", "aplicado", "fallido", "interrumpido"]);

export interface Cambio {
  id: number;
  estado: string;
  peticion: string;
  objetivo: ObjetivoCambio;
  cita: { capitulo: number; texto: string } | null;
  /** Lo que entendió el intérprete del backend. */
  cambio: { tipo: string; antes: string | null; despues: string | null } | null;
  capitulos: number[];
  informe: unknown;
  version: number | null;
  creado_en: string;
}

/** Los motivos de rechazo del worker para `cambio_lector`, en lenguaje legible. */
export const MOTIVOS_CAMBIO: Record<string, string> = {
  novela_no_terminada: "La novela no está terminada: el cambio se pide sobre una novela completada.",
  version_desfasada: "Estabas leyendo una versión que ya no es la última. Vuelve a la última y pídelo otra vez.",
  objetivo_inexistente: "Lo que querías cambiar ya no existe en la novela.",
  cambio_no_admisible: "Ese cambio no se puede aplicar como un cambio de la historia.",
};

async function leerSinContrato<T>(ruta: string): Promise<T> {
  const respuesta = await globalThis.fetch(`${window.location.origin}/api${ruta}`);
  const cuerpo: unknown = await respuesta.json().catch(() => null);
  if (!respuesta.ok) throw new ErrorApi(respuesta.status, cuerpo);
  return cuerpo as T;
}

export const leerCambio = (novelaId: number, cambioId: number) =>
  leerSinContrato<Cambio>(`/novelas/${novelaId}/cambios/${cambioId}`);

/** Los capítulos que reescribiría el worker, sin escribir nada. `null` si el objetivo no lo admite. */
export function leerAlcance(novelaId: number, objetivo: ObjetivoCambio): Promise<{ capitulos: number[] }> | null {
  if (objetivo.tipo === "fragmento") return null;
  const q =
    objetivo.tipo === "hecho"
      ? `hecho_id=${objetivo.hecho_id}`
      : `entidad=${encodeURIComponent(objetivo.entidad)}&id=${objetivo.id}`;
  return leerSinContrato<{ capitulos: number[] }>(`/novelas/${novelaId}/cambios/alcance?${q}`);
}

/**
 * El 422 `cambio_invalido`: el mensaje y los campos señalados, o `null` si el error es otro. El
 * `detalle` es un JSON con una lista `[{ campo, error }]`.
 */
export function errorDeCambio(e: unknown): { mensaje: string; campos: string[] } | null {
  if (!(e instanceof ErrorApi) || e.estado !== 422) return null;
  const cuerpo = e.cuerpo as { codigo?: unknown; detalle?: unknown } | null;
  if (cuerpo?.codigo !== "cambio_invalido") return null;
  let campos: string[] = [];
  try {
    const detalle: unknown = typeof cuerpo.detalle === "string" ? JSON.parse(cuerpo.detalle) : cuerpo.detalle;
    if (Array.isArray(detalle)) {
      campos = detalle.flatMap((d: unknown) => {
        const { campo, error } = (d ?? {}) as { campo?: unknown; error?: unknown };
        if (typeof campo !== "string") return [];
        return [typeof error === "string" && error ? `${campo}: ${error}` : campo];
      });
    }
  } catch {
    // Un detalle ilegible no esconde el mensaje.
  }
  return { mensaje: e.message, campos };
}
