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
    """Los conflictos de la puerta 3, numerados, y la prosa rechazada del capitulo."""
    p = Paquete(agente=AGENTE, capitulo=capitulo)
    conflictos = [
        f"{n}. [{c.comprobacion}] {c.descripcion}"
        + (f"\n   Datos: {json.dumps(c.datos, ensure_ascii=False)}" if c.datos else "")
        for n, c in enumerate(resultado.bloqueantes, start=1)
    ]
    p.anadir(
        "instrucciones",
        f"La puerta de continuidad ha parado el capitulo {capitulo}. Explica cada conflicto y "
        "da tu opinion de si parece real, un falso positivo o dudoso, con un elemento de "
        "`opiniones` por cada uno, en su orden. La parada sigue abierta digas lo que digas: "
        "quien decide es el autor.\n\nCONFLICTOS\n" + "\n".join(conflictos),
        "TU ENCARGO Y LOS CONFLICTOS",
    )
    p.anadir(
        "prosa",
        "\n\n".join(f"[Escena {orden}]\n{texto}" for orden, texto in sorted(textos.items())),
        f"PROSA RECHAZADA DEL CAPITULO {capitulo}",
    )
    return ajustar(p, presupuesto)
