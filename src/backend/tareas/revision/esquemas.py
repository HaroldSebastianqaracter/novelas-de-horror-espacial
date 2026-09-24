"""Salida del revisor en la pasada del cambio del lector (specs/spec3.md, RF3-CAM-08).

Las mismas escenas que tiene el capitulo, corregidas; los dos resumenes corregidos; y las citas
del cambio, que el codigo busca en la prosa nueva (RF3-CAM-09).
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from config import MARCADORES_PENDIENTES

#: Los mismos limites que el extractor pone a los resumenes (spec3, RF3-PAS-02).
PALABRAS_RESUMEN = 250
PALABRAS_RESUMEN_BREVE = 40
MAX_LETRAS_CITA = 300


def _recortar(texto: str, palabras: int) -> str:
    partes = texto.split()
    return texto if len(partes) <= palabras else " ".join(partes[:palabras])


class EscenaCorregida(BaseModel):
    orden: int = Field(ge=1, description="El orden de la escena en el capitulo, igual que llego")
    texto: str = Field(min_length=50)

    @field_validator("texto")
    @classmethod
    def _sin_marcadores(cls, v: str) -> str:
        encontrados = [m for m in MARCADORES_PENDIENTES if m in v]
        if encontrados:
            raise ValueError(f"El texto trae marcadores pendientes {encontrados}.")
        return v

    @property
    def palabras(self) -> int:
        return len(self.texto.split())


class SalidaRevision(BaseModel):
    escenas: list[EscenaCorregida] = Field(min_length=1)
    resumen: str = Field(min_length=10)
    resumen_breve: str = Field(min_length=10)
    citas: list[str] = Field(
        default_factory=list[str],
        description="Fragmentos literales de la prosa corregida donde se aplico el cambio",
    )
    notas: str = ""

    @field_validator("escenas")
    @classmethod
    def _ordenes_unicos(cls, v: list[EscenaCorregida]) -> list[EscenaCorregida]:
        ordenes = [e.orden for e in v]
        if len(set(ordenes)) != len(ordenes):
            raise ValueError(f"Hay escenas repetidas en la salida: {ordenes}")
        return v

    @field_validator("resumen")
    @classmethod
    def _resumen(cls, v: str) -> str:
        return _recortar(v, PALABRAS_RESUMEN)

    @field_validator("resumen_breve")
    @classmethod
    def _resumen_breve(cls, v: str) -> str:
        return _recortar(v, PALABRAS_RESUMEN_BREVE)

    @field_validator("citas")
    @classmethod
    def _citas(cls, v: list[str]) -> list[str]:
        return [c.strip()[:MAX_LETRAS_CITA] for c in v if c.strip()]

    def textos(self) -> dict[int, str]:
        return {e.orden: e.texto for e in self.escenas}
