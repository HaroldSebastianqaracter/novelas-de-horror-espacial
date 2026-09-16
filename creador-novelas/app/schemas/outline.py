"""Escaleta de capítulos (spec técnica §4; RF-03.1, RF-03.2)."""

from __future__ import annotations

from pydantic import BaseModel, Field, RootModel, model_validator


class EntradaOutline(BaseModel):
    num: int
    titulo: str = Field(min_length=1)  # RF-03.1: generado en fase 3, no por el escritor
    objetivo_narrativo: str = Field(min_length=1)
    personajes: list[str]
    locacion: str = Field(min_length=1)
    informacion_nueva: str
    tension: int = Field(ge=1, le=5)


class Outline(RootModel[list[EntradaOutline]]):
    """Array completo. RF-03.1: `num` consecutivo desde 1, sin huecos; ningún `titulo` vacío ni repetido."""

    @model_validator(mode="after")
    def _consecutivos_y_titulos_unicos(self) -> "Outline":
        nums = [e.num for e in self.root]
        if nums != list(range(1, len(nums) + 1)):
            raise ValueError(f"RF-03.1: `num` debe ser consecutivo desde 1 sin huecos; se recibió {nums}")
        titulos = [e.titulo.strip() for e in self.root]
        repetidos = sorted({t for t in titulos if titulos.count(t) > 1})
        if repetidos:
            raise ValueError(f"RF-03.1: títulos repetidos en el outline: {repetidos}")
        return self

    def __len__(self) -> int:
        return len(self.root)

    def entrada(self, n: int) -> EntradaOutline | None:
        for e in self.root:
            if e.num == n:
                return e
        return None

    def tension_maxima_en_tercio_final(self) -> bool:
        """RF-03.2: el máximo de `tension` ocurre en el tercio final del outline."""
        if not self.root:
            return False
        maximo = max(e.tension for e in self.root)
        inicio_tercio_final = len(self.root) - len(self.root) // 3
        return any(e.tension == maximo for e in self.root[inicio_tercio_final - 1:])

    def personajes_mencionados(self) -> list[str]:
        vistos: dict[str, None] = {}
        for e in self.root:
            for p in e.personajes:
                vistos.setdefault(p, None)
        return list(vistos)

    def locaciones_mencionadas(self) -> list[str]:
        vistas: dict[str, None] = {}
        for e in self.root:
            vistas.setdefault(e.locacion, None)
        return list(vistas)
