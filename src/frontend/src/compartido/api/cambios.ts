/**
 * DEUDA (RF-FE-API-04): lo que el OpenAPI del cambio del lector no tipa. El `payload` de
 * `POST /intenciones` y los campos `objetivo`, `cita` y `cambio` de `CambioVista` salen como
 * objetos libres, y el `422` de `cambio_invalido` no está declarado: aquí se escriben desde spec3
 * (RF3-CAM-01, RF3-CAM-13). El tipo `cambio_lector`, `/cambios` y `/cambios/alcance` ya vienen de
 * `esquema.gen.ts`.
 */
import { api, ErrorApi, leer } from "./cliente";
import type { EntidadLectura } from "./consultas";
import type { CambioVista } from "./tipos";

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

/** `CambioVista` con sus campos libres leídos con la forma de RF3-CAM-13. */
export type Cambio = Omit<CambioVista, "objetivo" | "cita" | "cambio"> & {
  objetivo: ObjetivoCambio;
  cita: { capitulo: number; texto: string } | null;
  /** Lo que entendió el intérprete del backend; al renombrar, `tabla` y `entidad_id` dicen a quién. */
  cambio: { tipo: string; antes: string | null; despues: string | null; tabla?: string | null; entidad_id?: number | null } | null;
};

/** Los motivos de rechazo del worker para `cambio_lector`, en lenguaje legible. */
export const MOTIVOS_CAMBIO: Record<string, string> = {
  novela_no_terminada: "La novela no está terminada: el cambio se pide sobre una novela completada.",
  version_desfasada: "Estabas leyendo una versión que ya no es la última. Vuelve a la última y pídelo otra vez.",
  objetivo_inexistente: "Lo que querías cambiar ya no existe en la novela.",
  cambio_no_admisible: "Ese cambio no se puede aplicar como un cambio de la historia.",
  cambio_invalido: "El cambio no tiene una forma que el worker pueda aplicar.",
};

export async function leerCambio(novelaId: number, cambioId: number): Promise<Cambio> {
  const cambio = await leer(
    api.GET("/novelas/{novela_id}/cambios/{cambio_id}", {
      params: { path: { novela_id: novelaId, cambio_id: cambioId } },
    }),
  );
  return cambio as Cambio;
}

export async function leerCambios(novelaId: number): Promise<Cambio[]> {
  const cambios = await leer(api.GET("/novelas/{novela_id}/cambios", { params: { path: { novela_id: novelaId } } }));
  return cambios as Cambio[];
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
