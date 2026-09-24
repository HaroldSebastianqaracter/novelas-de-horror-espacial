/**
 * Qué cambió entre dos versiones de un capítulo (RF-FE-LEE-07). Se compara por párrafos y,
 * dentro de cada párrafo cambiado, por palabras. Todo en el cliente: la API ya sirve las dos
 * versiones enteras.
 */

export type TipoTrozo = "igual" | "nuevo" | "quitado";
export interface Trozo {
  tipo: TipoTrozo;
  texto: string;
}
export interface ParrafoComparado {
  tipo: "igual" | "nuevo" | "quitado" | "cambiado";
  trozos: Trozo[];
}

/**
 * Con más pares de palabras que esto entre las dos versiones del capítulo, se compara solo por
 * párrafos: un párrafo cambiado sale entero como quitado y nuevo (RF-FE-LEE-07).
 */
export const MAX_PARES = 4_000_000;

const contarPalabras = (texto: string) => texto.split(/\s+/).filter(Boolean).length;

export const partirEnParrafos = (texto: string) =>
  texto
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter(Boolean);

type Op<T> = { tipo: TipoTrozo; valor: T };

/** Subsecuencia común más larga, en orden. O(n·m) en memoria y tiempo: se acota con MAX_PARES. */
function diferencias<T>(a: readonly T[], b: readonly T[]): Op<T>[] {
  const n = a.length;
  const m = b.length;
  const tabla = new Uint32Array((n + 1) * (m + 1));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      tabla[i * (m + 1) + j] =
        a[i] === b[j]
          ? (tabla[(i + 1) * (m + 1) + j + 1] ?? 0) + 1
          : Math.max(tabla[(i + 1) * (m + 1) + j] ?? 0, tabla[i * (m + 1) + j + 1] ?? 0);
    }
  }
  const ops: Op<T>[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      ops.push({ tipo: "igual", valor: a[i] as T });
      i++;
      j++;
    } else if ((tabla[(i + 1) * (m + 1) + j] ?? 0) >= (tabla[i * (m + 1) + j + 1] ?? 0)) {
      ops.push({ tipo: "quitado", valor: a[i++] as T });
    } else {
      ops.push({ tipo: "nuevo", valor: b[j++] as T });
    }
  }
  while (i < n) ops.push({ tipo: "quitado", valor: a[i++] as T });
  while (j < m) ops.push({ tipo: "nuevo", valor: b[j++] as T });
  return ops;
}

/** Une los trozos seguidos del mismo tipo. */
function juntar(trozos: Trozo[]): Trozo[] {
  const salida: Trozo[] = [];
  for (const t of trozos) {
    const ultimo = salida.at(-1);
    if (ultimo && ultimo.tipo === t.tipo) ultimo.texto += t.texto;
    else if (t.texto) salida.push({ ...t });
  }
  return salida;
}

/** Palabras y espacios, para que al unir los trozos salga el texto exacto. */
const tokens = (texto: string) => texto.split(/(\s+)/).filter((t) => t !== "");

export function compararPalabras(antes: string, despues: string, maxPares = MAX_PARES): Trozo[] {
  const a = tokens(antes);
  const b = tokens(despues);
  if (contarPalabras(antes) * contarPalabras(despues) > maxPares) {
    return juntar([
      { tipo: "quitado", texto: antes },
      { tipo: "nuevo", texto: despues },
    ]);
  }
  return juntar(diferencias(a, b).map((op) => ({ tipo: op.tipo, texto: op.valor })));
}

/** El capítulo `despues` comparado con `antes`. Sin `antes`, todo es nuevo. */
export function compararCapitulo(antes: string | undefined, despues: string, maxPares = MAX_PARES): ParrafoComparado[] {
  const nuevos = partirEnParrafos(despues);
  if (antes === undefined) return nuevos.map((p) => ({ tipo: "nuevo", trozos: [{ tipo: "nuevo", texto: p }] }));
  const viejos = partirEnParrafos(antes);
  // Por palabras solo si el capítulo entero cabe en el tope; si no, solo por párrafos.
  const porPalabras = contarPalabras(antes) * contarPalabras(despues) <= maxPares;
  if (viejos.length * nuevos.length > maxPares) {
    return [
      ...viejos.map((p): ParrafoComparado => ({ tipo: "quitado", trozos: [{ tipo: "quitado", texto: p }] })),
      ...nuevos.map((p): ParrafoComparado => ({ tipo: "nuevo", trozos: [{ tipo: "nuevo", texto: p }] })),
    ];
  }

  const salida: ParrafoComparado[] = [];
  let quitados: string[] = [];
  let anadidos: string[] = [];
  // Entre dos párrafos iguales, cada quitado se empareja con un añadido: es un párrafo cambiado.
  const vaciar = () => {
    const pares = Math.min(quitados.length, anadidos.length);
    for (let k = 0; k < pares; k++) {
      const [a, b] = [quitados[k] as string, anadidos[k] as string];
      salida.push({
        tipo: "cambiado",
        trozos: porPalabras
          ? compararPalabras(a, b, maxPares)
          : [
              { tipo: "quitado", texto: a },
              { tipo: "nuevo", texto: b },
            ],
      });
    }
    for (const p of quitados.slice(pares)) salida.push({ tipo: "quitado", trozos: [{ tipo: "quitado", texto: p }] });
    for (const p of anadidos.slice(pares)) salida.push({ tipo: "nuevo", trozos: [{ tipo: "nuevo", texto: p }] });
    quitados = [];
    anadidos = [];
  };
  for (const op of diferencias(viejos, nuevos)) {
    if (op.tipo === "igual") {
      vaciar();
      salida.push({ tipo: "igual", trozos: [{ tipo: "igual", texto: op.valor }] });
    } else if (op.tipo === "quitado") quitados.push(op.valor);
    else anadidos.push(op.valor);
  }
  vaciar();
  return salida;
}

/** Reconstruye una de las dos versiones a partir de la comparación. */
export function reconstruir(comparado: ParrafoComparado[], lado: "antes" | "despues"): string {
  const excluir: TipoTrozo = lado === "antes" ? "nuevo" : "quitado";
  return comparado
    .map((p) =>
      p.trozos
        .filter((t) => t.tipo !== excluir)
        .map((t) => t.texto)
        .join(""),
    )
    .filter(Boolean)
    .join("\n\n");
}
