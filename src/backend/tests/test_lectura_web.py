"""Lo que la lectura web pide al backend (specs/spec3.md, 3.7): la portada y las apariciones."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main
from compartido import db
from compartido.db import transaccion
from compartido.grafo import insertar, lectura
from orquestador import pipeline
from tests.entorno import cfg_de, crear_novela, nueva_bd
from tests.test_personalizacion import contexto, crear


def _cliente(ruta: Path) -> Iterator[TestClient]:
    main.app.state.cfg = cfg_de(ruta)
    with TestClient(main.app) as c:
        yield c


@pytest.fixture(scope="module")
def completa() -> tuple[Path, int]:
    """Una novela personalizada completa, con el puerto falso."""
    con, ruta = nueva_bd()
    novela_id = crear(con, ruta, capitulos=3)
    assert pipeline.avanzar(contexto(con, ruta, novela_id)) in (
        "completada", "completada_con_avisos")
    con.close()
    return ruta, novela_id


@pytest.fixture()
def api(completa: tuple[Path, int]) -> Iterator[tuple[TestClient, int, Path]]:
    ruta, novela_id = completa
    for c in _cliente(ruta):
        yield c, novela_id, ruta


# --- RF3-LEC-01: la portada -------------------------------------------------------------------


def test_la_portada_trae_la_dedicatoria_y_el_regalo(api: tuple[TestClient, int, Path]) -> None:
    c, novela_id, ruta = api
    detalle = c.get(f"/novelas/{novela_id}").json()
    con = db.conectar(ruta)
    brief = lectura.brief(con, novela_id)
    novela = lectura.novela(con, novela_id) or {}
    con.close()
    assert brief is not None
    assert detalle["dedicatoria"] == novela["dedicatoria"] and detalle["dedicatoria"]
    assert detalle["regalo"] == {
        "para": brief.destinatario.nombre, "de": brief.quien_regala, "ocasion": "cumpleaños",
    }


def test_la_ocasion_otra_se_lee_por_su_detalle() -> None:
    con, ruta = nueva_bd()
    novela_id = crear(con, ruta, ocasion="otra", ocasion_detalle="fin de la carrera")
    regalo = lectura.regalo(con, novela_id)
    assert regalo is not None and regalo["ocasion"] == "fin de la carrera"


def test_sin_brief_no_hay_regalo() -> None:
    con, ruta = nueva_bd()
    novela_id = crear_novela(con)
    con.close()
    for c in _cliente(ruta):
        detalle = c.get(f"/novelas/{novela_id}").json()
        assert detalle["regalo"] is None and detalle["dedicatoria"] is None


# --- RF3-LEC-02: las apariciones --------------------------------------------------------------


def test_las_apariciones_salen_de_la_presencia_y_del_lugar_de_cada_escena(
    api: tuple[TestClient, int, Path],
) -> None:
    c, novela_id, ruta = api
    datos = c.get(f"/novelas/{novela_id}/apariciones").json()
    con = db.conectar(ruta)
    esperado_personajes: dict[int, set[int]] = {}
    for f in con.execute(
        "SELECT p.personaje_id, c.numero FROM presencia p JOIN escena e ON e.id = p.escena_id "
        "JOIN capitulo c ON c.id = e.capitulo_id WHERE e.novela_id = ?", (novela_id,)
    ):
        esperado_personajes.setdefault(int(f[0]), set()).add(int(f[1]))
    esperado_lugares: dict[int, set[int]] = {}
    for f in con.execute(
        "SELECT e.lugar_id, c.numero FROM escena e JOIN capitulo c ON c.id = e.capitulo_id "
        "WHERE e.novela_id = ?", (novela_id,)
    ):
        esperado_lugares.setdefault(int(f[0]), set()).add(int(f[1]))
    total_personajes = con.execute(
        "SELECT COUNT(*) FROM personaje WHERE novela_id = ?", (novela_id,)).fetchone()[0]
    con.close()

    assert len(datos["personajes"]) == total_personajes
    for p in datos["personajes"]:
        assert p["capitulos"] == sorted(esperado_personajes.get(p["id"], set()))
    assert any(p["capitulos"] for p in datos["personajes"])
    for lg in datos["lugares"]:
        assert lg["capitulos"] == sorted(esperado_lugares.get(lg["id"], set()))


def test_solo_cuentan_los_capitulos_completados_y_quien_no_aparece_sale_vacio() -> None:
    con, ruta = nueva_bd()
    novela_id = crear(con, ruta, capitulos=3)
    assert pipeline.avanzar(contexto(con, ruta, novela_id)) in (
        "completada", "completada_con_avisos")
    with transaccion(con):
        con.execute("UPDATE capitulo SET estado = 'planificado' WHERE novela_id = ? AND "
                    "numero = 3", (novela_id,))
        faccion = con.execute("SELECT faccion_id FROM personaje WHERE novela_id = ? LIMIT 1",
                              (novela_id,)).fetchone()[0]
        nuevo = insertar(con, "personaje", novela_id=novela_id, faccion_id=faccion,
                         nombre="Oriol Fuster", rol_narrativo="aliado")
    datos = lectura.apariciones(con, novela_id)
    assert all(3 not in p["capitulos"] for p in datos["personajes"] + datos["lugares"])
    [ausente] = [p for p in datos["personajes"] if p["id"] == nuevo]
    assert ausente["capitulos"] == []


def test_apariciones_de_una_novela_que_no_existe_es_404(
    api: tuple[TestClient, int, Path],
) -> None:
    c, _, _ = api
    assert c.get("/novelas/9999/apariciones").status_code == 404
