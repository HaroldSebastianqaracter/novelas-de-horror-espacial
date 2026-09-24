/**
 * Alias legibles de los esquemas generados. Aquí no se escribe ningún tipo a mano
 * (RF-FE-API-01): si un esquema cambia, se regenera `esquema.gen.ts` y esto lo sigue.
 */
import type { components } from "./esquema.gen";

type Esquemas = components["schemas"];

export type NovelaResumen = Esquemas["NovelaResumen"];
export type NovelaDetalle = Esquemas["NovelaDetalle"];
export type Ejecucion = Esquemas["Ejecucion"];
export type Parada = Esquemas["Parada"];
export type Estructura = Esquemas["Estructura"];
export type Capitulo = Esquemas["Capitulo"];
export type CapituloTexto = Esquemas["CapituloTexto"];
export type VersionResumen = Esquemas["VersionResumen"];
export type VersionNovela = Esquemas["VersionNovela"];
export type NuevaIntencion = Esquemas["NuevaIntencion"];
export type IntencionEncolada = Esquemas["IntencionEncolada"];
export type Intencion = Esquemas["EstadoIntencion"];
export type TipoIntencion = NuevaIntencion["tipo"];
