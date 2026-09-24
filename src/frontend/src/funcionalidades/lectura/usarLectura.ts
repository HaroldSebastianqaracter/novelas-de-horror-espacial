import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "react-router";
import { consultaVersion, consultaVersiones } from "../../compartido/api/consultas";

/** Lo que se lee (RF-FE-LEE-01): una versión publicada, la última salvo `?version=n`. */
export function useLectura() {
  const params = useParams();
  const [busqueda] = useSearchParams();
  const novelaId = Number(params.id);
  const versiones = useQuery(consultaVersiones(novelaId));
  const lista = [...(versiones.data ?? [])].sort((a, b) => a.numero - b.numero);
  const ultima = lista.at(-1)?.numero ?? null;
  const pedida = Number(busqueda.get("version")) || null;
  const numero = pedida ?? ultima;
  const version = useQuery({ ...consultaVersion(novelaId, numero ?? 0), enabled: numero !== null });
  const resumen = lista.find((v) => v.numero === numero);
  const esUltima = numero !== null && numero === ultima;

  /** Una ruta de la lectura que conserva la versión si no es la última. */
  const enlace = (ruta: string, extra: Record<string, string> = {}) => {
    const q = new URLSearchParams(extra);
    if (numero !== null && !esUltima) q.set("version", String(numero));
    const cadena = q.toString();
    return `/novelas/${novelaId}/lectura${ruta}${cadena ? `?${cadena}` : ""}`;
  };

  return { novelaId, versiones, lista, ultima, numero, resumen, esUltima, version, enlace };
}

export type Lectura = ReturnType<typeof useLectura>;

export const MOTIVO: Record<string, string> = {
  primera: "Primera edición",
  relanzamiento: "Reescrita desde un capítulo",
  cambio_lector: "Cambio pedido por el lector",
};
export const motivoLegible = (motivo: string) => MOTIVO[motivo] ?? motivo;
