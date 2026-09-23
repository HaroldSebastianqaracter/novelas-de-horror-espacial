/* ==========================================================================
   novelasv2 · datos ficticios del prototipo
   Imitan lo que devolverían los endpoints del backend (novelas, ejecuciones,
   capítulos cerrados, paradas). Todos los títulos y personajes son inventados.
   Nombres de estados y fases idénticos a los del backend.
   ========================================================================== */
(function () {
  "use strict";

  /* Catálogos del dominio (fuente única para app.js) */
  const ESTADOS = [
    "configurada", "planificando", "escaletando", "generando", "parada",
    "detenida", "completada", "completada_con_avisos", "error"
  ];
  const FASES = [
    "arquitecto", "mundo", "elenco", "estructura", "puerta_1", "escaleta", "puerta_2",
    "paquete", "redaccion", "extraccion", "puerta_3", "puerta_4", "puerta_5", "ninguna"
  ];

  /* ---------- Títulos de capítulos cerrados ---------- */
  const TITULOS = {
    "exp-0409": ["Señal de rumbo", "El casco canta", "Inventario de bodega", "Guardia de tercera",
      "Lo que respira en el conducto", "Reloj de a bordo"],
    "exp-0412": ["Perforación", "Bajo la plataforma", "El cuerpo en el pozo"],
    "exp-0407": ["Contacto perdido", "Protocolo de abordaje", "La cubierta de carga", "Luces de reserva",
      "Diario del segundo oficial", "Veintitrés contenedores", "Lo que había en el once", "Presión",
      "Nadie en el puente", "Rumbo automático"],
    "exp-0398": ["Anillo en calma", "Doce tazas", "Registro de actividad", "Once minutos",
      "El muelle tres", "Rotación", "Gravedad de mano", "La sala de cultivos", "Voces en el intercomunicador",
      "Inventario de trajes", "El módulo sellado", "Lo que dice el ordenador", "Noche de estación",
      "Esclusa norte", "El décimo tercero", "Contención", "Fuera del anillo", "Deriva",
      "El eje central", "Señal de relevo", "La última vuelta", "Silencio"]
  };

  /* Avisos no bloqueantes que emiten las puertas (se muestran en capítulos cerrados) */
  const AVISOS = {
    "exp-0409": { 3: ["Repetición léxica: «oscuridad» ×11 en la escena 2."],
                  5: ["La escena 3 supera el máximo de palabras (1.910 / 1.600)."] },
    "exp-0407": { 4: ["Deriva de punto de vista en el párrafo 12 (tercera limitada → omnisciente)."] },
    "exp-0398": { 4: ["Ritmo: dos escenas consecutivas sin conflicto."],
                  9: ["Repetición léxica: «silencio» ×14 en el capítulo.", "Diálogo sin atribución en la escena 2."],
                  15: ["Personaje secundario sin nombrar en ficha: «el técnico del muelle»."],
                  21: ["La escena 1 queda por debajo del mínimo de palabras (640 / 900)."] }
  };

  function palabrasDe(id, n) {
    // Pseudoaleatorio estable para que el prototipo no cambie en cada carga
    let h = 2166136261; const s = id + ":" + n;
    for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; }
    return 2900 + (h % 1500);
  }

  function capitulosCerrados(id) {
    return (TITULOS[id] || []).map((titulo, i) => ({
      numero: i + 1,
      titulo,
      palabras: palabrasDe(id, i + 1),
      escenas: 3 + ((i + id.length) % 2),
      avisos: (AVISOS[id] && AVISOS[id][i + 1]) || []
    }));
  }

  /* ---------- Texto del lector ---------- */
  // Capítulos escritos a mano. El resto se compone con el banco de párrafos (marcado como relleno).
  const TEXTOS = {
    "exp-0409:1": [
      ["El Kessler-9 llevaba doscientos once días sin ver otra luz que la suya. Nadia Vero lo sabía porque lo contaba: cada turno, al entrar en el puente, rascaba una muesca en el borde de la consola con la uña del pulgar. La tripulación había dejado de preguntar por qué.",
       "A las 03:40 de a bordo, el receptor de largo alcance emitió un tono único, grave, y se calló. No era una baliza. Las balizas repiten. Aquello sonó una vez, como alguien que llama a una puerta y se arrepiente.",
       "—Repítelo —dijo Vero, sin levantar la voz. El ordenador reprodujo el registro. Cuatro segundos de estática y, en mitad, una caída de tono que se parecía demasiado a una respiración."],
      ["En la cocina, Ilya Brandt calentaba café recuperado por tercera vez. Escuchó el informe con la taza entre las manos, sin beber.",
       "—Puede ser un eco nuestro —dijo—. El casco rebota cosas. Lo hemos visto antes.",
       "—No lo hemos visto antes —respondió Vero—. Lo hemos oído antes. No es lo mismo.",
       "Nadie contestó. Afuera, al otro lado de treinta centímetros de aleación y aislante, no había nada durante millones de kilómetros. Eso era lo que decía el radar. Eso era lo que el radar había dicho siempre."],
      ["Vero corrigió el rumbo dos grados hacia la fuente estimada. Lo hizo sola, a mano, y no lo anotó en el diario.",
       "Más tarde, cuando le preguntaran, diría que fue el procedimiento. Que una señal sin identificar exige verificación. Que el carguero tenía combustible de sobra.",
       "No diría que, mientras giraba la rueda de trimado, había sentido que algo al otro lado giraba con ella."]
    ],
    "exp-0409:2": [
      ["El sonido empezó en la cubierta inferior, a la altura de la bodega dos. No era un golpe ni un chirrido: era una nota sostenida, casi musical, que subía por las cuadernas y se metía en los dientes.",
       "Brandt apoyó la palma contra el mamparo. Vibraba.",
       "—Dilatación térmica —dijo, y sonó como alguien que repite una oración en la que ya no cree."],
      ["El diagnóstico estructural no encontró nada. Ni fisuras, ni presión anómala, ni temperaturas fuera de rango. El casco estaba entero. El casco cantaba.",
       "Teo Asgard, el más joven, grabó el sonido con su terminal y lo pasó por el analizador de frecuencia. Lo hizo tres veces. Las tres veces, el patrón coincidía con el tono del receptor. Las tres veces decidió no enseñárselo a nadie."],
      ["Esa noche nadie durmió en su litera. Arrastraron los colchones hasta la cocina, bajo la única luz que no parpadeaba, y fingieron que era por el frío.",
       "A las 03:40 exactas, la nota se detuvo. El silencio que dejó era peor. Era el silencio de algo que ha terminado de afinar."]
    ],
    "exp-0398:1": [
      ["La estación Hesperia giraba como siempre, una vuelta cada noventa segundos, y como siempre la gravedad del anillo exterior tiraba de los tobillos con la suavidad de una mano conocida. Lo extraño no era el giro. Lo extraño era que nadie contestaba.",
       "La lanzadera de relevo se acopló en el muelle tres sin incidencias. Las luces de bienvenida estaban encendidas. El café de la sala de control estaba caliente. Doce tripulantes registrados; doce tazas sobre la mesa."],
      ["Mara Okafor recorrió el anillo entero con la linterna apagada, porque no hacía falta: todo estaba iluminado. Las camas, hechas. Las esclusas, cerradas por dentro. El registro de actividad marcaba movimiento continuo en todos los módulos —pasos, puertas, voces— hasta once minutos antes de su llegada.",
       "Luego, nada. Ni una puerta. Ni un paso. Como si la estación hubiera contenido el aliento al verla llegar."],
      ["Volvió a la sala de control y se sentó frente a las doce tazas. Una a una, las tocó con el dorso de los dedos.",
       "Todas estaban calientes. Todas a la misma temperatura. Como si alguien acabara de servirlas, hacía un momento, para doce personas que iban a volver enseguida."]
    ]
  };

  const BANCO_PARRAFOS = [
    "Las luces de emergencia tiñeron el pasillo de un ámbar sucio. Alguien había dejado una bota junto a la esclusa, de pie, perfectamente alineada con la marca del suelo.",
    "El ordenador de a bordo repitió la hora dos veces. La segunda vez, la voz llegó un poco más tarde de lo que debía.",
    "Nadie recordaba haber cerrado la compuerta de la bodega. El registro decía que se había cerrado desde dentro.",
    "El frío no venía del casco. Venía del conducto de ventilación, y olía a metal mojado, a algo que no debería haber estado nunca a bordo.",
    "Contaron a la tripulación en voz alta, uno por uno, y el número salió bien. Lo repitieron por si acaso. Salió bien otra vez. Eso no tranquilizó a nadie.",
    "En la pantalla de navegación, el punto que marcaba su posición temblaba, como si la nave no terminara de decidir dónde estaba.",
    "El silencio entre dos zumbidos del reciclador duraba ahora un segundo más. Lo habían medido. Llevaban tres días midiéndolo.",
    "Encontraron el diario de la guardia anterior abierto sobre la consola. La última línea estaba escrita con otra letra.",
    "La esclusa completó el ciclo sin que nadie lo hubiera ordenado. Cuando llegaron, la cámara estaba vacía y el suelo, húmedo.",
    "Durante la cena, alguien dejó de hablar a mitad de frase y miró hacia el techo. Los demás siguieron comiendo, sin preguntar, como se aprende a hacer.",
    "Las cámaras de la cubierta inferior mostraban el pasillo vacío. El sensor de movimiento, en cambio, contaba pasos: lentos, regulares, de ida y vuelta.",
    "Por la ventanilla del observatorio no se veía nada. Esa era la parte que más costaba explicar: no había estrellas donde debía haberlas."
  ];

  function textoCapitulo(novelaId, numero, nEscenas) {
    const clave = novelaId + ":" + numero;
    if (TEXTOS[clave]) return { escenas: TEXTOS[clave], relleno: false };
    let h = 7;
    for (const c of clave) h = (h * 33 + c.charCodeAt(0)) >>> 0;
    const escenas = [];
    for (let e = 0; e < (nEscenas || 3); e++) {
      const parrafos = [];
      for (let p = 0; p < 3; p++) parrafos.push(BANCO_PARRAFOS[(h + e * 5 + p * 7) % BANCO_PARRAFOS.length]);
      escenas.push(parrafos);
    }
    return { escenas, relleno: true };
  }

  /* ---------- Semilla del servidor simulado ---------- */
  function semilla() {
    const ahora = Date.now();
    const hace = (seg) => new Date(ahora - seg * 1000).toISOString();

    const novelas = [
      {
        id: "exp-0409", codigo: "EXP-0409", titulo: "La deriva del Kessler-9",
        genero: "terror espacial", longitud_objetivo_palabras: 64000,
        longitud_capitulo_palabras: { min: 3000, max: 4200 }, publico: "Adulto",
        politica_contenido: "Violencia sugerida, sin gore explícito.",
        pov_por_defecto: "tercera_limitada", tiempo_verbal: "pasado",
        semilla_premisa: "Un carguero minero capta una señal que suena como una respiración y su capitana corrige el rumbo sin decírselo a nadie.",
        capitulos_total: 18, creada_en: hace(86400 * 2)
      },
      {
        id: "exp-0412", codigo: "EXP-0412", titulo: "Ecos bajo el hielo de Encélado",
        genero: "terror espacial", longitud_objetivo_palabras: 56000,
        longitud_capitulo_palabras: { min: 3000, max: 3800 }, publico: "Adulto",
        politica_contenido: "", pov_por_defecto: "primera", tiempo_verbal: "presente",
        semilla_premisa: "Una base de perforación bajo la corteza helada recibe llamadas por radio desde el fondo del pozo.",
        capitulos_total: 16, creada_en: hace(86400 * 1.5)
      },
      {
        id: "exp-0407", codigo: "EXP-0407", titulo: "Carguero Tántalo, sin respuesta",
        genero: "terror espacial", longitud_objetivo_palabras: 72000,
        longitud_capitulo_palabras: null, publico: "Adulto joven y adulto",
        politica_contenido: "Sin violencia contra animales.", pov_por_defecto: "tercera_limitada",
        tiempo_verbal: "pasado",
        semilla_premisa: "Un equipo de salvamento aborda un carguero que lleva dos años en rumbo automático.",
        capitulos_total: 20, creada_en: hace(86400 * 4)
      },
      {
        id: "exp-0398", codigo: "EXP-0398", titulo: "Silencio en el anillo Hesperia",
        genero: "terror espacial", longitud_objetivo_palabras: 80000,
        longitud_capitulo_palabras: { min: 3200, max: 4000 }, publico: "Adulto",
        politica_contenido: "", pov_por_defecto: "omnisciente", tiempo_verbal: "pasado",
        semilla_premisa: "El relevo llega a una estación orbital en perfecto estado donde no queda nadie.",
        capitulos_total: 22, creada_en: hace(86400 * 9)
      },
      {
        id: "exp-0414", codigo: "EXP-0414", titulo: "Los que duermen en la bodega 4",
        genero: "terror espacial", longitud_objetivo_palabras: 50000,
        longitud_capitulo_palabras: null, publico: "", politica_contenido: "",
        pov_por_defecto: "tercera_limitada", tiempo_verbal: "pasado",
        semilla_premisa: "Las cápsulas de hibernación de una nave colonial se abren una por una, pero siempre falta alguien.",
        capitulos_total: null, creada_en: hace(1500)
      },
      {
        id: "exp-0410", codigo: "EXP-0410", titulo: "Órbita de cementerio",
        genero: "terror espacial", longitud_objetivo_palabras: 60000,
        longitud_capitulo_palabras: null, publico: "Adulto", politica_contenido: "",
        pov_por_defecto: "objetiva", tiempo_verbal: "presente", semilla_premisa: "",
        capitulos_total: null, creada_en: hace(86400 * 3)
      }
    ];

    const ejecuciones = {
      "exp-0409": { novela_id: "exp-0409", estado: "generando", fase: "redaccion", capitulo_actual: 7,
        intento_actual: 2, capitulos_completados: 6, parada_abierta_id: null, ultimo_error: null, actualizado_en: hace(14) },
      "exp-0412": { novela_id: "exp-0412", estado: "parada", fase: "puerta_3", capitulo_actual: 4,
        intento_actual: 3, capitulos_completados: 3, parada_abierta_id: "P-0093", ultimo_error: null, actualizado_en: hace(660) },
      "exp-0407": { novela_id: "exp-0407", estado: "error", fase: "extraccion", capitulo_actual: 11,
        intento_actual: 3, capitulos_completados: 10, parada_abierta_id: null,
        ultimo_error: "extraccion · cap. 11 · intento 3/3: el agente de extracción devolvió un canon inválido (campo «ubicacion» ausente en 3 entidades). Reintentos agotados.",
        actualizado_en: hace(7400) },
      "exp-0398": { novela_id: "exp-0398", estado: "completada_con_avisos", fase: "ninguna", capitulo_actual: null,
        intento_actual: 1, capitulos_completados: 22, parada_abierta_id: null, ultimo_error: null, actualizado_en: hace(86400 * 3) },
      "exp-0414": { novela_id: "exp-0414", estado: "configurada", fase: "ninguna", capitulo_actual: null,
        intento_actual: 1, capitulos_completados: 0, parada_abierta_id: null, ultimo_error: null, actualizado_en: hace(1500) },
      "exp-0410": { novela_id: "exp-0410", estado: "detenida", fase: "elenco", capitulo_actual: null,
        intento_actual: 1, capitulos_completados: 0, parada_abierta_id: null, ultimo_error: null, actualizado_en: hace(86400 * 1.1) }
    };

    const capitulos = {};
    for (const n of novelas) capitulos[n.id] = capitulosCerrados(n.id);

    const paradas = {
      "P-0093": {
        id: "P-0093", novela_id: "exp-0412", capitulo: 4, escena: 3, fase: "puerta_3",
        detectada_en: hace(660), gravedad: "bloqueante", intentos_consumidos: 3,
        conflicto: "Contradicción de canon · estado de personaje",
        resumen: "El borrador del capítulo 4 hace hablar por radio a HALVARD, IDUN. El canon la registra como fallecida desde el capítulo 2. La puerta 3 rechazó los tres intentos de redacción por el mismo motivo.",
        texto: {
          ubicacion: "Cap. 4 · escena 3 · párrafo 7",
          cita: "La radio chasquea y la voz de Halvard llega limpia, sin estática: «Estoy en el pozo tres. Abridme. Hace frío aquí abajo». Nadie se mueve. Yo tampoco."
        },
        canon: {
          ubicacion: "Canon · elenco · ficha HALVARD, IDUN · establecido en cap. 2, escena 4",
          cita: "Ingeniera de perforación. Estado: FALLECIDA. Cae por la grieta bajo la plataforma durante la tormenta; el cuerpo se recupera en el capítulo 3."
        }
      }
    };

    return { novelas, ejecuciones, capitulos, paradas, secuencia: 415, secuenciaParada: 94 };
  }

  window.NV_DATOS = {
    ESTADOS, FASES, semilla, textoCapitulo, BANCO_PARRAFOS,
    TITULOS_EXTRA: ["Esclusa B", "Presión diferencial", "Lo que queda en la bodega", "Turno de noche",
      "El segundo tono", "Cuaderna 40", "Oxígeno de reserva", "Hablar con el casco", "Deriva",
      "La luz de la sonda", "Rumbo de colisión", "Nadie firma el diario", "Última guardia"],
    AVISOS_EXTRA: ["Repetición léxica por encima del umbral en la escena 2.",
      "La escena 1 supera el máximo de palabras.", "Diálogo sin atribución en la escena 3."]
  };
})();
