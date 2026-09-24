import { useEffect } from "react";

/** El título de la pestaña sigue a la vista (RF-FE-LEE-08). */
export function useTitulo(titulo: string | null | undefined) {
  useEffect(() => {
    if (!titulo) return;
    const previo = document.title;
    document.title = `${titulo} · novelasv2`;
    return () => {
      document.title = previo;
    };
  }, [titulo]);
}
