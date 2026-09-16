"""HarnessConfig §8.1: EX-05, RF-CFG-01/02/03/06, partición novela.json / ejecucion.json (§11.1)."""

import json

import pytest

from app.config import HarnessConfig, cargar_config, construir_config, hash_prompts
from app.errores import ConfiguracionInvalidaError
from app.rutas import Rutas

BASE_NOVELA = {"total_capitulos": 40, "palabras_por_capitulo": 3000, "idioma": "es-ES", "persona_narrativa": "tercera_limitada",
               "tiempo_verbal": "pasado", "ventana_resumen_rodante": 3, "cadencia_qa": 8, "max_tokens_contexto_escritor": 5000,
               "max_hechos_por_capitulo": 4}
BASE_EJEC = {"capitulos_por_tanda": 5, "max_llamadas_por_tanda": None, "registrar_uso": True}


def test_config_valida_y_rango_de_palabras():
    c = construir_config(BASE_NOVELA, BASE_EJEC)
    assert isinstance(c, HarnessConfig)
    assert c.rango_palabras() == (2400, 3600)


@pytest.mark.parametrize("campo,valor", [
    ("total_capitulos", 29), ("total_capitulos", 51), ("palabras_por_capitulo", 0),
    ("persona_narrativa", "segunda"), ("tiempo_verbal", "futuro"), ("cadencia_qa", 0), ("max_hechos_por_capitulo", 0),
])
def test_ex05_parametros_fuera_de_rango(campo, valor):
    novela = dict(BASE_NOVELA, **{campo: valor})
    with pytest.raises(ConfiguracionInvalidaError, match=campo):
        construir_config(novela, BASE_EJEC)


def test_ex05_capitulos_por_tanda_invalido_y_none_permitido():
    with pytest.raises(ConfiguracionInvalidaError, match="capitulos_por_tanda"):
        construir_config(BASE_NOVELA, dict(BASE_EJEC, capitulos_por_tanda=0))
    assert construir_config(BASE_NOVELA, dict(BASE_EJEC, capitulos_por_tanda=None)).capitulos_por_tanda is None
    # un tope mayor que los capítulos restantes es válido (RF-CFG-02)
    assert construir_config(BASE_NOVELA, dict(BASE_EJEC, capitulos_por_tanda=500)).capitulos_por_tanda == 500


def test_campo_en_archivo_equivocado_es_ex05():
    with pytest.raises(ConfiguracionInvalidaError, match="ejecucion.json"):
        construir_config(dict(BASE_NOVELA, capitulos_por_tanda=3), BASE_EJEC)
    with pytest.raises(ConfiguracionInvalidaError, match="INV-04"):
        construir_config(BASE_NOVELA, dict(BASE_EJEC, total_capitulos=40))
    with pytest.raises(ConfiguracionInvalidaError):
        construir_config(dict(BASE_NOVELA, desconocido=1), BASE_EJEC)


def test_rf_cfg_03_solo_capitulos_por_tanda_admite_override(proyecto):
    c = cargar_config(proyecto)
    assert c.capitulos_por_tanda == 3
    assert cargar_config(proyecto, capitulos_por_tanda=1).capitulos_por_tanda == 1
    with pytest.raises(ConfiguracionInvalidaError):
        cargar_config(proyecto, capitulos_por_tanda=0)


def test_archivo_faltante_o_corrupto_es_ex05(proyecto):
    rutas = Rutas(proyecto)
    rutas.ejecucion_json.write_text("{ no es json", encoding="utf-8")
    with pytest.raises(ConfiguracionInvalidaError, match="JSON"):
        cargar_config(proyecto)
    rutas.ejecucion_json.unlink()
    with pytest.raises(ConfiguracionInvalidaError, match="falta"):
        cargar_config(proyecto)


def test_hash_prompts_cambia_con_el_prompt_y_con_la_skill(proyecto):
    rutas = Rutas(proyecto)
    antes = hash_prompts(proyecto)
    assert set(antes) == {"escritor", "extractor", "qa"}
    (rutas.prompts_config / "escritor.md").write_text((rutas.prompts_config / "escritor.md").read_text(encoding="utf-8") + "\nx", encoding="utf-8")
    despues = hash_prompts(proyecto)
    assert despues["escritor"] != antes["escritor"] and despues["qa"] == antes["qa"]
    skill = rutas.skills / "criterios-qa" / "SKILL.md"
    skill.write_text(skill.read_text(encoding="utf-8") + "\ny", encoding="utf-8")
    assert hash_prompts(proyecto)["qa"] != antes["qa"]
