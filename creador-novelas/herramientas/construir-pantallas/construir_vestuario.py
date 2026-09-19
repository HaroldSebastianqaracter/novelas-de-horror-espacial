"""Construye app/static/vestuario.html: la dirección 4 sobre la novela real."""
from comun import NAV_HTML, REDUCIDO_JS, atmosfera_de, escribir, leer_maqueta

src, cabeza = leer_maqueta("direccion-4-barra-de-vida.html", """
  /* El diseño reparte cinco columnas iguales porque enseñaba cinco novelas inventadas. El harness
     lleva una por carpeta, así que las perchas toman su ancho natural y se alinean a la izquierda;
     la rejilla sigue creciendo sola si algún día cuelgan más trajes. */
  .trajes{grid-template-columns:repeat(auto-fit,minmax(300px,360px));justify-content:start;gap:0 56px}
  .traje .acciones a,.traje .acciones button{text-align:left}
  /* Los trajes cuelgan del riel, así que se alinean por arriba. La maqueta lo escribía así, pero
     su regla quedaba antes que la base (`align-items:end`) y perdía: con seis capítulos la barra
     caía al fondo y el gancho quedaba flotando a media pantalla. */
  .trajes{align-items:start;padding-top:64px}
  .traje{align-items:start}
  /* La barra de navegación es la primera fila de la escena y va de borde a borde. */
  .pantalla{grid-template-rows:auto auto 1fr}
  .pantalla > .ir{margin:-36px -56px 0}
  @media (max-width:1280px){.pantalla > .ir{margin:-28px -36px 0}}
""")

CUERPO = '''<body>
<main class="pantalla escena">
''' + NAV_HTML + atmosfera_de(src) + '''
<div class="focos" id="focos" aria-hidden="true"></div>
  <header><span class="fantasma" aria-hidden="true">Biblioteca</span>
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

// El gancho del que cuelga cada traje, tal como lo dibujó el diseñador.
var GANCHO = '<svg class="gancho" viewBox="0 0 24 56" aria-hidden="true">' +
  '<path d="M12 2 a 7 7 0 1 0 0.01 0 M12 16 V 30 a 8 8 0 0 0 16 0" fill="none" stroke="#8B939A" stroke-width="2.4" transform="translate(-4 0)"/>' +
  '<path d="M8 30 V 56" stroke="#5C656C" stroke-width="3"/></svg>';

// La barra del diseño: segmentos de 14px cada 18px, de abajo arriba. El alto depende del número de
// capítulos, que es lo que hace que un traje de 30 cuelgue más que uno de 18.
function barra(id, total, cerrados, corte, cadencia){
  if (!total) total = 1;
  var primero = 24 + 18 * (total - 1);
  var alto = primero + 34;
  var p = ['<svg viewBox="0 0 64 ' + alto + '" class="barra" style="height:' + Math.min(alto, 522) + 'px"',
           ' role="img" aria-label="Barra de ' + total + ' segmentos, ' + cerrados + ' encendidos">',
           '<defs><filter id="' + id + '" x="-60%" y="-60%" width="220%" height="220%">',
           '<feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/>',
           '<feMergeNode in="SourceGraphic"/></feMerge></filter></defs>',
           '<rect x="14" y="6" width="36" height="' + (alto-12) + '" rx="8" fill="#10141A" stroke="#6B7378" stroke-width="1.5"/>',
           '<rect x="20" y="16" width="24" height="' + (alto-32) + '" rx="3" fill="#05070A" stroke="#2A3138" stroke-width="1"/>',
           '<circle cx="8" cy="12" r="2" fill="#6B7378"/><circle cx="56" cy="12" r="2" fill="#6B7378"/>',
           '<path d="M4 12 H 12 M52 12 H 60" stroke="#6B7378" stroke-width="1.5"/>',
           '<circle cx="8" cy="' + (alto-12) + '" r="2" fill="#6B7378"/><circle cx="56" cy="' + (alto-12) + '" r="2" fill="#6B7378"/>',
           '<path d="M4 ' + (alto-12) + ' H 12 M52 ' + (alto-12) + ' H 60" stroke="#6B7378" stroke-width="1.5"/>'];
  for (var i = 1; i <= total; i++) {
    var y = primero - 18 * (i - 1);
    if (i === corte)
      p.push('<rect x="23" y="' + y + '" width="18" height="14" rx="1.5" fill="#B3261E" filter="url(#' + id + ')"/>');
    else if (i <= cerrados)
      p.push('<rect x="23" y="' + y + '" width="18" height="14" rx="1.5" fill="#A8D8C8" filter="url(#' + id + ')"/>');
    else
      p.push('<rect x="23" y="' + y + '" width="18" height="14" rx="1.5" fill="#12171C" stroke="#232A31" stroke-width=".8"/>');
  }
  // Las marcas rojas del canto son las auditorías: donde el revisor puede pararlo todo.
  if (cadencia) for (var c = cadencia; c <= total; c += cadencia)
    p.push('<path d="M10 ' + (primero - 18*(c-1) + 7) + ' H 14" stroke="#B3261E" stroke-width="2"/>');
  return p.join("") + "</svg>";
}

function trajeNuevo(){
  return '<li class="traje nueva" id="traje-nuevo">' + GANCHO + barra("gn", 30, 0, 0, 0) +
    '<div class="datos"><h2>Libro nuevo</h2>' +
    '<p class="premisa serif">Cuenta de qué va, o déjalo en blanco y escríbelo luego. En cualquier caso pasarás a la orden de trabajo, que es donde se fijan los capítulos, las palabras y el resto.</p>' +
    '<label for="premisa-nueva" class="estado bajo">Premisa</label>' +
    '<input id="premisa-nueva" class="serif" placeholder="[Quién despierta, dónde, y qué no debería estar ahí]">' +
    '<div class="acciones"><button type="button" class="primaria btn-luz" id="btn-conectar">Empezar el libro</button></div>' +
    "</div></li>";
}

function trajeActual(ix, coste){
  var cerrados = ix.capitulos_cerrados || 0, total = ix.total_capitulos || 0;
  var corte = (ix.capitulos.filter(function(c){ return c.corte_qa; })[0] || {}).num || 0;
  var parada = ix.estado === "pausado_por_qa";
  // Un libro recién encargado todavía no tiene título ni premisa: los pone el harness al
  // prepararlo. Hasta entonces se le llama por su idea, que es lo único suyo que existe.
  var preparado = !!ix.titulo;
  var linea = parada ? '<span class="estado rojo">Detenida por el revisor en el capítulo ' + corte + "</span>"
            : !preparado ? '<span class="estado">Encargado, sin preparar</span>'
            : cerrados >= total && total ? '<span class="estado visor">Terminada</span>'
            : cerrados ? '<span class="estado visor">En producción, van ' + cerrados + " de " + total + "</span>"
            : '<span class="estado">Preparado, sin escribir</span>';
  return '<li class="traje">' + GANCHO + barra("g1", total, cerrados, parada ? corte : 0, ix.cadencia_qa) +
    '<div class="datos"><h2>' + esc(ix.titulo || "Libro sin título todavía") + "</h2>" +
    '<p class="premisa serif">' + esc(ix.logline || ix.idea || "Sin premisa todavía.") + "</p>" + linea +
    '<span class="estado">' + cerrados + " de " + total + " capítulos escritos, " +
      (coste ? dinero(coste.total, coste.moneda) : "—") + "</span>" +
    '<div class="acciones">' +
      '<a class="' + (parada ? "rojo" : "primaria btn-luz") + '" href="/consola">' +
        (parada ? "Volver a la producción" : !preparado ? "Seguir preparándolo"
                                                        : "Vigilar la producción") + "</a>" +
      (cerrados ? '<a href="/lectura">Leer lo cerrado</a>' : "") +
      '<button type="button" class="rojo" id="btn-borrar">Borrar este libro</button>' +
    "</div></div></li>";
}

// Un cono de luz sobre cada percha. El diseño los repartía a 10 %, 30 %, 50 %... porque tenía
// cinco trajes fijos; aquí se calculan sobre las barras que de verdad hay.
function pintarFocos(){
  var escena = document.querySelector(".pantalla").getBoundingClientRect();
  var conos = [];
  document.querySelectorAll(".traje .barra").forEach(function(b){
    var r = b.getBoundingClientRect();
    var x = ((r.left + r.width/2 - escena.left) / escena.width * 100).toFixed(1);
    conos.push("radial-gradient(ellipse 9% 55% at " + x + "% 40%,rgba(232,217,181,.10),transparent 70%)");
  });
  $("focos").style.background = conos.join(",");
}

Promise.all([
  fetch("/api/indice").then(function(r){ return r.json(); }),
  fetch("/api/coste").then(function(r){ return r.ok ? r.json() : null; })
]).then(function(xs){
  var ix = xs[0], coste = xs[1];
  var hay = ix.hay_novela;
  $("trajes").innerHTML = (hay ? trajeActual(ix, coste) : "") + trajeNuevo();
  pintarFocos();
  window.addEventListener("resize", pintarFocos);
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
    // El único movimiento de la pantalla: el traje se conecta (primer segmento y carcasa encendidos)
    // y acto seguido se abre la orden de trabajo.
    $("traje-nuevo").classList.add("conectado");
    var premisa = ($("premisa-nueva").value || "").trim();
    setTimeout(function(){
      location.href = "/encargo" + (premisa ? "?idea=" + encodeURIComponent(premisa) : "");
    }, 450);
  });
}).catch(function(e){
  $("trajes").innerHTML = "<li><p>No se pudo hablar con el harness: " + esc(e.message) + "</p></li>";
});
})();
</script>
''' + REDUCIDO_JS + '''</body>
</html>
'''

escribir("vestuario.html", cabeza + CUERPO)
