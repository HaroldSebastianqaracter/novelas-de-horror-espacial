import { Link } from "react-router";
import { Hace } from "../../compartido/ui/Hace";
import { useTitulo } from "../../compartido/ui/titulo";
import { useLecturaActual } from "./MarcoLectura";
import { motivoLegible } from "./usarLectura";

const miles = new Intl.NumberFormat("es-ES");

/** Portada, novedades e índice de una versión (RF-FE-LEE-02, RF-FE-LEE-03, RF-FE-LEE-06). */
export function Portada() {
  const { version, numero, enlace } = useLecturaActual();
  useTitulo(version.titulo || "Lectura");
  const conNovedades = (numero ?? 1) > 1;
  const cambiados = new Set(version.capitulos_cambiados);

  return (
    <div className="lectura__pila">
      <article className="libro portada" aria-labelledby="titulo-libro">
        <p className="portada__genero">Terror espacial</p>
        <h1 id="titulo-libro" className="portada__titulo">
          {version.titulo || "Sin título"}
        </h1>
        {version.dedicatoria && <p className="portada__dedicatoria">{version.dedicatoria}</p>}
      </article>

      {conNovedades && <Novedades />}

      <nav className="libro indice" aria-labelledby="titulo-indice">
        <h2 id="titulo-indice">Índice</h2>
        <ol className="indice__lista">
          {version.capitulos.map((c) => (
            <li key={c.numero}>
              <Link to={enlace(`/capitulos/${c.numero}`)}>Capítulo {c.numero}</Link>
              <span className="indice__relleno" aria-hidden="true" />
              {conNovedades && cambiados.has(c.numero) && <span className="marca-cambio">cambió en la versión {numero}</span>}
              <span className="indice__palabras">{miles.format(c.palabras)} palabras</span>
            </li>
          ))}
        </ol>
        <p className="indice__mas">
          <Link to={enlace("/ficha")}>Personajes y lugares</Link>
          <span aria-hidden="true"> · </span>
          <Link to={enlace("/versiones")}>Todas las versiones</Link>
          <span aria-hidden="true"> · </span>
          <Link to={enlace("/imprimir", { imprimir: "1" })}>Exportar a PDF</Link>
        </p>
      </nav>
    </div>
  );
}

/** Lo nuevo de esta versión respecto a la anterior (RF-FE-LEE-06). */
function Novedades() {
  const { version, numero, resumen, enlace } = useLecturaActual();
  return (
    <section className="libro novedades" aria-labelledby="titulo-novedades">
      <h2 id="titulo-novedades">Novedades de la versión {numero}</h2>
      <p className="novedades__motivo">
        {motivoLegible(version.motivo)}
        {resumen && (
          <>
            {" · "}
            <Hace iso={resumen.creado_en} />
          </>
        )}
      </p>
      {version.detalle && <blockquote className="novedades__detalle">{version.detalle}</blockquote>}
      {version.capitulos_cambiados.length > 0 ? (
        <p>
          Cambiaron{" "}
          {version.capitulos_cambiados.map((n, i) => (
            <span key={n}>
              {i > 0 && (i === version.capitulos_cambiados.length - 1 ? " y " : ", ")}
              <Link to={enlace(`/capitulos/${n}`, { cambios: "1" })}>el capítulo {n}</Link>
            </span>
          ))}
          .
        </p>
      ) : (
        <p>No cambió el texto de ningún capítulo.</p>
      )}
    </section>
  );
}
