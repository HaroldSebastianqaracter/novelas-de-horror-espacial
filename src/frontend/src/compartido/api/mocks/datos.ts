/**
 * Datos ficticios para MSW. Tipados contra el esquema generado, así que un cambio del
 * contrato rompe la compilación aquí antes que en una pantalla (RF-FE-API-03).
 * Títulos inventados; ningún nombre de persona real.
 */
import type { Ejecucion, NovelaResumen } from "../tipos";

const hace = (minutos: number) => new Date(Date.now() - minutos * 60_000).toISOString();

export const novelas: NovelaResumen[] = [
  { id: 1, titulo: "", genero: "terror_espacial", creado_en: hace(20), estado: "configurada", capitulos_completados: 0, subgenero_dominante: null },
  { id: 2, titulo: "Esclusa norte", genero: "terror_espacial", creado_en: hace(3000), estado: "detenida", capitulos_completados: 3, subgenero_dominante: "infeccion" },
  { id: 3, titulo: "La bodega once", genero: "terror_espacial", creado_en: hace(900), estado: "generando", capitulos_completados: 5, subgenero_dominante: "ia_hostil" },
  { id: 4, titulo: "Perforación en el pozo siete", genero: "terror_espacial", creado_en: hace(4000), estado: "parada", capitulos_completados: 2, subgenero_dominante: "horror_cosmico" },
  { id: 5, titulo: "Señal de relevo", genero: "terror_espacial", creado_en: hace(6000), estado: "error", capitulos_completados: 4, subgenero_dominante: "supervivencia" },
  { id: 6, titulo: "Deriva en el anillo Tántalo", genero: "terror_espacial", creado_en: hace(20000), estado: "completada_con_avisos", capitulos_completados: 10, subgenero_dominante: "horror_cosmico" },
];

export const ejecuciones: Record<number, Ejecucion> = {
  1: { novela_id: 1, estado: "configurada", fase: null, capitulo_actual: null, intento_actual: 1, capitulos_completados: 0, total_capitulos: 10, parada_abierta_id: null, ultimo_error: null, actualizado_en: hace(20) },
  2: { novela_id: 2, estado: "detenida", fase: null, capitulo_actual: null, intento_actual: 1, capitulos_completados: 3, total_capitulos: 8, parada_abierta_id: null, ultimo_error: null, actualizado_en: hace(2900) },
  3: { novela_id: 3, estado: "generando", fase: "redaccion", capitulo_actual: 6, intento_actual: 2, capitulos_completados: 5, total_capitulos: 10, parada_abierta_id: null, ultimo_error: null, actualizado_en: hace(1) },
  4: { novela_id: 4, estado: "parada", fase: "puerta_3", capitulo_actual: 3, intento_actual: 1, capitulos_completados: 2, total_capitulos: 6, parada_abierta_id: 93, ultimo_error: null, actualizado_en: hace(45) },
  5: { novela_id: 5, estado: "error", fase: "extraccion", capitulo_actual: 5, intento_actual: 3, capitulos_completados: 4, total_capitulos: 10, parada_abierta_id: null, ultimo_error: "El puerto a Claude Code agotó sus dos reintentos: tiempo de espera superado.", actualizado_en: hace(300) },
  6: { novela_id: 6, estado: "completada_con_avisos", fase: null, capitulo_actual: null, intento_actual: 1, capitulos_completados: 10, total_capitulos: 10, parada_abierta_id: null, ultimo_error: null, actualizado_en: hace(19000) },
};

const novelasIniciales = structuredClone(novelas);
const ejecucionesIniciales = structuredClone(ejecuciones);

/** Deshace lo que las intenciones simuladas cambiaron. Los tests lo llaman entre caso y caso. */
export function restaurarDatos() {
  novelas.splice(0, novelas.length, ...structuredClone(novelasIniciales));
  for (const id of Object.keys(ejecuciones)) delete ejecuciones[Number(id)];
  Object.assign(ejecuciones, structuredClone(ejecucionesIniciales));
}
