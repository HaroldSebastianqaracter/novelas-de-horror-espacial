"""Fichas de personajes (spec técnica §4, RF-04.1, RF-06.2)."""

from __future__ import annotations

from pydantic import BaseModel, RootModel


class Personaje(BaseModel):
    estado_fisico: str
    estado_psicologico: str
    secretos_que_conoce: list[str] = []
    ultima_aparicion: int


class FichaPersonajes(RootModel[dict[str, Personaje]]):
    """Diccionario nombre canónico -> ficha. Las claves son el registro de sujetos de RF-06.1."""

    def nombres(self) -> list[str]:
        return list(self.root.keys())
