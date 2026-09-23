/**
 * Manejadores MSW del contrato. Imitan lo justo del worker para que `npm run dev:mocks` se vea
 * vivo: una intención tarda unos segundos en atenderse, cambia el estado y respeta la regla
 * de una novela a la vez. Los tests los sustituyen con `servidor.use(...)` cuando necesitan otro caso.
 */
import { http, HttpResponse } from "msw";
import type { Ejecucion, Intencion, IntencionEncolada, NovelaResumen, TipoIntencion } from "../tipos";
import { ejecuciones, novelas } from "./datos";

/** Lo que tarda el «worker» en atender una intención. */
const ESPERA_MS = 2_500;
const ACTIVOS = ["planificando", "escaletando", "generando"];

interface IntencionSimulada {
  id: number;
  tipo: TipoIntencion;
  novelaId: number | null;
  creada: number;
  cierre?: { estado: "hecha" | "rechazada"; motivo: string | null };
}

const intenciones = new Map<number, IntencionSimulada>();
let siguienteIntencion = 1;

const ahora = () => new Date().toISOString();

function fijarEstado(novelaId: number, estado: string, fase: string | null) {
  const ejecucion = ejecuciones[novelaId];
  const novela = novelas.find((n) => n.id === novelaId);
  if (!ejecucion || !novela) return;
  Object.assign(ejecucion, { estado, fase, actualizado_en: ahora() });
  novela.estado = estado;
}

/** Lo que haría el worker al tomar la intención. */
function atender(i: IntencionSimulada): IntencionSimulada["cierre"] {
  const id = i.novelaId;
  const estado = id !== null ? ejecuciones[id]?.estado : undefined;
  if (i.tipo === "arrancar" && id !== null) {
    const otra = Object.values(ejecuciones).some((e) => e.novela_id !== id && ACTIVOS.includes(e.estado));
    if (otra) return { estado: "rechazada", motivo: "otra_ejecucion_activa" };
    if (estado === "parada") return { estado: "rechazada", motivo: "hay una parada abierta: resuelvela o relanza" };
    fijarEstado(id, "planificando", "arquitecto");
    return { estado: "hecha", motivo: null };
  }
  if (i.tipo === "parar" && id !== null) {
    if (estado && ACTIVOS.includes(estado)) fijarEstado(id, "detenida", null);
    return { estado: "hecha", motivo: null };
  }
  return { estado: "hecha", motivo: null };
}

export const manejadores = [
  http.get("*/api/novelas", () => HttpResponse.json<NovelaResumen[]>(novelas)),

  http.get("*/api/novelas/:id/ejecucion", ({ params }) => {
    const ejecucion = ejecuciones[Number(params.id)];
    if (!ejecucion) return HttpResponse.json({ codigo: "no_encontrada", mensaje: "No existe la novela" }, { status: 404 });
    return HttpResponse.json<Ejecucion>(ejecucion);
  }),

  http.post("*/api/intenciones", async ({ request }) => {
    const cuerpo = (await request.json()) as { tipo: TipoIntencion; novela_id?: number | null };
    const intencion: IntencionSimulada = {
      id: siguienteIntencion++,
      tipo: cuerpo.tipo,
      novelaId: cuerpo.novela_id ?? null,
      creada: Date.now(),
    };
    intenciones.set(intencion.id, intencion);
    return HttpResponse.json<IntencionEncolada>(
      { id: intencion.id, tipo: intencion.tipo, estado: "pendiente" },
      { status: 202 },
    );
  }),

  http.get("*/api/intenciones/:id", ({ params }) => {
    const intencion = intenciones.get(Number(params.id));
    if (!intencion) return HttpResponse.json({ codigo: "no_encontrada", mensaje: "No existe la intención" }, { status: 404 });
    if (!intencion.cierre && Date.now() - intencion.creada >= ESPERA_MS) intencion.cierre = atender(intencion);
    return HttpResponse.json<Intencion>({
      id: intencion.id,
      tipo: intencion.tipo,
      estado: intencion.cierre?.estado ?? "pendiente",
      motivo: intencion.cierre?.motivo ?? null,
      resultado: null,
      creado_en: new Date(intencion.creada).toISOString(),
    });
  }),
];
