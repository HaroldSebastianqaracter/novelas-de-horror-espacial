"""Piezas comunes de los tests que corren el pipeline sobre una base temporal.

Viven aparte para que los tests de spec2 (reanudacion, cerrojo, capitulo a medias...) monten
el mismo entorno sin copiarlo, y para que un cambio en `Config` se arregle en un solo sitio.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import config
from compartido import db
from compartido.db import transaccion
from compartido.puerto import PuertoFalso
from compartido.puerto import demo as agentes_falsos
from orquestador import pipeline


def nueva_bd() -> tuple[sqlite3.Connection, Path]:
    ruta = Path(tempfile.mkdtemp()) / "novela.db"
    return db.preparar(ruta), ruta


def cfg_de(ruta: Path, **cambios: object) -> config.Config:
    base: dict[str, object] = {
        "db_path": ruta, "claude_bin": "claude", "skills_dir": Path(".claude/skills"),
        "poll_segundos": 1, "timeout_agente_segundos": 60, "presupuesto_tokens": 100_000,
        "puerto": "falso", "puerto_falso_dir": None, "embedding_modelo": "hash",
        "vectores_activos": False,
    }
    base.update(cambios)
    return config.Config(**base)  # type: ignore[arg-type]


def crear_novela(con: sqlite3.Connection, palabras: int = 5400) -> int:
    from compartido.grafo import insertar

    with transaccion(con):
        novela_id = insertar(con, "novela", titulo="Cerro Quince", genero="terror_espacial")
        insertar(con, "restriccion", novela_id=novela_id,
                 tipo="longitud_objetivo_palabras", valor=str(palabras))
        insertar(con, "ejecucion", novela_id=novela_id, estado="configurada")
    return novela_id


def puerto_falso(con: sqlite3.Connection) -> PuertoFalso:
    return PuertoFalso(generadores=dict(agentes_falsos.TODOS), con=con)


def contexto(
    con: sqlite3.Connection, puerto: PuertoFalso, ruta: Path, novela_id: int
) -> pipeline.Contexto:
    return pipeline.Contexto(con=con, puerto=puerto, cfg=cfg_de(ruta), novela_id=novela_id)


def contar(con: sqlite3.Connection, sql: str, *params: object) -> int:
    return int(con.execute(sql, params).fetchone()[0])


def hechos_del_capitulo(con: sqlite3.Connection, novela_id: int, numero: int) -> int:
    return contar(
        con,
        "SELECT COUNT(*) FROM hecho h JOIN escena e ON e.id = h.escena_id "
        "JOIN capitulo c ON c.id = e.capitulo_id WHERE h.novela_id = ? AND c.numero = ?",
        novela_id, numero,
    )


def textos_vigentes_del_capitulo(con: sqlite3.Connection, novela_id: int, numero: int) -> int:
    return contar(
        con,
        "SELECT COUNT(*) FROM escena_texto t JOIN escena e ON e.id = t.escena_id "
        "JOIN capitulo c ON c.id = e.capitulo_id "
        "WHERE t.novela_id = ? AND c.numero = ? AND t.estado = 'vigente'",
        novela_id, numero,
    )
