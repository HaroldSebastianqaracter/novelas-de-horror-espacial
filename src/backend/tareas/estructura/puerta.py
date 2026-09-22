"""Puerta 1 — estructura (RF-PIPE-05). Solo la parte determinista.

Comprueba con consultas que el arco resuelve antes de dejar bajar a capitulos. La parte de
juicio —si el climax responde de verdad la pregunta dramatica— no se evalua en la v1 y
esta declarada como riesgo aceptado U1 en el plan de verificacion.

La comprobacion de cierre en orden inverso viene del principio 5: los hilos se anidan como
munecas rusas, y la mayoria de los finales insatisfactorios no son climax debiles, son
hilos cerrados en el orden equivocado.
"""

from __future__ import annotations

import sqlite3

from compartido.puerta_base import Conflicto, ResultadoPuerta
from config import FINALES_POR_SUBGENERO

APERTURAS = ("gancho", "incidente_incitador", "primer_umbral")
CIERRES = ("climax", "resolucion")
OBLIGATORIOS_PRINCIPAL = ("incidente_incitador", "punto_medio", "climax", "resolucion")


def evaluar(con: sqlite3.Connection, novela_id: int) -> ResultadoPuerta:
    conflictos: list[Conflicto] = []

    hilos = [dict(f) for f in con.execute(
        "SELECT id, tipo, conflicto_central FROM hilo WHERE novela_id = ?", (novela_id,)
    )]
    principales = [h for h in hilos if h["tipo"] == "principal"]

    if len(principales) != 1:
        conflictos.append(Conflicto(
            comprobacion="hilo_principal",
            descripcion=f"Tiene que haber exactamente un hilo principal, hay {len(principales)}.",
            datos={"hilos": len(hilos)},
        ))
    else:
        principal = principales[0]
        giros = [dict(f) for f in con.execute(
            "SELECT tipo, posicion FROM punto_de_giro WHERE hilo_id = ? ORDER BY posicion",
            (principal["id"],),
        )]
        tipos = [g["tipo"] for g in giros]
        faltan = [t for t in OBLIGATORIOS_PRINCIPAL if t not in tipos]
        if faltan:
            conflictos.append(Conflicto(
                comprobacion="giros_obligatorios",
                descripcion=f"Al hilo principal le faltan puntos de giro: {faltan}",
                datos={"presentes": tipos},
            ))
        else:
            posiciones = {g["tipo"]: g["posicion"] for g in giros}
            secuencia = [posiciones[t] for t in OBLIGATORIOS_PRINCIPAL]
            if secuencia != sorted(secuencia):
                conflictos.append(Conflicto(
                    comprobacion="orden_de_giros",
                    descripcion=(
                        "Incidente incitador, punto medio, climax y resolucion no van en orden: "
                        f"{dict(zip(OBLIGATORIOS_PRINCIPAL, secuencia, strict=True))}"
                    ),
                    datos={"posiciones": posiciones},
                ))

    # Cierre en orden inverso al de apertura: el ultimo hilo que abre es el primero que cierra.
    aperturas: list[tuple[float, int]] = []
    cierres: list[tuple[float, int]] = []
    for h in hilos:
        giros = [dict(f) for f in con.execute(
            "SELECT tipo, posicion FROM punto_de_giro WHERE hilo_id = ? ORDER BY posicion",
            (h["id"],),
        )]
        if not giros:
            conflictos.append(Conflicto(
                comprobacion="hilo_sin_giros",
                descripcion=f"El hilo '{h['conflicto_central'][:60]}' no tiene puntos de giro.",
                datos=h,
            ))
            continue
        aperturas.append((giros[0]["posicion"], h["id"]))
        cierres.append((giros[-1]["posicion"], h["id"]))

    if len(aperturas) > 1:
        orden_apertura = [i for _, i in sorted(aperturas)]
        orden_cierre = [i for _, i in sorted(cierres)]
        if orden_cierre != list(reversed(orden_apertura)):
            conflictos.append(Conflicto(
                comprobacion="cierre_en_orden_inverso",
                descripcion=(
                    "Los hilos no cierran en orden inverso al de apertura. Es la causa habitual "
                    "de un final que no satisface."
                ),
                aviso=True,
                datos={"apertura": orden_apertura, "cierre": orden_cierre},
            ))

    # Protagonista con arco declarado y oponente.
    protagonistas = [dict(f) for f in con.execute(
        "SELECT nombre, tipo_arco FROM personaje WHERE novela_id = ? AND rol_narrativo = "
        "'protagonista'", (novela_id,)
    )]
    if len(protagonistas) != 1:
        conflictos.append(Conflicto(
            comprobacion="protagonista",
            descripcion=f"Tiene que haber un protagonista, hay {len(protagonistas)}.",
        ))
    elif not protagonistas[0]["tipo_arco"]:
        conflictos.append(Conflicto(
            comprobacion="arco_del_protagonista",
            descripcion=f"{protagonistas[0]['nombre']} no tiene tipo de arco declarado.",
        ))

    oponentes = con.execute(
        "SELECT COUNT(*) FROM personaje WHERE novela_id = ? AND rol_narrativo = 'oponente'",
        (novela_id,),
    ).fetchone()[0]
    if not oponentes:
        conflictos.append(Conflicto(
            comprobacion="oponente",
            descripcion="No hay oponente: el tema no tiene quien sostenga la posicion contraria.",
        ))

    # Final compatible con el subgenero (principios 52 y 54).
    fila = con.execute(
        "SELECT subgenero_dominante, tipo_final FROM novela WHERE id = ?", (novela_id,)
    ).fetchone()
    if fila is not None:
        sub, final = fila["subgenero_dominante"], fila["tipo_final"]
        if not final:
            conflictos.append(Conflicto(
                comprobacion="tipo_de_final",
                descripcion="La novela no declara tipo de final.",
            ))
        elif sub in FINALES_POR_SUBGENERO and final not in FINALES_POR_SUBGENERO[sub]:
            conflictos.append(Conflicto(
                comprobacion="final_incompatible", aviso=True,
                descripcion=(
                    f"Un final '{final}' no es el habitual del subgenero '{sub}'. "
                    f"Los que pide son: {sorted(FINALES_POR_SUBGENERO[sub])}"
                ),
                datos={"subgenero": sub, "tipo_final": final},
            ))

    return ResultadoPuerta(puerta=1, conflictos=conflictos)
