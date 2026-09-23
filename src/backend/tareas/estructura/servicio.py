"""Lo que el estructurador escribe en el grafo, y el paquete que recibe."""

from __future__ import annotations

import sqlite3

from compartido.brief import linea_destinatario
from compartido.grafo import Resolvedor, insertar, lectura

from .esquemas import SalidaEstructura

AGENTE = "estructura"


def paquete(con: sqlite3.Connection, novela_id: int) -> str:
    n = lectura.novela(con, novela_id) or {}
    temas = con.execute(
        "SELECT pregunta_central, verdad_tematica FROM tema WHERE novela_id = ?", (novela_id,)
    ).fetchall()
    personajes = con.execute(
        "SELECT nombre, rol_narrativo, deseo, necesidad_interna, mentira, tipo_arco,"
        " posicion_tematica FROM personaje WHERE novela_id = ? ORDER BY id",
        (novela_id,),
    ).fetchall()
    lugares = con.execute(
        "SELECT nombre, tipo FROM lugar WHERE novela_id = ? ORDER BY id", (novela_id,)
    ).fetchall()
    restricciones = lectura.restricciones(con, novela_id)

    lineas = [
        "La novela ya tiene fijado esto:",
        f"- Premisa: {n.get('premisa', '')}",
        f"- Logline: {n.get('logline', '')}",
        f"- Pregunta dramatica (el climax la responde): {n.get('pregunta_dramatica', '')}",
        f"- Subgenero: {n.get('subgenero_dominante', '')} | Final: {n.get('tipo_final', '')}",
        f"- Longitud objetivo: {restricciones.get('longitud_objetivo_palabras', 'sin fijar')}",
        "",
        "Tema:",
    ]
    lineas.extend(f"- {t['pregunta_central']} -> {t['verdad_tematica']}" for t in temas)

    lineas += ["", "Elenco (usa estos nombres exactos):"]
    for p in personajes:
        lineas.append(
            f"- {p['nombre']} ({p['rol_narrativo']}, arco {p['tipo_arco']}): "
            f"desea {p['deseo']}; necesita {p['necesidad_interna']}; "
            f"cree que {p['mentira']}. Ante el tema: {p['posicion_tematica']}"
        )

    lineas += ["", "Lugares disponibles:"]
    lineas.extend(f"- {lugar['nombre']} ({lugar['tipo']})" for lugar in lugares)

    brief = lectura.brief(con, novela_id)
    if brief is not None:
        # RF3-PER-03: el hilo principal es el del destinatario, que sobrevive.
        lineas += ["", linea_destinatario(brief),
                   "El hilo principal es el suyo, y su personaje sobrevive a la novela."]
    return "\n".join(lineas)


def aplicar(con: sqlite3.Connection, novela_id: int, salida: SalidaEstructura) -> None:
    resolvedor = Resolvedor(con, novela_id)

    for a in salida.actos:
        insertar(
            con, "acto", novela_id=novela_id, numero=a.numero,
            funcion_narrativa=a.funcion_narrativa,
        )

    tema_id = con.execute(
        "SELECT id FROM tema WHERE novela_id = ? ORDER BY id LIMIT 1", (novela_id,)
    ).fetchone()

    por_nombre: dict[str, int] = {}
    for h in salida.hilos:
        hid = insertar(
            con, "hilo", novela_id=novela_id,
            tema_id=tema_id["id"] if (tema_id and h.dramatiza_tema) else None,
            tipo=h.tipo, conflicto_central=h.conflicto_central,
        )
        por_nombre[h.nombre] = hid
        for g in h.puntos_de_giro:
            insertar(con, "punto_de_giro", hilo_id=hid, tipo=g.tipo, posicion=g.posicion)
        for nombre in h.personajes:
            pid = resolvedor.id_de("personaje", nombre)
            if pid is not None:
                con.execute(
                    "INSERT OR IGNORE INTO hilo_personaje (hilo_id, personaje_id) VALUES (?,?)",
                    (hid, pid),
                )

    for o in salida.objetos:
        oid = insertar(
            con, "objeto", novela_id=novela_id, nombre=o.nombre,
            funcion_narrativa=o.funcion_narrativa,
        )
        resolvedor.registrar("objeto", o.nombre, oid)

    # Las siembras del estructurador todavia no tienen escena: las escenas no existen hasta
    # la escaleta. `sembrada_en_escena_id` queda a NULL y se rellena cuando el extractor las
    # vea plantadas en la pagina.
    for s in salida.siembras:
        insertar(
            con, "siembra", novela_id=novela_id, hilo_id=por_nombre.get(s.hilo),
            elemento=s.elemento, capitulo_pago_previsto=s.capitulo_pago_previsto,
            origen="estructura",
        )
