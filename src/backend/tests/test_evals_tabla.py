"""La tabla de evals (specs/spec3.md, 3.10, RF3-EVL-01 a 04), con el puerto falso.

Los cinco briefs de `ejemplos/` recortados a tres capitulos: el camino entero, sin coste.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import replace
from pathlib import Path

import pytest

import config
from evals import tabla

EJEMPLOS = config.raiz_repo() / "ejemplos"
BRIEFS = [EJEMPLOS / "brief-ejemplo.json", *sorted((EJEMPLOS / "evals").glob("*.json"))]


@pytest.fixture()
def cfg(monkeypatch: pytest.MonkeyPatch) -> config.Config:
    monkeypatch.setenv("NOVELAS_DB_PATH", "sin_uso.db")
    monkeypatch.setenv("NOVELAS_VECTORES", "0")
    return replace(config.cargar(), puerto="falso")


def _dir() -> Path:
    return Path(tempfile.mkdtemp())


def test_hay_cinco_briefs_con_un_adversarial_y_uno_de_incoherencia_temporal() -> None:
    """RF3-EVL-01: los que pide el enunciado, validos y con su proposito escrito."""
    assert len(BRIEFS) == 5
    nombres = {json.loads(b.read_text(encoding="utf-8")).get("eval", {}).get("nombre")
               for b in BRIEFS[1:]}
    assert {"adversarial-inyeccion", "incoherencia-temporal"} <= nombres
    adversarial = json.loads((EJEMPLOS / "evals" / "adversarial-inyeccion.json")
                             .read_text(encoding="utf-8"))
    assert adversarial["eval"]["canario"] in adversarial["payload"]["brief"]["texto_libre"]


def test_un_brief_normal_pasa_de_principio_a_fin(cfg: config.Config) -> None:
    r = tabla.evaluar_brief(BRIEFS[0], _dir(), cfg, capitulos=3)
    assert r.estado in ("completada", "completada_con_avisos")
    assert r.capitulos == "3/3" and r.llamadas > 0
    for clave in ("brief_schema", "brief_completo", "puerta_1", "puerta_5"):
        assert r.celdas[clave] == "pasa", (clave, r.celdas[clave])
    assert r.celdas["inyeccion"] == r.celdas["canario"] == "no aplica"
    assert r.celdas["lean"] == "no integrado"


def test_el_adversarial_detecta_la_inyeccion_y_el_canario_no_llega(cfg: config.Config) -> None:
    r = tabla.evaluar_brief(EJEMPLOS / "evals" / "adversarial-inyeccion.json", _dir(), cfg,
                            capitulos=3)
    assert r.celdas["inyeccion"].startswith("detecta ")
    assert r.celdas["canario"] == "pasa"


def test_un_brief_que_no_cumple_el_schema_no_llega_al_pipeline(cfg: config.Config) -> None:
    roto = _dir() / "roto.json"
    roto.write_text(json.dumps({"payload": {"brief": {"capitulos": 99}}}), encoding="utf-8")
    r = tabla.evaluar_brief(roto, _dir(), cfg)
    assert r.celdas["brief_schema"].startswith("falla")
    assert r.estado == "brief rechazado" and r.celdas["puerta_1"] == "sin ejecutar"


def test_cada_eval_empieza_sobre_una_base_nueva(cfg: config.Config) -> None:
    carpeta = _dir()
    (carpeta / "brief-ejemplo.db").write_text("", encoding="utf-8")
    with pytest.raises(FileExistsError):
        tabla.evaluar_brief(BRIEFS[0], carpeta, cfg, capitulos=3)


@pytest.mark.parametrize(("puerta", "comprobacion", "fila"), [
    (4, "juicio:cuentas_cuadran", "juez"),
    (4, "juicio_dividido", "juez"),
    (4, "termino_vetado", "guardrail"),
    (4, "allegado_ausente", "nombres"),
    (4, "etiqueta_en_la_prosa", "nombres"),
    (4, "longitud_real", "longitud"),
    (4, "palabras_filtro", "puerta_4_mecanica"),
    (3, "conocimiento_no_adquirido", "puerta_3"),
    (1, "destinatario_protagonista", "puerta_1"),
])
def test_cada_comprobacion_va_a_su_fila(puerta: int, comprobacion: str, fila: str) -> None:
    assert tabla.validador_de(puerta, comprobacion) == fila


def test_una_celda_cuenta_evaluaciones_fallos_y_avisos() -> None:
    assert tabla._celda(0, 0, 0) == "sin ejecutar"
    assert tabla._celda(3, 0, 0) == "pasa"
    assert tabla._celda(4, 1, 2) == "falla 1/4 · 2 avisos"


def test_la_tabla_tiene_una_fila_por_validador_y_una_columna_por_brief() -> None:
    a = tabla.Resultado(nombre="uno", proposito="")
    b = tabla.Resultado(nombre="dos", proposito="p")
    texto = tabla.tabla_markdown([a, b])
    assert "| Validador | Tipo | Dónde | uno | dos |" in texto
    for v in tabla.VALIDADORES:
        assert f"| {v.nombre} | {v.tipo} |" in texto


def test_el_cli_escribe_la_tabla_y_su_json(tmp_path: Path) -> None:
    import subprocess
    import sys

    salida = tmp_path / "tabla.md"
    entorno = {**os.environ, "NOVELAS_VECTORES": "0", "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run(
        [sys.executable, "-m", "evals.tabla", str(BRIEFS[0]), "--puerto", "falso",
         "--dir", str(tmp_path / "bases"), "--capitulos", "3", "--salida", str(salida)],
        capture_output=True, text=True, encoding="utf-8", env=entorno,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert r.returncode == 0, r.stderr[-2000:]
    assert "| Schema del brief |" in salida.read_text(encoding="utf-8")
    datos = json.loads(salida.with_suffix(".json").read_text(encoding="utf-8"))
    assert datos[0]["nombre"] == "brief-ejemplo"
