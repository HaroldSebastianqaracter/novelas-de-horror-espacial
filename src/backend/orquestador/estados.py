"""Maquina de estados de la ejecucion (RF-WK-05, RF2-WK-06).

Las transiciones que no aparecen aqui no existen y se rechazan. Tenerlas en una tabla y no
repartidas por ifs es lo que permite comprobarlas de una vez, que es la forma barata de
verificar un invariante de orden.

Desde `parada` la salida depende del TIPO de la parada abierta (RF2-FALLO-03): una parada de
estructura solo se resuelve rehaciendo la estructura, y relanzar capitulos sobre ella seria
saltarse la puerta 1.
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

    ("generando", "terminado_limpio"): "completada",
    ("generando", "terminado_con_avisos"): "completada_con_avisos",

    ("planificando", "error"): "error",
    ("escaletando", "error"): "error",
    ("generando", "error"): "error",
    ("parada", "error"): "error",
}

#: (tipo de la parada abierta, accion de resolver_parada) -> estado de llegada (RF2-FALLO-03).
#: `relanzar` directo sobre una parada tambien pasa por aqui.
RESOLUCIONES: dict[tuple[str, str], EstadoEjecucion] = {
    ("estructura", "rehacer"): "planificando",
    ("escaleta", "rehacer"): "escaletando",
    ("continuidad", "aceptar_retcon"): "generando",
    ("continuidad", "dar_por_sabido"): "generando",
    ("continuidad", "relanzar"): "generando",
    ("oficio", "relanzar"): "generando",
    ("presupuesto", "relanzar"): "generando",
}

ACCIONES_DE_PARADA = frozenset(accion for _, accion in RESOLUCIONES)

#: Desde donde se admite `relanzar N` fuera de una parada. Ademas hace falta que las puertas 1
#: y 2 esten vigentes, cosa que comprueba el worker (RF2-WK-06).
ESTADOS_QUE_ADMITEN_RELANZAR = frozenset({
    "detenida", "completada", "completada_con_avisos", "error",
})

#: `arrancar` solo tiene sentido si queda algo por hacer.
ESTADOS_QUE_ADMITEN_ARRANCAR = frozenset({"configurada", "detenida", "error"})

ESTADOS_ACTIVOS = frozenset({"planificando", "escaletando", "generando"})


def acciones_validas(tipo_parada: str) -> list[str]:
    return sorted(accion for tipo, accion in RESOLUCIONES if tipo == tipo_parada)


class TransicionInvalida(Exception):
    """Se pidio un cambio de estado que la maquina no contempla."""


@dataclass(frozen=True)
class Estado:
    estado: EstadoEjecucion
    fase: str | None = None
    capitulo_actual: int | None = None
    intento_actual: int = 1


def siguiente(desde: str, suceso: str, *, tipo_parada: str | None = None) -> EstadoEjecucion:
    if desde == "parada" and suceso in ACCIONES_DE_PARADA:
        destino = RESOLUCIONES.get((str(tipo_parada), suceso))
        if destino is None:
            validas = acciones_validas(str(tipo_parada))
            raise TransicionInvalida(
                f"Una parada de tipo '{tipo_parada}' no se resuelve con '{suceso}'. "
                f"Acciones validas: {', '.join(validas) or 'ninguna'}."
            )
        return destino
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
    tipo_parada: str | None = None,
) -> EstadoEjecucion:
    """Aplica una transicion sobre la fila `ejecucion`. Corre dentro de una transaccion."""
    fila = con.execute(
        "SELECT estado FROM ejecucion WHERE novela_id = ?", (novela_id,)
    ).fetchone()
    if fila is None:
        raise TransicionInvalida(f"La novela {novela_id} no tiene ejecucion.")

    destino = siguiente(str(fila["estado"]), suceso, tipo_parada=tipo_parada)
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
