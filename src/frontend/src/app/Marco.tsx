import { NavLink, Outlet } from "react-router";
import "./Marco.css";

/** Cabecera persistente y zona de contenido. */
export function Marco() {
  return (
    <>
      <a className="saltar" href="#contenido">
        Saltar al contenido
      </a>
      <header className="cabecera">
        <div className="cabecera__marca">
          <span className="marca__nombre">novelasv2</span>
          <span className="marca__codigo">Consola de composición</span>
        </div>
        <nav className="cabecera__nav" aria-label="Principal">
          <NavLink to="/" end>
            Tablero
          </NavLink>
          <NavLink to="/crear">Nueva novela</NavLink>
        </nav>
      </header>
      <main id="contenido" className="contenido" tabIndex={-1}>
        <Outlet />
      </main>
    </>
  );
}
