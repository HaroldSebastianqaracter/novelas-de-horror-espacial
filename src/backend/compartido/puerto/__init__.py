"""Puerto al motor de agentes. La unica abstraccion real del backend."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from .base import (
    AgenteInterrumpido,
    AgenteNoAutenticado,
    ErrorDePuerto,
    PuertoAgente,
    ResultadoAgente,
    SalidaInvalida,
    SkillDesconocida,
    TiempoAgotado,
)
from .falso import PuertoFalso
from .terminal import PuertoTerminal

if TYPE_CHECKING:
    from config import Config

__all__ = [
    "AgenteInterrumpido",
    "AgenteNoAutenticado",
    "ErrorDePuerto",
    "PuertoAgente",
    "PuertoFalso",
    "PuertoTerminal",
    "ResultadoAgente",
    "SalidaInvalida",
    "SkillDesconocida",
    "TiempoAgotado",
    "construir",
]


def construir(cfg: Config, con: sqlite3.Connection | None = None) -> PuertoAgente:
    """Devuelve el puerto que pide la configuracion (RF-PROC-02)."""
    if cfg.puerto == "falso":
        return PuertoFalso(fixtures_dir=cfg.puerto_falso_dir, con=con)
    return PuertoTerminal(
        claude_bin=cfg.claude_bin,
        skills_dir=cfg.skills_dir,
        timeout_agente_segundos=cfg.timeout_agente_segundos,
        con=con,
    )
