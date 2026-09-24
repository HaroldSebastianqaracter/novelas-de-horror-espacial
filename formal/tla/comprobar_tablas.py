"""Comprueba que las tablas de StoryMaker.tla son las de orquestador/estados.py (RF-TLA-06).

La especificacion copia a mano las transiciones del codigo. Si alguien cambia una tabla y no
la otra, TLC seguiria verificando una maquina que ya no existe. Este script lee las dos y
falla si difieren en algo:

- TRANSICIONES y RESOLUCIONES, fila a fila;
- ESTADOS_QUE_ADMITEN_RELANZAR, ESTADOS_QUE_ADMITEN_ARRANCAR y ESTADOS_ACTIVOS;
- que MaxIntentos del modelo no pasa de config.MAX_INTENTOS_CAPITULO.

Las transiciones del cambio del lector (TransicionesDelLector) se comparan aparte: mientras el
backend no las tenga, salen como pendientes y no fallan; cuando las tenga, tienen que ser las
mismas.

Uso, desde la raiz del repo:

    src\\backend\\.venv\\Scripts\\python.exe formal\\tla\\comprobar_tablas.py

Sale con 0 si todo coincide y con 1 si algo difiere.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
BACKEND = AQUI.parent.parent / "src" / "backend"
sys.path.insert(0, str(BACKEND))

import config  # noqa: E402
from orquestador import estados  # noqa: E402

Terna = tuple[str, str, str]


def _definicion(texto: str, nombre: str) -> str:
    """El cuerpo de `nombre == ...` hasta la siguiente definicion de nivel superior."""
    m = re.search(rf"^{nombre} ==(.*?)(?=^\S)", texto, re.DOTALL | re.MULTILINE)
    if m is None:
        raise SystemExit(f"No encuentro la definicion {nombre} en StoryMaker.tla")
    return m.group(1)


def _ternas(cuerpo: str) -> set[Terna]:
    return {
        (a, b, c)
        for a, b, c in re.findall(r'<<\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]+)"\s*>>', cuerpo)
    }


def _cadenas(cuerpo: str) -> set[str]:
    return set(re.findall(r'"([^"]+)"', cuerpo))


def _comparar(nombre: str, modelo: set, codigo: set) -> list[str]:
    fallos: list[str] = []
    for x in sorted(codigo - modelo):
        fallos.append(f"{nombre}: el codigo tiene {x} y el modelo no")
    for x in sorted(modelo - codigo):
        fallos.append(f"{nombre}: el modelo tiene {x} y el codigo no")
    return fallos


def main() -> int:
    tla = (AQUI / "StoryMaker.tla").read_text(encoding="utf-8")
    fallos: list[str] = []

    codigo_trans = {(d, s, h) for (d, s), h in estados.TRANSICIONES.items()}
    codigo_resol = {(t, a, h) for (t, a), h in estados.RESOLUCIONES.items()}
    lector = _ternas(_definicion(tla, "TransicionesDelLector"))

    fallos += _comparar(
        "TRANSICIONES", _ternas(_definicion(tla, "Transiciones")), codigo_trans - lector
    )
    fallos += _comparar("RESOLUCIONES", _ternas(_definicion(tla, "Resoluciones")), codigo_resol)
    fallos += _comparar(
        "ESTADOS_QUE_ADMITEN_RELANZAR",
        _cadenas(_definicion(tla, "AdmitenRelanzar")),
        set(estados.ESTADOS_QUE_ADMITEN_RELANZAR),
    )
    fallos += _comparar(
        "ESTADOS_QUE_ADMITEN_ARRANCAR",
        _cadenas(_definicion(tla, "AdmitenArrancar")),
        set(estados.ESTADOS_QUE_ADMITEN_ARRANCAR),
    )
    fallos += _comparar(
        "ESTADOS_ACTIVOS", _cadenas(_definicion(tla, "Activos")), set(estados.ESTADOS_ACTIVOS)
    )

    pendientes = sorted(lector - codigo_trans)
    for cfg in sorted(AQUI.glob("*.cfg")):
        m = re.search(r"MaxIntentos\s*=\s*(\d+)", cfg.read_text(encoding="utf-8"))
        if m and int(m.group(1)) > config.MAX_INTENTOS_CAPITULO:
            fallos.append(
                f"{cfg.name}: MaxIntentos = {m.group(1)} pasa del codigo "
                f"({config.MAX_INTENTOS_CAPITULO})"
            )

    print(f"TRANSICIONES: {len(codigo_trans - lector)} filas en el codigo")
    print(f"RESOLUCIONES: {len(codigo_resol)} filas en el codigo")
    for t in pendientes:
        print(f"pendiente en el backend (cambio del lector): {t}")
    for f in fallos:
        print(f"DIFIERE  {f}")
    if fallos:
        return 1
    print("El modelo y estados.py coinciden.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
