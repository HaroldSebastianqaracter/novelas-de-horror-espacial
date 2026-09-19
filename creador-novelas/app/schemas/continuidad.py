"""Log de continuidad (spec técnica §4, §12.3; RF-04.3, RF-06.3, RF-07.6, INV-03)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, RootModel

Categoria = Literal["personaje", "locacion", "mundo"]


class HechoContinuidad(BaseModel):
    sujeto: str  # clave de personajes.json, locación de mundo.json, o "mundo"
    categoria: Categoria
    sujeto_validado: bool = True  # False si `sujeto` no estaba en el registro (RF-06.1)
    hecho: str = Field(min_length=1)  # la formulación en prosa: es lo que lee el escritor
    cap_origen: int  # INV-03: todo hecho es trazable a su capítulo
    superado_por: int | None = None  # RF-07.6; nulo mientras el hecho siga vigente

    def vigente(self) -> bool:
        return self.superado_por is None


class LogContinuidad(RootModel[list[HechoContinuidad]]):
    def __len__(self) -> int:
        return len(self.root)

    def __iter__(self):
        return iter(self.root)

    def vigentes(self) -> list[HechoContinuidad]:
        return [h for h in self.root if h.vigente()]
