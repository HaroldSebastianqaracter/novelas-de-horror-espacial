"""Salida del revisor de continuidad: el informe y la segunda opinion de una parada.

La puerta 3 es SQL y decide sola. El revisor se invoca unicamente cuando ya ha parado, para
explicar cada conflicto en lenguaje legible y dar su opinion de si parece real o un falso
positivo (specs/spec3.md, RF3-JUE-01). La opinion va al informe de la parada para el autor, y
nunca la levanta.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Opinion(BaseModel):
    conflicto: int = Field(ge=1, description="Numero del conflicto en la lista, desde 1")
    parece: Literal["real", "falso_positivo", "dudoso"]
    motivo: str = Field(min_length=10, description="Por que, citando la prosa o el canon")


class SalidaContinuidad(BaseModel):
    resumen: str = Field(min_length=20)
    explicacion_por_conflicto: list[str] = Field(default_factory=list[str])
    opiniones: list[Opinion] = Field(default_factory=list[Opinion])
    sugerencia: str = ""
