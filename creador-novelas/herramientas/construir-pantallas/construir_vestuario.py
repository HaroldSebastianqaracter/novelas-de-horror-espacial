"""Construye app/static/vestuario.html: la direccion 4 sobre la novela real."""
from pathlib import Path

BASE = Path(r"C:\Users\harold.rodriguez\Desktop\Nueva carpeta\novelas-de-horror-espacial")
src = (BASE / "falcon-diseno/html/direccion-4-barra-de-vida.html").read_text(encoding="utf-8")
cabeza = src[:src.index("<body>")]

# El harness gestiona una novela por carpeta, asi que el vestuario tiene dos perchas: la novela en
# curso y el traje nuevo. La rejilla del diseno reparte cinco columnas iguales; con dos quedarian
# separadisimas, así que se les da su ancho natural y se alinean a la izquierda.
cabeza = cabeza.replace(
    "</style>",
    """  /* El diseno reparte cinco columnas iguales porque enseñaba cinco novelas inventadas. El harness
     lleva una por carpeta, asi que las perchas toman su ancho natural y se alinean a la izquierda;
     la rejilla sigue creciendo sola si algun dia cuelgan mas trajes. */
  .trajes{grid-template-columns:repeat(auto-fit,minmax(300px,360px));justify-content:start;gap:0 56px}
  .traje .acciones a,.traje .acciones button{text-align:left}
</style>""")

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

CUERPO = '''<body>
''' + NAV_HTML + '''<main class="pantalla">
  <header>
    <div class="marco">
      <h1>Biblioteca<small>Cada libro tiene su columna: un segmento por capítulo, encendidos los que ya están escritos. Abre uno o empieza otro.</small></h1>
    </div>
    <div class="cuenta" role="status"><b id="v-coste">—</b><span id="n-coste">leyendo el gasto</span></div>
  </header>

  <ul class="trajes" id="trajes"></ul>
</main>

<script>
(function(){
"use strict";
var $ = function(id){ return document.getElementById(id); };

function esc(s){ return String(s == null ? "" : s)
  .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }

function dinero(n, moneda){
  if (n == null) return "—";
  return n.toLocaleString("es-ES", {style:"currency", currency: moneda || "USD",
                                    currencyDisplay:"narrowSymbol", maximumFractionDigits:2});
}

// La barra del diseño: segmentos de 14px cada 18px, de abajo arriba. El alto depende del numero de
// capitulos, que es lo que hace que un traje de 30 cuelgue mas que uno de 18.
function barra(id, total, cerrados, corte, cadencia){
  if (!total) total = 1;
  var primero = 24 + 18 * (total - 1);
  var alto = primero + 34;
  var p = ['<svg viewBox="0 0 64 ' + alto + '" class="barra" style="height:' + Math.min(alto, 522) + 'px"',
           ' role="img" aria-label="Barra de ' + total + ' segmentos, ' + cerrados + ' encendidos">',
           '<defs><filter id="' + id + '" x="-60%" y="-60%" width="220%" height="220%">',
           '<feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/>',
           '<feMergeNode in="SourceGraphic"/></feMerge></filter></defs>',
           '<rect x="14" y="6" width="36" height="' + (alto-12) + '" rx="8" fill="#1C1812" stroke="#A88A52" stroke-width="1.5"/>',
           '<rect x="20" y="16" width="24" height="' + (alto-32) + '" rx="3" fill="#0C0A07" stroke="#4A3D28" stroke-width="1"/>',
           '<circle cx="8" cy="12" r="2" fill="#A88A52"/><circle cx="56" cy="12" r="2" fill="#A88A52"/>',
           '<path d="M4 12 H 12 M52 12 H 60" stroke="#A88A52" stroke-width="1.5"/>',
           '<circle cx="8" cy="' + (alto-12) + '" r="2" fill="#A88A52"/><circle cx="56" cy="' + (alto-12) + '" r="2" fill="#A88A52"/>',
           '<path d="M4 ' + (alto-12) + ' H 12 M52 ' + (alto-12) + ' H 60" stroke="#A88A52" stroke-width="1.5"/>'];
  for (var i = 1; i <= total; i++) {
    var y = primero - 18 * (i - 1);
    if (i === corte)
      p.push('<rect x="23" y="' + y + '" width="18" height="14" rx="1.5" fill="#C0392B" filter="url(#' + id + ')"/>');
    else if (i <= cerrados)
      p.push('<rect x="23" y="' + y + '" width="18" height="14" rx="1.5" fill="#6FE3E6" filter="url(#' + id + ')"/>');
    else
      p.push('<rect x="23" y="' + y + '" width="18" height="14" rx="1.5" fill="#17201F" stroke="#24302F" stroke-width=".8"/>');
  }
  // Las marcas rojas del canto son las auditorias: donde el revisor puede pararlo todo.
  if (cadencia) for (var c = cadencia; c <= total; c += cadencia)
    p.push('<path d="M10 ' + (primero - 18*(c-1) + 7) + ' H 14" stroke="#C0392B" stroke-width="2"/>');
  return p.join("") + "</svg>";
}

function trajeNuevo(){
  return '<li class="traje">' + barra("gn", 30, 0, 0, 0) +
    '<div class="datos"><h2>Libro nuevo</h2>' +
    '<p class="premisa serif">Cuenta de qué va, o déjalo en blanco y escríbelo luego. En cualquier caso pasarás a la orden de trabajo, que es donde se fijan los capítulos, las palabras y el resto.</p>' +
    '<label for="premisa-nueva" class="estado bajo">Premisa</label>' +
    '<input id="premisa-nueva" class="serif" placeholder="[Quién despierta, dónde, y qué no debería estar ahí]">' +
    '<div class="acciones"><button type="button" class="primaria" id="btn-conectar">Empezar el libro</button></div>' +
    "</div></li>";
}

function trajeActual(ix, coste){
  var cerrados = ix.capitulos_cerrados || 0, total = ix.total_capitulos || 0;
  var corte = (ix.capitulos.filter(function(c){ return c.corte_qa; })[0] || {}).num || 0;
  var parada = ix.estado === "pausado_por_qa";
  // Un libro recien encargado todavia no tiene titulo ni premisa: los pone el harness al
  // prepararlo. Hasta entonces se le llama por su idea, que es lo unico suyo que existe.
  var preparado = !!ix.titulo;
  var linea = parada ? '<span class="estado rojo">Detenida por el revisor en el capítulo ' + corte + "</span>"
            : !preparado ? '<span class="estado">Encargado, sin preparar</span>'
            : cerrados >= total && total ? '<span class="estado">Terminada</span>'
            : cerrados ? '<span class="estado">En producción, van ' + cerrados + " de " + total + "</span>"
            : '<span class="estado">Preparado, sin escribir</span>';
  return '<li class="traje">' + barra("g1", total, cerrados, parada ? corte : 0, ix.cadencia_qa) +
    '<div class="datos"><h2>' + esc(ix.titulo || "Libro sin título todavía") + "</h2>" +
    '<p class="premisa serif">' + esc(ix.logline || ix.idea || "Sin premisa todavía.") + "</p>" + linea +
    '<span class="estado">' + cerrados + " de " + total + " capítulos escritos, " +
      (coste ? dinero(coste.total, coste.moneda) : "—") + "</span>" +
    '<div class="acciones">' +
      '<a class="' + (parada ? "rojo" : "") + '" href="/consola">' +
        (parada ? "Volver a la producción" : !preparado ? "Seguir preparándolo"
                                                        : "Vigilar la producción") + "</a>" +
      (cerrados ? '<a href="/lectura">Leer lo cerrado</a>' : "") +
      '<button type="button" class="rojo" id="btn-borrar">Borrar este libro</button>' +
    "</div></div></li>";
}

Promise.all([
  fetch("/api/indice").then(function(r){ return r.json(); }),
  fetch("/api/coste").then(function(r){ return r.ok ? r.json() : null; })
]).then(function(xs){
  var ix = xs[0], coste = xs[1];
  var hay = ix.hay_novela;
  $("trajes").innerHTML = (hay ? trajeActual(ix, coste) : "") + trajeNuevo();
  $("v-coste").textContent = coste ? dinero(coste.total, coste.moneda) : "—";
  $("n-coste").textContent = coste
    ? "gastados en " + (hay ? "este libro" : "ningún libro") + ", contando el preludio"
    : "no se pudo leer el gasto";

  var d = $("btn-borrar");
  if (d) d.addEventListener("click", function(){
    var aparte = "\\n\\n";
    if (!confirm(
      "Borrar «" + ix.titulo + "»." + aparte +
      "Se borran los " + ix.capitulos_cerrados + " capítulos escritos, los hechos, los informes " +
      "de calidad y el registro de ejecución. Las obras de referencia y los ajustes se quedan." + aparte +
      "Lo borrado sigue en git, así que se puede recuperar con git restore, pero desde la web no."
    )) return;
    d.disabled = true; d.textContent = "Borrando…";
    fetch("/api/borrar-novela", {method:"POST"})
      .then(function(r){ return r.json().then(function(j){ return {ok:r.ok, j:j}; }); })
      .then(function(x){
        if (!x.ok) { alert(x.j.error); d.disabled = false; d.textContent = "Borrar este libro"; return; }
        location.reload();
      })
      .catch(function(e){ alert(e.message); d.disabled = false; d.textContent = "Borrar este libro"; });
  });

  var b = $("btn-conectar");
  if (b) b.addEventListener("click", function(){
    var premisa = ($("premisa-nueva").value || "").trim();
    location.href = "/encargo" + (premisa ? "?idea=" + encodeURIComponent(premisa) : "");
  });
}).catch(function(e){
  $("trajes").innerHTML = "<li><p>No se pudo hablar con el harness: " + esc(e.message) + "</p></li>";
});
})();
</script>
</body>
</html>
'''

destino = BASE / "creador-novelas/app/static/vestuario.html"
destino.write_text(cabeza + CUERPO, encoding="utf-8")
print("vestuario.html:", len(cabeza + CUERPO), "bytes")
