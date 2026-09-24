import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { consultaCanon, consultaEstructura } from "../../compartido/api/consultas";
import type { components } from "../../compartido/api/esquema.gen";
import { EstadoConsulta } from "../../compartido/ui/EstadoConsulta";
import { useTitulo } from "../../compartido/ui/titulo";
import { aparicionesDesdeEscaleta, capitulosDe } from "./apariciones";
import { useLecturaActual } from "./MarcoLectura";

type Personaje = components["schemas"]["PersonajeCanon"];
type Lugar = components["schemas"]["LugarCanon"];

/**
 * Personajes y lugares (RF-FE-LEE-04). Solo lo que el lector puede leer sin que le destripen la
 * historia: nada de deseo, herida, mentira ni secreto.
 */
export function Ficha() {
  const { novelaId, version, enlace } = useLecturaActual();
  useTitulo(`Personajes y lugares · ${version.titulo}`);
  const personajes = useQuery(consultaCanon(novelaId, "personajes"));
  const lugares = useQuery(consultaCanon(novelaId, "lugares"));
  const estructura = useQuery(consultaEstructura(novelaId));
  const error = personajes.error ?? lugares.error ?? estructura.error;
  const cargando = personajes.isPending || lugares.isPending || estructura.isPending;

  const apariciones = estructura.data
    ? aparicionesDesdeEscaleta(
        estructura.data,
        version.capitulos.map((c) => c.numero),
      )
    : null;

  const aparece = (capitulos: number[]) =>
    capitulos.length === 0 ? (
      <span className="ficha__nunca">No aparece en esta versión</span>
    ) : (
      <>
        Aparece en {capitulos.length === 1 ? "el capítulo" : "los capítulos"}{" "}
        {capitulos.map((n, i) => (
          <span key={n}>
            {i > 0 && (i === capitulos.length - 1 ? " y " : ", ")}
            <Link to={enlace(`/capitulos/${n}`)} aria-label={`capítulo ${n}`}>
              {n}
            </Link>
          </span>
        ))}
      </>
    );

  return (
    <article className="libro ficha" aria-labelledby="titulo-ficha">
      <h1 id="titulo-ficha">Personajes y lugares</h1>
      <EstadoConsulta
        cargando={cargando}
        error={error}
        reintentar={() => {
          void personajes.refetch();
          void lugares.refetch();
          void estructura.refetch();
        }}
      >
        <p className="ficha__fuente">
          Dónde aparece cada uno sale de la escaleta (quién está y dónde ocurre cada escena), no de la prosa: alguien
          puede asomar en un capítulo sin figurar aquí.
        </p>
        <section aria-labelledby="titulo-personajes">
          <h2 id="titulo-personajes">Personajes</h2>
          <ul className="ficha__lista">
            {(personajes.data ?? [])
              .filter((p): p is Personaje => p.entidad === "personajes")
              .map((p) => (
                <li key={p.id} className="ficha__entrada">
                  <h3>{p.nombre}</h3>
                  <p className="ficha__rol">
                    {[p.rol, typeof p.edad === "number" ? `${p.edad} años` : null].filter(Boolean).join(" · ")}
                  </p>
                  <p className="ficha__aparece">{apariciones && aparece(capitulosDe(apariciones.personajes, p.nombre))}</p>
                </li>
              ))}
          </ul>
        </section>
        <section aria-labelledby="titulo-lugares">
          <h2 id="titulo-lugares">Lugares</h2>
          <ul className="ficha__lista">
            {(lugares.data ?? [])
              .filter((l): l is Lugar => l.entidad === "lugares")
              .map((l) => (
                <li key={l.id} className="ficha__entrada">
                  <h3>{l.nombre}</h3>
                  {(l.tipo || l.descripcion) && (
                    <p className="ficha__rol">{[l.tipo, l.descripcion].filter(Boolean).join(" · ")}</p>
                  )}
                  <p className="ficha__aparece">{apariciones && aparece(capitulosDe(apariciones.lugares, l.nombre))}</p>
                </li>
              ))}
          </ul>
        </section>
      </EstadoConsulta>
    </article>
  );
}
