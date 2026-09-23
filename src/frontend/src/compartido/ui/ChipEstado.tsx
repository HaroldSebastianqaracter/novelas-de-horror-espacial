import { comoEstadoEjecucion } from "../api/reglas";
import { ETIQUETA_ESTADO, ICONO_ESTADO } from "./vocabulario";
import "./ui.css";

/** Píldora de estado. Un estado que el cliente no conoce se pinta tal cual (RF-FE-API-04). */
export function ChipEstado({ estado }: { estado: string | null | undefined }) {
  const conocido = comoEstadoEjecucion(estado);
  if (!conocido) {
    return (
      <span className="chip" data-estado="desconocido" title="Estado que esta versión del frontend no conoce">
        <span className="chip__icono" aria-hidden="true">?</span>
        {estado ?? "sin ejecución"}
      </span>
    );
  }
  return (
    <span className="chip" data-estado={conocido}>
      <span className="chip__icono" aria-hidden="true">
        {ICONO_ESTADO[conocido]}
      </span>
      {ETIQUETA_ESTADO[conocido]}
    </span>
  );
}
