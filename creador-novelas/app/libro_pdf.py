"""El libro en PDF, para el botón de la pantalla de lectura.

El trabajo de verdad lo hace `herramientas/a_latex.py`, que ya sabía convertir una novela --de la
raíz o de `09_archivo/`-- en un `.tex` y compilarlo. Aquí solo está lo que hace falta para llamarlo
desde el servidor: dónde dejar el resultado, y qué decir cuando no se puede.

Se carga por ruta porque `herramientas/` no es un paquete, igual que hacen sus tests. Mantenerlo
ahí deja intacta la línea de comandos, que es como se usó para las novelas ya archivadas.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from app.errores import EstadoInvalidoError
from app.rutas import Rutas

_HERRAMIENTA = Path(__file__).resolve().parents[1] / "herramientas" / "a_latex.py"


def _conversor():
    spec = importlib.util.spec_from_file_location("a_latex", _HERRAMIENTA)
    if spec is None or spec.loader is None:  # pragma: no cover - solo si se borra la herramienta
        raise EstadoInvalidoError(f"no se encuentra el conversor en {_HERRAMIENTA}")
    modulo = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("a_latex", modulo)
    spec.loader.exec_module(modulo)
    return modulo


def hay_motor() -> str | None:
    """El nombre del motor LaTeX disponible, o None. La pantalla lo usa para no ofrecer un botón muerto."""
    motor = _conversor().buscar_motor()
    return Path(motor).stem if motor else None


def generar(raiz: Path, *, novela: Path | None = None) -> Path:
    """Escribe `08_entrega/novela.pdf` y devuelve su ruta.

    `novela` permite apuntar a una carpeta de `09_archivo/`; por defecto es el libro en curso. El
    `.tex` se deja al lado a propósito: si la compilación falla, es el entregable que sí existe y
    con el que se puede ir a un editor de LaTeX.
    """
    rutas = Rutas(raiz)
    origen = novela or raiz
    capitulos = sorted((origen / "05_manuscrito").glob("cap_*.md"))
    if not capitulos:
        raise EstadoInvalidoError("todavía no hay ningún capítulo escrito: no hay libro que componer")

    conversor = _conversor()
    destino = rutas.raiz / "08_entrega"
    destino.mkdir(parents=True, exist_ok=True)
    tex = destino / "novela.tex"
    documento, _titulo = conversor.construir_documento(origen)
    tex.write_text(documento, encoding="utf-8")

    pdf = conversor.compilar(tex)
    if pdf is None:
        motor = conversor.buscar_motor()
        raise EstadoInvalidoError(
            f"el .tex se escribió en {tex}, pero la compilación falló. "
            + ("Revisa novela.log, al lado." if motor else
               "No hay ningún motor LaTeX instalado: instala tectonic o MiKTeX."))
    return pdf
