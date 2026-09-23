"""Puerta 2 — escaleta (RF-PIPE-07). Determinista, sobre toda la escaleta.

La comprobacion central es la del principio 10: una escena existe si algo esta en un polo al
empezar y en el contrario al terminar. Es el test mas falsable del oficio, y aqui es una
comparacion de dos cadenas normalizadas.
"""

from __future__ import annotations

import sqlite3

from compartido.puerta_base import Conflicto, ResultadoPuerta
from tareas.escaleta.esquemas import normalizar_valor

DESVIACION_LONGITUD = 0.10
MIN_ESCENAS_SECUENCIA = 3
MAX_ESCENAS_SECUENCIA = 8


def _restriccion(con: sqlite3.Connection, novela_id: int, tipo: str) -> str | None:
    fila = con.execute(
        "SELECT valor FROM restriccion WHERE novela_id = ? AND tipo = ?", (novela_id, tipo)
    ).fetchone()
    return None if fila is None else str(fila["valor"])


def evaluar(con: sqlite3.Connection, novela_id: int) -> ResultadoPuerta:
    conflictos: list[Conflicto] = []

    escenas = [dict(f) for f in con.execute(
        """
        SELECT e.id, e.orden, e.pov_id, e.lugar_id, e.objetivo, e.conflicto,
               e.valor_inicial, e.valor_final, e.longitud_prevista, e.secuencia_id,
               c.numero AS capitulo
        FROM escena e JOIN capitulo c ON c.id = e.capitulo_id
        WHERE e.novela_id = ? ORDER BY c.numero, e.orden
        """,
        (novela_id,),
    )]

    for e in escenas:
        donde = f"{e['capitulo']}.{e['orden']}"
        # «Sin POV declarado» no se comprueba: escena.pov_id es NOT NULL y el esquema de la
        # escaleta lo exige, asi que nunca podria disparar (RF2-PIPE-07).
        en_reparto = con.execute(
            "SELECT 1 FROM escena_personaje WHERE escena_id = ? AND personaje_id = ?",
            (e["id"], e["pov_id"]),
        ).fetchone()
        if en_reparto is None:
            conflictos.append(Conflicto(
                comprobacion="pov_fuera_del_reparto", capitulo=e["capitulo"],
                escena_id=e["id"],
                descripcion=f"El POV de la escena {donde} no esta en su reparto.",
            ))

        if normalizar_valor(e["valor_inicial"] or "") == normalizar_valor(e["valor_final"] or ""):
            conflictos.append(Conflicto(
                comprobacion="escena_sin_cambio_de_valor", capitulo=e["capitulo"],
                escena_id=e["id"],
                descripcion=(
                    f"La escena {donde} termina en la misma polaridad en que empezo "
                    f"('{e['valor_inicial']}'): es relleno declarado."
                ),
            ))

        if not (e["conflicto"] or "").strip() or not (e["objetivo"] or "").strip():
            conflictos.append(Conflicto(
                comprobacion="escena_sin_conflicto", capitulo=e["capitulo"], escena_id=e["id"],
                descripcion=f"La escena {donde} no tiene objetivo o conflicto.",
            ))

        if not e["lugar_id"]:
            conflictos.append(Conflicto(
                comprobacion="escena_sin_lugar", capitulo=e["capitulo"], escena_id=e["id"],
                descripcion=f"La escena {donde} no ocurre en ningun lugar del canon.",
            ))

    # Cobertura: ningun acto sin capitulos, ningun capitulo sin escenas.
    for f in con.execute(
        "SELECT a.numero FROM acto a WHERE a.novela_id = ? AND NOT EXISTS "
        "(SELECT 1 FROM capitulo c WHERE c.acto_id = a.id)", (novela_id,)
    ):
        conflictos.append(Conflicto(
            comprobacion="acto_sin_capitulos",
            descripcion=f"El acto {f['numero']} no tiene capitulos.",
        ))
    for f in con.execute(
        "SELECT c.numero FROM capitulo c WHERE c.novela_id = ? AND NOT EXISTS "
        "(SELECT 1 FROM escena e WHERE e.capitulo_id = c.id)", (novela_id,)
    ):
        conflictos.append(Conflicto(
            comprobacion="capitulo_sin_escenas", capitulo=f["numero"],
            descripcion=f"El capitulo {f['numero']} no tiene escenas.",
        ))

    # Presupuesto de longitud.
    objetivo_bruto = _restriccion(con, novela_id, "longitud_objetivo_palabras")
    total = sum(int(e["longitud_prevista"] or 0) for e in escenas)
    if objetivo_bruto:
        objetivo = int(objetivo_bruto)
        if objetivo > 0 and abs(total - objetivo) / objetivo > DESVIACION_LONGITUD:
            conflictos.append(Conflicto(
                comprobacion="presupuesto_de_longitud",
                descripcion=(
                    f"La escaleta suma {total} palabras previstas y el objetivo es {objetivo}, "
                    f"mas de un {int(DESVIACION_LONGITUD * 100)} % de desviacion."
                ),
                datos={"total": total, "objetivo": objetivo},
            ))

    rango = _restriccion(con, novela_id, "longitud_capitulo_palabras")
    if rango and "-" in rango:
        minimo, maximo = (int(x) for x in rango.split("-", 1))
        por_capitulo: dict[int, int] = {}
        for e in escenas:
            por_capitulo[e["capitulo"]] = por_capitulo.get(e["capitulo"], 0) + int(
                e["longitud_prevista"] or 0
            )
        for numero, palabras in sorted(por_capitulo.items()):
            if not (minimo <= palabras <= maximo):
                conflictos.append(Conflicto(
                    comprobacion="longitud_de_capitulo", capitulo=numero,
                    descripcion=(
                        f"El capitulo {numero} prevee {palabras} palabras, fuera del rango "
                        f"{minimo}-{maximo}."
                    ),
                ))

    # Tamano de secuencia: aviso, no fallo.
    for f in con.execute(
        """
        SELECT s.id, COUNT(e.id) AS n
        FROM secuencia s LEFT JOIN escena e ON e.secuencia_id = s.id
        WHERE s.novela_id = ? GROUP BY s.id
        """,
        (novela_id,),
    ):
        if not (MIN_ESCENAS_SECUENCIA <= f["n"] <= MAX_ESCENAS_SECUENCIA):
            conflictos.append(Conflicto(
                comprobacion="tamano_de_secuencia", aviso=True,
                descripcion=(
                    f"Una secuencia tiene {f['n']} escenas; lo habitual son "
                    f"{MIN_ESCENAS_SECUENCIA} a {MAX_ESCENAS_SECUENCIA}."
                ),
            ))

    return ResultadoPuerta(puerta=2, conflictos=conflictos)
