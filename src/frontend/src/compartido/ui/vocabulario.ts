/**
 * Del código exacto del backend a la etiqueta que lee una persona. El código se sigue usando
 * en los atributos `data-estado` y `data-fase`; esto es solo lo que se muestra.
 */
import type { EstadoEjecucion, Fase } from "../api/reglas";

export const ETIQUETA_ESTADO: Record<EstadoEjecucion, string> = {
  configurada: "Configurada",
  planificando: "Planificando",
  escaletando: "Escaletando",
  generando: "Generando",
  parada: "Parada",
  detenida: "Detenida",
  completada: "Completada",
  completada_con_avisos: "Completada con avisos",
  error: "Error",
};

/** El icono acompaña siempre al color: el estado nunca depende solo del tono. */
export const ICONO_ESTADO: Record<EstadoEjecucion, string> = {
  configurada: "○",
  planificando: "◐",
  escaletando: "◑",
  generando: "●",
  parada: "■",
  detenida: "‖",
  completada: "✓",
  completada_con_avisos: "▲",
  error: "✕",
};

export const ETIQUETA_FASE: Record<Fase, string> = {
  arquitecto: "Arquitecto",
  mundo: "Mundo",
  elenco: "Elenco",
  estructura: "Estructura",
  puerta_1: "Puerta 1",
  escaleta: "Escaleta",
  puerta_2: "Puerta 2",
  paquete: "Paquete",
  redaccion: "Redacción",
  extraccion: "Extracción",
  puerta_3: "Puerta 3",
  puerta_4: "Puerta 4",
  puerta_5: "Puerta 5",
};
