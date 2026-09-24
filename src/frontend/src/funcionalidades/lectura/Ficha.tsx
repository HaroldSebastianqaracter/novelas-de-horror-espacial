import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { consultaCanon, consultaEstructura } from "../../compartido/api/consultas";
import type { components } from "../../compartido/api/esquema.gen";
import type { VersionNovela } from "../../compartido/api/tipos";
import { EstadoConsulta } from "../../compartido/ui/EstadoConsulta";
import { useTitulo } from "../../compartido/ui/titulo";
import { aparicionesDesdeEscaleta, aparicionesEnLaProsa, capitulosDe } from "./apariciones";
import { useLecturaActual } from "./MarcoLectura";

type Personaje = components["schemas"]["PersonajeCanon"];
type Lugar = components["schemas"]["LugarCanon"];

/** Personajes y lugares como página de la lectura (RF-FE-LEE-04). */
export function Ficha() {
  const { novelaId, version, enlace, esUltima, ultima } = useLecturaActual();
  useTitulo(`Personajes y lugares · ${version.titulo}`);
  return (
    <article className="libro ficha" aria-labelledby="titulo-ficha">
      <h1 id="titulo-ficha">Personajes y lugares</h1>
      <FichaContenido
        novelaId={novelaId}
        version={version}
        esUltima={esUltima}
        ultima={ultima}
        nivel={2}
        enlazar={(n) => (
          <Link to={enlace(`/capitulos/${n}`)} aria-label={`capítulo ${n}`}>
            {n}
          </Link>
        )}
      />
    </article>
  );
}

/** Las consultas de la ficha: la vista de impresión las usa para saber cuándo está lista. */
export function useConsultasFicha(novelaId: number) {
  const personajes = useQuery(consultaCanon(novelaId, "personajes"));
  const lugares = useQuery(consultaCanon(novelaId, "lugares"));
  const estructura = useQuery(consultaEstructura(novelaId));
  return { personajes, lugares, estructura, cargando: personajes.isPending || lugares.isPending || estructura.isPending };
}

/**
 * El contenido de la ficha, que también va como apéndice del PDF (RF-FE-PDF-01): ahí los enlaces
 * son anclas. Solo lo que el lector puede leer sin que le destripen la historia: nada de deseo,
 * herida, mentira ni secreto.
 */
export function FichaContenido({
  novelaId,
  version,
  esUltima,
  ultima,
  nivel,
  enlazar,
}: {
  novelaId: number;
  version: VersionNovela;
  esUltima: boolean;
  ultima: number | null;
  nivel: 2 | 3;
  enlazar: (capitulo: number) => ReactNode;
}) {
  const { personajes, lugares, estructura, cargando } = useConsultasFicha(novelaId);
  const error = personajes.error ?? lugares.error ?? estructura.error;

  // El canon y la escaleta son los de ahora. En una versión anterior, «aparece en» se busca en su
  // propia prosa, para que la ficha no contradiga el texto que se está leyendo.
  const nombres = {
    personajes: (personajes.data ?? []).flatMap((p) => ("nombre" in p ? [p.nombre] : [])),
    lugares: (lugares.data ?? []).flatMap((l) => ("nombre" in l ? [l.nombre] : [])),
  };
  const apariciones = !esUltima
    ? aparicionesEnLaProsa(version.capitulos, nombres)
    : estructura.data
      ? aparicionesDesdeEscaleta(
          estructura.data,
          version.capitulos.map((c) => c.numero),
        )
      : null;

  const Seccion = `h${nivel}` as "h2" | "h3";
  const Entrada = `h${nivel + 1}` as "h3" | "h4";
  const aparece = (capitulos: number[]) =>
    capitulos.length === 0 ? (
      <span className="ficha__nunca">No aparece en esta versión</span>
    ) : (
      <>
        Aparece en {capitulos.length === 1 ? "el capítulo" : "los capítulos"}{" "}
        {capitulos.map((n, i) => (
          <span key={n}>
            {i > 0 && (i === capitulos.length - 1 ? " y " : ", ")}
            {enlazar(n)}
          </span>
        ))}
      </>
    );

  return (
    <EstadoConsulta
      cargando={cargando}
      error={error}
      reintentar={() => {
        void personajes.refetch();
        void lugares.refetch();
        void estructura.refetch();
      }}
    >
      {esUltima ? (
        <p className="ficha__fuente">
          Dónde aparece cada uno sale de la escaleta (quién está y dónde ocurre cada escena), no de la prosa: alguien
          puede asomar en un capítulo sin figurar aquí.
        </p>
      ) : (
        <p className="ficha__fuente">
          Esta ficha es la de la versión {ultima}, la actual: en la versión que lees puede haber nombres o datos que
          luego cambiaron. «Aparece en» se busca en el texto de esta versión.
        </p>
      )}
      <section aria-labelledby={`titulo-personajes-${nivel}`}>
        <Seccion id={`titulo-personajes-${nivel}`}>Personajes</Seccion>
        <ul className="ficha__lista">
          {(personajes.data ?? [])
            .filter((p): p is Personaje => p.entidad === "personajes")
            .map((p) => (
              <li key={p.id} className="ficha__entrada">
                <Entrada>{p.nombre}</Entrada>
                <p className="ficha__rol">
                  {[p.rol, typeof p.edad === "number" ? `${p.edad} años` : null].filter(Boolean).join(" · ")}
                </p>
                <p className="ficha__aparece">{apariciones && aparece(capitulosDe(apariciones.personajes, p.nombre))}</p>
              </li>
            ))}
        </ul>
      </section>
      <section aria-labelledby={`titulo-lugares-${nivel}`}>
        <Seccion id={`titulo-lugares-${nivel}`}>Lugares</Seccion>
        <ul className="ficha__lista">
          {(lugares.data ?? [])
            .filter((l): l is Lugar => l.entidad === "lugares")
            .map((l) => (
              <li key={l.id} className="ficha__entrada">
                <Entrada>{l.nombre}</Entrada>
                {(l.tipo || l.descripcion) && <p className="ficha__rol">{[l.tipo, l.descripcion].filter(Boolean).join(" · ")}</p>}
                <p className="ficha__aparece">{apariciones && aparece(capitulosDe(apariciones.lugares, l.nombre))}</p>
              </li>
            ))}
        </ul>
      </section>
    </EstadoConsulta>
  );
}
