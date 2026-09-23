"""Versiones de la novela: lo que leyo el lector (specs/spec3.md, RF3-BIB-11 y RF3-BIB-12).

Una version nace cuando la novela se completa con un texto distinto del de la ultima version
publicada. Lo que el harness rehace por dentro (reintentos de oficio, paradas) nunca llega a
completarse con otro texto sin pasar por aqui, y tampoco lo leyo nadie: no es una version.

La version COPIA el texto de cada capitulo. Rehacer la escaleta borra los capitulos y sus
compilados en cascada, y una version que apuntase a ellos perderia su texto.
"""

from __future__ import annotations

import sqlite3
from typing import Literal

from compartido.grafo import emitir_evento, insertar

Motivo = Literal["primera", "relanzamiento", "cambio_lector"]


def _texto_vigente(con: sqlite3.Connection, novela_id: int) -> dict[int, tuple[str, int]]:
    """Numero de capitulo -> (texto, palabras) del compilado vigente."""
    return {
        int(f["numero"]): (str(f["texto"]), int(f["palabras"]))
        for f in con.execute(
            """
            SELECT c.numero, cc.texto, cc.palabras
            FROM capitulo c
            JOIN capitulo_compilado cc ON cc.capitulo_id = c.id AND cc.estado = 'vigente'
            WHERE c.novela_id = ?
            ORDER BY c.numero
            """,
            (novela_id,),
        )
    }


def publicar(
    con: sqlite3.Connection,
    novela_id: int,
    *,
    motivo: Motivo | None = None,
    detalle: str | None = None,
) -> int | None:
    """Publica una version si el texto difiere de la ultima. Devuelve su numero, o None.

    Corre dentro de la transaccion del llamante: la que completa la novela. Sin `motivo`, es
    `primera` si no habia ninguna y `relanzamiento` si la habia; el cambio del lector (bloque 8)
    pasa el suyo.
    """
    capitulos = _texto_vigente(con, novela_id)
    novela = con.execute(
        "SELECT titulo, dedicatoria FROM novela WHERE id = ?", (novela_id,)
    ).fetchone()
    titulo, dedicatoria = str(novela["titulo"]), novela["dedicatoria"]

    ultima = con.execute(
        "SELECT id, numero, titulo, dedicatoria FROM novela_version WHERE novela_id = ? "
        "ORDER BY numero DESC LIMIT 1",
        (novela_id,),
    ).fetchone()
    previos: dict[int, str] = {}
    if ultima is not None:
        previos = {
            int(f["numero"]): str(f["texto"]) for f in con.execute(
                "SELECT numero, texto FROM novela_version_capitulo WHERE version_id = ?",
                (int(ultima["id"]),),
            )
        }
        sin_cambios = (
            previos == {n: t for n, (t, _) in capitulos.items()}
            and ultima["titulo"] == titulo and ultima["dedicatoria"] == dedicatoria
        )
        if sin_cambios:
            return None

    numero = 1 if ultima is None else int(ultima["numero"]) + 1
    elegido: Motivo = motivo or ("primera" if ultima is None else "relanzamiento")
    version_id = insertar(
        con, "novela_version", novela_id=novela_id, numero=numero, motivo=elegido,
        detalle=detalle, titulo=titulo, dedicatoria=dedicatoria,
    )
    cambiados: list[int] = []
    for n, (texto, palabras) in capitulos.items():
        cambiado = previos.get(n) != texto
        if cambiado:
            cambiados.append(n)
        insertar(
            con, "novela_version_capitulo", version_id=version_id, numero=n, texto=texto,
            palabras=palabras, cambiado=int(cambiado),
        )
    emitir_evento(
        con, novela_id, "version_publicada", numero=numero, motivo=elegido,
        capitulos_cambiados=cambiados,
    )
    return numero
