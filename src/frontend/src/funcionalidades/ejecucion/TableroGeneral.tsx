import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { consultaNovelas } from "../../compartido/api/consultas";
import { EstadoConsulta } from "../../compartido/ui/EstadoConsulta";

/**
 * Paso 1: solo comprueba el cableado (cliente, caché y mocks). Las columnas, las tarjetas
 * y el arrastre de RF-FE-TAB llegan en los pasos 2 y 3.
 */
export function TableroGeneral() {
  const { data, isPending, error, refetch } = useQuery(consultaNovelas());

  return (
    <section className="pantalla" aria-labelledby="titulo-tablero">
      <h1 id="titulo-tablero">Tablero</h1>
      <EstadoConsulta cargando={isPending} error={error} reintentar={() => void refetch()}>
        {data && data.length === 0 ? (
          <p className="aviso">
            Todavía no hay novelas. <Link to="/crear">Crea la primera</Link>.
          </p>
        ) : (
          <ul>
            {data?.map((novela) => (
              <li key={novela.id}>
                <Link to={`/novelas/${novela.id}`}>{novela.titulo || "Sin título"}</Link>{" "}
                <span className="codigo">{novela.estado ?? "sin ejecución"}</span>
              </li>
            ))}
          </ul>
        )}
      </EstadoConsulta>
    </section>
  );
}
