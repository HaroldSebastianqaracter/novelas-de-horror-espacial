/**
 * Manejadores MSW del contrato. Imitan lo justo del worker para que `npm run dev:mocks` se vea
 * vivo: una intención tarda unos segundos en atenderse, cambia el estado y respeta la regla
 * de una novela a la vez. Los tests los sustituyen con `servidor.use(...)` cuando necesitan otro caso.
 */
import { http, HttpResponse } from "msw";
import type { CapituloTexto, Ejecucion, Estructura, Intencion, IntencionEncolada, NovelaDetalle, NovelaResumen, Parada, TipoIntencion } from "../tipos";
import { capitulosDe, detalleDe, ejecuciones, novelas, paradas, textoDe } from "./datos";

/** Lo que tarda el «worker» en atender una intención. */
const ESPERA_MS = 2_500;
const ACTIVOS = ["planificando", "escaletando", "generando"];

interface IntencionSimulada {
  id: number;
  tipo: TipoIntencion;
  novelaId: number | null;
  payload: Record<string, unknown>;
  creada: number;
  cierre?: { estado: "hecha" | "rechazada"; motivo: string | null; resultado?: Record<string, unknown> };
}

interface BriefSimulado {
  destinatario?: { nombre?: string; edad?: number; pronombres?: string; rasgos?: unknown[] };
  recuerdos?: unknown[];
  ocasion?: string;
  quien_regala?: string;
  intensidad?: string;
  tono?: string;
}

const EDAD_MINIMA: Record<string, number> = { atmosferico: 10, tension: 14, intenso: 18 };

/**
 * Lo justo de `analizar` para que `dev:mocks` enseñe el camino del 422: faltantes y la
 * contradicción de edad. El frontend real no lo hace nunca: lo hace la API (RF-FE-BRF-04).
 */
function analizarBrief(b: BriefSimulado) {
  const d = b.destinatario ?? {};
  const faltantes = (
    [
      ["destinatario.nombre", !d.nombre],
      ["destinatario.edad", d.edad === undefined],
      ["destinatario.pronombres", !d.pronombres],
      ["destinatario.rasgos", !d.rasgos?.length],
      ["recuerdos", !b.recuerdos?.length],
      ["ocasion", !b.ocasion],
      ["quien_regala", !b.quien_regala],
      ["intensidad", !b.intensidad],
      ["tono", !b.tono],
    ] as const
  )
    .filter(([, falta]) => falta)
    .map(([campo]) => campo);
  const contradicciones = [];
  const minima = b.intensidad ? EDAD_MINIMA[b.intensidad] : undefined;
  if (d.edad !== undefined && minima !== undefined && d.edad < minima) {
    contradicciones.push({
      codigo: "edad_bajo_intensidad",
      campos: ["destinatario.edad", "intensidad"],
      mensaje: `La intensidad «${b.intensidad}» pide al menos ${minima} años y el destinatario tiene ${d.edad}.`,
    });
  }
  return { faltantes, contradicciones };
}

function crearNovela(): number {
  const id = Math.max(0, ...novelas.map((n) => n.id)) + 1;
  const ahoraIso = ahora();
  novelas.push({ id, titulo: "", genero: "terror_espacial", creado_en: ahoraIso, estado: "configurada", capitulos_completados: 0, subgenero_dominante: null });
  ejecuciones[id] = {
    novela_id: id, estado: "configurada", fase: null, capitulo_actual: null, intento_actual: 1,
    capitulos_completados: 0, total_capitulos: 0, parada_abierta_id: null, ultimo_error: null, actualizado_en: ahoraIso,
  };
  capitulosDe[id] = [];
  return id;
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
  if (i.tipo === "crear_novela") {
    return { estado: "hecha", motivo: null, resultado: { novela_id: crearNovela() } };
  }
  if (i.tipo === "arrancar" && id !== null) {
    const otra = Object.values(ejecuciones).some((e) => e.novela_id !== id && ACTIVOS.includes(e.estado));
    if (otra) return { estado: "rechazada", motivo: "otra_ejecucion_activa" };
    if (estado === "parada") return { estado: "rechazada", motivo: "hay una parada abierta: resuelvela o relanza" };
    const e = ejecuciones[id];
    if ((capitulosDe[id]?.length ?? 0) > 0 && e) {
      e.capitulo_actual = (e.capitulos_completados ?? 0) + 1;
      e.intento_actual = 1;
      fijarEstado(id, "generando", "paquete");
    } else {
      fijarEstado(id, "planificando", "arquitecto");
    }
    return { estado: "hecha", motivo: null };
  }
  if (i.tipo === "resolver_parada" && id !== null) {
    const parada = paradas[Number(i.payload.parada_id)];
    if (!parada || parada.estado !== "abierta") return { estado: "rechazada", motivo: "la parada no esta abierta" };
    const accion = String(i.payload.accion);
    const e = ejecuciones[id];
    parada.estado = "resuelta";
    parada.resolucion = accion === "aceptar_retcon" || accion === "dar_por_sabido" ? accion : accion === "rehacer" ? "rehecho" : "relanzado";
    if (e) Object.assign(e, { parada_abierta_id: null, intento_actual: 1 });
    if (accion === "rehacer") fijarEstado(id, parada.tipo === "estructura" ? "planificando" : "escaletando", parada.tipo);
    else fijarEstado(id, "generando", "paquete");
    return { estado: "hecha", motivo: null };
  }
  if (i.tipo === "parar" && id !== null) {
    if (estado && ACTIVOS.includes(estado)) fijarEstado(id, "detenida", null);
    return { estado: "hecha", motivo: null };
  }
  return { estado: "hecha", motivo: null };
}

const FASES_PLAN = ["arquitecto", "mundo", "elenco", "estructura", "puerta_1", "escaleta", "puerta_2"];
const FASES_CAP = ["paquete", "redaccion", "extraccion", "puerta_3", "puerta_4"];

/** Un paso del pipeline simulado. Devuelve el tipo de evento, o `null` si la novela no está activa. */
function avanzar(id: number): string | null {
  const e = ejecuciones[id];
  if (!e || !ACTIVOS.includes(e.estado)) return null;
  const capitulos = capitulosDe[id] ?? [];
  if (e.estado === "planificando" || e.estado === "escaletando") {
    const siguiente = FASES_PLAN[FASES_PLAN.indexOf(e.fase ?? "") + 1];
    if (siguiente === "escaleta" && capitulos.length === 0) {
      capitulosDe[id] = Array.from({ length: 10 }, (_, i) => ({
        numero: i + 1, estado: "planificado", objetivo: null, resumen: null, escenas: [],
      }));
      e.total_capitulos = 10;
    }
    if (!siguiente) {
      Object.assign(e, { capitulo_actual: 1, intento_actual: 1 });
      fijarEstado(id, "generando", "paquete");
    } else {
      fijarEstado(id, siguiente === "escaleta" || siguiente === "puerta_2" ? "escaletando" : "planificando", siguiente);
    }
    return "fase_cambiada";
  }
  const siguiente = FASES_CAP[FASES_CAP.indexOf(e.fase ?? "") + 1];
  if (siguiente) {
    fijarEstado(id, "generando", siguiente);
    return "fase_cambiada";
  }
  const capitulo = capitulos.find((c) => c.numero === e.capitulo_actual);
  if (capitulo) capitulo.estado = "completado";
  e.capitulos_completados = (e.capitulos_completados ?? 0) + 1;
  const novela = novelas.find((n) => n.id === id);
  if (novela) novela.capitulos_completados = e.capitulos_completados;
  if (e.capitulos_completados >= capitulos.length) {
    Object.assign(e, { capitulo_actual: null });
    fijarEstado(id, "completada", null);
    return "completada";
  }
  Object.assign(e, { capitulo_actual: (e.capitulo_actual ?? 0) + 1, intento_actual: 1 });
  fijarEstado(id, "generando", "paquete");
  return "capitulo_completado";
}

/** En `npm run dev:mocks` la novela en curso avanza sola; en los tests, no. */
const SIMULAR = typeof window !== "undefined" && import.meta.env?.VITE_MOCKS === "1";
const PASO_MS = 4_000;
let siguienteEvento = 1;

/**
 * Un solo reloj para todo el pipeline simulado, con los streams suscritos. Si cada stream
 * avanzara por su cuenta, dos conexiones a la misma novela (StrictMode en desarrollo, o un
 * stream que MSW no llega a cancelar al abortarse) harían avanzar la novela dos veces por paso.
 */
const oyentes = new Set<(cambios: ReadonlyMap<number, string>) => void>();
let reloj: ReturnType<typeof setInterval> | undefined;

function asegurarReloj() {
  if (reloj) return;
  reloj = setInterval(() => {
    const cambios = new Map<number, string>();
    if (SIMULAR) {
      for (const id of Object.keys(ejecuciones).map(Number)) {
        const tipo = avanzar(id);
        if (tipo) cambios.set(id, tipo);
      }
    }
    for (const oyente of oyentes) oyente(cambios);
  }, PASO_MS);
  // En Node (tests) el reloj no debe mantener vivo el proceso.
  (reloj as { unref?: () => void }).unref?.();
}

function streamEventos(novelaId: number): ReadableStream<Uint8Array> {
  const codificador = new TextEncoder();
  let oyente: ((cambios: ReadonlyMap<number, string>) => void) | undefined;
  return new ReadableStream({
    start(control) {
      control.enqueue(codificador.encode(": conectado\n\n"));
      oyente = (cambios) => {
        const tipo = cambios.get(novelaId);
        const linea = tipo
          ? `id: ${siguienteEvento++}\nevent: ${tipo}\ndata: ${JSON.stringify({ tipo, payload: {} })}\n\n`
          : ": keepalive\n\n";
        try {
          control.enqueue(codificador.encode(linea));
        } catch {
          // El stream ya se cerró sin avisar: deja de escucharlo.
          if (oyente) oyentes.delete(oyente);
        }
      };
      oyentes.add(oyente);
      asegurarReloj();
    },
    cancel() {
      if (oyente) oyentes.delete(oyente);
    },
  });
}

const noEncontrada = (que: string) => HttpResponse.json({ codigo: "no_encontrada", mensaje: `No existe ${que}` }, { status: 404 });

export const manejadores = [
  http.get("*/api/novelas", () => HttpResponse.json<NovelaResumen[]>(novelas)),

  http.get("*/api/novelas/:id/ejecucion", ({ params }) => {
    const ejecucion = ejecuciones[Number(params.id)];
    if (!ejecucion) return HttpResponse.json({ codigo: "no_encontrada", mensaje: "No existe la novela" }, { status: 404 });
    return HttpResponse.json<Ejecucion>(ejecucion);
  }),

  http.get("*/api/novelas/:id", ({ params }) => {
    const detalle = detalleDe(Number(params.id));
    return detalle ? HttpResponse.json<NovelaDetalle>(detalle) : noEncontrada("la novela");
  }),

  http.get("*/api/novelas/:id/estructura", ({ params }) => {
    const capitulos = capitulosDe[Number(params.id)];
    if (!capitulos) return noEncontrada("la novela");
    return HttpResponse.json<Estructura>({ actos: [], capitulos, hilos: [], puntos_de_giro: [], siembras: [] });
  }),

  http.get("*/api/novelas/:id/capitulos/:n", ({ params }) => {
    const numero = Number(params.n);
    const texto = textoDe(Number(params.id), numero);
    if (texto === undefined) {
      return HttpResponse.json({ detail: `El capitulo ${numero} no esta escrito` }, { status: 404 });
    }
    return HttpResponse.json<CapituloTexto>({ numero, version: 1, palabras: texto.split(/\s+/).length, texto });
  }),

  http.get("*/api/novelas/:id/paradas/:pid", ({ params }) => {
    const parada = paradas[Number(params.pid)];
    return parada ? HttpResponse.json<Parada>(parada) : noEncontrada("la parada");
  }),

  http.get("*/api/novelas/:id/eventos", ({ params }) =>
    new HttpResponse(streamEventos(Number(params.id)), {
      headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
    }),
  ),

  http.post("*/api/intenciones", async ({ request }) => {
    const cuerpo = (await request.json()) as { tipo: TipoIntencion; novela_id?: number | null; payload?: Record<string, unknown> };
    if (cuerpo.tipo === "crear_novela" && cuerpo.payload?.brief) {
      const analisis = analizarBrief(cuerpo.payload.brief as BriefSimulado);
      if (analisis.faltantes.length || analisis.contradicciones.length) {
        return HttpResponse.json(
          { codigo: "brief_incompleto", mensaje: "El brief no esta completo", detalle: JSON.stringify(analisis) },
          { status: 422 },
        );
      }
    }
    const intencion: IntencionSimulada = {
      id: siguienteIntencion++,
      tipo: cuerpo.tipo,
      novelaId: cuerpo.novela_id ?? null,
      payload: cuerpo.payload ?? {},
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
      resultado: intencion.cierre?.resultado ?? null,
      creado_en: new Date(intencion.creada).toISOString(),
    });
  }),
];
