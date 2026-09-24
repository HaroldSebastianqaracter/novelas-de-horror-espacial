/**
 * Claves y consultas de TanStack Query. El `GET` es la verdad (RF-FE-DAT-01): nada de esto
 * guarda datos propios, solo la caché de lo que dice el servidor.
 */
import { queryOptions } from "@tanstack/react-query";
import { leerCambios, type ObjetivoCambio } from "./cambios";
import { api, ErrorApi, leer } from "./cliente";
import { comoEstadoEjecucion, ESTADOS_ACTIVOS } from "./reglas";

export const claves = {
  novelas: ["novelas"] as const,
  novela: (id: number) => ["novelas", id] as const,
  ejecucion: (id: number) => ["novelas", id, "ejecucion"] as const,
  estructura: (id: number) => ["novelas", id, "estructura"] as const,
  paradas: (id: number) => ["novelas", id, "paradas"] as const,
  parada: (id: number, pid: number) => ["novelas", id, "paradas", pid] as const,
  capitulo: (id: number, n: number) => ["novelas", id, "capitulos", n] as const,
  versiones: (id: number) => ["novelas", id, "versiones"] as const,
  version: (id: number, n: number) => ["novelas", id, "versiones", n] as const,
  canon: (id: number, entidad: EntidadLectura) => ["novelas", id, "canon", entidad] as const,
  apariciones: (id: number) => ["novelas", id, "apariciones"] as const,
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

export const consultaParada = (novelaId: number, paradaId: number) =>
  queryOptions({
    queryKey: claves.parada(novelaId, paradaId),
    queryFn: () =>
      leer(
        api.GET("/novelas/{novela_id}/paradas/{parada_id}", {
          params: { path: { novela_id: novelaId, parada_id: paradaId } },
        }),
      ),
  });

export const consultaCapitulo = (novelaId: number, numero: number) =>
  queryOptions({
    queryKey: claves.capitulo(novelaId, numero),
    queryFn: () =>
      leer(
        api.GET("/novelas/{novela_id}/capitulos/{numero}", {
          params: { path: { novela_id: novelaId, numero } },
        }),
      ),
  });

/** Las entidades del canon que usa la lectura (RF-FE-LEE-04, RF-FE-CAM-02). */
export type EntidadLectura = "personajes" | "lugares" | "objetos";

export const consultaVersiones = (novelaId: number) =>
  queryOptions({
    queryKey: claves.versiones(novelaId),
    queryFn: () =>
      leer(api.GET("/novelas/{novela_id}/versiones", { params: { path: { novela_id: novelaId } } })),
  });

/** Una versión publicada no cambia nunca (RF3-BIB-11): no hace falta reconsultarla. */
export const consultaVersion = (novelaId: number, numero: number) =>
  queryOptions({
    queryKey: claves.version(novelaId, numero),
    queryFn: () =>
      leer(
        api.GET("/novelas/{novela_id}/versiones/{numero}", {
          params: { path: { novela_id: novelaId, numero } },
        }),
      ),
    staleTime: Infinity,
  });

/** Los hechos que se establecen o se usan en un capítulo (vista `hecho_escena`). */
export const consultaHechosDeCapitulo = (novelaId: number, capitulo: number) =>
  queryOptions({
    queryKey: [...claves.novela(novelaId), "hechos", capitulo] as const,
    queryFn: () =>
      leer(
        api.GET("/novelas/{novela_id}/hechos", {
          params: { path: { novela_id: novelaId }, query: { capitulo, limite: 500 } },
        }),
      ),
  });

/** La misma consulta que usa el seguidor de intenciones: comparten caché. */
export const consultaIntencion = (intencionId: number) =>
  queryOptions({
    queryKey: claves.intencion(intencionId),
    queryFn: () =>
      leer(api.GET("/intenciones/{intencion_id}", { params: { path: { intencion_id: intencionId } } })),
  });

export const consultaCanon = (novelaId: number, entidad: EntidadLectura) =>
  queryOptions({
    queryKey: claves.canon(novelaId, entidad),
    queryFn: () =>
      leer(
        api.GET("/novelas/{novela_id}/canon/{entidad}", {
          params: { path: { novela_id: novelaId, entidad } },
        }),
      ),
  });

/** Dónde aparece cada personaje y cada lugar, en los capítulos completados (RF3-LEC-02). */
export const consultaApariciones = (novelaId: number) =>
  queryOptions({
    queryKey: claves.apariciones(novelaId),
    queryFn: () =>
      leer(api.GET("/novelas/{novela_id}/apariciones", { params: { path: { novela_id: novelaId } } })),
  });

/** Los cambios del lector de la novela, con lo que entendió el intérprete y la versión que publicaron. */
export const consultaCambios = (novelaId: number) =>
  queryOptions({
    queryKey: [...claves.novela(novelaId), "cambios", "lista"] as const,
    queryFn: () => leerCambios(novelaId),
  });

/** Los capítulos que reescribiría un cambio, con la regla del worker (RF3-CAM-05). Un fragmento no tiene. */
export const consultaAlcance = (novelaId: number, objetivo: ObjetivoCambio | undefined) =>
  queryOptions({
    queryKey: [...claves.novela(novelaId), "cambios", "alcance", objetivo ?? null] as const,
    queryFn: () => {
      if (!objetivo || objetivo.tipo === "fragmento") throw new Error("Un fragmento no tiene alcance previo");
      const query =
        objetivo.tipo === "hecho" ? { hecho_id: objetivo.hecho_id } : { entidad: objetivo.entidad, id: objetivo.id };
      return leer(api.GET("/novelas/{novela_id}/cambios/alcance", { params: { path: { novela_id: novelaId }, query } }));
    },
    enabled: !!objetivo && objetivo.tipo !== "fragmento",
  });

/** Un 4xx no mejora reintentando: se enseña ya. Los fallos de red y los 5xx, hasta tres veces. */
export const reintentar = (intentos: number, error: Error) =>
  !(error instanceof ErrorApi && error.estado >= 400 && error.estado < 500) && intentos < 3;
