"""La cola es una tabla (RF-WK-01).

Una tabla `intencion` y un worker que hace polling cada pocos segundos. La ventaja no es la
simplicidad, es la transaccionalidad: encolar lo siguiente entra en la misma transaccion que
guardar lo anterior, asi que la unidad de encolado y la unidad de trabajo coinciden.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from typing import Any

from compartido.db import transaccion


@dataclass(frozen=True)
class Intencion:
    id: int
    tipo: str
    novela_id: int | None
    payload: dict[str, Any]


def encolar(
    con: sqlite3.Connection, tipo: str, novela_id: int | None = None, **payload: Any
) -> int:
    cur = con.execute(
        "INSERT INTO intencion (tipo, novela_id, payload) VALUES (?,?,?)",
        (tipo, novela_id, json.dumps(payload, ensure_ascii=False)),
    )
    return int(cur.lastrowid or 0)


def tomar(con: sqlite3.Connection) -> Intencion | None:
    """Coge la intencion pendiente mas antigua y la marca en curso, de forma atomica."""
    with transaccion(con):
        fila = con.execute(
            """
            UPDATE intencion SET estado = 'en_curso', actualizado_en = datetime('now')
             WHERE id = (SELECT id FROM intencion WHERE estado = 'pendiente'
                          ORDER BY creado_en, id LIMIT 1)
            RETURNING id, tipo, novela_id, payload
            """
        ).fetchone()
    if fila is None:
        return None
    try:
        payload = json.loads(fila["payload"] or "{}")
    except json.JSONDecodeError:
        payload = {}
    return Intencion(
        id=int(fila["id"]), tipo=str(fila["tipo"]),
        novela_id=fila["novela_id"], payload=payload,
    )


def hay_parada_pendiente(con: sqlite3.Connection, novela_id: int | None) -> bool:
    """Si el autor ha pedido parar, el worker tiene que enterarse a mitad de una llamada."""
    fila = con.execute(
        "SELECT 1 FROM intencion WHERE estado = 'pendiente' AND tipo = 'parar' "
        "AND (novela_id IS ? OR novela_id IS NULL) LIMIT 1",
        (novela_id,),
    ).fetchone()
    return fila is not None


def cerrar(
    con: sqlite3.Connection,
    intencion_id: int,
    estado: str,
    *,
    motivo: str | None = None,
    resultado: dict[str, Any] | None = None,
) -> None:
    with transaccion(con):
        con.execute(
            """
            UPDATE intencion SET estado = ?, motivo = ?, resultado = ?,
                   actualizado_en = datetime('now')
             WHERE id = ?
            """,
            (
                estado, motivo,
                json.dumps(resultado, ensure_ascii=False) if resultado else None,
                intencion_id,
            ),
        )


# --- Cerrojo del worker (RF-PROC-04, RF-WK-07) ---------------------------------------------


class OtroWorkerVivo(Exception):
    """Ya hay un worker escribiendo en esta base de datos."""


def tomar_cerrojo(con: sqlite3.Connection, *, ciclos_de_gracia: int = 3,
                  poll_segundos: int = 2) -> None:
    """SQLite admite un escritor a la vez: dos workers serian `database is locked`."""
    limite = ciclos_de_gracia * poll_segundos
    with transaccion(con):
        fila = con.execute(
            "SELECT pid, (julianday('now') - julianday(latido_en)) * 86400 AS antiguedad "
            "FROM worker_lock WHERE id = 1"
        ).fetchone()
        mio = os.getpid()
        if fila is not None and int(fila["pid"]) != mio and float(fila["antiguedad"]) < limite:
            raise OtroWorkerVivo(
                f"Hay otro worker vivo (pid {fila['pid']}, ultimo latido hace "
                f"{float(fila['antiguedad']):.1f} s). Solo puede escribir uno."
            )
        con.execute(
            "INSERT INTO worker_lock (id, pid) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET pid = excluded.pid, "
            "arrancado_en = datetime('now'), latido_en = datetime('now')",
            (mio,),
        )


def latir(con: sqlite3.Connection) -> None:
    with transaccion(con):
        con.execute(
            "UPDATE worker_lock SET latido_en = datetime('now') WHERE id = 1 AND pid = ?",
            (os.getpid(),),
        )


def soltar_cerrojo(con: sqlite3.Connection) -> None:
    with transaccion(con):
        con.execute("DELETE FROM worker_lock WHERE id = 1 AND pid = ?", (os.getpid(),))
