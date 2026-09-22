"""Entrada y salida del redactor (RF-PIPE-09).

Devuelve una entrada por escena de la escaleta y en su orden. Falla la validacion si falta
una escena, sobra una, o algun texto trae un marcador pendiente: un capitulo con marcadores
no esta escrito.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from config import MARCADORES_PENDIENTES


class EscenaEscrita(BaseModel):
    orden: int = Field(ge=1, description="El mismo orden que la escena tiene en la escaleta")
    texto: str = Field(min_length=50)

    @field_validator("texto")
    @classmethod
    def _sin_marcadores(cls, v: str) -> str:
        encontrados = [m for m in MARCADORES_PENDIENTES if m in v]
        if encontrados:
            raise ValueError(
                f"El texto trae marcadores pendientes {encontrados}: el capitulo no esta escrito."
            )
        return v

    @property
    def palabras(self) -> int:
        return len(self.texto.split())


class SalidaRedaccion(BaseModel):
    escenas: list[EscenaEscrita] = Field(min_length=1)
    notas: str = ""

    @field_validator("escenas")
    @classmethod
    def _ordenes_unicos(cls, v: list[EscenaEscrita]) -> list[EscenaEscrita]:
        ordenes = [e.orden for e in v]
        if len(set(ordenes)) != len(ordenes):
            raise ValueError(f"Hay escenas repetidas en la salida: {ordenes}")
        return v

    def comprobar_contra_escaleta(self, ordenes_esperados: list[int]) -> None:
        """Exige una escena por cada escena de la escaleta, ni una mas ni una menos."""
        dados = sorted(e.orden for e in self.escenas)
        esperados = sorted(ordenes_esperados)
        if dados != esperados:
            faltan = sorted(set(esperados) - set(dados))
            sobran = sorted(set(dados) - set(esperados))
            partes: list[str] = []
            if faltan:
                partes.append(f"faltan las escenas {faltan}")
            if sobran:
                partes.append(f"sobran las escenas {sobran}")
            raise ValueError("La redaccion no cuadra con la escaleta: " + "; ".join(partes))
