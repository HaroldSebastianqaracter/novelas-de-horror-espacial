"""Reporte de QA y registro de recursos narrativos (spec técnica §4; RF-07.2, RF-07.3, RF-07.5)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, RootModel, model_validator


class Hallazgo(BaseModel):
    tipo: Literal["contradiccion", "repeticion"]
    descripcion: str = Field(min_length=1)
    cap_origen: int | None = None  # obligatorio si tipo == "contradiccion"

    @model_validator(mode="after")
    def _contradiccion_cita_origen(self) -> "Hallazgo":
        if self.tipo == "contradiccion" and self.cap_origen is None:
            raise ValueError("RF-07.2: toda contradicción debe citar el cap_origen del hecho contradicho")
        return self


class ReporteQA(BaseModel):
    cap_corte: int
    hallazgos: list[Hallazgo]
    tiene_contradicciones: bool

    @model_validator(mode="after")
    def _bandera_coherente(self) -> "ReporteQA":
        hay = any(h.tipo == "contradiccion" for h in self.hallazgos)
        if hay != self.tiene_contradicciones:
            raise ValueError(
                "RF-07.4: `tiene_contradicciones` debe coincidir con la presencia de hallazgos de tipo contradiccion"
            )
        return self

    def conteo_por_tipo(self) -> dict[str, int]:
        conteo = {"contradiccion": 0, "repeticion": 0}
        for h in self.hallazgos:
            conteo[h.tipo] += 1
        return conteo


class RecursoUsado(BaseModel):
    recurso: str = Field(min_length=1)
    veces: int = Field(ge=1)
    caps: list[int]


class RecursosUsados(RootModel[list[RecursoUsado]]):
    pass
