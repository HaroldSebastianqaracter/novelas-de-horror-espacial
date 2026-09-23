import { useQuery } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Link, useParams } from "react-router";
import { consultaEjecucion, consultaEstructura, consultaNovela, consultaNovelas } from "../../compartido/api/consultas";
import { type Enlace, useEventosNovela } from "../../compartido/api/eventos";
import { useIntenciones } from "../../compartido/api/intenciones";
import {
  comoEstadoEjecucion,
  comoFase,
  type EstadoEjecucion,
  ESTADOS_ACTIVOS,
  ESTADOS_QUE_ADMITEN_ARRANCAR,
  ESTADOS_QUE_ADMITEN_RELANZAR,
  type Fase,
} from "../../compartido/api/reglas";
import type { Capitulo, Ejecucion, NovelaDetalle } from "../../compartido/api/tipos";
import { ChipEstado } from "../../compartido/ui/ChipEstado";
import { EstadoConsulta } from "../../compartido/ui/EstadoConsulta";
import { Hace } from "../../compartido/ui/Hace";
import { Progreso } from "../../compartido/ui/Progreso";
import { ETIQUETA_FASE } from "../../compartido/ui/vocabulario";
import { MOTIVO_OTRA_ACTIVA } from "./acciones";
import { ETIQUETA_INTENCION } from "./Tarjeta";
import "./TableroGeneral.css";
import "./TableroNovela.css";

const FASES_PLAN: readonly Fase[] = ["arquitecto", "mundo", "elenco", "estructura", "puerta_1", "escaleta", "puerta_2"];
const FASES_CAP: readonly Fase[] = ["paquete", "redaccion", "extraccion", "puerta_3", "puerta_4"];

type EstadoPaso = "hecho" | "activo" | "pendiente" | "detenido" | "parada" | "error";
const TEXTO_PASO: Record<EstadoPaso, string> = {
  hecho: "Hecho",
  activo: "En curso",
  pendiente: "Pendiente",
  detenido: "Detenido aquí",
  parada: "Parada",
  error: "Error",
};

/** Estado de un paso de una secuencia, dada la posición del paso en curso y el estado de la ejecución. */
function estadoPaso(i: number, actual: number, estado: EstadoEjecucion | null): EstadoPaso {
  if (actual < 0 || i > actual) return "pendiente";
  if (i < actual) return "hecho";
  if (estado && ESTADOS_ACTIVOS.has(estado)) return "activo";
  if (estado === "detenida") return "detenido";
  if (estado === "parada" || estado === "error") return estado;
  return "pendiente";
}

const dos = (n: number) => String(n).padStart(2, "0");

/** Tablero de una novela (RF-FE-NOV). */
export function TableroNovela() {
  const id = Number(useParams().id);
  const detalle = useQuery(consultaNovela(id));
  const ejecucion = useQuery(consultaEjecucion(id));
  const estructura = useQuery(consultaEstructura(id));
  const enlace = useEventosNovela(id);

  const cargando = detalle.isPending || ejecucion.isPending;
  const error = detalle.error ?? ejecucion.error;

  return (
    <section className="pantalla pantalla--novela">
      <nav className="migas" aria-label="Ruta">
        <Link to="/">Tablero</Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page">N-{String(id).padStart(4, "0")}</span>
      </nav>
      <BannerEnlace enlace={enlace} />
      <EstadoConsulta
        cargando={cargando}
        error={error}
        reintentar={() => {
          void detalle.refetch();
          void ejecucion.refetch();
        }}
      >
        {detalle.data && ejecucion.data && (
          <Contenido detalle={detalle.data} ejecucion={ejecucion.data} capitulos={estructura.data?.capitulos ?? []} />
        )}
      </EstadoConsulta>
    </section>
  );
}

function BannerEnlace({ enlace }: { enlace: Enlace }) {
  if (enlace !== "perdido") return null;
  return (
    <p className="banner-enlace" role="status">
      <span className="baliza" aria-hidden="true" />
      <strong>Enlace perdido.</strong> Reintentando; al volver se reconsulta todo. Lo que ves puede estar desfasado.
    </p>
  );
}

interface PropsContenido {
  detalle: NovelaDetalle;
  ejecucion: Ejecucion;
  capitulos: Capitulo[];
}

function Contenido({ detalle, ejecucion, capitulos }: PropsContenido) {
  const { novela } = detalle;
  const estado = comoEstadoEjecucion(ejecucion.estado);
  const fase = comoFase(ejecucion.fase);
  const enPlanificacion = capitulos.length === 0 || (fase !== null && FASES_PLAN.includes(fase));

  return (
    <>
      <Cabecera detalle={detalle} ejecucion={ejecucion} capitulos={capitulos} />
      {estado === "parada" && ejecucion.parada_abierta_id && (
        <Link className="franja-alerta" to={`/novelas/${novela.id}/paradas/${ejecucion.parada_abierta_id}`}>
          <span className="baliza baliza--alerta" aria-hidden="true" />
          <strong>Parada P-{ejecucion.parada_abierta_id} · la ejecución espera tu decisión</strong>
          <span>Abrir informe →</span>
        </Link>
      )}
      {estado === "error" && (
        <section className="bloque-error" aria-labelledby="titulo-error">
          <h2 id="titulo-error">
            <span aria-hidden="true">✕</span> Error de ejecución
          </h2>
          <pre className="bloque-error__texto">{ejecucion.ultimo_error ?? "Sin detalle del error."}</pre>
          <p>La ejecución no seguirá sola. Arráncala para reintentar o relanza desde un capítulo.</p>
        </section>
      )}
      {estado === "completada_con_avisos" && (
        <section className="bloque-avisos" aria-labelledby="titulo-avisos">
          <h2 id="titulo-avisos">
            <span aria-hidden="true">▲</span> Completada con avisos
          </h2>
          <p>La novela pasó todas las puertas. Los avisos no bloquearon la generación, pero conviene revisarlos.</p>
        </section>
      )}
      {enPlanificacion ? (
        <Planificacion fase={fase} estado={estado} />
      ) : (
        <Generacion novelaId={novela.id} ejecucion={ejecucion} capitulos={capitulos} />
      )}
      <Ficha detalle={detalle} />
    </>
  );
}

function IntentoPips({ intento }: { intento: number }) {
  return (
    <span className="intento" aria-label={`Intento ${intento} de 3`}>
      <span className="intento__pips" aria-hidden="true">
        {[1, 2, 3].map((k) => (
          <i key={k} data-on={k <= intento ? true : undefined} />
        ))}
      </span>
      Intento {intento}/3
    </span>
  );
}

function Cabecera({ detalle, ejecucion, capitulos }: PropsContenido) {
  const { novela } = detalle;
  const estado = comoEstadoEjecucion(ejecucion.estado);
  const fase = comoFase(ejecucion.fase);
  const { pendientes, rechazos, pedir, descartarRechazo } = useIntenciones();
  const novelas = useQuery(consultaNovelas());
  const [relanzando, setRelanzando] = useState(false);
  const [errorPedir, setErrorPedir] = useState<string | null>(null);

  const pendiente = pendientes.find((p) => p.novelaId === novela.id);
  const rechazo = rechazos[novela.id];
  const otraActiva = (novelas.data ?? []).some((n) => {
    const e = comoEstadoEjecucion(n.estado);
    return n.id !== novela.id && e !== null && ESTADOS_ACTIVOS.has(e);
  });
  const puedeArrancar = estado !== null && ESTADOS_QUE_ADMITEN_ARRANCAR.has(estado);
  const puedeParar = estado !== null && ESTADOS_ACTIVOS.has(estado);
  const puedeRelanzar = estado !== null && ESTADOS_QUE_ADMITEN_RELANZAR.has(estado) && capitulos.length > 0;
  const conIntento = estado !== null && (ESTADOS_ACTIVOS.has(estado) || estado === "parada" || estado === "error");

  const pedirIntencion = (tipo: "arrancar" | "parar" | "relanzar", payload: Record<string, unknown> = {}) => {
    setErrorPedir(null);
    pedir({ tipo, novela_id: novela.id, payload }).catch((e: unknown) =>
      setErrorPedir(`No se pudo pedir «${ETIQUETA_INTENCION[tipo]}»: ${(e as Error).message}`),
    );
  };

  return (
    <header className="novela-cabecera" data-estado={ejecucion.estado}>
      <div>
        <p className="etiqueta">
          N-{String(novela.id).padStart(4, "0")} · terror espacial
          {novela.subgenero_dominante ? ` · ${novela.subgenero_dominante.replaceAll("_", " ")}` : ""}
        </p>
        <h1>{novela.titulo || "Sin título"}</h1>
        {novela.logline && <p className="novela-cabecera__logline">{novela.logline}</p>}
      </div>
      <dl className="telemetria">
        <div>
          <dt>Estado</dt>
          <dd>
            <ChipEstado estado={ejecucion.estado} /> <code className="codigo-estado">{ejecucion.estado}</code>
          </dd>
        </div>
        <div>
          <dt>Fase</dt>
          <dd data-fase={ejecucion.fase ?? undefined}>{fase ? ETIQUETA_FASE[fase] : (ejecucion.fase ?? "—")}</dd>
        </div>
        <div>
          <dt>Capítulo</dt>
          <dd>{ejecucion.capitulo_actual ? dos(ejecucion.capitulo_actual) : "—"}</dd>
        </div>
        <div>
          <dt>Intento</dt>
          <dd>{conIntento ? <IntentoPips intento={ejecucion.intento_actual ?? 1} /> : "—"}</dd>
        </div>
        <div>
          <dt>Progreso</dt>
          <dd>
            <Progreso completados={ejecucion.capitulos_completados ?? 0} total={ejecucion.total_capitulos ?? 0} />
          </dd>
        </div>
        <div>
          <dt>Actualizado</dt>
          <dd>
            <Hace iso={ejecucion.actualizado_en} />
          </dd>
        </div>
      </dl>
      <div className="acciones" role="group" aria-label="Intenciones sobre la ejecución">
        <button
          type="button"
          className="boton"
          disabled={!puedeArrancar || otraActiva || pendiente !== undefined}
          title={puedeArrancar && otraActiva ? MOTIVO_OTRA_ACTIVA : undefined}
          onClick={() => pedirIntencion("arrancar")}
        >
          <span aria-hidden="true">▶</span> {estado === "error" ? "Reintentar" : "Arrancar"}
        </button>
        <button
          type="button"
          className="boton"
          disabled={!puedeParar || pendiente !== undefined}
          onClick={() => pedirIntencion("parar")}
        >
          <span aria-hidden="true">‖</span> Parar
        </button>
        <button
          type="button"
          className="boton"
          disabled={!puedeRelanzar || pendiente !== undefined}
          aria-expanded={relanzando}
          onClick={() => setRelanzando((r) => !r)}
        >
          <span aria-hidden="true">↻</span> Relanzar…
        </button>
        <p className="acciones__nota" role="status">
          {pendiente ? (
            <>
              <span className="cursor" aria-hidden="true" />
              {ETIQUETA_INTENCION[pendiente.tipo]} en cola · esperando confirmación
            </>
          ) : puedeArrancar && otraActiva ? (
            MOTIVO_OTRA_ACTIVA
          ) : null}
        </p>
        {relanzando && (
          <FormRelanzar
            capitulos={capitulos}
            sugerido={ejecucion.capitulo_actual ?? Math.min((ejecucion.capitulos_completados ?? 0) + 1, capitulos.length)}
            alCancelar={() => setRelanzando(false)}
            alConfirmar={(desde) => {
              setRelanzando(false);
              pedirIntencion("relanzar", { desde_capitulo: desde });
            }}
          />
        )}
        {rechazo && (
          <div className="acciones__rechazo" role="alert">
            <strong>{ETIQUETA_INTENCION[rechazo.tipo]}: rechazada.</strong> {rechazo.motivo}{" "}
            <button type="button" className="boton boton--mini" onClick={() => descartarRechazo(novela.id)}>
              Entendido
            </button>
          </div>
        )}
        {errorPedir && (
          <p className="acciones__rechazo" role="alert">
            {errorPedir}
          </p>
        )}
      </div>
    </header>
  );
}

function FormRelanzar({
  capitulos,
  sugerido,
  alCancelar,
  alConfirmar,
}: {
  capitulos: Capitulo[];
  sugerido: number;
  alCancelar: () => void;
  alConfirmar: (desde: number) => void;
}) {
  const [desde, setDesde] = useState(Math.max(1, sugerido));
  const posteriores = capitulos.filter((c) => c.numero >= desde && c.estado === "completado").length;
  const enviar = (evento: FormEvent) => {
    evento.preventDefault();
    alConfirmar(desde);
  };
  return (
    <form className="relanzar" onSubmit={enviar}>
      <label>
        Desde el capítulo{" "}
        <select value={desde} onChange={(e) => setDesde(Number(e.target.value))}>
          {capitulos.map((c) => (
            <option key={c.numero} value={c.numero}>
              {dos(c.numero)}
            </option>
          ))}
        </select>
      </label>
      <p className="relanzar__consecuencia">
        {posteriores > 0
          ? `Se rehacen ${posteriores} capítulo${posteriores === 1 ? "" : "s"} ya cerrado${posteriores === 1 ? "" : "s"}, del ${dos(desde)} en adelante.`
          : `Se sigue desde el capítulo ${dos(desde)}; no se rehace ninguno cerrado.`}
      </p>
      <button type="submit" className="boton boton--primario">
        Relanzar
      </button>
      <button type="button" className="boton" onClick={alCancelar}>
        Cancelar
      </button>
    </form>
  );
}

/** Barra de pasos mientras no hay capítulos (RF-FE-NOV-02). */
function Planificacion({ fase, estado }: { fase: Fase | null; estado: EstadoEjecucion | null }) {
  const actual = fase ? FASES_PLAN.indexOf(fase) : -1;
  return (
    <section className="momento" aria-labelledby="titulo-plan">
      <header className="momento__cabecera">
        <h2 id="titulo-plan">Planificación</h2>
        <p>Aún no hay capítulos: el total se fija al cerrar la estructura.</p>
      </header>
      <ol className="pasos" aria-label="Pasos de la planificación">
        {FASES_PLAN.map((f, i) => {
          const paso = estadoPaso(i, actual, estado);
          return (
            <li key={f} className="paso" data-fase={f} data-paso={paso} aria-current={paso === "activo" ? "step" : undefined}>
              <span className="paso__num">{dos(i + 1)}</span>
              <span className="paso__nombre">{ETIQUETA_FASE[f]}</span>
              <span className="paso__estado">{TEXTO_PASO[paso]}</span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

/** Capítulos en Pendiente → En curso → Cerrado (RF-FE-NOV-03). */
function Generacion({ novelaId, ejecucion, capitulos }: { novelaId: number; ejecucion: Ejecucion; capitulos: Capitulo[] }) {
  const estado = comoEstadoEjecucion(ejecucion.estado);
  const fase = comoFase(ejecucion.fase);
  const total = ejecucion.total_capitulos || capitulos.length;
  const actual = ejecucion.capitulo_actual;
  const enCurso = capitulos.find((c) => c.numero === actual && c.estado !== "completado");
  const revisionFinal = fase === "puerta_5" && estado !== "completada" && estado !== "completada_con_avisos";
  const pendientes = capitulos.filter((c) => c.estado !== "completado" && c.numero !== enCurso?.numero);
  const cerrados = capitulos.filter((c) => c.estado === "completado").sort((a, b) => b.numero - a.numero);

  return (
    <section className="momento" aria-labelledby="titulo-generacion">
      <header className="momento__cabecera">
        <h2 id="titulo-generacion">Generación</h2>
        <p>Un capítulo existe para el lector solo cuando supera la puerta 4. Solo uno en curso.</p>
      </header>
      <div className="tablero-caps">
        <section className="col-cap" data-col="pendiente" aria-labelledby="titulo-pendiente">
          <h3 id="titulo-pendiente">
            Pendiente <span className="cuenta">{pendientes.length}</span>
          </h3>
          {pendientes.length > 0 ? (
            <ol className="caps-pendientes">
              {pendientes.map((c) => (
                <li key={c.numero} title={c.objetivo ?? undefined}>
                  <span className="solo-lectores">Capítulo </span>
                  {dos(c.numero)}
                </li>
              ))}
            </ol>
          ) : (
            <p className="columna__vacio">Nada pendiente.</p>
          )}
        </section>

        <section className="col-cap" data-col="en_curso" aria-labelledby="titulo-en-curso">
          <h3 id="titulo-en-curso">
            En curso <span className="cuenta">{enCurso || revisionFinal ? 1 : 0}</span>
          </h3>
          {revisionFinal ? (
            <div className="cap-curso" data-estado={ejecucion.estado}>
              <p className="etiqueta">Revisión final</p>
              <h4>Puerta 5 · novela completa</h4>
              <p className="cap-curso__nota">Todos los capítulos están cerrados. Se revisa la novela entera.</p>
            </div>
          ) : enCurso ? (
            <CapituloEnCurso novelaId={novelaId} capitulo={enCurso} total={total} ejecucion={ejecucion} />
          ) : (
            <p className="columna__vacio">
              {estado === "completada" || estado === "completada_con_avisos"
                ? "Todos los capítulos cerrados."
                : "Ningún capítulo en curso."}
            </p>
          )}
        </section>

        <section className="col-cap" data-col="cerrado" aria-labelledby="titulo-cerrado">
          <h3 id="titulo-cerrado">
            Cerrado <span className="cuenta">{cerrados.length}</span>
          </h3>
          {cerrados.length > 0 ? (
            <ol className="caps-cerrados">
              {cerrados.map((c) => (
                <li key={c.numero} className="cap-cerrado">
                  <Link to={`/novelas/${novelaId}/capitulos/${c.numero}`}>
                    <span className="codigo">CAP {dos(c.numero)}</span>
                    <span className="cap-cerrado__titulo">Capítulo {c.numero}</span>
                    {c.objetivo && <span className="cap-cerrado__meta">{c.objetivo}</span>}
                  </Link>
                </li>
              ))}
            </ol>
          ) : (
            <p className="columna__vacio">Ningún capítulo cerrado.</p>
          )}
        </section>
      </div>
    </section>
  );
}

function CapituloEnCurso({
  novelaId,
  capitulo,
  total,
  ejecucion,
}: {
  novelaId: number;
  capitulo: Capitulo;
  total: number;
  ejecucion: Ejecucion;
}) {
  const estado = comoEstadoEjecucion(ejecucion.estado);
  const fase = comoFase(ejecucion.fase);
  const actual = fase ? FASES_CAP.indexOf(fase) : -1;
  return (
    <div className="cap-curso" data-estado={ejecucion.estado} data-fase={ejecucion.fase ?? undefined}>
      <div className="tarjeta__fila">
        <span className="codigo">
          CAP {dos(capitulo.numero)} / {dos(total)}
        </span>
        <IntentoPips intento={ejecucion.intento_actual ?? 1} />
      </div>
      <h4>Capítulo {capitulo.numero}</h4>
      {capitulo.objetivo && <p className="cap-curso__objetivo">{capitulo.objetivo}</p>}
      <p className="cap-curso__nota">Sin texto visible hasta superar la puerta 4.</p>
      <ol className="subfases" aria-label="Subfase del capítulo">
        {FASES_CAP.map((f, i) => {
          const paso = estadoPaso(i, actual, estado);
          return (
            <li key={f} data-fase={f} data-paso={paso} aria-current={paso === "activo" ? "step" : undefined}>
              <span className="subfase__marca" aria-hidden="true" />
              {ETIQUETA_FASE[f]}
              <span className="solo-lectores">: {TEXTO_PASO[paso]}</span>
            </li>
          );
        })}
      </ol>
      {estado === "parada" && ejecucion.parada_abierta_id && (
        <p className="cap-curso__estado">
          <Link to={`/novelas/${novelaId}/paradas/${ejecucion.parada_abierta_id}`}>
            ■ Parada P-{ejecucion.parada_abierta_id} · abrir informe
          </Link>
        </p>
      )}
      {estado === "detenida" && <p className="cap-curso__estado">Detenido en esta fase</p>}
      {estado === "error" && <p className="cap-curso__estado">Error en esta fase</p>}
    </div>
  );
}

const ETIQUETA_RESTRICCION: Record<string, string> = {
  longitud_objetivo_palabras: "Longitud objetivo",
  longitud_capitulo_palabras: "Palabras por capítulo",
  capitulos: "Capítulos",
  publico: "Público",
  politica_contenido: "Política de contenido",
  pov_por_defecto: "Punto de vista",
  tiempo_verbal: "Tiempo verbal",
};

/** Parámetros con los que se creó la novela y lo que el arquitecto ya fijó. */
function Ficha({ detalle }: { detalle: NovelaDetalle }) {
  const { novela, restricciones } = detalle;
  const filas: [string, string][] = [
    ...Object.entries(restricciones ?? {}).map(
      ([clave, valor]) => [ETIQUETA_RESTRICCION[clave] ?? clave, String(valor)] as [string, string],
    ),
    ...(novela.premisa ? ([["Premisa", novela.premisa]] as [string, string][]) : []),
    ...(novela.tema_central ? ([["Tema central", novela.tema_central]] as [string, string][]) : []),
    ...(novela.pregunta_dramatica ? ([["Pregunta dramática", novela.pregunta_dramatica]] as [string, string][]) : []),
  ];
  if (filas.length === 0) return null;
  return (
    <details className="ficha">
      <summary>Parámetros de la novela</summary>
      <dl className="ficha__lista">
        {filas.map(([clave, valor]) => (
          <div key={clave} className={valor.length > 60 ? "ficha__ancho" : undefined}>
            <dt>{clave}</dt>
            <dd>{valor}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}
