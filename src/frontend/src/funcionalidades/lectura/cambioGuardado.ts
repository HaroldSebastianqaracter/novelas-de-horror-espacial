import { useCallback, useState } from "react";

/**
 * El cambio del lector que se pidió desde esta lectura (RF-FE-CAM-04). Solo se guarda la
 * intención: lo demás (si la aceptó el worker, por dónde va, la versión nueva) se consulta,
 * así que sobrevive a recargar la página sin guardar nada que pueda desfasarse.
 */
export interface CambioGuardado {
  intencionId: number;
  versionBase: number;
  peticion: string;
  /** Se aplicó, se rechazó, falló o se interrumpió: ya no bloquea pedir otro. */
  terminado?: boolean;
}

const clave = (novelaId: number) => `novelasv2.cambio-lector.${novelaId}`;

function leer(novelaId: number): CambioGuardado | null {
  try {
    const crudo = sessionStorage.getItem(clave(novelaId));
    return crudo ? (JSON.parse(crudo) as CambioGuardado) : null;
  } catch {
    return null;
  }
}

export function useCambioGuardado(novelaId: number) {
  const [cambio, setCambio] = useState<CambioGuardado | null>(() => leer(novelaId));
  const guardar = useCallback(
    (nuevo: CambioGuardado | null) => {
      setCambio(nuevo);
      try {
        if (nuevo) sessionStorage.setItem(clave(novelaId), JSON.stringify(nuevo));
        else sessionStorage.removeItem(clave(novelaId));
      } catch {
        // Sin almacenamiento, el seguimiento solo se pierde al recargar.
      }
    },
    [novelaId],
  );
  return [cambio, guardar] as const;
}
