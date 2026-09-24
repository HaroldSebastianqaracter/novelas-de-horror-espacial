import type { CSSProperties } from "react";
import { portadaDe } from ".";

/**
 * Una franja con la foto de la portada de un subgénero (RF-FE-IMG-06, RF-FE-IMG-07): el centro de
 * la ilustración, sin el papel de arriba ni sus márgenes. Decorativa: lo que dice va en el texto
 * que la acompaña.
 */
export function MiniaturaPortada({ subgenero, className }: { subgenero: string | null | undefined; className?: string }) {
  return (
    <span
      className={className ? `miniatura-portada ${className}` : "miniatura-portada"}
      style={{ "--portada": `url("${portadaDe(subgenero).web}")` } as CSSProperties}
      aria-hidden="true"
    />
  );
}
