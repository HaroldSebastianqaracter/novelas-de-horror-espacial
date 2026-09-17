"""Frontend de entrada de requisitos: `python -m app ui` (spec técnica §15; RF-UI-01, RF-UI-02).

Solo entrada: no llama a ningún modelo, no muestra progreso, no lee el manuscrito. Solo biblioteca estándar
(`http.server`), escucha únicamente en 127.0.0.1. Valida con el mismo `HarnessConfig` de §8.1 antes de escribir.
La lógica (`estado_formulario`, `procesar_guardado`) está separada del servidor para poder probarla sin red.
"""

from __future__ import annotations

import html
import json
import shutil
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from app import web
from app.config import CAMPOS_EJECUCION, CAMPOS_NOVELA, HarnessConfig, construir_config
from app.errores import ConfiguracionInvalidaError, EstadoInvalidoError
from app.orchestrator import checkpoint
from app.rutas import Rutas
from app.state import repository as repo

HOST = "127.0.0.1"
EXTENSIONES_REFERENCIA = (".md", ".txt")

# Valores con los que se precarga el formulario cuando config/ todavía no existe (§15.1).
DEFAULTS: dict[str, Any] = {
    "idioma": "es-ES",
    "persona_narrativa": "tercera_limitada",
    "tiempo_verbal": "pasado",
    "total_capitulos": 30,
    "palabras_por_capitulo": 1500,
    "ventana_resumen_rodante": 2,
    "cadencia_qa": 3,
    "max_tokens_contexto_escritor": 12000,
    "max_hechos_por_capitulo": 4,
    "capitulos_por_tanda": 3,
    "max_llamadas_por_tanda": 30,
    "registrar_uso": True,
}

OPCIONES = {
    "persona_narrativa": ("primera", "tercera_limitada", "tercera_omnisciente"),
    "tiempo_verbal": ("presente", "pasado"),
}

# (campo, etiqueta, ayuda) — el orden es el del formulario (§15.1)
CAMPOS_VOZ = (
    ("idioma", "Idioma", "RF-CFG-05 · p. ej. es-ES"),
    ("persona_narrativa", "Persona narrativa", "RF-CFG-05"),
    ("tiempo_verbal", "Tiempo verbal", "RF-CFG-05"),
)
CAMPOS_DIMENSION = (
    ("total_capitulos", "Total de capítulos", "RF-CFG-01 · entre 30 y 50"),
    ("palabras_por_capitulo", "Palabras por capítulo", "RF-CFG-01 · tolerancia ±20 %"),
    ("ventana_resumen_rodante", "Ventana del resumen rodante", "RF-06.4 · en capítulos, >= 1"),
    ("cadencia_qa", "Cadencia de QA", "RF-07.1 · cada cuántos capítulos corre el corte, >= 1"),
    ("max_tokens_contexto_escritor", "Máx. tokens de contexto del escritor", "RF-05.1 · > 0"),
    ("max_hechos_por_capitulo", "Máx. hechos por capítulo", "§11.6 · acota continuidad.json, > 0"),
)
CAMPOS_EJEC = (
    ("capitulos_por_tanda", "Capítulos por tanda", "RF-CFG-02 · vacío = sin tope"),
    ("max_llamadas_por_tanda", "Máx. llamadas por tanda", "RF-CFG-06 · vacío = sin tope"),
)


@dataclass
class EstadoFormulario:
    valores: dict[str, Any]
    idea: str
    bloqueado: bool
    motivo_bloqueo: str | None
    capitulos_cerrados: int
    referencias: list[str]  # nombres ya presentes en 00_referencias/


@dataclass
class ResultadoGuardado:
    escritos: list[Path] = field(default_factory=list)
    copiados: list[Path] = field(default_factory=list)
    comando_siguiente: str = ""


# ---------- lógica ----------

def _leer_json_tolerante(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        datos = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return datos if isinstance(datos, dict) else {}


def _referencias_presentes(rutas: Rutas) -> list[str]:
    if not rutas.referencias.exists():
        return []
    return sorted(p.name for p in rutas.referencias.iterdir() if p.is_file() and p.name != ".gitkeep")


def bloqueo_inv04(raiz: Path) -> tuple[int, str | None]:
    """RF-UI-02: (capítulos cerrados, motivo). El motivo no es nulo si novela.json ya no puede cambiar."""
    m = checkpoint.leer_manifest(raiz)
    cerrados = m.ultimo_capitulo_cerrado if m else 0
    if cerrados > 0:
        return cerrados, (f"INV-04: hay {cerrados} capítulos cerrados; config/novela.json es inmutable "
                          f"(EX-06). Solo la idea y config/ejecucion.json siguen editables.")
    return cerrados, None


def estado_formulario(raiz: Path) -> EstadoFormulario:
    """Lo que muestra el GET: valores actuales de config/ (o los defaults), la idea y el bloqueo de INV-04."""
    rutas = Rutas(raiz)
    valores = dict(DEFAULTS)
    valores.update({k: v for k, v in _leer_json_tolerante(rutas.novela_json).items() if k in CAMPOS_NOVELA})
    valores.update({k: v for k, v in _leer_json_tolerante(rutas.ejecucion_json).items() if k in CAMPOS_EJECUCION})
    cerrados, motivo = bloqueo_inv04(raiz)
    return EstadoFormulario(valores=valores, idea=repo.leer_texto(rutas.idea), bloqueado=motivo is not None,
                            motivo_bloqueo=motivo, capitulos_cerrados=cerrados, referencias=_referencias_presentes(rutas))


def _valor_o_nulo(campos: dict[str, str], clave: str) -> Any:
    crudo = campos.get(clave, "").strip()
    return None if crudo == "" else crudo


def _novela_desde_formulario(campos: dict[str, str]) -> dict[str, Any]:
    novela: dict[str, Any] = {}
    for clave in CAMPOS_NOVELA:
        crudo = campos.get(clave, "").strip()
        if crudo != "":
            novela[clave] = crudo
    return novela


def _ejecucion_desde_formulario(campos: dict[str, str]) -> dict[str, Any]:
    return {
        "capitulos_por_tanda": _valor_o_nulo(campos, "capitulos_por_tanda"),
        "max_llamadas_por_tanda": _valor_o_nulo(campos, "max_llamadas_por_tanda"),
        "registrar_uso": campos.get("registrar_uso", "").strip().lower() in ("on", "true", "1", "si", "sí"),
    }


def _rutas_referencia(campos: dict[str, str]) -> list[Path]:
    crudo = campos.get("referencias", "")
    return [Path(linea.strip().strip('"')) for linea in crudo.splitlines() if linea.strip()]


def _archivos_de_referencia(origenes: list[Path]) -> list[Path]:
    """Expande las rutas dadas a archivos .md/.txt. Falla antes de escribir nada si alguna no existe (RF-UI-01)."""
    archivos: list[Path] = []
    for origen in origenes:
        if not origen.exists():
            raise ConfiguracionInvalidaError(f"RF-00.2: la ruta de referencia no existe: {origen}")
        if origen.is_dir():
            dentro = sorted(p for p in origen.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONES_REFERENCIA)
            if not dentro:
                raise ConfiguracionInvalidaError(f"RF-00.2: la carpeta no contiene archivos {EXTENSIONES_REFERENCIA}: {origen}")
            archivos.extend(dentro)
        elif origen.suffix.lower() not in EXTENSIONES_REFERENCIA:
            raise ConfiguracionInvalidaError(f"RF-00.2: solo se aceptan referencias {EXTENSIONES_REFERENCIA}: {origen}")
        else:
            archivos.append(origen)
    return archivos


def _normalizar_idea(texto: str) -> str:
    """El navegador manda CRLF; en disco queda exactamente lo tecleado, con saltos LF."""
    return texto.replace("\r\n", "\n").replace("\r", "\n")


def procesar_guardado(raiz: Path, campos: dict[str, str]) -> ResultadoGuardado:
    """POST /guardar. Valida TODO antes de escribir: una configuración inválida nunca llega al disco (RF-UI-01)."""
    rutas = Rutas(raiz)
    idea = _normalizar_idea(campos.get("idea", ""))
    if not idea.strip():
        raise EstadoInvalidoError("RF-01.1: la idea no puede estar vacía")

    cerrados, motivo = bloqueo_inv04(raiz)
    novela_actual = _leer_json_tolerante(rutas.novela_json)
    novela_form = _novela_desde_formulario(campos)
    ejecucion = _ejecucion_desde_formulario(campos)
    if motivo is not None:
        # RF-UI-02: con capítulos cerrados, novela.json se conserva tal cual; el formulario no puede pisarlo.
        for clave, valor in novela_form.items():
            vigente = novela_actual.get(clave)
            if str(vigente) != str(valor):
                raise EstadoInvalidoError(f"{motivo} Campo rechazado: {clave} ({vigente!r} -> {valor!r}).")
        novela = novela_actual
    else:
        novela = novela_form

    config: HarnessConfig = construir_config(novela, ejecucion)
    archivos_ref = _archivos_de_referencia(_rutas_referencia(campos))

    # --- desde acá, ya nada puede fallar por validación: se escribe ---
    rutas.crear_carpetas()
    resultado = ResultadoGuardado()
    repo.escribir_texto(rutas.idea, idea)
    resultado.escritos.append(rutas.idea)
    if motivo is None:
        rutas.novela_json.write_text(json.dumps(config.a_novela_json(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        resultado.escritos.append(rutas.novela_json)
    rutas.ejecucion_json.write_text(json.dumps(config.a_ejecucion_json(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    resultado.escritos.append(rutas.ejecucion_json)
    for archivo in archivos_ref:
        destino = rutas.referencias / archivo.name
        shutil.copyfile(archivo, destino)
        resultado.copiados.append(destino)
    resultado.comando_siguiente = "/destilar-estilo" if _referencias_presentes(rutas) else "/generar-premisa"
    return resultado


# ---------- HTML ----------

_ESTILO = """
body{font-family:system-ui,sans-serif;max-width:60rem;margin:2rem auto;padding:0 1rem;line-height:1.4;color:#222;background:#fafafa}
h1{font-size:1.5rem}h2{font-size:1.1rem;margin-top:2rem;border-bottom:1px solid #ccc;padding-bottom:.25rem}
fieldset{border:1px solid #ccc;padding:1rem;margin:1rem 0;background:#fff}fieldset:disabled{background:#eee;color:#777}
label{display:block;margin:.6rem 0 .2rem;font-weight:600}small{font-weight:400;color:#666;margin-left:.5rem}
input[type=text],input[type=number],select,textarea{width:100%;box-sizing:border-box;padding:.4rem;font:inherit}
textarea{min-height:10rem}.aviso{background:#fff3cd;border:1px solid #e0a800;padding:.75rem 1rem;margin:1rem 0}
.error{background:#f8d7da;border:1px solid #b02a37;padding:.75rem 1rem;margin:1rem 0;white-space:pre-wrap}
.ok{background:#d1e7dd;border:1px solid #0f5132;padding:.75rem 1rem;margin:1rem 0}
button{font:inherit;padding:.6rem 1.4rem;cursor:pointer}code{background:#eee;padding:0 .25rem}
"""


def _pagina(titulo: str, cuerpo: str) -> str:
    return (f"<!doctype html><html lang='es'><head><meta charset='utf-8'><title>{html.escape(titulo)}</title>"
            f"<style>{_ESTILO}</style></head><body><h1>{html.escape(titulo)}</h1>{cuerpo}</body></html>")


def _campo(clave: str, etiqueta: str, ayuda: str, valor: Any, *, requerido: bool = True) -> str:
    v = "" if valor is None else html.escape(str(valor))
    if clave in OPCIONES:
        opciones = "".join(f"<option value='{o}'{' selected' if o == valor else ''}>{o}</option>" for o in OPCIONES[clave])
        control = f"<select id='{clave}' name='{clave}'>{opciones}</select>"
    elif clave == "idioma":
        control = f"<input type='text' id='{clave}' name='{clave}' value='{v}' required>"
    else:
        control = f"<input type='number' id='{clave}' name='{clave}' value='{v}'{' required' if requerido else ''}>"
    return f"<label for='{clave}'>{html.escape(etiqueta)}<small>{html.escape(ayuda)}</small></label>{control}"


def render_formulario(estado: EstadoFormulario, error: str | None = None) -> str:
    v = estado.valores
    aviso = f"<div class='aviso'>{html.escape(estado.motivo_bloqueo)}</div>" if estado.bloqueado else ""
    err = f"<div class='error'><strong>No se guardó nada.</strong>\n{html.escape(error)}</div>" if error else ""
    deshabilitado = " disabled" if estado.bloqueado else ""
    refs = ("<p>Ya en <code>00_referencias/</code>: " + ", ".join(html.escape(r) for r in estado.referencias) + "</p>"
            if estado.referencias else "<p><code>00_referencias/</code> está vacía.</p>")
    voz = "".join(_campo(c, e, a, v.get(c)) for c, e, a in CAMPOS_VOZ)
    dimension = "".join(_campo(c, e, a, v.get(c)) for c, e, a in CAMPOS_DIMENSION)
    ejecucion = "".join(_campo(c, e, a, v.get(c), requerido=False) for c, e, a in CAMPOS_EJEC)
    marcado = " checked" if v.get("registrar_uso") else ""
    cuerpo = f"""
{aviso}{err}
<form method='post' action='/guardar'>
<h2>Idea de la novela <small>RF-01.1 · 01_concepto/idea.md</small></h2>
<textarea name='idea' required placeholder='Texto libre: situación, lugar, tripulación, qué sale mal...'>{html.escape(estado.idea)}</textarea>

<h2>Voz narrativa <small>RF-CFG-05 · config/novela.json</small></h2>
<fieldset{deshabilitado}>{voz}</fieldset>

<h2>Dimensionamiento <small>RF-CFG-01 · config/novela.json</small></h2>
<fieldset{deshabilitado}>{dimension}</fieldset>

<h2>Ejecución <small>RF-CFG-02, RF-CFG-06 · config/ejecucion.json</small></h2>
<fieldset>{ejecucion}
<label><input type='checkbox' name='registrar_uso'{marcado}> Registrar uso<small>RF-CFG-06 · escribe 04_estado/uso.jsonl</small></label>
</fieldset>

<h2>Ejemplos de referencia <small>RF-00.2 · copia a 00_referencias/</small></h2>
<fieldset>{refs}
<label for='referencias'>Rutas locales<small>una por línea; archivos .md/.txt o carpetas que los contengan</small></label>
<textarea id='referencias' name='referencias' style='min-height:5rem' placeholder='C:\\ruta\\al\\ejemplo.txt'></textarea>
</fieldset>

<p><button type='submit'>Validar y guardar</button></p>
</form>
<p><small>Este formulario no invoca ningún modelo ni lee el manuscrito (§15). Escucha solo en {HOST}.</small></p>
"""
    return _pagina("creador-novelas · entrada de requisitos", cuerpo)


def render_resultado(resultado: ResultadoGuardado, raiz: Path) -> str:
    def rel(p: Path) -> str:
        try:
            return html.escape(p.relative_to(raiz).as_posix())
        except ValueError:
            return html.escape(str(p))

    escritos = "".join(f"<li><code>{rel(p)}</code></li>" for p in resultado.escritos)
    copiados = "".join(f"<li><code>{rel(p)}</code></li>" for p in resultado.copiados)
    bloque_copiados = f"<h2>Referencias copiadas</h2><ul>{copiados}</ul>" if copiados else ""
    cuerpo = f"""
<div class='ok'><strong>Guardado.</strong> La configuración validó contra HarnessConfig antes de escribirse.</div>
<h2>Archivos escritos</h2><ul>{escritos}</ul>
{bloque_copiados}
<h2>Siguiente paso</h2>
<p>En la sesión de Claude Code, teclear: <code>{html.escape(resultado.comando_siguiente)}</code></p>
<p><a href='/'>Volver al formulario</a></p>
"""
    return _pagina("creador-novelas · guardado", cuerpo)


# ---------- servidor ----------

def _parsear_formulario(cuerpo: bytes) -> dict[str, str]:
    return {k: v[-1] for k, v in parse_qs(cuerpo.decode("utf-8"), keep_blank_values=True).items()}


class _Manejador(BaseHTTPRequestHandler):
    raiz: Path  # la fija crear_servidor

    def _responder(self, codigo: int, pagina: str) -> None:
        datos = pagina.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(datos)

    def _bytes(self, codigo: int, datos: bytes, tipo: str) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(datos)

    def _json(self, codigo: int, datos: Any) -> None:
        self._bytes(codigo, json.dumps(datos, ensure_ascii=False).encode("utf-8"),
                    "application/json; charset=utf-8")

    def _estatico(self, nombre: str) -> None:
        """Sirve `app/static/`. Resuelve y comprueba el padre: ninguna ruta puede salir de ahí."""
        base = (Path(__file__).parent / "static").resolve()
        destino = (base / nombre).resolve()
        if destino.parent != base or not destino.is_file():
            self._responder(404, _pagina("No encontrado", "<p>No existe ese archivo.</p>"))
            return
        tipos = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                 ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8",
                 ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                 ".webp": "image/webp", ".svg": "image/svg+xml"}
        self._bytes(200, destino.read_bytes(), tipos.get(destino.suffix.lower(), "application/octet-stream"))

    def _redirigir(self, destino: str) -> None:
        """302 conservando la consulta: `/lectura?cap=4` tiene que seguir siendo el capítulo 4."""
        consulta = self.path.split("?", 1)
        self.send_response(302)
        self.send_header("Location", destino + ("?" + consulta[1] if len(consulta) > 1 else ""))
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        ruta = self.path.split("?", 1)[0]
        if ruta == "/":
            self._responder(200, render_formulario(estado_formulario(self.raiz)))
        elif ruta in ("/consola", "/consola/"):
            # Redirección y no servir aquí el HTML: así sus rutas relativas (gsap.min.js) siguen
            # resolviendo igual servidas que abriendo el archivo a mano.
            self._redirigir("/static/consola.html")
        elif ruta.startswith("/static/"):
            self._estatico(ruta[len("/static/"):])
        elif ruta in ("/lectura", "/lectura/"):
            self._redirigir("/static/lectura.html")
        elif ruta == "/api/indice":
            self._json(200, web.indice(self.raiz))
        elif ruta.startswith("/api/capitulo/"):
            try:
                n = int(ruta[len("/api/capitulo/"):].strip("/"))
            except ValueError:
                self._json(400, {"error": "el capítulo se pide por su número"})
                return
            cap = web.capitulo(self.raiz, n)
            self._json(200 if cap else 404, cap or {"error": f"el capítulo {n} todavía no está escrito"})
        elif ruta == "/api/estado":
            self._json(200, web.estado(self.raiz))
        elif ruta == "/api/eventos":
            self._json(200, web.eventos(self.raiz))
        elif ruta == "/api/qa":
            informe = web.informe_qa(self.raiz)
            self._json(200 if informe else 404, informe or {"error": "no hay ningún informe pendiente"})
        else:
            self._responder(404, _pagina("No encontrado",
                                         "<p>Existen <a href='/'>/</a> y <a href='/consola'>/consola</a>.</p>"))

    def do_POST(self) -> None:  # noqa: N802
        if self.path.startswith("/api/fase/"):
            fase = self.path[len("/api/fase/"):].strip("/")
            try:
                self._json(200, web.lanzar_fase(self.raiz, fase))
            except (ValueError, RuntimeError) as e:
                self._json(409, {"error": str(e)})
            return
        if self.path != "/guardar":
            self._responder(404, _pagina("No encontrado", "<p>Solo existe <code>POST /guardar</code>.</p>"))
            return
        longitud = int(self.headers.get("Content-Length") or 0)
        campos = _parsear_formulario(self.rfile.read(longitud))
        try:
            resultado = procesar_guardado(self.raiz, campos)
        except (ConfiguracionInvalidaError, EstadoInvalidoError) as e:
            self._responder(400, render_formulario(estado_formulario(self.raiz), error=str(e)))
            return
        self._responder(200, render_resultado(resultado, self.raiz))

    def log_message(self, formato: str, *args) -> None:  # silencio: el usuario ve solo la URL
        pass


def crear_servidor(raiz: Path, puerto: int) -> ThreadingHTTPServer:
    """Servidor ligado a 127.0.0.1 únicamente (§15.2). Puerto 0 = que lo elija el sistema (tests)."""
    manejador = type("Manejador", (_Manejador,), {"raiz": raiz})
    return ThreadingHTTPServer((HOST, puerto), manejador)


def servir(raiz: Path, puerto: int = 8765) -> int:
    servidor = crear_servidor(raiz, puerto)
    puerto_real = servidor.server_address[1]
    print(f"Consola de puente en http://{HOST}:{puerto_real}/consola   (raíz: {raiz})", flush=True)
    print(f"Formulario suelto en http://{HOST}:{puerto_real}/  —  los mismos parámetros, sin la consola",
          flush=True)
    print("Ctrl+C para detener.", flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()
    return 0
