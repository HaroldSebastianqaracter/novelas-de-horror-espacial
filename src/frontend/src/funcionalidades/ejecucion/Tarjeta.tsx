import { Link } from "react-router";
import { type Rechazo, type Seguimiento, UN_MINUTO } from "../../compartido/api/intenciones";
import { capituloEnCurso, comoFase } from "../../compartido/api/reglas";
import type { Ejecucion, NovelaResumen } from "../../compartido/api/tipos";
import { MiniaturaPortada } from "../../compartido/imagenes/MiniaturaPortada";
import { ChipEstado } from "../../compartido/ui/ChipEstado";
import { Hace, useAhora } from "../../compartido/ui/Hace";
import { MenuAcciones, type OpcionMenu } from "../../compartido/ui/Menu";
import { Progreso } from "../../compartido/ui/Progreso";
import { ETIQUETA_FASE } from "../../compartido/ui/vocabulario";

export interface NovelaEnTablero {
  novela: NovelaResumen;
  /** Puede faltar mientras llega su consulta: la tarjeta se pinta con lo que trae el resumen. */
  ejecucion: Ejecucion | undefined;
}

export const tituloDe = (novela: NovelaResumen) => novela.titulo || "Sin título";

export const estadoDe = ({ novela, ejecucion }: NovelaEnTablero) => ejecucion?.estado ?? novela.estado;

/** Una novela terminada ya tiene lectura, y con ella portada (RF-FE-IMG-06). */
export const terminada = (estado: string | null | undefined) => estado === "completada" || estado === "completada_con_avisos";

export const destinoDe = ({ novela, ejecucion }: NovelaEnTablero) =>
  estadoDe({ novela, ejecucion }) === "parada" && ejecucion?.parada_abierta_id
    ? `/novelas/${novela.id}/paradas/${ejecucion.parada_abierta_id}`
    : `/novelas/${novela.id}`;

export const ETIQUETA_INTENCION: Record<string, string> = {
  arrancar: "Arrancar",
  parar: "Parar",
  relanzar: "Relanzar",
  resolver_parada: "Resolver parada",
  crear_novela: "Crear novela",
  cambio_lector: "Cambio del lector",
};

function lineaFase(ejecucion: Ejecucion | undefined, estado: string | null | undefined): string {
  if (!ejecucion?.fase) return estado === "configurada" || estado == null ? "Sin arrancar" : "Sin fase activa";
  const fase = comoFase(ejecucion.fase);
  let texto = `Fase ${fase ? ETIQUETA_FASE[fase] : ejecucion.fase}`;
  const capitulo = capituloEnCurso(ejecucion);
  if (capitulo) texto += ` · cap. ${capitulo}`;
  if ((ejecucion.intento_actual ?? 1) > 1) texto += ` · intento ${ejecucion.intento_actual}/3`;
  return texto;
}

const recortar = (texto: string, max: number) => (texto.length > max ? `${texto.slice(0, max - 1)}…` : texto);

interface Props extends NovelaEnTablero {
  opciones?: readonly OpcionMenu[];
  pendiente?: Seguimiento;
  rechazo?: Rechazo;
  alDescartarRechazo?: () => void;
  /** Copia que sigue al puntero durante el arrastre: sin enlaces, ids ni menú. */
  fantasma?: boolean;
}

/** Tarjeta de novela del tablero general (RF-FE-TAB-02). */
export function Tarjeta({ opciones = [], pendiente, rechazo, alDescartarRechazo, fantasma, ...x }: Props) {
  const { novela, ejecucion } = x;
  const estado = estadoDe(x);
  const idTitulo = fantasma ? undefined : `tarjeta-${novela.id}`;
  const ahora = useAhora(pendiente ? 5_000 : null);
  const sigueEnCola = pendiente !== undefined && ahora - pendiente.desde > UN_MINUTO;
  const capituloParado = ejecucion ? capituloEnCurso(ejecucion) : null;

  return (
    <article
      className={`tarjeta${fantasma ? " tarjeta--fantasma" : ""}`}
      data-estado={estado ?? "sin_ejecucion"}
      data-fase={ejecucion?.fase ?? undefined}
      data-pendiente={pendiente?.tipo}
      data-rechazada={rechazo ? true : undefined}
      aria-labelledby={idTitulo}
    >
      <div className="tarjeta__fila">
        <span className="codigo">N-{String(novela.id).padStart(4, "0")}</span>
        <Hace className="tarjeta__hace" iso={ejecucion?.actualizado_en ?? novela.creado_en} />
      </div>
      <h3 className="tarjeta__titulo" id={idTitulo}>
        {fantasma ? (
          tituloDe(novela)
        ) : (
          <Link className="tarjeta__enlace" to={destinoDe(x)} draggable={false}>
            {tituloDe(novela)}
          </Link>
        )}
      </h3>
      {terminada(estado) && <MiniaturaPortada subgenero={novela.subgenero_dominante} className="tarjeta__portada" />}
      <div className="tarjeta__estado">
        <ChipEstado estado={estado} />
        <span className="tarjeta__fase">{lineaFase(ejecucion, estado)}</span>
      </div>
      <Progreso
        completados={ejecucion?.capitulos_completados ?? novela.capitulos_completados ?? 0}
        total={ejecucion?.total_capitulos ?? 0}
      />
      {estado === "error" && ejecucion?.ultimo_error && (
        <p className="tarjeta__alerta">
          <span className="solo-lectores">Último error: </span>
          {recortar(ejecucion.ultimo_error, 120)}
        </p>
      )}
      {estado === "parada" && (
        <p className="tarjeta__alerta">
          Parada{ejecucion?.parada_abierta_id ? ` P-${ejecucion.parada_abierta_id}` : ""}
          {capituloParado ? ` · cap. ${capituloParado}` : ""} · esperando decisión
        </p>
      )}
      {estado === "completada_con_avisos" && (
        <p className="tarjeta__avisos">
          <span aria-hidden="true">▲ </span>Terminada con avisos no bloqueantes
        </p>
      )}
      {pendiente && (
        <p className="tarjeta__pendiente" role="status">
          <span className="cursor" aria-hidden="true" />
          {ETIQUETA_INTENCION[pendiente.tipo] ?? pendiente.tipo} en cola ·{" "}
          {sigueEnCola ? "sigue en cola, el worker la atenderá al terminar lo que está haciendo" : "esperando confirmación"}
        </p>
      )}
      {rechazo && (
        <div className="tarjeta__rechazo" role="alert">
          <p>
            <strong>{ETIQUETA_INTENCION[rechazo.tipo] ?? rechazo.tipo}: rechazada.</strong> {rechazo.motivo}
          </p>
          {alDescartarRechazo && (
            <button type="button" className="boton boton--mini" onClick={alDescartarRechazo}>
              Entendido
            </button>
          )}
        </div>
      )}
      {!fantasma && opciones.length > 0 && (
        <MenuAcciones className="tarjeta__menu" etiqueta={`Acciones: ${tituloDe(novela)}`} opciones={opciones} />
      )}
    </article>
  );
}
