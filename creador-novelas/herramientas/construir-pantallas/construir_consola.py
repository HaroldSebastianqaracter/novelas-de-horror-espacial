"""Construye app/static/consola.html: la dirección 1 sobre datos del harness."""
from comun import NAV_HTML, escribir, leer_maqueta

src, cabeza = leer_maqueta("direccion-1-sala-de-maquinas.html")

# El plano entero, tal como lo entregó el diseño. No se toca: solo se le da nombre a las cubiertas.
plano = src[src.index('<section class="plano"'):src.index("</section>", src.index('<section class="plano"')) + len("</section>")]

# Las cubiertas se encienden según quién trabaje, no con un interruptor global. La maqueta gobierna
# todo con `body.en-marcha` (reanudar/detener); aquí manda `body[data-vista]` (el estado del
# manifiesto) y `body[data-activo]` (el agente que está trabajando ahora mismo).
VIEJAS = """  .plano .relleno[data-agente="revisor"]{opacity:.85}
  body.en-marcha .plano .relleno[data-agente="revisor"]{opacity:0}
  body.en-marcha .plano .relleno[data-agente="orquestador"]{opacity:.8;transition-delay:200ms}
  body.en-marcha .plano .relleno[data-agente="escritor"]{opacity:.8;transition-delay:600ms}
  body.en-marcha .plano .relleno[data-agente="extractor"]{opacity:.55;transition-delay:1000ms}"""
NUEVAS = """  body[data-vista="pausado_por_qa"] .plano .relleno[data-agente="revisor"]{opacity:.85}
  body[data-activo="qa"] .plano .relleno[data-agente="revisor"]{opacity:.85}
  body[data-activo="orquestador"] .plano .relleno[data-agente="orquestador"]{opacity:.8}
  body[data-activo="escritor"] .plano .relleno[data-agente="escritor"]{opacity:.8}
  body[data-activo="extractor"] .plano .relleno[data-agente="extractor"]{opacity:.55}
  /* En marcha sin saber aún quién trabaja: el puente queda tenue para que no parezca apagada. */
  body[data-vista="en_progreso"]:not([data-activo]) .plano .relleno[data-agente="orquestador"]{opacity:.35}
  .pie .acciones button[disabled]{opacity:.4;cursor:not-allowed}
  .pie .acciones button.peligro{border-color:var(--rojo)}
  .aviso-lanzar{grid-column:1/-1;color:var(--texto-bajo);font-size:13px;margin-top:6px}
  /* La preparación es una secuencia con orden: se enseña entera para que se vea cuánto falta,
     pero solo el paso pendiente lleva botón. Los demás no se pueden lanzar aunque se quiera. */
  .preludio{grid-column:1/-1;list-style:none;margin:10px 0 0;padding:0;
            border-top:1px solid var(--linea-tenue)}
  .preludio li{display:grid;grid-template-columns:22px 1fr auto;gap:0 10px;align-items:baseline;
               padding:6px 0;border-bottom:1px solid var(--linea-tenue)}
  .preludio .marca{color:var(--verde)}
  .preludio li[data-estado="pendiente"]{color:var(--texto-bajo)}
  .preludio li[data-estado="ahora"]{color:var(--texto)}
  .preludio small{grid-column:2/-1;color:var(--texto-bajo);font-size:12.5px}
  /* El diseño reservó 44px para «14:52»; el registro real anota «12:04:11» y se pegaba al texto. */
  .pie .registro li{grid-template-columns:64px 1fr}
  /* La barra de navegación es la primera fila de la pantalla y va de borde a borde. */
  .pantalla{grid-template-rows:auto auto 1fr auto auto}
  .pantalla > .ir{margin:-36px -56px 0}
  @media (max-width:1280px){.pantalla > .ir{margin:-28px -36px 0}}
  /* En reposo el veredicto no es una alarma: sin rojo en el titular ni en el halo, y el botón de
     arrancar en verde, que es el color de «en marcha». */
  body[data-vista="inactivo"] .veredicto h2 b{color:var(--texto)}
  body[data-vista="inactivo"] .veredicto.marco::before,body[data-vista="inactivo"] .veredicto.marco::after{animation-name:halo}
  body[data-vista="inactivo"] .veredicto button.primario{border-color:var(--verde);color:#fff;background:rgba(123,227,178,.14)}"""
assert VIEJAS in cabeza, "las reglas de encendido no están donde se esperaba"
cabeza = cabeza.replace(VIEJAS, NUEVAS)

# El parpadeo: la maqueta hace latir el ramal en rojo siempre (la animación pisa la opacidad, así
# que se vería aun con el revisor apagado) y lo apaga con `en-marcha`. Aquí late solo cuando el
# revisor ha detenido la nave; y cuando un agente trabaja, respira su cubierta y ninguna otra.
PARPADEO_VIEJO = """  .plano .relleno[data-agente="revisor"]{animation:parpadeo-emergencia 1.6s steps(1,end) infinite}
  .cargando .ticks i.stop{animation:parpadeo-emergencia 1.6s steps(1,end) infinite}
  body.en-marcha .plano .relleno[data-agente="revisor"],body.en-marcha .cargando .ticks i.stop{animation:none}
  body.en-marcha .plano .relleno[data-agente="orquestador"]{animation:parpadeo-trabajo 2.4s ease-in-out .2s infinite}
  body.en-marcha .plano .relleno[data-agente="escritor"]{animation:parpadeo-trabajo 1.4s ease-in-out .6s infinite}
  body.en-marcha .plano .relleno[data-agente="extractor"]{animation:parpadeo-trabajo-bajo 3s ease-in-out 1s infinite}"""
PARPADEO_NUEVO = """  body[data-vista="pausado_por_qa"] .plano .relleno[data-agente="revisor"]{animation:parpadeo-emergencia 1.6s steps(1,end) infinite}
  body[data-vista="pausado_por_qa"] .cargando .ticks i.stop{animation:parpadeo-emergencia 1.6s steps(1,end) infinite}
  body[data-activo="qa"] .plano .relleno[data-agente="revisor"]{animation:parpadeo-trabajo 1.8s ease-in-out infinite}
  body[data-activo="orquestador"] .plano .relleno[data-agente="orquestador"]{animation:parpadeo-trabajo 2.4s ease-in-out .2s infinite}
  body[data-activo="escritor"] .plano .relleno[data-agente="escritor"]{animation:parpadeo-trabajo 1.4s ease-in-out .6s infinite}
  body[data-activo="extractor"] .plano .relleno[data-agente="extractor"]{animation:parpadeo-trabajo-bajo 3s ease-in-out 1s infinite}"""
assert PARPADEO_VIEJO in cabeza, "las reglas de parpadeo no están donde se esperaba"
cabeza = cabeza.replace(PARPADEO_VIEJO, PARPADEO_NUEVO)

# Al reanudar, la maqueta pintaba de verde las marcas de parada de la cabecera. Aquí esas marcas
# son los capítulos con hallazgos y siguen siéndolo aunque la máquina vuelva a andar.
TICKS_VERDES = "  body.en-marcha .cargando .ticks i.stop{background:var(--verde)}\n"
assert TICKS_VERDES in cabeza
cabeza = cabeza.replace(TICKS_VERDES, "")
# Lo que queda de `en-marcha` (titular en verde, halo normal, haz rojo más lento) es lo que debe
# pasar mientras la máquina trabaja.
cabeza = cabeza.replace("body.en-marcha", 'body[data-vista="en_progreso"]')
assert "en-marcha" not in cabeza

# Los subrótulos de las cubiertas llevan el estado de cada agente: hay que poder escribirlos.
for viejo, ident in (("Escritor, capítulo 7 en espera", "r-escritor"),
                     ("Extractor, 41 hechos fijados", "r-extractor"),
                     ("Revisor, ha detenido la nave", "r-revisor"),
                     ("Orquestador, espera", "r-orquestador")):
    assert viejo in plano, viejo
    plano = plano.replace(f">{viejo}<", f' id="{ident}">{viejo}<')
# El rótulo del puente se sale por la derecha del viewBox, que mide 1240: «Orquestador, esperando»
# empieza en 1126 y no cabe. Se corre a la izquierda en vez de recortar el texto.
plano = plano.replace('<text x="1126"', '<text x="1080"')
# El pie del plano nombraba «El casco frío del Falcon» a fuego. Es el libro en producción.
plano = plano.replace(">El casco frío del Falcon, corte longitudinal, cubierta de trabajo<",
                      ' id="pie-plano">Corte longitudinal, cubierta de trabajo<')
assert 'id="pie-plano"' in plano

CUERPO = '''<body>
<main class="pantalla">
  <div class="fx fx-barrido" aria-hidden="true"></div>
  <div class="fx fx-haz" aria-hidden="true"></div>
''' + NAV_HTML + '''  <header class="cabecera">
    <div class="marco">
      <h1 id="t-cap">Cargando<small id="t-titulo"></small></h1>
      <p class="premisa" id="t-premisa"></p>
    </div>
    <div class="cargando" role="status">
      <b id="estado-txt"><span id="estado-palabra">...</span><span class="puntos" id="puntos" aria-hidden="true" hidden></span></b>
      <span id="t-agente"></span>
      <div class="ticks" id="ticks" aria-hidden="true"></div>
    </div>
  </header>

''' + plano + '''

  <section class="indicadores" aria-label="Indicadores de producción">
    <div class="ind">
      <span class="nombre">Capítulos cerrados</span><span class="valor" id="v-caps">-</span>
      <div class="barra" aria-hidden="true"><i class="verde" id="b-caps" style="width:0%"></i><span class="marca" id="m-caps" style="left:0%"></span></div>
      <span class="nota" id="n-caps"></span>
    </div>
    <div class="ind">
      <span class="nombre">Gastado hasta ahora</span><span class="valor" id="v-coste">-</span>
      <div class="barra" aria-hidden="true"><i class="rojo" id="b-coste" style="width:0%"></i></div>
      <span class="nota" id="n-coste"></span>
    </div>
    <div class="ind">
      <span class="nombre" id="e-tiempo">Tiempo</span><span class="valor" id="v-tiempo">-</span>
      <div class="barra" aria-hidden="true"><i id="b-tiempo" style="width:0%"></i></div>
      <span class="nota" id="n-tiempo"></span>
    </div>
  </section>

  <footer class="pie">
    <div class="marco veredicto" role="alert">
      <h2><b id="veredicto-t">Leyendo el estado</b><span id="veredicto-h2"></span></h2>
      <p id="veredicto-p"></p>
      <div class="acciones" id="acciones"></div>
      <ol class="preludio" id="preludio" hidden></ol>
      <p class="aviso-lanzar" id="aviso"></p>
    </div>
    <div class="registro">
      <h2>Registro de a bordo</h2>
      <ol reversed id="registro"></ol>
    </div>
  </footer>
</main>

<script>
(function(){
"use strict";
var $ = function(id){ return document.getElementById(id); };
var estado = null, qa = null, coste = null, lanzando = false;

function esc(s){ return String(s == null ? "" : s)
  .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }

function dinero(n, moneda){
  if (n == null) return "-";
  return n.toLocaleString("es-ES", {style:"currency", currency: moneda || "USD", currencyDisplay:"narrowSymbol", maximumFractionDigits:2});
}

function duracion(segundos){
  if (segundos == null || !isFinite(segundos)) return "-";
  var h = Math.floor(segundos/3600), m = Math.round((segundos%3600)/60);
  return h ? h + " h " + m + " min" : m + " min";
}

var NOMBRE_AGENTE = {escritor:"Escritor", extractor:"Extractor de hechos",
                     qa:"Revisor de calidad", orquestador:"Orquestador"};

function pintarCabecera(){
  var e = estado;
  $("t-cap").firstChild.nodeValue = e.total_capitulos
    ? "Capítulo " + (e.capitulo_actual || "-") + " de " + e.total_capitulos : "Sin novela en curso";
  $("t-titulo").textContent = e.titulo_capitulo || "";
  $("t-premisa").textContent = e.logline || "";
  var pie = $("pie-plano");
  // Centrado en la cota; con el título delante crecía hacia la izquierda y pisaba la etiqueta de la
  // bodega de minería, así que lleva el título o la coletilla, no las dos cosas.
  if (pie) pie.textContent = e.titulo ? e.titulo + ", corte longitudinal" : "Corte longitudinal, cubierta de trabajo";

  // Los puntos suspensivos se escriben solos (CSS) mientras la máquina hace algo o espera una
  // decisión; en reposo o con error no hay nada que esperar y se quitan.
  var palabra = {en_progreso:"Escribiendo", pausado_por_qa:"Detenido",
                 error:"Con un error", inactivo:"En reposo"}[e.estado] || e.estado;
  $("estado-palabra").textContent = palabra;
  $("puntos").hidden = !(e.estado === "en_progreso" || e.estado === "pausado_por_qa");
  $("t-agente").textContent = e.agente_activo ? NOMBRE_AGENTE[e.agente_activo] || e.agente_activo
                                              : (e.estado === "pausado_por_qa" ? "Revisor de calidad" : "");
  document.body.setAttribute("data-vista", e.estado);
  if (e.agente_activo) document.body.setAttribute("data-activo", e.agente_activo);
  else document.body.removeAttribute("data-activo");

  var total = e.total_capitulos || 0, cerrados = e.capitulos_cerrados || 0;
  var cortes = {}; (e.capitulos_con_hallazgos || []).forEach(function(n){ cortes[n] = true; });
  var t = [];
  for (var i = 1; i <= total; i++)
    t.push("<i class='" + (cortes[i] ? "stop" : i <= cerrados ? "on" : "") + "'></i>");
  $("ticks").innerHTML = t.join("");
}

function pintarRotulos(){
  var e = estado;
  var r = function(id, txt){ var n = $(id); if (n) n.textContent = txt; };
  r("r-escritor", e.agente_activo === "escritor"
      ? "Escritor, escribiendo el capítulo " + e.capitulo_actual
      : "Escritor, capítulo " + (e.capitulo_actual || "-") + " en espera");
  r("r-extractor", e.agente_activo === "extractor"
      ? "Extractor, leyendo el capítulo " + e.capitulo_actual : "Extractor de hechos");
  r("r-revisor", e.estado === "pausado_por_qa"
      ? "Revisor, ha detenido la nave" : e.agente_activo === "qa" ? "Revisor, auditando" : "Revisor, en espera");
  r("r-orquestador", e.agente_activo === "orquestador" ? "Orquestador, repartiendo" : "Orquestador, espera");
}

function pintarIndicadores(){
  var e = estado, total = e.total_capitulos || 0, cerrados = e.capitulos_cerrados || 0;
  $("v-caps").textContent = cerrados + " de " + (total || "-");
  $("b-caps").style.width = total ? (cerrados/total*100).toFixed(1) + "%" : "0%";
  var ultima = e.cadencia_qa ? Math.floor(cerrados / e.cadencia_qa) * e.cadencia_qa : 0;
  $("m-caps").style.width = "2px";
  $("m-caps").style.left = total ? (ultima/total*100).toFixed(1) + "%" : "0%";
  $("n-caps").textContent = e.cadencia_qa
    ? "El revisor audita cada " + e.cadencia_qa + "; la marca ámbar es la última auditoría."
    : "";

  if (coste) {
    $("v-coste").textContent = dinero(coste.total, coste.moneda);
    var porCap = cerrados ? coste.total / cerrados : 0;
    $("b-coste").style.width = total && porCap ? Math.min(100, coste.total/(porCap*total)*100).toFixed(1) + "%" : "0%";
    $("n-coste").textContent = cerrados
      ? "A " + dinero(porCap, coste.moneda) + " por capítulo cerrado; la novela entera saldría por "
        + dinero(porCap*total, coste.moneda) + "."
      : "Todavía no hay ningún capítulo cerrado que promediar.";
    if (coste.modelos_sin_precio && coste.modelos_sin_precio.length)
      $("n-coste").textContent += " Sin precio para " + coste.modelos_sin_precio.join(", ") + ": no están contados.";
  }

  if (e.agente_activo && e.agente_desde) {
    var seg = (Date.now() - new Date(e.agente_desde).getTime())/1000;
    $("e-tiempo").textContent = "Lleva trabajando";
    $("v-tiempo").textContent = duracion(seg);
    $("b-tiempo").style.width = Math.min(100, seg/600*100).toFixed(1) + "%";
    $("n-tiempo").textContent = "Un capítulo tarda unos cinco minutos. En pausa la máquina no cobra.";
  } else {
    $("e-tiempo").textContent = "Tiempo";
    $("v-tiempo").textContent = "en reposo";
    $("b-tiempo").style.width = "0%";
    $("n-tiempo").textContent = "Nada en marcha ahora mismo.";
  }
}

function boton(fase, etiqueta, clase){
  return '<button type="button" data-fase="' + fase + '"' + (clase ? ' class="' + clase + '"' : "") +
         (lanzando ? " disabled" : "") + ">" + esc(etiqueta) + "</button>";
}

// Las cinco fases de preparación, en el orden que fija CLAUDE.md. Cada una deja un artefacto y
// la siguiente lo necesita: no es una lista de opciones, es una cadena.
var PRELUDIO = [
  {fase:"destilar-estilo", clave:"style_guide", nombre:"Destilar el estilo",
   nota:"Lee las obras de referencia y escribe la guía de estilo."},
  {fase:"generar-premisa", clave:"premisa", nombre:"Generar la premisa",
   nota:"Convierte tu idea en premisa, logline y título."},
  {fase:"generar-sinopsis", clave:"tres_actos", nombre:"Generar la sinopsis",
   nota:"Gancho, punto medio y clímax."},
  {fase:"generar-escaleta", clave:"capitulos", nombre:"Generar la escaleta",
   nota:"Un objetivo, una locación y unos personajes por capítulo."},
  {fase:"inicializar-estado", clave:"estado_inicializado", nombre:"Inicializar el estado",
   nota:"Personajes, mundo y registro de continuidad."}
];

function pasosPendientes(){
  var a = estado.artefactos || {};
  return PRELUDIO.filter(function(p){
    // Sin referencias no hay estilo que destilar: el paso se salta en vez de bloquear la cadena.
    if (p.fase === "destilar-estilo" && !estado.tiene_referencias) return false;
    return !a[p.clave];
  });
}

function pintarPreludio(){
  var a = estado.artefactos || {};
  var pendientes = pasosPendientes();
  var caja = $("preludio");
  if (!a.idea || !pendientes.length || estado.estado === "en_progreso") { caja.hidden = true; return; }
  var siguiente = pendientes[0];
  caja.innerHTML = PRELUDIO.map(function(p){
    var saltado = p.fase === "destilar-estilo" && !estado.tiene_referencias;
    var hecho = !!a[p.clave] || saltado;
    var ahora = p.fase === siguiente.fase;
    return '<li data-estado="' + (hecho ? "hecho" : ahora ? "ahora" : "pendiente") + '">' +
      '<span class="marca">' + (hecho ? "\\u2713" : "\\u00b7") + "</span>" +
      "<span>" + esc(p.nombre) + "</span>" +
      (ahora ? boton(p.fase, "Lanzar") : "<span>" + (saltado ? "sin referencias" : hecho ? "" : "en espera") + "</span>") +
      "<small>" + esc(p.nota) + "</small></li>";
  }).join("");
  caja.hidden = false;
}

function pintarVeredicto(){
  var e = estado, h2 = $("veredicto-t"), extra = $("veredicto-h2"), p = $("veredicto-p"), acc = [];

  if (e.estado === "pausado_por_qa" && qa) {
    var c = (qa.hallazgos||[]).filter(function(x){ return x.tipo === "contradiccion"; }).length;
    var r = (qa.hallazgos||[]).filter(function(x){ return x.tipo === "repeticion"; }).length;
    h2.textContent = "El revisor ha detenido la producción";
    extra.textContent = " al cerrar el capítulo " + qa.cap_corte + ".";
    p.textContent = c + (c===1?" contradicción":" contradicciones") + " con hechos ya establecidos y " +
                    r + (r===1?" repetición":" repeticiones") + " de lenguaje. Nada se escribe hasta que decidas.";
    acc.push('<a class="primario" href="/lectura?cap=' + qa.cap_corte + '">Leer el capítulo señalado</a>');
    acc.push(boton("reanudar", "Reanudar bajo mi responsabilidad", "peligro"));
  } else if (e.estado === "en_progreso") {
    h2.textContent = "La máquina está trabajando";
    extra.textContent = e.agente_activo ? ". Ahora mismo, el " + (NOMBRE_AGENTE[e.agente_activo]||e.agente_activo) + "." : ".";
    p.textContent = "No se puede lanzar nada más mientras tanto: dos ejecuciones sobre el mismo estado lo corromperían.";
  } else if (e.estado === "error") {
    h2.textContent = "La última ejecución terminó con un error";
    extra.textContent = ".";
    p.textContent = e.ultimo_error || "El manifiesto guarda el detalle.";
    acc.push(boton("escribir-tanda", "Reintentar la tanda"));
  } else {
    var a = e.artefactos || {};
    var faltan = pasosPendientes();
    if (!a.idea) {
      h2.textContent = "Todavía no hay ningún libro";
      extra.textContent = ".";
      p.textContent = "Empieza por el encargo: la premisa, los capítulos y los ajustes.";
      acc.push('<a class="primario" href="/encargo">Ir al encargo</a>');
      $("acciones").innerHTML = acc.join("");
      $("aviso").textContent = lanzando ? "Lanzando…" : "";
      return;
    }
    if (faltan.length) {
      h2.textContent = "El libro está encargado y falta prepararlo";
      extra.textContent = ": " + faltan.length + (faltan.length === 1 ? " paso." : " pasos.");
      p.textContent = "Cada paso deja un artefacto que el siguiente necesita, así que van en orden. " +
                      "Se lanzan de uno en uno y tardan un rato cada uno.";
      $("acciones").innerHTML = "";
      $("aviso").textContent = lanzando ? "Lanzando…" : "";
      return;
    }
    h2.textContent = e.capitulos_cerrados ? "En reposo" : "Preparado, sin escribir todavía";
    extra.textContent = e.capitulos_cerrados ? ", con " + e.capitulos_cerrados + " capítulos cerrados." : ".";
    p.textContent = e.capitulos_cerrados
      ? "Puedes lanzar la siguiente tanda o montar lo que ya hay en un solo archivo."
      : "El estilo, la premisa, la sinopsis, la escaleta y el estado están listos. Falta escribir.";
    if (!e.capitulos_cerrados) {
      acc.push(boton("escribir-tanda", "Escribir la primera tanda", "primario"));
    } else {
      acc.push(boton("escribir-tanda", "Escribir la siguiente tanda", "primario"));
      acc.push(boton("ensamblar", "Ensamblar lo cerrado"));
      acc.push('<a href="/lectura">Leer lo escrito</a>');
    }
  }
  $("acciones").innerHTML = acc.join("");
  $("aviso").textContent = lanzando ? "Lanzando…" : "";
}

function pintarRegistro(evs){
  // Los eventos llegan como {ts, tipo, texto}. El tipo decide si la línea se destaca en rojo:
  // un bloqueo de hook o un error son lo único que merece robar la atención en un registro.
  $("registro").innerHTML = (evs||[]).map(function(ev){
    var grave = ev.tipo === "error" || ev.tipo === "bloqueo";
    return "<li" + (grave ? ' class="rev"' : "") + "><time>" + esc(ev.ts || "") + "</time><span>" +
           esc(ev.texto || "") + "</span></li>";
  }).join("") || "<li><time></time><span>Todavía no hay eventos registrados.</span></li>";
}

function refrescar(){
  return Promise.all([
    fetch("/api/estado").then(function(r){ return r.json(); }),
    fetch("/api/eventos").then(function(r){ return r.json(); }),
    fetch("/api/coste").then(function(r){ return r.ok ? r.json() : null; }),
    fetch("/api/qa").then(function(r){ return r.ok ? r.json() : null; })
  ]).then(function(xs){
    estado = xs[0]; coste = xs[2]; qa = xs[3];
    pintarCabecera(); pintarRotulos(); pintarIndicadores(); pintarVeredicto();
    pintarPreludio(); pintarRegistro(xs[1]);
  }).catch(function(e){
    $("veredicto-t").textContent = "No se puede hablar con el harness";
    $("veredicto-p").textContent = e.message;
  });
}

function alPulsar(ev){
  var b = ev.target.closest("button[data-fase]");
  if (!b || lanzando) return;
  var fase = b.getAttribute("data-fase");
  if (fase === "reanudar" && !confirm(
      "Reanudar sin corregir nada.\\n\\nEl revisor deja constancia de que aceptaste su veredicto y las " +
      "contradicciones quedan abiertas en la novela. Esto no se deshace.")) return;
  lanzando = true; pintarVeredicto();
  fetch("/api/fase/" + fase, {method:"POST"})
    .then(function(r){ return r.json().then(function(d){ return {ok:r.ok, d:d}; }); })
    .then(function(x){
      lanzando = false;
      if (!x.ok) { $("aviso").textContent = x.d.error || "No se pudo lanzar."; return; }
      return refrescar();
    })
    .catch(function(e){ lanzando = false; $("aviso").textContent = e.message; });
}
$("acciones").addEventListener("click", alPulsar);
$("preludio").addEventListener("click", alPulsar);

refrescar();
setInterval(refrescar, 5000);  // el estado se lee del disco; 5 s es suficiente y no castiga a nadie
})();
</script>
</body>
</html>
'''

escribir("consola.html", cabeza + CUERPO)
