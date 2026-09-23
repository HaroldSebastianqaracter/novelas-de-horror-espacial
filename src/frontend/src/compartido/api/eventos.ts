/**
 * Stream SSE de una novela (RF-FE-DAT-02, RF-FE-DAT-04). Cada evento invalida lo de esa novela;
 * ninguno rellena la caché. Si el stream se corta, se reconecta con `Last-Event-ID` y, al
 * volver, se reconsulta todo, porque lo ocurrido mientras tanto pudo no llegar como evento.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { claves } from "./consultas";

export type Enlace = "conectando" | "conectado" | "perdido";

export interface EventoSSE {
  id: string | null;
  tipo: string;
  datos: string;
}

/** Esperas entre reintentos: crecen y se quedan en la última. */
export const ESPERAS_RECONEXION_MS = [1_000, 2_000, 5_000, 10_000];
/** Los eventos que llegan juntos se agrupan en una sola invalidación. */
const AGRUPAR_MS = 500;

/**
 * Parte un trozo de `text/event-stream` en eventos. Devuelve los completos y el resto, que
 * espera al siguiente trozo. Los comentarios (`: keepalive`) se ignoran.
 */
export function partirEventos(bufer: string): { eventos: EventoSSE[]; resto: string } {
  const normalizado = bufer.replace(/\r\n?/g, "\n");
  const bloques = normalizado.split("\n\n");
  const resto = bloques.pop() ?? "";
  const eventos: EventoSSE[] = [];
  for (const bloque of bloques) {
    let id: string | null = null;
    let tipo = "message";
    const datos: string[] = [];
    for (const linea of bloque.split("\n")) {
      if (linea === "" || linea.startsWith(":")) continue;
      const dos = linea.indexOf(":");
      const campo = dos === -1 ? linea : linea.slice(0, dos);
      const valor = dos === -1 ? "" : linea.slice(dos + 1).replace(/^ /, "");
      if (campo === "id") id = valor;
      else if (campo === "event") tipo = valor;
      else if (campo === "data") datos.push(valor);
    }
    if (id !== null || datos.length > 0) eventos.push({ id, tipo, datos: datos.join("\n") });
  }
  return { eventos, resto };
}

/** Escucha los eventos de una novela mientras el componente esté montado y dice cómo va el enlace. */
export function useEventosNovela(novelaId: number): Enlace {
  const clienteConsultas = useQueryClient();
  const [enlace, setEnlace] = useState<Enlace>("conectando");

  useEffect(() => {
    let vivo = true;
    let ultimoId: string | null = null;
    let intento = 0;
    let seCorto = false;
    let controlador: AbortController | null = null;
    let temporizador: ReturnType<typeof setTimeout> | undefined;
    let agrupador: ReturnType<typeof setTimeout> | undefined;

    const invalidarNovela = () => {
      if (agrupador) return;
      agrupador = setTimeout(() => {
        agrupador = undefined;
        void clienteConsultas.invalidateQueries({ queryKey: claves.novela(novelaId) });
      }, AGRUPAR_MS);
    };

    const conectar = async () => {
      controlador = new AbortController();
      try {
        const respuesta = await globalThis.fetch(
          `${window.location.origin}/api/novelas/${novelaId}/eventos`,
          {
            headers: { Accept: "text/event-stream", ...(ultimoId ? { "Last-Event-ID": ultimoId } : {}) },
            signal: controlador.signal,
          },
        );
        if (!respuesta.ok || !respuesta.body) throw new Error(`SSE respondió ${respuesta.status}`);
        setEnlace("conectado");
        intento = 0;
        if (seCorto) {
          // Volver no basta: lo ocurrido mientras tanto se reconsulta entero (RF-FE-DAT-04).
          seCorto = false;
          void clienteConsultas.invalidateQueries();
        }
        const lector = respuesta.body.getReader();
        const decodificador = new TextDecoder();
        let bufer = "";
        for (;;) {
          const { value, done } = await lector.read();
          if (done) break;
          const { eventos, resto } = partirEventos(bufer + decodificador.decode(value, { stream: true }));
          bufer = resto;
          for (const evento of eventos) {
            if (evento.id) ultimoId = evento.id;
          }
          if (eventos.length > 0) invalidarNovela();
        }
        throw new Error("El servidor cerró el stream");
      } catch {
        if (!vivo) return;
        seCorto = true;
        setEnlace("perdido");
        const espera = ESPERAS_RECONEXION_MS[Math.min(intento, ESPERAS_RECONEXION_MS.length - 1)];
        intento += 1;
        temporizador = setTimeout(() => void conectar(), espera);
      }
    };

    // Volver a la pestaña tras una suspensión cuenta como reconexión (RF-FE-DAT-04).
    const alVolver = () => {
      if (document.visibilityState === "visible") void clienteConsultas.invalidateQueries();
    };
    document.addEventListener("visibilitychange", alVolver);
    void conectar();

    return () => {
      vivo = false;
      controlador?.abort();
      clearTimeout(temporizador);
      clearTimeout(agrupador);
      document.removeEventListener("visibilitychange", alVolver);
    };
  }, [novelaId, clienteConsultas]);

  return enlace;
}
