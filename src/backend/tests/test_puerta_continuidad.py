"""Tests de la puerta 3 por mutacion (propiedades 6 y 7 del plan de verificacion).

El grafo de `fabrica.novela_minima` es correcto. Cada test introduce UNA contradiccion y
exige que la puerta la detecte; los dos ultimos exigen lo contrario, que no invente
conflictos donde hay una explicacion legitima (supersede_a y analepsis).
"""

from __future__ import annotations

import sqlite3
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from compartido import db
from tareas.continuidad import puerta
from tests.fabrica import Grafo, novela_minima


@pytest.fixture()
def grafo() -> Iterator[tuple[sqlite3.Connection, Grafo]]:
    ruta = Path(tempfile.mkdtemp()) / "novela.db"
    con = db.preparar(ruta)
    con.execute("BEGIN")
    g = novela_minima(con)
    con.execute("COMMIT")
    yield con, g
    con.close()


def comprobaciones(con: sqlite3.Connection, g: Grafo, capitulo: int = 2) -> set[str]:
    resultado = puerta.evaluar(con, g.novela_id, capitulo)
    return {c.comprobacion for c in resultado.bloqueantes}


# --- El grafo limpio no produce conflictos ------------------------------------------------


def test_grafo_correcto_pasa(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    con, g = grafo
    assert db.verificar_integridad(con) == []
    for capitulo in (1, 2):
        resultado = puerta.evaluar(con, g.novela_id, capitulo)
        assert resultado.pasa, [str(c) for c in resultado.bloqueantes]


# --- Una mutacion por tipo de conflicto ----------------------------------------------------


def test_detecta_contradiccion_factual(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    con, g = grafo
    con.execute(
        """
        INSERT INTO hecho (novela_id, escena_id, sujeto_tipo, sujeto_id, sujeto_nombre,
                           atributo, valor, categoria, cita)
        VALUES (?,?,'personaje',?,?,'color de ojos','azules','fisico','los ojos azules')
        """,
        (g.novela_id, g.escenas[(2, 1)], g.personajes["Ibarra"], "Ibarra"),
    )
    assert "continuidad_factual" in comprobaciones(con, g)


def test_detecta_conocimiento_no_adquirido(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    con, g = grafo
    # Reyes usa el hecho sin haberlo recibido nunca.
    con.execute(
        "INSERT INTO uso_conocimiento (novela_id, personaje_id, hecho_id, escena_id) "
        "VALUES (?,?,?,?)",
        (g.novela_id, g.personajes["Reyes"], g.hechos["ojos"], g.escenas[(2, 1)]),
    )
    assert "conocimiento_no_adquirido" in comprobaciones(con, g)


def test_detecta_personaje_muerto_que_reaparece(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    con, g = grafo
    con.execute(
        "INSERT INTO estado_personaje (novela_id, personaje_id, escena_id, salud_fisica) "
        "VALUES (?,?,?, 'muerta por descompresion')",
        (g.novela_id, g.personajes["Ibarra"], g.escenas[(1, 2)]),
    )
    assert "presencia_imposible" in comprobaciones(con, g)


def test_detecta_dos_lugares_a_la_vez(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    con, g = grafo
    # Las dos escenas del capitulo 2 pasan en la misma fecha interna y en lugares distintos.
    con.execute(
        "UPDATE evento SET fecha_interna = 'dia 3' WHERE escena_id = ?",
        (g.escenas[(2, 2)],),
    )
    con.execute(
        "UPDATE evento SET fecha_interna = 'dia 3' WHERE escena_id = ?",
        (g.escenas[(2, 1)],),
    )
    assert "presencia_imposible" in comprobaciones(con, g)


def test_detecta_objeto_sin_traslado(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    con, g = grafo
    # La baliza aparece en la esclusa sin que nadie la haya movido alli.
    con.execute("UPDATE escena SET lugar_id = ? WHERE id = ?",
                (g.lugares["Esclusa"], g.escenas[(2, 2)]))
    con.execute("DELETE FROM estado_objeto WHERE escena_id = ?", (g.escenas[(2, 2)],))
    assert "objeto_sin_traslado" in comprobaciones(con, g)


def test_detecta_retroceso_temporal(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    con, g = grafo
    con.execute("UPDATE evento SET orden_interno = 0 WHERE escena_id = ?",
                (g.escenas[(2, 1)],))
    assert "coherencia_temporal" in comprobaciones(con, g)


def test_detecta_entidad_fuera_de_canon(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    con, g = grafo
    con.execute(
        "INSERT INTO entidad_no_reconocida (novela_id, escena_id, nombre, contexto) "
        "VALUES (?,?,'Doctor Vance','aparece sin estar en el paquete')",
        (g.novela_id, g.escenas[(2, 1)]),
    )
    assert "entidad_fuera_de_canon" in comprobaciones(con, g)


# --- Nada de falsos positivos --------------------------------------------------------------


def test_supersede_no_es_contradiccion(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    """Una herida que cicatriza no contradice la herida."""
    con, g = grafo
    con.execute(
        """
        INSERT INTO hecho (novela_id, escena_id, sujeto_tipo, sujeto_id, sujeto_nombre,
                           atributo, valor, categoria, cita, supersede_a)
        VALUES (?,?,'personaje',?,?,'color de ojos','azules','fisico','los ojos azules',?)
        """,
        (g.novela_id, g.escenas[(2, 1)], g.personajes["Ibarra"], "Ibarra", g.hechos["ojos"]),
    )
    assert "continuidad_factual" not in comprobaciones(con, g)


def test_analepsis_no_es_retroceso_temporal(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    """Un flashback marcado no es un error de cronologia."""
    con, g = grafo
    con.execute("UPDATE evento SET orden_interno = 0 WHERE escena_id = ?",
                (g.escenas[(2, 1)],))
    con.execute("UPDATE escena SET analepsis = 1 WHERE id = ?", (g.escenas[(2, 1)],))
    assert "coherencia_temporal" not in comprobaciones(con, g)


def test_sorpresa_repetida_es_aviso_y_no_para(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    con, g = grafo
    con.execute(
        "INSERT INTO estado_conocimiento (novela_id, personaje_id, hecho_id, escena_id, postura,"
        " via) VALUES (?,?,?,?, 'sabe','se_lo_contaron')",
        (g.novela_id, g.personajes["Kowalski"], g.hechos["ojos"], g.escenas[(2, 1)]),
    )
    resultado = puerta.evaluar(con, g.novela_id, 2)
    assert resultado.pasa, "una sorpresa repetida es aviso, no debe parar el pipeline"
    assert any(c.comprobacion == "sorpresa_imposible" for c in resultado.avisos)


# --- El indice no cambia ningun veredicto (propiedad 25) -----------------------------------


def test_puerta_no_depende_del_indice(grafo: tuple[sqlite3.Connection, Grafo]) -> None:
    """Ningun veredicto de puerta cambia si el indice vectorial esta o no."""
    from compartido.vectores import Indice

    con, g = grafo
    sin_indice = {c.comprobacion for c in puerta.evaluar(con, g.novela_id, 2).conflictos}
    con.execute("BEGIN")
    Indice(con, modelo="hash")
    con.execute("COMMIT")
    con_indice = {c.comprobacion for c in puerta.evaluar(con, g.novela_id, 2).conflictos}
    assert sin_indice == con_indice
