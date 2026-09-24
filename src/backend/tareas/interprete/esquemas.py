"""Salida del interprete de cambios del lector (specs/spec3.md, RF3-CAM-03).

El esquema fija la forma; lo que el interprete devuelve no se cree hasta que el codigo lo
comprueba contra los candidatos que recibio (RF3-CAM-04).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class SalidaInterprete(BaseModel):
    admisible: bool = Field(description="Si la peticion es un cambio de canon que se puede aplicar")
    motivo: str = Field(min_length=1, max_length=400,
                        description="Por que es o no es admisible, para el lector")
    tipo: Literal["renombrar", "cambiar_hecho"] | None = None
    entidad: Literal["personajes", "lugares", "objetos"] | None = None
    entidad_id: int | None = Field(default=None, ge=1)
    nombre_nuevo: str | None = None
    hecho_id: int | None = Field(default=None, ge=1)
    valor_nuevo: str | None = None

    @model_validator(mode="after")
    def _cambio_completo(self) -> SalidaInterprete:
        if not self.admisible:
            return self
        if self.tipo == "renombrar":
            if self.entidad is None or self.entidad_id is None or not self.nombre_nuevo:
                raise ValueError("Renombrar exige entidad, entidad_id y nombre_nuevo.")
        elif self.tipo == "cambiar_hecho":
            if self.hecho_id is None or not self.valor_nuevo:
                raise ValueError("Cambiar un hecho exige hecho_id y valor_nuevo.")
        else:
            raise ValueError("Un cambio admisible necesita tipo: renombrar o cambiar_hecho.")
        return self
