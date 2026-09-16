"""CLI §8.2: status, guardar (fases 0-4), resolver en tres pasos (RF-07.4, RF-07.6), ensamblar, verbos internos."""

import json
import re

import pytest

from app import cli
from app.orchestrator import checkpoint, loop
from app.rutas import Rutas
from app.state import repository as repo
from tests.conftest import AgentesDobles, construir_proyecto, outline_de_prueba


def correr(capsys, *argv):
    codigo = cli.main(list(argv))
    salida = capsys.readouterr()
    return codigo, salida.out, salida.err


def test_status_sin_manifiesto_y_con_manifiesto(tmp_path, monkeypatch, capsys):
    raiz = construir_proyecto(tmp_path / "vacio", con_estado=False)
    monkeypatch.setenv("HARNESS_RAIZ", str(raiz))
    codigo, out, _ = correr(capsys, "status")
    assert codigo == 0 and "no existe" in out and "fase 3" in out
    construir_proyecto(raiz)
    m = checkpoint.leer_manifest(raiz)
    checkpoint.escribir_manifest(raiz, m.model_copy(update={"ultimo_capitulo_cerrado": 12, "estado": "pausado_por_qa", "reporte_qa_pendiente": "qa_cap_12"}))
    codigo, out, _ = correr(capsys, "status")
    assert "ultimo_capitulo_cerrado: 12" in out and "pausado_por_qa" in out and "qa_cap_12" in out  # RF-08.3


def test_guardar_outline_crea_manifest_y_valida(tmp_path, monkeypatch, capsys):
    raiz = construir_proyecto(tmp_path / "p", con_estado=False)
    monkeypatch.setenv("HARNESS_RAIZ", str(raiz))
    borrador = raiz / "outline.json"
    datos = outline_de_prueba(30)
    borrador.write_text(json.dumps(datos[:29]), encoding="utf-8")
    codigo, _, err = correr(capsys, "guardar", "outline", "--desde", str(borrador))
    assert codigo == 1 and "RF-CFG-01" in err
    for d in datos:
        d["tension"] = 2
    datos[0]["tension"] = 5
    borrador.write_text(json.dumps(datos), encoding="utf-8")
    codigo, _, err = correr(capsys, "guardar", "outline", "--desde", str(borrador))
    assert codigo == 1 and "RF-03.2" in err
    borrador.write_text(json.dumps(outline_de_prueba(30)), encoding="utf-8")
    codigo, out, _ = correr(capsys, "guardar", "outline", "--desde", str(borrador))
    assert codigo == 0 and "RESULTADO: guardado" in out
    assert checkpoint.leer_manifest(raiz).total_capitulos_esperado == 30


def test_guardar_personajes_mundo_continuidad_validan_cobertura(tmp_path, monkeypatch, capsys):
    raiz = construir_proyecto(tmp_path / "p", con_estado=False)
    monkeypatch.setenv("HARNESS_RAIZ", str(raiz))
    (raiz / "o.json").write_text(json.dumps(outline_de_prueba(30)), encoding="utf-8")
    assert correr(capsys, "guardar", "outline", "--desde", str(raiz / "o.json"))[0] == 0
    ficha = {"estado_fisico": "a", "estado_psicologico": "b", "secretos_que_conoce": [], "ultima_aparicion": 0}
    (raiz / "p.json").write_text(json.dumps({"Kovacs": ficha, "Ilse": ficha}), encoding="utf-8")
    codigo, _, err = correr(capsys, "guardar", "personajes", "--desde", str(raiz / "p.json"))
    assert codigo == 1 and "Dara" in err  # RF-04.1
    (raiz / "p.json").write_text(json.dumps({"Kovacs": ficha, "Ilse": ficha, "Dara": ficha}), encoding="utf-8")
    assert correr(capsys, "guardar", "personajes", "--desde", str(raiz / "p.json"))[0] == 0
    (raiz / "m.json").write_text(json.dumps({"reglas": ["r"], "objetos": [], "linea_de_tiempo": [], "locaciones": {"Puente": "x"}}), encoding="utf-8")
    codigo, _, err = correr(capsys, "guardar", "mundo", "--desde", str(raiz / "m.json"))
    assert codigo == 1 and "Bodega 4" in err  # RF-04.2
    (raiz / "m.json").write_text(json.dumps({"reglas": ["r"], "objetos": [], "linea_de_tiempo": [], "locaciones": {"Puente": "x", "Bodega 4": "y", "Enfermería": "z"}}), encoding="utf-8")
    assert correr(capsys, "guardar", "mundo", "--desde", str(raiz / "m.json"))[0] == 0
    (raiz / "c.json").write_text(json.dumps([{"sujeto": "mundo", "categoria": "mundo", "hecho": "h", "cap_origen": 1}]), encoding="utf-8")
    codigo, _, err = correr(capsys, "guardar", "continuidad", "--desde", str(raiz / "c.json"))
    assert codigo == 1 and "cap_origen = 0" in err
    (raiz / "c.json").write_text(json.dumps([{"sujeto": "mundo", "categoria": "mundo", "hecho": "h", "cap_origen": 0},
                                              {"sujeto": "el médico", "categoria": "personaje", "hecho": "x", "cap_origen": 0}]), encoding="utf-8")
    assert correr(capsys, "guardar", "continuidad", "--desde", str(raiz / "c.json"))[0] == 0
    log = repo.leer_continuidad(raiz)
    assert [h.sujeto_validado for h in log.root] == [True, False]


def test_guardar_premisa_y_tres_actos_exigen_campos(proyecto, capsys, tmp_path):
    f = tmp_path / "x.md"
    f.write_text("Título: Algo\nLogline: Una frase.\n", encoding="utf-8")
    codigo, _, err = correr(capsys, "guardar", "premisa", "--desde", str(f))
    assert codigo == 1 and "RF-01.1" in err
    f.write_text("Título: Algo\nLogline: Una frase.\nPremisa: Un párrafo.\n", encoding="utf-8")
    assert correr(capsys, "guardar", "premisa", "--desde", str(f))[0] == 0
    f.write_text("## Gancho inicial\nx\n## Punto medio\ny\n", encoding="utf-8")
    codigo, _, err = correr(capsys, "guardar", "tres_actos", "--desde", str(f))
    assert codigo == 1 and "RF-02.1" in err


def test_guardar_style_guide_rechaza_copia_literal(proyecto, capsys, tmp_path):
    rutas = Rutas(proyecto)
    (rutas.referencias / "ejemplo.txt").write_text("El pasillo respiraba con un ritmo que nadie había programado en los ventiladores.", encoding="utf-8")
    f = tmp_path / "sg.md"
    f.write_text("# Guía\n\nUsar frases como: el pasillo respiraba con un ritmo que nadie había programado.\n", encoding="utf-8")
    codigo, _, err = correr(capsys, "guardar", "style_guide", "--desde", str(f))
    assert codigo == 1 and "RF-00.2" in err
    f.write_text("# Guía\n\nDescribir la nave como organismo sin citar los ejemplos.\n", encoding="utf-8")
    assert correr(capsys, "guardar", "style_guide", "--desde", str(f))[0] == 0


def test_inmutables_con_capitulos_cerrados(proyecto, config, capsys, tmp_path):
    loop.ejecutar_tanda(config, proyecto, AgentesDobles(proyecto), capitulos_por_tanda=1)
    f = tmp_path / "o.json"
    f.write_text(json.dumps(outline_de_prueba(30)), encoding="utf-8")
    codigo, _, err = correr(capsys, "guardar", "outline", "--desde", str(f))
    assert codigo == 1 and "INV-04" in err


def test_resolver_en_tres_pasos(proyecto, config, capsys):
    dobles = AgentesDobles(proyecto, contradiccion_en={3})
    loop.ejecutar_tanda(config, proyecto, dobles, capitulos_por_tanda=3)
    assert checkpoint.leer_manifest(proyecto).estado == "pausado_por_qa"
    # errores de uso
    assert correr(capsys, "resolver", "--reporte", "qa_cap_3")[0] == 1  # ni --capitulos ni --sin-cambios
    assert correr(capsys, "resolver", "--reporte", "qa_cap_3", "--capitulos", "2", "--sin-cambios")[0] == 1
    assert correr(capsys, "resolver", "--reporte", "qa_cap_2", "--capitulos", "2")[0] == 1  # reporte equivocado
    codigo, _, err = correr(capsys, "resolver", "--cerrar")  # paso 3 sin paso 1: no se puede saltar la declaración
    assert codigo == 1 and "paso 3 exige" in err
    # paso 1
    codigo, out, _ = correr(capsys, "resolver", "--reporte", "qa_cap_3", "--capitulos", "2,3")
    assert codigo == 0 and "RESULTADO: reextraccion_pendiente" in out
    m = checkpoint.leer_manifest(proyecto)
    assert m.reextraccion_pendiente == [2, 3] and m.capitulo_activo == 2 and m.estado == "pausado_por_qa"
    log = repo.leer_continuidad(proyecto)
    superados = [h for h in log.root if h.superado_por is not None]
    assert len(superados) == 4 and {h.cap_origen for h in superados} == {2, 3}
    assert len(log) == 9  # nada se borró
    # paso 3 prematuro
    codigo, _, err = correr(capsys, "resolver", "--cerrar")
    assert codigo == 1 and "quedan capítulos" in err
    # paso 2: reextracción por capítulo con el delta del doble
    rutas = Rutas(proyecto)
    for k in (2, 3):
        assert correr(capsys, "preparar-extractor", str(k))[0] == 0
        rutas.delta(k).write_text(dobles.extraer(f"05_manuscrito/cap_{k}.md"), encoding="utf-8")
        codigo, out, _ = correr(capsys, "aplicar-delta", str(k), "--reextraccion")
        assert codigo == 0 and "RESULTADO: reextraido" in out
    m = checkpoint.leer_manifest(proyecto)
    assert m.reextraccion_pendiente == [] and m.capitulo_activo is None
    log = repo.leer_continuidad(proyecto)
    assert len(log) == 13  # 9 + 2 + 2 nuevos
    assert len([h for h in log.root if h.superado_por is None and h.cap_origen in (2, 3)]) == 4
    assert repo.leer_personajes(proyecto).root["Kovacs"].ultima_aparicion == 3  # no retrocede
    # paso 3
    codigo, out, _ = correr(capsys, "resolver", "--cerrar")
    assert codigo == 0 and checkpoint.leer_manifest(proyecto).estado == "en_progreso"
    assert checkpoint.leer_manifest(proyecto).reporte_qa_pendiente is None
    # la tanda siguiente reanuda desde el 4 sin reescribir
    r = loop.ejecutar_tanda(config, proyecto, AgentesDobles(proyecto), capitulos_por_tanda=1)
    assert (r.cerrados, checkpoint.leer_manifest(proyecto).ultimo_capitulo_cerrado) == (1, 4)


def test_resolver_sin_cambios_es_un_solo_paso(proyecto, config, capsys):
    loop.ejecutar_tanda(config, proyecto, AgentesDobles(proyecto, contradiccion_en={3}), capitulos_por_tanda=3)
    codigo, out, _ = correr(capsys, "resolver", "--reporte", "qa_cap_3", "--sin-cambios")
    assert codigo == 0 and "RESULTADO: resuelto" in out
    m = checkpoint.leer_manifest(proyecto)
    assert m.estado == "en_progreso" and m.reporte_qa_pendiente is None
    assert all(h.superado_por is None for h in repo.leer_continuidad(proyecto).root)


def test_ensamblar_concatena_con_titulos(proyecto, config, capsys, tmp_path):
    loop.ejecutar_tanda(config, proyecto, AgentesDobles(proyecto), capitulos_por_tanda=2)
    salida = tmp_path / "novela.md"
    codigo, out, _ = correr(capsys, "ensamblar", "--salida", str(salida))
    assert codigo == 0 and "2 capítulos ensamblados" in out
    texto = salida.read_text(encoding="utf-8")
    assert texto.startswith("# El silencio de Ceres")
    assert "## 1. Capítulo de prueba 1" in texto and "## 2. Capítulo de prueba 2" in texto and "## 3." not in texto
    assert "Texto del capítulo 1." in texto


def test_verbos_internos_por_cli(proyecto, config, capsys):
    rutas = Rutas(proyecto)
    dobles = AgentesDobles(proyecto)
    codigo, out, _ = correr(capsys, "tanda", "iniciar", "--capitulos", "1")
    assert codigo == 0 and "RESULTADO: seguir siguiente=1" in out
    codigo, out, _ = correr(capsys, "preparar-capitulo", "1")
    assert codigo == 0 and "RESULTADO: contexto_listo" in out
    repo.guardar_capitulo(proyecto, 1, dobles.generar_capitulo(rutas.prompt_escritor(1).read_text(encoding="utf-8")))
    codigo, _, err = correr(capsys, "registrar-escritor", "1", "Quedó un capítulo precioso lleno de tensión y misterio.")
    assert codigo == 1 and "ContratoRetornoError" in err
    codigo, out, _ = correr(capsys, "registrar-escritor", "1", "cap_1.md · 1500 palabras · personajes: Kovacs")
    assert codigo == 0 and "RESULTADO: borrador_aceptado" in out
    codigo, _, err = correr(capsys, "aplicar-delta", "1")
    assert codigo == 1 and "no existe" in err
    rutas.delta(1).write_text(dobles.extraer("05_manuscrito/cap_1.md"), encoding="utf-8")
    codigo, out, _ = correr(capsys, "aplicar-delta", "1")
    assert codigo == 0 and "RESULTADO: capitulo_cerrado" in out and "toca_qa=false" in out
    codigo, out, _ = correr(capsys, "tanda", "siguiente")
    assert codigo == 0 and "RESULTADO: tope_de_tanda" in out
    assert checkpoint.leer_manifest(proyecto).ultimo_capitulo_cerrado == 1
