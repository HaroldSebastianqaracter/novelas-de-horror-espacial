/**
 * Comparación de nombres y términos para la lectura: sin mayúsculas ni tildes y por palabras
 * completas, como `contiene_termino` de `compartido/texto.py` en el backend.
 */

export const normalizar = (texto: string) =>
  texto
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();

const escapar = (texto: string) => texto.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** ¿Aparece `termino` en `texto` como palabras completas? «Nala» sí en «a Nala le», no en «Nalas». */
export function contieneTermino(texto: string, termino: string): boolean {
  const t = normalizar(termino);
  if (!t) return false;
  return new RegExp(`(^|[^\\p{L}\\p{N}])${escapar(t)}(?=$|[^\\p{L}\\p{N}])`, "u").test(normalizar(texto));
}
