"""Estimación conservadora de tokens (spec técnica §3.5): tiktoken +15 %, o heurística si tiktoken no está disponible.

La heurística (caracteres / 4, +15 %) se marca como tal en la salida para no dar falsa precisión.
"""

from __future__ import annotations

MARGEN = 1.15
_codificador = None
_intentado = False


def _cargar() -> None:
    global _codificador, _intentado
    if _intentado:
        return
    _intentado = True
    try:
        import tiktoken

        _codificador = tiktoken.get_encoding("cl100k_base")
    except Exception:  # sin el paquete o sin red la primera vez que descarga el vocabulario
        _codificador = None


def estimar_tokens(texto: str) -> tuple[int, str]:
    """Devuelve (tokens estimados con margen, método: 'tiktoken' | 'heuristica')."""
    _cargar()
    if _codificador is not None:
        base = len(_codificador.encode(texto, disallowed_special=()))
        return int(base * MARGEN) + 1, "tiktoken"
    return int(len(texto) / 4 * MARGEN) + 1, "heuristica"
