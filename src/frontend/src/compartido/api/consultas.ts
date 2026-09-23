/**
 * Claves y consultas de TanStack Query. El `GET` es la verdad (RF-FE-DAT-01): nada de esto
 * guarda datos propios, solo la caché de lo que dice el servidor.
 */
import { queryOptions } from "@tanstack/react-query";
import { api, leer } from "./cliente";
import { comoEstadoEjecucion, ESTADOS_ACTIVOS } from "./reglas";

export const claves = {
  novelas: ["novelas"] as const,
  novela: (id: number) => ["novelas", id] as const,
  ejecucion: (id: number) => ["novelas", id, "ejecucion"] as const,
  estructura: (id: number) => ["novelas", id, "estructura"] as const,
  paradas: (id: number) => ["novelas", id, "paradas"] as const,
  capitulo: (id: number, n: number) => ["novelas", id, "capitulos", n] as const,
  intencion: (id: number) => ["intenciones", id] as const,
};

/** Tablero general: se reconsulta cada 15 s aunque no llegue ningún evento (RF-FE-DAT-03). */
export const consultaNovelas = () =>
  queryOptions({
    queryKey: claves.novelas,
    queryFn: () => leer(api.GET("/novelas")),
    refetchInterval: 15_000,
  });

/** Una ejecución activa se reconsulta cada 5 s aunque no llegue ningún evento (RF-FE-DAT-03). */
export const consultaEjecucion = (novelaId: number) =>
  queryOptions({
    queryKey: claves.ejecucion(novelaId),
    queryFn: () =>
      leer(api.GET("/novelas/{novela_id}/ejecucion", { params: { path: { novela_id: novelaId } } })),
    refetchInterval: (consulta) => {
      const estado = comoEstadoEjecucion(consulta.state.data?.estado);
      return estado && ESTADOS_ACTIVOS.has(estado) ? 5_000 : false;
    },
  });

export const consultaNovela = (novelaId: number) =>
  queryOptions({
    queryKey: claves.novela(novelaId),
    queryFn: () => leer(api.GET("/novelas/{novela_id}", { params: { path: { novela_id: novelaId } } })),
  });

export const consultaEstructura = (novelaId: number) =>
  queryOptions({
    queryKey: claves.estructura(novelaId),
    queryFn: () =>
      leer(api.GET("/novelas/{novela_id}/estructura", { params: { path: { novela_id: novelaId } } })),
  });
