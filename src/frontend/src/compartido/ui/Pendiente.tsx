import "./ui.css";

/** Marcador de una pantalla que todavía no está construida. Desaparece al terminar la sección 6 de la spec. */
export function Pendiente({ titulo, paso }: { titulo: string; paso: number }) {
  return (
    <section className="pantalla">
      <h1>{titulo}</h1>
      <p className="aviso">Pantalla pendiente: paso {paso} del orden de implementación de la spec del frontend.</p>
    </section>
  );
}
