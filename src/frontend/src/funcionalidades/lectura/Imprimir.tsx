import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router";
import { consultaNovela } from "../../compartido/api/consultas";
import { useTitulo } from "../../compartido/ui/titulo";
import { partirEnEscenas } from "../manuscrito/Lector";
import { FichaContenido, useConsultasFicha } from "./Ficha";
import { useLecturaActual } from "./MarcoLectura";
import { planoNave, portadaDe, precargar } from "../../compartido/imagenes";
import { fondoPortada, LineaRegalo } from "./Portada";
import { motivoLegible } from "./usarLectura";

const miles = new Intl.NumberFormat("es-ES");
const ancla = (n: number) => `cap-${n}`;

/**
 * El libro entero en una página, para imprimirlo o guardarlo como PDF (RF-FE-PDF-01): portada,
 * novedades, índice, capítulos en página nueva y la ficha como apéndice. Los enlaces son anclas,
 * que el PDF conserva. Con `?imprimir=1` abre el diálogo de imprimir en cuanto está listo (RF-FE-PDF-02).
 */
export function Imprimir() {
  const { novelaId, version, numero, esUltima, ultima } = useLecturaActual();
  const [busqueda] = useSearchParams();
  useTitulo(version.titulo || "Novela");
  // Lista solo con todo lo que lleva el libro: si el canon, las apariciones o la novela (la línea
  // del regalo) fallan, no se imprime un libro a medias, y `npm run pdf` lo detecta por
  // `data-error-impresion`.
  const ficha = useConsultasFicha(novelaId, esUltima);
  const novela = useQuery(consultaNovela(novelaId));
  // La portada y el plano son fondos CSS: sin precargarlos, el PDF podía salir sin ellos.
  const ilustracion = novela.data ? portadaDe(novela.data.novela.subgenero_dominante).impresion : null;
  const [imagenesListas, setImagenesListas] = useState<string | null>(null);
  useEffect(() => {
    if (!ilustracion) return;
    let vigente = true;
    void precargar([ilustracion, planoNave]).then(() => vigente && setImagenesListas(ilustracion));
    return () => {
      vigente = false;
    };
  }, [ilustracion]);
  const listo = ficha.listo && novela.isSuccess && imagenesListas === ilustracion;
  const fallo = ficha.error !== null || novela.isError;
  const impreso = useRef(false);

  useEffect(() => {
    if (!listo || impreso.current || busqueda.get("imprimir") !== "1") return;
    impreso.current = true;
    // Las fuentes de la hoja tienen que estar cargadas antes de maquetar.
    void (document.fonts?.ready ?? Promise.resolve()).then(() => window.print());
  }, [listo, busqueda]);

  const conNovedades = (numero ?? 1) > 1;
  const enlaceCapitulos = (ns: number[]) =>
    ns.map((n, i) => (
      <span key={n}>
        {i > 0 && (i === ns.length - 1 ? " y " : ", ")}
        <a href={`#${ancla(n)}`}>el capítulo {n}</a>
      </span>
    ));

  return (
    <div
      className="imprimir"
      data-listo-para-imprimir={listo ? true : undefined}
      data-error-impresion={fallo ? true : undefined}
    >
      <div className="imprimir__barra no-imprimir">
        <p>
          {fallo
            ? "No se pudo cargar la portada o la ficha de personajes y lugares: el libro no está completo para imprimirlo."
            : "Vista para imprimir: portada, índice, capítulos y personajes, cada capítulo en página nueva."}
        </p>
        <button type="button" className="boton boton--primario" onClick={() => window.print()} disabled={!listo}>
          Imprimir o guardar como PDF
        </button>
      </div>

      <section
        className="libro portada portada--ilustrada hoja"
        aria-labelledby="imprimir-titulo"
        style={fondoPortada(ilustracion)}
      >
        <div className="portada__texto">
          <p className="portada__genero">Terror espacial</p>
          <h1 id="imprimir-titulo" className="portada__titulo">
            {version.titulo || "Sin título"}
          </h1>
          {version.dedicatoria && <p className="portada__dedicatoria">{version.dedicatoria}</p>}
          <LineaRegalo regalo={novela.data?.regalo} />
          <p className="portada__edicion">
            Versión {numero} · {motivoLegible(version.motivo).toLowerCase()}
          </p>
        </div>
        <div className="portada__hueco" aria-hidden="true" />
      </section>

      {conNovedades && (
        <section className="libro novedades hoja" aria-labelledby="imprimir-novedades">
          <h2 id="imprimir-novedades">Novedades de la versión {numero}</h2>
          <p className="novedades__motivo">{motivoLegible(version.motivo)}</p>
          {version.detalle && <blockquote className="novedades__detalle">{version.detalle}</blockquote>}
          <p>
            {version.capitulos_cambiados.length > 0 ? (
              <>Cambiaron {enlaceCapitulos(version.capitulos_cambiados)}.</>
            ) : (
              "No cambió el texto de ningún capítulo."
            )}
          </p>
        </section>
      )}

      <nav className="libro indice hoja" aria-labelledby="imprimir-indice">
        <h2 id="imprimir-indice">Índice</h2>
        <ol className="indice__lista">
          {version.capitulos.map((c) => (
            <li key={c.numero}>
              <a href={`#${ancla(c.numero)}`}>Capítulo {c.numero}</a>
              <span className="indice__relleno" aria-hidden="true" />
              {conNovedades && c.cambiado && <span className="marca-cambio">cambió en la versión {numero}</span>}
              <span className="indice__palabras">{miles.format(c.palabras)} palabras</span>
            </li>
          ))}
          <li>
            <a href="#apendice-ficha">Personajes y lugares</a>
            <span className="indice__relleno" aria-hidden="true" />
          </li>
        </ol>
      </nav>

      {version.capitulos.map((c) => (
        <article key={c.numero} id={ancla(c.numero)} className="libro capitulo hoja" aria-labelledby={`imprimir-cap-${c.numero}`}>
          <header className="capitulo__cabecera">
            <h2 id={`imprimir-cap-${c.numero}`}>Capítulo {c.numero}</h2>
          </header>
          <div className="capitulo__texto">
            {partirEnEscenas(c.texto).map((parrafos, i) => (
              <section key={i} className="capitulo__escena" aria-label={`Capítulo ${c.numero}, escena ${i + 1}`}>
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
        </article>
      ))}

      <section id="apendice-ficha" className="libro ficha hoja" aria-labelledby="imprimir-ficha">
        <div className="ficha__plano" aria-hidden="true" />
        <h2 id="imprimir-ficha">Personajes y lugares</h2>
        <FichaContenido
          novelaId={novelaId}
          version={version}
          esUltima={esUltima}
          ultima={ultima}
          nivel={3}
          enlazar={(n) => (
            <a href={`#${ancla(n)}`} aria-label={`capítulo ${n}`}>
              {n}
            </a>
          )}
        />
      </section>
    </div>
  );
}
