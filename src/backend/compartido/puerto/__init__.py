"""Puerto al motor de agentes. La unica abstraccion real del backend."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from . import demo
from .base import (
    AgenteInterrumpido,
    AgenteNoAutenticado,
    AgenteUsoHerramientas,
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
    "AgenteUsoHerramientas",
    "ErrorDePuerto",
    "PuertoAgente",
    "PuertoFalso",
    "PuertoTerminal",
    "demo",
    "ResultadoAgente",
    "SalidaInvalida",
    "SkillDesconocida",
    "TiempoAgotado",
    "construir",
]


def construir(cfg: Config, con: sqlite3.Connection | None = None) -> PuertoAgente:
    """Devuelve el puerto que pide la configuracion (RF-PROC-02)."""
    if cfg.puerto == "falso":
        # Sin fixtures propios, los generadores de demostracion: asi `NOVELAS_PUERTO=falso`
        # arranca y corre sin preparar nada (RF-PUERTO-07).
        return PuertoFalso(
            fixtures_dir=cfg.puerto_falso_dir,
            generadores=None if cfg.puerto_falso_dir else dict(demo.TODOS),
            con=con,
        )
    return PuertoTerminal(
        claude_bin=cfg.claude_bin,
        skills_dir=cfg.skills_dir,
        timeout_agente_segundos=cfg.timeout_agente_segundos,
        con=con,
        modelo=cfg.modelo,
    )
