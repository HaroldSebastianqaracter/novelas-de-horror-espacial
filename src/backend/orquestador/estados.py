"""Maquina de estados de la ejecucion (RF-WK-05, RF-WK-06).

Las transiciones que no aparecen aqui no existen y se rechazan. Tenerlas en una tabla y no
repartidas por ifs es lo que permite comprobarlas de una vez, que es la forma barata de
verificar un invariante de orden.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from compartido.tipos import EstadoEjecucion

#: (estado de partida, suceso) -> estado de llegada
TRANSICIONES: dict[tuple[str, str], EstadoEjecucion] = {
    ("configurada", "arrancar"): "planificando",

    ("planificando", "puerta_1_ok"): "escaletando",
    ("escaletando", "puerta_2_ok"): "generando",

    ("planificando", "parar"): "detenida",
    ("escaletando", "parar"): "detenida",
    ("generando", "parar"): "detenida",

    ("detenida", "arrancar_planificacion"): "planificando",
    ("detenida", "arrancar_escaleta"): "escaletando",
    ("detenida", "arrancar_generacion"): "generando",
    ("error", "arrancar_planificacion"): "planificando",
    ("error", "arrancar_escaleta"): "escaletando",
    ("error", "arrancar_generacion"): "generando",

    ("planificando", "conflicto"): "parada",
    ("escaletando", "conflicto"): "parada",
    ("generando", "conflicto"): "parada",

    ("parada", "resolver"): "generando",

    ("generando", "terminado_limpio"): "completada",
    ("generando", "terminado_con_avisos"): "completada_con_avisos",

    ("planificando", "error"): "error",
    ("escaletando", "error"): "error",
    ("generando", "error"): "error",
    ("parada", "error"): "error",
}

#: `relanzar N` se admite desde cualquier estado salvo `configurada`.
ESTADOS_QUE_ADMITEN_RELANZAR = frozenset({
    "planificando", "escaletando", "generando", "parada", "detenida", "completada",
    "completada_con_avisos", "error",
})

ESTADOS_ACTIVOS = frozenset({"planificando", "escaletando", "generando"})


class TransicionInvalida(Exception):
    """Se pidio un cambio de estado que la maquina no contempla."""


@dataclass(frozen=True)
class Estado:
    estado: EstadoEjecucion
    fase: str | None = None
    capitulo_actual: int | None = None
    intento_actual: int = 1


def siguiente(desde: str, suceso: str) -> EstadoEjecucion:
    if suceso == "relanzar":
        if desde not in ESTADOS_QUE_ADMITEN_RELANZAR:
            raise TransicionInvalida(f"No se puede relanzar desde '{desde}'.")
        return "generando"
    destino = TRANSICIONES.get((desde, suceso))
    if destino is None:
        raise TransicionInvalida(f"No hay transicion de '{desde}' con el suceso '{suceso}'.")
    return destino


def transicion(
    con: sqlite3.Connection,
    novela_id: int,
    suceso: str,
    *,
    fase: str | None = None,
    capitulo: int | None = None,
    intento: int | None = None,
    error: str | None = None,
    parada_id: int | None = None,
) -> EstadoEjecucion:
    """Aplica una transicion sobre la fila `ejecucion`. Corre dentro de una transaccion."""
    fila = con.execute(
        "SELECT estado FROM ejecucion WHERE novela_id = ?", (novela_id,)
    ).fetchone()
    if fila is None:
        raise TransicionInvalida(f"La novela {novela_id} no tiene ejecucion.")

    destino = siguiente(str(fila["estado"]), suceso)
    con.execute(
        """
        UPDATE ejecucion
           SET estado = ?, fase = ?, capitulo_actual = COALESCE(?, capitulo_actual),
               intento_actual = COALESCE(?, intento_actual),
               ultimo_error = ?, parada_abierta_id = ?,
               actualizado_en = datetime('now')
         WHERE novela_id = ?
        """,
        (destino, fase, capitulo, intento, error, parada_id, novela_id),
    )
    return destino


def fijar_fase(
    con: sqlite3.Connection,
    novela_id: int,
    fase: str | None,
    *,
    capitulo: int | None = None,
    intento: int | None = None,
) -> None:
    """Mueve la fase sin cambiar de estado. Es lo que alimenta el progreso del frontend."""
    con.execute(
        """
        UPDATE ejecucion SET fase = ?, capitulo_actual = COALESCE(?, capitulo_actual),
               intento_actual = COALESCE(?, intento_actual), actualizado_en = datetime('now')
         WHERE novela_id = ?
        """,
        (fase, capitulo, intento, novela_id),
    )
