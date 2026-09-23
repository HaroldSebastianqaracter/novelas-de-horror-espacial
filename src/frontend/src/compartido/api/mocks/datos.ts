/**
 * Datos ficticios para MSW. Tipados contra el esquema generado, así que un cambio del
 * contrato rompe la compilación aquí antes que en una pantalla (RF-FE-API-03).
 * Títulos inventados; ningún nombre de persona real.
 */
import type { Capitulo, Ejecucion, NovelaDetalle, NovelaResumen, Parada } from "../tipos";

/** Como las da la API: UTC sin zona, «2026-09-23 15:44:20». */
export const fechaApi = (ms = Date.now()) => new Date(ms).toISOString().slice(0, 19).replace("T", " ");
const hace = (minutos: number) => fechaApi(Date.now() - minutos * 60_000);

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
  6: { novela_id: 6, estado: "completada_con_avisos", fase: null, capitulo_actual: 11, intento_actual: 1, capitulos_completados: 10, total_capitulos: 10, parada_abierta_id: null, ultimo_error: null, actualizado_en: hace(19000) },
};

const OBJETIVOS = [
  "La tripulación descubre que la baliza de socorro emite desde dentro de la nave.",
  "Revisar la bodega once sin despertar a lo que respira en el conducto.",
  "Restablecer el soporte vital antes de que se agote el turno de guardia.",
  "Convencer a la capitana de que el registro del ordenador miente.",
  "Sellar el módulo de cultivos con alguien todavía dentro.",
  "Encontrar el traje que falta en el inventario.",
];

function capitulos(total: number, completados: number): Capitulo[] {
  return Array.from({ length: total }, (_, i) => ({
    numero: i + 1,
    estado: i < completados ? "completado" : "planificado",
    objetivo: OBJETIVOS[i % OBJETIVOS.length] ?? null,
    resumen: null,
    escenas: [],
  }));
}

/** Capítulos por novela: la 1 todavía no tiene estructura. */
export const capitulosDe: Record<number, Capitulo[]> = {
  1: [],
  2: capitulos(8, 3),
  3: capitulos(10, 5),
  4: capitulos(6, 2),
  5: capitulos(10, 4),
  6: capitulos(10, 10),
};

const RESTRICCIONES: Record<string, string> = {
  longitud_objetivo_palabras: "12500",
  longitud_capitulo_palabras: "1000-1500",
  capitulos: "10",
  publico: "Adulto; terror con tensión, sin violencia gráfica",
  pov_por_defecto: "tercera_limitada",
  tiempo_verbal: "pasado",
};

export function detalleDe(id: number): NovelaDetalle | undefined {
  const resumen = novelas.find((n) => n.id === id);
  if (!resumen) return undefined;
  const planificada = (capitulosDe[id]?.length ?? 0) > 0;
  return {
    novela: {
      id,
      titulo: resumen.titulo,
      genero: resumen.genero,
      creado_en: resumen.creado_en,
      subgenero_dominante: resumen.subgenero_dominante ?? null,
      logline: planificada
        ? "Una tripulación de carguero descubre que la señal que persigue no viene de fuera, sino de su propia bodega."
        : null,
      premisa: planificada ? "El miedo a lo que se lleva dentro, puesto en una nave que no se puede abandonar." : null,
    },
    restricciones: RESTRICCIONES,
    estilo: null,
  };
}

const ESCENAS = [
  [
    "La bodega olía a óxido y a algo más dulce, algo que no debería estar ahí. La ingeniera se detuvo junto al contenedor once y escuchó.",
    "Nada. Solo el zumbido del soporte vital y, debajo, muy debajo, un ritmo que no era el de las bombas.",
  ],
  [
    "En el puente, el piloto repasaba el registro por tercera vez. Las horas no cuadraban: faltaban once minutos entre la última guardia y el aviso de la baliza.",
    "—El ordenador no se equivoca —dijo la capitana, sin apartar la vista del casco.",
    "—Entonces alguien le ha enseñado a mentir.",
  ],
  [
    "Cuando volvieron a la bodega, el contenedor once estaba abierto desde dentro.",
  ],
];

/** El texto compilado de un capítulo cerrado, con las escenas unidas como las une `compilar`. */
export function textoDe(novelaId: number, numero: number): string | undefined {
  const capitulo = capitulosDe[novelaId]?.find((c) => c.numero === numero);
  if (capitulo?.estado !== "completado") return undefined;
  return ESCENAS.map((parrafos) => parrafos.join("\n\n")).join("\n\n* * *\n\n");
}

/** La parada abierta de la novela 4: continuidad, con un choque de hechos y uno de conocimiento. */
export const paradas: Record<number, Parada> = {
  93: {
    id: 93,
    tipo: "continuidad",
    estado: "abierta",
    capitulo: 3,
    intento: 1,
    resolucion: null,
    creado_en: hace(45),
    informe: {
      puerta: 3,
      veredicto: "falla",
      conflictos: [
        {
          comprobacion: "continuidad_factual",
          descripcion: "El traje de la ingeniera cambia de color entre el capítulo 1 y el 3 sin que el texto lo explique.",
          aviso: false,
          capitulo: 3,
          escena_id: 31,
          datos: {
            hecho_nuevo_id: 412,
            hecho_previo_id: 118,
            sujeto_nombre: "traje de la ingeniera",
            atributo: "color",
            valor_nuevo: "naranja",
            valor_previo: "gris",
            cita_nueva: "El naranja del traje era lo único que se veía en la bodega.",
            cita_previa: "Se enfundó el traje gris, todavía con el polvo de la última salida.",
            capitulo_nuevo: 3,
            capitulo_previo: 1,
          },
        },
        {
          comprobacion: "conocimiento_no_adquirido",
          descripcion: "El piloto usa el código de la esclusa norte, pero ninguna escena cuenta que lo aprendiera.",
          aviso: false,
          capitulo: 3,
          escena_id: 32,
          datos: { personaje: "el piloto", hecho: "código de la esclusa norte", hecho_id: 97, personaje_id: 4 },
        },
        {
          comprobacion: "palabras_filtro",
          descripcion: "«De repente» aparece cuatro veces en la escena 2.",
          aviso: true,
          capitulo: 3,
          escena_id: 32,
          datos: {},
        },
      ],
      prosa_rechazada: {
        "1": "La bodega olía a óxido y a algo más dulce, algo que no debería estar ahí.\n\nEl naranja del traje era lo único que se veía en la bodega.",
        "2": "De repente, el piloto tecleó el código de la esclusa norte sin mirar el panel.",
      },
    },
  },
};

const novelasIniciales = structuredClone(novelas);
const ejecucionesIniciales = structuredClone(ejecuciones);
const capitulosIniciales = structuredClone(capitulosDe);
const paradasIniciales = structuredClone(paradas);

/** Deshace lo que las intenciones simuladas cambiaron. Los tests lo llaman entre caso y caso. */
export function restaurarDatos() {
  novelas.splice(0, novelas.length, ...structuredClone(novelasIniciales));
  for (const id of Object.keys(ejecuciones)) delete ejecuciones[Number(id)];
  Object.assign(ejecuciones, structuredClone(ejecucionesIniciales));
  Object.assign(capitulosDe, structuredClone(capitulosIniciales));
  Object.assign(paradas, structuredClone(paradasIniciales));
}
