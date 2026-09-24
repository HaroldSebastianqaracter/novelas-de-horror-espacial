"""El paquete del revisor para la pasada del cambio del lector (specs/spec3.md, RF3-CAM-08).

Se construye dentro de la transaccion simulada (RF3-CAM-07): el canon que lee ya tiene el
cambio aplicado, aunque todavia no se haya confirmado nada.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from compartido import politica
from compartido.cambio import Cambio, partes_viejas
from compartido.contexto import Elemento, Paquete
from compartido.grafo import lectura

AGENTE = "revision"


def _que_hacer(cambio: Cambio) -> str:
    if cambio.tipo == "renombrar":
        partes = [p for p in partes_viejas(cambio.antes, cambio.despues) if p != cambio.antes]
        extra = (" Tambien cuando la prosa lo llama solo "
                 + " o ".join(f"«{p}»" for p in partes) + ".") if partes else ""
        return (
            f"«{cambio.antes}» se llama ahora «{cambio.despues}». Sustituye cada vez que la "
            f"prosa lo nombra.{extra} Ajusta las concordancias si el nombre nuevo las cambia, y "
            "nada mas."
        )
    return (
        f"El dato «{cambio.sujeto} · {cambio.atributo}» vale ahora «{cambio.despues}» (antes, "
        f"«{cambio.antes}»). Donde la prosa lo diga o dependa de el, que diga lo nuevo. Si una "
        "cuenta o una frase deja de tener sentido por el cambio, arreglala con lo minimo. Si el "
        "capitulo no escribe el dato, devuelvelo igual."
    )


def paquete(
    con: sqlite3.Connection,
    novela_id: int,
    capitulo: int,
    cambio: Cambio,
    textos: dict[int, str],
    *,
    criterios_incumplidos: list[dict[str, Any]] | None = None,
) -> Paquete:
    n = lectura.novela(con, novela_id) or {}
    cap = lectura.capitulo(con, novela_id, capitulo) or {}
    p = Paquete(agente=AGENTE, capitulo=capitulo)

    instrucciones = [
        f"Corriges el capitulo {capitulo} de «{n.get('titulo', '')}», que ya estaba aprobado, "
        "porque el lector pidio un cambio. Cambia SOLO lo que toca el cambio: el resto del "
        "capitulo tiene que quedar identico, palabra por palabra.",
    ]
    vetadas = [r.termino for r in politica.reglas(con, novela_id)]
    if vetadas:
        instrucciones.append("PALABRAS VETADAS (no pueden aparecer): " + ", ".join(vetadas) + ".")
    fijados = lectura.cambios_aplicados(con, novela_id)
    if fijados:
        instrucciones.append("Lo que el lector ya fijo antes: " + " ".join(fijados))
    p.anadir("instrucciones", "\n".join(instrucciones), "TU ENCARGO")
    p.anadir("cambio", _que_hacer(cambio), "EL CAMBIO", obligatorio=True)

    p.anadir_elementos(
        "prosa",
        [Elemento(f"[escena {orden}]\n{textos[orden]}", obligatorio=True)
         for orden in sorted(textos)],
        f"PROSA APROBADA DEL CAPITULO {capitulo}, ESCENA POR ESCENA",
        separador="\n\n",
    )
    p.anadir("resumenes", (
        f"Resumen: {cap.get('resumen') or ''}\n\nResumen breve: {cap.get('resumen_breve') or ''}"
    ), "RESUMENES DEL CAPITULO (corrigelos igual)", obligatorio=True)

    if criterios_incumplidos:
        p.anadir("criterios_incumplidos", "\n\n".join(
            f"**{c.get('criterio', '')}**: {c.get('sugerencia', '')}"
            + (f"\nEvidencia: «{c['evidencia']}»" if c.get("evidencia") else "")
            for c in criterios_incumplidos
        ), "LO QUE FALLO EN EL INTENTO ANTERIOR. Corrigelo sin tocar nada mas")
    return p
