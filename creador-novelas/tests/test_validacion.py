"""Autovalidación (RF-08.4, §9): el validador que corre el agente es el mismo código que corre el harness.

`validar-delta` sobre un delta inválido devuelve el mismo error que `aplicar-delta`; `validar-capitulo` sobre un
borrador corto devuelve el mismo desvío que calcula EX-07. Los verbos son de solo lectura.
"""

import json

import pytest

from app import cli, validacion
from app.agents import escritor, extractor, qa
from app.errores import AutovalidacionFallidaError, ContratoRetornoError, EstadoInvalidoError
from app.orchestrator import checkpoint, loop
from app.rutas import Rutas
from app.state import repository as repo
from tests.conftest import AgentesDobles


def correr(capsys, *argv):
    codigo = cli.main(list(argv))
    salida = capsys.readouterr()
    return codigo, salida.out, salida.err


def _huella(raiz):
    rutas = Rutas(raiz)
    return {p.name: p.read_bytes() for p in (rutas.personajes, rutas.continuidad, rutas.resumen_rodante, rutas.manifest) if p.exists()}


# ---------- escritor ----------

def test_validar_capitulo_mismo_desvio_que_ex07(proyecto, config, capsys):
    rutas = Rutas(proyecto)
    codigo, out, _ = correr(capsys, "validar-capitulo", "1")
    assert codigo == 1 and "no existe 05_manuscrito/cap_1.md" in out
    rutas.capitulo(1).write_text("Kovacs " + "palabra " * 899, encoding="utf-8")  # 900 palabras
    antes = _huella(proyecto)
    codigo, out, _ = correr(capsys, "validar-capitulo", "1")
    assert codigo == 1 and "RESULTADO: invalido" in out
    _, esperado = escritor.evaluar_longitud(900, config)
    assert esperado in out  # el mismo desvío que calcula EX-07
    assert _huella(proyecto) == antes  # solo lectura: nada cambió
    # y registrar-escritor (el verbo que aplica) calcula exactamente el mismo desvío
    r = loop.evaluar_borrador(proyecto, config, 1)
    assert r.mensaje == esperado and r.reintentar


def test_validar_capitulo_personajes_en_escena_y_encabezados(proyecto, config, capsys):
    rutas = Rutas(proyecto)
    rutas.capitulo(1).write_text("# Título\n" + "palabra " * 1500, encoding="utf-8")  # sin Kovacs, con encabezado
    v = validacion.validar_capitulo(proyecto, config, 1)
    assert not v.valido
    assert any("encabezados" in e for e in v.errores) and any("Kovacs" in a for a in v.avisos)
    rutas.capitulo(1).write_text("Kovacs miró el panel. " + "palabra " * 1495, encoding="utf-8")
    v = validacion.validar_capitulo(proyecto, config, 1)
    assert v.valido and v.datos["personajes_detectados"] == ["Kovacs"]
    codigo, out, _ = correr(capsys, "validar-capitulo", "1")
    assert codigo == 0 and "RESULTADO: valido" in out
    # el verbo que aplica rechaza lo que no es longitud como EX-01, sin reintento
    rutas.capitulo(1).write_text("## Capítulo\nKovacs " + "palabra " * 1499, encoding="utf-8")
    with pytest.raises(EstadoInvalidoError, match="encabezados"):
        loop.evaluar_borrador(proyecto, config, 1)


# ---------- extractor ----------

def test_validar_delta_mismo_error_que_aplicar_delta(proyecto, config, capsys):
    rutas = Rutas(proyecto)
    repo.guardar_capitulo(proyecto, 1, "Kovacs " * 1500)
    codigo, out, _ = correr(capsys, "validar-delta", "1")
    assert codigo == 1 and "no existe 04_estado/deltas/delta_cap_1.json" in out
    hechos = [{"sujeto": "mundo", "categoria": "mundo", "hecho": f"h{i}", "cap_origen": 1} for i in range(5)]
    rutas.deltas_trabajo.mkdir(parents=True, exist_ok=True)
    rutas.delta(1).write_text(json.dumps({"personajes": {}, "hechos_nuevos": hechos, "resumen_corto": "a\nb\nc"}), encoding="utf-8")
    antes = _huella(proyecto)
    codigo, out, _ = correr(capsys, "validar-delta", "1")
    assert codigo == 1 and "tope es 4" in out
    with pytest.raises(EstadoInvalidoError, match="tope es 4") as e_aplicar:
        loop.aplicar_delta(proyecto, config, 1)
    assert str(e_aplicar.value) in out  # el mismo error, letra por letra
    assert _huella(proyecto) == antes
    # JSON roto: mismo mensaje por las dos vías
    rutas.delta(1).write_text("{ roto", encoding="utf-8")
    codigo, out, _ = correr(capsys, "validar-delta", "1")
    with pytest.raises(EstadoInvalidoError) as e2:
        loop.aplicar_delta(proyecto, config, 1)
    assert codigo == 1 and str(e2.value) in out


def test_validar_delta_avisa_ex08_y_sujetos_sin_validar_sin_invalidar(proyecto, config, capsys):
    rutas = Rutas(proyecto)
    rutas.deltas_trabajo.mkdir(parents=True, exist_ok=True)
    rutas.delta(1).write_text(json.dumps({
        "personajes": {"Vos": {"estado_fisico": "a", "estado_psicologico": "b", "secretos_que_conoce": [], "ultima_aparicion": 1}},
        "hechos_nuevos": [{"sujeto": "la bodega", "categoria": "locacion", "hecho": "Se abrió.", "cap_origen": 1}],
        "resumen_corto": "a\nb\nc"}), encoding="utf-8")
    v = validacion.validar_delta(proyecto, config, 1)
    assert v.valido and len(v.avisos) == 2 and any("EX-08" in a for a in v.avisos)
    codigo, out, _ = correr(capsys, "validar-delta", "1")
    assert codigo == 0 and "aviso: EX-08" in out and "RESULTADO: valido" in out
    r = loop.aplicar_delta(proyecto, config, 1)  # el harness sí lo trata: regenerar (EX-08, primer fallo)
    assert r.regenerar and r.claves_no_previstas == ["Vos"]


# ---------- qa ----------

def test_validar_reporte_mismo_error_que_cerrar_qa(proyecto, config, capsys):
    rutas = Rutas(proyecto)
    loop.ejecutar_tanda(config, proyecto, AgentesDobles(proyecto), capitulos_por_tanda=2)
    codigo, out, _ = correr(capsys, "validar-reporte", "2")
    assert codigo == 1 and "no existe 06_qa/reportes/qa_cap_2.json" in out
    rutas.reportes_qa.mkdir(parents=True, exist_ok=True)
    rutas.reporte_qa_json(2).write_text(json.dumps({"cap_corte": 3, "hallazgos": [], "tiene_contradicciones": False}), encoding="utf-8")
    codigo, out, _ = correr(capsys, "validar-reporte", "2")
    assert codigo == 1 and "cap_corte = 3" in out and "qa_cap_2.md" in out and "recursos_usados.json" in out
    with pytest.raises(EstadoInvalidoError) as e:
        loop.cerrar_qa(proyecto, config, 2)
    for error in validacion.validar_reporte(proyecto, 2).errores:
        assert error in str(e.value)
    rutas.reporte_qa_json(2).write_text(json.dumps({"cap_corte": 2, "hallazgos": [], "tiene_contradicciones": False}), encoding="utf-8")
    rutas.reporte_qa_md(2).write_text("# QA 2\n", encoding="utf-8")
    rutas.recursos_usados.write_text("[]", encoding="utf-8")
    codigo, out, _ = correr(capsys, "validar-reporte", "2")
    assert codigo == 0 and "RESULTADO: valido" in out and "contradicciones=0" in out


# ---------- contratos de retorno con `validado` y EX-10 ----------

def test_parser_extractor_linea_validada():
    r = extractor.parsear_retorno_extractor("delta_cap_4.json · 4 hechos · 2 personajes · validado")
    assert (r.n, r.hechos, r.personajes) == (4, 4, 2)
    r = extractor.parsear_retorno_extractor("04_estado/deltas/delta_cap_12.json - 1 hecho - 0 personajes - validado\n")
    assert (r.n, r.hechos, r.personajes) == (12, 1, 0)
    with pytest.raises(ContratoRetornoError, match="no devuelve el JSON"):
        extractor.parsear_retorno_extractor('{"personajes": {}, "hechos_nuevos": [], "resumen_corto": "a"}')
    with pytest.raises(ContratoRetornoError, match="una línea"):
        extractor.parsear_retorno_extractor("delta_cap_4.json · 4 hechos · 2 personajes · validado\nListo.")
    with pytest.raises(ContratoRetornoError, match="validado"):
        extractor.parsear_retorno_extractor("delta_cap_4.json · 4 hechos · 2 personajes")
    with pytest.raises(AutovalidacionFallidaError, match="EX-10.*extractor.*capítulo 4.*tope es 4"):
        extractor.parsear_retorno_extractor("delta_cap_4.json · NO VALIDADO · §11.6: el delta trae 5 hechos y el tope es 4")


def test_parser_escritor_exige_validado_y_detecta_ex10():
    with pytest.raises(ContratoRetornoError, match="validado"):
        escritor.parsear_retorno_escritor("cap_7.md · 2.940 palabras · personajes: Kovacs, Ilse")
    with pytest.raises(AutovalidacionFallidaError, match="EX-10.*escritor.*capítulo 7"):
        escritor.parsear_retorno_escritor("cap_7.md · NO VALIDADO · El borrador tiene 900 palabras")


def test_parser_qa_exige_validado_y_detecta_ex10():
    ok = "tiene_contradicciones: false\ncontradicciones: 0 · repeticiones: 2\nreporte: 06_qa/reportes/qa_cap_3.md\nvalidado"
    assert not qa.parsear_retorno_qa(ok).tiene_contradicciones
    with pytest.raises(ContratoRetornoError, match="validado"):
        qa.parsear_retorno_qa("tiene_contradicciones: false\ncontradicciones: 0 · repeticiones: 2\nreporte: 06_qa/reportes/qa_cap_3.md")
    with pytest.raises(AutovalidacionFallidaError, match="EX-10.*qa.*cap_corte"):
        qa.parsear_retorno_qa("tiene_contradicciones: false\nNO VALIDADO · RF-07.2: el reporte dice cap_corte = 2 y el corte es 3")


def test_aplicar_delta_y_cerrar_qa_aceptan_retorno_por_cli(proyecto, config, capsys):
    rutas = Rutas(proyecto)
    dobles = AgentesDobles(proyecto)
    codigo, out, _ = correr(capsys, "tanda", "iniciar")
    assert "RESULTADO: seguir siguiente=1" in out
    correr(capsys, "preparar-capitulo", "1")
    repo.guardar_capitulo(proyecto, 1, dobles.generar_capitulo(rutas.prompt_escritor(1).read_text(encoding="utf-8")))
    codigo, out, _ = correr(capsys, "registrar-escritor", "1", "cap_1.md · 1500 palabras · personajes: Kovacs · validado")
    assert codigo == 0 and "borrador_aceptado" in out
    rutas.delta(1).write_text(dobles.extraer("05_manuscrito/cap_1.md"), encoding="utf-8")
    codigo, _, err = correr(capsys, "aplicar-delta", "1", "--retorno", '{"personajes": {}}')
    assert codigo == 1 and "ContratoRetornoError" in err and checkpoint.leer_manifest(proyecto).ultimo_capitulo_cerrado == 0
    codigo, _, err = correr(capsys, "aplicar-delta", "1", "--retorno", "delta_cap_2.json · 2 hechos · 1 personajes · validado")
    assert codigo == 1 and "delta_cap_2.json" in err
    codigo, out, _ = correr(capsys, "aplicar-delta", "1", "--retorno", "delta_cap_1.json · 2 hechos · 1 personajes · validado")
    assert codigo == 0 and "capitulo_cerrado" in out
