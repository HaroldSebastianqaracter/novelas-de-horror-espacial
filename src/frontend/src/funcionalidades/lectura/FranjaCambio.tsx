import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link } from "react-router";
import { CAMBIO_TERMINADO, leerCambio } from "../../compartido/api/cambios";
import { claves, consultaEjecucion, consultaIntencion } from "../../compartido/api/consultas";
import { motivoLegible } from "../../compartido/api/intenciones";
import { comoEstadoIntencion, comoFase } from "../../compartido/api/reglas";
import type { VersionResumen } from "../../compartido/api/tipos";
import { ETIQUETA_FASE } from "../../compartido/ui/vocabulario";
import type { CambioGuardado } from "./cambioGuardado";

const enumerar = (xs: number[]) =>
  xs.length === 1 ? `el capítulo ${xs[0]}` : `los capítulos ${xs.slice(0, -1).join(", ")} y ${xs.at(-1) ?? ""}`;

/**
 * Seguimiento de un cambio del lector (RF-FE-CAM-04, RF-FE-CAM-05): pedido, reescribiendo,
 * versión nueva, rechazado o fallido. Todo sale del `GET`: la intención, el cambio y las versiones.
 */
export function FranjaCambio({
  novelaId,
  cambio,
  versiones,
  alCerrar,
}: {
  novelaId: number;
  cambio: CambioGuardado;
  versiones: readonly VersionResumen[];
  alCerrar: () => void;
}) {
  const intencion = useQuery({
    ...consultaIntencion(cambio.intencionId),
    refetchInterval: (q) => {
      const e = comoEstadoIntencion(q.state.data?.estado);
      return e === "hecha" || e === "rechazada" || e === "interrumpida" ? false : 1_000;
    },
  });
  const estadoIntencion = comoEstadoIntencion(intencion.data?.estado);
  const resultado = (intencion.data?.resultado ?? null) as { cambio_id?: unknown; capitulos?: unknown; explicacion?: unknown } | null;
  const cambioId = typeof resultado?.cambio_id === "number" ? resultado.cambio_id : null;
  const seguimiento = useQuery({
    queryKey: ["novelas", novelaId, "cambios", cambioId],
    queryFn: () => leerCambio(novelaId, cambioId ?? 0),
    enabled: cambioId !== null,
    retry: false,
    refetchInterval: (q) => (q.state.data && CAMBIO_TERMINADO.has(q.state.data.estado) ? false : 3_000),
  });
  const ejecucion = useQuery({ ...consultaEjecucion(novelaId), enabled: estadoIntencion === "hecha" });
  const nueva = versiones.find((v) => v.numero > cambio.versionBase && v.motivo === "cambio_lector");

  // La versión nueva la anuncia el SSE; si el evento se pierde, el cambio aplicado también la pide.
  const clienteConsultas = useQueryClient();
  const aplicado = seguimiento.data?.estado === "aplicado";
  useEffect(() => {
    if (aplicado && !nueva) void clienteConsultas.invalidateQueries({ queryKey: claves.versiones(novelaId) });
  }, [aplicado, nueva, clienteConsultas, novelaId]);

  const cerrar = (
    <button type="button" className="boton boton--mini" onClick={alCerrar}>
      Cerrar
    </button>
  );
  const pie = (
    <p className="franja-cambio__peticion">
      Tu cambio: <q>{cambio.peticion}</q>
    </p>
  );

  if (nueva) {
    return (
      <section className="franja-cambio" data-tono="hecho" role="status" aria-label="Tu cambio">
        <p>
          <strong>Versión {nueva.numero}:</strong>{" "}
          {nueva.capitulos_cambiados.length > 0 ? (
            <>
              {nueva.capitulos_cambiados.length === 1 ? "cambió el capítulo " : "cambiaron los capítulos "}
              {nueva.capitulos_cambiados.map((n, i) => (
                <span key={n}>
                  {i > 0 && (i === nueva.capitulos_cambiados.length - 1 ? " y " : ", ")}
                  <Link to={`/novelas/${novelaId}/lectura/capitulos/${n}?cambios=1`}>{n}</Link>
                </span>
              ))}
              .
            </>
          ) : (
            "no cambió el texto de ningún capítulo."
          )}{" "}
          La versión {cambio.versionBase} se sigue pudiendo leer.
        </p>
        {pie}
        {cerrar}
      </section>
    );
  }

  if (estadoIntencion === "rechazada" || estadoIntencion === "interrumpida") {
    return (
      <section className="franja-cambio" data-tono="aviso" role="alert" aria-label="Tu cambio">
        <p>
          <strong>No se aplicó.</strong> {motivoLegible(intencion.data?.motivo, intencion.data?.estado ?? "rechazada")}
        </p>
        {typeof resultado?.explicacion === "string" && <p>{resultado.explicacion}</p>}
        {pie}
        {cerrar}
      </section>
    );
  }

  const estadoCambio = seguimiento.data?.estado;
  if (estadoCambio === "fallido" || estadoCambio === "rechazado" || estadoCambio === "interrumpido") {
    const informe = seguimiento.data?.informe as { motivo?: unknown } | null;
    return (
      <section className="franja-cambio" data-tono="aviso" role="alert" aria-label="Tu cambio">
        <p>
          <strong>No se pudo aplicar tu cambio.</strong> La novela sigue como estaba, sin versión nueva.
        </p>
        {typeof informe?.motivo === "string" && <p>{informe.motivo}</p>}
        {pie}
        {cerrar}
      </section>
    );
  }

  const e = ejecucion.data;
  const fase = comoFase(e?.fase);
  const capitulos = Array.isArray(resultado?.capitulos) ? (resultado.capitulos as number[]) : [];
  return (
    <section className="franja-cambio" data-tono="curso" role="status" aria-label="Tu cambio">
      <p>
        <span className="cursor" aria-hidden="true" />
        {estadoIntencion !== "hecha" ? (
          "Cambio pedido, esperando al worker…"
        ) : e?.estado === "parada" ? (
          <>
            El worker se paró mientras reescribía.{" "}
            {e.parada_abierta_id && <Link to={`/novelas/${novelaId}/paradas/${e.parada_abierta_id}`}>Ver la parada</Link>}
          </>
        ) : e?.estado === "detenida" ? (
          "Se detuvo antes de terminar."
        ) : (
          <>
            Reescribiendo por tu cambio
            {capitulos.length > 0 && ` ${enumerar(capitulos)}`}
            {fase && ` · ${ETIQUETA_FASE[fase]}`}
            {e?.capitulo_actual && fase !== "puerta_5" ? ` · capítulo ${e.capitulo_actual}` : ""}
          </>
        )}
      </p>
      {pie}
    </section>
  );
}
