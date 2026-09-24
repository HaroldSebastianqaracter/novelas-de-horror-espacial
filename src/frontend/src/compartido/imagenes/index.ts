/**
 * Las imágenes de la web (RF-FE-IMG). Todas son decorativas: se pintan con CSS (fondo o máscara)
 * y no llevan texto dentro. El plano de la nave y la cabecera de la consola van por `url()` en
 * su CSS. Procedencia y tratamiento en `CREDITOS.md`.
 */
import crearNovela from "./crear-novela.svg";
import parada from "./parada.svg";
import planoNave from "./plano-nave.webp";
import generica from "./portada-generica.webp";
import genericaWeb from "./portada-generica-web.webp";
import cosmico from "./portada-horror_cosmico.webp";
import cosmicoWeb from "./portada-horror_cosmico-web.webp";
import iaHostil from "./portada-ia_hostil.webp";
import iaHostilWeb from "./portada-ia_hostil-web.webp";
import infeccion from "./portada-infeccion.webp";
import infeccionWeb from "./portada-infeccion-web.webp";
import slasher from "./portada-slasher_espacial.webp";
import slasherWeb from "./portada-slasher_espacial-web.webp";
import supervivencia from "./portada-supervivencia.webp";
import supervivenciaWeb from "./portada-supervivencia-web.webp";
import corporal from "./portada-terror_corporal.webp";
import corporalWeb from "./portada-terror_corporal-web.webp";
import sinSenal from "./sin-senal.svg";
import vacioTablero from "./vacio-tablero.svg";

/** Una portada en dos tamaños: 874 px de ancho para la pantalla y 1748 (A5 a 300 ppp) para imprimir. */
export interface Portada {
  web: string;
  impresion: string;
}

export const PORTADA_GENERICA: Portada = { web: genericaWeb, impresion: generica };

/** Una por subgénero de `compartido/tipos.py`. */
const PORTADAS: Record<string, Portada> = {
  terror_corporal: { web: corporalWeb, impresion: corporal },
  infeccion: { web: infeccionWeb, impresion: infeccion },
  horror_cosmico: { web: cosmicoWeb, impresion: cosmico },
  slasher_espacial: { web: slasherWeb, impresion: slasher },
  ia_hostil: { web: iaHostilWeb, impresion: iaHostil },
  supervivencia: { web: supervivenciaWeb, impresion: supervivencia },
};

/** La portada del subgénero dominante; sin subgénero, o con uno que no se conoce, la genérica. */
export function portadaDe(subgenero: string | null | undefined): Portada {
  return (subgenero && PORTADAS[subgenero]) || PORTADA_GENERICA;
}

/** El plano de la ficha. Se pinta por CSS; aquí solo para que la vista de impresión lo precargue. */
export { planoNave };

/**
 * Se resuelve cuando todas las imágenes están decodificadas, o han fallado: son decorativas y no
 * bloquean. Sin `decode()` (jsdom), en cuanto se piden.
 */
export function precargar(srcs: readonly string[]): Promise<void> {
  return Promise.all(
    srcs.map((src) => {
      const img = new Image();
      img.src = src;
      return typeof img.decode === "function" ? img.decode().catch(() => undefined) : Promise.resolve();
    }),
  ).then(() => undefined);
}

export const DIBUJOS = { parada, vacioTablero, sinSenal, crearNovela } as const;
