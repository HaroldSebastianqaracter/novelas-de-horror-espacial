"""Lo que el disenador de elenco escribe en el grafo, y el paquete que recibe."""

from __future__ import annotations

import json
import sqlite3

from compartido.grafo import Resolvedor, insertar, lectura

from .esquemas import SalidaElenco

AGENTE = "elenco"


def paquete(con: sqlite3.Connection, novela_id: int) -> str:
    n = lectura.novela(con, novela_id) or {}
    temas = con.execute(
        "SELECT pregunta_central, verdad_tematica FROM tema WHERE novela_id = ?", (novela_id,)
    ).fetchall()
    mundo = con.execute(
        "SELECT nombre, reglas_fisicas FROM mundo WHERE novela_id = ?", (novela_id,)
    ).fetchone()
    amenaza = con.execute(
        "SELECT naturaleza, origen, reglas FROM amenaza WHERE novela_id = ?", (novela_id,)
    ).fetchone()
    facciones = con.execute(
        "SELECT nombre, proposito, objetivos, recursos FROM faccion WHERE novela_id = ?",
        (novela_id,),
    ).fetchall()

    lineas = [
        "La novela ya tiene fijado esto:",
        f"- Premisa: {n.get('premisa', '')}",
        f"- Pregunta dramatica: {n.get('pregunta_dramatica', '')}",
        f"- Subgenero: {n.get('subgenero_dominante', '')} | Final: {n.get('tipo_final', '')}",
        "",
        "Tema (cada personaje es una variacion suya):",
    ]
    lineas.extend(f"- {t['pregunta_central']} -> {t['verdad_tematica']}" for t in temas)

    if mundo:
        lineas += ["", f"Mundo: {mundo['nombre']}. {mundo['reglas_fisicas']}"]
    if amenaza:
        try:
            reglas = json.loads(amenaza["reglas"] or "[]")
        except json.JSONDecodeError:
            reglas = []
        lineas += ["", f"Amenaza: {amenaza['naturaleza']} (origen: {amenaza['origen']})"]
        lineas.extend(
            f"  - puede {r.get('capacidad', '')}; no puede {r.get('limite', '')}; "
            f"se activa con {r.get('activacion', '')}"
            for r in reglas if isinstance(r, dict)
        )

    lineas += ["", "Facciones a las que pueden pertenecer (usa estos nombres exactos):"]
    lineas.extend(f"- {f['nombre']}: {f['proposito']}" for f in facciones)
    return "\n".join(lineas)


def aplicar(con: sqlite3.Connection, novela_id: int, salida: SalidaElenco) -> None:
    resolvedor = Resolvedor(con, novela_id)

    # Dos pasadas: primero todos los personajes, despues sus relaciones. Una relacion puede
    # apuntar a alguien que todavia no existiria en la primera.
    for p in salida.personajes:
        pid = insertar(
            con, "personaje", novela_id=novela_id,
            faccion_id=resolvedor.id_de("faccion", p.faccion),
            nombre=p.nombre, rol=p.rol, rol_narrativo=p.rol_narrativo, deseo=p.deseo,
            necesidad_interna=p.necesidad_interna, fantasma=p.fantasma, herida=p.herida,
            mentira=p.mentira, defecto=p.defecto, tipo_arco=p.tipo_arco,
            subtipo_arco=p.subtipo_arco, idiolecto=p.idiolecto, secreto=p.secreto,
            posicion_tematica=p.posicion_tematica,
        )
        resolvedor.registrar("personaje", p.nombre, pid)

    for p in salida.personajes:
        origen = resolvedor.id_de("personaje", p.nombre, obligatorio=True)
        for r in p.relaciones:
            destino = resolvedor.id_de("personaje", r.destino)
            if destino is None or destino == origen:
                continue
            con.execute(
                "INSERT OR IGNORE INTO personaje_relacion (origen_id, destino_id, tipo) "
                "VALUES (?,?,?)",
                (origen, destino, r.tipo),
            )
