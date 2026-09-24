"""Lectura del grafo: las consultas que usan el ensamblado de contexto y la API.

Todo lo de aqui es de solo lectura, asi que vale igual para la conexion en modo `ro` de la
API que para la del worker.
"""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING, Any

from compartido.grafo.escritura import clave_laxa
from compartido.tipos import como_lista

if TYPE_CHECKING:
    from compartido.brief import Brief


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
        # Los elementos personales del encargo que la escaleta planifico aqui (RF3-PER-03).
        e["elementos"] = [
            f"{f['codigo']}: {f['texto']}" for f in con.execute(
                "SELECT ep.codigo, ep.texto FROM escena_elemento ee "
                "JOIN elemento_personal ep ON ep.id = ee.elemento_id "
                "WHERE ee.escena_id = ? ORDER BY ep.id", (e["id"],)
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

#: Los personajes que estuvieron en alguna escena de un capitulo anterior (la vista
#: `presencia`: reparto, POV, lo que constato el extractor o actuar) y no estan en el reparto de
#: este (spec3, RF3-PAS-10). Necesita la CTE `reparto` y los parametros :novela y :capitulo.
_VISTOS_FUERA_DEL_REPARTO = """
    SELECT pr.personaje_id, MAX(c5.numero) AS ultimo_capitulo
    FROM presencia pr
    JOIN escena e5   ON e5.id = pr.escena_id
    JOIN capitulo c5 ON c5.id = e5.capitulo_id
    WHERE e5.novela_id = :novela AND c5.numero < :capitulo
      AND pr.personaje_id NOT IN (SELECT personaje_id FROM reparto)
    GROUP BY pr.personaje_id
"""


def personajes_fuera_del_reparto(
    con: sqlite3.Connection, novela_id: int, numero: int
) -> list[dict[str, Any]]:
    """Quien ya salio en la novela y la escaleta no pone en este capitulo (RF3-PAS-10).

    El redactor mete a veces a alguien que la escaleta no puso (paradas 8 y 10 de la pasada
    real): si lo hace, que sea uno de estos y como es. Del mas reciente al mas antiguo, que es
    el orden en que se recortan desde el final.
    """
    return _filas(con.execute(
        _REPARTO_Y_LUGARES + f"""
        , vistos AS ({_VISTOS_FUERA_DEL_REPARTO})
        SELECT p.*, v.ultimo_capitulo FROM personaje p
        JOIN vistos v ON v.personaje_id = p.id
        ORDER BY v.ultimo_capitulo DESC, p.nombre
        """,
        {"novela": novela_id, "capitulo": numero},
    ))


def hechos_del_reparto(
    con: sqlite3.Connection, novela_id: int, numero: int
) -> list[dict[str, Any]]:
    """Hechos vigentes que este capitulo necesita, marcados como obligatorios u opcionales.

    Sin limite de filas (RF2-CTX-11). Obligatorios: los de los personajes del reparto y los de
    los lugares de sus escenas. Los opcionales se recortan desde el final, asi que van por
    prioridad y, dentro de cada una, del mas reciente al mas antiguo (spec3, RF3-PAS-10):
    primero los de amenaza, mundo y novela, que son los de las cuentas; despues los de los
    objetos del capitulo y las facciones del reparto; y al final los de los personajes que ya
    salieron sin estar en este reparto, que el redactor puede traer o no. Solo los establecidos
    antes de este capitulo y no sustituidos por otro.
    """
    return _filas(con.execute(
        _REPARTO_Y_LUGARES + f"""
        , objetos AS (
            SELECT DISTINCT eo.objeto_id
            FROM escena_objeto eo
            JOIN escena e4   ON e4.id = eo.escena_id
            JOIN capitulo c4 ON c4.id = e4.capitulo_id
            WHERE e4.novela_id = :novela AND c4.numero = :capitulo
        ),
        facciones AS (
            SELECT DISTINCT p.faccion_id FROM personaje p
            WHERE p.id IN (SELECT personaje_id FROM reparto) AND p.faccion_id IS NOT NULL
        ),
        vistos AS ({_VISTOS_FUERA_DEL_REPARTO}),
        candidatos AS (
            SELECT h.id, h.sujeto_tipo, h.sujeto_id, h.sujeto_nombre, h.atributo, h.valor,
                   h.categoria, c.numero AS capitulo_origen,
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
           OR (sujeto_tipo = 'objeto' AND sujeto_id IN (SELECT objeto_id FROM objetos))
           OR (sujeto_tipo = 'faccion' AND sujeto_id IN (SELECT faccion_id FROM facciones))
           OR (sujeto_tipo = 'personaje' AND sujeto_id IN (SELECT personaje_id FROM vistos))
        ORDER BY obligatorio DESC,
                 CASE WHEN obligatorio = 1 THEN sujeto_nombre END,
                 CASE WHEN obligatorio = 1 THEN 0
                      WHEN sujeto_tipo IN ('amenaza', 'mundo', 'novela') THEN 0
                      WHEN sujeto_tipo IN ('objeto', 'faccion') THEN 1
                      ELSE 2 END,
                 capitulo_origen DESC, id DESC
        """,
        {"novela": novela_id, "capitulo": numero},
    ))


def hechos_hasta(
    con: sqlite3.Connection, novela_id: int, numero: int
) -> list[dict[str, Any]]:
    """Los hechos vigentes y no sustituidos hasta este capitulo, incluido.

    Los usa el juez de oficio para las cuentas (spec3, RF3-PAS-12), y por eso incluye los de
    este capitulo, que el extractor acaba de sacar de su prosa: una cuenta puede descuadrar
    dentro del mismo capitulo. Primero los de amenaza, mundo y novela, que son los de toda la
    obra, y despues del mas reciente al mas antiguo: el recorte quita desde el final.
    """
    return _filas(con.execute(
        f"""
        SELECT h.id, h.sujeto_tipo, h.sujeto_nombre, h.atributo, h.valor,
               c.numero AS capitulo_origen
        FROM hecho_vigente h
        JOIN escena e   ON e.id = h.escena_id
        JOIN capitulo c ON c.id = e.capitulo_id
        WHERE h.novela_id = ? AND c.numero <= ? AND {_NO_SUSTITUIDO}
        ORDER BY CASE WHEN h.sujeto_tipo IN ('amenaza', 'mundo', 'novela') THEN 0 ELSE 1 END,
                 c.numero DESC, h.id DESC
        """,
        (novela_id, numero),
    ))


def valores_vigentes(
    con: sqlite3.Connection, novela_id: int
) -> dict[str, list[tuple[str, str]]]:
    """El valor que hoy fija cada sujeto y atributo (RF2-PIPE-23).

    Vigente, sin sustituir y el mas reciente: lo que el extractor tiene que repetir igual si el
    texto dice lo mismo, o sustituir a sabiendas si lo cambia.
    """
    salida: dict[str, list[tuple[str, str]]] = {}
    for f in con.execute(
        """
        SELECT h.sujeto_nombre, h.atributo, h.valor FROM hecho_vigente h
        WHERE h.novela_id = ?
          AND NOT EXISTS (SELECT 1 FROM hecho_vigente s WHERE s.supersede_a = h.id)
          AND h.id = (SELECT MAX(o.id) FROM hecho_vigente o
                      WHERE o.novela_id = h.novela_id AND o.sujeto_clave = h.sujeto_clave
                        AND o.atributo_clave = h.atributo_clave)
        ORDER BY h.sujeto_nombre, h.atributo
        """,
        (novela_id,),
    ):
        salida.setdefault(f["sujeto_nombre"] or "", []).append((f["atributo"], f["valor"]))
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


def nombres_menores(
    con: sqlite3.Connection, novela_id: int, antes_de_capitulo: int
) -> list[str]:
    """Los nombres fuera del canon que ya salieron antes de este capitulo (RF3-PAS-05).

    Sin duplicados por clave laxa y con la primera grafia: es la que el redactor tiene que
    mantener si vuelve a usar el nombre.
    """
    vistos: dict[str, str] = {}
    for f in con.execute(
        """
        SELECT en.nombre FROM entidad_no_reconocida en
        JOIN escena_ordinal eo ON eo.escena_id = en.escena_id
        WHERE en.novela_id = ? AND eo.capitulo_numero < ? AND en.parada_id IS NULL
        ORDER BY eo.ordinal, en.id
        """,
        (novela_id, antes_de_capitulo),
    ):
        vistos.setdefault(clave_laxa(str(f["nombre"])), str(f["nombre"]))
    return list(vistos.values())


def ultimo_dia(con: sqlite3.Connection, novela_id: int) -> int:
    """El mayor `dia` registrado (RF3-BIB-08); 0, el comienzo de la historia, si no hay."""
    valor = con.execute(
        "SELECT MAX(dia) FROM evento WHERE novela_id = ?", (novela_id,)
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
        "SELECT * FROM hilo_vigente WHERE novela_id = ? "
        "ORDER BY tipo = 'principal' DESC, hilo_id", (novela_id,)
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


# --- Personalizacion (specs/spec3.md, 3.2) ---------------------------------------------------


def brief(con: sqlite3.Connection, novela_id: int) -> Brief | None:
    """El brief de la novela, o None si se creo sin personalizar (RF3-PER-05)."""
    # Import aqui y no arriba: compartido.brief usa compartido.texto, que usa la
    # normalizacion de este mismo paquete, y el import de modulo cerraria un ciclo.
    from compartido.brief import Brief

    fila = con.execute(
        "SELECT contenido FROM brief WHERE novela_id = ?", (novela_id,)
    ).fetchone()
    return None if fila is None else Brief.model_validate_json(str(fila["contenido"]))


def elementos_personales(
    con: sqlite3.Connection, novela_id: int, *, solo_obligatorios: bool = False
) -> list[dict[str, Any]]:
    """Los rasgos, recuerdos y allegados del destinatario, en el orden del brief."""
    return _filas(con.execute(
        "SELECT id, codigo, tipo, texto, obligatorio, origen FROM elemento_personal "
        "WHERE novela_id = ? AND (obligatorio = 1 OR ? = 0) ORDER BY id",
        (novela_id, 1 if solo_obligatorios else 0),
    ))


# --- Huecos de la story bible (specs/spec3.md, 3.3) ------------------------------------------


def usos_de_hecho(
    con: sqlite3.Connection, novela_id: int, hecho_id: int
) -> list[dict[str, Any]]:
    """Donde se establece y donde se usa un hecho, en orden de escena (RF3-BIB-02)."""
    return _filas(con.execute(
        """
        SELECT he.capitulo_numero AS capitulo, he.escena_orden, he.escena_id, he.via, he.cita
        FROM hecho_escena he
        JOIN escena_ordinal o ON o.escena_id = he.escena_id
        WHERE he.novela_id = ? AND he.hecho_id = ?
        ORDER BY o.ordinal, he.via
        """,
        (novela_id, hecho_id),
    ))


def capitulos_de_hecho(con: sqlite3.Connection, novela_id: int, hecho_id: int) -> list[int]:
    """Los capitulos que establecen o usan el hecho: los que el bloque 8 regenerara."""
    return sorted({int(u["capitulo"]) for u in usos_de_hecho(con, novela_id, hecho_id)})


def cronologia(con: sqlite3.Connection, novela_id: int) -> list[dict[str, Any]]:
    """Los eventos en orden de dia y de orden interno, con sus personajes (RF3-BIB-10).

    Los eventos sin dia (anteriores al bloque 3 o no dramatizados sin fecha) van al final, en
    orden interno: no hay con que colocarlos entre los demas.
    """
    eventos = _filas(con.execute(
        """
        SELECT evento_id, dia, orden_interno, fecha_interna, descripcion, tipo, dramatizado,
               escena_id, capitulo_numero AS capitulo, escena_orden, lugar_id, lugar
        FROM cronologia
        WHERE novela_id = ?
        ORDER BY dia IS NULL, dia, orden_interno IS NULL, orden_interno, evento_id
        """,
        (novela_id,),
    ))
    personajes: dict[int, list[str]] = {}
    for f in con.execute(
        """
        SELECT cp.evento_id, cp.nombre FROM cronologia_personaje cp
        JOIN evento ev ON ev.id = cp.evento_id
        WHERE ev.novela_id = ? ORDER BY cp.nombre
        """,
        (novela_id,),
    ):
        personajes.setdefault(int(f["evento_id"]), []).append(str(f["nombre"]))
    for ev in eventos:
        ev["dramatizado"] = bool(ev["dramatizado"])
        ev["personajes"] = personajes.get(int(ev["evento_id"]), [])
    return eventos


def versiones(con: sqlite3.Connection, novela_id: int) -> list[dict[str, Any]]:
    """Las versiones publicadas, con los capitulos que cambiaron en cada una (RF3-BIB-11)."""
    salida = _filas(con.execute(
        "SELECT id, numero, motivo, detalle, titulo, dedicatoria, creado_en "
        "FROM novela_version WHERE novela_id = ? ORDER BY numero",
        (novela_id,),
    ))
    for v in salida:
        v["capitulos_cambiados"] = [
            int(f[0]) for f in con.execute(
                "SELECT numero FROM novela_version_capitulo WHERE version_id = ? AND cambiado = 1 "
                "ORDER BY numero",
                (v.pop("id"),),
            )
        ]
    return salida


def version(con: sqlite3.Connection, novela_id: int, numero: int) -> dict[str, Any] | None:
    """Una version con el texto de sus capitulos."""
    v = _fila(con.execute(
        "SELECT id, numero, motivo, detalle, titulo, dedicatoria, creado_en "
        "FROM novela_version WHERE novela_id = ? AND numero = ?",
        (novela_id, numero),
    ).fetchone())
    if v is None:
        return None
    v["capitulos"] = _filas(con.execute(
        "SELECT numero, texto, palabras, cambiado FROM novela_version_capitulo "
        "WHERE version_id = ? ORDER BY numero",
        (v.pop("id"),),
    ))
    for c in v["capitulos"]:
        c["cambiado"] = bool(c["cambiado"])
    v["capitulos_cambiados"] = [c["numero"] for c in v["capitulos"] if c["cambiado"]]
    return v


# --- Lo que la lectura web pide al backend (specs/spec3.md, 3.7) -----------------------------

#: La ocasion del brief, como la lee el destinatario en la portada (RF3-LEC-01).
OCASIONES: dict[str, str] = {
    "cumpleanos": "cumpleaños", "aniversario": "aniversario", "boda": "boda",
    "jubilacion": "jubilación", "navidad": "Navidad",
}


def regalo(con: sqlite3.Connection, novela_id: int) -> dict[str, str | None] | None:
    """Para quien es, de quien y por que, o None si la novela no tiene brief (RF3-LEC-01)."""
    b = brief(con, novela_id)
    if b is None:
        return None
    ocasion = (b.ocasion_detalle or None) if b.ocasion == "otra" else (
        OCASIONES.get(b.ocasion) if b.ocasion else None
    )
    return {"para": b.destinatario.nombre, "de": b.quien_regala, "ocasion": ocasion}


def apariciones(con: sqlite3.Connection, novela_id: int) -> dict[str, list[dict[str, Any]]]:
    """Cada personaje y cada lugar con los capitulos completados donde aparece (RF3-LEC-02).

    Los personajes, por la vista `presencia` (RF2-PIPE-31); los lugares, por el lugar de cada
    escena. Quien no aparece en ningun capitulo completado sale con la lista vacia.
    """
    def agrupar(entidades: str, apariciones_sql: str) -> list[dict[str, Any]]:
        capitulos: dict[int, set[int]] = {}
        for f in con.execute(apariciones_sql, (novela_id,)):
            capitulos.setdefault(int(f["id"]), set()).add(int(f["capitulo"]))
        return [
            {"id": int(f["id"]), "nombre": str(f["nombre"]),
             "capitulos": sorted(capitulos.get(int(f["id"]), set()))}
            for f in con.execute(entidades, (novela_id,))
        ]

    return {
        "personajes": agrupar(
            "SELECT id, nombre FROM personaje WHERE novela_id = ? ORDER BY id",
            """
            SELECT p.personaje_id AS id, c.numero AS capitulo
            FROM presencia p
            JOIN escena e ON e.id = p.escena_id
            JOIN capitulo c ON c.id = e.capitulo_id
            WHERE e.novela_id = ? AND c.estado = 'completado'
            """,
        ),
        "lugares": agrupar(
            "SELECT id, nombre FROM lugar WHERE novela_id = ? ORDER BY id",
            """
            SELECT e.lugar_id AS id, c.numero AS capitulo
            FROM escena e JOIN capitulo c ON c.id = e.capitulo_id
            WHERE e.novela_id = ? AND c.estado = 'completado' AND e.lugar_id IS NOT NULL
            """,
        ),
    }
