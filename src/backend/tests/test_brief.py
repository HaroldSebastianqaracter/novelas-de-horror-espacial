"""El brief personalizado: modelo, analisis determinista, API y worker (spec3, 3.2).

El analisis decide que falta y que se contradice sin llamar a ningun modelo (RF3-BRF-03), asi
que aqui se prueba entero con entradas concretas: cada contradiccion en rojo con su caso
minimo, y la ausencia de falsos positivos con el brief de ejemplo del README.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import main
import worker
from compartido import db
from compartido.brief import (
    Brief,
    BriefIncompleto,
    analizar,
    elementos,
    restricciones_derivadas,
)
from compartido.grafo import lectura
from compartido.texto import contiene_termino
from orquestador import cola
from tests.entorno import cfg_de, contar, nueva_bd

RAIZ_REPO = Path(__file__).resolve().parents[3]
EJEMPLO = RAIZ_REPO / "ejemplos" / "brief-ejemplo.json"


def brief_ejemplo() -> dict[str, Any]:
    return json.loads(EJEMPLO.read_text(encoding="utf-8"))["payload"]["brief"]


def con_cambios(**cambios: Any) -> Brief:
    datos = brief_ejemplo()
    for ruta, valor in cambios.items():
        destino = datos
        partes = ruta.split("__")
        for p in partes[:-1]:
            destino = destino[p]
        destino[partes[-1]] = valor
    return Brief.model_validate(datos)


def codigos(b: Brief) -> set[str]:
    return {c.codigo for c in analizar(b).contradicciones}


# --- Terminos -------------------------------------------------------------------------------


@pytest.mark.parametrize(("texto", "termino", "esperado"), [
    ("Las naves ardian en el muelle", "la nave", True),
    ("Tres motores fallaron", "motor", True),
    ("Le daban miedo las ARAÑAS", "araña", True),
    ("Una araña enorme", "arañas", True),
    ("Laurana volvio tarde", "Laura", False),
    ("Una pena muy honda", "peña", False),
    ("Camión y camion", "camion", True),
])
def test_contiene_termino(texto: str, termino: str, esperado: bool) -> None:
    assert contiene_termino(texto, termino) is esperado


# --- Analisis (RF3-BRF-03) -------------------------------------------------------------------


def test_el_brief_de_ejemplo_esta_completo() -> None:
    analisis = analizar(Brief.model_validate(brief_ejemplo()))
    assert analisis.completo, analisis.como_dict()


def test_un_brief_vacio_dice_todo_lo_que_falta_en_orden() -> None:
    assert analizar(Brief()).faltantes == [
        "destinatario.nombre", "destinatario.edad", "destinatario.pronombres",
        "destinatario.rasgos", "recuerdos", "ocasion", "quien_regala", "intensidad", "tono",
    ]


def test_edad_bajo_la_intensidad_es_contradiccion() -> None:
    assert "edad_bajo_intensidad" in codigos(con_cambios(destinatario__edad=12))
    assert "edad_bajo_intensidad" not in codigos(con_cambios(destinatario__edad=14))


def test_por_debajo_de_diez_anos_no_hay_nivel_aunque_falte_la_intensidad() -> None:
    b = con_cambios(destinatario__edad=8, intensidad=None)
    assert "edad_bajo_intensidad" in codigos(b)


def test_subgenero_corporal_en_atmosferico_es_contradiccion() -> None:
    b = con_cambios(subgenero="terror_corporal", intensidad="atmosferico")
    assert "subgenero_exige_intensidad" in codigos(b)
    assert "subgenero_exige_intensidad" not in codigos(
        con_cambios(subgenero="horror_cosmico", intensidad="atmosferico")
    )


def test_un_vetado_en_un_elemento_obligatorio_es_contradiccion_con_plural_y_tilde() -> None:
    # «camión» esta vetado; el recuerdo nuevo dice «camiones», en plural y sin tilde. La eñe,
    # en cambio, no se pierde: «arana» no es «araña», igual que «pena» no es «peña».
    datos = brief_ejemplo()
    datos["vetados"] = ["camión"]
    datos["recuerdos"].append({"texto": "Los camiones del puerto la despertaban cada madrugada"})
    assert "elemento_con_vetado" in codigos(Brief.model_validate(datos))


def test_un_vetado_en_un_elemento_opcional_no_es_contradiccion() -> None:
    datos = brief_ejemplo()
    datos["recuerdos"].append({"texto": "Le dan asco las arañas", "obligatorio": False})
    assert "elemento_con_vetado" not in codigos(Brief.model_validate(datos))


def test_el_nombre_de_un_allegado_vetado_es_contradiccion() -> None:
    assert "elemento_con_vetado" in codigos(con_cambios(vetados=["Nala"]))


def test_validar_completo_lanza_con_las_dos_listas() -> None:
    with pytest.raises(BriefIncompleto) as exc:
        con_cambios(destinatario__edad=12, tono=None).validar_completo()
    assert exc.value.analisis.faltantes == ["tono"]
    assert [c.codigo for c in exc.value.analisis.contradicciones] == ["edad_bajo_intensidad"]


# --- Lo que el pipeline saca del brief -------------------------------------------------------


def test_los_codigos_son_estables_y_por_tipo() -> None:
    b = Brief.model_validate(brief_ejemplo()).con_codigos()
    assert [e.codigo for e in b.destinatario.rasgos] == ["RAS1", "RAS2", "RAS3"]
    assert [e.codigo for e in b.recuerdos] == ["REC1", "REC2", "REC3"]
    assert [a.codigo for a in b.allegados] == ["ALL1", "ALL2"]
    assert b.con_codigos() == b


def test_restricciones_derivadas_de_la_escala_y_la_intensidad() -> None:
    r = restricciones_derivadas(Brief.model_validate(brief_ejemplo()))
    assert r["capitulos"] == "10"
    assert r["longitud_objetivo_palabras"] == "12500"
    assert r["longitud_capitulo_palabras"] == "1000-1500"
    assert "14" in r["publico"]


def test_elementos_lleva_todos_los_del_brief() -> None:
    tipos = [e[1] for e in elementos(Brief.model_validate(brief_ejemplo()))]
    assert tipos == ["rasgo"] * 3 + ["recuerdo"] * 3 + ["allegado"] * 2


# --- API (RF3-PER-05) ---------------------------------------------------------------------------


@pytest.fixture()
def cliente() -> Iterator[TestClient]:
    ruta = Path(tempfile.mkdtemp()) / "novela.db"
    db.preparar(ruta).close()
    main.app.state.cfg = cfg_de(ruta)
    with TestClient(main.app) as c:
        yield c


def test_la_api_acepta_el_brief_de_ejemplo(cliente: TestClient) -> None:
    cuerpo = json.loads(EJEMPLO.read_text(encoding="utf-8"))
    assert cliente.post("/intenciones", json=cuerpo).status_code == 202


def test_la_api_rechaza_un_brief_contradictorio_con_el_motivo(cliente: TestClient) -> None:
    brief = brief_ejemplo()
    brief["destinatario"]["edad"] = 12
    r = cliente.post("/intenciones", json={"tipo": "crear_novela", "payload": {"brief": brief}})
    assert r.status_code == 422
    assert "intensidad" in r.json()["mensaje"]


def test_la_api_rechaza_un_brief_incompleto(cliente: TestClient) -> None:
    r = cliente.post("/intenciones", json={
        "tipo": "crear_novela", "payload": {"brief": {"destinatario": {"nombre": "Ana"}}},
    })
    assert r.status_code == 422
    assert "falta destinatario.edad" in r.json()["mensaje"]


def test_el_payload_sin_brief_sigue_funcionando(cliente: TestClient) -> None:
    r = cliente.post("/intenciones", json={"tipo": "crear_novela", "payload": {"titulo": "X"}})
    assert r.status_code == 202


# --- Worker (RF3-PER-01, RF3-PER-02) -------------------------------------------------------------


def _crear(w: worker.Worker, payload: dict[str, Any]) -> cola.Intencion:
    from compartido.db import transaccion

    with transaccion(w.con):
        iid = cola.encolar(w.con, "crear_novela", None, **payload)
    intencion = cola.Intencion(id=iid, tipo="crear_novela", novela_id=None, payload=payload)
    w._crear_novela(intencion)
    return intencion


def test_el_worker_guarda_brief_elementos_restricciones_y_entrevista() -> None:
    _, ruta = nueva_bd()
    w = worker.Worker(cfg_de(ruta))
    _crear(w, {"brief": brief_ejemplo(), "entrevista": {"turnos": [{"pregunta": "?"}]}})

    novela_id = int(w.con.execute("SELECT MAX(id) FROM novela").fetchone()[0])
    guardado = lectura.brief(w.con, novela_id)
    assert guardado is not None
    assert guardado.destinatario.nombre == "Marta Ibáñez"
    assert guardado.recuerdos[0].codigo == "REC1"
    assert contar(w.con, "SELECT COUNT(*) FROM elemento_personal WHERE novela_id = ?",
                  novela_id) == 8
    assert lectura.restricciones(w.con, novela_id)["capitulos"] == "10"
    assert contar(w.con, "SELECT COUNT(*) FROM entrevista WHERE novela_id = ?", novela_id) == 1
    # El titulo lo propone el arquitecto.
    assert (lectura.novela(w.con, novela_id) or {})["titulo"] == ""


def test_el_worker_rechaza_un_brief_invalido_aunque_no_venga_de_la_api() -> None:
    _, ruta = nueva_bd()
    w = worker.Worker(cfg_de(ruta))
    brief = brief_ejemplo()
    brief["intensidad"] = "intenso"  # 34 años: valido. Ahora lo rompemos:
    brief["destinatario"]["edad"] = 16
    intencion = _crear(w, {"brief": brief})
    fila = w.con.execute(
        "SELECT estado, motivo FROM intencion WHERE id = ?", (intencion.id,)
    ).fetchone()
    assert fila["estado"] == "rechazada"
    assert "intenso" in fila["motivo"]
    assert contar(w.con, "SELECT COUNT(*) FROM novela") == 0


def test_la_migracion_crea_las_tablas_del_brief() -> None:
    con, _ = nueva_bd()
    tablas = {f[0] for f in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"brief", "elemento_personal", "escena_elemento", "entrevista"} <= tablas
    columnas = {f["name"] for f in con.execute("PRAGMA table_info(novela)")}
    assert "dedicatoria" in columnas
    assert db.version_actual(con) == db.version_objetivo()

