import { useQuery } from "@tanstack/react-query";
import type { CSSProperties } from "react";
import { Link } from "react-router";
import { consultaNovela } from "../../compartido/api/consultas";
import type { Regalo } from "../../compartido/api/tipos";
import { portadaDe } from "../../compartido/imagenes";
import { Astronauta } from "../../compartido/ui/Astronauta";
import { Hace } from "../../compartido/ui/Hace";
import { useTitulo } from "../../compartido/ui/titulo";
import { useLecturaActual } from "./MarcoLectura";
import { motivoLegible } from "./usarLectura";

const miles = new Intl.NumberFormat("es-ES");

/** Portada, novedades e índice de una versión (RF-FE-LEE-02, RF-FE-LEE-03, RF-FE-LEE-06). */
export function Portada() {
  const { novelaId, version, numero, enlace } = useLecturaActual();
  const novela = useQuery(consultaNovela(novelaId));
  useTitulo(version.titulo || "Lectura");
  const conNovedades = (numero ?? 1) > 1;
  const cambiados = new Set(version.capitulos_cambiados);
  // Hasta saber el subgénero, papel sin ilustración: así no parpadea la genérica.
  const ilustracion = novela.data ? portadaDe(novela.data.novela.subgenero_dominante).web : null;

  return (
    <div className="lectura__pila">
      <article className="libro portada portada--ilustrada" aria-labelledby="titulo-libro" style={fondoPortada(ilustracion)}>
        <div className="portada__texto">
          <p className="portada__genero">Terror espacial</p>
          <h1 id="titulo-libro" className="portada__titulo">
            {version.titulo || "Sin título"}
          </h1>
          {version.dedicatoria && <p className="portada__dedicatoria">{version.dedicatoria}</p>}
          <LineaRegalo regalo={novela.data?.regalo} />
        </div>
        <div className="portada__hueco" aria-hidden="true" />
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
      <Astronauta />
    </div>
  );
}

/** La ilustración de la portada como variable CSS (RF-FE-IMG-01), o nada mientras no se sabe cuál. */
export const fondoPortada = (src: string | null): CSSProperties | undefined =>
  src ? ({ "--portada": `url("${src}")` } as CSSProperties) : undefined;

/** Para quién es, de parte de quién y por qué ocasión (RF-FE-LEE-02). Nada si la novela no es un regalo. */
export function LineaRegalo({ regalo }: { regalo: Regalo | null | undefined }) {
  if (!regalo) return null;
  const ocasion = regalo.ocasion ? regalo.ocasion.charAt(0).toUpperCase() + regalo.ocasion.slice(1) : null;
  return (
    <p className="portada__regalo">
      {[`Para ${regalo.para}`, regalo.de ? `De ${regalo.de}` : null, ocasion].filter(Boolean).join(" · ")}
    </p>
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
