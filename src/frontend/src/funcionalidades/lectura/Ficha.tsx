import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { consultaApariciones, consultaCambios, consultaCanon } from "../../compartido/api/consultas";
import type { components } from "../../compartido/api/esquema.gen";
import type { VersionNovela } from "../../compartido/api/tipos";
import { EstadoConsulta } from "../../compartido/ui/EstadoConsulta";
import { useTitulo } from "../../compartido/ui/titulo";
import { aparicionesDeApi, capitulosDe, nombresEnVersion, reescritosDespues } from "./apariciones";
import { useLecturaActual } from "./MarcoLectura";
import { normalizar } from "./texto";

type Personaje = components["schemas"]["PersonajeCanon"];
type Lugar = components["schemas"]["LugarCanon"];

/** Personajes y lugares como página de la lectura (RF-FE-LEE-04). */
export function Ficha() {
  const { novelaId, version, enlace, esUltima, ultima } = useLecturaActual();
  useTitulo(`Personajes y lugares · ${version.titulo}`);
  return (
    <article className="libro ficha" aria-labelledby="titulo-ficha">
      <div className="ficha__plano" aria-hidden="true" />
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

/**
 * Las consultas de la ficha: la vista de impresión las usa para saber cuándo está lista. Los
 * cambios del lector solo hacen falta en una versión anterior, para sus nombres.
 */
export function useConsultasFicha(novelaId: number, esUltima: boolean) {
  const personajes = useQuery(consultaCanon(novelaId, "personajes"));
  const lugares = useQuery(consultaCanon(novelaId, "lugares"));
  const apariciones = useQuery(consultaApariciones(novelaId));
  const cambios = useQuery({ ...consultaCambios(novelaId), enabled: !esUltima });
  const todas = esUltima ? [personajes, lugares, apariciones] : [personajes, lugares, apariciones, cambios];
  return {
    personajes,
    lugares,
    apariciones,
    cambios,
    cargando: todas.some((c) => c.isPending),
    listo: todas.every((c) => c.isSuccess),
    error: todas.find((c) => c.isError)?.error ?? null,
    reintentar: () => todas.forEach((c) => void c.refetch()),
  };
}

const enumerarNumeros = (xs: number[]) => (xs.length === 1 ? `${xs[0]}` : `${xs.slice(0, -1).join(", ")} y ${xs.at(-1) ?? ""}`);

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
  const { lista } = useLecturaActual();
  const { personajes, lugares, cargando, error, reintentar, ...consultas } = useConsultasFicha(novelaId, esUltima);

  // El canon es el de ahora. En una versión anterior, cada entidad que un cambio renombró después
  // lleva el nombre que tenía en esa versión, para que la ficha no contradiga el texto que se lee.
  // Un renombre deshecho después (A, B y otra vez A) deja el nombre de entonces igual al actual.
  const antes = esUltima ? new Map<string, string>() : nombresEnVersion(consultas.cambios.data ?? [], version.numero);
  const entonces = (clave: string, actual: string) => {
    const nombre = antes.get(clave);
    return nombre && normalizar(nombre) !== normalizar(actual) ? nombre : null;
  };
  const reescritos = esUltima ? new Set<number>() : reescritosDespues(lista, version.numero);
  const apariciones = consultas.apariciones.data
    ? aparicionesDeApi(
        consultas.apariciones.data,
        version.capitulos,
        reescritos,
        (entidad, id, actual) => entonces(`${entidad}-${id}`, actual) ?? actual,
      )
    : null;
  const nombre = (clave: string, actual: string) => {
    const deEntonces = entonces(clave, actual);
    return deEntonces ? (
      <>
        {deEntonces} <span className="ficha__ahora">(ahora {actual})</span>
      </>
    ) : (
      actual
    );
  };

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
    <EstadoConsulta cargando={cargando} error={error} reintentar={reintentar}>
      {esUltima ? (
        <p className="ficha__fuente">
          Dónde aparece cada uno sale de la story bible: quién está en cada escena, quién sabe o usa algo en ella y
          dónde ocurre.
        </p>
      ) : (
        <p className="ficha__fuente">
          Esta ficha es la de la versión {ultima}, la actual, con los nombres de la versión que lees: otros datos pueden
          haber cambiado después. Dónde aparece cada uno sale de la story bible
          {reescritos.size > 0
            ? `, salvo en ${reescritos.size === 1 ? "el capítulo" : "los capítulos"} ${enumerarNumeros([...reescritos].sort((a, b) => a - b))}, que un relanzamiento reescribió después: ahí se busca el nombre en el texto de esta versión.`
            : "."}
        </p>
      )}
      <section aria-labelledby={`titulo-personajes-${nivel}`}>
        <Seccion id={`titulo-personajes-${nivel}`}>Personajes</Seccion>
        <ul className="ficha__lista">
          {(personajes.data ?? [])
            .filter((p): p is Personaje => p.entidad === "personajes")
            .map((p) => (
              <li key={p.id} className="ficha__entrada">
                <Entrada>{nombre(`personajes-${p.id}`, p.nombre)}</Entrada>
                <p className="ficha__rol">
                  {[p.rol, typeof p.edad === "number" ? `${p.edad} años` : null].filter(Boolean).join(" · ")}
                </p>
                <p className="ficha__aparece">{apariciones && aparece(capitulosDe(apariciones.personajes, p.id))}</p>
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
                <Entrada>{nombre(`lugares-${l.id}`, l.nombre)}</Entrada>
                {(l.tipo || l.descripcion) && <p className="ficha__rol">{[l.tipo, l.descripcion].filter(Boolean).join(" · ")}</p>}
                <p className="ficha__aparece">{apariciones && aparece(capitulosDe(apariciones.lugares, l.id))}</p>
              </li>
            ))}
        </ul>
      </section>
    </EstadoConsulta>
  );
}
