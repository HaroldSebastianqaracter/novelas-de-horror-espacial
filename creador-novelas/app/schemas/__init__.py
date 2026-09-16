"""Esquemas Pydantic de los artefactos de estado: única fuente (spec técnica §4, §5)."""

from app.schemas.continuidad import HechoContinuidad, LogContinuidad
from app.schemas.deltas import DeltaExtraccion
from app.schemas.manifest import ESTADOS, Manifest
from app.schemas.mundo import Mundo
from app.schemas.outline import EntradaOutline, Outline
from app.schemas.personajes import FichaPersonajes, Personaje
from app.schemas.qa import Hallazgo, RecursosUsados, RecursoUsado, ReporteQA
from app.schemas.recursos import RecursoAcumulado, RecursoNarrativo, RecursosNarrativos

__all__ = [
    "DeltaExtraccion", "EntradaOutline", "ESTADOS", "FichaPersonajes", "Hallazgo", "HechoContinuidad",
    "LogContinuidad", "Manifest", "Mundo", "Outline", "Personaje", "RecursoAcumulado", "RecursoNarrativo",
    "RecursosNarrativos", "RecursoUsado", "RecursosUsados", "ReporteQA",
]
