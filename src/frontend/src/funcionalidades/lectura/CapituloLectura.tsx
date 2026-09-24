import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { consultaVersion } from "../../compartido/api/consultas";
import { EstadoConsulta } from "../../compartido/ui/EstadoConsulta";
import { useTitulo } from "../../compartido/ui/titulo";
import { partirEnEscenas } from "../manuscrito/Lector";
import { compararCapitulo, type ParrafoComparado } from "./comparar";
import { useLecturaActual } from "./MarcoLectura";

const miles = new Intl.NumberFormat("es-ES");
const ORNAMENTO = /^\*\s\*\s\*$/;

/** Un capítulo de la versión que se lee, con «qué cambió» si cambió en ella (RF-FE-LEE-05, RF-FE-LEE-07). */
export function CapituloLectura({ herramientas }: { herramientas?: (numero: number, texto: string) => ReactNode }) {
  const { novelaId, version, numero, enlace } = useLecturaActual();
  const n = Number(useParams().n);
  const [busqueda, setBusqueda] = useSearchParams();
  const capitulo = version.capitulos.find((c) => c.numero === n);
  useTitulo(capitulo ? `Capítulo ${n} · ${version.titulo}` : null);

  const puedeComparar = !!capitulo?.cambiado && (numero ?? 1) > 1;
  const comparando = puedeComparar && busqueda.get("cambios") === "1";
  const anteriorVersion = useQuery({ ...consultaVersion(novelaId, (numero ?? 1) - 1), enabled: comparando });

  const numeros = version.capitulos.map((c) => c.numero);
  const anterior = [...numeros].reverse().find((x) => x < n);
  const siguiente = numeros.find((x) => x > n);

  if (!capitulo) {
    return (
      <div className="aviso">
        <h1 className="lectura__titulo-aviso">La versión {numero} no tiene capítulo {n}</h1>
        <p>
          <Link to={enlace("")}>Volver al índice</Link>.
        </p>
      </div>
    );
  }

  const alternar = () => {
    const q = new URLSearchParams(busqueda);
    if (comparando) q.delete("cambios");
    else q.set("cambios", "1");
    setBusqueda(q, { replace: true });
  };

  return (
    <article className="libro capitulo" aria-labelledby="titulo-capitulo">
      <header className="capitulo__cabecera">
        <p className="capitulo__novela">{version.titulo}</p>
        <h1 id="titulo-capitulo">Capítulo {n}</h1>
        <p className="capitulo__meta">{miles.format(capitulo.palabras)} palabras</p>
        <div className="capitulo__herramientas">
          {puedeComparar && (
            <button type="button" className="boton boton--mini" aria-pressed={comparando} onClick={alternar}>
              {comparando ? "Ocultar los cambios" : `Ver qué cambió en la versión ${numero}`}
            </button>
          )}
          {herramientas?.(n, capitulo.texto)}
        </div>
      </header>

      {comparando ? (
        <EstadoConsulta
          cargando={anteriorVersion.isPending}
          error={anteriorVersion.error}
          reintentar={() => void anteriorVersion.refetch()}
        >
          {anteriorVersion.data && (
            <Comparacion
              parrafos={compararCapitulo(
                anteriorVersion.data.capitulos.find((c) => c.numero === n)?.texto,
                capitulo.texto,
              )}
              versionAnterior={(numero ?? 1) - 1}
            />
          )}
        </EstadoConsulta>
      ) : (
        <div className="capitulo__texto" data-capitulo={n}>
          {partirEnEscenas(capitulo.texto).map((parrafos, i) => (
            <section key={i} className="capitulo__escena" aria-label={`Escena ${i + 1}`}>
              {i > 0 && (
                <p className="capitulo__ornamento" aria-hidden="true">
                  * * *
                </p>
              )}
              {parrafos.map((p, j) => (
                <p key={j}>{p}</p>
              ))}
            </section>
          ))}
        </div>
      )}

      <nav className="capitulo__navegacion" aria-label="Capítulos">
        {anterior ? (
          <Link to={enlace(`/capitulos/${anterior}`)} rel="prev">
            ← Capítulo {anterior}
          </Link>
        ) : (
          <span />
        )}
        <Link to={enlace("")}>Índice</Link>
        {siguiente ? (
          <Link to={enlace(`/capitulos/${siguiente}`)} rel="next">
            Capítulo {siguiente} →
          </Link>
        ) : (
          <span />
        )}
      </nav>
    </article>
  );
}

function Comparacion({ parrafos, versionAnterior }: { parrafos: ParrafoComparado[]; versionAnterior: number }) {
  return (
    <div className="capitulo__texto comparacion">
      <p className="comparacion__leyenda">
        Comparado con la versión {versionAnterior}: <ins>así lo añadido</ins> y <del>así lo quitado</del>.
      </p>
      {parrafos.map((p, i) => {
        const texto = p.trozos.map((t) => t.texto).join("");
        if (ORNAMENTO.test(texto.trim())) {
          return (
            <p key={i} className="capitulo__ornamento" aria-hidden="true">
              * * *
            </p>
          );
        }
        return (
          <p key={i} data-cambio={p.tipo === "igual" ? undefined : p.tipo}>
            {p.trozos.map((t, j) =>
              t.tipo === "nuevo" ? <ins key={j}>{t.texto}</ins> : t.tipo === "quitado" ? <del key={j}>{t.texto}</del> : t.texto,
            )}
          </p>
        );
      })}
    </div>
  );
}
