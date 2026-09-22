"""Tests de la puerta 1: que para y que solo avisa.

La regla del cierre de hilos se parte en dos a proposito. Que una subtrama cierre DESPUES del
climax es un defecto estructural seguro y para. Que el anidamiento completo no sea perfecto
se apoya en posiciones aproximadas, asi que avisa.
"""

from __future__ import annotations

import sqlite3
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from compartido import db
from tareas.estructura import puerta
from tests.fabrica import Grafo, novela_minima

GIROS_PRINCIPAL = (
    ("gancho", 2.0),
    ("incidente_incitador", 12.0),
    ("punto_medio", 50.0),
    ("climax", 92.0),
    ("resolucion", 97.0),
)


@pytest.fixture()
def grafo() -> Iterator[tuple[sqlite3.Connection, Grafo]]:
    con = db.preparar(Path(tempfile.mkdtemp()) / "novela.db")
    con.execute("BEGIN")
    g = novela_minima(con)
    con.execute("COMMIT")
    yield con, g
    con.close()


def _hilo(
    con: sqlite3.Connection, g: Grafo, tipo: str, giros: tuple[tuple[str, float], ...]
) -> int:
    hid = int(con.execute(
        "INSERT INTO hilo (novela_id, tipo, conflicto_central) VALUES (?,?,?)",
        (g.novela_id, tipo, f"Conflicto central del hilo {tipo}"),
    ).lastrowid or 0)
    for nombre, posicion in giros:
        con.execute(
            "INSERT INTO punto_de_giro (hilo_id, tipo, posicion) VALUES (?,?,?)",
            (hid, nombre, posicion),
        )
    return hid


def comprobaciones(con: sqlite3.Connection, g: Grafo) -> tuple[set[str], set[str]]:
    r = puerta.evaluar(con, g.novela_id)
    return ({c.comprobacion for c in r.bloqueantes}, {c.comprobacion for c in r.avisos})


def test_estructura_correcta_pasa(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    con, g = grafo
    con.execute("BEGIN")
    _hilo(con, g, "principal", GIROS_PRINCIPAL)
    # La subtrama abre despues y cierra antes: anidada como debe.
    _hilo(con, g, "subtrama", (("primer_umbral", 28.0), ("crisis", 85.0)))
    con.execute("COMMIT")
    bloqueantes, _ = comprobaciones(con, g)
    assert not bloqueantes, bloqueantes


def test_subtrama_que_cierra_tras_el_climax_para(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    con, g = grafo
    con.execute("BEGIN")
    _hilo(con, g, "principal", GIROS_PRINCIPAL)
    # Cierra en el 99 %, despues de la resolucion del principal: apendice colgando.
    _hilo(con, g, "subtrama", (("primer_umbral", 28.0), ("crisis", 99.0)))
    con.execute("COMMIT")
    bloqueantes, _ = comprobaciones(con, g)
    assert "subtrama_cierra_tras_el_principal" in bloqueantes


def test_anidamiento_imperfecto_solo_avisa(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    con, g = grafo
    con.execute("BEGIN")
    _hilo(con, g, "principal", GIROS_PRINCIPAL)
    # Dos subtramas que cierran en el mismo orden en que abrieron, no al reves.
    _hilo(con, g, "subtrama", (("primer_umbral", 20.0), ("crisis", 70.0)))
    _hilo(con, g, "subtrama", (("punto_de_pellizco", 35.0), ("todo_esta_perdido", 80.0)))
    con.execute("COMMIT")
    bloqueantes, avisos = comprobaciones(con, g)
    assert "cierre_en_orden_inverso" in avisos
    assert "cierre_en_orden_inverso" not in bloqueantes
    assert not bloqueantes, bloqueantes


def test_sin_giros_obligatorios_para(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    con, g = grafo
    con.execute("BEGIN")
    _hilo(con, g, "principal", (("gancho", 2.0), ("climax", 92.0)))
    con.execute("COMMIT")
    bloqueantes, _ = comprobaciones(con, g)
    assert "giros_obligatorios" in bloqueantes


def test_final_incompatible_con_el_subgenero_avisa(
    grafo: tuple[sqlite3.Connection, Grafo],
) -> None:
    """Un horror cosmico con final cerrado contradice la premisa del genero, pero es una
    eleccion del autor, no un error de estructura."""
    con, g = grafo
    con.execute("BEGIN")
    _hilo(con, g, "principal", GIROS_PRINCIPAL)
    con.execute("UPDATE novela SET tipo_final = 'cerrado' WHERE id = ?", (g.novela_id,))
    con.execute("COMMIT")
    bloqueantes, avisos = comprobaciones(con, g)
    assert "final_incompatible" in avisos
    assert not bloqueantes, bloqueantes
