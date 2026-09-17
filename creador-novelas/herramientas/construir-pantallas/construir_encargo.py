"""Construye app/static/encargo.html: la orden de trabajo de la direccion 2 sobre el formulario real."""
from pathlib import Path

BASE = Path(r"C:\Users\harold.rodriguez\Desktop\Nueva carpeta\novelas-de-horror-espacial")
src = (BASE / "falcon-diseno/html/direccion-2-orden-de-trabajo.html").read_text(encoding="utf-8")
cabeza = src[:src.index("<body>")]

cabeza = cabeza.replace("</style>", """  /* El bloque de tono del diseno listaba opciones inventadas; aqui la hoja lleva los ajustes que
     el harness acepta de verdad, en dos columnas para que no alargue la orden. */
  .ajustes{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 24px}
  .ajustes label{display:grid;grid-template-columns:1fr auto;gap:4px 12px;align-items:baseline;
                 border-bottom:1px solid var(--calco);padding-bottom:3px}
  .ajustes input,.ajustes select{border:0;background:transparent;font:inherit;color:var(--tinta);
                                 text-align:right;width:9rem}
  .ajustes small{grid-column:1/-1;color:var(--lapiz);font-size:12px}
  .bloqueo{border:1px solid var(--sello);color:var(--sello);padding:10px 14px;margin:0 0 18px}
  .fallo{color:var(--sello)}
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
''' + NAV_HTML + '''<div class="mesa">
  <form class="hoja" id="hoja" method="post" action="/guardar">
    <header class="cab">
      <div>
        <h1 id="titulo">Orden de trabajo para una novela de terror espacial</h1>
        <p>Rellene los campos. Al firmar, el encargo pasa al Orquestador y usted deja de
          intervenir: podrá vigilar la producción, detenerla y leer el resultado, pero no corregirlo
          mientras se escribe.</p>
      </div>
      <div class="num">Orden n.º<b id="folio">—</b><span id="fecha"></span></div>
    </header>

    <p class="bloqueo" id="bloqueo" hidden></p>

    <div class="campo">
      <div class="et">Premisa<small>Lo que la máquina sabrá de su historia. Todo lo demás lo decidirá ella, incluido el título.</small></div>
      <textarea name="idea" id="idea" class="escrito" required rows="3"
        placeholder="Quién despierta, dónde, y qué no debería estar ahí"></textarea>
    </div>

    <div class="campo">
      <div class="et">Número de capítulos<small>Cada capítulo cuesta dinero y unos cinco minutos. El revisor audita cada pocos.<span id="cotas-caps"></span></small></div>
      <div class="palotes" role="group" aria-label="Número de capítulos">
        <svg id="palotes" viewBox="0 0 520 40" height="40" role="img" aria-label="Recuento en palotes"></svg>
        <div class="ctrl">
          <button type="button" id="menos" aria-label="Un capítulo menos">−</button>
          <input type="number" name="total_capitulos" id="total_capitulos" required>
          <button type="button" id="mas" aria-label="Un capítulo más">+</button>
        </div>
      </div>
    </div>

    <div class="campo">
      <div class="et">Obras de referencia<small>El Orquestador destila su estilo antes de escribir. Nunca las cita. Una ruta por línea.</small></div>
      <div>
        <textarea name="referencias" id="referencias" class="escrito" rows="2"
          placeholder="C:\\ruta\\al\\ejemplo.txt"></textarea>
        <small id="ya-hay"></small>
      </div>
    </div>

    <div class="campo">
      <div class="et">Ajustes de producción<small>Los valores por defecto sirven. Cámbielos solo si sabe qué hacen.</small></div>
      <div class="ajustes" id="ajustes"></div>
    </div>

    <div class="firmar">
      <div>
        <label><input type="checkbox" name="registrar_uso" id="registrar_uso"> Registrar el uso de tokens</label>
        <small>Sin esto no hay forma de saber lo que cuesta cada capítulo.</small>
      </div>
      <button type="submit"  id="firmar">Firmar el encargo</button>
    </div>
  </form>

  <aside class="margen">
    <div><h2>Lo que costará</h2><p><b id="coste">—</b></p><small id="coste-nota"></small></div>
    <div><h2>Lo que tardará</h2><p><b id="tiempo">—</b></p><p >La máquina no se acelera, y usted no puede escribir mientras trabaja.</p></div>
    <div><h2>Dónde puede pararse</h2><svg id="paradas" viewBox="0 0 300 60" height="60" role="img" aria-label="Puntos de auditoría"></svg><small id="paradas-nota"></small></div>
    <div><h2>Lo que no podrá hacer</h2><p>Cambiar la premisa, el tono o el número de capítulos una vez empezada. Sí puede detener la producción en cualquier momento; lo escrito se queda.</p></div>
  </aside>
</div>

<script>
(function(){
"use strict";
var $ = function(id){ return document.getElementById(id); };
var estado = null;

// Coste medido en la unica tanda real: 0,55 $ por capitulo cerrado. Es una estimacion declarada
// como tal, no una promesa: el precio real lo cuenta `web.coste` sobre el uso ya registrado.
var COSTE_POR_CAPITULO = 0.55, MINUTOS_POR_CAPITULO = 12;

var ETIQUETAS = {
  palabras_por_capitulo: ["Palabras por capítulo", "Tolerancia de ±20 %."],
  cadencia_qa: ["El revisor audita cada", "capítulos. Más a menudo es más caro y más seguro."],
  capitulos_por_tanda: ["Capítulos por tanda", "Cuántos se escriben de una sentada."],
  max_llamadas_por_tanda: ["Llamadas máximas por tanda", "Tope de seguridad: si se pasa, para."],
  ventana_resumen_rodante: ["Resúmenes que ve el escritor", "Cuántos capítulos atrás recuerda."],
  max_hechos_por_capitulo: ["Hechos nuevos por capítulo", "Cuántos puede fijar el extractor."],
  max_tokens_contexto_escritor: ["Contexto del escritor", "Tope de tokens de su prompt."],
  idioma: ["Idioma", ""],
  persona_narrativa: ["Persona narrativa", ""],
  tiempo_verbal: ["Tiempo verbal", ""]
};
var OPCIONES = {
  idioma: ["es-ES", "es-419", "en-US"],
  persona_narrativa: ["tercera_limitada", "primera", "tercera_omnisciente"],
  tiempo_verbal: ["pasado", "presente"]
};

function cotas(clave){
  var l = (estado && estado.limites && estado.limites[clave]) || {};
  return (l.min != null ? ' min="' + l.min + '"' : "") + (l.max != null ? ' max="' + l.max + '"' : "");
}

function limitar(n){
  var l = (estado && estado.limites && estado.limites.total_capitulos) || {};
  if (l.min != null && n < l.min) n = l.min;
  if (l.max != null && n > l.max) n = l.max;
  return n;
}

function esc(s){ return String(s == null ? "" : s)
  .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }

function palotes(n){
  // Grupos de cinco, el quinto tachado: es como cuenta una persona, no como cuenta una barra de progreso.
  var p = [], x = 6, y1 = 8, y2 = 32;
  for (var i = 1; i <= Math.min(n, 60); i++) {
    if (i % 5 === 0) { p.push('<path d="M' + (x-30) + ' ' + (y2-4) + ' L ' + (x+4) + ' ' + (y1+4) + '"/>'); x += 14; }
    else { p.push('<path d="M' + x + ' ' + y1 + ' V ' + y2 + '"/>'); x += 7; }
  }
  if (n > 60) p.push('<text x="' + (x+8) + '" y="28" font-size="14">y ' + (n-60) + ' más</text>');
  $("palotes").innerHTML = '<g stroke="#17191C" stroke-width="1.6" fill="#17191C">' + p.join("") + "</g>";
}

function paradas(n, cadencia){
  if (!cadencia) { $("paradas").innerHTML = ""; return; }
  var p = ['<path d="M14 30 H 286" stroke="#6E726B" stroke-width="1"/>'];
  for (var c = cadencia; c <= n; c += cadencia) {
    var x = 14 + (286-14) * (c/n);
    p.push('<path d="M' + x.toFixed(1) + ' 20 V 40" stroke="#A8281F" stroke-width="2"/>');
  }
  p.push('<text x="14" y="56" font-size="11" fill="#6E726B">cap. 1</text>');
  p.push('<text x="286" y="56" font-size="11" fill="#6E726B" text-anchor="end">cap. ' + n + "</text>");
  $("paradas").innerHTML = p.join("");
  $("paradas-nota").textContent = "En cada marca roja el revisor puede detenerlo todo. Son " +
    Math.floor(n/cadencia) + " puntos de parada.";
}

function recalcular(){
  var n = parseInt($("total_capitulos").value, 10) || 0;
  var cad = parseInt((document.querySelector('[name="cadencia_qa"]')||{}).value, 10) || 0;
  palotes(n); paradas(n, cad);
  $("coste").textContent = (n * COSTE_POR_CAPITULO).toLocaleString("es-ES",
    {style:"currency", currency:"USD", currencyDisplay:"narrowSymbol", maximumFractionDigits:2}) + " aprox.";
  $("coste-nota").textContent = "A unos 0,55 $ por capítulo cerrado, medido sobre la única tanda que se ha "
    + "corrido de verdad. Lo escrito no se devuelve.";
  var min = n * MINUTOS_POR_CAPITULO;
  $("tiempo").textContent = min >= 60 ? Math.floor(min/60) + " h " + (min%60) + " min" : min + " min";
}

function pintarAjustes(){
  var v = estado.valores, h = [];
  Object.keys(ETIQUETAS).forEach(function(k){
    if (!(k in v)) return;
    var control = OPCIONES[k]
      ? '<select name="' + k + '">' + OPCIONES[k].map(function(o){
          return '<option value="' + esc(o) + '"' + (String(v[k]) === o ? " selected" : "") + ">" + esc(o) + "</option>";
        }).join("") + "</select>"
      : '<input type="number" name="' + k + '" value="' + esc(v[k]) + '" required' + cotas(k) + ">";
    h.push("<label><span>" + esc(ETIQUETAS[k][0]) + "</span>" + control +
           (ETIQUETAS[k][1] ? "<small>" + esc(ETIQUETAS[k][1]) + "</small>" : "") + "</label>");
  });
  $("ajustes").innerHTML = h.join("");
  var cad = document.querySelector('[name="cadencia_qa"]');
  if (cad) cad.addEventListener("input", recalcular);
}

fetch("/api/formulario").then(function(r){ return r.json(); }).then(function(d){
  estado = d;
  $("idea").value = d.idea || new URLSearchParams(location.search).get("idea") || "";
  $("total_capitulos").value = d.valores.total_capitulos;
  $("total_capitulos").setAttribute("min", (d.limites.total_capitulos || {}).min || 1);
  $("total_capitulos").setAttribute("max", (d.limites.total_capitulos || {}).max || 999);
  var lc = d.limites.total_capitulos || {};
  $("cotas-caps").textContent = (lc.min != null && lc.max != null)
    ? " El harness admite entre " + lc.min + " y " + lc.max + "." : "";
  $("registrar_uso").checked = d.valores.registrar_uso !== false;
  pintarAjustes();
  recalcular();

  $("folio").textContent = String(d.capitulos_cerrados || 0).padStart(4, "0");
  $("fecha").textContent = new Date().toLocaleDateString("es-ES",
    {weekday:"long", day:"numeric", month:"long"});
  $("ya-hay").textContent = d.referencias && d.referencias.length
    ? "Ya hay " + d.referencias.length + " en 00_referencias/: " + d.referencias.join(", ") + "."
    : "No hay ninguna todavía. Sin referencias el estilo se destila solo de la premisa.";

  if (d.bloqueado) {
    // INV-04 congela solo config/novela.json. La idea, las referencias y los ajustes de ejecucion
    // siguen siendo editables, asi que bloquear la hoja entera seria mas restrictivo que el harness.
    $("bloqueo").textContent = d.motivo_bloqueo;
    $("bloqueo").hidden = false;
    (d.campos_novela || []).forEach(function(k){
      var c = $("hoja").querySelector('[name="' + k + '"]');
      if (c) { c.disabled = true; c.title = "Congelado por INV-04: ya hay capitulos cerrados."; }
    });
    $("firmar").textContent = "Guardar lo que sigue siendo editable";
  }
}).catch(function(e){
  $("bloqueo").textContent = "No se pudo hablar con el harness: " + e.message;
  $("bloqueo").hidden = false;
});

// Firmar el encargo lleva a la consola, que es donde esta la secuencia de preparacion. Sin esto
// el formulario caia en la pagina llana de confirmacion, escrita cuando la web todavia no sabia
// lanzar fases, y el usuario acababa pensando que el resto habia que hacerlo en la terminal.
$("hoja").addEventListener("submit", function(ev){
  ev.preventDefault();
  var boton = $("firmar");
  boton.disabled = true; boton.textContent = "Guardando…";
  fetch("/guardar", {method:"POST", body:new URLSearchParams(new FormData($("hoja")))})
    .then(function(r){ return r.text().then(function(t){ return {ok:r.ok, t:t}; }); })
    .then(function(x){
      if (x.ok) { location.href = "/consola"; return; }
      var m = x.t.match(/EX-05[^<]*/);
      $("bloqueo").textContent = m ? m[0] : "No se guardó: revisa los campos.";
      $("bloqueo").hidden = false;
      boton.disabled = false; boton.textContent = "Firmar el encargo";
      $("bloqueo").scrollIntoView({block:"center"});
    })
    .catch(function(e){
      $("bloqueo").textContent = e.message; $("bloqueo").hidden = false;
      boton.disabled = false; boton.textContent = "Firmar el encargo";
    });
});

$("mas").addEventListener("click", function(){
  $("total_capitulos").value = limitar((parseInt($("total_capitulos").value,10)||0) + 1); recalcular(); });
$("menos").addEventListener("click", function(){
  $("total_capitulos").value = limitar((parseInt($("total_capitulos").value,10)||1) - 1); recalcular(); });
$("total_capitulos").addEventListener("input", recalcular);
})();
</script>
</body>
</html>
'''

destino = BASE / "creador-novelas/app/static/encargo.html"
destino.write_text(cabeza + CUERPO, encoding="utf-8")
print("encargo.html:", len(cabeza + CUERPO), "bytes")
