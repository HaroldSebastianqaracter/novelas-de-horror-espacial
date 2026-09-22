"""Tipos comunes de las puertas de control.

Una puerta devuelve siempre lo mismo: un veredicto y la lista de lo que encontro. Un
conflicto para el pipeline; un aviso queda en el informe y deja pasar.

Las puertas deterministas van primero porque son baratas y su fallo invalida el trabajo
posterior: no tiene sentido evaluar la prosa de una escena que contradice el canon.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Conflicto:
    """Un incumplimiento concreto, con lo que hace falta para entenderlo sin abrir la base."""

    comprobacion: str
    descripcion: str
    aviso: bool = False
    escena_id: int | None = None
    capitulo: int | None = None
    datos: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        marca = "aviso" if self.aviso else "conflicto"
        donde = f" (cap. {self.capitulo})" if self.capitulo is not None else ""
        return f"[{marca}] {self.comprobacion}{donde}: {self.descripcion}"


@dataclass(frozen=True)
class ResultadoPuerta:
    puerta: int
    conflictos: list[Conflicto] = field(default_factory=list)

    @property
    def bloqueantes(self) -> list[Conflicto]:
        return [c for c in self.conflictos if not c.aviso]

    @property
    def avisos(self) -> list[Conflicto]:
        return [c for c in self.conflictos if c.aviso]

    @property
    def pasa(self) -> bool:
        return not self.bloqueantes

    @property
    def veredicto(self) -> str:
        if self.bloqueantes:
            return "falla"
        return "aviso" if self.avisos else "pasa"

    def informe(self) -> dict[str, Any]:
        return {
            "puerta": self.puerta,
            "veredicto": self.veredicto,
            "conflictos": [asdict(c) for c in self.conflictos],
        }

    def registrar(
        self,
        con: sqlite3.Connection,
        novela_id: int,
        *,
        capitulo: int | None = None,
        intento: int | None = None,
    ) -> None:
        """Deja constancia en resultado_puerta. La llama el orquestador, dentro de su
        transaccion."""
        con.execute(
            """
            INSERT INTO resultado_puerta (novela_id, puerta, capitulo, intento, veredicto, detalle)
            VALUES (?,?,?,?,?,?)
            """,
            (
                novela_id, self.puerta, capitulo, intento, self.veredicto,
                json.dumps(self.informe(), ensure_ascii=False),
            ),
        )
