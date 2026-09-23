"""Tests de la API.

Lo que se comprueba aqui no es que los endpoints devuelvan datos, sino las tres reglas que la
arquitectura le impone al borde HTTP: que solo lee, que no ejecuta nada, y que el `GET` es la
verdad aunque el stream se caiga.
"""

from __future__ import annotations

import json
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


# --- spec2, fase 8: el contrato esta tipado y no cambia sin revision ----------------------------

SNAPSHOT = Path(__file__).with_name("openapi.json")


def _resolver(esquema: dict, raiz: dict) -> dict:
    while "$ref" in esquema:
        nombre = esquema["$ref"].rsplit("/", 1)[-1]
        esquema = raiz["components"]["schemas"][nombre]
    return esquema


def test_ninguna_respuesta_es_un_objeto_sin_esquema(cliente) -> None:
    """RF2-API-01: el cliente generado no puede salir con `any` en ninguna respuesta."""
    c, _ = cliente
    raiz = c.get("/openapi.json").json()
    sueltas: list[str] = []
    for ruta, metodos in raiz["paths"].items():
        for metodo, operacion in metodos.items():
            for codigo, respuesta in operacion.get("responses", {}).items():
                if not codigo.startswith("2"):
                    continue
                contenido = respuesta.get("content", {}).get("application/json")
                if contenido is None:
                    continue  # el SSE es text/event-stream
                esquema = _resolver(contenido["schema"], raiz)
                if esquema.get("type") == "array":
                    esquema = _resolver(esquema["items"], raiz)
                tipado = "properties" in esquema or "oneOf" in esquema or "anyOf" in esquema
                if not tipado:
                    sueltas.append(f"{metodo.upper()} {ruta} -> {esquema}")
    assert not sueltas, "Respuestas sin esquema:\n" + "\n".join(sueltas)


def test_el_contrato_no_cambia_sin_revisarlo(cliente) -> None:
    """Snapshot versionado del OpenAPI. Si el cambio es a proposito, regeneralo con
    NOVELAS_ACTUALIZAR_OPENAPI=1 y revisa el diff antes de commitear."""
    import os

    c, _ = cliente
    actual = c.get("/openapi.json").json()
    if os.environ.get("NOVELAS_ACTUALIZAR_OPENAPI") == "1":
        SNAPSHOT.write_text(
            json.dumps(actual, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    guardado = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert actual == guardado, (
        "El contrato de la API ha cambiado. Si es a proposito, regenera tests/openapi.json "
        "con NOVELAS_ACTUALIZAR_OPENAPI=1 y revisa el diff."
    )


@pytest.mark.parametrize("payload", [
    {"desde_capitulo": "tres"}, {"desde_capitulo": 0}, {},
])
def test_relanzar_con_un_capitulo_que_no_es_entero_es_422(cliente, payload: dict) -> None:
    c, ruta = cliente
    novela_id = _generar(ruta)
    respuesta = c.post(
        "/intenciones", json={"tipo": "relanzar", "novela_id": novela_id, "payload": payload}
    )
    assert respuesta.status_code == 422, respuesta.text
    assert respuesta.json()["codigo"] == "peticion_invalida"


@pytest.mark.parametrize("payload", [
    {"parada_id": 1, "accion": "borrar_todo"}, {"accion": "rehacer"},
    {"parada_id": "una", "accion": "rehacer"},
])
def test_resolver_parada_mal_formada_es_422(cliente, payload: dict) -> None:
    c, ruta = cliente
    novela_id = _generar(ruta)
    respuesta = c.post(
        "/intenciones",
        json={"tipo": "resolver_parada", "novela_id": novela_id, "payload": payload},
    )
    assert respuesta.status_code == 422, respuesta.text


def test_crear_una_novela_sin_titulo_es_422_y_no_500(cliente) -> None:
    c, _ = cliente
    respuesta = c.post("/intenciones", json={"tipo": "crear_novela", "payload": {}})
    assert respuesta.status_code == 422


def test_cada_entidad_del_canon_sale_con_su_esquema(cliente) -> None:
    c, ruta = cliente
    novela_id = _generar(ruta)
    for entidad in ("mundo", "sistemas", "lugares", "personajes", "facciones", "amenaza",
                    "objetos", "temas", "motivos", "eventos"):
        filas = c.get(f"/novelas/{novela_id}/canon/{entidad}").json()
        assert filas, entidad
        assert all(f["entidad"] == entidad for f in filas)
    amenaza = c.get(f"/novelas/{novela_id}/canon/amenaza").json()[0]
    assert amenaza["reglas"] and "capacidad" in amenaza["reglas"][0]
