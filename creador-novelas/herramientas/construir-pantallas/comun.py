"""Lo que comparten los cuatro generadores: la maqueta de origen, la barra de navegación y la
atmósfera de las direcciones 2, 3 y 4.

Antes cada generador llevaba su propia copia de la navegación y su propia ruta absoluta a la
carpeta del diseño. Al migrar a `falcon-diseno_2` se vio que eso había que tocarlo cuatro veces
seguidas, así que ahora vive aquí y los generadores solo dicen qué maqueta quieren.
"""
from pathlib import Path

# La raíz del repo se deduce de la posición de este archivo, no de una ruta absoluta: el mismo
# generador tiene que valer en otra máquina o en otra carpeta.
BASE = Path(__file__).resolve().parents[3]
MAQUETAS = BASE / "falcon-diseno_2" / "html"
DESTINO = BASE / "creador-novelas" / "app" / "static"


def leer_maqueta(nombre: str, css_extra: str = "") -> tuple[str, str]:
    """Devuelve (maqueta entera, cabeza con la navegación y el CSS extra colgados del <style>).

    La cabeza es todo lo anterior a `<body>`: el CSS del diseñador, intacto. Lo que el harness
    necesita cambiar se añade al final de la hoja, donde gana por orden sin tocar nada.
    """
    src = (MAQUETAS / nombre).read_text(encoding="utf-8")
    cabeza = src[:src.index("<body>")]
    assert "</style>" in cabeza, f"{nombre}: la maqueta no trae hoja de estilos donde colgar la navegación"
    cabeza = cabeza.replace("</style>", NAV_CSS + css_extra + "</style>", 1)
    return src, cabeza


def atmosfera_de(src: str) -> str:
    """Las capas de atmósfera de las direcciones 2, 3 y 4, tal como las entregó el diseñador.

    Son los filtros SVG (grano, sangre) y los `div.atm-*` que van dentro de `.escena`. Se copian de
    la maqueta en vez de escribirse aquí para que un ajuste del diseñador en los parámetros del
    ruido llegue a la web con solo regenerar.
    """
    inicio = src.index('<svg width="0" height="0"')
    ultimo = '<div class="atm atm-filo" aria-hidden="true"></div>'
    fin = src.index(ultimo, inicio) + len(ultimo)
    return src[inicio:fin]


def escribir(nombre: str, html: str) -> None:
    destino = DESTINO / nombre
    destino.write_text(html, encoding="utf-8")
    print(f"{nombre}: {len(html)} bytes")


# --- barra de navegación, común a las cuatro pantallas ---
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
  // Marca la sección en la que estás. Va aquí y no en cada página para que las cuatro barras sean
  // literalmente la misma y no se desincronicen al tocar una.
  (function(){
    // Las páginas se sirven desde /static/*.html --las rutas bonitas son redirecciones--, así que
    // la sección activa se deduce del nombre del archivo y no de la ruta, que nunca coincidiría.
    var donde = {"vestuario.html":"/", "encargo.html":"/encargo",
                 "consola.html":"/consola", "lectura.html":"/lectura"};
    var aqui = donde[location.pathname.split("/").pop()] || location.pathname;
    document.querySelectorAll(".ir a").forEach(function(a){
      if (a.getAttribute("href") === aqui) a.setAttribute("aria-current", "page");
    });
  })();
</script>
"""

# El diseñador apaga la animación SVG del fluido cuando el sistema pide menos movimiento; el CSS
# ya lo hace por su lado, pero el <animate> del filtro no obedece a media queries.
REDUCIDO_JS = """<script>
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    document.querySelectorAll('#sangre animate').forEach(function(a){ a.remove(); });
  }
</script>
"""
