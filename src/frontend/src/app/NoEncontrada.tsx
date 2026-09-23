import { Link } from "react-router";

export function NoEncontrada() {
  return (
    <section className="pantalla">
      <h1>Ruta desconocida</h1>
      <p>
        Esta dirección no lleva a ninguna pantalla. <Link to="/">Volver al tablero</Link>.
      </p>
    </section>
  );
}
