import axe from "axe-core";
import { expect } from "vitest";

/**
 * Pasa axe sobre un contenedor y falla con la lista de violaciones (RF-FE-VIS-03).
 * jsdom no calcula estilos, así que el contraste no se mide aquí: está medido en los tokens.
 */
export async function sinViolaciones(contenedor: Element) {
  const resultado = await axe.run(contenedor, { rules: { "color-contrast": { enabled: false } } });
  const resumen = resultado.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.length})`);
  expect(resumen).toEqual([]);
}
