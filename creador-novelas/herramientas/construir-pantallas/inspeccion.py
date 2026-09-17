"""Reconocimiento de una pantalla: captura, errores de consola y medidas del DOM.

Uso:  inspeccion.py <url> <salida.png> [selector[,selector...]]
El servidor ya esta levantado, asi que aplica el patron reconocimiento-luego-accion.
"""
import sys
from playwright.sync_api import sync_playwright

url = sys.argv[1]
salida = sys.argv[2]
selectores = sys.argv[3].split(",") if len(sys.argv) > 3 else []

with sync_playwright() as p:
    navegador = p.chromium.launch(headless=True, channel="chrome")  # Chrome del sistema: no hay chromium descargado
    pagina = navegador.new_page(viewport={"width": 1440, "height": 900})

    problemas = []
    pagina.on("console", lambda m: problemas.append(f"consola[{m.type}] {m.text}") if m.type == "error" else None)
    pagina.on("pageerror", lambda e: problemas.append(f"JS: {e}"))
    pagina.on("response", lambda r: problemas.append(f"HTTP {r.status} {r.url}") if r.status >= 400 else None)

    pagina.goto(url)
    # networkidle es lo correcto para una pagina que carga y se queda quieta, pero la consola se
    # refresca cada cinco segundos y no llega nunca al reposo: ahi se espera un tiempo fijo.
    try:
        pagina.wait_for_load_state("networkidle", timeout=6000)
    except Exception:
        pagina.wait_for_timeout(2500)

    pagina.screenshot(path=salida, full_page=True)
    print("captura:", salida)
    print("problemas:", problemas or "ninguno")

    # Recorte del viewport: lo que se ve sin desplazar, que es donde estan casi todos los defectos.
    pagina.screenshot(path=salida.replace(".png", "-visible.png"))

    alto = pagina.evaluate("document.documentElement.scrollHeight")
    ancho = pagina.evaluate("document.documentElement.scrollWidth")
    print(f"pagina: {ancho}x{alto}px", "| DESBORDA A LO ANCHO" if ancho > 1440 else "")

    for s in selectores:
        s = s.strip()
        if not s:
            continue
        try:
            n = pagina.locator(s).count()
            caja = pagina.eval_on_selector(
                s, "e => { const r = e.getBoundingClientRect();"
                   "  return [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]; }"
            ) if n else None
            print(f"  {s}: {n} elemento(s)" + (f", primero en x/y/w/h = {caja}" if caja else ""))
        except Exception as e:  # noqa: BLE001
            print(f"  {s}: no se pudo medir ({e})")

    # Texto recortado por su contenedor: el defecto que no se ve leyendo el codigo.
    recortados = pagina.evaluate("""() => {
      const malos = [];
      document.querySelectorAll('body *').forEach(e => {
        if (e.children.length === 0 && e.scrollWidth > e.clientWidth + 2 && e.clientWidth > 0)
          malos.push((e.id || e.className || e.tagName) + ': ' + (e.textContent || '').trim().slice(0, 40));
      });
      return malos.slice(0, 12);
    }""")
    print("texto recortado:", recortados or "ninguno")

    navegador.close()
