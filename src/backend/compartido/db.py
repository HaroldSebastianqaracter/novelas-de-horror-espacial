"""Conexion, PRAGMAs, transacciones, migraciones e integridad del grafo.

Reglas que este modulo impone (RF-PER-01, RF-API-05, RF2-WK-08, RF2-PROC-03):
  * WAL, busy_timeout y foreign_keys en toda conexion.
  * La API abre en SOLO LECTURA; el worker es el unico escritor.
  * Una conexion puede llevar una guarda que corre dentro de cada `BEGIN IMMEDIATE`: es el
    fencing del worker, que comprueba que el cerrojo sigue siendo suyo antes de escribir.
  * El esquema base vive en esquema.sql; las migraciones incrementales, en migraciones/. Las
    dos se aplican con el cerrojo de escritura tomado y releyendo la version dentro.
"""

from __future__ import annotations

import importlib.util
import sqlite3
import time
from collections.abc import Callable, Collection, Generator, Sequence
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


Guardia = Callable[[sqlite3.Connection], None]


class Conexion(sqlite3.Connection):
    """Una conexion que puede llevar una guarda de escritura (RF2-WK-08).

    `sqlite3.Connection` no admite referencias debiles ni atributos nuevos, asi que la guarda
    viaja en una subclase. Toda conexion que abre `conectar` es de este tipo.
    """

    guardia: Guardia | None = None


def fijar_guardia(con: sqlite3.Connection, guardia: Guardia | None) -> None:
    """Hace que toda transaccion inmediata de `con` ejecute `guardia` nada mas empezar."""
    if not isinstance(con, Conexion):
        raise TypeError("Solo una conexion abierta con db.conectar admite guardia.")
    con.guardia = guardia


# -----------------------------------------------------------------------------------------
# Conexion
# -----------------------------------------------------------------------------------------


def _aplicar_pragmas(con: sqlite3.Connection, solo_lectura: bool) -> None:
    con.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    con.execute("PRAGMA foreign_keys = ON")
    if not solo_lectura:
        # journal_mode es persistente en el fichero; el lector no necesita fijarlo y en
        # modo=ro ni siquiera puede.
        _activar_wal(con)
        con.execute("PRAGMA synchronous = NORMAL")


def _activar_wal(con: sqlite3.Connection) -> None:
    """Pone la base en WAL, reintentando si otro proceso la tiene ocupada.

    Cambiar el modo de diario necesita un cerrojo exclusivo y SQLite no aplica ahi el
    busy_timeout: con varios procesos abriendo a la vez una base recien creada (la API y el
    worker arrancando juntos), uno recibia «database is locked». Como el modo es persistente,
    si otro ya lo puso no hace falta volver a pedirlo.
    """
    limite = time.monotonic() + BUSY_TIMEOUT_MS / 1000
    while True:
        try:
            if str(con.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal":
                return
            con.execute("PRAGMA journal_mode = WAL")
            return
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() or time.monotonic() > limite:
                raise
            time.sleep(0.05)


def conectar(
    ruta: Path, *, solo_lectura: bool = False, entre_hilos: bool = False
) -> sqlite3.Connection:
    """Abre la base de datos con los PRAGMAs de la spec.

    `solo_lectura=True` es lo que usa la API: cualquier escritura falla en el motor, no por
    disciplina del programador. `entre_hilos=True` deja abrir la conexion en un hilo y usarla o
    cerrarla en otro, como hace el threadpool de FastAPI con una dependencia (RF2-API-06); quien
    la pide responde de que no la usen dos hilos a la vez.
    """
    ruta = Path(ruta)
    if solo_lectura:
        if not ruta.exists():
            raise ErrorDeDatos(f"No existe la base de datos: {ruta}")
        uri = f"file:{ruta.as_posix()}?mode=ro"
        con = sqlite3.connect(
            uri, uri=True, timeout=BUSY_TIMEOUT_MS / 1000, isolation_level=None,
            factory=Conexion, check_same_thread=not entre_hilos,
        )
    else:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(
            ruta, timeout=BUSY_TIMEOUT_MS / 1000, isolation_level=None, factory=Conexion,
            check_same_thread=not entre_hilos,
        )

    con.row_factory = sqlite3.Row
    _aplicar_pragmas(con, solo_lectura)
    return con


@contextmanager
def transaccion(
    con: sqlite3.Connection,
    *,
    inmediata: bool = True,
    al_empezar: Guardia | None = None,
) -> Generator[sqlite3.Connection]:
    """Transaccion explicita. Confirma al salir sin excepcion, revierte si la hay.

    `inmediata` toma el bloqueo de escritura al empezar, que es lo que quiere el worker: si
    otro proceso esta escribiendo, se entera ya y no a mitad del capitulo.

    `al_empezar` corre justo despues de `BEGIN IMMEDIATE`, con el cerrojo de escritura de
    SQLite ya tomado; si no se pasa, se usa la guarda de la conexion. Es el fencing del worker
    (RF2-WK-08): si lanza, la transaccion se revierte sin haber escrito nada. En una
    transaccion diferida no corre, porque sin el cerrojo tomado la comprobacion no protege.
    """
    con.execute("BEGIN IMMEDIATE" if inmediata else "BEGIN")
    try:
        guardia = al_empezar or getattr(con, "guardia", None)
        if inmediata and guardia is not None:
            guardia(con)
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


@dataclass(frozen=True)
class Migracion:
    """Una version del esquema: su guion SQL, su paso en Python, o los dos.

    Los dos ficheros de un mismo numero (`002_x.sql` y `002_x.py`) se aplican en la misma
    transaccion, primero el SQL. El `.py` define `aplicar(con)`: es lo que hace falta cuando
    una migracion tiene que calcular algo en Python, como las claves normalizadas.
    """

    numero: int
    sql: Path | None = None
    python: Path | None = None


def _migraciones() -> list[Migracion]:
    if not DIR_MIGRACIONES.exists():
        return []
    por_numero: dict[int, dict[str, Path]] = {}
    for fichero in sorted(DIR_MIGRACIONES.iterdir()):
        cabeza = fichero.name.split("_", 1)[0]
        if not cabeza.isdigit() or fichero.suffix not in (".sql", ".py"):
            continue
        por_numero.setdefault(int(cabeza), {})[fichero.suffix] = fichero
    return [
        Migracion(numero=n, sql=f.get(".sql"), python=f.get(".py"))
        for n, f in sorted(por_numero.items())
    ]


def _migraciones_pendientes(desde: int) -> list[Migracion]:
    return [m for m in _migraciones() if m.numero > desde]


def version_objetivo() -> int:
    """La version a la que llega el esquema con todas las migraciones aplicadas."""
    return max([VERSION_ESQUEMA, *(m.numero for m in _migraciones())])


def _paso_python(ruta: Path) -> Callable[[sqlite3.Connection], None]:
    spec = importlib.util.spec_from_file_location(f"migracion_{ruta.stem}", ruta)
    if spec is None or spec.loader is None:
        raise ErrorDeDatos(f"No se puede cargar la migracion {ruta.name}")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    aplicar = getattr(modulo, "aplicar", None)
    if not callable(aplicar):
        raise ErrorDeDatos(f"La migracion {ruta.name} no define aplicar(con).")
    return aplicar  # type: ignore[no-any-return]


def sentencias(sql: str) -> list[str]:
    """Parte un guion SQL en sentencias completas, en el orden en que aparecen.

    Hace falta porque `executescript` confirma cualquier transaccion abierta antes de empezar
    y el esquema tiene que aplicarse DENTRO de un `BEGIN IMMEDIATE` propio. Se apoya en
    `sqlite3.complete_statement`, que sabe de comentarios, cadenas y cuerpos de trigger.
    """
    salida: list[str] = []
    buffer = ""
    for linea in sql.splitlines(keepends=True):
        buffer += linea
        if sqlite3.complete_statement(buffer):
            salida.append(buffer.strip())
            buffer = ""
    if buffer.strip() and not all(
        not x.strip() or x.strip().startswith("--") for x in buffer.splitlines()
    ):
        raise ErrorDeDatos(f"Sentencia SQL incompleta al final del guion: {buffer[:200]!r}")
    return salida


def _aplicar_version(
    con: sqlite3.Connection,
    version: int,
    sql: str,
    paso: Callable[[sqlite3.Connection], None] | None = None,
) -> bool:
    """Aplica un guion y sella su version, todo o nada. Devuelve si lo aplico.

    Toma el cerrojo de escritura (`BEGIN IMMEDIATE`) y vuelve a leer la version DENTRO de la
    transaccion: si otro proceso ya la aplico mientras este esperaba, no hace nada. Es lo que
    cierra la carrera entre leer la version y migrar (RF2-PROC-03).
    """
    con.execute("BEGIN IMMEDIATE")
    try:
        if version_actual(con) >= version:
            con.execute("ROLLBACK")
            return False
        for sentencia in sentencias(sql):
            con.execute(sentencia)
        if paso is not None:
            paso(con)
        con.execute(
            "INSERT OR REPLACE INTO esquema_version (version) VALUES (?)", (version,)
        )
    except BaseException:
        con.execute("ROLLBACK")
        raise
    con.execute("COMMIT")
    return True


def crear_esquema(con: sqlite3.Connection) -> bool:
    """Lleva una base VACIA a la version actual. Idempotente y segura entre procesos.

    Una base nueva nace completa: esquema base y todas las migraciones. Es la unica escritura
    que el worker hace antes de tomar su cerrojo, porque la tabla del cerrojo vive en el
    esquema; y la unica que se le permite a la API (RF2-PROC-03). Una base que ya existe no se
    toca aqui: la migra el worker.
    """
    if version_actual(con) > 0:
        return False
    creada = _aplicar_version(con, VERSION_ESQUEMA, RUTA_ESQUEMA.read_text(encoding="utf-8"))
    if creada:
        _aplicar_migraciones(con)
    return creada


def _aplicar_migraciones(con: sqlite3.Connection) -> list[int]:
    aplicadas: list[int] = []
    for m in _migraciones_pendientes(version_actual(con)):
        sql = m.sql.read_text(encoding="utf-8") if m.sql else ""
        paso = _paso_python(m.python) if m.python else None
        if _aplicar_version(con, m.numero, sql, paso):
            aplicadas.append(m.numero)
    return aplicadas


def migrar(con: sqlite3.Connection) -> list[int]:
    """Aplica en orden las migraciones pendientes. Devuelve las que aplico este proceso."""
    if version_actual(con) == 0:
        crear_esquema(con)
        return []
    return _aplicar_migraciones(con)


def preparar(ruta: Path) -> sqlite3.Connection:
    """Abre la base creandola si hace falta y deja el esquema al dia.

    Comodidad para los tests y el lanzador. El worker no la usa: crea el esquema, toma el
    cerrojo y solo entonces migra (RF2-PROC-03).
    """
    con = conectar(ruta)
    crear_esquema(con)
    migrar(con)
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
        "uso_antes_del_hecho",
        "Ningun uso de un hecho precede a la escena que lo establece (RF3-BIB-14)",
        """
        SELECT u.id AS hecho_uso_id, u.hecho_id, u.via
        FROM hecho_uso u
        JOIN hecho h           ON h.id = u.hecho_id
        JOIN escena_ordinal ou ON ou.escena_id = u.escena_id
        JOIN escena_ordinal oh ON oh.escena_id = h.escena_id
        WHERE ou.ordinal <= oh.ordinal
        """,
    ),
    (
        "version_desfasada",
        "Una novela completada tiene version, y la ultima tiene exactamente sus capitulos "
        "vigentes, su titulo y su dedicatoria (RF3-BIB-14)",
        """
        WITH ultima AS (
          SELECT v.novela_id, v.id, v.titulo, v.dedicatoria FROM novela_version v
          WHERE v.numero = (SELECT MAX(v2.numero) FROM novela_version v2
                            WHERE v2.novela_id = v.novela_id)
        ),
        vigente AS (
          SELECT c.novela_id, c.numero, cc.texto FROM capitulo c
          JOIN capitulo_compilado cc ON cc.capitulo_id = c.id AND cc.estado = 'vigente'
        )
        SELECT x.novela_id
        FROM ejecucion x
        JOIN novela n ON n.id = x.novela_id
        LEFT JOIN ultima u ON u.novela_id = x.novela_id
        WHERE x.estado IN ('completada', 'completada_con_avisos')
          AND (
            u.id IS NULL
            OR u.titulo IS NOT n.titulo OR u.dedicatoria IS NOT n.dedicatoria
            OR EXISTS (
              SELECT 1 FROM vigente g WHERE g.novela_id = x.novela_id
                AND NOT EXISTS (SELECT 1 FROM novela_version_capitulo vc
                                WHERE vc.version_id = u.id AND vc.numero = g.numero
                                  AND vc.texto = g.texto))
            OR EXISTS (
              SELECT 1 FROM novela_version_capitulo vc WHERE vc.version_id = u.id
                AND NOT EXISTS (SELECT 1 FROM vigente g
                                WHERE g.novela_id = x.novela_id AND g.numero = vc.numero)))
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
    "hecho", "estado_conocimiento", "uso_conocimiento", "hecho_uso", "estado_personaje",
    "estado_objeto", "siembra_estado", "hilo_estado", "amenaza_revelacion",
    "entidad_no_reconocida", "atributo_conducta", "presencia_escena",
)

#: Las tablas de estado que cuelgan de un hecho: al revertir, caen tambien las filas de
#: escenas anteriores que apuntan a un hecho que desaparece.
TABLAS_QUE_CUELGAN_DE_UN_HECHO: tuple[str, ...] = (
    "estado_conocimiento", "uso_conocimiento", "hecho_uso",
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
