"""Lo que el escaletador escribe en el grafo, y el paquete que recibe."""

from __future__ import annotations

import sqlite3

from compartido.grafo import NombreDesconocido, Resolvedor, insertar, lectura

from .esquemas import SalidaEscaleta

AGENTE = "escaleta"


def paquete(con: sqlite3.Connection, novela_id: int) -> str:
    n = lectura.novela(con, novela_id) or {}
    restricciones = lectura.restricciones(con, novela_id)
    actos = con.execute(
        "SELECT numero, funcion_narrativa FROM acto WHERE novela_id = ? ORDER BY numero",
        (novela_id,),
    ).fetchall()
    hilos = con.execute(
        """
        SELECT h.id, h.tipo, h.conflicto_central,
               (SELECT GROUP_CONCAT(g.tipo || ' @' || CAST(g.posicion AS INT) || '%', '; ')
                  FROM (SELECT tipo, posicion FROM punto_de_giro WHERE hilo_id = h.id
                        ORDER BY posicion) g) AS giros
        FROM hilo h WHERE h.novela_id = ? ORDER BY h.tipo DESC, h.id
        """,
        (novela_id,),
    ).fetchall()
    personajes = con.execute(
        "SELECT nombre, rol_narrativo, idiolecto FROM personaje WHERE novela_id = ? ORDER BY id",
        (novela_id,),
    ).fetchall()
    lugares = con.execute(
        "SELECT nombre, tipo FROM lugar WHERE novela_id = ? ORDER BY id", (novela_id,)
    ).fetchall()
    objetos = con.execute(
        "SELECT nombre, funcion_narrativa FROM objeto WHERE novela_id = ? ORDER BY id",
        (novela_id,),
    ).fetchall()
    siembras = con.execute(
        "SELECT elemento, capitulo_pago_previsto FROM siembra WHERE novela_id = ? ORDER BY id",
        (novela_id,),
    ).fetchall()

    objetivo = restricciones.get("longitud_objetivo_palabras", "sin fijar")
    rango = restricciones.get("longitud_capitulo_palabras", "sin fijar")

    lineas = [
        f"Premisa: {n.get('premisa', '')}",
        f"Pregunta dramatica: {n.get('pregunta_dramatica', '')}",
        f"Subgenero: {n.get('subgenero_dominante', '')} | Final: {n.get('tipo_final', '')}",
        f"POV por defecto: {n.get('pov_por_defecto', '')} | Tiempo: {n.get('tiempo_verbal', '')}",
        "",
        f"PRESUPUESTO: {objetivo} palabras en total; cada capitulo dentro de {rango}.",
        "La suma de longitud_prevista de todas las escenas no puede desviarse mas de un 10 %",
        "del total.",
        "",
        "Actos:",
    ]
    lineas.extend(f"- Acto {a['numero']}: {a['funcion_narrativa']}" for a in actos)

    lineas += ["", "Hilos y sus puntos de giro (respeta el orden y la posicion):"]
    lineas.extend(f"- [{h['tipo']}] {h['conflicto_central']} :: {h['giros'] or ''}" for h in hilos)

    lineas += ["", "Personajes (usa estos nombres exactos como POV y en el reparto):"]
    lineas.extend(f"- {p['nombre']} ({p['rol_narrativo']})" for p in personajes)

    lineas += ["", "Lugares (usa estos nombres exactos):"]
    lineas.extend(f"- {lugar['nombre']} ({lugar['tipo']})" for lugar in lugares)

    if objetos:
        lineas += ["", "Objetos con funcion narrativa:"]
        lineas.extend(f"- {o['nombre']}: {o['funcion_narrativa']}" for o in objetos)
    if siembras:
        lineas += ["", "Siembras planificadas (colocalas donde parezcan naturales):"]
        lineas.extend(
            f"- {s['elemento']}"
            + (f" (pago previsto hacia el capitulo {s['capitulo_pago_previsto']})"
               if s["capitulo_pago_previsto"] else "")
            for s in siembras
        )
    return "\n".join(lineas)


def aplicar(con: sqlite3.Connection, novela_id: int, salida: SalidaEscaleta) -> None:
    resolvedor = Resolvedor(con, novela_id)

    actos = {
        int(f["numero"]): int(f["id"])
        for f in con.execute("SELECT id, numero FROM acto WHERE novela_id = ?", (novela_id,))
    }

    secuencias: dict[str, int] = {}
    for s in salida.secuencias:
        acto_id = actos.get(s.acto)
        if acto_id is None:
            raise NombreDesconocido(f"La secuencia '{s.nombre}' cuelga del acto {s.acto}, que "
                                    "no existe.")
        secuencias[s.nombre] = insertar(
            con, "secuencia", novela_id=novela_id, acto_id=acto_id,
            objetivo_intermedio=s.objetivo_intermedio, orden=s.orden,
        )

    for c in salida.capitulos:
        acto_id = actos.get(c.acto)
        if acto_id is None:
            raise NombreDesconocido(f"El capitulo {c.numero} cuelga del acto {c.acto}, que no "
                                    "existe.")
        capitulo_id = insertar(
            con, "capitulo", novela_id=novela_id, acto_id=acto_id, numero=c.numero,
            objetivo=c.objetivo, pov_id=resolvedor.id_de("personaje", c.pov, obligatorio=True),
            gancho_apertura=c.gancho_apertura, gancho_cierre=c.gancho_cierre,
            longitud_prevista=c.longitud_prevista, estado="planificado",
        )

        for e in c.escenas:
            escena_id = insertar(
                con, "escena", novela_id=novela_id, capitulo_id=capitulo_id,
                secuencia_id=secuencias.get(e.secuencia),
                pov_id=resolvedor.id_de("personaje", e.pov, obligatorio=True),
                lugar_id=resolvedor.id_de("lugar", e.lugar, obligatorio=True),
                orden=e.orden, objetivo=e.objetivo, conflicto=e.conflicto,
                resultado=e.resultado, valor_inicial=e.valor_inicial, valor_final=e.valor_final,
                tension=e.tension, gancho_salida=e.gancho_salida,
                longitud_prevista=e.longitud_prevista, analepsis=e.analepsis,
            )
            for nombre in e.reparto:
                pid = resolvedor.id_de("personaje", nombre)
                if pid is not None:
                    con.execute(
                        "INSERT OR IGNORE INTO escena_personaje (escena_id, personaje_id) "
                        "VALUES (?,?)", (escena_id, pid),
                    )
            for nombre in e.objetos:
                oid = resolvedor.id_de("objeto", nombre)
                if oid is not None:
                    con.execute(
                        "INSERT OR IGNORE INTO escena_objeto (escena_id, objeto_id) VALUES (?,?)",
                        (escena_id, oid),
                    )
            for orden, b in enumerate(e.beats, start=1):
                insertar(con, "beat", escena_id=escena_id, orden=orden, tipo=b.tipo,
                         cambio=b.cambio)
            if e.secuela is not None:
                insertar(
                    con, "secuela", escena_id=escena_id, reaccion=e.secuela.reaccion,
                    dilema=e.secuela.dilema, decision=e.secuela.decision,
                )
