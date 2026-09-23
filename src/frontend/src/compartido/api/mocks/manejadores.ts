/** Manejadores MSW del contrato. Los tests los sustituyen con `servidor.use(...)` cuando necesitan otro caso. */
import { http, HttpResponse } from "msw";
import type { Ejecucion, Intencion, IntencionEncolada, NovelaResumen } from "../tipos";
import { ejecuciones, novelas } from "./datos";

let siguienteIntencion = 1;

export const manejadores = [
  http.get("*/api/novelas", () => HttpResponse.json<NovelaResumen[]>(novelas)),

  http.get("*/api/novelas/:id/ejecucion", ({ params }) => {
    const ejecucion = ejecuciones[Number(params.id)];
    if (!ejecucion) return HttpResponse.json({ codigo: "no_encontrada", mensaje: "No existe la novela" }, { status: 404 });
    return HttpResponse.json<Ejecucion>(ejecucion);
  }),

  http.post("*/api/intenciones", async ({ request }) => {
    const cuerpo = (await request.json()) as { tipo: IntencionEncolada["tipo"] };
    return HttpResponse.json<IntencionEncolada>(
      { id: siguienteIntencion++, tipo: cuerpo.tipo, estado: "pendiente" },
      { status: 202 },
    );
  }),

  http.get("*/api/intenciones/:id", ({ params }) =>
    HttpResponse.json<Intencion>({
      id: Number(params.id),
      tipo: "arrancar",
      estado: "hecha",
      motivo: null,
      resultado: null,
      creado_en: new Date().toISOString(),
    }),
  ),
];
