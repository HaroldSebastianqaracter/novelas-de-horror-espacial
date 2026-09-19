"""Construye app/static/lectura.html: la piel de la dirección 3 sobre datos del harness."""
from comun import NAV_HTML, REDUCIDO_JS, atmosfera_de, escribir, leer_maqueta

src, cabeza = leer_maqueta("direccion-3-luz-de-emergencia.html", """
  /* La capital grande es solo para la prosa. El <p> del cierre, dentro de la cabecera del
     capítulo, también es el primero de su padre y heredaba la letra gigante. */
  .texto header .cierre::first-letter{float:none;font-size:inherit;line-height:inherit;padding:0;
                                      color:inherit;font-style:inherit;text-shadow:none}
  /* overflow:hidden convierte la escena en contenedor de desplazamiento y la cabecera pegajosa
     deja de pegarse al hacer scroll; clip recorta igual sin ese efecto secundario. */
  .escena{overflow:clip}

  /* La página crecía con el capítulo: 400 palabras daban 2.200 px y 1.500 pasaban de 6.500, así que
     leer era arrastrar una barra kilométrica y el margen del Extractor quedaba a media altura, lejos
     del párrafo del que hablaba. Ahora la lectura ocupa exactamente una pantalla: el texto y el
     margen tienen cada uno su propia rueda, y su contenido se apaga arriba y abajo como una
     proyección, en vez de cortarse a ras. */
  .pagina{height:calc(100vh - 150px);padding-bottom:0;align-items:stretch}
  .texto,.margen{overflow-y:auto;overscroll-behavior:contain;min-height:0;padding-bottom:64px}
  .texto{-webkit-mask-image:linear-gradient(to bottom,transparent 0,#000 34px,#000 92%,transparent 100%);
                 mask-image:linear-gradient(to bottom,transparent 0,#000 34px,#000 92%,transparent 100%)}
  .margen{-webkit-mask-image:linear-gradient(to bottom,#000 0,#000 93%,transparent 100%);
                  mask-image:linear-gradient(to bottom,#000 0,#000 93%,transparent 100%)}
  .texto::-webkit-scrollbar,.margen::-webkit-scrollbar{width:10px}
  .texto::-webkit-scrollbar-track,.margen::-webkit-scrollbar-track{background:transparent}
  .texto::-webkit-scrollbar-thumb,.margen::-webkit-scrollbar-thumb{
    background:var(--hilo-fuerte);border-radius:5px;border:3px solid transparent;background-clip:content-box}
  .texto::-webkit-scrollbar-thumb:hover,.margen::-webkit-scrollbar-thumb:hover{background:var(--halogeno);background-clip:content-box}
  .texto,.margen{scrollbar-width:thin;scrollbar-color:var(--hilo-fuerte) transparent}
  /* El costillar ya era pegajoso dentro de una página larga; dentro de una pantalla fija sobra. */
  .costillar{position:static;height:auto}
  /* El conflicto que discute el Revisor, una sola vez y antes de los hechos. */
  .margen .discute{margin:0 0 20px;padding:10px 12px;border-left:2px solid var(--emergencia);
    background:rgba(179,38,30,.10);color:#E0685C;font-size:13px;line-height:1.45}
  @media (max-width:1280px){ .pagina{height:calc(100vh - 140px)} }
""")
cabeza = cabeza.replace("<title>", "<title>Lectura · ", 1) if "<title>" in cabeza else cabeza

CUERPO = r'''<body>
<div class="pantalla escena">
''' + NAV_HTML + atmosfera_de(src) + r'''
  <header class="cabecera ui">
    <div class="marco">
      <h1 id="t-cap">Cargando<small id="t-titulo"></small></h1>
    </div>
    <div class="estado" role="status">
      <b id="t-modo">Leyendo...</b>
      <span id="t-novela"></span>
      <div class="ticks" id="ticks" aria-hidden="true"></div>
    </div>
  </header>

  <div class="cuarentena ui" role="status" id="cuarentena" hidden>
    <p id="t-cuarentena"></p>
    <a href="/consola">Ir a la producción</a>
  </div>

  <div class="pagina">
    <nav class="costillar ui" aria-label="Capítulos"><ol id="costillar"></ol></nav>

    <article class="texto" id="texto">
      <header><span class="fantasma" id="fantasma" aria-hidden="true"></span>
        <span class="numero ui" id="t-locacion"></span>
        <h2 id="t-h2"></h2>
        <p class="cierre ui" id="t-cierre"></p>
        <div class="regla-piloto" aria-hidden="true"></div>
      </header>
      <div id="prosa"></div>
      <nav class="siguiente ui" aria-label="Capítulos contiguos" id="contiguos"></nav>
    </article>

    <aside class="margen ui vidrio" aria-labelledby="margen-t">
      <div class="quien">
        <h3 id="margen-t">Lo que el Extractor fijó en este capítulo</h3>
        <span id="t-resumen-hechos"></span>
      </div>
      <p class="discute" id="discute" hidden></p>
      <dl id="hechos"></dl>

      <div class="accion" id="caja-accion" hidden>
        <button type="button" id="btn-conflicto" class="btn-luz" aria-pressed="false">Señalar lo que el Revisor discute<small id="t-btn-ayuda"></small></button>
      </div>

      <div class="actores" id="veredicto">
        <h3>Quién ha tocado este capítulo</h3>
        <ul id="actores"></ul>
      </div>
    </aside>
  </div>
</div>

<script>
(function(){
"use strict";
var $ = function(id){ return document.getElementById(id); };
var indice = null, qa = null, actual = null;

function esc(s){ return String(s == null ? "" : s)
  .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }

// El capítulo es prosa sin encabezados (EX-07): párrafos separados por línea en blanco y nada más.
function parrafos(texto){
  return texto.split(/\n\s*\n/).map(function(p){ return p.trim(); }).filter(Boolean)
    .map(function(p){ return "<p>" + esc(p).replace(/\n/g, " ") + "</p>"; }).join("");
}

// El Revisor cita literalmente los pasajes que discute, entre comillas simples. Esas citas SÍ se
// pueden localizar en el texto; los hechos del Extractor no, porque son paráfrasis, y buscarlos
// sería inventarse la correspondencia y pintar de verde la frase equivocada.
function citasDelRevisor(n){
  if (!qa || !qa.hallazgos) return [];
  var citas = [];
  qa.hallazgos.forEach(function(h){
    if (h.tipo !== "contradiccion") return;
    var d = h.descripcion || "";
    if (d.indexOf("Cap. " + n) !== 0 && h.cap_origen !== n) return;
    (d.match(/'([^']{12,})'/g) || []).forEach(function(c){ citas.push(c.slice(1, -1)); });
  });
  return citas;
}

function marcarCitas(html, citas){
  citas.forEach(function(c){
    var e = esc(c), i = html.indexOf(e);
    if (i >= 0) html = html.slice(0, i) + '<mark class="hecho conflicto">' + e + "</mark>" + html.slice(i + e.length);
  });
  return html;
}

function pintarCostillar(){
  $("costillar").innerHTML = indice.capitulos.map(function(c){
    var clase = c.num === actual.num ? "actual" : (c.escrito ? "leido" : "sellado");
    // En una novela larga el costillar solo numera de cinco en cinco para no amontonarse; en una
    // corta caben todos, y esconder el «2» de un libro de tres capítulos no ahorra nada.
    var visible = (indice.capitulos.length <= 12
                   || c.num % 5 === 0 || c.num === 1 || c.num === actual.num);
    var txt = c.num === actual.num ? c.num + ", estás aquí" : (visible ? c.num : "");
    var tit = "Capítulo " + c.num + (c.titulo ? ": " + esc(c.titulo) : "");
    var celda = c.escrito
      ? '<a href="?cap=' + c.num + '"' + (c.num === actual.num ? ' aria-current="page"' : "") +
        ' title="' + tit + '"><i aria-hidden="true"></i>' + txt + "</a>"
      : '<span title="' + tit + ', todavía sin escribir"><i aria-hidden="true"></i>' + txt + "</span>";
    var pausa = c.corte_qa ? '<li class="pausa"><span><i aria-hidden="true"></i>revisor</span></li>' : "";
    return '<li class="' + clase + '">' + celda + "</li>" + pausa;
  }).join("");
}

function pintarContiguos(){
  var escritos = indice.capitulos.filter(function(c){ return c.escrito; }).map(function(c){ return c.num; });
  var i = escritos.indexOf(actual.num), h = "";
  if (i > 0) { var a = indice.capitulos[escritos[i-1]-1];
    h += '<a href="?cap=' + a.num + '">Capítulo ' + a.num + (a.titulo ? ", " + esc(a.titulo) : "") + "<small>anterior</small></a>"; }
  if (i >= 0 && i < escritos.length - 1) { var s = indice.capitulos[escritos[i+1]-1];
    h += '<a href="?cap=' + s.num + '">Capítulo ' + s.num + (s.titulo ? ", " + esc(s.titulo) : "") + "<small>siguiente</small></a>"; }
  $("contiguos").innerHTML = h;
}

function pintarHechos(){
  var hs = actual.hechos || [];
  $("t-resumen-hechos").textContent = hs.length
    ? (hs.length === 1 ? "Un hecho. " : hs.length + " hechos. ") +
      "A partir de aquí el Escritor no puede contradecirlos sin que el Revisor lo vea."
    : "El Extractor no fijó ningún hecho nuevo en este capítulo.";
  // La contradicción es del capítulo, no de un hecho concreto: QA no dice cuál la provoca. Antes se
  // repetía bajo cada uno, así que un capítulo con cuatro hechos enseñaba cuatro veces el mismo
  // párrafo rojo y el margen se estiraba sin decir nada nuevo.
  var d = $("discute");
  if (actual.conflicto) { d.textContent = "El Revisor discute: " + actual.conflicto; d.hidden = false; }
  else d.hidden = true;
  $("hechos").innerHTML = hs.map(function(h){
    var s = "<dt>" + esc(h.sujeto || h.categoria || "Sin sujeto") + "</dt><dd>" + esc(h.hecho) + "</dd>";
    if (h.superado_por) s += '<dd class="conflicto">Superado por un hecho posterior.</dd>';
    return s;
  }).join("");
}

function pintarActores(){
  var hs = actual.hechos || [];
  var ficha = indice.capitulos[actual.num - 1] || {};
  var discutido = hs.some(function(h){ return h.conflicto; });
  var li = ["<li><b>Escritor</b>, redactó " + actual.palabras.toLocaleString("es-ES") + " palabras.</li>",
            "<li><b>Extractor de hechos</b>, fijó " + (hs.length || "cero") + (hs.length === 1 ? " hecho" : " hechos") + ".</li>",
            "<li><b>Revisor de calidad</b>, " + (ficha.corte_qa
              ? "detuvo la producción al cerrar este capítulo."
              : discutido ? "señala este capítulo como origen de una contradicción posterior."
                          : "no ha puesto reparos a este capítulo.") + "</li>"];
  $("actores").innerHTML = li.join("");
}

function pintar(){
  document.title = "Capítulo " + actual.num + " · " + indice.titulo;
  $("t-cap").firstChild.nodeValue = "Capítulo " + actual.num + " de " + indice.total_capitulos;
  $("t-titulo").textContent = actual.titulo || "";
  $("t-novela").textContent = indice.titulo;
  $("fantasma").textContent = actual.num;
  $("t-h2").textContent = actual.titulo || "Capítulo " + actual.num;
  $("t-locacion").textContent = actual.locacion ? "//" + actual.locacion : "";
  $("t-cierre").textContent = actual.palabras.toLocaleString("es-ES") + " palabras, cerradas por el Escritor.";

  $("ticks").innerHTML = indice.capitulos.map(function(c){
    return "<i class='" + (c.corte_qa ? "stop" : c.escrito ? "on" : "") + "'></i>";
  }).join("");

  var citas = citasDelRevisor(actual.num);
  $("prosa").innerHTML = marcarCitas(parrafos(actual.texto), citas);
  $("caja-accion").hidden = citas.length === 0;
  $("t-btn-ayuda").textContent = citas.length === 1
    ? "El Revisor cita un pasaje de este capítulo en su veredicto."
    : "El Revisor cita " + citas.length + " pasajes de este capítulo en su veredicto.";

  pintarCostillar(); pintarContiguos(); pintarHechos(); pintarActores();
}

function pintarCuarentena(){
  if (indice.estado !== "pausado_por_qa" || !qa || !qa.hallazgos) return;
  var c = qa.hallazgos.filter(function(h){ return h.tipo === "contradiccion"; }).length;
  var r = qa.hallazgos.filter(function(h){ return h.tipo === "repeticion"; }).length;
  $("t-cuarentena").innerHTML = "<b>//Producción detenida en el capítulo " + esc(qa.cap_corte) + ".</b> " +
    "El Revisor de calidad ha encontrado " + c + (c === 1 ? " contradicción" : " contradicciones") +
    " con hechos establecidos y " + r + (r === 1 ? " repetición" : " repeticiones") +
    " de lenguaje. Puedes leer lo cerrado; nada nuevo se escribe hasta que decidas.";
  $("cuarentena").hidden = false;
  $("t-modo").textContent = "Detenida...";
}

function fallo(mensaje){
  $("t-cap").firstChild.nodeValue = "No se puede leer";
  $("prosa").innerHTML = "<p>" + esc(mensaje) + "</p>";
}

fetch("/api/indice").then(function(r){ return r.json(); }).then(function(d){
  indice = d;
  var escritos = indice.capitulos.filter(function(c){ return c.escrito; });
  if (!escritos.length) { fallo("Todavía no hay ningún capítulo escrito. Cuando el Escritor cierre el primero, aparecerá aquí."); return; }
  var pedido = parseInt(new URLSearchParams(location.search).get("cap"), 10);
  var n = escritos.some(function(c){ return c.num === pedido; }) ? pedido : escritos[escritos.length - 1].num;
  return fetch("/api/qa").then(function(r){ return r.ok ? r.json() : null; })
    .then(function(d2){ qa = d2; return fetch("/api/capitulo/" + n); })
    .then(function(r){ return r.json(); })
    .then(function(cap){ actual = cap; pintar(); pintarCuarentena(); });
}).catch(function(e){ fallo("No se pudo hablar con el harness: " + e.message); });

$("btn-conflicto").addEventListener("click", function(){
  var on = document.body.classList.toggle("hechos");
  this.setAttribute("aria-pressed", on ? "true" : "false");
  this.firstChild.nodeValue = on ? "Ocultar lo que el Revisor discute" : "Señalar lo que el Revisor discute";
});
})();
</script>
''' + REDUCIDO_JS + r'''</body>
</html>
'''

escribir("lectura.html", cabeza + CUERPO)
