"""Loop §6 con dobles (§9): tanda parcial, QA en cadencia, EX-03/07/08, tope de llamadas, equivalencia INV-06, reanudación INV-07, interrupción."""

import json
import os
import shutil
import warnings
from pathlib import Path

import pytest

from app.config import cargar_config
from app.errores import LongitudFueraDeRangoAviso, PausadoPorQAError, PersonajeNoPrevistoError, OutlineFaltanteError, ConfiguracionInconsistenteError, ManifiestoInconsistenteError
from app.orchestrator import checkpoint, cursor as cur, loop
from app.rutas import Rutas
from app.schemas import Outline
from app.state import repository as repo
from tests.conftest import AgentesDobles, construir_proyecto, outline_de_prueba


def test_tanda_de_3_cierra_3_y_corre_qa_en_cadencia(proyecto, config, dobles):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        r = loop.ejecutar_tanda(config, proyecto, dobles)
    assert (r.cerrados, r.motivo) == (3, "tope_de_tanda")
    m = checkpoint.leer_manifest(proyecto)
    assert (m.ultimo_capitulo_cerrado, m.estado, m.ultimo_qa_ejecutado) == (3, "en_progreso", 3)
    rutas = Rutas(proyecto)
    assert all(rutas.capitulo(n).exists() for n in (1, 2, 3)) and not rutas.capitulo(4).exists()
    assert not rutas.cursor.exists()  # el cursor se borra al terminar
    assert rutas.reporte_qa_json(3).exists() and rutas.recursos_usados.exists() and rutas.metricas_qa.exists()
    log = repo.leer_continuidad(proyecto)
    assert len(log) == 3 + 2 * 3 and [h.cap_origen for h in log.root[3:]] == [1, 1, 2, 2, 3, 3]  # cap_origen lo fija el harness
    assert repo.leer_personajes(proyecto).root["Kovacs"].ultima_aparicion == 3
    assert repo.leer_personajes(proyecto).root["Kovacs"].secretos_que_conoce == ["Secreto del capítulo 1", "Secreto del capítulo 2", "Secreto del capítulo 3"]
    from app.state import resumen_rodante as rr
    # X-02.3: el almacenamiento conserva todos los capítulos; la ventana (2) solo recorta lo que se entrega.
    resumen = repo.leer_resumen_rodante(proyecto)
    assert rr.capitulos_cubiertos(resumen) == [1, 2, 3]
    assert rr.capitulos_cubiertos(rr.para_escritor(resumen, config.ventana_resumen_rodante)) == [2, 3]
    assert m.prompts_hash.keys() == {"escritor", "extractor", "qa"}
    # el escritor nunca recibió rutas de capítulos cerrados ni su texto
    for i, prompt in enumerate(dobles.prompts_escritor, start=1):
        for k in range(1, i):
            assert f"cap_{k}.md" not in prompt and f"Texto del capítulo {k}." not in prompt


def test_override_de_linea_de_comandos_y_hasta_el_final(proyecto, config, dobles):
    r = loop.ejecutar_tanda(config, proyecto, dobles, capitulos_por_tanda=1)
    assert (r.cerrados, r.motivo) == (1, "tope_de_tanda")
    config_pocos = config.model_copy(update={"total_capitulos": 30})
    r = loop.ejecutar_tanda(config_pocos, proyecto, dobles, capitulos_por_tanda=2)
    assert (r.cerrados, checkpoint.leer_manifest(proyecto).ultimo_capitulo_cerrado) == (2, 3)


def test_qa_con_contradiccion_pausa_y_no_reanuda(proyecto, config):
    dobles = AgentesDobles(proyecto, contradiccion_en={3})
    r = loop.ejecutar_tanda(config, proyecto, dobles, capitulos_por_tanda=5)
    assert (r.cerrados, r.motivo) == (3, "pausado_por_qa")
    m = checkpoint.leer_manifest(proyecto)
    assert (m.estado, m.reporte_qa_pendiente) == ("pausado_por_qa", "qa_cap_3")
    with pytest.raises(PausadoPorQAError):
        loop.ejecutar_tanda(config, proyecto, dobles)
    # edición manual del manifiesto: se detecta y no reanuda (RF-07.4)
    checkpoint.escribir_manifest(proyecto, m.model_copy(update={"estado": "en_progreso"}))
    with pytest.raises(ManifiestoInconsistenteError):
        loop.ejecutar_tanda(config, proyecto, dobles)


def test_ex07_un_reintento_con_feedback_y_luego_aviso(proyecto, config):
    dobles = AgentesDobles(proyecto, cortos={(1, 1), (2, 1), (2, 2)})
    with warnings.catch_warnings(record=True) as avisos:
        warnings.simplefilter("always")
        r = loop.ejecutar_tanda(config, proyecto, dobles, capitulos_por_tanda=2)
    assert r.cerrados == 2
    assert dobles.intentos == {1: 2, 2: 2}  # exactamente un reintento por capítulo
    assert "El borrador tiene 300 palabras" in dobles.prompts_escritor[1]  # el desvío viaja como feedback
    m = checkpoint.leer_manifest(proyecto)
    assert m.intentos_por_capitulo == {"2": 2}  # el 1 se recuperó, el 2 se aceptó con aviso
    assert any(issubclass(a.category, LongitudFueraDeRangoAviso) for a in avisos)
    assert len(list(Rutas(proyecto).manuscrito.glob("cap_*.md"))) == 2  # un solo archivo por capítulo


def test_ex08_regenera_una_vez_y_detiene_a_la_segunda(proyecto, config):
    dobles = AgentesDobles(proyecto, personaje_extra={1: 1, 2: 2})
    r = None
    with pytest.raises(PersonajeNoPrevistoError, match="capítulo 2"):
        r = loop.ejecutar_tanda(config, proyecto, dobles, capitulos_por_tanda=3)
    assert dobles.extracciones == {1: 2, 2: 2}
    m = checkpoint.leer_manifest(proyecto)
    assert m.ultimo_capitulo_cerrado == 1 and m.intentos_por_capitulo == {"1": 2, "2": 2}
    assert "EX-08" in m.ultimo_error and m.estado == "en_progreso"  # sin estado abortado (§5)
    assert "Vos" not in repo.leer_personajes(proyecto).root  # nada del delta rechazado se persistió
    assert not Rutas(proyecto).cursor.exists()


def test_ex03_outline_faltante_no_gasta_generacion(proyecto, config, dobles):
    outline = repo.leer_outline(proyecto)
    Rutas(proyecto).capitulos.write_text(json.dumps([e.model_dump() for e in outline.root[:2]]), encoding="utf-8")
    with pytest.raises(OutlineFaltanteError):
        loop.ejecutar_tanda(config, proyecto, dobles, capitulos_por_tanda=5)
    assert dobles.intentos == {1: 1, 2: 1}  # el 3 no se pidió
    assert checkpoint.leer_manifest(proyecto).ultimo_capitulo_cerrado == 2


def test_ex06_total_capitulos_cambiado_con_cerrados(proyecto, config, dobles):
    loop.ejecutar_tanda(config, proyecto, dobles, capitulos_por_tanda=1)
    with pytest.raises(ConfiguracionInconsistenteError):
        loop.ejecutar_tanda(config.model_copy(update={"total_capitulos": 31}), proyecto, dobles)


def test_max_llamadas_corta_entre_capitulos(proyecto, config, dobles):
    # 2 llamadas por capítulo (escritor + extractor); tope 3 → cierra 2 capítulos (RF-CFG-06: nunca a mitad de capítulo)
    c = config.model_copy(update={"max_llamadas_por_tanda": 3, "capitulos_por_tanda": None})
    r = loop.ejecutar_tanda(c, proyecto, dobles)
    assert (r.cerrados, r.motivo) == (2, "tope_de_llamadas")
    assert checkpoint.leer_manifest(proyecto).estado == "en_progreso"


def test_novela_completa(tmp_path, monkeypatch):
    raiz = construir_proyecto(tmp_path / "corta", total=30)
    monkeypatch.setenv("HARNESS_RAIZ", str(raiz))
    config = cargar_config(raiz)
    m = checkpoint.leer_manifest(raiz)
    checkpoint.escribir_manifest(raiz, m.model_copy(update={"ultimo_capitulo_cerrado": 28}))
    for n in range(1, 29):
        repo.guardar_capitulo(raiz, n, f"Texto del capítulo {n}.")
    dobles = AgentesDobles(raiz)
    r = loop.ejecutar_tanda(config, raiz, dobles, capitulos_por_tanda=10)
    assert (r.cerrados, r.motivo) == (2, "novela_completa")
    assert checkpoint.leer_manifest(raiz).estado == "completo"
    assert loop.ejecutar_tanda(config, raiz, dobles).motivo == "completo"


def _instantanea(raiz: Path) -> dict[str, bytes]:
    rutas = Rutas(raiz)
    archivos = {}
    for carpeta in (rutas.estado, rutas.manuscrito, rutas.qa):
        for p in carpeta.rglob("*"):
            if p.is_file() and "prompts" not in p.parts and "deltas" not in p.parts:
                archivos[p.relative_to(raiz).as_posix()] = p.read_bytes()
    return archivos


def test_inv06_equivalencia_6_vs_3_mas_3(tmp_path, monkeypatch):
    a = construir_proyecto(tmp_path / "a")
    b = construir_proyecto(tmp_path / "b")
    loop.ejecutar_tanda(cargar_config(a), a, AgentesDobles(a), capitulos_por_tanda=6)
    loop.ejecutar_tanda(cargar_config(b), b, AgentesDobles(b), capitulos_por_tanda=3)
    loop.ejecutar_tanda(cargar_config(b), b, AgentesDobles(b), capitulos_por_tanda=3)
    ia, ib = _instantanea(a), _instantanea(b)
    assert ia.keys() == ib.keys()
    distintos = [k for k in ia if ia[k] != ib[k]]
    assert distintos == []


def test_inv07_reanudar_avanza_y_no_reescribe(proyecto, config):
    loop.ejecutar_tanda(config, proyecto, AgentesDobles(proyecto), capitulos_por_tanda=3)
    rutas = Rutas(proyecto)
    mtimes = {n: rutas.capitulo(n).stat().st_mtime_ns for n in (1, 2, 3)}
    contenidos = {n: rutas.capitulo(n).read_bytes() for n in (1, 2, 3)}
    r = loop.ejecutar_tanda(config, proyecto, AgentesDobles(proyecto, palabras=1400), capitulos_por_tanda=3)
    assert r.cerrados == 3 and checkpoint.leer_manifest(proyecto).ultimo_capitulo_cerrado == 6
    assert {n: rutas.capitulo(n).stat().st_mtime_ns for n in (1, 2, 3)} == mtimes
    assert {n: rutas.capitulo(n).read_bytes() for n in (1, 2, 3)} == contenidos
    assert all(rutas.capitulo(n).exists() for n in (4, 5, 6))


def test_interrupcion_a_mitad_deja_manifiesto_consistente(proyecto, config):
    dobles = AgentesDobles(proyecto, fallar_en=2)
    with pytest.raises(ConnectionError):
        loop.ejecutar_tanda(config, proyecto, dobles, capitulos_por_tanda=3)
    m = checkpoint.leer_manifest(proyecto)
    assert m.ultimo_capitulo_cerrado == 1 and m.estado == "en_progreso"
    assert Rutas(proyecto).cursor.exists()  # cursor huérfano: la siguiente tanda lo descarta y recalcula
    r = loop.ejecutar_tanda(config, proyecto, AgentesDobles(proyecto), capitulos_por_tanda=2)
    assert (r.cerrados, checkpoint.leer_manifest(proyecto).ultimo_capitulo_cerrado) == (2, 3)


def test_tramos_por_cli_equivalen_al_loop(proyecto, config):
    """El camino real: la skill avanza tramo a tramo con los verbos; acá se simula sin subagentes."""
    rutas = Rutas(proyecto)
    dobles = AgentesDobles(proyecto)
    cursor = loop.iniciar_tanda(proyecto, config, capitulos_por_tanda=1)
    assert loop.evaluar_siguiente(proyecto, config, cursor).siguiente == 1
    ctx = loop.preparar_capitulo(proyecto, config, 1)
    assert rutas.prompt_escritor(1).exists() and rutas.prompt_extractor(1).exists() and rutas.hechos_inyectados(1).exists()
    repo.guardar_capitulo(proyecto, 1, dobles.generar_capitulo(ctx.texto))
    r = loop.registrar_escritor(proyecto, config, 1, "cap_1.md · 1500 palabras · personajes: Kovacs · validado")
    assert r.dentro_de_rango and not r.reintentar
    rutas.delta(1).write_text(dobles.extraer("05_manuscrito/cap_1.md"), encoding="utf-8")
    rd = loop.aplicar_delta(proyecto, config, 1)
    assert rd.cerrado and not rd.toca_qa
    fin = loop.tanda_siguiente(proyecto, config)
    assert fin.motivo == "tope_de_tanda" and not rutas.cursor.exists()
