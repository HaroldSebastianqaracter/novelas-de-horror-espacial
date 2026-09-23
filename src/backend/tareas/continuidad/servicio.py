"""El paquete del revisor de continuidad: la segunda opinion de una parada (spec3, RF3-JUE-01)."""

from __future__ import annotations

import json
import sqlite3

from compartido.contexto import Paquete, Presupuesto, ajustar
from compartido.puerta_base import ResultadoPuerta

AGENTE = "continuidad"


def paquete(
    con: sqlite3.Connection,
    novela_id: int,
    capitulo: int,
    resultado: ResultadoPuerta,
    textos: dict[int, str],
    *,
    presupuesto: Presupuesto,
) -> Paquete:
    """Los conflictos bloqueantes de la puerta 3 y la prosa rechazada del capitulo.

    Cada conflicto lleva su numero en la lista entera del informe, avisos incluidos: es el que
    ve el autor en el frontend, y la opinion tiene que nombrar el mismo (validador de 9cc7972).
    """
    p = Paquete(agente=AGENTE, capitulo=capitulo)
    conflictos = [
        f"{n}. [{c.comprobacion}] {c.descripcion}"
        + (f"\n   Datos: {json.dumps(c.datos, ensure_ascii=False)}" if c.datos else "")
        for n, c in enumerate(resultado.conflictos, start=1) if not c.aviso
    ]
    p.anadir(
        "instrucciones",
        f"La puerta de continuidad ha parado el capitulo {capitulo}. Explica cada conflicto y "
        "da tu opinion de si parece real, un falso positivo o dudoso, con un elemento de "
        "`opiniones` por cada uno, con el mismo numero que lleva aqui. La parada sigue "
        "abierta digas lo que digas: quien decide es el autor.\n\nCONFLICTOS\n"
        + "\n".join(conflictos),
        "TU ENCARGO Y LOS CONFLICTOS",
    )
    p.anadir(
        "prosa",
        "\n\n".join(f"[Escena {orden}]\n{texto}" for orden, texto in sorted(textos.items())),
        f"PROSA RECHAZADA DEL CAPITULO {capitulo}",
    )
    return ajustar(p, presupuesto)
