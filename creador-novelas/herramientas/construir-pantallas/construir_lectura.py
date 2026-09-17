"""Construye app/static/lectura.html: la piel de la direccion 3 sobre datos del harness."""
from pathlib import Path

BASE = Path(r"C:\Users\harold.rodriguez\Desktop\Nueva carpeta\novelas-de-horror-espacial")
src = (BASE / "falcon-diseno/html/direccion-3-luz-de-emergencia.html").read_text(encoding="utf-8")
cabeza = src[:src.index("<body>")]
cabeza = cabeza.replace("<title>", "<title>Lectura · ", 1) if "<title>" in cabeza else cabeza

# --- barra de navegacion, comun a las cuatro pantallas ---
NAV_CSS = """  .ir{display:flex;flex-wrap:wrap;gap:2px;align-items:baseline;padding:10px 28px;font-size:13.5px;
      border-bottom:1px solid color-mix(in srgb, currentColor 18%, transparent)}
  .ir b{font-weight:400;opacity:.45;margin-right:14px}
  .ir a{color:inherit;opacity:.5;text-decoration:none;padding:3px 11px;border:1px solid transparent}
  .ir a:hover{opacity:1}
  .ir a:focus-visible{opacity:1;outline:2px solid currentColor;outline-offset:1px}
  .ir a[aria-current="page"]{opacity:1;border-color:color-mix(in srgb, currentColor 45%, transparent)}
  @media (max-width:640px){ .ir{padding:8px 16px} }
"""
NAV_HTML = """<nav class="ir" aria-label="Secciones">
  <b>Creador de novelas</b>
  <a href="/">Biblioteca</a>
  <a href="/encargo">Encargo</a>
  <a href="/consola">Producción</a>
  <a href="/lectura">Lectura</a>
</nav>
<script>
  // Marca la seccion en la que estas. Va aqui y no en cada pagina para que las cuatro barras sean
  // literalmente la misma y no se desincronicen al tocar una.
  (function(){
    // Las paginas se sirven desde /static/*.html --las rutas bonitas son redirecciones--, asi que
    // la seccion activa se deduce del nombre del archivo y no de la ruta, que nunca coincidiria.
    var donde = {"vestuario.html":"/", "encargo.html":"/encargo",
                 "consola.html":"/consola", "lectura.html":"/lectura"};
    var aqui = donde[location.pathname.split("/").pop()] || location.pathname;
    document.querySelectorAll(".ir a").forEach(function(a){
      if (a.getAttribute("href") === aqui) a.setAttribute("aria-current", "page");
    });
  })();
</script>
"""
assert "</style>" in cabeza, "la maqueta no trae hoja de estilos donde colgar la navegacion"
cabeza = cabeza.replace("</style>", NAV_CSS + "</style>", 1)

CUERPO = r'''<body>
''' + NAV_HTML + r'''<div class="pantalla">
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
      <header>
        <span class="numero ui" id="t-locacion"></span>
        <h2 id="t-h2"></h2>
        <p class="cierre ui" id="t-cierre"></p>
      </header>
      <div id="prosa"></div>
      <nav class="siguiente ui" aria-label="Capítulos contiguos" id="contiguos"></nav>
    </article>

    <aside class="margen ui" aria-labelledby="margen-t">
      <div class="quien">
        <h3 id="margen-t">Lo que el Extractor fijó en este capítulo</h3>
        <span id="t-resumen-hechos"></span>
      </div>
      <dl id="hechos"></dl>

      <div class="accion" id="caja-accion" hidden>
        <button type="button" id="btn-conflicto" aria-pressed="false">Señalar lo que el Revisor discute<small id="t-btn-ayuda"></small></button>
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

// El capitulo es prosa sin encabezados (EX-07): parrafos separados por linea en blanco y nada mas.
function parrafos(texto){
  return texto.split(/\n\s*\n/).map(function(p){ return p.trim(); }).filter(Boolean)
    .map(function(p){ return "<p>" + esc(p).replace(/\n/g, " ") + "</p>"; }).join("");
}

// El Revisor cita literalmente los pasajes que discute, entre comillas simples. Esas citas SI se
// pueden localizar en el texto; los hechos del Extractor no, porque son parafrasis, y buscarlos
// seria inventarse la correspondencia y pintar de verde la frase equivocada.
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
    var visible = (c.num % 5 === 0 || c.num === 1 || c.num === actual.num);
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
  $("hechos").innerHTML = hs.map(function(h){
    var s = "<dt>" + esc(h.sujeto || h.categoria || "Sin sujeto") + "</dt><dd>" + esc(h.hecho) + "</dd>";
    if (h.superado_por) s += '<dd class="conflicto">Superado por un hecho posterior.</dd>';
    if (h.conflicto) s += '<dd class="conflicto">' + esc(h.conflicto) + "</dd>";
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
  document.title = "Capítulo " + actual.num + " \u00b7 " + indice.titulo;
  $("t-cap").firstChild.nodeValue = "Capítulo " + actual.num + " de " + indice.total_capitulos;
  $("t-titulo").textContent = actual.titulo || "";
  $("t-novela").textContent = indice.titulo;
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
</body>
</html>
'''

destino = BASE / "creador-novelas/app/static/lectura.html"
destino.write_text(cabeza + CUERPO, encoding="utf-8")
print("lectura.html:", len(cabeza + CUERPO), "bytes")
