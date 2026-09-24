/**
 * DEUDA (RF-FE-API-04). Copia en TypeScript de reglas que la API todavía no publica:
 * - las uniones de `src/backend/compartido/tipos.py`, porque el OpenAPI tipa estos campos como `string`;
 * - la tabla de resoluciones y los conjuntos de estados de `src/backend/orquestador/estados.py`.
 *
 * Pedidos al backend en la sección 5 de specs/spec-frontend.md: declarar los `Literal` en los
 * modelos de respuesta y exponer las acciones válidas. Cuando lleguen, este fichero se borra.
 * El worker sigue siendo quien decide: esto solo evita ofrecer botones que se rechazarían.
 */

export const ESTADOS_EJECUCION = [
  "configurada", "planificando", "escaletando", "generando", "parada", "detenida",
  "completada", "completada_con_avisos", "error",
] as const;
export type EstadoEjecucion = (typeof ESTADOS_EJECUCION)[number];

export const FASES = [
  "arquitecto", "mundo", "elenco", "estructura", "puerta_1", "escaleta", "puerta_2",
  "paquete", "redaccion", "extraccion", "puerta_3", "puerta_4", "puerta_5",
  // La del revisor que aplica un cambio del lector a cada capítulo de su alcance (bloque 8).
  "revision",
] as const;
export type Fase = (typeof FASES)[number];

export const TIPOS_PARADA = ["estructura", "escaleta", "continuidad", "oficio", "presupuesto"] as const;
export type TipoParada = (typeof TIPOS_PARADA)[number];

export const ESTADOS_INTENCION = ["pendiente", "en_curso", "hecha", "rechazada", "interrumpida"] as const;
export type EstadoIntencion = (typeof ESTADOS_INTENCION)[number];

export type AccionParada = "relanzar" | "aceptar_retcon" | "dar_por_sabido" | "rehacer";

/** (tipo de parada) -> acciones de `resolver_parada` que admite. Espejo de `RESOLUCIONES`. */
export const ACCIONES_POR_TIPO_DE_PARADA: Record<TipoParada, readonly AccionParada[]> = {
  estructura: ["rehacer"],
  escaleta: ["rehacer"],
  continuidad: ["aceptar_retcon", "dar_por_sabido", "relanzar"],
  oficio: ["relanzar"],
  presupuesto: ["relanzar"],
};

export const ESTADOS_QUE_ADMITEN_ARRANCAR: ReadonlySet<EstadoEjecucion> = new Set([
  "configurada", "detenida", "error",
]);
export const ESTADOS_QUE_ADMITEN_RELANZAR: ReadonlySet<EstadoEjecucion> = new Set([
  "detenida", "completada", "completada_con_avisos", "error",
]);
export const ESTADOS_ACTIVOS: ReadonlySet<EstadoEjecucion> = new Set([
  "planificando", "escaletando", "generando",
]);

/** Un valor que el cliente no conoce se devuelve como `null` y la pantalla lo pinta tal cual. */
function entre<T extends string>(lista: readonly T[], valor: string | null | undefined): T | null {
  return valor != null && (lista as readonly string[]).includes(valor) ? (valor as T) : null;
}

export const comoEstadoEjecucion = (v: string | null | undefined) => entre(ESTADOS_EJECUCION, v);
export const comoFase = (v: string | null | undefined) => entre(FASES, v);
export const comoTipoParada = (v: string | null | undefined) => entre(TIPOS_PARADA, v);
export const comoEstadoIntencion = (v: string | null | undefined) => entre(ESTADOS_INTENCION, v);

/** Las fechas de la API salen de SQLite (`datetime('now')`): UTC sin zona, «2026-09-23 15:44:20». */
export function instanteDeApi(texto: string): Date {
  const sinZona = /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(texto);
  return new Date(sinZona ? `${texto.replace(" ", "T")}Z` : texto);
}

/**
 * El capítulo en curso, o `null`. Al cerrar un capítulo el worker deja el cursor en el siguiente,
 * así que al terminar la novela `capitulo_actual` vale `total_capitulos + 1`.
 */
export function capituloEnCurso(e: { capitulo_actual?: number | null; total_capitulos?: number | null }): number | null {
  const n = e.capitulo_actual;
  if (!n) return null;
  return e.total_capitulos && n > e.total_capitulos ? null : n;
}
