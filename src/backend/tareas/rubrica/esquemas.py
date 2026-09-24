"""Salida de la rubrica: una nota de 1 a 5 por criterio, con su justificacion y su evidencia."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from compartido.tipos import CRITERIOS_RUBRICA, CriterioRubrica


class NotaRubrica(BaseModel):
    criterio: CriterioRubrica
    nota: int = Field(ge=1, le=5, description="1 muy flojo, 3 correcto, 5 excelente")
    justificacion: str = Field(min_length=1, max_length=800,
                               description="Por que esa nota, en dos o tres frases")
    evidencia: str = Field(min_length=1, max_length=400,
                           description="Una cita LITERAL de la novela que sostiene la nota")


class SalidaRubrica(BaseModel):
    notas: list[NotaRubrica]

    @model_validator(mode="after")
    def _un_criterio_cada_uno(self) -> SalidaRubrica:
        vistos = [n.criterio for n in self.notas]
        if sorted(vistos) != sorted(CRITERIOS_RUBRICA):
            raise ValueError(
                "Hace falta exactamente una nota por criterio: " + ", ".join(CRITERIOS_RUBRICA))
        return self
