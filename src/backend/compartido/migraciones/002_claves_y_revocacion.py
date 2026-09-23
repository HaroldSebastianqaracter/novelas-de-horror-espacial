"""Paso en Python de la migracion 002 (specs/spec2.md, fase 5).

Corre en la misma transaccion que 002_claves_y_revocacion.sql, despues de el:

1. Rellena las claves normalizadas de los hechos que ya existen, con la misma `normalizar()`
   que usa el resolvedor de nombres. SQLite no sabe quitar tildes, por eso esto es Python.
2. Pasa a `hecho_revocacion` los hechos que tenian `vigente = 0`.
3. Rellena `nombre_clave` y, antes de crear los indices unicos, busca duplicados. Si los hay,
   aborta con la lista: no decide por su cuenta cual de dos personajes se queda.
4. Crea los indices unicos y los triggers que hacen cumplir todo lo anterior a partir de ahora.
"""

from __future__ import annotations

import sqlite3

from compartido.db import ErrorDeDatos
from compartido.grafo.escritura import TABLAS_CON_NOMBRE_CLAVE, normalizar


def aplicar(con: sqlite3.Connection) -> None:
    for f in con.execute("SELECT id, sujeto_nombre, atributo, valor FROM hecho").fetchall():
        con.execute(
            "UPDATE hecho SET sujeto_clave = ?, atributo_clave = ?, valor_clave = ? WHERE id = ?",
            (normalizar(f[1] or ""), normalizar(f[2]), normalizar(f[3]), f[0]),
        )

    con.execute(
        """
        INSERT INTO hecho_revocacion (novela_id, hecho_id, parada_id, capitulo, motivo)
        SELECT h.novela_id, h.id, h.parada_id, COALESCE(p.capitulo, eo.capitulo_numero),
               COALESCE(h.motivo_no_vigente, 'retcon')
        FROM hecho h
        JOIN escena_ordinal eo ON eo.escena_id = h.escena_id
        LEFT JOIN parada p ON p.id = h.parada_id
        WHERE h.vigente = 0
        """
    )

    duplicados: list[str] = []
    for tabla in TABLAS_CON_NOMBRE_CLAVE:
        vistos: dict[tuple[int, str], str] = {}
        for f in con.execute(f"SELECT id, novela_id, nombre FROM {tabla}").fetchall():
            clave = normalizar(f[2])
            con.execute(f"UPDATE {tabla} SET nombre_clave = ? WHERE id = ?", (clave, f[0]))
            llave = (int(f[1]), clave)
            if llave in vistos:
                duplicados.append(f"{tabla}: '{vistos[llave]}' y '{f[2]}' (novela {f[1]})")
            else:
                vistos[llave] = str(f[2])
    if duplicados:
        raise ErrorDeDatos(
            "La migracion 002 no puede crear los nombres unicos: hay entidades cuyo nombre "
            "solo difiere en tildes o mayusculas. Renombralas y vuelve a arrancar: "
            + "; ".join(duplicados)
        )

    for tabla in TABLAS_CON_NOMBRE_CLAVE:
        con.execute(f"CREATE UNIQUE INDEX ux_{tabla}_nombre ON {tabla} (novela_id, nombre_clave)")
        con.execute(
            f"CREATE TRIGGER {tabla}_con_nombre_clave BEFORE INSERT ON {tabla} "
            f"WHEN NEW.nombre_clave IS NULL BEGIN "
            f"SELECT RAISE(ABORT, '{tabla} sin nombre_clave: insertalo con grafo.insertar'); END"
        )

    con.execute(
        "CREATE TRIGGER hecho_con_claves BEFORE INSERT ON hecho "
        "WHEN NEW.sujeto_clave IS NULL OR NEW.atributo_clave IS NULL OR NEW.valor_clave IS NULL "
        "BEGIN SELECT RAISE(ABORT, 'hecho sin claves normalizadas: usa insertar_hecho'); END"
    )
    # El hecho es append-only de verdad: ninguna columna de contenido cambia despues de
    # insertarse. `supersede_a` y `parada_id` quedan fuera para que sus ON DELETE SET NULL
    # puedan actuar al revertir.
    con.execute(
        "CREATE TRIGGER hecho_inmutable BEFORE UPDATE OF escena_id, sujeto_tipo, sujeto_id, "
        "sujeto_nombre, atributo, valor, categoria, cita, vigente, motivo_no_vigente, "
        "sujeto_clave, atributo_clave, valor_clave ON hecho "
        "BEGIN SELECT RAISE(ABORT, "
        "'un hecho no se modifica: revocarlo es insertar en hecho_revocacion'); END"
    )
