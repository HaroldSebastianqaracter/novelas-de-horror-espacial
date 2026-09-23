"""Vigencia de las puertas de planificacion (RF2-PIPE-00).

`avanzar` no decide que toca por el estado de `ejecucion`, que puede mentir tras una parada o
una caida: lo deriva del grafo. Y la pregunta central de esa derivacion es si una puerta esta
**vigente**, es decir, si su ultimo veredicto no fue `falla` y juzgo exactamente lo que hay
ahora.

«Exactamente lo que hay ahora» se comprueba con una huella: el registro de la puerta guarda un
SHA-256 de las filas que la puerta lee, y la puerta esta vigente solo si esa huella coincide con
la del grafo actual. Se descartaron las marcas de tiempo (`datetime('now')` tiene resolucion de
segundo y no ordena dos escrituras del mismo segundo) y los ids (los de tablas distintas no son
comparables).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any

#: Lo que lee cada puerta, fila a fila y en orden estable. Cambiar cualquiera de estas filas
#: deja la puerta sin vigencia; cambiar otra cosa, no.
_LECTURAS: dict[int, tuple[str, ...]] = {
    1: (
        "SELECT id, numero, funcion_narrativa FROM acto WHERE novela_id = :n ORDER BY id",
        "SELECT id, tipo, conflicto_central FROM hilo WHERE novela_id = :n ORDER BY id",
        "SELECT g.id, g.hilo_id, g.tipo, g.posicion FROM punto_de_giro g "
        "JOIN hilo h ON h.id = g.hilo_id WHERE h.novela_id = :n ORDER BY g.id",
        "SELECT id, rol_narrativo, tipo_arco FROM personaje WHERE novela_id = :n ORDER BY id",
        "SELECT subgenero_dominante, tipo_final FROM novela WHERE id = :n",
    ),
    2: (
        "SELECT id, numero FROM acto WHERE novela_id = :n ORDER BY id",
        # Sin estado ni resumenes: cambian al escribir la prosa, no al replanificar.
        "SELECT id, acto_id, numero, objetivo, pov_id, gancho_apertura, gancho_cierre, "
        "longitud_prevista FROM capitulo WHERE novela_id = :n ORDER BY id",
        "SELECT id, acto_id, objetivo_intermedio, orden FROM secuencia "
        "WHERE novela_id = :n ORDER BY id",
        "SELECT * FROM escena WHERE novela_id = :n ORDER BY id",
        "SELECT ep.escena_id, ep.personaje_id FROM escena_personaje ep "
        "JOIN escena e ON e.id = ep.escena_id WHERE e.novela_id = :n ORDER BY ep.id",
        "SELECT tipo, valor FROM restriccion WHERE novela_id = :n ORDER BY tipo",
    ),
}

PUERTAS_CON_VIGENCIA = frozenset(_LECTURAS)


def huella(con: sqlite3.Connection, novela_id: int, puerta: int) -> str | None:
    """SHA-256 de lo que la puerta lee. None para las puertas que no la necesitan."""
    consultas = _LECTURAS.get(puerta)
    if consultas is None:
        return None
    filas: list[list[Any]] = []
    for sql in consultas:
        filas.extend([list(f) for f in con.execute(sql, {"n": novela_id}).fetchall()])
        filas.append(["--"])  # separa tablas: dos tablas vacias no valen lo mismo que una
    bruto = json.dumps(filas, ensure_ascii=False, default=str, separators=(",", ":"))
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


def _ultimo_registro(
    con: sqlite3.Connection, novela_id: int, puerta: int
) -> sqlite3.Row | None:
    return con.execute(
        "SELECT veredicto, detalle FROM resultado_puerta WHERE novela_id = ? AND puerta = ? "
        "ORDER BY id DESC LIMIT 1",
        (novela_id, puerta),
    ).fetchone()


def _detalle(fila: sqlite3.Row) -> dict[str, Any]:
    try:
        cargado = json.loads(fila["detalle"] or "{}")
    except json.JSONDecodeError:
        return {}
    return cargado if isinstance(cargado, dict) else {}


def puerta_vigente(con: sqlite3.Connection, novela_id: int, puerta: int) -> bool:
    """Su ultimo veredicto no es `falla` y juzgo el grafo tal como esta ahora."""
    fila = _ultimo_registro(con, novela_id, puerta)
    if fila is None or str(fila["veredicto"]) == "falla":
        return False
    return _detalle(fila).get("huella") == huella(con, novela_id, puerta)


def informe_de_rechazo(con: sqlite3.Connection, novela_id: int, puerta: int) -> list[str]:
    """Los conflictos del ultimo veredicto de la puerta, si fue `falla`.

    Es lo que recibe el agente que rehace la fase. Se lee de `resultado_puerta` y no de
    memoria, para que sobreviva a un reinicio del worker entre el fallo y el nuevo intento.
    """
    fila = _ultimo_registro(con, novela_id, puerta)
    if fila is None or str(fila["veredicto"]) != "falla":
        return []
    salida: list[str] = []
    for c in _detalle(fila).get("conflictos", []):
        if isinstance(c, dict) and not c.get("aviso"):
            salida.append(f"[{c.get('comprobacion', '')}] {c.get('descripcion', '')}")
    return salida
