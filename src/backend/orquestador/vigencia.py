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

from compartido.tipos import como_dict, como_lista

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

#: Lo que ademas leen las puertas cuando la novela es un regalo (spec3, RF3-PER-07). Va aparte
#: y solo cuenta si hay brief: asi la huella de una novela sin personalizar es exactamente la de
#: antes, y ninguna novela ya generada pierde la vigencia de sus puertas al migrar.
_LECTURAS_DEL_ENCARGO: dict[int, tuple[str, ...]] = {
    1: (
        "SELECT contenido FROM brief WHERE novela_id = :n",
        "SELECT id, nombre_clave FROM personaje WHERE novela_id = :n ORDER BY id",
        "SELECT dedicatoria FROM novela WHERE id = :n",
    ),
    2: (
        "SELECT contenido FROM brief WHERE novela_id = :n",
        # El POV del destinatario se busca por su nombre: la puerta 2 tambien lee el elenco.
        "SELECT id, nombre_clave FROM personaje WHERE novela_id = :n ORDER BY id",
        "SELECT id, codigo, obligatorio FROM elemento_personal WHERE novela_id = :n ORDER BY id",
        "SELECT ee.escena_id, ee.elemento_id FROM escena_elemento ee "
        "JOIN escena e ON e.id = ee.escena_id WHERE e.novela_id = :n ORDER BY ee.id",
    ),
}

#: La edad de los personajes, por `edad_del_destinatario` (spec3, RF3-BIB-06). Solo cuenta si la
#: novela tiene brief Y edades: una novela con brief anterior al bloque 3 no tiene ninguna, y
#: su huella tiene que seguir siendo la que registro su puerta 1, o perderia la vigencia al
#: migrar y quedaria atascada.
_LECTURAS_DE_EDAD: dict[int, tuple[str, ...]] = {
    1: ("SELECT id, edad FROM personaje WHERE novela_id = :n ORDER BY id",),
}

PUERTAS_CON_VIGENCIA = frozenset(_LECTURAS)


def huella(con: sqlite3.Connection, novela_id: int, puerta: int) -> str | None:
    """SHA-256 de lo que la puerta lee. None para las puertas que no la necesitan."""
    consultas = _LECTURAS.get(puerta)
    if consultas is None:
        return None
    if con.execute("SELECT 1 FROM brief WHERE novela_id = ?", (novela_id,)).fetchone():
        consultas = (*consultas, *_LECTURAS_DEL_ENCARGO.get(puerta, ()))
        if con.execute(
            "SELECT 1 FROM personaje WHERE novela_id = ? AND edad IS NOT NULL", (novela_id,)
        ).fetchone():
            consultas = (*consultas, *_LECTURAS_DE_EDAD.get(puerta, ()))
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
    return como_dict(cargado)


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
    for c in map(como_dict, como_lista(_detalle(fila).get("conflictos"))):
        if c and not c.get("aviso"):
            salida.append(f"[{c.get('comprobacion', '')}] {c.get('descripcion', '')}")
    return salida
