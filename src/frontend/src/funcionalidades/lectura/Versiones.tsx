import { Link } from "react-router";
import { Hace } from "../../compartido/ui/Hace";
import { useTitulo } from "../../compartido/ui/titulo";
import { useLecturaActual } from "./MarcoLectura";
import { motivoLegible } from "./usarLectura";

/** Todas las versiones publicadas, la más nueva primero (RF-FE-LEE-06). */
export function Versiones() {
  const { novelaId, lista, numero, ultima, version } = useLecturaActual();
  useTitulo(`Versiones · ${version.titulo}`);
  const leer = (n: number, ruta = "", extra = "") =>
    `/novelas/${novelaId}/lectura${ruta}${n === ultima ? (extra ? `?${extra}` : "") : `?version=${n}${extra ? `&${extra}` : ""}`}`;

  return (
    <article className="libro versiones" aria-labelledby="titulo-versiones">
      <h1 id="titulo-versiones">Versiones</h1>
      <p>Cada vez que la novela se completa con otro texto nace una versión. Las anteriores se siguen pudiendo leer.</p>
      <ol className="versiones__lista" reversed>
        {[...lista].reverse().map((v) => (
          <li key={v.numero} className="versiones__entrada" aria-current={v.numero === numero ? "true" : undefined}>
            <h2>
              Versión {v.numero}
              {v.numero === ultima && <span className="versiones__marca">la última</span>}
              {v.numero === numero && <span className="versiones__marca">la que lees</span>}
            </h2>
            <p className="versiones__motivo">
              {motivoLegible(v.motivo)} · <Hace iso={v.creado_en} />
            </p>
            {v.detalle && <blockquote className="novedades__detalle">{v.detalle}</blockquote>}
            {v.motivo !== "primera" && v.capitulos_cambiados.length > 0 && (
              <p>
                Cambiaron:{" "}
                {v.capitulos_cambiados.map((n, i) => (
                  <span key={n}>
                    {i > 0 && ", "}
                    <Link to={leer(v.numero, `/capitulos/${n}`, "cambios=1")}>capítulo {n}</Link>
                  </span>
                ))}
              </p>
            )}
            <p>
              <Link to={leer(v.numero)}>Leer la versión {v.numero}</Link>
            </p>
          </li>
        ))}
      </ol>
    </article>
  );
}
