"""Helpers de agentes: ensamblado (RF-05.1, EX-03, EX-04), parsers de retorno (RF-08.1), delta (RF-06.1, EX-08, §11.6), reglas de importación (INV-01, INV-05)."""

import json
import re
from pathlib import Path

import pytest

from app.agents import escritor, extractor, qa
from app.agents.plantillas import MARCADORES_OBLIGATORIOS, verificar_checklist
from app.errores import ContratoRetornoError, EstadoInvalidoError, OutlineFaltanteError
from app.rutas import Rutas
from app.schemas import LogContinuidad, HechoContinuidad
from app.state import repository as repo
from tests.conftest import RAIZ_REAL

FUENTES = RAIZ_REAL / "app" / "agents"


def test_escritor_no_importa_lectura_de_manuscrito():
    fuente = (FUENTES / "escritor.py").read_text(encoding="utf-8")
    assert "leer_manuscrito" not in fuente and "leer_muestra_manuscrito" not in fuente
    assert "rutas.capitulo(" not in fuente.replace("rutas.capitulo(n).as_posix()", "")  # solo la ruta destino, nunca lectura


def test_solo_qa_importa_leer_muestra_manuscrito():
    con_muestra = [p.name for p in FUENTES.glob("*.py") if "leer_muestra_manuscrito" in p.read_text(encoding="utf-8")]
    assert con_muestra == ["qa.py"]


def test_prompts_cumplen_checklist_11_5():
    for rol in MARCADORES_OBLIGATORIOS:
        texto = (RAIZ_REAL / "config" / "prompts" / f"{rol}.md").read_text(encoding="utf-8")
        assert verificar_checklist(texto, rol) == [], rol


def test_ensamblar_contexto_rf_05_1(proyecto, config):
    # capítulo 1: Kovacs en el Puente
    repo.escribir_continuidad(proyecto, LogContinuidad(repo.leer_continuidad(proyecto).root + [
        HechoContinuidad(sujeto="Ilse", categoria="personaje", hecho="Ilse escondió la llave de purga.", cap_origen=0),
        HechoContinuidad(sujeto="Puente", categoria="locacion", hecho="El Puente perdió la iluminación principal.", cap_origen=0),
        HechoContinuidad(sujeto="el médico", categoria="personaje", hecho="El médico sin validar dijo algo.", cap_origen=0, sujeto_validado=False),
    ]))
    ctx = escritor.ensamblar_contexto(1, config, proyecto)
    t = ctx.texto
    assert "tercera_limitada" in t and "pasado" in t and "es-ES" in t  # RF-CFG-05
    assert "Nivel de tensión objetivo: 2 sobre 5" in t  # RF-05.1 tensión como objetivo
    assert "Capítulo de prueba 1" in t and "Objetivo narrativo del capítulo 1" in t  # RF-03.1 completa
    assert "oxígeno para 90 días" in t  # mundo entra siempre
    assert "El Puente perdió la iluminación" in t  # locación del capítulo
    assert "El médico sin validar" in t  # sujeto_validado = false entra siempre
    assert "Ilse escondió la llave" not in t  # personaje ausente: excluido (criterio d)
    assert "Bodega 4 está sellada" not in t  # otra locación
    assert "Dara es la única médica" not in t
    assert "### Kovacs" in t and "### Ilse" not in t  # fichas solo de los presentes
    assert "1200" in t and "1800" in t  # ±20 % de 1500
    assert ctx.tokens_estimados > 0 and ctx.metodo_estimacion in ("tiktoken", "heuristica")
    assert [h.hecho for h in ctx.hechos_inyectados] == [
        "La estación tiene oxígeno para 90 días.", "El Puente perdió la iluminación principal.", "El médico sin validar dijo algo.",
    ]


def test_ensamblar_contexto_ex03_y_ex04(proyecto, config):
    with pytest.raises(OutlineFaltanteError):
        escritor.ensamblar_contexto(31, config, proyecto)
    texto = ""
    from app.state import resumen_rodante as rr
    for n in range(1, 3):
        texto = rr.agregar(texto, n, "relleno " * 400, 2)
    repo.escribir_resumen_rodante(proyecto, texto)
    ctx = escritor.ensamblar_contexto(3, config.model_copy(update={"max_tokens_contexto_escritor": 900}), proyecto)
    assert ctx.excede_limite()
    recortado = escritor.recortar_resumen_rodante(ctx)
    assert recortado.resumen_recortado and recortado.tokens_estimados < ctx.tokens_estimados
    assert "## Capítulo 1" not in recortado.texto and "## Capítulo 2" in recortado.texto
    # el recorte nunca toca continuidad ni personajes
    assert len(recortado.hechos_inyectados) == len(ctx.hechos_inyectados)
    assert len(repo.leer_continuidad(proyecto)) == 3


def test_ensamblar_contexto_no_contiene_manuscrito(proyecto, config):
    capitulo = "Frase única del capítulo uno que no debe viajar al escritor jamás. " * 5
    repo.guardar_capitulo(proyecto, 1, capitulo)
    ctx = escritor.ensamblar_contexto(2, config, proyecto)
    for i in range(0, len(capitulo) - 20, 7):
        assert capitulo[i:i + 21] not in ctx.texto


def test_parser_retorno_escritor():
    r = escritor.parsear_retorno_escritor("cap_7.md · 2.940 palabras · personajes: Kovacs, Ilse · validado")
    assert (r.n, r.palabras_declaradas, r.personajes) == (7, 2940, ["Kovacs", "Ilse"])
    r = escritor.parsear_retorno_escritor("05_manuscrito/cap_12.md - 1500 palabras - personajes: Dara - validado\n")
    assert (r.n, r.palabras_declaradas) == (12, 1500)
    with pytest.raises(ContratoRetornoError, match="una línea"):
        escritor.parsear_retorno_escritor("cap_7.md · 2940 palabras · personajes: Kovacs · validado\nLa nave crujía en la oscuridad.")
    with pytest.raises(ContratoRetornoError, match="40 palabras"):
        escritor.parsear_retorno_escritor("cap_7.md · 2940 palabras · personajes: " + " ".join(["nombre"] * 45) + " · validado")
    with pytest.raises(ContratoRetornoError, match="forma"):
        escritor.parsear_retorno_escritor("Escribí el capítulo siete y quedó muy bien.")
    with pytest.raises(ContratoRetornoError):
        escritor.parsear_retorno_escritor("")


def test_evaluar_longitud_ex07(config):
    assert escritor.evaluar_longitud(1500, config) == (True, "")
    ok, msg = escritor.evaluar_longitud(900, config)
    assert not ok and "900 palabras" in msg and "1200 y 1800" in msg and "alargarlo" in msg
    assert "acortarlo" in escritor.evaluar_longitud(2000, config)[1]


def test_parsear_delta_y_validar(proyecto, config):
    bruto = """```json
{"personajes": {"Kovacs": {"estado_fisico": "Herido", "estado_psicologico": "Tenso", "secretos_que_conoce": ["x"], "ultima_aparicion": 1}},
 "hechos_nuevos": [{"sujeto": "Kovacs", "categoria": "personaje", "hecho": "Kovacs se hirió.", "cap_origen": 1},
                   {"sujeto": "la bodega", "categoria": "locacion", "hecho": "La bodega se abrió.", "cap_origen": 1}],
 "resumen_corto": "a\\nb\\nc"}
```"""
    delta = extractor.parsear_delta(bruto)
    registro = {"Kovacs", "Ilse", "Puente", "mundo"}
    v = extractor.validar_delta(delta, registro, config, 4)
    assert not v.requiere_regeneracion
    assert v.delta.personajes["Kovacs"].ultima_aparicion == 4
    assert [h.cap_origen for h in v.delta.hechos_nuevos] == [4, 4]
    assert [h.sujeto_validado for h in v.delta.hechos_nuevos] == [True, False]
    assert v.sujetos_no_validados == ["la bodega"]


def test_delta_invalido_es_ex01_y_tope_de_hechos(proyecto, config):
    with pytest.raises(EstadoInvalidoError, match="solo el JSON"):
        extractor.parsear_delta("Acá va el delta: {}")
    with pytest.raises(EstadoInvalidoError, match="DeltaExtraccion"):
        extractor.parsear_delta('{"personajes": {}, "hechos_nuevos": [{"sujeto": "x"}], "resumen_corto": "a"}')
    hechos = [{"sujeto": "mundo", "categoria": "mundo", "hecho": f"h{i}", "cap_origen": 1} for i in range(5)]
    delta = extractor.parsear_delta(json.dumps({"personajes": {}, "hechos_nuevos": hechos, "resumen_corto": "a\nb\nc"}))
    with pytest.raises(EstadoInvalidoError, match="tope es 4"):
        extractor.validar_delta(delta, {"mundo"}, config, 1)


def test_delta_con_personaje_no_previsto_ex08(config):
    delta = extractor.parsear_delta(json.dumps({
        "personajes": {"el capitán": {"estado_fisico": "a", "estado_psicologico": "b", "secretos_que_conoce": [], "ultima_aparicion": 1}},
        "hechos_nuevos": [], "resumen_corto": "a\nb\nc"}))
    v = extractor.validar_delta(delta, {"Kovacs", "mundo"}, config, 1)
    assert v.requiere_regeneracion and v.claves_no_previstas == ["el capitán"]


def test_prompt_extractor_lleva_registro_y_un_solo_capitulo(proyecto, config):
    p = extractor.preparar_prompt_extractor(3, config, proyecto)
    assert "05_manuscrito/cap_3.md" in p and "cap_2.md" not in p and "cap_1.md" not in p
    assert "Kovacs, Ilse, Dara" in p and "Puente, Bodega 4, Enfermería" in p
    assert "Máximo **4** hechos" in p


def test_qa_muestra_prompt_y_parser(proyecto, config):
    assert qa.capitulos_muestra(3, 3) == [1, 2, 3] and qa.capitulos_muestra(16, 8) == list(range(9, 17)) and qa.capitulos_muestra(2, 3) == [1, 2]
    prep = qa.preparar_corte(3, config, proyecto)
    assert prep.caps_muestra == [1, 2, 3]
    assert "oxígeno para 90 días" in prep.prompt and "superado_por" in prep.prompt  # log completo con superado_por visible
    assert "3 o más" in prep.prompt and "06_qa/reportes/qa_cap_3.json" in prep.prompt
    r = qa.parsear_retorno_qa("tiene_contradicciones: true\ncontradicciones: 1 · repeticiones: 0\nreporte: 06_qa/reportes/qa_cap_3.md\nvalidado")
    assert r.tiene_contradicciones
    with pytest.raises(ContratoRetornoError, match="líneas"):
        qa.parsear_retorno_qa("\n".join(["línea"] * 6))
    with pytest.raises(ContratoRetornoError, match="tiene_contradicciones"):
        qa.parsear_retorno_qa("todo bien")
    assert qa.entropia_bigramas("a b a b a b") < qa.entropia_bigramas("a b c d e f g")
