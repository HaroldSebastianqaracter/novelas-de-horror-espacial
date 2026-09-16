"""Esquemas §4: validadores de outline (RF-03.1), hechos (INV-03), reporte QA (RF-07.2, RF-07.4), manifiesto (§5)."""

import pytest
from pydantic import ValidationError

from harness.schemas import HechoContinuidad, Manifest, Outline, ReporteQA
from tests.conftest import outline_de_prueba


def test_outline_valido_y_maximo_en_tercio_final():
    outline = Outline.model_validate(outline_de_prueba(30))
    assert len(outline) == 30
    assert outline.tension_maxima_en_tercio_final()
    assert outline.entrada(7).num == 7 and outline.entrada(31) is None


def test_outline_rechaza_num_con_huecos():
    datos = outline_de_prueba(30)
    datos[4]["num"] = 9
    with pytest.raises(ValidationError, match="consecutivo"):
        Outline.model_validate(datos)


def test_outline_rechaza_titulos_repetidos_o_vacios():
    datos = outline_de_prueba(30)
    datos[1]["titulo"] = datos[0]["titulo"]
    with pytest.raises(ValidationError, match="repetidos"):
        Outline.model_validate(datos)
    datos = outline_de_prueba(30)
    datos[2]["titulo"] = ""
    with pytest.raises(ValidationError):
        Outline.model_validate(datos)


def test_outline_rechaza_tension_fuera_de_rango():
    datos = outline_de_prueba(30)
    datos[0]["tension"] = 6
    with pytest.raises(ValidationError):
        Outline.model_validate(datos)


def test_tension_maxima_fuera_del_tercio_final_se_detecta():
    datos = outline_de_prueba(30)
    for d in datos:
        d["tension"] = 2
    datos[0]["tension"] = 5
    assert not Outline.model_validate(datos).tension_maxima_en_tercio_final()


def test_hecho_exige_cap_origen_y_defaults():
    h = HechoContinuidad(sujeto="Kovacs", categoria="personaje", hecho="Perdió el brazo.", cap_origen=7)
    assert h.sujeto_validado is True and h.superado_por is None and h.vigente()
    with pytest.raises(ValidationError):
        HechoContinuidad(sujeto="Kovacs", categoria="personaje", hecho="x")  # sin cap_origen (INV-03)
    with pytest.raises(ValidationError):
        HechoContinuidad(sujeto="Kovacs", categoria="otra", hecho="x", cap_origen=1)


def test_reporte_qa_contradiccion_exige_cap_origen_y_bandera_coherente():
    with pytest.raises(ValidationError, match="cap_origen"):
        ReporteQA.model_validate({"cap_corte": 8, "hallazgos": [{"tipo": "contradiccion", "descripcion": "x"}], "tiene_contradicciones": True})
    with pytest.raises(ValidationError, match="tiene_contradicciones"):
        ReporteQA.model_validate({"cap_corte": 8, "hallazgos": [{"tipo": "contradiccion", "descripcion": "x", "cap_origen": 3}], "tiene_contradicciones": False})
    r = ReporteQA.model_validate({"cap_corte": 8, "hallazgos": [{"tipo": "repeticion", "descripcion": "x"}], "tiene_contradicciones": False})
    assert r.conteo_por_tipo() == {"contradiccion": 0, "repeticion": 1}


def test_manifest_pausado_exige_reporte_y_detecta_edicion_manual():
    with pytest.raises(ValidationError):
        Manifest(ultimo_capitulo_cerrado=3, total_capitulos_esperado=30, estado="pausado_por_qa")
    m = Manifest(ultimo_capitulo_cerrado=3, total_capitulos_esperado=30, estado="en_progreso", reporte_qa_pendiente="qa_cap_3")
    assert m.editado_a_mano()
    assert m.capitulo_actual() == 4
    assert m.model_copy(update={"capitulo_activo": 2}).capitulo_actual() == 2
    with pytest.raises(ValidationError):
        Manifest(ultimo_capitulo_cerrado=0, total_capitulos_esperado=30, estado="abortado")
