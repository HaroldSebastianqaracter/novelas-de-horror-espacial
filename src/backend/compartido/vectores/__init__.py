"""Indice vectorial derivado: recupera contexto, nunca verifica nada."""

from .embebido import Embedder, EmbeddingNoDisponible, construir
from .indice import Fragmento, Indice, IndiceNoDisponible, purgar_descartes

__all__ = [
    "Embedder", "EmbeddingNoDisponible", "Fragmento", "Indice", "IndiceNoDisponible",
    "construir", "purgar_descartes",
]
