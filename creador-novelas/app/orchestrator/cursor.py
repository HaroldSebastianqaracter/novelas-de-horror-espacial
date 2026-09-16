"""Cursor transitorio de tanda: `.tanda/cursor.json` (spec técnica §5).

No es un artefacto de estado. Guarda el tope y el conteo de la tanda en curso, y los contadores de reintento
del capítulo en curso. Lo escriben solo los verbos del loop; se borra cuando la tanda termina.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.rutas import Rutas


@dataclass
class Cursor:
    inicio: int  # primer capítulo de la tanda
    tope: int | None  # capitulos_por_tanda efectivo; None = hasta el final
    max_llamadas: int | None
    cerrados: int = 0  # capítulos cerrados en ESTA tanda (RF-CFG-02)
    llamadas: int = 0  # invocaciones de subagente en esta tanda (RF-CFG-06)
    capitulo_en_curso: int | None = None
    intentos_longitud: int = 0  # EX-07
    intentos_personaje: int = 0  # EX-08
    avisos: list[str] = field(default_factory=list)

    def tope_alcanzado(self) -> bool:
        return self.tope is not None and self.cerrados >= self.tope

    def llamadas_agotadas(self) -> bool:
        return self.max_llamadas is not None and self.llamadas >= self.max_llamadas


def leer(raiz: Path) -> Cursor | None:
    path = Rutas(raiz).cursor
    if not path.exists():
        return None
    try:
        return Cursor(**json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, TypeError):
        return None


def escribir(raiz: Path, cursor: Cursor) -> None:
    path = Rutas(raiz).cursor
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(cursor), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def borrar(raiz: Path) -> None:
    path = Rutas(raiz).cursor
    if path.exists():
        path.unlink()


def exigir(raiz: Path) -> Cursor:
    c = leer(raiz)
    if c is None:
        raise RuntimeError("no hay tanda en curso: ejecutá `python -m app tanda iniciar` primero")
    return c


def sumar_llamada(raiz: Path) -> Cursor | None:
    """Lo usa H-10 (y el loop con dobles) por cada invocación de subagente."""
    c = leer(raiz)
    if c is None:
        return None
    c.llamadas += 1
    escribir(raiz, c)
    return c
