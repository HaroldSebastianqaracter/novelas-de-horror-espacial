import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router";
import { ErrorApi } from "../../compartido/api/cliente";
import { consultaCapitulo, consultaEstructura, consultaNovela } from "../../compartido/api/consultas";
import { EstadoConsulta } from "../../compartido/ui/EstadoConsulta";
import "./Lector.css";

/** El separador de escenas con el que `compilar` une el capítulo (RF-FE-LEC-01). */
const SEPARADOR_ESCENAS = /\n\s*\*\s\*\s\*\s*\n/;

const dos = (n: number) => String(n).padStart(2, "0");
const miles = new Intl.NumberFormat("es-ES");

export function partirEnEscenas(texto: string): string[][] {
  return texto
    .split(SEPARADOR_ESCENAS)
    .map((escena) =>
      escena
        .split(/\n{2,}/)
        .map((p) => p.trim())
        .filter(Boolean),
    )
    .filter((parrafos) => parrafos.length > 0);
}

/** Lector de un capítulo cerrado (RF-FE-LEC). */
export function Lector() {
  const params = useParams();
  const novelaId = Number(params.id);
  const numero = Number(params.n);
  const capitulo = useQuery(consultaCapitulo(novelaId, numero));
  const detalle = useQuery(consultaNovela(novelaId));
  const estructura = useQuery(consultaEstructura(novelaId));

  const cerrados = (estructura.data?.capitulos ?? [])
    .filter((c) => c.estado === "completado")
    .map((c) => c.numero)
    .sort((a, b) => a - b);
  const anterior = [...cerrados].reverse().find((n) => n < numero);
  const siguiente = cerrados.find((n) => n > numero);
  const objetivo = estructura.data?.capitulos.find((c) => c.numero === numero)?.objetivo;
  const noEscrito = capitulo.error instanceof ErrorApi && capitulo.error.estado === 404;
  const tituloNovela = detalle.data?.novela.titulo || "Sin título";

  const navegacion = (
    <nav className="lector__navegacion" aria-label="Capítulos">
      {anterior ? (
        <Link to={`/novelas/${novelaId}/capitulos/${anterior}`} rel="prev">
          ← Capítulo {anterior}
        </Link>
      ) : (
        <span />
      )}
      <Link to={`/novelas/${novelaId}`}>Índice de la novela</Link>
      {siguiente ? (
        <Link to={`/novelas/${novelaId}/capitulos/${siguiente}`} rel="next">
          Capítulo {siguiente} →
        </Link>
      ) : (
        <span />
      )}
    </nav>
  );

  return (
    <section className="pantalla lector" aria-labelledby="titulo-capitulo">
      <nav className="migas" aria-label="Ruta">
        <Link to="/">Tablero</Link>
        <span aria-hidden="true">/</span>
        <Link to={`/novelas/${novelaId}`}>{tituloNovela}</Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page">Capítulo {numero}</span>
      </nav>
      {noEscrito ? (
        <div className="aviso">
          <h1 id="titulo-capitulo">El capítulo {numero} todavía no está escrito</h1>
          <p>
            Un capítulo solo existe para el lector cuando pasa la puerta 4.{" "}
            <Link to={`/novelas/${novelaId}`}>Volver a la novela</Link>.
          </p>
        </div>
      ) : (
        <EstadoConsulta cargando={capitulo.isPending} error={capitulo.error} reintentar={() => void capitulo.refetch()}>
          {capitulo.data && (
            <article className="lector__hoja">
              <header className="lector__cabecera">
                <p className="lector__novela">{tituloNovela}</p>
                <h1 id="titulo-capitulo">Capítulo {numero}</h1>
                {objetivo && <p className="lector__objetivo">{objetivo}</p>}
                <p className="codigo">
                  CAP {dos(numero)} · versión {capitulo.data.version} · {miles.format(capitulo.data.palabras)} palabras
                </p>
              </header>
              {partirEnEscenas(capitulo.data.texto).map((parrafos, i) => (
                <section key={i} className="lector__escena" aria-label={`Escena ${i + 1}`}>
                  {i > 0 && (
                    <p className="lector__ornamento" aria-hidden="true">
                      * * *
                    </p>
                  )}
                  {parrafos.map((parrafo, j) => (
                    <p key={j}>{parrafo}</p>
                  ))}
                </section>
              ))}
              {navegacion}
            </article>
          )}
        </EstadoConsulta>
      )}
    </section>
  );
}
