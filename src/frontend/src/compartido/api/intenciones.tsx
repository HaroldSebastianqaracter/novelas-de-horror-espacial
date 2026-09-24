/**
 * Ciclo de una intención (RF-FE-DAT-05): se encola, se consulta hasta que el worker la cierra
 * y entonces se invalida lo que pudo cambiar. La tarjeta que la pidió no se mueve por esto:
 * se mueve cuando la ejecución, que es la verdad, dice otra cosa.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { MOTIVOS_CAMBIO } from "./cambios";
import { api, leer } from "./cliente";
import { claves } from "./consultas";
import { comoEstadoIntencion } from "./reglas";
import type { Intencion, NuevaIntencion, TipoIntencion } from "./tipos";

export interface Seguimiento {
  id: number;
  tipo: TipoIntencion;
  novelaId: number | null;
  /** Cuándo se encoló, en ms. Pasado un minuto se consulta más despacio y se avisa. */
  desde: number;
}

export interface Rechazo {
  tipo: TipoIntencion;
  motivo: string;
}

interface Opciones {
  /** Para quien necesita el resultado, como `crear_novela` con su `novela_id`. No se guarda al recargar. */
  alTerminar?: (intencion: Intencion) => void;
}

interface ContextoIntenciones {
  pendientes: readonly Seguimiento[];
  rechazos: Readonly<Record<number, Rechazo>>;
  pedir: (intencion: NuevaIntencion, opciones?: Opciones) => Promise<Seguimiento>;
  descartarRechazo: (novelaId: number) => void;
}

export const UN_MINUTO = 60_000;
const CLAVE_ALMACEN = "novelasv2.intenciones";

const MOTIVOS: Record<string, string> = {
  otra_ejecucion_activa: "Ya hay otra novela en curso: solo se genera una a la vez.",
  worker_caido: "El worker se reinició antes de atenderla. Vuelve a pedirla.",
  ...MOTIVOS_CAMBIO,
};

/** El motivo del worker en lenguaje legible, o tal cual si no se conoce. */
export function motivoLegible(motivo: string | null | undefined, estado: string): string {
  if (motivo && motivo in MOTIVOS) return MOTIVOS[motivo] as string;
  if (motivo) return motivo.charAt(0).toUpperCase() + motivo.slice(1);
  return estado === "interrumpida" ? "Se interrumpió sin motivo declarado." : "El worker la rechazó sin motivo declarado.";
}

function leerAlmacen(): Seguimiento[] {
  try {
    const crudo = sessionStorage.getItem(CLAVE_ALMACEN);
    return crudo ? (JSON.parse(crudo) as Seguimiento[]) : [];
  } catch {
    return [];
  }
}

function escribirAlmacen(pendientes: readonly Seguimiento[]) {
  try {
    sessionStorage.setItem(CLAVE_ALMACEN, JSON.stringify(pendientes));
  } catch {
    // Sin almacenamiento, las pendientes solo se pierden al recargar.
  }
}

const Contexto = createContext<ContextoIntenciones | null>(null);

export function IntencionesProvider({ children }: { children: ReactNode }) {
  const clienteConsultas = useQueryClient();
  const [pendientes, setPendientes] = useState<Seguimiento[]>(leerAlmacen);
  const [rechazos, setRechazos] = useState<Record<number, Rechazo>>({});
  const retrollamadas = useRef(new Map<number, Opciones["alTerminar"]>());

  useEffect(() => escribirAlmacen(pendientes), [pendientes]);

  const descartarRechazo = useCallback((novelaId: number) => {
    setRechazos(({ [novelaId]: _, ...resto }) => resto);
  }, []);

  const pedir = useCallback(
    async (intencion: NuevaIntencion, opciones?: Opciones) => {
      const encolada = await leer(api.POST("/intenciones", { body: intencion }));
      const seguimiento: Seguimiento = {
        id: encolada.id,
        tipo: intencion.tipo,
        novelaId: intencion.novela_id ?? null,
        desde: Date.now(),
      };
      if (opciones?.alTerminar) retrollamadas.current.set(seguimiento.id, opciones.alTerminar);
      if (seguimiento.novelaId !== null) descartarRechazo(seguimiento.novelaId);
      setPendientes((actuales) => [...actuales, seguimiento]);
      return seguimiento;
    },
    [descartarRechazo],
  );

  const alCerrar = useCallback(
    (seguimiento: Seguimiento, intencion: Intencion) => {
      setPendientes((actuales) => actuales.filter((p) => p.id !== seguimiento.id));
      if (intencion.estado !== "hecha" && seguimiento.novelaId !== null) {
        const novelaId = seguimiento.novelaId;
        setRechazos((actuales) => ({
          ...actuales,
          [novelaId]: { tipo: seguimiento.tipo, motivo: motivoLegible(intencion.motivo, intencion.estado) },
        }));
      }
      retrollamadas.current.get(seguimiento.id)?.(intencion);
      retrollamadas.current.delete(seguimiento.id);
      void clienteConsultas.invalidateQueries({ queryKey: claves.novelas });
    },
    [clienteConsultas],
  );

  const valor = useMemo(
    () => ({ pendientes, rechazos, pedir, descartarRechazo }),
    [pendientes, rechazos, pedir, descartarRechazo],
  );

  return (
    <Contexto.Provider value={valor}>
      {pendientes.map((p) => (
        <Seguidor key={p.id} seguimiento={p} alCerrar={alCerrar} />
      ))}
      {children}
    </Contexto.Provider>
  );
}

/** Consulta una intención hasta que se cierra. No pinta nada. */
function Seguidor({
  seguimiento,
  alCerrar,
}: {
  seguimiento: Seguimiento;
  alCerrar: (s: Seguimiento, i: Intencion) => void;
}) {
  const { data } = useQuery({
    queryKey: claves.intencion(seguimiento.id),
    queryFn: () =>
      leer(api.GET("/intenciones/{intencion_id}", { params: { path: { intencion_id: seguimiento.id } } })),
    refetchInterval: () => (Date.now() - seguimiento.desde < UN_MINUTO ? 1_000 : 5_000),
  });

  useEffect(() => {
    const estado = comoEstadoIntencion(data?.estado);
    if (data && (estado === "hecha" || estado === "rechazada" || estado === "interrumpida")) {
      alCerrar(seguimiento, data);
    }
  }, [data, seguimiento, alCerrar]);

  return null;
}

export function useIntenciones(): ContextoIntenciones {
  const contexto = useContext(Contexto);
  if (!contexto) throw new Error("useIntenciones necesita un IntencionesProvider por encima");
  return contexto;
}
