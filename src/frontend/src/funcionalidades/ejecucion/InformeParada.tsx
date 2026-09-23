/**
 * El informe de una parada, que llega sin esquema (RF-FE-PAR-01). Se reconocen unas pocas
 * claves y todo lo demás se enseña tal cual: un informe nunca pierde información en pantalla.
 */

type Datos = Record<string, unknown>;

const esObjeto = (v: unknown): v is Datos => typeof v === "object" && v !== null && !Array.isArray(v);

/** `conocimiento_no_adquirido` → «Conocimiento no adquirido». */
export const legible = (clave: string) => {
  const texto = clave.replaceAll("_", " ");
  return texto.charAt(0).toUpperCase() + texto.slice(1);
};

function Valor({ valor }: { valor: unknown }) {
  if (valor === null || valor === undefined || valor === "") return <span className="informe__vacio">—</span>;
  if (typeof valor === "string" || typeof valor === "number" || typeof valor === "boolean") return <>{String(valor)}</>;
  return <pre className="informe__json">{JSON.stringify(valor, null, 2)}</pre>;
}

function ClaveValor({ datos, excluir = [] }: { datos: Datos; excluir?: readonly string[] }) {
  const filas = Object.entries(datos).filter(([clave]) => !excluir.includes(clave));
  if (filas.length === 0) return null;
  return (
    <dl className="informe__datos">
      {filas.map(([clave, valor]) => (
        <div key={clave}>
          <dt>{clave}</dt>
          <dd>
            <Valor valor={valor} />
          </dd>
        </div>
      ))}
    </dl>
  );
}

function CaraACara({ datos }: { datos: Datos }) {
  const lado = (titulo: string, valor: unknown, cita: unknown, capitulo: unknown) => (
    <figure className="cara__lado">
      <figcaption>
        <span className="etiqueta">{titulo}</span>
        {typeof capitulo === "number" && <span className="codigo">cap. {String(capitulo).padStart(2, "0")}</span>}
      </figcaption>
      {valor !== undefined && valor !== null && <p className="cara__valor">{String(valor)}</p>}
      <blockquote>{String(cita)}</blockquote>
    </figure>
  );
  return (
    <div className="cara">
      {lado("Lo que dice el texto", datos.valor_nuevo, datos.cita_nueva, datos.capitulo_nuevo)}
      <div className="cara__contra" aria-hidden="true">
        ≠
      </div>
      {lado("Lo que dice el canon", datos.valor_previo, datos.cita_previa, datos.capitulo_previo)}
    </div>
  );
}

function FichaConflicto({ conflicto, indice }: { conflicto: Datos; indice: number }) {
  const comprobacion = typeof conflicto.comprobacion === "string" ? conflicto.comprobacion : "conflicto";
  const datos = esObjeto(conflicto.datos) ? conflicto.datos : {};
  const conCaraACara = typeof datos.cita_nueva === "string" && typeof datos.cita_previa === "string";
  const aviso = conflicto.aviso === true;
  return (
    <li className="conflicto" data-aviso={aviso ? true : undefined}>
      <header className="conflicto__cabecera">
        <span className="codigo">#{indice + 1}</span>
        <h3>{legible(comprobacion)}</h3>
        <span className="conflicto__tipo">{aviso ? "aviso" : "conflicto"}</span>
        {typeof conflicto.capitulo === "number" && (
          <span className="codigo">
            cap. {String(conflicto.capitulo).padStart(2, "0")}
            {typeof conflicto.escena_id === "number" ? ` · escena ${conflicto.escena_id}` : ""}
          </span>
        )}
      </header>
      {typeof conflicto.descripcion === "string" && <p className="conflicto__descripcion">{conflicto.descripcion}</p>}
      {conCaraACara && <CaraACara datos={datos} />}
      {Object.keys(datos).length > 0 && (
        <details className="conflicto__datos">
          <summary>Datos del conflicto</summary>
          <ClaveValor datos={datos} />
        </details>
      )}
      <ClaveValor datos={conflicto} excluir={["comprobacion", "descripcion", "aviso", "capitulo", "escena_id", "datos"]} />
    </li>
  );
}

function ProsaRechazada({ prosa }: { prosa: Datos }) {
  const escenas = Object.entries(prosa).sort(([a], [b]) => Number(a) - Number(b));
  return (
    <details className="prosa-rechazada">
      <summary>Prosa del capítulo rechazado ({escenas.length} escena{escenas.length === 1 ? "" : "s"})</summary>
      {escenas.map(([orden, texto]) => (
        <section key={orden} className="prosa-rechazada__escena" aria-label={`Escena ${orden}`}>
          <p className="codigo">Escena {orden}</p>
          {String(texto)
            .split(/\n{2,}/)
            .map((parrafo, i) => (
              <p key={i}>{parrafo}</p>
            ))}
        </section>
      ))}
    </details>
  );
}

function Bloques({ bloques }: { bloques: Datos }) {
  return (
    <table className="informe__tabla">
      <caption>Bloques del paquete</caption>
      <thead>
        <tr>
          <th scope="col">Bloque</th>
          <th scope="col">Tamaño</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(bloques).map(([bloque, tam]) => (
          <tr key={bloque}>
            <th scope="row">{bloque}</th>
            <td>
              <Valor valor={tam} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const CONOCIDAS = ["motivo", "conflictos", "prosa_rechazada", "bloques"] as const;

export function InformeParada({ informe }: { informe: Datos | null | undefined }) {
  if (!informe || Object.keys(informe).length === 0) {
    return <p className="aviso">Esta parada no trae informe.</p>;
  }
  const conflictos = Array.isArray(informe.conflictos) ? informe.conflictos.filter(esObjeto) : [];
  const bloqueantes = conflictos.filter((c) => c.aviso !== true).length;
  return (
    <div className="informe-parada">
      {typeof informe.motivo === "string" && <p className="informe-parada__motivo">{informe.motivo}</p>}
      {conflictos.length > 0 && (
        <section aria-labelledby="titulo-conflictos">
          <h2 id="titulo-conflictos" className="informe-parada__titulo">
            {bloqueantes} conflicto{bloqueantes === 1 ? "" : "s"}
            {conflictos.length > bloqueantes ? ` y ${conflictos.length - bloqueantes} aviso${conflictos.length - bloqueantes === 1 ? "" : "s"}` : ""}
          </h2>
          <ol className="conflictos">
            {conflictos.map((c, i) => (
              <FichaConflicto key={i} conflicto={c} indice={i} />
            ))}
          </ol>
        </section>
      )}
      {esObjeto(informe.prosa_rechazada) && <ProsaRechazada prosa={informe.prosa_rechazada} />}
      {esObjeto(informe.bloques) && <Bloques bloques={informe.bloques} />}
      <ClaveValor datos={informe} excluir={CONOCIDAS} />
    </div>
  );
}
