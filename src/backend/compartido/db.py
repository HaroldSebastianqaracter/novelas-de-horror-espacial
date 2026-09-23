"""Conexion, PRAGMAs, transacciones, migraciones e integridad del grafo.

Reglas que este modulo impone (RF-PER-01, RF-API-05):
  * WAL, busy_timeout y foreign_keys en toda conexion.
  * La API abre en SOLO LECTURA; el worker es el unico escritor.
  * El esquema base vive en esquema.sql; las migraciones incrementales, en migraciones/.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Collection, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

VERSION_ESQUEMA = 1

_AQUI = Path(__file__).resolve().parent
RUTA_ESQUEMA = _AQUI / "esquema.sql"
DIR_MIGRACIONES = _AQUI / "migraciones"

BUSY_TIMEOUT_MS = 5_000


class ErrorDeDatos(Exception):
    """Fallo de persistencia que el llamante debe tratar."""


class EscrituraEnSoloLectura(ErrorDeDatos):
    """Se intento escribir por una conexion de solo lectura."""


# -----------------------------------------------------------------------------------------
# Conexion
# -----------------------------------------------------------------------------------------


def _aplicar_pragmas(con: sqlite3.Connection, solo_lectura: bool) -> None:
    con.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    con.execute("PRAGMA foreign_keys = ON")
    if not solo_lectura:
        # journal_mode es persistente en el fichero; el lector no necesita fijarlo y en
        # modo=ro ni siquiera puede.
        con.execute("PRAGMA journal_mode = WAL")
        con.execute("PRAGMA synchronous = NORMAL")


def conectar(ruta: Path, *, solo_lectura: bool = False) -> sqlite3.Connection:
    """Abre la base de datos con los PRAGMAs de la spec.

    `solo_lectura=True` es lo que usa la API: cualquier escritura falla en el motor, no por
    disciplina del programador.
    """
    ruta = Path(ruta)
    if solo_lectura:
        if not ruta.exists():
            raise ErrorDeDatos(f"No existe la base de datos: {ruta}")
        uri = f"file:{ruta.as_posix()}?mode=ro"
        con = sqlite3.connect(uri, uri=True, timeout=BUSY_TIMEOUT_MS / 1000, isolation_level=None)
    else:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(ruta, timeout=BUSY_TIMEOUT_MS / 1000, isolation_level=None)

    con.row_factory = sqlite3.Row
    _aplicar_pragmas(con, solo_lectura)
    return con


@contextmanager
def transaccion(con: sqlite3.Connection, *, inmediata: bool = True) -> Iterator[sqlite3.Connection]:
    """Transaccion explicita. Confirma al salir sin excepcion, revierte si la hay.

    `inmediata` toma el bloqueo de escritura al empezar, que es lo que quiere el worker: si
    otro proceso esta escribiendo, se entera ya y no a mitad del capitulo.

    Es la pieza de RF-PIPE-08: todo el capitulo entra en una sola transaccion o no entra nada.
    """
    con.execute("BEGIN IMMEDIATE" if inmediata else "BEGIN")
    try:
        yield con
    except BaseException:
        con.execute("ROLLBACK")
        raise
    else:
        con.execute("COMMIT")


def uno(con: sqlite3.Connection, sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
    return con.execute(sql, params).fetchone()


def todos(con: sqlite3.Connection, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
    return list(con.execute(sql, params).fetchall())


def escalar(con: sqlite3.Connection, sql: str, params: Sequence[Any] = ()) -> Any:
    fila = con.execute(sql, params).fetchone()
    return None if fila is None else fila[0]


# -----------------------------------------------------------------------------------------
# Esquema y migraciones (RF-PROC-03, RF-PER-04)
# -----------------------------------------------------------------------------------------


def version_actual(con: sqlite3.Connection) -> int:
    fila = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='esquema_version'"
    ).fetchone()
    if fila is None:
        return 0
    valor = escalar(con, "SELECT MAX(version) FROM esquema_version")
    return int(valor) if valor is not None else 0


def _migraciones_pendientes(desde: int) -> list[tuple[int, Path]]:
    if not DIR_MIGRACIONES.exists():
        return []
    encontradas: list[tuple[int, Path]] = []
    for fichero in sorted(DIR_MIGRACIONES.glob("*.sql")):
        cabeza = fichero.name.split("_", 1)[0]
        if not cabeza.isdigit():
            continue
        numero = int(cabeza)
        if numero > desde:
            encontradas.append((numero, fichero))
    return sorted(encontradas)


def _script_atomico(con: sqlite3.Connection, sql: str, version: int) -> None:
    """Ejecuta un script DDL y sella su version, todo o nada.

    `executescript` confirma cualquier transaccion pendiente antes de arrancar y no abre
    ninguna por su cuenta, asi que el control de transaccion tiene que ir DENTRO del script.
    """
    sello = f"INSERT OR REPLACE INTO esquema_version (version) VALUES ({version});"
    guion = f"BEGIN;\n{sql}\n{sello}\nCOMMIT;"
    try:
        con.executescript(guion)
    except Exception:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise


def preparar(ruta: Path) -> sqlite3.Connection:
    """Abre la base creandola si hace falta y deja el esquema al dia.

    Es lo que llaman API y worker al arrancar (RF-PROC-03).
    """
    con = conectar(ruta)
    actual = version_actual(con)

    if actual == 0:
        _script_atomico(con, RUTA_ESQUEMA.read_text(encoding="utf-8"), VERSION_ESQUEMA)
        actual = VERSION_ESQUEMA

    for numero, fichero in _migraciones_pendientes(actual):
        _script_atomico(con, fichero.read_text(encoding="utf-8"), numero)

    return con


# -----------------------------------------------------------------------------------------
# Integridad del grafo (RF-PER-07)
# -----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Violacion:
    """Una regla del grafo que no se cumple, con las filas concretas que la rompen."""

    regla: str
    descripcion: str
    filas: list[dict[str, Any]]

    def __str__(self) -> str:
        return f"{self.regla}: {self.descripcion} ({len(self.filas)} filas)"


_COMPROBACIONES: tuple[tuple[str, str, str], ...] = (
    (
        "hecho_sin_escena",
        "Todo hecho tiene una escena de origen existente",
        """
        SELECT h.id AS hecho_id, h.escena_id
        FROM hecho h
        LEFT JOIN escena e ON e.id = h.escena_id
        WHERE e.id IS NULL
        """,
    ),
    (
        "pago_antes_de_siembra",
        "Toda siembra pagada se paga en una escena posterior a la de siembra",
        """
        SELECT se.id AS siembra_estado_id, se.siembra_id,
               oe.ordinal AS ordinal_pago, os.ordinal AS ordinal_siembra
        FROM siembra_estado se
        JOIN siembra s        ON s.id = se.siembra_id
        JOIN escena_ordinal oe ON oe.escena_id = se.escena_id
        JOIN escena_ordinal os ON os.escena_id = s.sembrada_en_escena_id
        WHERE se.estado = 'pagada' AND oe.ordinal <= os.ordinal
        """,
    ),
    (
        "conocimiento_antes_del_hecho",
        "Ningun estado de conocimiento precede a la escena que establece su hecho",
        """
        SELECT ec.id AS estado_conocimiento_id, ec.personaje_id, ec.hecho_id,
               oc.ordinal AS ordinal_conocimiento, oh.ordinal AS ordinal_hecho
        FROM estado_conocimiento ec
        JOIN hecho h           ON h.id = ec.hecho_id
        JOIN escena_ordinal oc ON oc.escena_id = ec.escena_id
        JOIN escena_ordinal oh ON oh.escena_id = h.escena_id
        WHERE oc.ordinal < oh.ordinal
        """,
    ),
    (
        "capitulo_completado_sin_texto",
        "Ningun capitulo completado carece de compilado vigente",
        """
        SELECT c.id AS capitulo_id, c.numero
        FROM capitulo c
        WHERE c.estado = 'completado'
          AND NOT EXISTS (SELECT 1 FROM capitulo_compilado cc
                          WHERE cc.capitulo_id = c.id AND cc.estado = 'vigente')
        """,
    ),
    (
        "texto_vigente_sin_capitulo_completado",
        "Ningun compilado vigente pertenece a un capitulo no completado",
        """
        SELECT cc.id AS capitulo_compilado_id, cc.capitulo_id
        FROM capitulo_compilado cc
        JOIN capitulo c ON c.id = cc.capitulo_id
        WHERE cc.estado = 'vigente' AND c.estado <> 'completado'
        """,
    ),
    (
        "uso_sin_hecho_previo",
        "Ningun uso de conocimiento precede a la escena que establece su hecho",
        """
        SELECT u.id AS uso_id, u.personaje_id, u.hecho_id
        FROM uso_conocimiento u
        JOIN hecho h           ON h.id = u.hecho_id
        JOIN escena_ordinal ou ON ou.escena_id = u.escena_id
        JOIN escena_ordinal oh ON oh.escena_id = h.escena_id
        WHERE ou.ordinal < oh.ordinal
        """,
    ),
    (
        "escena_texto_multiple_vigente",
        "Cada escena tiene como mucho una version de texto vigente",
        """
        SELECT escena_id, COUNT(*) AS vigentes
        FROM escena_texto
        WHERE estado = 'vigente'
        GROUP BY escena_id
        HAVING COUNT(*) > 1
        """,
    ),
)


#: Tablas de ESTADO: append-only y con escena de origen (RF-PER-06). Revertir un capitulo es
#: borrar sus filas de aqui; `evento` va aparte porque su escena admite NULL (los antecedentes
#: del mundo y los retcon no ocurren en ninguna escena).
TABLAS_DE_ESTADO: tuple[str, ...] = (
    "hecho", "estado_conocimiento", "uso_conocimiento", "estado_personaje", "estado_objeto",
    "siembra_estado", "hilo_estado", "amenaza_revelacion", "entidad_no_reconocida",
)

ESTADOS_ACTIVOS: tuple[str, ...] = ("planificando", "escaletando", "generando")


def _sql_estado_en_capitulo_no_completado() -> str:
    partes = [
        f"SELECT '{tabla}' AS tabla, x.id AS fila_id, ea.novela_id, ea.capitulo "
        f"FROM {tabla} x JOIN escena_abierta ea ON ea.escena_id = x.escena_id"
        for tabla in (*TABLAS_DE_ESTADO, "evento")
    ]
    partes.append(
        "SELECT 'escena_texto' AS tabla, x.id AS fila_id, ea.novela_id, ea.capitulo "
        "FROM escena_texto x JOIN escena_abierta ea ON ea.escena_id = x.escena_id "
        "WHERE x.estado = 'vigente'"
    )
    return (
        "WITH escena_abierta AS (SELECT e.id AS escena_id, e.novela_id, c.numero AS capitulo "
        "FROM escena e JOIN capitulo c ON c.id = e.capitulo_id WHERE c.estado <> 'completado') "
        + " UNION ALL ".join(partes)
    )


def novelas_activas(con: sqlite3.Connection) -> set[int]:
    return {
        int(f["novela_id"]) for f in con.execute(
            f"SELECT novela_id FROM ejecucion WHERE estado IN "
            f"({','.join('?' * len(ESTADOS_ACTIVOS))})",
            ESTADOS_ACTIVOS,
        )
    }


def verificar_integridad(
    con: sqlite3.Connection, *, activas: Collection[int] | None = None
) -> list[Violacion]:
    """Devuelve las violaciones de los invariantes del grafo. Lista vacia = grafo integro.

    La usan la recuperacion del worker caido (RF2-FALLO-06) y los tests de propiedades.

    `activas` son las novelas cuya ejecucion esta en marcha: en ellas un capitulo con texto y
    hechos sin completar es el estado intermedio legitimo del tramo 2, no una violacion
    (RF2-PER-07). Si no se dice, se lee de la tabla `ejecucion`.
    """
    violaciones: list[Violacion] = []
    for regla, descripcion, sql in _COMPROBACIONES:
        filas = [dict(f) for f in con.execute(sql).fetchall()]
        if filas:
            violaciones.append(Violacion(regla=regla, descripcion=descripcion, filas=filas))

    en_marcha = set(activas) if activas is not None else novelas_activas(con)
    a_medias = [
        dict(f) for f in con.execute(_sql_estado_en_capitulo_no_completado()).fetchall()
        if int(f["novela_id"]) not in en_marcha
    ]
    if a_medias:
        violaciones.append(Violacion(
            regla="estado_en_capitulo_no_completado",
            descripcion=(
                "Ningun texto vigente ni ninguna fila de estado pertenece a un capitulo no "
                "completado de una novela sin ejecucion activa"
            ),
            filas=a_medias,
        ))

    fk_rotas = [dict(f) for f in con.execute("PRAGMA foreign_key_check").fetchall()]
    if fk_rotas:
        violaciones.append(
            Violacion(
                regla="clave_ajena_rota",
                descripcion="Hay claves ajenas que apuntan a filas inexistentes",
                filas=fk_rotas,
            )
        )
    return violaciones
