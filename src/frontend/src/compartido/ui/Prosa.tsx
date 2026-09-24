import type { ReactNode } from "react";

/**
 * La cursiva de la prosa (RF-FE-LEE-09): el redactor marca entre asteriscos lo que va en cursiva
 * (la voz de una IA o de una radio, un pensamiento). Un párrafo con un número par de asteriscos
 * alterna texto normal y cursiva; con un número impar no se toca nada, porque el asterisco suelto
 * es del texto.
 */
export function tramosDeEnfasis(texto: string): { texto: string; cursiva: boolean }[] {
  const partes = texto.split("*");
  if (partes.length < 3 || partes.length % 2 === 0) return [{ texto, cursiva: false }];
  return partes.map((t, i) => ({ texto: t, cursiva: i % 2 === 1 })).filter((t) => t.texto !== "");
}

/** Un párrafo de prosa con sus cursivas. */
export function ConEnfasis({ texto }: { texto: string }) {
  return (
    <>
      {tramosDeEnfasis(texto).map((t, i) => (t.cursiva ? <em key={i}>{t.texto}</em> : t.texto))}
    </>
  );
}

/**
 * Lo mismo sobre un párrafo partido en trozos (la comparación de versiones): la cursiva puede
 * empezar en un trozo y acabar en otro, así que el estado pasa de uno al siguiente. `envolver`
 * recibe lo que pinta cada trozo.
 */
export function trozosConEnfasis<T extends { texto: string }>(
  trozos: readonly T[],
  envolver: (trozo: T, contenido: ReactNode, clave: number) => ReactNode,
): ReactNode[] {
  const asteriscos = trozos.reduce((n, t) => n + t.texto.split("*").length - 1, 0);
  const activa = asteriscos > 0 && asteriscos % 2 === 0;
  let cursiva = false;
  return trozos.map((trozo, i) => {
    if (!activa) return envolver(trozo, trozo.texto, i);
    const partes = trozo.texto.split("*");
    const contenido = partes.map((p, j) => {
      if (j > 0) cursiva = !cursiva;
      if (p === "") return null;
      return cursiva ? <em key={j}>{p}</em> : p;
    });
    return envolver(trozo, contenido, i);
  });
}
