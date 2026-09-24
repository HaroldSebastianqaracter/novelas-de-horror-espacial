import type { ReactNode } from "react";
import { Astronauta } from "./Astronauta";
import "./ui.css";

interface Props {
  cargando: boolean;
  error: Error | null;
  reintentar: () => void;
  children: ReactNode;
}

/** Los estados «cargando» y «error de red con reintento» que toda pantalla cubre (spec, sección 4). */
export function EstadoConsulta({ cargando, error, reintentar, children }: Props) {
  if (cargando) {
    return (
      <div className="aviso aviso--carga" role="status">
        <Astronauta modo="flotar" />
        <span>Consultando…</span>
      </div>
    );
  }
  if (error) {
    return (
      <div className="aviso aviso--error" role="alert">
        <p>No se pudo consultar: {error.message}</p>
        <button type="button" className="boton" onClick={reintentar}>
          Reintentar
        </button>
      </div>
    );
  }
  return <>{children}</>;
}
