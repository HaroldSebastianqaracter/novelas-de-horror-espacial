import { useQuery } from "@tanstack/react-query";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { consultaEjecucion, consultaNovelas, consultaVersion } from "../../compartido/api/consultas";
import { comoEstadoEjecucion, ESTADOS_ACTIVOS } from "../../compartido/api/reglas";
import { EstadoConsulta } from "../../compartido/ui/EstadoConsulta";
import { ConEnfasis, trozosConEnfasis } from "../../compartido/ui/Prosa";
import { useTitulo } from "../../compartido/ui/titulo";
import { partirEnEscenas } from "../manuscrito/Lector";
import { compararCapitulo, type ParrafoComparado } from "./comparar";
import { useLecturaActual } from "./MarcoLectura";
import { PanelCambio } from "./PanelCambio";

const miles = new Intl.NumberFormat("es-ES");
const ORNAMENTO = /^\*\s\*\s\*$/;

/** Un capítulo de la versión que se lee, con «qué cambió» y el cambio del lector (RF-FE-LEE-05, 07; RF-FE-CAM-01). */
export function CapituloLectura() {
  const { novelaId, version, numero, esUltima, enlace, cambio, guardarCambio } = useLecturaActual();
  const n = Number(useParams().n);
  const [busqueda, setBusqueda] = useSearchParams();
  const capitulo = version.capitulos.find((c) => c.numero === n);
  useTitulo(capitulo ? `Capítulo ${n} · ${version.titulo}` : `Sin capítulo ${n} · ${version.titulo}`);

  const puedeComparar = !!capitulo?.cambiado && (numero ?? 1) > 1;
  const comparando = puedeComparar && busqueda.get("cambios") === "1";
  const anteriorVersion = useQuery({ ...consultaVersion(novelaId, (numero ?? 1) - 1), enabled: comparando });

  // Cambio del lector: solo sobre la última versión, con la novela terminada y nada más generándose.
  const ejecucion = useQuery(consultaEjecucion(novelaId));
  const novelas = useQuery(consultaNovelas());
  const estado = comoEstadoEjecucion(ejecucion.data?.estado);
  const otraActiva = (novelas.data ?? []).some((x) => {
    const e = comoEstadoEjecucion(x.estado);
    return x.id !== novelaId && e !== null && ESTADOS_ACTIVOS.has(e);
  });
  const motivoNoPuede = !esUltima
    ? "Solo se pide sobre la última versión."
    : cambio && !cambio.terminado
      ? "Ya hay un cambio tuyo en marcha."
      : ejecucion.isPending || novelas.isPending
        ? "Comprobando el estado de la novela…"
        : estado !== "completada" && estado !== "completada_con_avisos"
          ? "La novela se está generando o no está terminada."
          : otraActiva
            ? "Hay otra novela generándose: el worker hace una cosa a la vez."
            : null;

  const articulo = useRef<HTMLElement>(null);
  const botonCambio = useRef<HTMLButtonElement>(null);
  const tituloCapitulo = useRef<HTMLHeadingElement>(null);
  const texto = useRef<HTMLDivElement>(null);
  const [seleccion, setSeleccion] = useState<{ texto: string; arriba: number; izquierda: number } | null>(null);
  const [panel, setPanel] = useState<{ cita: string | null } | null>(null);

  useEffect(() => {
    const alCambiar = () => {
      const sel = document.getSelection();
      const nodo = texto.current;
      if (!sel || sel.isCollapsed || sel.rangeCount === 0 || !nodo || !nodo.contains(sel.getRangeAt(0).commonAncestorContainer)) {
        setSeleccion(null);
        return;
      }
      const citado = sel.toString().replace(/\s+/g, " ").trim();
      if (!citado) {
        setSeleccion(null);
        return;
      }
      const rango = sel.getRangeAt(0);
      const caja = typeof rango.getBoundingClientRect === "function" ? rango.getBoundingClientRect() : { bottom: 0, left: 0 };
      const base = articulo.current?.getBoundingClientRect();
      setSeleccion({ texto: citado, arriba: caja.bottom - (base?.top ?? 0) + 8, izquierda: Math.max(0, caja.left - (base?.left ?? 0)) });
    };
    document.addEventListener("selectionchange", alCambiar);
    return () => document.removeEventListener("selectionchange", alCambiar);
  }, []);

  // Cambiar de capítulo cierra el panel.
  useEffect(() => setPanel(null), [n]);

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
  const abrir = (cita: string | null) => {
    setPanel({ cita });
    setSeleccion(null);
  };

  return (
    <article ref={articulo} className="libro capitulo" aria-labelledby="titulo-capitulo">
      <header className="capitulo__cabecera">
        <p className="capitulo__novela">{version.titulo}</p>
        <h1 id="titulo-capitulo" ref={tituloCapitulo} tabIndex={-1}>
          Capítulo {n}
        </h1>
        <p className="capitulo__meta">{miles.format(capitulo.palabras)} palabras</p>
        <div className="capitulo__herramientas">
          {puedeComparar && (
            <button type="button" className="boton boton--mini" aria-pressed={comparando} onClick={alternar}>
              {comparando ? "Ocultar los cambios" : `Ver qué cambió en la versión ${numero}`}
            </button>
          )}
          <button
            ref={botonCambio}
            type="button"
            className="boton boton--mini"
            disabled={motivoNoPuede !== null || panel !== null}
            aria-describedby={motivoNoPuede ? "motivo-no-cambio" : undefined}
            onClick={() => abrir(seleccion?.texto ?? null)}
          >
            Pedir un cambio
          </button>
        </div>
        {motivoNoPuede && (
          <p id="motivo-no-cambio" className="capitulo__motivo">
            {motivoNoPuede}
          </p>
        )}
      </header>

      {panel && (
        <PanelCambio
          novelaId={novelaId}
          capitulo={n}
          cita={panel.cita}
          version={version}
          alCerrar={() => {
            setPanel(null);
            // El foco vuelve a quien abrió el panel.
            requestAnimationFrame(() => botonCambio.current?.focus());
          }}
          alPedir={(intencionId, peticion) => {
            guardarCambio({ intencionId, versionBase: version.numero, peticion });
            setPanel(null);
            // El botón queda desactivado mientras dura el cambio: el foco va al capítulo.
            requestAnimationFrame(() => tituloCapitulo.current?.focus());
          }}
        />
      )}

      {seleccion && motivoNoPuede === null && !panel && !comparando && (
        <button
          type="button"
          className="boton boton--mini burbuja-cambio"
          style={{ top: seleccion.arriba, left: seleccion.izquierda }}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => abrir(seleccion.texto)}
        >
          Pedir un cambio
        </button>
      )}

      {comparando ? (
        <EstadoConsulta
          cargando={anteriorVersion.isPending}
          error={anteriorVersion.error}
          reintentar={() => void anteriorVersion.refetch()}
        >
          {anteriorVersion.data && (
            <Comparacion
              parrafos={compararCapitulo(anteriorVersion.data.capitulos.find((c) => c.numero === n)?.texto, capitulo.texto)}
              versionAnterior={(numero ?? 1) - 1}
            />
          )}
        </EstadoConsulta>
      ) : (
        <div ref={texto} className="capitulo__texto" data-capitulo={n}>
          {partirEnEscenas(capitulo.texto).map((parrafos, i) => (
            <section key={i} className="capitulo__escena" aria-label={`Escena ${i + 1}`}>
              {i > 0 && (
                <p className="capitulo__ornamento" aria-hidden="true">
                  * * *
                </p>
              )}
              {parrafos.map((p, j) => (
                <p key={j}>
                  <ConEnfasis texto={p} />
                </p>
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

/** Lo añadido y lo quitado, con color, subrayado o tachado, y una pista para lectores de pantalla. */
function Comparacion({ parrafos, versionAnterior }: { parrafos: ParrafoComparado[]; versionAnterior: number }) {
  const anadido = (t: ReactNode, k: number) => (
    <ins key={k}>
      <span className="solo-lectores">[añadido: </span>
      {t}
      <span className="solo-lectores">]</span>
    </ins>
  );
  const quitado = (t: ReactNode, k: number) => (
    <del key={k}>
      <span className="solo-lectores">[quitado: </span>
      {t}
      <span className="solo-lectores">]</span>
    </del>
  );
  return (
    <div className="capitulo__texto comparacion">
      <p className="comparacion__leyenda">
        Comparado con la versión {versionAnterior}: <ins>así lo añadido</ins> y <del>así lo quitado</del>.
      </p>
      {parrafos.map((p, i) => {
        const texto = p.trozos.map((t) => t.texto).join("");
        if (ORNAMENTO.test(texto.trim())) {
          // Un separador de escena añadido o quitado es una escena nueva o eliminada: también se marca.
          if (p.tipo === "igual") {
            return (
              <p key={i} className="capitulo__ornamento" aria-hidden="true">
                * * *
              </p>
            );
          }
          return (
            <p key={i} className="capitulo__ornamento" data-cambio={p.tipo}>
              {p.tipo === "quitado" ? quitado("* * *", 0) : anadido("* * *", 0)}
              <span className="solo-lectores">{p.tipo === "quitado" ? " (se quitó un cambio de escena)" : " (escena nueva)"}</span>
            </p>
          );
        }
        return (
          <p key={i} data-cambio={p.tipo === "igual" ? undefined : p.tipo}>
            {trozosConEnfasis(p.trozos, (t, contenido, j) =>
              t.tipo === "nuevo" ? anadido(contenido, j) : t.tipo === "quitado" ? quitado(contenido, j) : <span key={j}>{contenido}</span>,
            )}
          </p>
        );
      })}
    </div>
  );
}
