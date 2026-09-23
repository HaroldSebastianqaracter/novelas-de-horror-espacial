"""La migracion 002 y lo que hace cumplir (spec2, fase 5: RF2-PIPE-11, RF2-PER-06, RF2-PER-11).

Una base creada con el esquema 1, con datos, migra a la 2 sin perder nada: los hechos ganan
sus claves normalizadas, los que tenian `vigente = 0` pasan a `hecho_revocacion`, las entidades
ganan su nombre normalizado y desde ese momento los triggers impiden volver atras.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from compartido import db


def _base_v1() -> sqlite3.Connection:
    """Una base como la dejaba spec1: solo esquema.sql, sin ninguna migracion."""
    con = db.conectar(Path(tempfile.mkdtemp()) / "novela.db")
    db._aplicar_version(
        con, db.VERSION_ESQUEMA, db.RUTA_ESQUEMA.read_text(encoding="utf-8")
    )
    assert db.version_actual(con) == 1
    return con


def _poblar(con: sqlite3.Connection, *, nombres: tuple[str, ...] = ("Ibarra", "Reyes")) -> dict:
    ids: dict[str, int] = {}
    x = con.execute
    ids["novela"] = x("INSERT INTO novela (titulo) VALUES ('Vieja')").lastrowid
    n = ids["novela"]
    ids["ejecucion"] = x("INSERT INTO ejecucion (novela_id, estado) VALUES (?, 'parada')",
                         (n,)).lastrowid
    ids["parada"] = x(
        "INSERT INTO parada (ejecucion_id, tipo, capitulo, informe) VALUES (?, 'continuidad', 2,"
        " '{}')", (ids["ejecucion"],),
    ).lastrowid
    mundo = x("INSERT INTO mundo (novela_id, nombre) VALUES (?, 'Estacion')", (n,)).lastrowid
    lugar = x("INSERT INTO lugar (novela_id, mundo_id, nombre) VALUES (?, ?, 'Módulo')",
              (n, mundo)).lastrowid
    personajes = [
        x("INSERT INTO personaje (novela_id, nombre, rol_narrativo) VALUES (?, ?, 'aliado')",
          (n, nombre)).lastrowid
        for nombre in nombres
    ]
    acto = x("INSERT INTO acto (novela_id, numero) VALUES (?, 1)", (n,)).lastrowid
    escenas = []
    for numero in (1, 2):
        cap = x("INSERT INTO capitulo (novela_id, acto_id, numero) VALUES (?,?,?)",
                (n, acto, numero)).lastrowid
        escenas.append(x(
            "INSERT INTO escena (novela_id, capitulo_id, pov_id, lugar_id, orden, objetivo, "
            "conflicto, valor_inicial, valor_final) VALUES (?,?,?,?,1,'o','c','a','b')",
            (n, cap, personajes[0], lugar),
        ).lastrowid)
    ids["retirado"] = x(
        "INSERT INTO hecho (novela_id, escena_id, sujeto_tipo, sujeto_id, sujeto_nombre, "
        "atributo, valor, vigente, motivo_no_vigente, parada_id) "
        "VALUES (?,?,'personaje',?,'Ibarra','Color de ojos','Grises',0,'retcon',?)",
        (n, escenas[0], personajes[0], ids["parada"]),
    ).lastrowid
    ids["vigente"] = x(
        "INSERT INTO hecho (novela_id, escena_id, sujeto_tipo, sujeto_id, sujeto_nombre, "
        "atributo, valor) VALUES (?,?,'personaje',?,'Ibarra','Color de pelo','Ámbar')",
        (n, escenas[1], personajes[0]),
    ).lastrowid
    return ids


def _filas(con: sqlite3.Connection) -> dict[str, int]:
    tablas = [f[0] for f in con.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    )]
    return {t: int(con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]) for t in tablas}


def test_una_base_del_esquema_1_migra_a_la_2_y_conserva_los_datos() -> None:
    con = _base_v1()
    ids = _poblar(con)
    antes = _filas(con)

    assert db.migrar(con) == [m.numero for m in db._migraciones()]
    assert db.version_actual(con) == db.version_objetivo()

    despues = _filas(con)
    datos = [t for t in antes if t != "esquema_version"]
    assert {t: despues[t] for t in datos} == {t: antes[t] for t in datos}, (
        "la migracion no borra ni duplica filas"
    )
    assert despues["hecho_revocacion"] == 1

    claves = con.execute(
        "SELECT sujeto_clave, atributo_clave, valor_clave FROM hecho WHERE id = ?",
        (ids["vigente"],),
    ).fetchone()
    assert tuple(claves) == ("ibarra", "color de pelo", "ambar")

    revocacion = con.execute(
        "SELECT hecho_id, parada_id, capitulo, motivo FROM hecho_revocacion"
    ).fetchone()
    assert tuple(revocacion) == (ids["retirado"], ids["parada"], 2, "retcon")
    assert [f[0] for f in con.execute("SELECT id FROM hecho_vigente")] == [ids["vigente"]]

    assert {f[0] for f in con.execute("SELECT nombre_clave FROM personaje")} == {
        "ibarra", "reyes",
    }
    assert con.execute("SELECT nombre_clave FROM lugar").fetchone()[0] == "modulo"


def test_con_nombres_duplicados_la_migracion_aborta_con_la_lista_y_no_toca_nada() -> None:
    con = _base_v1()
    _poblar(con, nombres=("Reyes", "reyes"))
    antes = _filas(con)

    with pytest.raises(db.ErrorDeDatos, match="'Reyes' y 'reyes'"):
        db.migrar(con)

    assert db.version_actual(con) == 1
    assert _filas(con) == antes
    columnas = {f["name"] for f in con.execute("PRAGMA table_info(hecho)")}
    assert "sujeto_clave" not in columnas, "el ALTER de la migracion tiene que revertirse"


def test_crear_el_esquema_no_migra_una_base_existente() -> None:
    """La API solo crea: una base del esquema 1 la migra el worker, con el cerrojo."""
    con = _base_v1()
    assert db.crear_esquema(con) is False
    assert db.version_actual(con) == 1


# --- Lo que los triggers hacen cumplir -------------------------------------------------------


@pytest.fixture()
def migrada() -> tuple[sqlite3.Connection, dict]:
    con = _base_v1()
    ids = _poblar(con)
    db.migrar(con)
    return con, ids


def test_un_hecho_sin_claves_no_entra(migrada: tuple[sqlite3.Connection, dict]) -> None:
    con, ids = migrada
    escena = con.execute("SELECT escena_id FROM hecho WHERE id = ?", (ids["vigente"],)).fetchone()
    with pytest.raises(sqlite3.IntegrityError, match="insertar_hecho"):
        con.execute(
            "INSERT INTO hecho (novela_id, escena_id, sujeto_tipo, sujeto_nombre, atributo, "
            "valor) VALUES (?,?,'mundo','Estacion','gravedad','media')",
            (ids["novela"], escena[0]),
        )


@pytest.mark.parametrize("cambio", ["valor = 'Castaño'", "vigente = 0", "atributo_clave = 'x'"])
def test_un_hecho_no_se_modifica(migrada: tuple[sqlite3.Connection, dict], cambio: str) -> None:
    con, ids = migrada
    with pytest.raises(sqlite3.IntegrityError, match="hecho_revocacion"):
        con.execute(f"UPDATE hecho SET {cambio} WHERE id = ?", (ids["vigente"],))


def test_una_entidad_sin_nombre_normalizado_no_entra(
    migrada: tuple[sqlite3.Connection, dict],
) -> None:
    con, ids = migrada
    with pytest.raises(sqlite3.IntegrityError, match="nombre_clave"):
        con.execute(
            "INSERT INTO personaje (novela_id, nombre, rol_narrativo) VALUES (?, 'Vance', "
            "'mentor')", (ids["novela"],),
        )


def test_borrar_un_hecho_sustituido_sigue_pudiendo_revertir(
    migrada: tuple[sqlite3.Connection, dict],
) -> None:
    """El trigger deja actuar al ON DELETE SET NULL de `supersede_a` al revertir."""
    from compartido.grafo import insertar_hecho

    con, ids = migrada
    escena = con.execute("SELECT escena_id FROM hecho WHERE id = ?", (ids["vigente"],)).fetchone()
    nuevo = insertar_hecho(
        con, novela_id=ids["novela"], escena_id=escena[0], sujeto_tipo="personaje",
        sujeto_nombre="Ibarra", atributo="color de pelo", valor="gris",
        supersede_a=ids["vigente"],
    )
    con.execute("DELETE FROM hecho WHERE id = ?", (ids["vigente"],))
    assert con.execute("SELECT supersede_a FROM hecho WHERE id = ?", (nuevo,)).fetchone()[0] is None
