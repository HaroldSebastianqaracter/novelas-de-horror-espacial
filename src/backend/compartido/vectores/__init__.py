"""Indice vectorial derivado: recupera contexto, nunca verifica nada."""

from .embebido import Embedder, EmbeddingNoDisponible, construir
from .indice import Fragmento, Indice

__all__ = ["Embedder", "EmbeddingNoDisponible", "Fragmento", "Indice", "construir"]
