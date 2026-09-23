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
from typing import Any

from compartido.contexto import Elemento, Paquete, Presupuesto, ajustar
from compartido.grafo import (
    Resolvedor,
    actualizar,
    insertar,
    insertar_hecho,
    lectura,
    normalizar,
)

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
    atributos = lectura.valores_vigentes(con, novela_id)
    siembras = lectura.siembras_vivas(con, novela_id, capitulo, margen=99)

    p = Paquete(agente=AGENTE, capitulo=capitulo)

    ultimo_orden = lectura.ultimo_orden_interno(con, novela_id)
    p.anadir(
        "instrucciones",
        f"Extrae del capitulo {capitulo} todo lo que el texto afirma. Refierete a cada "
        "elemento por el numero de escena en que aparece.\n"
        f"El ultimo orden_interno registrado en la novela es {ultimo_orden}: todo evento "
        "dramatizado lleva el suyo y continua la escala desde ahi (dos sucesos simultaneos "
        "comparten orden; uno anterior en la cronologia, como un recuerdo, lleva uno menor).",
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
                "Atributos que ya existen, con su valor vigente. Si el texto vuelve a decir lo "
                "mismo, repite el valor EXACTO. Si lo cambia, registra el nuevo con supersede_a "
                "igual a ese atributo. Si habla de otro aspecto, usa otro atributo:",
                True,
            )] + [
                Elemento(
                    f"- {sujeto}: " + "; ".join(f"{a} = {v}" for a, v in lista),
                    posicion=i + 1,
                )
                for i, (sujeto, lista) in enumerate(ordenados)
            ],
            "ATRIBUTOS QUE YA EXISTEN",
        )

    hilos = lectura.hilos(con, novela_id)
    vivos: list[str] = []
    if siembras:
        vivos.append("Siembras (marca si el capitulo las planta, las riega o las paga):")
        vivos.extend(f"- [{s['estado']}] {s['elemento']}" for s in siembras)
    if hilos:
        vivos.append(
            "Hilos (refierete a cada uno por su numero; marca si el capitulo lo abre, lo "
            "complica, lo deja latente o lo resuelve):"
        )
        vivos.extend(
            f"- Hilo {i} [{h['tipo']}, {h['estado']}]: {h['conflicto_central']}"
            for i, h in enumerate(hilos, start=1)
        )
    if vivos:
        p.anadir("siembras", "\n".join(vivos), "SIEMBRAS E HILOS VIVOS")

    cuerpo: list[str] = []
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


class Descartes:
    """Lo que el extractor dijo y no se pudo registrar, con el motivo (RF2-PIPE-16).

    Antes cada `continue` perdia el dato sin rastro: el extractor escribia «Dra. Kowalski» y el
    uso de conocimiento desaparecia, asi que la comprobacion de conocimiento no adquirido nunca
    llegaba a verlo. Ahora se cuenta, va a la traza, y los usos descartados vuelven a la puerta
    3 como aviso.
    """

    def __init__(self) -> None:
        self.recuento: dict[str, dict[str, int]] = {}
        self.usos: list[dict[str, Any]] = []
        #: Lo que se registro, pero no donde el extractor dijo (RF2-PIPE-24).
        self.correcciones: dict[str, int] = {}

    def anotar(self, tipo: str, motivo: str) -> None:
        por_motivo = self.recuento.setdefault(tipo, {})
        por_motivo[motivo] = por_motivo.get(motivo, 0) + 1

    @property
    def total(self) -> int:
        return sum(n for m in self.recuento.values() for n in m.values())


def _motivo(eid: int | None, pid: int | None = 0, hid: int | None = 0,
            objeto: int | None = 0) -> str | None:
    """Por que no se puede registrar algo, o None si se puede. 0 significa «no aplica»."""
    if eid is None:
        return "escena_desconocida"
    if pid is None:
        return "personaje_sin_resolver"
    if hid is None:
        return "hecho_sin_resolver"
    if objeto is None:
        return "objeto_sin_resolver"
    return None


def aplicar(
    con: sqlite3.Connection,
    novela_id: int,
    capitulo: int,
    salida: SalidaExtraccion,
    escenas_por_orden: dict[int, int],
    textos: dict[int, str] | None = None,
) -> Descartes:
    """Registra en el grafo todo lo que el texto fijo. Append-only, con escena de origen.

    Devuelve lo que no pudo registrar y por que: nada se descarta en silencio.
    """
    resolvedor = Resolvedor(con, novela_id)
    descartes = Descartes()

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
    def ultimo_hecho(sujeto: str, atributo: str) -> int | None:
        """El hecho vigente mas reciente de ese sujeto y atributo, comparando por claves."""
        fila = con.execute(
            """
            SELECT id FROM hecho_vigente
            WHERE novela_id = ? AND sujeto_clave = ? AND atributo_clave = ?
            ORDER BY id DESC LIMIT 1
            """,
            (novela_id, normalizar(sujeto), normalizar(atributo)),
        ).fetchone()
        return int(fila["id"]) if fila else None

    def valor_vigente(sujeto: str, atributo: str) -> sqlite3.Row | None:
        """El hecho que hoy fija ese sujeto y atributo: vigente y sin sustituir."""
        return con.execute(
            """
            SELECT h.id, h.valor_clave FROM hecho_vigente h
            WHERE h.novela_id = ? AND h.sujeto_clave = ? AND h.atributo_clave = ?
              AND NOT EXISTS (SELECT 1 FROM hecho_vigente s WHERE s.supersede_a = h.id)
            ORDER BY h.id DESC LIMIT 1
            """,
            (novela_id, normalizar(sujeto), normalizar(atributo)),
        ).fetchone()

    # La cita manda sobre el numero de escena (RF2-PIPE-24): si solo esta, literal, en otra
    # escena del capitulo, el hecho es de esa escena.
    prosa = {orden: normalizar(t) for orden, t in (textos or {}).items()}

    def orden_por_cita(declarada: int, cita: str) -> int:
        clave = normalizar(cita)
        if not clave or not prosa or clave in prosa.get(declarada, ""):
            return declarada
        otras = [o for o, t in prosa.items() if clave in t]
        if len(otras) != 1:
            return declarada
        descartes.correcciones["escena_por_cita"] = (
            descartes.correcciones.get("escena_por_cita", 0) + 1
        )
        return otras[0]

    hechos_nuevos: dict[tuple[str, str], int] = {}
    for h in salida.hechos:
        eid = escena(orden_por_cita(h.escena_orden, h.cita))
        if eid is None:
            descartes.anotar("hechos", "escena_desconocida")
            continue
        # Reafirmar el valor vigente no es un hecho nuevo (RF2-PIPE-19): el conocimiento y los
        # usos de la escena apuntan al hecho ya establecido. Si cada reafirmacion creara una
        # fila, un uso posterior quedaria enganchado a una fila que nadie sabe, y la puerta 3
        # veria conocimiento no adquirido donde no lo hay. Un valor antiguo ya sustituido si
        # entra como fila nueva: es justo lo que la puerta tiene que comparar.
        vigente = valor_vigente(h.sujeto_ref, h.atributo)
        if vigente is not None and not h.supersede_a and (
            vigente["valor_clave"] == normalizar(h.valor)
        ):
            hechos_nuevos[(normalizar(h.sujeto_ref), normalizar(h.atributo))] = int(vigente["id"])
            continue
        previo = ultimo_hecho(h.sujeto_ref, h.supersede_a) if h.supersede_a else None
        hid = insertar_hecho(
            con, novela_id=novela_id, escena_id=eid, sujeto_tipo=h.sujeto_tipo,
            sujeto_id=sujeto_id(h.sujeto_tipo, h.sujeto_ref), sujeto_nombre=h.sujeto_ref,
            atributo=h.atributo, valor=h.valor, categoria=h.categoria, cita=h.cita,
            supersede_a=previo,
        )
        hechos_nuevos[(normalizar(h.sujeto_ref), normalizar(h.atributo))] = hid

    def hecho_id(sujeto: str, atributo: str) -> int | None:
        clave = (normalizar(sujeto), normalizar(atributo))
        if clave in hechos_nuevos:
            return hechos_nuevos[clave]
        return ultimo_hecho(sujeto, atributo)

    # --- Conocimiento adquirido y conocimiento usado -------------------------------------
    for c in salida.conocimiento:
        eid, pid, hid = (
            escena(c.escena_orden),
            resolvedor.id_de("personaje", c.personaje_ref),
            hecho_id(c.sujeto_ref, c.atributo),
        )
        motivo = _motivo(eid, pid, hid)
        if motivo:
            descartes.anotar("conocimiento", motivo)
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
        motivo = _motivo(eid, pid, hid)
        if motivo:
            descartes.anotar("usos_de_conocimiento", motivo)
            descartes.usos.append({
                "personaje": u.personaje_ref, "sujeto": u.sujeto_ref, "atributo": u.atributo,
                "escena_orden": u.escena_orden, "escena_id": eid, "motivo": motivo,
            })
            continue
        insertar(
            con, "uso_conocimiento", novela_id=novela_id, personaje_id=pid, hecho_id=hid,
            escena_id=eid,
        )

    # --- Estados -------------------------------------------------------------------------
    for ep in salida.estados_personaje:
        eid, pid = escena(ep.escena_orden), resolvedor.id_de("personaje", ep.personaje_ref)
        motivo = _motivo(eid, pid)
        if motivo:
            descartes.anotar("estados_personaje", motivo)
            continue
        insertar(
            con, "estado_personaje", novela_id=novela_id, personaje_id=pid, escena_id=eid,
            condicion=ep.condicion, salud_fisica=ep.salud_fisica,
            estado_psicologico=ep.estado_psicologico, nivel_confianza=ep.nivel_confianza or None,
        )

    for eo in salida.estados_objeto:
        eid, oid = escena(eo.escena_orden), resolvedor.id_de("objeto", eo.objeto_ref)
        motivo = _motivo(eid, objeto=oid)
        if motivo:
            descartes.anotar("estados_objeto", motivo)
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
        # El orden interno lo pone el extractor, que es quien lee la prosa; nunca se inventa
        # aqui (RF2-PIPE-10). Un evento no dramatizado puede no tenerlo.
        for ev in salida.eventos:
            insertar(
                con, "evento", novela_id=novela_id, linea_de_tiempo_id=int(linea["id"]),
                escena_id=escena(ev.escena_orden), fecha_interna=ev.fecha_interna,
                orden_interno=ev.orden_interno, descripcion=ev.descripcion, tipo=ev.tipo,
                dramatizado=ev.dramatizado,
            )

    # --- Siembras ------------------------------------------------------------------------
    for s in salida.siembras:
        eid = escena(s.escena_orden)
        if eid is None:
            descartes.anotar("siembras", "escena_desconocida")
            continue
        fila = None
        if s.siembra_ref:
            clave = normalizar(s.siembra_ref)
            fila = next(
                (f for f in con.execute(
                    "SELECT id, elemento, sembrada_en_escena_id FROM siembra "
                    "WHERE novela_id = ? ORDER BY id", (novela_id,),
                ).fetchall() if normalizar(f["elemento"]) == clave),
                None,
            )
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

    # --- Hilos (RF2-PIPE-18): el numero es el de la lista que traia el paquete ------------
    hilo_por_numero = {
        i: int(h["hilo_id"]) for i, h in enumerate(lectura.hilos(con, novela_id), start=1)
    }
    for hx in salida.hilos:
        eid = escena(hx.escena_orden)
        hilo_id = hilo_por_numero.get(hx.hilo)
        if eid is None or hilo_id is None:
            descartes.anotar("hilos", "escena_desconocida" if eid is None else "hilo_desconocido")
            continue
        insertar(
            con, "hilo_estado", novela_id=novela_id, hilo_id=hilo_id, escena_id=eid,
            estado=hx.nuevo_estado,
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
            descartes.anotar("entidades_no_reconocidas", "escena_desconocida")
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
    return descartes
