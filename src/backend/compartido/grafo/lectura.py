"""Lectura del grafo: las consultas que usan el ensamblado de contexto y la API.

Todo lo de aqui es de solo lectura, asi que vale igual para la conexion en modo `ro` de la
API que para la del worker.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from compartido.tipos import como_lista


def _fila(f: sqlite3.Row | None) -> dict[str, Any] | None:
    return None if f is None else dict(f)


def _filas(cur: sqlite3.Cursor) -> list[dict[str, Any]]:
    return [dict(f) for f in cur.fetchall()]


def novela(con: sqlite3.Connection, novela_id: int) -> dict[str, Any] | None:
    return _fila(con.execute("SELECT * FROM novela WHERE id = ?", (novela_id,)).fetchone())


def restricciones(con: sqlite3.Connection, novela_id: int) -> dict[str, str]:
    return {
        f["tipo"]: f["valor"]
        for f in con.execute(
            "SELECT tipo, valor FROM restriccion WHERE novela_id = ?", (novela_id,)
        )
    }


def estilo(con: sqlite3.Connection, novela_id: int) -> dict[str, Any] | None:
    fila = _fila(con.execute(
        "SELECT * FROM estilo_narrativo WHERE novela_id = ?", (novela_id,)
    ).fetchone())
    if fila and fila.get("tics_prohibidos"):
        try:
            fila["tics_prohibidos"] = json.loads(fila["tics_prohibidos"])
        except json.JSONDecodeError:
            fila["tics_prohibidos"] = []
    return fila


def tics_prohibidos(con: sqlite3.Connection, novela_id: int) -> list[str]:
    e = estilo(con, novela_id) or {}
    return [str(t) for t in como_lista(e.get("tics_prohibidos"))]


def ejecucion(con: sqlite3.Connection, novela_id: int) -> dict[str, Any] | None:
    return _fila(con.execute(
        "SELECT * FROM ejecucion WHERE novela_id = ?", (novela_id,)
    ).fetchone())


# --- Estructura ---------------------------------------------------------------------------


def capitulo(con: sqlite3.Connection, novela_id: int, numero: int) -> dict[str, Any] | None:
    return _fila(con.execute(
        "SELECT * FROM capitulo WHERE novela_id = ? AND numero = ?", (novela_id, numero)
    ).fetchone())


def escenas_del_capitulo(
    con: sqlite3.Connection, novela_id: int, numero: int
) -> list[dict[str, Any]]:
    """Escenas con su POV, lugar y reparto ya resueltos a nombres."""
    escenas = _filas(con.execute(
        """
        SELECT e.*, p.nombre AS pov_nombre, l.nombre AS lugar_nombre, s.objetivo_intermedio
        FROM escena e
        JOIN capitulo c   ON c.id = e.capitulo_id
        JOIN personaje p  ON p.id = e.pov_id
        JOIN lugar l      ON l.id = e.lugar_id
        LEFT JOIN secuencia s ON s.id = e.secuencia_id
        WHERE e.novela_id = ? AND c.numero = ?
        ORDER BY e.orden
        """,
        (novela_id, numero),
    ))
    for e in escenas:
        e["reparto"] = [
            f["nombre"] for f in con.execute(
                "SELECT p.nombre FROM escena_personaje ep JOIN personaje p ON p.id = "
                "ep.personaje_id WHERE ep.escena_id = ? ORDER BY p.nombre", (e["id"],)
            )
        ]
        e["objetos"] = [
            f["nombre"] for f in con.execute(
                "SELECT o.nombre FROM escena_objeto eo JOIN objeto o ON o.id = eo.objeto_id "
                "WHERE eo.escena_id = ? ORDER BY o.nombre", (e["id"],)
            )
        ]
        e["beats"] = _filas(con.execute(
            "SELECT orden, tipo, cambio FROM beat WHERE escena_id = ? ORDER BY orden", (e["id"],)
        ))
        e["secuela"] = _fila(con.execute(
            "SELECT reaccion, dilema, decision FROM secuela WHERE escena_id = ?", (e["id"],)
        ).fetchone())
    return escenas


def ultimo_capitulo_completado(con: sqlite3.Connection, novela_id: int) -> int:
    valor = con.execute(
        "SELECT MAX(numero) FROM capitulo WHERE novela_id = ? AND estado = 'completado'",
        (novela_id,),
    ).fetchone()[0]
    return int(valor) if valor is not None else 0


def total_capitulos(con: sqlite3.Connection, novela_id: int) -> int:
    return int(con.execute(
        "SELECT COUNT(*) FROM capitulo WHERE novela_id = ?", (novela_id,)
    ).fetchone()[0])


# --- Canon filtrado al capitulo -------------------------------------------------------------


def canon_del_capitulo(
    con: sqlite3.Connection, novela_id: int, numero: int
) -> dict[str, list[dict[str, Any]]]:
    """Solo las entidades que este capitulo toca. Nada se vuelca entero (principio 7).

    El orden de cada lista es por relevancia: primero lo que aparece en mas escenas del
    capitulo. Es el criterio determinista de recorte cuando el bloque no cabe.
    """
    personajes = _filas(con.execute(
        """
        SELECT p.*, COUNT(ep.id) AS apariciones,
               (SELECT COUNT(*) FROM escena e2 JOIN capitulo c2 ON c2.id = e2.capitulo_id
                 WHERE e2.pov_id = p.id AND c2.numero = ?) AS escenas_pov
        FROM personaje p
        JOIN escena_personaje ep ON ep.personaje_id = p.id
        JOIN escena e   ON e.id = ep.escena_id
        JOIN capitulo c ON c.id = e.capitulo_id
        WHERE p.novela_id = ? AND c.numero = ?
        GROUP BY p.id
        ORDER BY escenas_pov DESC, apariciones DESC, p.nombre
        """,
        (numero, novela_id, numero),
    ))
    lugares = _filas(con.execute(
        """
        SELECT l.*, COUNT(e.id) AS apariciones
        FROM lugar l
        JOIN escena e   ON e.lugar_id = l.id
        JOIN capitulo c ON c.id = e.capitulo_id
        WHERE l.novela_id = ? AND c.numero = ?
        GROUP BY l.id ORDER BY apariciones DESC, l.nombre
        """,
        (novela_id, numero),
    ))
    objetos = _filas(con.execute(
        """
        SELECT o.*, COUNT(eo.id) AS apariciones
        FROM objeto o
        JOIN escena_objeto eo ON eo.objeto_id = o.id
        JOIN escena e   ON e.id = eo.escena_id
        JOIN capitulo c ON c.id = e.capitulo_id
        WHERE o.novela_id = ? AND c.numero = ?
        GROUP BY o.id ORDER BY apariciones DESC, o.nombre
        """,
        (novela_id, numero),
    ))

    # Sistemas tecnicos: los que cuelgan de los lugares de este capitulo.
    ids_sistemas: set[int] = set()
    for lugar in lugares:
        try:
            ids_sistemas.update(int(x) for x in json.loads(lugar.get("sistemas_criticos") or "[]"))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    sistemas = (
        _filas(con.execute(
            f"SELECT * FROM sistema_tecnologico WHERE id IN ({','.join('?' * len(ids_sistemas))})",
            list(ids_sistemas),
        )) if ids_sistemas else []
    )

    ids_facciones = {p["faccion_id"] for p in personajes if p.get("faccion_id")}
    facciones = (
        _filas(con.execute(
            f"SELECT * FROM faccion WHERE id IN ({','.join('?' * len(ids_facciones))})",
            list(ids_facciones),
        )) if ids_facciones else []
    )

    amenaza = _fila(con.execute(
        "SELECT * FROM amenaza WHERE novela_id = ?", (novela_id,)
    ).fetchone())

    return {
        "personajes": personajes,
        "lugares": lugares,
        "objetos": objetos,
        "sistemas": sistemas,
        "facciones": facciones,
        "amenaza": [amenaza] if amenaza else [],
    }


_REPARTO_Y_LUGARES = """
WITH reparto AS (
    SELECT DISTINCT ep.personaje_id
    FROM escena_personaje ep
    JOIN escena e2   ON e2.id = ep.escena_id
    JOIN capitulo c2 ON c2.id = e2.capitulo_id
    WHERE e2.novela_id = :novela AND c2.numero = :capitulo
),
lugares AS (
    SELECT DISTINCT e3.lugar_id
    FROM escena e3
    JOIN capitulo c3 ON c3.id = e3.capitulo_id
    WHERE e3.novela_id = :novela AND c3.numero = :capitulo
)
"""

#: Un hecho que otro hecho vigente sustituye ya no es el estado actual: el agente ve la herida
#: cicatrizada, no la herida.
_NO_SUSTITUIDO = (
    "NOT EXISTS (SELECT 1 FROM hecho_vigente s WHERE s.supersede_a = h.id)"
)


def hechos_del_reparto(
    con: sqlite3.Connection, novela_id: int, numero: int
) -> list[dict[str, Any]]:
    """Hechos vigentes que este capitulo necesita, marcados como obligatorios u opcionales.

    Sin limite de filas (RF2-CTX-11). Obligatorios: los de los personajes del reparto y los de
    los lugares de sus escenas. Opcionales: los de amenaza, mundo y novela, del mas reciente al
    mas antiguo, que es el orden en que se recortan desde el final. Solo los establecidos
    antes de este capitulo y no sustituidos por otro.
    """
    return _filas(con.execute(
        _REPARTO_Y_LUGARES + f"""
        , candidatos AS (
            SELECT h.id, h.sujeto_tipo, h.sujeto_nombre, h.atributo, h.valor, h.categoria,
                   c.numero AS capitulo_origen,
                   CASE WHEN (h.sujeto_tipo = 'personaje'
                              AND h.sujeto_id IN (SELECT personaje_id FROM reparto))
                          OR (h.sujeto_tipo = 'lugar'
                              AND h.sujeto_id IN (SELECT lugar_id FROM lugares))
                        THEN 1 ELSE 0 END AS obligatorio
            FROM hecho_vigente h
            JOIN escena e   ON e.id = h.escena_id
            JOIN capitulo c ON c.id = e.capitulo_id
            WHERE h.novela_id = :novela AND c.numero < :capitulo
              AND {_NO_SUSTITUIDO}
        )
        SELECT * FROM candidatos
        WHERE obligatorio = 1 OR sujeto_tipo IN ('amenaza', 'mundo', 'novela')
        ORDER BY obligatorio DESC,
                 CASE WHEN obligatorio = 1 THEN sujeto_nombre END,
                 capitulo_origen DESC, id DESC
        """,
        {"novela": novela_id, "capitulo": numero},
    ))


def atributos_por_sujeto(
    con: sqlite3.Connection, novela_id: int
) -> dict[str, list[str]]:
    """Atributos ya usados por cada sujeto, para que el extractor no invente sinonimos."""
    salida: dict[str, list[str]] = {}
    for f in con.execute(
        "SELECT DISTINCT sujeto_nombre, atributo FROM hecho_vigente WHERE novela_id = ?"
        " ORDER BY sujeto_nombre, atributo",
        (novela_id,),
    ):
        salida.setdefault(f["sujeto_nombre"] or "", []).append(f["atributo"])
    return salida


def conocimiento_del_reparto(
    con: sqlite3.Connection, novela_id: int, numero: int
) -> list[dict[str, Any]]:
    """La ULTIMA postura de cada personaje del reparto sobre cada hecho vigente (RF2-CTX-11).

    Solo lo adquirido antes de este capitulo, y solo sobre hechos que siguen siendo el estado
    actual: saber algo que ya no es verdad no es conocimiento que el redactor deba usar.
    """
    return _filas(con.execute(
        _REPARTO_Y_LUGARES + f"""
        , ultima AS (
            SELECT ec.personaje_id, ec.hecho_id, ec.postura, ec.via,
                   eo.capitulo_numero AS capitulo,
                   ROW_NUMBER() OVER (
                       PARTITION BY ec.personaje_id, ec.hecho_id
                       ORDER BY eo.ordinal DESC, ec.id DESC
                   ) AS rn
            FROM estado_conocimiento ec
            JOIN escena_ordinal eo ON eo.escena_id = ec.escena_id
            WHERE ec.novela_id = :novela AND eo.capitulo_numero < :capitulo
              AND ec.personaje_id IN (SELECT personaje_id FROM reparto)
        )
        SELECT p.nombre AS personaje, h.sujeto_nombre, h.atributo, h.valor,
               u.postura, u.via, u.capitulo
        FROM ultima u
        JOIN personaje p ON p.id = u.personaje_id
        JOIN hecho_vigente h ON h.id = u.hecho_id
        WHERE u.rn = 1 AND {_NO_SUSTITUIDO}
        ORDER BY p.nombre, u.capitulo, h.id
        """,
        {"novela": novela_id, "capitulo": numero},
    ))


def ultimo_orden_interno(con: sqlite3.Connection, novela_id: int) -> int:
    """El mayor `orden_interno` registrado: el extractor continua la escala desde ahi."""
    valor = con.execute(
        "SELECT MAX(orden_interno) FROM evento WHERE novela_id = ?", (novela_id,)
    ).fetchone()[0]
    return int(valor) if valor is not None else 0


def siembras_vivas(
    con: sqlite3.Connection, novela_id: int, numero: int, margen: int = 3
) -> list[dict[str, Any]]:
    """Las que hay que regar o pagar en este tramo. Es barato y su olvido es caro."""
    return _filas(con.execute(
        """
        SELECT sv.siembra_id, sv.elemento, sv.estado, sv.capitulo_pago_previsto
        FROM siembra_vigente sv
        WHERE sv.novela_id = ?
          AND sv.estado IN ('sembrada','regada')
          AND (sv.capitulo_pago_previsto IS NULL OR sv.capitulo_pago_previsto <= ?)
        ORDER BY sv.capitulo_pago_previsto IS NULL, sv.capitulo_pago_previsto
        """,
        (novela_id, numero + margen),
    ))


def hilos(con: sqlite3.Connection, novela_id: int) -> list[dict[str, Any]]:
    return _filas(con.execute(
        "SELECT * FROM hilo_vigente WHERE novela_id = ? ORDER BY tipo DESC", (novela_id,)
    ))


def estado_rodante(
    con: sqlite3.Connection, novela_id: int, hasta_capitulo: int, completos: int = 3
) -> list[dict[str, Any]]:
    """Sinopsis de lo escrito hasta aqui (RF-CTX-04), un elemento por capitulo.

    Los ultimos `completos` capitulos van con su resumen entero; los anteriores, con su
    resumen de una frase. Determinista, sin llamar a nadie. Devuelve filas y no texto para que
    el paquete pueda recortar por capitulos enteros, empezando por los mas antiguos.
    """
    filas = _filas(con.execute(
        """
        SELECT numero, resumen, resumen_breve FROM capitulo
        WHERE novela_id = ? AND numero < ? AND estado = 'completado'
        ORDER BY numero
        """,
        (novela_id, hasta_capitulo),
    ))
    corte = max(0, len(filas) - completos)
    salida: list[dict[str, Any]] = []
    for i, f in enumerate(filas):
        texto = f["resumen"] if i >= corte else f["resumen_breve"]
        if texto:
            salida.append({"numero": f["numero"], "texto": texto, "completo": i >= corte})
    return salida


def texto_capitulo(
    con: sqlite3.Connection, novela_id: int, numero: int
) -> str:
    fila = con.execute(
        """
        SELECT cc.texto FROM capitulo_compilado cc
        JOIN capitulo c ON c.id = cc.capitulo_id
        WHERE cc.novela_id = ? AND c.numero = ? AND cc.estado = 'vigente'
        ORDER BY cc.version DESC LIMIT 1
        """,
        (novela_id, numero),
    ).fetchone()
    return "" if fila is None else str(fila["texto"])
