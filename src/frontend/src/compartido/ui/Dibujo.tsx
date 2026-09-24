import type { CSSProperties } from "react";

/**
 * Un dibujo SVG de línea (RF-FE-IMG-03) pintado con el color del texto que lo rodea: el SVG hace de
 * máscara y el color sale de `currentColor`, así que el mismo fichero va en azul o en rojo. Es
 * decorativo, y los lectores de pantalla lo saltan.
 */
export function Dibujo({ src, className }: { src: string; className?: string }) {
  return (
    <span
      className={className ? `dibujo ${className}` : "dibujo"}
      style={{ "--dibujo": `url("${src}")` } as CSSProperties}
      aria-hidden="true"
    />
  );
}
