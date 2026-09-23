import { useQueries, useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { consultaEjecucion, consultaNovelas } from "../../compartido/api/consultas";
import { comoEstadoEjecucion, ESTADOS_ACTIVOS } from "../../compartido/api/reglas";
import { EstadoConsulta } from "../../compartido/ui/EstadoConsulta";
import { COLUMNAS, type GrupoId, grupoDe } from "./columnas";
import { estadoDe, type NovelaEnTablero, Tarjeta, tituloDe } from "./Tarjeta";
import "./TableroGeneral.css";

const reciente = (x: NovelaEnTablero) => x.ejecucion?.actualizado_en ?? x.novela.creado_en;

function agrupar(novelas: NovelaEnTablero[]): Record<GrupoId, NovelaEnTablero[]> {
  const grupos: Record<GrupoId, NovelaEnTablero[]> = {
    espera: [],
    planificando: [],
    escribiendo: [],
    terminada: [],
    atencion: [],
  };
  for (const x of novelas) grupos[grupoDe(estadoDe(x))].push(x);
  for (const g of Object.values(grupos)) g.sort((a, b) => reciente(b).localeCompare(reciente(a)));
  return grupos;
}

const plural = (n: number, singular: string, varias: string) => (n === 1 ? singular : varias);

/** Tablero general (RF-FE-TAB). */
export function TableroGeneral() {
  const novelas = useQuery(consultaNovelas());
  // El resumen no trae fase ni total: una consulta de ejecución por novela (RF-FE-API-04).
  const ejecuciones = useQueries({ queries: (novelas.data ?? []).map((n) => consultaEjecucion(n.id)) });

  const enTablero: NovelaEnTablero[] = (novelas.data ?? []).map((novela, i) => ({
    novela,
    ejecucion: ejecuciones[i]?.data,
  }));
  const grupos = agrupar(enTablero);
  const activa = enTablero.find((x) => {
    const estado = comoEstadoEjecucion(estadoDe(x));
    return estado !== null && ESTADOS_ACTIVOS.has(estado);
  });
  const atencion = grupos.atencion.length;

  return (
    <section className="pantalla pantalla--tablero" aria-labelledby="titulo-tablero">
      <header className="pantalla__cabecera">
        <div>
          <h1 id="titulo-tablero">Tablero general</h1>
          {novelas.data && (
            <p className="resumen">
              {enTablero.length} {plural(enTablero.length, "novela", "novelas")} · en curso:{" "}
              <strong>{activa ? tituloDe(activa.novela) : "ninguna"}</strong> · {atencion}{" "}
              {plural(atencion, "requiere", "requieren")} atención
            </p>
          )}
        </div>
        <Link className="boton boton--primario" to="/crear">
          <span aria-hidden="true">+</span> Nueva novela
        </Link>
      </header>

      <EstadoConsulta cargando={novelas.isPending} error={novelas.error} reintentar={() => void novelas.refetch()}>
        {enTablero.length === 0 ? (
          <TableroVacio />
        ) : (
          <>
            <CarrilAtencion novelas={grupos.atencion} />
            <div className="tablero">
              {COLUMNAS.map((columna) => {
                const lista = grupos[columna.id];
                const idTitulo = `columna-${columna.id}`;
                return (
                  <section key={columna.id} className="columna" data-columna={columna.id} aria-labelledby={idTitulo}>
                    <header className="columna__cabecera">
                      <h2 id={idTitulo}>{columna.nombre}</h2>
                      <span className="cuenta" aria-label={`${lista.length} ${plural(lista.length, "novela", "novelas")}`}>
                        {lista.length}
                      </span>
                      <p className="columna__estados">{columna.estados.join(" · ")}</p>
                    </header>
                    <div className="columna__zona">
                      {lista.length > 0 ? (
                        lista.map((x) => <Tarjeta key={x.novela.id} {...x} />)
                      ) : (
                        <p className="columna__vacio">{columna.vacio}</p>
                      )}
                    </div>
                  </section>
                );
              })}
            </div>
          </>
        )}
      </EstadoConsulta>
    </section>
  );
}

/** Carril de parada y error: siempre visible, nunca escondido dentro de otra columna (RF-FE-TAB-01). */
function CarrilAtencion({ novelas }: { novelas: NovelaEnTablero[] }) {
  const vacio = novelas.length === 0;
  return (
    <section className="carril-atencion" data-vacio={vacio} aria-labelledby="titulo-atencion">
      <header className="carril-atencion__cabecera">
        <h2 id="titulo-atencion">
          <span aria-hidden="true">■</span> Requiere atención{" "}
          <span className="cuenta" aria-label={`${novelas.length} ${plural(novelas.length, "novela", "novelas")}`}>
            {novelas.length}
          </span>
        </h2>
        <p>parada · error: no se arrastran, se abren para decidir</p>
      </header>
      <div className="carril-atencion__zona">
        {vacio ? (
          <p className="carril-atencion__vacio">Sin incidencias. Ninguna ejecución espera decisión.</p>
        ) : (
          novelas.map((x) => <Tarjeta key={x.novela.id} {...x} />)
        )}
      </div>
    </section>
  );
}

/** Primera vez: qué es esto y por dónde se empieza (RF-FE-TAB-06). */
function TableroVacio() {
  return (
    <div className="vacio">
      <h2>Todavía no hay novelas</h2>
      <p>
        Cada novela nace <strong>En espera</strong>. Al arrancarla, los agentes la planifican y la escriben solos,
        durante horas. Este tablero observa y avisa cuando algo necesita tu decisión.
      </p>
      <ol className="vacio__flujo" aria-label="Recorrido de una novela">
        {COLUMNAS.map((c) => (
          <li key={c.id}>{c.nombre}</li>
        ))}
      </ol>
      <Link className="boton boton--primario" to="/crear">
        Crea la primera
      </Link>
    </div>
  );
}
