"""Delta de extracción que devuelve el agente extractor (spec técnica §4; RF-06.1, RF-08.1)."""

from __future__ import annotations

from pydantic import BaseModel

from harness.schemas.continuidad import HechoContinuidad
from harness.schemas.personajes import Personaje


class DeltaExtraccion(BaseModel):
    personajes: dict[str, Personaje]  # solo los que cambiaron; claves del registro (RF-06.1)
    hechos_nuevos: list[HechoContinuidad]
    resumen_corto: str  # 3-5 líneas
