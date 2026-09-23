/* ==========================================================================
   novelasv2 · prototipo navegable · PROPUESTA B (papel técnico)
   - Rutas hash, render de pantallas, arrastre con reglas, menú contextual.
   - Servidor simulado (sustituye a FastAPI) y panel de simulación.
   Principio rector: la interfaz NUNCA cambia el estado por su cuenta. Envía
   una intención, la marca como pendiente y repinta cuando el servidor confirma.
   ========================================================================== */
(function () {
  "use strict";

  const D = window.NV_DATOS;

  /* ------------------------------------------------------------------------
     1. Utilidades
     ------------------------------------------------------------------------ */
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const esc = (v) => String(v == null ? "" : v).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const num = (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  const dos = (n) => String(n).padStart(2, "0");
  const hora = (t) => { const d = new Date(t); return `${dos(d.getHours())}:${dos(d.getMinutes())}:${dos(d.getSeconds())}`; };
  const recortar = (s, n) => (s && s.length > n ? s.slice(0, n - 1) + "…" : s || "");
  const movimientoReducido = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Propuesta B: los mensajes del sistema se muestran en frase normal, no en mayúsculas.
  function frase(s) {
    let t = String(s || "").toLowerCase();
    t = t.replace(/[a-záéíóúñ]/, (c) => c.toUpperCase());
    t = t.replace(/([.·]\s+)([a-záéíóúñ])/g, (m, a, b) => a + b.toUpperCase());
    return t.replace(/\b(exp|p)-(\d+)/g, (m) => m.toUpperCase());
  }

  function haceX(iso) {
    const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
    if (s < 5) return "ahora";
    if (s < 60) return `hace ${s} s`;
    if (s < 3600) return `hace ${Math.floor(s / 60)} min`;
    if (s < 86400) return `hace ${Math.floor(s / 3600)} h`;
    return `hace ${Math.floor(s / 86400)} d`;
  }

  const almacen = {
    leer(k, def) { try { const v = localStorage.getItem(k); return v == null ? def : v; } catch (e) { return def; } },
    escribir(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* sin almacenamiento: se ignora */ } }
  };

  /* ------------------------------------------------------------------------
     2. Vocabulario del dominio (códigos exactos → etiquetas humanas)
     ------------------------------------------------------------------------ */
  const ESTADO = {
    configurada: "Configurada", planificando: "Planificando", escaletando: "Escaletando",
    generando: "Generando", parada: "Parada", detenida: "Detenida", completada: "Completada",
    completada_con_avisos: "Completada con avisos", error: "Error"
  };
  // El icono acompaña siempre al color: el estado nunca depende solo del tono.
  const ICONO = {
    configurada: "○", planificando: "◐", escaletando: "◑", generando: "●", parada: "■",
    detenida: "‖", completada: "✓", completada_con_avisos: "▲", error: "✕"
  };
  const FASE = {
    arquitecto: "Arquitecto", mundo: "Mundo", elenco: "Elenco", estructura: "Estructura",
    puerta_1: "Puerta 1", escaleta: "Escaleta", puerta_2: "Puerta 2", paquete: "Paquete",
    redaccion: "Redacción", extraccion: "Extracción", puerta_3: "Puerta 3", puerta_4: "Puerta 4",
    puerta_5: "Puerta 5", ninguna: "—"
  };
  const POV = {
    primera: "Primera persona", tercera_limitada: "Tercera persona limitada",
    omnisciente: "Narrador omnisciente", objetiva: "Objetiva (cámara externa)"
  };
  const TIEMPO = { pasado: "Pasado", presente: "Presente" };
  const INTENCION = {
    arrancar: "Arrancar", parar: "Parar", relanzar: "Relanzar",
    resolver_parada: "Resolver parada", crear_novela: "Crear novela"
  };
  const ACTIVOS = ["planificando", "escaletando", "generando"];
  const FASES_PLAN = ["arquitecto", "mundo", "elenco", "estructura", "puerta_1", "escaleta", "puerta_2"];
  const FASES_CAP = ["paquete", "redaccion", "extraccion", "puerta_3", "puerta_4"];

  const COLUMNAS = [
    { id: "espera", codigo: "01", nombre: "En espera", estados: ["configurada", "detenida"] },
    { id: "planificando", codigo: "02", nombre: "Planificando", estados: ["planificando", "escaletando"] },
    { id: "escribiendo", codigo: "03", nombre: "Escribiendo", estados: ["generando"] },
    { id: "terminada", codigo: "04", nombre: "Terminada", estados: ["completada", "completada_con_avisos"] }
  ];
  const CARRIL_ATENCION = { id: "atencion", nombre: "Requiere atención", estados: ["parada", "error"] };
  const columnaDe = (estado) => {
    if (CARRIL_ATENCION.estados.includes(estado)) return "atencion";
    return (COLUMNAS.find((c) => c.estados.includes(estado)) || COLUMNAS[0]).id;
  };
  // Únicas transiciones que el arrastre puede pedir. Todo lo demás está bloqueado.
  const TRANSICIONES = {
    "espera>planificando": "arrancar",
    "planificando>espera": "parar",
    "escribiendo>espera": "parar"
  };

  /* ------------------------------------------------------------------------
     3. SERVIDOR SIMULADO — sustituye al backend. La interfaz solo lo toca
        mediante consultar() y procesar(intención).
     ------------------------------------------------------------------------ */
  const Servidor = (function () {
    let db = D.semilla();
    const oyentes = [];
    const opciones = { latencia: 1500, retener: false, rechazarProxima: false };
    const clonar = (o) => JSON.parse(JSON.stringify(o));
    const ahoraISO = () => new Date().toISOString();
    const novela = (id) => db.novelas.find((n) => n.id === id);
    const activa = () => Object.values(db.ejecuciones).find((e) => ACTIVOS.includes(e.estado)) || null;
    const notificar = (ev) => oyentes.forEach((f) => f(ev));
    const tocar = (e) => { e.actualizado_en = ahoraISO(); };
    const rechazo = (motivo, campo) => ({ aceptada: false, motivo, campo });

    function reanudar(e) {
      if (e.estado === "configurada" || e.fase === "ninguna") {
        if (e.capitulos_completados > 0) {
          e.estado = "generando"; e.fase = "paquete"; e.capitulo_actual = e.capitulos_completados + 1;
        } else { e.estado = "planificando"; e.fase = "arquitecto"; }
        e.intento_actual = 1;
      } else if (FASES_PLAN.includes(e.fase)) {
        e.estado = FASES_PLAN.indexOf(e.fase) >= 5 ? "escaletando" : "planificando";
      } else {
        e.estado = "generando";
      }
    }

    function relanzarDesde(e, desde) {
      const n = novela(e.novela_id);
      e.parada_abierta_id = null; e.ultimo_error = null; e.intento_actual = 1;
      if (!n.capitulos_total || !desde) {
        db.capitulos[e.novela_id] = [];
        e.capitulos_completados = 0; e.capitulo_actual = null;
        e.estado = "planificando"; e.fase = "arquitecto";
        return;
      }
      db.capitulos[e.novela_id] = (db.capitulos[e.novela_id] || []).filter((c) => c.numero < desde);
      e.capitulos_completados = desde - 1; e.capitulo_actual = desde;
      e.estado = "generando"; e.fase = "paquete";
    }

    function crear(datos) {
      const titulo = (datos.titulo || "").trim();
      if (!titulo) return rechazo("TÍTULO REQUERIDO.", "titulo");
      if (db.novelas.some((n) => n.titulo.trim().toLowerCase() === titulo.toLowerCase()))
        return rechazo("YA EXISTE UNA NOVELA CON ESE TÍTULO.", "titulo");
      if (!Number.isInteger(datos.longitud_objetivo_palabras) || datos.longitud_objetivo_palabras <= 0)
        return rechazo("LONGITUD OBJETIVO NO VÁLIDA.", "longitud_objetivo_palabras");
      const id = "exp-0" + (++db.secuencia);
      db.novelas.push(Object.assign({ id, codigo: id.toUpperCase(), genero: "terror espacial",
        capitulos_total: null, creada_en: ahoraISO() }, datos, { titulo }));
      db.ejecuciones[id] = { novela_id: id, estado: "configurada", fase: "ninguna", capitulo_actual: null,
        intento_actual: 1, capitulos_completados: 0, parada_abierta_id: null, ultimo_error: null, actualizado_en: ahoraISO() };
      db.capitulos[id] = [];
      return { aceptada: true, novela_id: id };
    }

    function procesar(int) {
      if (opciones.rechazarProxima) {
        opciones.rechazarProxima = false; notificar({ origen: "opciones" });
        return rechazo("EL SERVIDOR RECHAZÓ LA INTENCIÓN (FORZADO DESDE SIMULACIÓN).");
      }
      if (int.tipo === "crear_novela") {
        const r = crear(int.datos);
        if (r.aceptada) notificar({ origen: "intencion" });
        return r;
      }
      const e = db.ejecuciones[int.novela_id];
      if (!e) return rechazo("NOVELA DESCONOCIDA.");
      const ocupa = activa();
      const ocupadaPorOtra = ocupa && ocupa.novela_id !== e.novela_id;
      const motivoRanura = ocupa ? `RANURA OCUPADA: ${novela(ocupa.novela_id).codigo} ESTÁ EN CURSO. SOLO SE GENERA UNA NOVELA A LA VEZ.` : "";

      switch (int.tipo) {
        case "arrancar":
          if (!["configurada", "detenida"].includes(e.estado)) return rechazo(`EL ESTADO «${e.estado}» NO ADMITE ARRANQUE.`);
          if (ocupadaPorOtra) return rechazo(motivoRanura);
          reanudar(e); break;
        case "parar":
          if (!ACTIVOS.includes(e.estado)) return rechazo("LA EJECUCIÓN NO ESTÁ EN CURSO.");
          e.estado = "detenida"; break;
        case "relanzar":
          if (ACTIVOS.includes(e.estado)) return rechazo("DETÉN LA EJECUCIÓN ANTES DE RELANZAR.");
          if (ocupadaPorOtra) return rechazo(motivoRanura);
          relanzarDesde(e, int.desde_capitulo); break;
        case "resolver_parada": {
          if (e.estado !== "parada") return rechazo("NO HAY PARADA ABIERTA PARA ESTA NOVELA.");
          if (ocupadaPorOtra) return rechazo(motivoRanura);
          const p = db.paradas[e.parada_abierta_id];
          if (p) p.resuelta = int.accion;
          if (int.accion === "relanzar") relanzarDesde(e, int.desde_capitulo);
          else {
            e.parada_abierta_id = null;
            const enPlan = FASES_PLAN.includes(e.fase);
            e.estado = enPlan ? (FASES_PLAN.indexOf(e.fase) >= 5 ? "escaletando" : "planificando") : "generando";
            if (int.accion === "aceptar_retcon") { e.fase = enPlan ? e.fase : "puerta_4"; }
            else { e.fase = enPlan ? e.fase : "paquete"; e.intento_actual = 1; } // rehacer
          }
          break;
        }
        default: return rechazo("INTENCIÓN DESCONOCIDA.");
      }
      tocar(e);
      notificar({ origen: "intencion", novela_id: e.novela_id });
      return { aceptada: true };
    }

    /* --- Avance del pipeline (lo que en producción hace el backend solo) --- */
    function cerrarCapitulo(e) {
      const n = novela(e.novela_id);
      const numero = e.capitulo_actual;
      const lista = db.capitulos[e.novela_id] || (db.capitulos[e.novela_id] = []);
      lista.push({
        numero,
        titulo: D.TITULOS_EXTRA[(numero + n.titulo.length) % D.TITULOS_EXTRA.length],
        palabras: 2900 + ((numero * 977) % 1400),
        escenas: 3,
        avisos: numero % 4 === 0 ? [D.AVISOS_EXTRA[numero % D.AVISOS_EXTRA.length]] : []
      });
      e.capitulos_completados = numero;
      if (numero >= n.capitulos_total) { e.fase = "puerta_5"; e.capitulo_actual = null; }
      else { e.capitulo_actual = numero + 1; e.fase = "paquete"; e.intento_actual = 1; }
    }

    function avanzar() {
      const e = activa();
      if (!e) return "NO HAY EJECUCIÓN EN CURSO.";
      const n = novela(e.novela_id);
      if (e.estado === "planificando" || e.estado === "escaletando") {
        const i = FASES_PLAN.indexOf(e.fase);
        if (e.fase === "estructura" && !n.capitulos_total) {
          const media = n.longitud_capitulo_palabras ? (n.longitud_capitulo_palabras.min + n.longitud_capitulo_palabras.max) / 2 : 3500;
          n.capitulos_total = Math.max(6, Math.round(n.longitud_objetivo_palabras / media));
        }
        if (e.fase === "puerta_2") {
          e.estado = "generando"; e.fase = "paquete"; e.capitulo_actual = e.capitulos_completados + 1; e.intento_actual = 1;
        } else {
          e.fase = FASES_PLAN[i + 1] || "arquitecto";
          if (e.fase === "escaleta") e.estado = "escaletando";
        }
      } else if (e.fase === "puerta_5") {
        const conAvisos = (db.capitulos[e.novela_id] || []).some((c) => c.avisos.length);
        e.estado = conAvisos ? "completada_con_avisos" : "completada"; e.fase = "ninguna"; e.capitulo_actual = null;
      } else if (e.fase === "puerta_4") {
        cerrarCapitulo(e);
      } else {
        e.fase = FASES_CAP[FASES_CAP.indexOf(e.fase) + 1] || "paquete";
      }
      tocar(e); notificar({ origen: "pipeline", novela_id: e.novela_id });
      return `${n.codigo} → ${e.estado} · ${e.fase}${e.capitulo_actual ? " · cap. " + e.capitulo_actual : ""}`;
    }

    function reintento() {
      const e = activa();
      if (!e) return "NO HAY EJECUCIÓN EN CURSO.";
      if (e.intento_actual >= 3) return "YA ESTÁ EN EL INTENTO 3/3.";
      e.intento_actual++; e.fase = e.estado === "generando" ? "redaccion" : e.fase;
      tocar(e); notificar({ origen: "pipeline", novela_id: e.novela_id });
      return `${novela(e.novela_id).codigo} → intento ${e.intento_actual}/3`;
    }

    function provocarParada() {
      const e = activa();
      if (!e) return "NO HAY EJECUCIÓN EN CURSO.";
      const id = "P-0" + (++db.secuenciaParada);
      const enPlan = FASES_PLAN.includes(e.fase);
      if (enPlan) e.fase = FASES_PLAN.indexOf(e.fase) >= 5 ? "puerta_2" : "puerta_1";
      else e.fase = "puerta_3";
      const cap = enPlan ? null : e.capitulo_actual;
      db.paradas[id] = {
        id, novela_id: e.novela_id, capitulo: cap, escena: enPlan ? null : 2, fase: e.fase,
        detectada_en: ahoraISO(), gravedad: "bloqueante", intentos_consumidos: e.intento_actual,
        conflicto: enPlan ? "Contradicción de canon · regla del mundo" : "Contradicción de canon · estado de un objeto",
        resumen: enPlan
          ? "La escaleta propone una comunicación con la Tierra en tiempo real; el canon del mundo fija un retardo mínimo de 40 minutos."
          : `El borrador del capítulo ${cap} usa el transmisor de largo alcance. El canon lo registra como destruido en un capítulo anterior.`,
        texto: { ubicacion: enPlan ? "Escaleta · capítulo 5" : `Cap. ${cap} · escena 2 · párrafo 4`,
          cita: enPlan ? "La comandante habla con control de misión y recibe la respuesta al instante."
            : "Encendió el transmisor de largo alcance y esperó. La luz verde parpadeó una vez: canal abierto." },
        canon: { ubicacion: enPlan ? "Canon · mundo · regla COM-02" : "Canon · objetos · TRANSMISOR LARGO ALCANCE",
          cita: enPlan ? "Toda comunicación con la Tierra tiene un retardo mínimo de 40 minutos por trayecto."
            : "Estado: DESTRUIDO. Queda inutilizado durante la despresurización del módulo de comunicaciones." }
      };
      e.estado = "parada"; e.parada_abierta_id = id;
      tocar(e); notificar({ origen: "pipeline", novela_id: e.novela_id });
      return `${novela(e.novela_id).codigo} → parada ${id}`;
    }

    function provocarError() {
      const e = activa();
      if (!e) return "NO HAY EJECUCIÓN EN CURSO.";
      e.estado = "error";
      e.ultimo_error = `${e.fase}${e.capitulo_actual ? " · cap. " + e.capitulo_actual : ""} · intento ${e.intento_actual}/3: tiempo de espera agotado (120 s) esperando respuesta del agente de ${FASE[e.fase].toLowerCase()}. Reintentos agotados.`;
      tocar(e); notificar({ origen: "pipeline", novela_id: e.novela_id });
      return `${novela(e.novela_id).codigo} → error`;
    }

    function completarConAvisos() {
      const e = activa();
      if (!e) return "NO HAY EJECUCIÓN EN CURSO.";
      const n = novela(e.novela_id);
      if (!n.capitulos_total) n.capitulos_total = Math.max(6, Math.round(n.longitud_objetivo_palabras / 3500));
      if (!e.capitulo_actual) e.capitulo_actual = e.capitulos_completados + 1;
      while (e.fase !== "puerta_5") cerrarCapitulo(e);
      const lista = db.capitulos[e.novela_id];
      if (!lista.some((c) => c.avisos.length)) lista[lista.length - 1].avisos.push(D.AVISOS_EXTRA[0]);
      e.estado = "completada_con_avisos"; e.fase = "ninguna"; e.capitulo_actual = null;
      tocar(e); notificar({ origen: "pipeline", novela_id: e.novela_id });
      return `${n.codigo} → completada_con_avisos`;
    }

    return {
      opciones,
      suscribir: (f) => oyentes.push(f),
      consultar: () => clonar(db),
      procesar, avanzar, reintento, provocarParada, provocarError, completarConAvisos,
      activa: () => { const e = activa(); return e ? clonar(e) : null; },
      vaciar() { db = { novelas: [], ejecuciones: {}, capitulos: {}, paradas: {}, secuencia: db.secuencia, secuenciaParada: db.secuenciaParada }; notificar({ origen: "pipeline" }); },
      reiniciar() { db = D.semilla(); notificar({ origen: "pipeline" }); }
    };
  })();

  /* ------------------------------------------------------------------------
     4. CLIENTE — lo que será el estado del frontend en React
     ------------------------------------------------------------------------ */
  const C = {
    datos: Servidor.consultar(),   // última instantánea confirmada por el servidor
    consultadoEn: Date.now(),
    enlace: "nominal",             // nominal | perdido | restableciendo
    simCortado: false,
    intentoReconexion: 0,
    proximoReintento: 0,
    restablecidoEn: 0,
    pendientes: {},                // clave (novela_id | tipo) → intención en vuelo
    rechazos: {},                  // clave → { motivo, hasta }
    recien: {},                    // novela_id → instante en que se confirmó un movimiento
    retenidas: [],                 // entregas retenidas desde el panel de simulación
    ruta: { vista: "tablero" },
    menuAbierto: null,
    arrastre: null,
    renderPendiente: false,
    paradaArmada: null,            // confirmación en dos pasos de la alerta de parada
    paradaDesde: {},
    focoCarril: false,
    tamLectura: almacen.leer("nv-lectura", "m")
  };

  const ejec = (id) => C.datos.ejecuciones[id];
  const novelaDe = (id) => C.datos.novelas.find((n) => n.id === id);
  const activaCliente = () => Object.values(C.datos.ejecuciones).find((e) => ACTIVOS.includes(e.estado)) || null;

  function reconsultar() {
    const previo = C.datos;
    C.datos = Servidor.consultar();
    C.consultadoEn = Date.now();
    detectarAlertas(previo, C.datos);
    render();
  }

  // Push simulado del servidor (en producción: SSE/WebSocket o sondeo). Sin enlace, se pierde.
  Servidor.suscribir((ev) => {
    if (ev.origen === "intencion") return; // la confirmación de la intención trae su propia reconsulta
    if (C.enlace !== "nominal") return;
    setTimeout(() => { if (C.enlace === "nominal") reconsultar(); }, 250);
  });

  function detectarAlertas(previo, actual) {
    for (const id in actual.ejecuciones) {
      const a = actual.ejecuciones[id], p = previo.ejecuciones[id];
      if (!p || p.estado === a.estado) continue;
      const n = actual.novelas.find((x) => x.id === id);
      if (a.estado === "parada") { anunciar(`Alerta: parada en ${n.codigo}. Requiere decisión.`, true); aviso(`■ PARADA · ${n.codigo} · ${a.parada_abierta_id}`, "alerta"); }
      if (a.estado === "error") { anunciar(`Alerta: error en ${n.codigo}.`, true); aviso(`✕ ERROR · ${n.codigo}`, "alerta"); }
      if (a.estado === "completada" || a.estado === "completada_con_avisos") aviso(`✓ ${n.codigo} · ${ESTADO[a.estado].toUpperCase()}`, "confirmado");
    }
  }

  function enviarIntencion(int) {
    const clave = int.novela_id || int.tipo;
    if (C.enlace !== "nominal") {
      aviso("SIN ENLACE · INTENCIÓN NO ENVIADA", "rechazo");
      return Promise.resolve({ aceptada: false, motivo: "SIN ENLACE." });
    }
    if (C.pendientes[clave]) {
      aviso("YA HAY UNA INTENCIÓN EN COLA PARA ESTE EXPEDIENTE", "rechazo");
      return Promise.resolve({ aceptada: false, motivo: "INTENCIÓN DUPLICADA." });
    }
    C.pendientes[clave] = Object.assign({ enviada_en: Date.now() }, int);
    delete C.rechazos[clave];
    anunciar(`Intención en cola: ${INTENCION[int.tipo]}. Esperando confirmación.`);
    render();

    return new Promise((resolve) => {
      const procesarYEntregar = () => {
        const r = Servidor.procesar(int);       // el servidor recibe y decide
        if (!C.pendientes[clave]) return resolve(r);   // ya resuelta por una reconsulta
        if (C.enlace !== "nominal") {           // la confirmación no llega: se aclarará al reconsultar
          C.pendientes[clave].sinConfirmar = true; render(); return resolve(null);
        }
        delete C.pendientes[clave];
        if (r.aceptada) {
          C.recien[int.novela_id || r.novela_id] = Date.now();
          aviso(`✓ CONFIRMADO · ${INTENCION[int.tipo].toUpperCase()}`, "confirmado");
          anunciar(`Confirmado por el servidor: ${INTENCION[int.tipo]}.`);
        } else {
          C.rechazos[clave] = { motivo: frase(r.motivo), hasta: Date.now() + 8000 };
          aviso(`✕ RECHAZADA · ${r.motivo}`, "rechazo");
          anunciar(`Intención rechazada. ${frase(r.motivo)}`, true);
          setTimeout(render, 8100);
        }
        reconsultar();
        resolve(r);
      };
      setTimeout(() => {
        if (Servidor.opciones.retener) { C.retenidas.push(procesarYEntregar); pintarSim(); }
        else procesarYEntregar();
      }, int.tipo === "crear_novela" ? Math.max(2600, Servidor.opciones.latencia) : Servidor.opciones.latencia);
    });
  }

  /* --- Enlace y reconexión --- */
  function perderEnlace() {
    if (C.enlace === "perdido") return;
    C.enlace = "perdido"; C.intentoReconexion = 0;
    programarReintento();
    anunciar("Señal perdida. Restableciendo enlace. Las acciones quedan en pausa.", true);
    render();
  }
  function programarReintento() {
    C.intentoReconexion++;
    const espera = Math.min(2 ** C.intentoReconexion, 16);
    C.proximoReintento = Date.now() + espera * 1000;
    clearTimeout(C.tReintento);
    C.tReintento = setTimeout(reintentar, espera * 1000);
    pintarEnlace();
  }
  function reintentar() {
    clearTimeout(C.tReintento);
    if (C.simCortado || !navigator.onLine) { programarReintento(); return; }
    C.enlace = "restableciendo"; pintarEnlace();
    setTimeout(() => {
      const sinConfirmar = Object.keys(C.pendientes).length;
      C.pendientes = {}; C.retenidas = [];
      C.enlace = "nominal"; C.restablecidoEn = Date.now();
      reconsultar();
      aviso(sinConfirmar ? `ENLACE RESTABLECIDO · ${sinConfirmar} INTENCIÓN(ES) SIN CONFIRMAR: ESTADO RECONSULTADO` : "ENLACE RESTABLECIDO · ESTADO RECONSULTADO", "confirmado");
      anunciar("Enlace restablecido. Estado reconsultado.");
      setTimeout(pintarEnlace, 4200);
    }, 1200);
  }
  window.addEventListener("offline", perderEnlace);
  window.addEventListener("online", () => { if (C.enlace === "perdido") reintentar(); });
  let ocultoDesde = 0;
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) { ocultoDesde = Date.now(); return; }
    // Al volver de una suspensión o de otra pestaña se reconsulta todo.
    if (C.enlace === "nominal" && Date.now() - ocultoDesde > 2000) reconsultar();
  });

  /* ------------------------------------------------------------------------
     5. Avisos, anuncios y cabecera
     ------------------------------------------------------------------------ */
  function anunciar(texto, asertivo) {
    const el = $(asertivo ? "#vivo-alertas" : "#vivo-cortes");
    el.textContent = ""; setTimeout(() => { el.textContent = texto; }, 30);
  }
  function aviso(texto, tipo) {
    const lista = $("#avisos");
    const li = document.createElement("li");
    li.className = "aviso"; li.dataset.tipo = tipo || "info"; li.textContent = frase(texto);
    lista.prepend(li);
    while (lista.children.length > 4) lista.lastChild.remove();
    setTimeout(() => li.remove(), 5200);
  }

  function pintarEnlace() {
    const ind = $("#indicador-enlace"), banner = $("#banner-enlace");
    document.documentElement.dataset.enlace = C.enlace;
    ind.dataset.enlace = C.enlace;
    const textoInd = { nominal: "Enlace nominal", perdido: "Sin señal", restableciendo: "Restableciendo" }[C.enlace];
    $(".indicador-enlace__texto", ind).textContent = textoInd;
    if (C.enlace === "perdido") {
      const faltan = Math.max(0, Math.ceil((C.proximoReintento - Date.now()) / 1000));
      banner.hidden = false; banner.dataset.tipo = "perdido";
      banner.innerHTML = `<span class="baliza" aria-hidden="true"></span>
        <strong>Señal perdida · restableciendo enlace</strong>
        <span>Intento ${C.intentoReconexion} · próximo en ${faltan} s</span>
        <span class="banner-enlace__nota">Datos de ${hora(C.consultadoEn)}: pueden no ser actuales. Intenciones en pausa.</span>
        <button type="button" class="boton boton--mini boton--invertido" data-accion="reintentar-ya">Reintentar ahora</button>`;
    } else if (C.enlace === "restableciendo") {
      banner.hidden = false; banner.dataset.tipo = "restableciendo";
      banner.innerHTML = `<span class="baliza" aria-hidden="true"></span><strong>Enlace detectado · reconsultando estado…</strong>`;
    } else if (Date.now() - C.restablecidoEn < 4000) {
      banner.hidden = false; banner.dataset.tipo = "ok";
      banner.innerHTML = `<strong>✓ Enlace restablecido</strong><span>Estado reconsultado a las ${hora(C.consultadoEn)}</span>`;
    } else { banner.hidden = true; banner.innerHTML = ""; }
  }

  function pintarCabecera() {
    const n = Object.values(C.datos.ejecuciones).filter((e) => CARRIL_ATENCION.estados.includes(e.estado)).length;
    const ind = $("#indicador-atencion");
    ind.hidden = n === 0;
    ind.innerHTML = `<span aria-hidden="true">■</span> ${n} requiere${n === 1 ? "" : "n"} atención`;
    $$(".cabecera__nav a").forEach((a) => {
      const activo = a.dataset.nav === (C.ruta.vista === "crear" ? "crear" : C.ruta.vista === "tablero" ? "tablero" : "");
      if (activo) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
    pintarEnlace();
  }

  /* ------------------------------------------------------------------------
     6. Rutas
     ------------------------------------------------------------------------ */
  function leerRuta() {
    const p = (location.hash.replace(/^#\/?/, "") || "tablero").split("/").filter(Boolean);
    if (p[0] === "tablero") return { vista: "tablero" };
    if (p[0] === "crear") return { vista: "crear" };
    if (p[0] === "novela" && p[1] && !p[2]) return { vista: "novela", id: p[1] };
    if (p[0] === "novela" && p[1] && p[2] === "parada") return { vista: "parada", id: p[1] };
    if (p[0] === "novela" && p[1] && p[2] === "capitulo" && p[3]) return { vista: "lector", id: p[1], n: parseInt(p[3], 10) };
    return { vista: "desconocida" };
  }
  const VISTAS_VIVAS = ["tablero", "novela", "parada"]; // se repintan con cada cambio del servidor

  function navegar(inicial) {
    cerrarMenu(false);
    C.ruta = leerRuta();
    C.paradaArmada = null;
    document.documentElement.dataset.ruta = C.ruta.vista;
    if (window.Ambiente) window.Ambiente.desmontar();
    pintarVista(true);
    pintarCabecera();
    if (!inicial) {
      window.scrollTo(0, 0);
      const h1 = $("#contenido h1");
      if (C.focoCarril && $("#carril-atencion")) { $("#carril-atencion").focus(); C.focoCarril = false; }
      else if (h1) h1.focus({ preventScroll: true });
    }
  }
  window.addEventListener("hashchange", () => navegar(false));

  function render() {
    pintarCabecera();
    pintarSim();
    if (VISTAS_VIVAS.includes(C.ruta.vista)) pintarVista(false);
  }

  function pintarVista(forzar) {
    const main = $("#contenido");
    if (!forzar && (C.menuAbierto || C.arrastre)) { C.renderPendiente = true; return; }
    C.renderPendiente = false;
    // Conservar foco y desplazamientos internos entre repintados
    const act = document.activeElement;
    const foco = act && main.contains(act) ? act.dataset.foco : null;
    const scrolls = {};
    if (!forzar) $$("[data-scroll]", main).forEach((el) => { scrolls[el.dataset.scroll] = [el.scrollLeft, el.scrollTop]; });

    const r = C.ruta;
    let html, titulo = "novelasv2";
    if (r.vista === "tablero") { html = vistaTablero(); titulo = "Tablero · novelasv2"; }
    else if (r.vista === "crear") { html = vistaCrear(); titulo = "Nueva novela · novelasv2"; }
    else if (r.vista === "novela") { html = vistaNovela(r.id); titulo = (novelaDe(r.id) || {}).titulo || titulo; }
    else if (r.vista === "parada") { html = vistaParada(r.id); titulo = "Parada · novelasv2"; }
    else if (r.vista === "lector") { html = vistaLector(r.id, r.n); titulo = `Capítulo ${r.n} · novelasv2`; }
    else html = vistaNoEncontrada("Ruta no reconocida.");
    main.innerHTML = html;
    document.title = titulo;

    $$("[data-scroll]", main).forEach((el) => { const s = scrolls[el.dataset.scroll]; if (s) { el.scrollLeft = s[0]; el.scrollTop = s[1]; } });
    if (foco) { const el = main.querySelector(`[data-foco="${foco}"]`); if (el) el.focus({ preventScroll: true }); }
    if (r.vista === "crear") montarCrear();
    if (r.vista === "lector") document.documentElement.dataset.tamLectura = C.tamLectura;
  }

  /* ------------------------------------------------------------------------
     7. Piezas comunes
     ------------------------------------------------------------------------ */
  const chip = (estado) =>
    `<span class="chip" data-estado="${estado}"><span class="chip__icono" aria-hidden="true">${ICONO[estado]}</span>${ESTADO[estado]}</span>`;

  function lineaFase(e) {
    if (e.fase === "ninguna") return e.estado === "configurada" ? "Sin arrancar" : "Sin fase activa";
    let t = `Fase ${FASE[e.fase]}`;
    if (e.capitulo_actual) t += ` · cap. ${e.capitulo_actual}`;
    if (e.intento_actual > 1 && e.estado !== "completada") t += ` · intento ${e.intento_actual}/3`;
    return t;
  }

  function progreso(e, n) {
    const total = n.capitulos_total;
    const pct = total ? Math.round((e.capitulos_completados / total) * 100) : 0;
    const texto = total ? `${e.capitulos_completados} / ${total} cap.` : `${e.capitulos_completados} / ? cap.`;
    const desc = total ? `${e.capitulos_completados} de ${total} capítulos cerrados` : "Total de capítulos aún sin fijar (se define en la fase estructura)";
    return `<div class="progreso" title="${desc}">
      <div class="progreso__barra" role="progressbar" aria-label="Capítulos cerrados" aria-valuemin="0" aria-valuemax="${total || 0}" aria-valuenow="${e.capitulos_completados}" aria-valuetext="${desc}"><span style="width:${pct}%"></span></div>
      <span class="progreso__texto">${texto}</span></div>`;
  }

  function intentoPips(i) {
    return `<span class="intento" aria-label="Intento ${i} de 3"><span class="intento__pips" aria-hidden="true">${[1, 2, 3].map((k) => `<i${k <= i ? " data-on" : ""}></i>`).join("")}</span>Intento ${i}/3</span>`;
  }

  function vistaNoEncontrada(motivo) {
    return `<section class="pantalla pantalla--estrecha"><p class="etiqueta">Código 404 · sin registro</p>
      <h1 tabindex="-1">Expediente no encontrado</h1><p>${esc(motivo)}</p>
      <p><a class="boton" href="#/tablero">Volver al tablero</a></p></section>`;
  }

  /* ------------------------------------------------------------------------
     8. Pantalla · TABLERO GENERAL
     ------------------------------------------------------------------------ */
  function vistaTablero() {
    const d = C.datos;
    const grupos = { espera: [], planificando: [], escribiendo: [], terminada: [], atencion: [] };
    d.novelas.forEach((n) => { const e = d.ejecuciones[n.id]; grupos[columnaDe(e.estado)].push({ n, e }); });
    Object.values(grupos).forEach((g) => g.sort((a, b) => b.e.actualizado_en.localeCompare(a.e.actualizado_en)));
    const activa = activaCliente();
    const enCurso = activa ? novelaDe(activa.novela_id).codigo : "ninguna";

    const cabecera = `
      <header class="pantalla__cabecera">
        <div>
          <p class="etiqueta">Módulo 01 · control de expedientes</p>
          <h1 tabindex="-1">Tablero general</h1>
          <p class="resumen">${d.novelas.length} novela${d.novelas.length === 1 ? "" : "s"} · en curso: <strong>${enCurso}</strong> · ${grupos.atencion.length} requieren atención · consulta ${hora(C.consultadoEn)}</p>
        </div>
        <a class="boton boton--primario" href="#/crear"><span aria-hidden="true">+</span> Nueva novela</a>
      </header>`;
    const ayuda = `
      <p class="ayuda-arrastre">Arrastra <strong>En espera → Planificando</strong> para arrancar y <strong>Planificando/Escribiendo → En espera</strong> para parar. Teclado o táctil: botón <span aria-hidden="true">⋯</span> de cada tarjeta, o <kbd>Mayús</kbd>+<kbd>F10</kbd>. Una sola ejecución a la vez.</p>`;

    const carril = `
      <section class="carril-atencion" id="carril-atencion" tabindex="-1" data-columna="atencion" data-vacio="${grupos.atencion.length === 0}" aria-labelledby="carril-titulo">
        <header class="carril-atencion__cabecera">
          <h2 id="carril-titulo"><span aria-hidden="true">■</span> Requiere atención <span class="cuenta">${grupos.atencion.length}</span></h2>
          <p>parada · error — no se arrastran: ábrelas para decidir</p>
        </header>
        <div class="carril-atencion__zona" data-scroll="atencion">
          ${grupos.atencion.length ? grupos.atencion.map((x) => tarjeta(x, "atencion")).join("") : `<p class="carril-atencion__vacio">Sin incidencias. Ninguna ejecución espera decisión.</p>`}
        </div>
        <div class="zona-destino" aria-hidden="true"></div>
      </section>`;

    if (d.novelas.length === 0) {
      return `<section class="pantalla">${cabecera}${carril}
        <div class="vacio">
          <p class="etiqueta">Bitácora vacía · primera sesión</p>
          <h2>No hay novelas registradas</h2>
          <p>Cada novela es un expediente. Al crearla queda <strong>En espera</strong>; al arrancarla, el pipeline de agentes la planifica y la escribe solo, durante horas. Esta consola observa y te avisa cuando algo requiere tu decisión.</p>
          <ol class="vacio__flujo" aria-label="Recorrido de una novela">
            <li>En espera</li><li>Planificando</li><li>Escribiendo</li><li>Terminada</li>
          </ol>
          <a class="boton boton--primario" href="#/crear">Crear la primera novela</a>
        </div></section>`;
    }

    const columnas = COLUMNAS.map((col) => {
      const lista = grupos[col.id];
      const huecos = Object.values(C.pendientes).filter((p) => p.destino === col.id).map((p) => {
        const n = novelaDe(p.novela_id);
        return `<div class="hueco-pendiente" aria-hidden="true"><span>En cola → ${INTENCION[p.tipo]}</span><span>${n ? n.codigo : ""} · esperando confirmación${p.sinConfirmar ? " (sin enlace)" : ""}</span></div>`;
      }).join("");
      const vacioTxt = col.id === "planificando" ? "Sin ejecución. Suelta aquí una novela en espera para arrancarla."
        : col.id === "escribiendo" ? "Ninguna novela escribiendo." : col.id === "terminada" ? "Aún no hay novelas terminadas." : "Sin novelas en espera.";
      return `<section class="columna" data-columna="${col.id}" aria-labelledby="col-${col.id}">
        <header class="columna__cabecera">
          <h2 id="col-${col.id}"><span class="codigo">${col.codigo}</span> ${col.nombre}</h2>
          <span class="cuenta" aria-label="${lista.length} novelas">${lista.length}</span>
          <p class="columna__estados">${col.estados.join(" · ")}</p>
        </header>
        <div class="columna__zona" data-scroll="col-${col.id}">
          ${huecos}
          ${lista.length ? lista.map((x) => tarjeta(x, col.id)).join("") : (huecos ? "" : `<p class="columna__vacio">${vacioTxt}</p>`)}
        </div>
        <div class="zona-destino" aria-hidden="true"></div>
      </section>`;
    }).join("");

    return `<section class="pantalla pantalla--tablero">${cabecera}${ayuda}${carril}
      <div class="tablero" id="tablero" data-scroll="tablero">${columnas}</div></section>`;
  }

  function tarjeta({ n, e }, col) {
    const pend = C.pendientes[n.id];
    const rech = C.rechazos[n.id] && C.rechazos[n.id].hasta > Date.now() ? C.rechazos[n.id] : null;
    const arrastrable = ["espera", "planificando", "escribiendo"].includes(col) && !pend && C.enlace === "nominal";
    const recien = C.recien[n.id] && Date.now() - C.recien[n.id] < 2600;
    const href = e.estado === "parada" ? `#/novela/${n.id}/parada` : `#/novela/${n.id}`;
    let extra = "";
    if (e.estado === "error") extra = `<p class="tarjeta__alerta"><span class="solo-lector">Último error: </span>${esc(recortar(e.ultimo_error, 120))}</p>`;
    if (e.estado === "parada") extra = `<p class="tarjeta__alerta">Parada ${esc(e.parada_abierta_id)}${e.capitulo_actual ? " · cap. " + e.capitulo_actual : ""} · esperando decisión</p>`;
    if (e.estado === "completada_con_avisos") {
      const nAv = (C.datos.capitulos[n.id] || []).reduce((s, c) => s + c.avisos.length, 0);
      extra = `<p class="tarjeta__avisos"><span aria-hidden="true">▲</span> ${nAv} aviso${nAv === 1 ? "" : "s"} no bloqueante${nAv === 1 ? "" : "s"}</p>`;
    }
    return `<article class="tarjeta" data-id="${n.id}" data-estado="${e.estado}" data-fase="${e.fase}" data-origen="${col}"
        data-arrastrable="${arrastrable}"${pend ? ` data-pendiente="${pend.tipo}"` : ""}${rech ? ` data-rechazada="true"` : ""}${recien ? ` data-recien="true"` : ""}
        aria-labelledby="t-${n.id}" aria-describedby="d-${n.id}">
      <div class="tarjeta__fila"><span class="codigo">${n.codigo}</span><span class="tarjeta__hace" data-hace="${e.actualizado_en}">${haceX(e.actualizado_en)}</span></div>
      <h3 class="tarjeta__titulo" id="t-${n.id}"><a class="tarjeta__enlace" href="${href}" draggable="false" data-foco="tarjeta-${n.id}" data-tarjeta="${n.id}">${esc(n.titulo)}</a></h3>
      <div class="tarjeta__estado" id="d-${n.id}">${chip(e.estado)}<span class="tarjeta__fase">${lineaFase(e)}</span></div>
      ${progreso(e, n)}
      ${extra}
      ${pend ? `<p class="tarjeta__pendiente" role="status"><span class="cursor" aria-hidden="true"></span>Intención en cola · ${INTENCION[pend.tipo]} · ${pend.sinConfirmar ? "sin confirmar (enlace caído)" : "esperando confirmación"}</p>` : ""}
      ${rech ? `<p class="tarjeta__rechazo"><strong>✕ Intención rechazada.</strong> ${esc(rech.motivo)}</p>` : ""}
      <button type="button" class="tarjeta__menu" data-menu="${n.id}" data-foco="menu-${n.id}" aria-haspopup="menu" aria-expanded="false" aria-label="Acciones: ${esc(n.titulo)}">⋯</button>
    </article>`;
  }

  /* ------------------------------------------------------------------------
     9. Arrastre (ratón/lápiz) con reglas de intención
     ------------------------------------------------------------------------ */
  let suprimirClic = false;

  document.addEventListener("pointerdown", (ev) => {
    const t = ev.target.closest(".tarjeta[data-arrastrable='true']");
    if (!t || ev.button !== 0 || ev.pointerType === "touch" || ev.target.closest(".tarjeta__menu")) return;
    C.arrastre = { el: t, id: t.dataset.id, origen: t.dataset.origen, x0: ev.clientX, y0: ev.clientY, activo: false, pointerId: ev.pointerId };
  });

  document.addEventListener("pointermove", (ev) => {
    const a = C.arrastre;
    if (!a) return;
    if (!a.activo) {
      if (Math.hypot(ev.clientX - a.x0, ev.clientY - a.y0) < 6) return;
      iniciarArrastre(a, ev);
    }
    ev.preventDefault();
    a.fantasma.style.transform = `translate(${ev.clientX - a.dx}px, ${ev.clientY - a.dy}px)`;
    const bajo = document.elementFromPoint(ev.clientX, ev.clientY);
    const col = bajo && bajo.closest("[data-columna]");
    $$("[data-columna]").forEach((c) => c.toggleAttribute("data-sobre", c === col));
    a.destino = col ? col.dataset.columna : null;
  });

  function iniciarArrastre(a, ev) {
    a.activo = true;
    const r = a.el.getBoundingClientRect();
    a.dx = ev.clientX - r.left; a.dy = ev.clientY - r.top;
    const f = a.el.cloneNode(true);
    f.classList.add("tarjeta--fantasma"); f.removeAttribute("id");
    f.querySelectorAll("[id]").forEach((x) => x.removeAttribute("id"));
    f.setAttribute("aria-hidden", "true");
    f.style.width = r.width + "px";
    document.body.appendChild(f);
    a.fantasma = f;
    a.el.dataset.arrastrando = "true";
    document.documentElement.dataset.arrastrando = "true";
    $$("[data-columna]").forEach((c) => {
      const id = c.dataset.columna;
      const intencion = TRANSICIONES[`${a.origen}>${id}`];
      c.dataset.destino = id === a.origen ? "origen" : intencion ? "valido" : "invalido";
      const z = $(".zona-destino", c);
      if (z) z.textContent = id === a.origen ? "Origen" : intencion ? `Soltar · ${INTENCION[intencion]}` : "Bloqueado · sin intención válida";
    });
  }

  function terminarArrastre(cancelar) {
    const a = C.arrastre;
    C.arrastre = null;
    if (!a || !a.activo) return;
    suprimirClic = true; setTimeout(() => { suprimirClic = false; }, 0);
    a.fantasma.remove();
    delete a.el.dataset.arrastrando;
    delete document.documentElement.dataset.arrastrando;
    $$("[data-columna]").forEach((c) => { delete c.dataset.destino; c.removeAttribute("data-sobre"); });
    const intencion = !cancelar && a.destino && TRANSICIONES[`${a.origen}>${a.destino}`];
    if (intencion) enviarIntencion({ tipo: intencion, novela_id: a.id, destino: a.destino });
    else if (!cancelar && a.destino && a.destino !== a.origen) aviso("ZONA BLOQUEADA · NO EXISTE ESA INTENCIÓN", "rechazo");
    if (C.renderPendiente || !intencion) pintarVista(false);
  }
  document.addEventListener("pointerup", () => terminarArrastre(false));
  document.addEventListener("pointercancel", () => terminarArrastre(true));
  document.addEventListener("click", (ev) => { if (suprimirClic) { ev.preventDefault(); ev.stopPropagation(); } }, true);

  /* ------------------------------------------------------------------------
     10. Menú contextual (alternativa accesible al arrastre)
     ------------------------------------------------------------------------ */
  function accionesTarjeta(id) {
    const e = ejec(id); const col = columnaDe(e.estado); const items = [];
    const puede = C.enlace === "nominal" && !C.pendientes[id];
    if (col === "espera") items.push({ accion: "arrancar", texto: "Arrancar → Planificando", destino: "planificando", deshabilitado: !puede });
    if (col === "planificando" || col === "escribiendo") items.push({ accion: "parar", texto: "Parar → En espera", destino: "espera", deshabilitado: !puede });
    if (e.estado === "parada") items.push({ accion: "ir", texto: "Abrir informe de parada", href: `#/novela/${id}/parada` });
    items.push({ accion: "ir", texto: "Abrir tablero de la novela", href: `#/novela/${id}` });
    if (C.enlace !== "nominal") items.push({ nota: "Intenciones en pausa: sin enlace" });
    else if (C.pendientes[id]) items.push({ nota: "Ya hay una intención en cola" });
    return items;
  }

  function abrirMenu(ancla, id, x, y) {
    cerrarMenu(false);
    const menu = $("#menu-tarjeta");
    const items = accionesTarjeta(id);
    menu.innerHTML = `<p class="menu__titulo">${esc(novelaDe(id).codigo)} · intenciones</p>` + items.map((it, i) => it.nota
      ? `<p class="menu__nota">${esc(it.nota)}</p>`
      : `<button type="button" role="menuitem" class="menu__item" data-i="${i}" ${it.deshabilitado ? 'aria-disabled="true"' : ""}>${esc(it.texto)}</button>`).join("");
    menu.hidden = false;
    const r = ancla.getBoundingClientRect();
    const px = x != null ? x : r.right - 8, py = y != null ? y : r.bottom + 4;
    const mw = menu.offsetWidth, mh = menu.offsetHeight;
    menu.style.left = Math.max(8, Math.min(px - (x != null ? 0 : mw), innerWidth - mw - 8)) + "px";
    menu.style.top = Math.max(8, Math.min(py, innerHeight - mh - 8)) + "px";
    ancla.setAttribute("aria-expanded", "true");
    C.menuAbierto = { ancla, id, items };
    const primero = $(".menu__item:not([aria-disabled])", menu) || $(".menu__item", menu);
    if (primero) primero.focus();
  }

  function cerrarMenu(devolverFoco) {
    if (!C.menuAbierto) return;
    const { ancla } = C.menuAbierto;
    $("#menu-tarjeta").hidden = true;
    ancla.setAttribute("aria-expanded", "false");
    C.menuAbierto = null;
    if (C.renderPendiente) pintarVista(false);
    if (devolverFoco) { const f = document.querySelector(`[data-foco="${ancla.dataset.foco}"]`); if (f) f.focus(); }
  }

  $("#menu-tarjeta").addEventListener("click", (ev) => {
    const b = ev.target.closest(".menu__item");
    if (!b || b.getAttribute("aria-disabled") === "true") return;
    const it = C.menuAbierto.items[+b.dataset.i]; const id = C.menuAbierto.id;
    cerrarMenu(true);
    if (it.href) location.hash = it.href;
    else enviarIntencion({ tipo: it.accion, novela_id: id, destino: it.destino });
  });
  $("#menu-tarjeta").addEventListener("keydown", (ev) => {
    const items = $$(".menu__item", ev.currentTarget);
    const i = items.indexOf(document.activeElement);
    if (ev.key === "ArrowDown") { ev.preventDefault(); items[(i + 1) % items.length].focus(); }
    else if (ev.key === "ArrowUp") { ev.preventDefault(); items[(i - 1 + items.length) % items.length].focus(); }
    else if (ev.key === "Home") { ev.preventDefault(); items[0].focus(); }
    else if (ev.key === "End") { ev.preventDefault(); items[items.length - 1].focus(); }
    else if (ev.key === "Escape") { ev.preventDefault(); cerrarMenu(true); }
    else if (ev.key === "Tab") { cerrarMenu(false); }
  });
  document.addEventListener("mousedown", (ev) => {
    if (C.menuAbierto && !ev.target.closest("#menu-tarjeta") && ev.target.closest("[data-menu]") !== C.menuAbierto.ancla) cerrarMenu(false);
  });
  // Evita el arrastre nativo de enlaces: el arrastre de tarjetas es propio (pointer events).
  document.addEventListener("dragstart", (ev) => { if (ev.target.closest && ev.target.closest(".tarjeta")) ev.preventDefault(); });

  /* ------------------------------------------------------------------------
     11. Delegación de eventos del contenido
     ------------------------------------------------------------------------ */
  document.addEventListener("click", (ev) => {
    const m = ev.target.closest("[data-menu]");
    if (m) { ev.preventDefault(); C.menuAbierto && C.menuAbierto.ancla === m ? cerrarMenu(true) : abrirMenu(m, m.dataset.menu); return; }
    const acc = ev.target.closest("[data-accion]");
    if (!acc) {
      const carril = ev.target.closest("[data-foco-carril]");
      if (carril) { if (C.ruta.vista === "tablero") { ev.preventDefault(); $("#carril-atencion").focus(); $("#carril-atencion").scrollIntoView({ block: "start" }); } else C.focoCarril = true; }
      return;
    }
    const id = acc.dataset.id;
    switch (acc.dataset.accion) {
      case "arrancar": enviarIntencion({ tipo: "arrancar", novela_id: id, destino: "planificando" }); break;
      case "parar": enviarIntencion({ tipo: "parar", novela_id: id, destino: "espera" }); break;
      case "relanzar": abrirRelanzar(id); break;
      case "reintentar-ya": reintentar(); break;
      case "resolver": resolverParada(id, acc.dataset.opcion); break;
      case "lectura": C.tamLectura = acc.dataset.tam; almacen.escribir("nv-lectura", C.tamLectura);
        document.documentElement.dataset.tamLectura = C.tamLectura;
        $$("[data-accion='lectura']").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.tam === C.tamLectura))); break;
    }
  });

  document.addEventListener("contextmenu", (ev) => {
    const t = ev.target.closest(".tarjeta");
    if (!t || C.ruta.vista !== "tablero") return;
    ev.preventDefault();
    abrirMenu($(".tarjeta__menu", t), t.dataset.id, ev.clientX, ev.clientY);
  });

  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && C.arrastre) { terminarArrastre(true); return; }
    const t = document.activeElement && document.activeElement.closest && document.activeElement.closest(".tarjeta");
    if (t && ((ev.shiftKey && ev.key === "F10") || ev.key === "ContextMenu")) {
      ev.preventDefault(); abrirMenu($(".tarjeta__menu", t), t.dataset.id);
    }
  });

  document.addEventListener("change", (ev) => {
    if (ev.target.matches("[data-parada-desde]")) { C.paradaDesde[ev.target.dataset.paradaDesde] = +ev.target.value; C.paradaArmada = null; pintarVista(false); }
  });

  /* ------------------------------------------------------------------------
     12. Diálogo · relanzar desde capítulo
     ------------------------------------------------------------------------ */
  function opcionesRelanzar(id) {
    const n = novelaDe(id), e = ejec(id);
    if (!n.capitulos_total) return [{ valor: 0, texto: "Desde el principio (planificación)" }];
    const tope = Math.min(n.capitulos_total, e.capitulos_completados + 1);
    const ops = [];
    for (let k = 1; k <= tope; k++) ops.push({ valor: k, texto: `Capítulo ${k}${k === e.capitulos_completados + 1 ? " (siguiente sin cerrar)" : ""}` });
    return ops;
  }
  function consecuenciaRelanzar(id, desde) {
    const e = ejec(id);
    if (!desde) return "Se descarta la planificación y el pipeline empieza de nuevo por el arquitecto.";
    const descartados = e.capitulos_completados - desde + 1;
    if (descartados <= 0) return `No se descarta ningún capítulo cerrado. Se retoma el capítulo ${desde} desde el paquete, intento 1/3.`;
    return `Se descartan ${descartados} capítulo${descartados === 1 ? "" : "s"} cerrado${descartados === 1 ? "" : "s"} (${desde}–${e.capitulos_completados}) y se regeneran. Los capítulos 1–${desde - 1 || 0} no se tocan.`;
  }
  function abrirRelanzar(id) {
    const dlg = $("#dialogo-relanzar"), sel = $("#relanzar-desde"), e = ejec(id), n = novelaDe(id);
    const ops = opcionesRelanzar(id);
    sel.innerHTML = ops.map((o) => `<option value="${o.valor}">${o.texto}</option>`).join("");
    sel.value = String(ops[ops.length - 1].valor);
    $("#relanzar-explicacion").textContent = `${n.codigo} · ${n.titulo}. Estado actual: ${e.estado}. El servidor confirmará antes de que cambie nada.`;
    const pinta = () => { $("#relanzar-consecuencia").textContent = consecuenciaRelanzar(id, +sel.value); };
    sel.onchange = pinta; pinta();
    dlg.returnValue = "";
    dlg.onclose = () => { if (dlg.returnValue === "confirmar") enviarIntencion({ tipo: "relanzar", novela_id: id, desde_capitulo: +sel.value || null }); };
    dlg.showModal();
  }

  /* ------------------------------------------------------------------------
     13. Pantalla · TABLERO DE UNA NOVELA
     ------------------------------------------------------------------------ */
  function momentoDe(e) {
    if (e.capitulos_completados > 0 || FASES_CAP.includes(e.fase) || e.fase === "puerta_5" ||
      e.estado === "completada" || e.estado === "completada_con_avisos") return "generacion";
    return "planificacion";
  }

  function vistaNovela(id) {
    const n = novelaDe(id), e = n && ejec(id);
    if (!n) return vistaNoEncontrada(`No existe ningún expediente con el identificador «${id}».`);
    const pend = C.pendientes[id];
    const rech = C.rechazos[id] && C.rechazos[id].hasta > Date.now() ? C.rechazos[id] : null;
    const sinEnlace = C.enlace !== "nominal";
    const bloq = !!pend || sinEnlace;
    const puedeArrancar = ["configurada", "detenida"].includes(e.estado);
    const puedeParar = ACTIVOS.includes(e.estado);
    const puedeRelanzar = !ACTIVOS.includes(e.estado) && e.estado !== "configurada";
    const disponibles = [puedeArrancar && "arrancar", puedeParar && "parar", puedeRelanzar && "relanzar"].filter(Boolean);

    let bloque = "";
    if (e.estado === "parada") bloque = `
      <a class="franja-alerta" href="#/novela/${id}/parada" data-foco="ir-parada">
        <span class="baliza baliza--alerta" aria-hidden="true"></span>
        <strong>Parada ${esc(e.parada_abierta_id)} · la ejecución espera tu decisión</strong>
        <span>Abrir informe →</span></a>`;
    if (e.estado === "error") bloque = `
      <section class="bloque-error" aria-labelledby="h-error">
        <h2 id="h-error"><span aria-hidden="true">✕</span> Error de ejecución</h2>
        <p class="bloque-error__campo">ultimo_error</p>
        <pre class="bloque-error__texto">${esc(e.ultimo_error)}</pre>
        <p>La ejecución no continuará sola. Relanza desde el capítulo afectado o desde uno anterior.</p>
      </section>`;
    if (e.estado === "completada_con_avisos") {
      const avs = (C.datos.capitulos[id] || []).flatMap((c) => c.avisos.map((a) => ({ c: c.numero, a })));
      bloque = `<section class="bloque-avisos" aria-labelledby="h-avisos">
        <h2 id="h-avisos"><span aria-hidden="true">▲</span> Completada con ${avs.length} aviso${avs.length === 1 ? "" : "s"}</h2>
        <p>La novela pasó todas las puertas. Los avisos no bloquearon la generación, pero conviene revisarlos.</p>
        <ul>${avs.map((x) => `<li><a href="#/novela/${id}/capitulo/${x.c}">Cap. ${x.c}</a> · ${esc(x.a)}</li>`).join("")}</ul></section>`;
    }

    const cabecera = `
      <nav class="migas" aria-label="Ruta"><a href="#/tablero">Tablero</a><span aria-hidden="true">/</span><span aria-current="page">${n.codigo}</span></nav>
      <header class="novela-cabecera" data-estado="${e.estado}">
        <div class="novela-cabecera__titulo">
          <p class="etiqueta">Expediente ${n.codigo} · ${esc(n.genero)}</p>
          <h1 tabindex="-1">${esc(n.titulo)}</h1>
        </div>
        <dl class="telemetria">
          <div><dt>Estado</dt><dd>${chip(e.estado)} <code class="codigo-estado" data-estado="${e.estado}">${e.estado}</code></dd></div>
          <div><dt>Fase</dt><dd data-fase="${e.fase}">${FASE[e.fase]}</dd></div>
          <div><dt>Capítulo</dt><dd>${e.capitulo_actual ? dos(e.capitulo_actual) : "—"}</dd></div>
          <div><dt>Intento</dt><dd>${ACTIVOS.includes(e.estado) || ["parada", "error"].includes(e.estado) ? intentoPips(e.intento_actual) : "—"}</dd></div>
          <div><dt>Progreso</dt><dd>${progreso(e, n)}</dd></div>
          <div><dt>Actualizado</dt><dd data-hace="${e.actualizado_en}">${haceX(e.actualizado_en)}</dd></div>
        </dl>
        <div class="acciones" role="group" aria-label="Intenciones sobre la ejecución">
          <button type="button" class="boton" data-accion="arrancar" data-id="${id}" data-foco="b-arrancar" ${!puedeArrancar || bloq ? "disabled" : ""}>▶ Arrancar</button>
          <button type="button" class="boton" data-accion="parar" data-id="${id}" data-foco="b-parar" ${!puedeParar || bloq ? "disabled" : ""}>‖ Parar</button>
          <button type="button" class="boton" data-accion="relanzar" data-id="${id}" data-foco="b-relanzar" ${!puedeRelanzar || bloq ? "disabled" : ""}>↻ Relanzar…</button>
          <p class="acciones__nota">${pend ? `<span class="cursor" aria-hidden="true"></span>Intención en cola · ${INTENCION[pend.tipo]} · esperando confirmación del servidor`
            : sinEnlace ? "Sin enlace · intenciones en pausa"
            : `Disponible: ${disponibles.length ? disponibles.join(" · ") : "ninguna intención en este estado"}`}</p>
          ${rech ? `<p class="acciones__rechazo" role="alert">✕ Rechazada: ${esc(rech.motivo)}</p>` : ""}
        </div>
      </header>`;

    const cuerpo = momentoDe(e) === "planificacion" ? momentoPlan(n, e) : momentoGeneracion(n, e);

    const ficha = `
      <details class="ficha">
        <summary>Parámetros de la novela</summary>
        <dl class="ficha__lista">
          <div><dt>longitud_objetivo_palabras</dt><dd>${num(n.longitud_objetivo_palabras)}</dd></div>
          <div><dt>longitud_capitulo_palabras</dt><dd>${n.longitud_capitulo_palabras ? `${num(n.longitud_capitulo_palabras.min)}–${num(n.longitud_capitulo_palabras.max)}` : "—"}</dd></div>
          <div><dt>publico</dt><dd>${esc(n.publico) || "—"}</dd></div>
          <div><dt>politica_contenido</dt><dd>${esc(n.politica_contenido) || "—"}</dd></div>
          <div><dt>pov_por_defecto</dt><dd>${POV[n.pov_por_defecto]}</dd></div>
          <div><dt>tiempo_verbal</dt><dd>${TIEMPO[n.tiempo_verbal]}</dd></div>
          <div class="ficha__ancho"><dt>semilla_premisa</dt><dd>${esc(n.semilla_premisa) || "—"}</dd></div>
        </dl>
      </details>`;

    return `<section class="pantalla pantalla--novela">${cabecera}${bloque}${cuerpo}${ficha}</section>`;
  }

  function estadoPaso(i, idx, e) {
    if (idx < 0 || i > idx) return "pendiente";
    if (i < idx) return "hecho";
    if (ACTIVOS.includes(e.estado)) return "activo";
    return { detenida: "detenido", parada: "parada", error: "error" }[e.estado] || "pendiente";
  }
  const TEXTO_PASO = { hecho: "Hecho", activo: "En curso", pendiente: "Pendiente", detenido: "Detenido aquí", parada: "Parada", error: "Error" };

  function momentoPlan(n, e) {
    const idx = FASES_PLAN.indexOf(e.fase);
    return `<section class="momento" aria-labelledby="h-plan">
      <header class="momento__cabecera"><h2 id="h-plan"><span class="codigo">A</span> Planificación</h2>
        <p>Aún no existen capítulos. El total se fija al cerrar <em>estructura</em>.</p></header>
      <ol class="pasos">
        ${FASES_PLAN.map((f, i) => {
          const est = estadoPaso(i, idx, e);
          return `<li class="paso" data-fase="${f}" data-paso="${est}"${est === "activo" ? ' aria-current="step"' : ""}>
            <span class="paso__num">${dos(i + 1)}</span><span class="paso__nombre">${FASE[f]}</span>
            <span class="paso__estado">${TEXTO_PASO[est]}</span></li>`;
        }).join("")}
      </ol></section>`;
  }

  function momentoGeneracion(n, e) {
    const cerrados = (C.datos.capitulos[n.id] || []).slice().sort((a, b) => b.numero - a.numero);
    const total = n.capitulos_total || cerrados.length;
    const terminada = e.estado === "completada" || e.estado === "completada_con_avisos";
    const enCurso = !terminada && e.capitulo_actual && e.capitulo_actual > e.capitulos_completados ? e.capitulo_actual : null;
    const desdePend = (enCurso || e.capitulos_completados) + 1;
    const pendientes = [];
    for (let k = desdePend; k <= total; k++) pendientes.push(k);

    let tarjetaCurso = `<p class="columna__vacio">${terminada ? "Todos los capítulos cerrados." : "Ningún capítulo en curso."}</p>`;
    if (e.fase === "puerta_5" && !terminada) {
      tarjetaCurso = `<div class="cap-curso" data-estado="${e.estado}"><p class="etiqueta">Revisión final</p>
        <h4>Puerta 5 · novela completa</h4><p>Todos los capítulos cerrados. El servidor revisa la novela entera.</p></div>`;
    } else if (enCurso) {
      const idx = FASES_CAP.indexOf(e.fase);
      const etiquetaEstado = { generando: "", detenida: "Detenido en esta fase", parada: `Parada ${e.parada_abierta_id}`, error: "Error en esta fase" }[e.estado] || "";
      tarjetaCurso = `<div class="cap-curso" data-estado="${e.estado}" data-fase="${e.fase}">
        <div class="tarjeta__fila"><span class="codigo">CAP ${dos(enCurso)} / ${dos(total)}</span>${intentoPips(e.intento_actual)}</div>
        <h4>Capítulo ${enCurso}</h4>
        <p class="cap-curso__nota">Sin texto visible hasta superar la puerta 4.</p>
        <ol class="subfases" aria-label="Subfase del capítulo">
          ${FASES_CAP.map((f, i) => { const est = estadoPaso(i, idx, e);
            return `<li data-fase="${f}" data-paso="${est}"${est === "activo" ? ' aria-current="step"' : ""}><span class="subfase__marca" aria-hidden="true"></span>${FASE[f]}<span class="solo-lector">: ${TEXTO_PASO[est]}</span></li>`; }).join("")}
        </ol>
        ${etiquetaEstado ? `<p class="cap-curso__estado">${e.estado === "parada" ? `<a href="#/novela/${n.id}/parada">■ ${etiquetaEstado} · abrir informe</a>` : esc(etiquetaEstado)}</p>` : ""}
      </div>`;
    }

    return `<section class="momento" aria-labelledby="h-gen">
      <header class="momento__cabecera"><h2 id="h-gen"><span class="codigo">B</span> Generación</h2>
        <p>Un capítulo existe para el lector solo cuando supera la puerta 4. Solo uno en curso.</p></header>
      <div class="tablero-caps">
        <section class="col-cap" data-col="pendiente" aria-labelledby="h-pend">
          <h3 id="h-pend">Pendiente <span class="cuenta">${pendientes.length}</span></h3>
          ${pendientes.length ? `<ol class="caps-pendientes" data-scroll="pend">${pendientes.map((k) => `<li><span class="solo-lector">Capítulo </span>${dos(k)}</li>`).join("")}</ol>` : `<p class="columna__vacio">Nada pendiente.</p>`}
        </section>
        <section class="col-cap" data-col="en_curso" aria-labelledby="h-curso">
          <h3 id="h-curso">En curso <span class="cuenta">${enCurso || (e.fase === "puerta_5" && !terminada) ? 1 : 0}</span></h3>
          ${tarjetaCurso}
        </section>
        <section class="col-cap" data-col="cerrado" aria-labelledby="h-cerr">
          <h3 id="h-cerr">Cerrado <span class="cuenta">${cerrados.length}</span></h3>
          <ol class="caps-cerrados" data-scroll="cerr">
            ${cerrados.map((c) => `<li class="cap-cerrado"${c.avisos.length ? ' data-avisos="true"' : ""}>
              <a href="#/novela/${n.id}/capitulo/${c.numero}" data-foco="cap-${c.numero}">
                <span class="codigo">CAP ${dos(c.numero)}</span>
                <span class="cap-cerrado__titulo">${esc(c.titulo)}</span>
                <span class="cap-cerrado__meta">${num(c.palabras)} palabras${c.avisos.length ? ` · <span class="marca-aviso">▲ ${c.avisos.length} aviso${c.avisos.length === 1 ? "" : "s"}</span>` : ""}</span>
              </a>
              ${c.avisos.length ? `<ul class="cap-cerrado__avisos">${c.avisos.map((a) => `<li>${esc(a)}</li>`).join("")}</ul>` : ""}
            </li>`).join("") || `<li class="columna__vacio">Ningún capítulo cerrado.</li>`}
          </ol>
        </section>
      </div></section>`;
  }

  /* ------------------------------------------------------------------------
     14. Pantalla · ALERTA DE PARADA
     ------------------------------------------------------------------------ */
  function vistaParada(id) {
    const n = novelaDe(id), e = n && ejec(id);
    if (!n) return vistaNoEncontrada(`No existe ningún expediente con el identificador «${id}».`);
    const p = e.parada_abierta_id && C.datos.paradas[e.parada_abierta_id];
    if (e.estado !== "parada" || !p) {
      return `<section class="pantalla pantalla--estrecha"><nav class="migas" aria-label="Ruta"><a href="#/tablero">Tablero</a><span aria-hidden="true">/</span><a href="#/novela/${id}">${n.codigo}</a><span aria-hidden="true">/</span><span aria-current="page">Parada</span></nav>
        <p class="etiqueta">Sin parada abierta</p><h1 tabindex="-1">No hay ninguna parada abierta</h1>
        <p>${n.codigo} está en estado <code>${e.estado}</code>. La parada pudo resolverse desde otra sesión.</p>
        <p><a class="boton" href="#/novela/${id}">Ir al tablero de la novela</a></p></section>`;
    }
    const pend = C.pendientes[id];
    const rech = C.rechazos[id] && C.rechazos[id].hasta > Date.now() ? C.rechazos[id] : null;
    const otra = activaCliente();
    const desdeMax = p.capitulo || 1;
    const desde = C.paradaDesde[id] || desdeMax;
    const arm = C.paradaArmada && C.paradaArmada.id === id && C.paradaArmada.hasta > Date.now() ? C.paradaArmada.opcion : null;
    const bloq = !!pend || C.enlace !== "nominal";

    const opciones = [
      { op: "relanzar", nombre: "Relanzar", consecuencia: p.capitulo
          ? consecuenciaRelanzar(id, desde)
          : "Descarta la planificación y el pipeline vuelve a empezar por el arquitecto.",
        extra: p.capitulo ? `<label class="campo__etiqueta" for="p-desde">desde_capitulo</label>
          <select id="p-desde" class="campo__control" data-parada-desde="${id}" ${bloq ? "disabled" : ""}>
            ${Array.from({ length: desdeMax }, (_, k) => k + 1).map((k) => `<option value="${k}"${k === desde ? " selected" : ""}>Capítulo ${k}</option>`).join("")}
          </select>` : "",
        boton: p.capitulo ? `Relanzar desde cap. ${desde}` : "Relanzar desde el principio" },
      { op: "aceptar_retcon", nombre: "Aceptar retcon", consecuencia: "El texto manda: el canon se reescribe para aceptar lo que dice el borrador y la ejecución continúa. Los capítulos cerrados no se revisan.", boton: "Aceptar retcon" },
      { op: "rehacer", nombre: "Rehacer", consecuencia: `Se vuelve a redactar ${p.capitulo ? "solo el capítulo " + p.capitulo : "el paso afectado"} desde el paquete, con el conflicto como restricción. Reinicia el contador a intento 1/3.`, boton: `Rehacer ${p.capitulo ? "cap. " + p.capitulo : "paso"}` }
    ];

    return `<section class="pantalla alerta-parada" aria-labelledby="h-parada">
      <nav class="migas" aria-label="Ruta"><a href="#/tablero">Tablero</a><span aria-hidden="true">/</span><a href="#/novela/${id}">${n.codigo}</a><span aria-hidden="true">/</span><span aria-current="page">Parada ${esc(p.id)}</span></nav>
      <div class="alerta-parada__franja" role="presentation">
        <span class="baliza baliza--alerta" aria-hidden="true"></span>
        <span>Alerta de a bordo · parada ${esc(p.id)}</span>
        <span class="alerta-parada__franja-der">Ejecución detenida · esperando decisión</span>
      </div>
      <header class="alerta-parada__cabecera">
        <p class="etiqueta etiqueta--alerta">${esc(p.conflicto)}</p>
        <h1 id="h-parada" tabindex="-1">${esc(n.titulo)}: conflicto con el canon</h1>
        <p class="alerta-parada__resumen">${esc(p.resumen)}</p>
      </header>
      <dl class="informe">
        <div><dt>Expediente</dt><dd>${n.codigo}</dd></div>
        <div><dt>Capítulo · escena</dt><dd>${p.capitulo ? `${dos(p.capitulo)} · ${dos(p.escena)}` : "Planificación"}</dd></div>
        <div><dt>Detectada por</dt><dd data-fase="${p.fase}">${FASE[p.fase]}</dd></div>
        <div><dt>Intentos consumidos</dt><dd>${p.intentos_consumidos}/3</dd></div>
        <div><dt>Gravedad</dt><dd>${esc(p.gravedad)}</dd></div>
        <div><dt>Detectada</dt><dd data-hace="${p.detectada_en}">${haceX(p.detectada_en)}</dd></div>
      </dl>
      <div class="comparacion">
        <figure class="comparacion__lado" data-lado="texto">
          <figcaption><span class="etiqueta">Lo que dice el texto</span><span class="comparacion__ubicacion">${esc(p.texto.ubicacion)}</span></figcaption>
          <blockquote>${esc(p.texto.cita)}</blockquote>
        </figure>
        <div class="comparacion__contra" aria-hidden="true">≠</div>
        <figure class="comparacion__lado" data-lado="canon">
          <figcaption><span class="etiqueta">Lo que dice el canon</span><span class="comparacion__ubicacion">${esc(p.canon.ubicacion)}</span></figcaption>
          <blockquote>${esc(p.canon.cita)}</blockquote>
        </figure>
      </div>
      ${otra && otra.novela_id !== id ? `<p class="nota-ranura"><strong>Ranura ocupada.</strong> ${novelaDe(otra.novela_id).codigo} está en curso: el servidor rechazará cualquier acción que reanude esta ejecución hasta que se detenga. <a href="#/novela/${otra.novela_id}">Ir a ${novelaDe(otra.novela_id).codigo}</a></p>` : ""}
      <h2 class="alerta-parada__decision">Decisión <span>una acción · requiere confirmación</span></h2>
      <div class="opciones-parada" role="group" aria-label="Acciones de resolución">
        ${opciones.map((o) => `<div class="opcion" data-opcion="${o.op}"${arm === o.op ? ' data-armada="true"' : ""}>
          <h3><code>${o.op}</code> ${o.nombre}</h3>
          <p class="opcion__consecuencia">${esc(o.consecuencia)}</p>
          ${o.extra || ""}
          <button type="button" class="boton ${arm === o.op ? "boton--alerta" : ""}" data-accion="resolver" data-id="${id}" data-opcion="${o.op}" data-foco="op-${o.op}" ${bloq ? "disabled" : ""}>
            ${arm === o.op ? `Confirmar: ${o.boton.toLowerCase()}` : o.boton}</button>
        </div>`).join("")}
      </div>
      <p class="alerta-parada__pie">${pend ? `<span class="cursor" aria-hidden="true"></span>Intención en cola · resolver_parada (${esc(pend.accion)}) · esperando confirmación`
        : rech ? `<span role="alert">✕ Rechazada: ${esc(rech.motivo)}</span>`
        : C.enlace !== "nominal" ? "Sin enlace · intenciones en pausa" : "Primer clic arma la acción; el segundo envía la intención."}</p>
    </section>`;
  }

  function resolverParada(id, opcion) {
    const arm = C.paradaArmada;
    if (!arm || arm.id !== id || arm.opcion !== opcion || arm.hasta < Date.now()) {
      C.paradaArmada = { id, opcion, hasta: Date.now() + 6000 };
      pintarVista(false);
      anunciar("Acción armada. Pulsa de nuevo para confirmar.");
      setTimeout(() => { if (C.paradaArmada && C.paradaArmada.hasta <= Date.now()) { C.paradaArmada = null; if (C.ruta.vista === "parada") pintarVista(false); } }, 6100);
      return;
    }
    C.paradaArmada = null;
    const e = ejec(id);
    const p = C.datos.paradas[e.parada_abierta_id];
    const desde = opcion === "relanzar" && p && p.capitulo ? (C.paradaDesde[id] || p.capitulo) : null;
    enviarIntencion({ tipo: "resolver_parada", novela_id: id, accion: opcion, desde_capitulo: desde }).then((r) => {
      if (r && r.aceptada && C.ruta.vista === "parada" && C.ruta.id === id) location.hash = `#/novela/${id}`;
    });
  }

  /* ------------------------------------------------------------------------
     15. Pantalla · LECTOR DE CAPÍTULO
     ------------------------------------------------------------------------ */
  function vistaLector(id, numero) {
    const n = novelaDe(id), e = n && ejec(id);
    if (!n) return vistaNoEncontrada(`No existe ningún expediente con el identificador «${id}».`);
    const caps = (C.datos.capitulos[id] || []).slice().sort((a, b) => a.numero - b.numero);
    const cap = caps.find((c) => c.numero === numero);
    const volver = `<a class="lector__volver" href="#/novela/${id}"><span aria-hidden="true">←</span> ${n.codigo} · ${esc(n.titulo)}</a>`;
    if (!cap) {
      const enCurso = e.capitulo_actual === numero;
      return `<article class="lector"><nav class="lector__barra" aria-label="Lector">${volver}</nav>
        <p class="etiqueta">Capítulo ${dos(numero)} · no disponible</p>
        <h1 tabindex="-1">Este capítulo aún no existe para el lector</h1>
        <p>${enCurso ? `Está en curso (fase ${FASE[e.fase]}, intento ${e.intento_actual}/3). Su texto no se muestra hasta que supere la puerta 4.` : "No ha superado la puerta 4."}</p></article>`;
    }
    const t = D.textoCapitulo(id, numero, cap.escenas);
    const i = caps.indexOf(cap);
    const prev = caps[i - 1], sig = caps[i + 1];
    return `<article class="lector" aria-labelledby="h-lector">
      <nav class="lector__barra" aria-label="Lector">${volver}
        <div class="lector__tam" role="group" aria-label="Tamaño de letra">
          ${[["s", "A−"], ["m", "A"], ["l", "A+"]].map(([k, l]) => `<button type="button" class="boton boton--mini" data-accion="lectura" data-tam="${k}" aria-pressed="${C.tamLectura === k}" aria-label="Tamaño ${k === "s" ? "pequeño" : k === "m" ? "normal" : "grande"}">${l}</button>`).join("")}
        </div>
      </nav>
      <header class="lector__cabecera">
        <p class="etiqueta">Capítulo ${dos(numero)} de ${dos(n.capitulos_total || caps.length)}</p>
        <h1 id="h-lector" tabindex="-1">${esc(cap.titulo)}</h1>
        <p class="lector__meta">${num(cap.palabras)} palabras · ${t.escenas.length} escenas · ${POV[n.pov_por_defecto].toLowerCase()} · ${TIEMPO[n.tiempo_verbal].toLowerCase()}</p>
        ${cap.avisos.length ? `<details class="lector__avisos"><summary>▲ ${cap.avisos.length} aviso${cap.avisos.length === 1 ? "" : "s"} de las puertas</summary><ul>${cap.avisos.map((a) => `<li>${esc(a)}</li>`).join("")}</ul></details>` : ""}
      </header>
      <p class="nota-prototipo">Prototipo · ${t.relleno ? "texto de relleno compuesto con un banco de párrafos (solo los capítulos 1–2 de EXP-0409 y el 1 de EXP-0398 están escritos a mano)" : "fragmento escrito a mano"}. La cifra de palabras de la cabecera es la del capítulo completo.</p>
      <div class="lector__texto">
        ${t.escenas.map((parrafos, k) => `<section class="escena" aria-labelledby="esc-${k}">
          <h2 class="escena__titulo" id="esc-${k}">Escena ${k + 1}</h2>
          ${parrafos.map((p) => `<p>${esc(p)}</p>`).join("")}
        </section>`).join('<hr class="escena__corte">')}
      </div>
      <nav class="lector__pie" aria-label="Capítulos">
        ${prev ? `<a href="#/novela/${id}/capitulo/${prev.numero}" rel="prev"><span aria-hidden="true">←</span> Cap. ${prev.numero} · ${esc(prev.titulo)}</a>` : "<span></span>"}
        ${sig ? `<a href="#/novela/${id}/capitulo/${sig.numero}" rel="next">Cap. ${sig.numero} · ${esc(sig.titulo)} <span aria-hidden="true">→</span></a>` : `<span class="lector__fin">Último capítulo cerrado</span>`}
      </nav>
    </article>`;
  }

  /* ------------------------------------------------------------------------
     16. Pantalla · CREAR NOVELA
     ------------------------------------------------------------------------ */
  function campo(nombre, etiqueta, control, { obligatorio, pista } = {}) {
    return `<div class="campo" data-campo="${nombre}">
      <label class="campo__etiqueta" for="f-${nombre}">${etiqueta}${obligatorio ? ' <span class="campo__req">obligatorio</span>' : ' <span class="campo__opc">opcional</span>'}</label>
      ${control}
      ${pista ? `<p class="campo__pista" id="p-${nombre}">${pista}</p>` : ""}
      <p class="campo__error" id="e-${nombre}" hidden></p>
    </div>`;
  }

  function vistaCrear() {
    const radios = (nombre, opciones, def) => opciones.map(([v, l, d]) => `
      <label class="opcion-radio"><input type="radio" name="${nombre}" value="${v}"${v === def ? " checked" : ""}>
        <span class="opcion-radio__caja"><span class="opcion-radio__nombre">${l}</span>${d ? `<span class="opcion-radio__desc">${d}</span>` : ""}<code>${v}</code></span></label>`).join("");
    return `<div class="crear">
      <section class="crear__formulario pantalla">
        <nav class="migas" aria-label="Ruta"><a href="#/tablero">Tablero</a><span aria-hidden="true">/</span><span aria-current="page">Nueva novela</span></nav>
        <p class="etiqueta">Intención · crear_novela</p>
        <h1 tabindex="-1">Nueva novela</h1>
        <p class="intro">El servidor asignará expediente y la novela quedará <strong>En espera</strong> hasta que la arranques.</p>
        <div class="resumen-errores" id="resumen-errores" tabindex="-1" hidden></div>
        <form id="form-crear" novalidate>
          <fieldset class="form__cuerpo" id="form-cuerpo">
            <legend class="solo-lector">Parámetros de la novela</legend>
            ${campo("titulo", "Título", `<input id="f-titulo" name="titulo" class="campo__control" type="text" maxlength="120" autocomplete="off" required aria-required="true">`, { obligatorio: true })}
            ${campo("genero", "Género", `<input id="f-genero" class="campo__control campo__control--fijo" type="text" value="terror espacial" readonly aria-describedby="p-genero">`, { obligatorio: true, pista: "Fijo en esta versión. No editable." })}
            ${campo("longitud_objetivo_palabras", "Longitud objetivo (palabras)", `<input id="f-longitud_objetivo_palabras" name="longitud_objetivo_palabras" class="campo__control campo__control--num" type="text" inputmode="numeric" autocomplete="off" required aria-required="true" aria-describedby="p-longitud_objetivo_palabras">`, { obligatorio: true, pista: "Número entero, sin puntos. Ej.: 60000." })}
            <fieldset class="campo campo--grupo" data-campo="longitud_capitulo_palabras" aria-describedby="p-longitud_capitulo_palabras">
              <legend class="campo__etiqueta">Longitud por capítulo (palabras) <span class="campo__opc">opcional</span></legend>
              <div class="rango">
                <label><span>mínimo</span><input id="f-longitud_capitulo_palabras" name="cap_min" class="campo__control campo__control--num" type="text" inputmode="numeric" autocomplete="off"></label>
                <span class="rango__guion" aria-hidden="true">—</span>
                <label><span>máximo</span><input id="f-cap_max" name="cap_max" class="campo__control campo__control--num" type="text" inputmode="numeric" autocomplete="off"></label>
              </div>
              <p class="campo__pista" id="p-longitud_capitulo_palabras">Rango mínimo–máximo. Rellena ambos o ninguno.</p>
              <p class="campo__error" id="e-longitud_capitulo_palabras" hidden></p>
            </fieldset>
            ${campo("publico", "Público", `<input id="f-publico" name="publico" class="campo__control" type="text" autocomplete="off" aria-describedby="p-publico">`, { pista: "Texto libre. Ej.: adulto." })}
            ${campo("politica_contenido", "Política de contenido", `<textarea id="f-politica_contenido" name="politica_contenido" class="campo__control" rows="2" aria-describedby="p-politica_contenido"></textarea>`, { pista: "Texto libre. Qué evitar o cómo tratarlo." })}
            <fieldset class="campo campo--grupo" data-campo="pov_por_defecto">
              <legend class="campo__etiqueta">Punto de vista por defecto</legend>
              <div class="radios">${radios("pov_por_defecto", [
                ["primera", "Primera persona", "«Oigo la esclusa»"],
                ["tercera_limitada", "Tercera limitada", "Cerca de un personaje"],
                ["omnisciente", "Omnisciente", "Lo sabe todo"],
                ["objetiva", "Objetiva", "Solo lo observable"]], "tercera_limitada")}</div>
            </fieldset>
            <fieldset class="campo campo--grupo" data-campo="tiempo_verbal">
              <legend class="campo__etiqueta">Tiempo verbal</legend>
              <div class="radios radios--dos">${radios("tiempo_verbal", [["pasado", "Pasado", ""], ["presente", "Presente", ""]], "pasado")}</div>
            </fieldset>
            ${campo("semilla_premisa", "Semilla de la premisa", `<textarea id="f-semilla_premisa" name="semilla_premisa" class="campo__control" rows="5" aria-describedby="p-semilla_premisa"></textarea>`, { pista: "Texto largo. Una idea, una imagen, una situación de partida. <span id=\"contador-semilla\">0 caracteres</span>" })}
            <div class="form__acciones">
              <a class="boton" href="#/tablero">Cancelar</a>
              <button type="submit" class="boton boton--primario">Enviar intención · crear_novela</button>
            </div>
          </fieldset>
        </form>
        <div class="consola-envio" id="consola-envio" role="status" aria-live="polite" hidden></div>
      </section>
      <aside class="crear__ambiente" aria-hidden="true">
        <div class="ambiente" id="ambiente">${SVG_RESPALDO}</div>
        <p class="ambiente__pie"><span>Vista orbital · estación de referencia</span><span>Decorativo</span></p>
      </aside>
    </div>`;
  }

  // Silueta estática: se ve si Three.js no carga (sin red, CDN bloqueado) o no hay WebGL.
  const SVG_RESPALDO = `<svg class="ambiente__respaldo" viewBox="0 0 400 500" preserveAspectRatio="xMidYMid meet" fill="none" stroke="currentColor" style="color:var(--color-acento)">
    <g opacity="0.5" fill="var(--color-lectura-tenue)" stroke="none">${Array.from({ length: 60 }, (_, i) => `<circle cx="${(i * 97) % 400}" cy="${(i * 173) % 500}" r="${i % 7 === 0 ? 1.2 : 0.7}"/>`).join("")}</g>
    <g transform="translate(200 250) rotate(-18)">
      <ellipse rx="120" ry="42" stroke-width="1.2"/><ellipse rx="140" ry="50" stroke-width="1"/>
      <ellipse rx="120" ry="42" transform="translate(0 10)" opacity="0.35"/><ellipse rx="140" ry="50" transform="translate(0 10)" opacity="0.35"/>
      <path d="M-85 -30 L-14 -4 M85 30 L14 4 M85 -30 L14 -4 M-85 30 L-14 4" opacity="0.8"/>
      <rect x="-16" y="-24" width="32" height="48" opacity="0.9"/>
      <path d="M0 -24 V-150 M0 24 V160" opacity="0.4"/>
      <rect x="-12" y="-130" width="24" height="30" opacity="0.8"/><rect x="-10" y="110" width="20" height="26" opacity="0.8"/>
      <path d="M-70 -118 H70 M-70 -112 H70" opacity="0.4"/>
      <path d="M-18 160 Q0 185 18 160" opacity="0.8"/>
    </g></svg>`;

  function leerFormulario(f) {
    const v = (k) => (f.elements[k] ? f.elements[k].value.trim() : "");
    return {
      titulo: v("titulo"),
      longitud_objetivo_palabras: v("longitud_objetivo_palabras"),
      cap_min: v("cap_min"), cap_max: v("cap_max"),
      publico: v("publico"), politica_contenido: v("politica_contenido"),
      pov_por_defecto: f.elements.pov_por_defecto.value,
      tiempo_verbal: f.elements.tiempo_verbal.value,
      semilla_premisa: v("semilla_premisa")
    };
  }

  function validar(d) {
    const err = {};
    const entero = (s) => /^\d+$/.test(s);
    if (!d.titulo) err.titulo = "Título requerido.";
    if (!d.longitud_objetivo_palabras) err.longitud_objetivo_palabras = "Longitud objetivo requerida.";
    else if (!entero(d.longitud_objetivo_palabras)) err.longitud_objetivo_palabras = "Debe ser un número entero de palabras, sin puntos ni decimales.";
    else if (+d.longitud_objetivo_palabras <= 0) err.longitud_objetivo_palabras = "Debe ser mayor que 0.";
    if (d.cap_min || d.cap_max) {
      if (!d.cap_min || !d.cap_max) err.longitud_capitulo_palabras = "Indica mínimo y máximo, o deja ambos vacíos.";
      else if (!entero(d.cap_min) || !entero(d.cap_max)) err.longitud_capitulo_palabras = "Mínimo y máximo deben ser enteros.";
      else if (+d.cap_min > +d.cap_max) err.longitud_capitulo_palabras = "El mínimo no puede superar al máximo.";
      else if (!err.longitud_objetivo_palabras && +d.cap_max > +d.longitud_objetivo_palabras) err.longitud_capitulo_palabras = "El máximo por capítulo supera la longitud objetivo.";
    }
    return err;
  }

  const ETIQUETA_CAMPO = { titulo: "Título", longitud_objetivo_palabras: "Longitud objetivo", longitud_capitulo_palabras: "Longitud por capítulo" };

  function pintarErrores(f, err, resumen) {
    ["titulo", "longitud_objetivo_palabras", "longitud_capitulo_palabras"].forEach((k) => {
      const p = $(`#e-${k}`), c = $(`[data-campo="${k}"]`);
      const inputs = k === "longitud_capitulo_palabras" ? [f.elements.cap_min, f.elements.cap_max] : [f.elements[k]];
      if (err[k]) {
        p.hidden = false; p.innerHTML = `<span aria-hidden="true">▲</span> ${esc(err[k])}`; c.dataset.error = "true";
        inputs.forEach((i) => { i.setAttribute("aria-invalid", "true"); i.setAttribute("aria-describedby", [`e-${k}`, `p-${k}`].join(" ")); });
      } else {
        p.hidden = true; p.textContent = ""; delete c.dataset.error;
        inputs.forEach((i) => { i.removeAttribute("aria-invalid"); if (k !== "titulo") i.setAttribute("aria-describedby", `p-${k}`); else i.removeAttribute("aria-describedby"); });
      }
    });
    const r = $("#resumen-errores");
    const claves = Object.keys(err);
    if (resumen && claves.length) {
      r.hidden = false;
      r.innerHTML = `<p><strong>▲ ${claves.length} campo${claves.length === 1 ? "" : "s"} por corregir</strong></p><ul>${claves.map((k) =>
        `<li><a href="#f-${k}" data-ir-campo="f-${k}">${ETIQUETA_CAMPO[k]}: ${esc(err[k])}</a></li>`).join("")}</ul>`;
      r.focus();
    } else if (!claves.length) { r.hidden = true; r.innerHTML = ""; }
  }

  function montarCrear() {
    const f = $("#form-crear");
    let intentado = false;
    $("#resumen-errores").addEventListener("click", (ev) => {
      const a = ev.target.closest("[data-ir-campo]"); if (!a) return;
      ev.preventDefault(); $("#" + a.dataset.irCampo).focus();
    });
    const sem = $("#f-semilla_premisa");
    sem.addEventListener("input", () => { $("#contador-semilla").textContent = `${num(sem.value.length)} caracteres`; });
    f.addEventListener("input", () => { if (intentado) pintarErrores(f, validar(leerFormulario(f)), false); });
    f.addEventListener("submit", (ev) => {
      ev.preventDefault();
      intentado = true;
      const d = leerFormulario(f);
      const err = validar(d);
      pintarErrores(f, err, true);
      if (Object.keys(err).length) return;
      if (C.enlace !== "nominal") { aviso("SIN ENLACE · INTENCIÓN NO ENVIADA", "rechazo"); return; }
      const datos = {
        titulo: d.titulo, longitud_objetivo_palabras: parseInt(d.longitud_objetivo_palabras, 10),
        longitud_capitulo_palabras: d.cap_min ? { min: +d.cap_min, max: +d.cap_max } : null,
        publico: d.publico, politica_contenido: d.politica_contenido,
        pov_por_defecto: d.pov_por_defecto, tiempo_verbal: d.tiempo_verbal, semilla_premisa: d.semilla_premisa
      };
      const cuerpo = $("#form-cuerpo"), consola = $("#consola-envio");
      cuerpo.disabled = true;
      consola.hidden = false;
      const linea = (t, tipo) => { const p = document.createElement("p"); p.className = "consola-envio__linea"; if (tipo) p.dataset.tipo = tipo; p.textContent = frase(t); consola.appendChild(p); };
      consola.innerHTML = `<p class="etiqueta">Intención recibida · esperando asignación</p>`;
      linea(`${hora(Date.now())} INTENCIÓN crear_novela ENVIADA`);
      setTimeout(() => { if (!consola.isConnected) return; linea("RECIBIDA POR EL SERVIDOR"); linea("ESPERANDO ASIGNACIÓN DE EXPEDIENTE…", "espera"); }, 600);
      enviarIntencion({ tipo: "crear_novela", datos }).then((r) => {
        if (!consola.isConnected || !r) return;
        const esperando = consola.querySelector('[data-tipo="espera"]'); if (esperando) delete esperando.dataset.tipo;
        if (r.aceptada) {
          const n = C.datos.novelas.find((x) => x.id === r.novela_id);
          linea(`ASIGNADO ${n ? n.codigo : r.novela_id} · ESTADO configurada · COLUMNA EN ESPERA`, "ok");
          setTimeout(() => { if (C.ruta.vista === "crear") location.hash = "#/tablero"; }, 1100);
        } else {
          linea(`RECHAZADA · ${r.motivo}`, "rechazo");
          cuerpo.disabled = false;
          if (r.campo) { const e2 = {}; e2[r.campo] = frase(r.motivo); pintarErrores(f, e2, true); }
        }
      });
    });
    if (window.Ambiente) window.Ambiente.montar($("#ambiente"));
  }

  /* ------------------------------------------------------------------------
     17. Panel de simulación (herramienta del prototipo)
     ------------------------------------------------------------------------ */
  let autoIntervalo = null;
  function registroSim(t) { $("#sim-registro").textContent = frase(t); }

  function pintarSim() {
    const e = Servidor.activa();
    const n = e && C.datos.novelas.find((x) => x.id === e.novela_id);
    $("#sim-activa").textContent = e ? `${n ? n.codigo : e.novela_id} · ${e.estado} · ${e.fase}${e.capitulo_actual ? " · cap. " + e.capitulo_actual : ""}` : "Ninguna ejecución en curso";
    $("#sim-rechazar").checked = Servidor.opciones.rechazarProxima;
    const ret = $("#sim-retener");
    ret.checked = Servidor.opciones.retener;
    ret.parentElement.dataset.cola = C.retenidas.length ? `${C.retenidas.length} retenida(s)` : "";
  }

  $("#sim-asa").addEventListener("click", () => {
    const abierto = $("#sim-asa").getAttribute("aria-expanded") === "true";
    $("#sim-asa").setAttribute("aria-expanded", String(!abierto));
    $("#sim-cuerpo").hidden = abierto;
    $("#sim").dataset.abierto = String(!abierto);
  });
  $("#sim").addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && !$("#sim-cuerpo").hidden) { $("#sim-asa").click(); $("#sim-asa").focus(); }
  });

  function primeraEnEspera() {
    const e = Object.values(C.datos.ejecuciones).find((x) => ["configurada", "detenida"].includes(x.estado) && !C.pendientes[x.novela_id]);
    return e ? e.novela_id : null;
  }

  $("#sim-cuerpo").addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-sim]"); if (!b) return;
    const ir = () => { if (C.ruta.vista !== "tablero") location.hash = "#/tablero"; };
    switch (b.dataset.sim) {
      case "vacio": Servidor.vaciar(); C.pendientes = {}; C.rechazos = {}; ir(); registroSim("Servidor vaciado: primera sesión."); break;
      case "cortar": C.simCortado = true; perderEnlace(); registroSim("Enlace cortado. Los reintentos fallarán hasta restaurar."); break;
      case "restaurar": C.simCortado = false; if (C.enlace === "perdido") reintentar(); registroSim("Enlace restaurado: próximo reintento inmediato."); break;
      case "pendiente": {
        Servidor.opciones.retener = true;
        const act = Servidor.activa();
        const id = act ? act.novela_id : primeraEnEspera();
        if (!id) { registroSim("No hay novelas sobre las que enviar una intención."); break; }
        ir();
        enviarIntencion(act ? { tipo: "parar", novela_id: id, destino: "espera" } : { tipo: "arrancar", novela_id: id, destino: "planificando" });
        registroSim("Confirmaciones retenidas. Desmarca «Retener confirmaciones» para liberarlas.");
        break;
      }
      case "rechazada": {
        const id = primeraEnEspera();
        if (!id) { registroSim("No hay novelas en espera para intentar arrancar."); break; }
        if (!Servidor.activa()) Servidor.opciones.rechazarProxima = true;
        ir();
        enviarIntencion({ tipo: "arrancar", novela_id: id, destino: "planificando" });
        registroSim(Servidor.activa() ? "Intentando arrancar una 2.ª novela con la ranura ocupada." : "Rechazo forzado en el servidor.");
        break;
      }
      case "avanzar": registroSim(Servidor.avanzar()); break;
      case "reintento": registroSim(Servidor.reintento()); break;
      case "parada": registroSim(Servidor.provocarParada()); break;
      case "error": registroSim(Servidor.provocarError()); break;
      case "avisos": registroSim(Servidor.completarConAvisos()); break;
      case "reiniciar":
        Servidor.reiniciar(); C.pendientes = {}; C.rechazos = {}; C.retenidas = []; Servidor.opciones.retener = false;
        ir(); registroSim("Datos de ejemplo restaurados."); break;
    }
    pintarSim();
  });

  $("#sim-auto").addEventListener("change", (ev) => {
    clearInterval(autoIntervalo);
    if (ev.target.checked) autoIntervalo = setInterval(() => { if (Servidor.activa()) Servidor.avanzar(); pintarSim(); }, 3000);
  });
  $("#sim-retener").addEventListener("change", (ev) => {
    Servidor.opciones.retener = ev.target.checked;
    if (!ev.target.checked) C.retenidas.splice(0).forEach((f) => f());
    pintarSim();
  });
  $("#sim-rechazar").addEventListener("change", (ev) => { Servidor.opciones.rechazarProxima = ev.target.checked; });
  $("#sim-latencia").addEventListener("input", (ev) => {
    Servidor.opciones.latencia = +ev.target.value;
    $("#sim-latencia-valor").textContent = (ev.target.value / 1000).toFixed(1).replace(".", ",") + " s";
  });

  /* ------------------------------------------------------------------------
     18. Arranque: CRT, reloj, primera ruta
     ------------------------------------------------------------------------ */
  function aplicarCRT(v) {
    document.documentElement.dataset.crt = v;
    const b = $("#alternar-crt");
    if (!b) return; // Propuesta B: sin efectos CRT
    b.setAttribute("aria-pressed", String(v === "on"));
    b.textContent = `CRT: ${v === "on" ? "ON" : "OFF"}`;
  }
  aplicarCRT($("#alternar-crt") ? almacen.leer("nv-crt", "on") : "off");
  if ($("#alternar-crt")) $("#alternar-crt").addEventListener("click", () => {
    const v = document.documentElement.dataset.crt === "on" ? "off" : "on";
    aplicarCRT(v); almacen.escribir("nv-crt", v);
  });

  setInterval(() => {
    $("#reloj").textContent = hora(Date.now());
    if (C.enlace === "perdido") pintarEnlace();
  }, 1000);
  setInterval(() => { $$("[data-hace]").forEach((el) => { el.textContent = haceX(el.dataset.hace); }); }, 10000);
  $("#reloj").textContent = hora(Date.now());

  if (!location.hash) history.replaceState(null, "", "#/tablero");
  navegar(true);
  pintarSim();
})();
