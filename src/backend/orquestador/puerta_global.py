"""Puerta 5, parte determinista y no bloqueante (RF-PIPE-15, RF2-PIPE-15).

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

    conflictos.extend(_latentes(con, novela_id))
    conflictos.extend(_pagos_sin_siembra(con, novela_id))
    conflictos.extend(_cierres_fuera_de_orden(con, novela_id))

    return ResultadoPuerta(puerta=5, conflictos=conflictos)


def _latentes(con: sqlite3.Connection, novela_id: int) -> list[Conflicto]:
    """Un hilo latente demasiado tiempo se olvida (principio 14).

    Se mide el TRAMO CONTINUO en latente: desde que entra hasta el siguiente estado que no lo
    es, o hasta el final de la novela. Medir la distancia entre el primer y el ultimo registro
    latente sumaba tramos separados por capitulos en que el hilo estaba vivo (RF2-PIPE-15).
    """
    ultimo = con.execute(
        "SELECT COALESCE(MAX(numero), 0) FROM capitulo WHERE novela_id = ?", (novela_id,)
    ).fetchone()[0]
    filas = con.execute(
        """
        SELECT he.hilo_id, h.conflicto_central, he.estado, eo.capitulo_numero AS capitulo
        FROM hilo_estado he
        JOIN hilo h            ON h.id = he.hilo_id
        JOIN escena_ordinal eo ON eo.escena_id = he.escena_id
        WHERE he.novela_id = ?
        ORDER BY he.hilo_id, eo.ordinal, he.id
        """,
        (novela_id,),
    ).fetchall()

    avisos: list[Conflicto] = []
    tramos: dict[int, tuple[str, int]] = {}  # hilo -> (conflicto, capitulo en que entro)

    def cerrar(hilo: int, hasta: int) -> None:
        conflicto, desde = tramos.pop(hilo)
        if hasta - desde >= UMBRAL_HILO_LATENTE:
            avisos.append(Conflicto(
                comprobacion="hilo_latente_demasiado_tiempo", aviso=True,
                descripcion=(
                    f"«{conflicto[:70]}» estuvo latente {hasta - desde} capitulos seguidos, "
                    f"desde el {desde}. El lector lo habra olvidado."
                ),
                datos={"desde": desde, "hasta": hasta - 1, "capitulos": hasta - desde},
            ))

    for f in filas:
        hilo = int(f["hilo_id"])
        if f["estado"] == "latente":
            tramos.setdefault(hilo, (str(f["conflicto_central"]), int(f["capitulo"])))
        elif hilo in tramos:
            cerrar(hilo, int(f["capitulo"]))
    for hilo in list(tramos):
        cerrar(hilo, int(ultimo) + 1)
    return avisos


def _pagos_sin_siembra(con: sqlite3.Connection, novela_id: int) -> list[Conflicto]:
    """Nada debe resolverse con material que no se haya anunciado (principio 16)."""
    return [
        Conflicto(
            comprobacion="pago_sin_siembra", aviso=True,
            descripcion=(
                f"«{f['elemento']}» se paga en el capitulo {f['capitulo']} y nunca se registro "
                "plantado: el lector recibe una solucion que no se le anuncio."
            ),
            datos=dict(f),
        )
        for f in con.execute(
            """
            SELECT DISTINCT s.id AS siembra_id, s.elemento, eo.capitulo_numero AS capitulo
            FROM siembra s
            JOIN siembra_estado se ON se.siembra_id = s.id AND se.estado = 'pagada'
            JOIN escena_ordinal eo ON eo.escena_id = se.escena_id
            WHERE s.novela_id = ? AND s.sembrada_en_escena_id IS NULL
            """,
            (novela_id,),
        ).fetchall()
    ]


def _cierres_fuera_de_orden(con: sqlite3.Connection, novela_id: int) -> list[Conflicto]:
    """Los hilos se cierran en orden inverso al de apertura, como una pila (validators.md).

    Solo cuenta el cruce: A se abre antes que B y se cierra tambien antes que B, estando B
    abierto. Dos hilos que ni se solapan no dicen nada del orden.
    """
    hilos = [dict(f) for f in con.execute(
        """
        SELECT h.id, h.conflicto_central,
               (SELECT MIN(eo.ordinal) FROM hilo_estado he
                JOIN escena_ordinal eo ON eo.escena_id = he.escena_id
                WHERE he.hilo_id = h.id AND he.estado = 'abierto') AS apertura,
               (SELECT MIN(eo.ordinal) FROM hilo_estado he
                JOIN escena_ordinal eo ON eo.escena_id = he.escena_id
                WHERE he.hilo_id = h.id AND he.estado = 'resuelto') AS cierre
        FROM hilo h WHERE h.novela_id = ?
        """,
        (novela_id,),
    ).fetchall()]
    completos = sorted(
        (h for h in hilos if h["apertura"] is not None and h["cierre"] is not None),
        key=lambda h: int(h["apertura"]),
    )
    avisos: list[Conflicto] = []
    for i, a in enumerate(completos):
        for b in completos[i + 1:]:
            if int(a["apertura"]) < int(b["apertura"]) < int(a["cierre"]) < int(b["cierre"]):
                avisos.append(Conflicto(
                    comprobacion="cierre_fuera_de_orden", aviso=True,
                    descripcion=(
                        f"«{str(a['conflicto_central'])[:50]}» se abre antes que "
                        f"«{str(b['conflicto_central'])[:50]}» y se cierra tambien antes: lo "
                        "habitual es cerrar primero lo ultimo que se abrio."
                    ),
                    datos={"primero": a["id"], "segundo": b["id"]},
                ))
    return avisos
