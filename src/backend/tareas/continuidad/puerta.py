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
from typing import Any

from compartido.grafo import normalizar
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
       onu.capitulo_numero AS capitulo_nuevo
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

# --- 2. Conocimiento no adquirido (RF2-PIPE-21) --------------------------------------------
# Un personaje usa informacion que todavia no ha recibido. Es la fuente numero uno de
# errores de continuidad en obra larga. Recibirla es tener un estado de conocimiento que la
# habilite o haber estado (reparto o POV) en la escena donde el texto la fijo: presenciarla.
_SQL_CONOCIMIENTO = f"""
SELECT u.id AS uso_id, p.nombre AS personaje, h.atributo, h.valor, h.sujeto_nombre,
       u.escena_id, c.numero AS capitulo
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
                WHERE sp.escena_id = eh.id AND sp.personaje_id = u.personaje_id)))
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
       l1.nombre AS lugar_a, l2.nombre AS lugar_b,
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

# --- 5. Objeto sin traslado ----------------------------------------------------------------
_SQL_OBJETO = """
SELECT o.nombre AS objeto, l.nombre AS lugar_escena, lu.nombre AS ultima_ubicacion,
       e.id AS escena_id, c.numero AS capitulo
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

_SQL_ENTIDADES = """
SELECT en.nombre, en.contexto, en.escena_id, c.numero AS capitulo
FROM entidad_no_reconocida en
JOIN escena e   ON e.id = en.escena_id
JOIN capitulo c ON c.id = e.capitulo_id
WHERE en.novela_id = ? AND c.numero = ? AND en.parada_id IS NULL
"""


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

    for f in _filas(con, _SQL_CONTRADICCION, p):
        conflictos.append(Conflicto(
            comprobacion="continuidad_factual",
            descripcion=(
                f"'{f['sujeto_nombre']}' tiene '{f['atributo']}' = '{f['valor_nuevo']}', pero en "
                f"el capitulo {f['capitulo_previo']} quedo establecido como '{f['valor_previo']}'."
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

    for f in _filas(con, _SQL_ENTIDADES, p):
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

    return ResultadoPuerta(puerta=3, conflictos=conflictos)


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
    """,
    "lugar": """
        SELECT 1 FROM hecho h WHERE h.escena_id = :e AND h.sujeto_tipo = 'lugar'
                                AND h.sujeto_id = :id
        UNION ALL SELECT 1 FROM estado_objeto x
                  WHERE x.escena_id = :e AND x.ubicacion_lugar_id = :id
    """,
    "objeto": """
        SELECT 1 FROM hecho h WHERE h.escena_id = :e AND h.sujeto_tipo = 'objeto'
                                AND h.sujeto_id = :id
        UNION ALL SELECT 1 FROM estado_objeto x WHERE x.escena_id = :e AND x.objeto_id = :id
    """,
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
    hay = con.execute(
        "SELECT EXISTS (SELECT 1 FROM hecho WHERE escena_id = ? "
        "AND categoria IN ('fecha', 'distancia'))",
        (escena["id"],),
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
