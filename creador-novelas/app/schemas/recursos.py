"""Recursos narrativos recurrentes (RF-05.5; spec técnica §17.2, §17.3).

Dos formas del mismo dato:
- `RecursoNarrativo`: lo que el extractor emite en su delta para UN capítulo (imagen, gesto o giro, con las veces
  que lo vio en ese capítulo). No lo acota `max_hechos_por_capitulo` (§17.3).
- `RecursoAcumulado`: lo que vive en `04_estado/recursos_narrativos.json`, con las apariciones por capítulo. Se
  acumula como los hechos de continuidad y `preparar-capitulo` inyecta los más usados al escritor como recursos
  agotados, no prohibidos.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, RootModel


class RecursoNarrativo(BaseModel):
    recurso: str = Field(min_length=3, max_length=200)  # descripción corta del recurso, no la frase entera
    veces: int = Field(default=1, ge=1)  # apariciones en el capítulo extraído


class RecursoAcumulado(BaseModel):
    recurso: str = Field(min_length=3, max_length=200)
    apariciones: dict[str, int] = {}  # capítulo (clave JSON, texto) -> veces en ese capítulo

    @property
    def veces(self) -> int:
        return sum(self.apariciones.values())

    @property
    def caps(self) -> list[int]:
        return sorted(int(c) for c in self.apariciones)


class RecursosNarrativos(RootModel[list[RecursoAcumulado]]):
    def __len__(self) -> int:
        return len(self.root)

    def __iter__(self):
        return iter(self.root)
