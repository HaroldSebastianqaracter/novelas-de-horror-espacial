"""Escritura en el grafo: inserciones y resolucion de nombres a ids.

Vive en compartido/ porque es canon, no logica de una fase: cada tarea escribe lo suyo con
estas piezas desde su propio `servicio.py`, sin importar de otra tarea.

La pieza que mas importa aqui es el **resolvedor de nombres**. Los agentes se refieren a las
entidades por su nombre ("Kowalski", "Modulo de carga"), nunca por id, porque los ids no
significan nada para quien escribe. Traducir ese nombre a un id es trabajo del codigo, y lo
que no se pueda traducir no se inventa: se registra como entidad no reconocida, que es un
dato para la puerta 3.
"""

from __future__ import annotations

import json
import sqlite3
import unicodedata
from collections.abc import Mapping
from typing import Any


def normalizar(nombre: str) -> str:
    """Clave de comparacion de nombres: sin tildes, sin mayusculas, sin espacios de sobra."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", nombre) if unicodedata.category(c) != "Mn"
    )
    return " ".join(sin_tildes.lower().split())


def _serializar(valor: Any) -> Any:
    if isinstance(valor, (dict, list, tuple)):
        return json.dumps(valor, ensure_ascii=False)
    if isinstance(valor, bool):
        return int(valor)
    return valor


def insertar(con: sqlite3.Connection, tabla: str, **campos: Any) -> int:
    """Inserta una fila y devuelve su id. Los dict y list se guardan como JSON."""
    limpios = {k: _serializar(v) for k, v in campos.items() if v is not None}
    columnas = ", ".join(limpios)
    huecos = ", ".join("?" * len(limpios))
    cur = con.execute(
        f"INSERT INTO {tabla} ({columnas}) VALUES ({huecos})", list(limpios.values())
    )
    return int(cur.lastrowid or 0)


def actualizar(con: sqlite3.Connection, tabla: str, id_fila: int, **campos: Any) -> None:
    limpios = {k: _serializar(v) for k, v in campos.items() if v is not None}
    if not limpios:
        return
    asignaciones = ", ".join(f"{k} = ?" for k in limpios)
    con.execute(f"UPDATE {tabla} SET {asignaciones} WHERE id = ?",
                [*limpios.values(), id_fila])


class Resolvedor:
    """Traduce nombres de entidad a ids dentro de una novela.

    Se construye una vez por fase y cachea, porque una escaleta resuelve el mismo nombre de
    personaje decenas de veces.
    """

    TABLAS_CON_NOMBRE = (
        "personaje", "lugar", "objeto", "faccion", "sistema_tecnologico", "tema", "motivo",
    )

    def __init__(self, con: sqlite3.Connection, novela_id: int) -> None:
        self.con = con
        self.novela_id = novela_id
        self._cache: dict[str, dict[str, int]] = {}
        self.no_resueltos: list[tuple[str, str]] = []

    def _indice(self, tabla: str) -> dict[str, int]:
        if tabla not in self._cache:
            columna = "simbolo" if tabla == "motivo" else "nombre"
            if tabla == "tema":
                columna = "pregunta_central"
            filas = self.con.execute(
                f"SELECT id, {columna} AS nombre FROM {tabla} WHERE novela_id = ?",
                (self.novela_id,),
            ).fetchall()
            self._cache[tabla] = {normalizar(f["nombre"]): int(f["id"]) for f in filas}
        return self._cache[tabla]

    def id_de(self, tabla: str, nombre: str | None, *, obligatorio: bool = False) -> int | None:
        """Devuelve el id de esa entidad, o None si no existe.

        Con `obligatorio`, un nombre desconocido es un error: se usa donde el esquema exige
        la clave ajena y seguir seria escribir una fila invalida.
        """
        if not nombre or not nombre.strip():
            if obligatorio:
                raise NombreDesconocido(f"Falta el nombre de {tabla}.")
            return None
        clave = normalizar(nombre)
        encontrado = self._indice(tabla).get(clave)
        if encontrado is None:
            self.no_resueltos.append((tabla, nombre))
            if obligatorio:
                raise NombreDesconocido(
                    f"No existe {tabla} con nombre '{nombre}' en el canon de esta novela."
                )
        return encontrado

    def registrar(self, tabla: str, nombre: str, id_fila: int) -> None:
        """Mete en cache algo recien insertado, para que el resto de la fase lo vea."""
        self._indice(tabla)[normalizar(nombre)] = id_fila

    def olvidar(self, tabla: str) -> None:
        self._cache.pop(tabla, None)


class NombreDesconocido(Exception):
    """Un agente se refirio a una entidad que no esta en el canon."""


def anotar_entidades_no_reconocidas(
    con: sqlite3.Connection,
    novela_id: int,
    escena_id: int,
    nombres: Mapping[str, str],
) -> None:
    """Registra lo que el texto uso y el canon no conoce (RF-PIPE-12).

    No es un error de validacion: es justo lo que la puerta 3 tiene que ver.
    """
    for nombre, contexto in nombres.items():
        insertar(
            con, "entidad_no_reconocida",
            novela_id=novela_id, escena_id=escena_id, nombre=nombre, contexto=contexto,
        )


def emitir_evento(*args: Any, **payload: Any) -> int:
    """Escribe un evento de traza. El SSE lo lee de aqui; el GET sigue siendo la verdad.

    La firma va por posicion —(con, novela_id, tipo)— a proposito: el payload es libre y un
    evento cuyo payload lleve una clave `tipo` o `novela_id` chocaria con los parametros.
    """
    con, novela_id, tipo = args
    return insertar(
        con, "traza_evento", novela_id=novela_id, tipo=tipo,
        payload=json.dumps(payload, ensure_ascii=False, default=str),
    )
