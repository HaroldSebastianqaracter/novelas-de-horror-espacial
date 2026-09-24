import { useEffect, useRef } from "react";
import { Link, NavLink, Outlet, useLocation, useOutletContext } from "react-router";
import { ErrorApi } from "../../compartido/api/cliente";
import { useEventosNovela } from "../../compartido/api/eventos";
import { EstadoConsulta } from "../../compartido/ui/EstadoConsulta";
import { useTitulo } from "../../compartido/ui/titulo";
import { type CambioGuardado, useCambioGuardado } from "./cambioGuardado";
import { FranjaCambio } from "./FranjaCambio";
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
  const [cambio, guardarCambio] = useCambioGuardado(novelaId);
  const contexto: ContextoLectura = { ...lectura, cambio, guardarCambio };
  const sinLectura = !versiones.isPending && lista.length === 0;
  useTitulo(sinLectura ? "Sin lectura todavía" : noExiste ? `No existe la versión ${numero}` : null);

  // Al cambiar de vista (o de versión), se lee desde arriba y el foco va al texto (RF-FE-LEE-08).
  // Al cargar no se mueve: el primer foco es el enlace para saltar al texto.
  const principal = useRef<HTMLElement>(null);
  const { pathname } = useLocation();
  const vista = numero === null ? null : `${pathname}|${numero}`;
  const vistaAnterior = useRef<string | null>(null);
  useEffect(() => {
    // Resolver la versión al cargar no es cambiar de vista: la primera vista conocida solo se anota.
    if (vista === null || vistaAnterior.current === vista) return;
    const primera = vistaAnterior.current === null;
    vistaAnterior.current = vista;
    if (primera) return;
    document.documentElement.scrollTop = 0;
    principal.current?.focus({ preventScroll: true });
  }, [vista]);

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
      <main ref={principal} id="contenido-lectura" className="lectura__contenido" tabIndex={-1}>
        {cambio && (
          <FranjaCambio
            novelaId={novelaId}
            cambio={cambio}
            versiones={lista}
            alCerrar={() => guardarCambio(null)}
            alTerminar={() => guardarCambio({ ...cambio, terminado: true })}
          />
        )}
        <EstadoConsulta cargando={versiones.isPending} error={versiones.error} reintentar={() => void versiones.refetch()}>
          {sinLectura ? (
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
              {version.data && <Outlet context={contexto} />}
            </EstadoConsulta>
          )}
        </EstadoConsulta>
      </main>
    </div>
  );
}

type ContextoLectura = Lectura & {
  cambio: CambioGuardado | null;
  guardarCambio: (cambio: CambioGuardado | null) => void;
};

/** La lectura resuelta por el marco, con su versión ya cargada. */
export function useLecturaActual() {
  const lectura = useOutletContext<ContextoLectura>();
  const version = lectura.version.data;
  if (!version) throw new Error("La vista de lectura se pintó sin versión");
  return { ...lectura, version };
}
