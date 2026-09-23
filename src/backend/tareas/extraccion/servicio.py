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

from compartido.brief import linea_destinatario
from compartido.contexto import Elemento, Paquete, Presupuesto, ajustar
from compartido.grafo import (
    Resolvedor,
    actualizar,
    clave_laxa,
    insertar,
    insertar_hecho,
    lectura,
    normalizar,
)
from compartido.texto import aparece_en, palabras

from .esquemas import PALABRAS_VALOR, SalidaExtraccion

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
    ultimo_dia = lectura.ultimo_dia(con, novela_id)
    brief = lectura.brief(con, novela_id)
    # RF3-PER-03: el protagonista es el destinatario del regalo, y su condicion es lo que
    # comprueba `destinatario_muere` en la puerta 3.
    destinatario = f"\n{linea_destinatario(brief)}" if brief is not None else ""
    p.anadir(
        "instrucciones",
        f"Extrae del capitulo {capitulo} todo lo que el texto afirma. Refierete a cada "
        "elemento por el numero de escena en que aparece.\n"
        f"El ultimo orden_interno registrado en la novela es {ultimo_orden}: todo evento "
        "dramatizado lleva el suyo y continua la escala desde ahi (dos sucesos simultaneos "
        "comparten orden; uno anterior en la cronologia, como un recuerdo, lleva uno menor).\n"
        f"Cada evento dramatizado lleva tambien su dia: dias desde el comienzo de la historia, "
        f"que es el dia 0. El ultimo dia registrado es {ultimo_dia}. Un suceso posterior nunca "
        "cae en un dia anterior."
        + destinatario,
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
    # RF3-PAS-03: el nombre del mundo es canon. En la primera pasada real, el de la propia
    # estacion salio como entidad no reconocida.
    obra = _mundo_y_titulo(con, novela_id)
    if obra:
        inventario.append(Elemento(
            "Mundo y obra (sujeto_tipo 'mundo' o 'novela'): " + ", ".join(obra), True
        ))
    menores = lectura.nombres_menores(con, novela_id, capitulo)
    if menores:
        # RF3-PAS-05: no son canon, pero si reaparecen se registran con la misma grafia.
        inventario.append(Elemento(
            "Nombres menores de capitulos anteriores (no son canon: si reaparecen, van a "
            "entidades_no_reconocidas escritos igual): " + ", ".join(menores),
        ))
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
                "igual a ese atributo. Si habla de otro aspecto, usa otro atributo. Un valor "
                "marcado [COMPUESTO] tiene mas de un dato y no se repite: si el texto vuelve a "
                "hablar de el, registra cada dato en su propio hecho, con supersede_a igual a "
                "ese atributo:",
                True,
            )] + [
                Elemento(
                    f"- {sujeto}: " + "; ".join(
                        f"{a} = {v}" + (" [COMPUESTO]" if _es_compuesto(str(v)) else "")
                        for a, v in lista
                    ),
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


def _es_compuesto(valor: str) -> bool:
    """Un valor vigente de antes de RF3-PAS-01, mas largo de lo que hoy se admite."""
    return len(valor.split()) > PALABRAS_VALOR


#: Un trozo mas corto no dice nada por si mismo: «de», «humedad» o «vegetal» casan con casi
#: cualquier compuesto.
PALABRAS_MINIMAS_DEL_TROZO = 3
_NEGADORES = frozenset({"no", "sin", "nunca", "ni", "jamas"})


def _parte_de_un_compuesto(vigente: str, nuevo: str) -> bool:
    """Si `nuevo` es un trozo de un valor vigente compuesto (spec3, RF3-PAS-01).

    Con el limite de diez palabras, el extractor no puede repetir un valor vigente de
    veinte: se queda con una parte. Esa parte dice lo mismo que el valor, no lo contradice, y
    cuenta como reafirmacion. En la reanudacion de la pasada real, «treinta y un grados y
    ochenta por ciento de humedad» frente al valor entero, con el olor detras, paraba el
    capitulo 3.

    El trozo son palabras completas seguidas del vigente (con los plurales simples de
    `compartido/texto.py`), de tres palabras o mas, y que no vayan detras de un negador: «es
    vegetal» es un trozo de «que no es vegetal» y dice lo contrario.
    """
    if not _es_compuesto(vigente):
        return False
    buscadas = palabras(nuevo)
    presentes = palabras(vigente)
    n = len(buscadas)
    if n < PALABRAS_MINIMAS_DEL_TROZO:
        return False
    return any(
        all(presentes[i + k] & buscadas[k] for k in range(n))
        and not (i > 0 and presentes[i - 1] & _NEGADORES)
        for i in range(len(presentes) - n + 1)
    )


def _mundo_y_titulo(con: sqlite3.Connection, novela_id: int) -> list[str]:
    """El nombre del mundo y el titulo de la novela, sin repetir si coinciden."""
    fila = con.execute(
        "SELECT n.titulo, m.nombre FROM novela n LEFT JOIN mundo m ON m.novela_id = n.id "
        "WHERE n.id = ?",
        (novela_id,),
    ).fetchone()
    if fila is None:
        return []
    nombres: dict[str, str] = {}
    for nombre in (fila["nombre"], fila["titulo"]):
        if nombre:
            nombres.setdefault(clave_laxa(str(nombre)), str(nombre))
    return list(nombres.values())


#: Las tablas cuyos nombres cuentan como canon al registrar entidades no reconocidas.
_TABLAS_DEL_CANON = ("personaje", "lugar", "objeto", "faccion", "sistema_tecnologico")


def _claves_laxas_del_canon(con: sqlite3.Connection, novela_id: int) -> set[str]:
    """Las claves laxas de todo nombre del canon, del mundo y del titulo (RF3-PAS-04)."""
    claves = {clave_laxa(n) for n in _mundo_y_titulo(con, novela_id)}
    for tabla in _TABLAS_DEL_CANON:
        claves.update(
            clave_laxa(str(f[0])) for f in con.execute(
                f"SELECT nombre FROM {tabla} WHERE novela_id = ?", (novela_id,)
            )
        )
    return claves


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
            SELECT h.id, h.valor_clave, h.escena_id FROM hecho_vigente h
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

    # En orden de escena, no de lista (RF2-PIPE-25): una reafirmacion de la escena 1 se compara
    # con lo que valia en la escena 1, no con la sustitucion de la escena 2.
    por_escena = sorted(
        ((orden_por_cita(h.escena_orden, h.cita), h) for h in salida.hechos),
        key=lambda par: par[0],
    )
    for orden_hecho, h in por_escena:
        eid = escena(orden_hecho)
        if eid is None:
            descartes.anotar("hechos", "escena_desconocida")
            continue
        if h.conducta:
            # Ser conducta es del atributo, no del valor: se marca aunque el hecho sea una
            # reafirmacion que no crea fila (RF2-PIPE-29).
            con.execute(
                "INSERT OR IGNORE INTO atributo_conducta (novela_id, escena_id, sujeto_clave, "
                "atributo_clave) VALUES (?,?,?,?)",
                (novela_id, eid, normalizar(h.sujeto_ref), normalizar(h.atributo)),
            )
        # Reafirmar el valor vigente no es un hecho nuevo (RF2-PIPE-19): el conocimiento y los
        # usos de la escena apuntan al hecho ya establecido. Si cada reafirmacion creara una
        # fila, un uso posterior quedaria enganchado a una fila que nadie sabe, y la puerta 3
        # veria conocimiento no adquirido donde no lo hay. Un valor antiguo ya sustituido si
        # entra como fila nueva: es justo lo que la puerta tiene que comparar.
        vigente = valor_vigente(h.sujeto_ref, h.atributo)
        if vigente is not None and not h.supersede_a and (
            vigente["valor_clave"] == normalizar(h.valor)
            or _parte_de_un_compuesto(str(vigente["valor_clave"]), h.valor)
        ):
            # Pero la escena lo USA, y eso es lo que el bloque 8 necesita saber para regenerar
            # solo lo afectado por un cambio (RF3-BIB-01). Antes se perdia sin rastro.
            if int(vigente["escena_id"]) != eid:
                con.execute(
                    "INSERT OR IGNORE INTO hecho_uso (novela_id, hecho_id, escena_id, via, cita) "
                    "VALUES (?, ?, ?, 'reafirma', ?)",
                    (novela_id, int(vigente["id"]), eid, h.cita or None),
                )
            continue
        previo = ultimo_hecho(h.sujeto_ref, h.supersede_a) if h.supersede_a else None
        insertar_hecho(
            con, novela_id=novela_id, escena_id=eid, sujeto_tipo=h.sujeto_tipo,
            sujeto_id=sujeto_id(h.sujeto_tipo, h.sujeto_ref), sujeto_nombre=h.sujeto_ref,
            atributo=h.atributo, valor=h.valor, categoria=h.categoria, cita=h.cita,
            supersede_a=previo,
        )

    def hecho_id(sujeto: str, atributo: str, eid: int | None) -> int | None:
        """El hecho vigente EN esa escena (RF2-PIPE-25): el ultimo fijado en una escena de
        ordinal menor o igual. Los del capitulo ya estan insertados, asi que basta el grafo."""
        if eid is None:
            return None
        fila = con.execute(
            """
            SELECT h.id FROM hecho_vigente h
            JOIN escena_ordinal o ON o.escena_id = h.escena_id
            WHERE h.novela_id = ? AND h.sujeto_clave = ? AND h.atributo_clave = ?
              AND o.ordinal <= (SELECT ordinal FROM escena_ordinal WHERE escena_id = ?)
            ORDER BY o.ordinal DESC, h.id DESC LIMIT 1
            """,
            (novela_id, normalizar(sujeto), normalizar(atributo), eid),
        ).fetchone()
        return int(fila["id"]) if fila else None

    # --- Conocimiento adquirido y conocimiento usado -------------------------------------
    for c in salida.conocimiento:
        eid, pid, hid = (
            escena(c.escena_orden),
            resolvedor.id_de("personaje", c.personaje_ref),
            hecho_id(c.sujeto_ref, c.atributo, escena(c.escena_orden)),
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
            hecho_id(u.sujeto_ref, u.atributo, escena(u.escena_orden)),
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
                dia=ev.dia, orden_interno=ev.orden_interno, descripcion=ev.descripcion,
                tipo=ev.tipo, dramatizado=ev.dramatizado,
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
    # Salvo que sea una variante de algo del canon, del mundo o del titulo, o un nombre que el
    # capitulo ya registro, con esa u otra grafia (RF3-PAS-04). No se pierde: queda en la traza.
    # Se compara contra las claves laxas del canon y no con el resolvedor, que anotaria cada
    # intento en sus listas y contaria dos veces lo mismo en la traza.
    canon_laxo = _claves_laxas_del_canon(con, novela_id)
    ya_registradas: set[str] = set()
    for en in salida.entidades_no_reconocidas:
        eid = escena(en.escena_orden)
        if eid is None:
            descartes.anotar("entidades_no_reconocidas", "escena_desconocida")
            continue
        clave = clave_laxa(en.nombre)
        del_canon = clave in canon_laxo
        if del_canon or clave in ya_registradas:
            motivo = "entidad_del_canon" if del_canon else "entidad_repetida"
            descartes.correcciones[motivo] = descartes.correcciones.get(motivo, 0) + 1
            continue
        ya_registradas.add(clave)
        insertar(
            con, "entidad_no_reconocida", novela_id=novela_id, escena_id=eid, nombre=en.nombre,
            contexto=en.contexto,
        )
    if resolvedor.por_variante:
        descartes.correcciones["nombre_por_variante"] = len(resolvedor.por_variante)
    # Un valor de mas de un dato entra igual: se cuenta aqui y la puerta 3 avisa (RF3-PAS-01).
    if salida.valores_largos:
        descartes.correcciones["valor_largo"] = len(salida.valores_largos)

    # --- Lo que la prosa usa sin que el extractor lo diga (RF3-BIB-01) ---------------------
    registrar_menciones(con, novela_id, escenas_por_orden, textos or {})

    # --- Los dos resumenes con los que se construye el estado rodante ----------------------
    cap = lectura.capitulo(con, novela_id, capitulo)
    if cap is not None:
        actualizar(
            con, "capitulo", int(cap["id"]),
            resumen=salida.resumen, resumen_breve=salida.resumen_breve,
        )
    return descartes


#: Hechos cuyo valor es un literal que la prosa repite tal cual: un nombre, una fecha, una
#: distancia o una cifra. «Castano corto» o «alta» aparecen en cualquier descripcion, y buscarlos
#: llenaria la tabla de usos falsos.
_SQL_BUSCABLES = """
SELECT h.id, h.valor, o.ordinal,
       (SELECT MIN(os.ordinal) FROM hecho_vigente s
        JOIN escena_ordinal os ON os.escena_id = s.escena_id
        WHERE s.supersede_a = h.id) AS sustituido_en
FROM hecho_vigente h
JOIN escena_ordinal o ON o.escena_id = h.escena_id
WHERE h.novela_id = ?
  AND (h.categoria IN ('nombre', 'fecha', 'distancia') OR h.valor GLOB '*[0-9]*')
"""
_LETRAS_MINIMAS = 3


def _buscable(valor: str) -> bool:
    return len(normalizar(valor)) >= _LETRAS_MINIMAS or any(c.isdigit() for c in valor)


def registrar_menciones(
    con: sqlite3.Connection,
    novela_id: int,
    escenas_por_orden: dict[int, int],
    textos: dict[int, str],
) -> int:
    """La via `menciona` de `hecho_uso`: el valor exacto de un hecho vigente en una escena.

    Es el segundo metodo que mira el texto (regla 3 de validators.md): la reafirmacion depende
    de que el extractor repita el hecho, y esto no. Solo cuentan los hechos establecidos en una
    escena ANTERIOR: la propia no es un uso, y una posterior todavia no existia. Y un hecho solo
    mientras no este sustituido en ese punto de la historia: repetir un valor viejo despues de
    la sustitucion no es usarlo. Devuelve cuantos usos registro.
    """
    candidatos = [
        (
            int(f["id"]), str(f["valor"]), int(f["ordinal"]),
            int(f["sustituido_en"]) if f["sustituido_en"] is not None else None,
        )
        for f in con.execute(_SQL_BUSCABLES, (novela_id,)).fetchall()
        if _buscable(str(f["valor"]))
    ]
    if not candidatos:
        return 0
    registrados = 0
    for orden, texto in textos.items():
        eid = escenas_por_orden.get(int(orden))
        if eid is None or not texto:
            continue
        ordinal = int(con.execute(
            "SELECT ordinal FROM escena_ordinal WHERE escena_id = ?", (eid,)
        ).fetchone()[0])
        presentes = palabras(texto)
        for hid, valor, ordinal_hecho, sustituido_en in candidatos:
            vigente_aqui = ordinal_hecho < ordinal and (
                sustituido_en is None or ordinal < sustituido_en
            )
            if vigente_aqui and aparece_en(presentes, valor):
                cur = con.execute(
                    "INSERT OR IGNORE INTO hecho_uso (novela_id, hecho_id, escena_id, via, cita) "
                    "VALUES (?, ?, ?, 'menciona', ?)",
                    (novela_id, hid, eid, valor),
                )
                registrados += cur.rowcount
    return registrados
