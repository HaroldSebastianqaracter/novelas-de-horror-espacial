"""Tests de la API.

Lo que se comprueba aqui no es que los endpoints devuelvan datos, sino las tres reglas que la
arquitectura le impone al borde HTTP: que solo lee, que no ejecuta nada, y que el `GET` es la
verdad aunque el stream se caiga.
"""

from __future__ import annotations

import sqlite3
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import config
import main
from compartido import db
from compartido.db import transaccion
from compartido.puerto import PuertoFalso
from compartido.puerto import demo as agentes_falsos
from orquestador import pipeline


@pytest.fixture()
def cliente() -> Iterator[tuple[TestClient, Path]]:
    ruta = Path(tempfile.mkdtemp()) / "novela.db"
    db.preparar(ruta).close()
    main.app.state.cfg = config.Config(
        db_path=ruta, claude_bin="claude", skills_dir=Path(".claude/skills"), poll_segundos=1,
        timeout_agente_segundos=60, presupuesto_tokens=100_000, puerto="falso",
        puerto_falso_dir=None, embedding_modelo="hash", vectores_activos=False,
    )
    with TestClient(main.app) as c:
        yield c, ruta


def _generar(ruta: Path) -> int:
    """Una novela entera, como la habria dejado el worker."""
    con = db.preparar(ruta)
    from compartido.grafo import insertar

    with transaccion(con):
        novela_id = insertar(con, "novela", titulo="Cerro Quince", genero="terror_espacial")
        insertar(con, "restriccion", novela_id=novela_id,
                 tipo="longitud_objetivo_palabras", valor="5400")
        insertar(con, "ejecucion", novela_id=novela_id, estado="configurada")
    cfg = main.app.state.cfg
    ctx = pipeline.Contexto(
        con=con, puerto=PuertoFalso(generadores=dict(agentes_falsos.TODOS), con=con),
        cfg=cfg, novela_id=novela_id,
    )
    pipeline.avanzar(ctx)
    con.close()
    return novela_id


# --- Las tres reglas del borde -----------------------------------------------------------------


def test_la_api_solo_escribe_intenciones(cliente) -> None:
    """RF-API-02: ninguna ruta cambia nada salvo la tabla de intenciones."""
    c, ruta = cliente
    novela_id = _generar(ruta)

    def foto() -> dict[str, int]:
        con = db.conectar(ruta, solo_lectura=True)
        try:
            tablas = [
                f[0] for f in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name <> 'intencion'"
                )
            ]
            return {t: int(con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
                    for t in tablas}
        finally:
            con.close()

    antes = foto()
    for ruta_http in (
        "/novelas", f"/novelas/{novela_id}", f"/novelas/{novela_id}/ejecucion",
        f"/novelas/{novela_id}/estructura", f"/novelas/{novela_id}/canon/personajes",
        f"/novelas/{novela_id}/capitulos/1", f"/novelas/{novela_id}/capitulos/1/versiones",
        f"/novelas/{novela_id}/hechos", f"/novelas/{novela_id}/conocimiento",
        f"/novelas/{novela_id}/paradas", f"/novelas/{novela_id}/traza/llamadas",
    ):
        assert c.get(ruta_http).status_code == 200, ruta_http

    c.post("/intenciones", json={"tipo": "arrancar", "novela_id": novela_id})
    assert foto() == antes


def test_encolar_una_intencion_no_ejecuta_nada(cliente) -> None:
    c, ruta = cliente
    novela_id = _generar(ruta)

    respuesta = c.post("/intenciones", json={"tipo": "parar", "novela_id": novela_id})
    assert respuesta.status_code == 202
    intencion_id = respuesta.json()["id"]

    # Sigue pendiente: quien la ejecuta es el worker, que aqui no corre.
    estado = c.get(f"/intenciones/{intencion_id}").json()
    assert estado["estado"] == "pendiente"


def test_el_get_es_la_verdad(cliente) -> None:
    c, ruta = cliente
    novela_id = _generar(ruta)
    ejecucion = c.get(f"/novelas/{novela_id}/ejecucion").json()
    assert ejecucion["estado"] in ("completada", "completada_con_avisos")
    assert ejecucion["capitulos_completados"] == agentes_falsos.CAPITULOS
    assert ejecucion["total_capitulos"] == agentes_falsos.CAPITULOS


# --- Contrato -----------------------------------------------------------------------------------


def test_openapi_declara_todas_las_rutas(cliente) -> None:
    """RF-API-01: el frontend genera su cliente desde aqui."""
    c, _ = cliente
    esquema = c.get("/openapi.json").json()
    rutas = set(esquema["paths"])
    assert {
        "/intenciones", "/intenciones/{intencion_id}", "/novelas", "/novelas/{novela_id}",
        "/novelas/{novela_id}/ejecucion", "/novelas/{novela_id}/estructura",
        "/novelas/{novela_id}/capitulos/{numero}", "/novelas/{novela_id}/hechos",
        "/novelas/{novela_id}/paradas", "/novelas/{novela_id}/eventos",
    } <= rutas


def test_errores_en_json_con_codigo(cliente) -> None:
    c, _ = cliente
    respuesta = c.get("/novelas/9999/ejecucion")
    assert respuesta.status_code == 404
    assert respuesta.json()["codigo"] == "no_encontrado"

    respuesta = c.post("/intenciones", json={"tipo": "arrancar"})
    assert respuesta.status_code == 422


def test_intencion_sobre_novela_inexistente_es_404(cliente) -> None:
    c, _ = cliente
    respuesta = c.post("/intenciones", json={"tipo": "arrancar", "novela_id": 4242})
    assert respuesta.status_code == 404


def test_el_manuscrito_se_lee_con_sus_versiones(cliente) -> None:
    c, ruta = cliente
    novela_id = _generar(ruta)

    capitulo = c.get(f"/novelas/{novela_id}/capitulos/1").json()
    assert capitulo["palabras"] > 0
    assert capitulo["version"] == 1

    versiones = c.get(f"/novelas/{novela_id}/capitulos/1/versiones").json()
    assert len(versiones) == agentes_falsos.ESCENAS_POR_CAPITULO
    assert all(v["estado"] == "vigente" for v in versiones)

    assert c.get(f"/novelas/{novela_id}/capitulos/99").status_code == 404


def test_la_traza_no_devuelve_el_prompt_salvo_que_se_pida(cliente) -> None:
    c, ruta = cliente
    novela_id = _generar(ruta)

    breve = c.get(f"/novelas/{novela_id}/traza/llamadas").json()
    assert breve and "entrada" not in breve[0]

    completo = c.get(f"/novelas/{novela_id}/traza/llamadas?completo=true").json()
    assert "entrada" in completo[0]


def test_los_hechos_se_paginan_y_filtran(cliente) -> None:
    c, ruta = cliente
    novela_id = _generar(ruta)

    pagina = c.get(f"/novelas/{novela_id}/hechos?limite=1").json()
    assert pagina["total"] >= 1
    assert len(pagina["items"]) == 1

    filtrado = c.get(f"/novelas/{novela_id}/hechos?sujeto=Puente").json()
    assert all("puente" in (h["sujeto_nombre"] or "").lower() for h in filtrado["items"])


def test_la_conexion_de_lectura_rechaza_escrituras(cliente) -> None:
    """No es disciplina del programador: lo impone el motor."""
    _, ruta = cliente
    con = db.conectar(ruta, solo_lectura=True)
    with pytest.raises(sqlite3.OperationalError):
        con.execute("INSERT INTO novela (titulo) VALUES ('x')")
    con.close()
