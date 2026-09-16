"""Delta de extracción que devuelve el agente extractor (spec técnica §4; RF-06.1, RF-08.1)."""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.continuidad import HechoContinuidad
from app.schemas.personajes import Personaje
from app.schemas.recursos import RecursoNarrativo


class DeltaExtraccion(BaseModel):
    personajes: dict[str, Personaje]  # solo los que cambiaron; claves del registro (RF-06.1)
    hechos_nuevos: list[HechoContinuidad]
    resumen_corto: str  # 3-5 líneas
    recursos_narrativos: list[RecursoNarrativo] = []  # RF-05.5 / §17.2: imágenes, gestos y giros recurrentes; sin tope de hechos
