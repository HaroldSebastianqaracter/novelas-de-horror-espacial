import { Link, NavLink, Outlet, useOutletContext } from "react-router";
import { ErrorApi } from "../../compartido/api/cliente";
import { useEventosNovela } from "../../compartido/api/eventos";
import { EstadoConsulta } from "../../compartido/ui/EstadoConsulta";
import { type Lectura, useLectura } from "./usarLectura";
import "./Lectura.css";

/**
 * Marco de la lectura (RF-FE-LEE): papel y tipografía de lectura, sin la barra de la consola.
 * Resuelve qué versión se lee y cubre los estados comunes; las vistas reciben la lectura por contexto.
 */
export function MarcoLectura() {
  const lectura = useLectura();
  const { novelaId, versiones, lista, numero, esUltima, ultima, version, enlace } = lectura;
  // El SSE invalida `/versiones`: una versión nueva aparece sola (RF-FE-CAM-05).
  useEventosNovela(novelaId);
  const noExiste = version.error instanceof ErrorApi && version.error.estado === 404;

  return (
    <div className="lectura">
      <a className="saltar" href="#contenido-lectura">
        Saltar al texto
      </a>
      <header className="lectura__barra">
        <Link className="lectura__consola" to={`/novelas/${novelaId}`}>
          ← Consola
        </Link>
        <nav className="lectura__nav" aria-label="Lectura">
          <NavLink to={enlace("")} end>
            Portada
          </NavLink>
          <NavLink to={enlace("/ficha")}>Personajes y lugares</NavLink>
          <NavLink to={enlace("/versiones")}>Versiones</NavLink>
        </nav>
        {numero !== null && (
          <p className="lectura__version">
            Versión {numero}
            {!esUltima && ultima !== null && (
              <>
                {" "}
                · <Link to={`/novelas/${novelaId}/lectura`}>ir a la última ({ultima})</Link>
              </>
            )}
          </p>
        )}
      </header>
      <main id="contenido-lectura" className="lectura__contenido" tabIndex={-1}>
        <EstadoConsulta cargando={versiones.isPending} error={versiones.error} reintentar={() => void versiones.refetch()}>
          {lista.length === 0 ? (
            <div className="aviso">
              <h1 className="lectura__titulo-aviso">Esta novela todavía no tiene lectura</h1>
              <p>
                La lectura enseña versiones publicadas, y una versión nace cuando la novela se completa.{" "}
                <Link to={`/novelas/${novelaId}`}>Ver cómo va en la consola</Link>.
              </p>
            </div>
          ) : noExiste ? (
            <div className="aviso">
              <h1 className="lectura__titulo-aviso">No existe la versión {numero}</h1>
              <p>
                <Link to={`/novelas/${novelaId}/lectura`}>Leer la última versión</Link>.
              </p>
            </div>
          ) : (
            <EstadoConsulta cargando={version.isPending} error={version.error} reintentar={() => void version.refetch()}>
              {version.data && <Outlet context={lectura} />}
            </EstadoConsulta>
          )}
        </EstadoConsulta>
      </main>
    </div>
  );
}

/** La lectura resuelta por el marco, con su versión ya cargada. */
export function useLecturaActual() {
  const lectura = useOutletContext<Lectura>();
  const version = lectura.version.data;
  if (!version) throw new Error("La vista de lectura se pintó sin versión");
  return { ...lectura, version };
}
