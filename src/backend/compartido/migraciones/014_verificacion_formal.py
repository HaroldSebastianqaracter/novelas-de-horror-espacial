"""Paso en Python de la migracion 014 (specs/spec-lean.md, RF-LEAN-06).

Anade el tipo `formal` al CHECK de `parada`. Rehacer la tabla no sirve aqui: tiene hijos
(`hecho`, `entidad_no_reconocida`, `hecho_revocacion`) con ON DELETE SET NULL, y dentro de la
transaccion de la migracion las claves ajenas estan activas, asi que borrar la tabla vieja
vaciaria su `parada_id`, y renombrarla reescribiria las claves de los hijos. Es el caso que la
documentacion de SQLite resuelve editando el esquema guardado (`writable_schema`): cambiar un
CHECK no cambia el formato en disco. Despues se sube `schema_version` para que toda conexion
relea el esquema, y se comprueba la integridad.
"""

from __future__ import annotations

import sqlite3

from compartido.db import ErrorDeDatos

VIEJO = "'oficio','presupuesto')"
NUEVO = "'oficio','presupuesto','formal')"


def aplicar(con: sqlite3.Connection) -> None:
    fila = con.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'parada'"
                       ).fetchone()
    sql = str(fila[0]) if fila else ""
    if sql.count(VIEJO) != 1:
        raise ErrorDeDatos("La tabla parada no tiene el CHECK de tipos que espera la 014.")
    version = int(con.execute("PRAGMA schema_version").fetchone()[0])
    con.execute("PRAGMA writable_schema = ON")
    try:
        con.execute("UPDATE sqlite_master SET sql = ? WHERE type = 'table' AND name = 'parada'",
                    (sql.replace(VIEJO, NUEVO),))
        con.execute(f"PRAGMA schema_version = {version + 1}")
    finally:
        con.execute("PRAGMA writable_schema = OFF")
    if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ErrorDeDatos("La base no pasa integrity_check tras la migracion 014.")
