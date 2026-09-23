"""La cola es una tabla (RF-WK-01).

Una tabla `intencion` y un worker que hace polling cada pocos segundos. La ventaja no es la
simplicidad, es la transaccionalidad: encolar lo siguiente entra en la misma transaccion que
guardar lo anterior, asi que la unidad de encolado y la unidad de trabajo coinciden.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from compartido.db import BUSY_TIMEOUT_MS, conectar, transaccion
from compartido.tipos import como_dict


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
        payload = como_dict(json.loads(fila["payload"] or "{}"))
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


# --- Cerrojo del worker (RF-PROC-04, RF2-WK-07, RF2-WK-08) ---------------------------------


class OtroWorkerVivo(Exception):
    """Ya hay un worker escribiendo en esta base de datos."""


class CerrojoPerdido(BaseException):
    """Otro proceso se ha quedado el cerrojo: este worker no puede escribir nada mas.

    Hereda de BaseException a proposito: ningun `except Exception` del pipeline o del worker
    debe tragarsela. Su unico destino es terminar el proceso (RF2-WK-08).
    """


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


def latir(con: sqlite3.Connection, pid: int | None = None) -> bool:
    """Renueva el latido. Devuelve si la fila sigue siendo de este proceso (RF2-WK-07)."""
    with transaccion(con, al_empezar=_sin_guardia):
        cur = con.execute(
            "UPDATE worker_lock SET latido_en = datetime('now') WHERE id = 1 AND pid = ?",
            (pid if pid is not None else os.getpid(),),
        )
    return cur.rowcount == 1


def _sin_guardia(_: sqlite3.Connection) -> None:
    """El latido no pasa por el fencing: su propio `rowcount` ya dice si sigue siendo dueno."""


def exigir_cerrojo(con: sqlite3.Connection) -> None:
    """Fencing: corre dentro de `BEGIN IMMEDIATE`, antes de cualquier escritura (RF2-WK-08).

    Con el cerrojo de escritura de SQLite tomado, nadie mas puede cambiar `worker_lock` hasta
    que esta transaccion termine: si la fila es nuestra ahora, lo sigue siendo mientras
    escribimos.
    """
    fila = con.execute("SELECT pid FROM worker_lock WHERE id = 1").fetchone()
    if fila is None or int(fila["pid"]) != os.getpid():
        dueno = "nadie" if fila is None else f"el pid {fila['pid']}"
        raise CerrojoPerdido(
            f"El cerrojo del worker es de {dueno}, no de este proceso ({os.getpid()}). "
            "No se escribe nada mas."
        )


def soltar_cerrojo(con: sqlite3.Connection) -> None:
    with transaccion(con, al_empezar=_sin_guardia):
        con.execute("DELETE FROM worker_lock WHERE id = 1 AND pid = ?", (os.getpid(),))


class Latido:
    """Hilo que renueva el cerrojo mientras el proceso vive (RF2-WK-07).

    Tiene su propia conexion: la del worker puede pasarse minutos esperando a un agente o
    dentro de una transaccion, y el latido no puede depender de ella. Si un latido descubre
    que la fila ya no es suya, levanta `perdido` y deja de latir; el pipeline lo mira en cada
    punto de comprobacion.
    """

    def __init__(self, ruta: Path, intervalo_s: float) -> None:
        self._ruta = Path(ruta)
        self._intervalo = intervalo_s
        self._pid = os.getpid()
        self._parar = threading.Event()
        self.perdido = threading.Event()
        self._hilo = threading.Thread(target=self._correr, name="latido", daemon=True)

    def iniciar(self) -> Latido:
        self._hilo.start()
        return self

    def detener(self) -> None:
        self._parar.set()
        if self._hilo.is_alive():
            self._hilo.join(timeout=self._intervalo + BUSY_TIMEOUT_MS / 1000)

    def _correr(self) -> None:
        con = conectar(self._ruta)
        try:
            while not self._parar.wait(self._intervalo):
                try:
                    if not latir(con, self._pid):
                        self.perdido.set()
                        return
                except sqlite3.OperationalError:
                    # La base estuvo ocupada mas que el busy_timeout: se reintenta en el
                    # siguiente ciclo. Tres ciclos seguidos asi y otro worker podria entrar.
                    continue
        finally:
            con.close()
