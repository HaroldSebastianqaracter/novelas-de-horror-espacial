import { Link } from "react-router";
import { comoFase } from "../../compartido/api/reglas";
import type { Ejecucion, NovelaResumen } from "../../compartido/api/tipos";
import { ChipEstado } from "../../compartido/ui/ChipEstado";
import { Hace } from "../../compartido/ui/Hace";
import { Progreso } from "../../compartido/ui/Progreso";
import { ETIQUETA_FASE } from "../../compartido/ui/vocabulario";

export interface NovelaEnTablero {
  novela: NovelaResumen;
  /** Puede faltar mientras llega su consulta: la tarjeta se pinta con lo que trae el resumen. */
  ejecucion: Ejecucion | undefined;
}

export const tituloDe = (novela: NovelaResumen) => novela.titulo || "Sin título";

export const estadoDe = ({ novela, ejecucion }: NovelaEnTablero) => ejecucion?.estado ?? novela.estado;

function lineaFase(ejecucion: Ejecucion | undefined, estado: string | null | undefined): string {
  if (!ejecucion?.fase) return estado === "configurada" || estado == null ? "Sin arrancar" : "Sin fase activa";
  const fase = comoFase(ejecucion.fase);
  let texto = `Fase ${fase ? ETIQUETA_FASE[fase] : ejecucion.fase}`;
  if (ejecucion.capitulo_actual) texto += ` · cap. ${ejecucion.capitulo_actual}`;
  if ((ejecucion.intento_actual ?? 1) > 1) texto += ` · intento ${ejecucion.intento_actual}/3`;
  return texto;
}

const recortar = (texto: string, max: number) => (texto.length > max ? `${texto.slice(0, max - 1)}…` : texto);

/** Tarjeta de novela del tablero general (RF-FE-TAB-02). El arrastre y el menú llegan en el paso 3. */
export function Tarjeta(props: NovelaEnTablero) {
  const { novela, ejecucion } = props;
  const estado = estadoDe(props);
  const destino =
    estado === "parada" && ejecucion?.parada_abierta_id
      ? `/novelas/${novela.id}/paradas/${ejecucion.parada_abierta_id}`
      : `/novelas/${novela.id}`;
  const idTitulo = `tarjeta-${novela.id}`;

  return (
    <article
      className="tarjeta"
      data-estado={estado ?? "sin_ejecucion"}
      data-fase={ejecucion?.fase ?? undefined}
      aria-labelledby={idTitulo}
    >
      <div className="tarjeta__fila">
        <span className="codigo">N-{String(novela.id).padStart(4, "0")}</span>
        <Hace className="tarjeta__hace" iso={ejecucion?.actualizado_en ?? novela.creado_en} />
      </div>
      <h3 className="tarjeta__titulo" id={idTitulo}>
        <Link className="tarjeta__enlace" to={destino}>
          {tituloDe(novela)}
        </Link>
      </h3>
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
          {ejecucion?.capitulo_actual ? ` · cap. ${ejecucion.capitulo_actual}` : ""} · esperando decisión
        </p>
      )}
      {estado === "completada_con_avisos" && (
        <p className="tarjeta__avisos">
          <span aria-hidden="true">▲ </span>Terminada con avisos no bloqueantes
        </p>
      )}
    </article>
  );
}
