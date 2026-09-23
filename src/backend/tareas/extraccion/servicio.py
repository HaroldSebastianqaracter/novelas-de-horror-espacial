"""El paquete del extractor y el registro de lo que el texto fijo.

El extractor es la pieza fragil del diseno: es el unico punto por el que el texto alimenta el
grafo. Si captura mal o de menos, la coherencia aguas abajo se degrada sin que ninguna puerta
lo note, porque una puerta no puede echar de menos un hecho que nadie registro.

Por eso todo lo que se escribe aqui lleva su escena de origen, y por eso el paquete le
entrega al agente los atributos que ya existen: para que reutilice `color de ojos` en vez de
inventar `tono de la mirada`.
"""

from __future__ import annotations

import sqlite3

from compartido.contexto import Elemento, Paquete, Presupuesto, ajustar
from compartido.grafo import Resolvedor, actualizar, insertar, lectura, normalizar

from .esquemas import SalidaExtraccion

AGENTE = "extraccion"


def paquete(
    con: sqlite3.Connection,
    novela_id: int,
    capitulo: int,
    textos: dict[int, str],
    *,
    presupuesto: Presupuesto,
) -> Paquete:
    escenas = lectura.escenas_del_capitulo(con, novela_id, capitulo)
    canon = lectura.canon_del_capitulo(con, novela_id, capitulo)
    atributos = lectura.atributos_por_sujeto(con, novela_id)
    siembras = lectura.siembras_vivas(con, novela_id, capitulo, margen=99)

    p = Paquete(agente=AGENTE, capitulo=capitulo)

    p.anadir(
        "instrucciones",
        f"Extrae del capitulo {capitulo} todo lo que el texto afirma. Refierete a cada "
        "elemento por el numero de escena en que aparece.",
        "TU ENCARGO",
    )

    # El inventario de nombres es obligatorio entero: sin el, el extractor no puede referirse
    # a nada del canon y todo acabaria en entidades no reconocidas.
    inventario = [Elemento(
        "Usa EXACTAMENTE estos nombres. Lo que no este aqui va a entidades_no_reconocidas.",
        True,
    )]
    inventario.append(Elemento(
        "Personajes: " + ", ".join(p_["nombre"] for p_ in canon["personajes"]), True
    ))
    inventario.append(Elemento(
        "Lugares: " + ", ".join(lugar["nombre"] for lugar in canon["lugares"]), True
    ))
    if canon["objetos"]:
        inventario.append(Elemento(
            "Objetos: " + ", ".join(o["nombre"] for o in canon["objetos"]), True
        ))
    if canon["amenaza"]:
        inventario.append(Elemento("Amenaza: la de la novela (sujeto_tipo 'amenaza')", True))
    p.anadir_elementos("canon", inventario, "ENTIDADES QUE EXISTEN")

    if atributos:
        # Opcionales: ayudan a no inventar sinonimos, y se recortan primero los de sujetos que
        # este capitulo no toca.
        del_capitulo = {normalizar(x["nombre"]) for x in (*canon["personajes"], *canon["lugares"])}
        ordenados = sorted(
            atributos.items(), key=lambda par: normalizar(par[0]) not in del_capitulo
        )
        p.anadir_elementos(
            "hechos",
            [Elemento(
                "Reutiliza estos nombres de atributo cuando el texto vuelva a hablar de lo mismo:",
                True,
            )] + [
                Elemento(f"- {sujeto}: {', '.join(lista)}", posicion=i + 1)
                for i, (sujeto, lista) in enumerate(ordenados)
            ],
            "ATRIBUTOS QUE YA EXISTEN",
        )

    if siembras:
        p.anadir(
            "siembras",
            "\n".join(f"- [{s['estado']}] {s['elemento']}" for s in siembras),
            "SIEMBRAS VIVAS (marca si el capitulo las riega o las paga)",
        )

    cuerpo = []
    for e in escenas:
        texto = textos.get(int(e["orden"]), "")
        if not texto:
            continue
        cuerpo.append(
            f"### Escena {e['orden']} — POV {e['pov_nombre']}, en {e['lugar_nombre']}"
            + (" (ANALEPSIS)" if e["analepsis"] else "")
            + f"\n\n{texto}"
        )
    p.anadir("prosa", "\n\n".join(cuerpo), "PROSA DEL CAPITULO")

    return ajustar(p, presupuesto)


def aplicar(
    con: sqlite3.Connection,
    novela_id: int,
    capitulo: int,
    salida: SalidaExtraccion,
    escenas_por_orden: dict[int, int],
) -> None:
    """Registra en el grafo todo lo que el texto fijo. Append-only, con escena de origen."""
    resolvedor = Resolvedor(con, novela_id)

    def escena(orden: int | None) -> int | None:
        return escenas_por_orden.get(int(orden)) if orden is not None else None

    def sujeto_id(tipo: str, nombre: str) -> int | None:
        tabla = {
            "personaje": "personaje", "lugar": "lugar", "objeto": "objeto",
            "faccion": "faccion", "sistema_tecnologico": "sistema_tecnologico",
        }.get(tipo)
        if tabla is None:
            return None
        return resolvedor.id_de(tabla, nombre)

    # --- Hechos, y el indice por (sujeto, atributo) que el conocimiento necesita ---------
    hechos_nuevos: dict[tuple[str, str], int] = {}
    for h in salida.hechos:
        eid = escena(h.escena_orden)
        if eid is None:
            continue
        previo = con.execute(
            """
            SELECT id FROM hecho
            WHERE novela_id = ? AND vigente = 1
              AND LOWER(TRIM(sujeto_nombre)) = LOWER(TRIM(?))
              AND LOWER(TRIM(atributo)) = LOWER(TRIM(?))
            ORDER BY id DESC LIMIT 1
            """,
            (novela_id, h.sujeto_ref, h.supersede_a or h.atributo),
        ).fetchone()
        hid = insertar(
            con, "hecho", novela_id=novela_id, escena_id=eid, sujeto_tipo=h.sujeto_tipo,
            sujeto_id=sujeto_id(h.sujeto_tipo, h.sujeto_ref), sujeto_nombre=h.sujeto_ref,
            atributo=h.atributo, valor=h.valor, categoria=h.categoria, cita=h.cita,
            supersede_a=int(previo["id"]) if (previo and h.supersede_a) else None,
        )
        hechos_nuevos[(normalizar(h.sujeto_ref), normalizar(h.atributo))] = hid

    def hecho_id(sujeto: str, atributo: str) -> int | None:
        clave = (normalizar(sujeto), normalizar(atributo))
        if clave in hechos_nuevos:
            return hechos_nuevos[clave]
        fila = con.execute(
            """
            SELECT id FROM hecho WHERE novela_id = ? AND vigente = 1
              AND LOWER(TRIM(sujeto_nombre)) = LOWER(TRIM(?))
              AND LOWER(TRIM(atributo)) = LOWER(TRIM(?))
            ORDER BY id DESC LIMIT 1
            """,
            (novela_id, sujeto, atributo),
        ).fetchone()
        return int(fila["id"]) if fila else None

    # --- Conocimiento adquirido y conocimiento usado -------------------------------------
    for c in salida.conocimiento:
        eid, pid, hid = (
            escena(c.escena_orden),
            resolvedor.id_de("personaje", c.personaje_ref),
            hecho_id(c.sujeto_ref, c.atributo),
        )
        if None in (eid, pid, hid):
            continue
        insertar(
            con, "estado_conocimiento", novela_id=novela_id, personaje_id=pid, hecho_id=hid,
            escena_id=eid, postura=c.postura, via=c.via,
        )

    for u in salida.usos_de_conocimiento:
        eid, pid, hid = (
            escena(u.escena_orden),
            resolvedor.id_de("personaje", u.personaje_ref),
            hecho_id(u.sujeto_ref, u.atributo),
        )
        if None in (eid, pid, hid):
            continue
        insertar(
            con, "uso_conocimiento", novela_id=novela_id, personaje_id=pid, hecho_id=hid,
            escena_id=eid,
        )

    # --- Estados -------------------------------------------------------------------------
    for ep in salida.estados_personaje:
        eid, pid = escena(ep.escena_orden), resolvedor.id_de("personaje", ep.personaje_ref)
        if eid is None or pid is None:
            continue
        insertar(
            con, "estado_personaje", novela_id=novela_id, personaje_id=pid, escena_id=eid,
            salud_fisica=ep.salud_fisica, estado_psicologico=ep.estado_psicologico,
            nivel_confianza=ep.nivel_confianza or None,
        )

    for eo in salida.estados_objeto:
        eid, oid = escena(eo.escena_orden), resolvedor.id_de("objeto", eo.objeto_ref)
        if eid is None or oid is None:
            continue
        insertar(
            con, "estado_objeto", novela_id=novela_id, objeto_id=oid, escena_id=eid,
            poseedor_id=resolvedor.id_de("personaje", eo.poseedor_ref),
            ubicacion_lugar_id=resolvedor.id_de("lugar", eo.ubicacion_ref),
        )

    # --- Cronologia ----------------------------------------------------------------------
    linea = con.execute(
        "SELECT id FROM linea_de_tiempo WHERE novela_id = ?", (novela_id,)
    ).fetchone()
    if linea is not None:
        base = int(con.execute(
            "SELECT COALESCE(MAX(orden_interno), 0) FROM evento WHERE novela_id = ?",
            (novela_id,),
        ).fetchone()[0])
        for i, ev in enumerate(salida.eventos, start=1):
            insertar(
                con, "evento", novela_id=novela_id, linea_de_tiempo_id=int(linea["id"]),
                escena_id=escena(ev.escena_orden), fecha_interna=ev.fecha_interna,
                orden_interno=ev.orden_interno if ev.orden_interno is not None else base + i,
                descripcion=ev.descripcion, tipo=ev.tipo, dramatizado=ev.dramatizado,
            )

    # --- Siembras ------------------------------------------------------------------------
    for s in salida.siembras:
        eid = escena(s.escena_orden)
        if eid is None:
            continue
        fila = None
        if s.siembra_ref:
            fila = con.execute(
                "SELECT id, sembrada_en_escena_id FROM siembra WHERE novela_id = ? "
                "AND LOWER(TRIM(elemento)) = LOWER(TRIM(?)) LIMIT 1",
                (novela_id, s.siembra_ref),
            ).fetchone()
        if fila is None:
            sid = insertar(
                con, "siembra", novela_id=novela_id, elemento=s.elemento or s.siembra_ref,
                sembrada_en_escena_id=eid, origen="extraccion",
            )
        else:
            sid = int(fila["id"])
            if fila["sembrada_en_escena_id"] is None:
                actualizar(con, "siembra", sid, sembrada_en_escena_id=eid)
        insertar(
            con, "siembra_estado", novela_id=novela_id, siembra_id=sid, escena_id=eid,
            estado=s.nuevo_estado,
        )

    # --- Revelacion de la amenaza ---------------------------------------------------------
    if salida.amenaza_revelacion:
        amenaza = con.execute(
            "SELECT id FROM amenaza WHERE novela_id = ?", (novela_id,)
        ).fetchone()
        ultima = max(escenas_por_orden.values(), default=None)
        if amenaza is not None and ultima is not None:
            insertar(
                con, "amenaza_revelacion", novela_id=novela_id, amenaza_id=int(amenaza["id"]),
                escena_id=ultima, nivel=salida.amenaza_revelacion,
            )

    # --- Lo que el texto uso y el canon no conoce ------------------------------------------
    for en in salida.entidades_no_reconocidas:
        eid = escena(en.escena_orden)
        if eid is None:
            continue
        insertar(
            con, "entidad_no_reconocida", novela_id=novela_id, escena_id=eid, nombre=en.nombre,
            contexto=en.contexto,
        )

    # --- Los dos resumenes con los que se construye el estado rodante ----------------------
    cap = lectura.capitulo(con, novela_id, capitulo)
    if cap is not None:
        actualizar(
            con, "capitulo", int(cap["id"]),
            resumen=salida.resumen, resumen_breve=salida.resumen_breve,
        )
