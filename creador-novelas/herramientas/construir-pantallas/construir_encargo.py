"""Construye app/static/encargo.html: la orden de trabajo de la dirección 2 sobre el formulario real."""
from comun import NAV_HTML, REDUCIDO_JS, atmosfera_de, escribir, leer_maqueta

src, cabeza = leer_maqueta("direccion-2-orden-de-trabajo.html", """
  /* El bloque de tono del diseño listaba opciones inventadas; aquí la hoja lleva los ajustes que
     el harness acepta de verdad, en dos columnas para que no alargue la orden. */
  .ajustes{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 24px}
  .ajustes label{display:grid;grid-template-columns:1fr auto;gap:4px 12px;align-items:baseline;
                 border-bottom:1px solid var(--hilo);padding-bottom:3px;color:var(--niebla)}
  .ajustes input,.ajustes select{border:0;background:transparent;font:inherit;color:var(--niebla);
                                 text-align:right;width:7rem;color-scheme:dark}
  .ajustes small{grid-column:1/-1;color:var(--niebla-baja);font-size:12px}
  /* El diseño cuenta los capítulos con un <output>; aquí se teclean, y el campo tiene que verse
     como ese número escrito a mano y no como un control de sistema. */
  .palotes input[type=number]{width:4.5rem;border:0;border-bottom:1px solid var(--hilo-fuerte);background:transparent;
    font-family:Georgia,"Iowan Old Style",serif;font-size:20px;text-align:center;color:var(--niebla);color-scheme:dark}
  .palotes input[type=number]:focus{outline:none;border-bottom-color:var(--halogeno)}
  .bloqueo{border:1px solid var(--emergencia);color:#E0685C;padding:10px 14px;margin:18px 0 0;background:rgba(179,38,30,.10)}
  .condiciones label{display:flex;gap:10px;align-items:baseline;color:var(--niebla);cursor:pointer;margin-bottom:4px}
  .condiciones input[type=checkbox]{accent-color:var(--halogeno)}
  .hoja input:disabled,.hoja select:disabled,.hoja textarea:disabled{opacity:.5}
""")

CUERPO = '''<body>
<div class="escena">
''' + NAV_HTML + atmosfera_de(src) + '''
<div class="mesa">
  <form class="hoja" id="hoja" method="post" action="/guardar"><svg class="clip" viewBox="0 0 120 44" aria-hidden="true"><path d="M12 44 V 14 a 8 8 0 0 1 8 -8 h 80 a 8 8 0 0 1 8 8 V 44" fill="none" stroke="#7C848B" stroke-width="3"/><path d="M28 44 V 20 a 4 4 0 0 1 4 -4 h 56 a 4 4 0 0 1 4 4 V 44" fill="none" stroke="#3A4148" stroke-width="2"/><rect x="40" y="0" width="40" height="14" rx="3" fill="#9AA2A9"/><rect x="40" y="0" width="40" height="5" rx="3" fill="#C9D0D5"/></svg>
    <header class="cab"><span class="fantasma" id="fantasma" aria-hidden="true"></span>
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
      <label for="idea">Premisa<small>Lo que la máquina sabrá de su historia. Todo lo demás lo decidirá ella, incluido el título.</small></label>
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
      <label for="referencias">Obras de referencia<small>El Orquestador destila su estilo antes de escribir. Nunca las cita. Una ruta por línea.</small></label>
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

    <div class="pie">
      <div class="condiciones">
        <label><input type="checkbox" name="registrar_uso" id="registrar_uso"> Registrar el uso de tokens</label>
        <p>Sin esto no hay forma de saber lo que cuesta cada capítulo.</p>
        <p><strong>Condiciones.</strong> Se factura por capítulo cerrado, aunque el revisor lo rechace
          después. Si el revisor detiene la producción, usted decide si reanuda bajo su responsabilidad;
          lo escrito hasta entonces se conserva y se cobra.</p>
      </div>
      <div class="firmar">
        <svg class="tampon" id="tampon" viewBox="0 0 260 120" aria-hidden="true">
          <g fill="none" stroke="#A8281F" stroke-width="3">
            <rect x="6" y="6" width="248" height="108" rx="4"/>
            <rect x="14" y="14" width="232" height="92" rx="2" stroke-width="1.5"/>
          </g>
          <text x="130" y="58" text-anchor="middle" fill="#A8281F" font-family="Helvetica,Arial,sans-serif" font-weight="700" font-size="34">Recibido</text>
          <text x="130" y="86" text-anchor="middle" fill="#A8281F" font-family="Helvetica,Arial,sans-serif" font-size="14" id="tampon-fecha">Orquestador</text>
          <path d="M40 96 L 220 96" stroke="#A8281F" stroke-width="1" stroke-dasharray="3 4"/>
        </svg>
        <button type="submit" id="firmar" class="btn-luz">Firmar el encargo</button>
        <p class="nota" id="nota-firma">A partir de aquí solo se mira.</p>
      </div>
    </div>
  </form>

  <aside class="margen" aria-label="Anotaciones al margen">
    <div><h2>Lo que costará</h2><p class="coste" id="coste">—</p><p id="coste-nota"></p></div>
    <div><h2>Lo que tardará</h2><p><b id="tiempo">—</b></p><p>La máquina no se acelera, y usted no puede escribir mientras trabaja.</p></div>
    <div><h2>Dónde puede pararse</h2><svg id="paradas" viewBox="0 0 300 60" height="60" role="img" aria-label="Puntos de auditoría"></svg><p id="paradas-nota"></p></div>
    <div><h2>Lo que no podrá hacer</h2><p>Cambiar la premisa ni el número de capítulos una vez empezada. Sí puede detener la producción en cualquier momento; lo escrito se queda.</p></div>
  </aside>
</div>
</div>

<script>
(function(){
"use strict";
var $ = function(id){ return document.getElementById(id); };
var estado = null;

// Coste medido en la única tanda real: 0,55 $ por capítulo cerrado. Es una estimación declarada
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
  if (n > 60) p.push('<text x="' + (x+8) + '" y="28" font-size="14" fill="#8A9399">y ' + (n-60) + ' más</text>');
  $("palotes").innerHTML = '<g stroke="#E8D9B5" stroke-width="1.6" stroke-linecap="round" fill="none">' + p.join("") + "</g>";
}

function paradas(n, cadencia){
  if (!cadencia) { $("paradas").innerHTML = ""; return; }
  var p = ['<path d="M14 30 H 286" stroke="#4A525A" stroke-width="1.5"/>', '<g id="hitos">'];
  for (var c = cadencia; c <= n; c += cadencia) {
    var x = 14 + (286-14) * (c/n);
    p.push('<path d="M' + x.toFixed(1) + ' 20 V 40" stroke="#B3261E" stroke-width="3"/>');
  }
  p.push("</g>");
  p.push('<text x="14" y="56" font-size="11">cap. 1</text>');
  p.push('<text x="286" y="56" font-size="11" text-anchor="end">cap. ' + n + "</text>");
  $("paradas").innerHTML = p.join("");
  $("paradas-nota").textContent = "En cada marca roja el revisor puede detenerlo todo. Son " +
    Math.floor(n/cadencia) + " puntos de parada.";
}

function recalcular(){
  var n = parseInt($("total_capitulos").value, 10) || 0;
  var cad = parseInt((document.querySelector('[name="cadencia_qa"]')||{}).value, 10) || 0;
  palotes(n); paradas(n, cad);
  $("coste").innerHTML = esc((n * COSTE_POR_CAPITULO).toLocaleString("es-ES",
    {style:"currency", currency:"USD", currencyDisplay:"narrowSymbol", maximumFractionDigits:2})) + " <small>aprox.</small>";
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

  var folio = String(d.capitulos_cerrados || 0).padStart(4, "0");
  $("folio").textContent = folio;
  $("fantasma").textContent = folio;
  $("fecha").textContent = new Date().toLocaleDateString("es-ES",
    {weekday:"long", day:"numeric", month:"long"});
  $("ya-hay").textContent = d.referencias && d.referencias.length
    ? "Ya hay " + d.referencias.length + " en 00_referencias/: " + d.referencias.join(", ") + "."
    : "No hay ninguna todavía. Sin referencias el estilo se destila solo de la premisa.";

  if (d.bloqueado) {
    // INV-04 congela solo config/novela.json. La idea, las referencias y los ajustes de ejecución
    // siguen siendo editables, así que bloquear la hoja entera sería más restrictivo que el harness.
    $("bloqueo").textContent = d.motivo_bloqueo;
    $("bloqueo").hidden = false;
    (d.campos_novela || []).forEach(function(k){
      var c = $("hoja").querySelector('[name="' + k + '"]');
      if (c) { c.disabled = true; c.title = "Congelado por INV-04: ya hay capítulos cerrados."; }
    });
    $("firmar").textContent = "Guardar lo que sigue siendo editable";
  }
}).catch(function(e){
  $("bloqueo").textContent = "No se pudo hablar con el harness: " + e.message;
  $("bloqueo").hidden = false;
});

// Firmar el encargo lleva a la consola, que es donde está la secuencia de preparación. Sin esto
// el formulario caía en la página llana de confirmación, escrita cuando la web todavía no sabía
// lanzar fases, y el usuario acababa pensando que el resto había que hacerlo en la terminal.
$("hoja").addEventListener("submit", function(ev){
  ev.preventDefault();
  var boton = $("firmar");
  boton.disabled = true; boton.textContent = "Guardando…";
  fetch("/guardar", {method:"POST", body:new URLSearchParams(new FormData($("hoja")))})
    .then(function(r){ return r.text().then(function(t){ return {ok:r.ok, t:t}; }); })
    .then(function(x){
      if (x.ok) {
        // El único movimiento de la pantalla: cae el tampón «Recibido» y la hoja se bloquea. Se le
        // deja verse un momento antes de pasar a la consola.
        $("tampon-fecha").textContent = "Orquestador, " + new Date().toLocaleString("es-ES",
          {day:"numeric", month:"short", hour:"2-digit", minute:"2-digit"});
        $("tampon").classList.add("puesto");
        boton.textContent = "Encargado. En manos del Orquestador";
        $("nota-firma").textContent = "Pasando a la producción…";
        document.querySelectorAll(".hoja input, .hoja textarea, .hoja select, .hoja .palotes button")
          .forEach(function(el){ el.disabled = true; });
        setTimeout(function(){ location.href = "/consola"; }, 900);
        return;
      }
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
''' + REDUCIDO_JS + '''</body>
</html>
'''

escribir("encargo.html", cabeza + CUERPO)
