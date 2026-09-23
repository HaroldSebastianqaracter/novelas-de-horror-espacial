"""Puerta 3 — continuidad (RF-PIPE-12). Es SQL, no juicio.

Esta es la puerta que PARA el pipeline. Un conflicto de continuidad no se marca ni se
acumula: se detiene la generacion y se espera a un humano, porque nunca se acumula deuda
narrativa silenciosa. La fricción es informacion: si el sistema se detiene catorce veces en
el primer acto, el problema no son las paradas, es que el canon estaba mal especificado.

Todas las comprobaciones son consultas exactas sobre el grafo. Ninguna pregunta a un modelo,
y ninguna depende del indice vectorial: una puerta que a veces falla no es una puerta.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable
from typing import Any

from compartido.grafo import clave_laxa, lectura, normalizar
from compartido.puerta_base import Conflicto, ResultadoPuerta

POSTURAS_QUE_HABILITAN = ("sabe", "cree", "sospecha", "cree_version_falsa")


def _filas(con: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    return [dict(f) for f in con.execute(sql, params).fetchall()]


# --- 1. Continuidad factual (RF2-PIPE-11, RF2-PIPE-12) --------------------------------------
# Dos hechos vigentes del mismo sujeto y atributo con distinto valor se contradicen, salvo
# que el anterior este SUSTITUIDO por otro hecho vigente de ordinal menor o igual al del
# nuevo. Eso hace transitiva la cadena herida -> infectada -> cicatrizada: cada eslabon
# sustituye al anterior y ninguno choca con los de atras.
#
# Todo se compara por las claves normalizadas que calcula `insertar_hecho`, nunca con LOWER(),
# que en SQLite solo pliega ASCII: «Ámbar» y «ámbar» son el mismo valor.
#
# Cada par sale una sola vez: si los dos hechos estan en la misma escena, el de id mayor es el
# «nuevo».
_SQL_CONTRADICCION = """
SELECT n.id AS hecho_nuevo_id, n.atributo, n.valor AS valor_nuevo, n.cita AS cita_nueva,
       n.sujeto_tipo, n.sujeto_nombre, n.escena_id AS escena_nueva,
       v.id AS hecho_previo_id, v.valor AS valor_previo, v.cita AS cita_previa,
       v.escena_id AS escena_previa, opr.capitulo_numero AS capitulo_previo,
       onu.capitulo_numero AS capitulo_nuevo,
       EXISTS (SELECT 1 FROM atributo_conducta ac
               JOIN escena_ordinal oa ON oa.escena_id = ac.escena_id
               WHERE ac.novela_id = n.novela_id AND ac.sujeto_clave = n.sujeto_clave
                 AND ac.atributo_clave = n.atributo_clave
                 AND oa.ordinal <= onu.ordinal) AS es_conducta
FROM hecho_vigente n
JOIN hecho_vigente v
  ON v.novela_id = n.novela_id
 AND v.sujeto_tipo = n.sujeto_tipo
 AND IFNULL(v.sujeto_id, -1) = IFNULL(n.sujeto_id, -1)
 AND v.sujeto_clave = n.sujeto_clave
 AND v.atributo_clave = n.atributo_clave
 AND v.valor_clave <> n.valor_clave
JOIN escena_ordinal onu ON onu.escena_id = n.escena_id
JOIN escena_ordinal opr ON opr.escena_id = v.escena_id
WHERE n.novela_id = ?
  AND onu.capitulo_numero = ?
  AND (opr.ordinal < onu.ordinal OR (opr.ordinal = onu.ordinal AND v.id < n.id))
  AND NOT EXISTS (
        SELECT 1 FROM hecho_vigente s
        JOIN escena_ordinal os ON os.escena_id = s.escena_id
        WHERE s.supersede_a = v.id AND os.ordinal <= onu.ordinal)
"""

# --- 2. Conocimiento no adquirido (RF2-PIPE-21, RF2-PIPE-27) -------------------------------
# Un personaje usa informacion que todavia no ha recibido. Es la fuente numero uno de
# errores de continuidad en obra larga. Recibirla es tener un estado de conocimiento que la
# habilite, haber estado (reparto o POV) en la escena donde el texto la fijo, o que otro
# miembro de su faccion la supiera al terminar un capitulo anterior: entre capitulos, lo que
# sabe la cuadrilla lo sabe cada uno de la cuadrilla.
_SQL_CONOCIMIENTO = f"""
SELECT u.id AS uso_id, p.nombre AS personaje, h.atributo, h.valor, h.sujeto_nombre,
       u.escena_id, c.numero AS capitulo, h.id AS hecho_id, p.id AS personaje_id
FROM uso_conocimiento u
JOIN personaje p       ON p.id = u.personaje_id
JOIN hecho_vigente h   ON h.id = u.hecho_id
JOIN escena_ordinal ou ON ou.escena_id = u.escena_id
JOIN escena e          ON e.id = u.escena_id
JOIN capitulo c        ON c.id = e.capitulo_id
WHERE u.novela_id = ? AND c.numero = ?
  AND NOT EXISTS (
        SELECT 1 FROM estado_conocimiento ec
        JOIN escena_ordinal oc ON oc.escena_id = ec.escena_id
        WHERE ec.personaje_id = u.personaje_id
          AND ec.hecho_id = u.hecho_id
          AND ec.postura IN {POSTURAS_QUE_HABILITAN}
          AND oc.ordinal <= ou.ordinal)
  AND NOT EXISTS (
        SELECT 1 FROM escena eh
        JOIN escena_ordinal oh ON oh.escena_id = eh.id
        WHERE eh.id = h.escena_id
          AND oh.ordinal <= ou.ordinal
          AND (eh.pov_id = u.personaje_id OR EXISTS (
                SELECT 1 FROM escena_personaje sp
                WHERE sp.escena_id = eh.id AND sp.personaje_id = u.personaje_id)
            -- Quien actua en la escena esta en ella aunque la escaleta no lo pusiera
            -- (RF2-PIPE-30).
            OR EXISTS (SELECT 1 FROM uso_conocimiento ua
                       WHERE ua.escena_id = eh.id AND ua.personaje_id = u.personaje_id)
            OR EXISTS (SELECT 1 FROM estado_personaje ep
                       WHERE ep.escena_id = eh.id AND ep.personaje_id = u.personaje_id)))
  AND NOT EXISTS (
        SELECT 1 FROM personaje otro
        WHERE otro.faccion_id = p.faccion_id AND otro.id <> p.id
          AND (EXISTS (
                SELECT 1 FROM estado_conocimiento ec2
                JOIN escena_ordinal o2 ON o2.escena_id = ec2.escena_id
                WHERE ec2.personaje_id = otro.id AND ec2.hecho_id = u.hecho_id
                  AND ec2.postura IN {POSTURAS_QUE_HABILITAN}
                  AND o2.capitulo_numero < ou.capitulo_numero)
            OR EXISTS (
                SELECT 1 FROM escena eh2
                JOIN escena_ordinal oh2 ON oh2.escena_id = eh2.id
                WHERE eh2.id = h.escena_id AND oh2.capitulo_numero < ou.capitulo_numero
                  AND (eh2.pov_id = otro.id OR EXISTS (
                        SELECT 1 FROM escena_personaje sp2
                        WHERE sp2.escena_id = eh2.id AND sp2.personaje_id = otro.id)))))
"""

# --- 3. Sorpresa imposible (aviso) --------------------------------------------------------
_SQL_SORPRESA = """
SELECT ec.id AS conocimiento_id, p.nombre AS personaje, h.atributo, ec.via,
       ec.escena_id, c.numero AS capitulo
FROM estado_conocimiento ec
JOIN personaje p       ON p.id = ec.personaje_id
JOIN hecho_vigente h   ON h.id = ec.hecho_id
JOIN escena_ordinal oc ON oc.escena_id = ec.escena_id
JOIN escena e          ON e.id = ec.escena_id
JOIN capitulo c        ON c.id = e.capitulo_id
WHERE ec.novela_id = ? AND c.numero = ?
  AND ec.via IN ('presencio','se_lo_contaron')
  AND EXISTS (
        SELECT 1 FROM estado_conocimiento p2
        JOIN escena_ordinal o2 ON o2.escena_id = p2.escena_id
        WHERE p2.personaje_id = ec.personaje_id
          AND p2.hecho_id = ec.hecho_id
          AND p2.postura = 'sabe'
          AND o2.ordinal < oc.ordinal)
"""

# --- 4a. Presencia imposible: personaje muerto que reaparece -------------------------------
# La muerte es un dato cerrado, `estado_personaje.condicion`, y no una busqueda en el texto
# libre de la salud: «casi muerto» no es una muerte y «fallecida» si. Cuenta la ULTIMA
# condicion registrada antes de la escena, de modo que un desaparecido que vuelve no para.
_SQL_MUERTO = """
SELECT p.nombre AS personaje, ult.escena_id AS escena_muerte,
       om.capitulo_numero AS capitulo_muerte, e.id AS escena_reaparicion, c.numero AS capitulo
FROM escena_personaje sp
JOIN personaje p       ON p.id = sp.personaje_id
JOIN escena e          ON e.id = sp.escena_id
JOIN capitulo c        ON c.id = e.capitulo_id
JOIN escena_ordinal oe ON oe.escena_id = e.id
JOIN estado_personaje ult ON ult.id = (
        SELECT ep.id FROM estado_personaje ep
        JOIN escena_ordinal o2 ON o2.escena_id = ep.escena_id
        WHERE ep.personaje_id = sp.personaje_id AND ep.condicion IS NOT NULL
          AND o2.ordinal < oe.ordinal
        ORDER BY o2.ordinal DESC, ep.id DESC LIMIT 1)
JOIN escena_ordinal om ON om.escena_id = ult.escena_id
WHERE e.novela_id = ? AND c.numero = ?
  AND ult.condicion = 'muerto'
  AND e.analepsis = 0
"""

# --- 4b. Presencia imposible: dos lugares a la vez -----------------------------------------
# SIMULTANEO significa mismo `orden_interno`, no misma fecha. Comparar por fecha daria un
# falso positivo en cuanto dos escenas del mismo dia ocurran en sitios distintos, que es lo
# normal: dentro de un dia el tiempo pasa. El `orden_interno` es el ordinal estricto de la
# cronologia interna, y dos sucesos con el mismo ordinal si son a la vez.
_SQL_UBICUIDAD = """
SELECT p.nombre AS personaje, ev1.fecha_interna, ev1.orden_interno,
       l1.nombre AS lugar_a, l2.nombre AS lugar_b, l1.id AS lugar_a_id, l2.id AS lugar_b_id,
       e1.id AS escena_a, e2.id AS escena_b, c1.numero AS capitulo
FROM escena_personaje sp1
JOIN escena_personaje sp2 ON sp2.personaje_id = sp1.personaje_id
                         AND sp2.escena_id <> sp1.escena_id
JOIN personaje p  ON p.id = sp1.personaje_id
JOIN escena e1    ON e1.id = sp1.escena_id
JOIN escena e2    ON e2.id = sp2.escena_id
JOIN capitulo c1  ON c1.id = e1.capitulo_id
JOIN lugar l1     ON l1.id = e1.lugar_id
JOIN lugar l2     ON l2.id = e2.lugar_id
JOIN evento ev1   ON ev1.escena_id = e1.id AND ev1.dramatizado = 1
JOIN evento ev2   ON ev2.escena_id = e2.id AND ev2.dramatizado = 1
WHERE e1.novela_id = ? AND c1.numero = ?
  AND e1.lugar_id <> e2.lugar_id
  AND ev1.orden_interno IS NOT NULL AND ev2.orden_interno IS NOT NULL
  AND ev1.orden_interno = ev2.orden_interno
  AND e1.id < e2.id
"""

# --- 5. Objeto sin traslado (RF2-PIPE-28) ---------------------------------------------------
# Un objeto que lleva alguien viaja con el: si su poseedor esta en la escena, no hay traslado
# que registrar.
_SQL_OBJETO = """
SELECT o.nombre AS objeto, l.nombre AS lugar_escena, lu.nombre AS ultima_ubicacion,
       e.id AS escena_id, c.numero AS capitulo, l.id AS lugar_escena_id,
       lu.id AS ultima_ubicacion_id
FROM escena_objeto eo
JOIN objeto o    ON o.id = eo.objeto_id
JOIN escena e    ON e.id = eo.escena_id
JOIN capitulo c  ON c.id = e.capitulo_id
JOIN lugar l     ON l.id = e.lugar_id
JOIN escena_ordinal oe ON oe.escena_id = e.id
JOIN estado_objeto ult ON ult.id = (
        SELECT eo2.id FROM estado_objeto eo2
        JOIN escena_ordinal o2 ON o2.escena_id = eo2.escena_id
        WHERE eo2.objeto_id = eo.objeto_id AND o2.ordinal < oe.ordinal
        ORDER BY o2.ordinal DESC, eo2.id DESC LIMIT 1)
LEFT JOIN lugar lu ON lu.id = ult.ubicacion_lugar_id
WHERE e.novela_id = ? AND c.numero = ?
  AND ult.ubicacion_lugar_id IS NOT NULL
  AND ult.ubicacion_lugar_id <> e.lugar_id
  AND NOT EXISTS (SELECT 1 FROM estado_objeto nu
                  WHERE nu.objeto_id = eo.objeto_id AND nu.escena_id = e.id)
  AND NOT (ult.poseedor_id IS NOT NULL AND (e.pov_id = ult.poseedor_id OR EXISTS (
            SELECT 1 FROM escena_personaje sp
            WHERE sp.escena_id = e.id AND sp.personaje_id = ult.poseedor_id)))
"""

# --- 6. Coherencia temporal ----------------------------------------------------------------
_SQL_TEMPORAL = """
WITH esc AS (
  SELECT e.id AS escena_id, oe.ordinal, c.numero AS capitulo, e.analepsis,
         MIN(ev.orden_interno) AS min_orden, MAX(ev.orden_interno) AS max_orden,
         MIN(ev.fecha_interna) AS fecha
  FROM escena e
  JOIN capitulo c        ON c.id = e.capitulo_id
  JOIN escena_ordinal oe ON oe.escena_id = e.id
  JOIN evento ev         ON ev.escena_id = e.id
                        AND ev.dramatizado = 1 AND ev.orden_interno IS NOT NULL
  WHERE e.novela_id = ?
  GROUP BY e.id
)
SELECT a.escena_id, a.capitulo, a.min_orden, a.fecha,
       (SELECT MAX(b.max_orden) FROM esc b
         WHERE b.ordinal < a.ordinal AND b.analepsis = 0) AS max_previo
FROM esc a
WHERE a.capitulo = ? AND a.analepsis = 0
  AND (SELECT MAX(b.max_orden) FROM esc b
        WHERE b.ordinal < a.ordinal AND b.analepsis = 0) > a.min_orden
"""

# --- 6b. El dia y el orden no se contradicen (RF3-BIB-09) ---------------------------------
# Dos datos que declara el extractor, comparados entre si: si un evento va antes en orden
# interno, no puede caer en un dia posterior, y dos sucesos simultaneos (mismo orden) caen el
# mismo dia. Al menos uno de los dos es de este capitulo.
#
# Como en `coherencia_temporal`, solo se comparan eventos dramatizados fuera de una analepsis.
# Los antecedentes del mundo llevan un orden negativo que el extractor no ve, y el orden de un
# recuerdo respecto a sucesos de capitulos lejanos tampoco: compararlos daba choques que el
# extractor no podia evitar. Esos pares los comprueba Lean (bloque 9) por el dia.
_SQL_DIA_CONTRA_ORDEN = """
SELECT a.id AS evento_id, a.descripcion, a.dia, a.orden_interno, a.escena_id,
       b.id AS otro_id, b.descripcion AS otra_descripcion, b.dia AS otro_dia,
       b.orden_interno AS otro_orden, b.escena_id AS otra_escena_id,
       oa.capitulo_numero AS capitulo_evento
FROM evento a
JOIN evento b ON b.novela_id = a.novela_id AND b.id <> a.id
JOIN escena ea ON ea.id = a.escena_id AND ea.analepsis = 0
JOIN escena eb ON eb.id = b.escena_id AND eb.analepsis = 0
JOIN escena_ordinal oa ON oa.escena_id = a.escena_id
JOIN escena_ordinal ob ON ob.escena_id = b.escena_id
WHERE a.novela_id = :novela
  AND (oa.capitulo_numero = :capitulo OR ob.capitulo_numero = :capitulo)
  AND a.dramatizado = 1 AND b.dramatizado = 1
  AND a.dia IS NOT NULL AND b.dia IS NOT NULL
  AND a.orden_interno IS NOT NULL AND b.orden_interno IS NOT NULL
  AND ((b.orden_interno < a.orden_interno AND b.dia > a.dia)
       OR (b.orden_interno = a.orden_interno AND b.dia <> a.dia AND b.id < a.id))
"""

_SQL_ENTIDADES = """
SELECT en.nombre, en.contexto, en.escena_id, c.numero AS capitulo
FROM entidad_no_reconocida en
JOIN escena e   ON e.id = en.escena_id
JOIN capitulo c ON c.id = e.capitulo_id
WHERE en.novela_id = ? AND c.numero = ? AND en.parada_id IS NULL
"""


def _mismo_sitio(con: sqlite3.Connection, novela_id: int) -> Callable[[int, int], bool]:
    """Dos lugares son el mismo sitio si son el mismo o uno contiene al otro (RF2-PIPE-26)."""
    padre = {
        int(f["id"]): (int(f["dentro_de_id"]) if f["dentro_de_id"] is not None else None)
        for f in con.execute(
            "SELECT id, dentro_de_id FROM lugar WHERE novela_id = ?", (novela_id,)
        )
    }

    def contenedores(lugar: int) -> set[int]:
        vistos = {lugar}
        actual = padre.get(lugar)
        while actual is not None and actual not in vistos:
            vistos.add(actual)
            actual = padre.get(actual)
        return vistos

    def mismo(a: int, b: int) -> bool:
        return a in contenedores(b) or b in contenedores(a)

    return mismo


def evaluar(
    con: sqlite3.Connection,
    novela_id: int,
    capitulo: int,
    *,
    textos: dict[int, str] | None = None,
    usos_descartados: list[dict[str, Any]] | None = None,
) -> ResultadoPuerta:
    """Corre la puerta 3 sobre un capitulo ya extraido, dentro de la transaccion abierta.

    Con `textos` (la prosa por numero de escena) anade los avisos de las busquedas dirigidas
    (RF2-PIPE-17); con `usos_descartados`, un aviso por cada uso de conocimiento que el
    extractor dijo y no se pudo registrar (RF2-PIPE-16).
    """
    conflictos: list[Conflicto] = []
    p = (novela_id, capitulo)
    mismo_sitio = _mismo_sitio(con, novela_id)

    for f in _filas(con, _SQL_CONTRADICCION, p):
        # Romper un habito es un recurso, no un error: aviso (RF2-PIPE-29).
        conducta = bool(f.pop("es_conducta"))
        conflictos.append(Conflicto(
            comprobacion="continuidad_factual", aviso=conducta,
            descripcion=(
                f"'{f['sujeto_nombre']}' tiene '{f['atributo']}' = '{f['valor_nuevo']}', pero en "
                f"el capitulo {f['capitulo_previo']} quedo establecido como '{f['valor_previo']}'."
                + (" Es una conducta: puede ser un habito roto a proposito." if conducta else "")
            ),
            escena_id=f["escena_nueva"], capitulo=capitulo, datos=f,
        ))

    for f in _filas(con, _SQL_CONOCIMIENTO, p):
        conflictos.append(Conflicto(
            comprobacion="conocimiento_no_adquirido",
            descripcion=(
                f"{f['personaje']} actua sobre '{f['sujeto_nombre']}: {f['atributo']} = "
                f"{f['valor']}' sin haberlo recibido en ninguna escena anterior."
            ),
            escena_id=f["escena_id"], capitulo=capitulo, datos=f,
        ))

    for f in _filas(con, _SQL_SORPRESA, p):
        conflictos.append(Conflicto(
            comprobacion="sorpresa_imposible", aviso=True,
            descripcion=(
                f"{f['personaje']} se entera de '{f['atributo']}' por {f['via']}, y ya lo sabia."
            ),
            escena_id=f["escena_id"], capitulo=capitulo, datos=f,
        ))

    for f in _filas(con, _SQL_MUERTO, p):
        conflictos.append(Conflicto(
            comprobacion="presencia_imposible",
            descripcion=(
                f"{f['personaje']} aparece en una escena posterior a su muerte, registrada en "
                f"el capitulo {f['capitulo_muerte']}."
            ),
            escena_id=f["escena_reaparicion"], capitulo=capitulo, datos=f,
        ))

    for f in _filas(con, _SQL_UBICUIDAD, p):
        if mismo_sitio(f["lugar_a_id"], f["lugar_b_id"]):
            continue
        conflictos.append(Conflicto(
            comprobacion="presencia_imposible",
            descripcion=(
                f"{f['personaje']} esta en '{f['lugar_a']}' y en '{f['lugar_b']}' en el mismo "
                f"momento de la cronologia ({f['fecha_interna']}, orden "
                f"{f['orden_interno']})."
            ),
            escena_id=f["escena_a"], capitulo=capitulo, datos=f,
        ))

    for f in _filas(con, _SQL_OBJETO, p):
        if mismo_sitio(f["lugar_escena_id"], f["ultima_ubicacion_id"]):
            continue
        conflictos.append(Conflicto(
            comprobacion="objeto_sin_traslado",
            descripcion=(
                f"'{f['objeto']}' aparece en '{f['lugar_escena']}' y su ultima ubicacion "
                f"registrada era '{f['ultima_ubicacion']}', sin traslado."
            ),
            escena_id=f["escena_id"], capitulo=capitulo, datos=f,
        ))

    for f in _filas(con, _SQL_TEMPORAL, p):
        conflictos.append(Conflicto(
            comprobacion="coherencia_temporal",
            descripcion=(
                f"La escena retrocede en el tiempo (orden interno {f['min_orden']} tras "
                f"{f['max_previo']}, fecha '{f['fecha']}') y no esta marcada como analepsis."
            ),
            escena_id=f["escena_id"], capitulo=capitulo, datos=f,
        ))

    # Cada par sale una vez: `a` es siempre el de orden mayor, asi que un par no se repite al
    # reves. El recuerdo que el capitulo coloca antes de un suceso ya escrito tambien sale.
    for f in [dict(x) for x in con.execute(
        _SQL_DIA_CONTRA_ORDEN, {"novela": novela_id, "capitulo": capitulo}
    ).fetchall()]:
        simultaneos = f["orden_interno"] == f["otro_orden"]
        conflictos.append(Conflicto(
            comprobacion="dia_contra_orden",
            descripcion=(
                f"«{f['descripcion'][:60]}» y «{f['otra_descripcion'][:60]}» son simultaneos "
                f"(orden {f['orden_interno']}) y caen en dias distintos ({f['dia']} y "
                f"{f['otro_dia']})."
                if simultaneos else
                f"«{f['descripcion'][:60]}» va despues en la cronologia (orden "
                f"{f['orden_interno']}) que «{f['otra_descripcion'][:60]}» (orden "
                f"{f['otro_orden']}), pero cae en el dia {f['dia']}, antes que el dia "
                f"{f['otro_dia']}."
            ),
            escena_id=(
                f["escena_id"] if f["capitulo_evento"] == capitulo else f["otra_escena_id"]
            ),
            capitulo=capitulo, datos=f,
        ))

    # Un aviso por nombre nuevo (RF3-PAS-06): el que ya salio en un capitulo anterior, el autor
    # ya lo vio. En la primera pasada real, 50 avisos para 15 nombres tapaban los que importan.
    ya_vistos = {clave_laxa(n) for n in lectura.nombres_menores(con, novela_id, capitulo)}
    for f in _filas(con, _SQL_ENTIDADES, p):
        if clave_laxa(str(f["nombre"])) in ya_vistos:
            continue
        conflictos.append(Conflicto(
            # Aviso (RF2-PIPE-22): el redactor inventa detalles menores como cualquier
            # novelista, y quedan registrados para que el autor los revise.
            comprobacion="entidad_fuera_de_canon", aviso=True,
            descripcion=(
                f"El texto usa '{f['nombre']}', que no estaba en el paquete: el redactor "
                "invento una entidad fuera del canon."
            ),
            escena_id=f["escena_id"], capitulo=capitulo, datos=f,
        ))

    for u in usos_descartados or []:
        conflictos.append(Conflicto(
            comprobacion="conocimiento_sin_comprobar", aviso=True, capitulo=capitulo,
            escena_id=u.get("escena_id"),
            descripcion=(
                f"{u['personaje']} usa '{u['sujeto']}: {u['atributo']}' en la escena "
                f"{u['escena_orden']} y no se pudo registrar ({u['motivo']}): ninguna consulta "
                "ha comprobado que lo supiera."
            ),
            datos=dict(u),
        ))

    if textos:
        conflictos.extend(busquedas_dirigidas(con, novela_id, capitulo, textos))

    conflictos.extend(_destinatario_muere(con, novela_id, capitulo))
    return ResultadoPuerta(puerta=3, conflictos=conflictos)


def _destinatario_muere(
    con: sqlite3.Connection, novela_id: int, capitulo: int
) -> list[Conflicto]:
    """RF3-PER-04: el destinatario del regalo nunca muere (decision entrevistada)."""
    brief = lectura.brief(con, novela_id)
    if brief is None or brief.destinatario.nombre is None:
        return []
    return [
        Conflicto(
            comprobacion="destinatario_muere", capitulo=capitulo, escena_id=f["escena_id"],
            descripcion=(
                f"«{f['nombre']}» es el destinatario del regalo y muere en la escena "
                f"{f['orden']}. El destinatario sobrevive siempre."
            ),
            datos=dict(f),
        )
        for f in _filas(con, """
            SELECT p.nombre, ep.escena_id, e.orden
            FROM estado_personaje ep
            JOIN personaje p ON p.id = ep.personaje_id
            JOIN escena e    ON e.id = ep.escena_id
            JOIN capitulo c  ON c.id = e.capitulo_id
            WHERE ep.novela_id = ? AND c.numero = ? AND ep.condicion = 'muerto'
              AND p.nombre_clave = ?
        """, (novela_id, capitulo, normalizar(brief.destinatario.nombre)))
    ]


# --- Busquedas dirigidas sobre la prosa: el segundo metodo que mira el texto (RF2-PIPE-17) ----
# Todas las comprobaciones de arriba consultan el grafo, y el grafo solo tiene lo que el
# extractor registro. Estas miran la prosa y la comparan con lo registrado: es la regla 3 de
# validators.md, con picaresca antes que con un juez. Son AVISOS: una escena puede nombrar a
# alguien sin que haya nada que extraer, y lo que miden es la cobertura del extractor. Su
# punto ciego: rasgos sin nombre propio ni cifra, alias y pronombres.

_CIFRA = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)?(?![\w])")
_LONGITUD_MINIMA_NOMBRE = 3


def _aparece(texto_normalizado: str, nombre: str) -> bool:
    clave = normalizar(nombre)
    if len(clave) < _LONGITUD_MINIMA_NOMBRE:
        return False
    return re.search(rf"(?<!\w){re.escape(clave)}(?!\w)", texto_normalizado) is not None


def _escenas(con: sqlite3.Connection, novela_id: int, capitulo: int) -> list[dict[str, Any]]:
    return [dict(f) for f in con.execute(
        """
        SELECT e.id, e.orden, e.lugar_id, e.analepsis, eo.ordinal
        FROM escena e
        JOIN capitulo c        ON c.id = e.capitulo_id
        JOIN escena_ordinal eo ON eo.escena_id = e.id
        WHERE e.novela_id = ? AND c.numero = ?
        ORDER BY e.orden
        """,
        (novela_id, capitulo),
    ).fetchall()]


# Una reafirmacion tambien es el extractor diciendo algo de la entidad en la escena: antes se
# descartaba sin rastro y dejaba un falso `nombre_sin_registro` (RF3-BIB-03).
_REAFIRMA = """
        UNION ALL SELECT 1 FROM hecho_uso u JOIN hecho h ON h.id = u.hecho_id
                  WHERE u.escena_id = :e AND u.via = 'reafirma'
                    AND h.sujeto_tipo = '{tipo}' AND h.sujeto_id = :id
"""

# Registros que cuentan como «el extractor dijo algo de esta entidad en esta escena».
_REGISTROS: dict[str, str] = {
    "personaje": """
        SELECT 1 FROM hecho h WHERE h.escena_id = :e AND h.sujeto_tipo = 'personaje'
                                AND h.sujeto_id = :id
        UNION ALL SELECT 1 FROM estado_personaje x WHERE x.escena_id = :e AND x.personaje_id = :id
        UNION ALL SELECT 1 FROM estado_conocimiento x
                  WHERE x.escena_id = :e AND x.personaje_id = :id
        UNION ALL SELECT 1 FROM uso_conocimiento x WHERE x.escena_id = :e AND x.personaje_id = :id
        UNION ALL SELECT 1 FROM estado_objeto x WHERE x.escena_id = :e AND x.poseedor_id = :id
    """ + _REAFIRMA.format(tipo="personaje"),
    "lugar": """
        SELECT 1 FROM hecho h WHERE h.escena_id = :e AND h.sujeto_tipo = 'lugar'
                                AND h.sujeto_id = :id
        UNION ALL SELECT 1 FROM estado_objeto x
                  WHERE x.escena_id = :e AND x.ubicacion_lugar_id = :id
    """ + _REAFIRMA.format(tipo="lugar"),
    "objeto": """
        SELECT 1 FROM hecho h WHERE h.escena_id = :e AND h.sujeto_tipo = 'objeto'
                                AND h.sujeto_id = :id
        UNION ALL SELECT 1 FROM estado_objeto x WHERE x.escena_id = :e AND x.objeto_id = :id
    """ + _REAFIRMA.format(tipo="objeto"),
}


def _nombres_sin_registro(
    con: sqlite3.Connection, novela_id: int, capitulo: int,
    escena: dict[str, Any], plano: str, entidades: dict[str, list[dict[str, Any]]],
) -> Conflicto | None:
    sin_registro: list[str] = []
    for tipo, filas in entidades.items():
        for f in filas:
            # El lugar donde transcurre la escena se nombra sin que haya nada que extraer.
            if tipo == "lugar" and f["id"] == escena["lugar_id"]:
                continue
            if not _aparece(plano, f["nombre"]):
                continue
            hay = con.execute(
                f"SELECT EXISTS ({_REGISTROS[tipo]})", {"e": escena["id"], "id": f["id"]}
            ).fetchone()[0]
            if not hay:
                sin_registro.append(str(f["nombre"]))
    if not sin_registro:
        return None
    return Conflicto(
        comprobacion="nombre_sin_registro", aviso=True, capitulo=capitulo,
        escena_id=escena["id"],
        descripcion=(
            f"La escena {escena['orden']} nombra a {', '.join(sin_registro)} y el extractor no "
            "registro nada sobre ellos en ella. Si la prosa fija algo, se ha perdido."
        ),
        datos={"nombres": sin_registro},
    )


def _cifras_sin_hecho(
    con: sqlite3.Connection, capitulo: int, escena: dict[str, Any], texto: str
) -> Conflicto | None:
    cifras = _CIFRA.findall(texto)
    if not cifras:
        return None
    # Un hecho de fecha o distancia que la escena establece, reafirma o menciona: la cifra ya
    # esta en el canon (RF3-BIB-03).
    hay = con.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM hecho WHERE escena_id = :e AND categoria IN ('fecha', 'distancia')
            UNION ALL
            SELECT 1 FROM hecho_uso u JOIN hecho h ON h.id = u.hecho_id
            WHERE u.escena_id = :e AND h.categoria IN ('fecha', 'distancia'))
        """,
        {"e": escena["id"]},
    ).fetchone()[0]
    if hay:
        return None
    return Conflicto(
        comprobacion="cifra_sin_hecho", aviso=True, capitulo=capitulo, escena_id=escena["id"],
        descripcion=(
            f"La escena {escena['orden']} da cifras ({', '.join(cifras[:5])}) y no hay ningun "
            "hecho de fecha ni de distancia registrado en ella."
        ),
        datos={"cifras": cifras[:20]},
    )


def _muertos_nombrados(
    con: sqlite3.Connection, novela_id: int, capitulo: int,
    escena: dict[str, Any], plano: str,
) -> Conflicto | None:
    if escena["analepsis"]:
        return None
    muertos = [dict(f) for f in con.execute(
        """
        SELECT p.id, p.nombre FROM personaje p
        WHERE p.novela_id = ?
          AND (SELECT ep.condicion FROM estado_personaje ep
               JOIN escena_ordinal o ON o.escena_id = ep.escena_id
               WHERE ep.personaje_id = p.id AND ep.condicion IS NOT NULL AND o.ordinal < ?
               ORDER BY o.ordinal DESC, ep.id DESC LIMIT 1) = 'muerto'
        """,
        (novela_id, escena["ordinal"]),
    ).fetchall()]
    nombrados = [m["nombre"] for m in muertos if _aparece(plano, m["nombre"])]
    if not nombrados:
        return None
    return Conflicto(
        comprobacion="muerto_nombrado", aviso=True, capitulo=capitulo, escena_id=escena["id"],
        descripcion=(
            f"La escena {escena['orden']} nombra a {', '.join(nombrados)}, que murio antes, y no "
            "es una analepsis. Puede ser un recuerdo; puede ser una reaparicion imposible."
        ),
        datos={"nombres": nombrados},
    )


def busquedas_dirigidas(
    con: sqlite3.Connection, novela_id: int, capitulo: int, textos: dict[int, str]
) -> list[Conflicto]:
    """Los avisos de las tres busquedas dirigidas sobre la prosa del capitulo."""
    entidades = {
        tabla: [dict(f) for f in con.execute(
            f"SELECT id, nombre FROM {tabla} WHERE novela_id = ? ORDER BY id", (novela_id,)
        ).fetchall()]
        for tabla in ("personaje", "lugar", "objeto")
    }
    avisos: list[Conflicto] = []
    for escena in _escenas(con, novela_id, capitulo):
        texto = textos.get(int(escena["orden"]), "")
        if not texto:
            continue
        plano = normalizar(texto)
        for aviso in (
            _nombres_sin_registro(con, novela_id, capitulo, escena, plano, entidades),
            _cifras_sin_hecho(con, capitulo, escena, texto),
            _muertos_nombrados(con, novela_id, capitulo, escena, plano),
        ):
            if aviso is not None:
                avisos.append(aviso)
    return avisos
