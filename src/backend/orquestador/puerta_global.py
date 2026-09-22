"""Puerta 5, parte determinista y no bloqueante (RF-PIPE-15).

Corre sobre el manuscrito completo y produce un informe. No para nada: llegado aqui, el
manuscrito existe, y lo que esta puerta encuentra son cosas que se arreglan revisando, no
regenerando.

Las otras dos mitades de la puerta 5 quedan fuera de la v1 y estan declaradas como riesgo
aceptado: que la prosa respete las reglas de la amenaza de principio a fin exige interpretar
el texto, y la curva de tension solo se manifiesta en lectura seguida.
"""

from __future__ import annotations

import sqlite3

from compartido.puerta_base import Conflicto, ResultadoPuerta
from config import UMBRAL_HILO_LATENTE


def evaluar(con: sqlite3.Connection, novela_id: int) -> ResultadoPuerta:
    conflictos: list[Conflicto] = []

    for f in con.execute(
        """
        SELECT elemento, estado FROM siembra_vigente
        WHERE novela_id = ? AND estado NOT IN ('pagada','abandonada')
        """,
        (novela_id,),
    ):
        conflictos.append(Conflicto(
            comprobacion="siembra_sin_pagar", aviso=True,
            descripcion=(
                f"«{f['elemento']}» se quedo en «{f['estado']}». Todo lo que se destaca debe "
                "usarse: una siembra sin pagar es una promesa rota al lector."
            ),
            datos=dict(f),
        ))

    for f in con.execute(
        """
        SELECT conflicto_central, estado, tipo FROM hilo_vigente
        WHERE novela_id = ? AND estado NOT IN ('resuelto','abierto_deliberado')
        """,
        (novela_id,),
    ):
        conflictos.append(Conflicto(
            comprobacion="hilo_sin_cerrar", aviso=True,
            descripcion=(
                f"El hilo [{f['tipo']}] «{f['conflicto_central'][:70]}» termina la novela en "
                f"«{f['estado']}». Un hilo que nunca sale de abierto es la causa habitual de un "
                "final insatisfactorio."
            ),
            datos=dict(f),
        ))

    # Un hilo latente demasiado tiempo se olvida (principio 14).
    for f in con.execute(
        """
        SELECT h.conflicto_central,
               MIN(eo.capitulo_numero) AS desde, MAX(eo.capitulo_numero) AS hasta
        FROM hilo_estado he
        JOIN hilo h            ON h.id = he.hilo_id
        JOIN escena_ordinal eo ON eo.escena_id = he.escena_id
        WHERE he.novela_id = ? AND he.estado = 'latente'
        GROUP BY h.id
        HAVING (MAX(eo.capitulo_numero) - MIN(eo.capitulo_numero)) >= ?
        """,
        (novela_id, UMBRAL_HILO_LATENTE),
    ):
        conflictos.append(Conflicto(
            comprobacion="hilo_latente_demasiado_tiempo", aviso=True,
            descripcion=(
                f"«{f['conflicto_central'][:70]}» estuvo latente entre los capitulos "
                f"{f['desde']} y {f['hasta']}. El lector lo habra olvidado."
            ),
            datos=dict(f),
        ))

    return ResultadoPuerta(puerta=5, conflictos=conflictos)
