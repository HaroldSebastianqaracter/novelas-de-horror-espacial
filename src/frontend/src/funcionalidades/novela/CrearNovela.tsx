import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { analisisDeError, INTENSIDADES } from "../../compartido/api/brief";
import { motivoLegible, useIntenciones } from "../../compartido/api/intenciones";
import { DIBUJOS } from "../../compartido/imagenes";
import { Dibujo } from "../../compartido/ui/Dibujo";
import {
  aBrief,
  type Borrador,
  borradorVacio,
  borrarBorrador,
  type Errores,
  erroresDeForma,
  erroresDelAnalisis,
  guardarBorrador,
  leerBorrador,
  PASOS,
  pasoDe,
  primerPasoConErrores,
} from "./borrador";
import {
  ETIQUETA_INTENSIDAD,
  ETIQUETA_OCASION,
  ETIQUETA_PRONOMBRES,
  ETIQUETA_SUBGENERO,
  ETIQUETA_TONO,
  PasoDestinatario,
  PasoEncargo,
  PasoMundo,
  PasoTerror,
} from "./PasosBrief";
import "./CrearNovela.css";

// La pieza 3D es decorativa: se carga aparte y solo en pantallas anchas (RF-FE-BRF-06).
const AmbienteEstacion = lazy(() => import("./AmbienteEstacion"));
const pantallaAncha = () => typeof window.matchMedia === "function" && window.matchMedia("(min-width: 768px)").matches;

type Envio = { fase: "editando" } | { fase: "enviando" } | { fase: "esperando" };

/** Crear novela desde un brief (RF-FE-BRF). */
export function CrearNovela() {
  const [borrador, setBorrador] = useState<Borrador>(leerBorrador);
  const [paso, setPaso] = useState(0);
  const [errores, setErrores] = useState<Errores>({});
  const [envio, setEnvio] = useState<Envio>({ fase: "editando" });
  const [errorEnvio, setErrorEnvio] = useState<string | null>(null);
  const [conAmbiente] = useState(pantallaAncha);
  const { pedir } = useIntenciones();
  const navegar = useNavigate();
  const tituloPaso = useRef<HTMLHeadingElement>(null);
  const pasoAnterior = useRef(paso);

  useEffect(() => guardarBorrador(borrador), [borrador]);
  useEffect(() => {
    // Al cambiar de paso, el foco va a su título; al cargar, no se mueve.
    if (pasoAnterior.current !== paso) tituloPaso.current?.focus();
    pasoAnterior.current = paso;
  }, [paso]);

  const actualizar = (cambios: Partial<Borrador>) => setBorrador((b) => ({ ...b, ...cambios }));
  const irA = (n: number) => setPaso(Math.max(0, Math.min(PASOS.length - 1, n)));

  const enviar = () => {
    setErrorEnvio(null);
    const forma = erroresDeForma(borrador);
    if (Object.keys(forma).length > 0) {
      setErrores(forma);
      irA(primerPasoConErrores(forma) ?? paso);
      return;
    }
    setErrores({});
    setEnvio({ fase: "enviando" });
    pedir(
      { tipo: "crear_novela", payload: { brief: aBrief(borrador) } },
      {
        alTerminar: (intencion) => {
          const novelaId = (intencion.resultado as { novela_id?: unknown } | null)?.novela_id;
          if (intencion.estado === "hecha" && typeof novelaId === "number") {
            borrarBorrador();
            void navegar(`/novelas/${novelaId}`);
            return;
          }
          setErrorEnvio(motivoLegible(intencion.motivo, intencion.estado));
          setEnvio({ fase: "editando" });
        },
      },
    )
      .then(() => setEnvio({ fase: "esperando" }))
      .catch((e: unknown) => {
        setEnvio({ fase: "editando" });
        const analisis = analisisDeError(e);
        if (analisis) {
          // Qué falta y qué se contradice lo dice la API; el formulario lo lleva a cada campo.
          const delServidor = erroresDelAnalisis(analisis);
          setErrores(delServidor);
          irA(primerPasoConErrores(delServidor) ?? PASOS.length - 1);
          return;
        }
        setErrorEnvio(`No se pudo enviar: ${(e as Error).message}`);
      });
  };

  const bloqueado = envio.fase !== "editando";
  const erroresPorPaso = PASOS.map((_, i) => Object.keys(errores).filter((c) => pasoDe(c) === i).length);
  const propsPaso = { borrador, actualizar, errores };

  return (
    <div className="crear">
      <section className="pantalla crear__formulario" aria-labelledby="titulo-crear">
        <nav className="migas" aria-label="Ruta">
          <Link to="/">Tablero</Link>
          <span aria-hidden="true">/</span>
          <span aria-current="page">Nueva novela</span>
        </nav>
        <header className="crear__cabecera">
          <Dibujo src={DIBUJOS.crearNovela} className="dibujo--crear" />
          <h1 id="titulo-crear">Nueva novela</h1>
          <p className="intro">
            Un terror espacial a medida: quien la recibe es el protagonista. Al crearla queda <strong>En espera</strong> hasta
            que la arranques. El título lo propone el arquitecto.
          </p>
        </header>

        <ol className="pasos-brief" aria-label="Pasos del brief">
          {PASOS.map((nombre, i) => (
            <li key={nombre}>
              <button
                type="button"
                className="paso-brief"
                aria-current={i === paso ? "step" : undefined}
                data-error={erroresPorPaso[i] ? true : undefined}
                onClick={() => irA(i)}
              >
                <span className="paso-brief__num" aria-hidden="true">
                  {i + 1}
                </span>
                <span>
                  <span className="solo-lectores">Paso {i + 1}:</span> {nombre}
                  {erroresPorPaso[i] ? <span className="solo-lectores">, con errores</span> : null}
                </span>
              </button>
            </li>
          ))}
        </ol>

        {Object.keys(errores).length > 0 && (
          <div className="resumen-errores" role="alert">
            <p>
              <strong>Hay que revisar el brief antes de enviarlo.</strong>
            </p>
            <ul>
              {porMensaje(errores).map(([mensaje, pasos]) => (
                <li key={mensaje}>
                  {pasos.map((p, i) => (
                    <span key={p}>
                      {i > 0 && ", "}
                      <button type="button" className="enlace" onClick={() => irA(p)}>
                        {PASOS[p]}
                      </button>
                    </span>
                  ))}
                  : {mensaje}
                </li>
              ))}
            </ul>
          </div>
        )}

        <form
          className="brief"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            if (paso < PASOS.length - 1) irA(paso + 1);
            else enviar();
          }}
        >
          <fieldset className="brief__cuerpo" disabled={bloqueado}>
            <legend className="solo-lectores">{PASOS[paso]}</legend>
            <h2 className="brief__titulo" ref={tituloPaso} tabIndex={-1}>
              {paso + 1} · {PASOS[paso]}
            </h2>
            {paso === 0 && <PasoDestinatario {...propsPaso} />}
            {paso === 1 && <PasoMundo {...propsPaso} />}
            {paso === 2 && <PasoEncargo {...propsPaso} />}
            {paso === 3 && <PasoTerror {...propsPaso} />}
            {paso === 4 && <Revision borrador={borrador} />}
          </fieldset>
          <div className="form__acciones">
            <button
              type="button"
              className="boton boton--fantasma"
              disabled={bloqueado}
              onClick={() => {
                setBorrador(borradorVacio());
                setErrores({});
                irA(0);
              }}
            >
              Empezar de cero
            </button>
            {paso > 0 && (
              <button type="button" className="boton" disabled={bloqueado} onClick={() => irA(paso - 1)}>
                Anterior
              </button>
            )}
            <button type="submit" className="boton boton--primario" disabled={bloqueado}>
              {paso < PASOS.length - 1 ? "Siguiente" : "Crear novela"}
            </button>
          </div>
        </form>

        {envio.fase !== "editando" && (
          <p className="consola-envio" role="status">
            <span className="cursor" aria-hidden="true" />
            {envio.fase === "enviando" ? "Enviando el brief…" : "Intención recibida, esperando asignación del worker…"}
          </p>
        )}
        {errorEnvio && (
          <p className="aviso aviso--error" role="alert">
            {errorEnvio}
          </p>
        )}
      </section>

      {conAmbiente && (
        <aside className="crear__ambiente" aria-hidden="true">
          <Suspense fallback={<div className="ambiente" />}>
            <AmbienteEstacion />
          </Suspense>
          <p className="ambiente__pie">
            <span>Vista orbital · estación de referencia</span>
            <span>Decorativo</span>
          </p>
        </aside>
      )}
    </div>
  );
}

/** Un mismo mensaje puede venir en varios campos (una contradicción nombra dos): se agrupa por mensaje. */
function porMensaje(errores: Errores): [string, number[]][] {
  const grupos = new Map<string, Set<number>>();
  for (const [campo, mensajes] of Object.entries(errores)) {
    for (const m of mensajes) (grupos.get(m) ?? grupos.set(m, new Set()).get(m))?.add(pasoDe(campo));
  }
  return [...grupos].map(([m, pasos]) => [m, [...pasos].sort()]);
}

/** Paso 5: todo el encargo, legible, antes de enviarlo. */
function Revision({ borrador }: { borrador: Borrador }) {
  const b = aBrief(borrador);
  const d = b.destinatario;
  const fila = (clave: string, valor: string | undefined) => (
    <div key={clave}>
      <dt>{clave}</dt>
      <dd>{valor || <span className="brief__vacio">Sin rellenar</span>}</dd>
    </div>
  );
  const elementos = (xs: { texto: string; obligatorio: boolean }[]) =>
    xs.length ? xs.map((e) => `${e.texto}${e.obligatorio ? "" : " (opcional)"}`).join(" · ") : undefined;
  return (
    <div className="revision">
      <p className="campo__pista">Revisa el encargo. Qué falta o se contradice lo comprueba el servidor al enviarlo.</p>
      <dl className="revision__lista">
        {fila("Destinatario", d.nombre)}
        {fila("Edad", d.edad !== undefined ? `${d.edad} años` : undefined)}
        {fila("Pronombres", d.pronombres ? ETIQUETA_PRONOMBRES[d.pronombres] : undefined)}
        {fila("Rasgos", elementos(d.rasgos))}
        {fila("Recuerdos", elementos(b.recuerdos))}
        {fila(
          "Allegados",
          b.allegados.length
            ? b.allegados.map((a) => `${a.nombre} (${a.relacion}${a.rasgos.length ? `: ${a.rasgos.join(", ")}` : ""})`).join(" · ")
            : "Ninguno",
        )}
        {fila("Ocasión", b.ocasion ? `${ETIQUETA_OCASION[b.ocasion]}${b.ocasion_detalle ? `: ${b.ocasion_detalle}` : ""}` : undefined)}
        {fila("Quién regala", b.quien_regala)}
        {fila("Dedicatoria", b.mensaje_dedicatoria ?? "Sin mensaje")}
        {fila(
          "Intensidad",
          b.intensidad ? `${ETIQUETA_INTENSIDAD[b.intensidad]} (desde ${INTENSIDADES[b.intensidad].edadMinima} años)` : undefined,
        )}
        {fila("Tono", b.tono ? ETIQUETA_TONO[b.tono][0] : undefined)}
        {fila("Subgénero", b.subgenero ? ETIQUETA_SUBGENERO[b.subgenero] : "Lo elige el arquitecto")}
        {fila("Capítulos", String(b.capitulos))}
        {fila("Vetados", b.vetados.length ? b.vetados.join(", ") : "Ninguno")}
      </dl>
    </div>
  );
}
