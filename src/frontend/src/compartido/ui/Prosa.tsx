import type { ReactNode } from "react";

/**
 * La cursiva de la prosa (RF-FE-LEE-09): el redactor marca entre asteriscos lo que va en cursiva
 * (la voz de una IA o de una radio, un pensamiento). Solo cuenta la marca bien formada: un
 * asterisco pegado a la primera letra, otro pegado a la última, y ninguno doble. Así `5 * 3 * 2`,
 * `**negrita**` o un asterisco suelto salen tal cual.
 */
const CURSIVA = /(?<![*\p{L}\p{N}])\*(?=[^\s*])[^*\n]*?[^\s*]\*(?![*\p{L}\p{N}])/gu;

interface Marcas {
  cursiva: boolean[];
  oculto: boolean[];
}

function marcas(texto: string): Marcas {
  const cursiva = new Array<boolean>(texto.length).fill(false);
  const oculto = new Array<boolean>(texto.length).fill(false);
  for (const m of texto.matchAll(CURSIVA)) {
    const inicio = m.index;
    const fin = inicio + m[0].length - 1;
    oculto[inicio] = true;
    oculto[fin] = true;
    for (let i = inicio + 1; i < fin; i++) cursiva[i] = true;
  }
  return { cursiva, oculto };
}

/** Los tramos de `texto[desde, desde + largo)`, sin los asteriscos de marca. */
function tramos(texto: string, { cursiva, oculto }: Marcas, desde = 0, largo = texto.length) {
  const salida: { texto: string; cursiva: boolean }[] = [];
  for (let i = desde; i < desde + largo; i++) {
    if (oculto[i]) continue;
    const ultimo = salida.at(-1);
    if (ultimo && ultimo.cursiva === cursiva[i]) ultimo.texto += texto[i];
    else salida.push({ texto: texto[i] ?? "", cursiva: cursiva[i] ?? false });
  }
  return salida;
}

export function tramosDeEnfasis(texto: string): { texto: string; cursiva: boolean }[] {
  return tramos(texto, marcas(texto));
}

const pintar = (ts: { texto: string; cursiva: boolean }[]) =>
  ts.map((t, i) => (t.cursiva ? <em key={i}>{t.texto}</em> : t.texto));

/** Un párrafo de prosa con sus cursivas. */
export function ConEnfasis({ texto }: { texto: string }) {
  return <>{pintar(tramosDeEnfasis(texto))}</>;
}

/**
 * Lo mismo sobre un párrafo de la comparación de versiones, partido en trozos iguales, quitados y
 * nuevos. El texto de antes (iguales y quitados) y el de después (iguales y nuevos) son dos textos
 * distintos, y cada uno lleva sus marcas: un asterisco pegado a una palabra que cambia está en los
 * dos. Lo quitado se pinta con las marcas de antes, y lo igual y lo nuevo, con las de después.
 */
export function trozosConEnfasis<T extends { tipo: string; texto: string }>(
  trozos: readonly T[],
  envolver: (trozo: T, contenido: ReactNode, clave: number) => ReactNode,
): ReactNode[] {
  const lado = (incluye: (t: T) => boolean) => {
    let texto = "";
    const desde = new Map<number, number>();
    trozos.forEach((t, i) => {
      if (!incluye(t)) return;
      desde.set(i, texto.length);
      texto += t.texto;
    });
    return { texto, desde, marcas: marcas(texto) };
  };
  const antes = lado((t) => t.tipo !== "nuevo");
  const despues = lado((t) => t.tipo !== "quitado");
  return trozos.map((trozo, i) => {
    const l = trozo.tipo === "quitado" ? antes : despues;
    const contenido = pintar(tramos(l.texto, l.marcas, l.desde.get(i) ?? 0, trozo.texto.length));
    return envolver(trozo, contenido, i);
  });
}
