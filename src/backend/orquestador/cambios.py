"""El cambio del lector aplicado al canon (specs/spec3.md, RF3-CAM-07 y RF3-CAM-11).

`aplicar_canon` corre dos veces por cambio: dentro de la transaccion simulada, para que los
paquetes y la mecanica vean el canon ya cambiado, y en la transaccion final que lo confirma
junto con los textos y la version. Es la misma funcion las dos veces, asi que lo que se valido
es exactamente lo que se aplica.

Aqui no entra la prosa: la corrige el revisor, y la confirma el pipeline.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from compartido.cambio import Cambio, sustituir_nombres
from compartido.grafo import TABLAS_CON_NOMBRE_CLAVE, insertar_hecho, lectura, normalizar

#: Tablas que no se tocan al sustituir un nombre en los textos: la prosa y sus versiones (las
#: corrige el revisor, y las versiones son historia), el hecho (inmutable: se revoca y se
#: inserta de nuevo) y todo lo que es registro de lo que paso.
_NO_SE_SUSTITUYEN = frozenset({
    "hecho", "hecho_revocacion", "escena_texto", "capitulo_compilado", "novela_version",
    "novela_version_capitulo", "llamada_modelo", "traza_evento", "intencion",
    "resultado_puerta", "parada", "decision_politica", "cambio_lector", "termino_vetado",
    "ejecucion", "entrevista", "entidad_no_reconocida", "langfuse_envio", "indice_estado",
    "evaluacion_rubrica",
})

class CanonDesfasado(Exception):
    """El canon ya no es el que el cambio vio: un error de datos, no del codigo (RF3-CAM-12)."""


#: Las marcas que van por la clave del sujeto (RF2-PIPE-29, RF3-PAS-15): al renombrarlo, pasan
#: a la clave nueva, o el hecho dejaria de ser conducta u observable (validador de 221f1be).
_MARCAS_POR_SUJETO = ("atributo_conducta", "atributo_observable")

#: Lo que cuelga de un hecho y pasa a apuntar al que lo sustituye.
_QUE_APUNTAN_A_UN_HECHO = ("hecho_uso", "estado_conocimiento", "uso_conocimiento")


def aplicar_canon(
    con: sqlite3.Connection, novela_id: int, cambio: Cambio,
    *, citas: dict[int, list[str]] | None = None,
) -> None:
    """Escribe el cambio en el canon. Corre dentro de la transaccion del llamante."""
    if cambio.tipo == "renombrar":
        _renombrar(con, novela_id, cambio)
    else:
        _cambiar_hecho(con, novela_id, cambio, citas or {})


# --- Renombrar ----------------------------------------------------------------------------------


def _renombrar(con: sqlite3.Connection, novela_id: int, cambio: Cambio) -> None:
    mapa = cambio.mapa()
    tabla = str(cambio.tabla)
    con.execute(
        f"UPDATE {tabla} SET nombre = ?, nombre_clave = ? WHERE novela_id = ? AND id = ?",
        (cambio.despues, normalizar(cambio.despues), novela_id, cambio.entidad_id),
    )
    # Los hechos que llevan el nombre en el sujeto, el valor o la cita.
    claves: set[tuple[str, str]] = set()
    for h in _filas(con, "SELECT * FROM hecho_vigente WHERE novela_id = ? ORDER BY id",
                    novela_id):
        nuevos = {c: sustituir_nombres(str(h[c]), mapa, cambio.protegidos)
                  for c in ("sujeto_nombre", "valor", "cita") if h[c] is not None}
        if any(nuevos[c] != h[c] for c in nuevos):
            nuevo = _sustituir_hecho(con, novela_id, h, **nuevos)
            clave = con.execute("SELECT sujeto_clave FROM hecho WHERE id = ?",
                                (nuevo,)).fetchone()[0]
            if clave != h["sujeto_clave"]:
                claves.add((str(h["sujeto_clave"]), str(clave)))
    for vieja, nueva in sorted(claves):
        for tabla in _MARCAS_POR_SUJETO:
            con.execute(
                f"UPDATE OR IGNORE {tabla} SET sujeto_clave = ? "  # tabla cerrada
                "WHERE novela_id = ? AND sujeto_clave = ?",
                (nueva, novela_id, vieja),
            )
    _sustituir_en_textos(con, novela_id, mapa, cambio.protegidos)


def _sustituir_en_textos(con: sqlite3.Connection, novela_id: int, mapa: dict[str, str],
                         protegidos: tuple[str, ...]) -> None:
    """El nombre, como palabra completa, en los textos del plan y del canon de la novela.

    Fichas, escaleta, resumenes, brief, titulo y dedicatoria: todo lo que tenga texto y sea de
    esta novela, salvo lo que no se sustituye (`_NO_SE_SUSTITUYEN`). El nombre de las demas
    entidades no se toca nunca: renombrar a una no renombra a otra (validador de 2fa0ee6).
    """
    for tabla, todas, filtro in _textos_de_la_novela(con):
        columnas = [c for c in todas
                    if not (tabla in TABLAS_CON_NOMBRE_CLAVE and c == "nombre")]
        if not columnas:
            continue
        for fila in _filas(con, f"SELECT id, {', '.join(columnas)} FROM {tabla} "
                                f"WHERE {filtro}", novela_id):
            nuevos = {c: sustituir_nombres(str(fila[c]), mapa, protegidos) for c in columnas
                      if fila[c] is not None}
            cambiados = {c: v for c, v in nuevos.items() if v != fila[c]}
            if not cambiados:
                continue
            asignaciones = ", ".join(f"{c} = ?" for c in cambiados)
            con.execute(f"UPDATE {tabla} SET {asignaciones} WHERE id = ?",
                        (*cambiados.values(), fila["id"]))


def _textos_de_la_novela(con: sqlite3.Connection) -> list[tuple[str, list[str], str]]:
    """Cada tabla de la novela con sus columnas de texto y el filtro de sus filas.

    Las claves normalizadas, fuera. Es de la novela lo que lleva `novela_id` y lo que cuelga de
    una escena suya por `escena_id` (`beat`, `secuela`: validador de 58e70f0). El filtro lleva
    un solo parametro, el id de la novela.
    """
    salida: list[tuple[str, list[str], str]] = []
    for tabla, sql in con.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name"
    ).fetchall():
        # El indice vectorial (sus tablas virtuales y las que cuelgan de ellas) se reindexa
        # aparte, y sin su extension cargada ni siquiera se puede inspeccionar.
        virtual = str(sql or "").upper().startswith("CREATE VIRTUAL")
        if tabla in _NO_SE_SUSTITUYEN or virtual or str(tabla).startswith("vec_"):
            continue
        info = con.execute(f"PRAGMA table_info({tabla})").fetchall()
        nombres = {str(c["name"]) for c in info}
        if "id" not in nombres:
            continue
        if tabla == "novela":
            filtro = "id = ?"
        elif "novela_id" in nombres:
            filtro = "novela_id = ?"
        elif "escena_id" in nombres:
            filtro = "escena_id IN (SELECT id FROM escena WHERE novela_id = ?)"
        else:
            continue
        columnas = [
            str(c["name"]) for c in info
            if str(c["type"]).upper() == "TEXT" and not str(c["name"]).endswith("_clave")
            and str(c["name"]) not in ("creado_en", "actualizado_en")
        ]
        if columnas:
            salida.append((str(tabla), columnas, filtro))
    return salida


# --- Cambiar un hecho ---------------------------------------------------------------------------


def _cambiar_hecho(con: sqlite3.Connection, novela_id: int, cambio: Cambio,
                   citas: dict[int, list[str]]) -> None:
    h = lectura.hecho_vigente(con, novela_id, int(cambio.hecho_id or 0))
    if h is None:
        raise CanonDesfasado(f"El hecho {cambio.hecho_id} ya no esta vigente.")
    fila = _filas(con, "SELECT * FROM hecho_vigente WHERE id = ?", int(h["id"]))[0]
    cita = next(iter(citas.get(int(h["capitulo"]), [])), None) or fila["cita"]
    nuevo = _sustituir_hecho(con, novela_id, fila, valor=cambio.despues, cita=cita)
    # La via `menciona` guarda como cita el valor que encontro en la prosa (RF3-BIB-01).
    con.execute(
        "UPDATE hecho_uso SET cita = ? WHERE hecho_id = ? AND via = 'menciona'",
        (cambio.despues, nuevo),
    )


def _sustituir_hecho(con: sqlite3.Connection, novela_id: int, h: dict[str, Any],
                     **nuevos: Any) -> int:
    """Revoca el hecho y lo inserta de nuevo en su misma escena con los campos nuevos.

    Un hecho no se modifica nunca (el trigger `hecho_inmutable`, RF2-PER-06): cambiarlo es
    revocarlo, con el motivo, e insertar otro. Lo que colgaba del viejo pasa al nuevo.
    """
    capitulo = int(con.execute(
        "SELECT capitulo_numero FROM escena_ordinal WHERE escena_id = ?", (h["escena_id"],)
    ).fetchone()[0])
    con.execute(
        "INSERT INTO hecho_revocacion (novela_id, hecho_id, capitulo, motivo) "
        "VALUES (?, ?, ?, 'cambio_lector')",
        (novela_id, h["id"], capitulo),
    )
    campos = {**h, **nuevos}
    # Se relee: si un hecho anterior de la misma pasada ya se sustituyo, este apunta al nuevo.
    supersede_a = con.execute(
        "SELECT supersede_a FROM hecho WHERE id = ?", (h["id"],)
    ).fetchone()[0]
    nuevo = insertar_hecho(
        con, sujeto_nombre=str(campos["sujeto_nombre"] or ""), atributo=str(campos["atributo"]),
        valor=str(campos["valor"]), novela_id=novela_id, escena_id=h["escena_id"],
        sujeto_tipo=h["sujeto_tipo"], sujeto_id=h["sujeto_id"], categoria=h["categoria"],
        cita=campos["cita"], supersede_a=supersede_a,
    )
    for tabla in _QUE_APUNTAN_A_UN_HECHO:
        con.execute(f"UPDATE {tabla} SET hecho_id = ? WHERE hecho_id = ?", (nuevo, h["id"]))
    con.execute("UPDATE hecho SET supersede_a = ? WHERE supersede_a = ?", (nuevo, h["id"]))
    return nuevo


# --- La prosa corregida (RF3-CAM-11, paso 2) ----------------------------------------------------


def textos_del_capitulo(con: sqlite3.Connection, novela_id: int, numero: int) -> dict[int, str]:
    """El texto vigente de cada escena del capitulo, por su orden."""
    return {
        int(f["orden"]): str(f["texto"]) for f in con.execute(
            """
            SELECT e.orden, et.texto FROM escena e
            JOIN capitulo c ON c.id = e.capitulo_id
            JOIN escena_texto et ON et.escena_id = e.id AND et.estado = 'vigente'
            WHERE e.novela_id = ? AND c.numero = ?
            ORDER BY e.orden
            """,
            (novela_id, numero),
        )
    }


def guardar_textos(con: sqlite3.Connection, novela_id: int, numero: int,
                   textos: dict[int, str]) -> list[int]:
    """Una version nueva de cada escena que cambio, con origen `revision` (RF-PER-05).

    La anterior queda `descartada`, nunca se borra. Devuelve los ordenes que cambiaron.
    """
    cambiados: list[int] = []
    for orden, escena_id, previo in con.execute(
        """
        SELECT e.orden, e.id, et.texto FROM escena e
        JOIN capitulo c ON c.id = e.capitulo_id
        JOIN escena_texto et ON et.escena_id = e.id AND et.estado = 'vigente'
        WHERE e.novela_id = ? AND c.numero = ?
        ORDER BY e.orden
        """,
        (novela_id, numero),
    ).fetchall():
        texto = textos.get(int(orden))
        if texto is None or texto == previo:
            continue
        con.execute("UPDATE escena_texto SET estado = 'descartada' WHERE escena_id = ? "
                    "AND estado = 'vigente'", (escena_id,))
        version = int(con.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM escena_texto WHERE escena_id = ?",
            (escena_id,),
        ).fetchone()[0])
        con.execute(
            "INSERT INTO escena_texto (novela_id, escena_id, version, texto, palabras, origen, "
            "estado) VALUES (?, ?, ?, ?, ?, 'revision', 'vigente')",
            (novela_id, escena_id, version, texto, len(texto.split())),
        )
        cambiados.append(int(orden))
    return cambiados


def _filas(con: sqlite3.Connection, sql: str, *params: object) -> list[dict[str, Any]]:
    return [dict(f) for f in con.execute(sql, params).fetchall()]
