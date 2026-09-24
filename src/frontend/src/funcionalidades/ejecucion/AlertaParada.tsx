import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { consultaEstructura, consultaNovela, consultaParada } from "../../compartido/api/consultas";
import { useIntenciones } from "../../compartido/api/intenciones";
import { DIBUJOS } from "../../compartido/imagenes";
import { Dibujo } from "../../compartido/ui/Dibujo";
import { type AccionParada, ACCIONES_POR_TIPO_DE_PARADA, comoTipoParada, type TipoParada } from "../../compartido/api/reglas";
import type { Parada } from "../../compartido/api/tipos";
import { EstadoConsulta } from "../../compartido/ui/EstadoConsulta";
import { Hace } from "../../compartido/ui/Hace";
import { InformeParada, legible } from "./InformeParada";
import "./TableroNovela.css";
import "./AlertaParada.css";

const NOMBRE_ACCION: Record<AccionParada, string> = {
  rehacer: "Rehacer",
  relanzar: "Relanzar",
  aceptar_retcon: "Aceptar retcon",
  dar_por_sabido: "Dar por sabido",
};

const RESOLUCION: Record<string, string> = {
  aceptar_retcon: "Se aceptó el retcon",
  dar_por_sabido: "Se dio por sabido",
  relanzado: "Se relanzó",
  rehecho: "Se rehízo la fase",
};

/** Qué pasa si se elige cada acción, según el tipo de parada (RF2-FALLO-03). */
function consecuencia(accion: AccionParada, tipo: TipoParada, desde: number): string {
  switch (accion) {
    case "rehacer":
      return tipo === "estructura"
        ? "Borra actos, hilos, siembras de la estructura y objetos, y el estructurador vuelve a correr con este informe. La puerta 1 se reevalúa."
        : "Borra capítulos, secuencias y escenas planificados, y el escaletador vuelve a correr con este informe. La puerta 2 se reevalúa.";
    case "relanzar":
      return `Revierte lo escrito desde el capítulo ${desde} y lo vuelve a generar. La prosa rechazada no se reutiliza.`;
    case "aceptar_retcon":
      return "El texto manda: el hecho establecido se retira con rastro de retcon y el capítulo se regenera con el canon corregido.";
    case "dar_por_sabido":
      return "El personaje se enteró fuera de escena: queda registrado que lo sabe al final del capítulo anterior, y el capítulo se regenera.";
  }
}

/** Aviso, sin bloquear, cuando el worker va a rechazar la acción (RF-FE-PAR-04). */
function avisoDe(accion: AccionParada, parada: Parada): string | null {
  const conflictos = Array.isArray(parada.informe?.conflictos)
    ? (parada.informe.conflictos as Record<string, unknown>[])
    : [];
  if (accion === "aceptar_retcon") {
    const conPrevio = conflictos.some((c) => {
      const datos = c.datos as Record<string, unknown> | undefined;
      return datos?.hecho_previo_id != null;
    });
    return conPrevio ? null : "Ningún conflicto señala un hecho establecido que revocar: el worker lo rechazará.";
  }
  if (accion === "dar_por_sabido") {
    const deConocimiento = conflictos.some((c) => c.comprobacion === "conocimiento_no_adquirido");
    return deConocimiento ? null : "Ningún conflicto es de conocimiento no adquirido: el worker lo rechazará.";
  }
  return null;
}

/** Alerta de parada (RF-FE-PAR). */
export function AlertaParada() {
  const params = useParams();
  const novelaId = Number(params.id);
  const paradaId = Number(params.pid);
  const parada = useQuery(consultaParada(novelaId, paradaId));
  const detalle = useQuery(consultaNovela(novelaId));
  const codigo = `N-${String(novelaId).padStart(4, "0")}`;

  return (
    <section className="pantalla alerta-parada" aria-labelledby="titulo-parada">
      <nav className="migas" aria-label="Ruta">
        <Link to="/">Tablero</Link>
        <span aria-hidden="true">/</span>
        <Link to={`/novelas/${novelaId}`}>{codigo}</Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page">P-{paradaId}</span>
      </nav>
      <EstadoConsulta cargando={parada.isPending} error={parada.error} reintentar={() => void parada.refetch()}>
        {parada.data && (
          <Contenido parada={parada.data} novelaId={novelaId} titulo={detalle.data?.novela.titulo || "Sin título"} />
        )}
      </EstadoConsulta>
    </section>
  );
}

function Contenido({ parada, novelaId, titulo }: { parada: Parada; novelaId: number; titulo: string }) {
  const abierta = parada.estado === "abierta";
  const tipo = comoTipoParada(parada.tipo);
  return (
    <>
      <div className="alerta-parada__franja" data-abierta={abierta ? true : undefined}>
        <span className="baliza" aria-hidden="true" />
        <span>
          Alerta de a bordo · parada P-{parada.id} · {legible(parada.tipo)}
        </span>
        <span className="alerta-parada__franja-der">
          {abierta ? "Ejecución detenida · esperando decisión" : (RESOLUCION[parada.resolucion ?? ""] ?? `Resuelta: ${parada.resolucion ?? "sin resolución"}`)}
        </span>
      </div>
      <header className="alerta-parada__cabecera">
        <div className="alerta-parada__titulo">
          <Dibujo src={DIBUJOS.parada} className="dibujo--parada" />
          <h1 id="titulo-parada">
            {titulo}: parada de {parada.tipo}
          </h1>
        </div>
        <dl className="telemetria">
          <div>
            <dt>Tipo</dt>
            <dd>{legible(parada.tipo)}</dd>
          </div>
          <div>
            <dt>Capítulo</dt>
            <dd>{parada.capitulo ? String(parada.capitulo).padStart(2, "0") : "Planificación"}</dd>
          </div>
          <div>
            <dt>Intento</dt>
            <dd>{parada.intento ? `${parada.intento}/3` : "—"}</dd>
          </div>
          <div>
            <dt>Abierta</dt>
            <dd>
              <Hace iso={parada.creado_en} />
            </dd>
          </div>
        </dl>
      </header>
      <InformeParada informe={parada.informe} />
      {abierta && tipo ? (
        <Decision parada={parada} tipo={tipo} novelaId={novelaId} />
      ) : abierta ? (
        <p className="aviso aviso--error">
          Esta versión del frontend no conoce el tipo de parada «{parada.tipo}», así que no ofrece acciones.
        </p>
      ) : (
        <p className="aviso">
          Esta parada ya está resuelta. <Link to={`/novelas/${novelaId}`}>Volver a la novela</Link>.
        </p>
      )}
    </>
  );
}

function Decision({ parada, tipo, novelaId }: { parada: Parada; tipo: TipoParada; novelaId: number }) {
  const { pendientes, rechazos, pedir, descartarRechazo } = useIntenciones();
  const navegar = useNavigate();
  const estructura = useQuery(consultaEstructura(novelaId));
  const [armada, setArmada] = useState<AccionParada | null>(null);
  const [desde, setDesde] = useState(parada.capitulo ?? 1);
  const [errorPedir, setErrorPedir] = useState<string | null>(null);
  const pendiente = pendientes.find((p) => p.novelaId === novelaId);
  const rechazo = rechazos[novelaId];
  const acciones = ACCIONES_POR_TIPO_DE_PARADA[tipo];
  const capitulos = (estructura.data?.capitulos ?? [])
    .map((c) => c.numero)
    .filter((n) => n <= (parada.capitulo ?? n));

  useEffect(() => {
    if (!armada) return;
    const alTeclear = (e: KeyboardEvent) => e.key === "Escape" && setArmada(null);
    document.addEventListener("keydown", alTeclear);
    return () => document.removeEventListener("keydown", alTeclear);
  }, [armada]);

  const resolver = (accion: AccionParada) => {
    setErrorPedir(null);
    setArmada(null);
    const payload: Record<string, unknown> = { parada_id: parada.id, accion };
    if (accion === "relanzar") payload.desde_capitulo = desde;
    pedir(
      { tipo: "resolver_parada", novela_id: novelaId, payload },
      { alTerminar: (i) => i.estado === "hecha" && void navegar(`/novelas/${novelaId}`) },
    ).catch((e: unknown) => setErrorPedir(`No se pudo pedir «${NOMBRE_ACCION[accion]}»: ${(e as Error).message}`));
  };

  return (
    <section aria-labelledby="titulo-decision">
      <h2 id="titulo-decision" className="alerta-parada__decision">
        Decisión <span>una acción · el primer clic la arma, el segundo la envía</span>
      </h2>
      <div className="opciones-parada" role="group" aria-label="Acciones de resolución">
        {acciones.map((accion) => {
          const esArmada = armada === accion;
          const aviso = avisoDe(accion, parada);
          return (
            <div key={accion} className="opcion" data-opcion={accion} data-armada={esArmada ? true : undefined}>
              <h3>
                <code>{accion}</code> {NOMBRE_ACCION[accion]}
              </h3>
              <p className="opcion__consecuencia">{consecuencia(accion, tipo, desde)}</p>
              {accion === "relanzar" && parada.capitulo && capitulos.length > 0 && (
                <label className="opcion__campo">
                  Desde el capítulo{" "}
                  <select value={desde} onChange={(e) => setDesde(Number(e.target.value))} disabled={pendiente !== undefined}>
                    {capitulos.map((n) => (
                      <option key={n} value={n}>
                        {String(n).padStart(2, "0")}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {aviso && <p className="opcion__aviso">{aviso}</p>}
              <button
                type="button"
                className={`boton${esArmada ? " boton--alerta" : ""}`}
                disabled={pendiente !== undefined}
                onClick={() => (esArmada ? resolver(accion) : setArmada(accion))}
              >
                {esArmada ? `Confirmar: ${NOMBRE_ACCION[accion].toLowerCase()}` : NOMBRE_ACCION[accion]}
              </button>
            </div>
          );
        })}
      </div>
      <p className="alerta-parada__pie" role="status">
        {pendiente ? (
          <>
            <span className="cursor" aria-hidden="true" />
            Resolución en cola · esperando confirmación del worker
          </>
        ) : armada ? (
          `«${NOMBRE_ACCION[armada]}» armada: vuelve a pulsar para enviarla, o Escape para desarmarla.`
        ) : null}
      </p>
      {rechazo && (
        <div className="aviso aviso--error" role="alert">
          <p>
            <strong>{NOMBRE_ACCION[(rechazo.tipo as AccionParada)] ?? "Resolución"}: rechazada.</strong> {rechazo.motivo}
          </p>
          <button type="button" className="boton boton--mini" onClick={() => descartarRechazo(novelaId)}>
            Entendido
          </button>
        </div>
      )}
      {errorPedir && (
        <p className="aviso aviso--error" role="alert">
          {errorPedir}
        </p>
      )}
    </section>
  );
}
