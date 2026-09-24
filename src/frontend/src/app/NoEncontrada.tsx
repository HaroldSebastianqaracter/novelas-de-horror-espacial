import { Link } from "react-router";
import { DIBUJOS } from "../compartido/imagenes";
import { Dibujo } from "../compartido/ui/Dibujo";

export function NoEncontrada() {
  return (
    <section className="pantalla pantalla--sin-senal">
      <Dibujo src={DIBUJOS.sinSenal} className="dibujo--sin-senal" />
      <h1>Ruta desconocida</h1>
      <p>
        Esta dirección no lleva a ninguna pantalla. <Link to="/">Volver al tablero</Link>.
      </p>
    </section>
  );
}
