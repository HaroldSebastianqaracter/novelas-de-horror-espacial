/**
 * Cliente HTTP tipado desde el OpenAPI. En desarrollo, `/api` pasa por el proxy de Vite
 * (RF-FE-API-02); en los tests lo sirve MSW.
 */
import createClient from "openapi-fetch";
import type { paths } from "./esquema.gen";

export const api = createClient<paths>({
  baseUrl: `${window.location.origin}/api`,
  // Se resuelve en cada llamada: openapi-fetch guarda el `fetch` global al crearse, y en los
  // tests MSW lo sustituye después.
  fetch: (peticion) => globalThis.fetch(peticion),
});

/** Error de la API en su forma de RF-API-07, o un fallo de red. */
export class ErrorApi extends Error {
  readonly estado: number;
  readonly cuerpo: unknown;

  constructor(estado: number, cuerpo: unknown) {
    super(mensajeDe(cuerpo) ?? `La API respondió ${estado}`);
    this.name = "ErrorApi";
    this.estado = estado;
    this.cuerpo = cuerpo;
  }
}

function mensajeDe(cuerpo: unknown): string | undefined {
  if (typeof cuerpo !== "object" || cuerpo === null) return undefined;
  const c = cuerpo as Record<string, unknown>;
  if (typeof c.mensaje === "string") return c.mensaje;
  if (typeof c.detail === "string") return c.detail;
  return undefined;
}

/** Convierte la respuesta de openapi-fetch en dato o excepción, que es lo que espera TanStack Query. */
export async function leer<T>(
  peticion: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await peticion;
  if (error !== undefined || data === undefined) throw new ErrorApi(response.status, error);
  return data;
}
