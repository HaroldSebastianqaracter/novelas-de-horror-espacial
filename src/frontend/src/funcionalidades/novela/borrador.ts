/**
 * El borrador del formulario del brief (RF-FE-BRF): lo que el usuario escribe, como texto, y su
 * conversión al brief que se envía. El borrador sobrevive a recargar la página (RF-FE-BRF-05).
 */
import {
  type AnalisisBrief,
  type Brief,
  type ElementoPersonal,
  type Intensidad,
  LIMITES,
  type Ocasion,
  type Pronombres,
  type Subgenero,
  type Tono,
} from "../../compartido/api/brief";

export interface ElementoBorrador {
  id: string;
  texto: string;
  obligatorio: boolean;
}

export interface AllegadoBorrador {
  id: string;
  nombre: string;
  relacion: string;
  /** Separados por comas. */
  rasgos: string;
  obligatorio: boolean;
}

export interface Borrador {
  nombre: string;
  edad: string;
  pronombres: Pronombres | "";
  rasgos: ElementoBorrador[];
  recuerdos: ElementoBorrador[];
  allegados: AllegadoBorrador[];
  ocasion: Ocasion | "";
  ocasion_detalle: string;
  quien_regala: string;
  mensaje_dedicatoria: string;
  intensidad: Intensidad | "";
  tono: Tono | "";
  subgenero: Subgenero | "";
  capitulos: string;
  /** Separados por comas o saltos de línea. */
  vetados: string;
}

let contador = 0;
export const nuevoId = () => `e${Date.now().toString(36)}${(contador++).toString(36)}`;
export const elementoVacio = (): ElementoBorrador => ({ id: nuevoId(), texto: "", obligatorio: true });
export const allegadoVacio = (): AllegadoBorrador => ({
  id: nuevoId(),
  nombre: "",
  relacion: "",
  rasgos: "",
  obligatorio: true,
});

export const borradorVacio = (): Borrador => ({
  nombre: "",
  edad: "",
  pronombres: "",
  rasgos: [elementoVacio()],
  recuerdos: [elementoVacio()],
  allegados: [],
  ocasion: "",
  ocasion_detalle: "",
  quien_regala: "",
  mensaje_dedicatoria: "",
  intensidad: "",
  tono: "",
  subgenero: "",
  capitulos: String(LIMITES.capitulos.defecto),
  vetados: "",
});

const lista = (texto: string) =>
  texto
    .split(/[,\n]/)
    .map((t) => t.trim())
    .filter(Boolean);

const elementos = (xs: ElementoBorrador[]): ElementoPersonal[] =>
  xs.filter((e) => e.texto.trim()).map((e) => ({ texto: e.texto.trim(), obligatorio: e.obligatorio }));

/** Del borrador al brief. Lo vacío no se envía: que falte lo dice la API, no el cliente. */
export function aBrief(b: Borrador): Brief {
  const edad = Number.parseInt(b.edad, 10);
  const capitulos = Number.parseInt(b.capitulos, 10);
  return {
    destinatario: {
      ...(b.nombre.trim() ? { nombre: b.nombre.trim() } : {}),
      ...(Number.isFinite(edad) ? { edad } : {}),
      ...(b.pronombres ? { pronombres: b.pronombres } : {}),
      rasgos: elementos(b.rasgos),
    },
    recuerdos: elementos(b.recuerdos),
    allegados: b.allegados
      .filter((a) => a.nombre.trim())
      .map((a) => ({
        nombre: a.nombre.trim(),
        relacion: a.relacion.trim(),
        rasgos: lista(a.rasgos),
        obligatorio: a.obligatorio,
      })),
    ...(b.ocasion ? { ocasion: b.ocasion } : {}),
    ...(b.ocasion === "otra" && b.ocasion_detalle.trim() ? { ocasion_detalle: b.ocasion_detalle.trim() } : {}),
    ...(b.quien_regala.trim() ? { quien_regala: b.quien_regala.trim() } : {}),
    ...(b.mensaje_dedicatoria.trim() ? { mensaje_dedicatoria: b.mensaje_dedicatoria.trim() } : {}),
    ...(b.intensidad ? { intensidad: b.intensidad } : {}),
    ...(b.tono ? { tono: b.tono } : {}),
    ...(b.subgenero ? { subgenero: b.subgenero } : {}),
    capitulos: Number.isFinite(capitulos) ? capitulos : LIMITES.capitulos.defecto,
    vetados: lista(b.vetados),
  };
}

/** Errores por campo, con la ruta del backend como clave (`destinatario.edad`, `recuerdos`…). */
export type Errores = Record<string, string[]>;

const agregar = (errores: Errores, campo: string, mensaje: string) => {
  (errores[campo] ??= []).push(mensaje);
};

/**
 * Límites de forma (RF-FE-BRF-04): lo que Pydantic rechazaría como payload mal formado. No mira
 * qué falta ni qué se contradice.
 */
export function erroresDeForma(b: Borrador): Errores {
  const e: Errores = {};
  if (b.nombre.trim().length > LIMITES.nombre) agregar(e, "destinatario.nombre", `Como mucho ${LIMITES.nombre} caracteres.`);
  if (b.edad.trim()) {
    const edad = Number(b.edad);
    if (!Number.isInteger(edad) || edad < LIMITES.edad.min || edad > LIMITES.edad.max) {
      agregar(e, "destinatario.edad", `Un número entero entre ${LIMITES.edad.min} y ${LIMITES.edad.max}.`);
    }
  }
  const rasgos = b.rasgos.filter((x) => x.texto.trim());
  if (rasgos.length > LIMITES.rasgos) agregar(e, "destinatario.rasgos", `Como mucho ${LIMITES.rasgos} rasgos.`);
  if (rasgos.some((x) => x.texto.trim().length > LIMITES.textoElemento)) {
    agregar(e, "destinatario.rasgos", `Cada rasgo, como mucho ${LIMITES.textoElemento} caracteres.`);
  }
  const recuerdos = b.recuerdos.filter((x) => x.texto.trim());
  if (recuerdos.length > LIMITES.recuerdos) agregar(e, "recuerdos", `Como mucho ${LIMITES.recuerdos} recuerdos.`);
  if (recuerdos.some((x) => x.texto.trim().length > LIMITES.textoElemento)) {
    agregar(e, "recuerdos", `Cada recuerdo, como mucho ${LIMITES.textoElemento} caracteres.`);
  }
  const allegados = b.allegados.filter((a) => a.nombre.trim() || a.relacion.trim());
  if (allegados.length > LIMITES.allegados) agregar(e, "allegados", `Como mucho ${LIMITES.allegados} allegados.`);
  for (const a of allegados) {
    if (!a.nombre.trim() || !a.relacion.trim()) agregar(e, "allegados", "Cada allegado necesita nombre y relación.");
    if (a.nombre.trim().length > LIMITES.nombreAllegado || a.relacion.trim().length > LIMITES.relacion) {
      agregar(e, "allegados", `Nombre y relación, como mucho ${LIMITES.nombreAllegado} caracteres.`);
    }
    if (lista(a.rasgos).length > LIMITES.rasgosAllegado) {
      agregar(e, "allegados", `Como mucho ${LIMITES.rasgosAllegado} rasgos por allegado.`);
    }
  }
  if (b.ocasion_detalle.trim().length > LIMITES.ocasionDetalle) agregar(e, "ocasion_detalle", `Como mucho ${LIMITES.ocasionDetalle} caracteres.`);
  if (b.quien_regala.trim().length > LIMITES.quienRegala) agregar(e, "quien_regala", `Como mucho ${LIMITES.quienRegala} caracteres.`);
  if (b.mensaje_dedicatoria.trim().length > LIMITES.mensajeDedicatoria) {
    agregar(e, "mensaje_dedicatoria", `Como mucho ${LIMITES.mensajeDedicatoria} caracteres.`);
  }
  const capitulos = Number(b.capitulos);
  if (!Number.isInteger(capitulos) || capitulos < LIMITES.capitulos.min || capitulos > LIMITES.capitulos.max) {
    agregar(e, "capitulos", `Entre ${LIMITES.capitulos.min} y ${LIMITES.capitulos.max} capítulos.`);
  }
  if (lista(b.vetados).length > LIMITES.vetados) agregar(e, "vetados", `Como mucho ${LIMITES.vetados} términos.`);
  return e;
}

/**
 * Del análisis del servidor a errores por campo. Las contradicciones nombran a veces un elemento
 * concreto («rasgo RAS1», «allegado Nala»): se llevan a su lista.
 */
export function erroresDelAnalisis(analisis: AnalisisBrief): Errores {
  const e: Errores = {};
  for (const campo of analisis.faltantes) agregar(e, campo, "Falta este dato.");
  for (const c of analisis.contradicciones) {
    for (const campo of c.campos) agregar(e, normalizarCampo(campo), c.mensaje);
  }
  return e;
}

export function normalizarCampo(campo: string): string {
  if (campo.startsWith("rasgo ")) return "destinatario.rasgos";
  if (campo.startsWith("recuerdo ")) return "recuerdos";
  if (campo.startsWith("allegado ")) return "allegados";
  return campo;
}

export const PASOS = ["Destinatario", "Su mundo", "El encargo", "El terror", "Revisión"] as const;

const PASO_DE_CAMPO: Record<string, number> = {
  "destinatario.nombre": 0,
  "destinatario.edad": 0,
  "destinatario.pronombres": 0,
  "destinatario.rasgos": 0,
  recuerdos: 1,
  allegados: 1,
  ocasion: 2,
  ocasion_detalle: 2,
  quien_regala: 2,
  mensaje_dedicatoria: 2,
  intensidad: 3,
  tono: 3,
  subgenero: 3,
  capitulos: 3,
  vetados: 3,
};

/** El paso de un campo; uno que el formulario no conoce va a la revisión, donde se ve todo. */
export const pasoDe = (campo: string) => PASO_DE_CAMPO[campo] ?? PASOS.length - 1;

/** El primer paso con errores, o `null`. */
export function primerPasoConErrores(errores: Errores): number | null {
  const pasos = Object.keys(errores).map(pasoDe);
  return pasos.length ? Math.min(...pasos) : null;
}

const CLAVE_BORRADOR = "novelasv2.borrador-brief";

export function leerBorrador(): Borrador {
  try {
    const crudo = localStorage.getItem(CLAVE_BORRADOR);
    return crudo ? { ...borradorVacio(), ...(JSON.parse(crudo) as Partial<Borrador>) } : borradorVacio();
  } catch {
    return borradorVacio();
  }
}

export function guardarBorrador(b: Borrador) {
  try {
    localStorage.setItem(CLAVE_BORRADOR, JSON.stringify(b));
  } catch {
    // Sin almacenamiento, el borrador solo se pierde al recargar.
  }
}

export function borrarBorrador() {
  try {
    localStorage.removeItem(CLAVE_BORRADOR);
  } catch {
    // Nada que borrar.
  }
}
